"""grok_media.py — Grok CLI（Grok Build）経由のメディア生成 共通ラッパー

banner.py / generate_video.py から使う。API直叩きではなく、SuperGrok/X Premium+
サブスクで動く `grok` コマンド（ヘッドレス `--prompt-file`）に生成を任せ、
このラッパーが「指示文の組み立て」と「成果物の機械検証」を決定論的に行う。

設計方針（2026-08-30 スモークテストの実測に基づく）:
- 画像: 組み込みツール `image_gen`（aspect_ratio パラメータあり）。出力はJPEGのことが
  あるため、指示文でPNG保存先の絶対パスを明示し、検証はこちらで行う
- 動画: 組み込みの video 系ツールは環境によってZDR制約（output.upload_url必須）で
  失敗することがあるが、grokエージェント自身がフォールバック（xAI Video APIの
  text-to-video直呼び）で完遂できることを確認済み。指示文でフォールバックを許可する
- 実測: 画像1枚 約1〜2分、動画10秒 約80秒（純生成）＋エージェントのオーバーヘッド。
  タイムアウトは headless制約（Bash timeout 600000ms）の内側に収める
- grokの会話出力は信用せず、ファイルの存在・寸法・尺・音声トラックを必ず検証する

CLIとしても使える（デバッグ用）:
  python3 grok_media.py image --prompt-file p.txt --out /abs/path.png --aspect-ratio 3:4
  python3 grok_media.py video --prompt-file p.txt --out /abs/path.mp4 --duration 10
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# grok バイナリの解決。launchd 環境では PATH に ~/.local/bin が無いことがある
GROK_CANDIDATES = [
    os.environ.get("GROK_BIN", ""),
    shutil.which("grok") or "",
    str(Path.home() / ".local/bin/grok"),
]

IMAGE_TIMEOUT_SEC = 420
VIDEO_TIMEOUT_SEC = 570  # Bash timeout 600000ms の内側


def _grok_bin_from_dotenv() -> str:
    """プロジェクトの .env に GROK_BIN があれば返す（launchd や手動実行では .env が環境変数に入っていないため）。"""
    env_file = Path(__file__).resolve().parents[4] / ".env"
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("GROK_BIN=") and not line.startswith("#"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


def resolve_grok() -> str:
    for c in [os.environ.get("GROK_BIN", ""), _grok_bin_from_dotenv(), *GROK_CANDIDATES]:
        if c and Path(c).exists():
            return c
    raise FileNotFoundError(
        "grok コマンドが見つかりません。`grok login` 済みのGrok CLIが必要です "
        "(https://x.ai/cli)。GROK_BIN 環境変数でパス指定も可能。"
    )


def _run_grok(instruction: str, cwd: Path, timeout_sec: int) -> tuple[int, str]:
    """grok をヘッドレス実行して (returncode, tail_of_output) を返す。"""
    grok_bin = resolve_grok()
    with tempfile.NamedTemporaryFile(
        "w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write(instruction)
        prompt_path = f.name
    try:
        proc = subprocess.run(
            [
                grok_bin,
                "--always-approve",
                "--max-turns", "25",
                "--prompt-file", prompt_path,
            ],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        tail = (proc.stdout or "")[-2000:] + (proc.stderr or "")[-500:]
        return proc.returncode, tail
    except subprocess.TimeoutExpired:
        return 124, f"grok がタイムアウト（{timeout_sec}秒）しました"
    finally:
        Path(prompt_path).unlink(missing_ok=True)


# ---------------------------------------------------------------- 画像生成

def generate_image(prompt: str, out_path: Path, aspect_ratio: str = "3:4") -> None:
    """プロンプトから画像を1枚生成して out_path（PNG）に保存する。

    検証NG・生成失敗時は RuntimeError。リトライは呼び出し元が loop-limits に従って行う。
    """
    out_path = Path(out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.unlink(missing_ok=True)

    instruction = f"""あなたは画像生成の実行役です。次の作業だけを行ってください。

1. 組み込みの画像生成ツール（image_gen）を使い、下の === IMAGE PROMPT === 以下の
   プロンプトを一字一句そのまま渡して画像を1枚生成する（要約・翻訳・改変をしない）。
   ツールのパラメータで aspect_ratio="{aspect_ratio}" を指定する。
2. 生成された画像を PNG形式 で次の絶対パスに保存する（JPEGで出力された場合は
   sips 等でPNGに変換してから保存する）:
   {out_path}
3. 保存できたらパスを報告して終了する。それ以外の作業（画像の再解釈・加工・追加生成）は
   一切しない。

