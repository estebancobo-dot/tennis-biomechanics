"""Moves the analysed matches into the library (docs/almacenamiento.md, block 4) and switches it on.

    uv run python scripts/migrate_library.py

Copies (never moves or deletes) <output>/<id>/ into biblioteca/partidos/<año>/<partido>/ (etapas/ and
golpes/<jugadora>/), test runs into pruebas/, resumable (journal), verifies the copy and only then writes
biblioteca/datos/activa.json: from then on the pipeline, the report, the audit and the application use the
library (tennisbio.layout). The old folders stay until the user removes them. Result in
<output>/biblioteca_migracion.json (uploaded with the PC logs)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio import layout, library  # noqa: E402
from tennisbio.config import load_config  # noqa: E402


def main():
    cfg = load_config()
    out = Path((cfg.get("paths") or {}).get("output") or "output")
    root = library.library_root(cfg)
    print(f"Biblioteca: {root}\nDesde: {out}", flush=True)
    stats = library.migrate(out, root, log=lambda m: print(m, flush=True))
    on = layout.activate(root, stats)
    res = {"biblioteca": str(root), "activada": on, **{k: v for k, v in stats.items() if k != "avisos"},
           "avisos": stats.get("avisos", [])[:50]}
    (out / "biblioteca_migracion.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(("Biblioteca activada: los partidos se leen y escriben ya allí."
           if on else f"NO activada: {len(stats.get('problemas', []))} problemas en la copia (se sigue con output)."), flush=True)
    return 0 if on else 1


if __name__ == "__main__":
    sys.exit(main())
