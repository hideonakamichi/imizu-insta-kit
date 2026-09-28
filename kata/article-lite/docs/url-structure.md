# URL 設計 — 全国制度と都道府県制度

最終更新: 2026-07-25

このサイトは「全国どこでも使える制度」と「その都道府県だけの制度」を、
**URL のレベルではっきり分ける**設計になっている。
47都道府県に自動展開できることを最優先にしているので、
**ページを増やすのに JSX を触る必要はない**（DB に行を足すだけ）。

---

## 1. URL 一覧

| URL | 内容 | 実装ファイル |
| --- | --- | --- |
| `/` | トップ。全国制度のカテゴリ別一覧＋地域制度への入口 | `site/app/page.jsx` |
| `/support/{id}` | **全国制度**の記事（既存10本） | `site/app/support/[id]/page.jsx` |
| `/{pref}` | **都道府県ハブ**（例: `/tokyo`） | `site/app/[pref]/page.jsx` |
| `/{pref}/support/{id}` | **都道府県の制度記事**（例: `/tokyo/support/11`） | `site/app/[pref]/support/[id]/page.jsx` |
| `/words` `/words/{slug}` | 用語集 | `site/app/words/…` |
| `/roundtable` `/roundtable/{slug}` | おしゃべり | `site/app/roundtable/…` |
| `/about` `/characters` `/privacy` `/disclaimer` | 固定ページ | 各 `page.jsx` |

`{pref}` は `prefectures.slug`（`tokyo` / `osaka` / `hokkaido` …）。
`{id}` は `supports.id`。**都道府県名や slug をコードに直書きしない**のがこの設計の肝。

### なぜ `/tokyo/support/{id}` で、`/support/tokyo/{id}` ではないのか

- `/tokyo` という短い URL が「東京都のひとり親支援」というクエリの受け皿になる（競合が手薄な領域）
- パスの第1階層が地域なので、将来 `/tokyo/shibuya`（市区町村）へ自然に伸ばせる
- `/support/…` は「全国制度」という意味を保てる

---

## 2. ルーティングの仕組み

### 2-1. データの流れ

```
prefectures            47件（id, slug, name_ja, region）— 最初から全件入っている
supports               制度。is_nationwide で全国/地域を区別
support_prefectures    supports × prefectures の join（地域制度だけがここに載る）
```

- **全国制度** = `is_nationwide` が `true`（または NULL）。`/support/{id}` で公開。
- **地域制度** = `is_nationwide = false` かつ `support_prefectures` にひもづきがある。
  `/{pref}/support/{id}` で公開。

### 2-2. クエリは `site/lib/supabase.js` に集約

| 関数 | 返すもの |
| --- | --- |
| `getSupportList()` | **全国制度のみ**（記事本文あり）。トップ・`/support/[id]` の静的生成・sitemap が使う |
| `getPrefecture(slug)` | `prefectures` から1件（存在しなければ `null`） |
| `getPrefectureList({ requireArticle })` | **制度がひもづく都道府県だけ**。47件全部は返さない。`support_count` / `article_count` 付き |
| `getPrefectureSupports(slug, { requireArticle })` | その県の制度一覧。`has_article` 付き |
| `getSupportWithPrefecture(id)` | 制度1件＋ひもづく都道府県（整合性チェック用） |
| `getPrefectureSupportPairs()` | 記事本文がある `(pref slug × support id)` の組み合わせ |

`requireArticle` の使い分け:

- `true`（既定）… 記事本文がある県／制度だけ。**sitemap と SEO 導線**はこちら
- `false` … 記事がまだでも制度が登録されていれば含む。**ハブページの 404 判定**と `generateStaticParams` はこちら
  （＝記事0本の県でもハブは 200 で「準備中」を出す）

すべて `sbFetchSafe` 経由なので、テーブル未作成・0件でもページは落ちない。

### 2-3. 404 の判定ルール

| URL | 結果 | 理由 |
| --- | --- | --- |
| `/tokyo` | 200 | `prefectures` にあり、制度がひもづいている（記事0本でも「準備中」表示で 200） |
| `/hokkaido` | 404 | `prefectures` にはあるが、制度が1件もひもづいていない |
| `/foo` | 404 | `prefectures` に無い |
| `/tokyo/support/11` | 200 | `support_prefectures` に (11, 東京都) がある |
| `/tokyo/support/1` | 404 | 1 は全国制度。東京都にひもづいていない |
| `/osaka/support/11` | 404 | 11 は東京都の制度。大阪府にひもづいていない |
| `/support/11` | **308 →** `/tokyo/support/11` | 地域制度の正規 URL は都道府県つきなので寄せる |

`/{pref}/support/{id}` の検証は `loadPrefSupport()` に集約してある。
**pref と id の整合性を必ず `support_prefectures` で確認する**こと（推測でページを出さない）。

### 2-4. ★ルート衝突★（必ず読むこと）

