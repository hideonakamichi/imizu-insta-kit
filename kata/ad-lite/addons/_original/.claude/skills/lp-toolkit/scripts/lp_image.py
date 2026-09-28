"""LP セクション画像生成 — gpt-image-2 で LP のセクション別画像を作る

入力: lp/<lp_id>_sections.json（analyze.py / 手書きで作る）
出力: 同 JSON と同じディレクトリ配下の images/<lp_id>_<section_id>_<ts>.png

使い方:
  python lp_image.py --json data/my-project/lp/example_sections.json --section S01_fv
  python lp_image.py --json <path>   # --section 省略で全セクション生成
"""

import argparse
import base64
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from openai import OpenAI

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


def section_dirname(section_id: str) -> str:
    """S01_fv -> 01.fv"""
    body = section_id.lstrip("Ss")
    if "_" in body:
        num, rest = body.split("_", 1)
        return f"{num}.{rest}"
    return body


def generate_section(client: OpenAI, section: dict, model: str, quality: str, base_dir: Path, lp_id: str) -> Path:
    sid = section["id"]
    size = section.get("size", "1024x1024")
    prompt = section["prompt"]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    # base_dir/<lp_id>/<NN.section>/<ts>.png
    section_dir = base_dir / lp_id / section_dirname(sid)
    section_dir.mkdir(parents=True, exist_ok=True)
    out_file = section_dir / f"{ts}.png"
    prompt_file = section_dir / f"{ts}.prompt.txt"
    print(f"[+] generating: {out_file.name}")
    print(f"    model={model} size={size} quality={quality}")
    resp = client.images.generate(
        model=model,
        prompt=prompt,
        size=size,
        quality=quality,
        n=1,
    )
    item = resp.data[0]
    if getattr(item, "b64_json", None):
        out_file.write_bytes(base64.b64decode(item.b64_json))
    elif getattr(item, "url", None):
        import urllib.request
        with urllib.request.urlopen(item.url) as r:
            out_file.write_bytes(r.read())
    else:
        raise RuntimeError(f"unknown image response shape: {item}")
    prompt_file.write_text(prompt, encoding="utf-8")
    print(f"    ✓ saved: {out_file}")
    return out_file


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", required=True, help="lp/<lp_id>_sections.json のパス")
    ap.add_argument("--section", help="生成するセクションID（例: S01_fv）。未指定=全部")
    ap.add_argument("--model", default="gpt-image-2")
    ap.add_argument("--quality", default="medium", choices=["low", "medium"])
    args = ap.parse_args()

    load_env(PROJECT_ROOT)
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("[!] OPENAI_API_KEY が設定されていません。", file=sys.stderr)
        return 1
    client = OpenAI(api_key=api_key)

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
            generate_section(client, s, args.model, args.quality, out_dir, lp_id)
        except Exception as e:
            print(f"  ! failed {s['id']}: {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
