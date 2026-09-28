import { notFound } from 'next/navigation';
import { getPrefecture, getPrefectureList, getPrefectureSupports } from '@/lib/supabase';
import { amountLabel } from '@/lib/amount';
import LineCta from '@/components/LineCta';
/* 画像置き場のベース URL は環境変数から (lib/siteConfig.js) */
import { STORAGE_BASE } from '@/lib/siteConfig';

export const revalidate = 300;

/* ============================================================
   都道府県ハブページ  /{pref}   (例: /tokyo)
   ------------------------------------------------------------
   ★ルート衝突について★
   /about /words /roundtable /characters /privacy /disclaimer /support …
   といった静的ルートは Next.js App Router が [pref] より優先して解決するため、
   このファイルには入ってこない。逆に prefectures テーブルに無い slug
   (/foo など) はここに落ちてくるので、必ず notFound() を返すこと。

   ★47都道府県への自動展開★
   県名・slug はハードコードしない。DB に制度を足して support_prefectures に
   ひもづければ、このページは自動で生えてくる。手順は docs/url-structure.md。
   ============================================================ */

const CATEGORY_ORDER = ['手当', '助成', '給付金', '貸付', '税制', '年金', 'サービス'];

const CATEGORY_DESC = {
  手当: { text: '定期的にもらえるお金' },
  助成: { text: '費用の一部を負担してもらう' },
  給付金: { text: '目的に応じてもらえるお金' },
  貸付: { text: '返済が必要なお金', warn: '返済が必要' },
  税制: { text: '税金が安くなる' },
  年金: { text: '死別のときに受け取れるお金' },
};

const THUMB_BASE = `${STORAGE_BASE}/thumbs`;

const SCOPE_BADGES = {
  all_families: { label: 'すべての子育て家庭', cls: 'badge-scope-all' },
  bereaved: { label: '死別のご家庭向け', cls: 'badge-scope-bereaved' },
};

function CategoryDesc({ cat }) {
  const d = CATEGORY_DESC[cat];
  if (!d) return null;
  const hasWarn = d.warn && d.text.startsWith(d.warn);
  return (
    <span className="cat-desc">
      {hasWarn ? (
        <>
          <em className="cat-desc-warn">{d.warn}</em>
          {d.text.slice(d.warn.length)}
        </>
      ) : (
        d.text
      )}
    </span>
  );
}

/* 記事がまだ0本の県もページ自体は出す (「準備中」表示)。
   制度が1件もひもづいていない県は存在しないものとして 404 にする */
export async function generateStaticParams() {
  const prefs = await getPrefectureList({ requireArticle: false });
  return prefs.map((p) => ({ pref: p.slug }));
}

async function loadPrefecture(slug) {
  const pref = await getPrefecture(slug);
  if (!pref) return null;
  const listed = await getPrefectureList({ requireArticle: false });
  return listed.some((p) => p.slug === pref.slug) ? pref : null;
}

export async function generateMetadata({ params }) {
  const { pref: slug } = await params;
  const pref = await loadPrefecture(slug);
  if (!pref) return {};
  const name = pref.name_ja;
  return {
    title: `${name}のひとり親支援制度｜シングルマザーが使える手当・助成`,
    description: `${name}にお住まいのひとり親家庭（シングルマザー・シングルファーザー）が使える、${name}独自の手当・医療費助成・給付金・貸付をまとめました。児童扶養手当などの全国の制度と併用できます。`,
    alternates: { canonical: `/${pref.slug}` },
  };
}

