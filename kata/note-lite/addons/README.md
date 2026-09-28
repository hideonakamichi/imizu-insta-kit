# 外した機能

元のキットのファイルは `_original/` に、同じ構成のまま置いてあります（元の README・手順書・note エディタの操作ガイド・画像の作り方・入稿用スクリプト）。

## 足すと何が増えるか

| 足すもの | 増えること | 要るもの・費用 | 手間 | 気をつけること |
|---|---|---|---|---|
| Jina（競合分析・ファクトチェック用） | 上位記事の取得が速く安定する | Jina の API キー（従量。無料で使える分があるかは各自で確認） | キーを取って `.env.local` に書く | Lite 版は Claude Code の Web 検索・読み込みで代わりをしている。困っていなければ不要 |
| 画像生成（サムネイル・図解） | 記事のカバー画像と図解を作れる | Gemini の API キー。元のキットは `gemini-3.1-flash-image-preview` を指定。**無料枠で使えるかは要確認** | プロンプトの調整。日本語の文字が崩れることがある | `_original/.../image-style-guide.md` に作り方がある |
| note への自動入稿 | 記事を note の下書きに自動で流し込む | Chrome DevTools MCP（無料）。**note のメールアドレスとパスワードを `.env.local` に書く** | note の編集画面の作りが変わると動かなくなる。直し方は `editor-guide.md` | **ブラウザの自動操作は note 側に機械的な操作と判定されるおそれがある**（元の作者も公開は手動を推奨）。パスワードをファイルに置くことになる |

## 戻し方

- 元の手順書は `_original/.claude/skills/note-publishing-toolkit/SKILL.md`。**このフォルダごと `.claude/skills/` の下に写すと、元のスキルとして使える**
- 入稿に使う MCP の設定は `_original/.mcp.json.example`。`<ブラウザのプロファイルを置く場所>` を自分のパソコンの場所に書き換え、`.mcp.json` という名前でキットのいちばん上に置く
- キーは `_original/.env.example` を `.env.local` にコピーして埋める（**人に見せない・上げない**）
- 元の入稿用スクリプト `note-publish.py` は、Windows では日本語の記事を読めずに止まる（文字コードの指定が無い）。使うなら `read_text()` に `encoding="utf-8"` を足す
