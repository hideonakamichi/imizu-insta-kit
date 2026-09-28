"""generate_video.py — 統合マルチモーダルプロンプトからリール動画をフル生成する

reel-script-writer が書いた動画プロンプト（ショット別タイムスタンプ・タイポグラフィ・
SE/BGM/ナレーション込みの統合プロンプト。仕様: references/video-prompt-spec.md）を、
Grok CLI 経由の動画生成（grok-imagine-video-1.5、9:16、音声込み）でMP4にする。

動画生成モデルの1クリップ上限は15秒のため、16〜20秒のリールは2セグメント
（各8〜10秒）を生成してffmpegで結合する（音楽の継ぎ目はプロンプト設計で吸収する。
仕様書「セグメント構成」参照）。

Usage:
    python3 generate_video.py --meta OUTPUT_DIR/reel_meta.json \
        --out OUTPUT_DIR/reel_video.mp4
    python3 generate_video.py --meta ... --out ... --only-segment 2   # 失敗セグメントの再生成
    python3 generate_video.py --meta ... --out ... --lint-only        # 生成せず事前検査だけ

生成前に lint_prompt.py（プロンプトの事前検査）を自動実行する。エラーがあれば Grok を
呼ばずに exit 2 で止まる（1セグメント2〜5分の生成と evaluator 1周を無駄にしないため）。
lint の指摘は reel-script-writer に渡して直させる。--skip-lint は手動デバッグ専用。

reel_meta.json の必須キー: duration_sec（10〜20）、segments（各 file / duration_sec）。
プロンプトファイルは reel_meta.json と同じディレクトリに置く。
検証: セグメントごとに 9:16／尺±2秒／音声トラックあり、結合後に合計尺を機械確認。
失敗時は非0終了。リトライは loop-limits.yaml の video_generation_retry に従い
オーケストレーターが行う。
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[3]

sys.path.insert(0, str(PROJECT_ROOT / ".claude/skills/shared/scripts"))
sys.path.insert(0, str(SCRIPT_DIR))
import grok_media
import lint_prompt

MAX_TOTAL_SEC = 20
MAX_SEGMENT_SEC = 15


def load_segments(meta: dict, meta_dir: Path) -> list[dict]:
    """metaからセグメント定義を読む。旧形式（segmentsなし）は1セグメント扱い。"""
    segments = meta.get("segments")
    if not segments:
        segments = [{"file": "video_prompt_1.txt", "duration_sec": int(meta["duration_sec"])}]
    result = []
    for i, seg in enumerate(segments, start=1):
        path = meta_dir / seg["file"]
        dur = int(seg["duration_sec"])
        if not path.exists():
            # 旧名 video_prompt.txt へのフォールバック（1セグメント時のみ）
            legacy = meta_dir / "video_prompt.txt"
            if len(segments) == 1 and legacy.exists():
                path = legacy
            else:
                raise FileNotFoundError(f"segment {i}: プロンプトがありません: {path}")
        if not (5 <= dur <= MAX_SEGMENT_SEC):
            raise ValueError(f"segment {i}: duration_sec は5〜{MAX_SEGMENT_SEC}にしてください（現在: {dur}）")
        prompt = path.read_text(encoding="utf-8").strip()
        if len(prompt) < 200:
            raise ValueError(
                f"segment {i}: プロンプトが短すぎます（{len(prompt)}字）。"
                "video-prompt-spec.md のテンプレートに従っているか確認してください。"
            )
        result.append({"idx": i, "path": path, "duration": dur, "prompt": prompt})
    return result


def concat_segments(clip_paths: list[Path], out_path: Path, music_mode: str = "file_bgm") -> None:
    """セグメントを1080x1920に正規化して結合する（映像・音声とも再エンコード）。

    クリップごとに実解像度が微妙に違うことがある（実測: 1088x1920）ため、
    scale+padで統一してから concat フィルタで繋ぐ。

    music_mode="native"（動画側に音楽を焼き込む旧構成）ではセグメント間の音楽音量差を
    loudnormで揃える。既定の "file_bgm"（音声=SEのみ、BGMは narrate_and_mix.py が
    ファイルから敷く）では、まばらなSEをloudnormすると過剰増幅されるため何もしない。
    """
    inputs = []
    for p in clip_paths:
        inputs += ["-i", str(p)]
    n = len(clip_paths)
    a_filter = (
        "loudnorm=I=-21:TP=-2:LRA=11,aresample=48000" if music_mode == "native"
        else "aresample=48000"
    )
    norm = "".join(
        f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
        f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=24[v{i}];"
        f"[{i}:a]{a_filter}[a{i}];"
        for i in range(n)
    )
    streams = "".join(f"[v{i}][a{i}]" for i in range(n))
    filter_complex = f"{norm}{streams}concat=n={n}:v=1:a=1[v][a]"
    cmd = [
        "ffmpeg", "-v", "error", "-y", *inputs,
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(out_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg concat失敗: {proc.stderr[-500:]}")


DEAD_AUDIO_DB = -48.0  # 1秒窓の平均がこれ未満なら「音が死んでいる」とみなす


def check_audio_bed(path: Path, duration: int) -> None:
    """音楽・SEベッドの無音帯チェック。

    生成音楽は尺いっぱい鳴るよう指示しても早く終わることがある（実測: 10秒指示で
    8秒以降無音）。無音帯は「終盤で音が消えた」体感に直結するため、生成失敗として
    非0終了させ、video_generation_retry のリトライに乗せる。
    冒頭1秒は立ち上がりの静けさを許容してスキャン対象外。
    """
    dead = []
    for ss in range(1, duration - 1):
        proc = subprocess.run(
            ["ffmpeg", "-v", "info", "-ss", str(ss), "-t", "1", "-i", str(path),
             "-map", "0:a", "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, text=True, timeout=60,
        )
        for line in proc.stderr.splitlines():
            if "mean_volume:" in line:
                db = float(line.split("mean_volume:")[1].replace("dB", "").strip())
                if db < DEAD_AUDIO_DB:
                    dead.append((ss, db))
    if dead:
        zones = ", ".join(f"{ss}s({db:.0f}dB)" for ss, db in dead)
        raise RuntimeError(
            f"音楽・SEに無音帯があります: {zones} — 音楽が尺の途中で途切れた生成ハズレ。"
            "このセグメントを再生成してください"
        )


def probe_duration(path: Path) -> float:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, timeout=60,
    )
    return float(proc.stdout.strip())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--meta", required=True, help="reel_meta.json のパス")
    ap.add_argument("--out", required=True,
                    help="出力MP4のパス（例: OUTPUT_DIR/reel_video.mp4）。"
                         "reel_final.mp4 は narrate_and_mix.py がナレーションを重ねた"
                         "投稿用ファイルの名前なので、ここに指定しないこと（上書き事故になる）")
    ap.add_argument("--only-segment", type=int, default=None,
                    help="指定セグメント(1始まり)だけ再生成して再結合する")
    ap.add_argument("--lint-only", action="store_true",
                    help="プロンプトの事前検査（lint_prompt.py）だけ行い、生成しない")
    ap.add_argument("--skip-lint", action="store_true",
                    help="事前検査を飛ばす（手動デバッグ専用。自動運用では使わない）")
    # 旧インターフェース互換（--prompt は segments 定義があれば無視される）
    ap.add_argument("--prompt", default=None, help=argparse.SUPPRESS)
    args = ap.parse_args()

    meta_path = Path(args.meta)
    if not meta_path.is_absolute():
        meta_path = (PROJECT_ROOT / args.meta).resolve()
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = (PROJECT_ROOT / args.out).resolve()
    meta_dir = meta_path.parent

    # --- 事前検査（生成前に「読めば分かる不備」で止める） -------------------
    if not args.skip_lint:
        rep = lint_prompt.lint(meta_path)
        for name, st in rep.stats.items():
            if isinstance(st, dict) and "chars" in st:
                print(f"[lint] {name}: {st['chars']}字 / 否定表現 {st['negations']}件")
        for w in rep.warnings:
            print(f"[lint][W] {w}")
        for e in rep.errors:
            print(f"[lint][E] {e}", file=sys.stderr)
        if not rep.ok:
            print(f"[!] 事前検査でエラー {len(rep.errors)}件。生成せず終了します。"
                  " 指摘を reel-script-writer に渡して video_prompt_N.txt と reel_meta.json を直してください",
                  file=sys.stderr)
            return 2
        print(f"[lint] ok（警告 {len(rep.warnings)}件）")
        if args.lint_only:
            return 0
    elif args.lint_only:
        print("[!] --lint-only と --skip-lint は同時に指定できません", file=sys.stderr)
        return 2

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        total = int(meta["duration_sec"])
        music_mode = meta.get("music_mode", "file_bgm")
        segments = load_segments(meta, meta_dir)
    except Exception as e:
        print(f"[!] reel_meta.json の読み取りに失敗: {e}", file=sys.stderr)
        return 2

    if not (10 <= total <= MAX_TOTAL_SEC):
        print(f"[!] duration_sec は10〜{MAX_TOTAL_SEC}にしてください（現在: {total}）", file=sys.stderr)
        return 2
    seg_sum = sum(s["duration"] for s in segments)
    if seg_sum != total:
        print(f"[!] segments の合計（{seg_sum}s）が duration_sec（{total}s）と一致しません", file=sys.stderr)
        return 2

    try:
        grok_media.resolve_grok()
    except FileNotFoundError as e:
        print(f"[!] {e}", file=sys.stderr)
        return 1

    targets = segments
    if args.only_segment is not None:
        if not (1 <= args.only_segment <= len(segments)):
            print(f"[!] --only-segment は1〜{len(segments)}で指定してください", file=sys.stderr)
            return 2
        targets = [s for s in segments if s["idx"] == args.only_segment]
        print(f"[+] segment {args.only_segment} のみ再生成（全{len(segments)}セグメント構成）")

    clip_paths = [meta_dir / f"segment_{s['idx']}.mp4" for s in segments]

    for seg in targets:
        clip = meta_dir / f"segment_{seg['idx']}.mp4"
        print(f"[+] generating segment {seg['idx']}/{len(segments)}: {seg['duration']}s, 9:16, audio=on")
        print(f"    prompt: {seg['path'].name} ({len(seg['prompt'])} chars)")
        try:
            info = grok_media.generate_video(seg["prompt"], clip, duration_sec=seg["duration"])
            if music_mode == "native":
                # 音楽焼き込み構成のみ: 音楽が尺の途中で無音化する生成ハズレを検出。
                # file_bgm構成（音声=まばらなSEのみ）では無音帯が正常なのでスキップ
                check_audio_bed(clip, seg["duration"])
        except Exception as e:
            print(f"[!] segment {seg['idx']} の生成に失敗しました: {e}", file=sys.stderr)
            return 1
        print(f"    OK {info['width']}x{info['height']}, {info['duration']:.1f}s")

    missing = [p for p in clip_paths if not p.exists()]
    if missing:
        if args.only_segment is not None:
            # セグメント分割実行の途中（headlessのBash 600秒制約対策で1セグメントずつ
            # 呼ばれるケース）。残りを生成してから再実行すれば結合される
            print(f"[ok] segment {args.only_segment} 生成完了。未生成: "
                  f"{[p.name for p in missing]} — 残りのセグメントを --only-segment で"
                  "生成すると自動的に結合されます")
            return 0
        print(f"[!] 未生成のセグメントがあります: {[p.name for p in missing]}", file=sys.stderr)
        return 1

    if len(clip_paths) == 1:
        # 1セグメント: 正規化のみ不要、そのまま採用
        out_path.unlink(missing_ok=True)
        out_path.write_bytes(clip_paths[0].read_bytes())
    else:
        print(f"[+] concatenating {len(clip_paths)} segments -> {out_path.name}")
        try:
            concat_segments(clip_paths, out_path, music_mode=music_mode)
        except Exception as e:
            print(f"[!] 結合に失敗しました: {e}", file=sys.stderr)
            return 1

    final_dur = probe_duration(out_path)
    if abs(final_dur - total) > 2.5:
        print(f"[!] 結合後の尺がズレています: {final_dur:.1f}s (expected {total}s)", file=sys.stderr)
        return 1
    print(f"[done] {out_path}")
    print(f"       total {final_dur:.1f}s ({len(segments)} segment(s)), audio=yes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
