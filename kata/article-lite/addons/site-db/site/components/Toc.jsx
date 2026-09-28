// 記事の目次 (h2 見出しへのアンカーリンク)。headings は lib/markdown.js の renderArticle が返す [{id, text}]
//
// スマホは初期状態を「閉じる」、640px 以上は「開く」。
// <details> の開閉状態は CSS のメディアクエリからは操作できない (UA が中身を隠すため) ので、
// SSR では閉じたまま出し、直後のインラインスクリプトで幅を見て開く。
// スクリプトは HTML パース中 = ハイドレーション前に走るので、PC でも開閉のチラつきは出ない。
// (JS 無効の PC では閉じた状態で出るが、サマリーをタップすれば開くので機能は失われない)
//
// TOC_ID は components/TocFab.jsx (「もくじへ戻る」ボタン) からも参照される。
export const TOC_ID = 'toc-details';

const OPEN_ON_DESKTOP = `(function(){try{var d=document.getElementById('${TOC_ID}');if(d&&window.matchMedia('(min-width:640px)').matches){d.open=true;}}catch(e){}})();`;

export default function Toc({ headings }) {
  if (!headings || headings.length < 2) return null;
  return (
    <nav className="toc" aria-label="目次">
      <details className="toc-details" id={TOC_ID} suppressHydrationWarning>
        <summary className="toc-summary">もくじ（全{headings.length}項目）</summary>
        <ol className="toc-list">
          {headings.map((h) => (
            <li key={h.id}>
              <a href={`#${h.id}`}>{h.text}</a>
            </li>
          ))}
        </ol>
      </details>
      <script dangerouslySetInnerHTML={{ __html: OPEN_ON_DESKTOP }} />
    </nav>
  );
}
