/* ============================================================
   「当サイトについて」ページ — ★配布版はすべてダミーです★

   YMYL (お金・健康など、人生に影響する分野) のサイトでは、
   「誰が書いているのか」「どういう方針で書いているのか」を明示することが
   検索評価でも読者の信頼でも効いてきます。このページはその型だけを残し、
   中身は placeholder に差し替えてあります。

   運営者名・会社名・サイト名は lib/siteConfig.js 経由で環境変数から読みます
   (.env.local の NEXT_PUBLIC_OPERATOR_ORG / NEXT_PUBLIC_OPERATOR_NAME / NEXT_PUBLIC_SITE_NAME)。
   ★このファイルに実名を直接書かないでください。★

   自分のサイトを立ち上げるときは、以下を書いてください:
     - 運営者 (会社名 / 個人名) … .env.local に設定
     - なぜこのサイトをつくったのか (一次体験があるなら、それが一番強い) … 下の本文
     - 編集方針 (どこを一次ソースにしているか)
     - 免責 (個別の適用は保証しない / 窓口で確認を)
   ============================================================ */

import { SITE_NAME, OPERATOR_ORG, OPERATOR_NAME } from '@/lib/siteConfig';

export const metadata = {
  title: '当サイトについて',
  description: `${SITE_NAME}の運営者と、サイトをつくった理由、編集方針についてご案内します。`,
};

export default function AboutPage() {
  return (
    <article className="about-page">
      <header className="article-header">
        <h1>当サイトについて</h1>
      </header>

      <p className="about-catch">（ここにサイトのキャッチコピーが入ります）</p>

      <p className="about-lead">
        「{SITE_NAME}」は、ひとり親家庭が使える手当・助成・給付金の情報を、
        できるだけ分かりやすい言葉でお届けするサイトです。
        （※配布版のサンプル文です）
      </p>

      {/* ---------- 運営者 ---------- */}
      <section className="about-section">
        <h2>運営者</h2>
        <div className="about-owner">
          <dl className="about-owner-facts">
            <dt>運営会社</dt>
            <dd>{OPERATOR_ORG}</dd>
            <dt>代表者</dt>
            <dd>{OPERATOR_NAME}</dd>
          </dl>
        </div>
      </section>

      {/* ---------- つくった理由 ---------- */}
      <section className="about-section">
        <h2>このサイトをつくった理由</h2>
        <div className="about-message">
          <p>
            ★ここに運営者自身の言葉で「なぜこのテーマを扱うのか」を書いてください。★
          </p>
          <p>
            扱うテーマの当事者である、実務で関わってきた、といった
            <strong>一次体験</strong>があるなら、それを具体的に書くのが最も効きます。
            AI に書かせた一般論をここに置くと、ページの意味がなくなります。
          </p>
          <p>
            運営に AI を使っている場合は、それを隠さずに書き、
            <strong>どういう検証工程を通してから公開しているか</strong>をセットで示してください。
            （このキットで言えば「執筆エージェント → 査読エージェント → 機械検出」の三段構え）
          </p>
          <p className="about-signature">
            {OPERATOR_ORG} {OPERATOR_NAME}
          </p>
        </div>
      </section>

      {/* ---------- ★ 最重要: 確認を促すセクション ---------- */}
      <section className="box pointbox about-check">
        <div className="box-title">申請の前に、必ずご確認ください</div>
        <p>
          このサイトの情報は、国や自治体が公表している内容をもとに、
          できるだけ分かりやすくお伝えすることを心がけています。
        </p>
        <p>
          ただ、制度は改正されますし、同じ制度でもお住まいの市区町村によって金額や条件が違うことがあります。
        </p>
        <p>
          だからこそ、実際に申請される前には、
          <strong>必ずお住まいの市区町村の窓口や公式サイトで最新の情報をご確認ください。</strong>
        </p>
        <p>
          このサイトは「そんな制度があるんだ」と知っていただくための入口です。
          窓口に行くときの持ち物や、聞くことのメモ代わりに使っていただけたら嬉しいです。
        </p>
      </section>

      {/* ---------- 編集方針 ---------- */}
      <section className="about-section">
        <h2>編集方針</h2>
        <ul className="about-policy">
          <li>
            公的機関（省庁・自治体等）の公表情報を一次ソースとして確認しています
          </li>
          <li>金額や要件には、いつ時点の情報かを明記しています</li>
          <li>自治体によって異なる制度は、その旨を明示しています</li>
          <li>特定の生き方や選択を推奨・否定しません</li>
        </ul>
      </section>

      {/* ---------- 免責事項 ---------- */}
      <section className="about-section">
        <h2>免責事項</h2>
        <ul className="about-policy">
          <li>
            掲載情報の正確性には努めていますが、個別の状況への適用を保証するものではありません
          </li>
          <li>実際の判断は、必ず公式の窓口でご確認ください</li>
        </ul>
        <p className="about-disclaimer-link">
          情報の正確性、記事の品質管理の体制、広告の取り扱いなどについては、
          <a href="/disclaimer">免責事項</a>のページで詳しくご説明しています。
        </p>
      </section>

      <a href="/" className="back-link">← 制度一覧にもどる</a>
    </article>
  );
}
