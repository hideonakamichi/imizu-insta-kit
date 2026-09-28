# 配布用パッケージ化の作業報告

配布にあたって行った、秘密情報の除去・個人情報のダミー化・設定の外出しの記録です。

> **※このファイルには、実際のキー・トークン・URL の値は一切書いていません。**
> 「どこにあった何を、どの変数に置き換えたか」だけを記録しています。

---

## 1. 秘密情報の除去

### 削除したファイル

| ファイル | 中身 | 対応 |
|---|---|---|
| `.env.local` | Supabase URL / service_role キー / Gemini API キー / Discord Webhook URL ほか | **削除**し `.env.example` を新設 |
| `.env.cloud` | 同上（クラウド実行用） | **削除**（`.env.example` に統合） |
| `site/.env.local` | Supabase URL / service_role キー | **削除**（`.env.example` をコピーして使う手順を README に記載） |
| `.env.local.sample` | 旧テンプレート | **削除**（`.env.example` に置き換え） |
| `.git/` | コミット履歴（過去の版にキーが含まれる可能性） | **フォルダごと削除** |
| `.claude/db/agents.db` | エージェントの実行記録（実運用ログ） | **削除**（スクリプト初回実行時に自動生成される） |

### `.env.example` の方針

- **値はすべて空**。埋めないと動きません
- 各変数の直上に**取得先の手順**を 1 行記載（例: Supabase の Project Settings → API のどこを見るか）
- 専門用語には一言説明を添付（例: 「Supabase = データベースとファイル置き場を、ブラウザから使えるサービス」）

### `.gitignore`

配布物のルートに設置。先頭に警告コメント付きで以下を登録:

```
.env
.env.local
.env.cloud
site/.env.local
```

受け取った人が誤ってキーをコミットしないための保険です。

---

## 2. 個人・組織に依存する情報の置き換え

**すべて `site/lib/siteConfig.js`（新規作成）に集約し、環境変数から読む形にしました。**
コードに直書きされていた値はゼロになっています。

| 元の場所 | 何が書かれていたか | 置き換え先の変数 |
|---|---|---|
| `site/app/layout.jsx` | サイト名・キャッチコピー・meta description | `NEXT_PUBLIC_SITE_NAME` / `_PRE` / `_MAIN` / `SITE_TAGLINE` / `SITE_DESCRIPTION` |
| `site/components/Analytics.jsx` | GA4 の測定 ID（**直書きされていた**） | `NEXT_PUBLIC_GA_ID` |
| `site/components/LineCta.jsx` | LINE 公式アカウントの友だち追加 URL | `NEXT_PUBLIC_LINE_ADD_URL` |
| `site/app/about/page.jsx` | 運営者の氏名・会社名・自己紹介文 | `NEXT_PUBLIC_OPERATOR_NAME` / `_ORG`（本文はサンプルに差し替え） |
| `site/app/privacy/page.jsx` | 会社名・制定日 | `NEXT_PUBLIC_OPERATOR_ORG` / `NEXT_PUBLIC_POLICY_DATE` |
| `site/app/disclaimer/page.jsx` | 会社名 | `NEXT_PUBLIC_OPERATOR_ORG` |
| 各ページの metadata | 独自ドメイン | `PUBLIC_SITE_URL` |
| `site/lib/*.js` 複数 | Supabase Storage のプロジェクト URL・バケット名・画像ディレクトリ | `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_STORAGE_BUCKET` / `_SECTIONS_DIR` / `_CHARACTERS_DIR` |
| `.claude/launchd/*.plist` | 実行パス | `<YOUR_PROJECT_PATH>` に置換（README に書き換え手順あり） |
| `.claude/launch.json` | 絶対パス | 相対パスに変更 |
| `scripts/*.sh` | 絶対パス | リポジトリルートからの相対パスに変更 |

### 差し替えた個人情報の種類

氏名 / 会社名 / メールアドレス / 独自ドメイン / GA4 測定 ID /
LINE 公式アカウントの URL と ID / Supabase のプロジェクト ID / Windows のユーザー名を含むパス

---

## 3. 設定の外出し（口調・人物設定）

**`config/persona.example.json`（新規作成）** に、登場人物の設定を切り出しました。

- 切り出したもの: **名前・年齢・家族構成・役割・口調・一人称**
- 手順書（skill）側は「この設定ファイルを読み、その人物設定に従う」と書く形に変更

**あえて切り出さなかったもの**（手順書の本体に残した）:

- 「質問役には専門用語を使わせない」「解説役にも正確性チェックは効かせる」といった**役割の非対称性のルール**
- **過去に起きた事故の実例**（「毎月お金が入る」と書いたが実際は奇数月だった、など）

これらは題材に依存しない普遍的な学びで、設定ファイルに出すと意味が失われるためです。

---

## 4. 除外したもの（消したものの記録）

講師のルール「消すのではなく置き換えを優先し、消したものは必ず報告する」に基づく記録です。

### 事業情報（17 ファイル）

競合分析 / 収益計画 / LINE 公式アカウントの運用計画・設定手順 /
登場人物の詳細設定 / 東京都・千葉県の制度リサーチ / 記事ごとの外部レビュー記録（10 本）

→ **仕組みではなく特定事業の中身**のため除外。ただし人物設定は消さず、
`config/persona.example.json` のサンプルに**置き換え**ています。

### ブランド素材（11 ファイル）

ロゴ（縦組み・横組み・シンボル）/ ファビコン / OGP 画像 / 各サイズのアイコン

→ 依頼者の著作物のため除外。`site/public/brand/mark-placeholder.svg`（プレースホルダ）と
差し替え手順を書いた README に**置き換え**ています。

### 実データ

`supabase/seed*.sql` の投入データを、**「サンプル手当A」「サンプル省庁」等のダミー 2〜3 件**に差し替え。

### 作業の一時ファイル

`.tmp/` `.scratch/` `export/` `preview/` `scratchpad/` `node_modules/` `.next/`

---

## 5. ★手動で確認していただきたい箇所★

機械的な検索では判定できないものです。

### 必ず見てほしいもの

1. **`.env.example`** — 全変数の値が空か。コメントに実際の値が紛れていないか
2. **`config/persona.example.json`** — 人物設定がサンプルになっているか
3. **`site/public/brand/mark-placeholder.svg`** — 中身が本当にプレースホルダか
4. **`README.md` の付録 A「実際に起きた事故」** — 公開して差し支えない内容か

### 画像は自動検査ができません

配布物に残っている画像は `mark-placeholder.svg` のみですが、
**画像の中に書かれた文字は grep で検出できません。** 目視をお願いします。

### 検査した項目（すべて 0 件）

以下のパターンで配布物全体を走査し、いずれも検出されませんでした。

- JWT 形式の文字列（`eyJ` で始まるもの）
- API キー形式の文字列（`sk-` / `AIza` で始まるもの）
- Supabase のプロジェクト URL
- Discord の Webhook URL
- 32 桁以上の連続した 16 進文字列
- Windows / Unix の絶対パス（ユーザー名を含むもの）
- 氏名・会社名・メールアドレス・独自ドメイン・GA4 測定 ID・LINE の URL と ID

**ただし、この検査は「既知のパターン」しか見ていません。**
最終確認はご自身の目でお願いします。

---

## 6. 動作について

**元の動作は変えていません。** 設定を外出ししただけで、
`.env.local` に値を入れれば同じように動きます。

Next.js のビルドが通ることは確認済みです。
