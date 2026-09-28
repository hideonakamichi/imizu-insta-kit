import { notFound } from 'next/navigation';
import { getRoundtable, getRoundtableList, getSupportsByIds, getGlossaryBySlugs } from '@/lib/supabase';
import { renderArticle } from '@/lib/markdown';
import RoundtableCast from '@/components/RoundtableCast';

export const revalidate = 300;

export async function generateStaticParams() {
  const list = await getRoundtableList();
  return list.filter((r) => r.has_article).map((r) => ({ slug: r.slug }));
}

export async function generateMetadata({ params }) {
  const { slug } = await params;
  const rt = await getRoundtable(slug);
  if (!rt) return {};
  return {
    // 画面表示は「おしゃべり」。<title> だけは検索語 (座談会) を括弧で併記する
    title: `${rt.title}｜おしゃべり（座談会）`,
    description: rt.lead,
  };
}

export default async function RoundtablePage({ params }) {
  const { slug } = await params;
  const rt = await getRoundtable(slug);
  if (!rt || !rt.article_md) notFound();

  // おしゃべりは流れで読むものなので Toc は出さない
  const { html, faq } = await renderArticle(rt.article_md);
  const [relatedSupports, relatedWords] = await Promise.all([
    getSupportsByIds(rt.related_support_ids),
    getGlossaryBySlugs(rt.related_glossary_slugs),
  ]);

  const updated = rt.updated_at
    ? new Date(rt.updated_at).toLocaleDateString('ja-JP', { year: 'numeric', month: 'long', day: 'numeric' })
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
    <article className="rt-page">
      <header className="article-header">
        <p className="rt-breadcrumb">
          <a href="/roundtable">おしゃべり</a>
        </p>
        <h1>{rt.title}</h1>
        <div className="article-meta">
          <span className="badge badge-cat">おしゃべり</span>
          {rt.theme && <span className="badge badge-theme">{rt.theme}</span>}
          {updated && <span className="article-updated">最終更新: {updated}</span>}
        </div>
      </header>

      {rt.lead && <p className="rt-lead">{rt.lead}</p>}

      <RoundtableCast participants={rt.participants} />

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

      {relatedSupports.length > 0 && (
        <section className="rt-related">
          <h2>このおしゃべりに出てきた制度</h2>
          <ul className="card-list">
            {relatedSupports.map((s) => (
              <li key={s.id}>
                <a href={`/support/${s.id}`} className="card">
                  <h3>{s.article_title || s.title}</h3>
                  <p>{s.summary}</p>
                </a>
              </li>
            ))}
          </ul>
        </section>
      )}

      {relatedWords.length > 0 && (
        <section className="rt-related">
          <h2>あわせて読みたい言葉</h2>
          <ul className="card-list">
            {relatedWords.map((w) => (
              <li key={w.slug}>
                <a href={`/words/${w.slug}`} className="card word-card">
                  <h3>
                    {w.term}
                    {w.reading && <span className="word-reading">{w.reading}</span>}
                  </h3>
                  <p>{w.short_def}</p>
                </a>
              </li>
            ))}
          </ul>
        </section>
      )}

      <a href="/roundtable" className="back-link">← おしゃべりの一覧にもどる</a>
    </article>
  );
}
