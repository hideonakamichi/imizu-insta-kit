---
name: support-pipeline-orchestrator
description: ひとり親支援制度 (supports テーブル) パイプラインのオーケストレーション手順。データ同期、未記事化リスト選定、Writer (support-writer) → Reviewer (support-reviewer) のリトライループ制御 (最大 3 回)、Discord 完了サマリー作成までを定義。編集長 (support-orchestrator) 専用。
user-invocable: false
---

# ひとり親支援パイプライン・オーケストレーション手順

編集長 (support-orchestrator) 専用の編集長手順。データ同期 → 未記事化リスト → ライター/レビュアーのループ → 完了通知までを担う。

## 役割分担

| エージェント | 役割 | 責任範囲 |
|---|---|---|
| **編集長 (本体)** | 編集長・オーケストレーター | データ同期 / 対象 ID 選定 / フロー管理 / リトライループ / スキップ判定 |
| **ライター (support-writer)** | Writer | 支援制度記事 Markdown 作成・DB 投入 |
| **レビュアー (support-reviewer)** | Reviewer | 23 項目品質チェックで差し戻し or 承認 |

## ワークフロー

```
1. 起動時チェック (★毎回必須★)
   - 直近 24 時間の自身の reflection 確認 (重複処理回避)

2. データ同期 (外部データソース → DB 取り込み)
   bash scripts/sync-data.sh
   → ★ このスクリプトは雛形のみ同梱。自分のデータソースに合わせて実装してください
   → application_end が今日より前の制度を status='closed' に自動更新する SQL を含めること
     (全国の常設制度は application_end が NULL のため closed にならない)

3. 未記事化リスト作成
   bash scripts/supabase-query.sh select supports "article_md=is.null&status=eq.active&select=id,title&order=id&limit=5"
   → 対象 ID 取得 (Discord 開始通知は送らない)

4. 各 ID について Writer→Reviewer ループ:
   a. Task(support-writer, "支援制度ID {id}")
   b. Task(support-reviewer, "支援制度ID {id} のレビュー")
   c. 差し戻しループ (最大 3 回)
      - 合格 → break (個別 Discord 通知なし)
      - 3 回 NG → スキップ (理由をサマリーに含める)

5. 全完了 → サマリー Discord 通知 (1 回のみ)

6. 振り返り (4 層 reflection 書き込み + 完了)
```

## 起動時チェック (具体 SQL)

```bash
# 直近 24 時間の自分のログ
bash scripts/agents-db.sh "SELECT action, status, items_processed, items_succeeded, items_failed, created_at FROM reflections WHERE agent_slug='support-orchestrator' AND created_at > datetime('now', 'localtime', '-24 hours') ORDER BY created_at"
```

## データ同期 (編集長固有責務)

外部データソースからの同期は編集長が直接行う (ライターの責務ではない)。

```bash
# 雛形 (scripts/sync-data.sh) — 自分のデータソースに合わせて書き換えてください
bash scripts/sync-data.sh
```

### ステータス自動更新

データ同期の際、application_end が今日より前の制度を `status='closed'` に自動更新する:

```sql
UPDATE supports SET status = 'closed', updated_at = now()
WHERE status = 'active' AND application_end IS NOT NULL AND application_end < CURRENT_DATE;
```

REST 経由で実行する場合:

```bash
bash scripts/supabase-query.sh update supports '{"status":"closed"}' "status=eq.active&application_end=lt.$(date +%Y-%m-%d)"
```

## Subagent 呼び出しテンプレ

### ★ subagent への prompt 必須プレフィックス

**全ての Task 呼び出しの prompt 先頭に `PARENT_RUN_ID=$AGENT_RUN_ID` を明示する**。これがないと subagent の reflection が親に紐付かず、ダッシュボードで実行ツリーが切れる。

### ★ subagent は必ず同期実行 (結果を待つ)

Writer/Reviewer の Task 呼び出しは**必ず同期実行** (`run_in_background: false` / 結果を待ってから次に進む)。バックグラウンドで投げると自分のターンが終了してリトライループが停止し、DB 未反映のまま追跡不能になる (2026-07-21 の初回実行で実際に発生)。

