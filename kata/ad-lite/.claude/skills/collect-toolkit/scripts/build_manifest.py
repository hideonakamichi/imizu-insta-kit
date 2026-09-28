"""手で書き写した競合広告コピー(competitors.md)を manifest.jsonl に変換する。

入力: data/<プロジェクト>/competitors.md（`## 広告主名` の見出し＋本文を `---` で区切った形式）
出力: 同じフォルダの manifest.jsonl（analyze-toolkit がそのまま読める形式）

使い方:
  python build_manifest.py --md data/my-project/competitors.md
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Windows の Python は出力を cp932 で書くため、Claude Code（Git Bash）で読むと日本語が化ける。UTF-8 に固定する
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

MARKER = "<!-- ここから下に、実際に見つけた広告を書き写してください -->"
PLACEHOLDER_ADVERTISER = "（広告主名をここに）"
PLACEHOLDER_BODY = "（コピー本文をここに）"


def parse_competitors(text: str) -> list[dict]:
    if MARKER in text:
        text = text.split(MARKER, 1)[1]

    # "## 見出し" で分割し、各ブロックを最初の "---" までで区切る
    blocks = re.split(r"^##\s+", text, flags=re.MULTILINE)[1:]
    entries: list[dict] = []
    for block in blocks:
        body_part = block.split("\n---", 1)[0]
        lines = body_part.splitlines()
        if not lines:
            continue
        advertiser = lines[0].strip()
        body = "\n".join(lines[1:]).strip()
        if not advertiser or not body:
            continue
        if advertiser == PLACEHOLDER_ADVERTISER or body == PLACEHOLDER_BODY:
            continue
        entries.append({"advertiser": advertiser, "body_text": body})
    return entries


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", required=True, help="competitors.md のパス")
    args = ap.parse_args()

    md_path = Path(args.md)
    if not md_path.exists():
        print(f"[!] not found: {md_path}", file=sys.stderr)
        return 2

    text = md_path.read_text(encoding="utf-8")
    entries = parse_competitors(text)

    out_path = md_path.parent / "manifest.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for i, e in enumerate(entries, 1):
            record = {
                "library_id": f"manual_{i:03d}",
                "advertiser": e["advertiser"],
                "body_text": e["body_text"],
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(f"  [{i}] {e['advertiser']}: {e['body_text'][:40]}")

    print(f"[+] 件数: {len(entries)}")
    print(f"[+] manifest: {out_path}")
    if len(entries) < 3:
        print("[!] 3件未満です。competitors.md に書き足してからもう一度実行してください。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
