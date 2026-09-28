#!/usr/bin/env bash
# setup_launchd.sh — launchd の定期実行を設定する
#
# config/schedule.yaml（スケジュールの唯一の正）から plist を生成し、
# ~/Library/LaunchAgents/ に配置して読み込む。schedule.yaml で enabled: false にした
# ジョブは、再実行すると解除される。
#
# 使い方:
#   bash bin/setup_launchd.sh            # plist を生成して読み込む（無効にしたジョブは解除）
#   bash bin/setup_launchd.sh --dry-run  # 生成だけして読み込まない（中身を確認したいとき）
#   bash bin/setup_launchd.sh --unload   # このプロジェクトのジョブをすべて解除する
#   bash bin/setup_launchd.sh --status   # 登録状況と次回の予定を表示する
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AGENTS_DIR="$HOME/Library/LaunchAgents"
BUILD_DIR="$PROJECT_ROOT/launchd/generated"

# Label は「ユーザー名＋フォルダ名＋置き場所のハッシュ」で作る。フォルダ名だけだと、別の場所にある同名フォルダや、
# 記号違い（kit_a と kit-a）、日本語だけの名前（英数字に直すと空になる）で衝突し、後から登録したキットが
# 先のキットのジョブを上書き・解除してしまう。フォルダを移動したら、移動前に --unload しておくこと。
# 変えたいときは環境変数 INSTA_LABEL_PREFIX で上書きする
DIR_SLUG="$(basename "$PROJECT_ROOT" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9-' '-' | sed -e 's/--*/-/g' -e 's/^-//' -e 's/-$//')"
PATH_HASH="$(printf '%s' "$PROJECT_ROOT" | shasum | cut -c1-8)"
LABEL_PREFIX="${INSTA_LABEL_PREFIX:-com.$(id -un | tr -cd '[:alnum:]').${DIR_SLUG:-insta}-${PATH_HASH}}"

usage() { sed -n '2,/^set -euo/p' "${BASH_SOURCE[0]}" | grep '^#' | sed 's/^# \{0,1\}//'; exit 0; }

MODE="install"
case "${1:-}" in
  --dry-run) MODE="dry-run" ;;
  --unload)  MODE="unload" ;;
  --status)  MODE="status" ;;
  --help|-h) usage ;;
  "")        ;;
  *) echo "不明なオプション: $1" >&2; exit 1 ;;
esac

if [[ "$(uname)" != "Darwin" ]]; then
  echo "[error] launchd は macOS 専用です。ほかのOSでは cron 等で bin/run_*.sh を呼んでください。" >&2
  exit 1
fi

owned_by_this_project() {  # 既存の plist がこのフォルダのものか（INSTA_LABEL_PREFIX を手で揃えた場合の保険）
  local wd
  wd="$(/usr/libexec/PlistBuddy -c "Print :WorkingDirectory" "$1" 2>/dev/null || true)"
  [[ "$wd" == "$PROJECT_ROOT" ]]
}

unload_job() {  # unload_job <label>
  local plist="$AGENTS_DIR/$1.plist"
  if [[ -f "$plist" ]] && ! owned_by_this_project "$plist"; then
    echo "[error] $1 は別のフォルダのジョブです（$plist）。上書き・解除しません。INSTA_LABEL_PREFIX を別の値にしてください。" >&2
    exit 1
  fi
  launchctl bootout "gui/$(id -u)/$1" 2>/dev/null || true
  if [[ -f "$plist" ]]; then rm -f "$plist"; echo "[unloaded] $1"; fi
}

installed_labels() {
  find "$AGENTS_DIR" -maxdepth 1 -name "${LABEL_PREFIX}.*.plist" 2>/dev/null \
    | sed -e "s|^$AGENTS_DIR/||" -e 's|\.plist$||' | sort
}

if [[ "$MODE" == "unload" ]]; then
  for label in $(installed_labels); do unload_job "$label"; done
  echo "解除しました（prefix: $LABEL_PREFIX）"
  exit 0
fi

if [[ "$MODE" == "status" ]]; then
  echo "prefix: $LABEL_PREFIX"
  for label in $(installed_labels); do
    echo "--- $label"
    /usr/libexec/PlistBuddy -c "Print :StartCalendarInterval" "$AGENTS_DIR/$label.plist" | tr -d '\n' | sed 's/  */ /g'; echo
  done
  [[ -z "$(installed_labels)" ]] && echo "（登録されているジョブはありません）"
  exit 0
fi

# --- 前提コマンドの確認 -------------------------------------------------
MISSING=()
for cmd in claude python3; do
  command -v "$cmd" >/dev/null 2>&1 || MISSING+=("$cmd")
