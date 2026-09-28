"""データの窓口（Lite 版）。元は Supabase の REST API、ここでは data/<テーブル>.json を読み書きする。

scripts/supabase-query.sh から呼ばれる。使い方は元と同じ:
  select  <table> "<条件>&select=a,b&order=id&limit=5"
  insert  <table> '<JSON>' | @<ファイル>
  update  <table> '<JSON>' | @<ファイル>  "<条件>"
  delete  <table> "<条件>"
Lite 版で足した動き（jq の代わり）:
  set     <table> "<条件>" 列=値 列=@text:<ファイル> 列=@json:<ファイル> …
  append  <table> "<条件>" <列>.<キー> '<JSON>' | @<ファイル>     例: research_notes.reviewer_verifications
条件で使えるもの: 列=eq.値 / neq / gt / gte / lt / lte / is.null / not.is.null / in.(a,b)
"""
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def fail(msg: str) -> None:
    print(json.dumps({"error": msg}, ensure_ascii=False))
    sys.exit(1)


def local_path(p: str) -> Path:
    """Git Bash の /tmp/... のような書き方を、Windows の Python が開ける形に直す。"""
    if os.name == "nt" and p.startswith("/") and not Path(p).exists():
        try:
            out = subprocess.run(["cygpath", "-w", p], capture_output=True, text=True).stdout.strip()
            if out:
                return Path(out)
        except OSError:
            pass
    return Path(p)


def read_arg(s: str) -> str:
    if s.startswith("@"):
        return local_path(s[1:]).read_text(encoding="utf-8")
    return s


def load(table: str) -> list:
    f = DATA / f"{table}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def save(table: str, rows: list) -> None:
    DATA.mkdir(exist_ok=True)
    tmp = DATA / f"{table}.json.tmp"
    tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(DATA / f"{table}.json")


def coerce(cell, raw: str):
    if isinstance(cell, bool):
        return raw.lower() == "true"
    if isinstance(cell, (int, float)):
        try:
            return type(cell)(raw)
        except ValueError:
            return raw
    return raw


def match(row: dict, key: str, cond: str) -> bool:
    v = row.get(key)
    neg = cond.startswith("not.")
    if neg:
        cond = cond[4:]
    op, _, raw = cond.partition(".")
    if op == "is":
        r = {"null": v is None, "true": v is True, "false": v is False}.get(raw.lower(), False)
    elif op == "in":
        items = [x.strip().strip('"') for x in raw.strip("()").split(",")]
        r = v is not None and str(v) in items
    elif v is None:
        r = False
    else:
        c = coerce(v, raw)
        r = {"eq": v == c, "neq": v != c, "gt": v > c, "gte": v >= c, "lt": v < c, "lte": v <= c}.get(op)
        if r is None:
            fail(f"この条件の書き方には対応していません: {key}={cond}")
    return (not r) if neg else r


def split_top(s: str) -> list:
    """select=a,b(c(d)),e をカッコの外のカンマで分ける。"""
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    return out + ([cur] if cur else [])


def parse_query(q: str):
    filters, cols, order, limit = [], None, None, None
    for part in [p for p in q.split("&") if p]:
        key, _, val = part.partition("=")
        if key == "select":
            cols = split_top(val)
        elif key == "order":
            order = val
        elif key == "limit":
            limit = int(val)
        else:
            filters.append((key, val))
    return filters, cols, order, limit


def pick(rows: list, q: str) -> list:
    filters, _, _, _ = parse_query(q)
    return [r for r in rows if all(match(r, k, c) for k, c in filters)]


def do_select(table: str, q: str) -> list:
    filters, cols, order, limit = parse_query(q)
    rows = [r for r in load(table) if all(match(r, k, c) for k, c in filters)]
    if order:
        col, _, direction = order.partition(".")
        rows.sort(key=lambda r: (r.get(col) is None, r.get(col)), reverse=direction == "desc")
    if limit is not None:
        rows = rows[:limit]
    if cols and cols != ["*"]:
        out = []
        for r in rows:
            o = {}
            for c in cols:
                if "(" in c:  # 他の表とのつながり（入れ子）。Lite 版では空で返す
                    o[c.split("(")[0]] = []
                else:
                    o[c] = r.get(c)
            out.append(o)
        rows = out
    return rows


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def main() -> None:
    if len(sys.argv) < 3:
        fail("使い方: supabase-query.sh select|insert|update|delete|set|append <table> ...")
    action, table, args = sys.argv[1], sys.argv[2], sys.argv[3:]

    if action == "select":
        result = do_select(table, args[0] if args else "")
    elif action == "insert":
        new = json.loads(read_arg(args[0]))
        new = new if isinstance(new, list) else [new]
        rows = load(table)
        nid = max([r.get("id", 0) for r in rows] + [0])
        for r in new:
            if "id" not in r:
                nid += 1
                r["id"] = nid
            r.setdefault("created_at", now())
            r.setdefault("updated_at", now())
        save(table, rows + new)
        result = new
    elif action in ("update", "set", "append", "delete"):
        rows = load(table)
        if action == "update":
            patch, q = json.loads(read_arg(args[0])), (args[1] if len(args) > 1 else "")
        else:
            q = args[0] if args else ""
        if not q:
            fail("条件が空です。全部の行を書き換えるのを防ぐため、条件（例: id=eq.1）を付けてください")
        hit = pick(rows, q)
        if action == "delete":
            save(table, [r for r in rows if r not in hit])
            result = hit
        else:
            if action == "set":
                patch = {}
                for a in args[1:]:
                    k, _, v = a.partition("=")
                    if v.startswith("@text:"):
                        v = local_path(v[6:]).read_text(encoding="utf-8")
                    elif v.startswith("@json:"):
                        v = json.loads(local_path(v[6:]).read_text(encoding="utf-8"))
                    patch[k] = v
            for r in hit:
                if action == "append":
                    col, _, key = args[1].partition(".")
                    item = json.loads(read_arg(args[2]))
                    box = r.get(col) or {}
                    box[key] = (box.get(key) or []) + [item]
                    r[col] = box
                else:
                    r.update(patch)
                r["updated_at"] = now()
            save(table, rows)
            result = hit
    elif action == "rpc":
        fail("Lite 版は rpc に対応していません（データベースの関数が無いため）")
    else:
        fail(f"知らない動きです: {action}")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
