#!/usr/bin/env python3
"""
ig_post.py - Instagram API 投稿（新規スクリプト）

Phase 0のセットアップで、このプロジェクトのInstagramアカウントは「Instagram業務用ログイン」
（Facebookページ不要、graph.instagram.com を直接使う方式）で連携することが確定したため、
Facebookページ経由（graph.facebook.com）ではなくこちらのエンドポイントを使う。

フロー自体はどちらの方式でも変わらない（コンテナ作成→(reelsのみ)ポーリング→publish）。

# 画像投稿
POST /{ig-user-id}/media?image_url=<公開URL>&caption=<本文>
  -> creation_id
POST /{ig-user-id}/media_publish?creation_id=<id>
  -> media_id

# リール投稿
POST /{ig-user-id}/media?media_type=REELS&video_url=<公開URL>&caption=<本文>
  -> creation_id
GET  /{creation_id}?fields=status_code   (FINISHEDまでポーリング)
POST /{ig-user-id}/media_publish?creation_id=<id>
  -> media_id

# カルーセル投稿（画像2〜10枚）
POST /{ig-user-id}/media?image_url=<公開URL>&is_carousel_item=true   (枚数分繰り返す)
  -> item creation_id ×N
POST /{ig-user-id}/media?media_type=CAROUSEL&children=<id1>,<id2>,...&caption=<本文>
  -> carousel creation_id
POST /{ig-user-id}/media_publish?creation_id=<id>
  -> media_id

使い方:
  python3 ig_post.py \
    --media-type image \
    --media-url https://.../banner.png \
    --caption-file OUTPUT_DIR/caption.txt \
    --out-json OUTPUT_DIR/post_result.json

  python3 ig_post.py \
    --media-type reels \
    --media-url https://.../reel.mp4 \
    --caption-file OUTPUT_DIR/caption.txt \
    --out-json OUTPUT_DIR/post_result.json

  python3 ig_post.py \
    --media-type carousel \
    --media-urls https://.../slide_1.png https://.../slide_2.png https://.../slide_3.png \
    --caption-file OUTPUT_DIR/caption.txt \
    --out-json OUTPUT_DIR/post_result.json

終了コード:
  0 = 成功（post_result.jsonにmedia_id/permalinkを書き出す）
  1 = 失敗（トークン失効・APIエラー等。post_result.jsonにerrorを書き出す）

env（プロジェクトルートの .env から読む）:
  IG_USER_ID, IG_ACCESS_TOKEN, GRAPH_API_VERSION（既定 v21.0）
"""
import argparse
import json
from datetime import datetime, timezone
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[3]

MAX_RETRIES = 3
RETRY_BACKOFF_S = [5, 15, 45]
POLL_INTERVAL_S = 10
POLL_TIMEOUT_S = 600  # config/loop-limits.yaml の ig_container_polling と合わせる


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


def graph_request(method: str, url: str, params: dict) -> dict:
    """Graph APIを叩く。エラー時は {"error": {...}} を含むレスポンスをそのままdictで返す。"""
    if method == "GET":
        full_url = f"{url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(full_url, method="GET")
    else:
        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(url, data=data, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return {"error": {"message": f"応答がJSONではありません: {body[:120]!r}", "code": "bad_response"}}
        if not isinstance(data, dict) or ("error" in data and not isinstance(data["error"], dict)):
            # 空・配列・null、error が dict でない、など。呼び出し側は「dict で、error があれば dict」を前提にしている
            return {"error": {"message": f"応答の形が想定外です: {body[:120]!r}", "code": "bad_response"}}
        return data
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict) and isinstance(data.get("error"), dict):
            return data
        return {"error": {"message": f"HTTP {e.code}: {body[:200]}", "code": e.code}}
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
        # 通信の失敗（タイムアウト・DNS・回線断）。HTTPError だけを捕まえていた頃は、ここで例外のまま
        # スクリプトが落ち、リトライも失敗通知の整形も行われなかった。ほかのエラーと同じ形にして返す
        return {"error": {"message": f"network error: {type(e).__name__}: {e}", "code": "network"}}


