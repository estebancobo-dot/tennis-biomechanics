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
AIR_PCT = 0.04               # ankle higher than its ground level by > 4 % of the height = in the air
MAX_SPEED = 9.0              # m/s: faster than any tennis player; above it the feet track is noise


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
    """(T, 2) bool: each ankle above its ground level (the lower envelope of its image height
    over ~0.6 s), by more than AIR_PCT of the body height."""
    T = len(img)
    out = np.zeros((T, 2), bool)
    k = max(2, int(0.3 * fps))
    for j, name in enumerate(("dom_ankle", "non_ankle")):
        y = img[:, sk[name], 1]
        for t in range(T):
            seg = y[max(0, t - k):t + k + 1]
            if np.isfinite(y[t]) and np.isfinite(seg).any():
                out[t, j] = (np.nanmax(seg) - y[t]) > AIR_PCT * scale[t]      # image y grows downwards
    return out


def planted(feet: np.ndarray, air: np.ndarray, fps: float) -> np.ndarray:
    """(T, 2) bool: foot on the ground and (nearly) still on the court."""
    sp = np.full(feet.shape[:2], np.nan)
    for j in range(2):
        p = smooth(feet[:, j], fps, 0.06)
        v = np.linalg.norm(np.gradient(p, axis=0), axis=1) * fps
        sp[:, j] = v
    return (sp < PLANTED_SPEED) & ~air


def steps(feet: np.ndarray, plant: np.ndarray, a: int, b: int) -> list[Step]:
    """Steps of either foot between frames a and b (a step that lands in the interval counts)."""
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
                    if L >= MIN_STEP_M:
                        other = feet[start:u + 1, 1 - j, 0]
                        mov = feet[start:u + 1, j, 0]
                        rel = mov - other
                        rel = rel[np.isfinite(rel)]
                        cross = bool(len(rel) > 1 and np.sign(rel[0]) != np.sign(rel[-1]) and abs(rel[0]) > 0.1 and abs(rel[-1]) > 0.1)
                        out.append(Step(foot, start, u, L, float(d[0]), float(d[1]), cross))
                t = u
            t += 1
    return sorted(out, key=lambda s: s.land)


def hip_court(img: np.ndarray, sk: Skeleton, H: np.ndarray, feet: np.ndarray) -> np.ndarray:
    """Her position on the court per frame: the midpoint of both feet (ground truth for the
    homography), NaN when either foot is unseen."""
    return np.nanmean(feet, axis=1) if np.isfinite(feet).any() else np.full((len(img), 2), np.nan)


def footwork(img: np.ndarray, sk: Skeleton, H: np.ndarray, scale: np.ndarray, fps: float, impact: int,
             opp: int | None, split: int | None, finish: int | None, loaded: int | None, surface: str = "") -> dict:
    """All footwork descriptors of one stroke (frame indices are clip frames)."""
    T = len(img)
    feet = feet_track(img, sk, H)
    air = airborne(img, sk, scale, fps)
    feet_g = feet.copy()
    feet_g[air] = np.nan                       # positions only from feet on the ground
    plant = planted(feet_g, air, fps)
    with np.errstate(invalid="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)        # frames with no foot on the ground
        pos = smooth(np.nanmean(feet_g, axis=1), fps, 0.25)          # body position: ~0.25 s smoothing
    vel = np.gradient(pos, axis=0) * fps
    spd = np.linalg.norm(vel, axis=1)
    spd[spd > MAX_SPEED] = np.nan
    s = lambda sec: int(round(sec * fps))
    a = opp if opp is not None else max(0, impact - s(1.2))
    b = min(T, impact + s(1.0))
    st = steps(feet_g, plant, a, b)
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
        out["first_step_type"] = ("cruzado" if f.crossover else
                                  "pivote" if f.length_m < 0.3 else
                                  "lateral" if abs(f.dy) < 0.5 * abs(f.dx) else "hacia delante" if f.dy > 0 else "hacia atrás")
    adj = [x for x in pre if x.land >= impact - s(0.8) and x.length_m < 0.5]
    out["adjustment_steps"] = len(adj)
    if pre:
        last = pre[-1]
        out["last_plant_foot"] = last.foot
        out["last_plant_before_impact_s"] = round((impact - last.land) / fps, 3)
    if loaded is not None and 0 <= loaded < T:                        # loading foot: the hips over which foot
        hips = (img[loaded, sk["left_hip"], 0] + img[loaded, sk["right_hip"], 0]) / 2
        ax = img[loaded, [sk["dom_ankle"], sk["non_ankle"]], 0]
        if np.isfinite(ax).all() and np.isfinite(hips) and abs(ax[0] - ax[1]) > 0.04 * scale[loaded]:
            w = (hips - ax[0]) / (ax[1] - ax[0])                     # 0 = over the dominant foot, 1 = over the other
            out["weight_loaded_to_non"] = round(float(np.clip(w, -0.5, 1.5)), 2)
    # in the air: both feet up for at least 2 consecutive frames around contact (one noisy frame is not a jump)
    i0, i1 = max(0, impact - 2), min(T, impact + 3)
    both = air[i0:i1].all(axis=1)
    out["airborne_at_impact"] = bool(len(both) > 1 and (both[1:] & both[:-1]).any())
    one = air[i0:i1].any(axis=1)
    out["one_foot_at_impact"] = bool(len(one) > 1 and (one[1:] & one[:-1]).any()) and not out["airborne_at_impact"]
    v_imp = float(np.nanmedian(spd[max(0, impact - s(0.1)):impact + 1])) if np.isfinite(spd[max(0, impact - s(0.1)):impact + 1]).any() else None
    out["speed_at_impact_mps"] = None if v_imp is None else round(v_imp, 2)
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
    v = out.get("speed_at_impact_mps")
    out["movement"] = ("en el aire" if out["airborne_at_impact"] else "deslizando" if out.get("sliding_at_impact")
                       else None if v is None else "parada" if v < 0.7 else "en movimiento" if v < 2.0 else "en carrera")
    return out
