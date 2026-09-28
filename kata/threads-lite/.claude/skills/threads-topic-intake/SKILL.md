---
name: threads-topic-intake
description: 最初に「テーマ」または「note記事(URL/本文)」を受け取り、その文体・主張・想定読者を抽出して topic-profile.json を作り、その文体を真似た7日分の投稿本文を draft-bank.json にストックするときに使う。「テーマは〇〇」「このnoteで投稿を作って」「7日分ストックして」「ネタを補充して」で起動する。投稿はしない（生成まで）。
---

# Threads Topic Intake（テーマ取り込み → 文体模倣で7日分ストック）

最初に入力したテーマ/note を「発信の核」に変換し、その**文体を真似た7日分の投稿**を作って
ストックする。投稿そのものは行わない（投稿は threads-publishing スキルの担当）。

## 入力の2系統

1. **テーマ文字列**: 例「個人開発で月5万円を作るまで」
2. **note**: URL または貼り付け本文。URL のときは `WebFetch` で本文を取得して読む。

note が複数あれば全部読む（文体精度が上がる）。

## ワークフロー

### A. profile を作る（`data/topic-profile.json`）

1. 入力（テーマ / note 本文）を読む。note URL は WebFetch で取得。
2. 次を抽出して `topic-profile.json` を更新し、`active` を `true` にする:
   - `theme`: 発信の中心テーマ（短文）
   - `audience`: 想定読者
   - `voice`: **文体の特徴を箇条書き**（一人称・語尾・改行癖・絵文字有無・断定/問いかけ・句読点の癖など）。
     これが模倣の基準になるので具体的に。
   - `claims`: 繰り返し伝えたい主張（3〜6個）
   - `keywords`: 投稿に登場させたい語
   - `ngWords`: 避ける語・煽り表現
   - `sourceNotes`: 参照した note の URL か引用
   - `hashtags`: 毎回付ける固定タグ（不要なら空配列）
3. profile をユーザーに見せて**合意を取る**（特に voice と claims）。ズレていれば直す。

### B. 7日分をストックする（`data/draft-bank.json`）

4. profile の `voice` を**忠実に模倣**して、投稿本文を**7件**書く。
   - 7件は **切り口（angle）を変える**: 体験談 / 失敗談 / Tips / 問いかけ / 数字 / 逆張り / まとめ など。
   - 各本文は**500文字以内**（ハッシュタグ前で計算）。
   - `claims` のどれかを必ず1つ含める。`ngWords` は使わない。
   - 過去投稿（`data/threads-posts.json`）と内容が被らないようにする。
5. `draft-bank.json` の `items` に `{ body, angle, dayOffset }` を7件入れ、
   `profileTheme` と `generatedAt` を埋める。
6. 変換スクリプトで投稿キューに反映する:

   ```bash
   npm run threads:drafts -- --from-bank
   ```

   `data/threads-drafts.json` の `mode` が `profile-bank`、`drafts` が7件になっていれば成功。

### C. セルフチェック（出す前に必ず）

- [ ] 各本文 ≤ 500文字
- [ ] `ngWords` を含まない
- [ ] `data/threads-posts.json` の既投稿と本文が重複しない
- [ ] 7件の angle が散っている（同じ切り口の連発でない）
- [ ] voice（文体）が profile と一致している

## 補充（ストックが減ったら）

「ネタを補充して」と言われたら、A はスキップ（profile は既にある）。
B から再実行し、**過去投稿と既存 bank に被らない**新しい7件を作って `--from-bank` で反映する。

## ガードレール

- ここでは**投稿しない**。生成と保存まで。
- 事実を捏造しない。読者を煽らない。
- token / user ID / secret を読まない・書かない。
- profile の `active` を true にするのは、ユーザーが内容に合意してから。
