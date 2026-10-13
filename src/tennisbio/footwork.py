"""Footwork from the ankles on the court: steps, first step, adjustment steps, loading foot,
airborne / sliding detection, movement speed and recovery.

Everything is in her own court frame (court_metrics.player_frame_H: her baseline at y = 0,
x + = her right, the net at y = 11.885), in metres. A foot is "planted" while it barely moves on
the court; a step is a foot that leaves one planted spot and lands on another. The homography is
exact only on the ground, so a foot in the air (higher in the image than its planted level)
is never used as a position and marks the frame as airborne instead.
"""
import warnings
from dataclasses import dataclass

import numpy as np

from .court_metrics import to_court
from .kinematics import smooth
from .skeleton import Skeleton

PLANTED_SPEED = 0.7          # m/s: below this a foot counts as on the ground
MIN_STEP_M = 0.15            # shorter displacements are weight shifts, not steps
MAX_STEP_M = 2.2             # longer "steps" are runs where the ground contacts were not seen
MAX_STEP_S = 0.7             # a foot cannot stay in the air this long in one step
AIR_PCT = 0.04               # ankle higher than its ground level by > 4 % of the height = in the air
MAX_SPEED = 9.0              # m/s: faster than any tennis player; above it the feet track is noise
STEPS_MIN_STILL = 0.4        # share of frames with a foot seen still, below which steps are not measured


@dataclass
class Step:
    foot: str                # "dom" / "non"
    start: int               # frame the foot leaves the ground spot
    land: int                # frame it is planted again
    length_m: float
    dx: float                # lateral (+ = her right) and forward (+ = towards the net) components
    dy: float
    crossover: bool          # the moving foot passed in front of / behind the other one

    def to_dict(self, fps: float, ref: int) -> dict:
        return {"foot": self.foot, "t_start": round((self.start - ref) / fps, 3), "t_land": round((self.land - ref) / fps, 3),
                "length_m": round(self.length_m, 2), "dx": round(self.dx, 2), "dy": round(self.dy, 2), "crossover": self.crossover}


def feet_track(img: np.ndarray, sk: Skeleton, H: np.ndarray):
    """Court positions (T, 2, 2) of the dominant and non-dominant ankle, NaN when unseen."""
    T = len(img)
    out = np.full((T, 2, 2), np.nan)
    for j, name in enumerate(("dom_ankle", "non_ankle")):
        p = img[:, sk[name]]
        ok = np.isfinite(p).all(axis=1)
        if ok.any():
            out[ok, j] = to_court(H, p[ok])
    return out


def airborne(img: np.ndarray, sk: Skeleton, scale: np.ndarray, fps: float) -> np.ndarray:
    """(T, 2) bool: each ankle above its ground level by more than AIR_PCT of the body height.

    The ground level is the LOWER of the two envelopes before and after (~0.3 s each side): a foot
    in the air comes back down, so it is above the ground on both sides. Running towards the net
    also raises the feet in the image (depth), but only relative to the past, never to the future:
    with a one-sided envelope every stroke on the move looked like a jump (user's PC, 10 of 10)."""
    T = len(img)
    out = np.zeros((T, 2), bool)
    k = max(2, int(0.3 * fps))
    for j, name in enumerate(("dom_ankle", "non_ankle")):
        y = img[:, sk[name], 1]
        for t in range(T):
            if not np.isfinite(y[t]):
                continue
            before, after = y[max(0, t - k):t], y[t + 1:t + k + 1]
            if not (np.isfinite(before).any() and np.isfinite(after).any()):
                continue
            ground = min(np.nanmax(before), np.nanmax(after))           # image y grows downwards
            out[t, j] = (ground - y[t]) > AIR_PCT * scale[t]
    return out


def planted(feet: np.ndarray, air: np.ndarray, fps: float) -> np.ndarray:
    """(T, 2) bool: foot on the ground and (nearly) still on the court."""
    sp = np.full(feet.shape[:2], np.nan)
    for j in range(2):
        p = smooth(feet[:, j], fps, 0.06)
        v = np.linalg.norm(np.gradient(p, axis=0), axis=1) * fps
        sp[:, j] = v
    return (sp < PLANTED_SPEED) & ~air


