import { getSeasonalNoticesForSupport } from '@/lib/seasonal';
import styles from './ArticleSeasonalNotice.module.css';

/* 記事ページの季節ブロック。トップの SeasonalNotice とは出し分けが違う:

     トップ (components/SeasonalNotice.jsx) … いま時期の通知をすべて出す
     記事 (これ)                            … ★その制度の通知だけ★を出す

   ひもづきの根拠は lib/seasonal.js の supportIds のみ。該当が無ければ null を返し、
   セクションごと描画しない (無関係な記事に季節通知を出すとノイズになるため)。

   リンク先は /calendar にする。通知の href はその制度自身の記事を指しているので、
   記事ページで使うと自分自身へのリンクになってしまう。 */

const LINE_ADD_URL = process.env.NEXT_PUBLIC_LINE_ADD_URL;

export default function ArticleSeasonalNotice({ supportId }) {
  const notices = getSeasonalNoticesForSupport(supportId);
  if (notices.length === 0) return null;

  return (
    <aside className={styles.box} aria-label="今の時期の手続きのご案内">
      {notices.map((n) => (
        <div key={n.id} className={styles.item}>
          <p className={styles.head}>
            <span className={styles.period}>{n.period}</span>
            <span className={styles.itemTitle}>{n.title}</span>
          </p>
          <p className={styles.body}>{n.body}</p>
        </div>
      ))}

      <p className={styles.links}>
        <a className={styles.calendarLink} href="/calendar">
          1年の手続きカレンダーを見る <span aria-hidden="true">→</span>
        </a>
        {LINE_ADD_URL && (
          <a
            className={styles.lineLink}
            href={LINE_ADD_URL}
            target="_blank"
            rel="noopener noreferrer"
          >
            この時期のお知らせをLINEで受け取る
          </a>
        )}
      </p>

      <p className={styles.note}>
        提出期限や必要書類は、お住まいの市区町村によって異なる場合があります。
      </p>
    </aside>
  );
}
