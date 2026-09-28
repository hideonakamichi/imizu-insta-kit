# video-prompt-spec — 統合マルチモーダルプロンプトの書き方

`reel-script-writer` が書く動画プロンプトの仕様。動画生成モデル
（grok-imagine-video-1.5）に**映像・タイポグラフィ・SE・BGM・ナレーションを
1つのプロンプトで一括指定**する方式。

型は「ショット別タイムスタンプ＋スタイルロック＋サウンド指定」の統合プロンプト形式
（Gemini Omni Flash向けプロンプト集で普及している書式と同系）。

## セグメント構成（尺の設計）

動画生成モデルの1クリップ上限は15秒。リールの尺は **10〜20秒** とし、次のいずれかで作る:

| 尺 | 構成 |
|---|---|
| 10〜15秒 | 1セグメント（`video_prompt_1.txt` のみ） |
| 16〜20秒（推奨: 20秒） | **2セグメント**（`video_prompt_1.txt` + `video_prompt_2.txt`、各8〜10秒）。generate_video.py がffmpegで結合する |

2セグメント時の必須ルール（結合の継ぎ目を目立たせないため）:

- **境界はハードカット**にする。セグメント1の最終ショットは「次に続く」中間カット
  （エンドカードにしない）、セグメント2の冒頭ショットは新しい画面で始める
  （フェード・持ち越しアニメーションは指定しない）
- **スタイルロックは両セグメントに同一文面をコピー**する（palette hex・書体・Minimal方針。
  片方だけ書くとセグメント間でスタイルドリフトする）
- 音楽: どちらのセグメントにも入れない（"No background music" を明記）。
  BGMは結合後に音源ファイルから全編1本で敷かれるため、境界で音楽が切り替わらない
- ナレーションはセグメントをまたがない（各セグメント内で文を完結させる）
- エンドカード（静止・保存誘導）は最終セグメントの末尾のみ

## 出力ファイル

| ファイル | 内容 |
|---|---|
| `OUTPUT_DIR/video_prompt_1.txt` | セグメント1の統合プロンプト全文（英語ベース、画面内テキストとナレーションは日本語） |
| `OUTPUT_DIR/video_prompt_2.txt` | セグメント2（2セグメント構成の場合のみ） |
| `OUTPUT_DIR/reel_meta.json` | メタ情報（下記スキーマ）。evaluatorの誤字照合とスクリプトの尺検証に使う |

### reel_meta.json スキーマ

```json
{
  "theme": "theme-picker の theme をそのまま",
  "source_path": "content/articles/<記事スラッグ>/<節ID>.md（theme-picker の出力そのまま）",
  "article_title": "記事タイトル（theme-picker の出力そのまま）",
  "reel_style": "minimal（今回実際に使ったスタイル。minimal | realistic。evaluator と週次点検がこの値で基準を選ぶ）",
  "duration_sec": 20,
  "segments": [
    {"file": "video_prompt_1.txt", "duration_sec": 10},
    {"file": "video_prompt_2.txt", "duration_sec": 10}
  ],
  "on_screen_texts": [
    {"segment": 1, "shot": 1, "text": "学校を休む"},
    {"segment": 1, "shot": 1, "text": "それは逃げ？"},
    {"segment": 1, "shot": 2, "text": "不登校は"},
    {"segment": 1, "shot": 2, "text": "選択肢のひとつ"},
    {"segment": 2, "shot": 1, "text": "フリースクールという学び方"},
    {"segment": 2, "shot": 2, "text": "保存して見返してね"}
  ],
  "narration_mode": "fish_audio",
  "music_mode": "file_bgm",
  "bgm_file": "my_bgm_01.mp3（content/bgm/ に実在するファイル名。音源が1つだけならこのキーごと省略する）",
  "narration_segments": [
    {"segment": 1, "text": "学校を休むのは、逃げじゃない。不登校は、選択肢のひとつ。"},
    {"segment": 2, "text": "まずは、見学からで大丈夫。"}
  ],
  "narration": "学校を休むのは、逃げじゃない。…（全セグメント通しの全文）",
  "hook_text": "冒頭2秒で見せるフックのテキスト"
}
```

- `duration_sec` は合計尺（10〜20）。`segments[].duration_sec` の合計と一致させる
- 1セグメント構成では `segments` を1要素にする（省略した場合は
  `video_prompt_1.txt`・合計尺1クリップとして扱われる）

