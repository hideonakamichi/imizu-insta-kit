"""narrate_and_mix.py — Fish Audio ナレーションを生成してリール動画にミックスする

Grokのフル動画生成は映像・SE・BGMの一体生成が強みだが、日本語ナレーションの
イントネーションが不安定（2026-08-30ユーザーフィードバック）。そのため:

  動画（映像+SE、音楽・ナレーションなし）… generate_video.py（Grok）
  BGM（全編1本の音源をループ敷き込み）   … 本スクリプト（content/bgm/ のmp3）
  ナレーション                          … 本スクリプト（Fish Audio TTS）
  ミックス（ナレーション + 生成済みBGM/SE）… 本スクリプト（ffmpeg）
                                          ※ダッキングは既定オフ（下記参照）

というハイブリッド構成にする。BGMをファイルにしたのは、Grok生成音楽が
セグメント間で不連続・途切れがちだったため（2026-08-30ユーザーフィードバック）。
毎回同じBGMを使うことでアカウントのブランドサウンドにもなる。TTS呼び出しは旧スライド式で実績のある
audio_generate.py の call_fish を再利用する。

Usage:
    python3 narrate_and_mix.py --meta OUTPUT_DIR/reel_meta.json \
        --video OUTPUT_DIR/reel_video.mp4 --out OUTPUT_DIR/reel_final.mp4

    # デバッグ/リトライ用: 生成済みナレーション（narration_seg<N>.mp3）を再利用
    python3 narrate_and_mix.py --meta ... --video ... --out ... --skip-tts

reel_meta.json:
    "narration_mode": "fish_audio"（既定） | "native"
    "narration_segments": [{"segment": 1, "text": "…"}, ...]
    - native の場合（またはnarration_segmentsが無い場合）は動画をそのままコピーして終了
      （動画側にナレーションが焼き込まれている旧・ネイティブ音声構成）
    - fish_audio の場合、各セグメントのナレーションを生成し、そのセグメントの
      時間窓（先頭+0.3秒〜末尾-0.2秒）に収まるよう自動で話速調整（atempo 最大1.35）。
      収まらない場合はエラー（原稿を短くする）

BGMの選択: --bgm で明示指定 > reel_meta.json の "bgm_file" > content/bgm/ の先頭mp3。
音源が無い場合は警告してBGMなし（SE+ナレーションのみ）で続行する。
"music_mode": "native" の場合はBGMを敷かない（動画に音楽が焼き込まれている旧構成）。

env: FISH_AUDIO_API_KEY, FISH_AUDIO_VOICE_ID（fish_audio モード時に必須）
"""

import argparse
import json
import shutil
import subprocess
import sys
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[3]

sys.path.insert(0, str(SCRIPT_DIR))
from audio_generate import call_fish, load_env  # 実績あるFish Audio呼び出しを再利用

LEAD_IN_SEC = 0.3       # セグメント先頭からナレーション開始までの間
TAIL_MARGIN_SEC = 0.2   # セグメント末尾に残す余白
MAX_ATEMPO = 1.35       # 話速調整の上限（これ以上は不自然になる）
BGM_LUFS = -23          # BGMベッドの音量（ナレーション-15 LUFSの下に安定して収まる）
BGM_DIR = PROJECT_ROOT / "content/bgm"


def probe_duration(path: Path) -> float:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, timeout=60,
    )
    return float(proc.stdout.strip())


