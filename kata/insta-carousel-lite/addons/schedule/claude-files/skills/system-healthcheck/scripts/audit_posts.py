#!/usr/bin/env python3
"""
audit_posts.py - 直近1週間の投稿成否集計・ネタ帳残数チェック（新規スクリプト）

logs/posted.jsonl を集計し、想定スケジュール（config/schedule.yaml。launchd の登録と同じファイル）
に対して投稿の欠落がないかを検知する。content/themes.md の残数もあわせて報告する。

使い方:
  python3 audit_posts.py
"""
import json
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[3]
POSTED_LOG = PROJECT_ROOT / "logs" / "posted.jsonl"
THEMES_FILE = PROJECT_ROOT / "content" / "themes.md"
ARTICLE_INDEX_STATE = PROJECT_ROOT / "logs" / "article_index_state.json"

SCHEDULE_FILE = PROJECT_ROOT / "config" / "schedule.yaml"
LOOKBACK_DAYS = 7
# theme-picker が「直近14日以内に使ったテーマ」を避ける仕様なので、在庫もその窓で数える
THEME_COOLDOWN_DAYS = 14
# ネタ切れ警告の下限。実際の閾値は「1週間ぶんの投稿数」とこの値の大きい方
# （週次点検の間隔は7日なので、警告が出てから補充するまでに1週間の猶予を残す）
THEME_LOW_STOCK_MIN = 5
# datetime.weekday() は 0=月 … 6=日
WEEKDAY_INDEX = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def load_expected_schedule() -> dict:
    """config/schedule.yaml から {pipeline: [(曜日の集合, 1日あたりの回数), ...]} を作る。

    スケジュールの正は schedule.yaml だけ（launchd の登録も同じファイルから生成する）。
    以前は plist とこのスクリプトに同じ曜日を二重に書いていて、片方だけ直してズレた結果
    「投稿漏れ」を誤検知していた。realistic 便のように、複数のジョブが同じ pipeline に
    記録されることがあるので、ジョブ単位で持って足し合わせる。
    """
    sys.path.insert(0, str(PROJECT_ROOT / ".claude" / "skills" / "shared" / "scripts"))
    from schedule_config import load_jobs  # 検証は launchd の登録と同じ関数で行う（enabled は真偽値のみ）
    expected: dict = {}
    for job in load_jobs().values():
        if not job["enabled"] or not job["pipeline"]:
            continue
        days = {WEEKDAY_INDEX[w] for w in job["weekdays"]} or set(range(7))
        expected.setdefault(job["pipeline"], []).append((days, len(job["times"])))
    return expected


def expected_counts_for(expected: dict, now: datetime) -> dict:
    """直近 LOOKBACK_DAYS 日で、スケジュールどおりなら何本投稿されているはずか。"""
    # launchd はMacのローカル時刻で発火するので、曜日もローカル時刻で数える
    local_now = now.astimezone()
    counts = {}
    for pipeline, jobs in expected.items():
        n = 0
        for i in range(LOOKBACK_DAYS):
            day = (local_now - timedelta(days=i)).weekday()
            n += sum(per_day for days, per_day in jobs if day in days)
        counts[pipeline] = n
    return counts


def load_posted() -> list[dict]:
    if not POSTED_LOG.exists():
        return []
    entries = []
    for line in POSTED_LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def load_theme_bodies() -> list[str]:
    """themes.md のテーマ本文を列挙する。

    テーマ行は `- [軸] 本文` の形式。ただしコードブロック（``` で囲まれた範囲）内の
    行は書き方の例示なので除外する。除外しないと、説明用のサンプル行まで在庫として
    数えてしまい、ネタ切れ警告が出なくなる。
    戻り値は `[軸]` を落とした本文（theme-picker が posted.jsonl に記録する形）。
    """
    if not THEMES_FILE.exists():
        return []
    bodies = []
    in_fence = False
    for line in THEMES_FILE.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = re.match(r"^\s*-\s+(?:\[[^\]]*\]\s*)?(\S.*)$", line)
        if m:
            bodies.append(m.group(1).strip())
    return bodies


def parse_dt(value) -> datetime | None:
    """posted.jsonl の posted_at を tz-aware な datetime にする。不正値は None。"""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _same_theme(a: str, b: str) -> bool:
    """テーマ本文の同一判定。

    完全一致に加えて、片方がもう片方の先頭12文字以上の接頭辞になっている場合も
    同じテーマとみなす（投稿時に言い換え・省略されて記録されることがあるため）。
    取りこぼすと使用済みを在庫として数え、警告が鳴らなくなる側に倒れる。
    """
    a, b = a.strip(), b.strip()
    if a == b:
        return True
    short, long = sorted((a, b), key=len)
    return len(short) >= 12 and long.startswith(short)


