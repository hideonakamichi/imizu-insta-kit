# 追加パック: 自動投稿（auto-post）

投稿用フォルダを人がスマホから投稿する代わりに、Instagram の API で自動投稿します。

## 中身

フォルダ名は `claude-files/` にしてあります（`.claude/` のままだと、Claude Code が本体を開いたときにこのパックのスキルまで読み込むため）。
足すときは、中身をキットの `.claude/` の同じ場所へ移します。

| ファイル | 役割 |
|---|---|
| `claude-files/skills/instagram-publishing/` | 投稿の手順と、投稿・一時公開・記録・通知・トークン更新のスクリプト |
| `claude-files/orchestrators/banner-orchestrator.md` | 生成から投稿・通知までを通す、フル版の司令塔の指示書 |
| `env.template` | 必要なキーの一覧（値は入っていない） |

## 要るもの

- Instagram をプロアカウントにし、Meta for Developers でアプリを作って長期アクセストークンを取る（フル版でいちばんの山場）
- Cloudflare R2（Instagram の API は公開 URL の画像しか受け付けないので、投稿の直前に一時公開する）
- Discord の Webhook（成功・失敗の通知）
- Python ライブラリ `boto3`

手順は `../_original/SETUP-GUIDE.md` の8節（Meta）と、R2・Discord の節にあります。

## Lite 版とのつながり（未対応）

- 投稿の記録先が `logs/posted.jsonl` で、Lite 版の `logs/history.jsonl` と違う
- `ig_post.py` と `record_post.py` が `fcntl` を使うので、Windows では動かない
- `notify.py` の呼び出しが、Lite 版の carousel スキルには無い
