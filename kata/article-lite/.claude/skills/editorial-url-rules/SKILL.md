---
name: editorial-url-rules
description: サイトの URL 構造ルール。全国制度は `/support/{id}`、地域制度は `/{pref}/support/{id}` (例 /tokyo/support/11)、都道府県ハブは `/{pref}`。用語集は `/words/{slug}`、おしゃべりは `/roundtable/{slug}`。記事執筆・レビュー・通知・内部リンクを書くすべての agent が読む。
user-invocable: false
---

# URL ルール

★2026-07-25 更新: 都道府県別 URL 構造 (A案) を導入。詳細設計は `docs/url-structure.md` を参照。

## URL 一覧

| コンテンツ | URL | 例 |
|---|---|---|
| **全国制度** (is_nationwide=true) | `/support/{id}` | `/support/1` 児童扶養手当 |
| **地域制度** (is_nationwide=false) | **`/{pref}/support/{id}`** | `/tokyo/support/11` 児童育成手当 |
| **都道府県ハブ** | **`/{pref}`** | `/tokyo` 東京都のひとり親支援制度 |
| 用語集 | `/words/{slug}` | `/words/fuyou` 扶養 |
| おしゃべり | `/roundtable/{slug}` | `/roundtable/jijitsukon-to-iu-sentaku` |
| 固定ページ | `/about` `/privacy` `/disclaimer` `/characters` | |

> `${PUBLIC_SITE_URL}` は `.env.local` の `PUBLIC_SITE_URL` (本番: `https://example.com`)

`{pref}` は `prefectures` テーブルの `slug` (tokyo / osaka / hokkaido …)。

## ★地域制度と全国制度の判別 (最重要)★

リンクを書く前に、その制度が**全国制度か地域制度か**を必ず DB で確認する:

```bash
bash scripts/supabase-query.sh select supports "id=eq.{id}&select=id,title,is_nationwide"
```

- `is_nationwide: true` → `/support/{id}`
- `is_nationwide: false` → `/{pref}/support/{id}` ← **都道府県 slug が必要**。紐づく都道府県は support_prefectures から取得:

```bash
bash scripts/supabase-query.sh select support_prefectures "support_id=eq.{id}&select=prefecture_id"
bash scripts/supabase-query.sh select prefectures "id=eq.{prefecture_id}&select=slug,name_ja"
```

★地域制度を `/support/{id}` でリンクしても 308 リダイレクトで正しいページに飛ぶが、**記事中には正しい URL を直接書くこと** (リダイレクトは SEO 上わずかに不利)。

## ❌ 絶対書いてはいけない

- `/support/tokyo` (旧設計。都道府県ハブは `/{pref}` = `/tokyo`)
- `/support/11` のような**地域制度を全国パスで書くこと** (308 になる)
- `/tokyo/support/1` のような**全国制度を地域パスで書くこと** (404 になる)
- `/subsidy/{id}` (旧テーマの廃止パス)
- 存在しない ID へのリンク

## ID・slug 取得の原則

必ず **DB から取得**。自分で計算・推測しない。書く前に存在確認する。

```bash
# 全国制度
bash scripts/supabase-query.sh select supports "id=eq.{id}&select=id,title,is_nationwide"
# 用語集
bash scripts/supabase-query.sh select glossary "slug=eq.{slug}&select=slug,term,article_md"
# おしゃべり
bash scripts/supabase-query.sh select roundtables "slug=eq.{slug}&select=slug,title,article_md"
```

★用語集・おしゃべりは `article_md` が NULL のものはページが 404 になる (執筆前)。リンクする前に本文があることを確認すること。

## Discord 通知での URL 書式

外部に出す URL (Discord / note 等) は **Full URL** で書く。相対パスは禁止:

- ❌ `ID 124` / `制度124` / `/support/124`
- ✅ `${PUBLIC_SITE_URL}/support/124`
- ✅ `${PUBLIC_SITE_URL}/tokyo/support/11` (地域制度)

## 内部リンクの書き方 (記事中)

```markdown
[児童扶養手当](/support/1)                    ← 全国制度
[児童育成手当](/tokyo/support/11)             ← 地域制度 (東京都)
[東京都のひとり親支援制度](/tokyo)             ← 都道府県ハブ
[扶養とは](/words/fuyou)                      ← 用語集
[事実婚という選択](/roundtable/jijitsukon-to-iu-sentaku)  ← おしゃべり
```

- リンクテキストには制度名・用語を含める (アンカーテキスト SEO)
- **地域記事から全国制度へのリンクは特に重要** (併給関係の説明で必ず使う)
- 全国記事から地域制度へのリンクは、地域限定であることが分かる書き方にする (例: 「東京都には[児童育成手当](/tokyo/support/11)という独自の制度もあります」)

## 47都道府県への展開

新しい都道府県を追加する手順は `docs/url-structure.md` §3 を参照。コード変更は不要で、DB への登録 (supports + support_prefectures) と記事執筆だけでページが自動生成される。
