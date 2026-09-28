// Supabase REST fetch (サーバーサイド専用 — service_role key はクライアントに出さないこと)
const BASE = process.env.NEXT_PUBLIC_SUPABASE_URL;
const KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

/* ★環境変数が無いときに分かりやすく落とす★
   これが無いと「Failed to parse URL from undefined/rest/v1/...」という
   原因の分からないエラーになる (セットアップ時に必ず一度は踏むため、明示的に案内する) */
function assertEnv() {
  if (!BASE || !KEY) {
    throw new Error(
      [
        'Supabase の環境変数が設定されていません。',
        '',
        '  1. プロジェクト直下で:  cp .env.example .env.local',
        '  2. .env.local の NEXT_PUBLIC_SUPABASE_URL と SUPABASE_SERVICE_ROLE_KEY を埋める',
        '  3. サイト側にもコピー:  cp .env.local site/.env.local',
        '',
        '値は Supabase の Project Settings → API から取得します',
        '(service_role キーのほう。anon キーではありません)。',
      ].join('\n')
    );
  }
}

async function sbFetch(path, revalidate = 300) {
  assertEnv();
  const res = await fetch(`${BASE}/rest/v1/${path}`, {
    headers: {
      apikey: KEY,
      Authorization: `Bearer ${KEY}`,
    },
    next: { revalidate },
  });
  if (!res.ok) throw new Error(`Supabase ${res.status}: ${await res.text()}`);
  return res.json();
}

/* カード表示に使う最小セット / 記事ページで使うフルセット。
   都道府県ページでも同じ形を使い回すので定数にしておく */
const SUPPORT_CARD_FIELDS = 'id,title,article_title,summary,category,target_scope,amount_max,amount_note';
const SUPPORT_FULL_FIELDS = `${SUPPORT_CARD_FIELDS},support_rate,organizer,official_url,article_md,updated_at`;

/* 全国制度だけ (is_nationwide が未設定の行は全国扱いにする)。
   地域制度 (東京都など) はトップ・/support/{id}・sitemap には出さず、
   /{pref} と /{pref}/support/{id} 側で扱う */
const NATIONWIDE_FILTER = 'or=(is_nationwide.is.null,is_nationwide.eq.true)';

export async function getSupportList() {
  return sbFetch(
    `supports?status=eq.active&article_md=not.is.null&${NATIONWIDE_FILTER}&select=${SUPPORT_CARD_FIELDS}&order=id`
  );
}

export async function getSupport(id) {
  const rows = await sbFetch(
    `supports?id=eq.${encodeURIComponent(id)}&select=${SUPPORT_FULL_FIELDS}`
  );
  return rows[0] ?? null;
}

// glossary (用語集 = /words) はテーブル未作成でもページを落とさない
async function sbFetchSafe(path, revalidate = 300) {
  try {
    return await sbFetch(path, revalidate);
  } catch (e) {
    console.warn(`[supabase] fetch failed (空配列で継続): ${path} — ${e.message}`);
    return [];
  }
}

export async function getGlossaryList() {
  const rows = await sbFetchSafe(
    'glossary?status=eq.active&select=id,slug,term,reading,short_def,level,sort_order&order=sort_order,id'
  );
  // 本文が書かれている語だけリンクを張りたいので、別クエリで slug 一覧を取る
  const ready = await sbFetchSafe('glossary?status=eq.active&article_md=not.is.null&select=slug');
  const readySlugs = new Set(ready.map((r) => r.slug));
  return rows.map((r) => ({ ...r, has_article: readySlugs.has(r.slug) }));
}

export async function getGlossary(slug) {
  const rows = await sbFetchSafe(
    `glossary?slug=eq.${encodeURIComponent(slug)}&select=id,slug,term,reading,short_def,level,article_md,related_support_ids,updated_at`
  );
  return rows[0] ?? null;
}

// roundtables (おしゃべり = /roundtable) もテーブル未作成でページを落とさない
export async function getRoundtableList() {
  const rows = await sbFetchSafe(
    'roundtables?status=eq.active&select=id,slug,title,theme,lead,participants,sort_order,published_at&order=sort_order,id'
  );
  // 本文が書かれている回だけリンクを張りたいので、別クエリで slug 一覧を取る
  const ready = await sbFetchSafe('roundtables?status=eq.active&article_md=not.is.null&select=slug');
  const readySlugs = new Set(ready.map((r) => r.slug));
  return rows.map((r) => ({ ...r, has_article: readySlugs.has(r.slug) }));
}

export async function getRoundtable(slug) {
  const rows = await sbFetchSafe(
    `roundtables?slug=eq.${encodeURIComponent(slug)}&select=id,slug,title,theme,lead,participants,article_md,related_support_ids,related_glossary_slugs,published_at,updated_at`
  );
  return rows[0] ?? null;
}

