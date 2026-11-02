"""Honest status of every user request from an audit (see tennisbio.real_status).

    uv run python scripts/real_status.py <auditoria.json> [--out docs/estado_real_peticiones.md]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio.real_status import LEVELS, ROOT, level, packages, registry, render  # noqa: E402,F401


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audit")
    ap.add_argument("--out", default=str(ROOT / "docs" / "estado_real_peticiones.md"))
    a = ap.parse_args()
    md, counts = render(json.loads(Path(a.audit).read_text(encoding="utf-8")))
    Path(a.out).write_text(md, encoding="utf-8")
    print(json.dumps(counts, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
