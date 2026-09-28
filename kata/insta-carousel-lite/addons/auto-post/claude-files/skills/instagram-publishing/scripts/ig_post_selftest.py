#!/usr/bin/env python3
"""ig_post.py の安全装置の回帰テスト（Instagram には一切つながない。graph_request を差し替える）

無人で公開投稿をするスクリプトなので、「止まるべきときに止まる」ことを機械的に確かめる。
ig_post.py を触ったら必ず回す:
    python3 .claude/skills/instagram-publishing/scripts/ig_post_selftest.py
"""
import importlib.util
import json
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ig_post", HERE / "ig_post.py")
ig = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ig)
sys.path.insert(0, str(HERE.parents[1] / "shared" / "scripts"))
import check_brand  # noqa: E402

ig.RETRY_BACKOFF_S[:] = [0, 0, 0]
REAL_GRAPH_REQUEST = ig.graph_request  # ほかのテストが差し替える前の本物
ig.load_env = lambda root: None
_TMP = tempfile.TemporaryDirectory()
ig.UNCONFIRMED_FILE = Path(_TMP.name) / "logs" / "PUBLISH_UNCONFIRMED.json"
ig.PUBLISH_LOCK_FILE = Path(_TMP.name) / "logs" / "locks" / "ig_post.flock"  # 実際の logs/ を汚さない
failures = 0
CAPTION = "テスト用のキャプション\n\n#test"


def check(name, got, want):
    global failures
    ok = got == want
    failures += not ok
    print(f"[{'ok' if ok else 'NG'}] {name} → {got!r}" + ("" if ok else f" (期待: {want!r})"))


def run(handler, brand_problems=(), handle="my_account", use_real_graph_request=False):
    """handler(method, url, params) -> dict を graph_request として ig_post.main() を回す。"""
    calls = []

    def fake(method, url, params):
        calls.append((method, url.split("/v21.0/")[-1]))
        return handler(method, url, params)

    if not use_real_graph_request:
        ig.graph_request = fake
    check_brand.check = lambda *a, **k: list(brand_problems)
    check_brand.brand_handle = lambda *a, **k: handle
    import os
    os.environ.update({"IG_USER_ID": "111", "IG_ACCESS_TOKEN": "dummy", "GRAPH_API_VERSION": "v21.0"})
    with tempfile.TemporaryDirectory() as td:
        cap = Path(td) / "caption.txt"
        cap.write_text(CAPTION, encoding="utf-8")
        out = Path(td) / "result.json"
        sys.argv = ["ig_post.py", "--media-type", "image", "--media-url", "https://example.invalid/a.png",
                    "--caption-file", str(cap), "--out-json", str(out)]
        code = ig.main()
        return code, json.loads(out.read_text(encoding="utf-8")), calls


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+0000")


# 1) brand.yaml が未設定なら、API を1回も呼ばずに止まる
code, res, calls = run(lambda *a: {"id": "x"}, brand_problems=["account.name が雛形のままです"])
check("未設定の brand.yaml → exit 1", code, 1)
check("未設定の brand.yaml → API を呼ばない", calls, [])
check("未設定の brand.yaml → stage", res.get("stage"), "check_brand")

# 2) トークンのアカウントが brand.yaml のハンドルと違えば、コンテナを作らずに止まる
code, res, calls = run(lambda m, u, p: {"username": "someone_else"} if u.endswith("/me") else {"id": "x"})
check("別アカウントのトークン → exit 1", code, 1)
check("別アカウントのトークン → me 以外を呼ばない", [c[1] for c in calls], ["me"])

# 3) 正常系
def ok_handler(m, u, p):
    if u.endswith("/me"):
        return {"username": "My_Account"}  # 大文字小文字は区別しない
    if u.endswith("/media_publish"):
        return {"id": "MEDIA1"}
    if u.endswith("/media"):
        return {"id": "CONTAINER1"}
    return {"permalink": "https://www.instagram.com/p/xxx/"}
