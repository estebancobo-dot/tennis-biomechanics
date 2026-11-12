"""Why the identity decides less in an F3Set compilation than before (12-11: Azarenka's, 78 runs «sin decidir» with the
code of 12-11 against almost none on 08-11). Compares <datasets>/f3set/recall/<A>/<mid>/identity.json with <B>/<mid>
(default A = salidas, the 08-11 recount; B = salidas_base, today's): decided runs, the cue that decided each one, the
clothes check (distinguishable, why, parity agreement), the votes and the scoreboard base; and for the runs decided
before and undecided now, what each run says. Writes <output>/capturas_diag/diag_identidad_f3set.json. Reads only.

    uv run python scripts/diag_identidad_f3set.py --match azarenka [--a salidas --b salidas_base]"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio import match_files as _mf  # noqa: E402
from tennisbio.config import load_config  # noqa: E402

KEYS = ("near_is_target", "method", "ends_said", "cluster", "clothes_margin", "clothes_says", "end_changes",
        "serve_vote", "return_vote", "games", "start", "end")


def load(d: Path) -> dict:
    f = _mf.at(d, "identity.json")
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def side(ident: dict) -> dict:
    runs = ident.get("runs") or []
    return {"runs": len(runs), "decided": sum(r.get("near_is_target") is not None for r in runs),
            "by_method": dict(Counter(str(r.get("method")) for r in runs)), "clothes": ident.get("clothes"),
            "votes": ident.get("votes"), "ends_base": ident.get("ends_base"), "click_by": ident.get("click_by"),
            "confidence": ident.get("confidence")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--match", required=True)
    ap.add_argument("--a", default="salidas")
    ap.add_argument("--b", default="salidas_base")
    a = ap.parse_args()
    cfg = load_config()
    out = Path((cfg.get("paths") or {}).get("output") or "output")
    rec = out.parent / "datasets" / "f3set" / "recall"
    rep = {}
    for d in sorted((rec / a.a).glob(f"*{a.match.lower()}*")):
        ia, ib = load(d), load(rec / a.b / d.name)
        ra, rb = ia.get("runs") or [], ib.get("runs") or []
        lost, flipped = [], []
        for x, y in zip(ra, rb):
            if x.get("near_is_target") is not None and y.get("near_is_target") is None:
                lost.append({"antes": {k: x.get(k) for k in KEYS}, "ahora": {k: y.get(k) for k in KEYS}})
        # 13-11 (F3Set v16 against v15: one point of Azarenka's went to the other player): runs decided both times
        # but the other way, matched by overlap (the runs need not be the same ones in both)
        for y in rb:
            if y.get("near_is_target") is None:
                continue
            for x in ra:
                ov = min(x.get("end", 0), y.get("end", 0)) - max(x.get("start", 0), y.get("start", 0))
                if ov > 0 and x.get("near_is_target") is not None and x["near_is_target"] != y["near_is_target"]:
                    flipped.append({"solape_fotogramas": int(ov), "antes": {k: x.get(k) for k in KEYS},
                                    "ahora": {k: y.get(k) for k in KEYS}})
        rep[d.name] = {"antes": side(ia), "ahora": side(ib), "decididos_antes_y_no_ahora": len(lost),
                       "ejemplos": lost[:12], "decididos_al_reves": len(flipped), "al_reves": flipped[:12]}
    dst = out / "capturas_diag"
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "diag_identidad_f3set.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: {kk: v[kk] for kk in ("antes", "ahora", "decididos_antes_y_no_ahora",
                                                                      "decididos_al_reves")} for k, v in rep.items()},
                     ensure_ascii=False, indent=1, default=str)[:4000])


if __name__ == "__main__":
    main()