done
# ffmpeg と grok はリールにだけ要る（カルーセルだけの運用なら無くてよい）
for cmd in ffmpeg grok; do
  command -v "$cmd" >/dev/null 2>&1 || echo "[warn] $cmd が見つかりません。リールのジョブを有効にするなら入れてください（README「必要なもの」）"
done
if (( ${#MISSING[@]} > 0 )); then
  echo "[error] 次のコマンドが見つかりません: ${MISSING[*]}" >&2
  echo "        README.md の「必要なもの」を先に済ませてください。" >&2
  exit 1
fi

PYTHON="python3"
[[ -x "$PROJECT_ROOT/.venv/bin/python3" ]] && PYTHON="$PROJECT_ROOT/.venv/bin/python3"
if ! "$PYTHON" -c "import yaml" 2>/dev/null; then
  echo "[error] PyYAML が入っていません。README の手順で .venv を作ってから再実行してください:" >&2
  echo "        python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt" >&2
  exit 1
fi

# launchd は shell の PATH を継承しないため、必要なコマンドの実ディレクトリを集めて埋め込む
PATH_DIRS=""
for cmd in claude python3 ffmpeg grok; do
  command -v "$cmd" >/dev/null 2>&1 || continue
  d="$(dirname "$(command -v "$cmd")")"
  case ":$PATH_DIRS:" in *":$d:"*) ;; *) PATH_DIRS="${PATH_DIRS:+$PATH_DIRS:}$d" ;; esac
done
EMBED_PATH="${PATH_DIRS}:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

# --- plist を生成 -------------------------------------------------------
mkdir -p "$BUILD_DIR" "$PROJECT_ROOT/logs/launchd"
JOB_LIST="$("$PYTHON" "$PROJECT_ROOT/bin/render_launchd.py" --label-prefix "$LABEL_PREFIX" --path "$EMBED_PATH" --out "$BUILD_DIR")"
ENABLED=()
while IFS=$'\t' read -r name state; do
  [[ -z "$name" ]] && continue
  if [[ "$state" == "enabled" ]]; then
    plutil -lint "$BUILD_DIR/${LABEL_PREFIX}.${name}.plist" >/dev/null
    ENABLED+=("$name")
    echo "[built] ${LABEL_PREFIX}.${name}"
  else
    echo "[skip]  ${name}（schedule.yaml で enabled: false）"
  fi
done <<< "$JOB_LIST"

if [[ "$MODE" == "dry-run" ]]; then
  echo
  echo "生成のみで終了しました（$BUILD_DIR）。引数なしで実行すると読み込みます:"
  echo "  bash bin/setup_launchd.sh"
  exit 0
fi

# --- 読み込み（無効になったジョブ・schedule.yaml から消えたジョブは解除） ---------
mkdir -p "$AGENTS_DIR"
for label in $(installed_labels); do
  name="${label#"$LABEL_PREFIX".}"
  keep=false
  for e in ${ENABLED[@]+"${ENABLED[@]}"}; do [[ "$e" == "$name" ]] && keep=true; done
  $keep || unload_job "$label"
done
for name in ${ENABLED[@]+"${ENABLED[@]}"}; do
  label="${LABEL_PREFIX}.${name}"
  if [[ -f "$AGENTS_DIR/${label}.plist" ]] && ! owned_by_this_project "$AGENTS_DIR/${label}.plist"; then
    echo "[error] ${label} は別のフォルダのジョブとして登録済みです。上書きしません。INSTA_LABEL_PREFIX を別の値にしてください。" >&2
    exit 1
  fi
  cp "$BUILD_DIR/${label}.plist" "$AGENTS_DIR/${label}.plist"
  launchctl bootout "gui/$(id -u)/${label}" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$AGENTS_DIR/${label}.plist"
  echo "[loaded] $label"
done

echo
echo "登録状況の確認:  bash bin/setup_launchd.sh --status"
echo
echo "注意: 予定の時刻に Mac がスリープしていると、ジョブは**スリープから復帰した時点で遅れて実行**されます"
echo "      （電源が切れていた場合は実行されません）。決めた時刻に投稿したいなら、システム設定 > バッテリー"
echo "      （またはロック画面）で、その時刻にスリープしない設定にしてください。"
echo "注意: このフォルダで一度 'claude' を対話モードで起動し、信頼の確認ダイアログを承認しておいてください。"
echo "      未承認だと .claude/settings.json の許可が無視され、無人実行はすべての処理が拒否されて止まります。"
