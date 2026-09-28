# CLAUDE.md — Instagram カルーセル Lite 共通方針

このフォルダで Claude Code を開くと、毎回読み込まれる共通ルール。
カルーセル作りの手順は `.claude/skills/carousel/SKILL.md` にあるので、ここでは
「どの場面でも共通の判断基準」だけを書く。使い方は [README.md](README.md)。

## このキットの目的

自分の文章の1節を根拠に、Instagram 用の図解カルーセルを1本ずつ作る。
AI が作って評価し、合格したものだけを投稿用フォルダにそろえる。**投稿は人がスマホから行う。**

どのアカウントで・誰に・何を発信するかは `config/brand.yaml`、
どの PC・どのモデルで動かすかは `config/runtime.yaml` に書かれている。

## 入口

| 頼まれたこと | 使うスキル |
|---|---|
| 「カルーセル作って」「投稿を1本作って」 | `.claude/skills/carousel/SKILL.md` |
| 「brand-setup で設定して」「ネタを増やしたい」 | `.claude/skills/brand-setup/SKILL.md` |
| 「これは没」「投稿しなかった」 | `record_history.py cancel`（carousel スキルの手順6） |

## 発信ポリシー（厳守）

**作業を始めるときに必ず `config/brand.yaml` を読む。**

| 参照先 | 何を決めるか |
|---|---|
| `account.purpose` | このアカウントが何のために発信するか |
| `audience.who` / `audience.pains` / `audience.vision` | 誰に向けて書くか。刺さる切り口の判断基準 |
| `tone.voice` / `tone.policy` / `tone.ng_words` | 書き方の憲法。**1つでも破ったら投稿用フォルダを作らない** |
| `offer.*` | 売りたいもの。誘導の文言と頻度 |
| `strategy_axes` | テーマの切り口の分類 |
| `hashtags.core` / `hashtags.wide` | キャプションのハッシュタグ |
| `design.palette` | スライドの固定3色 |

`tone.policy` はこのキットの安全弁であり、**司令塔が勝手に緩めてはならない**。
読者の不安を材料にした投稿は、短期の数字が出ても中長期でアカウントの信頼を壊すため、意図的に禁止している。

`brand.yaml` が未設定（雛形の `（...）` や `@your_account` が残っている）のときは作らない。
`check_brand.py` がこれを判定する。司令塔がこの判定を迂回する手段を探してはならない。

## 投稿は「自分の文章の紹介」として作る（厳守）

- 投稿の中身は、`content/sources/` に置いた利用者自身の文章の1節（`## 見出し` の単位）を根拠にする。
  1行のテーマだけから文言を起こすと、どの本にも書いてある一般論になり中身が薄くなる
- `theme-picker` が返す **`source_path` を、構成・キャプション・evaluator の全員に渡す。**
  画面・キャプションに書く事実は、その節の本文にあるものだけ。自分の知識で補わない
- `source_path` 冒頭に「注意（この節を扱うときの縛り）」があれば、全員がそれに従う
- 索引が無い・読めないときは作らない

## 役割とモデル

| 役割 | 誰がやるか | モデル |
|---|---|---|
| 司令塔（進行・構成の設計） | このセッション | Claude Code で選んでいるモデル（`/model` で切り替え） |
| ネタ選び | `theme-picker` | `config/runtime.yaml` の `models.theme_picker` |
| キャプション | `caption-writer` | `config/runtime.yaml` の `models.caption_writer` |
| 評価 | `evaluator` | `config/runtime.yaml` の `models.evaluator` |
| スライドの描画 | `banner.py`（Pillow） | AI を使わない。同じ構成なら毎回同じ絵 |

サブエージェントを呼ぶときは、`runtime.yaml` の値を `model` に渡す。評価役を生成役と分けているのは、
作った本人は自分の誤りに気づきにくく、**生成より判定の失敗の方が高くつく**（悪い投稿が世に出る）ため。

**司令塔はメインセッションのままにし、サブエージェントにしない。** サブエージェントは自分の中から
さらにサブエージェントを呼べないので、司令塔をサブエージェントにすると evaluator を起動できなくなる。

## 生成→評価→直すループ（厳守）

```
生成 → evaluator が合否判定
  → 合格: 次へ
  → 不合格: 修正指示に沿って、該当の箇所だけ直してもう一度（最大2回）
  → 2回で合格しない: 投稿用フォルダを作らずに止め、何が通らなかったかを人に伝える
```

上限は `config/loop-limits.yaml`。ここに書かれた上限を勝手に緩めない（やり直すたびに Claude の利用量がかかる）。

## コマンドの実行（厳守）

- Python の呼び方は `config/runtime.yaml` で決まる（Windows: `py` / Mac: `python3`）
- **Bash ツールで**、`PY .claude/skills/...` の**相対パス**のまま実行する。`.claude/settings.json` の許可は
  この形で登録してあり、絶対パスにすると一致しない。Windows でも PowerShell ツールは使わない
  （スクリプトの出力は UTF-8。PowerShell では日本語が化ける）
- 権限で止められたら、形を変えての再試行は1回まで。それでも止まったら、止まったコマンドを人に伝える

## 止めるとき

- どの段階でも、通らなければ「投稿用フォルダを作らない」に倒す
- 生成物は `output/YYYY-MM-DD_<テーマ>/` にそのまま残す（人が見返して手で直せる）
- 何が・どの段階で・なぜ通らなかったかを人に伝える

## 重複を防ぐ

`theme-picker` は `content/articles/index.json`（ネタの索引）と `logs/history.jsonl`（作成履歴）を照合し、
直近14日に使った節と、直近2件で紹介したネタ元を避ける。履歴に記録する `theme` は theme-picker の出力を
一字一句そのまま使う（照合はこの文字列の一致で行われる）。

## 外してある機能

自動投稿・リール・定期実行は `addons/` に置いてある（まだ Mac 専用）。本体からは呼ばない。
