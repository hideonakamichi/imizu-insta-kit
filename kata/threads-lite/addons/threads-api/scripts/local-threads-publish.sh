#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT_DIR/scripts/.cache/launchd"
LOCK_DIR="$LOG_DIR/threads-publish.lock"

mkdir -p "$LOG_DIR"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "Another Threads publish job is already running. Skipping."
  exit 0
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

cd "$ROOT_DIR"

if [[ -f "$ROOT_DIR/.env.local" ]]; then
  set -a
  source "$ROOT_DIR/.env.local"
  set +a
fi

missing=()
for name in THREADS_ACCESS_TOKEN THREADS_USER_ID; do
  if [[ -z "${(P)name:-}" ]]; then
    missing+=("$name")
  fi
done

if (( ${#missing[@]} > 0 )); then
  echo "Missing required env vars in .env.local: ${missing[*]}"
  exit 1
fi

export THREADS_DRY_RUN=False

npm run threads:drafts
npm run threads:publish -- --skip-posted --skip-today --live
