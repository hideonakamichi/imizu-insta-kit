---
name: creating-visual-explainers
description: >-
  図解 HTML と色つき Mermaid。起動は「図解」「図解を作って」。モード・公開・パレット・一言を
  グリルミーで1問ずつ聞き、完成稿のあと人がOKしてから絵を1本出す。
  出力先の既定は Claude Design（design スキル）。印刷・Surge・4月報告形式のときだけ従来 HTML。
  提出物モードは Why/What/How/When。公開は要のときだけ。ネオは使わない。
---

# Creating Visual Explainers

親が描く。子に描かせない。ネオは使わない。

正本: `~/.claude/skills/creating-visual-explainers/`（`~/.claude/skills/` はここへのジャンクション。Cursor ミラー: `~/.cursor/skills/creating-visual-explainers/`）

役割: 論理と一目の分かりやすさを両立する図解。体言止め。Z視線。

## モード

| モード | 用途 | 完成稿 | HTML |
|--------|------|--------|------|
| **軽量** | 概念・比較・1メッセージ | [four-steps.md](references/four-steps.md) | コア図1枚＋各論 |
| **提出物** | 提案・報告・行動まで網羅 | [four-steps-submission.md](references/four-steps-submission.md) | [html-submission.md](references/html-submission.md) |

未指定は **軽量**。起動文に「提出物」「提案」「報告」があれば **提出物**。

## 出力先

| 出力先 | いつ | 手順 |
|--------|------|------|
| **Claude Design** | **既定。** 人が手で整えたいもの全般 | [references/claude-design.md](references/claude-design.md) |
| 従来 HTML（`base.html`） | 印刷・PDF／Surge の URL が要る／4月報告形式 | 本 SKILL のステップ5・6 |

モードと出力先は別。軽量でも提出物でも Claude Design が既定。迷ったら Claude Design。

## 正本（コピー禁止）

| 領域 | 正本 |
|------|------|
| 色・型・チェックリスト | `~/.cursor/rules/references/starbucks-visual.md` |
| 固定質問の全文 | [references/questions.md](references/questions.md) |
| 軽量完成稿 | [references/four-steps.md](references/four-steps.md) |
| 提出物完成稿 | [references/four-steps-submission.md](references/four-steps-submission.md) |
| 提出物 HTML | [references/html-submission.md](references/html-submission.md) |
| 改行 | [references/typography.md](references/typography.md) |
| アイコン | [references/icons.md](references/icons.md) |
| 出力先 Claude Design（既定） | [references/claude-design.md](references/claude-design.md) |
| 公開（Surge。従来 HTML のみ） | [references/deploy.md](references/deploy.md) |
| 設問UI | `grill-me/references/question-format.md` |

ビジュアル仕様を本 SKILL に書かない。色は `tm1.*` または `tm2.*`。`sb.*` 禁止。

## 模範解答（初めての型を作るとき）

**過去に作った実績のない型・見せ方**を頼まれたら、本編に入る前に **模範解答を1本作るか確認する**。3条件（やり直しが重い／好みが結果を左右する／初めての種類）がそろう作業だけが対象。既存の型の作り直しでは聞かない。

OK が出た模範解答は **使い捨てにせず `references/` に保存する。** 2回目以降は参照するだけで済み、作る手間が消える。

| 既存の模範解答 | 対象 |
|---|---|
| [references/model-answer.html](references/model-answer.html) | 軽量モードの量の目安 |

提出物モードの模範解答は未整備。**初めて作ったときに保存すること。**

## 依存

- `references/base.html` — 従来 HTML の額縁（`tm1` と `tm2`）。従来 HTML を出すときだけ必要で、**無ければ終了**（運営連絡）。Claude Design では使わない
- `references/model-answer.html` — 軽量の量の目安（色は SSoT が正）

成果物は **案件の `output/`**（ワークスペース直下）。スキル内 `output/` に書かない。

## 流れ

```
固定4問（1問ずつ）→ 不足だけ追加質問 → 完成稿（モードに応じた4ステップ）
  → 人のOK → 出力先で1本（既定 Claude Design / 従来 HTML）
  → 公開が要のときだけ（Artifact または Surge）
```

