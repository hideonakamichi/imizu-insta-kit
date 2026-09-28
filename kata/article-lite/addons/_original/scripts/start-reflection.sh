#!/bin/bash
# 全エージェント共通の reflection 開始ヘルパー
#
# 使い方:
#   RUN_ID=$(bash scripts/start-reflection.sh --slug support-orchestrator --trigger launchd)
#   RUN_ID=$(bash scripts/start-reflection.sh --slug support-writer --parent 38 --trigger subagent)
#
# 戻り値: stdout に新しい reflections.id を出力
# - subagent invocation でも独立した reflection 行が作られる
# - parent_run_id でツリー構造を辿れる (orchestrator(38) → writer(N) → reviewer(M))

set -euo pipefail
cd "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null || cd "$(dirname "$0")/.."

SLUG=""
PARENT=""
TRIGGER="manual"

while [ $# -gt 0 ]; do
  case "$1" in
    --slug)    SLUG="$2"; shift 2 ;;
    --parent)  PARENT="$2"; shift 2 ;;
    --trigger) TRIGGER="$2"; shift 2 ;;
    *) echo "[start-reflection] unknown arg: $1" >&2; exit 1 ;;
  esac
done

if [ -z "$SLUG" ]; then
  echo "[start-reflection] --slug required" >&2
  exit 1
fi

DB=".claude/db/agents.db"

# DB が無ければスキーマ初期化
if [ ! -f "$DB" ]; then
  mkdir -p "$(dirname "$DB")"
  sqlite3 "$DB" <<'SQL'
CREATE TABLE IF NOT EXISTS agents (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  slug        TEXT UNIQUE NOT NULL,
  name_jp     TEXT,
  role        TEXT,
  created_at  TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS reflections (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id            INTEGER,
  agent_slug          TEXT NOT NULL,
  parent_run_id       INTEGER,
  trigger             TEXT,
  status              TEXT DEFAULT 'running',
  action              TEXT,
  items_processed     INTEGER DEFAULT 0,
  items_succeeded     INTEGER DEFAULT 0,
  items_failed        INTEGER DEFAULT 0,
  started_at          TEXT,
  ended_at            TEXT,
  duration_ms         INTEGER,
  tokens_in           INTEGER,
  tokens_out          INTEGER,
  cost_usd            REAL,
  quality_score       INTEGER,
  what_done           TEXT,
  quality_check       TEXT,
  self_improvement    TEXT,
  content_improvement TEXT,
  result_full         TEXT,
  error_message       TEXT,
  metadata            TEXT,
  reflected_at        TEXT,
  created_at          TEXT DEFAULT (datetime('now','localtime')),
  updated_at          TEXT DEFAULT (datetime('now','localtime')),
  FOREIGN KEY (agent_id) REFERENCES agents(id),
  FOREIGN KEY (parent_run_id) REFERENCES reflections(id)
);
CREATE INDEX IF NOT EXISTS idx_reflections_slug ON reflections(agent_slug);
CREATE INDEX IF NOT EXISTS idx_reflections_parent ON reflections(parent_run_id);
CREATE INDEX IF NOT EXISTS idx_reflections_created ON reflections(created_at);

-- 初期エージェント登録
INSERT OR IGNORE INTO agents (slug, name_jp, role) VALUES
  ('support-orchestrator', '編集長', 'leader'),
  ('support-writer', 'ライター', 'worker'),
  ('support-reviewer', 'レビュアー', 'worker');
SQL
  echo "[start-reflection] DB を初期化しました: $DB" >&2
fi

# parent カラムは NULL or 整数
PARENT_SQL="NULL"
if [ -n "$PARENT" ] && [ "$PARENT" != "0" ]; then
  PARENT_SQL="$PARENT"
fi

ID=$(sqlite3 "$DB" "
INSERT INTO reflections (agent_id, agent_slug, trigger, status, started_at, parent_run_id)
VALUES (
  (SELECT id FROM agents WHERE slug = '$SLUG' LIMIT 1),
  '$SLUG',
  '$TRIGGER',
  'running',
  datetime('now','localtime'),
  $PARENT_SQL
) RETURNING id;
")

echo "$ID"
