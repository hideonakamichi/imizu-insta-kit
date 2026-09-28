# legacy-slide-pipeline — 旧リール生成手順（スライド式）の退避文書

**2026-08-30の設計変更で既定経路から外れた旧手順。** 現行の既定は
`SKILL.md`（Grok CLIによる10〜20秒フル動画生成）。この文書は、フル動画生成が
使えない場合のフォールバック手段として旧手順（スライド生成→TTS→ffmpeg結合、
30〜60秒）を残すもの。スクリプト群（generate_slides.py / overlay_text.py /
audio_generate.py / assemble_video.py / mix_bgm.py / extract_narration.py /
check_consistency.py）はすべて温存されている。

注意: 旧手順の generate_slides.py は OpenAI API（OPENAI_API_KEY）、
audio_generate.py は Fish Audio（FISH_AUDIO_API_KEY）を必要とする。
また reel-script-writer は現行定義では slides.json を書かないため、
この手順に戻す場合はエージェント定義の巻き戻しも必要。

---

# reel-production

テーマから30〜60秒の縦型リール動画（1080x1920、MP4）を生成する手順。
参照リポジトリ myuuu-io/youtube の No.003（16:9・14分の教材動画パイプライン）を、
短尺・縦型向けに簡略化したもの。

**字幕（テロップ）は使わない**（2026-07-20の設計変更）。スライド本文と字幕が併存すると
縦型では視線移動が多く視聴ストレスになり、スライド切替と字幕切替のタイミングズレも
ノイズになる、というユーザーフィードバックによる。代わりに各スライドの
`headline_text` + `sub_text` だけで無音でも内容が完結するようにする
（`references/slides-json-spec.md` 参照）。`telop-srt-toolkit` スキルはこのパイプラインでは
呼ばない。

## 前提

- 台本と `slides.json` の作成は `reel-script-writer` サブエージェント（Sonnet）が行う
- 縦型・短尺化に伴い、No.003にあった「Stage 0リサーチ」「structure-reviewerによる
  構成案審査ループ」は行わない（テーマは既にtheme-pickerが選定済み、構成の妥当性は
  最終的にevaluatorが見る）
- 番号体系は `slide_id` を全ファイルの単一の真実源（SOT）とする（詳細:
  `references/ffmpeg-pitfalls.md` 4項）

## 作業ディレクトリ

`output/<YYYY-MM-DD>_<テーマスラッグ>/` を `OUTPUT_DIR` とする。

```
OUTPUT_DIR/
├── slides.json                # SOT
├── slides/slide_NNN.png       # 縦型スライド画像（イラスト+PILテキスト焼き込み済み）
├── slides/raw/slide_NNN.png   # 文字なしイラスト原本（テキストだけ直すとき再利用）
├── audio/
│   ├── slide_texts.json       # narration_text抽出
│   └── slide_NNN.mp3
├── reel_raw.mp4                # 画像+音声結合（BGM前）
└── reel_final.mp4              # BGMミックス後（投稿用）
```

## 手順

### Step 1: 台本・slides.json 生成

`reel-script-writer` サブエージェントに、選定済みテーマを渡して依頼する。
`references/slides-json-spec.md` の仕様（TTS変換ルール・headline文字数制約含む）に
必ず従わせる。出力は `OUTPUT_DIR/slides.json`。

### Step 2: スライド画像生成

画像モデルは**文字なしイラストのみ**を生成し（`slides/raw/` に保存）、
headline_text / sub_text はスクリプト内で自動的にPILで焼き込まれる（`slides/slide_NNN.png`）。
テキストの位置・サイズ・折り返し・セーフゾーンはコードで決定論的に保証されるため、
プロンプトでの文字制御は不要（AIに文字を描かせると幅制約を守らず左右見切れが再発するため廃止した）。

```bash
python3 .claude/skills/reel-production/scripts/generate_slides.py \
  --slides-json OUTPUT_DIR/slides.json \
  --out-dir OUTPUT_DIR/slides \
  --concurrency 4 --quality medium
```

失敗したら `config/loop-limits.yaml` の `image_generation_retry`（最大3回）に従って
リトライする。3回で揃わなければ投稿せず中止。

**テキストだけ修正したい場合**（誤字修正・文言変更など）: イラスト再生成は不要。
slides.json を直してから overlay_text.py を再実行する（APIコストゼロ・数秒で完了）:

```bash
python3 .claude/skills/reel-production/scripts/overlay_text.py \
  --slides-json OUTPUT_DIR/slides.json \
  --slides-dir  OUTPUT_DIR/slides --ids <対象id>
```

整合性チェック:
```bash
python3 .claude/skills/reel-production/scripts/check_consistency.py \
  --slides-json OUTPUT_DIR/slides.json \
  --slides-dir  OUTPUT_DIR/slides
```

### Step 3: ナレーションテキスト抽出

