# site/public/brand/ — ブランド素材の置き場

配布版にはロゴ・アイコン・OGP 画像を**同梱していません**（配布元サイトのブランド素材のため）。
`mark-placeholder.svg` だけがダミーとして入っています。

自分のサイトを立ち上げるときは、以下を用意してここに置いてください。

| ファイル | 用途 | 参照している場所 |
|---|---|---|
| `mark-192.png` (192×192) | ヘッダーのロゴマーク（44px で表示、Retina 用に 192px を縮小） | `site/app/layout.jsx` |
| `ogp.png` (1200×630) | SNS シェア時のサムネイル。**透過 PNG にしない**（背景を黒く描く環境がある） | `site/app/layout.jsx` の `openGraph.images` |
| `site/app/icon.png` (512×512) | favicon（Next.js の File Convention。`app/` 直下に置くと自動で使われる） | 自動 |
| `site/app/apple-icon.png` (180×180) | iOS のホーム画面アイコン | 自動 |

## ロゴに文字を焼き込まない

元の実装では**マークだけを画像にし、サイト名はライブテキスト**で出しています（`layout.jsx` の
`.site-logo-text`）。理由:

- 画像に文字を焼くと Google がサイト名を読めない
- スマホで 2 段に組み替えられない
- 表記を直したいときに画像を作り直すことになる
