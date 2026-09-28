#!/bin/bash
# 書き上がった記事を output/ に書き出す（詳しくは scripts/export_articles.py）
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
PY=$(command -v py || command -v python3 || command -v python || true)
[ -z "$PY" ] && { echo "[export] ERROR: Python が見つかりません" >&2; exit 1; }
exec "$PY" scripts/export_articles.py "$@"
