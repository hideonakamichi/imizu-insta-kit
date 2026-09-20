---
name: writing-slide-decks
description: 提案完成稿を grill→ジャッジ経由で深堀し、スタバ図解トンマナ付きのスライド設計図（Markdown+JSON）と Gemini 用プロンプトを作るスキル。HTML図解は要否確認後のみ。「スライド資料」「プレゼン資料」「枚割り」「スライド設計」「writing-slide-decks」と依頼された際に使用する。
---

# Writing Slide Decks

提案完成稿を **深堀（grill-me）→ レビュー（judge-panel）→ スライド設計図（A）** で作る。v0 の主成果物は **スライド定義**（Markdown ＋ JSON）。完成 PPT は必須にしない。

```
writing-proposals（4問 → 一発出し）
        ↓ 「プレゼン資料を作る」
本スキル: B要否確認 → grill → （推奨）presentations → judge → スライド設計 A → Geminiプロンプト
        ↓ B=要 のときのみ
creating-visual-explainers（HTML図解）
```

正本: `~/.claude/skills/writing-slide-decks/`（`~/.claude/skills/` はここへのジャンクション）  
Cursor ミラー: `~/.cursor/skills/writing-slide-decks/`（`scripts/sync-from-claude.ps1` で同期）

## スキルの構成

```
writing-slide-decks/
├── SKILL.md
└── references/
    ├── material-pipeline.md   … grill → judge → A（手順正本）
    ├── output-contract.md     … 入出力契約
    ├── gemini-slides-prompt.md  … Gemini 用プロンプト（Step 4b 正本）
    ├── output-quality.md      … 品質チェック
    └── examples.md              … 枚割りの例
```

**図解トンマナ:** `~/.cursor/rules/references/starbucks-visual.md`（コピー禁止。パターン1／2）

## 成果物

| ID | 内容 | デフォルト |
|----|------|------------|
| **A** | スライド設計図 Markdown ＋ JSON | **必須** |
| **C** | Gemini 用スライド作成プロンプト（コピペ1ブロック） | **必須**（A の直後） |
| **B** | HTML 図解 | **不要**（毎回確認） |

詳細フロー → [references/material-pipeline.md](references/material-pipeline.md)

## 模範解答（初めての構成を作るとき）

**過去に実績のない構成・枚割り**を頼まれたら、全枚数を書き始める前に **代表1〜2枚を模範解答として出し、確認を取る**。3条件（やり直しが重い／好みが結果を左右する／初めての種類）がそろう作業だけが対象。既存の型の焼き直しでは聞かない。

資料は枚数が多く、方向がずれたまま全枚数を書くと損失が大きい。**代表1枚で方向を合わせてから残りを書く。**

OK が出た模範解答は [references/examples.md](references/examples.md) に追記する。使い捨てにしない。

## 起動時（毎回・最初）

すぐ設計図を書かない。

1. **入力の受け取り**
   - **a.** 提案完成稿がある（直前の `writing-proposals`／貼付）→ 下記 2 へ
   - **b.** ない／薄い → `writing-proposals` を推奨してから戻る
2. **HTML 図解（B）要否** — AskQuestion 推奨。**1. 不要（A のみ）— 推奨** を先頭に
3. **読み上げ原稿の有無**
   - ある → Step 1（grill）へ
   - ない → 提案文のみで grill 可。**presentations は推奨**（具体・フックが薄いとき必須級）

## 基本ルール

- **提案文はチャットで磨かない。** 深堀は grill、修正は judge 後の **再出力**（`writing-proposals` ルール①②と両立）
- **原稿が正。** スライド側で結論・お願い・数字・体験を書き換えない
- **1枚1メッセージ。** 詰まりそうなら割る
- **山場の絵は1枚に絞る**
- **読み上げ全文をスライドに載せない**
- **懸念は先出し枚で回収**
- **手で直させない。** 材料を足してパイプライン再実行
- **トンマナ:** ビジュアル注記・任意 HTML モックは `~/.cursor/rules/references/starbucks-visual.md`（ADS 配色は使わない）

## 進め方（親エージェント）

| Step | 内容 |
|------|------|
| 0 | 起動確認（入力・B 要否・原稿有無） |
| 1 | **grill-me** — 提案完成稿を深堀（1問ずつ・実装しない） |
| 2 | **（推奨）writing-presentations** — 読み上げ原稿。省略可 |
| 3 | **judge-panel** — ハイブリッド: `reader` + `product`（資料）/ コード時 `bugbot` + `security-review` |
| 4 | **スライド設計 A** — 枚割り → Markdown + JSON。図解トンマナ注記付き |
| 4b | **Gemini プロンプト C** — [gemini-slides-prompt.md](references/gemini-slides-prompt.md) に従い生成 |
| 5 | **B=要** のときのみ `creating-visual-explainers` |

- **Revise（Step 3）:** 足りない材料を確認 → Step 2 または 4 を再実行。ユーザー Typing 修正禁止
- **Approve 後:** 設計図（A）＋ Gemini プロンプト（C）を **そのまま** スライド作成の入力に使う

### 枚割り（6ステップ → 枚）

| 原稿 | スライドの役割 | 目安枚数 |
|---|---|---|
| ① フック | 場面の一言 | 1 |
| ② 結論 | お願い ＋ キー数字（3つまで） | 1 |
| ③ なぜ | 根拠（山場1枚） | 1〜2 |
| ④ どうやって | 進め方・成功ゲート | 1〜2 |
| ⑤ どうなる | 変わった後 | 1 |
| ⑥ お願い | 懸念→対策 → Yes/No | 1〜2 |

目安: **5〜10分で 6〜10枚**。

## 出力フォーマット（A）

```markdown
## Slide N. {タイトル}
- **メッセージ（1文）:** …
- **画面に載せる:**
  - …
- **載せない（口頭のみ）:** …
- **スピーカーノート:** …
- **ビジュアル（図解トンマナ）:** 未指定はパターン1。背景 `#F0F4F8`、枠 `#102A43`、アクセント `#1890FF`
```

末尾に JSON（`output-contract.md`）。保存例: `スライド設計_◯◯.md`

### 出力フォーマット（C — Gemini プロンプト）

Step 4 直後 → [references/gemini-slides-prompt.md](references/gemini-slides-prompt.md)

- 保存例: `Geminiプロンプト_◯◯.md`（設計図と同じ `◯◯`）
- チャットにも **プロンプト全文** を fenced code で提示（ファイルと同一）

模範 → [references/examples.md](references/examples.md)

## 入出力契約

→ [references/output-contract.md](references/output-contract.md)

| | 内容 |
|---|---|
| **入力** | 提案完成稿 ＋ grill 合意 ＋ （推奨）読み上げ原稿 |
| **出力** | スライド設計 Markdown ＋ JSON ＋ Gemini プロンプト |
| **やらない（v0）** | 完成 PPT 必須、体験創作、B の無確認自動生成、Gemini 出力を SSoT にすること |

## 品質チェック

Step 4 直前・Step 4b 直前 → [references/output-quality.md](references/output-quality.md)

## やらないこと

- 提案文・読み上げ原稿そのものの作成（proposals / presentations の責務）
- ユーザー未確認の HTML 図解（B）自動生成
- ユーザーが語っていない体験・数字の創作
- v0 で完成 PPT を必須成果物にすること

## チューニング欄

### よくある場と枚数上限

（例: 上司10分 → 最大8枚）

### 社内で載せてはいけないもの

（例: 未公開顧客名）
