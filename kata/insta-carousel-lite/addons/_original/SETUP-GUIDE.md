# Instagram自動投稿システム 構築手順書（研修用）

あるアカウントで実際にゼロから立ち上げ、毎日投稿まで運用したときの記録をもとにした手順書。
「押すボタン」だけでなく、**実際に詰まった箇所と回避策**を中心に書く。
全体の概要・費用・運用の注意は `README.md`、ここは設定作業を順番に進めるための詳細版。

対象読者: このキットを使って、自分のアカウントで同じ仕組みを立ち上げる人。

---

## 0. 全体像

```
ネタ選定 → 生成 → 品質評価（evaluator） → 投稿（Instagram API） → 記録 → Discord通知
  ↑ content/sources/ の    ↑ カルーセル: Pillowで3〜6枚を描画    ↑ 不合格なら該当箇所だけ    ↑ R2に一時公開して    ↑ posted.jsonl
    文章の1節を根拠に       ↑ リール: Grokで10秒×2セグメント        作り直し。2回で不合格は       投稿後に削除
  ↑ brand.yaml                                                     投稿しない
```

- 司令塔は Claude Code（headless）。launchd で定期起動する
- **カルーセルの画像は AI に描かせない**（Pillow で文字をそのまま描く）。リールの映像は **Grok CLI**
  （SuperGrok / X Premium+ のサブスク枠）。ナレーションは **Fish Audio TTS**。BGM は音源ファイル1本
- Instagram には **公開URL上のメディアしか渡せない**ので、Cloudflare R2 に置いてから投稿し、直後に消す

必要なサービスと、それぞれ何に使うか:

| サービス | 用途 | 必須度 |
|---|---|---|
| Meta for Developers | Instagram への投稿（トークン発行） | 必須 |
| SuperGrok / X Premium+ | リールの映像生成 | リールを使うときだけ（カルーセルだけなら不要） |
| Cloudflare R2 | メディアの一時公開 | 必須 |
| Discord Webhook | 成功・失敗の通知 | 必須（無人運用の生命線） |
| Fish Audio | リールのナレーション | リールを使うときだけ |

---

## 1. 前提環境

- macOS（launchd で定期実行するため。予定の時刻にスリープしていると、復帰した時点で遅れて実行される）
- Claude Code（`claude` コマンド）
- Python 3.10 以上、ffmpeg（`brew install ffmpeg`）
- Grok CLI（`curl -fsSL https://x.ai/cli.sh | bash` → `grok login`）

---

## 2. キットの展開と初期化

```bash
unzip insta-autopost-kit.zip
cd insta-autopost-kit          # フォルダ名は変えてよい（launchd のジョブ名に使われる）
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp env.template .env
git init && git add -A && git commit -m "初期コミット"
```

`.env` はこの時点では空でよい。**値は本人が埋める**（AIには読ませない・貼らせない）。

---

## 3. アカウントの人格とネタ元を用意する（brand.yaml / content/sources）

Claude Code をこのフォルダで開き、「brand-setup スキルで設定して」と頼むと、対話で埋めてくれる。
用意するのは次の3つだけ。パイプライン本体は触らない。

| ファイル | 役割 |
|---|---|
| `config/brand.yaml` | 誰に・何を・どんなトーンで。evaluator の合否基準がここから作られる |
| `content/sources/*.md` | **投稿の根拠になる自分の文章**。`## 見出し` の1節が1ネタになる（書式は `content/sources/README.md`） |
| `docs/DESIGN.md` | 見た目の憲法。5節 Tone の1行目だけジャンルに合わせて書き換える |

`config/brand.yaml` に `（…）` のプレースホルダーが1つでも残っていると、パイプラインは投稿せずに止まる
（他人の設定のまま無人投稿してしまう事故を防ぐ安全装置）。

### 詰まりどころ: 1行のテーマだけで書かせると中身が薄くなる

最初は「テーマを1行ずつ並べたネタ帳」から投稿を作らせていた。出てくるのは、どの本にも書いてある
一般論だった。**自分で書いた文章の1節を根拠として渡し、そこに書いてある事実だけを使わせる**方式に
変えてから、固有の数字・手順・資料名が入るようになった。だからこのキットは、ネタ元の文章が無いと投稿を作らない。

### 詰まりどころ: 根拠のないネタを入れない

サイトに1回だけ出てくる一校の事例を、「読者に共通する悩み」として一般化して投稿1本を組み立てて
しまったことがある。指摘されて出典を確認したら、一般化できる話ではなかった。

