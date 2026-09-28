---
name: threads-growth
description: Threads運用の全体（テーマ取り込み→7日分ストック→今日の1本→手で投稿→記録→補充）を段取りするときに使う。「Threadsを回して」「今日の分をまとめてやって」「全体の段取り」を頼まれたら起動する。投稿は人が手で行う。
---

# Threads Growth（全体の段取り・Lite 版）

## 設計の核（3つを分離する）

- **人格 / 戦略**: `data/topic-profile.json` と `.claude/skills/` が「どんな投稿が存在すべきか」を決める
- **決定的実行**: `scripts/` が変換・重複スキップ・書き出し・記録をする（AI を使わない）
- **人の判断**: 投稿するかどうかと、投稿そのものは人が行う

## 流れ

```
1. テーマ／文章を取り込む（初回だけ）   threads-topic-intake の A
2. 7日分の本文をストックする            threads-topic-intake の B → npm run threads:drafts -- --from-bank
3. 今日の1本を出す                      npm run threads:today   → output/today.txt
4. 人が Threads アプリに貼って投稿する
5. 投稿を記録する                        npm run threads:posted
6. ストックが減ったら補充する            「ネタを補充して」→ threads-topic-intake の B
```

「Threadsを回して」と頼まれたら、状態を見て次の1手だけ進める。

| 状態 | やること |
|---|---|
| `data/topic-profile.json` の `active` が false | テーマか文章を聞く（1へ） |
| まだ投稿していない下書きが無い | 補充する（6へ） |
| 今日まだ出していない | 3を実行し、`output/today.txt` の中身を見せる。投稿したら「投稿した」と言ってもらう |
| 今日はもう記録済み | 何もしない。明日また頼んでもらう |

## データの場所

- 発信の核: `data/topic-profile.json`
- 本文のストック: `data/draft-bank.json`
- 下書きキュー: `data/threads-drafts.json`
- 投稿の記録: `data/threads-posts.json`（手で投稿したものは `status: "posted-manual"`）
- 今日の1本: `output/today.txt`

## 安全ルール

- 投稿本文は500文字以内。事実を作らない。読者を煽らない
- 人が「投稿した」と言う前に `threads:posted` を実行しない（記録と実際がずれる）
- 自動投稿・反応の取得・定期実行は `addons/threads-api/`。本体からは使わない
