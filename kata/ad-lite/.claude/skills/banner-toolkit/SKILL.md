---
name: banner-toolkit
description: Banner専門スキル。banner-designer サブエージェントが呼ぶ実行手順。空きポジから言語化した訴求コンセプトで、Meta Feed用バナー(1024×1024)を Gemini の画像生成で作る(日本語コピーを画像に直接描画)。「バナーを生成」「広告画像を作る」など、バナー画像生成の実コマンドが必要なときに参照する。
allowed-tools: Bash(py *), Bash(python3 *), Read, Write, Edit, Glob, Grep
---

# banner-toolkit — ステージ3: 空きポジ訴求のバナー生成

空きポジから言語化した訴求コンセプトで、Meta Feed用バナー（1024×1024）を生成する。**要 GEMINI_API_KEY**。
`gemini-3.1-flash-image-preview` で日本語コピーを画像に直接描画する（元のキットは OpenAI の gpt-image-2 を
使っていたが、Gemini に差し替えてある）。

## 前提（最初に必ず確認）

- **Python**: `py`（Windows）/ `python3`（Mac）
- **APIキー**: `.env` に `GEMINI_API_KEY` が必要。**`.env` はスクリプトが自動で読む**
- **スクリプト**: このスキル内 `.claude/skills/banner-toolkit/scripts/banner.py`
- **入力**: ステージ2（analyze-toolkit）で言語化した訴求コンセプト（headline_jp / sub_jp）

```
py                                                     # Windows。Mac は python3
.claude/skills/banner-toolkit/scripts                  # = S
```

---

## 実行

```bash
# 設定の一覧確認（API呼び出しなし）
py $S/banner.py --brief config/banner_concepts.json --list

# 1枚だけ試打
py $S/banner.py --brief config/banner_concepts.json --concept benefit_first --persona professional --out-dir data/my-project/banners

# 全パターン生成
py $S/banner.py
```

主なオプション:
- `--brief`: 訴求・デザイン・ペルソナを定義したJSON（既定: `config/banner_concepts.json`）
- `--concept`: JSON内のコンセプトID。未指定=全部
- `--persona`: JSON内の `personas` ID。未指定=全部
- `--list`: APIを使わずconcept/persona一覧を表示
- `--size`: `1024x1024`（既定）/ `1024x1536`（縦長）/ `1536x1024`（横長）
- `--out-dir`: 出力先（既定は最新 analyze 配下の `banners/`）

出力: `<out-dir>/<concept>_<persona>_<日時>.png` と `.prompt.txt`（使ったプロンプト記録）

> **コスト注意**: 1枚あたり数円〜十数円。**必ず `--concept ... --persona ...` で1枚試打 → Readで目視確認 →
> 良ければ全パターン生成**、の順で慎重に。生成後は必ず画像をReadで目視確認する。
>
> **新コンセプト追加**: `config/banner_concepts.json` に headline_jp / sub_jp / tone_prompt /
> personas を追記する。スクリプト本体の編集は不要。

## 呼び出し元への返却

生成が終わったら、次を呼び出し元（orchestrator）に返す:
- 生成したバナー画像のパス一覧
- 目視確認の結果（日本語コピーの誤字・レイアウト崩れの有無）

## トラブルシュート

- `GEMINI_API_KEY が設定されていません` → `.env` に記入
- `画像データが返されませんでした` → プロンプトが長すぎるか、安全フィルタに引っかかった可能性。
  人物描写や実在ブランド名を含めていないか見直す
- 日本語テキストが崩れる → Geminiの既知の弱点。プロンプトの見出し・サブテキストを短くして再生成する
