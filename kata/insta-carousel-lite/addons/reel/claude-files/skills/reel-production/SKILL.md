---
name: reel-production
description: テーマから縦型（9:16）のInstagramリール動画を生成する手順。統合マルチモーダルプロンプト（ショット別タイムスタンプ・タイポグラフィ・SE/BGM/ナレーション込み）を設計し、Grok CLI経由のフル動画生成で10〜20秒・音声込みのMP4を作る（16秒以上は2セグメント生成→ffmpeg結合）。リール投稿パイプラインで、theme-pickerがテーマを選んだ直後に使う。
---

# reel-production

テーマから10〜20秒の縦型リール動画（9:16、音声込みMP4）を生成する手順。

**2026-08-30の設計変更**: 従来の「スライド画像生成→TTS→ffmpeg結合」方式（30〜60秒）から、
**統合マルチモーダルプロンプトによるフル動画生成**（Grok CLI / grok-imagine-video-1.5）に
移行した。Grokが生成するのは映像・画面内タイポグラフィ・**効果音**。
**ナレーションはFish Audio TTS**（Grokネイティブ音声は日本語イントネーションが不安定）、
**BGMは `content/bgm/` の固定音源1本**（Grok生成音楽はセグメント間で不連続になりがち）を
それぞれ後付けミックスする。
旧方式は `references/legacy-slide-pipeline.md` にフォールバック手段として温存してある。

## 前提

- 統合プロンプトの設計は `reel-script-writer` サブエージェント（Sonnet）が行う。
  仕様は `references/video-prompt-spec.md`（厳守）
- 尺は10〜20秒・既定20秒。動画生成1クリップの上限が15秒のため、16秒以上は
  2セグメント（各8〜10秒）を生成してffmpegで結合する（継ぎ目の設計ルールは
  video-prompt-spec.md「セグメント構成」）
- 動画モデルの日本語文字は稀に崩れる（実測: 「ひとつ」→「ひつ」等）。
  そのため evaluator が `reel_meta.json` の `on_screen_texts` と実フレームを
  一字一句照合する。誤字が出たら再生成で吸収する

## 作業ディレクトリ

`output/<YYYY-MM-DD>_<テーマスラッグ>/` を `OUTPUT_DIR` とする。

```
OUTPUT_DIR/
├── video_prompt_1.txt  # セグメント1の統合プロンプト（SOT）
├── video_prompt_2.txt  # セグメント2（16秒以上の場合）
├── reel_meta.json      # 尺・セグメント定義・画面内テキスト一覧・ナレーション原稿
├── segment_N.mp4       # セグメント生成物（中間）
├── reel_video.mp4      # 結合済み動画（ナレーションなし・音楽+SE入り）
├── narration_segN.mp3  # Fish Audioナレーション（中間）
├── reel_final.mp4      # ナレーションミックス済み（投稿用）
└── frames/             # 評価用抽出フレーム
```

## 手順

### Step 1: 統合プロンプト設計

`reel-script-writer` サブエージェントに theme-picker の出力一式（`theme`・`source_path`・
`article_title`・`short_title`・`section_heading`・`has_caution`）を渡し、
**`source_path`（記事の節の根拠テキスト）を読んだうえで**
`OUTPUT_DIR/video_prompt_1.txt`（＋16秒以上なら `video_prompt_2.txt`）と
`OUTPUT_DIR/reel_meta.json` を作らせる。
`references/video-prompt-spec.md` の仕様に必ず従わせる。

### Step 1.5: プロンプトの機械検査（生成前・2026-09-16 新設）

```bash
python3 .claude/skills/reel-production/scripts/generate_video.py \
  --meta OUTPUT_DIR/reel_meta.json \
  --out OUTPUT_DIR/reel_video.mp4 --lint-only
```

- `lint_prompt.py` が on_screen_texts とプロンプトの一致・危険な書き方（行内数字の強調、
  サイズ差、文字単位アニメ）・必須文・タイムスタンプ・ナレーション整合を検査する
  （項目は video-prompt-spec.md「機械検査」）。Grok は呼ばないので数秒で終わる
