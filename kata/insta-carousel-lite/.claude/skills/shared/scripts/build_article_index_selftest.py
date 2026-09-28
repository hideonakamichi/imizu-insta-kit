#!/usr/bin/env python3
"""build_article_index.py の回帰テスト（一時フォルダの中だけで動く。実際の content/ には触れない）

    python3 .claude/skills/shared/scripts/build_article_index_selftest.py
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("bai", HERE / "build_article_index.py")
bai = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bai)

failures = 0
BODY = "これは節の本文です。" * 25  # 200字以上


def check(name, got, want):
    global failures
    ok = got == want
    failures += not ok
    print(f"[{'ok' if ok else 'NG'}] {name} → {got!r}" + ("" if ok else f" (期待: {want!r})"))


BRAND = """
strategy_axes:
  - {key: how-to, label: 手順, description: d, keywords: [手順]}
  - {key: checklist, label: 確認, description: d, keywords: [チェック]}
content_sources:
  markdown_dir: content/sources
  cautions:
    - note: "未確定の話は検討中と明記する"
      words: ["検討中"]
"""


def sandbox(td: Path, files: dict[str, str]):
    """bai のパス定数を一時フォルダに向け、ネタ元を置く。"""
    (td / "config").mkdir(parents=True)
    (td / "content" / "sources").mkdir(parents=True)
    (td / "logs").mkdir()
    (td / "config" / "brand.yaml").write_text(BRAND, encoding="utf-8")
    (td / "content" / "themes.md").write_text("# ネタ帳\n\n## ストック\n\n", encoding="utf-8")
    for name, text in files.items():
        (td / "content" / "sources" / name).write_text(text, encoding="utf-8")
    bai.PROJECT_ROOT = td
    bai.BRAND_FILE = td / "config" / "brand.yaml"
    bai.THEMES_FILE = td / "content" / "themes.md"
    bai.ARTICLES_DIR = td / "content" / "articles"
    bai.INDEX_FILE = bai.ARTICLES_DIR / "index.json"
    bai.STATE_FILE = td / "logs" / "article_index_state.json"
    bai.LOCK_FILE = td / "logs" / "locks" / "article_index.flock"
    bai.TRUNCATED_SHORT_TITLES.clear()


def build(files):
    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        sandbox(td, files)
        sys.argv = ["build_article_index.py"]
        code = bai.main()
        index = json.loads(bai.INDEX_FILE.read_text(encoding="utf-8")) if bai.INDEX_FILE.exists() else None
        sources = {p.name: p.read_text(encoding="utf-8") for p in bai.ARTICLES_DIR.glob("*/*.md")} if bai.ARTICLES_DIR.exists() else {}
        return code, index, sources


# --- コードフェンス内の「## 見出し」を節にしない --------------------------------
md = f"# 題\n\n導入。\n\n## 本物の手順\n\n{BODY}\n\n~~~markdown\n## チルダの中の見出し\n{BODY}\n~~~\n"
code, index, _ = build({"a.md": md})
check("~~~ の中の見出しは節にならない", [u["theme"] for u in index], ["「題」より：本物の手順"])

md = f"# 題\n\n## 本物の手順\n\n{BODY}\n\n````md\n```\n## 4本フェンスの中\n{BODY}\n```\n````\n\n## 次のチェック\n\n{BODY}\n"
code, index, _ = build({"a.md": md})
check("4本フェンスの中の3本フェンスで境界が崩れない", [u["theme"] for u in index],
      ["「題」より：本物の手順", "「題」より：次のチェック"])
check("見出しのキーワードで軸が分かれる", [u["strategy"] for u in index], ["how-to", "checklist"])

md = f"# 題\n\n## 本物の手順\n\n{BODY}\n\n```\n## 閉じ忘れたフェンスの中\n{BODY}\n"
code, index, _ = build({"a.md": md})
check("閉じ忘れたフェンス以降は節にならない", [u["theme"] for u in index], ["「題」より：本物の手順"])

# --- 導入部の前提が根拠テキストに残る -------------------------------------------
md = f"# 題\n\n以下の数値と事例はすべて架空です。\n\n## 本物の手順\n\n{BODY}\n"
code, index, sources = build({"a.md": md})
text = next(iter(sources.values()))
check("導入部の限定が根拠テキストに残る", "以下の数値と事例はすべて架空です。" in text, True)

# --- 注意書き（導入部の語でも付く） ---------------------------------------------
md = f"# 題\n\nこの制度は検討中です。\n\n## 本物の手順\n\n{BODY}\n"
code, index, sources = build({"a.md": md})
check("導入部に words があれば has_caution", index[0]["has_caution"], True)
check("注意書きが根拠テキストの冒頭に出る", "未確定の話は検討中と明記する" in next(iter(sources.values())), True)

# --- 取り下げたネタ元が索引に残らない -------------------------------------------
with tempfile.TemporaryDirectory() as d:
    td = Path(d)
    sandbox(td, {"a.md": f"# 題\n\n## 本物の手順\n\n{BODY}\n"})
    sys.argv = ["build_article_index.py"]
    bai.main()
    before = len(json.loads(bai.INDEX_FILE.read_text(encoding="utf-8")))
    (td / "content/sources/a.md").rename(td / "content/sources/_a.md")  # 下書きに戻す
    code = bai.main()
    after = json.loads(bai.INDEX_FILE.read_text(encoding="utf-8"))
    check("最後の1本を下書きに戻す前は1件", before, 1)
    check("下書きに戻したら exit 0（失敗扱いにしない）", code, 0)
    check("下書きに戻したら索引は空になる（古い索引が残らない）", after, [])
    check("ネタ帳のストックも空になる", "本物の手順" in bai.THEMES_FILE.read_text(encoding="utf-8"), False)

# --- 導入部は切り捨てない。長すぎたら失敗させる ---------------------------------
long_intro = "前置き。" * 150 + "以下の数値と事例はすべて架空です。"
md = f"# 題\n\n{long_intro[:1900]}以下の数値はすべて架空です。\n\n## 本物の手順\n\n{BODY}\n"
code, index, sources = build({"a.md": md})
check("長い導入部の末尾の限定も根拠テキストに残る", "以下の数値はすべて架空です。" in next(iter(sources.values())), True)
code, index, _ = build({"a.md": f"# 題\n\n{'長い導入。' * 500}\n\n## 本物の手順\n\n{BODY}\n"})
check("上限を超える導入部は、切り捨てずに exit 1", code, 1)

# --- HTML: 指定した本文 div の外は根拠にしない ------------------------------------
HTML_BRAND = BRAND.replace("  markdown_dir: content/sources", "  html: {enabled: true, source_dir: site, body_class: article-body}")
def build_html(html, brand=HTML_BRAND):
    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        sandbox(td, {})
        (td / "config" / "brand.yaml").write_text(brand, encoding="utf-8")
        (td / "site").mkdir()
        (td / "site" / "post.html").write_text(html, encoding="utf-8")
        sys.argv = ["build_article_index.py"]
        code = bai.main()
        index = json.loads(bai.INDEX_FILE.read_text(encoding="utf-8")) if bai.INDEX_FILE.exists() else None
        return code, index
page = f"""<html><body><h1>題</h1><div class="wrap article-body"><p>導入</p>
<h2>本文の手順</h2><div class="inner"><p>{BODY}</p></div></div>
<aside><h2>関連記事の手順</h2><p>{BODY}</p></aside><footer>f</footer></body></html>"""
code, index = build_html(page)
check("本文 div の外にある見出し（関連記事）は節にならない", [u["theme"] for u in index], ["「題」より：本文の手順"])

# --- HTML: body_class なし（article を自動選択）でも、article の外は根拠にしない -----
AUTO_BRAND = BRAND.replace("  markdown_dir: content/sources", "  html: {enabled: true, source_dir: site}")
page2 = f"""<html><body><h1>題</h1><article><p>導入</p><h2>本文の手順</h2><p>{BODY}</p></article>
<aside><h2>広告の手順</h2><p>{BODY}</p></aside><footer class="site-footer">f</footer></body></html>"""
for label, brand in [("footer_class なし", AUTO_BRAND),
                     ("footer_class あり", AUTO_BRAND.replace("source_dir: site}", "source_dir: site, footer_class: site-footer}")),
                     ("該当しない footer_class", AUTO_BRAND.replace("source_dir: site}", "source_dir: site, footer_class: no-such}"))]:
    code, index = build_html(page2, brand)
    check(f"article の外の見出し（広告）は節にならない（{label}）", [u["theme"] for u in index], ["「題」より：本文の手順"])

# --- HTML: コメントの中のタグで境界を取り違えない／閉じタグが無ければ失敗 ----------
page3 = f"""<html><body><h1>題</h1><article><!-- <article> は記事本文を囲む要素 --><p>導入</p>
<h2>本文の手順</h2><p>{BODY}</p><!-- <h2>コメントの中の見出し</h2> --></article>
<aside><h2>外部広告の手順</h2><p>{BODY}</p></aside></body></html>"""
code, index = build_html(page3, AUTO_BRAND)
check("コメント内の <article>・<h2> に惑わされない", [u["theme"] for u in index], ["「題」より：本文の手順"])
page4 = f"<html><body><h1>題</h1><article><h2>本文の手順</h2><p>{BODY}</p><aside><h2>広告の手順</h2><p>{BODY}</p></aside></body></html>"
code, index = build_html(page4, AUTO_BRAND)
check("<article> の閉じタグが無ければ exit 1（文末までを本文にしない）", code, 1)

# --- HTML: 本物の本文より前に、コメントの中の偽の開始タグがある ---------------------
page5 = f"""<html><body><h1>題</h1><div class="wrap"><div class="ad"><!-- <div class="article-body"> -->
<h2>広告の宣伝の手順</h2><p>{BODY}</p></div>
<div class="article-body"><p>導入</p><h2>本文の手順</h2><p>{BODY}</p></div></div></body></html>"""
code, index = build_html(page5)
check("コメント内の偽の開始タグより、本物の本文 div を選ぶ（広告を取り込まない）", [u["theme"] for u in index], ["「題」より：本文の手順"])
page6 = f"""<html><body><h1>題</h1><!-- <div class="article-body"> --><div class="other"><h2>広告の手順</h2><p>{BODY}</p></div></body></html>"""
code, index = build_html(page6)
check("指定した class がコメントの中にしか無ければ exit 1", code, 1)

# --- html.enabled が文字列なら失敗（無効にしたつもりのHTMLを取り込まない） ---------
code, index = build_html(page, HTML_BRAND.replace("enabled: true", 'enabled: "false"'))
check('html.enabled: "false"（文字列）は exit 1', code, 1)

# --- 短い名前の切り詰めを知らせる -----------------------------------------------
md = f"# とても長いタイトルなので十三字では収まらない記事\n\n## 本物の手順\n\n{BODY}\n"
build({"a.md": md})
check("13字で切り詰めたら記録する", len(bai.TRUNCATED_SHORT_TITLES), 1)

# --- 壊れた front matter は失敗（黙って索引から落とさない） -----------------------
code, index, _ = build({"a.md": "---\n- これはリスト\n---\n# 題\n\n## 手順\n\n" + BODY})
check("front matter が「キー: 値」でなければ exit 1", code, 1)

print()
if failures:
    print(f"{failures} 件 失敗")
    sys.exit(1)
print("チェックはすべて期待どおり")
