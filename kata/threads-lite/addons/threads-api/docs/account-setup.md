# Threads / Meta App Setup

## 1. Threadsアカウント

1. Instagramアカウントを用意する
2. Threadsにログインする
3. プロフィール名、自己紹介、アイコンを整える
4. 初期投稿を1-2件入れて空アカウント感を避ける

## 2. Meta for Developers

1. `https://developers.facebook.com/` にログイン
2. 新規アプリを作成
3. Threads APIのユースケースを追加
4. OAuth Redirect URIを登録

例:

```text
https://example.com/threads-callback
```

このテンプレートの `public/threads-callback.html` を自分のサイトに配置すると、認可後の `code` をコピーしやすくなります。

## 3. 必要スコープ

最小:

```text
threads_basic
threads_content_publish
```

分析も行う場合:

```text
threads_manage_insights
```

## 4. OAuth

```bash
export THREADS_CLIENT_ID="..."
export THREADS_CLIENT_SECRET="..."
export THREADS_REDIRECT_URI="https://example.com/threads-callback"
npm run threads:auth-url
```

表示されたURLを開き、認可後の `code` を控えます。

```bash
npm run threads:exchange-code -- --code="..."
```

トークンを保存する直前だけ:

```bash
npm run threads:exchange-code -- --code="..." --print-token
```

## 5. 接続確認

```bash
THREADS_ACCESS_TOKEN="..." npm run threads:me
```

出力された `THREADS_USER_ID` を `.env.local` に保存します。

## 6. 注意

- tokenをGitに入れない
- app secretを画面共有で見せない
- tokenは期限があるため、期限前に再発行する
- まずはテスター/管理者の自分のアカウントで検証する