- **エラー（exit≠0）なら生成に進まず、出力をそのまま `reel-script-writer` に渡して直させる**
  （`config/loop-limits.yaml` の `prompt_lint`: 最大2回。直らなければ投稿せず中止）。
  オーケストレーター自身がプロンプトを書き換えない
- 警告のみなら進んでよい。Step 2 の generate_video.py も生成前に同じ検査を自動実行する

### Step 2: 動画生成（セグメントごとに1コマンド）

**1回のBash呼び出しは600秒以内に収める必要があるため（headless制約）、
セグメントを1つずつ生成する。** 最後のセグメント生成時に全セグメントが揃うと
自動的に結合されて `reel_video.mp4`（＝`--out` で指定した名前）ができる。

`reel_final.mp4` は次の Step 2.5 でナレーションを重ねた**投稿用ファイル**の名前。
`--out` にこの名前を指定すると Step 2.5 の入力と出力が同じになり、
ナレーションなしの動画が投稿用ファイルを上書きしてしまうので注意する。

```bash
python3 .claude/skills/reel-production/scripts/generate_video.py \
  --meta OUTPUT_DIR/reel_meta.json \
  --out OUTPUT_DIR/reel_video.mp4 --only-segment 1
```

```bash
python3 .claude/skills/reel-production/scripts/generate_video.py \
  --meta OUTPUT_DIR/reel_meta.json \
  --out OUTPUT_DIR/reel_video.mp4 --only-segment 2
```

（1セグメント構成なら `--only-segment` なしで1回だけ実行してよい）

- 内部でGrok CLI（`grok` ヘッドレス）を呼び、セグメントごとに 9:16／尺±2秒／
  音声トラックあり、結合後に合計尺をffprobeで機械検証する。検証NGは非0終了
- **必ずフォアグラウンド・Bash timeout 600000ms で実行する**（`run_in_background` 禁止）。
  1セグメントの生成は通常2〜5分
- 失敗したら `config/loop-limits.yaml` の `video_generation_retry`（最大2回）に従い、
  **失敗したセグメントだけ** `--only-segment N` で再実行する。
  2回で成功しなければ投稿せず中止

### Step 2.5: BGM敷き込み＋ナレーション生成＋ミックス

```bash
python3 .claude/skills/reel-production/scripts/narrate_and_mix.py \
  --meta OUTPUT_DIR/reel_meta.json \
  --video OUTPUT_DIR/reel_video.mp4 \
  --out OUTPUT_DIR/reel_final.mp4
```

- BGM: `content/bgm/` の音源（`reel_meta.json` の `bgm_file` で指定、省略時は先頭のmp3）を
  全編に1本ループ敷き込みする（クロスフェードループ・-23 LUFS・末尾フェードアウト）。
  Grokに音楽を作らせないのは、セグメント間で不連続になるため（動画側の音声はSEのみ）
- ナレーション: `narration_segments` をFish Audio TTSで音声化し、各セグメントの
  時間窓に自動フィット（話速調整は最大x1.35）させる
- ミックス: BGMは全編一定音量（-23 LUFS）でナレーション中も下げない
  （ナレーション-15 LUFSとの音量差で聞き取りを確保。`reel_meta.json` に
  `"ducking": true` を入れると旧来の自動ダッキングに戻せる）。
  `narration_mode: "native"` の場合はコピーのみ
- TTSに失敗したら `config/loop-limits.yaml` の `tts_generation_retry`（最大3回）。
  「ナレーションが長すぎます」エラーは reel-script-writer に原稿短縮を依頼して再実行
- ミックスだけやり直す場合（BGMバランス調整等）は `--skip-tts` で生成済み
  ナレーションを再利用できる（TTS課金なし）

### Step 3: 評価用フレーム抽出（実フレーム必須）

```bash
python3 .claude/skills/reel-production/scripts/extract_frames.py \
  --video OUTPUT_DIR/reel_final.mp4 \
  --out-dir OUTPUT_DIR/frames
```

**映像スタイルが realistic のときは `--interval 0.5` を付ける**（顔の取りこぼしを減らすため。
`.claude/orchestrators/reel-orchestrator.md`「映像スタイルが realistic のとき」）。

