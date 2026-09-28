/* 金額の見せ方をカテゴリ別に決める。
   「最大35万円」とだけ書くと、ひとり親控除 (税制) は "税金が35万円安くなる" と
   読まれてしまう。実際は所得から差し引く額で、軽減されるのは控除額 × 税率。
   貸付も同様に「もらえるお金」と誤読されうるので借入である旨を出す。
   カード一覧と記事冒頭のサマリーで表記がずれないよう、ここに一本化する。 */

function man(amountMax) {
  const v = amountMax / 10000;
  return Number.isInteger(v)
    ? v.toLocaleString()
    : v.toLocaleString(undefined, { maximumFractionDigits: 1 });
}

/* 一覧カードのバッジ用 (短い) */
export function amountLabel(support) {
  if (!support?.amount_max) return null;
  const n = man(support.amount_max);
  switch (support.category) {
    case '税制':
      return `所得から${n}万円控除`;
    case '貸付':
      return `貸付上限${n}万円`;
    default:
      return `最大${n}万円`;
  }
}

/* 記事冒頭サマリー用。label と value を分けて返す */
export function amountRow(support) {
  if (!support?.amount_max) return null;
  const yen = `${support.amount_max.toLocaleString()}円`;
  switch (support.category) {
    case '税制':
      return {
        label: '控除額',
        value: `所得から ${yen}`,
        note: '税金がこの額だけ安くなるのではなく、控除額 × 税率が実際の軽減額です',
      };
    case '貸付':
      return {
        label: '貸付上限',
        value: `${yen} まで`,
        note: '返済が必要な貸付です。上限額で、資金の種類や状況によって変わります',
      };
    default:
      return {
        label: '金額',
        value: `最大 ${yen}`,
        // amount_max は「加算込みの真の上限額」を入れる運用 (supabase/schema.sql)
        note: '加算などを含めた上限額です',
      };
  }
}
