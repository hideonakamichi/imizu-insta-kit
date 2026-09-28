#!/usr/bin/env python3
"""
refresh_token.py - Instagram長期アクセストークンの更新（新規スクリプト）

Phase 0のセットアップで、このプロジェクトのInstagramアカウントは「Instagram業務用ログイン」
（Facebookページ不要）で連携することが確定した。この方式のトークン更新は
Facebookの fb_exchange_token 方式ではなく、Instagram独自の ig_refresh_token 方式を使う。
META_APP_ID / META_APP_SECRET は不要（今のトークン自身だけで更新できる）。

Instagram Platform API仕様:
  GET https://graph.instagram.com/refresh_access_token
    ?grant_type=ig_refresh_token
    &access_token={現在のIG_ACCESS_TOKEN}
  -> {"access_token": "...", "token_type": "bearer", "expires_in": 5184000}

制約:
  - 対象トークンは発行/前回更新から24時間以上経過している必要がある
  - 既に失効したトークンは更新できない（その場合は手動でMeta developer consoleから再生成が必要）

更新成功時、.env の IG_ACCESS_TOKEN を書き換え、logs/token_state.json に
発行時刻(issued_at)と有効期間(expires_in)を記録する（check_token.pyが期限計算に使う）。

使い方:
  python3 refresh_token.py
"""
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[3]
TOKEN_STATE_PATH = PROJECT_ROOT / "logs" / "token_state.json"


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


def refresh_instagram_token(current_token: str) -> dict:
    url = "https://graph.instagram.com/refresh_access_token"
    params = {"grant_type": "ig_refresh_token", "access_token": current_token}
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(full_url, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"error": {"message": body, "code": e.code}}


def write_new_token(project_root: Path, new_token: str) -> None:
    """.env のIG_ACCESS_TOKEN行だけを書き換える（他の行は変更しない）。"""
    env_path = project_root / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines()
    found = False
    new_lines = []
    for line in lines:
        if re.match(r"^\s*IG_ACCESS_TOKEN\s*=", line):
            new_lines.append(f"IG_ACCESS_TOKEN={new_token}")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"IG_ACCESS_TOKEN={new_token}")
    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def write_token_state(expires_in: int) -> None:
    TOKEN_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "expires_in": expires_in,
    }
    TOKEN_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    load_env(PROJECT_ROOT)
    current_token = os.environ.get("IG_ACCESS_TOKEN", "").strip()

    if not current_token:
        print("[!] IG_ACCESS_TOKEN が未設定です。", file=sys.stderr)
        return 1

    print("[+] refreshing Instagram long-lived token (ig_refresh_token)...")
    result = refresh_instagram_token(current_token)
    if "error" in result:
        print(f"[!] token refresh failed: {result['error']}", file=sys.stderr)
        print("[!] トークンが既に失効している可能性があります。その場合はMeta developer console", file=sys.stderr)
        print("    のInstagram API設定画面から手動でトークンを再生成してください。", file=sys.stderr)
        return 1

    new_token = result["access_token"]
    expires_in = result.get("expires_in", 5184000)
    expires_in_days = expires_in / 86400

    write_new_token(PROJECT_ROOT, new_token)
    write_token_state(expires_in)

    print(f"[ok] token refreshed. expires_in={expires_in_days:.1f} days")
    return 0


if __name__ == "__main__":
    sys.exit(main())