**生成プロンプトだけで評価してはならない。** 誤字・見切れ・スタイルドリフトは
実フレームでしか検出できない。

### Step 4: 評価

`evaluator` サブエージェントに以下を渡し、リールのルーブリックで判定させる:

- `OUTPUT_DIR/frames/` の抽出フレーム
- `OUTPUT_DIR/reel_meta.json`（画面内テキストの照合元）
- `OUTPUT_DIR/reel_final.mp4`（音声品質の確認用）
- `OUTPUT_DIR/video_prompt_N.txt`（全セグメント。evaluator が `cause` を切り分けるのに必須）
- theme-picker が返した `source_path`（記事の節。画面・ナレーションの事実を記事と照合するため）
- 再評価（2回目）では、前回の evaluator 出力と「何を変えたか（改訂したセグメント・再生成した
  セグメント・原稿の変更）」も渡す

判定と分岐:

- **合格**: `caption-writer` に進み、`.claude/skills/instagram-publishing/SKILL.md` で投稿
- **不合格**: `config/loop-limits.yaml` の `reel_evaluation`（最大2回）に従い、
  evaluator が返す `failed_items`（項目ごとの `cause` / `retry_action` / `segment`）**のとおりに**
  最小範囲でやり直す（上限2回＝やり直しは実質1回。分類を自分で上書きしない）。
  **複数の項目があれば全部を済ませてから再評価する**（片方だけ直して再評価に回すと、
  残った不合格で2回目も落ちて中止になる）。`failed_segments`（和集合）は生成対象の決定には
  使わず、**項目ごとの `retry_action` と `segment` から次の順で対象を決める**:

  1. **改訂（`revise_prompt`）**: 該当項目の `segment` を集める。`segment: null`（全体項目:
     スタイル不一致・ポリシー等）が1件でもあれば**全セグメント**が対象。
     `reel-script-writer` に evaluator の指摘をそのまま渡し、**その指示を削って要素数を減らす**
     改訂を依頼（禁止文の追加は不可。video_prompt.txt と reel_meta.json の両方を整合させる）
     → Step 1.5 の lint を通す。`cause: prompt_induced` は**不合格の要素がプロンプトで名指し
     した要素と対応している**場合（例: 金色の数字を指示→巨大な金の数字）
  2. **生成対象 = 改訂したセグメント ∪ `regenerate_segment` 項目の `segment`**（重複を除き、
     各セグメントを**1回だけ** `--only-segment N` で生成。改訂済みのセグメントを別項目の
     引き直しで二度生成しない）。`regenerate_segment`（`cause: generation_miss`。プロンプトの
     どの語とも対応しない偶発的な字形崩れ・欠け）はプロンプトそのままで引き直す。
     **同一プロンプトでの引き直しは同じセグメントにつき1回まで**。再生成後に同じ不合格が
     再現したら、それは prompt_induced だったということ（上限に達していれば中止）。
     不合格でないセグメントは作り直さない
  3. **ナレーション（`revise_narration`）**: 原稿を `narration_segments`（と通し全文
     `narration`）で調整する。動画の再生成は不要
  4. **Step 2.5 のミックス → Step 3 のフレーム抽出 → 再評価**。
     **`--skip-tts` は `narration_segments` と音声設定（voice.style / `bgm_file` / `ducking`）を
     一切変えていないときだけ**使う（既存MP3をそのまま流用するため、原稿を直したのに付けると
     旧原稿の音声が残る）。原稿を1文字でも変えたら `--skip-tts` なしで TTS から再実行する
- **2回で合格しない場合**: 投稿せず中止し、`CLAUDE.md` の失敗時ルールに従って
  `OUTPUT_DIR` を残したままDiscordに通知する

### Step 5: 投稿へ

合格した `reel_final.mp4` の絶対パスと `reel_meta.json`、`source_path` を `caption-writer` →
`instagram-publishing` に渡す（リール手順は従来どおり）。

## 出力

- `OUTPUT_DIR/reel_final.mp4`（9:16・10〜20秒・音声込み、投稿用）
- 中間生成物（video_prompt_*.txt、reel_meta.json、segment_*.mp4、frames/）は同ディレクトリに保持
  （デバッグ・再生成用）
