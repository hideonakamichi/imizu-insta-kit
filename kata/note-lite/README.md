# note Lite（記事を1本ずつ仕上げる）

テーマを渡すと、**競合の記事を読んで勝ち筋を決め → 自分の人格で書き → 事実を一次情報で確かめて**、
note に貼るための記事ファイルを1本用意します。**note への投稿は自分で行います。**

```
themes.md のテーマを1つ選ぶ
   ↓ 競合分析（上位の記事を3本以上読む → 比較表 → 勝ち筋3つ）
記事を書く（persona.md の人格で、5つの構成パターンから選ぶ）
   ↓ ファクトチェック（事実を1つずつ一次情報と突き合わせる。確かめられない事実は消す）
output/<スラッグ>/ に article.md と preview.html
   ↓
自分で note に貼って公開 → 「公開した <URL>」と伝える
```

- 動く OS … Windows・Mac（Python 3.10 以上）
- 外部サービスのアカウントとキー … 要りません
- 費用 … Claude の利用量だけ。Web の検索と読み込みは Claude Code に入っている機能を使います

元は、有料の API（Jina・画像生成）とブラウザの自動操作で note への入稿まで行うキットです。
その部分は `addons/` に外してあります。

## はじめかた

1. このフォルダを VS Code で開く。「このフォルダを信頼しますか」と聞かれたら承認する
2. **書き手の人格を埋める。** Claude Code に「persona.md を一緒に埋めて」と頼む。
   埋めるまでは記事を書かずに止まります（見本は `_例_みなと.md`。**見本の名前と肩書きは使わない**）
3. `themes.md` に書きたいテーマを足す（書き方はファイルの中にあります）
4. 「note 記事を1本書いて」と頼む
5. `output/<スラッグ>/preview.html` をブラウザで開いて読む。よければ note の編集画面に本文を貼る。見出しは note の「見出し」ボタンで付ける
6. 公開したら「公開した <URL>」と伝える。themes.md のそのテーマに印が付きます

## できるもの

| ファイル | 中身 |
|---|---|
| `article.md` | 記事の本文（note に貼るもの） |
| `preview.html` | 見た目の確認用。本文の文字数も出る |
| `research.md` | 競合の比較表と勝ち筋 |
| `factcheck.md` | 確かめた事実・出典・判定 |

## 自分用に直す場所

| 変えたいもの | 場所 |
|---|---|
| 書き手の名前・立場・口調・書いてよい体験 | `.claude/skills/note-writing/references/persona.md` |
| 記事の組み立て | `.claude/skills/note-writing/references/article-template.md`（分野向けに作り込んだ例: `_例_給付金の記事の型.md`） |
| 題名のつけ方 | `.claude/skills/note-writing/references/title-guide.md` |
| 使わない言葉 | `.claude/skills/note-writing/SKILL.md` の「禁止表現」 |

## ディレクトリ構成

```
CLAUDE.md                          共通ルール（Claude Code が毎回読む）
themes.md                          書くテーマのキュー（自分で足す）
.claude/skills/note-writing/       手順書・人格・記事の型・題名のつけ方・スクリプト
.claude/agents/note-writer.md      手順書を読んで1本書く役（任せたいとき）
output/                            1本ごとのフォルダ
addons/                            外した機能（有料 API・自動入稿）と元の文書
```

## 利用について

note の利用規約は各自で確認してください。記事の内容とその影響は、公開した人の責任になります。
