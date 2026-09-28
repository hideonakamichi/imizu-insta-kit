---
name: agent-bootstrap
description: 編集長 / ライター / レビュアー 3 体の共通起動プロトコル — reflection 行作成 (Step 0)、reflection 完了 (Step Final) の 2 つを 1 セットで提供する。Task ツール経由 (subagent) でも launchd / cron 経由 (top-level) でも同じ手順で動く。各 agent.md の `skills:` frontmatter に追加して使う。
user-invocable: false
---

# Agent Bootstrap (共通起動プロトコル)

このスキルは Writer/Reviewer/Orchestrator の全エージェントに注入される共通起動 boilerplate。Step 0 reflection 作成、parent_run_id 引き継ぎ、Step Final reflection 完了書き込みを集約する。

## 用語

- **Top-level 起動**: `scripts/run-agent.sh` (launchd / cron 経由) で起動された場合。`AGENT_RUN_ID` が既に export 済み。
- **Subagent 起動**: 親エージェント (編集長) が `Task()` ツールで spawn した場合。prompt 先頭で `PARENT_RUN_ID=N` が渡される。

## Step 0 — 起動直後 (必ず最初に実行)

`{AGENT_SLUG}` は自分のエージェント名 (例: `support-writer`) に置換する。

```bash
if [ -z "${AGENT_RUN_ID:-}" ]; then
  PARENT_ARG=""
  [ -n "${PARENT_RUN_ID:-}" ] && PARENT_ARG="--parent $PARENT_RUN_ID"
  AGENT_RUN_ID=$(bash scripts/start-reflection.sh \
    --slug {AGENT_SLUG} --trigger subagent $PARENT_ARG)
  export AGENT_RUN_ID
fi
echo "AGENT_RUN_ID=$AGENT_RUN_ID"
```

**親 (orchestrator) が subagent を呼ぶときの prompt 規約**:

```
Task(
  subagent_type="support-writer",
  prompt="""
  PARENT_RUN_ID={your_AGENT_RUN_ID}  ← prompt 先頭で必ず渡す

  支援制度ID: 1
  この支援制度の記事を執筆してください。
  """
)
```

これがないと subagent の reflection が親に紐付かず、ダッシュボードで実行ツリーが切れる。

## Step Final — 作業完了直前 (必ず最後に実行)

```bash
bash scripts/agents-db.sh "
UPDATE reflections SET
  status = 'completed',
  ended_at = datetime('now','localtime'),
  duration_ms = (strftime('%s','now','localtime') - strftime('%s', started_at)) * 1000,
  what_done = '{箇条書き: 何をやったか}',
  quality_check = '{箇条書き: 品質確認結果 OK/NG}',
  quality_score = {0-100 の数値},
  result_full = '{詳細レポート全文}',
  self_improvement = '{自己改善案}',
  content_improvement = '{コンテンツ進化案}',
  updated_at = datetime('now','localtime')
WHERE id = $AGENT_RUN_ID;
"
```

### 4 層 reflection の役割分担

| カラム | 中身 | 読む相手 |
|---|---|---|
| `result_full` | Discord 通知本文 + 成果物 URL + メトリクス (SSOT) | 人間 |
| `what_done` | やったこと (箇条書き) | 人間 + メタ |
| `quality_check` | agent.md ルール準拠の自己診断 ✅/❌ | 人間 + メタ |
| `self_improvement` | agent.md / コード / ルールの修正候補 | レビュー担当人間 |
| `content_improvement` | アウトプット構造の進化案 | レビュー担当人間 |

### 前回の実行を読む (自己学習)

```bash
bash scripts/agents-db.sh "
  SELECT quality_score, what_done, quality_check, self_improvement, content_improvement
  FROM reflections
  WHERE agent_slug='{AGENT_SLUG}' AND quality_score IS NOT NULL
  ORDER BY created_at DESC LIMIT 3
"
```

## なぜ 4 層 reflection が必要か

旧設計: top-level エージェントのみが reflection を書く。subagent は INSERT されない → ダッシュボードに subagent の活動が見えない。

新設計: 全エージェントが reflection 行を持つ + parent_run_id でツリー構造に紐付ける。これで subagent (ライター / レビュアー) の活動も完全可視化される。

## ハードルール

- 全エージェントが起動直後に Step 0 を実行 (reflection 行作成)
- 全エージェントが完了直前に Step Final を実行 (4 層 reflection 書き込み)
- subagent は必ず PARENT_RUN_ID を prompt 先頭で受け取り、それを `--parent` に渡す
- reflection を書かないまま終了するのは絶対禁止 (ダッシュボードに「途中で死んだ」と表示される)
