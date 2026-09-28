---
name: telop-srt-toolkit
description: リール動画から字幕SRTを生成し、動画に焼き込む手順。音声抽出→Whisper文字起こし→辞書補正→DP最適分割→ffmpeg焼き込みの一気通貫パイプライン。【2026-07-20以降、現行リールパイプラインでは未使用（スライド完結型に移行）。字幕付き動画が別途必要な場合のみ使う】
---

# telop-srt-toolkit

> **注記（2026-07-20）: 現行のリールパイプラインでは未使用。**
> ユーザーフィードバック（スライド本文＋字幕の併存は縦型では視線移動が多く視聴ストレスに
> なる・スライドと字幕の切替タイミングのズレがノイズになる）を受け、リールは
> 「スライドの文字情報だけで完結する」設計に移行し、字幕焼き込みを廃止した。
> このスキルとスクリプト群は、将来字幕付き動画が必要になった場合のために温存している。

reel-productionで結合した動画（`reel_raw.mp4`）から、Instagramリール用の字幕を自動生成し
動画に焼き込む。参照リポジトリ myuuu-io/youtube の telop-srt-toolkit（Premiere Pro取り込み用
SRT生成が目的）を、無人自動化向けに「動画への焼き込みまで」拡張したもの。

## 必要な環境変数

| キー | 必須 | 用途 |
|---|---|---|
| `OPENAI_API_KEY` | 要 | Whisper API（音声文字起こし） |

プロジェクトルートの `.env` から読む。

## 前提: ffmpegにlibass（subtitlesフィルタ）が必要

`burn_subtitles.py` はffmpegの `subtitles` フィルタ（libass依存）を使う。Homebrewの
標準 `ffmpeg` フォーミュラには **libassが含まれていない**（`brew info ffmpeg` の
Caveatsに明記されている）。実行前に確認すること:

```bash
ffmpeg -filters | grep subtitles
```

何も表示されない場合は、`ffmpeg-full` を導入する:

```bash
brew install ffmpeg-full
```

（`ffmpeg-full` は通常の `ffmpeg` と衝突するため、`brew unlink ffmpeg && brew link ffmpeg-full`
が必要になる場合がある。導入後は必ず `ffmpeg -filters | grep subtitles` で再確認すること）

## パイプライン全体像

```
reel_raw.mp4（reel-production Step 5の出力）
  │
  ├─ Stage 1: 音声抽出
  │     └─ ffmpeg で 16kHz mono 96kbps mp3 に変換（Whisper API 25MB制限内）
  │     ▶ scripts/extract_audio.sh
  │
  ├─ Stage 2: Whisper API 文字起こし
  │     └─ response_format=srt, language=ja で SRT 形式直接取得
  │     ▶ scripts/whisper_srt.py
  │
  ├─ Stage 3-4: 辞書ベース補正・冗長口語削除・スペース整理
  │     ▶ scripts/correct_srt.py
  │        (references/correction-dictionary.md, references/verbose-patterns.md 参照)
  │
  ├─ Stage 5-6: DP 最適分割・後処理
  │     └─ 文末強さ序列で動的計画法分割（リールは min4/ideal12/max18を推奨）
  │     ▶ scripts/dp_split_srt.py (references/caption-grammar.md 参照)
  │
  └─ Stage 7: 動画への焼き込み（新規、No.003/myuuu-io版には無い工程）
        └─ ffmpeg subtitlesフィルタで白文字+黒縁取り、画面下部に焼き込み
        ▶ scripts/burn_subtitles.py
```

## 手順

### Stage 1: 音声抽出

```bash
bash .claude/skills/telop-srt-toolkit/scripts/extract_audio.sh \
  OUTPUT_DIR/reel_raw.mp4 \
  OUTPUT_DIR/reel_16k.mp3
```

30〜60秒のリールなら出力は1MB未満（25MB上限に対し十分な余裕）。

### Stage 2: Whisper文字起こし

```bash
python3 .claude/skills/telop-srt-toolkit/scripts/whisper_srt.py \
  --input OUTPUT_DIR/reel_16k.mp3 \
  --out OUTPUT_DIR/reel_raw.srt \
  --env-file .env
```

### Stage 3-4: 辞書補正・冗長削除

```bash
python3 .claude/skills/telop-srt-toolkit/scripts/correct_srt.py \
  --input OUTPUT_DIR/reel_raw.srt \
  --out OUTPUT_DIR/reel_corrected.srt \
  --dict .claude/skills/telop-srt-toolkit/references/correction-dictionary.md \
  --verbose .claude/skills/telop-srt-toolkit/references/verbose-patterns.md
```

`references/correction-dictionary.md` を読まずに置換辞書を直書きしない。誤認識が
見つかったら都度このファイルに追記していく（初期状態は空）。

### Stage 5-6: DP最適分割

```bash
python3 .claude/skills/telop-srt-toolkit/scripts/dp_split_srt.py \
  --input OUTPUT_DIR/reel_corrected.srt \
  --out OUTPUT_DIR/reel.srt \
  --grammar .claude/skills/telop-srt-toolkit/references/caption-grammar.md \
  --min 4 --ideal 12 --max 18
```

`references/caption-grammar.md` を読まずに文末リストを直書きしない。

### Stage 7: 動画への焼き込み

```bash
python3 .claude/skills/telop-srt-toolkit/scripts/burn_subtitles.py \
  --video OUTPUT_DIR/reel_raw.mp4 \
  --srt OUTPUT_DIR/reel.srt \
  --out OUTPUT_DIR/reel_subtitled.mp4
```

既定スタイルは縦型小画面向け（白文字・黒縁取り太め・画面下寄り）。デザインを変える場合は
`--force-style` を渡す。

## 中間ファイルの取り扱い

| ファイル | 削除タイミング |
|---|---|
| `reel_16k.mp3` | `reel_subtitled.mp4` 完成後（デバッグ用に残してもよい） |
| `reel_raw.srt` / `reel_corrected.srt` | 同上 |
| `reel.srt` | **残す**（最終字幕、確認用） |
| `reel_subtitled.mp4` | **残す**（reel-production Step 7 のBGMミックス入力になる） |

生成物は `output/` 配下に日付フォルダで残るため、明示的な削除は不要（上書き禁止のため
自然に蓄積する）。

## 品質基準

- [ ] 全キャプションが 4〜18 文字以内（リールは横型より短め設定）
- [ ] 文末で切れている（「です」「ます」「ました」末等）
- [ ] 句読点なし（半角スペースで区切り）
- [ ] 冒頭フィラー（「はい」「えーっと」等）が除去済み
- [ ] タイムコードに不整合なし（重複・逆転なし）
- [ ] 動画全編に字幕が表示されている（無音でも内容が伝わる）

このチェックは最終的に `evaluator` サブエージェントがリールのルーブリック内で確認する。
