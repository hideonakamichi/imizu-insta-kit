#!/usr/bin/env python3
"""
burn_subtitles.py - SRT字幕を動画に焼き込む（新規スクリプト）

参照リポジトリ myuuu-io/youtube の telop-srt-toolkit は「Premiere Pro取り込み用SRTを
生成するところまで」が役割で、動画への焼き込みは行っていなかった（人間が編集ソフトで
テロップとして流し込む前提）。本プロジェクトは無人自動化のため、生成したSRTを
ffmpegでそのまま動画に焼き込むこのスクリプトを新規追加する。

縦型リール（1080x1920）向けに、画面下部・大きめ・白文字＋黒縁取りのスタイルを既定にする。

## SRT→ASS変換とPlayResの罠（重要）

ffmpegの`subtitles`フィルタにSRTを直接渡すと、内部でASSに自動変換されるが、その際
`PlayResX: 384 / PlayResY: 288`という固定デフォルトが使われる（実際の動画解像度とは
無関係）。FontSize/MarginVはこのPlayRes基準でスケールされるため、1080x1920動画に対して
素直にFontSize=56やMarginV=160を指定しても、実際には約6.67倍（1920/288）に拡大されて
描画され、画面下部を狙ったはずの字幕が中央付近に出るバグになる（開発時に実際に発生・
pixel解析で確認済み）。

対策として、SRTを一度ASSに変換し、`PlayResX`/`PlayResY`を実際の動画解像度に書き換えてから
焼き込む。これによりFontSize/MarginVの指定値がそのまま実ピクセル基準で機能する。

使い方:
  python3 burn_subtitles.py --video reel_raw.mp4 --srt reel.srt --out reel_subtitled.mp4
"""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path


# libass force_style。縦型・小画面での可読性を優先し、大きめフォント・太めアウトラインにする。
# PlayResXを実解像度に書き換えた後の値なので、FontSize/MarginVは実ピクセル単位として扱える。
#
# MarginV=380（1080x1920比で約20%）は、Phase 2の実運用でInstagramリールのUI
# （いいね・コメント・シェア・キャプション等が並ぶ画面下部帯）に字幕が隠れる問題が
# 実際に発生したため、それを避けるための値。reel-production/references/
# slides-json-spec.md の「画面下部32%は字幕専用に空ける」ルールとセットで機能する
# （スライド側が下部32%を空けていれば、この字幕帯とスライド見出しは重ならない）。
DEFAULT_FORCE_STYLE = (
    "FontName=Noto Sans JP,FontSize=56,PrimaryColour=&H00FFFFFF,"
    "OutlineColour=&H00000000,BorderStyle=1,Outline=4,Shadow=0,"
    "Alignment=2,MarginV=380"
)


def ffmpeg_escape_path(p: Path) -> str:
    """ffmpegのsubtitlesフィルタに渡すパスをエスケープする（コロン・バックスラッシュ対策）。"""
    s = str(p.resolve())
    s = s.replace("\\", "\\\\").replace(":", "\\:")
    return s


def probe_video_size(video: Path) -> tuple[int, int]:
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", str(video)],
        capture_output=True, text=True,
    )
    w_str, h_str = res.stdout.strip().split(",")
    return int(w_str), int(h_str)


def srt_to_ass_with_correct_playres(srt: Path, ass_out: Path, width: int, height: int) -> None:
    """SRTをASSに変換し、PlayResX/PlayResYを実際の動画解像度に書き換える。"""
    res = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(srt), str(ass_out)],
        capture_output=True,
    )
    if res.returncode != 0:
        raise RuntimeError(f"SRT->ASS変換に失敗: {res.stderr.decode()[-500:]}")

    text = ass_out.read_text(encoding="utf-8")
    text = re.sub(r"PlayResX:\s*\d+", f"PlayResX: {width}", text)
    text = re.sub(r"PlayResY:\s*\d+", f"PlayResY: {height}", text)
    ass_out.write_text(text, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", type=Path, required=True, help="字幕を焼き込む動画")
    ap.add_argument("--srt", type=Path, required=True, help="焼き込むSRTファイル")
    ap.add_argument("--out", type=Path, required=True, help="出力パス")
    ap.add_argument(
        "--force-style", default=DEFAULT_FORCE_STYLE,
        help="libass force_style（既定は縦型向け白文字+黒縁取り）",
    )
    args = ap.parse_args()

    if not args.video.exists():
        print(f"エラー: 動画が見つかりません: {args.video}", file=sys.stderr)
        return 1
    if not args.srt.exists():
        print(f"エラー: SRTが見つかりません: {args.srt}", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    video_w, video_h = probe_video_size(args.video)

    with tempfile.TemporaryDirectory(prefix="burn_subtitles_") as tmp:
        ass_path = Path(tmp) / "subs.ass"
        srt_to_ass_with_correct_playres(args.srt, ass_path, video_w, video_h)

        ass_escaped = ffmpeg_escape_path(ass_path)
        vf = f"subtitles='{ass_escaped}':force_style='{args.force_style}'"

        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(args.video),
            "-vf", vf,
            "-c:v", "libx264", "-crf", "18", "-preset", "medium",
            "-c:a", "copy",
            str(args.out),
        ]
        print(f"[burn] {args.video.name} + {args.srt.name} -> {args.out.name} (PlayRes={video_w}x{video_h})")
        res = subprocess.run(cmd, capture_output=True)
        if res.returncode != 0:
            print("[error] ffmpeg字幕焼き込みに失敗しました", file=sys.stderr)
            print(res.stderr.decode()[-800:], file=sys.stderr)
            return 1

    size_mb = args.out.stat().st_size / (1024 * 1024)
    print(f"[ok] {args.out.name} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
