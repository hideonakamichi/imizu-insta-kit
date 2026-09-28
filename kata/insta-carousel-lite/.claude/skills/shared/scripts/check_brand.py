#!/usr/bin/env python3
"""check_brand.py - config/brand.yaml が「設定済み」かを機械的に判定する

受け取ったままの雛形や、他人の設定のまま投稿を作ってしまう事故を防ぐため、
「未設定なら作らない」を AI への指示文に任せず、スクリプトで判定する。

呼ばれる場所:
  ・carousel スキルの最初（失敗したら、その回は何も作らずに終わる）
  ・brand-setup スキルの最後（設定が済んだかの確認）

判定内容:
  ・YAML として読めて、必須の項目が空でないこと
  ・雛形のプレースホルダー（値の全体が「（…）」の形、`#（…）`、`@your_account`）が1つも残っていないこと
    ※ 値の一部に全角カッコを含むだけ（例「初回相談（無料）」）はプレースホルダーではない

使い方:
  py .claude/skills/shared/scripts/check_brand.py          # 問題が無ければ exit 0（Mac は python3）
  py .claude/skills/shared/scripts/check_brand.py --json   # 結果を JSON で出す
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

# Windows の Python は出力を cp932 で書くため、Claude Code（Git Bash）で読むと日本語が化ける。UTF-8 に固定する
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[4]
BRAND_FILE = PROJECT_ROOT / "config" / "brand.yaml"

PLACEHOLDER_RE = re.compile(r"^\s*#?（.*）\s*$", re.S)
PLACEHOLDER_LITERALS = {"@your_account"}
# (キーの道筋, 説明, 型)。型: "str"=空白を除いて空でない文字列 / "strlist"=そういう文字列だけの空でないリスト
# offer.* は offer.enabled が true のときだけ必須
REQUIRED = [
    (("account", "handle"), "Instagramのハンドル名", "str"),
    (("account", "name"), "アカウント名", "str"),
    (("account", "purpose"), "アカウントの目的", "str"),
    (("audience", "who"), "対象読者", "str"),
    (("audience", "pains"), "読者の悩み", "strlist"),
    (("tone", "voice"), "基本の声色", "str"),
    (("tone", "policy"), "守るルール", "strlist"),
    (("hashtags", "core"), "軸ハッシュタグ", "strlist"),
    (("design", "palette", "bg"), "背景色", "hex"),
    (("design", "palette", "text"), "文字色", "hex"),
    (("design", "palette", "accent"), "アクセント色", "hex"),
]
REQUIRED_IF_OFFER = [
    (("offer", "name"), "オファーの名前", "str"),
    (("offer", "cta_line"), "誘導文", "str"),
]
# 真偽値でなければならない項目。YAML の `enabled: "false"` は文字列で、Python では真と評価される
# （止めたつもりの機能が有効になる）ので、型そのものを見る
BOOL_KEYS = [("offer", "enabled"), ("content_sources", "html", "enabled")]


def _is_text(v) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _type_ok(v, kind: str) -> bool:
    if kind == "str":
        return _is_text(v)
    if kind == "strlist":
        return isinstance(v, list) and bool(v) and all(_is_text(x) for x in v)
    if kind == "hex":
        return isinstance(v, str) and bool(re.fullmatch(r"#[0-9A-Fa-f]{6}", v.strip()))
    return False


def _get(data, path):
    for key in path:
        if not isinstance(data, dict) or key not in data:
            return None
        data = data[key]
    return data


def _walk(node, path=()):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _walk(v, path + (str(k),))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk(v, path + (f"[{i}]",))
    else:
        yield path, node


def check(brand_file: Path = BRAND_FILE) -> list[str]:
    """問題点のリストを返す（空なら設定済み）。"""
    if not brand_file.is_file():
        return [f"{brand_file} がありません"]
    try:
        data = yaml.safe_load(brand_file.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        return [f"brand.yaml を YAML として読めません: {e}"]
    if not isinstance(data, dict):
        return ["brand.yaml の最上位が「キー: 値」の形になっていません"]

    problems = []
    required = list(REQUIRED)
    offer = data.get("offer")
    if isinstance(offer, dict) and offer.get("enabled") is True:
        required += REQUIRED_IF_OFFER
    kinds = {"str": "空でない文字列", "strlist": "空でない文字列のリスト", "hex": "#RRGGBB の色"}
    for path, label, kind in required:
        if not _type_ok(_get(data, path), kind):
            problems.append(f"{'.'.join(path)}（{label}）は{kinds[kind]}で書いてください")
    for path in BOOL_KEYS:
        v = _get(data, path)
        if v is not None and not isinstance(v, bool):
            problems.append(f"{'.'.join(path)} は true か false（引用符なし）で書いてください: {v!r}")
    axes = data.get("strategy_axes")
    if not isinstance(axes, list) or not axes:
        problems.append("strategy_axes（テーマ軸）が空です")
    else:
        for i, ax in enumerate(axes):
            if not isinstance(ax, dict) or not _is_text(ax.get("key")) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", str(ax.get("key"))):
                problems.append(f"strategy_axes[{i}].key は半角小文字・数字・ハイフンで書いてください")
            elif not isinstance(ax.get("keywords", []), list) or not all(_is_text(k) for k in ax.get("keywords", [])):
                problems.append(f"strategy_axes[{i}].keywords は文字列のリストで書いてください")
        keys = [ax.get("key") for ax in axes if isinstance(ax, dict)]
        if len(keys) != len(set(keys)):
            problems.append("strategy_axes の key が重複しています")
    offer_on = isinstance(offer, dict) and offer.get("enabled") is True
    for path, value in _walk(data):
        if not offer_on and path[:1] == ("offer",):
            continue  # オファーを使わない設定なら、雛形のまま残っていても止めない
        if isinstance(value, str) and (PLACEHOLDER_RE.match(value) or value.strip() in PLACEHOLDER_LITERALS):
            problems.append(f"{'.'.join(path)} が雛形のままです: {value.strip()[:30]}")
    handle = _get(data, ("account", "handle"))
    if isinstance(handle, str) and handle.strip() and not re.fullmatch(r"@[A-Za-z0-9._]{1,30}", handle.strip()):
        problems.append(f"account.handle は @ から始まる Instagram のユーザーネームにしてください: {handle.strip()[:30]}")
    return problems


def brand_handle(brand_file: Path = BRAND_FILE) -> str:
    """account.handle を @ なし・小文字で返す（読めなければ空文字）。"""
    try:
        data = yaml.safe_load(brand_file.read_text(encoding="utf-8")) or {}
        return str(_get(data, ("account", "handle")) or "").strip().lstrip("@").lower()
    except Exception:
        return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    problems = check()
    if args.json:
        print(json.dumps({"ok": not problems, "problems": problems}, ensure_ascii=False, indent=2))
    elif problems:
        print("[error] config/brand.yaml の設定が終わっていないため、投稿を作りません:", file=sys.stderr)
        for p in problems[:20]:
            print(f"  ・{p}", file=sys.stderr)
        if len(problems) > 20:
            print(f"  …ほか {len(problems) - 20} 件", file=sys.stderr)
        print("  Claude Code で「brand-setup スキルで設定して」と頼むと、対話で埋められます。", file=sys.stderr)
    else:
        print("[ok] brand.yaml は設定済みです")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
