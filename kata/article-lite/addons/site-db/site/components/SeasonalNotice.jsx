import { getSeasonalNotices } from '@/lib/seasonal';
import styles from './SeasonalNotice.module.css';

/* トップページ「今の時期にやること」

   サーバー側で現在日時を判定する (クライアント JS なし)。
   トップページは revalidate = 300 なので、日付が変わっても最大5分で切り替わる。
   月日の判定は必ず Asia/Tokyo。ロジックは lib/seasonal.js を参照。

   LINE の一言は components/LineCta.jsx と同じく NEXT_PUBLIC_LINE_ADD_URL を見て、
   未設定なら描画しない。最下部の LineCta とは訴求を変え、ここは「時期の通知」だけに絞る。 */

const LINE_ADD_URL = process.env.NEXT_PUBLIC_LINE_ADD_URL;

export default function SeasonalNotice() {
  const notices = getSeasonalNotices();
  if (notices.length === 0) return null; // 該当のない時期はセクションごと出さない

  return (
    <section className="seasonal" aria-labelledby="seasonal-title">
      <h2 className="seasonal-title" id="seasonal-title">
        今の時期にやること
      </h2>

      <ul className="seasonal-list">
        {notices.map((n) => (
          <li key={n.id} className="seasonal-item">
            <span className="seasonal-period">{n.period}</span>
            <h3 className="seasonal-item-title">{n.title}</h3>
            <p className="seasonal-body">{n.body}</p>
            <a className="seasonal-link" href={n.href}>
              詳しく見る <span aria-hidden="true">→</span>
            </a>
          </li>
        ))}
      </ul>

      {/* 年間の見通しは /calendar に集約。ここは「いま」だけを出す方針は変えない */}
      <p className={styles.calendarLink}>
        <a href="/calendar">
          ひとり親の1年カレンダーを見る <span aria-hidden="true">→</span>
        </a>
      </p>

      {LINE_ADD_URL && (
        <p className="seasonal-line">
          次の手続きの時期も{' '}
          <a href={LINE_ADD_URL} target="_blank" rel="noopener noreferrer">
            LINEでお知らせします
          </a>
        </p>
      )}

      <p className="seasonal-note">
        提出期限や必要書類は、お住まいの市区町村によって異なる場合があります。
      </p>
    </section>
  );
}
