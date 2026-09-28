---
name: threads-publishing
description: 承認済みThreads下書きのチェック・ドライラン・投稿・記録をローカルスクリプトやThreads API経由で行うときに使う。「投稿する」「ドライランする」「公開する」と頼まれたら起動する。デフォルトはドライラン。
---

# Threads Publishing（投稿）

## 入力

- 下書きキュー: `data/threads-drafts.json`
- 投稿記録: `data/threads-posts.json`
- ローカルシークレット: `.env.local`（コミット禁止）

## ワークフロー

1. 下書きを1件選ぶ。
2. 500文字以内であることを確認する。
3. デフォルトでドライランする。
4. live モードでは token / user ID を検証する。
5. Threadsコンテナを作成する。
6. 投稿前に待機する。
7. コンテナを公開する。
8. 結果を記録する。

## コマンド

```bash
# ドライラン（デフォルト・安全）
npm run threads:publish

# live投稿（明示的な意図があるときだけ）
npm run threads:publish -- --skip-posted --skip-today --live
```

## ガードレール

- token を絶対に出力しない。
- 明示的な意図なしに live投稿しない。
- 本文が重複する下書きはスキップする。
- スケジュール実行では同日既投稿ならスキップする。
- token / user ID 欠如、重複、同日既投稿のいずれかで停止する。
