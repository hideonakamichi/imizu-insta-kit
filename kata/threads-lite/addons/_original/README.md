# Threads Automation Template (Claude Code版)

Claude Code を使って、Threads投稿を毎日自動生成・投稿・記録・改善するための講義用テンプレート。

元の `threads-automation-template/`（Codex / 汎用AI agent形式）を、**Claude Code のベストプラクティス**に沿って
`.claude/` ディレクトリ構成（agents / skills / commands）へ移植したもの。仕組みと安全装置は同じ。

## Codex版との違い

| 要素 | Codex版（旧） | Claude Code版（本フォルダ） |
|------|------|------|
| エージェント | `agents/*.toml` | `.claude/agents/*.md`（YAML frontmatter + 本文） |
| スキル | `skills/*/SKILL.md` | `.claude/skills/*/SKILL.md`（自動認識） |
| プロジェクト指示 | README中心 | `CLAUDE.md` |
| 司令塔 | orchestrator agent | メイン会話、もしくは `threads-orchestrator` サブエージェント |

## フォルダ構成

```text
threads-automation-claude/
  CLAUDE.md                  # プロジェクト指示
  package.json
  .env.example
  .claude/
    agents/
      threads-orchestrator.md
      threads-draft-strategist.md
      threads-publisher.md
      threads-insights-analyst.md
    skills/
      threads-growth/SKILL.md
      threads-draft-generation/SKILL.md
      threads-publishing/SKILL.md
      threads-insights/SKILL.md
  scripts/                   # 決定的実行（生成・投稿・記録）
  data/                      # topics / drafts / posts / performance
  public/                    # OAuthコールバック
  schema/                    # 将来のDB
  launchd/                   # 毎日12:00ローカル実行
  docs/                      # lecture-guide / account-setup / launchd
```

## Quick Start

```bash
cd training/threads-automation-claude
npm run check
npm run threads:drafts
npm run threads:publish     # ドライラン
```

最初の publish はドライラン。選んだ投稿を表示するだけで Threads API は呼ばない。

## Claude Code での使い方

会話で頼むと、メイン会話が司令塔として動き、必要なサブエージェントを起動する。

```text
「Threadsの日次運用を回して」  → 下書き→投稿チェック→分析を順に
「下書き候補を作って」          → threads-draft-strategist
「ドライランして」              → threads-publisher
「反応を分析して」              → threads-insights-analyst
```

1コンテキストで一気に回したいときは `threads-orchestrator` サブエージェントに丸ごと委譲する。

## 自分のテーマ／note で運用する（文体模倣・推奨）

「最初にテーマ（または自分の note）を入力 → 以降はその文体・テーマの投稿を自動で出し続ける」運用。

```text
ステップ1（初回1回）: 会話で「テーマは〇〇」または「このnoteで: <URL>」と伝える
  → threads-topic-intake スキルが起動
  → data/topic-profile.json（発信の核・文体特徴）を作成
  → その文体を真似た7日分の投稿を data/draft-bank.json にストック
  → npm run threads:drafts -- --from-bank で投稿キューに反映

ステップ2（毎日・自動）: launchd が未投稿の1件を --live 投稿（あなたは不在でOK）

ステップ3（補充）: ストックが減ったら「ネタを補充して」と頼む
  → 過去投稿と被らない新しい7日分を生成
```

- 仕組みの中心は `data/topic-profile.json`。`active:true` のとき文体模倣モードで動く。
- 本文を書くのは AI（会話内生成・API課金なし）。Threads API を叩くのは投稿スクリプトだけ。
- 生成結果は `data/threads-drafts.json` の `mode: profile-bank` で確認できる。

### 旧方式: 既定トピックで指定する（後方互換）

`topic-profile.json` を使わない場合は、`data/post-plan.json` で優先トピックを指定する。

```json
{
  "firstPost": { "strategy": "parent-dialogue", "topicId": 1 },
  "pinned": []
}
```

- `firstPost` … 投稿履歴が空（＝初回）のときだけ、このテーマを最優先で先頭に置く。
- `pinned` … 初回かどうかに関わらず、毎回先頭に積みたいテーマの配列（順番どおり）。
- `strategy` は6種から選ぶ: `choice-expansion` / `parent-dialogue` / `social-capital` /
  `teacher-relief` / `myth-busting` / `small-step`
- `topicId` は `data/topics.json` の `id`。省略すると題材は自動割り当て。
- ファイルが無い／空なら、従来どおり全自動（後方互換）。

指定が効いたかは、生成後の `data/threads-drafts.json` の `planSummary` と、
各ドラフトの `metadata.plannedBy`（`post-plan.json` か `auto`）で確認できる。

## Live投稿

`.env.example` から `.env.local` を作り、実値を入れる:

```bash
cp .env.example .env.local
npm run threads:me
npm run threads:publish -- --skip-posted --skip-today --live
```

## 設計原則 — 3つを分離する

- **人格 / 戦略**: skills と agents が「どんな投稿が存在すべきか」を決める。
- **決定的実行**: scripts が生成・投稿・重複スキップ・記録をする。
- **シークレットと承認**: `.env.local` と人間の承認が live投稿を守る。

## 安全

- `.env.local` をコミットしない / token をログに出さない。
- まずドライラン。live投稿はユーザー明示時のみ。
- 投稿本文は500文字以内。
- スケジュール実行では `--skip-posted --skip-today` を付ける。
