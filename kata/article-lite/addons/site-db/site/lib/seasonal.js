/* 季節のやること (トップページ「今の時期にやること」)

   制度には「時期が決まった手続き」があり、出し忘れると実害が出る
   (例: 児童扶養手当の現況届を8月に出さないと11月分以降の支給が止まる)。
   年間カレンダーは README.md「LINE 連携」 の「2. 年間配信カレンダー」と対応させている。
   カレンダーを直すときは両方を必ず揃えること。

   設計メモ:
   - データは SEASONAL_NOTICES 配列に閉じ込め、判定は getSeasonalNotices() 系だけが行う。
     将来 Supabase のテーブルに移すときは、この配列を fetch 結果に差し替えるだけで済む
     (レコードの形 = { id, period, title, body, href, supportIds, start, end } をそのまま列にする)。
   - 期間は「月をまたぐ」ので 月 だけでは判定できない。start / end を {month, day} で持つ。
   - end < start のものは年をまたぐ期間として扱う (例: 12/11 → 2/29)。

   ★supportIds について★
   トップページは「いま時期のもの」を無条件に出すが、記事ページ
   (components/ArticleSeasonalNotice.jsx) は「その制度の通知」だけを出す。
   その判定に使うのが supportIds。無関係な記事に季節通知を出すとノイズになるので、
   ★その制度の記事本文に、その時期の手続きが実際に書かれているものだけ★を入れること。

   いま入れていない例と、その理由 (推測でひもづけを増やさないこと):
   - 児童手当 (id=2) を genkyo-todoke に入れない
     … 現況届は 6月 で、しかも令和4年6月分以降は原則提出不要 (記事本文どおり)。
       「毎年8月」の通知を出すと誤情報になる
   - ひとり親家庭等医療費助成 (id=3 / 12)・児童育成手当 (id=11) を入れない
     … 年1回の現況確認はあるが、★時期・方法が自治体ごとに異なる★ため
       全国共通の「毎年8月」として断定できない
   - nendo-kawari を 手当・給付金 全般に広げない
     … 年度ごとの改定が記事で確認できているのは児童扶養手当 (id=1)

   文言の方針 (YMYL):
   - 「あなたは対象です」等の断定はしない。「〜が届いたら」「〜の方は」と条件を添える
   - ここで制度を説明し切らず、必ず記事 (/support/N) に送る
*/

export const SEASONAL_NOTICES = [
  {
    id: 'genkyo-todoke',
    period: '毎年8月',
    title: '児童扶養手当の現況届の時期です',
    body: '受給中の方は毎年8月に提出が必要です。出し忘れると11月分以降の支給が止まります。',
    href: '/support/1',
    // 児童扶養手当の記事に「毎年8月に現況届」「未提出だと11月分以降差し止め」と明記がある
    supportIds: [1],
    start: { month: 7, day: 20 },
    end: { month: 9, day: 30 },
  },
  {
    id: 'nenmatsu-chosei',
    period: '年末調整の時期',
    title: '年末調整で「ひとり親控除」を忘れずに',
    body: '勤務先に出す書類で申告できます。要件に当てはまる方は所得税が最大35万円控除されます。',
    href: '/support/9',
    supportIds: [9],
    start: { month: 10, day: 1 },
    end: { month: 12, day: 10 },
  },
  {
    id: 'shugaku-shitaku',
    period: '入学・進学の準備期',
    title: '入学・進学の準備費用は早めに',
    body: '就学支度資金などの貸付（返済が必要）があります。申請から入金まで日数がかかります。',
    href: '/support/6',
    // 就学支度資金は母子父子寡婦福祉資金貸付金 (id=6) の12種類のうちの1つ
    supportIds: [6],
    // 年をまたぐ期間。2月末までなので閏年も拾えるよう 2/29 を終端にしている
    start: { month: 12, day: 11 },
    end: { month: 2, day: 29 },
  },
  {
    id: 'kakutei-shinkoku',
    period: '2〜3月',
    title: '確定申告の時期です',
    body: '年末調整で出し忘れたひとり親控除は、確定申告で申告することができます。',
    href: '/support/9',
    supportIds: [9],
    start: { month: 2, day: 1 },
    end: { month: 3, day: 15 },
  },
  {
    id: 'nendo-kawari',
    period: '年度替わり',
    title: '年度替わりで金額が変わることがあります',
    body: '手当の金額や所得の制限は、年度ごとに改定されることがあります。',
    href: '/support/1',
    supportIds: [1],
    start: { month: 4, day: 1 },
    end: { month: 6, day: 30 },
  },
];

