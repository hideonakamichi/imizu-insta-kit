"""Generate vertical slide images from slides.json using OpenAI gpt-image-2.

参照: myuuu-io/youtube No.003_video-production-automation/tools/generate_slides.py を
縦型リール（9:16）向けに改修したもの。SIZEを1024x1536に変更し、全スライドに
セーフゾーン指示を自動付加する。env読込はプロジェクトルートの .env を使う
（元スクリプトの .env.local + python-dotenv 依存をやめ、他スクリプトと同じ手動パーサに統一）。

## テキストはAIに描かせない（2026-07-27改修）

かつては headline_text / sub_text を gpt-image-2 に描画させていたが、幅制約を
確率的にしか守らず9:16クロップで左右見切れが再発した（abort_no_post、improvement id=39）。
現在は画像モデルには**文字なしイラストのみ**を生成させ（out_dir/raw/ に保存）、
テキストは overlay_text.py がPILで焼き込む（out_dir/slide_NNN.png）。
テキストだけ直したい場合はイラスト再生成不要で overlay_text.py を直接叩けばよい。

Usage:
    python generate_slides.py --slides-json PATH --out-dir DIR
    python generate_slides.py --slides-json PATH --out-dir DIR --ids 1-8 --concurrency 4
    python generate_slides.py --slides-json PATH --out-dir DIR --quality medium --high-ids 1
"""

import argparse
import asyncio
import base64
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

from openai import AsyncOpenAI, RateLimitError, APIError

from overlay_text import overlay_slide

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[3]

MODEL = "gpt-image-2"
SIZE = "1024x1536"  # 縦型9:16相当（2:3）。ffmpeg側でさらに1080x1920へscale
RETRIES_ON_RATE_LIMIT = 2
RATE_LIMIT_BACKOFF_S = 12.0
VALID_QUALITIES = {"low", "medium", "high", "auto"}

# 生成画像1024x1536のうち、上部約130pxはffmpegでの上下スケール時にクロップされうる領域。
# 下部約12%（約184px）はInstagramリールのキャプション・いいね等のUIと重なる領域のため空ける。
# （かつては字幕焼き込み帯のため下部32%を空けていたが、2026-07-20に字幕を廃止し
# 「headline+sub_textだけで完結する」設計に移行したため、下部12%に緩和。
# 詳細は references/slides-json-spec.md「スライドだけで内容を完結させる」）
#
# 左右セーフゾーン: assemble_video.py は 1024x1536（2:3）を 1280x1920 に拡大してから
# 中央 1080x1920（9:16）を切り出すため、左右それぞれ100px（1024px幅換算で80px＝約8%）が
# 必ずクロップされる。Phase 2の初回投稿で見出しの左右端が実際に見切れた（「とりあえず
# 聞くはズレる」の「と」「る」が欠けた）実績があるため、イラスト要素にも余白を取らせる。
# テキストはPILオーバーレイに移行済みなので、ここではイラスト構図だけを制約する。
SAFE_ZONE_SUFFIX = (
    "Composition rules for the 1024x1536 canvas: the top 45% of the canvas must be "
    "plain, uniform background color with no illustration elements — that area is "
    "reserved for a Japanese text overlay that will be added programmatically. "
    "Place the illustration in the lower half, keeping it within the vertical band "
    "from 45% down to 88% of the canvas height (the bottom 12% will be overlapped "
    "by Instagram Reels UI). Horizontal safe zone: the left 10% and right 10% of "
    "the canvas will be cropped off when converted to 9:16 video, so keep all "
    "important illustration elements within the central 80% of the canvas width."
)

# 文字なしイラスト強制。global_negative_prompt に頼らず全スライドで機械的に付ける
NO_TEXT_PREFIX = (
    "Illustration only. The image must contain absolutely no text of any kind: "
    "no letters, no words, no numbers, no Japanese characters, no typography, "
    "no captions, no labels, no signage, no watermark. "
)
NO_TEXT_NEGATIVE = "text, letters, words, numbers, typography, captions, labels, writing"


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


def parse_ids(spec: str) -> set[int]:
    ids: set[int] = set()
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            a, b = chunk.split("-", 1)
            ids.update(range(int(a), int(b) + 1))
        else:
            ids.add(int(chunk))
    return ids


def fetch_image_bytes(item) -> bytes:
    b64 = getattr(item, "b64_json", None)
    if b64:
        return base64.b64decode(b64)
    url = getattr(item, "url", None)
    if url:
        with urllib.request.urlopen(url) as r:
            return r.read()
    raise RuntimeError("No b64_json or url in response item")


def build_prompt(slide: dict, global_suffix: str, global_negative: str) -> str:
    # headline_text / sub_text はプロンプトに一切入れない。テキストは overlay_text.py が
    # PILで描くため、画像モデルには文字なしイラストだけを要求する。
    # （旧方式: AIにテキスト描画させる→幅制約を守らず左右見切れが再発、2026-07-27廃止）
    prompt = NO_TEXT_PREFIX + slide.get("prompt_for_generation", "").strip()
    prompt += " " + SAFE_ZONE_SUFFIX
    if global_suffix:
        prompt += " " + global_suffix
    negative = slide.get("negative_prompt", "").strip()
    merged_negative = ", ".join(p for p in (negative, global_negative, NO_TEXT_NEGATIVE) if p)
    if merged_negative:
        prompt += f" Avoid: {merged_negative}."
    return prompt


