# CLAUDE.md — Instagram自動投稿システム 共通方針

このファイルは、launchd から起動される **オーケストレーター**（メインセッション、`claude -p --model opus`）が
毎回読み込む共通ルール。パイプラインごとの実行手順は各スキルの `SKILL.md` にあるので、ここでは
「どのパイプラインでも共通の判断基準」だけを書く。

セットアップ手順は [README.md](README.md) を参照。

## このシステムの目的

Instagramアカウントに、図解カルーセル・解説ショート動画を人手ゼロで継続投稿する。
生成 → 評価 → 投稿 → 記録 → 通知までを1回の起動で完走させる。

**どのアカウントで・誰に・何を発信するかは `config/brand.yaml` に書かれている。**
このファイルはジャンルに依存しない共通ルールだけを扱う。

## 発信ポリシー（厳守 — 全コンテンツ共通）

**作業開始時に必ず `config/brand.yaml` を読み込むこと。** 以下はそこから適用する:

| 参照先 | 何を決めるか |
|---|---|
| `account.purpose` | このアカウントが何のために発信するか |
| `audience.who` / `audience.pains` / `audience.vision` | 誰に向けて書くか。刺さる切り口の判断基準 |
| `tone.voice` / `tone.policy` / `tone.ng_words` | 書き方の憲法。**1つでも破ったら投稿しない** |
| `offer.*` | 売りたいもの。CTAの文言と、誘導を入れる頻度 |
| `strategy_axes` | テーマの切り口の分類 |
| `hashtags.core` / `hashtags.wide` | キャプションのハッシュタグ |
| `design.palette` | 画像生成に使う固定3色 |

`brand.yaml` の `tone.policy` はこのシステムの安全弁であり、**オーケストレーターが勝手に
緩めてはならない**。読者の不安を材料にした投稿は、短期の数字が出ても中長期でアカウントの
信頼を壊すため、意図的に禁止している。

`brand.yaml` が未設定（雛形の `（...）` や `@your_account` が残っている・必須項目が空）のときは投稿しない。
これは指示文ではなく**スクリプトが止める**: `bin/run-agent.sh` が起動前に `check_brand.py` を実行して
投稿パイプラインを起動せず、`ig_post.py` も API を呼ぶ前に同じ検証と、トークンのアカウントが
`account.handle` と一致するかの確認をする。オーケストレーターがこの検証を迂回する手段を探してはならない
（検証に落ちたら、その旨を通知して終了する）。

## モデル割り当て（厳守）

| 役割 | モデル |
|---|---|
| オーケストレーター（このセッション自身） | Opus |
| `evaluator` サブエージェント・週次点検 | Opus |
| `theme-picker` / `reel-script-writer` / `caption-writer` サブエージェント | Sonnet |
| 画像生成（カルーセル） | **Pillow による決定論的描画**（`banner.py` → `render_slides.py`。AIを使わない） |
| 動画生成（リールの映像+SE） | Grok（`grok` CLI経由。スクリプトが内部で呼ぶ） |
| リールのナレーション音声 | Fish Audio TTS（`narrate_and_mix.py` が呼ぶ。日本語イントネーションのため） |
| リールのBGM | `content/bgm/` に置いた音源ファイル（生成しない。`narrate_and_mix.py` がミックスする） |

サブエージェントのモデルは各定義ファイル（`.claude/agents/*.md`）のフロントマターで固定済み。
呼び出し時に上書きしない。評価役だけをOpusに残すのは、**生成より判定の方が失敗コストが
高い**（悪い投稿が世に出てしまう）ため。

動画の生成はAPI従量課金ではなく **Grok CLI（SuperGrok/X Premium+サブスクの
サインイン、`~/.grok/auth.json`）** で行う。生成スクリプト（generate_video.py）が内部で
`grok` をヘッドレス起動するため、オーケストレーターが `grok` を直接叩く必要はない。
サインイン失効時はリール生成が失敗する（週次点検の check_grok.py が検知する。対処は `grok login`）。

