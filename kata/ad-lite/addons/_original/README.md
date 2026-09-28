# 広告クリエイティブ自動化キット

商品キーワードから競合広告を調べ、競合と重なりにくい訴求を見つけ、バナーとLPを作る Claude Code 用テンプレートです。

特定の商品、個人パス、APIキー、過去の成果物に依存しない共有用構成です。

## できること

1. Meta広告ライブラリから競合コピーを収集
2. EmbeddingとPCAで訴求の「空き」を可視化
3. JSONで定義した訴求からバナーを生成
4. 商品情報からLP構成とセクション画像を生成
5. 静的LPをビルドし、必要な場合だけVercelに公開

## 最短スタート

```bash
cd creative-pipeline-share
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
patchright install chromium
cp .env.example .env
python scripts/check_setup.py
```

`.env` に必要なAPIキーを記入し、Claude Codeをこのフォルダで開いて次のように依頼します。

> 「○○」のキーワードで競合を分析し、バナーとLPを作って。商品情報は data/my-project/product.md です。

詳細は [SETUP.md](SETUP.md) を参照してください。

## 設定する場所

- 商品情報: `data/example/product.md` を複製して編集
- バナー訴求: `config/banner_concepts.json`
- APIキー: `.env`
- LPのCTA: `.env` の `CTA_URL` または公開コマンドの `--cta-url`

```bash
.venv/bin/python .claude/skills/banner-toolkit/scripts/banner.py --brief config/banner_concepts.json --list
```

## 処理の流れ

```text
利用者
  └─ orchestrator（進行と判断）
      ├─ ad-scraper       → 競合広告収集
      ├─ gap-analyst      → 空き訴求分析
      ├─ banner-designer  → バナー生成
      ├─ lp-designer      → LP生成
      └─ lp-publisher     → 公開（任意）
```

## 安全な共有のために

- `.env`、`.venv`、`.browser_profile`、実案データ、Vercelの `.vercel/` はZIPに含めません。
- 初回は少数件・画像1枚で試し、コストと品質を確認してください。
- 競合広告の収集はMetaの利用条件、対象国の法令、ロボットアクセスに関する制限を確認して使用してください。
- 画像・コピーは公開前に目視と法務確認を行ってください。

## 必要環境

- macOS / Linux / WSL
- Python 3.10以上
- Claude Code
- Node.js / npx（Vercel公開時のみ）
- Gemini APIキー（分析）
- OpenAI APIキー（画像生成）
