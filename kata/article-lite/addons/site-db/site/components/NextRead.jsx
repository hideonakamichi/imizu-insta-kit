import {
  getLinkableSupports,
  getSupportsInCategory,
  getGlossaryForSupport,
  getPrefectureList,
} from '@/lib/supabase';
import { supportHref, supportPrefName, extractLinkedSupportIds } from '@/lib/links';
import styles from './NextRead.module.css';

/* 記事末尾の「次に読む」。検索から1記事だけ見て離脱するのを防ぐための回遊ブロック。

   ★推測で関連を作らないこと★ ここに出すのは DB から機械的に決まるものだけ:
     1. 関連制度   … article_md が実際にリンクしている制度 (出現順)
     2. 同じカテゴリ… supports.category が一致する制度
     3. 用語        … glossary.related_support_ids にその制度 id が入っている語
     4. 地域導線    … prefectures / support_prefectures

   ★リンク先の実在★ 1〜3 はすべて lib/supabase.js 側で
   status=active かつ article_md=not.is.null に絞ってから返している。
   article_md が NULL の制度・用語はページが 404 になるため、ここには出てこない。

   ★URL★ 全国 /support/{id} と地域 /{pref}/support/{id} の作り分けは
   lib/links.js の supportHref() に集約。県 slug はハードコードしない。 */

const MAX_RELATED = 4;
const MAX_SAME_CATEGORY = 3;
const MAX_TERMS = 6;

function SupportCard({ support }) {
  const prefName = supportPrefName(support);
  return (
    <li>
      <a className={styles.card} href={supportHref(support)}>
        <span className={styles.cardBadges}>
          {/* 地域限定の制度だと分かるように、県名バッジを制度名より先に出す */}
          {prefName && <span className={`${styles.badge} ${styles.badgePref}`}>{prefName}</span>}
          {support.category && (
            <span className={`${styles.badge} ${styles.badgeCat}`}>{support.category}</span>
          )}
        </span>
        <span className={styles.cardTitle}>{support.title}</span>
        {support.summary && <span className={styles.cardSummary}>{support.summary}</span>}
      </a>
    </li>
  );
}

export default async function NextRead({ support, prefSlug = null, prefName = null }) {
  /* 1. 本文が実際にリンクしている制度 = 併給・関連の根拠。自分自身は除く */
  const linkedIds = extractLinkedSupportIds(support.article_md).filter((id) => id !== support.id);
  const related = (await getLinkableSupports(linkedIds)).slice(0, MAX_RELATED);

  /* 2. 同じカテゴリ。1 で出したものと自分自身は重複させない */
  const shownIds = [support.id, ...related.map((s) => s.id)];
  const sameCategory = (
    await getSupportsInCategory(support.category, { excludeIds: shownIds })
  ).slice(0, MAX_SAME_CATEGORY);

  /* 3. その制度にひもづく用語 */
  const terms = (await getGlossaryForSupport(support.id)).slice(0, MAX_TERMS);

  /* 4. 地域導線。全国記事では「都道府県別の制度もある」ことを伝える。
        地域記事は自県ハブへ戻す導線を出す (県一覧はハブ側にあるので並べない) */
  const prefectures = prefSlug ? [] : await getPrefectureList();

  const hasAnything =
    related.length > 0 || sameCategory.length > 0 || terms.length > 0 || prefectures.length > 0 || prefSlug;
  if (!hasAnything) return null;

  return (
    <section className={styles.next} aria-labelledby="nextread-title">
      <h2 className={styles.title} id="nextread-title">
        次に読む
      </h2>

      {related.length > 0 && (
        <div className={styles.group}>
          <h3 className={styles.groupTitle}>この記事で触れている関連制度</h3>
          <p className={styles.groupNote}>
            本文のなかで出てきた制度です。あわせて使えるかどうかは、それぞれの記事と窓口でご確認ください。
          </p>
          <ul className={styles.list}>
            {related.map((s) => (
              <SupportCard key={s.id} support={s} />
            ))}
          </ul>
        </div>
      )}

      {sameCategory.length > 0 && (
        <div className={styles.group}>
          <h3 className={styles.groupTitle}>同じ「{support.category}」のほかの制度</h3>
          <ul className={styles.list}>
            {sameCategory.map((s) => (
              <SupportCard key={s.id} support={s} />
            ))}
          </ul>
        </div>
      )}

      {terms.length > 0 && (
        <div className={styles.group}>
          <h3 className={styles.groupTitle}>この制度に関係する用語</h3>
          <ul className={styles.terms}>
            {terms.map((t) => (
              <li key={t.slug}>
                <a className={styles.term} href={`/words/${t.slug}`}>
                  <span className={styles.termName}>{t.term}</span>
                  {t.short_def && <span className={styles.termDef}>{t.short_def}</span>}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className={styles.group}>
        <h3 className={styles.groupTitle}>ほかの制度をさがす</h3>
        <ul className={styles.plainList}>
          {prefSlug ? (
            <>
              <li>
                <a className={styles.plainLink} href={`/${prefSlug}`}>
                  <span className={styles.plainLabel}>{prefName}の制度一覧</span>
                  <span className={styles.plainNote}>{prefName}独自の手当・助成をまとめて見る</span>
                </a>
              </li>
              <li>
                <a className={styles.plainLink} href="/">
                  <span className={styles.plainLabel}>全国の制度を見る</span>
                  <span className={styles.plainNote}>
                    児童扶養手当など、どこに住んでいても使える制度
                  </span>
                </a>
              </li>
            </>
          ) : (
            <>
              {prefectures.map((p) => (
                <li key={p.slug}>
                  <a className={styles.plainLink} href={`/${p.slug}`}>
                    <span className={styles.plainLabel}>{p.name_ja}の制度</span>
                    <span className={styles.plainNote}>
                      全国の制度に加えて使える、{p.name_ja}独自の制度が{p.article_count}件
                    </span>
                  </a>
                </li>
              ))}
              <li>
                <a className={styles.plainLink} href="/">
                  <span className={styles.plainLabel}>全国の制度を見る</span>
                  <span className={styles.plainNote}>手当・助成・給付金・貸付・税制・年金の一覧</span>
                </a>
              </li>
            </>
          )}
          <li>
            <a className={styles.plainLink} href="/calendar">
              <span className={styles.plainLabel}>ひとり親の1年カレンダー</span>
              <span className={styles.plainNote}>
                現況届・年末調整・確定申告など、時期が決まった手続きを月ごとに
              </span>
            </a>
          </li>
        </ul>
      </div>
    </section>
  );
}
