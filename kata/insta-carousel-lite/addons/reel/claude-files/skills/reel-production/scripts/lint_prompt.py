#!/usr/bin/env python3
"""lint_prompt.py — 動画プロンプトと reel_meta.json の事前検査（動画生成前の機械チェック）

reel-script-writer が書いた video_prompt_N.txt / reel_meta.json を、Grok に投げる前に
決定論的に検査する。1セグメントの生成に2〜5分・evaluator（Opus）1周に数百円かかるため、
「読めば分かる不備」はここで止める。

2026-09-16 の失敗（evaluator 2回不合格で中止）で分かったこと:
  - `Render the numeral "3" in the gold accent, slightly larger ...` という行内ゴールド数字の
    指示は、9/2・9/9 では通ったが 9/16 は2回連続で「巨大な独立した金の数字」として
    描かれた（5回中2回の外れ）。強調は「金の細線1本」に固定する
  - 「？」が半角「?」で描かれることがある（evaluator 側で同一視するよう改定済み）
  - オーケストレーターが wc/grep で文字数・否定数を測ろうとして権限拒否された。
    その計測をこのスクリプトが担う（generate_video.py が自動で呼ぶので許可リスト追加は不要）

Usage:
    python3 lint_prompt.py --meta OUTPUT_DIR/reel_meta.json
    python3 lint_prompt.py --meta ... --json        # 機械可読出力

終了コード: 0 = エラーなし（警告は可）、1 = エラーあり（生成に進まないこと）、2 = 読み取り失敗
generate_video.py は生成前にこれを自動実行し、エラーがあれば生成せず終了する。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[3]

# 成功実績プロファイル（video-prompt-spec.md「否定指示を積むな」の表を機械化）
#   成功（9/2・9/9）: 約2,400字・否定23件 / 失敗（9/9 5連敗）: 3,400字超・否定48件
CHARS_WARN, CHARS_ERROR = 2_900, 3_300              # minimal（成功 2,400字 / 失敗 3,400字超）
CHARS_WARN_REAL, CHARS_ERROR_REAL = 3_400, 3_800    # realistic（9/2 成功例 3,371字）
NEG_WARN, NEG_ERROR = 32, 42

# 動画モデルが誤解釈しやすい書き方（実測で破綻を呼んだもの）。
# 否定文を足す代わりに、この書き方自体を使わない。
FLAKY_PATTERNS: list[tuple[str, str]] = [
    (r'Render the (numeral|number|digit|figure)\b',
     '行内の数字を金色/大きくする指示は「巨大な独立数字」として描かれることがある（9/16 2連敗）。'
     '文を削除し、強調は "A thin gold rule draws beneath the second line." の1文に置き換える'),
    (r'\b(word by word|letter by letter|character by character|stroke by stroke|one character at a time)\b',
     '文字単位のアニメーションは文字化けの温床。フレーズ単位（"appears in two stages"）にする'),
]
# minimal（フラット図解）だけに適用する危険パターン。realistic では手元でページをめくる描写が正当
FLAKY_PATTERNS_MINIMAL: list[tuple[str, str]] = [
    (r'\bpage[- ]?(turn|flip|curl)\b|\bpeel\b',
     'ページめくり表現は白い曲面・陰影を描く。遷移は "Cut to" にする'),
]
# ショット記述内で「大きく」を意味する語。行内の数字を巨大な独立文字にする外れを呼ぶ
SIZE_WORDS_RE = re.compile(
    r"\b(bigger|larger|enlarged?|oversized|giant|huge|scaled?[- ]up|extra[- ]large|"
    r"prominent(ly)?|emphasi[sz]ed? in size|dominant)\b", re.IGNORECASE)
# minimal のショット記述で許可する強調文（位置と個数が一意に決まる書き方だけ）
# アイコンとして許可する語（数字・文字・自由記述は不可: `icon of a large number three` を防ぐ）
ICON_WORDS = ('magnifying glass|check ?mark|arrow|dot|circle|light ?bulb|pencil|pen|book|notebook|clock|'
              'speech bubble|star|sparkle|leaf|target|compass|key|flag|document|sheet|envelope|calendar')


def _allowed_accent_sentences(accent: str) -> list[re.Pattern]:
    a = re.escape(accent)
    return [
        re.compile(rf'^A thin {a} (rule|underline|line) draws (beneath|under|below) (the (first|second|third|last|final) line|"[^"]+")\.$', re.IGNORECASE),
        re.compile(rf'^A small flat {a} (icon of (a |an )?(?:{ICON_WORDS})|arrow|dot|check ?mark|circle|line) (fades in|appears) '
                   rf'(below|beneath|under|above|between) (the text|the two lines|the heading|it|them)\.$', re.IGNORECASE),
    ]


def _allowed_endcard_sentences(accent: str) -> list[re.Pattern]:
    """最終セグメントの最終ショット（エンドカード）だけに許す誘導1行の書き方。"""
    a = re.escape(accent)
    return [re.compile(rf'^Below (it|them|the text), a smaller line of {a} text:$', re.IGNORECASE)]

REQUIRED_PHRASES: list[tuple[str, str]] = [
    (r'No background music', '"No background music." がない（BGMはファイルから敷くため必須）'),
    (r'No vocals', '"No vocals." がない'),
    (r'Do not let the style drift', '"Do not let the style drift between shots." がない'),
]
REQUIRED_FISH_AUDIO = (r'No narration', '"No narration." がない（narration_mode=fish_audio ではナレーションを後付けするため必須）')
REQUIRED_REALISTIC: list[tuple[str, str]] = [
    (r'ONLY as hands', 'realistic: 人物を手元のみに限定する文（"People may appear ONLY as hands and forearms ..."）がない。後ろ姿を許すと顔が写る（2026-09-02実測）'),
    (r'Never a mincho', 'realistic: 明朝禁止文（"Never a mincho/serif face ..."）がない'),
]
HEX_GUARD = r'Never render a hex code'
DISPLAY_LINE_RE = re.compile(r'^\s*"([^"\n]+)"\s*[.,]?\s*$')
# ショット記述の終わり（この見出し以降は音・ナレーション等で、画面表示の検査対象外）
SECTION_END_RE = re.compile(r'^(overall_soundscape|non_diegetic_music|voiceover|narration|narrator)\b.*$', re.IGNORECASE | re.MULTILINE)
# 行内引用に付く動詞: 描画指示（表示テキストは行全体を "..." にする） vs 位置参照（under "逃げ？" 等）
DISPLAY_VERB_RE = re.compile(r'\b(display|show|render|draw|write|add|place|put|paint|overlay|insert|reveal|animate|tint|colou?r|highlight|make)\b', re.IGNORECASE)
# 文字・数字を対象にした語（サイズ語と組み合わさるとエラー、単独では警告）
GLYPH_WORD_RE = re.compile(r'\b(numeral|digit|character|glyph|letter|font|typeface)s?\b', re.IGNORECASE)
# 日本語・ラテン文字を含まない引用（"3"・"３"・"③"・"?" 等）
HAS_LETTER_RE = re.compile(r'[぀-ヿ㐀-鿿A-Za-z]')
REALISTIC_KEYWORD_RE = re.compile(r'^Render "[^"]+" in a warm (gold|amber|orange|yellow)[a-z -]* tone within the same outlined style\.$', re.IGNORECASE)
DISPLAY_VERB_END_RE = re.compile(r'\b(display|show|render|draw|write|add|place|put|paint|overlay|insert|reveal|animate|tint|colou?r|highlight|make)s?\s*$', re.IGNORECASE)
POSITION_REF_RE = re.compile(r'\b(under|beneath|below|above|behind|around|next to|near|after|before|between|of|beside|following|from|to)\s*$', re.IGNORECASE)
CONNECTOR_RE = re.compile(r'^(then|and then|and|next|finally|after that|meanwhile)[,:]?\s+', re.IGNORECASE)

NEGATION_RE = re.compile(r"\b(no|never|not|without|avoid|don't|nothing|none)\b", re.IGNORECASE)
CJK_RE = re.compile(r'[぀-ヿ㐀-䶿一-鿿＀-￯①-⓿]')
QUOTED_RE = re.compile(r'"([^"\n]+)"')
SHOT_HEAD_RE = re.compile(
    r'\[Shot\s*(\d+)\]\s*(\d{1,2}):(\d{2})\.(\d{3})\s*[-–—]\s*(\d{1,2}):(\d{2})\.(\d{3})'
)
SHOT_SPLIT_RE = re.compile(r'(?=\[Shot\s*\d+\])')
HEX_RE = re.compile(r'#[0-9A-Fa-f]{6}\b')
HALFWIDTH_PUNCT = {'?': '？', '!': '！'}
MAX_LINE_CHARS = 15  # spec は「1行13字目安」。15を超えたら警告


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def err(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    @property
    def ok(self) -> bool:
        return not self.errors


def _norm_ws(s: str) -> str:
    return re.sub(r'\s+', '', s)


def _load_palette_hexes() -> list[str]:
    """brand.yaml の design.palette の hex を返す（yaml が無ければ正規表現で拾う）。"""
    path = PROJECT_ROOT / 'config' / 'brand.yaml'
    if not path.exists():
        return []
    text = path.read_text(encoding='utf-8')
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(text) or {}
        pal = (data.get('design') or {}).get('palette') or {}
        return [str(v).upper() for v in pal.values() if HEX_RE.fullmatch(str(v))]
    except Exception:
        m = re.search(r'^design:\s*\n\s+palette:\s*\n((?:\s+\w+:\s*"?#[0-9A-Fa-f]{6}"?.*\n)+)', text, re.M)
        return [h.upper() for h in HEX_RE.findall(m.group(1))] if m else []


def _accent_word(prompt: str) -> str:
    """スタイルロックの `one restrained gold accent` から強調色の語（gold 等）を推定する。"""
    m = re.search(r'\bone\s+(?:[\w-]+\s+){0,2}?([a-z]+(?:-[a-z]+)?)\s+accent\b', prompt, re.IGNORECASE)
    return m.group(1).lower() if m else 'accent'


def _style_lock(prompt: str) -> str:
    m = re.search(r'STYLE LOCK.*?(?=\[Shot)', prompt, re.S | re.IGNORECASE)
    return _norm_ws(m.group(0)) if m else ''


def _check_timestamps(rep: Report, seg_idx: int, prompt: str, duration: int) -> None:
    heads = SHOT_HEAD_RE.findall(prompt)
    if not heads:
        rep.err(f'segment {seg_idx}: [Shot N] MM:SS.mmm-MM:SS.mmm 形式のタイムスタンプが1つも無い（尺の検証ができない）')
        return
    prev_end = 0.0
    for n, m1, s1, ms1, m2, s2, ms2 in heads:
        start = int(m1) * 60 + int(s1) + int(ms1) / 1000
        end = int(m2) * 60 + int(s2) + int(ms2) / 1000
        if abs(start - prev_end) > 0.001:
            rep.err(f'segment {seg_idx} Shot {n}: 開始 {start:.3f}s が直前の終了 {prev_end:.3f}s と連続していない（隙間/重複）')
        if end <= start:
            rep.err(f'segment {seg_idx} Shot {n}: 終了 {end:.3f}s が開始以前')
        prev_end = end
    if abs(prev_end - duration) > 0.001:
        rep.err(f'segment {seg_idx}: 最終ショットの終了 {prev_end:.3f}s が duration_sec={duration} と一致しない')
    rep.stats.setdefault('shots', {})[seg_idx] = len(heads)


def _shots_part(prompt: str) -> str:
    """[Shot 1] から音・ナレーション見出しの手前までを返す（画面表示の検査範囲）。"""
    body = prompt[prompt.find('[Shot'):] if '[Shot' in prompt else prompt
    m = SECTION_END_RE.search(body)
    return body[:m.start()] if m else body


@dataclass
class Shot:
    head: str
    display: list[str] = field(default_factory=list)   # 画面に描く文字列（行全体が "..." の行）
    sentences: list[str] = field(default_factory=list)  # 記述文（折り返しを空白に正規化し、文単位に分割）


def _parse_shots(prompt: str) -> list[Shot]:
    """ショット記述を文脈付きで解析する。

    - 行全体が "..." の行は原則「表示行」。ただし直前の記述文が位置の前置詞や描画動詞で終わって
      目的語を待っているとき（例: `draws beneath` ＋ 次行 `"選択肢のひとつ".`）は記述文の続きとして扱う
    - 記述文の折り返しは空白で連結してから文に分割する（`Display` ＋ 次行 `"学校" above ...` も1文になる）
    """
    shots: list[Shot] = []
    for b in SHOT_SPLIT_RE.split(_shots_part(prompt)):
        if not b.startswith('[Shot'):
            continue
        head, _, body = b.partition('\n')
        shot = Shot(head=head.strip())
        parts: list[str] = []  # 確定した記述文のかたまり
        buf = ''               # 連結中の記述文
        for raw in body.splitlines():
            ln = raw.strip()
            if not ln:
                continue
            m = DISPLAY_LINE_RE.match(ln)
            # 直前の記述が位置の前置詞（draws beneath）や描画動詞（Display）で終わり、目的語を待っている
            # ときだけ折り返しの続き。それ以外（導入文の末尾にコロンが無い・接続語 and 等）は表示行
            continuing = bool(buf) and bool(POSITION_REF_RE.search(buf) or DISPLAY_VERB_END_RE.search(buf))
            if m and not continuing:
                if buf:
                    parts.append(buf)
                    buf = ''
                shot.display.append(m.group(1))
                continue
            buf = (buf + ' ' + ln).strip() if buf else ln
        if buf:
            parts.append(buf)
        for part in parts:  # 表示行で区切られたかたまりごとに文分割（表示行も文の境界）
            for x in re.split(r'(?<=[.:])\s+', part):
                x = CONNECTOR_RE.sub('', x.strip())
                if x and not CONNECTOR_RE.fullmatch(x + ' '):
                    shot.sentences.append(x)
        shots.append(shot)
    return shots


def _check_texts(rep: Report, seg_idx: int, prompt: str, texts: list[str], minimal: bool) -> None:
    shots = _parse_shots(prompt)
    display_all = [d for sh in shots for d in sh.display]
    # on_screen_texts → 表示行（一字一句。参照引用や音声原稿にあるだけでは「表示される」ことにならない）
    for t in texts:
        if t not in display_all:
            rep.err(f'segment {seg_idx}: on_screen_texts の「{t}」が表示行（行全体が "..." の行）として無い'
                    '（言い換え・省略・記号の全角半角違い・表示行の消し忘れを疑う）')
        if len(t) > MAX_LINE_CHARS:
            rep.warn(f'segment {seg_idx}: 「{t}」は{len(t)}字。1行13字目安を超えている（誤字率と可読性に不利）')
        for half, full in HALFWIDTH_PUNCT.items():
            if half in t:
                rep.warn(f'segment {seg_idx}: 「{t}」に半角「{half}」。画面内テキストは全角「{full}」に統一する')
    # 表示行 → on_screen_texts（完全一致。数字だけの表示行も対象）
    for q in display_all:
        if q not in texts:
            rep.err(f'segment {seg_idx}: 表示行の "{q}" が on_screen_texts に無い（evaluator の照合で不合格になる）')
    # 記述文中の引用: 位置参照（under "逃げ？"）は列挙済みテキストの一部でよい。
    #   描画動詞を伴う引用（Display "3" above ...）は表示指示なので表示行に書かせる → エラー
    for sh in shots:
        for sent in sh.sentences:
            realistic_keyword = (not minimal) and bool(REALISTIC_KEYWORD_RE.match(sent))
            for m in QUOTED_RE.finditer(sent):
                q = m.group(1)
                is_ref = bool(POSITION_REF_RE.search(sent[:m.start()]))
                if realistic_keyword or is_ref or not DISPLAY_VERB_RE.search(sent):
                    if not any(q in t for t in texts):
                        rep.err(f'segment {seg_idx} {sh.head}: 参照 "{q}" が on_screen_texts のどのテキストにも含まれない')
                else:
                    rep.err(f'segment {seg_idx} {sh.head}: 行内で "{q}" を描画指示と一緒に引用している（{sent[:60]}）。'
                            '画面に出す文字列は行全体を "..." にして on_screen_texts に列挙し、それ以外の文字を描かせない')


def _is_minimal(prompt: str) -> bool:
    return bool(re.search(r'Exactly 3 colou?rs|minimal flat', prompt, re.IGNORECASE))


def _check_shots(rep: Report, seg_idx: int, prompt: str, minimal: bool, is_last_segment: bool) -> None:
    accent = _accent_word(prompt)
    allowed = _allowed_accent_sentences(accent)
    allowed_end = _allowed_endcard_sentences(accent)
    shots = _parse_shots(prompt)
    for bi, sh in enumerate(shots):
        head = sh.head
        is_endcard = is_last_segment and bi == len(shots) - 1
        for x in sh.sentences:
            m = SIZE_WORDS_RE.search(x)
            if m:
                # 文字・数字が対象のサイズ指示だけエラー（余白・物体の larger は警告に留める）
                display_quote = any(not POSITION_REF_RE.search(x[:q.start()]) for q in QUOTED_RE.finditer(x))
                if display_quote or GLYPH_WORD_RE.search(x) or re.search(r'\bsurrounding\b', x, re.IGNORECASE):
                    rep.err(f'segment {seg_idx} {head}: 「{m.group(0)}」— 文字・数字を大きくする指示は独立した巨大文字を呼び込む'
                            f'（{x[:60]}）。サイズの指示は書かない')
                else:
                    rep.warn(f'segment {seg_idx} {head}: 「{m.group(0)}」（{x[:60]}）— サイズ語。文字の拡大指示でなければ可だが、余白は "generous" 等で表す')
            for q in QUOTED_RE.findall(x):
                if not HAS_LETTER_RE.search(q):
                    rep.err(f'segment {seg_idx} {head}: 行内で "{q}" を単体で引用している。数字・記号を単独で描かせる指示は書かない'
                            '（強調は金線1本にする）')
            if minimal and re.search(r'\b(numeral|digit|number)s?\b', x, re.IGNORECASE):
                rep.err(f'segment {seg_idx} {head}: 「{x[:60]}」— 数字（numeral/digit/number）を個別に扱う指示。行内の数字は本文と同じ色・サイズのままにする')
        if not minimal:
            continue
        accent_re = re.compile(rf'\b{re.escape(accent)}\b|\baccent\b|#[0-9A-Fa-f]{{6}}\b', re.IGNORECASE)
        accent_sentences = [x for x in sh.sentences if accent_re.search(x)]
        if len(accent_sentences) > 1:
            rep.warn(f'segment {seg_idx} {head}: 強調色「{accent}」の指定が{len(accent_sentences)}回。1ショット1強調（金線1本）に絞る')
        for x in accent_sentences:
            ok = any(p.match(x) for p in allowed) or (is_endcard and any(p.match(x) for p in allowed_end))
            if not ok:
                rep.err(f'segment {seg_idx} {head}: 強調文「{x}」が許可された書き方ではない。'
                        f'"A thin {accent} rule draws beneath the second line." に置き換える'
                        f'（許可: 細線1本／小さなフラットアイコン（許可リストの語のみ）／最終ショットのみ "Below it, a smaller line of {accent} text:"）')


def lint(meta_path: Path) -> Report:
    rep = Report()
    meta_dir = meta_path.parent
    try:
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
    except Exception as e:  # noqa: BLE001
        rep.err(f'reel_meta.json を読めない: {e}')
        return rep

    # --- 尺・セグメント -------------------------------------------------
    try:
        total = int(meta['duration_sec'])
    except Exception:  # noqa: BLE001
        rep.err('duration_sec が無い/数値でない')
        return rep
    if not 10 <= total <= 20:
        rep.err(f'duration_sec={total} は10〜20の範囲外')
    segments = meta.get('segments') or [{'file': 'video_prompt_1.txt', 'duration_sec': total}]
    seg_sum = sum(int(s.get('duration_sec', 0)) for s in segments)
    if seg_sum != total:
        rep.err(f'segments の合計 {seg_sum}s が duration_sec {total}s と一致しない')

    # --- ナレーション ---------------------------------------------------
    nseg = meta.get('narration_segments') or []
    narration = meta.get('narration') or ''
    if nseg:
        joined = _norm_ws(''.join(s.get('text', '') for s in nseg))
        if joined != _norm_ws(narration):
            rep.err('narration_segments を順に結合した文が narration（通し全文）と一致しない（締めの一言の落とし漏れ等）')
        if len(nseg) != len(segments):
            rep.err(f'narration_segments が{len(nseg)}件、segments が{len(segments)}件で数が合わない')
        ids = [s.get('segment') for s in nseg]
        if ids != list(range(1, len(nseg) + 1)):
            rep.err(f'narration_segments の segment 番号が 1..{len(nseg)} の順になっていない: {ids}（narrate_and_mix.py の時間窓と対応しない）')
        for i, s in enumerate(nseg, 1):
            n = len(s.get('text', ''))
            dur = int(segments[i - 1].get('duration_sec', 10)) if i <= len(segments) else 10
            limit = int(dur * 8)  # 10秒あたり55〜75字目安 → 80字で警告
            if n > limit:
                rep.warn(f'narration segment {i}: {n}字（{dur}秒）。尺に対して長い可能性（目安 {int(dur*5.5)}〜{int(dur*7.5)}字）')
    elif meta.get('narration_mode', 'fish_audio') == 'fish_audio':
        rep.err('narration_segments が無い（narration_mode=fish_audio では必須）')

    # --- 各プロンプト ---------------------------------------------------
    texts_by_seg: dict[int, list[str]] = {}
    for t in meta.get('on_screen_texts') or []:
        texts_by_seg.setdefault(int(t.get('segment', 1)), []).append(str(t.get('text', '')))
    if not texts_by_seg:
        rep.err('on_screen_texts が空（evaluator の誤字照合ができない）')

    palette = _load_palette_hexes()
    style_locks: dict[int, str] = {}
    for i, seg in enumerate(segments, 1):
        path = meta_dir / seg.get('file', f'video_prompt_{i}.txt')
        if not path.exists():
            rep.err(f'segment {i}: プロンプトが無い: {path.name}')
            continue
        prompt = path.read_text(encoding='utf-8')
        n_chars = len(prompt)
        n_neg = len(NEGATION_RE.findall(prompt))
        rep.stats[path.name] = {'chars': n_chars, 'negations': n_neg}

        minimal = _is_minimal(prompt)
        c_warn, c_err = (CHARS_WARN, CHARS_ERROR) if minimal else (CHARS_WARN_REAL, CHARS_ERROR_REAL)
        if n_chars > c_err:
            rep.err(f'{path.name}: {n_chars}字。成功プロファイル（minimal 約2,400字 / realistic 約3,400字）から大きく外れている。要素を削る')
        elif n_chars > c_warn:
            rep.warn(f'{path.name}: {n_chars}字。成功プロファイルより長い')
        if n_neg > NEG_ERROR:
            rep.err(f'{path.name}: 否定表現 {n_neg}件。成功例は23件・失敗例は48件。禁止文を削る（否定した語をモデルが描く）')
        elif n_neg > NEG_WARN:
            rep.warn(f'{path.name}: 否定表現 {n_neg}件（成功例は23件）。増やさない')

        patterns = FLAKY_PATTERNS + (FLAKY_PATTERNS_MINIMAL if minimal else [])
        for pat, why in patterns:
            for m in re.finditer(pat, prompt, re.IGNORECASE):
                line = prompt[:m.start()].count('\n') + 1
                rep.err(f'{path.name}:{line}: 「{m.group(0)}」— {why}')
        required = list(REQUIRED_PHRASES)
        if meta.get('narration_mode', 'fish_audio') == 'fish_audio':
            required.append(REQUIRED_FISH_AUDIO)
        if not minimal:
            required += REQUIRED_REALISTIC
        for pat, why in required:
            if not re.search(pat, prompt, re.IGNORECASE):
                rep.err(f'{path.name}: {why}')
        if HEX_RE.search(prompt) and not re.search(HEX_GUARD, prompt):
            rep.err(f'{path.name}: hex を書いているのに hex 焼き込み防止文（"{HEX_GUARD} ..."）が無い')
        for h in palette:
            if h not in prompt.upper():
                rep.warn(f'{path.name}: brand.yaml のパレット {h} がプロンプトに無い（minimal では3色hexを明記する）')

        _check_timestamps(rep, i, prompt, int(seg.get('duration_sec', total)))
        _check_texts(rep, i, prompt, texts_by_seg.get(i, []), minimal)
        _check_shots(rep, i, prompt, minimal, is_last_segment=(i == len(segments)))
        style_locks[i] = _style_lock(prompt)

    if len(style_locks) >= 2:
        locks = set(style_locks.values())
        if '' in locks:
            rep.err('STYLE LOCK ブロックを検出できないセグメントがある（"STYLE LOCK" の見出しで始め、同一文面を全セグメントに入れる）')
        elif len(locks) > 1:
            rep.err('STYLE LOCK が全セグメントで同一文面になっていない（セグメント境界でスタイルドリフトする）')
    return rep


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--meta', required=True, help='reel_meta.json のパス')
    ap.add_argument('--json', action='store_true', help='結果をJSONで出力')
    args = ap.parse_args()

    meta_path = Path(args.meta)
    if not meta_path.is_absolute():
        meta_path = (PROJECT_ROOT / args.meta).resolve()
    if not meta_path.exists():
        print(f'[!] reel_meta.json が見つかりません: {meta_path}', file=sys.stderr)
        return 2

    rep = lint(meta_path)
    if args.json:
        print(json.dumps({'ok': rep.ok, 'errors': rep.errors, 'warnings': rep.warnings, 'stats': rep.stats},
                         ensure_ascii=False, indent=2))
        return 0 if rep.ok else 1

    for name, st in rep.stats.items():
        if isinstance(st, dict) and 'chars' in st:
            print(f'[stat] {name}: {st["chars"]}字 / 否定表現 {st["negations"]}件（成功例: 約2,400字 / 23件）')
    for w in rep.warnings:
        print(f'[W] {w}')
    for e in rep.errors:
        print(f'[E] {e}')
    if rep.ok:
        print(f'[ok] lint 通過（警告 {len(rep.warnings)}件）')
        return 0
    print(f'[fail] エラー {len(rep.errors)}件・警告 {len(rep.warnings)}件。'
          ' reel-script-writer に上記を渡して video_prompt_N.txt と reel_meta.json を直してから生成する')
    return 1


if __name__ == '__main__':
    sys.exit(main())
