"""記事の Markdown を、ブラウザで確かめる preview.html にし、本文の文字数を数える。

使い方:  py .claude/skills/note-writing/scripts/note-preview.py output/<スラッグ>/article.md   （Mac は python3）
同じフォルダに preview.html を書き出す。本文が 800 字未満なら exit 1。
元のキットの note-publish.py の読み取り規則を使っている（見出し・引用・箇条書き・コード・区切り線）。
"""
import html
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

MIN_CHARS = 800


def inline(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    s = re.sub(r"\[(.+?)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', s)
    return s


def plain(s: str) -> str:
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"`(.+?)`", r"\1", s)
    return re.sub(r"\[(.+?)\]\((.+?)\)", r"\1", s)


def convert(md: str):
    lines = md.split("\n")
    out, text, title = [], [], None
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("# ") and title is None:
            title = line[2:].strip()
            i += 1
        elif line.startswith("## ") or line.startswith("### "):
            lv = 2 if line.startswith("## ") else 3
            body = line[lv + 1:].strip()
            out.append(f"<h{lv}>{inline(body)}</h{lv}>")
            text.append(plain(body))
            i += 1
        elif line.startswith("```"):
            i += 1
            code = []
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            out.append("<pre>" + html.escape("\n".join(code)) + "</pre>")
        elif line.startswith(">"):
            q = []
            while i < len(lines) and lines[i].startswith(">"):
                q.append(lines[i].lstrip(">").strip())
                i += 1
            out.append("<blockquote>" + "<br>".join(inline(x) for x in q) + "</blockquote>")
            text.extend(plain(x) for x in q)
        elif line.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(lines[i][2:])
                i += 1
            out.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ul>")
            text.extend(plain(x) for x in items)
        elif line.strip() == "---":
            out.append("<hr>")
            i += 1
        elif not line.strip() or line.strip().startswith("<!--"):
            i += 1
        else:
            out.append(f"<p>{inline(line.strip())}</p>")
            text.append(plain(line.strip()))
            i += 1
    return title, "\n".join(out), len("".join(text).replace(" ", ""))


PAGE = """<!doctype html><html lang="ja"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
body{{max-width:620px;margin:0 auto;padding:24px 16px;font-family:"Yu Gothic UI","Hiragino Sans",sans-serif;line-height:1.9;color:#222;background:#fff}}
h1{{font-size:1.5em;line-height:1.4}} h2{{font-size:1.25em;margin-top:2em}} h3{{font-size:1.05em}}
blockquote{{margin:1em 0;padding:.6em 1em;background:#f3f3f3;border-left:4px solid #ccc}}
pre{{background:#f6f6f6;padding:1em;overflow:auto}} .meta{{color:#666;font-size:.85em;border-bottom:1px solid #ddd;padding-bottom:.5em}}
</style>
<p class="meta">プレビュー（note での見え方とは少し違います）／本文 {chars} 字</p>
<h1>{title}</h1>
{body}
</html>
"""


def main() -> int:
    if len(sys.argv) != 2:
        print("使い方: note-preview.py output/<スラッグ>/article.md")
        return 2
    src = Path(sys.argv[1])
    title, body, chars = convert(src.read_text(encoding="utf-8"))
    if not title:
        print("[error] 1行目に「# タイトル」がありません")
        return 1
    dst = src.with_name("preview.html")
    dst.write_text(PAGE.format(title=html.escape(title), body=body, chars=chars), encoding="utf-8")
    print(f"[ok] {dst} を書き出しました（本文 {chars} 字）")
    if chars < MIN_CHARS:
        print(f"[error] 本文が {MIN_CHARS} 字未満です。書き足してください")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
