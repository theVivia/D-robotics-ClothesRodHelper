"""一键验证 v2 交付物：仿真、软件测试、链接、deck 页数、关键截图。"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKS = []


def run(name: str, cmd: list[str]) -> None:
    print(f"\n== {name} ==")
    r = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    tail = (r.stdout or "").strip().splitlines()[-4:]
    print("\n".join(tail))
    if r.returncode != 0:
        print(r.stderr[-800:])
    CHECKS.append((name, r.returncode == 0))


def main() -> int:
    py = sys.executable
    run("sim-v2", [py, "sim-v2/run_all.py"])
    run("software_v2 tests", [py, "-m", "pytest", "software_v2", "-q"])
    run("links", [py, "assets/scripts/check_links.py"])

    pdf = ROOT / "deck-v2" / "衣序-HangFlow-DDC2026.pdf"
    try:
        import pymupdf
        pages = len(pymupdf.open(pdf))
    except Exception:
        pages = 0
    print(f"\n== deck ==\n{pdf.name}: {pages} pages")
    CHECKS.append(("deck 10 pages", pages == 10))

    shots = [
        "app-v2/.verify/390x844-default.png",
        "app-v2/.verify/390x844-equal10.png",
    ]
    ok = all((ROOT / s).exists() for s in shots)
    print(f"\n== screenshots ==\n{ok}: {', '.join(shots)}")
    CHECKS.append(("app screenshots", ok))

    print("\n== summary ==")
    for name, passed in CHECKS:
        print(("PASS " if passed else "FAIL ") + name)
    return 0 if all(p for _, p in CHECKS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
