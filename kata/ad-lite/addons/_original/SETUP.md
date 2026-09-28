# セットアップ

## 1. 準備

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
patchright install chromium
cp .env.example .env
```

Python 3.10以上が必要です。Windows PowerShellでは `.venv\\Scripts\\Activate.ps1` で仮想環境を有効化します。

## 2. APIキー

`.env` の必要な項目だけ記入します。

- `GEMINI_API_KEY`: 競合コピーのベクトル化
- `OPENAI_API_KEY`: バナーとLP画像の生成
- `VERCEL_TOKEN`: Vercel公開時のみ
- `CTA_URL`: LPの申込み先

`.env` は共有やGitへのコミットをしないでください。

## 3. 診断

```bash
python scripts/check_setup.py
python .claude/skills/scrape-toolkit/scripts/scrape.py --help
python .claude/skills/analyze-toolkit/scripts/analyze.py --help
python .claude/skills/banner-toolkit/scripts/banner.py --help
python .claude/skills/banner-toolkit/scripts/banner.py --list
python .claude/skills/lp-toolkit/scripts/lp_image.py --help
python .claude/skills/publish-toolkit/scripts/publish.py --help
```

`--help` と `--list` はAPIを呼び出さず、課金も発生しません。

## 4. 新規案件

```bash
cp -R data/example data/my-project
```

`data/my-project/product.md` を埋め、分析後の訴求案を `config/banner_concepts.json` に入れます。

## 5. 個別実行例

```bash
.venv/bin/python .claude/skills/scrape-toolkit/scripts/scrape.py --query "<キーワード>" --limit 30
.venv/bin/python .claude/skills/analyze-toolkit/scripts/analyze.py --data-dir "data/<生成されたフォルダ>"
.venv/bin/python .claude/skills/banner-toolkit/scripts/banner.py --list
.venv/bin/python .claude/skills/banner-toolkit/scripts/banner.py --concept benefit_first --persona professional --out-dir data/my-project/banners
.venv/bin/python .claude/skills/lp-toolkit/scripts/lp_image.py --json data/my-project/lp/example_sections.json --section S01_fv
.venv/bin/python .claude/skills/publish-toolkit/scripts/publish.py --json data/my-project/lp/example_sections.json --cta-url "https://example.com/apply"
```

APIを使うコマンドは費用が発生します。画像は1枚から試し、本番公開はプレビュー確認後に行ってください。
