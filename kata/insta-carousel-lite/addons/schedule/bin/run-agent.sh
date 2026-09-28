#!/usr/bin/env bash
# run-agent.sh — オーケストレーターの汎用起動ラッパー
#
# 使い方:
#   bash bin/run-agent.sh banner-orchestrator
#   bash bin/run-agent.sh reel-orchestrator
#   bash bin/run-agent.sh healthcheck-orchestrator
#
# launchd からも手動デバッグからも同じ動作をする。
# 指定された .claude/orchestrators/<slug>.md を Claude Code のメインセッションに
# 読ませて実行させる（サブエージェント起動ではない。オーケストレーターは常に
# メインセッション。理由は同ディレクトリの README.md を参照）。
#
# ロック・ログ・タイムアウト監視・失敗時のDiscord通知はすべてここで面倒を見る。
# 各オーケストレーター固有の設定は <slug>.md の frontmatter で指定する:
#   timeout_sec:  この秒数を超えたら kill して失敗通知（既定 2400）
#   model:        claude -p に渡すモデル（既定 opus）
#   expects_post: true なら「正常終了したのに投稿履歴が増えていない」を警告通知する
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

SLUG="${1:?usage: run-agent.sh <orchestrator-slug>  (e.g. banner-orchestrator)}"
AGENT_MD=".claude/orchestrators/${SLUG}.md"

if [[ ! -f "$AGENT_MD" ]]; then
  echo "[error] $AGENT_MD が見つかりません" >&2
  echo "        利用可能: $(ls .claude/orchestrators/ 2>/dev/null | grep -v '^README' | sed 's/\.md$//' | tr '\n' ' ')" >&2
  exit 1
fi

