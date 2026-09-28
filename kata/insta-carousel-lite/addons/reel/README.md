# 追加パック: リール（reel）

10〜20秒の縦型動画を作ります。映像は Grok、ナレーションは Fish Audio、BGM は手持ちの音源です。

## 中身

フォルダ名は `claude-files/` にしてあります（`.claude/` のままだと、Claude Code が本体を開いたときにこのパックのスキルまで読み込むため）。
足すときは、中身をキットの `.claude/` の同じ場所へ移します。

| ファイル | 役割 |
|---|---|
| `claude-files/skills/reel-production/` | リールの手順と、動画生成・ナレーション・結合・台本の機械検査のスクリプト |
| `claude-files/skills/telop-srt-toolkit/` | 字幕（テロップ）づくりの道具 |
| `claude-files/skills/shared/scripts/grok_media.py` | Grok CLI を呼ぶ共通部品 |
| `claude-files/agents/reel-script-writer.md` | 台本を書くエージェント |
| `claude-files/orchestrators/` | リールの司令塔の指示書（minimal と realistic） |
| `content/bgm/` | BGM の置き場所の説明（音源は含まない） |
| `examples/` | 台本の作例 |

## 要るもの

- SuperGrok か X Premium+ のサブスクと、Grok CLI（`grok login`）
- Fish Audio（ナレーションの文字数に応じた従量課金）
- ffmpeg、Python ライブラリ `fish-audio-sdk`
- 商用利用できる BGM 音源

## 注意

フル版の実績では、リール minimal は7回中2回しか投稿まで行きませんでした（台本の機械検査を入れたあとは3回中2回）。
realistic（実写風）は、指示しても人の顔が描かれた実測があります。使う前に `../_original/README.md` の
「realistic を使う前に」を読んでください。

評価役（`evaluator.md`）のリール用の基準は、Lite 版では外してあります。フル版の評価基準は `../_original/evaluator-full.md` にあります。
