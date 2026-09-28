/* 記事のイラスト (見出しイラスト + 吹き出しのキャラアイコン) の割り当てロジック。
   素材と判定ルールの正本は docs/article-visuals-spec.md。ここはその実装。

   ★試験導入中★ いまは supports id=1 の記事だけに出している (app/support/[id]/page.jsx)。
   全記事に広げるときは、そこの条件を外すだけでよい。 */

/* ★画像置き場 (Supabase Storage) のバケット名・フォルダ名はコードに直接書かず、
   lib/siteConfig.js 経由で環境変数から読む。別の CDN に移すときもここは触らない。★ */
import { STORAGE_BASE, STORAGE_SECTIONS_DIR, STORAGE_CHARACTERS_DIR } from '@/lib/siteConfig';

export const sectionImage = (key) => `${STORAGE_BASE}/${STORAGE_SECTIONS_DIR}/${key}.png`;
export const faceImage = (key) => `${STORAGE_BASE}/${STORAGE_CHARACTERS_DIR}/${key}.png`;

/* ---------- 見出しイラスト ----------
   H2 の文言だけから機械的に決める。2段階。
   ★どれにも当たらなければ絵を出さない★ (先頭 H2 だけ overview にフォールバック)。
   間違ったランドマークを置くのは、置かないより悪いため。 */

// ステージA: 制度の性格を決める語。位置に関係なく、この順で先に確定させる
const STAGE_A = [
  ['faq', ['よくある質問', 'Q&A', '質問と答え']],
  ['summary', ['基本情報', 'まとめ']],
  ['related', ['併用', '併給', 'あわせて使える', 'あわせて利用', '他にも使える', '他の支援制度', '参考リンク', '一緒にできる', '関連']],
  ['overview', ['ってどんな制度', 'どんな制度', 'どういう制度', '制度か', '仕組み', '何をしてくれる', 'ではなく']],
];

/* ステージB: 見出しの中で「最も先に出てきた」キーワードの分類を採る。
   「申請の流れと必要書類」→ flow / 「必要書類と申請方法」→ documents のように
   複合見出しでも主題側が採れる。同位置なら上の行が優先。 */
const STAGE_B = [
  ['documents', ['必要書類', '必要な書類', 'そろえる', '持ち物', '用意するもの']],
  ['flow', ['流れ', '申請方法', '手続き', '申し込み', '申込', 'ステップ', '再申請']],
  ['schedule', ['スケジュール', '支給期間', '時期', '期限', 'タイミング', '支給月', '振込', '更新', 'いつ', '以降', '続くのか']],
  ['income-limit', ['所得制限', '所得要件', '所得の目安', '所得基準', '所得について']],
  ['eligibility', ['対象', '条件', '誰が', '誰?', '誰？', '受給要件', '納付要件', '資格', '世帯', 'お子さん', 'どんなとき', 'ならない人']],
  ['amount', ['いくら', '支給額', '金額', '給付額', '限度額', '上限額', '総額', '控除額', '利用料', '家賃', '月額', '早見表', '安くなる', '無利子', '負担']],
  ['related', ['との違い', 'どう違う', 'との関係', '選択肢']],
  ['caution', ['注意', '気をつけ', '知っておき', '確認しておきたい', '見落と']],
];

export function sectionKeyFor(headingText, isFirst = false) {
  const t = headingText || '';
  for (const [key, words] of STAGE_A) {
    if (words.some((w) => t.includes(w))) return key;
  }
  let best = null;
  for (const [key, words] of STAGE_B) {
    for (const w of words) {
      const at = t.indexOf(w);
      if (at === -1) continue;
      if (best === null || at < best.at) best = { key, at };
      break; // 同じ分類の中では最初に当たった語で十分
    }
  }
  if (best) return best.key;
  return isFirst ? 'overview' : null; // ★無理に埋めない★
}

/* ---------- 表情の出し分け ----------
   ★大原則: 判定を外すと表情と内容がちぐはぐになって逆効果。迷ったら通常に落とす★ */

const NATTOKU = ['なるほど', 'そうなんですね', 'そうなんだ', '助かります', 'ありがとうございます', 'よかった', '安心しました', 'わかりました', 'それなら', '心強い'];
const FUAN = ['不安', '心配', 'わからな', '分からな', '難しそう', 'どうしよう', '大変', '困っ', '間に合う', '間に合わ', 'できるのかな', '自信がな', 'ややこしい'];
// 「必ず」は藤井の発言で頻出する。注意顔が出すぎるようなら真っ先に外す候補 (仕様書 1-2)
const CHUI = ['注意', '気をつけ', '忘れずに', '忘れると', '期限', '締切', '締め切り', '失権', '支給停止', '資格を失', '打ち切', '受けられなくなり', '対象外', '必ず', '絶対に', '間に合わないと', '遅れると'];

const has = (text, words) => words.some((w) => text.includes(w));

export function faceFor(speaker, text, { isFirstMisaki = false } = {}) {
  const t = text || '';
  if (speaker === '藤井') return has(t, CHUI) ? 'fujii-chui' : 'fujii-normal';
  if (speaker === 'あかり') return 'akari-normal';
  if (speaker === 'みさき') {
    // 冒頭からいきなり困り顔だと導入の印象が重くなる (仕様書 1-2)
    if (isFirstMisaki) return 'misaki-normal';
    if (has(t, NATTOKU) && !has(t, FUAN)) return 'misaki-nattoku';
    if (/[？?]/.test(t) && has(t, FUAN)) return 'misaki-komari';
    return 'misaki-normal';
  }
  return null;
}
