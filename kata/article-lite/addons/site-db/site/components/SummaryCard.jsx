/* 記事冒頭の「30秒でわかる」サマリーカード。

   ★事実ベース厳守★
   ここに出す値は すべて supports テーブルの既存カラムをそのまま整形しただけ。
   推測・補完は一切しない。カラムが NULL の項目は行ごと出さない。
     対象   … target_scope (+ 地域制度なら県名)
     金額   … amount_max / support_rate / amount_note
              (見せ方はカテゴリで変える。税制は「所得から◯円」、貸付は「貸付上限」。
               lib/amount.js に一覧カードと共通化してある)
     実施機関 … organizer
     公式   … official_url
   読了目安だけは article_md の文字数から機械的に計算している (lib/markdown.js の readingMinutes)。

   「申請窓口」ではなく「実施機関」と書いているのは、organizer が制度の実施主体
   (こども家庭庁 等) であって申請先そのものとは限らないため。
   実際の申請先を DB から断定できないので、窓口名は書かない。 */

import { amountRow } from '@/lib/amount';

const SCOPE_TEXT = {
  hitorioya: 'ひとり親家庭（母子家庭・父子家庭）',
  all_families: 'すべての子育て家庭（ひとり親家庭も対象）',
  bereaved: '死別でひとり親になったご家庭',
};

/* 表示する行を組み立てる。値が無い項目は push しない (= カードに出ない) */
function buildRows(support, prefName) {
  const rows = [];

  const scope = SCOPE_TEXT[support.target_scope];
  if (scope) {
    rows.push({
      key: 'target',
      label: '対象',
      value: prefName ? `${prefName}にお住まいの${scope}` : scope,
    });
  }

  const amount = amountRow(support);
  if (amount) {
    rows.push({ key: 'amount', ...amount, sub: support.amount_note || null });
  } else if (support.support_rate) {
    rows.push({
      key: 'amount',
      label: '助成率',
      value: support.support_rate,
      sub: support.amount_note || null,
    });
  } else if (support.amount_note) {
    rows.push({ key: 'amount', label: '金額', value: support.amount_note });
  }

  if (support.organizer) {
    rows.push({ key: 'organizer', label: '実施機関', value: support.organizer });
  }

  return rows;
}

export default function SummaryCard({ support, minutes, prefName }) {
  if (!support) return null;
  const rows = buildRows(support, prefName);
  if (rows.length === 0 && !minutes) return null;

  return (
    <aside className="summary-card" aria-label="この制度の要点">
      <div className="summary-card-head">
        <span className="summary-card-badge">30秒でわかる</span>
        {minutes > 0 && (
          <span className="summary-card-read">全文を読む目安 約{minutes}分</span>
        )}
      </div>

      {rows.length > 0 && (
        <dl className="summary-list">
          {rows.map((r) => (
            <div className="summary-row" key={r.key}>
              <dt>{r.label}</dt>
              <dd>
                <span className="summary-value">{r.value}</span>
                {r.note && <span className="summary-note">{r.note}</span>}
                {r.sub && <span className="summary-sub">{r.sub}</span>}
              </dd>
            </div>
          ))}
        </dl>
      )}

      {support.official_url && (
        <a
          className="summary-official"
          href={support.official_url}
          target="_blank"
          rel="noopener noreferrer"
        >
          公式ページで確認する →
        </a>
      )}

      {/* 制度によって窓口は市区町村・都道府県・年金事務所などさまざまなので、
          ここでは特定の窓口名を書かない (断定すると事実と食い違う制度が出る) */}
      <p className="summary-caution">
        受けられるかどうかの最終的な判断は、必ず公式の窓口でご確認ください。
      </p>
    </aside>
  );
}