- ネタ元に置くのは、**自分が内容に責任を持てる文章だけ**。AIに下書きさせた場合も、必ず自分で事実を確認する
- `brand.yaml` の `tone.policy` に「実績・事例を新たに創作しない」を入れておくと、evaluator が弾く
- 一次資料に基づく話は、front matter の `sources` に資料名を書いておく（投稿でもその表記が使われる）

### 詰まりどころ: 扱いに縛りがある話題

まだ決まっていない制度、効果効能、価格、体験談など、書き方を間違えると問題になる話題は、避けるのではなく
**縛りを明文化する**。`tone.policy` に原則を書き、`content_sources.cautions` に「この語が出てくる節には
この注意を付ける」を登録する。注意は構成・台本・キャプションに渡り、evaluator が守られているか判定する。
断り書き（「検討中」「個人の感想」など）は、ナレーションだけでなく**画面の文字**にも入れさせる（無音視聴が多数派）。

---

## 4. Instagram アカウントの作成

### 作り方

- **スマホの Instagram アプリで作る**ことを勧める。PCでも作れるが、新規アカウントを
  デスクトップから作って即プロ化→即API投稿、という流れは凍結判定を受けやすい
- メールは事業用アドレス（個人メールだと引き継ぎで切り離せない）
- 生年月日は運営者本人の実際のもの（偽ると年齢確認で詰む）

### アカウントセンター

「個人の Facebook/Instagram と連結しますか」と聞かれる。**連結しない。**
このキットの投稿方式では不要で、連結すると「知り合いかも」で個人アカウントが露出する。
プロ化で単独のアカウントセンターが自動で1つ作られるのは問題ない。

### プロフィール設定（検索に効く）

| 項目 | 内容 | 理由 |
|---|---|---|
| ユーザーネーム | ほかのSNSと同じにする | 媒体をまたいで辿れる |
| **名前欄** | `ブランド名｜何の発信か`（30字以内。例: `〇〇ラボ｜在宅ワークの整理術`） | **Instagram検索は名前欄を拾う**。ブランド名だけだと誰も検索しない |
| 自己紹介 | 150字以内。何者か／差別化／何が流れてくるか／運営元 | 3行目が「フォローする理由」 |
| リンク | **短縮URLではなく直リンク** | アプリ内ブラウザで短縮リンクは中継ページが挟まる |
| アイコン | 小サイズで潰れない1文字ロゴ | 30px程度に縮む。キャラ絵は潰れる。**署名入りの画像に注意** |

### プロアカウント化

- 種別は **ビジネス**（API投稿の確実性・連絡先ボタン）
- カテゴリは `教育` 系（「AIクリエイター」だと個人制作者に見える）
- **途中で出る「Facebookページをリンク」はスキップ**（§8参照）

### 助走（アカウントを温める）

いきなり自動投稿を始めない。生成した画像を**スマホから手動で1日1本、3〜4本**出してから自動化へ。
最初の3本は実用情報、4本目で初めてサービス紹介、という順にする。

---

## 5. 先に見た目を確かめる（順番が重要）

**生成と投稿は分離できる。** カルーセルの描画（`banner.py`。Pillow で文字をそのまま描く）は、
R2 も Meta も Grok も要らない。作例の構成でまず1回描いてみる。

```bash
.venv/bin/python3 .claude/skills/banner-production/scripts/banner.py \
  --spec examples/carousel-4slides/carousel_spec.json --out-dir output/_trial/
```

したがって順番は **描いて目視 → brand.yaml（色・トーン）を調整 → 手動投稿で助走 → R2/Meta → 自動化**。
Meta の設定（最難関）を先にやると、突破した後に「トーンが違う」と判明する順序になる。

`carousel_spec.json` の文字量上限（見出し13字・sub 20字・points 15字×3・cta 18字）は余白と可読性に
直結するので厳守。描画前にスクリプトが検証する。

リールを使うなら、この段階で Grok CLI を入れてサインインしておく（`grok login`）。
SuperGrok か X Premium+ のサブスクが要る。カルーセルだけなら不要。

---

## 6. Discord Webhook（5分・最初に入れる）

チャンネル設定 → 連携サービス → ウェブフック → URLをコピー → `.env` の `DISCORD_WEBHOOK_URL`。
他システムの通知先とは**チャンネルを分ける**（失敗時にどのシステムか一目で分かるように）。

