"""Meta広告ライブラリ スクレイピング

検索URLにアクセス → SSR埋め込みJSONから初期広告データを抽出 →
スクロールで追加読込（/api/graphql/ XHRレスポンスをインターセプト）→ メタ情報を保存。

このパイプラインでは**広告コピー（body_text）**から空きポジションを探すため、
既定で画像ダウンロードは行わない。画像URLは manifest.jsonl に記録するので、
あとから --with-images で追加取得することも可能。

使い方:
  python scrape.py --query "<商品キーワード>" --limit 100
  python scrape.py --query "副業 AI" --search-type unordered
  python scrape.py --query "美容" --limit 30 --search-type exact --with-images

検索フラグ:
  --search-type {exact, unordered}   exact=完全一致 / unordered=単語の含有（既定）
  --active-status {active, all}      active=配信中のみ（既定） / all=過去配信も
  --include-untargeted               国ターゲット指定なしの広告も含める
  --with-images                      画像をローカル保存する（既定OFF）

出力:
  data/<日付>_<query>/manifest.jsonl    1行=1広告のメタ情報（body_text + image_urls 等）
  data/<日付>_<query>/images/           --with-images 時のみ作成
"""

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from patchright.sync_api import sync_playwright

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[3]
DATA_DIR = PROJECT_ROOT / "data"
USER_DATA_DIR = PROJECT_ROOT / ".browser_profile"


def build_search_url(
    query: str,
    country: str,
    media_type: str,
    search_type: str,
    active_status: str,
    targeted_only: bool,
) -> str:
    # exact phrase の場合のみダブルクォートで囲む
    q = f'"{query}"' if search_type == "exact" else query
    params = {
        "active_status": active_status,
        "ad_type": "all",
        "country": country,
        "is_targeted_country": "true" if targeted_only else "false",
        "media_type": media_type,
        "q": q,
        "search_type": "keyword_exact_phrase" if search_type == "exact" else "keyword_unordered",
        "sort_data[direction]": "desc",
        "sort_data[mode]": "total_impressions",
    }
    return "https://www.facebook.com/ads/library/?" + urllib.parse.urlencode(params)


def extract_search_results_from_html(html: str) -> dict | None:
    """SSR埋め込みJSONから search_results_connection を取り出す。"""
    pattern = re.compile(
        r'<script type="application/json"[^>]*data-sjs[^>]*>(.+?)</script>',
        re.DOTALL,
    )
    for match in pattern.finditer(html):
        raw = match.group(1)
        if "search_results_connection" not in raw:
            continue
        try:
            blob = json.loads(raw)
        except json.JSONDecodeError:
            continue
        found = _walk_for_search_results(blob)
        if found is not None:
            return found
    return None


def _walk_for_search_results(node):
    if isinstance(node, dict):
        if "search_results_connection" in node:
            return node["search_results_connection"]
        for v in node.values():
            r = _walk_for_search_results(v)
            if r is not None:
                return r
    elif isinstance(node, list):
        for v in node:
            r = _walk_for_search_results(v)
            if r is not None:
                return r
    return None


def parse_graphql_response_body(body: str) -> list[dict]:
    """/api/graphql/ のレスポンスは複数JSONが改行で連結された NDJSON 形式。
    各行をパースして search_results_connection の edges 部分だけを集める。
    """
    edges: list[dict] = []
    for line in body.split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            blob = json.loads(line)
        except json.JSONDecodeError:
            continue
        found = _walk_for_search_results(blob)
        if found is None:
            continue
        for e in found.get("edges", []) or []:
            edges.append(e)
    return edges


