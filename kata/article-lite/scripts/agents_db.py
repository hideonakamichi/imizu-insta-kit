"""実行記録のデータベース（.claude/db/agents.db）に SQL を1つ流す。sqlite3 コマンドの代わり。

使い方:  bash scripts/agents-db.sh "SQL"
Windows には sqlite3 コマンドが標準で入っていないため、Python に入っている sqlite3 を使う。
結果は sqlite3 コマンドと同じく「列を | でつないだ1行」ずつ出す。
"""
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
DB = Path(__file__).resolve().parents[1] / ".claude" / "db" / "agents.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
  id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT UNIQUE NOT NULL, name_jp TEXT, role TEXT,
  created_at TEXT DEFAULT (datetime('now','localtime')));
CREATE TABLE IF NOT EXISTS reflections (
  id INTEGER PRIMARY KEY AUTOINCREMENT, agent_id INTEGER, agent_slug TEXT NOT NULL, parent_run_id INTEGER,
  trigger TEXT, status TEXT DEFAULT 'running', action TEXT, items_processed INTEGER DEFAULT 0,
  items_succeeded INTEGER DEFAULT 0, items_failed INTEGER DEFAULT 0, started_at TEXT, ended_at TEXT,
  duration_ms INTEGER, tokens_in INTEGER, tokens_out INTEGER, cost_usd REAL, quality_score INTEGER,
  what_done TEXT, quality_check TEXT, self_improvement TEXT, content_improvement TEXT, result_full TEXT,
  error_message TEXT, metadata TEXT, reflected_at TEXT,
  created_at TEXT DEFAULT (datetime('now','localtime')), updated_at TEXT DEFAULT (datetime('now','localtime')),
  FOREIGN KEY (agent_id) REFERENCES agents(id), FOREIGN KEY (parent_run_id) REFERENCES reflections(id));
CREATE INDEX IF NOT EXISTS idx_reflections_slug ON reflections(agent_slug);
CREATE INDEX IF NOT EXISTS idx_reflections_parent ON reflections(parent_run_id);
CREATE INDEX IF NOT EXISTS idx_reflections_created ON reflections(created_at);
INSERT OR IGNORE INTO agents (slug, name_jp, role) VALUES
  ('support-orchestrator', '編集長', 'leader'), ('support-writer', 'ライター', 'worker'),
  ('support-reviewer', 'レビュアー', 'worker');
"""


def connect() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)
    return con


def main() -> int:
    if len(sys.argv) != 2:
        print('使い方: bash scripts/agents-db.sh "SQL"', file=sys.stderr)
        return 2
    con = connect()
    cur = con.execute(sys.argv[1])
    for row in cur.fetchall():
        print("|".join("" if v is None else str(v) for v in row))
    con.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
