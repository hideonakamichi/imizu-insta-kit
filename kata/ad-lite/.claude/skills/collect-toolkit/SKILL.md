---
name: collect-toolkit
description: Collect専門スキル。手で書き写した競合広告コピー(competitors.md)を、分析ステージが読める manifest.jsonl に変換する。「competitors.md を変換して」「集めた広告を分析用にして」など、収集した競合コピーの下ごしらえが必要なときに参照する。
allowed-tools: Bash(py *), Bash(python3 *), Read, Write, Edit, Glob, Grep
---

# collect-toolkit — ステージ1: 手で集めた競合コピーの下ごしらえ

元のキットはここをブラウザの自動操作（Meta広告ライブラリのスクレイプ）で行っていた。**このキットは
自動収集をしない。** 理由は Meta の利用条件・ロボットによるアクセス制限に触れるおそれがあるため
（詳しくは `addons/README.md`）。代わりに、ユーザーが自分のブラウザで広告を見て、手で書き写す。

## 前提

- **入力**: `data/<プロジェクト>/competitors.md`（`data/example/competitors.md` を複製して埋めたもの）。
  書き方はそのテンプレートの中に書いてある
- **スクリプト**: このスキル内 `.claude/skills/collect-toolkit/scripts/build_manifest.py`
- APIキーは不要（この変換はローカル処理のみ）

```
py                                                     # Windows。Mac は python3
.claude/skills/collect-toolkit/scripts                 # = S
```

## 実行

```bash
py $S/build_manifest.py --md "data/<プロジェクト>/competitors.md"
```

`competitors.md` の `## 広告主名` と本文の組を読み取り、`data/<プロジェクト>/manifest.jsonl` に
書き出す（analyze-toolkit がそのまま読める形式）。

出力後、件数が表示される。**3件未満なら次の Analyze が動かない。** `competitors.md` に書き足してから
もう一度実行する。

## 呼び出し元への返却

- 出力した `manifest.jsonl` のパス
- 変換できた件数（3件未満なら「分析不可・件数不足」と明示し、`competitors.md` への追記を提案）

## トラブルシュート

- `## ` の後ろが空、または本文が空の項目はスキップされる（変換後の件数に反映される）
- 文字コードは `competitors.md` を UTF-8 で保存すること（VS Codeの既定のまま保存すれば問題ない）