ig.UNCONFIRMED_FILE.unlink(missing_ok=True)
code, res, _ = run(ok_handler)
check("正常系 → exit 0", code, 0)
check("正常系 → media_id", res.get("media_id"), "MEDIA1")
state = json.loads(ig.UNCONFIRMED_FILE.read_text(encoding="utf-8"))
check("正常系 → 履歴に記録されるまで「公開確定・記録待ち」の状態が残る", state.get("state"), "published_not_recorded")
check("正常系 → 状態に media_id が入っている（記録の復旧に使える）", state.get("media_id"), "MEDIA1")
ig.UNCONFIRMED_FILE.unlink()

# ---- ここから下は「publish の応答が失敗だった」ときの3分岐 -------------------------------
# 共通のモック: me は一致、コンテナ作成は成功、publish は通信エラー。
# media 一覧は「公開前」と「公開後」で別の内容を返せる（GET /media の呼ばれた回数で切り替える）
def make_handler(container_status, before, after, status_error=False):
    state = {"media_gets": 0}

    def handler(m, u, p):
        if u.endswith("/me"):
            return {"username": "my_account"}
        if u.endswith("/media_publish"):
            return {"error": {"message": "network error", "code": "network"}}
        if m == "POST" and u.endswith("/media"):
            return {"id": "CONTAINER1"}
        if u.endswith("/CONTAINER1"):
            return {"error": {"message": "network error", "code": "network"}} if status_error else {"status_code": container_status}
        if m == "GET" and u.endswith("/media"):
            state["media_gets"] += 1
            return {"data": before if state["media_gets"] == 1 else after}
        return {"permalink": "https://www.instagram.com/p/mine/"}
    return handler


def run_clean(handler):
    ig.UNCONFIRMED_FILE.unlink(missing_ok=True)
    return run(handler)


OLD_SAME = {"id": "OLD", "caption": CAPTION}          # 過去の同文投稿（公開前からある）
OTHER = {"id": "OTHER", "caption": "別の投稿"}
MINE = {"id": "MINE", "caption": CAPTION}

# 4) コンテナは PUBLISHED・公開前に無かった同文の投稿がちょうど1件 → それを採用
code, res, _ = run_clean(make_handler("PUBLISHED", [OLD_SAME, OTHER], [MINE, OLD_SAME, OTHER]))
check("公開済み＋新しい同文が1件 → exit 0", code, 0)
check("公開済み＋新しい同文が1件 → 過去の同文(OLD)ではなく MINE", res.get("media_id"), "MINE")
check("確定できたら状態は「公開確定・記録待ち」", json.loads(ig.UNCONFIRMED_FILE.read_text(encoding="utf-8")).get("state"), "published_not_recorded")

# 5) 公開前からある同文の投稿しか見つからない → 取り違えない（exit 3）
code, res, _ = run_clean(make_handler("PUBLISHED", [OLD_SAME], [OLD_SAME]))
check("過去の同文投稿しかない → exit 3", code, 3)
check("過去の同文投稿しかない → media_id を捏造しない", res.get("media_id"), None)

# 6) 新しい同文の投稿が2件ある（手動投稿と重なった等）→ 一意に決められないので exit 3
code, res, _ = run_clean(make_handler("PUBLISHED", [OTHER], [MINE, {"id": "MINE2", "caption": CAPTION}, OTHER]))
check("新しい同文が2件 → exit 3", code, 3)

# 7) 状態確認も通信エラー → 「未公開」とは言い切れないので exit 3
code, res, _ = run_clean(make_handler("PUBLISHED", [OTHER], [MINE], status_error=True))
check("状態確認も失敗 → exit 3（通常の失敗に落とさない）", code, 3)
check("状態確認も失敗 → published_unconfirmed", res.get("published_unconfirmed"), True)

# 8) 未確定になったら印が残り、次の投稿は API を呼ばずに止まる
check("未確定の状態が残る", json.loads(ig.UNCONFIRMED_FILE.read_text(encoding="utf-8")).get("state"), "unconfirmed")
code, res, calls = run(ok_handler)
check("印があるあいだは投稿しない → exit 1", code, 1)
check("印があるあいだは API を呼ばない", calls, [])
check("印があるあいだは stage=unconfirmed_pending", res.get("stage"), "unconfirmed_pending")
ig.UNCONFIRMED_FILE.unlink()

