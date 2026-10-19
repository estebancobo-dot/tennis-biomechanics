"""Check the register of user requests (docs/peticiones_usuario.md) and list what is not done.

    uv run python scripts/check_requests.py            # errors → exit code 1
    uv run python scripts/check_requests.py --md out.md

Fails when a row has no valid status, a HECHO row has no evidence or cites code that does not exist, a
row that is not done does not say what is missing, or the counts at the top do not match the rows.
Always prints first every request that is not done (PARCIAL or FALTA)."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tennisbio import requests_check as R  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--register", type=Path, default=R.REGISTER)
    ap.add_argument("--md", type=Path, help="write the list of unfinished requests here (Markdown)")
    a = ap.parse_args(argv)
    rows = R.parse(a.register)
    if not rows:
        print(f"ERROR: no hay filas en {a.register}")
        return 1
    md = R.pending_markdown(rows)
    print(md)
    if a.md:
        a.md.write_text(md, encoding="utf-8")
    errs = R.problems(rows) + R.header_problems(a.register, rows)
    for e in errs:
        print(f"ERROR: {e}")
    print(f"{len(rows)} filas · {len(errs)} errores en el registro")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
