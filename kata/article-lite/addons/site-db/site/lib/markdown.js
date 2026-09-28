// article_md → HTML 変換 (サーバーサイド)
// - :::pointbox / :::warning / :::steps ディレクティブ
// - **みさき**: / **藤井**: の DialogueBubble 変換
// - <!-- FAQ_JSON [...] --> の抽出
import { unified } from 'unified';
import remarkParse from 'remark-parse';
import remarkGfm from 'remark-gfm';
import remarkDirective from 'remark-directive';
import remarkRehype from 'remark-rehype';
import rehypeRaw from 'rehype-raw';
import rehypeStringify from 'rehype-stringify';
import { h } from 'hastscript';
import { visit } from 'unist-util-visit';
import { sectionImage, faceImage, sectionKeyFor, faceFor } from './visuals';

const DIRECTIVE_TITLES = {
  pointbox: 'ポイント',
  warning: '注意',
  steps: 'ステップ',
};

// variant を持つ話者は dialogue-bubble-<variant> クラスが追加され、CSS でバブル色を変えられる
const SPEAKERS = {
  みさき: { side: 'left', label: 'みさき' },
  あかり: { side: 'left', label: 'あかり', variant: 'akari' }, // 座談会の相手役 (事実婚を選択)
  藤井: { side: 'right', label: '藤井先生' },
};

// :::pointbox{title="..."} → <div class="box pointbox"><div class="box-title">..</div>…</div>
function remarkCustomDirectives() {
  return (tree) => {
    visit(tree, 'containerDirective', (node) => {
      if (!DIRECTIVE_TITLES[node.name]) return;
      const title = (node.attributes && node.attributes.title) || DIRECTIVE_TITLES[node.name];
      node.data = node.data || {};
      node.data.hName = 'div';
      node.data.hProperties = { className: ['box', node.name] };
      node.children.unshift({
        type: 'paragraph',
        data: { hName: 'div', hProperties: { className: ['box-title'] } },
        children: [{ type: 'text', value: title }],
      });
    });
  };
}

// <p><strong>みさき</strong>: ...</p> → DialogueBubble (hast レベルで変換)
/* visuals=true のときだけ吹き出しにキャラクターの顔アイコンを足す。
   話者名はテキストのまま残し、アイコンは alt="" + aria-hidden にする
   (話者名が2回読み上げられるのを防ぐ。docs/article-visuals-spec.md §4) */
function rehypeDialogue({ visuals = false } = {}) {
  return (tree) => {
    let misakiSeen = 0;
    visit(tree, 'element', (node, index, parent) => {
      if (!parent || node.tagName !== 'p' || !node.children?.length) return;
      const first = node.children[0];
      if (first.type !== 'element' || first.tagName !== 'strong') return;
      const name = first.children?.[0]?.value;
      const speaker = SPEAKERS[name];
      if (!speaker) return;
      const rest = node.children.slice(1);
      if (rest[0]?.type === 'text') {
        rest[0] = { ...rest[0], value: rest[0].value.replace(/^[:：]\s*/, '') };
      }
      const cls = `dialogue-bubble dialogue-bubble-${speaker.side}${
        speaker.variant ? ` dialogue-bubble-${speaker.variant}` : ''
      }`;
      const body = [h('span', { class: 'who' }, speaker.label), h('div', { class: 'talk' }, rest)];

      let children = body;
      if (visuals) {
        if (name === 'みさき') misakiSeen += 1;
        const face = faceFor(name, nodeText({ children: rest }), { isFirstMisaki: name === 'みさき' && misakiSeen === 1 });
        if (face) {
          children = [
            h('img', {
              class: 'dialogue-face',
              src: faceImage(face),
              alt: '',
              'aria-hidden': 'true',
              width: '48',
              height: '48',
              loading: 'lazy',
              decoding: 'async',
            }),
            h('div', { class: 'dialogue-body' }, body),
          ];
        }
      }
      parent.children[index] = h('div', { class: cls + (visuals ? ' has-face' : '') }, children);
    });
  };
}

// hast ノードからプレーンテキストを取り出す
function nodeText(node) {
  if (!node) return '';
  if (node.type === 'text') return node.value || '';
  if (Array.isArray(node.children)) return node.children.map(nodeText).join('');
  return '';
}

