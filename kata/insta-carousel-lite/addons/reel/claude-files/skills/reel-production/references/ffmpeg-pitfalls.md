> **レガシー文書**: 旧スライド式リール手順（`legacy-slide-pipeline.md`）専用。
> 現行のフル動画生成方式では使わない。

# ffmpeg のハマりどころ（No.003から踏襲）

`assemble_video.py` / `mix_bgm.py` はすでにこれらの対策込みで実装済み。改修時に対策を
崩さないよう、理由をここに残す。

## 1. `-shortest` を使わない。`-t {audio_dur}` で明示的に時間を切る

`-loop 1`（静止画ループ）+ `-shortest` の組み合わせは、AAC encoderのlookahead delayの
影響で **video streamが音声長より数百ms〜数秒長く出力される既知の挙動** がある。
これが複数セグメントで累積すると、スライドの変わり目に「静止画＋無音」の死区間が残る。

対策（`assemble_video.py` の `build_segment()` 内）:
1. セグメント生成前に `ffprobe` で音声の実測durationを取得
2. `-t {audio_dur:.6f}` で動画長を音声長と完全一致させる
3. 生成後に再度ffprobeで測り、差が100msを超えたら異常終了

## 2. `amix` は `normalize=0` を明示する

ffmpegの `amix` フィルタはデフォルト `normalize=1`（入力数で割って正規化）。BGMミックスで
これを使うと、「ナレーションにBGMを重ねる」のではなく「2つを均等に混ぜる」挙動になり、
**ナレーション音量が半分（-6dB）に落ちる**。

対策（`mix_bgm.py` のfilter_complex）:
```
[1:a]volume=-27dB,afade=t=out:st={fadeout_start}:d={fadeout}[bgm];
[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]
```
`dropout_transition=0` も必須（入力ストリーム終了の誤検知による音量変動を防ぐ）。

検算: `ffmpeg -af volumedetect` でmean_volumeが元動画と概ね一致するか確認する。
-6dB下がっていたら `normalize=0` が抜けているバグ。

## 3. 縦型（9:16）へのscale時はcrop込みで整形する

gpt-image-2の縦長生成サイズは `1024x1536`（2:3、0.667）だが、Instagramリールの規定は
`1080x1920`（9:16、0.5625）。単純な `scale=1080:1920` だけだと縦横比が歪むため、
`assemble_video.py` では以下の2段構えで整形する:

```
scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920
```

`force_original_aspect_ratio=increase` で短辺を基準に拡大してから、`crop` で中央を
切り出す。これにより歪みなく1080x1920に収まる（`generate_slides.py` 側で
テキストをセーフゾーン内に収める指示を入れているのは、この後段クロップで
端が切られる前提のため）。

## 4. slide_id を全ファイルの単一の真実源（SOT）にする

過去、画像1-indexed・音声0-indexedのズレが発生した事例がある。これを防ぐため:

- 画像: `slides/slide_{slide_id:03d}.png`
- 音声: `audio/slide_{slide_id:03d}.mp3`
- 配列インデックスをファイル名の番号に使うことを禁止。必ず `slide_id` を継承する
- 各段階の完了後に必ず `check_consistency.py` を実行し、戻り値が0でなければ次工程に進まない
