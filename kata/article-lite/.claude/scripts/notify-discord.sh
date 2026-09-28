#!/bin/bash
# Discord Webhook 通知 (オーバーライド方式)
# 1 つの Webhook で全エージェントが共有。username/avatar_url をペイロードで上書き。
#
# Usage: bash notify-discord.sh --agent NAME "メッセージ"
#        bash notify-discord.sh "メッセージ"           (汎用、エージェント指定なし)
#
# キャラクタートーン (Discord 通知専用。ライティングには影響させないこと)
#   ライター (Support Writer):       一生懸命。「記事書いたよ！レビューお願い！」
#   レビュアー (Support Reviewer):   堅実。「…チェック完了。3 件修正した」
#   編集長 (Support Orchestrator):   簡潔に正確。「データ同期したよ」

set -euo pipefail
cd "$(dirname "$0")/../.."

# .env.local から DISCORD_WEBHOOK_URL を読む
if [ -f .env.local ]; then
  set -a
  source .env.local 2>/dev/null || true
  set +a
fi

# jq check
if ! command -v jq &>/dev/null; then
  echo "[notify-discord] jq not found, skipping notification" >&2
  exit 0
fi

if [ -z "${DISCORD_WEBHOOK_URL:-}" ]; then
  echo "[notify-discord] DISCORD_WEBHOOK_URL not set in .env.local, skipping" >&2
  exit 0
fi

# Avatar bucket URL (Supabase Storage の public bucket を想定)
# 任意: .env.local で AVATAR_BUCKET_URL を上書き可
AVATAR_BUCKET_URL="${AVATAR_BUCKET_URL:-${NEXT_PUBLIC_SUPABASE_URL:-}/storage/v1/object/public/agent-icons}"

# Agent → display name + avatar mapping
AGENT_NAME=""
AGENT_AVATAR=""
if [ "${1:-}" = "--agent" ]; then
  case "${2:-}" in
    support-writer)         AGENT_NAME="ライター";    AGENT_AVATAR="$AVATAR_BUCKET_URL/writer.png" ;;
    support-reviewer)       AGENT_NAME="レビュアー";  AGENT_AVATAR="$AVATAR_BUCKET_URL/reviewer.png" ;;
    support-orchestrator)   AGENT_NAME="編集長";      AGENT_AVATAR="$AVATAR_BUCKET_URL/orchestrator.png" ;;
    *)
      echo "[notify-discord] Unknown agent: ${2:-}" >&2
      exit 1
      ;;
  esac
  shift 2
fi

# Build payload
message="${1:-}"
if [ -z "$message" ]; then
  echo "Usage: notify-discord.sh [--agent NAME] \"メッセージ\"" >&2
  exit 1
fi

# ★ Windows (Git Bash) では日本語 UTF-8 を curl -d "$payload" で渡すと壊れて
#   Discord が 400 (invalid JSON) を返すため、必ず一時ファイル + --data-binary @file で送る
PAYLOAD_FILE=$(mktemp)
trap 'rm -f "$PAYLOAD_FILE"' EXIT

if [ -n "$AGENT_NAME" ]; then
  jq -n \
    --arg msg "$message" \
    --arg name "$AGENT_NAME" \
    --arg avatar "$AGENT_AVATAR" \
    '{content: $msg, username: $name, avatar_url: $avatar}' > "$PAYLOAD_FILE"
else
  jq -n --arg msg "$message" '{content: $msg}' > "$PAYLOAD_FILE"
fi

curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Content-Type: application/json" \
  --data-binary "@$PAYLOAD_FILE" \
  "$DISCORD_WEBHOOK_URL"