def with_retries(fn, *args, **kwargs) -> dict:
    last = None
    for attempt, backoff in enumerate([0] + RETRY_BACKOFF_S, start=1):
        if backoff:
            time.sleep(backoff)
        result = fn(*args, **kwargs)
        if "error" not in result:
            return result
        last = result
        code = result.get("error", {}).get("code")
        # トークン失効(190)や権限エラーはリトライしても無駄なので即終了
        if code == 190:
            return result
        print(f"[retry {attempt}/{MAX_RETRIES + 1}] error: {result['error']}", file=sys.stderr)
    return last


def create_container(base_url: str, ig_user_id: str, token: str, api_version: str,
                      media_type: str, media_url: str, caption: str) -> dict:
    url = f"{base_url}/{api_version}/{ig_user_id}/media"
    params = {"caption": caption, "access_token": token}
    if media_type == "reels":
        params["media_type"] = "REELS"
        params["video_url"] = media_url
    else:
        params["image_url"] = media_url
    return with_retries(graph_request, "POST", url, params)


def create_carousel_item(base_url: str, ig_user_id: str, token: str, api_version: str,
                          image_url: str) -> dict:
    """カルーセルの子コンテナ（画像1枚分）を作成する。captionは親にのみ付ける。"""
    url = f"{base_url}/{api_version}/{ig_user_id}/media"
    params = {"image_url": image_url, "is_carousel_item": "true", "access_token": token}
    return with_retries(graph_request, "POST", url, params)


def create_carousel_container(base_url: str, ig_user_id: str, token: str, api_version: str,
                               children_ids: list[str], caption: str) -> dict:
    url = f"{base_url}/{api_version}/{ig_user_id}/media"
    params = {
        "media_type": "CAROUSEL",
        "children": ",".join(children_ids),
        "caption": caption,
        "access_token": token,
    }
    return with_retries(graph_request, "POST", url, params)


def poll_status(base_url: str, creation_id: str, token: str, api_version: str) -> dict:
    url = f"{base_url}/{api_version}/{creation_id}"
    deadline = time.time() + POLL_TIMEOUT_S
    while time.time() < deadline:
        result = graph_request("GET", url, {"fields": "status_code", "access_token": token})
        if "error" in result:
            return result
        status = result.get("status_code")
        print(f"[poll] status_code={status}")
        if status == "FINISHED":
            return result
        if status == "ERROR":
            return {"error": {"message": "media processing failed (status_code=ERROR)"}}
        time.sleep(POLL_INTERVAL_S)
    return {"error": {"message": f"polling timed out after {POLL_TIMEOUT_S}s"}}


# 公開まわりの状態ファイル。**これがあるあいだ、ig_post.py も bin/run-agent.sh も新しい投稿をしない。**
# 公開リクエストの**前**に書き、「未公開だと確認できた」か「履歴（posted.jsonl）に記録できた」ときだけ消す。
# 途中でプロセスが落ちても・想定外の応答で例外になっても、次の投稿が止まるので二重投稿にならない。
#   state: publishing              公開リクエスト中（これが残っていたら、途中で落ちた）
#          unconfirmed             公開されたかもしれないが、どの投稿か特定できなかった
#          published_not_recorded  公開確定。履歴への記録がまだ（record_post.py が記録したら消す）
UNCONFIRMED_FILE = PROJECT_ROOT / "logs" / "PUBLISH_UNCONFIRMED.json"

# ig_post.py 自身の排他ロック。bin/run-agent.sh の投稿ロック（logs/locks/posting.flock）は、このスクリプトを
# 手で直接実行したときには効かない。状態ファイルの確認から公開結果の保存までをこのロックの中で行い、
# 並行実行で「両方が確認を通過して2件公開する」「相手の未確認状態を上書きして消す」を防ぐ。
# run-agent.sh のロックとは別のファイルなので、その中から呼ばれても二重取得で止まらない。
# record_post.py も、状態ファイルを消すときに同じロックを取る
PUBLISH_LOCK_FILE = PROJECT_ROOT / "logs" / "locks" / "ig_post.flock"


