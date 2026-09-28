#!/usr/bin/env python3
"""
check_token.py - アクセストークンの残存期限チェック（新規スクリプト）

Phase 0のセットアップで、このプロジェクトのInstagramアカウントは「Instagram業務用ログイン」
（graph.instagram.com、Facebookページ不要）で連携することが確定した。この方式には
Facebookの /debug_token に相当する期限照会APIが無いため、以下の2段構えで判定する。

  1. 生存確認: graph.instagram.com への軽量リクエスト（IG_USER_IDの id フィールド取得）で
     トークンが今も有効かを実際に確認する
  2. 残存日数の計算: logs/token_state.json に記録した issued_at + expires_in から算出する
     （state fileが無い場合はこの実行時点を issued_at として新規作成し、issued_at_assumed=True を
     立てる。これは残存日数を最大に見積もる楽観的な仮定なので、レポート側で「暫定値」と
     明示する必要がある。実際の発行日が分かるなら token_state.json を手で直す）

残存日数が config/loop-limits.yaml の token_refresh.warn_before_days 以下になったら
refresh_token.py を呼んで自動更新する。

使い方:
  python3 check_token.py
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[3]
PUBLISHING_SCRIPTS = PROJECT_ROOT / ".claude" / "skills" / "instagram-publishing" / "scripts"
TOKEN_STATE_PATH = PROJECT_ROOT / "logs" / "token_state.json"

DEFAULT_WARN_DAYS = 10
DEFAULT_EXPIRES_IN = 5184000  # 60日（秒）。Instagram長期トークンの標準有効期間


def load_env(project_root: Path) -> None:
    env_path = project_root / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if v and k not in os.environ:
            os.environ[k] = v


def load_warn_days(project_root: Path) -> int:
    yaml_path = project_root / "config" / "loop-limits.yaml"
    if not yaml_path.exists():
        return DEFAULT_WARN_DAYS
    text = yaml_path.read_text(encoding="utf-8")
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("warn_before_days:"):
            try:
                return int(s.split(":", 1)[1].strip())
            except ValueError:
                pass
    return DEFAULT_WARN_DAYS


def check_liveness(ig_user_id: str, token: str, api_version: str) -> dict:
    """軽量な認証付きリクエストでトークンが今も有効か確認する。"""
    url = f"https://graph.instagram.com/{api_version}/{ig_user_id}"
    params = {"fields": "id", "access_token": token}
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(full_url, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"error": {"message": body, "code": e.code}}


def load_or_init_token_state() -> dict:
    if TOKEN_STATE_PATH.exists():
        try:
            return json.loads(TOKEN_STATE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    # state fileが無い場合、この実行時点を issued_at として新規作成する。
    #
    # 注意: これは「保守的」ではなく残存日数を最大に見積もる楽観的な仮定である。
    # state file は配布物に含まれないため、新規導入者は必ずこの経路を通る。
    # 既に発行から55日経ったトークンを .env に入れても「残り60日」と算出されるため、
    # issued_at_assumed=True を立てて呼び出し側（SKILL.md の週次点検レポート）に
    # 「この残存日数は未確認」と伝える。実際の発行日が分かる場合は
    # logs/token_state.json の issued_at を手で正しい日時に直すこと。
    state = {
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "expires_in": DEFAULT_EXPIRES_IN,
        "issued_at_assumed": True,
    }
    TOKEN_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state


def main() -> int:
    load_env(PROJECT_ROOT)
    token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
    ig_user_id = os.environ.get("IG_USER_ID", "").strip()
    api_version = os.environ.get("GRAPH_API_VERSION", "v21.0").strip()
    warn_days = load_warn_days(PROJECT_ROOT)

    if not (token and ig_user_id):
        print(json.dumps({"ok": False, "error": "IG_ACCESS_TOKEN/IG_USER_ID未設定"}))
        return 1

    liveness = check_liveness(ig_user_id, token, api_version)
    if "error" in liveness:
        print(json.dumps({"ok": False, "valid": False, "error": liveness["error"]}, ensure_ascii=False))
        return 1

    state = load_or_init_token_state()
    issued_at = datetime.fromisoformat(state["issued_at"])
    expires_in = state.get("expires_in", DEFAULT_EXPIRES_IN)
    expires_at = issued_at.timestamp() + expires_in
    remaining_days = int((expires_at - datetime.now(timezone.utc).timestamp()) / 86400)

    summary = {
        "ok": True,
        "valid": True,
        "issued_at": state["issued_at"],
        "remaining_days": remaining_days,
        "refreshed": False,
    }
    if state.get("issued_at_assumed"):
        # 発行日が未確認なので remaining_days は当てにならない。レポートに明示させる。
        summary["issued_at_assumed"] = True
        summary["note"] = (
            "issued_at が未確認のため remaining_days は暫定値です"
            "（token_state.json を今回新規作成しました）。実際の発行日が分かる場合は "
            "logs/token_state.json の issued_at を修正するか、"
            "refresh_token.py を1回実行して発行日を確定させてください"
        )

    if remaining_days <= warn_days:
        print(f"[!] トークン残存 {remaining_days}日（閾値{warn_days}日以下）。自動更新を試みます。", file=sys.stderr)
        refresh_result = subprocess.run(
            [sys.executable, str(PUBLISHING_SCRIPTS / "refresh_token.py")],
            capture_output=True, text=True,
        )
        summary["refresh_attempted"] = True
        summary["refresh_stdout"] = refresh_result.stdout.strip()
        summary["refreshed"] = refresh_result.returncode == 0
        if refresh_result.returncode != 0:
            summary["refresh_stderr"] = refresh_result.stderr.strip()

    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