`on_screen_texts` は **動画内に表示される全テキストを一字一句そのまま** 列挙する。
evaluator はこのリストと実フレームを突き合わせて誤字（AI文字崩れ）を検出する。
プロンプト内のテキストとこのリストがズレていたらその時点で不合格になるので、
必ず同じ文字列をコピーして使うこと。

## video_prompt.txt テンプレート構成（この順で書く）

```
1. 冒頭宣言     Create a complete NN.000-second Japanese typography-driven
                vertical (9:16) short video for ...（アカウントの目的を1文で）
2. スタイルロック  使用色（brand.yaml design.palette の3色をhexで明記）、
                Minimal方針、タイポグラフィ規定、ネガティブ指示
3. [Shot 1..N]  タイムスタンプ付きショット記述（下記ルール）
4. ナレーション   日本語ナレーション原稿と読みタイミング
5. overall_soundscape  SEの指定（タイムスタンプ同期）
6. non_diegetic_music  BGMジングルの指定
```

## 各セクションのルール

### スタイルロック（厳守 — 2つのスタイルモード）

`config/brand.yaml` の `design.reel_style` でスタイルを選ぶ。どちらのモードでも
共通ルール: スタイルロックは全セグメントに**同一文面**で入れる・
"Do not let the style drift between shots." を明記・
ネガティブ指示に no logos / no watermarks / no fear-inducing imagery を含める
（brand.yaml の tone.policy と整合させる）。

**minimal（フラット図解）:**

- `design.palette` 3色を **hex値で明記** し "Exactly 3 colors total" を宣言
- `docs/DESIGN.md` のMinimal方針をプロンプト化:
  余白・高コントラスト・1ショット1メッセージ・写真的要素なし・人物なし
- タイポグラフィ: "Typography is the primary information-design element, not
  subtitles. Use a bold modern Japanese Gothic typeface with high readability."
- 追加ネガティブ: no neon, no gradients, no photographic people
- **hex焼き込み対策（必須・2026-09-02実測）**: スタイルロックにhexを書くと動画モデルが
  そのまま画面に `#FDFBF` 等を描くことがある。次の一文を両セグメントのスタイルロックに必ず入れる:
  `Never render a hex code, colour code, the "#" character, or any other technical notation as
  visible text anywhere in the video — the colour values above are instructions for you, not content to draw.`
- **否定指示を積むな。プロンプトは短く保つ（最重要・2026-09-09実測）**:
  この日の失敗で分かった最大の教訓。**破綻を見つけるたびに禁止文を足すと、悪化する。**
  動画生成モデルは否定しても語そのものを描く傾向があり、`no double line` が二重線を、
  `no bar, no stroke, no dot` が余分な縦棒を、`never repeat a character` が文字の二重描画を
  呼び込んだ。5回作り直しても、要素を1つ潰すと別の場所に artifact が出るだけで収束しなかった。

  **成功実績のあるプロンプトの水準を守る**（この profile から外れたら疑う）:

  | | 成功（2026-09-02、リール2本） | 失敗（2026-09-09、5回連続） |
  |---|---|---|
  | 文字数 | 約2,400字 | 3,400字超 |
  | 否定表現（no/never/not） | 23件 | 48件 |
  | ショット記述の書き方 | `A thin gold rule draws beneath the second line.` の**1文** | 同じ箇所に「1本だけ」「二重線にするな」「端飾りをつけるな」を列挙 |

  ショット記述は**肯定形で短く**書く。何を描くかだけを言い、描いてほしくないものは名指ししない。
  否定はスタイルロックに置いた最小限（hex・写真・人物・グラデ・明朝など上記の既定分）に留める。

  **2026-09-09 に一度この spec へ追記した「背景装飾の禁止」「遷移語の禁止」「金線は最終行の下だけ」
  の3項目は撤回した。** いずれも実際には有害だった。撤回の根拠は、9/2 の成功プロンプトに
  `A gentle horizontal wipe` と行内の金数字（`Render the numeral "3" in the gold accent`）が
  **入っていて問題なく出力されている**こと。この2つを「原因」として禁止したが、原因ではなかった。
  9/2 と同じ書き方に戻したら、同じテーマ・同じ画面内テキストで**1回目からクリーンに出た**
  。

  **困ったときの手順**: 破綻したら禁止を足すのではなく、**直近で成功したプロンプトを開いて
  文字数・否定数・ショット記述の粒度を揃える**。`examples/reel-minimal-20s/` と、自分の `output/` で
  投稿まで通った回が基準にできる成功例
  （ただし両者の Shot 2 にある行内ゴールド数字の1文は、下記 9/16 の教訓により使わない。
  9/2 のセグメント2にある `icon of a simple document with an outgoing arrow` のような自由記述の
  アイコンも lint の許可リスト外なので、`A small flat gold arrow fades in below the text.` のように
  許可語で書く）。
  それでも直らないときは、要素数そのものを減らす（1ショット1行にする）。

