#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT_DIR/scripts/.cache/launchd"
LOCAL_PUBLISH="$ROOT_DIR/scripts/local-threads-publish.sh"

mkdir -p "$LOG_DIR"
cd "$ROOT_DIR"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

echo "Starting scheduled Threads publish at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
"$LOCAL_PUBLISH"
echo "Scheduled Threads publish finished."