def flatten_ads_from_edges(edges: list[dict]) -> list[dict]:
    """edges 配列を 広告1件=1dict のリストに整形。

    画像/動画の有無は問わない（body_text さえあれば分析対象にできる）。
    """
    ads = []
    for edge in edges:
        node = edge.get("node") or {}
        for result in node.get("collated_results", []) or []:
            snap = result.get("snapshot") or {}
            image_urls = []
            for img in snap.get("images") or []:
                url = img.get("original_image_url") or img.get("resized_image_url")
                if url:
                    image_urls.append(url)
            for card in snap.get("cards") or []:
                url = card.get("original_image_url") or card.get("resized_image_url")
                if url:
                    image_urls.append(url)
            video_urls = []
            for vid in snap.get("videos") or []:
                v = vid.get("video_hd_url") or vid.get("video_sd_url")
                if v:
                    video_urls.append(v)
            body_text = (snap.get("body") or {}).get("text")
            # body_text も画像も動画もない広告は意味ないので skip
            if not body_text and not image_urls and not video_urls:
                continue
            ads.append(
                {
                    "library_id": result.get("ad_archive_id"),
                    "page_id": result.get("page_id"),
                    "advertiser": snap.get("page_name"),
                    "display_format": snap.get("display_format"),
                    "publisher_platform": result.get("publisher_platform"),
                    "start_date": result.get("start_date"),
                    "end_date": result.get("end_date"),
                    "body_text": body_text,
                    "image_urls": image_urls,
                    "video_urls": video_urls,
                }
            )
    return ads


