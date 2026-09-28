import { notFound } from 'next/navigation';
import { getPrefecture, getSupportWithPrefecture, getPrefectureSupportPairs } from '@/lib/supabase';
import { renderArticle, readingMinutes } from '@/lib/markdown';
import ArticleSeasonalNotice from '@/components/ArticleSeasonalNotice';
import CastIntro from '@/components/CastIntro';
import LineCta from '@/components/LineCta';
import NextRead from '@/components/NextRead';
import SummaryCard from '@/components/SummaryCard';
import Toc from '@/components/Toc';
import TocFab from '@/components/TocFab';

export const revalidate = 300;

/* ============================================================
   都道府県の制度記事  /{pref}/support/{id}   (例: /tokyo/support/11)
   ------------------------------------------------------------
   全国制度の /support/{id} とほぼ同じ構成。違いは
     ・ページ上部に都道府県バッジ
     ・下部に「{県}の制度一覧」と「全国の制度」の両方への導線
     ・title に県名を入れる
   ★検証★ support_prefectures にひもづきが無い (pref, id) の組み合わせは
   必ず notFound()。/osaka/support/11 のような URL を成立させないこと。
   ============================================================ */

export async function generateStaticParams() {
  const pairs = await getPrefectureSupportPairs();
  return pairs.map((p) => ({ pref: p.pref, id: String(p.id) }));
}

/* pref と id の整合性チェックをここに集約する。
   戻り値 null = 404 相当 */
async function loadPrefSupport(prefSlug, id) {
  const pref = await getPrefecture(prefSlug);
  if (!pref) return null;
  const support = await getSupportWithPrefecture(id);
  if (!support || !support.article_md) return null;
  // ★その制度が本当にこの都道府県のものか★
  if (!support.prefectures.some((p) => p.slug === pref.slug)) return null;
  return { pref, support };
}

export async function generateMetadata({ params }) {
  const { pref: prefSlug, id } = await params;
  const found = await loadPrefSupport(prefSlug, id);
  if (!found) return {};
  const { pref, support } = found;
  const base = support.article_title || support.title;
  return {
    title: base.includes(pref.name_ja) ? base : `${pref.name_ja}の${base}`,
    description: support.summary,
    alternates: { canonical: `/${pref.slug}/support/${support.id}` },
  };
}

const SCOPE_BADGES = {
  all_families: { label: 'すべての子育て家庭が対象', cls: 'badge-scope-all' },
  bereaved: { label: '死別のご家庭向け', cls: 'badge-scope-bereaved' },
};

export default async function PrefectureSupportPage({ params }) {
  const { pref: prefSlug, id } = await params;
  const found = await loadPrefSupport(prefSlug, id);
  if (!found) notFound();
  const { pref, support } = found;

  /* 全国制度の記事と同じく、見出しイラストとキャラアイコンを出す */
  const { html, faq, headings } = await renderArticle(support.article_md, { visuals: true });
  const minutes = readingMinutes(support.article_md);
  const scope = SCOPE_BADGES[support.target_scope];
  const updated = support.updated_at
    ? new Date(support.updated_at).toLocaleDateString('ja-JP', { year: 'numeric', month: 'long', day: 'numeric' })
    : null;

  const faqJsonLd =
    faq.length > 0
      ? {
          '@context': 'https://schema.org',
          '@type': 'FAQPage',
          mainEntity: faq.map((f) => ({
            '@type': 'Question',
            name: f.q ?? f.question,
            acceptedAnswer: { '@type': 'Answer', text: f.a ?? f.answer },
          })),
        }
      : null;

  return (
    <article>
      {/* パンくず。どこの制度の話なのかを本文より先に見せる */}
      <nav className="pref-breadcrumb" aria-label="現在地">
        <a href="/">全国の制度</a>
        <span aria-hidden="true">›</span>
        <a href={`/${pref.slug}`}>{pref.name_ja}の制度</a>
      </nav>

      <header className="article-header">
        <p className="pref-eyebrow">
          <span className="badge badge-pref">{pref.name_ja}の制度</span>
        </p>
        <h1>{support.article_title || support.title}</h1>
        <div className="article-meta">
          <span className="badge badge-cat">{support.category}</span>
          {scope && <span className={`badge ${scope.cls}`}>{scope.label}</span>}
          {updated && <span className="article-updated">最終更新: {updated}</span>}
        </div>
        <p className="pref-scope-note">
          この制度は<strong>{pref.name_ja}にお住まいの方</strong>が対象です。全国共通の制度と併用できます。
        </p>
      </header>

      {/* 本文を読む前に「自分ごとか」を30秒で判断できるようにする。中身はすべて DB の既存カラム */}
      <SummaryCard support={support} minutes={minutes} prefName={pref.name_ja} />

      {/* この制度に「いま時期の手続き」があるときだけ出る。無関係な記事には描画されない */}
      <ArticleSeasonalNotice supportId={support.id} />

      {headings.length >= 2 && <Toc headings={headings} />}

      <CastIntro />

      <div className="article" dangerouslySetInnerHTML={{ __html: html }} />

      {faq.length > 0 && (
        <section className="faq-section">
          <h2>よくある質問</h2>
          {faq.map((f, i) => (
            <details key={i} className="faq-item">
              <summary>{f.q ?? f.question}</summary>
              <div className="faq-a">{f.a ?? f.answer}</div>
            </details>
          ))}
        </section>
      )}

      {faqJsonLd && (
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }} />
      )}

      {/* 記事を行き止まりにしないための回遊ブロック。LineCta の手前に置く。
          地域制度と全国制度の両方への導線 (旧 .pref-nextlinks) も
          NextRead の「ほかの制度をさがす」に統合したので、ここでは重複させない */}
      <NextRead support={support} prefSlug={pref.slug} prefName={pref.name_ja} />

      <LineCta />

      {/* スマホ専用の追従ボタン。目次が無い記事では出さない */}
      {headings.length >= 2 && <TocFab />}
    </article>
  );
}
