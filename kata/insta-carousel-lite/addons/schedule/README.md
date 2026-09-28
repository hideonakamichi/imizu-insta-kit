# 追加パック: 定期実行（schedule）

決まった時刻に、人がいなくてもパイプラインを動かします。週に1回の点検（トークンの期限・投稿の抜け・ネタの残り）も含みます。

## 中身

フォルダ名は `claude-files/` にしてあります（`.claude/` のままだと、Claude Code が本体を開いたときにこのパックのスキルまで読み込むため）。
足すときは、中身をキットの `.claude/` の同じ場所へ移します。

| ファイル | 役割 |
|---|---|
| `bin/` | 無人実行の入口（`run-agent.sh`）と、launchd への登録（`setup_launchd.sh`） |
| `config/schedule.yaml` | 曜日と時刻 |
| `claude-files/skills/system-healthcheck/` | 週次点検の手順とスクリプト |
| `claude-files/orchestrators/` | 週次点検の司令塔と、司令塔の置き方の説明 |

## 要るもの

- 予定の時刻にスリープしない Mac（launchd を使う）
- 自動投稿パック（無人実行は、投稿まで自動でないと意味がない）

## 注意

- 無人実行（`claude -p`）では人が承認ボタンを押せないので、許可の書き方を1文字でも外すと、途中で黙って止まります。
  フル版の CLAUDE.md の「headless実行の制約」（`../_original/CLAUDE-full.md`）を必ず読んでください
- Windows で使うには、launchd をタスクスケジューラに、シェルスクリプトを PowerShell に置き換える必要があります（未対応）
