import { getConcernSupports } from '@/lib/supabase';
import { groupByConcern } from '@/lib/concerns';
import { naturesOf, NATURE_LEGEND } from '@/lib/nature';
import { supportHref, supportPrefName } from '@/lib/links';
import LineCta from '@/components/LineCta';
import styles from './start.module.css';

export const revalidate = 300;

/* ============================================================
   困りごとから探す  /start
   ------------------------------------------------------------
   ★このページの存在理由★
   トップページの分類 (手当 / 助成 / 給付金 / 貸付 / 税制 / 年金 / サービス) は
   行政側の分類で、読者はその言葉では探さない。「水道代が高い」「塾代が
   払えない」という困りごとから引けるようにするのがここ。
   実際、水道料金の減免は「手当でも助成でもない」と思われて長く見落とされていた。

   ★手書きの一覧にしないこと★
   見出し (困りごと) は lib/concerns.js、中身は DB (supports) から生成する。
   制度を1本追加して CONCERN_MAP にひもづければ、このページに自動で載る。

   ★記事がまだ無い制度も出す★
   「そもそも、そういう制度がある」と知らせるのがこのページの半分の仕事なので、
   status='draft' の制度も出す。ただし記事があるように見せてはいけないので、
   リンクにせず「解説を準備中」と明示し、公式サイトへの外部リンクだけを置く。

   ★カテゴリバッジは出さず、性質ラベル (lib/nature.js) を出す★
   「助成」「給付金」は行政の分類で、このページはそれを使わない前提で作った。
   同じ場所に「もらえる」「借りる・返済あり」を出すほうが読者には役に立ち、
   バッジの数も増えない (= 375px でカードが窮屈にならない)。
   カテゴリで探したい人にはトップページがある。
   ============================================================ */

export const metadata = {
  title: '困りごとから探す｜ひとり親家庭が使える支援制度',
  description:
    '「今月の生活費が足りない」「水道代が高い」「塾代が払えない」——困っていることから、ひとり親家庭が使える公的な支援制度を探せます。全国の制度と、お住まいの地域の制度をまとめて確認できます。',
  alternates: { canonical: '/start' },
};

const SCOPE_BADGES = {
  bereaved: { label: '死別のご家庭向け', cls: 'badge-scope-bereaved' },
};

/* 性質ラベル1個。貸付だけ警告色にする (start.module.css) */
function NatureBadge({ nature }) {
  const cls = nature.key === 'loan' ? `${styles.nature} ${styles.natureLoan}` : styles.nature;
  return <span className={`badge ${cls}`}>{nature.label}</span>;
}

/* 記事がある制度 = カード全体がリンク。
   記事がまだ無い制度 = リンクにせず、公式サイトへの外部リンクだけを添える。
   ★この出し分けを崩さないこと★ 記事の無い id を /support/{id} にリンクすると 404 */
function SupportItem({ support }) {
  const prefName = supportPrefName(support);
  const scope = SCOPE_BADGES[support.target_scope];
  /* 最大2個 (性質 + 返済免除)。バッジ全体でも最大4個に収まる */
  const natures = naturesOf(support);
  const meta = (
    <span className="meta">
      {prefName && <span className="badge badge-pref">{prefName}</span>}
      {natures.map((n) => (
        <NatureBadge key={n.key} nature={n} />
      ))}
      {scope && <span className={`badge ${scope.cls}`}>{scope.label}</span>}
      {!support.has_article && <span className="badge badge-pending">解説を準備中</span>}
    </span>
  );

  if (support.has_article) {
    return (
      <li>
        <a href={supportHref(support)} className="card concern-card">
          <div className="card-body">
            <h3>{support.title}</h3>
            {support.summary && <p>{support.summary}</p>}
            {meta}
          </div>
        </a>
      </li>
    );
  }

  return (
    <li>
      <div className="card concern-card concern-card-pending">
        <div className="card-body">
          <h3>{support.title}</h3>
          {support.summary && <p>{support.summary}</p>}
          {meta}
          <p className="concern-pending-note">
            この制度の解説記事はまだありません。いまは公式の案内をご覧ください。
          </p>
          {support.official_url && (
            <a
              className="concern-official-link"
              href={support.official_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              公式サイトで見る
              <span className="concern-official-host">（{hostOf(support.official_url)}）</span>
            </a>
          )}
        </div>
      </div>
    </li>
  );
}

/* 外部リンクであることを、飛ぶ前に分かるようにする (www. は落とす) */
function hostOf(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return '公式サイト';
  }
}

export default async function StartPage() {
  const supports = await getConcernSupports();
  const groups = groupByConcern(supports);
  const pendingCount = supports.filter((s) => !s.has_article).length;

  return (
    <>
      <section className="hero">
        <h1>
          いま困っていることから、<em>使える制度を探す</em>。
        </h1>
        <p>
          制度の名前が分からなくても大丈夫です。「今月の生活費が足りない」「水道代が高い」
          といった困りごとから、ひとり親家庭が使える公的な制度をたどれます。
          ひとつの制度が複数の困りごとに出てくることもあります。
        </p>
      </section>

      <nav className="cat-chips" aria-label="困りごとから探す">
        {groups.map((c) => (
          <a key={c.id} href={`#${c.id}`} className="cat-chip">
            {c.label}
          </a>
        ))}
      </nav>

      {/* ラベルの凡例。★カードより前に置くこと★
          「借りる・返済あり」の意味を知らないままカードを読ませない */}
      <div className={styles.legend}>
        <p className={styles.legendLead}>
          カードに付いているラベルは、その制度が<strong>もらえるお金か、借りるお金か</strong>を表しています。
        </p>
        <ul className={styles.legendList}>
          {NATURE_LEGEND.map((n) => (
            <li key={n.key}>
              <NatureBadge nature={n} />
              <span
                className={`${styles.legendDesc} ${n.key === 'loan' ? styles.legendDescWarn : ''}`}
              >
                {n.desc}
              </span>
            </li>
          ))}
        </ul>
      </div>

      {pendingCount > 0 && (
        <p className="concern-notice">
          「<strong>解説を準備中</strong>」と付いている制度は、当サイトの解説記事がまだありません。
          制度自体は今もありますので、公式の案内へのリンクを添えています。
        </p>
      )}

      {groups.map((c) => (
        <section key={c.id} id={c.id} className="cat-section concern-section">
          <h2 className="cat-title">
            <span className="cat-name">{c.label}</span>
          </h2>
          <p className="concern-lead">{c.lead}</p>
          <ul className="card-list">
            {c.supports.map((s) => (
              <SupportItem key={s.id} support={s} />
            ))}
          </ul>
        </section>
      ))}

      <section className="cat-section concern-outro">
        <h2 className="cat-title">
          <span className="cat-name">見つからなかったときは</span>
        </h2>
        <p>
          ここに載っているのは、当サイトが確認できた制度です。
          このほかにも、お住まいの市区町村が独自に用意している制度があります。
          あてはまりそうなものが見つからないときは、
          <a href="/">全国の制度一覧</a>や、市区町村のひとり親家庭の相談窓口もあわせて確認してください。
        </p>
      </section>

      <LineCta />

      <a href="/" className="back-link">
        ← 制度一覧にもどる
      </a>
    </>
  );
}