def acquire_publish_lock(lock_file: Path | None = None):
    """取れたらファイルオブジェクト（閉じるまで保持）、ほかの投稿処理が実行中なら None。"""
    import fcntl
    lock_file = lock_file or PUBLISH_LOCK_FILE
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    f = open(lock_file, "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        f.close()
        return None
    return f


WHAT_TO_DO = {
    "publishing": [
        "公開リクエストの途中で処理が止まった。公開されたかどうかは分からない",
        "1. Instagram でこの投稿が公開されているか確認する（caption_head の文面で探す）",
        "2. 公開されていた → record_post.py で logs/posted.jsonl に記録する（--theme は output_dir の carousel_spec.json / reel_meta.json の theme を一字一句そのまま。--media-id と --permalink は Instagram で確認した値）",
        "3. 公開されていなかった → 何も記録しない（同じネタは次回以降また選ばれる）",
        "4. どちらの場合も、最後にこのファイルを削除する。削除するまで投稿パイプラインは止まったままになる",
    ],
    "published_not_recorded": [
        "Instagram への公開は成功している（media_id と permalink はこのファイルにある）。履歴への記録がまだ",
        "1. record_post.py で logs/posted.jsonl に記録する（--theme は output_dir の carousel_spec.json / reel_meta.json の theme を一字一句そのまま。--media-id と --permalink はこのファイルの値）",
        "2. 同じ media_id で記録すると、このファイルは record_post.py が自動で削除する",
    ],
}
WHAT_TO_DO["unconfirmed"] = ["公開された可能性が高いが、どの投稿かを機械的に特定できなかった"] + WHAT_TO_DO["publishing"][1:]


def write_state(state: str, **fields) -> None:
    UNCONFIRMED_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {"state": state, "at": datetime.now(timezone.utc).isoformat(), **fields, "what_to_do": WHAT_TO_DO[state]}
    tmp = UNCONFIRMED_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, UNCONFIRMED_FILE)


def recent_media_ids(base_url: str, ig_user_id: str, token: str, api_version: str) -> set | None:
    """公開前の時点でアカウントにある直近のメディアID。取得できなければ None。"""
    r = graph_request("GET", f"{base_url}/{api_version}/{ig_user_id}/media",
                      {"fields": "id", "limit": 25, "access_token": token})
    if "error" in r or not isinstance(r.get("data"), list):
        return None
    return {m.get("id") for m in r["data"]}


def publish(base_url: str, ig_user_id: str, token: str, api_version: str, creation_id: str,
            caption: str = "", known_ids: set | None = None) -> dict:
    """media_publish を呼ぶ。戻り値は3通り:
      {"id": ...}                                   公開確定
      {"error": ...}                                未公開だと確認できた失敗（再試行してよい）
      {"error": ..., "published_unconfirmed": True}  公開されたかもしれない（**再投稿してはいけない**）
    """
    url = f"{base_url}/{api_version}/{ig_user_id}/media_publish"
    params = {"creation_id": creation_id, "access_token": token}
    result = with_retries(graph_request, "POST", url, params)
    if "error" not in result and result.get("id"):
        return result
    if "error" not in result:  # 成功応答なのに id が無い。公開されたかどうかを下で確かめる
        result = {"error": {"message": f"publish の応答に id がありません: {str(result)[:120]}", "code": "bad_response"}}
    # publish の通信がタイムアウトした場合、リクエスト自体はInstagram側で成功していることがある
    # （同じコンテナは二度 publish できないので、上の再試行で二重投稿にはならない）。
    # 失敗扱いにすると、次の起動で同じネタがもう一度投稿される。コンテナの状態を確認する
    status = with_retries(graph_request, "GET", f"{base_url}/{api_version}/{creation_id}",
                          {"fields": "status_code", "access_token": token})
    code = status.get("status_code")
    if "error" not in status and code in ("FINISHED", "IN_PROGRESS", "ERROR", "EXPIRED"):
        return result  # 未公開だと確認できた。通常の失敗
    unconfirmed = {"error": result["error"], "published_unconfirmed": True}
    if code != "PUBLISHED":
        return unconfirmed  # 状態を確認できなかった（通信失敗・想定外の応答）。未公開とは言い切れない
    # 公開済み。今回の投稿は「公開前には無かったメディア」のうち、キャプションが完全一致するもの。
    # それが**ちょうど1件**のときだけ確定する。「アカウントの最新1件」や「同じ文面の投稿」を今回の投稿と
    # みなすと、別のパイプライン・手動投稿・過去の同文投稿のID・URLを今回のネタとして記録してしまう
    if known_ids is None or not caption.strip():
        return unconfirmed
    recent = graph_request("GET", f"{base_url}/{api_version}/{ig_user_id}/media",
                           {"fields": "id,caption", "limit": 25, "access_token": token})
    if "error" in recent or not isinstance(recent.get("data"), list):
        return unconfirmed
    new = [m for m in recent["data"]
           if m.get("id") and m["id"] not in known_ids and (m.get("caption") or "").strip() == caption.strip()]
    if len(new) == 1:
        print("[info] publish の応答は失敗だったが、公開前に無かった同文の投稿を1件だけ特定した", file=sys.stderr)
        return {"id": new[0]["id"]}
    return unconfirmed


