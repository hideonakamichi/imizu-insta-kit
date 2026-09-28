#!/usr/bin/env python3
"""make_post_folder.py - 合格したスライドとキャプションを、投稿用フォルダ post/ にそろえる

スマホで投稿するときに迷わないよう、スライドを表示順に 01.png, 02.png, … という名前でコピーし、
caption.txt を添える。同じ番号のスライドが何枚かある（評価で差し戻されて描き直した）ときは、
いちばん新しいもの（= 最後に合格したもの）を使う。

コピーするだけで、元のファイルは output/<フォルダ>/ にそのまま残る。

使い方（Mac は py を python3 に読み替える）:
  py .claude/skills/shared/scripts/make_post_folder.py --out-dir output/<YYYY-MM-DD>_<テーマスラッグ>
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

# Windows の Python は出力を cp932 で書くため、Claude Code（Git Bash）で読むと日本語が化ける。UTF-8 に固定する
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SLIDE_RE = re.compile(r"^slide_(\d+)_[a-z]+_(\d{8}_\d{6})\.png$")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True, help="carousel_spec.json とスライドがあるフォルダ")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = (PROJECT_ROOT / out_dir).resolve()
    spec_file = out_dir / "carousel_spec.json"
    caption = out_dir / "caption.txt"
    if not spec_file.is_file():
        print(f"[error] {spec_file} がありません", file=sys.stderr)
        return 1
    if not caption.is_file():
        print(f"[error] {caption} がありません（キャプションが合格してから実行してください）", file=sys.stderr)
        return 1

    total = len(json.loads(spec_file.read_text(encoding="utf-8"))["slides"])
    latest: dict[int, tuple[str, Path]] = {}
    for f in out_dir.iterdir():
        m = SLIDE_RE.match(f.name)
        if m:
            n, ts = int(m.group(1)), m.group(2)
            if n not in latest or ts >= latest[n][0]:
                latest[n] = (ts, f)
    missing = [n for n in range(1, total + 1) if n not in latest]
    if missing:
        print(f"[error] スライド {missing} の画像が見つかりません（全{total}枚構成）", file=sys.stderr)
        return 1

    post = out_dir / "post"
    if post.exists():
        shutil.rmtree(post)  # 作り直すときは前回の post/ を捨てる（元のスライドは残っている）
    post.mkdir()
    for n in range(1, total + 1):
        shutil.copy2(latest[n][1], post / f"{n:02d}.png")
    shutil.copy2(caption, post / "caption.txt")
    print(f"[ok] 投稿用フォルダをそろえました: {post}（画像{total}枚 + caption.txt）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
