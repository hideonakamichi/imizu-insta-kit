# 外した機能

| フォルダ | 中身 |
|---|---|
| `site-db/` | Web サイト（Next.js）・データベースの設計（Supabase の SQL）・定期実行（launchd）・元の `.env.example` |
| `_original/` | 元の README（付録A〜E）・発表資料・報告・差し替える前の手順書とスクリプト |

## 足すと何が増えるか

| 足すもの | 増えること | 要るもの・費用 | 手間 | 気をつけること |
|---|---|---|---|---|
| データベース（Supabase） | 記事をネット上に置け、サイトから読める | Supabase のアカウント（無料枠あり） | SQL を実行して表を作る、キーを `.env.local` に書く | **service_role キーは管理者用。** 人に見せない、ブラウザに出さない |
| Web サイト（Next.js） | 記事をサイトとして公開できる | Node.js（レッスン4で入れたもの）、公開するなら Vercel など | 設定項目が多い（`site-db/.env.example` の【3】【4】） | お金・健康を扱うなら「誰が運営しているか」の明示が要る |
| 図解画像 | 記事に図解が2枚以上入る | Gemini の API キー。**無料枠で使えるかは要確認**。画像の置き場所（Supabase の Storage など） | `config/features.json` の `images` を `true` にする | 元のキットでは**26枚中10枚が別の記事の画像だった**事故がある（付録A 事故2） |
| 定期実行 | 決まった時刻に編集長が回る | 常時起動の Mac（launchd）。Windows ならタスクスケジューラ | `site-db/.claude/launchd/`、元の README の 5-5 | **回すたびに Claude の利用量**がかかる（止まった回も） |

## 戻し方

- 元の手順書・スクリプトは `_original/` に同じ構成で置いてある。上書きすれば元に戻る
- 元の `scripts/supabase-query.sh` は Supabase に接続する版。`site-db/.env.example` を `.env.local` にコピーして値を埋めてから使う
- 元の `start-reflection.sh` と手順書の `sqlite3` は、**Windows では sqlite3 コマンドを別に入れないと動かない**。手順書の `jq` も同じ（jq は Windows に標準で入っていない）
