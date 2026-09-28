---
name: analyze-toolkit
description: Analyze専門スキル。gap-analyst サブエージェントが呼ぶ実行手順。収集済みの広告コピーを Gemini Embedding でベクトル化→PCAで2次元化し、既存から最も遠い座標(=空きポジ=誰も言っていない訴求)を Top-K 抽出する。「空きポジを分析」「訴求の隙間を抽出」など、空きポジ分析の実コマンドが必要なときに参照する。
allowed-tools: Bash(.venv/bin/python *), Read, Write, Edit, Glob, Grep
---

# analyze-toolkit — ステージ2: 空きポジ（訴求の隙間）の抽出

各広告コピーを Gemini Embedding でベクトル化 → PCAで2次元化 → 既存広告から最も遠い座標
（＝誰も言っていない訴求＝空きポジ）を Top-K 抽出する。**要 GEMINI_API_KEY**。

設計の*理由*（なぜコピーで空きポジを測るのか等）は [../../../design.md](../../../design.md) を参照。

## 前提（最初に必ず確認）

- **作業ディレクトリ**: コマンドは `creative-pipeline-orchestrated/`（プロジェクト直下）からの相対パス。
- **Python**: `.venv/bin/python`
- **APIキー**: `.env` に `GEMINI_API_KEY` が必要。**`.env` はスクリプトが自動で読む**ので手動 `source` 不要。
- **スクリプト**: このスキル内 `.claude/skills/analyze-toolkit/scripts/analyze.py`
- **入力**: ステージ1（scrape-toolkit）が出力した `manifest.jsonl` を含むフォルダ
- 未セットアップなら [../../../SETUP.md](../../../SETUP.md) を先に実行する

```
.venv/bin/python                                        # = PY
.claude/skills/analyze-toolkit/scripts                  # = S
```

---

## 実行

```bash
$PY $S/analyze.py --data-dir "data/<クエリのフォルダ>"
```

例（scrape-toolkit の出力フォルダ名は `data/<日付>_<クエリ>/`。実在するフォルダ名をそのまま渡す）:
```bash
$PY $S/analyze.py --data-dir "data/<生成されたフォルダ>"
```

主なオプション:
- `--data-dir`（必須・複数可）: manifest.jsonl を含むフォルダ（scrape の出力フォルダ）。複数指定で1空間にマージ分析
- `--top-k`: 抽出する空きポジ数（既定3）

出力: `data/<クエリ>/analyze_<日時>/`
- `concept_map.json`: 各広告の座標・空きポジTop-K・空きポジ近傍の競合コピー
- `concept_map.png`: 可視化プロット

> **判断ポイント（重要）**: ここが gap-analyst の腕の見せ所。`concept_map.json` の各 GAP の
> `nearest_existing`（空きポジ近傍の競合コピー）を読み、「その近くに*無い*訴求は何か」を言語化する。
> それが次の Banner のコンセプトになる。PC1/PC2の寄与率が低い（各20%未満）場合は母数を増やす。

## 呼び出し元への返却

分析が終わったら、次を呼び出し元（orchestrator）に返す:
- `concept_map.json` のパス
- 各空きポジについて言語化した訴求コンセプト（**headline_jp + sub_jp の形**）。これが Banner の入力になる。
- 寄与率が低く母数不足なら、その旨と推奨対応（scrape の limit 増 or 別クエリ追加）

## トラブルシュート

- `GEMINI_API_KEY が設定されていません` → `.env` に記入。venv経由で実行しているか確認
- `レコードが少なすぎる (N件)` → scrape の `--limit` を上げるか複数クエリをマージ
- **初回実行が無出力のまま数十秒〜数分固まる** → ハングでもレート制限でもない。`import google.genai`
  が `websockets`/`aiohttp` など多数のサブモジュールを読み込み、その初回ファイルアクセスに
  オンアクセススキャン（AV/EDR）やクラウド同期フォルダの実体化が挟まると、1ファイルあたり約1秒×多数で
  import だけで数十秒〜数分かかるため。**埋め込みAPIを呼ぶ手前で止まっているだけ**なので、そのまま待てば
  `[i/N] embedded` が出て進む（2回目以降はキャッシュが効き 1秒未満で通過）。切り分けは
  `.venv/bin/python -X importtime -c "import google.genai"` で import 段の所要時間を確認する。