async def generate_one(
    client: AsyncOpenAI,
    slide: dict,
    prompt: str,
    quality: str,
    out_dir: Path,
    sem: asyncio.Semaphore,
    progress: dict,
) -> tuple[int, bool, str]:
    sid = slide["slide_id"]
    section = slide.get("section", "")
    role = slide.get("slide_role", "")

    async with sem:
        progress["started"] += 1
        idx = progress["started"]
        total = progress["total"]
        print(f"[{sid:03d}] start ({idx}/{total}) {section} / {role} [q={quality}]")

        attempt = 0
        while True:
            attempt += 1
            try:
                t0 = time.time()
                kwargs = {"model": MODEL, "prompt": prompt, "size": SIZE}
                if quality != "auto":
                    kwargs["quality"] = quality
                resp = await client.images.generate(**kwargs)
                img_bytes = fetch_image_bytes(resp.data[0])
                # 文字なしイラストを raw/ に保存し、テキストはPILで焼き込んで最終PNGを作る
                raw_dir = out_dir / "raw"
                raw_dir.mkdir(parents=True, exist_ok=True)
                raw_path = raw_dir / f"slide_{sid:03d}.png"
                raw_path.write_bytes(img_bytes)
                out_path = out_dir / f"slide_{sid:03d}.png"
                ok, msg = overlay_slide(raw_path, out_path, slide)
                if not ok:
                    progress["failed"].append((sid, f"overlay: {msg}"))
                    print(f"[{sid:03d}] FAIL overlay: {msg}")
                    return sid, False, msg
                elapsed = time.time() - t0
                progress["ok"] += 1
                print(
                    f"[{sid:03d}] done  ({progress['ok']+len(progress['failed'])}/{total}) "
                    f"{len(img_bytes)//1024} KB, {elapsed:.1f}s, overlay {msg}"
                )
                return sid, True, ""
            except RateLimitError as e:
                if attempt <= RETRIES_ON_RATE_LIMIT:
                    print(f"[{sid:03d}] rate-limited, sleep {RATE_LIMIT_BACKOFF_S}s then retry ({attempt}/{RETRIES_ON_RATE_LIMIT})")
                    await asyncio.sleep(RATE_LIMIT_BACKOFF_S)
                    continue
                progress["failed"].append((sid, f"RateLimit: {e}"))
                print(f"[{sid:03d}] FAIL after retries: rate limit")
                return sid, False, str(e)
            except APIError as e:
                progress["failed"].append((sid, f"APIError: {e}"))
                print(f"[{sid:03d}] FAIL: APIError: {e}")
                return sid, False, str(e)
            except Exception as e:
                progress["failed"].append((sid, str(e)))
                print(f"[{sid:03d}] FAIL: {e}")
                return sid, False, str(e)


async def amain(args) -> int:
    load_env(PROJECT_ROOT)
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("!! OPENAI_API_KEY missing in .env", file=sys.stderr)
        return 2

    if args.quality not in VALID_QUALITIES:
        print(f"!! invalid --quality: {args.quality}. choose from {VALID_QUALITIES}", file=sys.stderr)
        return 2

    slides_json = Path(args.slides_json)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    data = json.loads(slides_json.read_text(encoding="utf-8"))
    global_suffix = data.get("global_prompt_suffix", "")
    global_negative = data.get("global_negative_prompt", "")
    slides = data["slides"]

    target = parse_ids(args.ids) if args.ids else None
    high_ids = parse_ids(args.high_ids) if args.high_ids else set()
    queue = [s for s in slides if target is None or s["slide_id"] in target]
    if not queue:
        print("!! no slides matched", file=sys.stderr)
        return 1

    client = AsyncOpenAI(api_key=api_key)

    total = len(queue)
    print(f"=== generating {total} slide(s) with {MODEL} @ {SIZE}, base quality={args.quality}, concurrency={args.concurrency} ===")
    if high_ids:
        promoted = [s["slide_id"] for s in queue if s["slide_id"] in high_ids]
        if promoted:
            print(f"=== high-quality override for slide ids: {promoted} ===")

    started = time.time()
    sem = asyncio.Semaphore(args.concurrency)
    progress = {"total": total, "started": 0, "ok": 0, "failed": []}

    tasks = []
    for s in queue:
        sid = s["slide_id"]
        per_slide_quality = "high" if sid in high_ids else args.quality
        tasks.append(
            generate_one(
                client,
                s,
                build_prompt(s, global_suffix, global_negative),
                per_slide_quality,
                out_dir,
                sem,
                progress,
            )
        )
    await asyncio.gather(*tasks, return_exceptions=False)

    elapsed = time.time() - started
    failed = progress["failed"]
    print(f"=== done: {progress['ok']}/{total} ok, {len(failed)} failed, {elapsed:.1f}s total ===")
    for sid, msg in failed:
        print(f"  - slide {sid:03d}: {msg}")
    return 0 if not failed else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slides-json", required=True, help="Path to slides.json")
    parser.add_argument("--out-dir", required=True, help="Output directory for PNG files")
    parser.add_argument("--ids", default=None, help="Slide ids to generate (e.g. '1,2,5-8'). Omit for all.")
    parser.add_argument("--concurrency", type=int, default=4, help="Parallel workers (default 4)")
    parser.add_argument("--quality", default="medium", help="low / medium / high / auto (default medium)")
    parser.add_argument("--high-ids", default=None, help="Slide ids promoted to quality=high (e.g. cover slide)")
    args = parser.parse_args()
    return asyncio.run(amain(args))


if __name__ == "__main__":
    sys.exit(main())
