# 追加パック：Threads API（自動投稿・反応の取得・分析・定期実行）

Lite 版から外した部分です。元のテンプレートのファイルを、同じ相対パスのまま置いてあります。

## 足すと何が増えるか

| 増えること | 要るもの | 費用 | 手間 |
|---|---|---|---|
| 投稿まで無人で終わる | Meta for Developers のアプリと、Threads のアクセストークン | Threads API 自体は無料 | **アプリの設定が一番の山**（`docs/account-setup.md`）。トークンは期限がある |
| 反応（表示回数など）を自動で集めて分析する | 同上。API で投稿した記録が前提 | 分析のたびに Claude の利用量 | 数が少ないうちは分析しても当てにならない |
| 分析の結果で生成の仕組みを自動で直す | Git で管理していること（壊れたら自動で巻き戻すため） | 直すたびに Claude の利用量 | `threads-improve.mjs` は **Windows ではそのままでは動かない**（パスの扱いが Mac 前提） |
| 毎日決まった時刻に投稿する | 常時起動の Mac（launchd） | — | Windows では使えない。Windows ならタスクスケジューラ、パソコン不要にするなら GitHub Actions に置き換える |

## 戻し方

1. このフォルダの中身を、キットのいちばん上に同じ相対パスでコピーする
   （`scripts/` → `scripts/`、`.claude/agents/` → `.claude/agents/` など。`.claude/skills/threads-publishing/` は上書きされる）
2. `.claude/agents/threads-orchestrator.md` と `.claude/skills/threads-growth-SKILL.md` は、元の版の控え。
   元に戻すなら `.claude/skills/threads-growth/SKILL.md` をこの中身で置き換える
3. `package.json` の `scripts` を `addons/_original/package.json` のものに戻す
4. `.env.example` を `.env.local` にコピーして値を埋める（**`.env.local` は人に見せない・上げない**）

作業は Claude Code に「addons/threads-api を元に戻して」と頼んでも進められます。
