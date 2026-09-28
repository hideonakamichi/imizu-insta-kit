---
name: instagram-publishing
description: 生成済みのバナー画像・リール動画をInstagramに投稿する手順。R2への一時公開URL発行→Instagram APIコンテナ作成→publish→履歴記録→後片付け→Discord通知までを行う。バナー・リール両パイプラインの最終段（evaluator合格後）で使う。
---

# instagram-publishing

evaluatorが合格判定した生成物（バナー画像 or リール動画）を、Instagram API で
実際に投稿する手順。バナー・リール共通で使う。

## 前提

- 連携方式は「Instagram業務用ログイン」（Facebookページ不要、`graph.instagram.com` を
  直接使う）を前提にしている。Facebookページ経由の `graph.facebook.com` 方式ではない。
  Meta側の設定を後者で行っている場合、`ig_post.py` のエンドポイントとIDの取得方法を
  合わせて変更する必要がある
- `IG_USER_ID` は Business Suite等で見えるFacebookページ連携ベースのIDとは**別の値**。
  `GET https://graph.instagram.com/{version}/me?fields=id,username&access_token=<token>`
  で取得できるInstagram固有のユーザーIDを使う
- Instagram API はメディア投稿時に公開URLを要求するため、生成物はいったん
  Cloudflare R2に置いて公開URLを発行し、**投稿完了後に必ず削除する**
- 投稿は「コンテナ作成 → (リールのみ)ステータスポーリング → publish」の2〜3段階
  （詳細は付録「Instagram APIフロー」参照）
- 冪等性のため、`logs/posted.jsonl` への記録は `ig_post.py` が終了コード0（公開確定・`media_id` あり）で
  終わったときにのみ行う。終了コード3（公開されたかもしれない）でも記録しない（Step 2 の表）

## 手順

### Step 0: 二重投稿ガード

`logs/posted.jsonl` を確認し、**同じテーマの当日エントリが既にある場合は投稿を中止**する
（過去に同一テーマの二重投稿が発生した再発防止。再投稿が必要な場合はユーザーの明示指示を待つ）。

### Step 1: R2へアップロードして公開URLを取得

```bash
python3 .claude/skills/instagram-publishing/scripts/r2_upload.py upload \
  --file OUTPUT_DIR/<採用したバナー.png または reel_final.mp4> \
  --key <banners|reels>/<YYYY-MM-DD>_<テーマスラッグ>.<png|mp4>
```

標準出力に公開URLが1行で出る。このURLを次のステップに渡す。

**カルーセルの場合**はスライド枚数分繰り返す（keyは
`banners/<YYYY-MM-DD>_<テーマスラッグ>_<n>.png` のように連番を付け、**表示順を保つ**）。
1枚でもアップロードに失敗したら投稿を中止する。

### Step 2: Instagram APIへ投稿

```bash
# 単発画像 / リール
python3 .claude/skills/instagram-publishing/scripts/ig_post.py \
  --media-type <image|reels> \
  --media-url "<Step 1で取得した公開URL>" \
  --caption-file OUTPUT_DIR/caption.txt \
  --out-json OUTPUT_DIR/post_result.json

# カルーセル（バナー投稿の通常形式。URLは表示順に2〜10個）
python3 .claude/skills/instagram-publishing/scripts/ig_post.py \
  --media-type carousel \
  --media-urls "<slide1のURL>" "<slide2のURL>" "<slide3のURL>" \
  --caption-file OUTPUT_DIR/caption.txt \
  --out-json OUTPUT_DIR/post_result.json
```

- `image`: バナー投稿。コンテナ作成→即publish
- `carousel`: 子コンテナを枚数分作成→親コンテナ（CAROUSEL）作成→publish。
  **子コンテナが1つでも失敗したら親を作らず中止**（「投稿しない」原則）
- `reels`: リール投稿。コンテナ作成→`status_code=FINISHED`までポーリング（最大10分、
  `config/loop-limits.yaml` の `ig_container_polling`）→publish
- 失敗時のエラーコード別対応は `references/graph-api-errors.md` を参照。
  `code=190`（トークン失効）はリトライせず即座に失敗として扱う
- 終了コード0なら `OUTPUT_DIR/post_result.json` に `media_id` / `permalink` が入っている
- `ig_post.py` の結果は3通り。**どれなのかを終了コードで判断する**:

  | 終了コード | 意味 | やること |
  |---|---|---|
  | 0 | 公開確定（`ok: true`） | **すぐ Step 3（履歴に記録）** → Step 4（R2を片づけ）→ Step 5（成功通知） |
  | 1 | 公開していない失敗（公開の前の段階で失敗した／未公開だと確認できた／ほかの投稿処理が実行中 `stage: locked`／前回の後始末が未了 `stage: unconfirmed_pending`） | 記録しない → Step 4 → Step 5（失敗通知）。`post_result.json` の `stage` を通知に含める |
  | 3 | **公開されたかもしれないが、どの投稿か特定できなかった**（`published_unconfirmed: true`） | **絶対に再投稿しない。記録もしない** → Step 4 → Step 5（失敗通知） |

  `ig_post.py` は公開リクエストの**前**に `logs/PUBLISH_UNCONFIRMED.json`（状態ファイル）を書く。これがあるあいだ、
  `ig_post.py` も `bin/run-agent.sh` も新しい投稿をしない。消えるのは、未公開だと確認できたとき（終了コード1）と、
  **Step 3 の `record_post.py` が同じ `media_id` を記録できたとき**だけ。だから終了コード0のあとは、何よりも先に
  Step 3 を実行する（R2の片づけや通知が失敗しても、公開した事実と履歴が食い違わない。Step 3 の前に処理が
  落ちても、次の投稿は止まり、状態ファイルに `media_id` と `permalink` が残っているので記録を復旧できる）。
  終了コード3のときは、`posted.jsonl` に仮の記録を書いて済ませてはいけない（ネタが少ないと theme-picker が
  使用済みのネタを再利用しうるので、人が確認する前に同じ内容がもう一度出る）。Step 5 の通知には
  「公開済みの可能性あり。Instagram を目で確認し、`logs/PUBLISH_UNCONFIRMED.json` の `what_to_do` に従って
  解除すること。解除するまで投稿は止まる」と書く
