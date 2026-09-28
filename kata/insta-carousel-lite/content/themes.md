# ネタ帳（紹介ネタの一覧）

このファイルの「ストック」欄は `build_article_index.py` がネタ元から**自動生成**する
（carousel スキルが起動のたびに実行）。手で編集しても次の起動で上書きされる。
ネタを増やしたいときは、`content/sources/` に文章（Markdown）を足す。
置き場所と書式は `content/sources/README.md`、設定は `config/brand.yaml` の `content_sources`。

・`theme-picker` は `content/articles/index.json`（同じ内容の索引）を読んで1件選ぶ
・節ごとの根拠テキストは `content/articles/<スラッグ>/<節ID>-<内容ハッシュ>.md`
・`[ ]` 内は `config/brand.yaml` の `strategy_axes` の key（見出しのキーワードから自動で振り分け）

**注意**: このファイルの説明文で `- ` 始まりの箇条書きを使わないこと
（テーマ行と区別がつかなくなる）。説明の箇条書きには `・` を使う。

## ストック

<!-- この欄は build_article_index.py がネタ元から自動生成する。手で編集しても次の起動で上書きされる -->