```bash
mkdir -p OUTPUT_DIR/audio
python3 .claude/skills/reel-production/scripts/extract_narration.py \
  --slides-json OUTPUT_DIR/slides.json \
  --out-json OUTPUT_DIR/audio/slide_texts.json
```

### Step 4: 音声生成（1.5倍速）

```bash
python3 .claude/skills/reel-production/scripts/audio_generate.py \
  --texts OUTPUT_DIR/audio/slide_texts.json \
  --out-dir OUTPUT_DIR/audio \
  --tempo 1.5
```

`--tempo 1.5` は必須（リールのテンポ改善のため。atempoフィルタなのでピッチは自然なまま）。
音声素材の段階で倍速化するので、後続の動画結合は音声実測長で自動的に追従する。
`config/loop-limits.yaml` の `tts_generation_retry`（最大3回）に従う。

整合性チェック（画像・音声・テキストすべて）:
```bash
python3 .claude/skills/reel-production/scripts/check_consistency.py \
  --slides-json OUTPUT_DIR/slides.json \
  --slides-dir  OUTPUT_DIR/slides \
  --audio-dir   OUTPUT_DIR/audio \
  --slide-texts-json OUTPUT_DIR/audio/slide_texts.json
```
戻り値が0でなければ、Step 5に進まず原因を修正する。

### Step 5: 動画結合（1080x1920）

```bash
python3 .claude/skills/reel-production/scripts/assemble_video.py \
  --slides-json OUTPUT_DIR/slides.json \
  --slides-dir  OUTPUT_DIR/slides \
  --audio-dir   OUTPUT_DIR/audio \
  --out         OUTPUT_DIR/reel_raw.mp4
```

ffmpegのハマりどころ（`-shortest`禁止・crop込みscale）は `references/ffmpeg-pitfalls.md` を参照
（スクリプトにすでに実装済み、崩さないこと）。

### Step 6: BGMミックス

BGMは `content/bgm/` に置かれた `.mp3` から1つ選ぶ。複数ある場合は、直近のリールで
使っていないものを優先する（毎回同じ曲だと単調になるため）。

```bash
python3 .claude/skills/reel-production/scripts/mix_bgm.py \
  --video OUTPUT_DIR/reel_raw.mp4 \
  --bgm content/bgm/<選んだファイル>.mp3 \
  --db -27 \
  --out OUTPUT_DIR/reel_final.mp4
```

**`--db -27` を既定とする。** 経緯: -10dB → 実投稿で「大きすぎ」→ -15dB → それでも
「まだ大きい、-25〜-30dBを指標に」というフィードバックを経て、中央値の-27dBに落ち着いた。
ナレーションを邪魔しないことが最優先。使う音源の音圧によっては微調整してよいが、
**まず-27dBで1本作って実際に聴いてから**変えること（数値だけで判断しない）。

`content/bgm/` が空の場合は、BGMなしで `reel_raw.mp4` を `reel_final.mp4` として
そのまま使う（音源の用意については `content/bgm/README.md` を参照）。

### Step 7: 評価（実フレーム必須）

まず完成動画から評価用フレームを抽出する（**スライド元画像だけで評価してはならない**。
9:16変換時の左右クロップによる見切れは、実フレームでしか検出できない。Phase 2の初回
投稿で見出しの左右見切れがこの理由ですり抜けた実例あり）:

```bash
python3 .claude/skills/reel-production/scripts/extract_frames.py \
  --video OUTPUT_DIR/reel_final.mp4 \
  --out-dir OUTPUT_DIR/frames
```

`evaluator` サブエージェントに **抽出したフレーム（OUTPUT_DIR/frames/）** と
slides.jsonを渡し、リールのルーブリック（冒頭2秒フック・無音でもスライドの文字だけで
内容が伝わるか・セーフゾーン・テキスト見切れなし・音声映像整合・尺30〜60秒）で判定させる。

- 合格: `caption-writer` に進み、`.claude/skills/instagram-publishing/SKILL.md` で投稿
- 不合格: 指摘内容に応じて該当ステップをやり直す。`config/loop-limits.yaml` の
  `reel_evaluation`（最大2回）に従う。修正範囲は最小で選ぶ:
  - **テキストの問題**（文言・誤字・長すぎ）→ slides.json修正 → overlay_text.py 再実行のみ
    （イラスト再生成不要・APIコストゼロ）→ Step 5から再結合
  - **イラストの問題**（構図・不適切な描写）→ 該当idだけ Step 2 で再生成
  - **台本の問題** → Step 1 から
- 2回で合格しない場合: 投稿せず中止し、`CLAUDE.md` の失敗時ルールに従って
  `OUTPUT_DIR` を残したままDiscordに通知する

## 出力

- `output/<日付>_<テーマ>/reel_final.mp4`（1080x1920、BGM込み・字幕なし、投稿用）
- 中間生成物（slides.json、slides/、audio/、reel_raw.mp4等）は同ディレクトリに保持
  （デバッグ・再生成用）