疎通テスト:

```bash
.venv/bin/python3 .claude/skills/instagram-publishing/scripts/notify.py report \
  --title "接続テスト" --body "insta-autopost からの疎通確認です。"
```

---

## 7. Cloudflare R2（10分）

1. **バケットを新規作成**（他事業のバケットを使い回さない。権限・障害を分離するため）
2. 設定 → **パブリック開発URL を有効化** → `https://pub-xxxx.r2.dev` が `R2_PUBLIC_BASE_URL`（末尾スラッシュなし）
3. API → **Account API トークン**を作成（User API トークンは担当者が変わると失効する）
   - 権限: **オブジェクト読み取りと書き込み**（投稿後に削除するため書き込みが要る）
   - 適用先: **そのバケットのみ**
   - TTL: **無期限**（期限を付けると切れた瞬間に静かに失敗し始める）
4. 発行画面の「エンドポイント」URL の先頭部分が `R2_ACCOUNT_ID`

```
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET=my-insta-media
R2_PUBLIC_BASE_URL=https://pub-xxxx.r2.dev
```

疎通テスト（アップロード → 公開URLで取得 → 削除、を1周）:

```bash
S=.claude/skills/instagram-publishing/scripts/r2_upload.py
.venv/bin/python3 $S upload --file <画像> --key test/x.png     # 公開URLが返る
curl -sI <そのURL> | head -1                                      # 200
.venv/bin/python3 $S delete --key test/x.png
```

注意: `r2.dev` は Cloudflare が「本番非推奨・レート制限あり」としている。週数本なら問題ないが、
頻度を上げるならカスタムドメインに切り替える（`R2_PUBLIC_BASE_URL` の1行差し替えで済む）。

---

## 8. Meta（Instagram API）— 最難関

### 先に知っておくこと

- このキットは **Instagram業務用ログイン方式**（`graph.instagram.com`）。**Facebookページは不要**
- ただし developers.facebook.com に入るための **Facebookアカウント（個人ログイン）は必要**
- `META_APP_ID` / `META_APP_SECRET` も不要（トークン更新は `ig_refresh_token` 方式）
- 元キットの README と `env.template` は旧方式（Facebookページ連携）の記述だった。修正版では直してある

### 手順

1. developers.facebook.com → マイアプリ → アプリを作成
2. ユースケース: **「Instagramでメッセージとコンテンツを管理」**（説明に「投稿の公開」が含まれるもの）
3. ビジネスポートフォリオ: **「現時点ではリンクしない」**
   - ポートフォリオのリンクは「他人のデータを扱うアプリを公開する」ための手続き。自分のアカウント1つなら不要
   - 他事業のポートフォリオを選ばない（事業の資産が混ざる）
4. アプリ作成後、Instagram → **「Instagram APIをInstagramログインで設定」**
   - 「FacebookログインでInstagram APIを設定」は**選ばない**（旧方式）
5. 「Add all required permissions」を押す。**ただしこれだけでは足りない**（次項）
6. 「アカウントを追加」で自分の Instagram を接続 → 「トークンを生成」
7. 画面に出る数値 ID が `IG_USER_ID`、トークンが `IG_ACCESS_TOKEN`

### 詰まりどころ①: `instagram_business_content_publish` が必須リストに無い

「必要なメッセージアクセス許可」に並ぶのは `basic` / `manage_comments` / `manage_messages` の3つで、
**投稿に必要な `content_publish` は入っていない**。「アクセス許可と機能」ページから手動で追加する。
抜けているとトークンは正常に発行できるのに、**投稿の瞬間だけ権限エラー**で落ちる（読み取りは通るので気づきにくい）。

「テスト準備完了」のステータスで十分。アプリ審査は他人のアカウントに投稿するときだけ必要。

### 詰まりどころ②: 「開発者の役割が不十分です」

「アカウントを追加」で出る。**招待と承認の2段階**が要る。

1. アプリの役割 → 役割 → 「Instagramテスターを追加」→ ユーザーネーム（@なし）
2. **Instagram 側で承認**: https://www.instagram.com/accounts/manage_access/ → テスターの招待 → 承認
3. コンソールに戻って「アカウントを追加」を再実行

承認を忘れて詰まる人が多い。複数アカウントにログインしていると、別アカウントで承認してしまうことがある。

### 認可ダイアログ

