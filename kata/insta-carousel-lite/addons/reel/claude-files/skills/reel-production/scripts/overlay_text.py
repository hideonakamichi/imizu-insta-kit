"""slides.json の headline_text / sub_text をPILでスライドPNGに焼き込む。

## なぜAI描画ではなくコード描画か

gpt-image-2に日本語テキストを描かせる方式は、幅制約（「中央65%以内」等）を
確率的にしか守らず、9:16クロップでの左右見切れがevaluator不合格→画像再生成の
ループを繰り返し発生させた（2026-07-27 abort_no_post、improvement id=39）。
文字はPILで描けば位置・サイズ・折り返しを決定論的に制御でき、見切れは構造的に消える。
画像モデルはイラストのみ担当する（generate_slides.py が本モジュールを自動で呼ぶ）。

## セーフゾーンの計算根拠

assemble_video.py は 1024x1536 を 1280x1920 へ拡大後、中央 1080x1920 を切り出す。
よって左右各 100px（1024px幅換算で80px）が必ず失われる。evaluatorの合格基準は
「最終動画1080px幅で左右各108px（10%）以上のマージン」なので、1024キャンバス上では
左右各 (108+100)/1.25 = 166.4px 以上 → テキスト最大幅 1024-2*167 = 690px。
MAX_TEXT_W=672 はさらに約1.5%のバッファを持たせた値。

## 使い方

  # generate_slides.py から自動で呼ばれる（通常はこちら）
  # 手動での再オーバーレイ（イラスト再生成なしでテキストだけ直す）:
  python3 overlay_text.py --slides-json PATH --slides-dir DIR [--ids 1,2]

slides-dir には raw/slide_NNN.png（文字なしイラスト）が必要。
出力は slides-dir/slide_NNN.png（既存があれば上書き）。
raw/ が無いスライドはエラーにして止める（文字入り画像への二重描画を防ぐ）。

## 終了コード

- 0: 全件成功
- 1: 一部失敗（raw欠落・最小フォントでも収まらない等）
- 2: 引数・前提エラー
"""

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# 日本語の文節境界で折り返すためのライブラリ（Google製・純Python・依存なし）。
# 無い環境では文字単位折り返しにフォールバックする（語中分断が起きうるが動作はする）
try:
    import budoux
    _BUDOUX = budoux.load_default_japanese_parser()
except Exception:
    _BUDOUX = None

SCRIPT_DIR = Path(__file__).resolve().parent
ASSETS_FONT_DIR = SCRIPT_DIR.parent / "assets" / "fonts"

CANVAS_W = 1024
CANVAS_H = 1536

# 上部130pxはスケール時にクロップされうる領域（generate_slides.py と同じ前提）
TEXT_TOP = 176
MAX_TEXT_W = 672

HEADLINE_SIZE = 96
HEADLINE_MIN_SIZE = 64
HEADLINE_MAX_LINES = 2

SUB_SIZE = 54
SUB_MIN_SIZE = 40
SUB_MAX_LINES = 4

LINE_SPACING = 1.34
BLOCK_GAP = 48  # headlineブロックとsubブロックの間隔

TEXT_COLOR = (46, 42, 38)  # warm charcoal（イラスト指示の dark charcoal line work に合わせる）
FONT_SIZE_STEP = 4

# 折り返し規則: 句読点等の直後で優先的に折る。行頭に来てはいけない文字は前行末に送る
BREAK_AFTER = "、。！？!?・：」）』"
NO_LINE_START = "、。！？!?・：ー」）』…ッャュョァィゥェォん"


def resolve_font(bold: bool) -> str:
    """フォントを優先順に解決する。assets/fonts に置いたものが最優先
    （丸ゴシック等に差し替えたい場合はそこへ .ttf/.otf を置き weight名を含める）。"""
    keyword = "bold" if bold else "medium"
    candidates: list[Path] = []
    if ASSETS_FONT_DIR.is_dir():
        for p in sorted(ASSETS_FONT_DIR.iterdir()):
            if p.suffix.lower() in (".ttf", ".otf") and keyword in p.name.lower():
                candidates.append(p)
        # weight名一致がなければ任意の同梱フォント
        for p in sorted(ASSETS_FONT_DIR.iterdir()):
            if p.suffix.lower() in (".ttf", ".otf"):
                candidates.append(p)
    # 同梱フォントが無ければ macOS 標準の日本語ヒラギノを使う（追加設定なしで動く既定）。
    # ※ 游ゴシック等のOS付属フォントはライセンス上このスターターに同梱できないため、
    #   見た目を変えたい場合は再配布可能なフォント（例: Noto Sans JP, SIL OFL）を
    #   assets/fonts/ に置くこと（詳細は assets/fonts/README.md）
    hira_weights = ("W6", "W7", "W8") if bold else ("W3", "W4")
    candidates += [
        Path(f"/System/Library/Fonts/ヒラギノ角ゴシック {w}.ttc") for w in hira_weights
    ]
    candidates += [
        Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),  # 中華圏字形だが最終手段
        Path("/Library/Fonts/Arial Unicode.ttf"),
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    raise FileNotFoundError(
        f"日本語フォントが見つかりません。{ASSETS_FONT_DIR} に .ttf/.otf を配置してください"
    )