def fetch_permalink(base_url: str, media_id: str, token: str, api_version: str) -> str | None:
    url = f"{base_url}/{api_version}/{media_id}"
    result = graph_request("GET", url, {"fields": "permalink", "access_token": token})
    return result.get("permalink")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--media-type", choices=["image", "reels", "carousel"], required=True)
    ap.add_argument("--media-url", help="R2等でホストした公開URL（image/reels用）")
    ap.add_argument("--media-urls", nargs="+", help="カルーセル用の公開URL（表示順に2〜10個）")
    ap.add_argument("--caption-file", required=True)
    ap.add_argument("--out-json", required=True)
    args = ap.parse_args()

    if args.media_type == "carousel":
        if not args.media_urls or not (2 <= len(args.media_urls) <= 10):
            ap.error("carousel は --media-urls で公開URLを2〜10個指定してください")
    elif not args.media_url:
        ap.error(f"{args.media_type} は --media-url が必要です")

    load_env(PROJECT_ROOT)
    ig_user_id = os.environ.get("IG_USER_ID", "").strip()
    token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
    api_version = os.environ.get("GRAPH_API_VERSION", "v21.0").strip()
    base_url = "https://graph.instagram.com"

    out_path = Path(args.out_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not ig_user_id or not token:
        result = {"ok": False, "error": "IG_USER_ID / IG_ACCESS_TOKEN が未設定です"}
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"[!] {result['error']}", file=sys.stderr)
        return 1

    # --- 排他: ほかの投稿処理（定期実行・手動実行）が動いているあいだは何もしない ---
    lock = acquire_publish_lock()
    if lock is None:
        result = {"ok": False, "stage": "locked", "error": "ほかの投稿処理が実行中です。終わってからやり直してください"}
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"[!] {result['error']}", file=sys.stderr)
        return 1
    try:
        return _post(args, out_path, base_url, ig_user_id, token, api_version)
    finally:
        lock.close()