- `stage: unconfirmed_pending` で失敗したら、前回の状態ファイルが残っている。リトライせず、同じ案内を通知して終了する
- `stage: check_brand` / `stage: verify_account` で失敗したら、設定の問題なのでリトライしない。
  前者は `config/brand.yaml` が未設定、後者は `.env` のトークンが `brand.yaml` の `account.handle` と
  別のアカウントのもの（または確認の通信に失敗）。その旨を通知して終了する

### Step 3: 履歴記録（`ig_post.py` が終了コード0のときだけ。**公開確定の直後に、最初にやる**）

`post_result.json` の `ok: true` を確認してから実行する。

```bash
python3 .claude/skills/instagram-publishing/scripts/record_post.py \
  --pipeline <banner|reel> \
  --theme "<選定したテーマ>" \
  --media-id "<post_result.jsonのmedia_id>" \
  --permalink "<post_result.jsonのpermalink>"
```

カルーセルの場合は `--media-type carousel --slide-count <枚数>` を付けて記録する
（healthcheck・インサイト分析で投稿形式別に比較するため）。

記録に成功すると、`record_post.py` が状態ファイル（`logs/PUBLISH_UNCONFIRMED.json`）を消す。
**記録に失敗したら、状態ファイルは消さずに残し**（次の投稿が止まる）、Step 5 で失敗として通知する。
このあとの Step 4・5 が失敗しても、記録を取り消さない。

### Step 4: R2上の一時ファイルを削除

投稿の成否にかかわらず、公開URLは不要になるので削除する（失敗時もリトライ全滅が確定した時点で
削除してよい。R2容量をほぼ消費しない設計を保つ）。カルーセルの場合はアップロードした全keyを削除する。
削除に失敗しても投稿の成否は変わらない（通知に「R2に一時ファイルが残った」と書き添える）。

```bash
python3 .claude/skills/instagram-publishing/scripts/r2_upload.py delete \
  --key <Step 1で使ったkey>
```

### Step 5: Discord通知

成功時:
```bash
python3 .claude/skills/instagram-publishing/scripts/notify.py success \
  --pipeline <banner|reel> --theme "<テーマ>" \
  --url "<permalink>" --duration-sec <パイプライン開始からの経過秒数>
```

失敗時（どのステージで失敗しても、投稿せず中止した上でここに来る）:
```bash
python3 .claude/skills/instagram-publishing/scripts/notify.py failure \
  --pipeline <banner|reel> --stage "<失敗したステージ名>" \
  --error "<エラー概要>" --artifact-dir "OUTPUT_DIR"
```

## 失敗時の扱い

`CLAUDE.md` の失敗時ルールに従う。**公開の前**（R2アップロード・コンテナ作成・publish の未公開と確認できた失敗）で
失敗したら「投稿しない」に倒し、生成物は `OUTPUT_DIR` に残したまま、Step 5 の失敗通知を送って終了する。
`logs/posted.jsonl` には記録しない。

**公開が確定した後**（Step 3 以降）の失敗は、投稿の失敗ではない。履歴の記録を最優先で行い、
R2の片づけや通知の失敗で公開の事実を取り消さない。

---

## 付録: Instagram APIフロー詳細

ベースURL: `https://graph.instagram.com`（`graph.facebook.com` ではない）

```
# 画像投稿
POST https://graph.instagram.com/{version}/{ig-user-id}/media?image_url=<公開URL>&caption=<本文>
  -> creation_id を取得
POST https://graph.instagram.com/{version}/{ig-user-id}/media_publish?creation_id=<id>
  -> media_id を取得（投稿完了）

# カルーセル投稿（画像2〜10枚）
POST https://graph.instagram.com/{version}/{ig-user-id}/media?image_url=<公開URL>&is_carousel_item=true
  -> 子の creation_id を取得（枚数分繰り返す。captionは付けない）
POST https://graph.instagram.com/{version}/{ig-user-id}/media?media_type=CAROUSEL&children=<id1>,<id2>,...&caption=<本文>
  -> 親の creation_id を取得
POST https://graph.instagram.com/{version}/{ig-user-id}/media_publish?creation_id=<親のid>
  -> media_id を取得（投稿完了）

# リール投稿
POST https://graph.instagram.com/{version}/{ig-user-id}/media?media_type=REELS&video_url=<公開URL>&caption=<本文>
  -> creation_id を取得
GET  https://graph.instagram.com/{version}/{creation_id}?fields=status_code
  -> FINISHED になるまでポーリング（動画は非同期処理。数十秒〜数分）
POST https://graph.instagram.com/{version}/{ig-user-id}/media_publish?creation_id=<id>
  -> media_id を取得（投稿完了）
```

投稿後 `GET /{media_id}?fields=permalink` で投稿URLを取得する（`ig_post.py` が自動実行）。
