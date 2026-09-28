#!/usr/bin/env bash
# extract_audio.sh - 動画/音声 → Whisper API 最適化 mp3 (16kHz mono 96kbps)
#
# 参照: myuuu-io/youtube .claude/skills/telop-srt-toolkit/scripts/extract_audio.sh をそのまま流用。
#
# Usage: bash extract_audio.sh <INPUT> <OUTPUT_MP3>
# Example: bash extract_audio.sh reel_raw.mp4 reel_16k.mp3
#
# 出力サイズ目安: 96kbps。リールは30〜60秒なので1MB未満（Whisper API 25MB上限に対し余裕）
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <INPUT> <OUTPUT_MP3>" >&2
  exit 1
fi

INPUT="$1"
OUTPUT="$2"

if [[ ! -f "$INPUT" ]]; then
  echo "Error: input file not found: $INPUT" >&2
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "Error: ffmpeg not found in PATH" >&2
  exit 1
fi

ffmpeg -y -i "$INPUT" \
  -ar 16000 \
  -ac 1 \
  -b:a 96k \
  -codec:a libmp3lame \
  "$OUTPUT" 2>&1 | tail -3

SIZE_BYTES=$(stat -f%z "$OUTPUT" 2>/dev/null || stat -c%s "$OUTPUT")
SIZE_MB=$((SIZE_BYTES / 1024 / 1024))
echo "extracted: $OUTPUT (${SIZE_MB}MB)"

if [[ $SIZE_MB -ge 25 ]]; then
  echo "WARNING: output exceeds 25MB. Whisper API will reject. Consider lower bitrate." >&2
  exit 2
fi
