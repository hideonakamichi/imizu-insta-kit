"""カルーセルスライドの決定論的描画（Pillow） — carousel_spec.json → 1080x1350 PNG

2026-09-11: 画像生成AI（Grok image_gen）に日本語の文字組みをさせる方式から切り替えた。
理由は「1枚あたりの合格率が20〜30%で、5枚すべてを上限3回以内で通す確率が1〜3割」という
構造にあり、プロンプトの書き方では解決しなかったため（経緯は references/carousel-spec.md）。

この方式では spec の文字をそのままキャンバスに置くので、evaluator が今日まで落としてきた
「書体の混在」「勝手な装飾」「指定にない文字（「」・hex・重複）」は発生原理ごと起きない。
見た目はすべて数値（フォントサイズ・座標・線幅）で決まり、同じ spec なら毎回同じ絵になる。

レイアウトの方針は docs/DESIGN.md（Minimal）に従う:
  3色・ゴシック1書体・余白・1枚1メッセージ・数字は「意味」とセット（先頭数字だけアクセント色）。
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350          # Instagramフィード 4:5
MARGIN = 96                # 左右の安全余白

# 書体はキットに同梱した Noto Sans JP（SIL Open Font License）を固定で使う。
# OS に入っている書体に頼らないので、Windows でも Mac でも同じ絵になる。
# 混在の余地をなくすため、太さ違いの2ファイルだけ（元のヒラギノ W8/W6 に近い Black/Bold）。
FONT_DIR = Path(__file__).resolve().parents[4] / "assets" / "fonts"
FONT_BOLD = FONT_DIR / "NotoSansJP-Black.otf"
FONT_MEDIUM = FONT_DIR / "NotoSansJP-Bold.otf"

# 行頭に来ると読みにくい文字（行頭禁則）。見出しを2行に割るとき、ここでは絶対に割らない
KINSOKU_HEAD = set("っゃゅょぁぃぅぇぉーゝゞ、。，．・）」』】〕］,.)!?！？")
# 行頭に来ると意味が切れて見える助詞。中央付近に他の候補があればそちらを優先する
PARTICLES = set("はがをにへとでのもや")


class FontMissing(RuntimeError):
    pass


def check_fonts() -> None:
    missing = [str(p) for p in (FONT_BOLD, FONT_MEDIUM) if not p.exists()]
    if missing:
        raise FontMissing(
            "描画用フォントが見つかりません: " + ", ".join(missing)
            + "（assets/fonts/ に同梱の Noto Sans JP を置いてください。入手先は assets/fonts/README.md）"
        )


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size, index=0)


def wrap(text: str, f: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    """本文用の折り返し。日本語は単語境界がないので1文字ずつ詰め、幅を超えたら改行。"""
    lines, cur = [], ""
    for ch in text:
        if f.getlength(cur + ch) > max_w and cur:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def fit_headline(text: str, font_path: Path, max_size: int, min_size: int, max_w: int):
    """見出し用。(font, lines) を返す。
    - スペースがあればそこで割る（spec 側で意図した改行位置）
    - なければ1行に収まる最大サイズを探す
    - min_size でも収まらないときだけ、中央付近の行頭禁則にかからない位置で2行に割る
    """
    if " " in text:
        parts = [t for t in text.split(" ") if t]
        for size in range(max_size, min_size - 1, -2):
            f = font(font_path, size)
            if all(f.getlength(t) <= max_w for t in parts):
                return f, parts
        return font(font_path, min_size), parts
    for size in range(max_size, min_size - 1, -2):
        f = font(font_path, size)
        if f.getlength(text) <= max_w:
            return f, [text]
    n = len(text)
    center = (n + 1) // 2
    # 中央から近い順に、行頭禁則にも助詞にも当たらない位置を探す（±2文字まで）
    candidates = [center + d for d in (0, 1, -1, 2, -2) if 1 <= center + d < n]
    cut = next((c for c in candidates if text[c] not in KINSOKU_HEAD and text[c] not in PARTICLES),
               next((c for c in candidates if text[c] not in KINSOKU_HEAD), center))
    parts = [text[:cut], text[cut:]]
    for size in range(max_size, min_size - 1, -2):
        f = font(font_path, size)
        if all(f.getlength(t) <= max_w for t in parts):
            return f, parts
    return font(font_path, min_size), parts


def fit_single_line(text: str, font_path: Path, max_size: int, min_size: int, max_w: int):
    """sub / cta 用。折り返さず、1行に収まる最大サイズのフォントを返す（最小 min_size）。"""
    for size in range(max_size, min_size - 1, -2):
        f = font(font_path, size)
        if f.getlength(text) <= max_w:
            return f
    return font(font_path, min_size)


def split_leading_numeral(text: str) -> tuple[str, str]:
    """先頭の数字列とそれ以降に分ける。数字だけアクセント色にするため。"""
    i = 0
    while i < len(text) and text[i].isdigit():
        i += 1
    return text[:i], text[i:]


def draw_centered(d: ImageDraw.ImageDraw, y: int, text: str, f, fill: str, accent: str | None = None) -> None:
    """1行を水平中央に描く。accent が渡されたら先頭の数字だけその色で描く。"""
    num, rest = split_leading_numeral(text) if accent else ("", text)
    x = (W - (f.getlength(num) + f.getlength(rest))) / 2
    if num:
        d.text((x, y), num, font=f, fill=accent)
        x += f.getlength(num)
    d.text((x, y), rest, font=f, fill=fill)


def render_cover(d: ImageDraw.ImageDraw, slide: dict, pal: dict) -> dict:
    f_h, lines = fit_headline(slide["headline"], FONT_BOLD, 124, 92, W - 2 * MARGIN)
    sub = slide.get("sub")
    f_s = fit_single_line(sub or "", FONT_MEDIUM, 46, 36, W - 2 * MARGIN)
    lh = int(f_h.size * 1.28)
    block_h = lh * len(lines) + (70 + 56 if sub else 0)
    y = (H - block_h) // 2 - 20
    for ln in lines:
        draw_centered(d, y, ln, f_h, pal["text"], accent=pal["accent"])
        y += lh
    if sub:
        y += 40
        draw_centered(d, y, sub, f_s, pal["text"])
        y += 56 + 60
    # 細い金の罫1本（2px・中央）。装飾はこれだけ
    d.line([(W / 2 - 110, y), (W / 2 + 110, y)], fill=pal["accent"], width=2)
    return {"headline_size": f_h.size, "headline_lines": lines, "sub_size": f_s.size if sub else None}


def render_content(d: ImageDraw.ImageDraw, slide: dict, idx: int, total: int, pal: dict) -> dict:
    f_h, lines = fit_headline(slide["headline"], FONT_BOLD, 88, 70, W - 2 * MARGIN)
    # 箇条書きは 52px 固定: 上限15字がちょうど1行に収まる（15×52=780 ≤ 808）。
    # スライド間で文字サイズが揃うことを優先し、項目ごとの自動縮小はしない
    f_p = font(FONT_BOLD, 52)
    f_n = font(FONT_MEDIUM, 34)
    lh = int(f_h.size * 1.3)
    plh = int(52 * 1.35)
    points = slide.get("points", [])
    wrapped = [wrap(p, f_p, W - 2 * MARGIN - 80) for p in points]
    # 見出し + 罫 + 箇条書きの総高さを出して、全体を垂直中央に置く
    pt_h = sum(len(pl) * plh + 44 for pl in wrapped) - (44 if wrapped else 0)
    block_h = lh * len(lines) + 40 + 110 + pt_h
    # ページ番号ぶんだけ上に寄せた位置を中央とみなす（下部の死に領域を減らす）
    y = (H - 60 - block_h) // 2 + 20
    # 見出しは箇条書きと同じ左端に揃える（DESIGN.md「軸を決めて崩さない」。
    # 中央揃えだと見出しが短い枚だけ左端がずれて見える — 2026-09-11 evaluator 指摘）
    for ln in lines:
        d.text((MARGIN, y), ln, font=f_h, fill=pal["text"])
        y += lh
    # 見出し直下: 細い金の罫1本だけ（環や話題別アイコンは置かない）
    y += 40
    d.line([(MARGIN, y), (W - MARGIN, y)], fill=pal["accent"], width=2)
    y += 110
    # 箇条書き: 金の丸点 + 本文（左揃え）
    for pl in wrapped:
        cy = y + 34
        d.ellipse([MARGIN + 6, cy - 9, MARGIN + 24, cy + 9], fill=pal["accent"])
        for ln in pl:
            d.text((MARGIN + 60, y), ln, font=f_p, fill=pal["text"])
            y += plh
        y += 44
    # ページ番号: 右下・安全域内
    label = f"{idx}/{total}"
    d.text((W - MARGIN - f_n.getlength(label), H - 130), label, font=f_n, fill=pal["text"])
    return {"headline_size": f_h.size, "headline_lines": lines, "points_size": f_p.size, "page": label}


def render_summary(d: ImageDraw.ImageDraw, slide: dict, pal: dict) -> dict:
    f_h, lines = fit_headline(slide["headline"], FONT_BOLD, 108, 84, W - 2 * MARGIN)
    sub = slide.get("sub")
    cta = slide.get("cta")
    f_s = fit_single_line(sub or "", FONT_BOLD, 54, 40, W - 2 * MARGIN)
    f_c = fit_single_line(cta or "", FONT_MEDIUM, 40, 32, W - 2 * MARGIN)
    lh = int(f_h.size * 1.28)
    block_h = lh * len(lines) + (40 + 70 if sub else 0)
    y = (H - block_h) // 2 - 80
    for ln in lines:
        draw_centered(d, y, ln, f_h, pal["text"])
        y += lh
    if sub:
        y += 40
        draw_centered(d, y, sub, f_s, pal["text"], accent=pal["accent"])
    if cta:
        # 下部に1行だけ。装飾は置かない（近くに線があると下線＝ボタン風に見える）
        draw_centered(d, H - 250, cta, f_c, pal["text"])
    return {"headline_size": f_h.size, "headline_lines": lines, "sub_size": f_s.size if sub else None,
            "cta_size": f_c.size if cta else None}


def render_slide(slide: dict, idx: int, total: int, pal: dict, out_file: Path) -> dict:
    """1枚を描いて out_file に保存し、描画パラメータ（layout）を返す。"""
    check_fonts()
    img = Image.new("RGB", (W, H), pal["bg"])
    d = ImageDraw.Draw(img)
    role = slide["role"]
    if role == "cover":
        layout = render_cover(d, slide, pal)
    elif role == "content":
        layout = render_content(d, slide, idx, total, pal)
    else:
        layout = render_summary(d, slide, pal)
    img.save(out_file, "PNG")
    layout.update({
        "engine": "pillow",
        "role": role,
        "index": idx,
        "total": total,
        "palette": pal,
        "fonts": {"bold": FONT_BOLD.name, "medium": FONT_MEDIUM.name},
        "size": [W, H],
    })
    return layout


def write_layout(layout: dict, path: Path) -> None:
    path.write_text(json.dumps(layout, ensure_ascii=False, indent=2), encoding="utf-8")