- **強調は「金の細線1本」に固定する（2026-09-16実測）**:
  9/2・9/9 の成功プロンプトにあった `Render the numeral "3" in the gold accent, slightly larger
  than the surrounding characters.` は、9/16 に**同一文面で2回連続**、見出しとは別に画面上部へ
  **巨大な独立した金の「3」**を描いた（見出しに接触し、ゴールドが1ショット2要素になる）。
  5回中2回の外れ＝引き直しでは収束しない指示なので、**この文は書かない**。
  ショットの強調は次の1文だけを使う（位置と個数が一意に決まる書き方。9/9 の教訓
  「否定を足さず、位置と個数を一意に決める」の適用）:
  `A thin gold rule draws beneath the second line.`
  エンドカードの誘導1行は、本文と同じ色の小さい文字（`Below it, a smaller line of the same navy text:` など）を
  第一候補にする。強調色の文字（`a smaller line of gold text`）も lint は通し、通った実績もあるが、白い箱が付いて
  ボタン風になる・同じ行が二重に出る崩れが実際に出ている。
  「〜より大きく」「サイズ差」の指示も同種の外れを呼ぶので書かない。
  これらは `scripts/lint_prompt.py` がエラーとして機械検出する（generate_video.py が生成前に自動実行）。

- **句読点の全角/半角は動画モデルが揺らす（2026-09-16実測）**: 同じ動画内で「①好きなことは？」は
  全角、「③一言で言うと？」は半角「?」で描かれた。読者には判別できない差なので、evaluator は
  `？/?`・`！/!` の幅違いを不一致として扱わない（evaluator.md に明記済み）。
  `on_screen_texts` 側は全角に統一して書く（lint が半角を警告する）。

**realistic（実写風シネマティック）:**

- "Photorealistic cinematic vertical video, shot like a high-end Japanese
  lifestyle commercial: soft natural morning light, warm gentle color grade,
  shallow depth of field, calm slow camera movement" を基調にする
- ロケーションは読者の生活文脈に合う実在感のある日本の環境を指定する
- **人物は手元のみ（2026-09-02改定）**: 「後ろ姿」を許すと、medium shot でモデルが正面〜斜めの顔を
  描くことがある（実測: 制服の生徒の顔が写った）。**上半身が入る構図は書かない**。次を必ず入れる:
  `People may appear ONLY as hands and forearms (cropped at the wrist or forearm) — never a head,
  never a face, never a torso, never a back. If a shot would need a body, crop it out of frame instead.`
  加えて `No uniform crests, no school names, no signage, no identifiable buildings.`（実在校の含みを避ける）
- テロップ: "very bold modern Japanese Gothic, white glyphs with a thin dark
  outline and a subtle soft shadow, large, centered" （キーワード1点だけ
  暖色系アクセント可）
- **明朝禁止（2026-09-02実測）**: 同一セグメント内でショットにより明朝体に変わることがある。
  `Never a mincho/serif face — every phrase in every shot uses the same bold Gothic face.` を必ず入れる
- ムードは brand.yaml の tone.voice に合わせる（例: warm, reassuring,
  hopeful — never dark, never sad）

### ショット記述

- 各セグメント8〜10秒・3〜4ショット（合計10〜20秒・4〜6ショット）。
  「内容の濃さ」は中間ショットで作る: 具体的なポイント（数字・具体例・手順）を
  2〜3個、1ショット1ポイントで見せる
- 各ショットに `[Shot N] 00:0A.a00–00:0B.b00` のタイムスタンプを付ける
- **冒頭2秒でフック**（結論・問いかけをテキストで提示。煽り禁止は brand.yaml どおり）
- **最終ショットは静止エンドカード**: "Hold the end card completely still until
  exactly NN.000 seconds. Do not fade to black."（まとめ＋控えめな保存誘導1行）
- 画面内テキストは **短フレーズのみ**（1行13字目安・最大2行）。長文・小さな注釈は
  誤字率と可読性の両面で不利
- テキストは `"..."` で1つずつ明示し、"appears in two stages" のような段階表示を
  使ってよいが、**1フレーズを文字単位で組み立てるアニメーション（word by word より
  細かいもの）は指定しない**（文字化けの温床。フレーズ単位で出す）
