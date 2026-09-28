# Threads Lite（Claude Code版）

自分のテーマや文章から、その文体をまねた Threads の投稿を7日分ストックし、毎日1本ずつ出す。
**投稿は人がアプリから手で行う。** 全体の段取りは `threads-growth` スキルにある。

## 入口

| 頼まれたこと | 使うもの |
|---|---|
| 「テーマは〇〇」「この文章で投稿を作って」「ネタを補充して」 | `threads-topic-intake` スキル |
| 「今日の1本を出して」 | `npm run threads:today` |
| 「投稿した」「記録して」 | `npm run threads:posted` |
| 「Threadsを回して」（まとめて） | `threads-growth` スキル |

## 役割

- 下書き（本文を書く）: このセッション（`threads-topic-intake` に従う）。レビューだけなら `threads-draft-strategist`
- 下書きの変換・今日の1本・記録: `scripts/` の決まった処理。AI を使わない

## コマンドの実行

- `npm run ...` は **Bash ツール**で、このフォルダをカレントにして実行する。Windows でも PowerShell ツールは使わない
  （PowerShell では npm がスクリプト実行の制限で止まることがあり、`.claude/settings.json` の許可も Bash の形で登録してある）

## 安全ルール（常時遵守）

- 投稿本文は500文字以内。事実を作らない。読者を煽らない
- 重複・同日複数投稿を避ける（`threads:today` と `threads:posted` が自動で止める）
- 自動投稿（Threads API）・反応の取得・定期実行は `addons/threads-api/` にある。本体からは使わない
