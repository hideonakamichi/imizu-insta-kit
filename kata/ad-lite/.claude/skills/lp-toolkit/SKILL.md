---
name: lp-toolkit
description: LP専門スキル。lp-designer サブエージェントが呼ぶ実行手順。LPのセクション構成(_sections.json)とLP本文(HTML/Markdown)を商品情報と空きポジ訴求から書き、各セクションの画像を Gemini の画像生成で作る。「LPを作る」「ランディングページのセクション画像を生成」など、LP生成の実コマンドが必要なときに参照する。
allowed-tools: Bash(py *), Bash(python3 *), Read, Write, Edit, Glob, Grep
---

# lp-toolkit — ステージ4: LP本文＋セクション画像の生成

LPのセクション別画像を生成する。**要 GEMINI_API_KEY**。
LP本文（HTML/Markdown）とセクション構成（`_sections.json`）は lp-designer が書き、画像はこのスクリプトで作る。
**LPの公開はこのキットの範囲外。** 画像とHTML/Markdownがそろったら終わりで、公開先の用意と掲載は自分で行う。

## 前提（最初に必ず確認）

- **Python**: `py`（Windows）/ `python3`（Mac）
- **APIキー**: `.env` に `GEMINI_API_KEY` が必要。**`.env` はスクリプトが自動で読む**
- **スクリプト**: このスキル内 `.claude/skills/lp-toolkit/scripts/lp_image.py`
- **入力**: 商品情報（`data/<プロジェクト>/product.md`）と空きポジ訴求（analyze-toolkit の言語化結果）

```
py                                                   # Windows。Mac は python3
.claude/skills/lp-toolkit/scripts                    # = S
```

---

## 手順

1. **LP本文・セクション構成を書く**: 商品情報（`data/<プロジェクト>/product.md`）と空きポジ訴求をもとに、
   LPの HTML/Markdown と セクション構成 `data/<プロジェクト>/lp/<lp_id>_sections.json` を執筆する。
2. **セクション画像を生成**:

```bash
py $S/lp_image.py --json "data/<プロジェクト>/lp/<lp_id>_sections.json"

# 1セクションだけ
py $S/lp_image.py --json "data/my-project/lp/example_sections.json" --section S01_fv
```

入力 JSON の形式（`lp/<lp_id>_sections.json`）:
```json
{
  "lp_id": "example-product",
  "sections": [
    { "id": "S01_fv", "size": "1024x1536", "prompt": "..." }
  ]
}
```

各フィールド:
- `id`: セクションID（`S01_fv` のように連番＋役割）
- `size`: 画像サイズ。`1024x1024`（正方形）/ `1024x1536`（縦長。ファーストビュー向け）/ `1536x1024`（横長）
- `prompt`: Geminiへの英語プロンプト。**トーン（配色・雰囲気）と、画像内に焼き込む日本語テキスト
  （headline/sub）を明記**する。トーンは全セクションで揃え、LP全体の世界観を統一する。
  参考例は `data/example/lp/example_sections.json`。

出力: `data/<プロジェクト>/lp/images/<lp_id>/<NN.section>/<日時>.png`

> **コスト注意**: まず `--section` で1セクションだけ試打 → Readで目視確認 → 良ければ全セクション生成。

## 呼び出し元への返却

生成が終わったら、次を呼び出し元（orchestrator）に返す:
- 書いた LP本文・`_sections.json` のパス
- 生成したセクション画像のパス一覧と目視確認の結果

## トラブルシュート

- `GEMINI_API_KEY が設定されていません` → `.env` に記入
- `画像データが返されませんでした` → プロンプトが長すぎるか、安全フィルタに引っかかった可能性
- 日本語テキストが崩れる → プロンプトの見出し・サブテキストを短くして再生成する