export async function getGlossaryBySlugs(slugs) {
  if (!slugs || slugs.length === 0) return [];
  const list = slugs
    .filter((s) => typeof s === 'string' && s.length > 0)
    .map((s) => encodeURIComponent(s))
    .join(',');
  if (!list) return [];
  return sbFetchSafe(
    `glossary?slug=in.(${list})&status=eq.active&article_md=not.is.null&select=slug,term,reading,short_def`
  );
}

/* ============================================================
   都道府県 (地域制度) — /{pref} と /{pref}/support/{id}
   ------------------------------------------------------------
   47都道府県への自動展開が前提の設計。
   ★都道府県名も slug も一切ハードコードしないこと★
   すべて prefectures / support_prefectures テーブルから引く。
   新しい県を足す手順は docs/url-structure.md を参照。
   ============================================================ */

const PREF_FIELDS = 'id,slug,name_ja,region';

/* 本文が書き上がっている制度の id 集合。
   article_md は巨大なので「あるかないか」だけを別クエリで取る (glossary と同じ手) */
async function getArticleReadySupportIds() {
  const rows = await sbFetchSafe('supports?status=eq.active&article_md=not.is.null&select=id');
  return new Set(rows.map((r) => r.id));
}

export async function getPrefecture(slug) {
  if (!slug || typeof slug !== 'string') return null;
  const rows = await sbFetchSafe(`prefectures?slug=eq.${encodeURIComponent(slug)}&select=${PREF_FIELDS}`);
  return rows[0] ?? null;
}

/* 制度が1本以上ひもづく都道府県だけを返す (47件を全部返さない)。
     requireArticle: true  … 記事本文がある県のみ。トップの導線 / sitemap 用 (既定)
     requireArticle: false … 制度は登録済みだが記事がまだの県も含む。
                             ハブページの 404 判定と generateStaticParams 用
   support_count / article_count を添えるので、呼び出し側で「準備中」を出し分けられる */
export async function getPrefectureList({ requireArticle = true } = {}) {
  const rows = await sbFetchSafe(
    `prefectures?select=${PREF_FIELDS},support_prefectures!inner(support_id)&order=id`
  );
  const readyIds = await getArticleReadySupportIds();
  return rows
    .map(({ support_prefectures, ...pref }) => {
      const ids = (support_prefectures ?? []).map((r) => r.support_id);
      return {
        ...pref,
        support_count: ids.length,
        article_count: ids.filter((id) => readyIds.has(id)).length,
      };
    })
    .filter((p) => (requireArticle ? p.article_count > 0 : p.support_count > 0));
}

/* その都道府県の制度一覧。既定は記事本文があるものだけ。
   requireArticle:false なら執筆前の制度も has_article:false 付きで返す (ハブの「準備中」表示用) */
export async function getPrefectureSupports(prefSlug, { requireArticle = true } = {}) {
  if (!prefSlug || typeof prefSlug !== 'string') return [];
  const rows = await sbFetchSafe(
    `supports?status=eq.active&select=${SUPPORT_CARD_FIELDS},support_prefectures!inner(prefectures!inner(slug))` +
      `&support_prefectures.prefectures.slug=eq.${encodeURIComponent(prefSlug)}&order=id`
  );
  const readyIds = await getArticleReadySupportIds();
  const list = rows.map(({ support_prefectures, ...s }) => ({ ...s, has_article: readyIds.has(s.id) }));
  return requireArticle ? list.filter((s) => s.has_article) : list;
}

/* 制度1件 + ひもづく都道府県。
   /{pref}/support/{id} で「その制度が本当にその県のものか」を検証するために使う */
export async function getSupportWithPrefecture(id) {
  const rows = await sbFetchSafe(
    `supports?id=eq.${encodeURIComponent(id)}&select=${SUPPORT_FULL_FIELDS},support_prefectures(prefectures(${PREF_FIELDS}))`
  );
  const row = rows[0];
  if (!row) return null;
  const { support_prefectures, ...support } = row;
  return {
    ...support,
    prefectures: (support_prefectures ?? []).map((r) => r.prefectures).filter(Boolean),
  };
}

/* 記事本文がある (pref slug × support id) の組み合わせ。
   generateStaticParams と sitemap の両方がこれを使うので、URL がずれない */
export async function getPrefectureSupportPairs() {
  const rows = await sbFetchSafe(
    'support_prefectures?select=support_id,prefectures!inner(slug),supports!inner(id)' +
      '&supports.status=eq.active&supports.article_md=not.is.null&order=support_id'
  );
  return rows
    .map((r) => ({ pref: r.prefectures?.slug, id: r.support_id }))
    .filter((r) => r.pref && r.id != null);
}