「コンテンツへのアクセスと公開」が**オン**になっていることを確認して許可。
他（コメント・メッセージ・インサイト）は使わないが、外すと認可が弾かれることがあるので初回は全部オンで通す。
このトークンが漏れると DM の閲覧・送信までできる。`.env` は `.gitignore` 済みだが取り扱い注意。

### 検証

```bash
.venv/bin/python3 .claude/skills/system-healthcheck/scripts/check_token.py
# → {"ok": true, "valid": true, "remaining_days": 59, ...}
```

Instagram に実際に問い合わせて有効性を確認する。トークンは60日で失効。週次点検が10日前から警告する。

---

## 9. Fish Audio（リールを使うときだけ）

fish.audio でAPIキー発行、声を試聴して ID をコピー → `.env` の `FISH_AUDIO_API_KEY` / `FISH_AUDIO_VOICE_ID`。

```bash
.venv/bin/python3 .claude/skills/reel-production/scripts/audio_generate.py \
  --text "机の上に置く物を、3つに絞る方法をお話しします。" --out /tmp/tts_test.mp3
```

生成された mp3 を**実際に聴いて**、brand.yaml の `voice.style` に合うか確認する。

---

## 10. BGM

`content/bgm/` の先頭の mp3 が全リールに敷かれる（ランダム選曲はしない。ブランドサウンドとして固定）。

**音源はキットに含まれていない**（ライセンスの都合）。商用利用できる音源を自分で置くか、Grok で生成する。
Grok CLI に音楽専用の機能はないので、「音楽が主役の15秒動画」を作って音声トラックを抜く:

```bash
# grok_media.generate_video(prompt, out.mp4, duration_sec=15) を音楽主体のプロンプトで呼ぶ
ffmpeg -i out.mp4 -vn -c:a libmp3lame -q:a 2 -ar 44100 content/bgm/my_bgm_01.mp3
```

プロンプトの要点: 楽器・BPM・「ボーカルなし・効果音なし・フェードなし・ループできる終わり」。
生成後は `ffmpeg -af volumedetect` で無音や途切れがないか確認する。

---

## 11. 初投稿（API 経由・手動で1本）

自動パイプラインに任せる前に、**投稿経路だけを手動で1周**させる。
`content_publish` 権限が本当に効くかは、実際に投稿するまで分からないため。

```bash
S=.claude/skills/instagram-publishing/scripts
# 0. 二重投稿ガード: logs/posted.jsonl に同テーマの当日エントリが無いこと
# 1. R2 へ表示順にアップロード（key に連番）
.venv/bin/python3 $S/r2_upload.py upload --file slide_1.png --key banners/<date>_<slug>_1.png
# 2. 投稿（カルーセルは URL を表示順に2〜10個）
.venv/bin/python3 $S/ig_post.py --media-type carousel --media-urls <url1> <url2> ... \
  --caption-file caption.txt --out-json post_result.json
# 3. 履歴記録（ig_post.py が ok:true で終わったら、**まず最初に**。記録すると logs/PUBLISH_UNCONFIRMED.json が消える）
.venv/bin/python3 $S/record_post.py --pipeline banner --theme "..." --media-id ... --permalink ... \
  --media-type carousel --slide-count 4
# 4. R2 から削除（投稿の成否にかかわらず。ここが失敗しても、投稿と記録は取り消さない）
.venv/bin/python3 $S/r2_upload.py delete --key banners/<date>_<slug>_1.png
# 5. 通知
.venv/bin/python3 $S/notify.py success --pipeline banner --theme "..." --url <permalink>
```

`ig_post.py` は、`config/brand.yaml` が設定済みで、トークンのアカウントが `account.handle` と同じときだけ投稿する。
公開リクエストの前に `logs/PUBLISH_UNCONFIRMED.json` を書き、3 の記録が済むと消える。このファイルが残っているあいだは
次の投稿ができない（途中で止まった・公開されたか分からない、を二重投稿にしないため）。残ったら中の `what_to_do` に従う。

### 知っておくこと: `code 9007 / subcode 2207027` は失敗ではない

publish の1回目に「このメディアは公開する準備ができていません」が返ることがある。
コンテナ作成直後は公開できないだけで、`ig_post.py` のリトライ（5秒バックオフ）が吸収する。
ログでこのエラーを見ても、最後に `ok: true` なら成功。

---

## 12. リール

1本の流れ: 台本（`video_prompt_1.txt` / `_2.txt` / `reel_meta.json`）→ セグメントごとに生成 →
ナレーション＋BGMミックス → フレーム抽出 → 検品 → 投稿。

