"""LP セクション画像生成 — Gemini画像生成で LP のセクション別画像を作る

入力: lp/<lp_id>_sections.json（lp-designer が書く／手書きで作る）
出力: 同 JSON と同じディレクトリ配下の images/<lp_id>/<NN.section>/<ts>.png

使い方:
  python lp_image.py --json data/my-project/lp/example_sections.json --section S01_fv
  python lp_image.py --json <path>   # --section 省略で全セクション生成
"""

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# Windows の Python は出力を cp932 で書くため、Claude Code（Git Bash）で読むと日本語が化ける。UTF-8 に固定する
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[3]

GEMINI_MODEL = "gemini-3.1-flash-image-preview"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

SIZE_TO_ASPECT = {
    "1024x1024": "1:1",
    "1024x1536": "9:16",
    "1536x1024": "16:9",
}


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


def section_dirname(section_id: str) -> str:
    """S01_fv -> 01.fv"""
    body = section_id.lstrip("Ss")
    if "_" in body:
        num, rest = body.split("_", 1)
        return f"{num}.{rest}"
    return body


def generate_image_gemini(prompt: str, aspect_ratio: str, api_key: str) -> bytes:
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": {"aspectRatio": aspect_ratio},
        },
    }
    req = urllib.request.Request(
        f"{GEMINI_URL}?key={api_key}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"APIエラー ({e.code}): {detail[:500]}") from e

    for part in body.get("candidates", [{}])[0].get("content", {}).get("parts", []):
        inline = part.get("inlineData")
        if inline and inline.get("data"):
            return base64.b64decode(inline["data"])
    raise RuntimeError(f"画像データが返されませんでした: {json.dumps(body, ensure_ascii=False)[:500]}")


def generate_section(section: dict, api_key: str, base_dir: Path, lp_id: str) -> Path:
    sid = section["id"]
    size = section.get("size", "1024x1024")
    aspect = SIZE_TO_ASPECT.get(size, "1:1")
    prompt = section["prompt"]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    section_dir = base_dir / lp_id / section_dirname(sid)
    section_dir.mkdir(parents=True, exist_ok=True)
    out_file = section_dir / f"{ts}.png"
    prompt_file = section_dir / f"{ts}.prompt.txt"
    print(f"[+] generating: {out_file.name}")
    print(f"    model={GEMINI_MODEL} aspect={aspect}")
    image_bytes = generate_image_gemini(prompt, aspect, api_key)
    out_file.write_bytes(image_bytes)
    prompt_file.write_text(prompt, encoding="utf-8")
    print(f"    ✓ saved: {out_file}")
    return out_file


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", required=True, help="lp/<lp_id>_sections.json のパス")
    ap.add_argument("--section", help="生成するセクションID（例: S01_fv）。未指定=全部")
    args = ap.parse_args()

    load_env(PROJECT_ROOT)
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[!] GEMINI_API_KEY が設定されていません。", file=sys.stderr)
        return 1

    json_path = Path(args.json)
    if not json_path.is_absolute():
        json_path = (PROJECT_ROOT / args.json).resolve()
    if not json_path.exists():
        print(f"[!] not found: {json_path}", file=sys.stderr)
        return 2

    spec = json.loads(json_path.read_text(encoding="utf-8"))
    lp_id = spec["lp_id"]
    sections = spec["sections"]
    if args.section:
        sections = [s for s in sections if s["id"] == args.section]
        if not sections:
            print(f"[!] section not found: {args.section}", file=sys.stderr)
            return 3

    out_dir = json_path.parent / "images"
    out_dir.mkdir(exist_ok=True)
    print(f"[+] lp_id   : {lp_id}")
    print(f"[+] out_dir : {out_dir}")
    print(f"[+] sections: {len(sections)} / {len(spec['sections'])}")

    for s in sections:
        try:
            generate_section(s, api_key, out_dir, lp_id)
        except Exception as e:
            print(f"  ! failed {s['id']}: {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
