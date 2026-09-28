"""check_grok.py — Grok CLI の疎通・サインイン状態を確認する（週次点検用）

画像・動画生成はGrok CLI（サブスクのサインイン）に依存しているため、
サインイン失効・CLI破損は「生成が全部止まる」ことを意味する。
無人運用で気づけるよう、週次点検で軽量プロンプトの応答を確認する。

出力（JSON）:
  {"ok": true,  "grok_bin": "...", "response": "pong"}
  {"ok": false, "grok_bin": "...", "error": "..."}

exit code: ok=0 / NG=1（NGならオーケストレーターがDiscordの緊急通知に含める）
"""

import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[3]

sys.path.insert(0, str(PROJECT_ROOT / ".claude/skills/shared/scripts"))
import grok_media


def main() -> int:
    result = {"ok": False, "grok_bin": None, "error": None}
    try:
        grok_bin = grok_media.resolve_grok()
        result["grok_bin"] = grok_bin
    except FileNotFoundError as e:
        result["error"] = str(e)
        print(json.dumps(result, ensure_ascii=False))
        return 1

    try:
        proc = subprocess.run(
            [grok_bin, "--max-turns", "1", "-p", "pong とだけ返答してください"],
            capture_output=True, text=True, timeout=120,
        )
        out = (proc.stdout or "").strip()
        if proc.returncode == 0 and out:
            result["ok"] = True
            result["response"] = out[-100:]
        else:
            result["error"] = (
                f"exit={proc.returncode}: {(proc.stderr or out)[-300:]} "
                "（サインイン失効の可能性。`grok login` で再サインインしてください）"
            )
    except subprocess.TimeoutExpired:
        result["error"] = "120秒応答なし（ネットワークまたは認証の問題の可能性）"

    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
