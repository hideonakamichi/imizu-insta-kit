#!/usr/bin/env python3
"""check_brand.py の回帰テスト（実際の YAML を一時ファイルに書いて check() に読ませる）

    python3 .claude/skills/shared/scripts/check_brand_selftest.py
"""
import copy
import importlib.util
import sys
import tempfile
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("check_brand", HERE / "check_brand.py")
cb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cb)

failures = 0
GOOD = {
    "account": {"handle": "@my_account", "name": "机ラボ", "purpose": "在宅ワークの机まわりを整える情報発信", "site_url": ""},
    "audience": {"who": "在宅で働いていて机が片づかない人", "pains": ["物が多い", "配線が乱れる"], "vision": "v"},
    "offer": {"enabled": True, "name": "机ラボの講座", "cta_line": "続きはプロフィールから（無料）"},
    "tone": {"voice": "落ち着いた、ですます調", "policy": ["煽らない"], "ng_words": ["今すぐ"]},
    "strategy_axes": [{"key": "how-to", "label": "手順", "description": "d", "keywords": ["手順"]}],
    "content_sources": {"markdown_dir": "content/sources", "html": {"enabled": False}},
    "hashtags": {"core": ["#在宅ワーク"], "wide": ["#デスク周り"]},
    "design": {"palette": {"bg": "#FAF7F2", "text": "#1F2A44", "accent": "#5B8DB8"}},
}


def problems_for(data) -> list:
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True)
    try:
        return cb.check(Path(f.name))
    finally:
        Path(f.name).unlink()


def expect(name, mutate, should_pass=False):
    global failures
    data = copy.deepcopy(GOOD)
    mutate(data)
    probs = problems_for(data)
    ok = (not probs) == should_pass
    failures += not ok
    print(f"[{'ok' if ok else 'NG'}] {name} → {'合格' if not probs else '拒否: ' + probs[0][:50]}")


def setv(path, value):
    def f(d):
        for k in path[:-1]:
            d = d[k]
        d[path[-1]] = value
    return f


expect("設定済みの例は合格する", lambda d: None, should_pass=True)
expect("値の一部に全角カッコがあるだけなら合格（誘導文の「（無料）」）", lambda d: None, should_pass=True)
expect("雛形のプレースホルダー", setv(("account", "name"), "（アカウント名）"))
expect("雛形のハンドル @your_account", setv(("account", "handle"), "@your_account"))
expect("ハッシュタグの雛形 #（軸タグ1）", setv(("hashtags", "core"), ["#（軸タグ1）"]))
expect("空白だけの文字列", setv(("account", "purpose"), "   "))
expect("リストの要素が null", setv(("audience", "pains"), [None]))
expect("リストであるべき所が false", setv(("tone", "policy"), False))
expect("色が hex でない", setv(("design", "palette", "accent"), "blue"))
expect('html.enabled が文字列の "false"', setv(("content_sources", "html", "enabled"), "false"))
expect('offer.enabled が文字列の "false"', setv(("offer", "enabled"), "false"))
expect("テーマ軸の key が日本語", setv(("strategy_axes",), [{"key": "やり方"}]))
expect("ハンドルに @ が無い", setv(("account", "handle"), "my_account"))
expect("offer が有効なのに誘導文が空", setv(("offer", "cta_line"), ""))
expect("offer が無効なら誘導文は空でよい", lambda d: d["offer"].update({"enabled": False, "cta_line": ""}), should_pass=True)
expect("offer が無効なら雛形が残っていてもよい", lambda d: d["offer"].update({"enabled": False, "name": "（商品・サービス・サイト名）", "cta_line": "（18文字以内の控えめな誘導文）"}), should_pass=True)

# 配布時の雛形そのものが拒否されること（これが通ると、受け取ったまま投稿できてしまう）
template = HERE.parents[2].parent / "config" / "brand.yaml"
if template.exists() and "（アカウント名）" in template.read_text(encoding="utf-8"):
    ok = bool(cb.check(template))
    failures += not ok
    print(f"[{'ok' if ok else 'NG'}] 同梱の config/brand.yaml（雛形のまま）→ {'拒否' if ok else '合格してしまった'}")

print()
if failures:
    print(f"{failures} 件 失敗")
    sys.exit(1)
print("チェックはすべて期待どおり")
