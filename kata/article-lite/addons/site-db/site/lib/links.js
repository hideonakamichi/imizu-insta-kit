/* 制度の正規 URL を組み立てる唯一の場所。

   ルールは .claude/skills/editorial-url-rules / docs/url-structure.md と対応:
     全国制度 (support_prefectures にひもづきなし) … /support/{id}
     地域制度 (support_prefectures にひもづきあり) … /{pref}/support/{id}

   ★地域制度を /support/{id} でリンクすると 308 リダイレクトになる★
   (app/support/[id]/page.jsx の redirectIfRegional)。内部リンクは必ずここを通して、
   最初から正しいパスを出すこと。県 slug はハードコードせず DB の値をそのまま使う。

   引数は lib/supabase.js の getLinkableSupports / getSupportsInCategory /
   getSupportWithPrefecture が返す形 ({ id, prefectures: [{slug, name_ja}] }) を想定。 */

export function supportHref(support) {
  const slug = support?.prefectures?.[0]?.slug;
  return slug ? `/${slug}/support/${support.id}` : `/support/${support.id}`;
}

/* 地域制度なら都道府県名、全国制度なら null。
   「これは地域限定の制度です」とバッジで示すために使う */
export function supportPrefName(support) {
  return support?.prefectures?.[0]?.name_ja ?? null;
}

/* 本文 (article_md) 中の内部リンクから制度 id を出現順に拾う。
   /support/9 と /tokyo/support/11 の両方の書式に対応する。

   ★これが「関連制度」の根拠★ — 推測でひもづけを作らず、
   記事が実際にリンクしている制度だけを関連とみなす。 */
export function extractLinkedSupportIds(markdown) {
  const ids = [];
  const re = /\]\((?:\/[a-z0-9-]+)?\/support\/(\d+)\)/g;
  let m;
  while ((m = re.exec(markdown ?? '')) !== null) {
    const id = Number(m[1]);
    if (Number.isInteger(id) && !ids.includes(id)) ids.push(id);
  }
  return ids;
}
