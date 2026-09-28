"""コンセプト空間分析 — 空きポジ抽出（コピーベース）

manifest.jsonl の各広告の body_text（広告コピー）を Gemini Embedding
(gemini-embedding-001) でベクトル化 → PCA 2次元化 → グリッド距離法で
「既存クリエイティブから最も遠い座標 = 空きポジ Top-K」を抽出する。

設計方針:
  - 空きポジ＝訴求コンセプトの隙間 なので、画像ではなく広告コピーで距離を測る
  - 画像分類（filter ステージ）は廃止。コピーベースなら症例写真の有無は無関係
  - 入力は scrape.py が出す manifest.jsonl をそのまま使う

使い方:
  python analyze.py --data-dir data/<project-a>
  python analyze.py --data-dir data/<project-a> data/<project-b>

複数 --data-dir を指定するとマージして 1 空間で分析する。

出力:
  <data_dirs[0]>/analyze_YYYY-MM-DD_HHMMSS[_merged_with_xxx]/
    concept_map.json   各点の2D座標・コピー要約・空きポジTop-K
    concept_map.png    可視化プロット
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from google import genai
from google.genai import types

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[3]


def load_env(project_root: Path) -> None:
    """.env を読んで os.environ に注入。python-dotenv 依存を避ける簡易実装。"""
    env_path = project_root / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if v and k not in os.environ:
            os.environ[k] = v


def pick_japanese_font() -> str | None:
    """matplotlib で日本語表示できるフォントを探す。"""
    candidates = [
        "Hiragino Sans",
        "Hiragino Maru Gothic Pro",
        "Yu Gothic",
        "Noto Sans CJK JP",
        "IPAexGothic",
        "TakaoGothic",
    ]
    available = {f.name for f in fm.fontManager.ttflist}
    for c in candidates:
        if c in available:
            return c
    return None


def load_records(data_dirs: list[Path]) -> list[dict]:
    """各 data_dir の manifest.jsonl を読み込み、body_text を持つレコードだけ返す。"""
    records = []
    for d in data_dirs:
        fp = d / "manifest.jsonl"
        if not fp.exists():
            print(f"[!] not found: {fp}", file=sys.stderr)
            continue
        for line in fp.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            body = (r.get("body_text") or "").strip()
            if not body:
                print(
                    f"[!] skip (no body_text): {r.get('library_id')} in {d.name}",
                    file=sys.stderr,
                )
                continue
            # プレースホルダ未差し替え（{{product.brand}} 等）や極端に短いコピーは除外
            if "{{" in body or len(body) < 8:
                print(
                    f"[!] skip (placeholder/too short): {r.get('library_id')} body='{body[:30]}'",
                    file=sys.stderr,
                )
                continue
            # 埋め込み入力用テキスト：広告主名＋本文（誰が何を訴求しているかを揃える）
            advertiser = (r.get("advertiser") or "").strip()
            embed_text = f"【{advertiser}】\n{body}" if advertiser else body
            # トークン上限保護：長すぎたら先頭2000文字に
            r["_embed_text"] = embed_text[:2000]
            r["_data_dir"] = str(d)
            records.append(r)
    return records


def embed_texts(
    client: genai.Client,
    model: str,
    texts: list[str],
    output_dim: int = 768,
) -> np.ndarray:
    """gemini-embedding-001 でテキストをベクトル化。"""
    vectors = []
    for i, t in enumerate(texts, 1):
        resp = client.models.embed_content(
            model=model,
            contents=t,
            config=types.EmbedContentConfig(
                task_type="CLUSTERING",
                output_dimensionality=output_dim,
            ),
        )
        vectors.append(np.asarray(resp.embeddings[0].values, dtype=np.float32))
        print(f"  [{i}/{len(texts)}] embedded dim={len(vectors[-1])}")
    return np.stack(vectors, axis=0)


def pca_2d(X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """PCAで2次元に落とす。固有値（寄与率）も返す。"""
    Xc = X - X.mean(axis=0, keepdims=True)
    U, S, Vt = np.linalg.svd(Xc, full_matrices=False)
    components = Vt[:2]
    coords = Xc @ components.T
    explained = (S**2) / (S**2).sum()
    return coords, explained[:2]


def find_gap_positions(
    coords2d: np.ndarray,
    top_k: int = 3,
    grid: int = 80,
    padding: float = 0.25,
) -> list[tuple[np.ndarray, float, list[int]]]:
    """既存点から最も離れた座標 Top-K を返す。

    Returns: [(gap_xy, min_dist, [近傍点idx Top3])]
    """
    xmin, ymin = coords2d.min(axis=0)
    xmax, ymax = coords2d.max(axis=0)
    rx = (xmax - xmin) * padding
    ry = (ymax - ymin) * padding
    gx, gy = np.meshgrid(
        np.linspace(xmin - rx, xmax + rx, grid),
        np.linspace(ymin - ry, ymax + ry, grid),
    )
    g = np.stack([gx.ravel(), gy.ravel()], axis=1)
    # 各グリッド点から全既存点への距離
    diff = g[:, None, :] - coords2d[None, :, :]
    dists = np.linalg.norm(diff, axis=2)
    min_dists = dists.min(axis=1)

    # Top-K を「互いに離れている」よう Non-Maximum Suppression
    order = np.argsort(-min_dists)
    suppress_radius = min(rx, ry) * 1.5
    picks: list[int] = []
    for idx in order:
        ok = True
        for p in picks:
            if np.linalg.norm(g[idx] - g[p]) < suppress_radius:
                ok = False
                break
        if ok:
            picks.append(idx)
        if len(picks) >= top_k:
            break

    results = []
    for p in picks:
        nearest = np.argsort(dists[p])[:3].tolist()
        results.append((g[p], float(min_dists[p]), nearest))
    return results


def plot_map(
    coords: np.ndarray,
    records: list[dict],
    gaps: list[tuple[np.ndarray, float, list[int]]],
    out_path: Path,
    title: str,
) -> None:
    jp_font = pick_japanese_font()
    if jp_font:
        plt.rcParams["font.family"] = jp_font

    fig, ax = plt.subplots(figsize=(11, 8))
    # data_dir でグループ分け（複数クエリをマージした時に色分けされる）
    dirs = sorted({r.get("_data_dir", "unknown") for r in records})
    palette = ["#3478f6", "#ff5e57", "#28b463", "#a569bd", "#f39c12", "#16a085"]
    color_map = {d: palette[i % len(palette)] for i, d in enumerate(dirs)}

    for i, r in enumerate(records):
        d = r.get("_data_dir", "unknown")
        ax.scatter(coords[i, 0], coords[i, 1], s=140, color=color_map[d], alpha=0.85, edgecolor="white", linewidth=1.5, zorder=3)
        label = (r.get("advertiser") or "")[:14]
        ax.annotate(label, (coords[i, 0], coords[i, 1]), fontsize=8, alpha=0.85, xytext=(6, 4), textcoords="offset points")

    for k, (xy, dist, nearest) in enumerate(gaps, 1):
        ax.scatter(xy[0], xy[1], marker="*", s=380, color="#ffb400", edgecolor="black", linewidth=1.4, zorder=4)
        ax.annotate(f"GAP#{k}", (xy[0], xy[1]), fontsize=11, weight="bold", xytext=(8, 6), textcoords="offset points")

    handles = [plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=color_map[d], markersize=10, label=Path(d).name) for d in dirs]
    handles.append(plt.Line2D([0], [0], marker="*", color="w", markerfacecolor="#ffb400", markeredgecolor="black", markersize=14, label="空きポジ"))
    ax.legend(handles=handles, loc="best", fontsize=9)
    ax.set_title(title, fontsize=13)
    ax.set_xlabel("PC1")
    ax.set_ylabel("PC2")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", nargs="+", required=True, help="filtered_manifest.jsonl を含むディレクトリ。複数指定でマージ。")
    ap.add_argument("--model", default="gemini-embedding-001")
    ap.add_argument("--output-dim", type=int, default=768)
    ap.add_argument("--top-k", type=int, default=3, help="抽出する空きポジ数")
    args = ap.parse_args()

    load_env(PROJECT_ROOT)
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[!] GEMINI_API_KEY が設定されていません。", file=sys.stderr)
        return 1

    data_dirs = []
    for d in args.data_dir:
        p = Path(d)
        if not p.is_absolute() or not p.exists():
            p = (PROJECT_ROOT / d).resolve()
        if not p.exists():
            print(f"[!] dir not found: {p}", file=sys.stderr)
            return 2
        data_dirs.append(p)

    records = load_records(data_dirs)
    if len(records) < 3:
        print(f"[!] レコードが少なすぎる ({len(records)}件)。最低3件必要。", file=sys.stderr)
        return 3
    print(f"[+] records: {len(records)} (from {len(data_dirs)} dirs)")

    client = genai.Client(api_key=api_key)
    texts = [r["_embed_text"] for r in records]
    print(f"[+] embedding ({args.model}, dim={args.output_dim})...")
    X = embed_texts(client, args.model, texts, output_dim=args.output_dim)
    print(f"[+] vectors shape: {X.shape}")

    coords, explained = pca_2d(X)
    print(f"[+] PCA explained: PC1={explained[0]*100:.1f}% PC2={explained[1]*100:.1f}%")

    gaps = find_gap_positions(coords, top_k=args.top_k)

    # 出力は必ず data_dirs[0] 配下に閉じる。data/ ルートを汚さない。
    # 複数入力をマージした場合は、ディレクトリ名にマージ対象を含めて区別する。
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    if len(data_dirs) == 1:
        out_dir = data_dirs[0] / f"analyze_{ts}"
    else:
        import re as _re
        labels = []
        for d in data_dirs[1:]:
            m = _re.match(r"^\d{4}-\d{2}-\d{2}_(.+)$", d.name)
            labels.append(m.group(1) if m else d.name)
        out_dir = data_dirs[0] / f"analyze_{ts}_merged_with_{'+'.join(labels)}"
    out_dir.mkdir(parents=True, exist_ok=True)

    points = []
    for i, r in enumerate(records):
        body_preview = (r.get("body_text") or "").replace("\n", " ")[:120]
        points.append({
            "library_id": r["library_id"],
            "advertiser": r.get("advertiser"),
            "body_preview": body_preview,
            "x": float(coords[i, 0]),
            "y": float(coords[i, 1]),
            "data_dir": r["_data_dir"],
        })

    gap_records = []
    for k, (xy, dist, nearest) in enumerate(gaps, 1):
        gap_records.append({
            "rank": k,
            "x": float(xy[0]),
            "y": float(xy[1]),
            "min_distance_to_existing": dist,
            "nearest_existing": [
                {
                    "library_id": records[n]["library_id"],
                    "advertiser": records[n].get("advertiser"),
                    "body_preview": (records[n].get("body_text") or "").replace("\n", " ")[:120],
                    "distance": float(np.linalg.norm(coords[n] - xy)),
                }
                for n in nearest
            ],
        })

    out_json = out_dir / "concept_map.json"
    out_json.write_text(
        json.dumps(
            {
                "generated_at": ts,
                "model": args.model,
                "output_dim": args.output_dim,
                "n_points": len(records),
                "explained_variance": [float(explained[0]), float(explained[1])],
                "points": points,
                "gaps": gap_records,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[+] JSON: {out_json}")

    out_png = out_dir / "concept_map.png"
    title = f"Concept Map ({len(records)}件)  PC1={explained[0]*100:.1f}%  PC2={explained[1]*100:.1f}%"
    plot_map(coords, records, gaps, out_png, title)
    print(f"[+] PNG : {out_png}")

    print()
    print("=== 空きポジ Top {} ===".format(args.top_k))
    for g in gap_records:
        nearest_str = " / ".join(
            f"{n['advertiser']}" for n in g["nearest_existing"]
        )
        print(
            f"  GAP#{g['rank']}  ({g['x']:+.2f}, {g['y']:+.2f})  "
            f"min_dist={g['min_distance_to_existing']:.2f}  "
            f"nearest: {nearest_str}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
