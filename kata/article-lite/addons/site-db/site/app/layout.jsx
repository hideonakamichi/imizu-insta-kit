import './globals.css';
import Analytics from '@/components/Analytics';
/* ★サイト名・タグライン・OGP 画像はすべて lib/siteConfig.js 経由で
   環境変数 (.env.local) から読みます。ここに直接書かないこと。★ */
import {
  SITE_URL,
  SITE_NAME,
  SITE_NAME_PRE,
  SITE_NAME_MAIN,
  SITE_TAGLINE,
  SITE_DESCRIPTION,
  LOGO_MARK,
  OGP_IMAGE,
} from '@/lib/siteConfig';

export const metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: SITE_TAGLINE ? `${SITE_NAME}｜${SITE_TAGLINE}` : SITE_NAME,
    template: `%s｜${SITE_NAME}`,
  },
  description: SITE_DESCRIPTION,
  openGraph: {
    type: 'website',
    siteName: SITE_NAME,
    locale: 'ja_JP',
    // SNS でシェアされたときのサムネイル。透過 PNG のままだと背景を
    // 黒く描く環境があるので、白地に合成した不透明画像を置くこと。
    // ★配布版には画像を同梱していません。site/public/brand/README.md 参照★
    ...(OGP_IMAGE ? { images: [{ url: OGP_IMAGE, width: 1200, height: 630 }] } : {}),
  },
  twitter: { card: 'summary_large_image' },
};

export default function RootLayout({ children }) {
  return (
    <html lang="ja">
      <body>
        <header className="site-header">
          <div className="inner">
            <a href="/" className="site-logo">
              {/* ★文字はロゴ画像に含めず、下のライブテキストで出している★
                  画像に焼くと Google がサイト名を読めず、スマホで2段に組み替えることも、
                  表記を直すこともできなくなるため。マークだけを画像にしている。
                  表示は 44px (狭い端末は 34px)。Retina 用に 192px を読み込んで縮小表示する。
                  実サイズは globals.css の .site-logo-mark で決めている。
                  ★配布版はダミーの SVG。site/public/brand/README.md 参照★ */}
              <img
                className="site-logo-mark"
                src={LOGO_MARK}
                alt=""
                width="44"
                height="44"
                aria-hidden="true"
              />
              <span className="site-logo-text">
                {SITE_NAME_PRE ? <span className="site-logo-pre">{SITE_NAME_PRE}</span> : null}
                <span className="site-logo-main">
                  {SITE_NAME_MAIN}<span className="dot">.</span>
                </span>
              </span>
            </a>
            {SITE_TAGLINE ? <span className="site-tag">{SITE_TAGLINE}</span> : null}
            {/* 「当サイトについて」はフッターのみに置く。
                「困りごとから探す」は制度名を知らない読者の入口なので、
                ヘッダーの先頭に置き、他の2項目と区別できるよう強調する */}
            <nav className="site-nav">
              {/* 狭い端末では「困りごと」だけに縮める。ヘッダーは 375px で
                  ロゴ + ナビが1行に収まるかどうかのぎりぎりの幅しかないため */}
              <a href="/start" className="site-nav-primary">
                <span className="site-nav-long">困りごとから探す</span>
                <span className="site-nav-short">困りごと</span>
              </a>
              <a href="/words">用語集</a>
              <a href="/roundtable">おしゃべり</a>
            </nav>
          </div>
        </header>
        <main>{children}</main>
        <footer className="site-footer">
          <div className="inner">
            <p>
              本サイトは、ひとり親家庭向けの公的支援制度に関する情報を、公的機関の公表情報に基づいてわかりやすく紹介するものです。
              制度の内容は改正や自治体の運用によって変わることがあります。実際の手続きの前に、必ずお住まいの市区町村の窓口や公式サイトで最新情報をご確認ください。
            </p>
            <nav className="site-footer-nav">
              <a href="/about">当サイトについて</a>
              <a href="/words">用語集</a>
              <a href="/roundtable">おしゃべり</a>
              <a href="/privacy">プライバシーポリシー</a>
              <a href="/disclaimer">免責事項</a>
            </nav>
          </div>
        </footer>
        <Analytics />
      </body>
    </html>
  );
}
