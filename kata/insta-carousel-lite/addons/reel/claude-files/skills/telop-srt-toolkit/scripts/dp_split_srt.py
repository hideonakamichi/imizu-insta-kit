"""dp_split_srt.py - DP最適分割で SRT をテロップ単位に再構成

参照: myuuu-io/youtube .claude/skills/telop-srt-toolkit/scripts/dp_split_srt.py をそのまま流用
（言語処理・DPアルゴリズムは汎用のため改修不要）。

担当:
  - 全文連結（タイムコード按分）
  - 重複ノイズ削除（といういう → という 等）
  - 英字＋英字境界保護（ClaudeCode → Claude Code 等）
  - 動的計画法で最適分割（min/ideal/max 引数指定可）
  - 強制分割（max 超過時の保険）
  - 順序保証・最低表示時間確保

Usage:
    python3 dp_split_srt.py \
        --input CORRECTED.srt \
        --out FINAL.srt \
        --grammar references/caption-grammar.md \
        --min 4 --ideal 15 --max 22
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path


STRENGTH_VALUES = {
    "ULTRA": 300,
    "STRONG": 80,
    "MEDIUM": 40,
    "WEAK": 10,
    "SPACE": 3,
}


def parse_grammar(md_path: str) -> dict[str, list[str]]:
    """caption-grammar.md を読み込み、強さレベル別の表現リストを返す。
    Returns: {"ULTRA": [...], "STRONG": [...], "MEDIUM": [...], "WEAK": [...]}
    """
    result = {k: [] for k in STRENGTH_VALUES if k != "SPACE"}
    if not md_path or not Path(md_path).exists():
        return result
    current_section = None
    for line in Path(md_path).read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("## "):
            for level in result:
                if level in s.upper():
                    current_section = level
                    break
            continue
        if not s or s.startswith("#") or s.startswith("|") or s.startswith("```") or s.startswith("-"):
            continue
        if current_section:
            result[current_section].append(s)
    return result


def is_jp(c: str) -> bool:
    return (
        "぀" <= c <= "ゟ"
        or "゠" <= c <= "ヿ"
        or "一" <= c <= "鿿"
    )


def is_alpha(c: str) -> bool:
    return c.isalpha() and c.isascii()


def is_hiragana(c: str) -> bool:
    return "ぁ" <= c <= "ゖ"


def parse_ts(ts: str) -> int:
    h, m, rest = ts.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(ms)


def fmt_ts(ms: int) -> str:
    return (
        f"{ms//3600000:02d}:{(ms%3600000)//60000:02d}"
        f":{(ms%60000)//1000:02d},{ms%1000:03d}"
    )


def ms_replace(text: str, ms_list: list[int], old: str, new: str) -> tuple[str, list[int]]:
    """text 中の old を new に置換、ms_list も連動。"""
    diff = len(new) - len(old)
    idx = 0
    while True:
        idx = text.find(old, idx)
        if idx < 0:
            break
        if diff > 0:
            ms_list = ms_list[:idx] + [ms_list[idx]] * diff + ms_list[idx:]
            text = text[:idx] + new + text[idx + len(old):]
        elif diff < 0:
            ms_list = ms_list[:idx + len(new)] + ms_list[idx + len(old):]
            text = text[:idx] + new + text[idx + len(old):]
        else:
            text = text[:idx] + new + text[idx + len(old):]
        idx += len(new)
    return text, ms_list


def force_split(text: str, max_len: int, ideal: int) -> list[str]:
    """max_len 超過時の保険として強制分割。"""
    if len(text) <= max_len:
        return [text]
    out, rest = [], text
    while len(rest) > max_len:
        sp = rest.rfind(" ", 0, max_len + 1)
        if sp > 5:
            out.append(rest[:sp].strip())
            rest = rest[sp + 1:].strip()
        else:
            out.append(rest[:ideal])
            rest = rest[ideal:]
    if rest:
        out.append(rest.strip())
    return [x for x in out if x]


def dp_split(
    text: str,
    ms_list: list[int],
    grammar: dict[str, list[str]],
    min_len: int,
    ideal: int,
    max_len: int,
) -> list[tuple[int, int, str]]:
    """DP で最適分割。Returns: [(start_ms, end_ms, chunk_text), ...]"""
    n = len(text)
    strength = {0: 0, n: 500}
    for level, endings in grammar.items():
        val = STRENGTH_VALUES[level]
        for end in endings:
            # 単一文字の助詞（は/の/を/が/に/で/と 等）は text.find() の単純一致だと
            # 「当てはまる」のような単語内部にもマッチしてしまい、字幕が単語の途中で
            # 割れるバグになる（Phase 2のリール実行で実際に発生・evaluatorが検出）。
            # 直後がひらがなに続く場合は単語の内部である可能性が高いため、
            # 1文字の語尾に限り除外する（2文字以上の語尾はこの誤検出が起きにくいため対象外）。
            single_char_particle = len(end) == 1
            i = 0
            while True:
                i = text.find(end, i)
                if i < 0:
                    break
                pos = i + len(end)
                if single_char_particle and pos < n and is_hiragana(text[pos]):
                    i += 1
                    continue
                strength[pos] = max(strength.get(pos, 0), val)
                i += 1
    for i, c in enumerate(text):
        if c == " ":
            strength.setdefault(i + 1, STRENGTH_VALUES["SPACE"])

    points = sorted(strength.keys())
    INF = float("inf")
    cost = defaultdict(lambda: INF)
    cost[0] = 0
    prev = {0: None}

    for i, pi in enumerate(points):
        if cost[pi] >= INF:
            continue
        for j in range(i + 1, len(points)):
            pj = points[j]
            chunk = text[pi:pj].strip()
            cl = len(chunk)
            if cl == 0:
                continue
            if cl > max_len + 18:
                break
            c = abs(cl - ideal) ** 1.6
            if cl < min_len:
                c += 200
            if cl > max_len:
                c += (cl - max_len) ** 2 * 6
            c -= strength.get(pj, 0) * 0.8
            nc = cost[pi] + c
            if nc < cost[pj]:
                cost[pj] = nc
                prev[pj] = pi

    if cost[n] >= INF:
        reachable = max(p for p in cost if cost[p] < INF and p <= n)
        cost[n] = cost[reachable]
        prev[n] = reachable

    spans, cur, visited = [], n, set()
    while cur > 0:
        if cur in visited or cur not in prev:
            spans.append((0, cur))
            break
        visited.add(cur)
        prv = prev[cur]
        spans.append((prv, cur))
        cur = prv
    spans.reverse()

    out = []
    for st, en in spans:
        chunk = text[st:en].strip()
        if not chunk:
            continue
        s_ms = ms_list[st] if st < len(ms_list) else ms_list[-1]
        e_ms = ms_list[min(en - 1, len(ms_list) - 1)]
        if e_ms - s_ms < 500:
            e_ms = s_ms + 500
        subs = force_split(chunk, max_len, ideal)
        if len(subs) == 1:
            out.append((s_ms, e_ms, chunk))
        else:
            total = sum(len(s) for s in subs)
            cum, dur = 0, e_ms - s_ms
            for sb in subs:
                ns = s_ms + int(cum / total * dur)
                cum += len(sb)
                ne = s_ms + int(cum / total * dur)
                if ne - ns < 500:
                    ne = ns + 500
                out.append((ns, ne, sb))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--grammar", default=None, help="caption-grammar.md")
    ap.add_argument("--min", type=int, default=4, dest="min_len")
    ap.add_argument("--ideal", type=int, default=15)
    ap.add_argument("--max", type=int, default=22, dest="max_len")
    args = ap.parse_args()

    grammar = parse_grammar(args.grammar) if args.grammar else {
        k: [] for k in STRENGTH_VALUES if k != "SPACE"
    }
    if not any(grammar.values()):
        print("Warning: no grammar rules loaded", file=sys.stderr)

    raw = Path(args.input).read_text(encoding="utf-8")
    blocks = re.split(r"\n\n+", raw.strip())
    captions = []
    for b in blocks:
        bl = b.strip().split("\n")
        if len(bl) < 3:
            continue
        s_str, e_str = bl[1].split(" --> ")
        body = " ".join(bl[2:])
        captions.append((parse_ts(s_str), parse_ts(e_str), body))

    all_text, ms_list, prev_last = "", [], ""
    for s, e, t in captions:
        if not t:
            continue
        if prev_last and is_alpha(prev_last) and is_alpha(t[0]):
            all_text += " "
            ms_list.append(s)
        L = len(t)
        for i in range(L):
            ms_list.append(s + int(i / L * (e - s)) if L > 1 else s)
        all_text += t
        prev_last = t[-1]

    for old, new in [
        ("といういう", "という"),
        ("ということと", "ということ"),
        ("しているしている", "している"),
    ]:
        all_text, ms_list = ms_replace(all_text, ms_list, old, new)

    new_t, new_m, i = [], [], 0
    while i < len(all_text):
        c = all_text[i]
        if (
            c == " "
            and 0 < i < len(all_text) - 1
            and is_jp(all_text[i - 1])
            and is_jp(all_text[i + 1])
        ):
            i += 1
            continue
        new_t.append(c)
        new_m.append(ms_list[i])
        i += 1
    all_text, ms_list = "".join(new_t), new_m

    new_t, new_m, prev_sp = [], [], False
    for c, m in zip(all_text, ms_list):
        if c == " ":
            if prev_sp:
                continue
            prev_sp = True
        else:
            prev_sp = False
        new_t.append(c)
        new_m.append(m)
    all_text, ms_list = "".join(new_t), new_m
    while all_text and all_text[0] == " ":
        all_text = all_text[1:]
        ms_list = ms_list[1:]
    while all_text and all_text[-1] == " ":
        all_text = all_text[:-1]
        ms_list = ms_list[:-1]

    assert len(all_text) == len(ms_list), f"mismatch {len(all_text)} vs {len(ms_list)}"

    new_caps = dp_split(
        all_text, ms_list, grammar, args.min_len, args.ideal, args.max_len
    )

    for i in range(1, len(new_caps)):
        if new_caps[i][0] < new_caps[i - 1][1]:
            new_caps[i] = (
                new_caps[i - 1][1],
                max(new_caps[i][1], new_caps[i - 1][1] + 500),
                new_caps[i][2],
            )

    for i in range(len(new_caps) - 1):
        s, e, t = new_caps[i]
        next_s = new_caps[i + 1][0]
        if e < next_s:
            new_caps[i] = (s, next_s, t)

    out_lines = []
    for i, (s, e, t) in enumerate(new_caps, 1):
        out_lines.append(str(i))
        out_lines.append(f"{fmt_ts(s)} --> {fmt_ts(e)}")
        out_lines.append(t)
        out_lines.append("")

    Path(args.out).write_text("\n".join(out_lines), encoding="utf-8")
    chars = [len(t) for _, _, t in new_caps]
    print(
        f"wrote {args.out}: {len(new_caps)} caps, "
        f"min={min(chars)}/avg={sum(chars)/len(chars):.1f}/max={max(chars)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
