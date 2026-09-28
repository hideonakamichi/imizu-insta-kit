#!/usr/bin/env python3
"""audit_posts.py の在庫計算まわりの回帰テスト。

ネタ切れ警告は「鳴らなくても気づけない」種類の機能なので、
audit_posts.py を触ったら必ずこれを回す。

    python3 .claude/skills/system-healthcheck/scripts/audit_posts_selftest.py
"""
import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT = Path(__file__).with_name("audit_posts.py")
spec = importlib.util.spec_from_file_location("audit_posts", SCRIPT)
ap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ap)

failures = 0


def check(name: str, got, want) -> None:
    global failures
    ok = got == want
    failures += not ok
    print(f"[{'ok' if ok else 'NG'}] {name} → {got!r}" + ("" if ok else f" (期待: {want!r})"))


# --- テーマ同一判定 -------------------------------------------------------
check("完全一致", ap._same_theme("机の上に置く物の決め方", "机の上に置く物の決め方"), True)
check("前後の空白は無視", ap._same_theme("  机の上に置く物の決め方  ", "机の上に置く物の決め方"), True)
check(
    "記録側が途中で切れていても同一とみなす",
    ap._same_theme("「机まわりの整え方」より：手順2 充電ケーブルを1か所に集める", "「机まわりの整え方」より：手順2"),
    True,
)
check("11文字以下の一致は別テーマ扱い", ap._same_theme("充電ケーブルを1か所に集める手順とコツ", "充電ケーブルを1か所"), False)
check(
    "語彙が近いだけの別テーマ",
    ap._same_theme("「机まわりの整え方」より：手順1 机の上に置く物を3つに絞る", "「机まわりの整え方」より：手順3 終業の合図を物で作る"),
    False,
)

# --- 在庫カウント（クールダウン窓） ---------------------------------------
now = datetime(2026, 9, 20, tzinfo=timezone.utc)
import tempfile as _tf
_td = _tf.TemporaryDirectory()
_themes = Path(_td.name) / "themes.md"
_themes.write_text("## ストック\n\n" + "".join(f"- [how-to] テスト用のテーマその{i}：在庫計算の確認に使う\n" for i in range(1, 6)), encoding="utf-8")
_orig_themes = ap.THEMES_FILE
ap.THEMES_FILE = _themes  # 利用者の themes.md の中身（空のこともある）に依存させない
bodies = ap.load_theme_bodies()
assert len(bodies) == 5, "テスト用 themes.md を読めていない"
sample = bodies[0]


def posted(theme: str, days_ago: int) -> dict:
    return {"theme": theme, "posted_at": (now - timedelta(days=days_ago)).isoformat()}


total, avail = ap.count_remaining_themes([], now)
check("投稿ゼロなら在庫＝総数", avail, total)

_, avail = ap.count_remaining_themes([posted(sample, 1)], now)
check("クールダウン内の使用は在庫から引く", avail, total - 1)

_, avail = ap.count_remaining_themes([posted(sample, ap.THEME_COOLDOWN_DAYS + 1)], now)
check("クールダウンを過ぎたテーマは在庫に戻る", avail, total)

_, avail = ap.count_remaining_themes([posted(sample, 1), posted(sample, 2)], now)
check("同じテーマを2回使っても二重に引かない", avail, total - 1)

_, avail = ap.count_remaining_themes([posted("themes.mdに無いテーマ", 1)], now)
check("themes.md に無いテーマは在庫を減らさない", avail, total)

_, avail = ap.count_remaining_themes([{"theme": sample, "posted_at": "壊れた日付"}], now)
check("日付が壊れた記録は無視する", avail, total)

# --- コードブロック内の例示行を在庫に数えない -----------------------------
import tempfile
with tempfile.TemporaryDirectory() as td:
    tmp = Path(td) / "themes.md"
    tmp.write_text("## ストック\n\n- [how-to] 本物のテーマ\n\n```\n- [how-to] コードブロック内の例示\n```\n", encoding="utf-8")
    orig = ap.THEMES_FILE
    ap.THEMES_FILE = tmp
    try:
        check("コードブロック内の例示行は在庫に含めない", ap.load_theme_bodies(), ["本物のテーマ"])
    finally:
        ap.THEMES_FILE = orig

# --- schedule.yaml からの想定回数 ------------------------------------------
monday = datetime(2026, 9, 21, 3, 0, tzinfo=timezone.utc)  # どのタイムゾーンでも月曜
exp = {"banner": [({0, 2, 4}, 1)], "reel": [(set(range(7)), 1), ({3}, 2)]}
got = ap.expected_counts_for(exp, monday)
check("週3回のジョブは7日で3本", got["banner"], 3)
check("同じ pipeline の複数ジョブは足し合わせる（毎日1本＋木曜2本＝9本）", got["reel"], 9)
check("実際の config/schedule.yaml が読める", isinstance(ap.load_expected_schedule(), dict), True)

ap.THEMES_FILE = _orig_themes
_td.cleanup()
print()
if failures:
    print(f"{failures} 件 失敗")
    sys.exit(1)
print("チェックはすべて期待どおり")
