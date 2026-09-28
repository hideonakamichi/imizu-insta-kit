# 外した機能

元のキットのファイルは `_original/` に、同じ構成のまま置いてあります（元の README・SETUP・design.md・6エージェント・5スキル・スクリプト一式）。

## 足すと何が増えるか

| 足すもの | 増えること | 要るもの・費用 | 手間 | 気をつけること |
|---|---|---|---|---|
| 競合広告の自動収集（Meta広告ライブラリのスクレイプ） | キーワード1つで数十件の競合コピーを自動で集められる | 追加の登録・キーは不要。ただし `patchright`（ブラウザ自動操作）を入れる | Chromiumが実際に開いて動く。初回はログインを求められることがある | **Metaの利用条件・ロボットによるアクセス制限に触れるおそれ**がある。本体（Lite版）は「自分のブラウザで開いて手で書き写す」形にして、この心配を無くしている |
| LPのWeb公開（Vercelへの自動デプロイ） | 作ったLPに公開URLが付き、そのままSNSやLINEに貼れる | Vercelのアカウント（無料枠あり）、Node.js/npx | `.env` に `VERCEL_TOKEN` を書くか `vercel login` | **外部公開になる。** 本番前に必ずプレビューURLで確認する運用が元から必須。本体（Lite版）は「投稿用の画像がそろうまで」を終点にして、公開そのものは自分の判断に委ねている |

## 戻し方

- 元の手順書は `_original/.claude/agents/{ad-scraper,lp-publisher}.md` と `_original/.claude/skills/{scrape-toolkit,publish-toolkit}/`。**このフォルダごと本体の `.claude/agents/` `.claude/skills/` の下に写すと、元のエージェント・スキルとして使える**
- スクレイプには `patchright`（`requirements.txt` に追記して `pip install`）と、ブラウザが実際に開ける環境が要る
- 公開にはNode.js（`npx`経由でVercel CLIを呼ぶ）と、`_original/.env.example` の `VERCEL_TOKEN` / `CTA_URL`
- orchestrator（本体側）にScrapeとPublishの2ステージを戻す場合は、`_original/.claude/agents/orchestrator.md` の「進め方」を参考に、本体の `orchestrator.md` へ手順を書き足す