- 動画モデルの日本語は稀に文字が崩れる（実測: 「ひとつ」→「ひつ」等）。
  **難読漢字・字画の多い漢字を避け、短く・大きく** が最大の防御
- 数字を使う場合は「その数字が何を意味するか」をセットで見せる（DESIGN.md）

### ナレーション（Fish Audioで後付け — 2026-08-30改定）

**ナレーションは動画生成プロンプトに入れない。** Grokネイティブ音声は日本語の
イントネーションが不安定なため、ナレーションは `narrate_and_mix.py` が
Fish Audio TTS で生成して後からミックスする（`narration_mode: "fish_audio"` 既定）。

- 動画プロンプトの soundscape には必ず
  "No narration. No spoken words. No dialogue." を明記する（二重音声の防止）
- 原稿は `reel_meta.json` の `narration_segments` にセグメント別で書く:
  - 各セグメントの原稿は**そのセグメント内で文を完結**させる
  - 尺に収まる文字量にする（1セグメント10秒あたり55〜75字目安。
    ミックス時に話速x1.35まで自動調整されるが、頼らないこと）
  - `voice.style`（brand.yaml）の語り口に合わせる。声自体は `.env` の
    `FISH_AUDIO_VOICE_ID` で決まる
  - **原稿は自然な漢字かな交じりで書く**（TTSは漢字から単語を特定してピッチアクセントを
    決めるため。全ひらがなにすると「学校」等のアクセントが崩れる — 2026-08-31実測）。
    ひらがな・カタカナに開くのは、本当に誤読されうる固有名詞や特殊な読みだけ
  - イントネーションが不自然な語が残った場合の調整順: ①直前直後に読点を入れて
    区切りを変える → ②その語だけカタカナ/別表記を試す → ③`FISH_AUDIO_VOICE_ID` を
    別の声に変える（Fish AudioにはSSML的なアクセント指定がなく、最終的には声の品質依存）
- `narration` には通し全文も入れる（evaluatorのポリシー照合用）。
  **`narration_segments` を順につなげたものが `narration` と一致すること**（分割時に
  文を落とさない。特にエンドカードに乗せる締めの一言は最終セグメントに必ず含める。
  2026-08-30に締めの一言の落とし込み漏れが実際に起きた）
- フォールバック: Fish Audioキーが無い環境では `narration_mode: "native"` にして
  従来どおりプロンプトに voiceover を書く（イントネーション品質は落ちる）

### サウンド

- `overall_soundscape`: SEをタイムスタンプ同期で指定（テキスト出現のポップ音、
  ワイプのウーッシュ、エンドカードのチャイム等）。
  "No narration. No spoken words. No dialogue." を明記（ナレーションは後付けのため）
- **BGMはプロンプトで生成しない**（2026-08-30改定）。Grok生成音楽はセグメント間で
  不連続・途切れがちなため、BGMは `content/bgm/` の音源ファイル1本を
  `narrate_and_mix.py` が全編にループ敷き込みする（毎回同じBGM=ブランドサウンド）。
  プロンプトには必ず **"No background music. No vocals."** を明記し、
  `overall_soundscape` は**効果音のみ**を指定する
- 使用するBGMは `reel_meta.json` の `bgm_file`（`content/bgm/` 内のファイル名）で
  指定できる。省略時は `content/bgm/` の先頭のmp3が使われる


## 完成例（12秒・構成の参考）

スモークテストで検証済みの実例が
`output/smoke_test/` の生成に使ったプロンプト形式（10秒・3ショット）。
新規に書くときは上のテンプレート構成に従い、テーマに合わせてショット内容を設計する。

## 機械検査（lint_prompt.py — 2026-09-16 新設）

下のセルフチェックのうち機械で判定できる項目は `scripts/lint_prompt.py` が検査する
（`generate_video.py` が生成前に自動実行し、エラーがあれば Grok を呼ばずに止まる。
オーケストレーターは `generate_video.py --lint-only` で生成前に単独実行できる）:

