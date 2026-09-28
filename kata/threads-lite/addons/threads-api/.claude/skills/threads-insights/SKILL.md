---
name: threads-insights
description: Threadsの計測値を分析し、投稿戦略を比較して、学んだことを次回の下書き生成に反映するときに使う。「反応を分析する」「数字を振り返る」「レッスンをまとめる」と頼まれたら起動する。
---

# Threads Insights（分析）

## 入力

- `data/threads-posts.json`
- `data/threads-performance.json`
- 将来のDBテーブル: `threads_posts`, `threads_metrics`, `threads_lessons`

## メトリクス取得

`data/threads-performance.json` は `scripts/threads-fetch-metrics.mjs` が生成する。

```bash
npm run threads:metrics            # ドライラン：取得対象のpost一覧を表示
npm run threads:metrics -- --live  # 実取得：Threads Insights API を叩いて上書き
```

- live取得には `.env.local` のトークンと、live投稿実績（`threads-posts.json` の `threadsPostId`）が必要。
- 出力の `_source` で出所を判別する: `threads-insights-api`=実データ / `sample/fake`=講義用の架空サンプル。
- サンプルを分析するときは「デモ用の架空データ」と必ず断る。

## ワークフロー

1. Threads投稿IDまたは下書きメタデータで計測値と投稿を突き合わせる。
2. strategy / hookType / audience / ctaType で比較する。
3. 取れる範囲で views / likes / replies / reposts / quotes / profile clicks / link clicks を追う。
4. 露出が少ないだけのケースと、コピーが弱いケースを分けて考える。
5. 次の下書きサイクル向けに簡潔なレッスンを書く。

## ガードレール

- 1投稿に過剰適合しない。
- 欠損した計測値は 0 ではなく「欠損」として扱う。
- 明示的な指示なしに本番DBを変更しない。