def steps(feet: np.ndarray, plant: np.ndarray, a: int, b: int, fps: float) -> list[Step]:
    """Steps of either foot between frames a and b (a step that lands in the interval counts).
    Displacements too long or too slow for one step (missed ground contacts) are left out."""
    out = []
    for j, foot in enumerate(("dom", "non")):
        t = max(1, a)
        while t < min(b, len(plant)):
            if plant[t - 1, j] and not plant[t, j]:               # lift-off
                start = t - 1
                u = t
                while u < len(plant) and not plant[u, j]:
                    u += 1
                if u >= len(plant):
                    break
                p0, p1 = feet[start, j], feet[u, j]
                if np.isfinite(p0).all() and np.isfinite(p1).all():
                    d = p1 - p0
                    L = float(np.linalg.norm(d))
                    if L >= MIN_STEP_M and L <= MAX_STEP_M and (u - start) <= MAX_STEP_S * fps:
                        other = feet[start:u + 1, 1 - j, 0]
                        mov = feet[start:u + 1, j, 0]
                        rel = mov - other
                        rel = rel[np.isfinite(rel)]
                        cross = bool(len(rel) > 1 and np.sign(rel[0]) != np.sign(rel[-1]) and abs(rel[0]) > 0.1 and abs(rel[-1]) > 0.1)
                        out.append(Step(foot, start, u, L, float(d[0]), float(d[1]), cross))
                t = u
            t += 1
    return sorted(out, key=lambda s: s.land)


KIND_PLURAL = {"lateral": ("paso lateral", "pasos laterales"), "cruzado": ("paso cruzado", "pasos cruzados"),
               "carrera": ("paso de carrera", "pasos de carrera"), "hacia delante": ("paso hacia delante", "pasos hacia delante"),
               "hacia atrás": ("paso hacia atrás", "pasos hacia atrás"), "ajuste": ("paso de ajuste", "pasos de ajuste")}


def step_kinds(st: list[Step], impact: int, fps: float) -> list[str]:
    """Each step as a coach names it (Kovacs 2009; Tennis Australia): crossover, small adjustment
    step in the last 0.8 s before contact, running step (long and quick, alternating feet), side step
    (shuffle, the feet do not cross), forwards or backwards."""
    kinds = []
    for i, x in enumerate(st):
        dur = (x.land - x.start) / fps
        nb = [y for y in (st[i - 1] if i else None, st[i + 1] if i + 1 < len(st) else None) if y is not None and y.foot != x.foot]
        run = x.length_m >= 0.6 and dur <= 0.35 and any(y.length_m >= 0.6 for y in nb)
        if x.crossover:
            k = "cruzado"
        elif impact - 0.8 * fps <= x.land <= impact and x.length_m < 0.35:
            k = "ajuste"
        elif run:
            k = "carrera"
        elif abs(x.dx) >= abs(x.dy):
            k = "lateral"
        else:
            k = "hacia delante" if x.dy > 0 else "hacia atrás"
        kinds.append(k)
    return kinds


def kinds_text(kinds: list[str]) -> str:
    """'2 pasos laterales, 1 paso cruzado y 2 pasos de ajuste', in the order they first appear."""
    order = list(dict.fromkeys(kinds))
    parts = [f"{kinds.count(k)} {KIND_PLURAL[k][kinds.count(k) > 1]}" for k in order]
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " y " + parts[-1] if parts else ""


def hip_court(img: np.ndarray, sk: Skeleton, H: np.ndarray, feet: np.ndarray) -> np.ndarray:
    """Her position on the court per frame: the midpoint of both feet (ground truth for the
    homography), NaN when either foot is unseen."""
    return np.nanmean(feet, axis=1) if np.isfinite(feet).any() else np.full((len(img), 2), np.nan)


