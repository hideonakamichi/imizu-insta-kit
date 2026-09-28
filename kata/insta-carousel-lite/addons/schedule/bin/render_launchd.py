#!/usr/bin/env python3
"""render_launchd.py — config/schedule.yaml から launchd の plist を生成する

bin/setup_launchd.sh から呼ばれる。単体でも使える:
  python3 bin/render_launchd.py --label-prefix com.me.insta --path "$PATH" --out launchd/generated
標準出力に「<ジョブ名>\t<enabled|disabled>」を1行ずつ出す（setup_launchd.sh が読む）。
"""
import argparse
import sys
from pathlib import Path
from xml.sax.saxutils import escape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / ".claude" / "skills" / "shared" / "scripts"))
from schedule_config import ScheduleError, load_jobs  # noqa: E402  検証はここに一本化（週次点検と共有）

# launchd の Weekday は 0=日曜 … 6=土曜
WEEKDAYS = {"sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6}


def calendar_xml(job: dict) -> str:
    entries = []
    for t in job["times"]:
        hour, minute = (int(x) for x in str(t).split(":"))
        for wd in [WEEKDAYS[w] for w in (job.get("weekdays") or [])] or [None]:
            rows = [] if wd is None else [f"<key>Weekday</key><integer>{wd}</integer>"]
            rows += [f"<key>Hour</key><integer>{hour}</integer>", f"<key>Minute</key><integer>{minute}</integer>"]
            entries.append("        <dict>\n" + "".join(f"            {r}\n" for r in rows) + "        </dict>\n")
    return "    <array>\n" + "".join(entries) + "    </array>"


def render(name: str, job: dict, label_prefix: str, env_path: str) -> str:
    root = escape(str(PROJECT_ROOT))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<!-- config/schedule.yaml から bin/render_launchd.py が生成。手で編集せず、schedule.yaml を直して
     bash bin/setup_launchd.sh を再実行する -->
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{escape(label_prefix)}.{name}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{root}/{escape(str(job["script"]))}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{root}</string>
    <key>StartCalendarInterval</key>
{calendar_xml(job)}
    <key>StandardOutPath</key>
    <string>{root}/logs/launchd/{name}_stdout.log</string>
    <key>StandardErrorPath</key>
    <string>{root}/logs/launchd/{name}_stderr.log</string>
    <!-- launchd は shell の PATH を継承しないので、claude/python3/ffmpeg のある場所を埋め込む -->
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>{escape(env_path)}</string>
    </dict>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label-prefix", required=True)
    ap.add_argument("--path", required=True, help="plist に埋め込む PATH")
    ap.add_argument("--out", required=True, help="plist の出力先ディレクトリ")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob(f"{args.label_prefix}.*.plist"):
        old.unlink()
    try:
        jobs = load_jobs()
    except ScheduleError as e:
        sys.exit(f"[error] config/schedule.yaml: {e}")
    for name, job in jobs.items():
        if job["enabled"]:
            (out / f"{args.label_prefix}.{name}.plist").write_text(
                render(name, job, args.label_prefix, args.path), encoding="utf-8")
        print(f"{name}\t{'enabled' if job['enabled'] else 'disabled'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