# 9) コンテナが未公開だと確認できた → 通常の失敗（exit 1。印は残さない）
code, res, _ = run_clean(make_handler("FINISHED", [OTHER], [OTHER]))
check("未公開と確認できた失敗 → exit 1", code, 1)
check("未公開と確認できた失敗 → 印を残さない", ig.UNCONFIRMED_FILE.exists(), False)

# ---- 想定外の応答・途中で落ちた場合も、次の投稿が止まる ------------------------------
# urlopen の段階で差し替える（graph_request の JSON 解析・型の検証も通す）
import io
import urllib.request



class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def run_with_publish_body(body: bytes):
    """publish の HTTP 応答だけを body に差し替え、ほかは正常に返す。"""
    ig.UNCONFIRMED_FILE.unlink(missing_ok=True)

    def fake_urlopen(req, timeout=60):
        url = req.full_url
        if url.split("?")[0].endswith("/me"):
            return FakeResp(json.dumps({"username": "my_account"}).encode())
        if url.endswith("/media_publish"):
            return FakeResp(body)
        if req.get_method() == "POST" and url.endswith("/media"):
            return FakeResp(json.dumps({"id": "CONTAINER1"}).encode())
        if "/CONTAINER1" in url:
            return FakeResp(body)  # 状態照会も同じ壊れた応答
        return FakeResp(json.dumps({"data": []}).encode())

    orig_urlopen, orig_gr = urllib.request.urlopen, ig.graph_request
    urllib.request.urlopen = fake_urlopen
    ig.graph_request = REAL_GRAPH_REQUEST
    try:
        return run(None, use_real_graph_request=True)
    finally:
        urllib.request.urlopen = orig_urlopen
        ig.graph_request = orig_gr


for label, body in [("空の本文", b""), ("{}", b"{}"), ("null", b"null"), ("[]", b"[]"), ("HTML", b"<html>502</html>")]:
    code, res, _ = run_with_publish_body(body)
    check(f"publish の応答が {label} → 例外で落ちず exit 3", code, 3)
    check(f"publish の応答が {label} → 状態が残って次の投稿が止まる", ig.UNCONFIRMED_FILE.exists(), True)

# 公開リクエストの途中でプロセスが落ちた（例外）→ 状態 publishing が残る
def crash_on_publish(m, u, p):
    if u.endswith("/media_publish"):
        raise RuntimeError("公開リクエストの途中で落ちた")
    return published_handler_base(m, u, p)
def published_handler_base(m, u, p):
    if u.endswith("/me"):
        return {"username": "my_account"}
    if m == "POST" and u.endswith("/media"):
        return {"id": "CONTAINER1"}
    return {"data": []}
ig.UNCONFIRMED_FILE.unlink(missing_ok=True)
code, res, _ = run(crash_on_publish)
check("公開の途中で例外 → 落ちずに exit 3（未公開とは言い切れない）", code, 3)
check("公開の途中で例外 → 状態 unconfirmed が残る", json.loads(ig.UNCONFIRMED_FILE.read_text(encoding="utf-8")).get("state"), "unconfirmed")
check("公開の途中で例外 → 結果 JSON も書かれる", res.get("published_unconfirmed"), True)
ig.UNCONFIRMED_FILE.unlink()

# ---- 並行実行: ほかの投稿処理がロックを持っているあいだは、API を呼ばずに止まる -----------
held = ig.acquire_publish_lock()
check("1本目はロックを取れる", held is not None, True)
code, res, calls = run(ok_handler)
check("ロック中の2本目 → exit 1", code, 1)
check("ロック中の2本目 → stage=locked", res.get("stage"), "locked")
check("ロック中の2本目 → API を1回も呼ばない（公開要求が2件にならない）", calls, [])
check("ロック中の2本目 → 状態ファイルに触れない", ig.UNCONFIRMED_FILE.exists(), False)
held.close()
code, res, _ = run(ok_handler)
check("ロック解放後は投稿できる", code, 0)
ig.UNCONFIRMED_FILE.unlink()

