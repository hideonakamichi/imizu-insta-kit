"""LP 公開 — セクション画像を積んだ静的LPサイトを組み立て、Vercel にデプロイして URL を発行する

入力: lp/<lp_id>_sections.json（lp-designer が書いたもの）＋ images/<lp_id>/ のセクション画像
出力: lp/site/<lp-id>/ （index.html + assets/）、--deploy 時は公開URL（deploy_url.txt にも保存）

使い方:
  python publish.py --json data/my-project/lp/example_sections.json                                  # ビルドのみ
  python publish.py --json <path> --deploy                                                        # ビルド＋プレビューデプロイ
  python publish.py --json <path> --deploy --prod --cta-url "https://example.com/apply"            # 本番＋CTAリンク指定

前提:
  - Vercel CLI は npx 経由で呼ぶ（Node.js が必要）。認証は `.env` の VERCEL_TOKEN か、`vercel login` 済みであること。
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from html import escape
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[3]


def load_env(project_root: Path) -> None:
    env_path = project_root / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if v and k not in os.environ:
            os.environ[k] = v


def section_dirname(section_id: str) -> str:
    """S01_fv -> 01.fv（lp_image.py と同じ規則）"""
    body = section_id.lstrip("Ss")
    if "_" in body:
        num, rest = body.split("_", 1)
        return f"{num}.{rest}"
    return body


def sanitize_project_name(lp_id: str) -> str:
    """Vercel プロジェクト名に使える形（小文字英数とハイフン）へ"""
    name = re.sub(r"[^a-z0-9-]+", "-", lp_id.lower()).strip("-")
    return name or "lp"


def latest_png(section_dir: Path) -> Path | None:
    pngs = sorted(section_dir.glob("*.png"))
    return pngs[-1] if pngs else None


def build_site(spec: dict, json_path: Path, cta_url: str, accent: str) -> Path:
    lp_id = spec["lp_id"]
    product = spec.get("product", lp_id)
    direction = spec.get("direction", "")
    sections = spec["sections"]

    images_root = json_path.parent / "images" / lp_id
    site_dir = json_path.parent / "site" / sanitize_project_name(lp_id)
    assets_dir = site_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    cta_label = "詳しく見る"
    img_tags: list[str] = []
    missing: list[str] = []
    for i, s in enumerate(sections):
        dname = section_dirname(s["id"])
        src = latest_png(images_root / dname)
        if src is None:
            missing.append(s["id"])
            continue
        dst = assets_dir / f"{dname}.png"
        shutil.copyfile(src, dst)
        embed = s.get("embed_text", {})
        alt = embed.get("headline") or s.get("name") or s["id"]
        if embed.get("cta"):
            cta_label = embed["cta"]
        loading = "eager" if i == 0 else "lazy"
        img_tags.append(
            f'    <img src="assets/{dname}.png" alt="{escape(alt)}" loading="{loading}">'
        )
        print(f"[+] section {s['id']}: {src.name} -> assets/{dname}.png")

    if not img_tags:
        raise RuntimeError(f"セクション画像が1枚もありません: {images_root}")
    if missing:
        print(f"[!] 画像なしでスキップ: {', '.join(missing)}", file=sys.stderr)

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(product)}</title>
<meta name="description" content="{escape(direction)}">
<meta property="og:title" content="{escape(product)}">
<meta property="og:description" content="{escape(direction)}">
<meta name="robots" content="noindex">
<style>
  :root {{ --accent: {accent}; --text: #34352f; --base: #f5f3ef; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: var(--base); color: var(--text);
         font-family: "Hiragino Kaku Gothic ProN", "Hiragino Sans", "Noto Sans JP", sans-serif; }}
  main {{ max-width: 480px; margin: 0 auto; background: #fff;
          box-shadow: 0 0 24px rgba(52, 53, 47, .08); }}
  main img {{ display: block; width: 100%; height: auto; }}
  .cta {{ position: sticky; bottom: 0; padding: 12px 16px;
          background: rgba(245, 243, 239, .95); }}
  .cta a {{ display: block; max-width: 448px; margin: 0 auto; padding: 16px;
            background: var(--accent); color: #fff; text-align: center;
            text-decoration: none; font-weight: 700; font-size: 16px;
            border-radius: 999px; }}
  footer {{ max-width: 480px; margin: 0 auto; padding: 24px 16px 40px;
            font-size: 12px; color: #8a8a82; text-align: center; }}
</style>
</head>
<body>
  <main>
{chr(10).join(img_tags)}
    <div class="cta"><a href="{escape(cta_url)}">{escape(cta_label)}</a></div>
  </main>
  <footer>{escape(product)}</footer>
</body>
</html>
"""
    (site_dir / "index.html").write_text(html, encoding="utf-8")
    print(f"[+] site    : {site_dir}")
    print(f"    ✓ index.html（画像 {len(img_tags)} セクション）")
    return site_dir


def deploy_site(site_dir: Path, prod: bool) -> str | None:
    cmd = ["npx", "-y", "vercel", "deploy", str(site_dir), "--yes"]
    if prod:
        cmd.append("--prod")
    token = os.environ.get("VERCEL_TOKEN")
    if token:
        cmd += ["--token", token]
    else:
        print("[!] VERCEL_TOKEN 未設定。`vercel login` 済みの認証情報で試行します。", file=sys.stderr)
    print(f"[+] deploy  : npx vercel deploy {'--prod' if prod else '(preview)'}")
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
    out = (res.stdout or "") + "\n" + (res.stderr or "")
    urls = re.findall(r"https://[a-z0-9.-]+\.vercel\.app", out)
    if res.returncode != 0 or not urls:
        print(f"[!] デプロイ失敗 (exit={res.returncode})", file=sys.stderr)
        print(out.strip()[-2000:], file=sys.stderr)
        return None
    url = urls[-1]
    (site_dir / "deploy_url.txt").write_text(url + "\n", encoding="utf-8")
    print(f"    ✓ 公開URL: {url}")
    return url


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", required=True, help="lp/<lp_id>_sections.json のパス")
    ap.add_argument("--cta-url", default=os.environ.get("CTA_URL", "#"),
                    help="CTAボタンのリンク先（既定: 環境変数 CTA_URL か '#'）")
    ap.add_argument("--accent", default="#34352f", help="CTAボタンの色（既定: チャコール）")
    ap.add_argument("--deploy", action="store_true", help="ビルド後に Vercel へデプロイする")
    ap.add_argument("--prod", action="store_true", help="--deploy 時に本番デプロイにする")
    args = ap.parse_args()

    load_env(PROJECT_ROOT)

    json_path = Path(args.json)
    if not json_path.is_absolute():
        json_path = (PROJECT_ROOT / args.json).resolve()
    if not json_path.exists():
        print(f"[!] not found: {json_path}", file=sys.stderr)
        return 2

    spec = json.loads(json_path.read_text(encoding="utf-8"))
    print(f"[+] lp_id   : {spec['lp_id']}")

    try:
        site_dir = build_site(spec, json_path, args.cta_url, args.accent)
    except RuntimeError as e:
        print(f"[!] {e}", file=sys.stderr)
        return 3

    if args.deploy:
        url = deploy_site(site_dir, args.prod)
        if url is None:
            return 4

    return 0


if __name__ == "__main__":
    sys.exit(main())
