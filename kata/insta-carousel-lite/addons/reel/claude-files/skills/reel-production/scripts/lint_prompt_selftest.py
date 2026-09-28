#!/usr/bin/env python3
"""lint_prompt_selftest.py — lint_prompt.py の回帰テスト（Codex レビューで挙がった回避・誤検出パターン）

lint の検査を変えたら必ず実行する:
    python3 .claude/skills/reel-production/scripts/lint_prompt_selftest.py

ベースは examples/reel-minimal-20s（lint 通過が前提）。各ケースは一時ディレクトリにコピーして
1箇所だけ改変し、「エラーで止まるべきもの」「通るべきもの」を検証する。
Grok・ネットワーク・許可リストは使わない。
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[3]
sys.path.insert(0, str(SCRIPT_DIR))
import lint_prompt  # noqa: E402

BASE = PROJECT_ROOT / 'examples' / 'reel-minimal-20s'
RULE = 'A thin muted-green rule draws beneath the second line.'


def make_case(tmp: Path, name: str, mutate) -> Path:
    d = tmp / name
    shutil.copytree(BASE, d)
    mutate(d)
    return d


def sub(d: Path, fname: str, old: str, new: str) -> None:
    p = d / fname
    s = p.read_text(encoding='utf-8')
    assert old in s, f'{fname}: 置換元が無い: {old!r}'
    p.write_text(s.replace(old, new, 1), encoding='utf-8')


def meta(d: Path, fn) -> None:
    p = d / 'reel_meta.json'
    m = json.loads(p.read_text(encoding='utf-8'))
    fn(m)
    p.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding='utf-8')


def set_native(d: Path) -> None:
    """narration_mode=native: No narration を外し、voiceover 原稿をプロンプト末尾に書く（旧仕様のフォールバック）。"""
    meta(d, lambda m: m.update(narration_mode='native'))
    for f in ('video_prompt_1.txt', 'video_prompt_2.txt'):
        p = d / f
        s = p.read_text(encoding='utf-8').replace('No narration. No spoken words. No dialogue. ', '')
        s += '\n\nvoiceover (Japanese, calm female voice): "学校を休むのは、逃げじゃない。"\n'
        p.write_text(s, encoding='utf-8')


# (名前, 改変, 期待: 'ok' | 'error', エラー時に含まれるべき語)
CASES = [
    ('baseline: examples はそのまま通る', lambda d: None, 'ok', ''),
    ('9/16 原文: Render the numeral ... slightly larger', lambda d: sub(d, 'video_prompt_1.txt', RULE,
        'Render the numeral "500" in the muted-green accent, slightly larger than the surrounding characters.'), 'error', 'Render the numeral'),
    ('言い換え: Make "500" green and bigger', lambda d: sub(d, 'video_prompt_1.txt', RULE,
        'Make "500" muted-green and bigger than the other characters.'), 'error', 'bigger'),
    ('金線 + Display "3" above the heading', lambda d: sub(d, 'video_prompt_1.txt', RULE,
        RULE + ' Display "3" above the heading.'), 'error', '"3"'),
    ('金線に節を足す: , and a separate numeral appears', lambda d: sub(d, 'video_prompt_1.txt', RULE,
        'A thin muted-green rule draws beneath the second line, and a separate muted-green numeral 3 appears above the heading.'), 'error', '許可された書き方ではない'),
    ('accent colour 経由: Tint the numeral 3 with the accent colour', lambda d: sub(d, 'video_prompt_1.txt', RULE,
        RULE + ' Tint the numeral 3 with the accent colour.'), 'error', 'numeral'),
    ('hex 経由: Fill the numeral in #7FA383', lambda d: sub(d, 'video_prompt_1.txt', RULE,
        RULE + ' Fill the numeral 3 in #7FA383.'), 'error', 'numeral'),
    ('Display "問い"（既存見出しの部分文字列）', lambda d: sub(d, 'video_prompt_1.txt', RULE,
        RULE + ' Display "学校" above the heading.'), 'error', '描画指示'),
    ('全角数字の単体引用 "３"', lambda d: sub(d, 'video_prompt_1.txt', RULE,
        RULE + ' Show "３" next to it.'), 'error', '"３"'),
    ('参照引用は許容: under "逃げ？"（既存例に含まれる）', lambda d: None, 'ok', ''),
    ('折り返し: draws\\nbeneath the second line.', lambda d: sub(d, 'video_prompt_1.txt', RULE,
        'A thin muted-green rule draws\nbeneath the second line.'), 'ok', ''),
    ('余白の larger は警告のみ', lambda d: sub(d, 'video_prompt_1.txt', RULE,
        RULE + ' Keep a larger gap between the two text lines.'), 'ok', ''),
    ('文字の larger はエラー', lambda d: sub(d, 'video_prompt_1.txt', RULE,
        RULE + ' Make the characters larger.'), 'error', 'larger'),
    ('2文目の色指示: Paint the background band in green', lambda d: sub(d, 'video_prompt_2.txt', RULE,
        RULE + ' Paint the background band in muted-green.'), 'error', '許可された書き方ではない'),
    ('エンドカード誘導行は最終ショットのみ許可（既存例）', lambda d: None, 'ok', ''),
    ('エンドカード誘導行を先頭ショットに置くとエラー', lambda d: sub(d, 'video_prompt_1.txt', RULE,
        'Below it, a smaller line of muted-green text:'), 'error', '許可された書き方ではない'),
    ('表示行 "500" が on_screen_texts に無い', lambda d: sub(d, 'video_prompt_1.txt', '"全国500か所以上"', '"500"'), 'error', '表示行'),
    ('STYLE LOCK 見出し欠落', lambda d: sub(d, 'video_prompt_2.txt', 'STYLE LOCK', 'Style notes'), 'error', 'STYLE LOCK'),
    ('STYLE LOCK 文面不一致', lambda d: sub(d, 'video_prompt_2.txt', 'Generous negative space', 'Some negative space'), 'error', '同一文面'),
    ('narration_segments segment=99', lambda d: meta(d, lambda m: m['narration_segments'][1].update(segment=99)), 'error', 'segment 番号'),
    ('narration 結合不一致', lambda d: meta(d, lambda m: m.update(narration=m['narration'] + '追加の一言。')), 'error', 'narration'),
    ('タイムスタンプ全欠落', lambda d: (d / 'video_prompt_1.txt').write_text(
        re.sub(r'^\[Shot (\d)\] .*$', r'[Shot \1]', (d / 'video_prompt_1.txt').read_text(encoding='utf-8'), flags=re.M), encoding='utf-8'),
        'error', 'タイムスタンプ'),
    ('タイムスタンプの隙間', lambda d: sub(d, 'video_prompt_1.txt', '[Shot 2] 00:02.500', '[Shot 2] 00:03.000'), 'error', '連続していない'),
    ('No background music 欠落', lambda d: sub(d, 'video_prompt_1.txt', 'No background music. ', ''), 'error', 'No background music'),
    ('native モード: No narration 無し + voiceover 原稿あり → 通る', set_native, 'ok', ''),
    ('fish_audio で No narration 欠落 → エラー', lambda d: sub(d, 'video_prompt_1.txt', 'No narration. ', ''), 'error', 'No narration'),
    ('文字単位アニメ', lambda d: sub(d, 'video_prompt_1.txt', 'appears in two stages', 'appears letter by letter'), 'error', '文字単位'),
    ('9/9 成功例の書き方: arrow between the two lines / Below them', lambda d: (
        sub(d, 'video_prompt_2.txt', RULE, 'A small flat muted-green arrow fades in between the two lines.')), 'ok', ''),
    # --- Codex レビュー3回目で挙がった回避・誤検出 ---
    ('アイコン自由記述で数字: icon of a large number three', lambda d: sub(d, 'video_prompt_1.txt', RULE,
        'A small flat muted-green icon of a large number three appears above the heading.'), 'error', '許可された書き方ではない'),
    ('描画動詞の直後で折り返し: Display\\n"学校" above', lambda d: sub(d, 'video_prompt_1.txt', RULE,
        RULE + '\nDisplay\n"学校" above the heading.'), 'error', '描画指示'),
    ('参照引用の直前で折り返し: draws beneath\\n"選択肢のひとつ".', lambda d: sub(d, 'video_prompt_1.txt', RULE,
        'A thin muted-green rule draws beneath\n"選択肢のひとつ".'), 'ok', ''),
    ('slightly larger gap（余白）は通る', lambda d: sub(d, 'video_prompt_1.txt', RULE,
        RULE + ' Keep a slightly larger gap between the two text lines.'), 'ok', ''),
    ('slightly larger than the surrounding characters はエラー', lambda d: sub(d, 'video_prompt_1.txt', RULE,
        RULE + ' Keep the numeral slightly larger than the surrounding characters.'), 'error', 'larger'),
    ('描画動詞 + 位置参照: Make the gap under "選択肢のひとつ" generous. は通る', lambda d: sub(d, 'video_prompt_1.txt', RULE,
        RULE + ' Make the gap under "選択肢のひとつ" generous.'), 'ok', ''),
    ('表示行を消して参照だけ残す → on_screen_texts の表示行欠落', lambda d: sub(d, 'video_prompt_1.txt',
        '"それは逃げ？"\n', ''), 'error', '表示行'),
    # --- Codex レビュー4回目 ---
    ('余白サイズ語 + 位置参照: slightly larger gap under "..." は通る', lambda d: sub(d, 'video_prompt_1.txt', RULE,
        RULE + ' Keep a slightly larger gap under "選択肢のひとつ".'), 'ok', ''),
    ('表示導入文の末尾にコロンが無くても表示行と判定', lambda d: sub(d, 'video_prompt_1.txt',
        'text appears in two stages, centered:', 'text appears in two stages, centered'), 'ok', ''),
    ('表示行の間が then でなく and でも表示行と判定', lambda d: sub(d, 'video_prompt_1.txt',
        '"学校を休む"\nthen\n', '"学校を休む"\nand\n'), 'ok', ''),
    ('9/2 成功例の icon of a simple document は許可語で通る', lambda d: sub(d, 'video_prompt_2.txt', RULE,
        'A small flat muted-green icon of a document fades in below the text.'), 'ok', ''),
    ('ページめくり（minimal）', lambda d: sub(d, 'video_prompt_1.txt', 'Cut to a fresh off-white screen.', 'A page turn to a fresh off-white screen.'), 'error', 'ページめくり'),
]


REAL = PROJECT_ROOT / 'examples' / 'reel-realistic-20s'
REAL_CASES = [
    ('realistic: examples はそのまま通る', lambda d: None, 'ok', ''),
    ('realistic: キーワードを暖色にする許可形は通る', lambda d: sub(d, 'video_prompt_1.txt', '"それは逃げ？"\n',
        '"それは逃げ？"\nRender "逃げ" in a warm gold tone within the same outlined style.\n'), 'ok', ''),
    ('realistic: 手元のみ文の欠落', lambda d: sub(d, 'video_prompt_1.txt', 'ONLY as hands', 'ONLY as silhouettes'), 'error', '手元'),
    ('realistic: 明朝禁止の欠落', lambda d: sub(d, 'video_prompt_1.txt', 'Never a mincho', 'Prefer a gothic'), 'error', '明朝'),
    ('realistic: ページめくり（手元）は許容', lambda d: sub(d, 'video_prompt_1.txt', 'Slow gentle push-in.', 'Hands turn a page slowly.'), 'ok', ''),
    ('realistic: 許可文の途中で折り返し（tone の後）', lambda d: sub(d, 'video_prompt_1.txt', '"それは逃げ？"\n',
        '"それは逃げ？"\nRender "逃げ" in a warm gold tone\nwithin the same outlined style.\n'), 'ok', ''),
    ('realistic: Display "3" は不可', lambda d: sub(d, 'video_prompt_1.txt', 'Slow gentle push-in.', 'Display "3" above the text.'), 'error', '"3"'),
]


def main() -> int:
    failures = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        all_cases = [(BASE, c) for c in CASES] + [(REAL, c) for c in REAL_CASES]
        for i, (base, (name, mutate, expect, needle)) in enumerate(all_cases):
            d = tmp / f'case_{i:02d}'
            shutil.copytree(base, d)
            mutate(d)
            rep = lint_prompt.lint(d / 'reel_meta.json')
            got = 'ok' if rep.ok else 'error'
            detail = ''
            if got != expect:
                detail = f'期待 {expect} / 実際 {got}: ' + ('; '.join(rep.errors) or '(エラーなし)')
            elif expect == 'error' and needle and not any(needle in e for e in rep.errors):
                detail = f'エラーは出たが「{needle}」を含まない: ' + '; '.join(rep.errors)
            mark = 'NG' if detail else 'ok'
            print(f'[{mark}] {name}')
            if detail:
                print(f'      {detail}')
                failures.append(name)
    print()
    if failures:
        print(f'[fail] {len(failures)}/{len(all_cases)} ケース失敗')
        return 1
    print(f'[ok] {len(all_cases)} ケースすべて期待どおり')
    return 0


if __name__ == '__main__':
    sys.exit(main())
