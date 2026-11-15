"""R50b (15-11): which rule gives the racket face as a number only where it is stable and right?

Two near-identical runs of the same synthetic stroke (like half against full precision on Kaggle: the same
observations and 3D hand with tiny differences) are solved; for each rule we count the frames it keeps, those whose
side of the strings is wrong against the truth, and those it keeps in both runs with opposite sides (the R50 flips).
The 3D hand covers `cov` of the frames with an error of `sd` degrees (from TV it is scarce and noisy).

    uv run python -m tennisbio.validation.face_rules 0.1 60 60

Measured (60 strokes each): little hand (cov 0.1, sd 60°) — all frames: 11 % wrong, 3.0 % opposite; hand near: keeps
40 %, 3.4 % opposite; hand near and agreeing: keeps 35 %, 1.7 % opposite. More hand (0.3, 40°) — hand near: 83 %,
0.47 % opposite; agreeing: 82 %, 0.12 % opposite.
"""
from __future__ import annotations

import sys

import numpy as np

from ..racket3d import Camera, HandPrior, _ang, refine, solve_sequence, synthetic_observation
from ..racket_orientation import HAND_AGREES_DEG, HAND_NEAR_FRAMES
from .racket3d_synth import noisy, perturb, random_stroke


def _near(pr, t, k=HAND_NEAR_FRAMES):
    return range(max(0, t - k), min(len(pr), t + k + 1))


RULES = {
    "todo": lambda t, n, pr: True,
    "mano_cerca": lambda t, n, pr: any(pr[g] is not None for g in _near(pr, t)),
    "mano_de_acuerdo": lambda t, n, pr: any(pr[g] is not None and _ang(n[t], pr[g].face) < HAND_AGREES_DEG
                                            for g in _near(pr, t)),
}


def _tiny(o, rng):
    return None if o is None else noisy(o, rng, axis_deg=0.4, ratio_sd=0.006)


def _tiny_prior(p, rng):
    return None if p is None else HandPrior(face=perturb(p.face, rng, 2.0), face_sd_deg=p.face_sd_deg, forearm=p.forearm)


def study(n: int = 60, cov: float = 0.1, sd: float = 60.0, seed: int = 3, blur: int = 4) -> dict:
    rng = np.random.default_rng(seed)
    st = {r: {"kept": 0, "both": 0, "opposite": 0, "wrong": 0, "total": 0} for r in RULES}
    for _ in range(n):
        A, N, imp = random_stroke(rng)
        cam = Camera(rng.uniform(15, 25))
        base = [noisy(synthetic_observation(a, nn, cam), rng) for a, nn in zip(A, N)]
        for k in range(imp - blur, imp + blur + 1):
            base[k] = None
        pri = [HandPrior(face=perturb(nn, rng, sd), face_sd_deg=max(sd, 15.0), forearm=perturb(a, rng, 30.0))
               if rng.random() < cov else None for a, nn in zip(A, N)]
        runs = []
        for _r in range(2):
            ob = [_tiny(o, rng) for o in base]
            pr = [_tiny_prior(p, rng) for p in pri]
            ax, nm, _ = solve_sequence(ob, Camera(20.0), imp, priors=pr)
            if all(x is None for x in nm):
                break
            ax, nm = refine(ax, nm, ob, Camera(20.0), imp, priors=pr)
            runs.append((nm, pr))
        if len(runs) < 2:
            continue
        (n1, p1), (n2, p2) = runs
        for t in range(len(N)):
            if abs(t - imp) <= blur:
                continue
            for r, keep in RULES.items():
                s = st[r]
                s["total"] += 1
                k1, k2 = keep(t, n1, p1), keep(t, n2, p2)
                if k1:
                    s["kept"] += 1
                    s["wrong"] += _ang(n1[t], N[t]) > 90
                if k1 and k2:
                    s["both"] += 1
                    s["opposite"] += _ang(n1[t], n2[t]) > 90
    return {r: {"kept": round(s["kept"] / max(1, s["total"]), 3),
                "wrong_side": round(s["wrong"] / max(1, s["kept"]), 4),
                "opposite_between_runs": round(s["opposite"] / max(1, s["both"]), 4)} for r, s in st.items()}


if __name__ == "__main__":
    a = sys.argv[1:]
    print(study(n=int(a[2]) if len(a) > 2 else 60, cov=float(a[0]) if a else 0.1, sd=float(a[1]) if len(a) > 1 else 60.0))
