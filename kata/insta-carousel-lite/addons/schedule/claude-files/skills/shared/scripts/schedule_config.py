#!/usr/bin/env python3
"""schedule_config.py - config/schedule.yaml の読み込みと検証（唯一の入口）

launchd の登録（bin/render_launchd.py）と週次点検（audit_posts.py）が、同じこの関数で読む。
別々に読むと、片方だけが受け入れる書き方ができてしまい、「登録はされたが点検は数えていない」
「止めたつもりのジョブが動いている」が起きる。型は厳格に見る。とくに enabled は真偽値だけを受け付ける
（YAML の `enabled: "false"` は文字列で、Python では真と評価される。止めたつもりの投稿ジョブが有効になる）。

使い方:
  python3 .claude/skills/shared/scripts/schedule_config.py    # 検証して一覧を表示
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SCHEDULE_FILE = PROJECT_ROOT / "config" / "schedule.yaml"
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
PIPELINES = ("banner", "reel")  # record_post.py が受け付ける値と同じ
JOB_KEYS = {"enabled", "script", "pipeline", "times", "weekdays"}


class ScheduleError(ValueError):
    pass


def load_jobs(schedule_file: Path = SCHEDULE_FILE, project_root: Path = PROJECT_ROOT) -> dict[str, dict]:
    """検証済みのジョブを返す。{name: {enabled, script, pipeline(None可), times, weekdays(空=毎日)}}"""
    try:
        data = yaml.safe_load(schedule_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ScheduleError(f"{schedule_file} がありません")
    except yaml.YAMLError as e:
        raise ScheduleError(f"schedule.yaml を YAML として読めません: {e}")
    jobs = data.get("jobs") if isinstance(data, dict) else None
    if not isinstance(jobs, dict) or not jobs:
        raise ScheduleError("schedule.yaml に jobs がありません")

    out = {}
    for name, job in jobs.items():
        where = f"jobs.{name}"
        if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
            raise ScheduleError(f"ジョブ名は半角小文字・数字・ハイフンにしてください: {name!r}")
        if not isinstance(job, dict):
            raise ScheduleError(f"{where} が「キー: 値」の形になっていません")
        unknown = set(job) - JOB_KEYS
        if unknown:
            raise ScheduleError(f"{where} に知らないキーがあります（綴り間違い？）: {sorted(unknown)}")
        enabled = job.get("enabled")
        if not isinstance(enabled, bool):
            raise ScheduleError(f"{where}.enabled は true か false（引用符なし）で書いてください: {enabled!r}")
        script = job.get("script")
        if not isinstance(script, str) or not script.strip():
            raise ScheduleError(f"{where}.script がありません")
        if Path(script).is_absolute():
            raise ScheduleError(f"{where}.script はこのフォルダからの相対パスで書いてください（例: bin/run_banner.sh）: {script}")
        script_path = (project_root / script).resolve()
        if project_root.resolve() not in script_path.parents:
            raise ScheduleError(f"{where}.script はこのフォルダの中のファイルにしてください: {script}")
        if enabled and not script_path.is_file():
            raise ScheduleError(f"{where}.script が見つかりません: {script}")
        pipeline = job.get("pipeline")
        if pipeline is not None and pipeline not in PIPELINES:
            raise ScheduleError(f"{where}.pipeline は {list(PIPELINES)} のどれかにしてください: {pipeline!r}")
        times = job.get("times")
        if not isinstance(times, list) or not times:
            raise ScheduleError(f'{where}.times は ["09:00"] のようなリストで書いてください')
        for t in times:
            if not isinstance(t, str) or not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", t):
                raise ScheduleError(f'{where}.times は引用符つきの "HH:MM" で書いてください: {t!r}')
        if len(set(times)) != len(times):
            raise ScheduleError(f"{where}.times に同じ時刻が重複しています")
        weekdays = job.get("weekdays")
        if weekdays is None:
            weekdays = []
        if not isinstance(weekdays, list) or any(w not in WEEKDAYS for w in weekdays):
            raise ScheduleError(f"{where}.weekdays は {list(WEEKDAYS)} から選んだリストにしてください: {weekdays!r}")
        if len(set(weekdays)) != len(weekdays):
            raise ScheduleError(f"{where}.weekdays に同じ曜日が重複しています")
        out[name] = {"enabled": enabled, "script": script, "pipeline": pipeline,
                     "times": list(times), "weekdays": list(weekdays)}
    return out


def main() -> int:
    try:
        jobs = load_jobs()
    except ScheduleError as e:
        print(f"[error] {e}", file=sys.stderr)
        return 1
    for name, j in jobs.items():
        days = " ".join(j["weekdays"]) or "毎日"
        print(f"{'有効' if j['enabled'] else '無効'}  {name:16s} {days:28s} {' '.join(j['times'])}  → {j['pipeline'] or '（投稿なし）'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
