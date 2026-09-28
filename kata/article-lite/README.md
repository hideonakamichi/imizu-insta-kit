# 記事キット Lite（書く役と査読役を分ける）

AI に専門記事を**書かせて、別の AI に査読させて、合格したものだけを残す**ための一式です。
元は「ひとり親家庭の公的支援制度」を解説するサイトを実際に1か月運用して育てたキットで、
**事故が起きるたびに検査を足してきた記録**がいちばんの見どころです。

> **まず読むもの：** `addons/_original/README.md` の「付録A：この仕組みの肝」。
> 実際に起きた事故3つ（「毎月お金が入る」と書いたが実際は奇数月だった、など）と、それをどう検査に変えたかが書いてあります。

## 元のキットとの違い

| | 元のキット | Lite 版 |
|---|---|---|
| 記事の置き場所 | Supabase（データベースの有料・無料枠のサービス） | **`data/*.json`**（手元のファイル） |
| 公開 | Next.js のサイト | **`output/` に Markdown とプレビュー**。公開するなら自分で貼る |
| 図解画像 | 必須（Gemini で作って Supabase に置く） | **既定では作らない**（`config/features.json` で有効にできる） |
| 実行記録 | sqlite3 コマンド（Windows に標準で無い） | Python に入っている sqlite3 を使う |
| 登録・キー | Supabase・Gemini が必須 | **要らない**（Discord 通知と画像は任意） |

**手順書（`.claude/skills/`）の本文は、ほぼ元のままです。** データの窓口 `scripts/supabase-query.sh` を、
同じ使い方のまま手元のファイルを読み書きするように差し替えたので、手順書を書き換えずに済んでいます。

- 動く OS … Windows・Mac（Python 3.10 以上。Git Bash は Claude Code に付いてくるもので足ります）
- 費用 … Claude の利用量だけ。**ただし重いキットです**（下の「気をつけること」）

## はじめかた

1. このフォルダを VS Code で開く。「このフォルダを信頼しますか」と聞かれたら承認する
2. 登場人物を決める: `config/persona.example.json` を `config/persona.json` にコピーして書き換える（そのままでも動く）
3. まず1本書かせる

   ```
   ライター (support-writer) で supports id=1 の記事を書いてください。
   ```

4. 査読させる

   ```
   レビュアー (support-reviewer) で supports id=1 の記事を査読してください。
   ```

   **ここで出てくる検査の指摘（E01〜E24）を読むのが、このキットの一番の見どころです**

5. 書き出す

   ```
   記事を書き出して
   ```

   `output/<id>-<名前>/` に `article.md`（本文）・`preview.html`（見た目の確認）・`research_notes.json`（調べた根拠と査読の記録）ができます

> 最初に入っている3件（`data/supports.json`）は**ダミー**です。金額も URL も架空なので、そのまま公開しないでください。
> 自分のテーマで使うときは、ここを入れ替えます（読み替え方は `addons/_original/README.md` の付録B）。

## 気をつけること（重さ）

- 手順書だけで約12万字あり、記事も1万字以上を目指す作りです。**1本書いて査読するまでに、Claude の利用枠をかなり使います**
- 月 $20 のプランなら、**Claude Code のモデルを Sonnet にしてから**動かしてください（`/model sonnet`）。書く役と査読役はもともと Sonnet 指定です
- 最初は手順書の目標文字数や検査を変えずに1本だけ回し、様子を見る。慣れたら、自分の題材に合わせて軽くする

## ディレクトリ構成

```
CLAUDE.md                 共通ルール（Claude Code が毎回読む）
config/persona*.json      登場人物（質問役と解説役）
config/features.json      機能スイッチ（図解画像）
.claude/agents/           編集長・ライター・レビュアー（人格と契約だけの薄い定義）
.claude/skills/           手順書の本体。事故のたびにここが育った
data/                     記事の置き場所（元の Supabase の代わり）
scripts/supabase-query.sh データの窓口（元と同じ使い方で data/ を読み書き）
scripts/article-health-check.sh  公開後の点検（M01〜M22）
scripts/export-articles.sh       記事を output/ に書き出す
scripts/dashboard.py      実行記録を1枚の HTML にする（py scripts/dashboard.py --open）
output/                   書き出した記事
docs/                     点検の流れ・図解の仕様・URL の決まり
addons/                   外した機能（サイト・データベース・画像・定期実行）と元の文書
```