# --- frontmatter を読む（最初の --- ... --- の間の key: value） -----------
fm() {  # fm <key> <default>
  local v
  v=$(awk -v key="$1" '
    /^---$/ { n++; next }
    n == 1 && $1 == key":" { sub(/^[^:]*:[[:space:]]*/, ""); print; exit }
  ' "$AGENT_MD")
  echo "${v:-$2}"
}
TIMEOUT_SEC="$(fm timeout_sec 2400)"
MODEL="$(fm model opus)"
EXPECTS_POST="$(fm expects_post false)"

# --- ロック（多重起動と、投稿パイプラインどうしの同時実行を防ぐ） -----------------
# 投稿するパイプライン（banner / reel / reel-realistic）は**同じロックを共有する**。ネタの選定から
# 投稿履歴の記録までのあいだに別の投稿パイプラインが走ると、両方が同じ未使用ネタを選んで二重投稿になる。
# ロックは flock（bin/with_lock.py）。持っているプロセスが消えれば OS が外すので、残留ロックが無い。
# ロックのファイルはこのフォルダの中に置く（同じMacに展開した別アカウント用のキットと干渉しない）
LOG_DIR="$PROJECT_ROOT/logs/launchd"
mkdir -p "$LOG_DIR" "$PROJECT_ROOT/logs/locks"
if [[ -z "${INSTA_LOCK_HELD:-}" ]]; then
  if [[ "$EXPECTS_POST" == "true" ]]; then
    LOCK_NAME="posting"; LOCK_WAIT=2400   # 先に走っている投稿パイプラインが終わるのを最大40分待つ
  else
    LOCK_NAME="$SLUG"; LOCK_WAIT=0
  fi
  set +e
  python3 "$PROJECT_ROOT/bin/with_lock.py" --lock "$PROJECT_ROOT/logs/locks/${LOCK_NAME}.flock" --wait "$LOCK_WAIT" \
    -- bash "$PROJECT_ROOT/bin/run-agent.sh" "$@"
  RC=$?
  set -e
  if [[ $RC -eq 75 ]]; then
    SKIP_LOG="$LOG_DIR/${SLUG}_$(date +%Y%m%d_%H%M%S).log"
    echo "[skip] $SLUG: ほかのパイプラインが実行中のためロックを取れませんでした（待機 ${LOCK_WAIT}秒）" | tee -a "$SKIP_LOG"
    if [[ "$EXPECTS_POST" == "true" ]]; then
      # 投稿の予定が1回飛んだことになるので、黙ってスキップしない
      python3 "$PROJECT_ROOT/.claude/skills/instagram-publishing/scripts/notify.py" failure --pipeline "$SLUG" \
        --stage "lock" --error "ほかの投稿パイプラインが${LOCK_WAIT}秒たっても終わらないため、今回の実行を見送りました。スケジュールの時刻が近すぎないか確認してください。" \
        --artifact-dir "$SKIP_LOG" || true
    fi
    exit 0
  fi
  exit $RC
fi
LOG_FILE="$LOG_DIR/${SLUG}_$(date +%Y%m%d_%H%M%S).log"

# --- 実行環境 -------------------------------------------------------------
if [[ -f "$PROJECT_ROOT/.venv/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "$PROJECT_ROOT/.venv/bin/activate"
fi

# 展開先のパスに空白があっても壊れないよう、文字列ではなく関数で呼ぶ
notify() { python3 "$PROJECT_ROOT/.claude/skills/instagram-publishing/scripts/notify.py" "$@"; }
POSTED_LOG="$PROJECT_ROOT/logs/posted.jsonl"
NOTIFY_LOG="$PROJECT_ROOT/logs/notify.jsonl"   # notify.py が送信済み通知を追記する
LINES_BEFORE=$( [[ -f "$POSTED_LOG" ]] && wc -l < "$POSTED_LOG" || echo 0 )
# この起動を識別する run_id。notify.py が記録に含めるので、同時刻に走る別パイプライン
# （healthcheck の report 等）の通知と区別して「この実行が自分で通知したか」を判定できる
export INSTA_RUN_ID="${SLUG}_$(date +%Y%m%d_%H%M%S)_$$"

echo "[start] $SLUG $(date -Iseconds) (model=$MODEL, timeout=${TIMEOUT_SEC}s)" | tee -a "$LOG_FILE"

# --- 安全装置: 前回の投稿の結果が未確認のあいだは、投稿パイプラインを起動しない -------
# ig_post.py が「公開されたかもしれないが特定できない」で終わると、この印を残す。人が Instagram を
# 確認して印を消すまで、次の投稿はしない（同じ内容の二重投稿と、履歴の食い違いを防ぐ）
UNCONFIRMED_FILE="$PROJECT_ROOT/logs/PUBLISH_UNCONFIRMED.json"
if [[ "$EXPECTS_POST" == "true" && -f "$UNCONFIRMED_FILE" ]]; then
  echo "[abort] 前回の投稿の後始末が終わっていないため起動しません: $UNCONFIRMED_FILE" | tee -a "$LOG_FILE"
  INSTA_RUN_ID="${INSTA_RUN_ID}_preflight" notify failure --pipeline "$SLUG" --stage "unconfirmed-pending" \
    --error "前回の投稿の後始末（公開の確認、または履歴への記録）が終わっていないため、投稿を止めています。logs/PUBLISH_UNCONFIRMED.json の what_to_do に従って解除してください。" \
    --artifact-dir "$UNCONFIRMED_FILE" || true
  echo "[end] $SLUG $(date -Iseconds) exit=1" | tee -a "$LOG_FILE"
  exit 1
fi

# --- 安全装置: 設定が終わっていなければ投稿パイプラインを起動しない -----------------
# 「未設定なら投稿しない」を claude への指示文に任せず、ここで機械的に止める
# （受け取ったままの雛形や、他人の設定のまま無人投稿する事故を防ぐ）。ig_post.py も同じ検証をする。
# 起動前の通知は run_id を変えて送る（下の「この実行は自分で通知したか」の判定に数えさせないため）
if [[ "$EXPECTS_POST" == "true" ]]; then
  if ! python3 "$PROJECT_ROOT/.claude/skills/shared/scripts/check_brand.py" >> "$LOG_FILE" 2>&1; then
    echo "[abort] config/brand.yaml の設定が終わっていないため起動しません" | tee -a "$LOG_FILE"
    INSTA_RUN_ID="${INSTA_RUN_ID}_preflight" notify failure --pipeline "$SLUG" --stage "check-brand" \
      --error "config/brand.yaml の設定が終わっていないため、投稿パイプラインを起動しませんでした。ログ: $LOG_FILE" \
      --artifact-dir "$LOG_FILE" || true
    echo "[end] $SLUG $(date -Iseconds) exit=1" | tee -a "$LOG_FILE"
    exit 1
  fi
fi

# --- ネタの索引の更新（投稿は自分の文章の1節の紹介として作る） ------------------
# ネタ元を節ごとの根拠テキストに切り出し、ネタ帳のストックを作り直す。
# claude の外で実行するので許可リストは要らない。
# **失敗したら投稿パイプラインは止める。** 前回の索引で続行すると、取り下げた文章
# （削除した・下書きに戻した）が古い索引に残ったまま、無人投稿の根拠に使われ続ける。
# ネタ元がゼロ件なのは失敗ではない（空の索引が書かれ、theme-picker が選定を断って投稿せずに終わる）
if ! python3 "$PROJECT_ROOT/.claude/skills/shared/scripts/build_article_index.py" >> "$LOG_FILE" 2>&1; then
  echo "[error] ネタの索引の更新に失敗" | tee -a "$LOG_FILE"
  INSTA_RUN_ID="${INSTA_RUN_ID}_preflight" notify failure --pipeline "$SLUG" --stage "article-index" \
    --error "ネタの索引の更新に失敗しました。原因は logs/article_index_state.json の last_error とログを確認: $LOG_FILE" \
    --artifact-dir "$LOG_FILE" || true
  if [[ "$EXPECTS_POST" == "true" ]]; then
    echo "[abort] 古い索引では投稿しません" | tee -a "$LOG_FILE"
    echo "[end] $SLUG $(date -Iseconds) exit=1" | tee -a "$LOG_FILE"
    exit 1
  fi
fi

# --- claude -p をタイムアウト監視付きで起動 --------------------------------
set +e
claude -p "${AGENT_MD} を読み、そこに書かれたルールと手順に従って実行してください。" \
  --model "$MODEL" \
  --permission-mode acceptEdits \
  --output-format json \
  >> "$LOG_FILE" 2>&1 &
CLAUDE_PID=$!

# macOS互換のwatchdog（coreutilsのtimeoutに依存しない）
( sleep "$TIMEOUT_SEC" && kill -TERM "$CLAUDE_PID" 2>/dev/null && sleep 10 && kill -KILL "$CLAUDE_PID" 2>/dev/null ) 2>/dev/null &
WATCHDOG_PID=$!

wait "$CLAUDE_PID" 2>/dev/null
CLAUDE_EXIT=$?
# watchdog の子プロセス（sleep）を先に止める。サブシェルだけ kill すると sleep が孤児として
# 残り、TIMEOUT_SEC 後に再利用された可能性のある PID へ kill -TERM を送ってしまう
pkill -P "$WATCHDOG_PID" 2>/dev/null
kill "$WATCHDOG_PID" 2>/dev/null
wait "$WATCHDOG_PID" 2>/dev/null
set -e

LINES_AFTER=$( [[ -f "$POSTED_LOG" ]] && wc -l < "$POSTED_LOG" || echo 0 )
# この run_id で送られた通知の件数（0 なら、この実行は自分で何も通知していない）
# grep -c は0件のとき "0" を出力して exit 1 になるので || echo で足さない（"0\n0" になる）
SELF_NOTIFIED=$(grep -c "\"run_id\": \"$INSTA_RUN_ID\"" "$NOTIFY_LOG" 2>/dev/null || true)
SELF_NOTIFIED="${SELF_NOTIFIED:-0}"

# --- 結果判定と通知（オーケストレーター自身が通知できなかった場合の最終防衛線） ---
if [[ $CLAUDE_EXIT -eq 143 || $CLAUDE_EXIT -eq 137 ]]; then
  echo "[error] timeout: ${TIMEOUT_SEC}s を超過したため強制終了" | tee -a "$LOG_FILE"
  notify failure --pipeline "$SLUG" --stage "orchestrator" \
    --error "タイムアウト（${TIMEOUT_SEC}秒超過）で強制終了しました。ログ: $LOG_FILE" \
    --artifact-dir "$LOG_FILE" || true
  CLAUDE_EXIT=124
elif [[ $CLAUDE_EXIT -ne 0 ]]; then
  echo "[error] claude exited with code $CLAUDE_EXIT" | tee -a "$LOG_FILE"
  notify failure --pipeline "$SLUG" --stage "orchestrator" \
    --error "claude -p がexit code ${CLAUDE_EXIT} で終了しました。ログ: $LOG_FILE" \
    --artifact-dir "$LOG_FILE" || true
elif [[ "$EXPECTS_POST" == "true" && "$LINES_AFTER" -eq "$LINES_BEFORE" ]]; then
  # exit 0だが投稿履歴が増えていない = 「安全に停止して投稿しなかった」ケース。
  if [[ "$SELF_NOTIFIED" -gt 0 ]]; then
    # オーケストレーターが実行中に notify.py で通知済み（evaluator 不合格で中止など）。
    # 二重通知を避けるため最終防衛線の通知は省略する
    # （非0終了・タイムアウトの分岐は別種の障害なので、通知済みでも上で必ず通知する）
    echo "[info] exit=0・投稿なし。オーケストレーターが通知済み（run_id=$INSTA_RUN_ID の通知 ${SELF_NOTIFIED}件）のため追加通知は省略" | tee -a "$LOG_FILE"
  else
    echo "[warn] exit=0 だが posted.jsonl に新規行なく、通知の記録もなし。通知します" | tee -a "$LOG_FILE"
    notify failure --pipeline "$SLUG" --stage "orchestrator" \
      --error "パイプラインは正常終了しましたが投稿もDiscord通知も確認できませんでした（黙って停止した可能性）。ログ: $LOG_FILE" \
      --artifact-dir "$LOG_FILE" || true
  fi
fi

echo "[end] $SLUG $(date -Iseconds) exit=$CLAUDE_EXIT" | tee -a "$LOG_FILE"
exit $CLAUDE_EXIT
