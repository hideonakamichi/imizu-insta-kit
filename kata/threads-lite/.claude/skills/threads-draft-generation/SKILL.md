---
name: threads-draft-generation
description: Threadsの投稿下書き候補・戦略・フック・仮説・安全なコピーを生成またはレビューするときに使う。「下書きを作る」「投稿案を出す」「フックを考える」と頼まれたら起動する。投稿は行わない。
---

# Threads Draft Generation（下書き生成）

## 入力

- `data/topics.json`
- `data/threads-posts.json`
- `data/threads-performance.json`
- `data/post-plan.json`（最初の／優先テーマの指定。任意）

## 生成モードは2つ

1. **profile-bank モード（推奨・文体模倣）**: `data/topic-profile.json` が `active:true` で
   `data/draft-bank.json` に本文があるとき。最初に入力したテーマ/note の**文体を真似た**投稿を出す。
   本文を作るのは `threads-topic-intake` スキル。ここでは変換だけ:

   ```bash
   npm run threads:drafts -- --from-bank
   ```

   テーマ入力・文体抽出・7日分ストックは `threads-topic-intake` スキルに従う。

2. **topic-fallback モード**: profile が無い／active でないとき。`data/topics.json` から
   最小の下書きを作る後方互換動作。

生成後は `threads-drafts.json` の `mode`（`profile-bank` / `topic-fallback`）と
各ドラフトの `metadata.plannedBy` で、どちらで出たか確認する。

## 最初のテーマの指定（旧方式）

`topic-profile.json` を使わない場合のみ、`data/post-plan.json` の `firstPost` / `pinned` で
優先トピックを指定できる（topic-fallback 用）。新方式では通常は空でよい。

## ワークフロー

1. トピックデータを読む。
2. 直近の投稿を読み、本文の重複と戦略の重複を避ける。
3. 計測データがあれば読む。
4. 複数の下書き候補を生成する。
5. 後の分析のために戦略メタデータを保存する。
6. すべての下書き本文を500文字以内にする。

## 決定的生成

手作業でコピーを書く前に、まず決定的スクリプトを使う:

```bash
npm run threads:drafts
```

結果は `data/threads-drafts.json` に入る。`strategy` / `hypothesis` / `metadata` を確認する。

## レビュールール

- 事実を捏造しない。
- 読者を煽らない。
- 直接宣伝よりも、役立つ・内省的な投稿を優先する。
- 各仮説を計測可能にする。
- 直近投稿の回避に関するメタデータを含める。

## 出力

- strategy
- hypothesis
- body
- リスク注記
- 推奨ステータス（status）