**カルーセルの画像は 2026-09-11 から画像生成AIを使わない。** `banner.py` が spec の文字を
Pillow でそのまま描く（ヒラギノ角ゴシック固定・座標指定）。画像生成AIに日本語の文字組みを
させる方式は1枚あたりの合格率が20〜30%しかなく、5枚すべてを上限内で通せる確率が
1〜3割だったため（経緯は `.claude/skills/banner-production/references/carousel-spec.md`）。
evaluator は引き続き通すが、役割は「文言・発信ポリシー・構成」の判定に絞られる。

## パイプラインの入口

すべてのパイプラインは `bin/run-agent.sh <slug>` で起動される。起動されたメインセッションは
`.claude/orchestrators/<slug>.md`（オーケストレーターの職務記述書）を読み、それに従う。

| slug | 職務記述書 | 手順の実体 |
|---|---|---|
| `banner-orchestrator` | `.claude/orchestrators/banner-orchestrator.md` | `.claude/skills/banner-production/SKILL.md` → `.claude/skills/instagram-publishing/SKILL.md` |
| `reel-orchestrator` | `.claude/orchestrators/reel-orchestrator.md` | `.claude/skills/reel-production/SKILL.md` → `.claude/skills/instagram-publishing/SKILL.md` |
| `reel-realistic-orchestrator` | `.claude/orchestrators/reel-realistic-orchestrator.md` | `reel-orchestrator` と同じ手順。映像スタイルを realistic に固定し、顔チェックを強めた変種 |
| `healthcheck-orchestrator` | `.claude/orchestrators/healthcheck-orchestrator.md` | `.claude/skills/system-healthcheck/SKILL.md` |

初期設定（**最初に1回だけ**）は `.claude/skills/brand-setup/SKILL.md`。

**オーケストレーターは常にメインセッションであり、サブエージェントにしない。**
サブエージェントは自分の中からさらにサブエージェント（Task）を呼べないため、
オーケストレーターをサブエージェント化すると evaluator を起動できず、
評価ステップが実行不能になる（詳細は `.claude/orchestrators/README.md`）。

## 生成→評価→改善ループ（厳守）

生成物（バナー画像 / リール動画 / キャプション）は、投稿前に必ず `evaluator` サブエージェント（Opus）の
合否判定を通す。

```
生成 → evaluator が合否判定
  → 合格: 次ステップへ
  → 不合格: 修正指示付きで該当ステップだけ再実行（最大2回まで）
  → 2回で合格しない場合: 投稿せず中止。生成物は output/ に退避し、Discordに失敗通知を送って終了する
```

再試行回数の上限は `config/loop-limits.yaml` で管理する。ここに書かれた上限を勝手に緩めない。

## headless実行の制約（厳守 — 実運用で起きた失敗から）

launchd経由の実行は `claude -p`（headless）であり、人が承認ボタンを押せない。
以下を破ると、パイプラインは途中で黙って死ぬか、承認待ちのまま止まる:

1. **スクリプト実行のBashは必ずフォアグラウンドで実行し、`run_in_background` を絶対に使わない。**
   時間のかかるスクリプト（画像生成: 1枚1〜2分、動画生成: 1セグメント2〜5分）はBashの `timeout` を
   600000ms に設定して完了を待つ。headlessではターン終了＝プロセス終了なので、「完了を待機します」と報告して
   ターンを終えると、背後の生成処理ごと殺される（それは失敗を意味する）
2. **スクリプトはSKILL.md記載どおり素の `python3 .claude/skills/...` 形式で呼ぶ。**
   パスは**必ず相対パス**にする（allowlistは `python3 .claude/skills/...` の相対形で
   登録されているため、`/Users/.../insta-autopost/.claude/skills/...` のように絶対パスへ
   正規化すると一致せず全ステップが拒否される）。
   `.claude/settings.json` の実行許可はこの文字列との一致で判定されるため、
   `.venv/bin/python3` の直指定や `source ...activate &&` の前置は許可に一致せず自動拒否される
   （venvは `bin/run-agent.sh` がactivate済み）
