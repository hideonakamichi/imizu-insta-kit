#!/bin/bash
# 実行記録のデータベースに SQL を流す（sqlite3 コマンドの代わり。Windows に標準で入っていないため）
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
PY=$(command -v py || command -v python3 || command -v python || true)
[ -z "$PY" ] && { echo "[agents-db] ERROR: Python が見つかりません" >&2; exit 1; }
exec "$PY" scripts/agents_db.py "$@"