/* ============================================================
   表のレスポンシブ化 (rehypeResponsiveTables)
   ------------------------------------------------------------
   スマホで列が潰れて「1〜3文字ずつ縦棒に折り返される」問題への対策。
   本文は Supabase の article_md をそのまま使うので、表示層だけで解決する。

   ① すべての <table> を <div class="table-scroll"> でラップする
      → CSS 側で overflow-x:auto。列が潰れる前に横スクロールに逃がす。
   ② 各 <td> に、その列の <th> のテキストを data-label として付与する
      → モバイルでカード化したとき CSS の ::before で「見出し: 値」を出すため。
   ③ 列数で表示方式のクラスを出し分ける (判定基準は CARD_MIN_COLS 参照)

   ※ 情報を落とさないこと。列を隠す・truncate する処理は入れない。
   ============================================================ */

/* カード化する列数のしきい値。
   理由: 本文の最大幅は 760px、375px 端末では左右 padding を引いて実質 343px しかない。
     - 2列 … 1列あたり約170px。「用語 | 説明」型がほとんどで、そのまま表として読める。
              カード化するとかえって縦に伸びるだけなので変換しない。
     - 3列以上 … 1列あたり114px以下。自治体比較表のような長文セルが数文字ずつ折り返され、
              事実上読めなくなる。横スクロールでは「読める」が「行同士を比較できない」ため、
              1行=1カード (1列目を見出しにした「項目: 値」の縦積み) に変換する。 */
const CARD_MIN_COLS = 3;

function tableRows(table) {
  const rows = [];
  visit(table, 'element', (n) => {
    if (n.tagName === 'tr') rows.push(n);
  });
  return rows;
}

function rowCells(row) {
  return (row.children || []).filter(
    (c) => c.type === 'element' && (c.tagName === 'td' || c.tagName === 'th')
  );
}

// 見出し行 (セルがすべて th の最初の行) のテキスト一覧
function headerTexts(table) {
  for (const row of tableRows(table)) {
    const cells = rowCells(row);
    if (cells.length && cells.every((c) => c.tagName === 'th')) {
      return cells.map((c) => nodeText(c).trim());
    }
  }
  return [];
}

function setProp(node, key, value) {
  node.properties = { ...(node.properties || {}), [key]: value };
}

function rehypeResponsiveTables() {
  return (tree) => {
    // ラップするとツリーが変わるので、先に対象を集めてから差し替える
    const targets = [];
    visit(tree, 'element', (node, index, parent) => {
      if (node.tagName === 'table' && parent && typeof index === 'number') {
        targets.push({ node, index, parent });
      }
    });

    for (const { node, index, parent } of targets) {
      const headers = headerTexts(node);
      const rows = tableRows(node);
      const cols = rows.reduce((max, r) => Math.max(max, rowCells(r).length), headers.length);
      const asCards = cols >= CARD_MIN_COLS;

      // 各 td に data-label (その列の見出し) を付与
      for (const row of rows) {
        const cells = rowCells(row);
        // colspan がある行は列と見出しの対応が崩れるのでラベルを付けない (誤ラベルを出さない)
        const hasSpan = cells.some((c) => Number(c.properties?.colSpan || 1) > 1);
        if (hasSpan) continue;
        cells.forEach((cell, i) => {
          if (cell.tagName !== 'td') return;
          const label = headers[i];
          if (label) setProp(cell, 'dataLabel', label);
        });
      }

      /* カード化する表は CSS で display を block に変える = ブラウザが表としての
         セマンティクスを落とすので、role を明示してスクリーンリーダー向けに補う */
      if (asCards) {
        setProp(node, 'role', 'table');
        visit(node, 'element', (n) => {
          if (n.tagName === 'thead' || n.tagName === 'tbody' || n.tagName === 'tfoot') {
            setProp(n, 'role', 'rowgroup');
          } else if (n.tagName === 'tr') {
            setProp(n, 'role', 'row');
          } else if (n.tagName === 'td') {
            setProp(n, 'role', 'cell');
          } else if (n.tagName === 'th') {
            setProp(n, 'role', n.properties?.scope === 'row' ? 'rowheader' : 'columnheader');
          }
        });
      }

      parent.children[index] = h(
        'div',
        {
          class: `table-scroll ${asCards ? 'table-cards' : 'table-scroll-only'}`,
          // 列数を CSS に渡す。table の min-width = 列数 × 1列の最低幅 に使う
          style: `--table-cols:${cols}`,
          // 横スクロール領域はキーボードでも操作できる必要がある
          tabIndex: 0,
        },
        [node]
      );
    }
  };
}