=== IMAGE PROMPT ===
{prompt}
"""
    rc, tail = _run_grok(instruction, cwd=out_path.parent, timeout_sec=IMAGE_TIMEOUT_SEC)
    if rc != 0:
        raise RuntimeError(f"grok 画像生成が失敗しました (exit={rc}): {tail[-500:]}")
    _verify_image(out_path, aspect_ratio)


def _verify_image(path: Path, aspect_ratio: str) -> None:
    from PIL import Image  # 遅延import（検証時のみ）

    if not path.exists() or path.stat().st_size < 10_000:
        raise RuntimeError(f"生成画像が保存されていません: {path}")
    img = Image.open(path)
    w, h = img.size
    ar_w, ar_h = (int(x) for x in aspect_ratio.split(":"))
    expected = ar_w / ar_h
    actual = w / h
    if abs(actual - expected) > 0.05:
        raise RuntimeError(
            f"アスペクト比が不正です: {w}x{h} (expected {aspect_ratio}): {path}"
        )
    if min(w, h) < 600:
        raise RuntimeError(f"解像度が低すぎます: {w}x{h}: {path}")


# ---------------------------------------------------------------- 動画生成

def generate_video(prompt: str, out_path: Path, duration_sec: int) -> dict:
    """統合マルチモーダルプロンプトから縦型動画（9:16・音声込み）を生成する。

    成功時は ffprobe の検証結果 dict を返す。失敗時は RuntimeError。
    """
    if not (5 <= duration_sec <= 15):
        raise ValueError(f"duration_sec は5〜15の範囲で指定してください: {duration_sec}")
    out_path = Path(out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.unlink(missing_ok=True)

    instruction = f"""あなたは動画生成の実行役です。次の作業だけを行ってください。

1. 動画生成モデル grok-imagine-video-1.5 を使い、下の === VIDEO PROMPT === 以下の
   プロンプトを一字一句そのまま渡して動画を1本生成する（要約・翻訳・改変をしない）。
   パラメータ: アスペクト比 9:16、尺 {duration_sec}秒、解像度は指定可能なら1080p
   （不可なら720p）、音声生成あり（generate_audio=true 相当）。
   組み込みの動画生成ツールがエラー（upload_url必須等のZDR制約）になる場合は、
   これまでの成功例と同様に xAI Video API（POST /v1/videos/generations、text-to-video）へ
   自分でフォールバックして構わない。
2. 生成された動画（MP4）を次の絶対パスに保存する:
   {out_path}
3. 保存できたらパスを報告して終了する。動画の編集・再エンコード・追加生成はしない。

=== VIDEO PROMPT ===
{prompt}
"""
    rc, tail = _run_grok(instruction, cwd=out_path.parent, timeout_sec=VIDEO_TIMEOUT_SEC)
    if rc != 0:
        raise RuntimeError(f"grok 動画生成が失敗しました (exit={rc}): {tail[-500:]}")
    return _verify_video(out_path, duration_sec)


def _verify_video(path: Path, duration_sec: int) -> dict:
    if not path.exists() or path.stat().st_size < 100_000:
        raise RuntimeError(f"生成動画が保存されていません: {path}")
    proc = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=codec_type,width,height",
            "-show_entries", "format=duration",
            "-of", "json", str(path),
        ],
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe が失敗しました: {proc.stderr[-300:]}")
    info = json.loads(proc.stdout)
    streams = info.get("streams", [])
    vstreams = [s for s in streams if s.get("codec_type") == "video"]
    astreams = [s for s in streams if s.get("codec_type") == "audio"]
    if not vstreams:
        raise RuntimeError(f"映像ストリームがありません: {path}")
    if not astreams:
        raise RuntimeError(f"音声トラックがありません（音声込みで再生成が必要）: {path}")
    w, h = vstreams[0]["width"], vstreams[0]["height"]
    if abs(w / h - 9 / 16) > 0.02:
        raise RuntimeError(f"9:16ではありません: {w}x{h}: {path}")
    if h < 1280:
        raise RuntimeError(f"解像度が低すぎます（720p以上が必要）: {w}x{h}: {path}")
    duration = float(info["format"]["duration"])
    if abs(duration - duration_sec) > 2.0:
        raise RuntimeError(
            f"尺が指定とズレています: {duration:.1f}s (expected {duration_sec}s): {path}"
        )
    return {"width": w, "height": h, "duration": duration, "has_audio": True}


# ---------------------------------------------------------------- CLI

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="mode", required=True)

    p_img = sub.add_parser("image")
    p_img.add_argument("--prompt-file", required=True)
    p_img.add_argument("--out", required=True)
    p_img.add_argument("--aspect-ratio", default="3:4")

    p_vid = sub.add_parser("video")
    p_vid.add_argument("--prompt-file", required=True)
    p_vid.add_argument("--out", required=True)
    p_vid.add_argument("--duration", type=int, default=10)

    args = ap.parse_args()
    prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    try:
        if args.mode == "image":
            generate_image(prompt, Path(args.out), args.aspect_ratio)
            print(f"[ok] image saved: {args.out}")
        else:
            meta = generate_video(prompt, Path(args.out), args.duration)
            print(f"[ok] video saved: {args.out} ({meta})")
        return 0
    except Exception as e:
        print(f"[error] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
