import Script from 'next/script';
/* ★GA4 の測定 ID はコードに直接書かず、環境変数 NEXT_PUBLIC_GA_ID から読む。★
   (GA4 = Google Analytics 4。サイトの閲覧数などを測るサービス)
   未設定なら計測タグを一切出力しない = 配布物に他人の測定 ID が残らない。 */
import { GA_ID } from '@/lib/siteConfig';

// 本番ドメインでのみ計測する。プレビュー / ローカルのアクセスが混ざると
// 数字が読めなくなるので、VERCEL_ENV=production 以外では何も出力しない。
const ENABLED = process.env.NEXT_PUBLIC_VERCEL_ENV
  ? process.env.NEXT_PUBLIC_VERCEL_ENV === 'production'
  : process.env.NODE_ENV === 'production';

export default function Analytics() {
  if (!ENABLED || !GA_ID) return null;

  return (
    <>
      <Script
        src={`https://www.googletagmanager.com/gtag/js?id=${GA_ID}`}
        strategy="afterInteractive"
      />
      <Script id="ga4-init" strategy="afterInteractive">
        {`
          window.dataLayer = window.dataLayer || [];
          function gtag(){dataLayer.push(arguments);}
          gtag('js', new Date());
          gtag('config', '${GA_ID}');
        `}
      </Script>
    </>
  );
}