def download_image(url: str, dest: Path) -> bool:
    if dest.exists():
        return True
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
        dest.write_bytes(data)
        return True
    except Exception as e:
        print(f"  ! download failed ({e}): {url[:80]}...")
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True)
    ap.add_argument("--country", default="JP")
    ap.add_argument(
        "--media-type",
        default="all",
        choices=["image", "video", "all"],
        help="all=全形式（既定。コピーで分析するので形式は不問） / image / video",
    )
    ap.add_argument("--limit", type=int, default=30, help="広告件数の上限")
    ap.add_argument(
        "--search-type",
        default="unordered",
        choices=["exact", "unordered"],
        help="exact=完全一致 / unordered=単語含有（既定）",
    )
    ap.add_argument(
        "--active-status",
        default="active",
        choices=["active", "all"],
        help="active=配信中のみ（既定。今出てる広告だけ）/ all=過去配信も含む",
    )
    ap.add_argument(
        "--targeted-only",
        action="store_true",
        default=True,
        help="国ターゲット指定がある広告のみ（既定）。海外ノイズ排除用。",
    )
    ap.add_argument(
        "--include-untargeted",
        dest="targeted_only",
        action="store_false",
        help="国ターゲット指定なしの広告も含める",
    )
    ap.add_argument(
        "--max-scrolls",
        type=int,
        default=40,
        help="スクロール最大回数（既定40）。limit到達か新規ヒット枯渇でも終了。",
    )
    ap.add_argument(
        "--with-images",
        action="store_true",
        default=False,
        help="画像をローカル保存する（既定OFF）。Analyze は body_text だけで動くので通常は不要。",
    )
    args = ap.parse_args()

    url = build_search_url(
        args.query,
        args.country,
        args.media_type,
        args.search_type,
        args.active_status,
        args.targeted_only,
    )
    today = datetime.now().strftime("%Y-%m-%d")
    safe_query = re.sub(r"[^\w\-]+", "_", args.query)[:40]
    out_dir = DATA_DIR / f"{today}_{safe_query}"
    out_dir.mkdir(parents=True, exist_ok=True)
    images_dir = out_dir / "images"
    if args.with_images:
        images_dir.mkdir(exist_ok=True)
    manifest_path = out_dir / "manifest.jsonl"

    print(f"[+] query        : {args.query}")
    print(f"[+] search_type  : {args.search_type}")
    print(f"[+] active_status: {args.active_status}")
    print(f"[+] URL          : {url}")
    print(f"[+] out_dir      : {out_dir}")
    print(f"[+] limit        : {args.limit}")

    # 蓄積バッファ
    all_edges: list[dict] = []
    xhr_responses: list[str] = []

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_DIR),
            headless=False,
            viewport={"width": 1440, "height": 900},
            locale="ja-JP",
        )
        page = ctx.new_page()

        # /api/graphql/ レスポンスをインターセプト
        graphql_count = {"total": 0, "with_search": 0}

        def on_response(resp):
            try:
                if "/api/graphql/" not in resp.url:
                    return
                if resp.status != 200:
                    return
                graphql_count["total"] += 1
                body = resp.text()
                if "search_results_connection" not in body:
                    return
                graphql_count["with_search"] += 1
                xhr_responses.append(body)
            except Exception as e:
                print(f"  ! on_response err: {e}")

        page.on("response", on_response)

        print("[+] navigating...")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)
        try:
            page.wait_for_selector("script[data-sjs]", timeout=30000)
        except Exception:
            pass
        page.wait_for_timeout(2500)

        # 初期SSRから edges を抽出
        html = page.content()
        initial = extract_search_results_from_html(html)
        if initial is None:
            print("[!] 初期SSRから search_results_connection が見つかりません。HTMLを保存。")
            (out_dir / "debug.html").write_text(html, encoding="utf-8")
            ctx.close()
            return 2
        total_hits = initial.get("count")
        print(f"[+] total hits   : {total_hits}")
        all_edges.extend(initial.get("edges", []) or [])
        print(f"[+] initial edges: {len(all_edges)}")

        # ページネーション: JS でページ末尾までスクロール → XHR を待つ
        prev_count = len(flatten_ads_from_edges(all_edges))
        stale_rounds = 0
        for i in range(args.max_scrolls):
            ads_so_far = flatten_ads_from_edges(all_edges)
            if len(ads_so_far) >= args.limit:
                print(f"[+] limit reached ({len(ads_so_far)} >= {args.limit})")
                break

            # Meta は intersection observer で末尾検知して追加ロードする
            # JS で末尾までスクロール → トップに戻して再度末尾、を試行
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1500)
            page.evaluate("window.scrollBy(0, -200)")
            page.wait_for_timeout(300)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(3500)

            # XHR レスポンスから新規 edges を取り込む
            while xhr_responses:
                body = xhr_responses.pop(0)
                edges = parse_graphql_response_body(body)
                all_edges.extend(edges)

            ads_now = flatten_ads_from_edges(all_edges)
            added = len(ads_now) - prev_count
            print(
                f"  [scroll {i + 1:>2}] +{added} ads (total {len(ads_now)})  "
                f"graphql_xhr={graphql_count['total']} with_search={graphql_count['with_search']}"
            )
            if added == 0:
                stale_rounds += 1
                if stale_rounds >= 4:
                    print("[+] 4スクロール連続で新規ヒットなし → 終了")
                    break
            else:
                stale_rounds = 0
            prev_count = len(ads_now)

        ctx.close()

    ads = flatten_ads_from_edges(all_edges)
    # 重複削除（library_id 基準）
    seen: set = set()
    deduped: list[dict] = []
    for a in ads:
        lid = a.get("library_id")
        if not lid or lid in seen:
            continue
        seen.add(lid)
        deduped.append(a)
    ads = deduped[: args.limit]
    print(f"[+] unique ads   : {len(ads)} (after dedupe & limit)")

    n_imgs_ok = 0
    with manifest_path.open("w", encoding="utf-8") as mf:
        for i, ad in enumerate(ads, 1):
            local_paths: list[str] = []
            if args.with_images:
                for j, img_url in enumerate(ad["image_urls"], 1):
                    fname = f"{ad['library_id']}_{j}.jpg"
                    dest = images_dir / fname
                    if download_image(img_url, dest):
                        local_paths.append(f"images/{fname}")
                        n_imgs_ok += 1
            record = {**ad, "image_local_paths": local_paths}
            mf.write(json.dumps(record, ensure_ascii=False) + "\n")
            body_preview = (ad.get("body_text") or "").replace("\n", " ")[:50]
            print(
                f"  [{i:>3}/{len(ads)}] {(ad['advertiser'] or '')[:24]:<24} "
                f"body='{body_preview}'"
            )

    if args.with_images:
        print(f"[+] done. ads={len(ads)} images_dl={n_imgs_ok}")
    else:
        print(f"[+] done. ads={len(ads)} (画像はDLしてない。--with-images で取得可)")
    print(f"[+] manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
