"""Extract narration text from slides.json to slide_texts.json.

参照: myuuu-io/youtube No.003_video-production-automation/.claude/skills/video-production-pipeline/scripts/extract-narration.py
をそのまま流用（フォーマット非依存のため改修不要）。

slides.json はスライド全体のスキーマ（画像・音声・レイアウト等）を持つ。audio_generate.py が
期待するのは narration_text だけを抜き出した軽量な slide_texts.json。この変換は決定的なので
Claudeに書かせず、このスクリプトで機械的に行う。

Usage:
    python3 extract_narration.py --slides-json PATH --out-json PATH

## 命名規則（絶対ルール）

slides.json の slide_id を SOT とし、そのまま出力に継承する。画像・音声とも同じ slide_id で
揃うため、番号のズレが構造的に発生しない。

出力フォーマット:
    {
      "module": "動画タイトル",
      "slides": [
        {"slide_id": 1, "text": "narration text"},
        ...
      ]
    }
"""

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slides-json", required=True, help="Path to slides.json")
    parser.add_argument("--out-json", required=True, help="Path to output slide_texts.json")
    args = parser.parse_args()

    slides_path = Path(args.slides_json)
    out_path = Path(args.out_json)

    if not slides_path.exists():
        print(f"!! slides.json not found: {slides_path}", file=sys.stderr)
        return 1

    try:
        data = json.loads(slides_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"!! failed to parse slides.json: {e}", file=sys.stderr)
        return 1

    module_name = data.get("meta", {}).get("video_title", "untitled")
    slides_in = data.get("slides", [])

    if not slides_in:
        print("!! slides.json has no slides", file=sys.stderr)
        return 1

    slides_out = []
    missing = []
    for s in slides_in:
        sid = s.get("slide_id")
        if not isinstance(sid, int):
            print(f"!! slide without integer slide_id: {s}", file=sys.stderr)
            return 1
        text = s.get("narration_text", "")
        if not text:
            missing.append(sid)
        slides_out.append({
            "slide_id": sid,
            "text": text or "",
        })

    if missing:
        print(f"!! warning: narration_text is empty for slide_ids: {missing}", file=sys.stderr)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_data = {"module": module_name, "slides": slides_out}
    out_path.write_text(
        json.dumps(out_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"=== wrote {len(slides_out)} slides to {out_path} ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