/* 各月1日までの通算日数 (平年)。並び順を決めるための概算にしか使わないので閏日は無視する */
const CUM_DAYS = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];

function dayOfYear({ month, day }) {
  return CUM_DAYS[month - 1] + day;
}

/* 月日だけの比較用キー。7月25日 → 725 */
function key({ month, day }) {
  return month * 100 + day;
}

/* ★Vercel のサーバーは UTC で動くため、必ず Asia/Tokyo に変換してから月日を取る。
   UTC のまま判定すると、日本時間の 0:00〜9:00 が前日として扱われる。 */
export function getTokyoMonthDay(date = new Date()) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Tokyo',
    month: 'numeric',
    day: 'numeric',
  }).formatToParts(date);
  const get = (type) => Number(parts.find((p) => p.type === type).value);
  return { month: get('month'), day: get('day') };
}

/* today が start〜end の期間内か。end < start の場合は年をまたぐ期間として扱う */
function isInPeriod(today, notice) {
  const t = key(today);
  const s = key(notice.start);
  const e = key(notice.end);
  return s <= e ? t >= s && t <= e : t >= s || t <= e;
}

/* 終了日までの残り日数 (概算)。年をまたぐぶんは 365 を足して正の値にする */
function daysUntilEnd(today, notice) {
  const diff = dayOfYear(notice.end) - dayOfYear(today);
  return diff < 0 ? diff + 365 : diff;
}

/**
 * 現在 (日本時間) に該当する季節の案内を返す。
 * 該当が複数ある場合は「終了日が近い順」= 期限が近いものを優先し、最大 limit 件。
 * 該当なしなら空配列を返す (呼び出し側でセクションごと出さないこと)。
 *
 * @param {Date} date  判定に使う日時。省略時は現在時刻
 * @param {number} limit  最大表示件数
 * @returns {Array<object>} SEASONAL_NOTICES の要素の配列
 */
export function getSeasonalNotices(date = new Date(), limit = 2) {
  const today = getTokyoMonthDay(date);
  return SEASONAL_NOTICES.filter((n) => isInPeriod(today, n))
    .sort((a, b) => daysUntilEnd(today, a) - daysUntilEnd(today, b))
    .slice(0, limit);
}

/**
 * 制度の記事ページ用。★その制度にひもづく通知★のうち、いまが期間内のものだけを返す。
 * ひもづきは SEASONAL_NOTICES の supportIds が唯一の根拠 (推測でひもづけない)。
 * 該当なしなら空配列 = 記事ページには何も出さない。
 *
 * @param {number} supportId  制度 id
 * @param {Date} date  判定に使う日時。省略時は現在時刻
 * @param {number} limit  最大表示件数
 */
export function getSeasonalNoticesForSupport(supportId, date = new Date(), limit = 2) {
  const id = Number(supportId);
  if (!Number.isInteger(id)) return [];
  const today = getTokyoMonthDay(date);
  return SEASONAL_NOTICES.filter((n) => (n.supportIds ?? []).includes(id) && isInPeriod(today, n))
    .sort((a, b) => daysUntilEnd(today, a) - daysUntilEnd(today, b))
    .slice(0, limit);
}

/* 年度の並び (4月始まり → 翌3月)。/calendar の表示順 */
export const FISCAL_MONTH_ORDER = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3];

/* その月に通知の期間がかかっているか。start.month〜end.month を月単位で判定する
   (年をまたぐものは end.month < start.month になる) */
function coversMonth(notice, month) {
  const s = notice.start.month;
  const e = notice.end.month;
  return s <= e ? month >= s && month <= e : month >= s || month <= e;
}

/**
 * /calendar 用。4月〜翌3月の12か月を、その月にかかる通知つきで返す。
 *
 * ★事実ベース★ ここで返すのは SEASONAL_NOTICES にあるものだけ。
 * 空の月を埋めるために推測で項目を足さないこと (空なら空のまま返す)。
 *
 * @param {Date} date  「今月」の判定に使う日時 (Asia/Tokyo)
 * @returns {Array<{month:number, isCurrent:boolean, notices:Array<object>}>}
 */
export function getSeasonalCalendar(date = new Date()) {
  const { month: currentMonth } = getTokyoMonthDay(date);
  return FISCAL_MONTH_ORDER.map((month) => ({
    month,
    isCurrent: month === currentMonth,
    notices: SEASONAL_NOTICES.filter((n) => coversMonth(n, month)),
  }));
}
