"""The 8 key moments of a groundstroke, detected from pose events around a known impact.

1 ready / split step · 2 takeback start · 3 fully loaded · 4 acceleration start · 5 impact ·
6 extension · 7 finish · 8 recovery. Every event records how it was found and a confidence,
so weak detections can be sent to manual review instead of being trusted.
"""
from dataclasses import dataclass

import numpy as np
from scipy.signal import find_peaks

from .kinematics import line_turn, speed
from .skeleton import Skeleton

PHASES = ["ready", "takeback", "loaded", "acceleration", "impact", "extension", "finish", "recovery"]
LABELS_ES = {
    "ready": "Espera / split step", "takeback": "Inicio del takeback", "loaded": "Armado completo",
    "acceleration": "Inicio de aceleración", "impact": "Impacto", "extension": "Extensión",
    "finish": "Terminación", "recovery": "Recuperación",
}


@dataclass
class Event:
    name: str
    frame: int | None
    method: str
    confidence: float


def _argext(x: np.ndarray, a: int, b: int, fn) -> int | None:
    a, b = max(a, 0), min(b, len(x))
    if b <= a or np.all(np.isnan(x[a:b])):
        return None
    return a + int(fn(x[a:b]))


def _walk_down(x: np.ndarray, i: int, lo: int) -> int:
    """From i, move backwards while the signal keeps decreasing (to the nearest local minimum)."""
    while i - 1 >= lo and not np.isnan(x[i - 1]) and x[i - 1] <= x[i]:
        i -= 1
    return i


def _walk_up(x: np.ndarray, i: int, lo: int, tol=0.03) -> int:
    """From i, move backwards while the signal keeps increasing or stays on a plateau; returns the
    highest point found (nearest local maximum)."""
    best = i
    while i - 1 >= lo and not np.isnan(x[i - 1]) and x[i - 1] >= x[i] - tol * max(x[best], 1e-6):
        i -= 1
        if x[i] > x[best]:
            best = i
    return best


def _smooth(x: np.ndarray, k: int) -> np.ndarray:
    """Centred moving average over k frames that tolerates NaN gaps."""
    if k <= 1:
        return x
    v = np.where(np.isnan(x), 0.0, x)
    w = (~np.isnan(x)).astype(float)
    ker = np.ones(k)
    num, den = np.convolve(v, ker, "same"), np.convolve(w, ker, "same")
    out = num / np.maximum(den, 1e-9)
    out[den == 0] = np.nan
    return out