```bash
O="output/2026-01-15_my-theme"        # 直したい生成物のフォルダ（reel_meta.json があるもの）に置き換える
R=.claude/skills/reel-production/scripts
.venv/bin/python3 "$R/generate_video.py" --meta "$O/reel_meta.json" --out "$O/reel_video.mp4" --only-segment 1
.venv/bin/python3 "$R/generate_video.py" --meta "$O/reel_meta.json" --out "$O/reel_video.mp4" --only-segment 2  # 揃うと自動結合
.venv/bin/python3 "$R/narrate_and_mix.py" --meta "$O/reel_meta.json" --video "$O/reel_video.mp4" --out "$O/reel_final.mp4"
.venv/bin/python3 "$R/extract_frames.py" --video "$O/reel_final.mp4" --out-dir "$O/frames"
```

- 1セグメント2〜5分。**セグメントごとに1コマンド**（まとめると600秒の上限を超える）
- `--out` には `reel_video.mp4` を指定する。`reel_final.mp4` を指定すると、ナレーション無しの動画が投稿用ファイルを上書きする
- 映像を再生成してもナレーションは `--skip-tts` で流用できる（TTS課金なし）
- 検品は**実フレーム**で行う（プロンプトだけで判断しない）。各ショットの文字が出揃った時点のフレームを見る

### 実測で分かった不具合と対策（仕様書に反映済み）

| 症状 | 原因 | 対策 |
|---|---|---|
| 画面に `#FDFBF` が文字として描かれる | スタイルロックのパレットhexをモデルが描いた | 「カラーコードや#を文字として描くな」を必須化 |
| 表紙・一部ショットだけ明朝体になる | 書体指定が弱い | 「明朝禁止・全ショット同一ゴシック」を必須化 |
| realistic で**人物の顔**が描かれた | 「後ろ姿のみ」では medium shot に顔が出る | 「人物は手首から先のみ・上半身が入る構図は書かない」を必須化。全フレームで顔を目視 |
| ページ番号が下端で切れる | 3:4生成→4:5トリムの安全域外 | 安全域厳守・入らなければ省略 |
| 見出しに鉤括弧が勝手に付く | モデルの癖 | 「指定文字列に記号を足すな」を追加 |
| 背景装飾・ページめくり状の曲面・金線の二重・数字や文字の二重描画・余分な縦棒 | **禁止文を積んだこと自体が原因。** モデルは否定した語を描く（`no double line`→二重線、`no dot`→余分な点）。台本が3,400字/否定48件に膨らんでいた | **禁止を足さない。** 成功実績の水準（約2,400字・否定23件・ショット記述は肯定形1文）に戻す。`examples/reel-minimal-20s/` を基準に使う |

### 不合格になったリールを手で直すとき（安く済ませる手順）

パイプライン全体を回し直すと、Claude 側の費用が毎回まるごとかかる。映像だけ直せば済むことが多い:

1. evaluator の指摘を読み、`video_prompt_N.txt` の該当ショットを直す（**禁止を足さず、要素を減らす**）
2. `generate_video.py --lint-only` → `--only-segment N` で、直したセグメントだけ再生成
3. ナレーション原稿を変えていなければ `narrate_and_mix.py --skip-tts`
4. `extract_frames.py` → フレームを自分の目で見る → evaluator → 投稿

実際によく出る崩れと直し方: 1行10字以上で画面幅が足りないと**傍点や詰まった書体**が出る（1行9字以下に割る）。
エンドカードの誘導行にアクセント色を指定すると**白い箱付きのボタン風**になったり**同じ行が二重**に出たりする
（本文と同じ色の小さい文字にする）。2セグメントの片方だけ `top-centered` と書くと**つなぎ目で縦位置がずれる**（両方同じ語にする）。

### スタイルの運用方針

`brand.yaml` の `reel_style` は **minimal を既定**。realistic は見た目が強いが、2セグメントを別々に生成するため
**前半と後半で机・光・小道具が変わりやすく**、品質ゲートで落ちやすい（実績: 自動実行2回のうち投稿に至ったのは1回）。
効いた対策は「全ショットを同じ机の真上からの構図にする・小道具を1種類に絞る・光と机の形容を1語ずつにする・
後半に新しい物を持ち込まない」。真上からの構図にすると、胴体や顔がフレームに入る余地もなくなる。

