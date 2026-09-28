#!/usr/bin/env python3
"""
r2_upload.py - Cloudflare R2 にメディアをアップロードし、公開URLを発行/削除する（新規スクリプト）

Instagram Graph API はメディア投稿時に公開URL（image_url / video_url）を要求するため、
生成したバナー画像・リール動画を一時的にR2へ置いて公開URLを発行し、投稿完了後に削除する。

使い方:
  アップロード:
    python3 r2_upload.py upload --file OUTPUT_DIR/banner.png --key banners/2026-07-10_theme.png
    -> 標準出力に公開URLを1行で出す

  削除:
    python3 r2_upload.py delete --key banners/2026-07-10_theme.png

env（プロジェクトルートの .env から読む）:
  R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET, R2_PUBLIC_BASE_URL
"""
import argparse
import mimetypes
import os
import sys
from pathlib import Path

import boto3
from botocore.client import Config

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


def get_client():
    account_id = os.environ.get("R2_ACCOUNT_ID", "").strip()
    access_key = os.environ.get("R2_ACCESS_KEY_ID", "").strip()
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY", "").strip()
    if not (account_id and access_key and secret_key):
        print("[!] R2_ACCOUNT_ID / R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY が未設定です。", file=sys.stderr)
        sys.exit(1)
    endpoint = f"https://{account_id}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def cmd_upload(args) -> int:
    bucket = os.environ.get("R2_BUCKET", "").strip()
    base_url = os.environ.get("R2_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if not bucket or not base_url:
        print("[!] R2_BUCKET / R2_PUBLIC_BASE_URL が未設定です。", file=sys.stderr)
        return 1

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"[!] ファイルが見つかりません: {file_path}", file=sys.stderr)
        return 1

    content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    client = get_client()
    client.upload_file(
        str(file_path), bucket, args.key,
        ExtraArgs={"ContentType": content_type},
    )
    url = f"{base_url}/{args.key}"
    print(url)
    return 0


def cmd_delete(args) -> int:
    bucket = os.environ.get("R2_BUCKET", "").strip()
    if not bucket:
        print("[!] R2_BUCKET が未設定です。", file=sys.stderr)
        return 1
    client = get_client()
    client.delete_object(Bucket=bucket, Key=args.key)
    print(f"[ok] deleted: {args.key}")
    return 0


def main() -> int:
    load_env(PROJECT_ROOT)
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    up = sub.add_parser("upload")
    up.add_argument("--file", required=True)
    up.add_argument("--key", required=True, help="R2上のオブジェクトキー（例: banners/2026-07-10_theme.png）")

    de = sub.add_parser("delete")
    de.add_argument("--key", required=True)

    args = ap.parse_args()
    if args.cmd == "upload":
        return cmd_upload(args)
    if args.cmd == "delete":
        return cmd_delete(args)
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