export default async function PrefecturePage({ params }) {
  const { pref: slug } = await params;
  const pref = await loadPrefecture(slug);
  if (!pref) notFound();

  const name = pref.name_ja;
  const all = await getPrefectureSupports(pref.slug, { requireArticle: false });
  const published = all.filter((s) => s.has_article);
  const pending = all.filter((s) => !s.has_article);

  const byCategory = new Map();
  for (const s of published) {
    const key = s.category || 'その他';
    if (!byCategory.has(key)) byCategory.set(key, []);
    byCategory.get(key).push(s);
  }
  const categories = [
    ...CATEGORY_ORDER.filter((c) => byCategory.has(c)),
    ...[...byCategory.keys()].filter((c) => !CATEGORY_ORDER.includes(c)),
  ];

  return (
    <>
      <section className="hero pref-hero">
        <p className="pref-eyebrow">
          <span className="badge badge-pref">{name}</span>
        </p>
        <h1>
          {name}の<em>ひとり親支援制度</em>
        </h1>
        <p>
          {name}が独自に用意している手当・医療費助成・給付金などをまとめました。
          これらは児童扶養手当のような<strong>全国の制度と併用できる</strong>ものがほとんどです。
          「全国の制度＋{name}の制度」の両方を確認するのが、受け取りもれを防ぐいちばんの近道です。
        </p>
      </section>

      {categories.map((cat, i) => (
        <section key={cat} id={`cat-${i + 1}`} className="cat-section">
          <h2 className="cat-title">
            <span className="cat-name">{cat}</span>
            <CategoryDesc cat={cat} />
          </h2>
          <ul className="card-list">
            {byCategory.get(cat).map((s) => {
              const scope = SCOPE_BADGES[s.target_scope];
              const amount = amountLabel(s);
              return (
                <li key={s.id}>
                  <a href={`/${pref.slug}/support/${s.id}`} className="card">
                    <div className="card-thumb">
                      {/* alt="" = 装飾画像。直後の h3 に制度名がある */}
                      <img
                        src={`${THUMB_BASE}/support-${s.id}.png`}
                        alt=""
                        loading="lazy"
                        decoding="async"
                        width="640"
                        height="360"
                      />
                    </div>
                    <div className="card-body">
                      <h3>{s.title}</h3>
                      <p>{s.summary}</p>
                      <span className="meta">
                        <span className="badge badge-pref">{name}</span>
                        <span className="badge badge-cat">{cat}</span>
                        {scope && <span className={`badge ${scope.cls}`}>{scope.label}</span>}
                        {amount && <span className="badge badge-amount">{amount}</span>}
                      </span>
                    </div>
                  </a>
                </li>
              );
            })}
          </ul>
        </section>
      ))}

      {/* 執筆前の制度も名前だけ出しておく (何が使えるのかは先に伝わる) */}
      {pending.length > 0 && (
        <section className="cat-section">
          <h2 className="cat-title">
            <span className="cat-name">解説を準備中の制度</span>
            <span className="cat-desc">くわしい記事はまもなく公開します</span>
          </h2>
          <ul className="card-list">
            {pending.map((s) => (
              <li key={s.id}>
                <div className="card word-card-pending">
                  <div className="card-body">
                    <h3>{s.title}</h3>
                    {s.summary && <p>{s.summary}</p>}
                    <span className="meta">
                      <span className="badge badge-pending">解説を準備中</span>
                      {s.category && <span className="badge badge-cat">{s.category}</span>}
                    </span>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {all.length === 0 && (
        <p className="words-empty">{name}の制度は現在準備中です。もうしばらくお待ちください。</p>
      )}

      {/* ★全国制度への導線★ 地域制度だけを見て終わらせないための必須ブロック */}
      <section className="pref-nation">
        <h2>全国の制度も、あわせて確認してください</h2>
        <p>
          児童扶養手当・ひとり親家庭等医療費助成・就学援助などは、住んでいる場所に関係なく全国で使える制度です。
          {name}の制度と<strong>どちらか一方しか選べない、ということはありません</strong>。
          条件を満たせば両方受け取れるので、まずは全国の制度から確認するのがおすすめです。
        </p>
        <a href="/" className="pref-nation-link">
          全国の制度を見る →
        </a>
      </section>

      <LineCta />

      <a href="/" className="back-link">
        ← 全国の制度一覧にもどる
      </a>
    </>
  );
}
