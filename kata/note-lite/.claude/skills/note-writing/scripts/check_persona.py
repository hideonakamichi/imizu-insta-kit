"""persona.md が雛形のままなら止める。

使い方:  py .claude/skills/note-writing/scripts/check_persona.py   （Mac は python3）
雛形の（…）が1つも残っていなければ exit 0。残っていれば、その行を出して exit 1。
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

PERSONA = Path(__file__).resolve().parents[1] / "references" / "persona.md"
# 値の部分がまるごと（…）なら雛形。「わたし（ひらがな）」のように後ろに付いただけのカッコは雛形ではない
PLACEHOLDER = re.compile(r"(^|[:：]\s*|^\s*-\s*)（[^）]*）\s*$")


def main() -> int:
    if not PERSONA.is_file():
        print(f"[error] {PERSONA} がありません")
        return 1
    left = []
    for n, line in enumerate(PERSONA.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith(">"):
            continue  # 冒頭の注意書きは判定しない
        if PLACEHOLDER.search(line):
            left.append(f"  {n}行目: {line.strip()[:50]}")
    if left:
        print("[error] persona.md が雛形のままなので、記事を書きません:")
        print("\n".join(left))
        print("  Claude Code に「persona.md を一緒に埋めて」と頼むと、質問しながら埋められます。")
        return 1
    print("[ok] persona.md は設定済みです")
    return 0


if __name__ == "__main__":
    sys.exit(main())