realistic 便（`bin/run_reel_realistic.sh`）は、評価フレームを0.5秒間隔（20秒で約40枚）にし、顔が1枚でも
写れば引き直さずに中止する。それでも取りこぼしはゼロではない。**定期実行に入れる前に、手動で数本まわして
全フレームを自分の目で見ること。**

---

## 13. 定期実行へ

助走投稿を目視で2〜3本確認し、完全自動の1本（`bash bin/run_banner.sh`）も目視してから:

```bash
bash bin/setup_launchd.sh --dry-run
bash bin/setup_launchd.sh
```

スケジュールは **`config/schedule.yaml` だけ**に書く（launchd の登録も週次点検の「投稿漏れ」判定も、このファイルを読む）。
変えたら `bash bin/setup_launchd.sh` を再実行する。`enabled: false` にしたジョブは解除される。
登録状況は `bash bin/setup_launchd.sh --status` で見られる。

既定は カルーセル 月水金 9:00／リール 火土 12:00／週次点検 日曜 10:00（realistic 便は無効）。
いきなり毎日にしない。1回ごとに費用がかかり、品質ゲートで中止した回にも同じだけかかる（README「費用」）。
週次点検はトークン期限・投稿成否・いま選べるネタの残数を Discord に出す。

**定期実行の前に必ずやること**（やらないと初回が確実に失敗する）:

1. このフォルダで `claude` を**対話モードで1回起動**し、「このフォルダを信頼しますか」を承認する。
   未承認だと `.claude/settings.json` の許可リストが丸ごと無視され、無人実行ではすべての処理が
   承認待ちのまま拒否される。しかも実行中の Claude にはその理由が見えないので、ログの診断も外れる。
   起動時の標準出力に `Ignoring N permissions.allow entries ... has not been trusted` と出ていたらこれ
2. その時刻に Mac がスリープしない設定にする。予定の時刻にスリープしていると、ジョブは**復帰した時点で遅れて実行**される
   （朝9時の投稿が、昼にMacを開いた瞬間に出る）。電源が切れていた場合は実行されない

---

## 14. このキットを人に渡すとき

**実データで埋めた作業フォルダをそのまま固めて渡さない。**
`config/brand.yaml` にプレースホルダーが無いと「未設定なら実行中止」の安全装置が効かず、受け取った人が
自分のアカウントに他人のブランドの投稿を無人公開してしまう。渡すのは、受け取った状態の zip にする。
`.env`・`logs/`・`output/`・`content/articles/`・`content/sources/` の自分の文章も含めない。

---

## 15. `.env` の全変数

| 変数 | 取得元 | 用途 |
|---|---|---|
| `IG_USER_ID` | Meta アプリの Instagram 設定画面 | 投稿先アカウント（数値ID。@ハンドルではない） |
| `IG_ACCESS_TOKEN` | 同上「トークンを生成」 | 投稿・更新（60日で失効） |
| `GRAPH_API_VERSION` | 既定 `v21.0` | 通常そのまま |
| `R2_ACCOUNT_ID` | トークン発行画面のエンドポイントURL先頭 | R2接続 |
| `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` | Account API トークン | R2認証（シークレットは1回しか表示されない） |
| `R2_BUCKET` | 作成したバケット名 | 一時公開先 |
| `R2_PUBLIC_BASE_URL` | パブリック開発URL | 末尾スラッシュなし |
| `DISCORD_WEBHOOK_URL` | チャンネルのウェブフック | 通知 |
| `FISH_AUDIO_API_KEY` / `FISH_AUDIO_VOICE_ID` | fish.audio | ナレーション（リール時のみ） |
| `GROK_BIN` | 任意 | `grok` が PATH 外のときだけ |

Grok は `.env` ではなく `grok login`（`~/.grok/auth.json`）で認証する。

---

## 16. 検証コマンド集（設定後に順に叩く）

```bash
V=.venv/bin/python3
$V .claude/skills/instagram-publishing/scripts/notify.py report --title "接続テスト" --body "ok"   # Discord
$V .claude/skills/instagram-publishing/scripts/r2_upload.py upload --file <png> --key test/x.png   # R2
$V .claude/skills/system-healthcheck/scripts/check_token.py                                         # Meta
$V .claude/skills/system-healthcheck/scripts/check_grok.py                                          # Grok
$V .claude/skills/reel-production/scripts/audio_generate.py --text "テスト" --out /tmp/t.mp3        # Fish Audio
```
