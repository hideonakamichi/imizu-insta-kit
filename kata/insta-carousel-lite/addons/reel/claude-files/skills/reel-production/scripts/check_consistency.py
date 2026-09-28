#!/usr/bin/env python3
"""
slides.json の slide_id 集合と、slides/ 配下の PNG 番号集合と、audio/ 配下の
MP3 番号集合が完全一致するか検証する。

参照: myuuu-io/youtube No.003_video-production-automation/tools/check_consistency.py をそのまま流用
（パス・解像度非依存のため改修不要）。

## なぜこれが必要か

extract-narration系の番号ズレ（画像1-indexed・音声0-indexedのようなズレ）を、動画結合前に
早期検出するため。番号がズレたまま結合すると、映像と音声の対応が1つズレた動画が
成立してしまい、evaluatorでの目視確認まで気づかないリスクがある。

## 使い方

  python3 check_consistency.py \\
    --slides-json     output/JOB/slides.json \\
    --slides-dir      output/JOB/slides \\
    --audio-dir       output/JOB/audio

存在しないディレクトリは検証スキップ。Stage 進行中で audio がまだ無いケースに対応。

## 終了コード

- 0: 全部一致
- 1: 不一致を検出
"""
import argparse
import json
import re
import sys
from pathlib import Path


def collect_ids_from_dir(d: Path, suffix: str) -> set[int]:
    """slide_NNN.<suffix> から NNN を抽出して集合で返す。"""
    pat = re.compile(rf"^slide_(\d+)\{suffix}$")
    out = set()
    if not d.exists():
        return out
    for p in d.iterdir():
        m = pat.match(p.name)
        if m:
            out.add(int(m.group(1)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slides-json", type=Path, required=True)
    ap.add_argument("--slides-dir", type=Path)
    ap.add_argument("--audio-dir", type=Path)
    ap.add_argument("--slide-texts-json", type=Path)
    args = ap.parse_args()

    with args.slides_json.open() as f:
        data = json.load(f)
    sot_ids = {s["slide_id"] for s in data["slides"]}
    meta_total = data.get("meta", {}).get("total_slides")

    print(f"[sot ] slides.json: {len(sot_ids)} slide_ids ({min(sot_ids)}〜{max(sot_ids)})")

    errors: list[str] = []

    if meta_total is not None and meta_total != len(sot_ids):
        errors.append(f"meta.total_slides ({meta_total}) != 実 slides 数 ({len(sot_ids)})")

    # 字幕なし設計（2026-07-20〜）: sub_text がスライド本文を担うため必須
    no_subtext = sorted(
        s["slide_id"] for s in data["slides"] if not str(s.get("sub_text") or "").strip()
    )
    if no_subtext:
        errors.append(
            f"sub_text が空の slide_id: {no_subtext}（字幕なし設計のため sub_text は必須）"
        )

    if args.slides_dir and args.slides_dir.exists():
        png_ids = collect_ids_from_dir(args.slides_dir, ".png")
        print(f"[png ] {args.slides_dir.name}: {len(png_ids)} files ({min(png_ids) if png_ids else '-'}〜{max(png_ids) if png_ids else '-'})")
        missing = sot_ids - png_ids
        extra = png_ids - sot_ids
        if missing:
            errors.append(f"画像欠落 slide_id: {sorted(missing)}")
        if extra:
            errors.append(f"画像に余分な番号: {sorted(extra)}")
    else:
        print("[png ] (slides-dir 未指定 or 未生成、スキップ)")

    if args.audio_dir and args.audio_dir.exists():
        mp3_ids = collect_ids_from_dir(args.audio_dir, ".mp3")
        print(f"[mp3 ] {args.audio_dir.name}: {len(mp3_ids)} files ({min(mp3_ids) if mp3_ids else '-'}〜{max(mp3_ids) if mp3_ids else '-'})")
        missing = sot_ids - mp3_ids
        extra = mp3_ids - sot_ids
        if missing:
            errors.append(f"音声欠落 slide_id: {sorted(missing)}")
        if extra:
            errors.append(f"音声に余分な番号: {sorted(extra)}")
    else:
        print("[mp3 ] (audio-dir 未指定 or 未生成、スキップ)")

    if args.slide_texts_json and args.slide_texts_json.exists():
        with args.slide_texts_json.open() as f:
            tdata = json.load(f)
        text_entries = tdata.get("slides", [])
        text_ids_raw = [e.get("slide_id") for e in text_entries]
        text_ids = {x for x in text_ids_raw if isinstance(x, int)}
        print(f"[txt ] {args.slide_texts_json.name}: {len(text_ids)} entries with slide_id")
        if None in text_ids_raw or any(not isinstance(x, int) for x in text_ids_raw):
            errors.append("slide_texts.json に slide_id を持たない entry がある（旧フォーマット index の可能性）")
        missing = sot_ids - text_ids
        extra = text_ids - sot_ids
        if missing:
            errors.append(f"slide_texts に欠落 slide_id: {sorted(missing)}")
        if extra:
            errors.append(f"slide_texts に余分な番号: {sorted(extra)}")
    else:
        print("[txt ] (slide-texts-json 未指定 or 未生成、スキップ)")

    if errors:
        print()
        print("=== 整合性エラー ===")
        for e in errors:
            print(f"  x {e}")
        return 1

    print()
    print("=== 整合性 OK：slide_id が全ファイルで一致 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