def footwork(img: np.ndarray, sk: Skeleton, H: np.ndarray, scale: np.ndarray, fps: float, impact: int,
             opp: int | None, split: int | None, finish: int | None, loaded: int | None, surface: str = "",
             next_opp: int | None = None, stroke: str = "forehand") -> dict:
    """All footwork descriptors of one stroke (frame indices are clip frames). next_opp: the
    opponent's next hit (to know whether she had recovered by then)."""
    T = len(img)
    feet = feet_track(img, sk, H)
    air = airborne(img, sk, scale, fps)
    feet_g = feet.copy()
    feet_g[air] = np.nan                       # positions only from feet on the ground
    plant = planted(feet_g, air, fps)
    # body position: the midpoint of the feet only while BOTH are on the ground, interpolated in
    # between (a lifted foot used to make the "midpoint" jump to the other foot, half a stance
    # width in one frame, and every stroke looked like a sprint), then smoothed over ~0.3 s
    mid = (feet_g[:, 0] + feet_g[:, 1]) / 2
    ok = np.isfinite(mid).all(axis=1)
    if ok.sum() >= 2:
        idx = np.arange(T)
        for d in range(2):
            mid[:, d] = np.interp(idx, idx[ok], mid[ok, d])
        gap = np.zeros(T, bool)                                   # no invention over long gaps (> 0.4 s)
        run = 0
        for t in range(T):
            run = 0 if ok[t] else run + 1
            gap[t] = run > int(0.4 * fps)
        mid[gap] = np.nan
        mid[:idx[ok][0]] = np.nan
        mid[idx[ok][-1] + 1:] = np.nan
    with np.errstate(invalid="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        pos = smooth(mid, fps, 0.3)
    vel = np.gradient(pos, axis=0) * fps
    spd = np.linalg.norm(vel, axis=1)
    spd[spd > MAX_SPEED] = np.nan
    s = lambda sec: int(round(sec * fps))
    a = opp if opp is not None else max(0, impact - s(1.2))
    b = min(T, impact + s(1.0))
    st = steps(feet_g, plant, a, b, fps)
    out: dict = {}
    pre = [x for x in st if x.land <= impact]
    out["steps_to_impact"] = len(pre)
    out["steps"] = [x.to_dict(fps, impact) for x in st]
    after_split = [x for x in st if split is not None and x.start >= split] or ([x for x in st if opp is not None and x.start >= opp])
    if after_split:
        f = after_split[0]
        ref = split if split is not None else opp
        out["first_step_s"] = round((f.start - ref) / fps, 3)        # reaction: from landing (or opponent hit)
        out["first_step_foot"] = f.foot
        ang = float(np.degrees(np.arctan2(f.dy, f.dx * sk.dom_sign)))     # 0 = towards her forehand side
        out["first_step_dir_deg"] = round(ang, 0)
        # where she has to go (the impact position) decides gravity / jab steps
        ball_dx = None
        if opp is not None and np.isfinite(pos[[opp, impact]]).all():
            ball_dx = pos[impact, 0] - pos[opp, 0]
        fi = 0 if f.foot == "dom" else 1
        p0 = feet_g[f.start, fi]
        po = feet_g[f.start, 1 - fi]
        near_foot = None
        if ball_dx is not None and abs(ball_dx) > 0.5 and np.isfinite(p0).all() and np.isfinite(po).all():
            near_foot = (p0[0] - po[0]) * np.sign(ball_dx) > 0          # this foot is on the side of the ball
        out["first_step_length_m"] = round(f.length_m, 2)
        if ball_dx is not None and abs(ball_dx) > 0.5 and not (f.dx * np.sign(ball_dx) < -0.05 and f.length_m < 0.4):
            out["first_step_right_way"] = bool(f.dx * np.sign(ball_dx) > 0)      # a gravity step back is not a wrong way
        out["first_step_type"] = (
            "cruzado" if f.crossover else
            "gravity (contrapaso)" if ball_dx is not None and abs(ball_dx) > 0.5 and f.dx * np.sign(ball_dx) < -0.05 else
            "jab (pie cercano hacia la bola)" if near_foot and f.dx * np.sign(ball_dx) > 0.15 else
            "pivote" if f.length_m < 0.3 else
            "lateral" if abs(f.dy) < 0.5 * abs(f.dx) else "hacia delante" if f.dy > 0 else "hacia atrás")
    adj = [x for x in pre if x.land >= impact - s(0.8) and x.length_m < 0.5]
    out["adjustment_steps"] = len(adj)
    if pre:
        last = pre[-1]
        out["last_plant_foot"] = last.foot
        out["last_step_length_m"] = round(last.length_m, 2)
        out["last_plant_before_impact_s"] = round((impact - last.land) / fps, 3)
    if loaded is not None and 0 <= loaded < T:                        # loading foot: the hips over which foot
        hips = (img[loaded, sk["left_hip"], 0] + img[loaded, sk["right_hip"], 0]) / 2
        ax = img[loaded, [sk["dom_ankle"], sk["non_ankle"]], 0]
        if np.isfinite(ax).all() and np.isfinite(hips) and abs(ax[0] - ax[1]) > 0.04 * scale[loaded]:
            w = (hips - ax[0]) / (ax[1] - ax[0])                     # 0 = over the dominant foot, 1 = over the other
            out["weight_loaded_to_non"] = round(float(np.clip(w, -0.5, 1.5)), 2)
    # in the air: both feet up for at least 0.08 s around contact (a heel lifting on a noisy frame
    # is not a jump)
    i0, i1 = max(0, impact - s(0.06)), min(T, impact + s(0.06) + 1)
    both = air[i0:i1].all(axis=1)
    need = max(2, s(0.08))
    runs = np.convolve(both.astype(int), np.ones(need, int), "valid") if len(both) >= need else np.zeros(0)
    out["airborne_at_impact"] = bool((runs >= need).any())
    one = air[i0:i1].any(axis=1)
    out["one_foot_at_impact"] = bool(len(one) > 1 and (one[1:] & one[:-1]).any()) and not out["airborne_at_impact"]
    # speed AT contact: displacement of the feet midpoint (both feet down, lightly smoothed) over
    # ±0.06 s. The ~0.3 s smoothed track is fine for the path, but at contact it carried the run that
    # brought her to the ball into a stroke hit with both feet set (user's PC, contact sheets).
    with np.errstate(invalid="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        pos_c = smooth(mid, fps, 0.06)
    i0c, i1c = max(0, impact - s(0.06)), min(T - 1, impact + s(0.06))
    v_imp = None
    if i1c > i0c and np.isfinite(pos_c[[i0c, i1c]]).all():
        v_imp = float(np.linalg.norm(pos_c[i1c] - pos_c[i0c]) / ((i1c - i0c) / fps))
        v_imp = None if v_imp > MAX_SPEED else v_imp
    out["speed_at_impact_mps"] = None if v_imp is None else round(v_imp, 2)
    # how she arrives: mean speed from 0.8 to 0.3 s before contact, BEFORE the forward swing. Around
    # contact the body moves 2-3 m/s with the weight transfer of the stroke itself (hips and feet,
    # measured on the user's PC with both feet set), which is not running to the ball.
    i0a, i1a = max(0, impact - s(0.8)), max(0, impact - s(0.3))
    if i1a > i0a and np.isfinite(pos[[i0a, i1a]]).all():
        va = float(np.linalg.norm(pos[i1a] - pos[i0a]) / ((i1a - i0a) / fps))
        if va <= MAX_SPEED:
            out["approach_speed_mps"] = round(va, 2)
    # feet at contact: both set, one foot, (in the air below)
    pc = plant[max(0, impact - s(0.04)):impact + s(0.04) + 1]
    if len(pc):
        out["feet_at_impact"] = ("dos pies apoyados" if pc.all(axis=1).any() else
                                 "un pie apoyado" if pc.any(axis=1).any() else "ningún pie quieto")
    # sliding: a foot on the ground that keeps moving fast on the court (only on clay or grass;
    # on a hard court it is tracking noise)
    slide_surface = any(w in (surface or "").lower() for w in ("clay", "tierra", "arcilla", "grass", "hierba"))
    if v_imp is not None and slide_surface:
        g = feet_g[max(0, impact - s(0.15)):impact + 1]
        gv = [np.linalg.norm(np.nanmean(np.diff(g[:, j], axis=0), axis=0)) * fps for j in range(2)
              if np.isfinite(np.diff(g[:, j], axis=0)).all(axis=1).sum() >= 2]
        out["sliding_at_impact"] = bool(gv and max(gv) > 1.2 and not out["airborne_at_impact"])
    if opp is not None and np.isfinite(pos[opp]).all() and np.isfinite(pos[impact]).all():
        path = pos[opp:impact + 1]
        path = path[np.isfinite(path).all(axis=1)]
        out["path_m"] = round(float(np.sum(np.linalg.norm(np.diff(path, axis=0), axis=1))), 2) if len(path) > 1 else None
        d = pos[impact] - pos[opp]
        out["move_dx_m"], out["move_dy_m"] = round(float(d[0]), 2), round(float(d[1]), 2)
        pk = spd[opp:impact + 1]
        out["peak_speed_mps"] = round(float(np.nanpercentile(pk, 90)), 2) if np.isfinite(pk).sum() >= 3 else None
    if finish is not None and np.isfinite(pos[impact]).all():
        r1 = min(T - 1, impact + s(1.0))
        if np.isfinite(pos[r1]).all():
            d = pos[r1] - pos[impact]
            out["recovery_dx_m"], out["recovery_dy_m"] = round(float(d[0]), 2), round(float(d[1]), 2)
            out["recovery_to_centre_m"] = round(float(abs(pos[impact][0]) - abs(pos[r1][0])), 2)
            if d[1] > 1.5:
                out["moves_to_net"] = True                   # approach: keeps going forward after the hit
    # split step: take-off (feet start rising) and speed just before / after it
    if split is not None and 0 < split < T:
        y = (img[:, sk["left_ankle"], 1] + img[:, sk["right_ankle"], 1]) / 2
        a0 = max(0, split - s(0.6))
        seg = y[a0:split + 1]
        if np.isfinite(seg).sum() >= 4:
            base = np.nanmax(seg)                                  # ground level (image y grows down)
            lift = (base - seg) / np.nanmedian(scale[a0:split + 1])
            pk = int(np.nanargmax(lift))
            up = np.flatnonzero(lift[:pk + 1] < 0.25 * lift[pk]) if lift[pk] > 0.005 else []
            if len(up):
                take = a0 + int(up[-1])
                out["split_takeoff_s"] = round((take - impact) / fps, 3)
                if opp is not None:
                    out["split_takeoff_vs_opp_s"] = round((take - opp) / fps, 3)
                    out["split_landing_vs_opp_s"] = round((split - opp) / fps, 3)
        for key, a, b in (("speed_pre_split_mps", split - s(0.2), split), ("speed_post_split_mps", split, split + s(0.2))):
            w = spd[max(0, a):min(T, b + 1)]
            if np.isfinite(w).sum() >= 2:
                out[key] = round(float(np.nanmedian(w)), 2)
    # main direction of the run to the ball, and changes of direction on the way
    if opp is not None and out.get("move_dx_m") is not None:
        dx, dy = out["move_dx_m"], out["move_dy_m"]
        out["move_direction"] = ("sin desplazamiento" if np.hypot(dx, dy) < 0.8 else
                                 "lateral" if abs(dx) >= abs(dy) else "hacia delante" if dy > 0 else "hacia atrás")
        vx = vel[opp:min(T, impact + s(1.0)), 0]
        sp = spd[opp:min(T, impact + s(1.0))]
        sg = np.sign(vx[np.isfinite(vx) & (sp > 1.0)])
        out["direction_changes"] = int(np.sum(sg[1:] != sg[:-1])) if len(sg) > 1 else 0
    # the back leg stepping through after contact (strong trunk rotation)
    back = "dom" if stroke != "backhand" else "non"
    through = [x for x in st if x.foot == back and impact <= x.start <= impact + s(0.5) and x.dy > 0.2]
    out["rear_leg_step_after"] = bool(through)
    # every step named, on the way to the ball and on the way back (the movement cycle: split step →
    # first step → steps to the ball → adjustment and braking → stance → contact → recovery)
    kinds = step_kinds(st, impact, fps)
    out["step_kinds"] = kinds                                      # every step named, in order
    out["crossover_steps"] = sum(k == "cruzado" for k in kinds)    # to the ball and back
    t0 = split if split is not None else opp if opp is not None else a
    appr = [(x, k) for x, k in zip(st, kinds) if x.start >= t0 and x.land <= impact]
    out["approach_steps"] = [{**x.to_dict(fps, impact), "kind": k} for x, k in appr]
    out["approach_pattern"] = kinds_text([k for _, k in appr]) or "ningún paso: golpea desde donde está"
    if appr:
        last = appr[-1][0]
        v0 = spd[last.start] if 0 <= last.start < T else np.nan
        # braking: a long last step while she was moving, the speed falling a lot by contact
        out["braking_step"] = bool(last.length_m >= 0.7 and np.isfinite(v0) and v0 > 1.5
                                   and (v_imp is None or v_imp < 0.6 * v0))
    rec = [(x, k) for x, k in zip(st, kinds) if x.start >= impact + s(0.1)]
    out["recovery_steps"] = [{**x.to_dict(fps, impact), "kind": k} for x, k in rec]
    if rec:
        out["recovery_pattern"] = kinds_text([k for _, k in rec])
        out["recovery_first_step"] = rec[0][1]
        out["recovery_start_s"] = round((rec[0][0].start - impact) / fps, 3)
    bj = 0 if back == "dom" else 1
    # step-in (attack step): the front foot steps forward, into the court, in the last 0.5 s
    front = "non" if back == "dom" else "dom"
    out["step_in"] = any(x.foot == front and x.dy > 0.25 and impact - s(0.5) <= x.land <= impact + s(0.04) for x, _ in appr)
    # drag foot: after contact the back foot slides forward on the ground (not lifted) at least 0.25 m
    w2 = slice(impact, min(T, impact + s(0.4)))
    pb = feet[w2, bj]
    lifted_b = air[w2, bj]
    okb = np.isfinite(pb).all(axis=1) & ~lifted_b
    if okb.sum() >= 3:
        q = pb[okb]
        out["drag_foot"] = bool((q[-1][1] - q[0][1]) > 0.25 and lifted_b.mean() < 0.3)
    # kick-back (scissor kick): the back foot leaves the ground right after contact while the front
    # one stays down, for at least 0.08 s
    bj = 0 if back == "dom" else 1
    w = air[impact:min(T, impact + s(0.3))]
    if len(w):
        lifted = w[:, bj] & ~w[:, 1 - bj]
        runs_k = np.convolve(lifted.astype(int), np.ones(need, int), "valid") if len(lifted) >= need else np.zeros(0)
        out["kick_back"] = bool((runs_k >= need).any())
    # recovered when the opponent hits again: distance from the centre of her baseline area
    if next_opp is not None and 0 <= next_opp < T and np.isfinite(pos[next_opp]).all():
        out["off_centre_at_opp_hit_m"] = round(float(abs(pos[next_opp, 0])), 2)
        sp = spd[max(0, next_opp - 2):next_opp + 1]
        out["moving_at_opp_hit_mps"] = None if not np.isfinite(sp).any() else round(float(np.nanmedian(sp)), 2)
    # how she gets to the ball (before the swing), or in the air / sliding at contact
    v = out.get("approach_speed_mps")
    out["movement"] = ("en el aire" if out["airborne_at_impact"] else "deslizando" if out.get("sliding_at_impact")
                       else None if v is None else "parada" if v < 0.7 else "en movimiento" if v < 2.0 else "en carrera")
    # Are single steps measurable here? In a rally a foot is on the ground most of the time; when
    # the ankles of this player (small in the image, 50 fps) jitter so much that a foot is seen still
    # in less than 40 % of the frames, steps, plants and the split step are not measured: they would
    # be invented (user's PC: 5-36 % on a ~190 px player). Position, distance and speeds stay.
    ground = plant[a:b][np.isfinite(feet_g[a:b]).all(axis=2)]
    still = float(np.mean(ground)) if ground.size else 0.0
    out["feet_still_share"] = round(still, 2)
    if still < STEPS_MIN_STILL:
        for k in [k for k in out if k.startswith(("steps", "first_step", "last_plant", "last_step", "split_",
                                                    "adjustment", "rear_leg", "feet_at_impact", "weight_loaded",
                                                    "approach_steps", "approach_pattern", "braking", "recovery_steps",
                                                    "recovery_pattern", "recovery_first", "recovery_start", "kick_back",
                                                    "step_in", "drag_foot", "crossover_steps"))]:
            del out[k]
        out["steps_reliable"] = False
    else:
        out["steps_reliable"] = True
    return out