`app/[pref]/page.jsx` は動的セグメントなので、理屈のうえでは
`/about` `/words` `/roundtable` `/characters` `/privacy` `/disclaimer` `/support`
といった既存 URL とぶつかる。

- **Next.js App Router は静的ルートを動的ルートより優先して解決する**ので、
  `/about` などは `[pref]` に飲み込まれない（検証済み。下記 3-3 参照）
- ただしそれに頼りきらず、`[pref]` 側で
  **`prefectures` テーブルに無い slug は必ず `notFound()`** を返している。
  → `/foo` も `/support`（一覧ページは存在しない）も 404 になる

**新しい固定ページを増やすとき**は、そのパス名が
都道府県 slug と衝突しないことだけ確認すればよい
（`tokyo` `osaka` … という名前の固定ページを作らない、というだけの話）。

---

## 3. 新しい都道府県を追加する手順

コードの変更は**不要**。DB に行を足すだけで、ハブページも記事ページも sitemap も自動で生える。

### 3-1. 手順

```bash
# 0) 都道府県の id を確認（prefectures は最初から47件そろっている）
bash scripts/supabase-query.sh select prefectures "slug=eq.osaka&select=id,slug,name_ja"

# 1) 制度を登録する（is_nationwide は必ず false）
bash scripts/supabase-query.sh insert supports @/tmp/osaka-support.json
#    最低限: program_code, title, summary, category, is_nationwide=false, organizer, official_url, status='active'
#    program_code は「{pref-slug}-{制度名ローマ字}」の形にそろえる（例: osaka-jido-ikusei-teate）

# 2) 都道府県にひもづける ★これを忘れるとページが生えない★
bash scripts/supabase-query.sh insert support_prefectures '{"support_id":21,"prefecture_id":27}'

# 3) 記事を書く（article_md を埋める）
#    → この時点で /osaka/support/21 が公開され、sitemap にも載る
```

### 3-2. 各段階で何が起きるか

| 状態 | `/osaka` | `/osaka/support/{id}` | トップの導線 | sitemap |
| --- | --- | --- | --- | --- |
| `supports` に入れただけ（join なし） | 404 | 404 | 出ない | 載らない |
| `support_prefectures` にひもづけた | 200「準備中」 | 404 | 出る（「準備中」表示） | 載らない |
| `article_md` を書いた | 200（制度カード） | 200 | 出る（「N件の解説」） | 載る |

つまり **join を張った時点でハブが公開され、記事を書いた時点で SEO 導線が開く**。

### 3-3. 追加後に確認すること

```bash
cd site
for u in / /osaka /osaka/support/21 /about /words /support/1 /foo; do
  echo "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:3000$u)  $u"
done
```

- 新しい県のハブが 200 か
- 既存ページ（`/about` `/words` など）が 200 のままか（＝ `[pref]` に飲まれていないか）
- 存在しない slug が 404 か

> dev サーバーは `revalidate = 300`（5分）の fetch キャッシュを持つため、
> DB を変えた直後は古い結果が返ることがある。すぐ確かめたいときは
> `rm -rf site/.next/cache/fetch-cache` してからリクエストする。

---

## 4. 記事を書くときの内部リンク規約

| 参照先 | 書き方 |
| --- | --- |
| 全国制度 | `[児童扶養手当](/support/1)` |
| 地域制度 | `[児童育成手当](/tokyo/support/11)` ← **都道府県 slug を必ず付ける** |
| 都道府県ハブ | `[東京都の制度一覧](/tokyo)` |

- 地域制度を `/support/11` と書いても 308 でリダイレクトされるが、
  **内部リンクは最初から正規 URL（`/tokyo/support/11`）で書くこと**
- リンクを書く前に DB で id の存在を確認する
  （`bash scripts/supabase-query.sh select supports "id=eq.11&select=id,title"`）
- 全国制度の記事から地域制度へリンクするときは
  「東京都にお住まいの場合は」のように**地域限定であることを明示**する

> 注: `.claude/skills/editorial-url-rules/SKILL.md` は全国制度（`/support/{id}`）を
> 前提に書かれている。地域制度の記事を書くときは本ファイルの規約が優先。

---

## 5. 設計上まもること

1. **都道府県名・slug をコードに直書きしない。** すべて `prefectures` から引く。
   `if (pref === 'tokyo')` のような分岐を書いた時点でこの設計は壊れる。
2. **見た目を県ごとに変えない。** 47県ぶんの CSS を保守することになる。
   `.badge-pref` などは県共通のスタイル。
3. **`generateStaticParams` で47件を全部生成しない。** 制度がひもづく県だけ。
4. **地域制度をトップと `/support/{id}` に混ぜない。** `getSupportList()` が
   `is_nationwide` で絞っているので、この関数を経由すれば自動的に守られる。
5. **地域制度のページには必ず全国制度への導線を置く。**
   併用できることを知らずに取りこぼすのが、このジャンルで最大の実害になる。