def detect_split_step(img: np.ndarray, sk: Skeleton, height: float, fps: float, a: int, b: int):
    """Landing of a small two-footed hop between frames a and b (image coordinates).

    Both ankles rise together and come back down. Slow camera motion is removed by subtracting
    a 0.5 s moving average. Returns (landing_frame, hop_height_in_body_heights) or None.
    """
    a, b = max(a, 0), min(b, len(img))
    if b - a < int(0.2 * fps):
        return None
    y = (img[:, sk["left_ankle"], 1] + img[:, sk["right_ankle"], 1]) / 2
    seg = y[a:b]
    if np.isnan(seg).mean() > 0.3:
        return None
    seg = np.where(np.isnan(seg), np.nanmedian(seg), seg)
    k = max(3, int(0.5 * fps) | 1)
    base = np.convolve(np.pad(seg, k // 2, mode="edge"), np.ones(k) / k, mode="valid")
    lift = (base - seg) / height                     # >0 when the feet are above their local level
    peaks, props = find_peaks(lift, prominence=0.012, distance=int(0.25 * fps))
    if not len(peaks):
        return None
    p = peaks[np.argmax(props["prominences"])]
    after = np.flatnonzero(lift[p:] <= 0.002)
    land = p + (after[0] if len(after) else min(int(0.1 * fps), len(lift) - 1 - p))
    return a + int(land), float(props["prominences"].max())


def _shoulder_turn_start(img: np.ndarray, sk: Skeleton, fps: float, impact: int, min_rise_deg=25.0) -> int | None:
    from .kinematics import line_turn, smooth

    s = lambda sec: int(round(sec * fps))
    with np.errstate(invalid="ignore"):
        sh = smooth(line_turn(img, sk, "shoulder"), fps, 0.1)
    a, b = max(0, impact - s(0.6)), impact - s(0.12)
    if b <= a or not np.isfinite(sh[a:b]).any():
        return None
    pk = a + int(np.nanargmax(sh[a:b]))
    lo = max(0, impact - s(1.1))                 # a groundstroke preparation takes 0.5-1 s
    if not np.isfinite(sh[lo:pk + 1]).any():
        return None
    base = float(np.nanmin(sh[lo:pk + 1]))
    rise = float(sh[pk]) - base
    if rise < min_rise_deg:
        return None
    idx = [i for i in range(lo, pk) if np.isfinite(sh[i]) and sh[i] <= base + 0.2 * rise]
    return idx[-1] if idx else None


def detect_phases(img: np.ndarray, body: np.ndarray, conf: np.ndarray, sk: Skeleton, fps: float,
                  height: float, impact: int, opponent_impact: int | None = None) -> list[Event]:
    """Detect the 8 moments for one stroke.

    img: image-space keypoints (T, K, 2); body: body-frame keypoints (see kinematics.to_body_frame);
    conf: keypoint confidences (T, K); impact: frame index of ball contact.
    """
    T = len(img)
    s = lambda sec: int(round(sec * fps))
    dw = sk["dom_wrist"]
    wrist_y = body[:, dw, 1]
    wv = _smooth(speed(body[:, dw], fps), max(1, s(0.06)))   # body-relative: pans and zooms cancel out
    events: dict[str, Event] = {}

    def conf_at(f, base):
        if f is None:
            return 0.0
        c = conf[f, [sk["dom_shoulder"], sk["dom_elbow"], dw, sk["left_hip"], sk["right_hip"]]]
        return float(round(base * np.nanmean(c), 2))

    # 3 loaded: end of the backswing = the wrist pause right before the forward swing.
    # Walk back from the forward-swing speed peak to the nearest local minimum. Defined on the
    # wrist rather than on the shoulder turn, whose 2D proxy depends on the camera angle.
    # The pause is a real slowdown (below 35 % of the forward-swing peak), not just any dip of a
    # noisy speed curve.
    # A forward swing never takes less than ~0.1 s (elite forehands: 0.15-0.3 s), so the pause is
    # looked for before that: a dip of the speed inside the blurred acceleration is not the pause.
    loaded = None
    fwd = _argext(wv, impact - s(0.25), impact + 2, np.nanargmax)
    if fwd is not None:
        lo = max(0, impact - s(0.8))
        hi = max(lo + 1, min(fwd, impact - max(2, s(0.1))))
        slow = np.flatnonzero(wv[lo:hi] <= 0.35 * wv[fwd])
        f = _walk_down(wv, lo + int(slow[-1]), lo) if len(slow) else _walk_down(wv, hi, lo)
        loaded = f if f < impact - 1 else None
    events["loaded"] = Event("loaded", loaded, "wrist_pause_before_forward_swing", conf_at(loaded, 0.9))

    # 2 takeback: before "loaded" the wrist went back (a backswing speed hump); its start is the
    # pause before that hump. Volleys and blocked returns may have no real backswing.
    takeback, method = None, "no_backswing"
    if loaded is not None:
        lo = max(0, loaded - s(0.8))
        back_pk = _walk_up(wv, loaded, lo)
        hump = wv[back_pk] - wv[loaded]
        if back_pk < loaded and hump > 0.25:                         # body heights per second
            slow = np.flatnonzero(wv[lo:back_pk + 1] < wv[loaded] + 0.25 * hump)
            takeback = lo + int(slow[-1]) if len(slow) else lo
            method = "wrist_starts_back"
    # The unit turn starts with the shoulders (ITF; Tennis Australia; CLAUDE.md: "empiezan a girar los
    # hombros"): with a fluid loop the wrist never pauses and its hump starts late (-0.3 s on TV
    # strokes, where the shoulders start at -0.5 to -0.85 s). The shoulder-line turn proxy, smoothed,
    # peaks 0.12-0.6 s before contact; the start is where it last sat within 20 % of its rise.
    sh_start = _shoulder_turn_start(img, sk, fps, impact)
    if sh_start is not None and (takeback is None or sh_start < takeback) and (loaded is None or sh_start < loaded):
        takeback, method = sh_start, "shoulders_start_turning"
    events["takeback"] = Event("takeback", takeback, method, conf_at(takeback, 0.8))

    # 1 ready / split step: hop landing around the opponent's hit, else before the takeback
    end = takeback if takeback is not None else (loaded if loaded is not None else impact - s(0.5))
    if opponent_impact is not None and opponent_impact < end:
        win = (opponent_impact - s(0.35), min(end, opponent_impact + s(0.45)))
    else:
        win = (end - s(0.7), end)   # the split step always comes before the takeback
    hop = detect_split_step(img, sk, height, fps, *win)
    if hop:
        events["ready"] = Event("ready", hop[0], "split_step_landing", conf_at(hop[0], 0.85))
    else:
        f = max(0, (takeback if takeback is not None else impact - s(0.6)) - s(0.25))
        events["ready"] = Event("ready", f, "fallback_before_takeback", conf_at(f, 0.3))

    # 4 acceleration: lowest point of the dominant wrist between loaded and contact
    acc = None
    if loaded is not None and impact - loaded > 2:
        acc = _argext(wrist_y, loaded, impact - 1, np.nanargmin)
        method = "wrist_low_point"
        if acc is not None and acc <= loaded + 1:      # no visible drop: use the speed ramp instead
            peak = np.nanmax(wv[loaded:impact + 1])
            ramp = np.flatnonzero(wv[loaded:impact + 1] >= 0.5 * peak)
            acc = loaded + int(ramp[0]) if len(ramp) else None
            method = "wrist_speed_ramp"
    events["acceleration"] = Event("acceleration", acc, method if acc is not None else "none", conf_at(acc, 0.7))

    events["impact"] = Event("impact", impact, "given", conf_at(impact, 1.0))
    ext = min(impact + max(1, s(0.05)), T - 1)
    events["extension"] = Event("extension", ext, "impact_plus_50ms", conf_at(ext, 0.8))

    # 7 finish: highest dominant wrist after contact, looked for from 0.12 s after it (on TV strokes
    # the highest point came at +0.02-0.06 s: a high contact is already high, and wrapped around the
    # neck the wrist is hidden from behind). If the wrist is not seen, where the swing stops (wrist
    # speed under 25 % of its forward-swing peak).
    fin, fmethod = _argext(wrist_y, impact + max(2, s(0.12)), impact + s(0.7), np.nanargmax), "wrist_high_point"
    if fin is None:
        fmethod = "wrist_stops_after_swing"
        pk_v = np.nanmax(wv[max(0, impact - s(0.25)):impact + 2]) if impact + 2 <= T else np.nan
        if np.isfinite(pk_v) and pk_v > 0:
            a = impact + max(2, s(0.12))
            stop = np.flatnonzero(wv[a:min(T, impact + s(0.7))] <= 0.25 * pk_v)
            fin = a + int(stop[0]) if len(stop) else None
    events["finish"] = Event("finish", fin, fmethod, conf_at(fin, 0.9))

    # 8 recovery: first clear foot movement after the finish (ankle spacing changes fast)
    rec = None
    if fin is not None:
        gap = np.abs(img[:, sk["left_ankle"], 0] - img[:, sk["right_ankle"], 0]) / height
        v = speed(gap, fps)
        start = fin + s(0.1)                  # the feet keep moving during the swing itself
        moving = np.flatnonzero(v[start:min(T, fin + s(0.8))] > 0.8)
        rec = start + int(moving[0]) if len(moving) else None
        if rec is None:
            rec = min(T - 1, fin + s(0.3))
            events["recovery"] = Event("recovery", rec, "fallback_after_finish", conf_at(rec, 0.3))
        else:
            events["recovery"] = Event("recovery", rec, "first_step", conf_at(rec, 0.8))
    else:
        events["recovery"] = Event("recovery", None, "none", 0.0)
    return [events[p] for p in PHASES]


CHAIN_FROM_S = 0.4      # the chain's peaks are looked for from 0.4 s before contact ...
CHAIN_TO_S = 0.04       # ... to 40 ms after it
CHAIN_SMOOTH_S = 0.1    # every signal smoothed over 100 ms (5 frames at 50 fps)


def kinetic_chain(img: np.ndarray, body: np.ndarray, sk: Skeleton, fps: float, start: int, impact: int, scale=None):
    """Kinetic chain from behind (27-10): the time of the peak unwinding speed of the hips, then the
    shoulders, then the arm, in seconds from contact.

    Hips and shoulders: the rate of change of the signed image width of the hip and shoulder lines (per
    body height; it grows while the line unwinds towards the net). The former angle, arccos of that
    width, multiplies the keypoint noise near square-on, which is where the body is at contact: on the
    193 near forehands of the 4 reference matches both rotations peaked at -60 ms, with the order right in
    10 % of them. With the width rate: hips -120 ms, shoulders -80 ms, arm -20 ms (medians), hips not
    after the shoulders in 72 % and shoulders not after the arm in 85 %. Arm: speed of the dominant wrist
    in the body frame (the hand at the end of the chain).

    Returns ({segment: s from contact}, order, resolved), segments "pelvis", "trunk", "arm". resolved is
    False when a segment is missing. The order is judged with one frame of tolerance (chain_in_order): the
    peaks are 40 ms (2 frames at 50 fps) apart, so a one-frame swap is noise, not a different chain."""
    T = len(img)
    lo, hi = max(0, impact - int(round(CHAIN_FROM_S * fps))), min(T, impact + int(round(CHAIN_TO_S * fps)) + 1)
    sig = chain_signals(img, body, sk, fps, scale)
    peaks = {}
    for name, x in sig.items():
        w = x[lo:hi]
        if hi - lo < 3 or np.all(np.isnan(w)) or np.nanmax(w) <= 0:
            continue
        peaks[name] = round((lo + int(np.nanargmax(w)) - impact) / fps, 3)
    order = sorted(peaks, key=peaks.get)
    return peaks, order, len(peaks) == 3


def chain_signals(img: np.ndarray, body: np.ndarray, sk: Skeleton, fps: float, scale=None) -> dict:
    """Per-frame speeds of the chain (kinetic_chain): hips and shoulders unwinding (rate of their signed
    image width per body height, + = towards the net) and the dominant wrist in the body frame."""
    from .kinematics import smooth

    T = len(img)
    h = np.asarray(scale, float) if scale is not None else np.full(T, 1.0)
    if h.ndim == 0:
        h = np.full(T, float(h))

    def width(joint):
        w = (img[:, sk[f"dom_{joint}"], 0] - img[:, sk[f"non_{joint}"], 0]) * sk.dom_sign / h
        return np.gradient(smooth(w, fps, CHAIN_SMOOTH_S)) * fps

    wr = smooth(body[:, sk["dom_wrist"]], fps, CHAIN_SMOOTH_S)
    return {"pelvis": width("hip"), "trunk": width("shoulder"),
            "arm": np.linalg.norm(np.gradient(wr, axis=0), axis=1) * fps}


def chain_in_order(peaks: dict, fps: float) -> bool | None:
    """Hips, then shoulders, then arm, with one frame of tolerance between neighbours; None when a peak
    is missing."""
    if not all(k in peaks for k in ("pelvis", "trunk", "arm")):
        return None
    tol = 1.0 / fps + 1e-6
    return peaks["pelvis"] <= peaks["trunk"] + tol and peaks["trunk"] <= peaks["arm"] + tol


def kinetic_chain_angles(img: np.ndarray, body: np.ndarray, sk: Skeleton, fps: float, start: int, impact: int, scale=None):
    """Former measure (until 27-10), kept for comparison: peak timing of segment rotation speeds between
    `start` and just after contact.

    Pelvis and trunk: the speed at which the hip and shoulder lines unwind (their turn away from
    the camera decreases during the forward swing). Arm and forearm: angular speed of the
    segment in the body frame. Every signal is smoothed over ~50 ms first: a raw 2D derivative
    peaks on single-frame jitter.

    Returns ({segment: seconds from impact of its peak}, order, resolved). resolved is False when
    two peaks fall on the same frame or a segment is missing: the order is then not judged.
    """
    from .kinematics import segment_angle, smooth

    sl = slice(max(0, start), min(len(img), impact + 3))
    sig = {
        "pelvis": -np.gradient(smooth(line_turn(img, sk, "hip", scale=scale), fps)) * fps,
        "trunk": -np.gradient(smooth(line_turn(img, sk, "shoulder", scale=scale), fps)) * fps,
        "upper_arm": np.abs(np.gradient(smooth(segment_angle(body[:, sk["dom_shoulder"]], body[:, sk["dom_elbow"]]), fps))) * fps,
        "forearm": np.abs(np.gradient(smooth(segment_angle(body[:, sk["dom_elbow"]], body[:, sk["dom_wrist"]]), fps))) * fps,
    }
    peaks, frames = {}, {}
    for name, x in sig.items():
        w = x[sl]
        if np.all(np.isnan(w)) or np.nanmax(w) <= 0:
            continue
        f = sl.start + int(np.nanargmax(w))
        frames[name] = f
        peaks[name] = round((f - impact) / fps, 3)
    order = sorted(peaks, key=peaks.get)
    resolved = len(frames) == 4 and len(set(frames.values())) == 4
    return peaks, order, resolved
