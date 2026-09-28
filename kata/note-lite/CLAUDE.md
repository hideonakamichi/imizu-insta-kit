# note Lite（記事を1本ずつ仕上げる）

テーマを1つ選び、競合を読んで勝ち筋を決め、自分の人格で書き、事実を一次情報で確かめて、
note に貼る記事ファイルを用意する。**note への投稿は人が手で行う。**

## 入口

| 頼まれたこと | 使うもの |
|---|---|
| 「note 記事を1本書いて」 | `.claude/skills/note-writing/SKILL.md`（このセッションで進める。`note-writer` エージェントに任せてもよい） |
| 「persona.md を一緒に埋めて」 | 人格の雛形を、質問しながら埋める。**本人が言っていない経歴・体験を作らない** |
| 「公開した <URL>」 | SKILL.md の Step 6 に従い themes.md を更新する |

## コマンドの実行

- Python は Windows `py` ／ Mac `python3`
- **Bash ツール**で、`py .claude/skills/note-writing/scripts/...` の相対パスのまま実行する。Windows でも PowerShell ツールは使わない

## 外してある機能

有料の API（Jina・画像生成）と、ブラウザを自動で動かして note に入稿する機能は `addons/` にある。本体からは使わない。
