"""14-11: why Kaggle starts nothing. The account's real GPU quota (used, left, refresh) and the status of the last
versions of the «tennisbio-cola» notebook (each push is a version; are older ones still queued ahead of the new one?),
with Kaggle's failure message when there is one. Read only: nothing is launched or cancelled.

    python cloud/kaggle/diagnostico.py [--versiones 12]
"""
from __future__ import annotations

import argparse
import os
import sys

SLUG = "tennisbio-cola"


def hours(td) -> float:
    return round(td.total_seconds() / 3600, 2) if td is not None else -1.0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--versiones", type=int, default=12)
    a = ap.parse_args(argv)
    user = os.environ.get("KAGGLE_USERNAME", "").strip()
    from kaggle.api.kaggle_api_extended import KaggleApi
    from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest, ApiGetKernelSessionStatusRequest

    api = KaggleApi()
    api.authenticate()
    try:
        q = api.quota_view()
        g = q.gpu_quota
        print(f"cuota de GPU: usadas {hours(g.time_used)} h de {hours(g.total_time_allowed)} h; "
              f"se renueva {q.quota_refresh_time}")
    except Exception as e:  # noqa: BLE001 — say it, go on
        print(f"cuota de GPU: no se pudo leer ({type(e).__name__}: {e})")
    with api.build_kaggle_client() as kaggle:
        cli = kaggle.kernels.kernels_api_client
        r = ApiGetKernelRequest()
        r.user_name, r.kernel_slug = user, SLUG
        meta = cli.get_kernel(r).metadata
        cur = int(meta.current_version_number or 0)
        print(f"cuaderno {SLUG}: versión actual {cur}; GPU {meta.enable_gpu}; internet {meta.enable_internet}; "
              f"máquina {meta.machine_shape}; última ejecución {meta.last_run_time}")
        for v in range(cur, max(0, cur - a.versiones), -1):
            s = ApiGetKernelSessionStatusRequest()
            s.user_name, s.kernel_slug, s.version_label = user, SLUG, str(v)
            try:
                st = cli.get_kernel_session_status(s)
                print(f"  versión {v}: {st.status}" + (f" · {st.failure_message}" if st.failure_message else ""))
            except Exception as e:  # noqa: BLE001
                print(f"  versión {v}: sin estado ({type(e).__name__}: {str(e)[:120]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
