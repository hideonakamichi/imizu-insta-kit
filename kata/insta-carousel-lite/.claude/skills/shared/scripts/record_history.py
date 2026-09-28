#!/usr/bin/env python3
"""record_history.py - 作ったカルーセルを logs/history.jsonl に記録する／取り消す

Lite 版は投稿を人が手で行うので、キットには「投稿されたか」が分からない。そこで
**合格して投稿用フォルダをそろえた時点で「使用済み」として記録する**。theme-picker はこの履歴を見て、
直近14日に使った節を選ばない（同じネタの繰り返しを防ぐ）。

作ったけれど投稿しなかった（没にした）ときは cancel で履歴から外す。外した節は、また選ばれるようになる。

1行1件の JSON Lines。日時は ISO8601（UTC）。

使い方（Mac は py を python3 に読み替える）:
  py .claude/skills/shared/scripts/record_history.py add --theme "<theme>" --out-dir output/<フォルダ> --slides 5
  py .claude/skills/shared/scripts/record_history.py cancel                   # いちばん新しい1件を外す
  py .claude/skills/shared/scripts/record_history.py cancel --theme "<theme>"  # そのテーマの最新1件を外す
  py .claude/skills/shared/scripts/record_history.py list                     # 直近10件を表示
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Windows の Python は出力を cp932 で書くため、Claude Code（Git Bash）で読むと日本語が化ける。UTF-8 に固定する
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[4]
HISTORY = PROJECT_ROOT / "logs" / "history.jsonl"


def load() -> list[dict]:
    """履歴を読む。壊れた行があれば止める（そのまま書き戻すと記録が失われるため）。"""
    if not HISTORY.exists():
        return []
    rows = []
    for n, line in enumerate(HISTORY.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            raise SystemExit(f"[error] {HISTORY} の {n} 行目が JSON として読めません。その行を直すか消してから、もう一度実行してください")
    return rows


def save(rows: list[dict]) -> None:
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    tmp = HISTORY.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    tmp.replace(HISTORY)


def cmd_add(args) -> int:
    rows = load()
    entry = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "theme": args.theme,
        "out_dir": args.out_dir,
        "slide_count": args.slides,
    }
    rows.append(entry)
    save(rows)
    print(f"[ok] 記録しました: {entry['theme']}（没にするときは cancel で外せます）")
    return 0


def cmd_cancel(args) -> int:
    rows = load()
    for i in range(len(rows) - 1, -1, -1):
        if args.theme is None or rows[i].get("theme") == args.theme:
            removed = rows.pop(i)
            save(rows)
            print(f"[ok] 履歴から外しました: {removed.get('theme')}（{removed.get('created_at', '')[:10]}）")
            return 0
    print("[error] 外す対象が見つかりません" + (f": {args.theme}" if args.theme else "（履歴が空です）"), file=sys.stderr)
    return 1


def cmd_list(_args) -> int:
    rows = load()
    if not rows:
        print("履歴はまだありません")
    for r in rows[-10:]:
        print(f"{r.get('created_at', '')[:10]}  {r.get('theme')}  → {r.get('out_dir')}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add", help="作ったカルーセルを記録する")
    a.add_argument("--theme", required=True, help="theme-picker の theme を一字一句そのまま")
    a.add_argument("--out-dir", required=True, help="投稿用フォルダ（output/ 以下）")
    a.add_argument("--slides", type=int, required=True, help="枚数")
    c = sub.add_parser("cancel", help="没にしたものを履歴から外す")
    c.add_argument("--theme", default=None, help="省略するといちばん新しい1件")
    sub.add_parser("list", help="直近10件を表示する")
    args = ap.parse_args()
    return {"add": cmd_add, "cancel": cmd_cancel, "list": cmd_list}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
