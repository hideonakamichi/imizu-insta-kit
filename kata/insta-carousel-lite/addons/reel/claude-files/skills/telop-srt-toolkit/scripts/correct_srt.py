"""correct_srt.py - SRT 補正・冗長削除・スペース整理

参照: myuuu-io/youtube .claude/skills/telop-srt-toolkit/scripts/correct_srt.py をそのまま流用
（言語処理ロジックは汎用のため改修不要）。

担当:
  - 辞書ベース補正 (固有名詞・誤認識・英字直結)
  - 冗長口語の削除
  - 句読点 → 半角スペース
  - 日本語間スペース詰め
  - 連続スペース整理
  - 冒頭フィラー除去

Usage:
    python3 correct_srt.py \
        --input RAW.srt \
        --out CORRECTED.srt \
        --dict references/correction-dictionary.md \
        --verbose references/verbose-patterns.md
"""

import argparse
import re
import sys
from pathlib import Path


def parse_rules(md_path: str) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """補正辞書を読み込み。
    Returns: (normal_rules, leading_rules)
        normal_rules: [(old, new), ...] 通常置換
        leading_rules: [(old, new), ...] 行頭限定置換（LEADING: プレフィックス）
    """
    normal, leading = [], []
    if not md_path or not Path(md_path).exists():
        return normal, leading

    for line in Path(md_path).read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("```"):
            continue
        if " => " not in s:
            continue
        old, _, new = s.partition(" => ")
        old, new = old.strip(), new.strip()
        if old.startswith("LEADING:"):
            leading.append((old[len("LEADING:"):], new))
        else:
            normal.append((old, new))
    return normal, leading


def is_jp(c: str) -> bool:
    return (
        "぀" <= c <= "ゟ"
        or "゠" <= c <= "ヿ"
        or "一" <= c <= "鿿"
    )


def process_line(text: str, normal_rules: list[tuple[str, str]]) -> str:
    """1行の本文に対して補正＋整理を適用。"""
    for old, new in normal_rules:
        text = text.replace(old, new)

    text = text.replace("、", " ").replace("。", " ")

    new_chars = []
    i = 0
    while i < len(text):
        c = text[i]
        if (
            c == " "
            and 0 < i < len(text) - 1
            and is_jp(text[i - 1])
            and is_jp(text[i + 1])
        ):
            i += 1
            continue
        new_chars.append(c)
        i += 1
    text = "".join(new_chars)

    text = re.sub(r" +", " ", text)

    return text.strip()


def apply_leading(text: str, leading_rules: list[tuple[str, str]]) -> str:
    """行頭フィラー除去。"""
    for old, new in leading_rules:
        if text.startswith(old):
            text = new + text[len(old):]
            text = text.strip()
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--dict", default=None, help="correction-dictionary.md")
    ap.add_argument("--verbose", default=None, help="verbose-patterns.md")
    args = ap.parse_args()

    normal, leading = [], []
    if args.dict:
        n1, l1 = parse_rules(args.dict)
        normal.extend(n1)
        leading.extend(l1)
    if args.verbose:
        n2, l2 = parse_rules(args.verbose)
        normal.extend(n2)
        leading.extend(l2)

    if not normal and not leading:
        print("Warning: no rules loaded", file=sys.stderr)

    raw = Path(args.input).read_text(encoding="utf-8")
    lines = raw.split("\n")
    out_lines = []
    for line in lines:
        s = line.strip()
        if s.isdigit() or "-->" in s or not s:
            out_lines.append(line)
            continue
        new = process_line(line, normal)
        new = apply_leading(new, leading)
        out_lines.append(new)

    Path(args.out).write_text("\n".join(out_lines), encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
