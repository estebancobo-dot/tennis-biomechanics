"""N0 (13-11, #273): runs the deployed app's functions (cloud/modal_app.py, deployed first) from GitHub Actions.

    python cloud/lanzar.py comprobar                 waits and prints what the cloud sees (a few minutes)
    python cloud/lanzar.py f3set --tag nube          starts the F3Set run in the cloud and returns at once
"""
import argparse
import json

import modal

APP = "tennisbio"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("accion", choices=("ping", "comprobar", "f3set", "partidos", "prueba", "diagnostico"))
    ap.add_argument("--partidos", default="", help="partidos: sus id separados por comas (un contenedor cada uno)")
    ap.add_argument("--tag", default="nube")
    ap.add_argument("--max-points", type=int, default=0)
    ap.add_argument("--matches", default="")
    ap.add_argument("--pc-tag", default="v17")
    a = ap.parse_args()
    if a.accion in ("ping", "comprobar"):
        # 13-11: without enable_output the container's own output (start-up, errors) never reached the Actions log
        with modal.enable_output():
            res = modal.Function.from_name(APP, a.accion).remote()
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0
    if a.accion == "diagnostico":                # 13-11: which ffmpeg cleans the match's .ts (CPU only, cents)
        ids = [x.strip() for x in a.partidos.split(",") if x.strip()]
        fn = modal.Function.from_name(APP, "diag_ts")
        for mid in ids:
            print(f"diagnostico del .ts lanzado en la nube: {mid} ({fn.spawn(mid).object_id})")
        return 0 if ids else 2
    if a.accion == "prueba":                     # 13-11: 10 minutes of a match before the whole of it
        ids = [x.strip() for x in a.partidos.split(",") if x.strip()]
        fn = modal.Function.from_name(APP, "prueba")
        for mid in ids:
            print(f"prueba lanzada en la nube: {mid} ({fn.spawn(mid).object_id})")
        return 0 if ids else 2
    if a.accion == "partidos":                   # 13-11: a batch of matches, side by side
        ids = [x.strip() for x in a.partidos.split(",") if x.strip()]
        fn = modal.Function.from_name(APP, "partido")
        for mid in ids:
            print(f"partido lanzado en la nube: {mid} ({fn.spawn(mid).object_id})")
        return 0 if ids else 2
    call = modal.Function.from_name(APP, "f3set").spawn(tag=a.tag, max_points=a.max_points, matches=a.matches,
                                                        pc_tag=a.pc_tag)
    print(f"F3Set lanzado en la nube (tag {a.tag}): {call.object_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