# HTTP エラーの本文が null / 配列でも dict の error に整える
import urllib.error
def http_error_with(body: bytes):
    def fake_urlopen(req, timeout=60):
        raise urllib.error.HTTPError(req.full_url, 502, "Bad Gateway", {}, io.BytesIO(body))
    orig = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen
    try:
        return REAL_GRAPH_REQUEST("GET", "https://example.invalid/x", {})
    finally:
        urllib.request.urlopen = orig
for label, body in [("null", b"null"), ("[]", b"[]"), ("HTML", b"<html>502</html>"), ('{"error":null}', b'{"error":null}'), ('{"error":[]}', b'{"error":[]}')]:
    r = http_error_with(body)
    check(f"HTTP エラーの本文が {label} → error が dict の dict", isinstance(r, dict) and isinstance(r.get("error"), dict), True)

# ---- record_post.py: 同じ media_id を記録したときだけ「記録待ち」を解除する ---------------
spec_r = importlib.util.spec_from_file_location("record_post", HERE / "record_post.py")
rp = importlib.util.module_from_spec(spec_r)
spec_r.loader.exec_module(rp)
rp.PROJECT_ROOT = Path(_TMP.name)
rp.POSTED_LOG = Path(_TMP.name) / "logs" / "posted.jsonl"
STATE = Path(_TMP.name) / "logs" / "PUBLISH_UNCONFIRMED.json"


def record(media_id):
    sys.argv = ["record_post.py", "--pipeline", "reel", "--theme", "t", "--media-id", media_id]
    return rp.main()


STATE.parent.mkdir(parents=True, exist_ok=True)
STATE.write_text(json.dumps({"state": "published_not_recorded", "media_id": "M1"}), encoding="utf-8")
record("OTHER")
check("別の media_id の記録では解除しない", STATE.exists(), True)
record("M1")
check("同じ media_id を記録したら解除する", STATE.exists(), False)
n_before = len(rp.POSTED_LOG.read_text(encoding="utf-8").splitlines())
record("M1")
check("同じ media_id をもう一度記録しても行は増えない（復旧のやり直しで水増ししない）",
      len(rp.POSTED_LOG.read_text(encoding="utf-8").splitlines()), n_before)
STATE.write_text(json.dumps({"state": "unconfirmed", "creation_id": "C1"}), encoding="utf-8")
record("M1")
check("unconfirmed の状態は record_post.py では解除しない（人が確認して消す）", STATE.exists(), True)
STATE.unlink()

# 履歴の最終行が書き込みの途中で切れている → 追記せず、状態も消さない
rp.POSTED_LOG.write_text('{"media_id": "OLD1", "theme": "t"}\n{"media_id": "M9"', encoding="utf-8")
STATE.write_text(json.dumps({"state": "published_not_recorded", "media_id": "M9"}), encoding="utf-8")
code = record("M9")
check("壊れた履歴 → exit 1（追記しない）", code, 1)
check("壊れた履歴 → 状態ファイルを消さない（次の投稿は止まったまま）", STATE.exists(), True)
check("壊れた履歴 → 壊れた行に連結していない", rp.POSTED_LOG.read_text(encoding="utf-8").count("M9"), 1)
# 末尾に改行が無いだけの正常な履歴 → 改行を補って追記する
rp.POSTED_LOG.write_text('{"media_id": "OLD1", "theme": "t"}', encoding="utf-8")
code = record("M9")
check("末尾に改行が無い履歴 → 改行を補って記録（exit 0）", code, 0)
check("末尾に改行が無い履歴 → 2行とも有効な JSON", [json.loads(l)["media_id"] for l in rp.POSTED_LOG.read_text(encoding="utf-8").splitlines()], ["OLD1", "M9"])
check("記録を確かめてから状態を解除", STATE.exists(), False)

print()
if failures:
    print(f"{failures} 件 失敗")
    sys.exit(1)
print("チェックはすべて期待どおり")
