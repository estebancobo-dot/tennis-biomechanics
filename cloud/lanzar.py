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
    ap.add_argument("accion", choices=("comprobar", "f3set"))
    ap.add_argument("--tag", default="nube")
    ap.add_argument("--max-points", type=int, default=0)
    ap.add_argument("--matches", default="")
    ap.add_argument("--pc-tag", default="v17")
    a = ap.parse_args()
    if a.accion == "comprobar":
        res = modal.Function.from_name(APP, "comprobar").remote()
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0
    call = modal.Function.from_name(APP, "f3set").spawn(tag=a.tag, max_points=a.max_points, matches=a.matches,
                                                        pc_tag=a.pc_tag)
    print(f"F3Set lanzado en la nube (tag {a.tag}): {call.object_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
