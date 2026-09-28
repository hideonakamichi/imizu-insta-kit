#!/bin/bash
# エージェント実行ラッパー (top-level 起動用)
# 使い方: bash scripts/run-agent.sh <agent-name>
#         bash scripts/run-agent.sh support-orchestrator
#
# launchd / cron からはこれを呼ぶ。Claude Code CLI を起動し、
# 該当 agent.md のルールに従って実行させる。

set -euo pipefail
cd "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null || cd "$(dirname "$0")/.."

if [ -f .env.local ]; then
  set -a
  source .env.local 2>/dev/null || true
  set +a
fi

AGENT_FULL="${1:?agent slug required (e.g., support-orchestrator)}"
AGENT_MD=".claude/agents/${AGENT_FULL}.md"

if [ ! -f "$AGENT_MD" ]; then
  echo "[run-agent] ERROR: $AGENT_MD not found" >&2
  exit 1
fi

# タイムアウト: agent.md frontmatter の timeout_sec を読む
TIMEOUT_FROM_FM=$(awk '/^---$/{n++; next} n==1 && /^timeout_sec:/{print $2; exit}' "$AGENT_MD" 2>/dev/null)
DEFAULT_TIMEOUT="${TIMEOUT_FROM_FM:-1800}"
TIMEOUT_SEC="${AGENT_TIMEOUT:-$DEFAULT_TIMEOUT}"

# 実行開始時に reflections に running 行を INSERT → RUN_ID を agent 環境変数で渡す
RUN_ID=$(bash scripts/start-reflection.sh --slug "$AGENT_FULL" --trigger launchd)
export AGENT_RUN_ID="$RUN_ID"

echo "[run-agent] $AGENT_FULL を起動 (RUN_ID=$RUN_ID, timeout=${TIMEOUT_SEC}s)"

# Claude Code CLI を起動 (macOS 互換タイムアウト: バックグラウンド + wait + kill)
TMPOUT=$(mktemp)
claude -p "$AGENT_MD を読み、そのルールに従って実行せよ。あなたの AGENT_RUN_ID は ${RUN_ID} です。reflection を書く際は UPDATE reflections SET ... WHERE id=${RUN_ID}; を使ってください。" \
  --dangerously-skip-permissions \
  --output-format json > "$TMPOUT" 2>&1 &
CLAUDE_PID=$!

# タイムアウト監視
( sleep "$TIMEOUT_SEC" && kill -TERM $CLAUDE_PID 2>/dev/null && sleep 5 && kill -KILL $CLAUDE_PID 2>/dev/null ) &
WATCHDOG_PID=$!

wait $CLAUDE_PID 2>/dev/null
EXIT_CODE=$?
kill $WATCHDOG_PID 2>/dev/null; wait $WATCHDOG_PID 2>/dev/null

OUTPUT=$(cat "$TMPOUT")
rm -f "$TMPOUT"

# シグナルで死んだ場合
if [ $EXIT_CODE -eq 143 ] || [ $EXIT_CODE -eq 137 ]; then
  echo "[run-agent] TIMEOUT: $AGENT_FULL が ${TIMEOUT_SEC} 秒でタイムアウト" >&2
  sqlite3 .claude/db/agents.db "UPDATE reflections SET status='error', error_message='timeout', ended_at=datetime('now','localtime') WHERE id=$RUN_ID"
  exit 124
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] $AGENT_FULL 完了 (RUN_ID=$RUN_ID)"
echo "$OUTPUT"
