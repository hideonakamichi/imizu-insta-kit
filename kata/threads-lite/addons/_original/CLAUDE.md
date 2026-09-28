# Threads Automation (Claude Code版)

Threads投稿を毎日「生成・投稿・記録・改善」する講義用テンプレート。
詳細な設計・役割分担・ワークフロー・コマンドは **`threads-growth` スキル**に集約。

## まず使うもの（サブエージェント）

入口はサブエージェント。各サブエージェントが起動時に対応スキルを自分で読む。

- 司令塔: `threads-orchestrator` — 日次サイクルを1コンテキストで完結（skill: threads-growth）
- 下書き: `threads-draft-strategist` — 生成・戦略（skill: threads-draft-generation）
- 投稿: `threads-publisher` — ドライラン / live投稿 / 記録（skill: threads-publishing）
- 分析: `threads-insights-analyst` — 計測分析（skill: threads-insights）

全体の設計・役割分担・起動例・コマンドは `threads-orchestrator` 経由か
`.claude/skills/threads-growth/SKILL.md` を見る。

## 安全ルール（常時遵守）

- `.env.local` をコミットしない。token / user ID / app secret を読まない・出力しない・書かない。
- live投稿はユーザーが明示したときだけ。基本はドライラン。
- 投稿本文は500文字以内。重複・同日複数投稿を避ける。
