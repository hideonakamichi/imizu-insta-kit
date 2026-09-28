#!/usr/bin/env python3
"""
ナレーション動画に BGM をミックスするスクリプト。
ffmpeg で BGM をループ再生し、指定 dB で重ねる。

参照: myuuu-io/youtube No.003_video-production-automation/tools/mix_bgm.py をそのまま流用
（解像度非依存のため改修不要）。

使い方:
  python3 mix_bgm.py --video reel_raw.mp4 --bgm content/bgm/bgm.mp3

オプション:
  --db -27        BGM 音量（デフォルト -27dB）
  --suffix _bgm   出力ファイル名のサフィックス（デフォルト _bgm）
  --out PATH      出力パス直接指定（--suffix より優先）
"""
import argparse
import subprocess
import sys
from pathlib import Path


def get_duration(filepath: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", filepath],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", type=Path, required=True, help="ナレーションのみの動画MP4")
    ap.add_argument("--bgm", type=Path, required=True, help="BGMファイル（mp3/wav）")
    ap.add_argument("--db", type=float, default=-27, help="BGM音量 dB（デフォルト -27）")
    ap.add_argument("--fadeout", type=float, default=2.0, help="動画終了前 BGM フェードアウト秒数（デフォルト 2.0）")
    ap.add_argument("--suffix", default="_bgm", help="出力サフィックス（デフォルト _bgm）")
    ap.add_argument("--out", type=Path, help="出力パス直接指定（省略時は --suffix から導出）")
    args = ap.parse_args()

    video = args.video.resolve()
    bgm = args.bgm.resolve()

    if not video.exists():
        print(f"エラー: 動画ファイルが見つかりません: {video}", file=sys.stderr)
        return 1
    if not bgm.exists():
        print(f"エラー: BGMファイルが見つかりません: {bgm}", file=sys.stderr)
        return 1

    out: Path
    if args.out:
        out = args.out.resolve()
    else:
        stem = video.stem
        suffix = video.suffix
        out = video.parent / f"{stem}{args.suffix}{suffix}"
    out.parent.mkdir(parents=True, exist_ok=True)

    video_duration = get_duration(str(video))
    bgm_duration = get_duration(str(bgm))
    loops = int(video_duration / bgm_duration) + 1

    fadeout_start = max(0.0, video_duration - args.fadeout)

    print(f"[mix] video={video.name} ({video_duration:.1f}s)")
    print(f"[mix] bgm={bgm.name} ({bgm_duration:.1f}s, ~{loops} loops)")
    print(f"[mix] BGM volume={args.db}dB, fadeout={args.fadeout:.1f}s (from {fadeout_start:.1f}s)")
    print(f"[mix] output={out.name}")

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video),
        "-stream_loop", "-1", "-i", str(bgm),
        "-filter_complex",
        # ナレーション動画(input 0)にBGM(input 1)を --db 指定の音量で重ねる。
        # amix デフォルトの normalize=1 だと入力数で割って音量が半分になるため normalize=0 を明示。
        # dropout_transition=0 でストリーム途切れ時のフェード変動も無効化（誤検知の影響を防ぐ）。
        f"[1:a]volume={args.db}dB,afade=t=out:st={fadeout_start}:d={args.fadeout}[bgm];"
        f"[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-ac", "2",
        "-shortest",
        str(out),
    ]

    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        print("ffmpeg エラー:", file=sys.stderr)
        print(result.stderr.decode()[-500:], file=sys.stderr)
        return 1

    out_duration = get_duration(str(out))
    size_mb = out.stat().st_size / (1024 * 1024)

    print(f"[ok] {out.name} ({out_duration:.1f}s, {size_mb:.1f} MB)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