export async function getSupportsByIds(ids) {
  if (!ids || ids.length === 0) return [];
  const list = ids.filter((n) => Number.isInteger(n)).join(',');
  if (!list) return [];
  return sbFetchSafe(`supports?id=in.(${list})&article_md=not.is.null&select=id,title,article_title,summary`);
}

/* ============================================================
   「次に読む」(components/NextRead.jsx) 用の関連取得
   ------------------------------------------------------------
   ★ここで返すのは「記事本文がある制度」だけ★
   article_md が NULL の制度はページが 404 になるので、必ず
   article_md=not.is.null で絞ってから返すこと。呼び出し側で
   実在チェックをやり直さなくて済むようにするのがこの層の役目。

   都道府県のひもづきも一緒に返す。URL の作り分け (全国 /support/{id} と
   地域 /{pref}/support/{id}) は lib/links.js の supportHref() が担当する。
   ============================================================ */

const SUPPORT_LINK_SELECT =
  `${SUPPORT_CARD_FIELDS},is_nationwide,support_prefectures(prefectures(slug,name_ja))`;

function flattenPrefectures(rows) {
  return (rows ?? []).map(({ support_prefectures, ...s }) => ({
    ...s,
    prefectures: (support_prefectures ?? []).map((r) => r.prefectures).filter(Boolean),
  }));
}

/* 指定した id の制度を、記事本文があるものだけ返す。
   ★引数 ids の並び順を保つ★ (本文で先に触れられた制度ほど関連が強いため) */
export async function getLinkableSupports(ids) {
  const list = [...new Set((ids ?? []).filter((n) => Number.isInteger(n) && n > 0))];
  if (list.length === 0) return [];
  const rows = await sbFetchSafe(
    `supports?id=in.(${list.join(',')})&status=eq.active&article_md=not.is.null&select=${SUPPORT_LINK_SELECT}`
  );
  const found = new Map(flattenPrefectures(rows).map((s) => [s.id, s]));
  return list.map((id) => found.get(id)).filter(Boolean);
}

/* 同じカテゴリ (手当 / 助成 / 給付金 / 貸付 / 税制 / 年金 / サービス) の制度。
   excludeIds には「その記事自身」と「すでに別枠で出した制度」を渡して重複を防ぐ */
export async function getSupportsInCategory(category, { excludeIds = [] } = {}) {
  if (!category || typeof category !== 'string') return [];
  const rows = await sbFetchSafe(
    `supports?status=eq.active&article_md=not.is.null&category=eq.${encodeURIComponent(category)}` +
      `&select=${SUPPORT_LINK_SELECT}&order=id`
  );
  const skip = new Set(excludeIds);
  return flattenPrefectures(rows).filter((s) => !skip.has(s.id));
}

/* ============================================================
   「困りごとから探す」(/start) 用
   ------------------------------------------------------------
   ★このサイトで唯一 status=draft を含めて取るクエリ★
   /start は「まだ記事が無い制度も、存在だけは読者に知らせる」ための
   ページなので、執筆前 (article_md IS NULL / status='draft') の行も返す。
   代わりに has_article を必ず添えるので、呼び出し側で
     has_article: true  … 記事へリンクしてよい
     has_article: false … リンクせず「解説を準備中」+ 公式サイトへの外部リンク
   と出し分けること。★false の行を記事リンクにしないこと (404 になる)★

   トップ・/{pref}・記事ページ・sitemap は従来どおり status=eq.active かつ
   article_md=not.is.null で絞っているので、draft はそちらには出ない。
   ============================================================ */
const CONCERN_FIELDS =
  `${SUPPORT_CARD_FIELDS},program_code,official_url,status,is_nationwide,` +
  'support_prefectures(prefectures(slug,name_ja))';

export async function getConcernSupports() {
  const rows = await sbFetchSafe(
    `supports?status=in.(active,draft)&select=${CONCERN_FIELDS}&order=id`
  );
  const readyIds = await getArticleReadySupportIds();
  return flattenPrefectures(rows).map((s) => ({ ...s, has_article: readyIds.has(s.id) }));
}

/* その制度にひもづく用語 (glossary.related_support_ids に id が入っているもの)。
   ひもづけは用語側が持っているデータなので、こちらで推測しない。
   cs.{N} は PostgREST の配列 contains 演算子 ({} は URL エンコードして渡す) */
export async function getGlossaryForSupport(supportId) {
  if (!Number.isInteger(supportId)) return [];
  return sbFetchSafe(
    `glossary?status=eq.active&article_md=not.is.null&related_support_ids=cs.%7B${supportId}%7D` +
      '&select=slug,term,reading,short_def&order=sort_order,id'
  );
}
