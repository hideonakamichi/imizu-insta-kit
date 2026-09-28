"""JSONの訴求コンセプトから広告バナーを生成する。"""

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
DEFAULT_BRIEF = PROJECT_ROOT / "config" / "banner_concepts.json"


def load_env(project_root: Path) -> None:
    env_path = project_root / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if value and key not in os.environ:
            os.environ[key] = value


def resolve_path(value: str | None, default: Path) -> Path:
    path = Path(value) if value else default
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def load_briefs(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    briefs = data.get("concepts", data) if isinstance(data, dict) else data
    if not isinstance(briefs, list) or not briefs:
        raise ValueError("concepts が1件以上必要です")
    required = {"id", "headline_jp", "sub_jp", "tone_prompt", "personas"}
    for i, item in enumerate(briefs, 1):
        missing = required - set(item)
        if missing:
            raise ValueError(f"concepts[{i}] の必須項目が不足: {', '.join(sorted(missing))}")
        if not isinstance(item["personas"], dict) or not item["personas"]:
            raise ValueError(f"concepts[{i}].personas が空です")
    return briefs


def build_prompt(spec: dict, persona_id: str) -> str:
    persona = spec["personas"][persona_id]
    return f"""A high-quality Japanese advertising banner, {spec.get('format_prompt', 'square 1:1 composition, 1024x1024')}.

DESIGN DIRECTION:
{spec['tone_prompt']}

SUBJECT:
{persona}

JAPANESE TEXT TO RENDER:
- Headline: "{spec['headline_jp']}"
- Subtext: "{spec['sub_jp']}"

Render both Japanese lines directly and exactly as supplied. Use a highly legible Japanese typeface, strong contrast, clear hierarchy, intentional whitespace, and safe margins. The only text in the image is the supplied headline and subtext. No logos, watermarks, brand names, URLs, badges, or recognizable real people.
"""


def find_latest_analyze_dir() -> Path | None:
    candidates = list((PROJECT_ROOT / "data").glob("*/analyze_*"))
    candidates = [p for p in candidates if p.is_dir()]
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def generate_one(client: OpenAI, spec: dict, persona_id: str, out_dir: Path, model: str, size: str, quality: str) -> Path:
    prompt = build_prompt(spec, persona_id)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = f"{spec['id']}_{persona_id}_{ts}"
    out_file = out_dir / f"{stem}.png"
    response = client.images.generate(model=model, prompt=prompt, size=size, quality=quality, n=1)
    item = response.data[0]
    if getattr(item, "b64_json", None):
        out_file.write_bytes(base64.b64decode(item.b64_json))
    elif getattr(item, "url", None):
        import urllib.request
        with urllib.request.urlopen(item.url) as response_body:
            out_file.write_bytes(response_body.read())
    else:
        raise RuntimeError("画像データが返されませんでした")
    out_file.with_suffix(".prompt.txt").write_text(prompt, encoding="utf-8")
    print(f"[OK] {out_file}")
    return out_file


def main() -> int:
    parser = argparse.ArgumentParser(description="JSONの訴求コンセプトからバナーを生成")
    parser.add_argument("--brief", default=str(DEFAULT_BRIEF), help="コンセプJSONのパス")
    parser.add_argument("--concept", help="生成するconcept id。未指定は全件")
    parser.add_argument("--persona", help="personas内のID。未指定は全件")
    parser.add_argument("--out-dir", help="出力先。未指定は最新のanalyze配下")
    parser.add_argument("--model", default="gpt-image-2")
    parser.add_argument("--size", default="1024x1024")
    parser.add_argument("--quality", default="medium", choices=["low", "medium"])
    parser.add_argument("--list", action="store_true", help="生成せずconcept/persona一覧を表示")
    args = parser.parse_args()

    try:
        briefs = load_briefs(resolve_path(args.brief, DEFAULT_BRIEF))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[ERROR] 設定JSONを読み込めません: {exc}", file=sys.stderr)
        return 2
    targets = [(spec, persona) for spec in briefs for persona in spec["personas"]
               if (not args.concept or spec["id"] == args.concept)
               and (not args.persona or persona == args.persona)]
    if not targets:
        print("[ERROR] 指定に一致する生成対象がありません", file=sys.stderr)
        return 3
    if args.list:
        for spec, persona in targets:
            print(f"{spec['id']}\t{persona}\t{spec['headline_jp']}")
        return 0

    load_env(PROJECT_ROOT)
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("[ERROR] OPENAI_API_KEY が設定されていません", file=sys.stderr)
        return 1
    if args.out_dir:
        out_dir = resolve_path(args.out_dir, PROJECT_ROOT / "data")
    else:
        latest = find_latest_analyze_dir()
        if latest is None:
            print("[ERROR] analyzeディレクトリがありません。--out-dirを指定してください", file=sys.stderr)
            return 4
        out_dir = latest / "banners"
    out_dir.mkdir(parents=True, exist_ok=True)
    client = OpenAI(api_key=api_key)
    failures = 0
    for spec, persona in targets:
        try:
            generate_one(client, spec, persona, out_dir, args.model, args.size, args.quality)
        except Exception as exc:
            failures += 1
            print(f"[ERROR] {spec['id']}/{persona}: {exc}", file=sys.stderr)
    return 5 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
