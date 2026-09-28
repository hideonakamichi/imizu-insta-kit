"""ローカル診断。APIは呼び出さない。"""

import importlib.util
import os
import platform
import sys
from pathlib import Path

# Windows の Python は出力を cp932 で書くため、Claude Code（Git Bash）で読むと日本語が化ける。UTF-8 に固定する
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

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
    for module, package in [("numpy", "numpy"), ("matplotlib", "matplotlib"),
                            ("google.genai", "google-genai")]:
        ok = importlib.util.find_spec(module) is not None
        print(f"{'OK' if ok else 'NG'} dependency: {package}")
        if not ok:
            failures.append(f"依存が未導入: {package}")
    keys = read_env_keys() | ({"GEMINI_API_KEY"} if os.environ.get("GEMINI_API_KEY") else set())
    print(f"{'OK' if 'GEMINI_API_KEY' in keys else 'WARN'} env: GEMINI_API_KEY")
    if failures:
        print("\n要対応:")
        for item in failures:
            print(f"- {item}")
        return 1
    print("\n基本環境は正常です。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
