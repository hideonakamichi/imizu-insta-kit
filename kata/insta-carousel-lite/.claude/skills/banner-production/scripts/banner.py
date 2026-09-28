"""Banner 生成 — Instagram情報発信カルーセルを描く（DESIGN.md Minimal方針準拠）

insta-autopost-kit の banner.py から、画像生成AI（Grok）の旧経路を外した Lite 版。
描画は Pillow による決定論的描画（render_slides.py）だけ。同じ spec なら毎回同じ絵になり、
API もサインインも要らない。画像生成AIをやめた経緯は references/carousel-spec.md の末尾。

使い方（カルーセルモード — 通常はこちら）:
  python banner.py --spec OUTPUT_DIR/carousel_spec.json --out-dir <path>
  python banner.py --spec ... --out-dir <path> --only-slide 3   # 指定スライドのみ再描画

使い方（単発モード — 告知1枚ものなど）:
  python banner.py --headline "見出し" --sub "サブテキスト" --out-dir <path>

python の呼び方は OS で違う（Windows: py / Mac: python3）。config/runtime.yaml を参照。
specのスキーマは references/carousel-spec.md を参照。

出力（カルーセルモード）:
  <out-dir>/slide_<n>_<role>_<ts>.png          # 4:5 (1080x1350)。投稿用はこれを使う
  <out-dir>/slide_<n>_<role>_<ts>.layout.json  # 描画パラメータ

出力（単発モード）:
  <out-dir>/banner_1_<ts>.png / .layout.json
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[3]

sys.path.insert(0, str(SCRIPT_DIR))
import render_slides

# Windows の Python は出力を cp932 で書くため、Claude Code（Git Bash）で読むと日本語が化ける。UTF-8 に固定する
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

TARGET_SIZE = (1080, 1350)      # Instagramフィード最大表示の4:5

# カルーセルの文字量上限（references/carousel-spec.md と同期。
# 決定論的描画では誤字は出ないが、1枚1メッセージと余白を守るための上限として据え置く）
CHAR_LIMITS = {"headline": 13, "sub": 20, "point": 15, "cta": 18}
MAX_POINTS = 3


def validate_spec(spec: dict) -> list[str]:
    """carousel_spec.json の構造検証。構造違反はエラー(例外)、文字量超過は警告リストで返す。"""
    slides = spec.get("slides")
    if not isinstance(slides, list) or not (3 <= len(slides) <= 6):
        raise ValueError(f"slides は3〜6枚が必要です（現在: {len(slides) if isinstance(slides, list) else 'なし'}）")
    if slides[0].get("role") != "cover":
        raise ValueError("先頭スライドは role=cover が必要です")
    if slides[-1].get("role") != "summary":
        raise ValueError("末尾スライドは role=summary が必要です")
    for s in slides[1:-1]:
        if s.get("role") != "content":
            raise ValueError(f"中間スライドは role=content が必要です（検出: {s.get('role')}）")
    palette = spec.get("palette", {})
    for key in ("bg", "text", "accent"):
        v = palette.get(key, "")
        if not (isinstance(v, str) and v.startswith("#") and len(v) in (4, 7)):
            raise ValueError(f"palette.{key} は hex値（#RRGGBB）が必要です（検出: {v!r}）")

    warnings = []
    for i, s in enumerate(slides, start=1):
        if not s.get("headline"):
            raise ValueError(f"slide {i}: headline は必須です")
        if len(s["headline"]) > CHAR_LIMITS["headline"]:
            warnings.append(f"slide {i}: headline が{CHAR_LIMITS['headline']}字超（{len(s['headline'])}字）")
        if len(s.get("sub", "")) > CHAR_LIMITS["sub"]:
            warnings.append(f"slide {i}: sub が{CHAR_LIMITS['sub']}字超")
        points = s.get("points", [])
        if len(points) > MAX_POINTS:
            warnings.append(f"slide {i}: points が{MAX_POINTS}項目超（{len(points)}項目）")
        for p in points:
            if len(p) > CHAR_LIMITS["point"]:
                warnings.append(f"slide {i}: point「{p}」が{CHAR_LIMITS['point']}字超")
        if s.get("cta"):
            if s["role"] != "summary":
                raise ValueError(f"slide {i}: cta は summary スライドのみ指定できます")
            if len(s["cta"]) > CHAR_LIMITS["cta"]:
                warnings.append(f"slide {i}: cta が{CHAR_LIMITS['cta']}字超")
    return warnings


def _load_palette() -> dict:
    """単発モード用: brand.yaml の design.palette を読む（specがないため）。"""
    import yaml
    brand = yaml.safe_load((PROJECT_ROOT / "config/brand.yaml").read_text(encoding="utf-8"))
    pal = (brand.get("design") or {}).get("palette") or {}
    for key in ("bg", "text", "accent"):
        if not str(pal.get(key, "")).startswith("#"):
            raise ValueError(f"brand.yaml の design.palette.{key} が hex値ではありません")
    return {k: pal[k] for k in ("bg", "text", "accent")}


def render_one(slide: dict, idx: int, total: int, palette: dict, out_dir: Path, stem: str) -> Path:
    """1枚を描いて PNG と layout.json を保存する。"""
    out_file = out_dir / f"{stem}.png"
    print(f"[+] rendering {idx}/{total} ({slide['role']}): {out_file.name}")
    layout = render_slides.render_slide(slide, idx, total, palette, out_file)
    render_slides.write_layout(layout, out_dir / f"{stem}.layout.json")
    print(f"    OK saved: {out_file} (4:5 {TARGET_SIZE[0]}x{TARGET_SIZE[1]})")
    return out_file


def run_carousel_mode(args, out_dir: Path) -> int:
    spec_path = Path(args.spec)
    if not spec_path.is_absolute():
        spec_path = (PROJECT_ROOT / args.spec).resolve()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    try:
        warnings = validate_spec(spec)
    except ValueError as e:
        print(f"[!] spec検証エラー: {e}", file=sys.stderr)
        return 1
    for w in warnings:
        print(f"[warn] 文字量上限超過: {w}（詰め込みになる。specの見直しを推奨）", file=sys.stderr)

    slides = spec["slides"]
    total = len(slides)
    palette = spec["palette"]

    if args.only_slide is not None:
        if not (1 <= args.only_slide <= total):
            print(f"[!] --only-slide は1〜{total}の範囲で指定してください。", file=sys.stderr)
            return 1
        targets = [args.only_slide]
        print(f"[+] carousel mode: slide {args.only_slide} のみ再描画（全{total}枚構成）")
    else:
        targets = list(range(1, total + 1))
        print(f"[+] carousel mode: 全{total}枚を描画")

    ok, failed = 0, []
    for idx in targets:
        slide = slides[idx - 1]
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            render_one(slide, idx, total, palette, out_dir, f"slide_{idx}_{slide['role']}_{ts}")
            ok += 1
        except Exception as e:
            failed.append(idx)
            print(f"  ! failed slide {idx}: {e}", file=sys.stderr)

    # カルーセルは全枚揃わないと投稿できないため、1枚でも失敗したら失敗扱い
    if failed:
        print(f"[!] 描画に失敗したスライド: {failed}（成功{ok}/{len(targets)}枚）", file=sys.stderr)
        return 1
    print(f"[done] {ok}/{len(targets)}枚描画完了")
    return 0


def run_single_mode(args, out_dir: Path) -> int:
    # 単発バナーは表紙スライドと同じレイアウトで描く
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    try:
        render_one({"role": "cover", "headline": args.headline, "sub": args.sub},
                   1, 1, _load_palette(), out_dir, f"banner_1_{ts}")
    except Exception as e:
        print(f"[!] 描画に失敗しました: {e}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", help="carousel_spec.json のパス（カルーセルモード）")
    ap.add_argument("--only-slide", type=int, help="指定スライド番号(1始まり)のみ再描画（--spec必須）")
    ap.add_argument("--headline", help="見出し（日本語。単発モード）")
    ap.add_argument("--sub", help="サブテキスト（日本語。単発モード）")
    ap.add_argument("--out-dir", required=True, help="出力先ディレクトリ")
    args = ap.parse_args()

    if not args.spec and not (args.headline and args.sub):
        ap.error("--spec（カルーセルモード）または --headline/--sub（単発モード）のいずれかが必要です")
    if args.only_slide is not None and not args.spec:
        ap.error("--only-slide は --spec と併用してください")

    try:
        render_slides.check_fonts()
    except render_slides.FontMissing as e:
        print(f"[!] {e}", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = (PROJECT_ROOT / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[+] out_dir: {out_dir}")

    if args.spec:
        return run_carousel_mode(args, out_dir)
    return run_single_mode(args, out_dir)


if __name__ == "__main__":
    sys.exit(main())
