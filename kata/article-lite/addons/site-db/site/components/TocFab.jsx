'use client';

/* スマホ専用の追従ボタン「もくじへ戻る」。
   - ある程度 (600px) スクロールしたら右下にふわっと出す
   - タップで目次を開いた状態までスムーズスクロール
     (html の scroll-padding-top が効くので、固定ヘッダーの下にきちんと収まる)
   - ページ末尾のブロックが画面に入ってきたら消す。固定ボタンが LineCta のボタンに重ならないようにするため。
     基準は .line-cta。LineCta は NEXT_PUBLIC_LINE_ADD_URL が無いと描画されないので、
     その場合は必ず存在する .site-footer を基準にする
   - 640px 以上では CSS で非表示 (PC は目次が開いたまま見えているので不要) */

import { useEffect, useState } from 'react';
import { TOC_ID } from './Toc';

const SHOW_AFTER = 600; // これ以上スクロールしたら表示

export default function TocFab() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // 末尾ブロック。LineCta があればそれ、無ければフッター
    const tail = document.querySelector('.line-cta') || document.querySelector('.site-footer');

    const update = () => {
      const y = window.scrollY;
      const vh = window.innerHeight;
      // 末尾ブロックの上端が画面内に入ったら「終わりに来た」とみなして引っ込める
      const atTail = tail
        ? tail.getBoundingClientRect().top < vh - 8
        : y + vh > document.documentElement.scrollHeight - 400;
      setVisible(y > SHOW_AFTER && !atTail);
    };

    update();
    window.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update);
    return () => {
      window.removeEventListener('scroll', update);
      window.removeEventListener('resize', update);
    };
  }, []);

  const backToToc = () => {
    const toc = document.getElementById(TOC_ID);
    if (!toc) return;
    toc.open = true;
    toc.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <button
      type="button"
      className={`toc-fab${visible ? ' is-visible' : ''}`}
      onClick={backToToc}
      aria-hidden={!visible}
      tabIndex={visible ? 0 : -1}
    >
      <span className="toc-fab-icon" aria-hidden="true">↑</span>
      もくじへ戻る
    </button>
  );
}