// h2 に id ("sec-1", "sec-2", ...) を付与し、見出し一覧を collector に集める
/* visuals=true のときは H2 の直前に見出しイラストを差し込む。
   どの絵を出すかは H2 の文言だけで決まる (lib/visuals.js)。
   ★どれにも当たらない見出しには絵を出さない★ — 間違ったランドマークは無いより悪い */
function rehypeHeadingIds(collector, { visuals = false } = {}) {
  return (tree) => {
    let n = 0;
    const inserts = [];
    visit(tree, 'element', (node, index, parent) => {
      if (node.tagName !== 'h2') return;
      n += 1;
      const id = `sec-${n}`;
      node.properties = { ...(node.properties || {}), id };
      const text = nodeText(node).trim();
      collector.push({ id, text });
      if (!visuals || !parent) return;
      const key = sectionKeyFor(text, n === 1);
      if (key) inserts.push({ parent, index, key });
    });
    // 後ろから挿入しないと index がずれる
    for (const { parent, index, key } of inserts.reverse()) {
      parent.children.splice(
        index,
        0,
        h('div', { class: 'article-visual' }, [
          h('img', {
            src: sectionImage(key),
            alt: '',
            'aria-hidden': 'true',
            width: '1200',
            height: '300',
            loading: 'lazy',
            decoding: 'async',
          }),
        ])
      );
    }
  };
}

export function extractFaq(md) {
  const m = md.match(/<!--\s*FAQ_JSON\s*(\[[\s\S]*?\])\s*-->/);
  if (!m) return { faq: [], md };
  let faq = [];
  try {
    faq = JSON.parse(m[1]);
  } catch {
    faq = [];
  }
  return { faq, md: md.replace(m[0], '') };
}

/* 読了目安 (分)。本文の「読む文字」だけを数えたいので、
   URL・画像・表組みの記号・ディレクティブ記法などノイズを落としてから数える。
   1分あたり 500 字 (日本語の一般的な黙読速度) で計算し、最低 1 分を返す。
   ★ここは目安の表示専用。制度の事実には一切関与しない★ */
export function readingMinutes(articleMd, charsPerMinute = 500) {
  if (!articleMd) return 0;
  const text = articleMd
    .replace(/<!--[\s\S]*?-->/g, '')          // FAQ_JSON などのコメント
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '')     // 画像
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')  // リンクは表示テキストだけ残す
    .replace(/https?:\/\/\S+/g, '')           // 生 URL
    .replace(/^:::.*$/gm, '')                 // :::pointbox などのディレクティブ行
    .replace(/[#>*_`|:\-—–]/g, '')            // 記号
    .replace(/\s+/g, '');                     // 空白・改行
  if (!text) return 0;
  return Math.max(1, Math.round(text.length / charsPerMinute));
}

/* visuals: true を渡すと、見出しイラストと吹き出しのキャラアイコンを出す。
   ★試験導入中★ いまは supports id=1 の記事だけ (app/support/[id]/page.jsx)。
   全記事に広げるときは、そこの条件を外すだけでよい。
   渡さない既存の呼び出し (他の記事 / 用語集 / おしゃべり) は従来どおり何も変わらない。 */
export async function renderArticle(articleMd, { visuals = false } = {}) {
  const { faq, md } = extractFaq(articleMd);
  const headings = [];
  const file = await unified()
    .use(remarkParse)
    .use(remarkGfm)
    .use(remarkDirective)
    .use(remarkCustomDirectives)
    .use(remarkRehype, { allowDangerousHtml: true })
    .use(rehypeRaw)
    .use(rehypeDialogue, { visuals })
    .use(rehypeHeadingIds, headings, { visuals })
    .use(rehypeResponsiveTables)
    .use(rehypeStringify)
    .process(md);
  return { html: String(file), faq, headings };
}
