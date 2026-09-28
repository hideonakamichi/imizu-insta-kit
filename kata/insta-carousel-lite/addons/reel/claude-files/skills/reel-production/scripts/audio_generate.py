#!/usr/bin/env python3
"""
Fish Audio で WAV 経由 → MP3 にエンコードする音声生成スクリプト
（プツプツ対策で MP3 ストリーミングではなく WAV ストリーミングを使う）

参照: myuuu-io/youtube No.003_video-production-automation/tools/audio_generate.py を流用。
env読込のみプロジェクトルートの .env を使うよう変更（元は .env.local）。
本プロジェクト向けに --tempo（倍速化）オプションを追加（リールのテンポ改善用。
atempoフィルタなのでピッチは変わらない）。

使い方:
  単発:
    python3 audio_generate.py --text "テスト" --out out.mp3

  複数 (slide_texts.json):
    python3 audio_generate.py --texts slide_texts.json --out-dir audio/
    python3 audio_generate.py --texts slide_texts.json --out-dir audio/ --slides 0,3-5
    python3 audio_generate.py --texts slide_texts.json --out-dir audio/ --tempo 1.5

env:
  FISH_AUDIO_API_KEY, FISH_AUDIO_VOICE_ID 必須。プロジェクトルートの .env から読む
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[3]


def load_env(project_root: Path) -> None:
    env_path = project_root / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if v and k not in os.environ:
            os.environ[k] = v


def parse_indices(spec: str):
    out = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return out


def call_fish(text: str, api_key: str, voice_id: str, audio_format: str = "wav") -> bytes:
    from fish_audio_sdk import Session, TTSRequest
    session = Session(api_key)
    chunks = []
    for chunk in session.tts(TTSRequest(text=text, reference_id=voice_id, format=audio_format)):
        chunks.append(chunk)
    return b"".join(chunks)


def encode_to_mp3(src: Path, dst: Path, tempo: float = 1.0) -> None:
    """無音除去 + 50ms 先頭パディング + (任意)倍速化 + MP3エンコード

    tempo は ffmpeg の atempo フィルタで適用する（ピッチを保ったまま速度だけ変わる）。
    ここ（音声素材の段階）で倍速化しておけば、assemble_video.py は音声実測長で
    動画を切るため映像も自動的に追従する。下流での特別な対応は不要。
    """
    af = "silenceremove=start_periods=1:start_threshold=-30dB:start_silence=0.05,adelay=50|50"
    if tempo != 1.0:
        af += f",atempo={tempo}"
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(src),
            "-af", af,
            "-c:a", "libmp3lame", "-q:a", "2",
            str(dst),
        ],
        capture_output=True,
    )


def run_single(text: str, out_path: Path, api_key: str, voice_id: str, tempo: float = 1.0) -> None:
    print(f"[run] voice_id={voice_id[:8]}... text=({len(text)} chars) tempo={tempo}")
    t0 = time.time()
    wav_bytes = call_fish(text, api_key, voice_id, audio_format="wav")
    dt = time.time() - t0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_wav = out_path.with_suffix(".tmp.wav")
    tmp_wav.write_bytes(wav_bytes)
    encode_to_mp3(tmp_wav, out_path, tempo=tempo)
    tmp_wav.unlink(missing_ok=True)
    size_kb = out_path.stat().st_size / 1024
    print(f"[ok ] {out_path} ({size_kb:.0f} KB, {dt:.1f}s)")


def run_batch(texts_path: Path, out_dir: Path, api_key: str, voice_id: str, target: set, suffix: str = "", tempo: float = 1.0) -> None:
    raw = json.loads(texts_path.read_text())
    entries = raw["slides"] if isinstance(raw, dict) and "slides" in raw else raw
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[run] voice_id={voice_id[:8]}... entries={len(entries)} target={'all' if target is None else sorted(target)} suffix={suffix or '(none)'} tempo={tempo}")
    for entry in entries:
        if "slide_id" not in entry:
            raise KeyError(f"slide_texts.json entry missing 'slide_id': {entry}")
        sid = entry["slide_id"]
        if target is not None and sid not in target:
            continue
        out_path = out_dir / f"slide_{sid:03d}{suffix}.mp3"
        if out_path.exists() and target is None:
            print(f"[skip] {out_path.name} (exists)")
            continue
        text = entry["text"]
        title = (entry.get("title") or "")[:30]
        print(f"[gen ] slide_{sid:03d} — {title} ({len(text)} chars)")
        t0 = time.time()
        wav_bytes = call_fish(text, api_key, voice_id, audio_format="wav")
        dt = time.time() - t0
        tmp_wav = out_path.with_suffix(".tmp.wav")
        tmp_wav.write_bytes(wav_bytes)
        encode_to_mp3(tmp_wav, out_path, tempo=tempo)
        tmp_wav.unlink(missing_ok=True)
        size_kb = out_path.stat().st_size / 1024
        print(f"[ok  ] {out_path.name} ({size_kb:.0f} KB, {dt:.1f}s)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--texts", type=Path)
    ap.add_argument("--out-dir", type=Path)
    ap.add_argument("--slides", help="対象index指定 (例: 0,3-5)")
    ap.add_argument("--suffix", default="", help="出力ファイル名のサフィックス (例: _wav)")
    ap.add_argument("--tempo", type=float, default=1.0,
                    help="再生速度（1.5で1.5倍速。atempoフィルタでピッチ保持のまま短縮）")
    args = ap.parse_args()

    if not (0.5 <= args.tempo <= 2.0):
        print("Error: --tempo は 0.5〜2.0 の範囲で指定してください", file=sys.stderr)
        return 1

    load_env(PROJECT_ROOT)
    api_key = os.environ.get("FISH_AUDIO_API_KEY", "").strip()
    voice_id = os.environ.get("FISH_AUDIO_VOICE_ID", "").strip()
    if not api_key:
        print("Error: FISH_AUDIO_API_KEY not set in .env", file=sys.stderr)
        return 1
    if not voice_id:
        print("Error: FISH_AUDIO_VOICE_ID not set in .env", file=sys.stderr)
        return 1

    if args.text and args.out:
        run_single(args.text, args.out, api_key, voice_id, tempo=args.tempo)
        return 0

    if args.texts and args.out_dir:
        target = parse_indices(args.slides) if args.slides else None
        run_batch(args.texts, args.out_dir, api_key, voice_id, target, suffix=args.suffix, tempo=args.tempo)
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
