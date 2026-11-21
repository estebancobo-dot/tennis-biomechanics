"""P0.5a (15-11, #305): builds the new application's interface (ui/, React + TypeScript + Vite) into
src/tennisbio/app/p0/index.html (one self-contained file, in the repository: the PC has no Node) and writes the
fingerprint of its sources next to it (huella.txt), so a test can tell when the built page is older than its code.

    python scripts/construir_ui.py           (in Claude's cloud, which has Node)
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "ui"
OUT = ROOT / "src" / "tennisbio" / "app" / "p0"
SOURCES = ("index.html", "package.json", "package-lock.json", "tsconfig.json", "vite.config.ts", "tailwind.config.js",
           "postcss.config.js")


def fingerprint(ui: Path = UI) -> str:
    h = hashlib.sha256()
    # 21-11: by the posix name (Windows sorts paths without case: the PC saw another fingerprint of the same sources)
    files = [ui / f for f in SOURCES] + sorted((p for p in (ui / "src").rglob("*") if p.is_file()),
                                               key=lambda p: p.relative_to(ui).as_posix())
    for f in files:
        h.update(f.relative_to(ui).as_posix().encode() + b"\0" + f.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return h.hexdigest()


def main() -> int:
    subprocess.run(["npm", "ci", "--no-audit", "--no-fund"], cwd=UI, check=True)
    subprocess.run(["npm", "run", "build"], cwd=UI, check=True)
    (OUT / "huella.txt").write_text(fingerprint() + "\n", encoding="utf-8")
    print("hecho:", OUT / "index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
