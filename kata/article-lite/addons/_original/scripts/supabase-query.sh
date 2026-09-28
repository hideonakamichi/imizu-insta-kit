#!/bin/bash
# Supabase REST API ラッパー — MCP 不要、service_role key で認証
#
# 使い方:
#   # SELECT (テーブルからデータ取得)
#   bash scripts/supabase-query.sh select supports "status=eq.active&select=id,title&limit=10"
#
#   # INSERT
#   bash scripts/supabase-query.sh insert supports '{"title":"テスト制度","status":"active"}'
#
#   # UPDATE
#   bash scripts/supabase-query.sh update supports '{"title":"更新後"}' "id=eq.456"
#
#   # DELETE
#   bash scripts/supabase-query.sh delete supports "id=eq.456"
#
#   # RPC (任意 SQL 関数呼び出し)
#   bash scripts/supabase-query.sh rpc my_function '{"p_limit":50}'

set -euo pipefail
cd "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null || cd "$(dirname "$0")/.."

if [ -f .env.local ]; then
  set -a
  source .env.local 2>/dev/null || true
  set +a
fi

if [ -z "${NEXT_PUBLIC_SUPABASE_URL:-}" ] || [ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]; then
  echo "[supabase-query] ERROR: .env.local に NEXT_PUBLIC_SUPABASE_URL と SUPABASE_SERVICE_ROLE_KEY を設定してください" >&2
  exit 1
fi

ACTION="${1:?Action required: select|insert|update|delete|rpc}"
TABLE="${2:?Table/function name required}"
DATA="${3:-}"
FILTER="${4:-}"

# ★大容量ペイロード対応: DATA が「@ファイルパス」形式ならファイルの中身を使う
#   例: bash scripts/supabase-query.sh update supports @/tmp/payload.json "id=eq.10"
#   (記事本文のような巨大 JSON を引数で渡すと argv 上限で失敗するため)
if [ -n "$DATA" ] && [ "${DATA:0:1}" = "@" ]; then
  DATA_SRC_FILE="${DATA:1}"
  if [ ! -f "$DATA_SRC_FILE" ]; then
    echo "[supabase-query] ERROR: ペイロードファイルが見つかりません: $DATA_SRC_FILE" >&2
    exit 1
  fi
  DATA=$(cat "$DATA_SRC_FILE")
fi

BASE="${NEXT_PUBLIC_SUPABASE_URL}/rest/v1"
AUTH_HEADERS=(-H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}")

case "$ACTION" in
  select)
    curl -s "${BASE}/${TABLE}?${DATA}" "${AUTH_HEADERS[@]}"
    ;;
  insert)
    # ★ Windows (Git Bash) の日本語 UTF-8 対策: -d "$DATA" ではなく --data-binary @file で送る
    DATA_FILE=$(mktemp); printf '%s' "$DATA" > "$DATA_FILE"; trap 'rm -f "$DATA_FILE"' EXIT
    curl -s "${BASE}/${TABLE}" "${AUTH_HEADERS[@]}" \
      -H "Content-Type: application/json" \
      -H "Prefer: return=representation" \
      --data-binary "@$DATA_FILE"
    ;;
  update)
    DATA_FILE=$(mktemp); printf '%s' "$DATA" > "$DATA_FILE"; trap 'rm -f "$DATA_FILE"' EXIT
    curl -s "${BASE}/${TABLE}?${FILTER}" "${AUTH_HEADERS[@]}" \
      -H "Content-Type: application/json" \
      -H "Prefer: return=representation" \
      -X PATCH \
      --data-binary "@$DATA_FILE"
    ;;
  delete)
    curl -s "${BASE}/${TABLE}?${DATA}" "${AUTH_HEADERS[@]}" \
      -X DELETE
    ;;
  rpc)
    DATA_FILE=$(mktemp); printf '%s' "${DATA:-{}}" > "$DATA_FILE"; trap 'rm -f "$DATA_FILE"' EXIT
    curl -s "${BASE}/rpc/${TABLE}" "${AUTH_HEADERS[@]}" \
      -H "Content-Type: application/json" \
      --data-binary "@$DATA_FILE"
    ;;
  *)
    echo "Unknown action: $ACTION (use select|insert|update|delete|rpc)" >&2
    exit 1
    ;;
esac
