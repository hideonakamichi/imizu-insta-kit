#!/usr/bin/env python3
"""
スライド画像（slides/slide_NNN.png）と音声（audio/slide_NNN.mp3）を ffmpeg で結合し
output.mp4 を生成する。

参照: myuuu-io/youtube No.003_video-production-automation/tools/assemble_video.py を
縦型リール（9:16、1080x1920）向けに解像度定数だけ変更したもの。

## 命名規則（絶対ルール）

slides.json の slide_id を SOT とする。画像も音声も同じ slide_id を継承し、
ファイル名は必ず以下の形式：

- 画像: slides/slide_{slide_id:03d}.png
- 音声: audio/slide_{slide_id:03d}.mp3

slide_id がズレることはない（ズレたら check_consistency.py で検出される）。

## 使い方

  python3 assemble_video.py \\
    --slides-json output/JOB/slides.json \\
    --slides-dir  output/JOB/slides \\
    --audio-dir   output/JOB/audio \\
    --out         output/JOB/reel_raw.mp4
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
SILENT_DURATION_SEC = 3


def probe_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    return float(r.stdout.strip())


def build_segment(image: Path, audio: Path | None, out_seg: Path) -> None:
    # `-shortest` は AAC encoder の lookahead delay などで video stream が
    # 音声より数百ms 〜 数秒長く出力される既知の挙動がある。これが累積すると
    # スライドの変わり目に無音＋静止画が残るバグになるため、必ず音声長を
    # ffprobe で実測し `-t` で明示的に時間を切る。
    # scale後にcrop/padで正確に1080x1920へ整形（元画像が2:3のため若干の帯が出る場合がある）。
    vf = (
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT}"
    )
    if audio and audio.exists():
        audio_dur = probe_duration(audio)
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-loop", "1", "-i", str(image),
            "-i", str(audio),
            "-t", f"{audio_dur:.6f}",
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "192k", "-ac", "2",
            "-pix_fmt", "yuv420p",
            "-vf", vf,
            str(out_seg),
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-loop", "1", "-i", str(image),
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", str(SILENT_DURATION_SEC),
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-vf", vf,
            str(out_seg),
        ]
    res = subprocess.run(cmd, capture_output=True)
    if res.returncode != 0:
        print(f"[error] ffmpeg failed for {image.name}", file=sys.stderr)
        print(res.stderr.decode()[-500:], file=sys.stderr)
        sys.exit(1)

    # 検証：生成されたセグメントの video/audio 長が音声長と一致するかチェック
    if audio and audio.exists():
        seg_dur = probe_duration(out_seg)
        diff = abs(seg_dur - audio_dur)
        if diff > 0.10:  # 100ms 以上ズレたら異常
            print(f"[error] segment duration mismatch: audio={audio_dur:.3f}s segment={seg_dur:.3f}s diff={diff:.3f}s",
                  file=sys.stderr)
            sys.exit(1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slides-json", type=Path, required=True)
    ap.add_argument("--slides-dir", type=Path, required=True)
    ap.add_argument("--audio-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    with args.slides_json.open() as f:
        slides_data = json.load(f)
    slides = slides_data["slides"]
    total = len(slides)

    args.out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="assemble_") as tmp:
        tmp_dir = Path(tmp)
        segments: list[Path] = []
        for i, slide in enumerate(slides, start=1):
            sid = slide["slide_id"]
            image = args.slides_dir / f"slide_{sid:03d}.png"
            if not image.exists():
                print(f"[skip] {image.name} not found, skipping slide_id={sid}", file=sys.stderr)
                continue
            audio_path = args.audio_dir / f"slide_{sid:03d}.mp3"
            audio = audio_path if audio_path.exists() else None
            seg = tmp_dir / f"seg_{sid:03d}.mp4"

            audio_label = audio.name if audio else "(silent 3s)"
            print(f"[{i:3d}/{total}] slide_{sid:03d}.png + {audio_label}")

            build_segment(image, audio, seg)
            segments.append(seg)

        if not segments:
            print("[error] no segments to concat", file=sys.stderr)
            return 1

        concat_list = tmp_dir / "concat.txt"
        with concat_list.open("w") as f:
            for s in segments:
                f.write(f"file '{s}'\n")

        print(f"[concat] {len(segments)} segments -> {args.out.name}")
        res = subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-f", "concat", "-safe", "0",
                "-i", str(concat_list),
                "-c", "copy",
                str(args.out),
            ],
            capture_output=True,
        )
        if res.returncode != 0:
            print("[error] concat failed", file=sys.stderr)
            print(res.stderr.decode()[-500:], file=sys.stderr)
            return 1

    dur = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(args.out)],
        capture_output=True, text=True,
    ).stdout.strip()
    size_mb = args.out.stat().st_size / (1024 * 1024)
    print(f"[ok] {args.out.name} ({float(dur):.1f}s, {size_mb:.1f} MB)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