### ライター (Writer) を呼ぶ — 初回

```
Task(
  description="支援制度記事作成",
  subagent_type="support-writer",
  prompt="""
PARENT_RUN_ID={your AGENT_RUN_ID}

支援制度ID: {id}
タイトル: {title}

起動直後に Step 0 を実行して reflection 行を作ってください (PARENT_RUN_ID を引き継ぐ)。
この支援制度の記事 (article_md) を執筆してください。
執筆完了後、DB 投入 + reflection の UPDATE まで行い、結果を返してください。
"""
)
```

### レビュアー (Reviewer) にレビュー依頼

```
Task(
  description="支援制度記事レビュー",
  subagent_type="support-reviewer",
  prompt="""
PARENT_RUN_ID={your AGENT_RUN_ID}

支援制度ID: {id}
タイトル: {title}

起動直後に Step 0 を実行して reflection 行を作ってください (PARENT_RUN_ID を引き継ぐ)。
この制度の article_md をレビューしてください。
品質基準を満たしていれば「合格」、問題があれば「差し戻し」+ 具体的な修正指示を返してください。
レビュー完了後、reflection の UPDATE を実行してから結果を返してください。
"""
)
```

### 差し戻しを受けてライターに修正依頼

```
Task(
  description="支援制度記事修正",
  subagent_type="support-writer",
  prompt="""
PARENT_RUN_ID={your AGENT_RUN_ID}

レビュアーから以下の指摘を受けたので修正してください:

{reviewer_feedback}

支援制度ID: {id}
修正後、DB 再投入まで行い、結果を返してください。
"""
)
```

## リトライループ実装 (擬似コード)

```python
for id, title in target_ids:
    retry_count = 0
    max_retries = 3

    # 初回執筆
    writer_result = Task(support-writer, f"支援制度ID {id}")

    while retry_count < max_retries:
        review_result = Task(support-reviewer, f"支援制度ID {id} をレビュー")
        if review_result == "合格":
            results.append(("合格", id, ...))  # 個別 Discord 通知なし
            break
        else:
            retry_count += 1
            if retry_count >= max_retries:
                results.append(("スキップ", id, review_result))  # 理由をサマリーに
                break
            Task(support-writer, f"修正指示: {review_result}")
```

## Discord 通知ルール (★完了の 1 回のみ★)

**編集長 (オーケストレーター) のみが通知**。Writer/Reviewer は通知しない。
通知は **全完了時の 1 回のみ**。開始通知 / 中間通知 / 個別の合格・スキップ通知は送らない (ログを汚すため)。

### 通知タイミング

**全完了時: 成果物サマリー + Full URL + メトリクス**

```
🎉 本日完了 ({N} 件)。
✅ 合格 ${PUBLIC_SITE_URL}/support/{id1} ({chars}文字、出典 {N}件)
✅ 合格 ${PUBLIC_SITE_URL}/support/{id2} ({chars}文字、1回差し戻し→再執筆)
❌ スキップ ${PUBLIC_SITE_URL}/support/{id3} (3回NG、理由: {reason})
合計文字数 {total_chars} 字 / 所要 {min} 分
```

### URL フォーマット厳守

詳細は `editorial-url-rules` skill を参照。要点:
- **Full URL を使う**: `${PUBLIC_SITE_URL}/support/{id}` 形式
- ❌「ID 124」「制度 124」「/support/124」(相対パス) は禁止
- ✅「https://your-domain.example/support/124」(クリック可能)

### Discord 絶対ルール

- `--embed` は使わない (テキストのみ)
- Writer/Reviewer の個別呼び出しごとに中間通知しない
- サマリーには必ず各 ID の Full URL を含める
- 差し戻し回数・スキップ理由を明示
- キャラのトーンは 編集長らしく

```bash
bash .claude/scripts/notify-discord.sh --agent support-orchestrator "メッセージ"
```

## DB 操作

Supabase MCP は使わない。REST API で操作:

```bash
# 未記事化リスト取得
bash scripts/supabase-query.sh select supports "article_md=is.null&status=eq.active&select=id,title&order=id&limit=5"
```

