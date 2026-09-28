"""共有用パッケージのローカル診断。APIは呼び出さない。"""

import importlib.util
import os
import platform
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_env_keys() -> set[str]:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return set()
    keys = set()
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            if value.strip():
                keys.add(key.strip())
    return keys


def main() -> int:
    print(f"Python: {platform.python_version()} ({sys.executable})")
    failures = []
    if sys.version_info < (3, 10):
        failures.append("Python 3.10以上が必要")
    for module, package in [("patchright", "patchright"), ("numpy", "numpy"),
                            ("matplotlib", "matplotlib"), ("google.genai", "google-genai"),
                            ("openai", "openai")]:
        ok = importlib.util.find_spec(module) is not None
        print(f"{'OK' if ok else 'NG'} dependency: {package}")
        if not ok:
            failures.append(f"依存が未導入: {package}")
    keys = read_env_keys() | {key for key in ("GEMINI_API_KEY", "OPENAI_API_KEY", "VERCEL_TOKEN", "CTA_URL") if os.environ.get(key)}
    for key in ("GEMINI_API_KEY", "OPENAI_API_KEY"):
        print(f"{'OK' if key in keys else 'WARN'} env: {key}")
    print(f"{'OK' if shutil.which('node') else 'WARN'} optional: Node.js (Vercel公開用)")
    if failures:
        print("\n要対応:")
        for item in failures:
            print(f"- {item}")
        return 1
    print("\n基本環境は正常です。WARNは使う機能に応じて設定してください。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
