import { getSeasonalCalendar, SEASONAL_NOTICES } from '@/lib/seasonal';
import { getLinkableSupports } from '@/lib/supabase';
import { supportHref, supportPrefName } from '@/lib/links';
import LineCta from '@/components/LineCta';
import styles from './calendar.module.css';

export const revalidate = 300;

/* ============================================================
   ひとり親の1年カレンダー  /calendar
   ------------------------------------------------------------
   トップの「今の時期にやること」は “いまの1〜2件” しか見せられないので、
   年間で見通せる独立ページを用意する。記事ページの季節ブロックからもここに送る。

   ★事実ベース厳守★
   - 載せるのは lib/seasonal.js の SEASONAL_NOTICES だけ。
     月を埋めるために推測で項目を足さないこと。項目が無い月は空欄のままでよい
   - 断定するのは全国共通の時期のみ。現況届の提出方法・医療証の更新時期のように
     ★自治体で運用が分かれるもの★はページ冒頭と各月の注記で必ずその旨を書く

   ★リンク★ 各項目から制度記事へ送る。id → URL は lib/links.js の supportHref()
   経由 (全国 /support/{id} / 地域 /{pref}/support/{id})。
   getLinkableSupports() が article_md=NULL の制度を落とすので 404 は出ない。
   ============================================================ */

export const metadata = {
  title: 'ひとり親の1年カレンダー｜現況届・年末調整・確定申告の時期まとめ',
  description:
    'シングルマザー・シングルファーザーの手続きを4月から翌3月まで月ごとにまとめました。児童扶養手当の現況届（毎年8月）、年末調整のひとり親控除、確定申告、入学準備の貸付など、時期が決まった手続きを見落とさないためのカレンダーです。',
  alternates: { canonical: '/calendar' },
};

export default async function CalendarPage() {
  const months = getSeasonalCalendar();

  /* 通知がひもづける制度をまとめて1回で引く。記事本文があるものだけが返る */
  const allIds = [...new Set(SEASONAL_NOTICES.flatMap((n) => n.supportIds ?? []))];
  const supports = await getLinkableSupports(allIds);
  const supportById = new Map(supports.map((s) => [s.id, s]));

  const currentMonth = months.find((m) => m.isCurrent)?.month;

  return (
    <>
      <section className={`hero ${styles.hero}`}>
        <h1>
          ひとり親の<em>1年カレンダー</em>
        </h1>
        <p>
          ひとり親家庭の支援制度には、<strong>時期が決まっている手続き</strong>があります。
          出し忘れると支給が止まってしまうものもあるため、4月から翌3月までの流れをまとめました。
          各月には、<strong>その月に準備や案内の確認が必要になる手続き</strong>を載せています。
        </p>
      </section>

      {/* ★自治体差の但し書きは最初に置く★ */}
      <aside className={styles.caution} aria-label="ご確認のお願い">
        <p className={styles.cautionTitle}>お読みいただく前に</p>
        <ul className={styles.cautionList}>
          <li>
            ここに載せているのは<strong>全国共通の目安</strong>です。
            提出期限・必要書類・受付方法は<strong>お住まいの市区町村によって異なる場合があります</strong>。
          </li>
          <li>
            医療証の更新や、児童扶養手当以外の手当の現況確認は、
            <strong>時期も方法も自治体ごとに違います</strong>。案内が届いたら、その案内に書かれた期限に従ってください。
          </li>
          <li>
            1つの手続きは<strong>複数の月にまたがって表示されます</strong>。
            実際の提出時期は、各項目についている<strong>期間のバッジ</strong>（「毎年8月」など）をご確認ください。
          </li>
          <li>
            掲載していない月は「手続きが無い」という意味ではありません。
            当サイトで解説している制度に、その月の全国共通の手続きが無いというだけです。
          </li>
        </ul>
      </aside>

      <ol className={styles.months}>
        {months.map(({ month, isCurrent, notices }) => (
          <li
            key={month}
            id={`m${month}`}
            className={`${styles.month} ${isCurrent ? styles.monthCurrent : ''}`}
          >
            <div className={styles.monthHead}>
              <span className={styles.monthNum}>
                {month}
                <span className={styles.monthUnit}>月</span>
              </span>
              {isCurrent && <span className={styles.nowBadge}>今月</span>}
            </div>

            <div className={styles.monthBody}>
              {notices.length === 0 ? (
                <p className={styles.empty}>
                  当サイトで解説している制度に、この月の全国共通の手続きはありません。
                </p>
              ) : (
                <ul className={styles.items}>
                  {notices.map((n) => {
                    const linked = (n.supportIds ?? [])
                      .map((id) => supportById.get(id))
                      .filter(Boolean);
                    return (
                      <li key={n.id} className={styles.item}>
                        <p className={styles.itemHead}>
                          <span className={styles.period}>{n.period}</span>
                          <span className={styles.itemTitle}>{n.title}</span>
                        </p>
                        <p className={styles.itemBody}>{n.body}</p>
                        {linked.length > 0 && (
                          <p className={styles.itemLinks}>
                            {linked.map((s) => {
                              const prefName = supportPrefName(s);
                              return (
                                <a key={s.id} className={styles.itemLink} href={supportHref(s)}>
                                  {prefName ? `${prefName}の${s.title}` : s.title}を読む{' '}
                                  <span aria-hidden="true">→</span>
                                </a>
                              );
                            })}
                          </p>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </li>
        ))}
      </ol>

      <p className={styles.footNote}>
        金額や所得の制限は年度ごとに改定されることがあります。
        {currentMonth ? `${currentMonth}月時点の` : ''}最新の内容は、各制度の記事と、
        お住まいの市区町村の窓口でご確認ください。
      </p>

      {/* LINE 導線。LineCta と重ならないよう、ここは「時期のお知らせ」だけに絞る */}
      <LineCta />

      <a href="/" className="back-link">
        ← 制度一覧にもどる
      </a>
    </>
  );
}
