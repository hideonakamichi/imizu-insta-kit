"""書き上がった記事を output/ に書き出す（Lite 版の出し先）。

使い方:  bash scripts/export-articles.sh            （記事がある全件）
         bash scripts/export-articles.sh 4 11       （ID を指定）
1件ごとに output/<id>-<program_code>/ を作り、次の3つを置く:
  article.md          記事本文（対話形式の Markdown）
  preview.html        ブラウザで確かめる簡易プレビュー（md2preview.py）
  research_notes.json 調べた根拠と、査読の記録
"""
import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    want = {int(a) for a in sys.argv[1:]}
    rows = json.loads((ROOT / "data" / "supports.json").read_text(encoding="utf-8"))
    done = 0
    for r in rows:
        if not r.get("article_md") or (want and r["id"] not in want):
            continue
        d = ROOT / "output" / f"{r['id']}-{r.get('program_code') or 'article'}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "article.md").write_text(r["article_md"], encoding="utf-8")
        (d / "research_notes.json").write_text(
            json.dumps(r.get("research_notes"), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        title = r.get("article_title") or r.get("title") or ""
        subprocess.run([sys.executable, str(ROOT / "scripts" / "md2preview.py"),
                        str(d / "article.md"), str(d / "preview.html"), title], check=True)
        verdicts = (r.get("research_notes") or {}).get("reviewer_verifications") or []
        state = verdicts[-1].get("overall_verdict", "?") if verdicts else "査読の記録なし"
        print(f"[ok] {d.relative_to(ROOT)}  {len(r['article_md'])}字  査読: {state}")
        done += 1
    if not done:
        print("[info] 書き出す記事がありません（article_md が空）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
