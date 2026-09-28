#!/bin/bash
# 公開済み記事の定期点検 — 機械チェック層のエントリポイント
#
# supports テーブルから記事を読み出し、scripts/article_health_check.py で
# リンク切れ・禁止表現・年度陳腐化・alt 不整合などを一括検出する。
# 図解画像の「中身」は機械判定できないため、--images で DL して目視キューを出す。
#
# 使い方:
#   bash scripts/article-health-check.sh                      # 全記事・フル (URL 到達性あり)
#   bash scripts/article-health-check.sh --quick              # 高頻度用 (ネットワーク不要・数秒)
#   bash scripts/article-health-check.sh --id 4 --id 11       # 記事を絞る
#   bash scripts/article-health-check.sh --images             # 図解画像を DL して目視キュー生成
#   bash scripts/article-health-check.sh --json .scratch/maintenance/health.json
#
# 終了コード: 0 = CRIT なし / 1 = CRIT あり (cron の失敗検知に使える)
#
# 前提: .env.local に NEXT_PUBLIC_SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY
#       (scripts/supabase-query.sh と同じ)

set -euo pipefail
cd "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null || cd "$(dirname "$0")/.."

# Git Bash (Windows) で日本語出力が cp932 に落ちて化けるのを防ぐ
export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1

PY=$(command -v python3 || command -v python || true)
if [ -z "$PY" ]; then
  echo "[health-check] ERROR: python3 / python が見つかりません" >&2
  exit 1
fi

WORK_DIR=".scratch/maintenance"
mkdir -p "$WORK_DIR"
SNAPSHOT="$WORK_DIR/supports-snapshot.json"

# summary は M19 (役所言葉) の検査対象 — トップのカード説明文 / meta description になるため
COLS="id,title,summary,category,target_scope,status,is_nationwide,amount_max,amount_note,support_rate,official_url,source_url,article_md,article_title,research_notes,updated_at,support_prefectures(prefectures(slug))"

echo "[health-check] supports を取得中 ..." >&2
bash scripts/supabase-query.sh select supports "select=${COLS}&order=id" > "$SNAPSHOT"

# 取得失敗 (PostgREST のエラー JSON はオブジェクト) を早期に検知
if ! head -c 1 "$SNAPSHOT" | grep -q '\['; then
  echo "[health-check] ERROR: supports の取得に失敗しました:" >&2
  head -c 500 "$SNAPSHOT" >&2
  echo >&2
  exit 1
fi

exec "$PY" scripts/article_health_check.py "$SNAPSHOT" "$@"
