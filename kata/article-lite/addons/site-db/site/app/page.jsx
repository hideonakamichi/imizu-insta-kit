import { getSupportList, getPrefectureList } from '@/lib/supabase';
import { amountLabel } from '@/lib/amount';
import LineCta from '@/components/LineCta';
import SeasonalNotice from '@/components/SeasonalNotice';
/* 画像置き場のベース URL は環境変数から (lib/siteConfig.js) */
import { STORAGE_BASE } from '@/lib/siteConfig';

export const revalidate = 300;

const CATEGORY_ORDER = ['手当', '助成', '給付金', '貸付', '税制', '年金', 'サービス'];

/* カテゴリ見出しに添える一言説明。
   warn: 誤解が実害につながる語だけを強調する (現状は「貸付」の「返済が必要」のみ)。
   text の先頭が warn と一致する前提で分割する。 */
const CATEGORY_DESC = {
  手当: { text: '定期的にもらえるお金' },
  助成: { text: '費用の一部を負担してもらう' },
  給付金: { text: '目的に応じてもらえるお金' },
  貸付: { text: '返済が必要なお金', warn: '返済が必要' },
  税制: { text: '税金が安くなる' },
  // 「年金」には、もらう制度 (遺族基礎年金) と払う額が減る制度 (国民年金保険料の免除) の
  // 両方が入る。死別だけの分類ではないので、どちらも含む言い方にしている
  年金: { text: '年金でもらえるお金・保険料の免除' },
  // サービス: 名称だけで自明なため説明なし。未定義のカテゴリは自動的にカテゴリ名のみ表示される
};

/* 区切りの「—」は CSS の ::before で描く (読み上げに乗せないため) */
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

const THUMB_BASE = `${STORAGE_BASE}/thumbs`;

const SCOPE_BADGES = {
  all_families: { label: 'すべての子育て家庭', cls: 'badge-scope-all' },
  bereaved: { label: '死別のご家庭向け', cls: 'badge-scope-bereaved' },
};

export default async function HomePage() {
  const supports = await getSupportList();
  /* 制度が登録されている都道府県 (記事が0本の県も「準備中」として出す)。
     47都道府県のうち何県出るかは DB 次第 — ここに県名をハードコードしないこと */
  const prefectures = await getPrefectureList({ requireArticle: false });
  const byCategory = new Map();
  for (const s of supports) {
    const key = s.category || 'その他';
    if (!byCategory.has(key)) byCategory.set(key, []);
    byCategory.get(key).push(s);
  }
  const categories = [...CATEGORY_ORDER.filter((c) => byCategory.has(c)), ...[...byCategory.keys()].filter((c) => !CATEGORY_ORDER.includes(c))];

  return (
    <>
      <section className="hero">
        <h1>
          ひとり親家庭が使える支援制度を、<em>ぜんぶ、わかりやすく</em>。
        </h1>
        <p>
          手当・医療費助成・給付金・貸付・税金まで。みさきさん（シングルマザー）の素朴な疑問に、社労士の藤井先生が答える対話形式で、金額も申請方法も具体的に解説します。
        </p>
      </section>

      {/* ★制度名を知らない読者の入口★
          下のカテゴリ分類 (手当 / 助成 / …) は行政側の分類で、読者は
          「水道代が高い」「塾代が払えない」で探す。その受け皿が /start。
          解説がまだ無い制度も向こうには載っているので、ここで先に見せる */}
      <a href="/start" className="start-entry">
        <span className="start-entry-label">困りごとから探す</span>
        <span className="start-entry-text">
          「今月の生活費が足りない」「水道代が高い」など、
          <strong>困っていることから</strong>使える制度をたどれます。
        </span>
        <span className="start-entry-go">探してみる →</span>
      </a>

      {/* 時期が決まった手続きの案内。該当する時期でなければ何も描画されない */}
      <SeasonalNotice />

      {/* ファーストビューのカテゴリチップ。id は日本語を避けて連番 (cat-1…) */}
      <nav className="cat-chips" aria-label="カテゴリから探す">
        {categories.map((cat, i) => (
          <a key={cat} href={`#cat-${i + 1}`} className="cat-chip">
            {cat}
          </a>
        ))}
      </nav>

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
                  <a href={`/support/${s.id}`} className="card">
                    <div className="card-thumb">
                      {/* alt="" = 装飾画像。直後の h3 に制度名があるため。読み込み失敗時は
                          ブラウザが img を潰し、下地の淡いピンクだけが残る (フォールバック) */}
                      <img src={`${THUMB_BASE}/support-${s.id}.png`} alt="" loading="lazy" decoding="async" width="640" height="360" />
                    </div>
                    <div className="card-body">
                    <h3>{s.title}</h3>
                    <p>{s.summary}</p>
                    <span className="meta">
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

      {/* 地域制度への入口。カテゴリ一覧のあと・LINE CTA の前に置く */}
      {prefectures.length > 0 && (
        <section className="cat-section area-section">
          <h2 className="cat-title">
            <span className="cat-name">お住まいの地域の制度</span>
            <span className="cat-desc">自治体だけの手当・助成</span>
          </h2>
          <p className="area-lead">
            上の全国の制度に加えて、都道府県や市区町村が独自に用意している制度があります。
            全国の制度と<strong>併用できる</strong>ものがほとんどなので、お住まいの地域もあわせて確認してください。
          </p>
          <ul className="area-list">
            {prefectures.map((p) => (
              <li key={p.slug}>
                <a href={`/${p.slug}`} className="area-link">
                  <span className="area-link-name">{p.name_ja}の制度</span>
                  <span className="area-link-count">
                    {p.article_count > 0 ? `${p.article_count}件の解説` : '準備中'}
                  </span>
                </a>
              </li>
            ))}
          </ul>
          <p className="area-note">対応地域は順次増やしています。</p>
        </section>
      )}

      <LineCta />
    </>
  );
}