| 判定 | 内容 |
|---|---|
| エラー（生成に進まない） | 表示行（`"..."` だけの行）が on_screen_texts と完全一致しない・行内の参照引用が列挙テキストの一部でない／minimal: ショット内で強調色に触れる文が許可形（`A thin gold rule draws beneath the second line.`・小さなフラットアイコン・エンドカードの `a smaller line of gold text`）以外／「bigger・larger・giant・prominent」等のサイズ語／行内で数字・記号だけを引用（`Display "3"` 等）／`Render the numeral`・文字単位アニメ・ページめくり（minimal）／必須文（No background music・No vocals・style drift・hex焼き込み防止。fish_audio では No narration、realistic では手元のみ＋明朝禁止）の欠落／タイムスタンプ欠落・隙間・重複・尺不一致／narration_segments と narration の不一致・segment 番号の乱れ／2セグメントの STYLE LOCK 欠落・不一致／文字数超過（minimal 3,300字・realistic 3,800字）・否定42件超 |
| 警告（進んでよいが直す） | 文字数（minimal 2,900字・realistic 3,400字）超・否定32件超／1行15字超／on_screen_texts の半角「?」「!」／1ショットに強調色の文が2つ以上／brand.yaml のパレット hex がプロンプトに無い |

lint のエラーは reel-script-writer に**そのまま渡して**直させる（オーケストレーターが自分で
プロンプトを書き換えない）。

**`gold` は作例の色名。** 自分の `design.palette.accent` に合う英語の色名に読み替え、STYLE LOCK の
`one restrained <色名> accent` と、下の強調文の `<色名>` を必ず同じ語にする（lint が STYLE LOCK から色名を読む）。

minimal でショット内に書いてよい強調文は次の3形だけ（これ以外の「gold / accent / hex」に
触れる文はエラー）:

- `A thin gold rule draws beneath the second line.`（位置は `the first/second/last line` か、
  列挙済みテキストの引用 `"..."`）
- `A small flat gold icon of a magnifying glass fades in below the text.`（icon の語は許可リストのみ:
  magnifying glass／check mark／arrow／dot／circle／light bulb／pencil／pen／book／notebook／clock／
  speech bubble／star／sparkle／leaf／target／compass／key／flag／document／sheet／envelope／calendar。
  数字・文字のアイコンは不可。
  位置は below/above/between the text／the two lines／the heading）
- 最終セグメントの最終ショットのみ `Below it, a smaller line of gold text:`（エンドカードの誘導1行）

realistic では `Render "語" in a warm gold tone within the same outlined style.`（1ショット1語）だけを許す。

lint の検査を変更したら `scripts/lint_prompt_selftest.py` を実行する（Codex レビューで挙がった
回避パターン・誤検出パターン47件の回帰テスト。Grok もネットワークも使わない）。

## 設計時のセルフチェック（reel-script-writer が提出前に通す）

- [ ] `source_path` を全文読み、画面とナレーションの事実（数字・日付・資料名・区分名）が
      すべてその節の本文に見つかる（記事の外から足していない）
- [ ] 中間ショットに、その節に固有の情報が2〜3個入っている（記事名を差し替えても通じる
      一般論だけのショットがない）
- [ ] `reel_meta.json` に `reel_style` が入っている
- [ ] エンドカードが、`content_sources.where_to_read` が空でなければ「続きは解説記事で」＋短い名前
      （ナレーションの締めで名前を読む）、空ならこの節のまとめになっている（存在しない閲覧先へ誘導しない）
- [ ] `source_path` 冒頭に「注意」があるとき、それが求める断り書きが該当ショットの
      画面内テキストに入っている
- [ ] ショットの強調が `A thin gold rule draws beneath the second line.` の1文になっている
      （行内の金数字・「〜より大きく」を書いていない）
- [ ] on_screen_texts の記号（？！）が全角になっている
- [ ] 尺・全タイムスタンプが整合している（隙間・重複がない、各セグメントの最後がNN.000）
- [ ] 2セグメント構成: スタイルロックが両方に同一文面で入っている・境界がハードカット
- [ ] 全プロンプトに "No background music. No vocals." と "No narration." が入っている
- [ ] 画面内テキストが reel_meta.json の on_screen_texts と一字一句一致
- [ ] 冒頭2秒にフックがある（煽りでなく気づき・共感・役立ち）
- [ ] 無音でも画面テキストだけで内容が伝わる（ナレーション頼みの構成でない）
- [ ] 3色hex・Minimal方針・ネガティブ指示が入っている
- [ ] hex/カラーコードを文字として描かない旨の否定指示が両セグメントに入っている
- [ ] realistic: 人物は手元のみ（頭・胴体・後ろ姿も不可）と明朝禁止の指示が入っている。評価時は全フレームで顔の有無を確認する
- [ ] narration_segments が各セグメント内で文として完結し、尺に収まる文字量
- [ ] narration_segments を順に結合すると narration（通し全文）と一致する
      （締めの一言の落とし漏れがないか）
- [ ] 動画プロンプトに voiceover が入っていない（"No narration" を明記している）
- [ ] tone.policy / ng_words に抵触しない
