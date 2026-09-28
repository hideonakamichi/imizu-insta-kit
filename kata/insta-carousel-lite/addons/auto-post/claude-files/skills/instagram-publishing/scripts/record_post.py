#!/usr/bin/env python3
"""
record_post.py - 投稿履歴を logs/posted.jsonl に追記する（新規スクリプト）

media_publish が成功しmedia_idを取得した後にのみ呼ぶ（冪等性のため）。
1投稿1行のJSONLで追記専用。日時はISO8601、タイムゾーンはUTC。

使い方:
  python3 record_post.py \
    --pipeline banner --theme "..." --media-id "..." --permalink "https://..."
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[3]
POSTED_LOG = PROJECT_ROOT / "logs" / "posted.jsonl"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pipeline", required=True, choices=["banner", "reel"])
    ap.add_argument("--theme", required=True)
    ap.add_argument("--media-id", required=True)
    ap.add_argument("--permalink", default="")
    ap.add_argument("--media-type", choices=["image", "carousel", "reels"], default=None,
                    help="投稿形式（bannerパイプラインのカルーセル投稿は carousel を指定）")
    ap.add_argument("--slide-count", type=int, default=None, help="カルーセルの枚数")
    args = ap.parse_args()

    entry = {
        "posted_at": datetime.now(timezone.utc).isoformat(),
        "pipeline": args.pipeline,
        "theme": args.theme,
        "media_id": args.media_id,
        "permalink": args.permalink,
    }
    if args.media_type:
        entry["media_type"] = args.media_type
    if args.slide_count is not None:
        entry["slide_count"] = args.slide_count

    import fcntl
    lock_file = PROJECT_ROOT / "logs" / "locks" / "ig_post.flock"  # ig_post.py と同じロック（状態ファイルの読み書きを直列にする）
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_file, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)  # 投稿処理が終わるまで待つ（記録は投稿の直後に呼ばれるので、通常は待たない）

        def valid_media_ids() -> tuple[set, list]:
            """(有効な行の media_id の集合, 壊れている行の番号)"""
            ids, broken = set(), []
            if POSTED_LOG.exists():
                for n, line in enumerate(POSTED_LOG.read_text(encoding="utf-8").split("\n"), 1):
                    if not line.strip():
                        continue
                    try:
                        ids.add(str(json.loads(line).get("media_id")))
                    except json.JSONDecodeError:
                        broken.append(n)
            return ids, broken

        ids, broken = valid_media_ids()
        if broken:
            # 書き込みの途中で切れた行などがある。そこへ追記すると新しい記録が壊れた行に連結されて読めなくなり、
            # 公開済みの投稿が履歴から失われる。状態ファイルは残したまま止める（次の投稿は止まったまま）
            print(f"[error] {POSTED_LOG} の {broken} 行目が JSON として読めません。その行を直す（または削除する）まで"
                  "記録しません。状態ファイルは残してあります", file=sys.stderr)
            return 1
        # 同じ media_id は二重に記録しない（記録の直後に中断して、復旧のためにもう一度実行したとき）
        if str(args.media_id) in ids:
            print(f"[ok] media_id={args.media_id} は記録済みです（二重には記録しません）")
        else:
            POSTED_LOG.parent.mkdir(parents=True, exist_ok=True)
            needs_newline = POSTED_LOG.exists() and POSTED_LOG.stat().st_size > 0 and \
                not POSTED_LOG.read_bytes().endswith(b"\n")
            with POSTED_LOG.open("a", encoding="utf-8") as f:
                f.write(("\n" if needs_newline else "") + json.dumps(entry, ensure_ascii=False) + "\n")
            print(f"[ok] recorded: {entry}")
        # 独立した有効な1行として読めることを確かめてから、下で状態を解除する
        ids, broken = valid_media_ids()
        if broken or str(args.media_id) not in ids:
            print("[error] 記録を確認できませんでした。状態ファイルは残してあります", file=sys.stderr)
            return 1

        # ig_post.py が残した「公開確定・記録待ち」の状態を解除する（同じ media_id を記録できたときだけ）。
        # unconfirmed / publishing の状態は、人が Instagram を確認してから手で消す（ここでは消さない）
        state_file = PROJECT_ROOT / "logs" / "PUBLISH_UNCONFIRMED.json"
        if state_file.exists():
            try:
                state = json.loads(state_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                state = {}
            if state.get("state") == "published_not_recorded" and str(state.get("media_id")) == str(args.media_id):
                state_file.unlink()
                print("[ok] 公開確定・記録待ちの状態を解除しました")
    return 0


if __name__ == "__main__":
    sys.exit(main())
