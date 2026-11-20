"""P0.5e (15-11): opens the new application's window (tennisbio.app.p0_ventana) connected to the cloud: the Modal volume
through its storage adapter (cloud/almacen.py), with the key 5_conectar_nube.bat saved (<base>\\secretos\\modal.env).
Outside the package, as scripts/subir_nube.py: the core never imports the cloud's code or Modal.

    uv run --extra app --with "modal>=1.0,<2" python scripts/aplicacion_nueva.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "cloud"), str(ROOT / "scripts")]

from subir_nube import read_key, secrets_file  # noqa: E402
from tennisbio.app import p0_ventana  # noqa: E402

VOLUME = "tennisbio-datos"


def storage(out_root: Path):
    """The Modal volume as the application's storage, or (None, why)."""
    key = read_key(secrets_file(out_root))
    if not key:
        return None, "falta la clave de Modal: doble clic en 5_conectar_nube.bat"
    os.environ.update(key)
    try:
        import modal
    except ImportError:  # esperado: launched without the Modal client; every button says it
        return None, "falta el cliente de Modal (se instala con 6_aplicacion_nueva.bat)"
    import almacen
    return almacen.ModalStorage(modal.Volume.from_name(VOLUME), VOLUME), ""


def main() -> int:
    out_root = p0_ventana.output_root()
    store, why = storage(out_root)
    return p0_ventana.main(store, why, out_root)


if __name__ == "__main__":
    raise SystemExit(main())