def _post(args, out_path: Path, base_url: str, ig_user_id: str, token: str, api_version: str) -> int:
    """ロックを持った状態で呼ばれる本体（状態の確認 → コンテナ作成 → 公開 → 結果の保存）。"""
    # --- 安全装置: 前回の投稿の結果が未確認のあいだは、何も投稿しない ---
    if UNCONFIRMED_FILE.exists():
        result = {"ok": False, "stage": "unconfirmed_pending",
                  "error": f"前回の投稿の後始末が終わっていません。{UNCONFIRMED_FILE} の what_to_do に従って解除してください"}
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"[!] {result['error']}", file=sys.stderr)
        return 1

    # --- 安全装置: 未設定・他人の設定のまま投稿しない（AIへの指示文ではなく、ここで機械的に止める） ---
    sys.path.insert(0, str(PROJECT_ROOT / ".claude" / "skills" / "shared" / "scripts"))
    import check_brand
    problems = check_brand.check()
    if problems:
        result = {"ok": False, "stage": "check_brand", "error": "config/brand.yaml の設定が終わっていません: " + " / ".join(problems[:5])}
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"[!] {result['error']}", file=sys.stderr)
        return 1
    # 投稿先のアカウントが brand.yaml の account.handle と同じかを確かめる。.env を別アカウントのものと
    # 取り違えると、Aのブランドで作った投稿がBのアカウントに公開される
    me = with_retries(graph_request, "GET", f"{base_url}/{api_version}/me",
                      {"fields": "username", "access_token": token})
    username = str(me.get("username") or "").strip().lower()
    expected = check_brand.brand_handle()
    if "error" in me or not username or username != expected:
        detail = me.get("error") if "error" in me else f"トークンのアカウントは @{username}、brand.yaml は @{expected}"
        result = {"ok": False, "stage": "verify_account", "error": f"投稿先アカウントを確認できないため中止: {detail}"}
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"[!] {result['error']}", file=sys.stderr)
        return 1

    caption = Path(args.caption_file).read_text(encoding="utf-8").strip()

    if args.media_type == "carousel":
        # 子コンテナが1つでも失敗したら親を作らず中止（「投稿しない」原則）
        children_ids = []
        for i, url in enumerate(args.media_urls, start=1):
            print(f"[+] creating carousel item {i}/{len(args.media_urls)}")
            item = create_carousel_item(base_url, ig_user_id, token, api_version, url)
            if "error" in item:
                result = {"ok": False, "stage": f"create_carousel_item_{i}", "error": item["error"],
                          "children_ids": children_ids}
                out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
                print(f"[!] carousel item {i} failed: {item['error']}", file=sys.stderr)
                return 1
            children_ids.append(item["id"])
            print(f"[ok] item creation_id={item['id']}")

        print(f"[+] creating carousel container ({len(children_ids)} children)")
        container = create_carousel_container(base_url, ig_user_id, token, api_version, children_ids, caption)
    else:
        print(f"[+] creating container: media_type={args.media_type}")
        container = create_container(base_url, ig_user_id, token, api_version, args.media_type, args.media_url, caption)

    if "error" in container:
        result = {"ok": False, "stage": "create_container", "error": container["error"]}
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"[!] create_container failed: {container['error']}", file=sys.stderr)
        return 1
    creation_id = container["id"]
    print(f"[ok] creation_id={creation_id}")

    if args.media_type == "reels":
        print("[+] polling container status (video processing)...")
        status_result = poll_status(base_url, creation_id, token, api_version)
        if "error" in status_result:
            result = {"ok": False, "stage": "poll_status", "error": status_result["error"], "creation_id": creation_id}
            out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
            print(f"[!] poll_status failed: {status_result['error']}", file=sys.stderr)
            return 1

    print("[+] publishing...")
    known_ids = recent_media_ids(base_url, ig_user_id, token, api_version)  # 公開前の時点の一覧（照合用）
    state_fields = {"creation_id": creation_id, "media_type": args.media_type,
                    "caption_head": caption[:80], "output_dir": str(out_path.parent)}
    write_state("publishing", **state_fields)  # ここから先で何が起きても、次の投稿は止まる
    try:
        publish_result = publish(base_url, ig_user_id, token, api_version, creation_id, caption, known_ids)
    except Exception as e:  # noqa: BLE001  公開リクエストを出した後かもしれない。未公開とは言い切れない
        publish_result = {"error": {"message": f"publish 中の想定外の例外: {type(e).__name__}: {e}", "code": "exception"},
                          "published_unconfirmed": True}
    if publish_result.get("published_unconfirmed"):
        # 公開されたかもしれないが、どの投稿かを確定できなかった。通常の失敗と区別する（exit 3）。
        # 呼び出し側は**再投稿してはいけない**。履歴（posted.jsonl）に仮の記録を書く方式にしないのは、
        # ネタが少ないと theme-picker が使用済みのネタを再利用しうるため
        write_state("unconfirmed", **state_fields)
        result = {"ok": False, "stage": "publish", "published_unconfirmed": True,
                  "error": publish_result["error"], "creation_id": creation_id}
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print("[!] 公開済みの可能性が高いが、投稿を特定できなかった。再投稿せず、Instagram を確認すること", file=sys.stderr)
        return 3
    if "error" in publish_result:
        # 未公開だと確認できた失敗。状態を消してよい（再試行しても二重投稿にならない）
        UNCONFIRMED_FILE.unlink(missing_ok=True)
        result = {"ok": False, "stage": "publish", "error": publish_result["error"], "creation_id": creation_id}
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"[!] publish failed: {publish_result['error']}", file=sys.stderr)
        return 1
    media_id = publish_result["id"]
    print(f"[ok] media_id={media_id}")

    # permalink が取れなくても公開成功は変わらない（取得の失敗で成功を失わない）
    try:
        permalink = fetch_permalink(base_url, media_id, token, api_version)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] permalink の取得に失敗: {e}", file=sys.stderr)
        permalink = None

    # 公開確定。履歴に記録されるまで状態を残す（record_post.py が同じ media_id を記録したら消す）。
    # 記録の前に呼び出し側が落ちても、次の投稿は止まり、このファイルから記録を復旧できる
    write_state("published_not_recorded", media_id=media_id, permalink=permalink or "", **state_fields)
    result = {"ok": True, "media_id": media_id, "permalink": permalink, "creation_id": creation_id}
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"[done] {json.dumps(result, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
