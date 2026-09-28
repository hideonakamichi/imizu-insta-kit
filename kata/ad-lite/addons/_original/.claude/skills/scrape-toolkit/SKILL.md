---
name: scrape-toolkit
description: Scrape専門スキル。ad-scraper サブエージェントが呼ぶ実行手順。Meta(Facebook/Instagram)広告ライブラリをスクレイプし、競合の広告コピー(body_text)を収集して manifest.jsonl に書き出す。「競合広告を収集」「Meta広告をスクレイプ」など、競合コピー収集の実コマンドが必要なときに参照する。
allowed-tools: Bash(.venv/bin/python *), Read, Write, Edit, Glob, Grep
---

# scrape-toolkit — ステージ1: 競合広告コピーの収集

Meta広告ライブラリをスクレイプし、競合の広告コピー（body_text）を集める。**APIキー不要**。
Chromiumが実起動するので画面が開く（headless=False）。

設計の*理由*（なぜコピーで空きポジを測るのか等）は [../../../design.md](../../../design.md) を参照。

## 前提（最初に必ず確認）

- **作業ディレクトリ**: コマンドは `creative-pipeline-orchestrated/`（プロジェクト直下）からの相対パス。
  別の場所から打つ場合は絶対パスに読み替える（Bashツールは呼び出しごとにcwdがリセットされるため `cd` は基本不要）。
- **Python**: `.venv/bin/python` を使う（システムpythonではない）
- **スクリプト**: このスキル内 `.claude/skills/scrape-toolkit/scripts/scrape.py`
  （スクリプトは自分の位置からプロジェクトルートを解決する）
- 未セットアップなら [../../../SETUP.md](../../../SETUP.md) を先に実行する

```
.venv/bin/python                                       # = PY
.claude/skills/scrape-toolkit/scripts                  # = S
```

出力は `data/<日付>_<クエリ>/` 配下に閉じる。`data/` ルートは汚さない。

---

## 実行

```bash
$PY $S/scrape.py --query "<キーワード>" --limit 100
```

主なオプション:
- `--query`（必須）: 調べたい商品・市場の検索キーワード
- `--limit`: 収集件数の上限（**既定30**。分析の質には50〜100推奨なので上の例では100を指定）
- `--search-type`: `unordered`(単語含有・既定) / `exact`(完全一致)
- `--active-status`: `active`(配信中のみ・既定) / `all`(過去配信も)
- `--with-images`: 画像もDLする（既定OFF。分析はコピーだけで動くので通常不要）

出力: `data/<日付>_<query>/manifest.jsonl`（1行=1広告）

> **判断ポイント**: 件数が3件未満だと次の Analyze が動かない。少なければ `--limit` を上げるか、
> 別キーワードでもう1回 scrape して Analyze で複数 `--data-dir` をマージする。

## 呼び出し元への返却

収集が終わったら、次の情報を呼び出し元（orchestrator）に返す:
- 出力した `manifest.jsonl` のパス
- 収集できた件数（3件未満なら不足を明示）

## トラブルシュート

- `初期SSRから search_results_connection が見つかりません` → Metaのページ構造変化。`data/<>/debug.html` を確認
- スクレイプでログインを求められたら → `.browser_profile/` に手動ログイン状態が保持される（次回以降不要）
