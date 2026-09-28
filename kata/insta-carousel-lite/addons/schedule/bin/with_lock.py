#!/usr/bin/env python3
"""with_lock.py — ロックを持ったままコマンドを実行する（bin/run-agent.sh が使う）

  python3 bin/with_lock.py --lock logs/locks/posting.flock --wait 2400 -- bash bin/run-agent.sh <slug>

fcntl.flock を使う。ロックは**持っているプロセスがいなくなれば OS が自動で外す**ので、異常終了で
ロックが残って以降の定期実行が黙ってスキップされ続ける、ということが起きない。「古いロックを消して
取り直す」処理も要らない（その処理自体が競合して、2つの起動が同時に通り抜ける穴になっていた）。

ロックのファイル記述子は子プロセスに引き継ぐ（pass_fds）。このスクリプトだけが先に死んでも、
実行中のパイプライン（run-agent.sh → claude）が生きている間はロックが保たれる。

終了コード: 子プロセスの終了コード。ロックを取れなかったら 75（EX_TEMPFAIL）。
"""
import argparse
import fcntl
import os
import subprocess
import sys
import time
from pathlib import Path

EX_TEMPFAIL = 75


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lock", required=True)
    ap.add_argument("--wait", type=int, default=0, help="ロックが空くのを待つ秒数（0 なら待たない）")
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    args = ap.parse_args()
    cmd = args.cmd[1:] if args.cmd[:1] == ["--"] else args.cmd
    if not cmd:
        ap.error("実行するコマンドがありません")

    lock_path = Path(args.lock)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)
    deadline = time.time() + max(0, args.wait)
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if time.time() >= deadline:
                return EX_TEMPFAIL
            time.sleep(15)
    env = dict(os.environ, INSTA_LOCK_HELD=str(lock_path))
    rc = subprocess.run(cmd, pass_fds=[fd], env=env).returncode
    return 128 - rc if rc < 0 else rc  # シグナルで終わった子は、シェルと同じ 128+シグナル番号で返す


if __name__ == "__main__":
    sys.exit(main())
