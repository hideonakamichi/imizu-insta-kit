# note 自動入稿エージェント — 配布パッケージ

note.com にライフイベント起点の記事を **競合分析 → 執筆 → ファクトチェック → 画像生成 → 入稿 → デザイン QA** までフル自動で 1 本仕上げる Claude Code 用のサブエージェント／スキル。

note配信エージェント (note-publisher) は「補助金エージェント」で運用中の実装をそのまま配布用に切り出したもの。テーマ・人格・データソースを差し替えれば、給付金以外のジャンル (求人 / レシピ / レビュー / コラム etc) でも転用可能。

## このパッケージに入っているもの

```
automan/
├── README.md                                          ← このファイル
├── .env.example                                       ← 環境変数サンプル
├── themes.md                                          ← 投稿テーマキュー (ユーザーが編集)
└── .claude/
    ├── agents/
    │   └── note-publisher.md                          ← 薄いラッパー (フラット配置)
    └── skills/
        └── note-publishing-toolkit/
            ├── SKILL.md                               ← 業界中立の「note 入稿 9 ステップ」手順書
            ├── references/
            │   ├── article-template.md
            │   ├── editor-guide.md
            │   ├── image-style-guide.md
            │   ├── persona.md                         ← 「みなと」人格 (差し替え対象)
            │   └── title-guide.md
            └── scripts/
                └── note-publish.py                    ← Markdown → note 入稿プラン JSON 変換 (純 Python、依存なし)
```

### サブエージェント / スキルの役割分担

| 層 | ファイル | 中身 |
|---|---|---|
| **エージェント (薄いラッパー)** | `agents/note-publisher.md` | テーマキューの読み書き / 人格ポインタ / 通知声色 / 業界ハードルール |
| **スキル (手順書 + 共通アセット)** | `skills/note-publishing-toolkit/SKILL.md` + `references/` + `scripts/` | 競合分析 / 執筆 / 画像生成 / 入稿 / QA の 10 ステップ手順、テンプレ、入稿スクリプト |

→ 別ジャンルへ転用する時は **`note-publisher.md` を新しい slug でコピーして書き換える**。スキル側は触らない。

## セットアップ

### 1. 必要なツールを確認

```bash
python3 --version    # Python 3.9+ (note-publish.py は標準ライブラリのみで動く)
# CLI: jq, curl (基本入っている)
```

### 2. Chrome DevTools MCP の設定

note 入稿は Chrome DevTools MCP 経由で実ブラウザを操作する。`.mcp.json` は配布版に同梱済み (専用プロファイル `automan-profile` を使う設定)。

初回起動時は Claude Code を一度再起動するか `/mcp` で MCP をリロードして読み込ませる。同マシンで他の note 系エージェント (hojokin の note-publisher-profile 等) が動いていてもプロファイル衝突しないように分離している。

### 3. 環境変数を設定

```bash
cp .env.example .env.local
# エディタで .env.local を開いて値を埋める
```

必要なのは 4 つだけ:

- `NOTE_EMAIL` / `NOTE_PASSWORD` — 入稿先 note アカウント
- `JINA_API_KEY` — 競合分析 + ファクトチェック用 (https://jina.ai/api-dashboard/)
- `GEMINI_API_KEY` — 画像生成用 (https://aistudio.google.com/)

画像は MCP の `upload_file` で note エディタに直接アップするので、外部画像ホスト (R2 / S3 等) は不要。

### 4. (任意) Discord 通知の Webhook を準備

進捗 / 完了報告を Discord に投げたい場合は `DISCORD_WEBHOOK_URL` を設定し、エージェントの通知箇所をプロジェクトの `notify-discord.sh` 等に合わせて差し替える。

## 使い方

### 1. テーマを `themes.md` に追加

プロジェクト直下の `themes.md` を開いて、書きたいテーマをチェックリストに追加:

```markdown
- [ ] **在宅でできる副業の始め方** — メインKW: `在宅 副業 初心者` / サブKW: `在宅ワーク 主婦`
  - 切り口: 月3万を目標に、未経験から始められる選択肢を比較
  - 想定読者: 30 代の主婦
  - 想定文字数: 1200
```

### 2. note配信エージェントを呼ぶ

Claude Code 上で:

```
note配信エージェントで note 記事 1 本書いて
```

または `/agents` から `note-publisher` を選択。

note配信エージェントが `themes.md` の上から最初の `- [ ]` テーマを 1 つ拾って記事化し、完了後にチェックを入れる。

エージェントはスキル本体 (SKILL.md) に従い、以下を順に実行する:

1. **起動チェック** (重複回避 / 自己フィードバック確認)
2. **テーマ + 都市決定** (Google サジェスト + Jina Search)
3. **競合分析** (Jina Reader で上位 5 記事を全文取得 → 比較表 → 勝ち筋 3 つ)
4. **記事 Markdown 生成** (5 構成パターンから前回と被らないものを選択)
5. **ファクトチェック** (Jina Reader で公式ソース突合)
6. **画像生成** (Gemini 3.1 Flash でサムネ + 図解)
7. **note 入稿** (Chrome DevTools MCP で実 Chrome 操作 + 画像はローカル直接アップ)
8. **デザイン QA** (PC + モバイル スクショを Read tool で目視)
9. **公開 + Discord 通知 + 振り返り** (公開は bot 検知回避のため手動推奨)

## カスタマイズ

| 変えたい時 | 編集するファイル |
|---|---|
| 投稿テーマ | `themes.md` |
| 書き手の人格 (口調・一人称・ペルソナ) | `.claude/skills/note-publishing-toolkit/references/persona.md` |
| 記事の構成テンプレ | `.claude/skills/note-publishing-toolkit/references/article-template.md` |
| タイトル命名ルール | `.claude/skills/note-publishing-toolkit/references/title-guide.md` |
| 画像のスタイル | `.claude/skills/note-publishing-toolkit/references/image-style-guide.md` |
| エージェントの振る舞い | `.claude/agents/note-publisher.md` |

`SKILL.md` (note 入稿 9 ステップ手順書) は基本触らない。共通利用する前提。

## 注意事項 / ハマりどころ

- **画像モデルは `gemini-3.1-flash-image-preview` 必須**。2.5 Flash 等の旧モデルは日本語が崩れる。
- **入稿は Chrome DevTools MCP で実ブラウザ駆動のみ**。ヘッドレスブラウザ (Playwright 等) は note の bot 検知に蹴られるので非対応。
- **`note-publish.py` の役割は Markdown → JSON 変換だけ**。ブラウザは触らない。
- **`.env.local` は git 管理しない**。`.gitignore` に追加すること。
- **公開ステップは手動推奨**。完全自動化すると note 側のスパム検知に引っかかる可能性がある。
- **note エディタの contenteditable ブロック仕様は予告なく変わる**。MCP click のセレクタや Ctrl+Shift+1 ショートカットが効かなくなったら `references/editor-guide.md` を更新する。

## ライセンス / 利用条件

- このコードは「補助金エージェント」(hojokin-agent.jp) の内部実装を切り出したもの。
- 配布先で改変 / 商用利用するのは自由だが、note.com の利用規約に違反する形 (大量自動投稿 / 内容のないスパム記事 / 他人のコンテンツの転載) で運用しないこと。
- 1 アカウント 1 日 4 記事程度を上限に運用することを強く推奨。
