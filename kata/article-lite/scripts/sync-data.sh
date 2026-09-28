#!/bin/bash
# データ同期スクリプト (雛形) — 自分のデータソースに合わせて書き換えてください
#
# このスクリプトの責務:
#   1. 外部データソース (自治体サイト / CSV など) から最新データを取得
#   2. supports テーブルに upsert
#   3. application_end が今日より前の制度を status='closed' に自動更新
#      (常設制度は application_end が NULL のため対象外)
#
# 使い方:
#   bash scripts/sync-data.sh           # 通常同期
#   bash scripts/sync-data.sh --full    # フル同期 (オプション)

set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .env.local ]; then
  set -a
  source .env.local 2>/dev/null || true
  set +a
fi

MODE="${1:-diff}"

echo "[sync-data] 同期開始 (mode=$MODE)"

# -----------------------------------------------------------------------------
# ★★★ ここから下を自分のデータソースに合わせて実装してください ★★★
#
# 例 1: 自治体のひとり親支援ページ / オープンデータ CSV を取り込む場合
#   curl -o /tmp/supports.csv https://example.pref.example/hitorioya.csv
#   python3 csv-to-supabase.py /tmp/supports.csv
#
# 例 2: 手動キュレーション (supports テーブルに直接 insert)
#   bash scripts/supabase-query.sh insert supports '{"program_code":"...","title":"...",...}'
#
# 例 3: 既に Supabase に手動投入済みなら、この部分は空のままで OK
#   (期限切れ close 処理だけが毎回走る)
#
# -----------------------------------------------------------------------------

echo "[sync-data] WARN: このスクリプトは雛形のみです。自分のデータソースに合わせて実装してください。" >&2
echo "[sync-data] README.md の「データ同期スクリプトを実装する」セクション参照。" >&2

# -----------------------------------------------------------------------------
# 共通: 期限切れ補助金を closed に自動更新
# -----------------------------------------------------------------------------
TODAY=$(date +%Y-%m-%d)
echo "[sync-data] application_end < $TODAY の制度を closed に更新..."
bash scripts/supabase-query.sh update supports \
  '{"status":"closed"}' \
  "status=eq.active&application_end=lt.${TODAY}" > /dev/null

echo "[sync-data] 同期完了"
