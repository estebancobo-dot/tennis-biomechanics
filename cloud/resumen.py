"""14-11: a match's manifest (one entry per stage) as short lines: each stage's time and summary, and its faults.

    python cloud/resumen.py nube-out/manifest.json
"""
import json
import sys
from pathlib import Path


def lines(manifest: dict, width: int = 400) -> list[str]:
    out = []
    for stage, rec in manifest.items():
        if not isinstance(rec, dict):
            continue
        summ = json.dumps(rec.get("summary") or {}, ensure_ascii=False)
        out.append(f"{stage} ({rec.get('seconds', '?')} s): {summ[:width]}")
        if rec.get("faults"):
            out.append(f"  fallos: {json.dumps(rec['faults'], ensure_ascii=False)[:width]}")
    return out


def main(path: str) -> int:
    f = Path(path)
    if not f.exists():
        print(f"sin {f}")
        return 1
    print("\n".join(lines(json.loads(f.read_text(encoding="utf-8")))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "manifest.json"))