def ffmpeg(args: list, timeout: int = 300) -> None:
    proc = subprocess.run(["ffmpeg", "-v", "error", "-y", *args],
                          capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg失敗: {proc.stderr[-500:]}")


def tts_segment(text: str, out_mp3: Path, api_key: str, voice_id: str) -> None:
    """Fish AudioでTTS→無音トリム→MP3保存（audio_generate.pyと同じWAV経由方式）。"""
    wav_bytes = call_fish(text, api_key, voice_id, audio_format="wav")
    tmp_wav = out_mp3.with_suffix(".tmp.wav")
    tmp_wav.write_bytes(wav_bytes)
    ffmpeg([
        "-i", str(tmp_wav),
        "-af", "silenceremove=start_periods=1:start_threshold=-30dB:start_silence=0.05,"
               "areverse,silenceremove=start_periods=1:start_threshold=-30dB:start_silence=0.1,areverse",
        "-c:a", "libmp3lame", "-q:a", "2", str(out_mp3),
    ])
    tmp_wav.unlink(missing_ok=True)


def fit_to_window(src_mp3: Path, dst_mp3: Path, window_sec: float) -> float:
    """ナレーションを時間窓に収める。必要ならatempoで話速を上げる。収まらなければ例外。"""
    dur = probe_duration(src_mp3)
    if dur <= window_sec:
        shutil.copyfile(src_mp3, dst_mp3)
        return dur
    tempo = dur / window_sec
    if tempo > MAX_ATEMPO:
        raise RuntimeError(
            f"ナレーションが長すぎます: {dur:.1f}s（枠 {window_sec:.1f}s、必要話速 x{tempo:.2f} > "
            f"上限 x{MAX_ATEMPO}）。原稿を短くしてください: {src_mp3.name}"
        )
    ffmpeg(["-i", str(src_mp3), "-af", f"atempo={tempo:.4f}",
            "-c:a", "libmp3lame", "-q:a", "2", str(dst_mp3)])
    return probe_duration(dst_mp3)


def prepare_bgm(src: Path, total_sec: float, work_dir: Path) -> Path:
    """BGM音源を動画全長にフィットさせる。

    足りない場合は2秒クロスフェードでループし（ハードカットの継ぎ目を作らない）、
    全長にトリム後、末尾1.2秒をフェードアウト。音量はBGM_LUFSに正規化する。
    """
    out = work_dir / "bgm_fit.m4a"
    src_dur = probe_duration(src)
    if src_dur >= total_sec:
        chain_in = ["-i", str(src)]
        graph = "[0:a]anull[bgm]"
    else:
        # 2回分入力してacrossfadeで繋ぐ（20秒動画×15秒音源なら1回のループで足りる。
        # それ以上必要な長尺は現仕様(最大20秒)では発生しない）
        chain_in = ["-i", str(src), "-i", str(src)]
        graph = "[0:a][1:a]acrossfade=d=2:c1=tri:c2=tri[bgm]"
    fade_start = max(0.0, total_sec - 1.2)
    graph += (
        f";[bgm]loudnorm=I={BGM_LUFS}:TP=-2:LRA=7,"
        f"atrim=0:{total_sec:.3f},afade=t=out:st={fade_start:.3f}:d=1.2[bgmout]"
    )
    ffmpeg([*chain_in, "-filter_complex", graph, "-map", "[bgmout]",
            "-c:a", "aac", "-b:a", "192k", str(out)])
    return out


def pick_bgm(meta: dict, cli_bgm: str | None) -> Path | None:
    if cli_bgm:
        p = Path(cli_bgm)
        if not p.is_absolute():
            p = (PROJECT_ROOT / cli_bgm).resolve()
        return p if p.exists() else None
    if meta.get("bgm_file"):
        p = BGM_DIR / meta["bgm_file"]
        if p.exists():
            return p
        # 台本が作例のファイル名をそのまま書くことがある。指定が見つからないだけで BGM なしにしない
        print(f"[warn] reel_meta.json の bgm_file「{meta['bgm_file']}」が content/bgm/ にありません。"
              "先頭の mp3 を使います", file=sys.stderr)
    candidates = sorted(BGM_DIR.glob("*.mp3"))
    return candidates[0] if candidates else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--meta", required=True)
    ap.add_argument("--video", required=True, help="入力動画（ナレーションなし・音楽+SE入り）")
    ap.add_argument("--out", required=True, help="出力MP4（ナレーションミックス済み）")
    ap.add_argument("--skip-tts", action="store_true",
                    help="生成済み narration_seg<N>.mp3 を再利用（TTSを呼ばない）")
    ap.add_argument("--bgm", default=None,
                    help="BGM音源のパス（省略時: reel_meta.jsonのbgm_file → content/bgm/の先頭mp3）")
    args = ap.parse_args()

    meta_path = Path(args.meta)
    if not meta_path.is_absolute():
        meta_path = (PROJECT_ROOT / args.meta).resolve()
    video_path = Path(args.video)
    if not video_path.is_absolute():
        video_path = (PROJECT_ROOT / args.video).resolve()
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = (PROJECT_ROOT / args.out).resolve()
    meta_dir = meta_path.parent

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    mode = meta.get("narration_mode", "fish_audio")
    narration_segments = meta.get("narration_segments") or []

    if not video_path.exists():
        print(f"[!] 入力動画がありません: {video_path}", file=sys.stderr)
        return 2

    if mode == "native" or not narration_segments:
        print("[+] narration_mode=native — 動画をそのまま採用します")
        if video_path.resolve() != out_path.resolve():
            shutil.copyfile(video_path, out_path)
        return 0

    # セグメントの時間窓を計算
    segments = meta.get("segments") or [{"duration_sec": int(meta["duration_sec"])}]
    seg_durations = [int(s["duration_sec"]) for s in segments]
    offsets = [sum(seg_durations[:i]) for i in range(len(seg_durations))]

    load_env(PROJECT_ROOT)
    api_key = os.environ.get("FISH_AUDIO_API_KEY", "").strip()
    voice_id = os.environ.get("FISH_AUDIO_VOICE_ID", "").strip()
    if not args.skip_tts and (not api_key or not voice_id):
        print("[!] FISH_AUDIO_API_KEY / FISH_AUDIO_VOICE_ID が .env に必要です"
              "（narration_mode=fish_audio）。ナレーションなしで進める場合は"
              " reel_meta.json を narration_mode=native にしてください。", file=sys.stderr)
        return 1

    # セグメントごとにTTS→時間窓へフィット
    fitted = []
    for ns in narration_segments:
        n = int(ns["segment"])
        if not (1 <= n <= len(seg_durations)):
            print(f"[!] narration_segments の segment={n} が segments 定義と合いません", file=sys.stderr)
            return 2
        raw = meta_dir / f"narration_seg{n}.mp3"
        fit = meta_dir / f"narration_seg{n}.fit.mp3"
        if args.skip_tts:
            if not raw.exists():
                print(f"[!] --skip-tts 指定ですが {raw.name} がありません", file=sys.stderr)
                return 2
            print(f"[+] segment {n}: 既存ナレーションを再利用 ({raw.name})")
        else:
            print(f"[+] segment {n}: Fish Audio TTS ({len(ns['text'])} chars)")
            tts_segment(ns["text"], raw, api_key, voice_id)
        window = seg_durations[n - 1] - LEAD_IN_SEC - TAIL_MARGIN_SEC
        dur = fit_to_window(raw, fit, window)
        print(f"    {dur:.1f}s / 枠 {window:.1f}s (segment {n})")
        fitted.append((n, fit))

    # BGM準備（music_mode=file_bgm のとき。動画音声はSEのみの前提）
    total_sec = probe_duration(video_path)
    music_mode = meta.get("music_mode", "file_bgm")
    bgm_fit = None
    if music_mode != "native":
        bgm_src = pick_bgm(meta, args.bgm)
        if bgm_src is None:
            print("[warn] content/bgm/ にBGM音源がありません。BGMなし（SE+ナレーション）で続行します")
        else:
            print(f"[+] BGM: {bgm_src.name} を全編にループ敷き込み（{BGM_LUFS} LUFS）")
            bgm_fit = prepare_bgm(bgm_src, total_sec, meta_dir)

    # ミックス: ナレーションを各セグメント位置に配置し、BGM+SEはナレーション中だけ
    # サイドチェインで自動的に下げる（ダッキング）
    inputs = ["-i", str(video_path)]
    delay_labels = []
    fc = []
    for i, (n, fit) in enumerate(fitted, start=1):
        inputs += ["-i", str(fit)]
        delay_ms = int((offsets[n - 1] + LEAD_IN_SEC) * 1000)
        # loudnorm: TTSソースの収録音量差を吸収し、スピーチ標準(-15 LUFS)に揃えてから配置する
        fc.append(
            f"[{i}:a]loudnorm=I=-15:TP=-1.5:LRA=11,adelay={delay_ms}|{delay_ms}[d{i}]"
        )
        delay_labels.append(f"[d{i}]")
    bed = "[0:a]"
    if bgm_fit is not None:
        bgm_idx = len(fitted) + 1
        inputs += ["-i", str(bgm_fit)]
        fc.append(f"[0:a][{bgm_idx}:a]amix=inputs=2:duration=first:normalize=0[bed]")
        bed = "[bed]"
    if len(delay_labels) == 1:
        fc.append(f"{delay_labels[0]}anull[nar0]")
    else:
        fc.append(f"{''.join(delay_labels)}amix=inputs={len(delay_labels)}:normalize=0[nar0]")

    # ダッキングは既定でオフ（2026-08-31ユーザー要望: BGMはナレーション中も音量を
    # 下げない。参考動画も全編一定レベル）。BGM(-23 LUFS)とナレーション(-15 LUFS)の
    # 音量差で聞き取りは確保する。必要なら reel_meta.json に "ducking": true で復活可
    if meta.get("ducking", False):
        # apad必須: ナレーションは動画より短い。パディングしないと sidechaincompress が
        # ナレーション終了時点で音声ストリームごと打ち切り、末尾のBGMが消える
        # （2026-08-30に実際に起きたバグ。amixのduration=firstは残尺を救済しない）
        fc.append("[nar0]apad[nar]")
        fc.append("[nar]asplit=2[narKey][narMix]")
        fc.append(f"{bed}[narKey]sidechaincompress=threshold=0.02:ratio=8:attack=30:release=400[duck]")
        fc.append("[duck][narMix]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[aout]")
    else:
        fc.append(f"{bed}[nar0]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[aout]")

    ffmpeg([
        *inputs,
        "-filter_complex", ";".join(fc),
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(out_path),
    ])

    out_dur = probe_duration(out_path)
    in_dur = probe_duration(video_path)
    if abs(out_dur - in_dur) > 0.5:
        print(f"[!] ミックス後の尺がズレています: {out_dur:.1f}s (元 {in_dur:.1f}s)", file=sys.stderr)
        return 1
    duck_note = "ducking on" if meta.get("ducking", False) else "BGM constant (no ducking)"
    print(f"[done] {out_path} ({out_dur:.1f}s, narration={len(fitted)} segment(s), {duck_note})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
