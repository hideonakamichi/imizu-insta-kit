# 広告クリエイティブ Lite（競合の「空き」を見つけてバナーとLPを作る）

競合の広告コピーから**まだ誰も言っていない訴求（空きポジ）**を見つけ、そのコンセプトで
**広告バナーとLPの画像**を作るキットです。**投稿・公開は自分で行います。**

```
自分のブラウザで競合広告を見て、競合広告メモ（competitors.md）に書き写す
   ↓ Gemini Embedding でベクトル化 → PCA → 空きポジ Top-3 を抽出
空きポジの訴求コンセプト（headline_jp / sub_jp）
   ↓ 各案を1枚ずつ試打 → 目視で採用案を選ぶ → 採用案だけ本生成
バナー画像
   ↓
商品情報（product.md）と組み合わせて LP のセクション画像も生成
   ↓
自分で公開先を用意して掲載
```

元のキットとの違いは次のとおりです。

| | 元のキット | Lite 版 |
|---|---|---|
| 競合広告の収集 | Meta広告ライブラリをブラウザ自動操作でスクレイプ | **自分のブラウザで見て、手で書き写す**（`competitors.md`） |
| バナー・LP画像の生成 | OpenAI の gpt-image-2 | **Gemini の画像生成**（分析と同じAPIキーで動く） |
| LPの公開 | Vercelに自動デプロイ | **画像とHTML/Markdownがそろったら終わり。公開は自分で** |

**手順書（`.claude/skills/`）の骨組みは、ほぼ元のままです。** 分析（空きポジ抽出）のロジックは変えていません。
変えたのは「収集の入口」と「画像生成の呼び先」と「公開の有無」だけです。

- 動く OS … Windows・Mac（Python 3.10以上）
- 外部サービスのアカウントとキー … **Gemini APIキーが1つだけ要ります**（分析と画像生成の両方に使う）
- 費用 … Claude の利用量に加えて、**Geminiの利用量もかかります**（無料枠で足りるかは自分で確認してください）

> **このキットは、他の4本と違って本体からもGeminiに繋がります。** carousel・Threads・note・記事キットは
> 「本体は完全ローカル、外に出るのはaddonsだけ」でしたが、このキットは空きポジ分析（Embedding）と
> バナー・LP画像の生成そのものがGemini頼みの設計のため、無料化しても本体でAPIキーが要ります。

## はじめかた

1. このフォルダを VS Code で開く。「このフォルダを信頼しますか」と聞かれたら承認する
2. Python の仮想環境を作り、依存を入れる

   ```
   py -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

   (Mac: `python3 -m venv .venv` / `source .venv/bin/activate`)

3. `.env.example` を `.env` にコピーし、`GEMINI_API_KEY` を埋める（取得先: https://aistudio.google.com/）
4. `py scripts/check_setup.py` で診断する（APIは呼ばない）
5. `data/example/` を `data/my-project/` などにコピーし、`product.md` と `competitors.md` を埋める。
   `competitors.md` の書き方はファイルの中にある
6. Claude Code に「広告クリエイティブを作って」と頼む。`orchestrator` が Analyze → Banner → LP の順で進める

## できるもの

| ファイル | 中身 |
|---|---|
| `data/<プロジェクト>/analyze_<日時>/concept_map.json` | 競合の座標・空きポジTop-3・近傍の競合コピー |
| `data/<プロジェクト>/analyze_<日時>/banners/*.png` | 採用された訴求のバナー画像 |
| `data/<プロジェクト>/lp/<lp_id>_sections.json` | LPのセクション構成 |
| `data/<プロジェクト>/lp/images/<lp_id>/*/*.png` | LPのセクション画像 |

## 自分用に直す場所

| 変えたいもの | 場所 |
|---|---|
| 商品・サービスの情報 | `data/<プロジェクト>/product.md` |
| 競合の広告コピー | `data/<プロジェクト>/competitors.md` |
| バナーの訴求コンセプト・ペルソナ | `config/banner_concepts.json` |
| 空きポジの抽出数 | `analyze.py --top-k`（既定3） |

## ディレクトリ構成

```
CLAUDE.md                          共通ルール（Claude Code が毎回読む）
config/banner_concepts.json        バナーの訴求コンセプト（自分で足していく）
data/example/                      product.md・competitors.md・LPセクションJSONのひな形
.claude/agents/                    orchestrator・gap-analyst・banner-designer・lp-designer
.claude/skills/collect-toolkit/    competitors.md → manifest.jsonl の変換
.claude/skills/analyze-toolkit/    空きポジ分析（Gemini Embedding + PCA）
.claude/skills/banner-toolkit/     バナー画像生成（Gemini画像生成）
.claude/skills/lp-toolkit/         LPセクション画像生成（Gemini画像生成）
scripts/check_setup.py             ローカル診断（APIは呼ばない）
addons/                            外した機能（自動収集・自動公開）と元のキット一式
```

## 確かめたこと・確かめていないこと

- **確かめた**: `competitors.md` → `manifest.jsonl` の変換、依存のインストール、全スクリプトの構文チェック、
  Windowsでの日本語表示（cp932の文字化けをUTF-8に固定済み）
- **確かめていない**: `analyze.py`・`banner.py`・`lp_image.py` の**実際のGemini呼び出し**。
  APIキーを使う通しテストはまだ行っていません。**最初の1回は、途中で止まったらその場でClaude Codeに聞く**
  つもりで動かしてください

## 気をつけること

- 競合広告の閲覧は Meta の利用条件・対象国の法令に従ってください
- 生成した画像・コピーは、公開前に必ず自分の目で確認してください（実在ブランド名・人物に似ていないか等）
- Geminiの無料枠を超えると課金される場合があります。使う前に利用枠を確認してください