## 振り返り 4 層 reflection (完了時)

`agent-bootstrap` skill の Step Final 手順を踏まえ、編集長固有の中身を入れる。

### result_full に書く Discord 通知本文 (例)

```bash
REPORT_FILE=$(mktemp)
cat > "$REPORT_FILE" <<EOF
## 完了時通知
🎉 本日完了。
✅ 合格 ${PUBLIC_SITE_URL}/support/1 (12,456文字、出典 4件)
✅ 合格 ${PUBLIC_SITE_URL}/support/4 (11,203文字、1回差し戻し→再執筆)
❌ スキップ ${PUBLIC_SITE_URL}/support/{id} (3回NG、理由: 話者逆転+画像不足)
合計 {N} 万字 / 所要 {min} 分

## 同期件数
- 差分同期: {A} 件取り込み / {B} 件 closed 自動更新

## Subagent 起動
- writer: {N} 回 / reviewer: {M} 回
EOF

bash .claude/scripts/notify-discord.sh --agent support-orchestrator "$(cat "$REPORT_FILE")"

# reflection に記録 (詳細スキーマは agent-bootstrap skill 参照)
bash scripts/agents-db.sh "UPDATE reflections SET
  what_done = '...',
  quality_check = '...',
  self_improvement = '...',
  content_improvement = '...',
  quality_score = {0-100},
  result_full = readfile('$REPORT_FILE'),
  reflected_at = datetime('now','localtime')
WHERE id = $AGENT_RUN_ID"

rm -f "$REPORT_FILE"
```

### quality_check に書く項目 (編集長固有)

- ✅/❌ データ同期 + ステータス自動更新を先頭で実行
- ✅/❌ 対象選定時に `article_md IS NULL AND status='active'` を使用
- ✅/❌ Writer/Reviewer の呼び出しを Task ツールで実行 (直接執筆していない)
- ✅/❌ リトライループを 3 回で打ち切り自動スキップ
- ✅/❌ Discord 通知は完了時の 1 回のみ (中間通知なし)
- ✅/❌ 全 URL が Full URL 形式
- ✅/❌ 差し戻し回数・スキップ理由を完了通知に明示

## スケジューラー (launchd / cron)

| タスク | 頻度 | 内容 |
|---|---|---|
| 差分同期 + 記事生成 | 毎時 `:05` | 差分取り込み → 未記事化リスト → ライター+レビュアーのループ |
| フル同期 + 記事生成 | 毎日 6:00 | 全件同期 → 未記事化リスト → ライター+レビュアーのループ |

セットアップ詳細は同梱の `.claude/launchd/com.example.support-pipeline.plist` (Mac) または `.claude/launchd/cron-example.txt` (Linux) を参照。

## ハードルール (編集長の契約)

- **supports テーブルのみ**: 他の業務エンティティは触らない
- **記事は書かない**: 書くのはライター、レビューはレビュアー
- **Task ツールでしかエージェントを起動しない** (直接書いたり レビューしたりしない)
- **リトライループは必ず 3 回まで**。それ以上は自動スキップ (ユーザー確認しない)
- **レビュアーが差し戻し → そのまま公開は絶対禁止**
- **データ同期から記事完了まで自律実行** (ユーザー承認なし)

## コマンド一覧

| 操作 | 方法 |
|---|---|
| データ同期 (雛形) | `bash scripts/sync-data.sh` |
| Supabase クエリ | `bash scripts/supabase-query.sh ...` |
| Discord 通知 | `bash .claude/scripts/notify-discord.sh --agent support-orchestrator "メッセージ"` |

## カスタマイズの指針

- **データソース**: `scripts/sync-data.sh` を自分のデータソース (自治体サイト / 手動投入等) に合わせて書き換え
- **スキーマ**: `supports` テーブルのカラムを増減する場合は writer/reviewer skill 内の SQL も合わせて修正
- **キャラ名**: 「編集長」「ライター」「レビュアー」を別の名前に変えたい場合は agent.md の `name_jp:` と `notify-discord.sh` の case 文を編集
