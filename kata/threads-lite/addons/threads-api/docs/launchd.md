# launchd Daily Automation

Macで毎日12:00にThreads投稿を実行するテンプレートです。

## 1. plistを作る

`launchd/com.example.threads-automation.plist.template` の `__ABSOLUTE_PROJECT_PATH__` を、このフォルダの絶対パスに置き換えます。

例:

```text
/Users/you/path/to/threads-automation-template
```

## 2. LaunchAgentsへコピー

```bash
cp launchd/com.example.threads-automation.plist.template ~/Library/LaunchAgents/com.example.threads-automation.plist
```

コピー後のplist内のパスを置換してください。

## 3. 読み込み

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.example.threads-automation.plist
launchctl enable gui/$(id -u)/com.example.threads-automation
```

## 4. 状態確認

```bash
launchctl print gui/$(id -u)/com.example.threads-automation
```

## 5. 手動実行

```bash
launchctl kickstart -k gui/$(id -u)/com.example.threads-automation
```

## 6. ログ

```bash
tail -n 200 scripts/.cache/launchd/threads.out.log
tail -n 200 scripts/.cache/launchd/threads.err.log
```

## 7. 停止

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.example.threads-automation.plist
```

## Notes

- Macがスリープしている間は実行されません。
- 本番運用ならサーバーcronやクラウドスケジューラーも検討します。
- `scripts/local-threads-publish.sh` は `--skip-today` を付けて、同じ日に複数投稿しないようにしています。
