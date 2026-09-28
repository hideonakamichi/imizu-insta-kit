"""whisper_srt.py - OpenAI Whisper API で SRT 直接取得

参照: myuuu-io/youtube .claude/skills/telop-srt-toolkit/scripts/whisper_srt.py をそのまま流用。

Usage:
    python3 whisper_srt.py --input AUDIO.mp3 --out RAW.srt [--env-file PATH]

Requires:
    OPENAI_API_KEY in environment or .env

Output format: 標準 SRT (response_format=srt)
"""

import argparse
import os
import sys
import urllib.request
import urllib.error
import mimetypes
from pathlib import Path


def load_env_file(path: str) -> None:
    """簡易 .env パーサ。OPENAI_API_KEY 等を環境変数にセット。"""
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v


def whisper_srt(audio_path: str, api_key: str, language: str = "ja", timeout: int = 900) -> str:
    """Whisper API を叩いて SRT を返す。multipart/form-data を手組み。"""
    url = "https://api.openai.com/v1/audio/transcriptions"
    boundary = "----WhisperBoundary" + os.urandom(8).hex()
    body = bytearray()

    def add_field(name: str, value: str) -> None:
        body.extend(f'--{boundary}\r\n'.encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(value.encode())
        body.extend(b'\r\n')

    add_field("model", "whisper-1")
    add_field("response_format", "srt")
    add_field("language", language)

    mime, _ = mimetypes.guess_type(audio_path)
    mime = mime or "audio/mpeg"
    filename = os.path.basename(audio_path)
    body.extend(f'--{boundary}\r\n'.encode())
    body.extend(
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode()
    )
    body.extend(f'Content-Type: {mime}\r\n\r\n'.encode())
    with open(audio_path, "rb") as f:
        body.extend(f.read())
    body.extend(f'\r\n--{boundary}--\r\n'.encode())

    req = urllib.request.Request(url, data=bytes(body), method="POST")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Content-Length", str(len(body)))

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="音声ファイル (mp3/wav 等、25MB以下推奨)")
    ap.add_argument("--out", required=True, help="出力 SRT パス")
    ap.add_argument("--env-file", default=".env", help=".env パス")
    ap.add_argument("--language", default="ja", help="言語コード (default: ja)")
    args = ap.parse_args()

    load_env_file(args.env_file)
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not found", file=sys.stderr)
        return 1

    size_mb = os.path.getsize(args.input) / 1024 / 1024
    if size_mb > 25:
        print(f"Error: {args.input} is {size_mb:.1f}MB > 25MB limit", file=sys.stderr)
        return 1

    try:
        srt = whisper_srt(args.input, api_key, language=args.language)
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode()}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    Path(args.out).write_text(srt, encoding="utf-8")
    print(f"wrote {args.out} ({len(srt.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
