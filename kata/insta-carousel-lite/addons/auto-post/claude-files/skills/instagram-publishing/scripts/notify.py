#!/usr/bin/env python3
"""
notify.py - Discord Webhook通知（新規スクリプト）

成功時・失敗時のテンプレートでDiscordに通知する。参照リポジトリの
DISCORD_WEBHOOK_URL パターンを踏襲。

使い方:
  成功:
    python3 notify.py success \
      --pipeline banner --theme "..." --url "https://instagram.com/p/..." \
      --duration-sec 120

  失敗:
    python3 notify.py failure \
      --pipeline reel --stage "evaluator" --error "sub_textが読み切れない" \
      --artifact-dir output/2026-07-10_theme/

  汎用レポート（system-healthcheck用）:
    python3 notify.py report --title "週次点検レポート" --body "..."

env（プロジェクトルートの .env から読む）:
  DISCORD_WEBHOOK_URL
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[3]


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


def send(webhook_url: str, content: str) -> bool:
    payload = json.dumps({"content": content}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url, data=payload, method="POST",
        headers={
            "Content-Type": "application/json",
            # DiscordのWebhookエンドポイントはCloudflare経由で、Pythonの既定User-Agent
            # （Python-urllib/x.y）だとボット対策でHTTP 403 (Cloudflare error 1010) になる。
            # ブラウザ相当のUser-Agentを明示して回避する。
            "User-Agent": "Mozilla/5.0 (compatible; insta-jidouka/1.0)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return 200 <= resp.status < 300
    except urllib.error.HTTPError as e:
        print(f"[!] Discord webhook failed: HTTP {e.code} {e.read().decode()}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[!] Discord webhook failed: {e}", file=sys.stderr)
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    ok = sub.add_parser("success")
    ok.add_argument("--pipeline", required=True, help="banner / reel")
    ok.add_argument("--theme", required=True)
    ok.add_argument("--url", default="", help="投稿のpermalink")
    ok.add_argument("--duration-sec", type=float, default=None)

    ng = sub.add_parser("failure")
    ng.add_argument("--pipeline", required=True)
    ng.add_argument("--stage", required=True)
    ng.add_argument("--error", required=True)
    ng.add_argument("--artifact-dir", default="")

    rep = sub.add_parser("report")
    rep.add_argument("--title", required=True)
    rep.add_argument("--body", required=True)

    args = ap.parse_args()

    load_env(PROJECT_ROOT)
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook_url:
        print("[!] DISCORD_WEBHOOK_URL が未設定のため通知をスキップします。", file=sys.stderr)
        return 1

    if args.cmd == "success":
        lines = [f"✅ **{args.pipeline}投稿 成功**", f"テーマ: {args.theme}"]
        if args.url:
            lines.append(f"投稿URL: {args.url}")
        if args.duration_sec is not None:
            lines.append(f"所要時間: {args.duration_sec:.0f}秒")
        content = "\n".join(lines)
    elif args.cmd == "failure":
        lines = [
            f"❌ **{args.pipeline}投稿 失敗**",
            f"ステージ: {args.stage}",
            f"エラー: {args.error}",
        ]
        if args.artifact_dir:
            lines.append(f"生成物の退避先: {args.artifact_dir}")
        content = "\n".join(lines)
    else:  # report
        content = f"📋 **{args.title}**\n{args.body}"

    ok_sent = send(webhook_url, content)
    if not ok_sent:
        return 1
    record_sent(args)
    print("[ok] notified via Discord")
    return 0


NOTIFY_LOG = PROJECT_ROOT / "logs" / "notify.jsonl"


def record_sent(args: argparse.Namespace) -> None:
    """送信済み通知を logs/notify.jsonl に1行追記する。

    bin/run-agent.sh はこの行数の増減で「オーケストレーターが自分で通知したか」を判定し、
    通知済みなら最終防衛線の「投稿が確認できませんでした」通知を省略する
    （2026-09-16: evaluator 不合格で中止した際に失敗通知が2通届いた）。
    """
    try:
        from datetime import datetime, timezone
        NOTIFY_LOG.parent.mkdir(parents=True, exist_ok=True)
        rec = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "run_id": os.environ.get("INSTA_RUN_ID", ""),  # bin/run-agent.sh が起動ごとに設定
            "kind": args.cmd,
            "pipeline": getattr(args, "pipeline", None),
            "stage": getattr(args, "stage", None),
        }
        with NOTIFY_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception as e:  # noqa: BLE001 — 記録失敗で通知自体を失敗扱いにしない
        print(f"[!] notify.jsonl への記録に失敗: {e}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
