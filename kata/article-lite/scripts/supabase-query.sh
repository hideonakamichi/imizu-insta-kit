#!/bin/bash
# データの窓口（Lite 版）。元は Supabase の REST API。ここでは data/<テーブル>.json を読み書きする。
# 使い方は元と同じ（select / insert / update / delete）。jq の代わりに set / append を足してある。
# 詳しくは scripts/local_db.py の先頭。元の版は addons/_original/scripts/supabase-query.sh
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
# Windows では python3 が Microsoft Store の案内を開くことがあるので、py を先に探す
PY=$(command -v py || command -v python3 || command -v python || true)
[ -z "$PY" ] && { echo "[supabase-query] ERROR: Python が見つかりません" >&2; exit 1; }
exec "$PY" scripts/local_db.py "$@"
