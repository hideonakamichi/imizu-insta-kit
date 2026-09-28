import { getGlossaryList } from '@/lib/supabase';
import { groupByKanaRow } from '@/lib/kana';
import styles from './words.module.css';

export const revalidate = 300;

export const metadata = {
  // 画面上の呼称は「用語集」に統一。<title> だけは検索語 (基礎知識ワード集) を括弧で併記する
  title: '用語集（基礎知識ワード集）｜扶養・控除・所得と収入のちがいをやさしく',
  description:
    '扶養・控除・所得と収入のちがい・課税と非課税・世帯など、手当や助成の説明でよく出てくる言葉を、シングルマザー・シングルファーザー向けにやさしく解説する用語集（基礎知識ワード集）です。ふりがな付きのあいうえお索引から引けます。',
};

const LEVELS = [
  { key: 'L1', label: '生活の基本語', note: 'まずここから。手当や税金の話に必ず出てくる言葉です。' },
  { key: 'L2', label: '制度でよく出る語', note: '申請書や案内文で見かける、少しだけ専門的な言葉です。' },
  { key: 'L3', label: '手続き語', note: '窓口や書類のやりとりで使われる言葉です。' },
];

/* 行見出し（あ／か／さ…）を出すかどうかの分かれ目。
   語数が少ないと「1行に1語」ばかりになって見出しのほうが目立ってしまうので、
   ある程度たまってから出す。現在 8 語なので見出しあり（か・さ・は の3行に収まる）。 */
const ROW_LABEL_MIN_WORDS = 6;

/* 索引のチップ1個。リンク可否（has_article）で a / span を出し分ける。
   ふりがなは <ruby> で漢字の上に出す。★漢字が読めない人が引けること★ が索引の目的。 */
function WordChip({ word, className }) {
  const inner = (
    <ruby className={styles.chipTerm}>
      {word.term}
      {word.reading ? <rt>{word.reading}</rt> : null}
    </ruby>
  );
  if (!word.has_article) {
    // article_md が NULL の語は /words/{slug} が 404 になるのでリンクにしない
    return (
      <span className={`${styles.chip} ${styles.chipPending} ${className || ''}`} title="解説を準備中">
        {inner}
      </span>
    );
  }
  return (
    <a href={`/words/${word.slug}`} className={`${styles.chip} ${className || ''}`}>
      {inner}
    </a>
  );
}

export default async function WordsPage() {
  const words = await getGlossaryList();

  // ★索引は sort_order でも term の漢字でもなく reading（読み）で並べる★
  const kanaRows = groupByKanaRow(words);
  const showRowLabels = words.length >= ROW_LABEL_MIN_WORDS;

  const byLevel = new Map();
  for (const w of words) {
    const key = w.level || 'その他';
    if (!byLevel.has(key)) byLevel.set(key, []);
    byLevel.get(key).push(w);
  }
  const groups = [
    ...LEVELS.filter((l) => byLevel.has(l.key)),
    ...[...byLevel.keys()]
      .filter((k) => !LEVELS.some((l) => l.key === k))
      .map((k) => ({ key: k, label: k, note: null })),
  ];

  return (
    <>
      {/* ★ここに説明文は置かない★
          用語集に来る人は調べたい言葉が決まっている。使い方の説明も導入文も邪魔になるので、
          h1 の直下はすぐ索引。「ふりがなで引ける」ことは索引そのものを見れば分かる。
          読み物としての説明はページ下部（.about）に移した。 */}
      <div className={styles.head}>
        <h1 className={styles.title}>用語集</h1>
      </div>

      {words.length === 0 ? (
        <p className="words-empty">用語集は現在準備中です。もうしばらくお待ちください。</p>
      ) : (
        <>
          <nav className={styles.index} aria-labelledby="words-index-label">
            <h2 id="words-index-label" className={styles.indexLabel}>
              あいうえお索引（全{words.length}語）
            </h2>
            <ul className={styles.rows}>
              {kanaRows.map((row) => (
                <li
                  key={row.label}
                  className={`${styles.row} ${showRowLabels ? '' : styles.rowFlat}`}
                >
                  {showRowLabels && (
                    <span className={styles.rowLabel} aria-hidden="true">
                      {row.label}
                    </span>
                  )}
                  <ul className={styles.chips}>
                    {row.items.map((w) => (
                      <li key={w.slug}>
                        <WordChip word={w} />
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          </nav>

          {/* ── ここから下は「どれから読めばいいか分からない人」向けの棚。
                索引＝目的の語を引く導線 / レベル別＝はじめての人が読む順を決める導線。
                役割が違うので両方残す（レベル別だけが short_def を出せる、という利点もある）。 */}
          {groups.map((g) => (
            <section key={g.key} className="cat-section">
              <h2 className="cat-title">{g.label}</h2>
              {g.note && <p className="words-level-note">{g.note}</p>}
              <ul className="card-list">
                {byLevel.get(g.key).map((w) =>
                  w.has_article ? (
                    <li key={w.slug}>
                      <a href={`/words/${w.slug}`} className="card word-card">
                        <h3>
                          {w.term}
                          {w.reading && <span className="word-reading">{w.reading}</span>}
                        </h3>
                        <p>{w.short_def}</p>
                      </a>
                    </li>
                  ) : (
                    <li key={w.slug}>
                      <div className="card word-card word-card-pending">
                        <h3>
                          {w.term}
                          {w.reading && <span className="word-reading">{w.reading}</span>}
                        </h3>
                        <p>{w.short_def}</p>
                        <span className="meta">
                          <span className="badge badge-pending">解説を準備中</span>
                        </span>
                      </div>
                    </li>
                  )
                )}
              </ul>
            </section>
          ))}
        </>
      )}

      {/* 元ヒーローの説明文はここ（下部）に置いた。読み物としての導入は索引の邪魔になるため */}
      <section className={styles.about}>
        <h2 className={styles.aboutTitle}>この用語集について</h2>
        <p>
          「扶養って結局なに？」「所得と収入ってちがうの？」——手当や助成の案内でつまずきやすい言葉を、ひとつずつかみくだいて説明しています。
        </p>
      </section>

      {/* ▼ 将来の索引について（今回は未実装のメモ）
          語数が 30〜50 語に増えると、この全語一覧は1画面に収まらなくなる。そのとき必要なのは:
            1) 行ジャンプ（あ か さ た な… を押して該当行へ）＋ 語数の多い行の折りたたみ
            2) 読み・表記の両方に当たる絞り込み入力（reading と term を対象に前方一致）
            3) ★「どの記事で出てきた言葉か」から引く第2の入口★
               glossary.related_support_ids に制度 id が入っているので、
               supports 側（/support/{id}）とつき合わせて「この制度の説明に出てくる言葉」の
               束を作れる。読めない漢字に出会うのは必ず「どこかを読んでいるとき」なので、
               あいうえお索引より現実的な入口になりうる。
          今回はデータ取得を getGlossaryList のまま（related_support_ids は未取得）にしてあるが、
          select に related_support_ids を足すだけで上記 3) に進める構造にしてある。 */}

      <a href="/" className="back-link">← 制度一覧にもどる</a>
    </>
  );
}
