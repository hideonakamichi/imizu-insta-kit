# 記事キット Lite（書く役と査読役を分ける）

執筆担当と査読担当を別のエージェントにし、合格した記事だけを残す。題材は元のキットのまま
「ひとり親家庭が使える公的支援制度」。別テーマへの読み替えは `addons/_original/README.md` の付録B。

## 入口

| 頼まれたこと | やること |
|---|---|
| 「ライター (support-writer) で supports id=1 の記事を書いて」 | `support-writer` エージェント |
| 「レビュアー (support-reviewer) で supports id=1 の記事を査読して」 | `support-reviewer` エージェント |
| 「編集長 (support-orchestrator) でパイプラインを1周回して」 | `support-orchestrator` エージェント |
| 「記事を書き出して」 | `bash scripts/export-articles.sh` → `output/` |
| 「記事を点検して」 | `bash scripts/article-health-check.sh --quick` |

## Lite 版の違い（元のキットから）

- **データベースは `data/*.json`。** `scripts/supabase-query.sh` は元と同じ使い方で、手元のファイルを読み書きする。
  jq の代わりに `set`（列をまとめて書く）と `append`（JSON の配列に足す）がある
- **実行記録は `bash scripts/agents-db.sh "SQL"`。** sqlite3 コマンドの代わり（Windows に標準で入っていないため）
- **図解画像は既定で作らない。** `config/features.json` の `images` が `true` のときだけ作り、査読でも求める
- **サイト（Next.js）と定期実行は `addons/site-db/`。** 記事は `output/` に Markdown とプレビューで書き出す

## コマンドの実行

- `bash scripts/...` は **Bash ツール**で、このフォルダをカレントにして実行する。Windows でも PowerShell ツールは使わない
- Python は Windows `py` ／ Mac `python3`