3. **ツールが権限拒否されたら、形式を変えての再試行は1回まで。** それでも拒否されたら
   その時点で失敗として扱い、`notify.py` で「権限拒否で中止」をDiscordに通知して終了する
   （「承認をお願いします」「待機中です」で正常終了扱いにしない）

## 失敗時の安全側動作（厳守）

- どのステージで失敗しても「投稿しない」に倒す。中途半端な投稿はしない
- 失敗したら生成済み素材を `output/YYYY-MM-DD_<テーマ>/` に残す（デバッグ用）
- 失敗時は必ず `.claude/skills/instagram-publishing/scripts/notify.py` でDiscordに通知する
  （ステージ名・エラー概要・生成物の退避先を含める）
- 投稿履歴（`logs/posted.jsonl`）への記録は、`ig_post.py` が終了コード0（公開確定・メディアIDあり）で
  終わった後にのみ行う。**公開が確定したら、R2の片づけや通知より先に、まず記録する**
  （片づけの失敗で、公開済みの投稿が履歴から漏れると、同じネタがもう一度投稿される）
- `ig_post.py` が終了コード3（公開されたかもしれないが特定できない）で終わったら、**再投稿しない・記録もしない**。
  `logs/PUBLISH_UNCONFIRMED.json`（公開の前に書かれ、履歴に記録できるまで残る状態ファイル）があるあいだ、
  以降の投稿は起動時に止まる。オーケストレーターがこのファイルを自分の判断で消してはならない

## シークレット取り扱い（厳守）

- `.env` の値（APIキー・トークン）を会話ログ・コミットメッセージ・生成物に出力しない
- `.env` はコミットしない（`.gitignore` で除外済み）。新しいシークレットを追加する場合は
  `env.template` にキー名だけ追記する

## 投稿は「自分の文章の紹介」として作る（厳守）

投稿の中身は、利用者自身の文章（`config/brand.yaml` の `content_sources`。基本は `content/sources/*.md`、
任意で自サイトの記事HTML）の1節を根拠にする。1行のテーマだけから文言を起こすと、どの本にも
書いてある一般論になり中身が薄くなる。自分の文章には固有の数字・手順・理由・資料名が
書かれているので、それを運ぶ。

- `bin/run-agent.sh` が起動のたびに `build_article_index.py` を実行し、ネタ元を節（h2）ごとの
  根拠テキスト `content/articles/<スラッグ>/<節>-<内容ハッシュ>.md`（一度書いたら書き換えない。
  ネタ元が直されたら別名で作り直す）に切り出す。索引は `content/articles/index.json`、
  人が眺める一覧は `content/themes.md` のストック欄（どちらも自動生成。手で編集しない）
- `theme-picker` が返す **`source_path` を、構成・台本・キャプション・evaluator の全員に渡す。**
  画面・ナレーション・キャプションに書く事実は、その節の本文にあるものだけ。自分の知識で補わない
- `source_path` 冒頭に「注意（この節を扱うときの縛り）」があれば、全員がそれに従う
  （`content_sources.cautions` に登録した語句が本文にある節に付く。例: 未確定の話は「検討中」と明記）
- evaluator は「ネタ元との照合」で、本文に無い事実・意味の改変・一般論だけの薄い枚を不合格にする
- 索引が無い・読めないときは投稿を作らない（根拠にできる文章が無い状態で投稿しない）

## テーマ重複防止

投稿前に `content/articles/index.json`（紹介ネタの索引）と `logs/posted.jsonl`（投稿履歴）を
必ず照合し、直近14日で使った節と、直近2件で紹介したネタ元を再利用しない。
`theme-picker` サブエージェントがこの照合を担う。`posted.jsonl` に記録する `theme` は
theme-picker の出力を一字一句そのまま使う（突合はこの文字列の一致で行われる）。

## 手動実行での動作確認

すべてのパイプラインは `bin/run_banner.sh` / `bin/run_reel.sh` / `bin/run_reel_realistic.sh` /
`bin/run_healthcheck.sh` を
直接叩くだけで、launchdなしでも同じ手順で動くこと。デバッグ時はこれを使う。
