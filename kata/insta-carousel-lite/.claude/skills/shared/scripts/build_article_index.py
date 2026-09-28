#!/usr/bin/env python3
"""
build_article_index.py - 手持ちの文章を「紹介ネタ」に切り出す

Instagramの投稿を「自分の文章の紹介」にするための前処理。ネタ元（Markdown または記事HTML）を
h2 セクション単位に分け、セクションごとの根拠テキスト（content/articles/<スラッグ>/<節ID>-<ハッシュ>.md）と
索引（content/articles/index.json）を作り、content/themes.md のストック欄を書き換える。

なぜ根拠テキストを作るか: 1行のテーマだけから文言を起こすと、どの本にも書いてある一般論になり
中身が薄くなる。自分の文章（記事・メモ・FAQ・商品説明）の1節を根拠にすれば、固有の事実・数字・
手順を運べる。下流（構成・台本・キャプション・evaluator）は選ばれた1節ぶんだけを読めば足りる。
処理は決定論的（AIを使わない）。

ネタ元は2種類（config/brand.yaml の content_sources。併用できる）:
  ・markdown_dir: Markdown を置くだけ（基本）。書式は content/sources/README.md
  ・html:         自サイトの記事HTML（任意）。本文を囲む要素の class などを brand.yaml で指定する

carousel スキルが毎回の起動の最初に実行する。文章が増えれば自動でネタが増える。

壊れ方への備え（元キットは複数のパイプラインが同時に起動しえた。Lite 版は1回ずつ動かすので
ロックは外したが、次の備えはそのまま残している）:
  ・中身が変わったファイルだけを書く。ネタ元が変わっていなければ1バイトも書かない
  ・書き込みは一時ファイル→rename（読み手が書きかけを見ない）
  ・節ファイルの名前に内容のハッシュを入れ、一度書いたファイルは書き換えない（不変）。
    ネタ元が直されたら新しい名前のファイルができ、index.json だけがそちらを指す。
    ロックは更新処理どうししか守れず、すでに source_path を受け取って作業中の
    サブエージェントや、保存済みの source_path を後から読む週次点検は守れないため
  ・索引から外れた古い節ファイルは、**外れた日時**（state の retired に記録）から
    KEEP_STALE_DAYS 日たってから消す。ファイルの更新日時では数えない（変更の無い節は
    書き直さないので mtime が古いままになり、外れた瞬間に消えてしまう）
  ・順序は「節ファイル → index.json → themes.md → 古い節ファイルの削除」。
    index.json が存在しないファイルを指す瞬間を作らない
  ・解析に失敗したら何も書かずに exit 1（前回の索引がそのまま残る）
  ・成否を logs/article_index_state.json に記録する（週次点検が読む）

使い方:
  py .claude/skills/shared/scripts/build_article_index.py            # 生成（Mac は python3）
  py .claude/skills/shared/scripts/build_article_index.py --check    # 書き込まず件数だけ表示
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

import yaml

# Windows の Python は出力を cp932 で書くため、Claude Code（Git Bash）で読むと日本語が化ける。UTF-8 に固定する
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[3]
BRAND_FILE = PROJECT_ROOT / "config" / "brand.yaml"
THEMES_FILE = PROJECT_ROOT / "content" / "themes.md"
ARTICLES_DIR = PROJECT_ROOT / "content" / "articles"
INDEX_FILE = ARTICLES_DIR / "index.json"
STATE_FILE = PROJECT_ROOT / "logs" / "article_index_state.json"

STOCK_HEADING = "## ストック"
# 本文がこれより短い節は1投稿ぶんの根拠にならないので紹介ネタにしない
MIN_SECTION_CHARS = 200
# 導入部（最初の ## より前）は全節に共通の前提として、根拠テキストに**全文**残す。
# 黙って切り捨てると、後ろのほうに書かれた限定（「数値は架空」など）が下流に届かない。
# 長すぎる導入は、切らずに失敗させて書き手に整理してもらう
INTRO_MAX_CHARS = 2000
SHORT_TITLE_MAX = 13  # カルーセルの headline 上限と同じ。画面に出す前提の長さ
# 索引から外れた節ファイルを残す日数。実行中のパイプライン（最長1時間）と、
# 直近7日の生成物を読み直す週次点検が参照し終わるまで十分に長く取る
KEEP_STALE_DAYS = 30

# テーマ軸の振り分け・注意書きのルールは brand.yaml から読む（build() で設定する）:
#   strategy_axes[].keywords        … 節見出しにこの語があればその軸（上から順に最初に当たったもの）
#   content_sources.default_axis    … どれにも当たらない節の軸（省略時は strategy_axes の先頭）
#   content_sources.cautions[]      … 本文や導入部に words のどれかがある節／slug_prefixes に当たる
#                                      ネタ元の全節に、note を「注意」として付ける。
#                                      （例: 未確定の制度・薬機法・価格など、書き方に縛りがある話題）
#                                      付けすぎても害はない（注意は「触れるなら守れ」という条件付き）が、
#                                      漏れると縛りが下流に伝わらないので、words は広めに取る
AXIS_RULES: list[tuple[str, tuple[str, ...]]] = []
DEFAULT_AXIS = ""
CAUTIONS: list[dict] = []
FORMAT_NOTE = ""
TRUNCATED_SHORT_TITLES: list[str] = []

BLOCK_TAGS = {"p", "div", "li", "tr", "table", "ul", "ol", "aside", "h3", "h4", "figure", "figcaption", "blockquote", "br"}
# 中身ごと捨てる要素。img や use のような空要素は終了タグが来ないので入れない
# （入れると skip_depth が戻らず、以降の本文が全部消える）
SKIP_TAGS = {"svg", "script", "style", "nav"}


class SectionText(HTMLParser):
    """記事本文のHTML断片をプレーンテキストにする。

    表は「 | 」区切り、箇条書きは「・」、<mark>/<strong> は ** ** で残す（書き手が強調した箇所＝
    紹介の核）。対話形式の話者名・囲みのタイトルは、brand.yaml で class を指定したときだけ
    「話者: 発言」「【タイトル】」の形で残す。
    """

    def __init__(self, speaker_class: str = "", box_title_class: str = "") -> None:
        super().__init__(convert_charrefs=True)
        self.speaker_class = speaker_class
        self.box_title_class = box_title_class
        self.out: list[str] = []
        self.skip_depth = 0
        self.class_stack: list[str] = []
        self.pending_speaker: str | None = None
        self.name_buf: list[str] = []
        self.in_name = False
        self.in_box_title = False
        self.cell_open = False

    def _nl(self) -> None:
        if self.out and not self.out[-1].endswith("\n"):
            self.out.append("\n")

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        cls = dict(attrs).get("class", "") or ""
        if tag == "p" and self.speaker_class and self.speaker_class in cls.split():
            self.in_name = True
            self.name_buf = []
            return
        if tag == "p" and self.box_title_class and self.box_title_class in cls.split():
            self._nl()
            self.out.append("【")
            self.in_box_title = True
            return
        if tag in ("td", "th"):
            if self.cell_open:
                self.out.append(" | ")
            self.cell_open = True
            return
        if tag in ("mark", "strong"):
            self.out.append("**")
            return
        if tag in BLOCK_TAGS:
            self._nl()
            if tag == "tr":
                self.cell_open = False
            if tag == "li":
                self.out.append("・")
            if tag == "p" and self.pending_speaker:
                self.out.append(f"{self.pending_speaker}: ")
                self.pending_speaker = None

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if self.skip_depth:
            return
        if tag == "p" and self.in_name:
            # 話者名は閉じタグで確定する（<span> や改行で分割されて届いても落とさない）
            self.in_name = False
            self.pending_speaker = "".join(self.name_buf).strip() or None
            return
        if tag == "p" and self.in_box_title:
            self.out.append("】")
            self.in_box_title = False
            self._nl()
            return
        if tag in ("mark", "strong"):
            self.out.append("**")
            return
        if tag in BLOCK_TAGS:
            self._nl()

    def handle_data(self, data):
        if self.skip_depth:
            return
        if self.in_name:
            self.name_buf.append(data)
            return
        text = re.sub(r"\s+", " ", data)
        if text.strip():
            self.out.append(text.strip() if not self.out or self.out[-1].endswith("\n") else text)

    def text(self) -> str:
        raw = "".join(self.out)
        lines = [ln.strip() for ln in raw.splitlines()]
        return "\n".join(ln for ln in lines if ln)


def html_to_text(fragment: str, speaker_class: str = "", box_title_class: str = "") -> str:
    p = SectionText(speaker_class, box_title_class)
    p.feed(fragment)
    p.close()
    return p.text()


class ParseError(RuntimeError):
    pass


def find_tag_with_class(html: str, tag: str, cls: str, start: int = 0):
    """class 属性を空白で分けたトークンに cls を含む最初の <tag ...> の match を返す。
    並び順や追加クラスに依存せず、`article-body-extra` のような別クラスにも誤一致しない。"""
    for m in re.finditer(rf'<{tag}\b[^>]*\bclass="([^"]*)"[^>]*>', html[start:]):
        if cls in m.group(1).split():
            return m
    return None


def split_source_box(html: str, box_class: str) -> tuple[str, str]:
    """(出典ボックスの中身, 出典ボックスを取り除いたHTML) を返す。無ければ ("", html)。
    出典ボックスが複数あれば全部を集めて取り除く。中に aside が入れ子になっている形は
    閉じタグの対応を取れないので、部分的に抜き出して成功扱いにせず ParseError にする。"""
    if not box_class:
        return "", html
    boxes = []
    while True:
        m = find_tag_with_class(html, "aside", box_class)
        if not m:
            return "\n".join(boxes), html
        end = html.find("</aside>", m.end())
        if end == -1 or "<aside" in html[m.end():end]:
            raise ParseError(f"出典ボックス（{box_class}）の閉じタグが対応しません（入れ子の aside には未対応）")
        boxes.append(html[m.end():end])
        html = html[:m.start()] + html[end + len("</aside>"):]


def _mask_non_markup(html: str) -> str:
    """コメント・script・style の中身を同じ長さの空白に置き換える（位置はずらさない）。
    そこに書かれた `<article>` などの文字列をタグとして数えると、要素の境界を取り違える。"""
    def blank(m):
        return " " * len(m.group(0))
    html = re.sub(r"<!--.*?-->", blank, html, flags=re.S)
    return re.sub(r"<(script|style)\b[^>]*>.*?</\1\s*>", blank, html, flags=re.S | re.I)


def element_end(html: str, tag: str, start: int) -> int | None:
    """start（開始タグの直後）から数えて、その要素を閉じる終了タグの位置を返す。入れ子の同名タグを数える。"""
    depth = 1
    masked = _mask_non_markup(html)
    for m in re.finditer(rf"<(/?){tag}\b[^>]*>", masked[start:], re.I):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return start + m.start()
    return None


def strip_tags(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()


def derive_short_title(slug: str, title: str, overrides: dict, declared: str = "") -> str:
    """画面に出せる長さ（13字以内）の名前。brand.yaml の指定が最優先、次にネタ元の front matter。
    どちらも無ければタイトルを区切り記号の手前で切る（途中で切れた名前になりうるので、
    13字を超えるタイトルは short_titles に登録するのが確実）。"""
    if slug in overrides:
        return str(overrides[slug])
    if declared:
        return declared
    head = re.split(r"[？?｜|：:]", title, maxsplit=1)[0].strip()
    if len(head) > SHORT_TITLE_MAX:
        # 途中で切れた名前がそのまま画面・ナレーションに出る（実際に起きた）。結果に出して気づけるようにする
        TRUNCATED_SHORT_TITLES.append(f"{slug}: 「{head[:SHORT_TITLE_MAX]}」")
    return head[:SHORT_TITLE_MAX]


def pick_axis(heading: str) -> str:
    for axis, keywords in AXIS_RULES:
        if any(k in heading for k in keywords):
            return axis
    return DEFAULT_AXIS


def collect_cautions(slug: str, intro: str, text: str) -> list[str]:
    notes = []
    for c in CAUTIONS:
        words = tuple(c.get("words") or ())
        prefixes = tuple(c.get("slug_prefixes") or ())
        if (prefixes and slug.startswith(prefixes)) or any(w in intro or w in text for w in words):
            notes.append(str(c["note"]))
    return notes


def make_units(slug: str, title: str, short_title: str, url: str, updated: str,
               sources: list[str], intro: str, sections: list[tuple[str, str, str]]) -> list[dict]:
    """sections = [(見出し, アンカー, 本文テキスト), ...] から紹介ネタを作る（Markdown/HTML 共通）。"""
    if len(intro) > INTRO_MAX_CHARS:
        raise ParseError(f"{slug}: 導入部（最初の ## 見出しより前）が {len(intro)} 字あります。全節の根拠テキストに"
                         f"前提として全文を付けるので、{INTRO_MAX_CHARS} 字以内にしてください（本文は ## 見出しの下へ）")
    units = []
    for heading, anchor, text in sections:
        if len(text) < MIN_SECTION_CHARS:
            continue
        units.append({
            "theme": f"「{short_title}」より：{heading}",
            "strategy": pick_axis(heading),
            "article_slug": slug,
            "article_title": title,
            "short_title": short_title,
            "article_url": f"{url}#{anchor}" if url else "",
            "section_heading": heading,
            "section_anchor": anchor,
            "updated": updated,
            "cautions": collect_cautions(slug, intro, text),
            "intro": intro,
            "sources": sources,
            "_text": text,
        })
    if not units:
        # ネタ元なのに節が1つも取れないのは書式の問題。黙って索引から落とさない
        raise ParseError(f"{slug}: 紹介できる節（h2 見出しと {MIN_SECTION_CHARS}字以上の本文）が1つも取れません")
    for u in units:
        # 内容ハッシュ入りの不変パス（モジュール冒頭の「壊れ方への備え」）
        digest = hashlib.sha1(render_source_md(u).encode("utf-8")).hexdigest()[:8]
        u["source_path"] = f"content/articles/{slug}/{u['section_anchor']}-{digest}.md"
    return units


def parse_markdown(path: Path, short_titles: dict) -> list[dict]:
    """Markdown のネタ元。`## ` で節に分ける。書式は content/sources/README.md。"""
    raw = path.read_text(encoding="utf-8")
    slug = path.stem
    meta: dict = {}
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", raw, re.S)
    if m:
        meta = yaml.safe_load(m.group(1)) or {}
        if not isinstance(meta, dict):
            raise ParseError(f"{path.name}: 先頭の --- で囲んだ部分が「キー: 値」の形になっていません")
        raw = raw[m.end():]
    # コードブロック内の `## ` を見出しと誤認しない
    lines, chunks, cur_head, cur = raw.splitlines(), [], None, []
    h1 = ""
    fence = None  # 開いているコードフェンス (文字, 長さ)。CommonMark と同じく、同じ文字で同じ長さ以上の行だけが閉じる
    for ln in lines:
        in_fence = fence is not None
        fm = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", ln)
        if fm:
            ch, n, rest = fm.group(1)[0], len(fm.group(1)), fm.group(2)
            if fence is None:
                if not (ch == "`" and "`" in rest):  # バッククォートのフェンスは、情報文字列に ` を含められない
                    fence = (ch, n)
                    in_fence = True
            elif ch == fence[0] and n >= fence[1] and not rest.strip():
                fence = None
        if not in_fence and re.match(r"^#\s+\S", ln) and not h1 and cur_head is None:
            h1 = ln.lstrip("#").strip()
            continue
        if not in_fence and re.match(r"^##\s+\S", ln):
            chunks.append((cur_head, "\n".join(cur).strip()))
            cur_head, cur = ln.lstrip("#").strip(), []
            continue
        cur.append(ln)
    chunks.append((cur_head, "\n".join(cur).strip()))
    title = str(meta.get("title") or h1).strip()
    if not title:
        raise ParseError(f"{path.name}: タイトルがありません（先頭に `# タイトル` か front matter の title: を書く）")
    intro = next((t for h, t in chunks if h is None), "")
    sections = [(h, f"s{i}", t) for i, (h, t) in enumerate([c for c in chunks if c[0] is not None], 1)]
    src = meta.get("sources") or []
    if isinstance(src, str):
        src = [src]
    short = derive_short_title(slug, title, short_titles, str(meta.get("short_title") or "").strip())
    return make_units(slug, title, short, str(meta.get("url") or "").strip(),
                      str(meta.get("updated") or "").strip(), [str(x) for x in src], intro, sections)


def parse_html(path: Path, cfg: dict, short_titles: dict) -> list[dict]:
    """自サイトの記事HTML。本文の場所は brand.yaml の content_sources.html で指定する。"""
    # コメント・script・style の中身は最初に消す。そこに書かれた `<div class="article-body">` や <h1>・<h2> を
    # 本物のタグとして拾うと、本文の開始位置を取り違えて、広告や関連記事を根拠にしてしまう。
    # 開始タグ・終了タグ・h1・出典ボックス・見出しのすべてを、同じマスク済みの HTML から判定する
    html = _mask_non_markup(path.read_text(encoding="utf-8"))
    slug = path.stem
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    if not m:
        # 記事でないページは brand.yaml の content_sources.html.exclude で外す。黙って索引から落とさない
        raise ParseError(f"{path.name}: h1 が見つかりません（記事でないなら content_sources.html.exclude に追加する）")
    h1 = strip_tags(m.group(1))
    updated = ""
    if cfg.get("updated_pattern"):
        um = re.search(str(cfg["updated_pattern"]), html)
        updated = strip_tags(um.group(1)) if um and um.groups() else ""

    # 一次ソース（出典ボックス）。紹介投稿で出典名を正確に書くために渡す
    box_class = str(cfg.get("source_box_class") or "")
    sources: list[str] = []
    box, _ = split_source_box(html, box_class)
    if box:
        sources = [strip_tags(li) for li in re.findall(r"<li>(.*?)</li>", box, re.S)]

    # 本文の範囲。class 指定があればその div、無ければ <article> → <main> → <body> の順に探す
    body_class = str(cfg.get("body_class") or "")
    if body_class:
        bm = find_tag_with_class(html, "div", body_class)
        if not bm:
            raise ParseError(f"{path.name}: 本文（class に {body_class} を含む div）が見つかりません")
        start = bm.end()
        end = element_end(html, "div", start)
        if end is None:
            raise ParseError(f"{path.name}: 本文の div（{body_class}）の閉じタグが見つかりません")
        html = html[:end]  # 指定した要素の外（関連記事・広告・コメント欄など）は根拠にしない
    else:
        found = next(((t, x) for t, x in ((t, re.search(rf"<{t}\b[^>]*>", html)) for t in ("article", "main", "body")) if x), None)
        if not found:
            raise ParseError(f"{path.name}: 本文の範囲が分かりません（content_sources.html.body_class を指定する）")
        tag, bm = found
        start = bm.end()
        end = element_end(html, tag, start)
        if end is None:
            # 境界が決まらないまま文末までを本文にすると、要素の外（広告など）まで根拠になる。止める
            raise ParseError(f"{path.name}: 本文の要素 <{tag}> の閉じタグが見つかりません"
                             "（HTML が壊れているか、content_sources.html.body_class で本文の div を指定する）")
        html = html[:end]  # 選んだ要素の外（関連記事・広告・サイトのフッター）は根拠にしない
    body = _mask_non_markup(html)[start:]  # コメント・script の中の <h2> を節にしない
    # footer_class は、本文の要素の中をさらに手前で切るための指定（無ければ最初の <footer> の手前まで）
    foot_class = str(cfg.get("footer_class") or "")
    fm = find_tag_with_class(body, "footer", foot_class) if foot_class else None
    fm = fm or re.search(r"<footer\b", body)
    if fm:
        body = body[:fm.start()]
    speaker, box_title = str(cfg.get("speaker_class") or ""), str(cfg.get("box_title_class") or "")
    intro = strip_tags(re.split(r"<h2[\s>]", body, maxsplit=1)[0])
    parts = re.split(r'(<h2[^>]*>.*?</h2>)', body, flags=re.S)
    sections = []
    # parts = [導入, h2, 本文, h2, 本文, ...]
    for i in range(1, len(parts) - 1, 2):
        h2_html, section_html = parts[i], parts[i + 1]
        idm = re.search(r'id="([^"]+)"', h2_html)
        # 出典ボックスは節の本文ではない（別枠で渡す）
        _, section_html = split_source_box(section_html, box_class)
        sections.append((strip_tags(h2_html), idm.group(1) if idm else f"s{(i + 1) // 2}",
                         html_to_text(section_html, speaker, box_title)))
    base = str(cfg.get("base_url") or "").rstrip("/")
    return make_units(slug, h1, derive_short_title(slug, h1, short_titles),
                      f"{base}/{path.name}" if base else "", updated, sources, intro, sections)


def render_source_md(u: dict) -> str:
    lines = [
        "# 紹介するネタ元（この投稿の根拠）",
        "",
        f"- タイトル: {u['article_title']}",
        f"- 画面に出す短い名前（13字以内）: {u['short_title']}",
        f"- URL: {u['article_url'] or '（なし）'}",
        f"- 紹介する節: {u['section_heading']}",
        f"- 更新日: {u['updated'] or '不明'}",
        f"- テーマ軸: {u['strategy']}",
    ]
    lines += [f"- **注意（この節を扱うときの縛り）**: {c}" for c in u["cautions"]]
    if u.get("intro"):
        lines += [
            "",
            "## 全体の前提（ネタ元の導入部。この節にもかかる）",
            "",
            "書き手が全体にかけている前提・限定（「数値は概算」「事例は架空」「対象は〇〇の場合」など）が"
            "ここにあれば、この節を扱うときも必ず守る。ここに書かれた事実を投稿に使ってよい。",
            "",
            u["intro"],
        ]
    lines += [
        "",
        "## 節の本文",
        "",
        "投稿に書く事実・数字・資料名・日付は、**この節の本文・（あれば）上の「全体の前提」・下の「一次ソース」に"
        "書かれているものだけ**を使う。",
        "`**…**` は書き手が強調している箇所。" + (f" {FORMAT_NOTE}" if FORMAT_NOTE else ""),
        "",
        u["_text"],
        "",
        "## 依拠する一次ソース（資料名を書くときはこの表記に合わせる）",
        "",
    ]
    lines += [f"・{s}" for s in u["sources"]] or ["（記載なし）"]
    return "\n".join(lines) + "\n"


def interleave(by_article: list[list[dict]]) -> list[dict]:
    """記事をまたいで交互に並べる。theme-picker は記載順が早いものを優先するので、
    記事ごとに固めて並べると同じ記事の節が何日も続いてしまう。"""
    out, i = [], 0
    while any(by_article):
        for units in by_article:
            if i < len(units):
                out.append(units[i])
        i += 1
        if all(i >= len(units) for units in by_article):
            break
    return out


def write_if_changed(path: Path, content: str) -> bool:
    """中身が変わったときだけ、一時ファイル経由で置き換える。書いたら True。"""
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)
    return True


# --check のときは False にする。検証だけの実行で本番の成否記録を書き換えない
RECORD_STATE = True


def load_state() -> dict:
    """壊れている・型が違う state は空として扱う（退役日時は安全側＝いまから数え直しになる）。"""
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state = {}
    if not isinstance(state, dict):
        state = {}
    retired = state.get("retired")
    state["retired"] = {
        k: float(v) for k, v in (retired.items() if isinstance(retired, dict) else [])
        if isinstance(k, str) and isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float("inf")
    }
    return state


def save_retired(retired: dict) -> None:
    """退役日時だけを state に保存する（成否の記録には触れない）。失敗したら例外を上げる。"""
    state = load_state()
    state["retired"] = retired
    write_if_changed(STATE_FILE, json.dumps(state, ensure_ascii=False, indent=2) + "\n")


def record_state(ok: bool, detail: dict | str, retired: dict | None = None) -> None:
    """成否を残す。前回成功時刻は失敗しても消さない（いつから止まっているかを点検で出すため）。"""
    if not RECORD_STATE:
        return
    now = datetime.now(timezone.utc).isoformat()
    state = load_state()
    if ok:
        state.update({"last_ok_at": now, "last_error_at": None, "last_error": None, "summary": detail})
    else:
        state.update({"last_error_at": now, "last_error": str(detail)})
    if retired is not None:
        state["retired"] = retired
    try:
        write_if_changed(STATE_FILE, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    except OSError:
        pass  # 記録できなくても本処理の成否は変えない


def fail(msg: str) -> int:
    print(f"[error] {msg}", file=sys.stderr)
    record_state(False, msg)
    return 1


def rewrite_themes(units: list[dict]) -> bool:
    text = THEMES_FILE.read_text(encoding="utf-8")
    pos = text.find(STOCK_HEADING)
    if pos == -1:
        raise RuntimeError(f"{THEMES_FILE} に「{STOCK_HEADING}」見出しがありません")
    head = text[:pos]
    stock = [STOCK_HEADING, "",
             "<!-- この欄は build_article_index.py がネタ元から自動生成する。手で編集しても次の起動で上書きされる -->",
             ""]
    stock += [f"- [{u['strategy']}] {u['theme']}" for u in units]
    return write_if_changed(THEMES_FILE, head + "\n".join(stock) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="書き込まずに件数だけ表示する")
    args = ap.parse_args()

    if args.check:
        global RECORD_STATE
        RECORD_STATE = False
        try:
            return build(check=True)
        except ParseError as e:
            return fail(str(e))
    # Lite 版は1回ずつ対話で起動するので、同時実行を防ぐロック（元キットの fcntl。Windows に無い）は持たない
    try:
        return build(check=False)
    except ParseError as e:
        return fail(str(e))
    except Exception as e:  # 想定外の例外でも成否の記録は残す
        return fail(f"{type(e).__name__}: {e}")


def build(check: bool) -> int:
    global AXIS_RULES, DEFAULT_AXIS, CAUTIONS, FORMAT_NOTE
    brand = yaml.safe_load(BRAND_FILE.read_text(encoding="utf-8"))
    cs = brand.get("content_sources") or {}
    axes = brand.get("strategy_axes") or []
    if not axes:
        return fail("brand.yaml に strategy_axes がありません")
    AXIS_RULES = [(a["key"], tuple(a.get("keywords") or ())) for a in axes]
    DEFAULT_AXIS = str(cs.get("default_axis") or axes[0]["key"])
    if DEFAULT_AXIS not in {a["key"] for a in axes}:
        return fail(f"content_sources.default_axis「{DEFAULT_AXIS}」が strategy_axes にありません")
    CAUTIONS = [c for c in (cs.get("cautions") or []) if c.get("note")]
    FORMAT_NOTE = str(cs.get("format_note") or "").strip()
    short_titles = cs.get("short_titles") or {}

    by_article = []
    md_dir = cs.get("markdown_dir")
    if md_dir:
        src = (PROJECT_ROOT / md_dir).resolve()
        if not src.is_dir():
            return fail(f"Markdown のネタ元ディレクトリが見つかりません: {src}")
        for path in sorted(src.glob("*.md")):
            if path.name.lower() == "readme.md" or path.name.startswith("_"):
                continue  # 説明書きと、下書き（_ 始まり）はネタにしない
            by_article.append(parse_markdown(path, short_titles))
    html_cfg = cs.get("html") or {}
    if not isinstance(html_cfg, dict) or not isinstance(html_cfg.get("enabled", False), bool):
        return fail("content_sources.html.enabled は true か false（引用符なし）で書いてください"
                    "（\"false\" は文字列で、有効として扱われてしまう）")
    if html_cfg.get("enabled"):
        src = (PROJECT_ROOT / str(html_cfg.get("source_dir") or "")).resolve()
        if not html_cfg.get("source_dir") or not src.is_dir():
            return fail(f"記事HTMLのディレクトリが見つかりません: {src}")
        exclude = set(html_cfg.get("exclude") or [])
        for path in sorted(src.glob("*.html")):
            if path.name not in exclude:
                by_article.append(parse_html(path, html_cfg, short_titles))
    if not md_dir and html_cfg.get("enabled") is not True:
        return fail("brand.yaml の content_sources に markdown_dir も html も設定されていません")
    slugs = [u[0]["article_slug"] for u in by_article]
    if len(slugs) != len(set(slugs)):
        return fail(f"ネタ元のファイル名（拡張子を除く）が重複しています: {sorted({x for x in slugs if slugs.count(x) > 1})}")
    units = interleave(by_article)
    if not units and check:
        return fail("紹介ネタが1件もありません（content/sources/ に Markdown を置くか、content_sources.html を設定する）")
    # ネタ元がゼロ件でも失敗にはしない。空の索引を書く。失敗にすると前回の索引が残り、取り下げた文章
    # （削除した・`_` を付けて下書きに戻した）が無人投稿の根拠に使われ続ける。
    # 索引が空なら theme-picker が選定を断り、投稿せずに終わる
    # theme は投稿履歴との突合キー、source_path は根拠の置き場所。どちらも重複すると
    # 別の節が同じものとして扱われる（短い記事名の自動生成は13字で切るので衝突しうる）
    for key in ("theme", "source_path"):
        seen, dup = set(), set()
        for u in units:
            (dup if u[key] in seen else seen).add(u[key])
        if dup:
            return fail(f"{key} が重複しています: {sorted(dup)}（brand.yaml の content_sources.short_titles で短い名前を分ける）")

    too_long = sorted({u["short_title"] for u in units if len(u["short_title"]) > SHORT_TITLE_MAX})
    summary = {
        "articles": len(by_article),
        "units": len(units),
        "by_axis": {a: sum(1 for u in units if u["strategy"] == a) for a in sorted({u["strategy"] for u in units})},
        "short_title_over_limit": too_long,
        # 13字で自動的に切り詰めた名前。空でなければ、front matter の short_title か
        # brand.yaml の content_sources.short_titles に短い名前を登録する
        "short_title_truncated": sorted(set(TRUNCATED_SHORT_TITLES)),
    }
    if TRUNCATED_SHORT_TITLES:
        print("[warn] 短い名前を13字で切り詰めました（途中で切れた名前が画面に出ます）: "
              + " / ".join(sorted(set(TRUNCATED_SHORT_TITLES))), file=sys.stderr)
    if check:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    # 0) 今回の索引に入るパスの退役日時を、索引を切り替える**前に**消して保存する。
    #    後に回すと「復帰 → 途中で失敗 → 古い退役日時が残る → 次に外れた瞬間に削除」になる。
    #    保存に失敗したら例外で抜け、索引は切り替えない
    keep = {u["source_path"] for u in units}
    retired = {k: v for k, v in load_state()["retired"].items() if k not in keep}
    save_retired(retired)

    # 1) 節ファイル（変わったものだけ）
    written = sum(write_if_changed(PROJECT_ROOT / u["source_path"], render_source_md(u)) for u in units)
    # theme-picker が毎回読むので、選定に要る項目だけに絞って1件1行で書く（詳細は source_path の先にある）
    keys = ("theme", "strategy", "article_slug", "has_caution", "source_path")
    for u in units:
        u["has_caution"] = bool(u["cautions"])
    rows = [json.dumps({k: u[k] for k in keys}, ensure_ascii=False) for u in units]
    # 2) 索引 → 3) ネタ帳。ここまでは「新しい索引が指すファイルは必ずある」状態を保つ
    written += write_if_changed(INDEX_FILE, "[\n" + ",\n".join(rows) + "\n]\n")
    written += rewrite_themes(units)
    # 4) 索引から外れた古い節ファイルは、外れた日時から KEEP_STALE_DAYS 日たってから消す
    now_ts = time.time()
    removed = 0
    for old in ARTICLES_DIR.glob("*/*.md"):
        rel = old.relative_to(PROJECT_ROOT).as_posix()
        if rel in keep:
            continue
        retired.setdefault(rel, now_ts)  # 初めて索引から外れた（state が無い初回移行もここで起算）
        if now_ts - retired[rel] >= KEEP_STALE_DAYS * 86400:
            old.unlink()
            removed += 1
    retired = {k: v for k, v in retired.items() if (PROJECT_ROOT / k).exists()}
    for d in ARTICLES_DIR.iterdir():
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()
    summary.update({"files_written": written, "files_removed": removed})
    summary["files_retired"] = len(retired)
    record_state(True, summary, retired=retired)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