def count_remaining_themes(posted: list[dict], now: datetime) -> tuple[int, int]:
    """(在庫総数, 直近 THEME_COOLDOWN_DAYS で未使用の件数) を返す。

    theme-picker は直近14日以内に使ったテーマを避けるため、後者が「いま選べる件数」。
    総数だけを数えると使用済みが減らず、ネタ切れ警告が永久に鳴らない。
    """
    bodies = load_theme_bodies()
    cutoff = now - timedelta(days=THEME_COOLDOWN_DAYS)
    recent_themes = []
    for e in posted:
        dt = parse_dt(e.get("posted_at"))
        if e.get("theme") and dt and dt >= cutoff:
            recent_themes.append(e["theme"])
    available = [b for b in bodies if not any(_same_theme(b, t) for t in recent_themes)]
    return len(bodies), len(available)


def article_index_status() -> dict:
    """記事索引（build_article_index.py）の更新成否。

    更新に失敗しているあいだ、投稿パイプラインは起動時に中止される（bin/run-agent.sh）。
    ここで見て、投稿が止まっている原因として週次レポートに出す。
    """
    if not ARTICLE_INDEX_STATE.exists():
        return {"ok": False, "last_ok_at": None, "last_error": "記録なし（build_article_index.py が一度も成功していない）"}
    try:
        st = json.loads(ARTICLE_INDEX_STATE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"ok": False, "last_ok_at": None, "last_error": "article_index_state.json が壊れている"}
    # last_ok_at は ISO 形式の日時文字列のはず。数値・真偽値・解析できない文字列は成功記録とみなさない
    if not isinstance(st, dict) or not isinstance(st.get("last_ok_at"), str) or parse_dt(st["last_ok_at"]) is None:
        return {"ok": False, "last_ok_at": None, "last_error": "成功の記録がない（型が不正、または一度も成功していない）"}
    return {
        "ok": not st.get("last_error"),
        "last_ok_at": st.get("last_ok_at"),
        "last_error_at": st.get("last_error_at"),
        "last_error": st.get("last_error"),
    }


def main() -> int:
    entries = load_posted()
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=LOOKBACK_DAYS)

    recent = []
    for e in entries:
        try:
            posted_at = datetime.fromisoformat(e["posted_at"])
        except (KeyError, ValueError):
            continue
        if posted_at.tzinfo is None:
            posted_at = posted_at.replace(tzinfo=timezone.utc)
        if posted_at >= since:
            recent.append({**e, "_dt": posted_at})

    by_pipeline = Counter(e["pipeline"] for e in recent)

    # 想定回数（schedule.yaml どおりなら、過去7日間で何本投稿されているはずか）
    try:
        expected_counts = expected_counts_for(load_expected_schedule(), now)
        schedule_error = None
    except Exception as e:  # schedule.yaml が無い・壊れている。欠落検知はできないが、ほかの点検は続ける
        expected_counts, schedule_error = {}, f"{type(e).__name__}: {e}"

    gaps = {
        pipeline: max(0, n - by_pipeline.get(pipeline, 0))
        for pipeline, n in expected_counts.items()
    }

    total_themes, remaining_themes = count_remaining_themes(entries, now)
    # 1週間ぶんの投稿数を下回ったら警告（次の点検までに選べるネタが尽きうる）
    weekly_posts = sum(expected_counts.values())
    low_stock_threshold = max(THEME_LOW_STOCK_MIN, weekly_posts)
    low_stock = remaining_themes <= low_stock_threshold

    summary = {
        "period_days": LOOKBACK_DAYS,
        "posted_counts": dict(by_pipeline),
        "expected_counts": expected_counts,
        "gaps": gaps,
        "has_missing_posts": any(g > 0 for g in gaps.values()),
        "total_themes": total_themes,
        "remaining_themes": remaining_themes,  # 直近14日で未使用＝いま選べる件数
        "theme_cooldown_days": THEME_COOLDOWN_DAYS,
        "low_stock_threshold": low_stock_threshold,
        "low_stock_warning": low_stock,
        "article_index": article_index_status(),
        "schedule_error": schedule_error,  # null 以外なら config/schedule.yaml を直す
    }

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
