---
name: threads-publishing
description: 今日投稿する1本を選んで output/today.txt に書き出し、人が手で投稿したあとに記録するときに使う。「今日の1本を出して」「投稿した」「記録して」と頼まれたら起動する。Threads への投稿そのものは人が行う。
---

# Threads Publishing（今日の1本と記録・Lite 版）

## 今日の1本を出す

```bash
npm run threads:today
```

- まだ投稿していない下書きの先頭を選び、`output/today.txt` に書き出す
- 今日すでに記録があれば `SKIP` で止まる（1日1本まで）
- 下書きが尽きていたら、止まって補充を促す。「ネタを補充して」で `threads-topic-intake` を使う

`output/today.txt` の中身をそのまま人に見せ、Threads アプリに貼って投稿してもらう。

## 投稿したあとに記録する

人が「投稿した」と言ったら実行する。

```bash
npm run threads:posted
```

投稿の URL を残したいときは `npm run threads:posted -- --post-url=<URL>`。

## ガードレール

- 人が「投稿した」と言う前に記録しない
- 本文を書き換えて投稿したときも、そのまま記録してよい（重複の判定は下書き側の本文で行う）
- API での投稿は `addons/threads-api/` の作り。ここでは使わない
