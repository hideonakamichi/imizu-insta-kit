/* LINE 公式アカウントへの導線。

   NEXT_PUBLIC_LINE_ADD_URL (友だち追加 URL) が未設定なら null を返し、何も描画しない。
   → アカウント未開設のあいだは、サイト上に LINE の痕跡が一切出ない。
   ★配布版では LINE 連携のドキュメントは同梱していません★
   友だち追加 URL を .env.local の NEXT_PUBLIC_LINE_ADD_URL に入れれば表示されます。

   訴求の方針 (YMYL 配慮):
   - 訴えるのは「申請の時期を忘れないこと」。もらえる/損している といった断定・煽りは書かない
   - 個別の受給可否は判断できないので、必ず窓口確認への導線を添える */

import { LINE_ADD_URL } from '@/lib/siteConfig';

export default function LineCta() {
  if (!LINE_ADD_URL) return null;

  return (
    <aside className="line-cta" aria-label="LINE公式アカウントのご案内">
      <p className="line-cta-title">申請の時期を、LINEでお知らせします</p>
      <p className="line-cta-body">
        児童扶養手当の現況届（毎年8月）のように、出し忘れると支給が止まってしまう手続きがあります。
        そうした<strong>申請・手続きの時期</strong>と、新しい制度の解説記事を公開したときのお知らせをお届けします。
      </p>
      <a
        className="line-cta-btn"
        href={LINE_ADD_URL}
        target="_blank"
        rel="noopener noreferrer"
      >
        <span className="line-cta-btn-icon" aria-hidden="true">LINE</span>
        <span>友だち追加する</span>
      </a>
      <p className="line-cta-note">
        登録・配信は無料です。いつでも友だち解除で配信を停止できます。
      </p>
    </aside>
  );
}
