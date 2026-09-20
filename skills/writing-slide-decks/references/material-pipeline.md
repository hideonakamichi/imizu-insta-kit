# プレゼン資料作成パイプライン（A 正本）

「プレゼン資料を作る」選択時の手順正本。概要 → [SKILL.md](../SKILL.md)。

## 成果物

| ID | 内容 | デフォルト |
|----|------|------------|
| **A** | スライド設計図 Markdown ＋ JSON（`deck`） | **必須** |
| **C** | Gemini 用スライド作成プロンプト | **必須**（A の直後） |
| **B** | HTML 図解（Surge 等） | **不要** — 毎回1問で確認 |

## 全体フロー

```
提案完成稿（writing-proposals）
        ↓
Step 0  HTML図解（B）要否確認 — デフォルト「不要」
        ↓
Step 1  grill-me — 提案内容の深堀（実装しない）
        ↓
Step 2  （推奨）writing-presentations — 読み上げ原稿
        │         ※ 提案文のみでも可。原稿が薄いとき推奨
        ↓
Step 3  judge-panel（ハイブリッド）— 文章は reader+product / コードは bugbot+security-review
        ↓ Revise → 材料追加して Step 2 または Step 4 を再実行
Step 4  スライド設計図 A — スタバトンマナ注記付き
        ↓
Step 4b Gemini プロンプト C — 設計図を添付して使うコピペブロック
        ↓ B=要 のときのみ
Step 5  creating-visual-explainers（B）— ユーザー明示後
```

**提案文そのもの** をチャットで段落修正しない（`writing-proposals` ルール①②と両立）。

## Step 0 — HTML 図解（B）要否（毎回）

AskQuestion 推奨。先頭を **不要（A のみ）** にする。

| 選択 | 意味 |
|------|------|
| **1. 不要（A のみ）— 推奨** | スライド設計図だけ |
| **2. 必要（A + B）** | 設計図のあと HTML 図解も |

## Step 1 — grill-me（提案内容の深堀）

`grill-me` スキルに従う。**設問型** → [grill-me/references/question-format.md](../../grill-me/references/question-format.md)（毎回 AskQuestion・`グリル N問目`・A〜E）。

**提案完成稿** を対象に、前提・数字の穴・No 不安・スコープを1問ずつ詰める。

- **目的:** 資料に載せる材料を足す（提案文の段落磨きではない）
- **実装はしない**
- 合意を箇条書きでメモ（`grill-me` 終了フォーマット）
- グリルで判明した追記は、原稿／設計図に **創作せず** 反映

### グリルの観点（提案資料向け）

| 観点 | 例 |
|------|-----|
| 数字・根拠 | 会議時間・頻度・コストは具体があるか |
| 相手の問い | 4問③と資料の枚が対応しているか |
| No 不安 | リスク枚で先回りできるか |
| スコープ | やらないこと・試行期間・打ち切り |
| 尺・場 | 何分・誰の前か（原稿に無ければ1問） |

## Step 2 — 読み上げ原稿（推奨）

| 状況 | 動き |
|------|------|
| 直前に `writing-presentations` 完成稿がある | そのまま Step 3 へ |
| 提案完成稿のみ | **推奨:** presentations を実行。省略可（提案文を簡易マップして Step 4 へ） |
| フック・具体が薄い | presentations を推奨 |

入力の正: **読み上げ原稿** ＞ 提案完成稿（参照のみ）

## Step 3 — judge-panel（毎回・必須）

`judge-panel` スキル（**ハイブリッド**）に従い Task でレビュー。正本 → [judge-panel/references/hybrid-flow.md](../../judge-panel/references/hybrid-flow.md)

| 対象 | デフォルト |
|------|------------|
| 読み上げ原稿 / 提案ベースの資料 | `reader` + `product`（panel） |
| リポにコード変更を伴う | 上記に加え or 代替で `bugbot` + `security-review` |

- **Approve** → Step 4 へ
- **Revise** → 指摘と足りない材料をユーザーに確認 → 材料を足して **Step 2 または Step 4 を再実行**（手作業修正禁止）
- 再ジャッジは judge-panel 手順どおり **最大1回**

審査対象: 読み上げ原稿（あれば）＋ グリル合意メモ。スライド設計図は **Step 4 のあと** に別途 reader で軽く見てもよい（Revise なら Step 4 再出力）。

## Step 4 — スライド設計図（A）

- [output-quality.md](output-quality.md) を満たす
- 各 Slide に **ビジュアル（スタバ）** 注記 → `~/.cursor/rules/references/starbucks-visual.md`
- 出力: 設計図 Markdown ＋ JSON（[output-contract.md](output-contract.md)）
- **手で直させない** — 修正は材料追加 → パイプライン最初からまたは Step 4 再出力

## Step 4b — Gemini プロンプト（C・毎回必須）

- 正本 → [gemini-slides-prompt.md](gemini-slides-prompt.md)
- Step 4 の `deck` JSON / Markdown 設計図から **プレースホルダを埋めて** 1ブロック生成
- 出力: `Geminiプロンプト_{title}.md` ＋ チャットに同一内容
- **設計図が SSoT。** プロンプトに設計図にない KPI・体験を足さない
- Gemini の出力はたたき台。ズレたら材料修正 → Step 4 から再実行（手作業で設計を書き換えない）

## Step 5 — HTML 図解（B・任意）

Step 0 で **2. 必要** のときだけ。`creating-visual-explainers` ＋ `~/.cursor/rules/references/starbucks-visual.md`。

## 親エージェント（オーケストレーター）メモ

- grill / judge は **親が実行**。審査員 Task は **レビュー専用**
- 提案スキル Step 5 で「プレゼン**資料**を作る」と選ばれたら **本パイプライン** を起動（原稿だけの presentations とは別）
