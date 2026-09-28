#!/bin/bash
# 全エージェント共通の reflection（実行記録）開始ヘルパー
#
# 使い方:
#   RUN_ID=$(bash scripts/start-reflection.sh --slug support-orchestrator --trigger manual)
#   RUN_ID=$(bash scripts/start-reflection.sh --slug support-writer --parent 38 --trigger subagent)
#
# 戻り値: stdout に新しい reflections.id を出力。元の版は sqlite3 コマンドを使っていた（addons/_original/）
set -euo pipefail
cd "$(dirname "$0")/.."

SLUG=""; PARENT=""; TRIGGER="manual"
while [ $# -gt 0 ]; do
  case "$1" in
    --slug)    SLUG="$2"; shift 2 ;;
    --parent)  PARENT="$2"; shift 2 ;;
    --trigger) TRIGGER="$2"; shift 2 ;;
    *) echo "[start-reflection] unknown arg: $1" >&2; exit 1 ;;
  esac
done
[ -z "$SLUG" ] && { echo "[start-reflection] --slug required" >&2; exit 1; }
[[ "$SLUG" =~ ^[a-z0-9-]+$ ]] || { echo "[start-reflection] slug は半角小文字・数字・ハイフン" >&2; exit 1; }
[[ "$TRIGGER" =~ ^[a-z0-9_-]+$ ]] || { echo "[start-reflection] trigger は半角英数字" >&2; exit 1; }
PARENT_SQL="NULL"
if [ -n "$PARENT" ] && [ "$PARENT" != "0" ]; then
  [[ "$PARENT" =~ ^[0-9]+$ ]] || { echo "[start-reflection] --parent は数字" >&2; exit 1; }
  PARENT_SQL="$PARENT"
fi

bash scripts/agents-db.sh "
INSERT INTO reflections (agent_id, agent_slug, trigger, status, started_at, parent_run_id)
VALUES ((SELECT id FROM agents WHERE slug = '$SLUG' LIMIT 1), '$SLUG', '$TRIGGER', 'running',
        datetime('now','localtime'), $PARENT_SQL) RETURNING id;"