ウェブ検索は、数字や定義が手元に無いときだけ。必須にしない。

### 0. 額縁

`references/base.html` が無ければ終了。

### 1. 固定4問（1問1決定）

[questions.md](references/questions.md) の全文を使う。AskQuestion。無ければチャット A〜E。

| 順 | 決めること |
|----|------------|
| 0 | モード（提出物／軽量） |
| 1 | 公開するか（要／否） |
| 2 | パレット（1／2。無指定は1） |
| 3 | 伝えたい一言 |

起動文に答えがあれば再質問しない。足りない問だけ聞く。

### 2. 追加質問

材料が足りないときだけ、グリルミーで1問ずつ。  
提出物モードで Why/What/How/When のどれかが空なら、そのブロックだけ追加で聞く。

### 3. 完成稿（4ステップ）

**提出物** → [four-steps-submission.md](references/four-steps-submission.md)  
**軽量** → [four-steps.md](references/four-steps.md)。型は4つのうち1つ。

| 内容 | 型（軽量のみ） |
|------|----------------|
| 階層・分解 | ロジックツリー |
| 比較・2軸 | マトリックス |
| 手順・流れ | フローチャート |
| 重なり・共通 | ベン図 |

### 4. 人のOK

AskQuestion（A=この完成稿でHTMLにする — 推奨 / B=一言を直して完成稿からやり直し / C=ここで終える）。無ければ同じ A〜E をチャットへ。

OK の前に HTML を出さない。

### 4.5 改行チェック（必須）

[typography.md](references/typography.md) を読み、HTML に反映したあと内部で Pass 確認する。

- h1・サマリー・本文は `<br>` で文節切り（幅任せ禁止）
- 「、」の直後だけで切らない
- PC で1行に収まる文に `<br>` を入れない
- 補助文は `text-*-muted`（`text-*/70` 禁止）

### 5. 絵を1本

OK のあとだけ。

**Claude Design（既定）** → [claude-design.md](references/claude-design.md)。以下は従来 HTML のときだけ読む。

`base.html` を案件 `output/{slug}.html` にコピーし、TITLE / DESCRIPTION / CONTENT を埋める。

- **提出物** → [html-submission.md](references/html-submission.md)。構造=ADS、色=`tm1`/`tm2`。改行=[typography.md](references/typography.md)、アイコン=[icons.md](references/icons.md)
- **軽量** → 完成稿の型に合わせて1枚のコア図

選んだパレットのクラスだけ使う（1なら `tm1-*`、2なら `tm2-*`）。`ads.*` 禁止。フッタークレジット禁止。

SSoT の出力前チェックリストを内部で確認。提出物は §提出物形式 の Pass 条件も見る。

### 6. 公開

問1が **否** → 公開しない。ローカルパスだけ報告。  
問1が **要**・Claude Design → Artifact として公開し URL を報告。  
問1が **要**・従来 HTML → [deploy.md](references/deploy.md)。失敗したらローカル HTML だけで完了（止めない）。

ユーザーが後から「SURGEして」と言ったら、そのときだけ deploy.md。

## 子レビュー

デフォルト **0本**。ユーザーが「ジャッジ」と明示したときだけ、`reader` + `product`（最大2）。  
チェックリスト `judge-panel/references/starbucks-visual-checklist.md` を `reader` に載せる。  
Task が無ければ親が同じルーブリックで順に見る。子に Write させない。

## 禁止

- React / shadcn、絵文字、インタラクティブ、追加 CDN / script / style（額縁と Lucide 初期化除く。Claude Design も同じ）
- `sb.*`、`ads.*`、チャットのブランド HEX
- ヒーロー帯、全面塗り見出し、「初心者向け」ラベル
- ネオ、スキル内への成果物保存、自動公開
- 図解のたびに子を起動する

## 例外

ユーザーが **4月報告形式** と明示したときだけ SSoT §例外形式。

**次にできること:** 完成稿を案件の `output/` で開く。直すなら一言を直して完成稿からやり直す。
