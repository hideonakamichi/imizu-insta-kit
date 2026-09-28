/* かな並べ替えのユーティリティ（/words の あいうえお索引 で使用）

   なぜ localeCompare(ja) を使わないか:
   - Node / ブラウザの ICU 実装差でビルド環境によって並びが変わりうる
   - 「濁点・小書き・長音符を無視して清音で並べる」という国語辞典式の並びは
     localeCompare では素直に表現できない
   ここでは自前の折りたたみ（かな → 清音のひらがな）で決定的に並べる。 */

// 五十音（清音のひらがな）。この文字列の index がそのまま並び順になる
const GOJUON = 'あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん';

// 濁音・半濁音・小書き・ゔ → 清音のひらがなへ折りたたむ
const FOLD = {
  ぁ: 'あ', ぃ: 'い', ぅ: 'う', ぇ: 'え', ぉ: 'お',
  っ: 'つ', ゃ: 'や', ゅ: 'ゆ', ょ: 'よ', ゎ: 'わ', ゕ: 'か', ゖ: 'け',
  が: 'か', ぎ: 'き', ぐ: 'く', げ: 'け', ご: 'こ',
  ざ: 'さ', じ: 'し', ず: 'す', ぜ: 'せ', ぞ: 'そ',
  だ: 'た', ぢ: 'ち', づ: 'つ', で: 'て', ど: 'と',
  ば: 'は', び: 'ひ', ぶ: 'ふ', べ: 'へ', ぼ: 'ほ',
  ぱ: 'は', ぴ: 'ひ', ぷ: 'ふ', ぺ: 'へ', ぽ: 'ほ',
  ゔ: 'う',
};

/** 読みを「清音ひらがなだけ」の並べ替えキーに変換する。
 *  カタカナ→ひらがな、濁点/小書きを清音へ、長音符「ー」や「・」「、」などは落とす。 */
export function kanaSortKey(reading = '') {
  let out = '';
  for (const ch of String(reading)) {
    // カタカナ → ひらがな
    const code = ch.codePointAt(0);
    let c = code >= 0x30a1 && code <= 0x30f6 ? String.fromCodePoint(code - 0x60) : ch;
    c = FOLD[c] || c;
    if (GOJUON.includes(c)) out += c;
  }
  return out;
}

/* 行（あ行・か行…）の定義。索引の見出しに使う */
export const KANA_ROWS = [
  { label: 'あ', chars: 'あいうえお' },
  { label: 'か', chars: 'かきくけこ' },
  { label: 'さ', chars: 'さしすせそ' },
  { label: 'た', chars: 'たちつてと' },
  { label: 'な', chars: 'なにぬねの' },
  { label: 'は', chars: 'はひふへほ' },
  { label: 'ま', chars: 'まみむめも' },
  { label: 'や', chars: 'やゆよ' },
  { label: 'ら', chars: 'らりるれろ' },
  { label: 'わ', chars: 'わをん' },
];

/** 読みの1文字目から行ラベル（あ / か / さ …）を返す。判定できなければ null */
export function kanaRowLabel(reading = '') {
  const head = kanaSortKey(reading)[0];
  if (!head) return null;
  return KANA_ROWS.find((r) => r.chars.includes(head))?.label ?? null;
}

/** 語の配列を読み順に並べ、行ごとにグルーピングして返す。
 *  items: { reading, term, ... }[]  →  [{ label: 'か', items: [...] }, ...]
 *  読みが空の語は「その他」としていちばん後ろにまとめる（索引から漏らさないため）。 */
export function groupByKanaRow(items, { readingOf = (x) => x.reading, termOf = (x) => x.term } = {}) {
  const sorted = [...items].sort((a, b) => {
    const ka = kanaSortKey(readingOf(a));
    const kb = kanaSortKey(readingOf(b));
    if (ka !== kb) return ka < kb ? -1 : 1;
    // 同じ読みなら表記で安定させる
    return String(termOf(a)).localeCompare(String(termOf(b)));
  });

  const buckets = new Map();
  for (const it of sorted) {
    const label = kanaRowLabel(readingOf(it)) ?? 'その他';
    if (!buckets.has(label)) buckets.set(label, []);
    buckets.get(label).push(it);
  }

  const ordered = KANA_ROWS.map((r) => r.label).filter((l) => buckets.has(l));
  if (buckets.has('その他')) ordered.push('その他');
  return ordered.map((label) => ({ label, items: buckets.get(label) }));
}
