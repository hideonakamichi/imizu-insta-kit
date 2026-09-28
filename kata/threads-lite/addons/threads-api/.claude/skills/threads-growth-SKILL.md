---
name: threads-growth
description: Threads運用ループ全体（下書き生成→承認→投稿→計測→学習）を調整するときに使う。日次運用や「Threadsを回す」「投稿サイクルを回す」「全体の段取り」を頼まれたら起動する。このテンプレート全体の設計・役割分担・安全ルールのハブ。
---

# Threads Growth（全体オーケストレーション）

Claude Code で Threads投稿を毎日「生成・投稿・記録・改善」するための講義用テンプレート。
特定の事業やアカウントに依存しない抽象版で、実トークン・実投稿履歴・実ユーザーIDは含めない。
個別の作業手順は各専門スキルに委譲する。

## 設計の核（3つを分離する）

- **人格 / 戦略**: `.claude/skills/` と `.claude/agents/` が「どんな投稿が存在すべきか」を決める。
- **決定的実行**: `scripts/` が生成・投稿・重複スキップ・記録をする。
- **シークレットと承認**: `.env.local` と人間の承認が live投稿を守る。

## 役割分担（1サブエージェント=1役割、各自が対応SKILLを読む）

| サブエージェント | 読むスキル | 役割 |
|---|---|---|
| `threads-orchestrator` | threads-growth | 司令塔。日次サイクルを1コンテキストで完結 |
| `threads-draft-strategist` | threads-draft-generation | 下書き生成・戦略（投稿しない） |
| `threads-publisher` | threads-publishing | ドライラン / live投稿 / 記録 |
| `threads-insights-analyst` | threads-insights | 計測分析 → 次回レッスン |

> Claude Codeのサブエージェントは他サブエージェントを起動できない。
> 「3体を順に呼ぶ」司令塔役は **メイン会話** が担う（例: 「Threadsの日次運用を回して」）。
> 1コンテキストで完結させたい場合は `threads-orchestrator` サブエージェントに丸ごと委譲する。

## 起動例（会話）

- 全体: 「Threadsの日次運用を回して」→ メイン会話が3体を順に起動、または `threads-orchestrator` に委譲
- 下書きだけ: 「下書き候補を作って」→ `threads-draft-strategist`
- 投稿チェックだけ: 「ドライランして」→ `threads-publisher`
- 分析だけ: 「反応を分析して」→ `threads-insights-analyst`

## データの場所

- 静的トピック: `data/topics.json`
- 最初の／優先テーマの指定: `data/post-plan.json`
- 下書きキュー: `data/threads-drafts.json`
- 投稿記録: `data/threads-posts.json`
- 計測値: `data/threads-performance.json`
- 決定的処理: `scripts/generate-drafts.mjs` / `scripts/threads-publish-draft.mjs`

## よく使うコマンド

```bash
npm run check            # 全スクリプトの構文チェック
npm run threads:drafts   # 下書き生成 → data/threads-drafts.json
npm run threads:publish  # ドライラン（安全）
npm run threads:metrics  # 投稿の反応を取得 → data/threads-performance.json（--live で実取得）
npm run threads:me       # live投稿前のトークン確認
```

## ワークフロー

1. トピックと直近の投稿記録を読む。
2. 下書き候補を生成する。
3. 各下書きに `strategy` `hookType` `audience` `ctaType` `hypothesis` `body` `linkUrl` `metadata` `status` を保存する。
4. 承認済みまたは明示選択された下書きのみ投稿する。
5. 投稿結果を記録する。
6. 計測値が取れたら収集する。
7. レッスンを要約する。
8. レッスンを次回の下書き生成に渡す。

## 安全ルール（このテンプレート全体で常時守る）

- `.env.local` をコミットしない。
- token / user ID / app secret を読まない・出力しない・書かない。
- live投稿はユーザーが明示したときだけ。基本はドライラン。
- 投稿本文は500文字以内。
- 重複投稿・同日複数投稿を避ける（スケジュール実行では `--skip-posted --skip-today`）。
- 戦略/人格の判断とAPI実行を分離する。
