import { notFound } from 'next/navigation';
import { getGlossary, getGlossaryList, getSupportsByIds } from '@/lib/supabase';
import { renderArticle } from '@/lib/markdown';
import LineCta from '@/components/LineCta';

export const revalidate = 300;

export async function generateStaticParams() {
  const list = await getGlossaryList();
  return list.filter((w) => w.has_article).map((w) => ({ slug: w.slug }));
}

export async function generateMetadata({ params }) {
  const { slug } = await params;
  const word = await getGlossary(slug);
  if (!word) return {};
  return {
    // 画面表示は「用語集」。<title> だけは検索語 (基礎知識ワード集) を括弧で併記する
    title: `${word.term}とは？｜用語集（基礎知識ワード集）`,
    description: word.short_def,
  };
}

export default async function WordPage({ params }) {
  const { slug } = await params;
  const word = await getGlossary(slug);
  if (!word || !word.article_md) notFound();

  const { html, faq } = await renderArticle(word.article_md);
  const related = await getSupportsByIds(word.related_support_ids);
  const updated = word.updated_at
    ? new Date(word.updated_at).toLocaleDateString('ja-JP', { year: 'numeric', month: 'long', day: 'numeric' })
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
    <article className="word-page">
      <header className="article-header">
        <p className="word-breadcrumb">
          <a href="/words">用語集</a>
        </p>
        <h1>
          {word.term}
          {word.reading && <span className="word-reading">{word.reading}</span>}
        </h1>
        <div className="article-meta">
          <span className="badge badge-cat">用語集</span>
          {updated && <span className="article-updated">最終更新: {updated}</span>}
        </div>
      </header>

      {word.short_def && (
        <div className="word-def">
          <span className="word-def-label">ひとことで言うと</span>
          <p>{word.short_def}</p>
        </div>
      )}

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

      {related.length > 0 && (
        <section className="word-related">
          <h2>この言葉が出てくる制度</h2>
          <ul className="card-list">
            {related.map((s) => (
              <li key={s.id}>
                <a href={`/support/${s.id}`} className="card">
                  <h3>{s.title}</h3>
                  <p>{s.summary}</p>
                </a>
              </li>
            ))}
          </ul>
        </section>
      )}

      <LineCta />

      <a href="/words" className="back-link">← 用語集にもどる</a>
    </article>
  );
}
