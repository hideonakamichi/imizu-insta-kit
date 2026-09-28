import { notFound, permanentRedirect } from 'next/navigation';
import { getSupport, getSupportList, getSupportWithPrefecture } from '@/lib/supabase';
import { renderArticle, readingMinutes } from '@/lib/markdown';
import ArticleSeasonalNotice from '@/components/ArticleSeasonalNotice';
import CastIntro from '@/components/CastIntro';
import LineCta from '@/components/LineCta';
import NextRead from '@/components/NextRead';
import SummaryCard from '@/components/SummaryCard';
import Toc from '@/components/Toc';
import TocFab from '@/components/TocFab';

export const revalidate = 300;

export async function generateStaticParams() {
  const list = await getSupportList();
  return list.map((s) => ({ id: String(s.id) }));
}

export async function generateMetadata({ params }) {
  const { id } = await params;
  const support = await getSupport(id);
  if (!support) return {};
  return {
    title: support.article_title || support.title,
    description: support.summary,
  };
}

const SCOPE_BADGES = {
  all_families: { label: 'すべての子育て家庭が対象', cls: 'badge-scope-all' },
  bereaved: { label: '死別のご家庭向け', cls: 'badge-scope-bereaved' },
};

/* このパスは全国制度専用。地域制度 (support_prefectures にひもづきがある制度) は
   /{pref}/support/{id} が正規 URL なので、同じ記事が2つの URL で見えないよう
   308 で寄せる。generateStaticParams も全国制度しか返さない (getSupportList) */
async function redirectIfRegional(id) {
  const withPref = await getSupportWithPrefecture(id);
  const pref = withPref?.prefectures?.[0];
  if (pref?.slug) permanentRedirect(`/${pref.slug}/support/${id}`);
}

export default async function SupportPage({ params }) {
  const { id } = await params;
  const support = await getSupport(id);
  if (!support || !support.article_md) notFound();
  await redirectIfRegional(id);

  /* 見出しイラストと吹き出しのキャラアイコンを出す (制度記事のみ)。
     素材と割り当てルールは docs/article-visuals-spec.md / lib/visuals.js */
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
      <header className="article-header">
        <h1>{support.article_title || support.title}</h1>
        <div className="article-meta">
          <span className="badge badge-cat">{support.category}</span>
          {scope && <span className={`badge ${scope.cls}`}>{scope.label}</span>}
          {updated && <span className="article-updated">最終更新: {updated}</span>}
        </div>
      </header>

      {/* 本文を読む前に「自分ごとか」を30秒で判断できるようにする。中身はすべて DB の既存カラム */}
      <SummaryCard support={support} minutes={minutes} />

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

      {/* 記事を行き止まりにしないための回遊ブロック。LineCta の手前に置く */}
      <NextRead support={support} />

      <LineCta />

      <a href="/" className="back-link">← 制度一覧にもどる</a>

      {/* スマホ専用の追従ボタン。目次が無い記事では出さない */}
      {headings.length >= 2 && <TocFab />}
    </article>
  );
}
