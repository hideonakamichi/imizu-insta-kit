#!/usr/bin/env python3
"""
extract_frames.py - 完成動画から評価用フレームを抽出する（新規スクリプト）

Phase 2の初回投稿で「見出しの左右見切れ」がevaluatorをすり抜けた。原因は、evaluatorが
実際の動画フレームではなくスライド元画像（クロップ前の1024x1536）で判定していたこと。
見切れは assemble_video.py の 9:16 変換クロップで発生するため、元画像では検出できない。

このスクリプトは reel_final.mp4 から一定間隔でフレームPNGを抽出する。オーケストレーターは
評価前に必ずこれを実行し、抽出フレームを evaluator（Opus, Readのみ）に渡すこと。
ffmpeg本体は許可リストに載せず、この決まった用途のスクリプトだけを許可する運用のための
ラッパーでもある。

使い方:
  python3 extract_frames.py --video OUTPUT_DIR/reel_final.mp4 --out-dir OUTPUT_DIR/frames
  python3 extract_frames.py --video ... --out-dir ... --interval 2   # 2秒ごと

出力:
  <out-dir>/frame_01.png, frame_02.png, ...（幅540pxに縮小。評価には十分で容量節約）
"""
import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", type=Path, required=True, help="フレームを抽出する動画")
    ap.add_argument("--out-dir", type=Path, required=True, help="フレームPNGの出力先")
    ap.add_argument("--interval", type=float, default=2.0,
                    help="抽出間隔（秒、既定2秒）。20秒リールで10枚。"
                         "evaluatorがショット末尾とセグメント境界を照合するため、4秒だと粗すぎる")
    ap.add_argument("--width", type=int, default=540, help="出力フレームの幅px（既定540）")
    args = ap.parse_args()

    if not args.video.exists():
        print(f"エラー: 動画が見つかりません: {args.video}", file=sys.stderr)
        return 1
    if args.interval <= 0:
        print("エラー: --interval は正の値で指定してください", file=sys.stderr)
        return 1

    args.out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(args.video),
        "-vf", f"fps=1/{args.interval},scale={args.width}:-1",
        str(args.out_dir / "frame_%02d.png"),
    ]
    res = subprocess.run(cmd, capture_output=True)
    if res.returncode != 0:
        print("[error] フレーム抽出に失敗しました", file=sys.stderr)
        print(res.stderr.decode()[-500:], file=sys.stderr)
        return 1

    frames = sorted(args.out_dir.glob("frame_*.png"))
    if not frames:
        print("[error] フレームが1枚も出力されませんでした", file=sys.stderr)
        return 1
    print(f"[ok] {len(frames)} frames -> {args.out_dir}")
    for f in frames:
        print(f"  {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
