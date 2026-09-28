# orchestrators/ — オーケストレーターの職務記述書

ここにあるのは、`bin/run-agent.sh <slug>` が起動する **メインセッション用の指示書**。

## なぜ .claude/agents/ ではなくここに置くのか

`.claude/agents/` に置いたファイルは Task()（サブエージェント）として呼び出せるように
登録される。しかしオーケストレーターは **サブエージェントにしてはならない**:
Claude Code のサブエージェントは自分の中からさらに Task() を呼べないため、
サブエージェント化されたオーケストレーターは theme-picker / evaluator 等を
起動できず、パイプラインが評価ステップで実行不能になる（実機検証済み）。

そのため、オーケストレーターの定義は agents/ から分離したこのディレクトリに置き、
「メインセッションに読ませる指示書」としてだけ使う。

## frontmatter の意味（run-agent.sh が読む）

| キー | 意味 | 既定値 |
|---|---|---|
| `timeout_sec` | この秒数を超えたら kill して失敗通知 | 2400 |
| `model` | `claude -p --model` に渡す値 | opus |
| `expects_post` | true なら「正常終了したのに投稿履歴が増えていない」を警告通知 | false |

frontmatter の値は run-agent.sh が実際に CLI 引数へ変換する。
ここに書いただけで効く魔法ではない点に注意（新しいキーを足すなら
run-agent.sh 側の対応もセットで）。