def _measure(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> float:
    return draw.textlength(text, font=font)


def _split_chunks(text: str) -> list[str]:
    """折り返し可能な最小単位に分割する。budouxがあれば文節、なければ句読点区切り。"""
    if _BUDOUX:
        return [c for c in _BUDOUX.parse(text) if c]
    chunks: list[str] = []
    cur = ""
    for ch in text:
        cur += ch
        if ch in BREAK_AFTER:
            chunks.append(cur)
            cur = ""
    if cur:
        chunks.append(cur)
    return chunks


def _apply_kinsoku(lines: list[str]) -> list[str]:
    """行頭禁則: 禁則文字で始まる行は、その文字を前行末へ移動する。"""
    i = 1
    while i < len(lines):
        while lines[i] and lines[i][0] in NO_LINE_START:
            lines[i - 1] += lines[i][0]
            lines[i] = lines[i][1:]
        if not lines[i]:
            del lines[i]
            continue
        i += 1
    return [l for l in lines if l]


def _pack(
    draw: ImageDraw.ImageDraw,
    chunks: list[str],
    font: ImageFont.FreeTypeFont,
    soft_max: float,
    hard_max: float,
) -> list[str]:
    """チャンク列を行に詰める。soft_maxを目安に折り、hard_maxは絶対に超えない。"""
    lines: list[str] = []
    cur = ""
    for c in chunks:
        cand = cur + c
        w = _measure(draw, cand, font)
        if cur and (w > hard_max or w > soft_max):
            lines.append(cur)
            cur = c
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines


def wrap_auto(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: float
) -> list[str]:
    """文節単位で折り返し、行長を均等化して1〜2文字の孤立行を防ぐ。

    2026-07-27の2度目のabort（「見学だけでは分/からない」の語中分断、「が」1文字の
    孤立行）を受けた改修。greedy一発だと最終行だけ極端に短くなるため、いったん行数を
    確定させた後「合計幅÷行数」を目安幅にして再パックし、行長を揃える。
    """
    chunks = _split_chunks(text)
    # 単体で幅超過するチャンク（英数字の長い連続等）だけは文字単位に崩す
    norm: list[str] = []
    for c in chunks:
        if _measure(draw, c, font) > max_w:
            norm.extend(list(c))
        else:
            norm.append(c)
    lines = _pack(draw, norm, font, max_w, max_w)
    if len(lines) > 1:
        total = sum(_measure(draw, c, font) for c in norm)
        target = max(total / len(lines), max_w * 0.55)
        balanced = _pack(draw, norm, font, target, max_w)
        if len(balanced) == len(lines):
            lines = balanced
    return _apply_kinsoku(lines)


def layout_block(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: str,
    base_size: int,
    min_size: int,
    max_lines: int,
    max_w: float,
) -> tuple[ImageFont.FreeTypeFont, list[str], bool]:
    """収まるまでフォントサイズを下げながらレイアウトする。

    テキストに明示改行（\\n）がある場合は**その行割りを絶対尊重**し、再折り返しは
    一切しない。幅超過はフォント縮小のみで解決する（明示改行された行をさらに自動で
    折ると「が」等の1文字孤立行が生まれ、evaluator差し戻しの原因になった実例あり）。
    """
    explicit_lines = None
    if "\n" in text:
        explicit_lines = [l.strip() for l in text.split("\n") if l.strip()]

    font = None
    lines: list[str] = []
    for size in range(base_size, min_size - 1, -FONT_SIZE_STEP):
        font = ImageFont.truetype(font_path, size)
        if explicit_lines is not None:
            lines = explicit_lines
            if all(_measure(draw, l, font) <= max_w for l in lines):
                return font, lines, True
        else:
            lines = wrap_auto(draw, text, font, max_w)
            if len(lines) <= max_lines and all(_measure(draw, l, font) <= max_w for l in lines):
                return font, lines, True
    return font, lines, False


def overlay_slide(image_path: Path, out_path: Path, slide: dict) -> tuple[bool, str]:
    """1枚のイラストPNGに headline_text / sub_text を描画して保存する。

    戻り値: (成功か, メッセージ)。最小フォントでも収まらない場合は失敗を返す
    （呼び出し側でスライド設計＝テキスト長の問題として扱う）。
    """
    headline = str(slide.get("headline_text") or "").strip()
    sub = str(slide.get("sub_text") or "").strip()

    img = Image.open(image_path).convert("RGB")
    if img.size != (CANVAS_W, CANVAS_H):
        img = img.resize((CANVAS_W, CANVAS_H), Image.LANCZOS)
    draw = ImageDraw.Draw(img)

    y = TEXT_TOP
    blocks: list[tuple[str, str, int, int, int, int]] = []
    if headline:
        blocks.append((headline, resolve_font(bold=True), HEADLINE_SIZE, HEADLINE_MIN_SIZE, HEADLINE_MAX_LINES, 2))
    if sub:
        blocks.append((sub, resolve_font(bold=False), SUB_SIZE, SUB_MIN_SIZE, SUB_MAX_LINES, 0))
    if not blocks:
        img.save(out_path)
        return True, "no text"

    for text, font_path, base, mn, max_lines, stroke in blocks:
        font, lines, fitted = layout_block(draw, text, font_path, base, mn, max_lines, MAX_TEXT_W)
        if not fitted:
            return False, (
                f"テキストが最小フォント{mn}pxでも {max_lines}行 x {MAX_TEXT_W}px に収まりません: 「{text}」"
                " — slides.json側でテキストを短縮してください"
            )
        line_h = font.size * LINE_SPACING
        for line in lines:
            w = _measure(draw, line, font)
            x = (CANVAS_W - w) / 2
            draw.text((x, y), line, font=font, fill=TEXT_COLOR,
                      stroke_width=stroke, stroke_fill=TEXT_COLOR)
            y += line_h
        y += BLOCK_GAP

    img.save(out_path)
    # 検証ログ: 最終動画1080px幅換算のマージン最小値
    # 1024キャンバスの左右マージンm → 最終動画では m*1.25 - 100 px
    min_margin_1024 = (CANVAS_W - MAX_TEXT_W) / 2
    final_margin = min_margin_1024 * 1.25 - 100
    return True, f"ok (最終動画での左右マージン下限≈{final_margin:.0f}px, 基準108px)"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slides-json", required=True)
    parser.add_argument("--slides-dir", required=True, help="raw/slide_NNN.png を含むディレクトリ")
    parser.add_argument("--ids", default=None, help="対象slide id（例 '1,3-5'）。省略時は全件")
    args = parser.parse_args()

    slides_dir = Path(args.slides_dir)
    raw_dir = slides_dir / "raw"
    data = json.loads(Path(args.slides_json).read_text(encoding="utf-8"))

    target: set[int] | None = None
    if args.ids:
        target = set()
        for chunk in args.ids.split(","):
            chunk = chunk.strip()
            if "-" in chunk:
                a, b = chunk.split("-", 1)
                target.update(range(int(a), int(b) + 1))
            elif chunk:
                target.add(int(chunk))

    failed: list[str] = []
    done = 0
    for slide in data["slides"]:
        sid = slide["slide_id"]
        if target is not None and sid not in target:
            continue
        raw_path = raw_dir / f"slide_{sid:03d}.png"
        out_path = slides_dir / f"slide_{sid:03d}.png"
        if not raw_path.exists():
            failed.append(f"slide {sid:03d}: raw画像がありません ({raw_path})。"
                          "generate_slides.py で再生成してください")
            continue
        ok, msg = overlay_slide(raw_path, out_path, slide)
        print(f"[{sid:03d}] {'ok' if ok else 'FAIL'}: {msg}")
        if ok:
            done += 1
        else:
            failed.append(f"slide {sid:03d}: {msg}")

    print(f"=== overlay done: {done} ok, {len(failed)} failed ===")
    for f in failed:
        print(f"  - {f}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
