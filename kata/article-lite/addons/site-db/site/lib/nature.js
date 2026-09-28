/* ============================================================
   制度の「性質」ラベル  —  そのお金は、もらえるのか / 借りるのか
   ------------------------------------------------------------
   ★なぜ必要か★
   「貸付」を給付だと思って申し込み、あとで返済に苦しむ——これがこのサイトで
   いちばん実害の大きい誤解。カード上では制度名と要約しか見えないので、
   「借りるお金かどうか」が一目で分かる必要がある。

   ★カードに出すのは最大2個★
   ラベルは多いほど読まれなくなる。ここで定義するのは5種類だけで、
   1制度に付くのは基本1個、貸付で返済免除がある2制度だけが2個になる。
   「自治体によって異なる」「事前申請が必要」は意図的に作っていない:
     - 自治体差 → 都道府県バッジと見出しのリード文で既に伝えている
     - 事前申請 → ほぼ全制度に付いてしまい、ラベルとして機能しない

   ★原則: category から機械的に導く★
   supports.category (手当/助成/給付金/貸付/税制/年金/サービス) で決まるものは
   手で持たない。制度を1本足したら自動で正しいラベルが付くのが理想。
   category だけでは割れるものだけ OVERRIDE / WAIVER に列挙する。
   ★OVERRIDE を増やすときは、必ず一次情報で確認してから足すこと★
   ============================================================ */

/* label は読者の言葉で。見た目は app/start/start.module.css が持ち、
   key === 'loan' のときだけ警告色のチップにする (色はここに書かない) */
export const NATURE = {
  get: { key: 'get', label: 'もらえる' },
  reduce: { key: 'reduce', label: '支払いが減る' },
  loan: { key: 'loan', label: '借りる・返済あり' },
  waiver: { key: 'waiver', label: '条件つきで返済免除' },
  /* 「サービスを利用」ではなく「お金ではない支援」。公営住宅の優遇抽せんや
     母子生活支援施設まで含むので、「利用する」より「お金ではない」が正しい */
  service: { key: 'service', label: 'お金ではない支援' },
};

/* 凡例の並び順 (= 読者に説明する順)。desc は凡例だけで使う一言 */
export const NATURE_LEGEND = [
  { ...NATURE.get, desc: '返さなくてよいお金' },
  { ...NATURE.reduce, desc: '払う額そのものが安くなる' },
  { ...NATURE.loan, desc: 'あとで返すお金。給付と間違えないでください' },
  { ...NATURE.waiver, desc: '条件を満たして申請すると、返さなくてよくなる' },
  { ...NATURE.service, desc: '現金ではなく、人手・住まい・相談などの支援' },
];

/* category → 性質。ここに無い category の制度はラベルが付かない (落ちても壊れない) */
const BY_CATEGORY = {
  手当: 'get',
  給付金: 'get',
  助成: 'reduce',
  税制: 'reduce',
  貸付: 'loan',
  /* 年金は「遺族基礎年金 (もらえる)」が主。保険料免除は下の OVERRIDE で外す */
  年金: 'get',
  サービス: 'service',
};

/* ★配布版の注記★
   この下の OVERRIDE / WAIVER に出てくる program_code は、配布元の元データのものです
   (supabase/seed.sql のサンプル 3 件とは一致しません)。
   ★消さずに残しているのは、「推測で分類するな」というルールが
     具体例つきでないと伝わらないためです。★ 自分のデータに合わせて入れ替えてください。
   知らない program_code が来ても、この仕組みはラベルを付けないだけで壊れません。 */

/* category だけでは割れる制度。★推測で足さない★ */
const OVERRIDE = {
  /* category=年金 だが、もらう制度ではなく保険料を払わなくてよくなる制度 */
  'kokumin-nenkin-menjo': 'reduce',
  /* category=助成 だが、学用品費・修学旅行費などが保護者に支給される */
  'shugaku-enjo': 'get',
  /* category=サービス だが、実態は定期券代の割引 */
  'jr-tokuteisha-teiki': 'reduce',
};

/* 返済免除の仕組みがある貸付。
   ★一次情報 (各制度の記事) で確認済み★
     - jutaku-shien-shikin      : 1年間の就業継続などで償還免除
     - tokyo-jukensei-challenge : 高校・大学等へ入学し、償還免除を申請すると免除
   ★母子父子寡婦福祉資金 (boshi-fushi-kafu-shikin) は免除の仕組みが無い★
   「教育系の貸付は免除がある」という思い込みで足さないこと。
   生活福祉資金 (seikatsu-fukushi-shikin) も同様に一般的な免除は無い。 */
const WAIVER = new Set(['jutaku-shien-shikin', 'tokyo-jukensei-challenge']);

/* 1制度あたり最大2個 (基本の性質 + 返済免除) を返す。
   支援オブジェクトは category と program_code さえあればよい */
export function naturesOf(support) {
  if (!support) return [];
  const key = OVERRIDE[support.program_code] ?? BY_CATEGORY[support.category];
  const out = [];
  if (key && NATURE[key]) out.push(NATURE[key]);
  if (WAIVER.has(support.program_code)) out.push(NATURE.waiver);
  return out;
}
