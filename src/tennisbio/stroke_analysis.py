"""Per-stroke analysis: phases, kinetic chain, body metrics and racket across the whole stroke."""
from dataclasses import asdict, dataclass, field

import numpy as np

from .kinematics import joint_angle, line_turn, to_body_frame
from .phases import PHASES, detect_phases, kinetic_chain
from .racket import pick_racket, racket_from_polygon
from .skeleton import Skeleton


@dataclass
class StrokeResult:
    impact_frame: int
    impact_source: str
    stroke: str                                  # "forehand" / "backhand"
    phases: dict = field(default_factory=dict)   # name -> {frame, t_rel, method, confidence}
    metrics: dict = field(default_factory=dict)
    racket: dict = field(default_factory=dict)   # name -> per-phase racket values
    racket_track: list = field(default_factory=list)
    ball: dict = field(default_factory=dict)   # bounce before contact (image px, s before contact)  # per frame in window: [t_rel, elevation, head_above_wrist_cm]
    chain: dict = field(default_factory=dict)
    review: list = field(default_factory=list)   # reasons to send to manual review

    def to_dict(self):
        return asdict(self)


def classify_side(body: np.ndarray, sk: Skeleton, f: int, fps: float = 30.0) -> str:
    """'overhead' (serve or smash) if the dominant wrist is above the head at contact; otherwise
    forehand or backhand by a vote of three cues, so that an impact frame off by one or two
    frames (wrist already crossing the body) does not flip the answer:
    - side of the dominant wrist during the backswing (0.45-0.15 s before contact),
    - direction of the swing across the body around contact (forehand: towards the non-dominant side),
    - side of the dominant wrist at contact (and both hands together → backhand)."""
    dw, nw = body[:, sk["dom_wrist"]], body[:, sk["non_wrist"]]
    # serve/smash: hand above the head AND the arm raised (elbow above the shoulder); a forehand
    # taken very high reaches the head height with the elbow at or below the shoulder
    el, sh = body[f, sk["dom_elbow"], 1], body[f, sk["dom_shoulder"], 1]
    arm_up = not (np.isfinite(el) and np.isfinite(sh)) or el > sh + 0.04
    if dw[f, 1] > body[f, sk["nose"], 1] + 0.03 and arm_up:
        return "overhead"
    s = sk.dom_sign
    votes = []
    back = dw[max(0, f - round(0.45 * fps)):max(1, f - round(0.15 * fps)), 0]
    if np.isfinite(back).any():
        votes.append(np.nanmedian(back) * s > 0)
    a, b = max(0, f - round(0.1 * fps)), min(len(dw) - 1, f + round(0.05 * fps))
    if b > a and np.isfinite(dw[[a, b], 0]).all() and abs(dw[b, 0] - dw[a, 0]) > 0.03:
        votes.append((dw[b, 0] - dw[a, 0]) * s < 0)
    if np.isfinite(dw[f, 0]):
        two_hands = np.linalg.norm(dw[f] - nw[f]) < 0.08
        votes.append(dw[f, 0] * s > 0 and not two_hands)
    return "forehand" if sum(votes) * 2 > len(votes) else "backhand"


def serve_events(body: np.ndarray, sk: Skeleton, fps: float, i: int) -> dict:
    """Overhead (serve) moments that replace the groundstroke ones: toss start (takeback),
    trophy (loaded: tossing hand at its highest), racket drop (acceleration: hitting hand at its
    lowest between trophy and contact)."""
    nw, dw = body[:, sk["non_wrist"], 1], body[:, sk["dom_wrist"], 1]
    lo, hi = max(0, i - int(1.2 * fps)), max(1, i - int(0.15 * fps))
    out = {}
    if np.isfinite(nw[lo:hi]).any():
        trophy = lo + int(np.nanargmax(nw[lo:hi]))
        out["loaded"] = trophy
        seg = nw[lo:trophy + 1]
        if np.isfinite(seg).any():                     # toss start: tossing hand at its lowest before the trophy
            out["takeback"] = lo + int(np.nanargmin(seg))
        if i - trophy > 2 and np.isfinite(dw[trophy:i]).any():
            out["acceleration"] = trophy + int(np.nanargmin(dw[trophy:i]))
    return out


def analyze_stroke(img: np.ndarray, conf: np.ndarray, sk: Skeleton, fps: float, height_px: float,
                   impact: int, impact_source: str, rackets: list | None = None, height_m: float = 1.84,
                   opponent_impact: int | None = None, window=(1.0, 0.8), scale=None) -> StrokeResult:
    """Analyse one stroke. img/conf cover the whole clip; work happens in a window around impact.

    The window reaches back to half a second before the opponent's hit when it is known (up to
    2.2 s), so the split step and long backswings are inside it whatever the ball speed.
    scale: body height in pixels per frame of the clip (kinematics.scale_track)."""
    pre = window[0]
    if opponent_impact is not None and opponent_impact < impact:
        pre = min(2.2, max(pre, (impact - opponent_impact) / fps + 0.5))
    a = max(0, impact - int(round(pre * fps)))
    b = min(len(img), impact + int(window[1] * fps) + 1)
    w_img, w_conf = img[a:b], conf[a:b]
    hs = np.full(b - a, float(height_px)) if scale is None else np.asarray(scale, float)[a:b]
    body = to_body_frame(w_img, sk, hs)
    i = impact - a
    opp = None if opponent_impact is None else opponent_impact - a
    cm = height_m * 100                               # body heights -> cm

    events = detect_phases(w_img, body, w_conf, sk, fps, float(np.median(hs)), i, opp)
    res = StrokeResult(impact_frame=impact, impact_source=impact_source, stroke=classify_side(body, sk, i, fps))
    if res.stroke == "overhead":
        from .phases import Event
        se = serve_events(body, sk, fps, i)
        events = [Event(e.name, se[e.name], {"loaded": "trophy_toss_arm_highest", "takeback": "toss_start",
                                               "acceleration": "racket_drop_wrist_lowest"}[e.name], 0.8)
                  if e.name in se else e for e in events]
    for e in events:
        res.phases[e.name] = dict(frame=None if e.frame is None else a + e.frame,
                                  t_rel=None if e.frame is None else round((e.frame - i) / fps, 3),
                                  method=e.method, confidence=e.confidence)
        if e.frame is None or e.confidence < 0.4:
            res.review.append(f"phase:{e.name}")
    if "audio" not in impact_source and "ball" not in impact_source:
        res.review.append("impact_without_audio")

    ev = {e.name: e.frame for e in events}
    sh, hp = line_turn(w_img, sk, "shoulder", scale=hs), line_turn(w_img, sk, "hip", scale=hs)
    g = lambda arr, f: None if f is None or np.isnan(arr[f]) else float(arr[f])
    dsh, del_, dw = sk["dom_shoulder"], sk["dom_elbow"], sk["dom_wrist"]
    elbow = joint_angle(body[:, dsh], body[:, del_], body[:, dw])
    feet_y = np.fmin(body[:, sk["left_ankle"], 1], body[:, sk["right_ankle"], 1])
    base = np.abs(body[:, sk["left_ankle"], 0] - body[:, sk["right_ankle"], 0])
    hip_h = -feet_y                       # hip height above the lower foot, body heights (scale-free)
    m = res.metrics
    m["shoulder_turn_loaded_deg"] = g(sh, ev["loaded"])
    m["hip_turn_loaded_deg"] = g(hp, ev["loaded"])
    if m["shoulder_turn_loaded_deg"] is not None and m["hip_turn_loaded_deg"] is not None:
        m["x_factor_deg"] = m["shoulder_turn_loaded_deg"] - m["hip_turn_loaded_deg"]
    m["elbow_impact_deg"] = g(elbow, i)
    non_elbow = joint_angle(body[:, sk["non_shoulder"]], body[:, sk["non_elbow"]], body[:, sk["non_wrist"]])
    m["non_elbow_impact_deg"] = g(non_elbow, i)                   # two-handed backhand: second arm
    m["non_arm_extension_loaded_deg"] = g(non_elbow, ev["loaded"])  # forehand: free arm in the loading
    if m["elbow_impact_deg"] is not None and m["elbow_impact_deg"] < 60:
        res.review.append("elbow_implausible_at_impact")   # usually a blurred or swapped arm keypoint
    m["contact_height_pct"] = None if np.isnan(body[i, dw, 1] - feet_y[i]) else float((body[i, dw, 1] - feet_y[i]) * 100)
    m["contact_lateral_pct"] = None if np.isnan(body[i, dw, 0]) else float(abs(body[i, dw, 0]) * 100)
    m["base_width_loaded_pct"] = None if ev["loaded"] is None else g(base * 100, ev["loaded"])
    if ev["ready"] is not None and ev["loaded"] is not None:
        d = hip_h[ev["ready"]] - hip_h[ev["loaded"]]
        m["hip_drop_pct"] = None if np.isnan(d) else float(d * 100)
    m["finish_wrist_height_pct"] = None if ev["finish"] is None else g(body[:, dw, 1] * 100, ev["finish"])
    k50 = max(1, int(round(0.05 * fps)))            # ±50 ms, whatever the frame rate
    n0, n1 = max(0, i - k50), min(len(body) - 1, i + k50)
    nose = body[:, sk["nose"]]                       # relative to the hips: running and panning cancel out
    m["head_motion_impact_cm"] = None if np.isnan(nose[[n0, n1]]).any() else float(np.linalg.norm(nose[n1] - nose[n0]) * cm)
    if res.stroke == "overhead" and ev["loaded"] is not None:
        t = ev["loaded"]
        ls, rs = body[t, sk["non_shoulder"]], body[t, sk["dom_shoulder"]]
        if not (np.isnan(ls).any() or np.isnan(rs).any()):     # + = tossing-side shoulder higher
            m["serve_shoulder_tilt_trophy_deg"] = float(np.degrees(np.arctan2(ls[1] - rs[1], abs(ls[0] - rs[0]))))
        m["serve_toss_arm_height_pct"] = g((body[:, sk["non_wrist"], 1] - feet_y) * 100, t)
        start = hip_h[:max(1, int(0.3 * fps))]
        if np.isfinite(start).any() and not np.isnan(hip_h[t]):
            m["serve_knee_bend_hip_drop_pct"] = float((np.nanmax(start) - hip_h[t]) * 100)
    for name in ("ready", "takeback", "loaded", "acceleration"):
        if ev[name] is not None:
            m[f"time_{name}_to_impact_s"] = round((i - ev[name]) / fps, 3)
    if ev["finish"] is not None:
        m["time_impact_to_finish_s"] = round((ev["finish"] - i) / fps, 3)

    peaks, order, resolved = kinetic_chain(w_img, body, sk, fps, ev["loaded"] if ev["loaded"] is not None else i - int(0.4 * fps),
                                           i, scale=hs)
    # the order is judged only when every segment has its own, separated peak
    res.chain = {"peaks_s": peaks, "order": order,
                 "proximal_to_distal": (order == ["pelvis", "trunk", "upper_arm", "forearm"]) if resolved else None}

    # racket through the whole window
    if rackets is not None:
        for f in range(len(w_img)):
            wrist = w_img[f, dw]
            poly = pick_racket(rackets[a + f], wrist, max_dist=0.25 * height_px)
            obs = racket_from_polygon(poly, wrist) if poly is not None else None
            if obs is None:
                res.racket_track.append([round((f - i) / fps, 3), None, None])
            else:
                above = (wrist[1] - obs.head[1]) / hs[f] * cm
                res.racket_track.append([round((f - i) / fps, 3), round(obs.elevation_deg, 1), round(float(above), 1)])
        for name in PHASES:
            f = ev[name]
            if f is None:
                continue
            t, el, above = res.racket_track[f]
            res.racket[name] = dict(detected=el is not None, elevation_deg=el, head_above_wrist_cm=above)
        if not res.racket.get("loaded", {}).get("detected"):
            res.review.append("racket_not_seen_when_loaded")
    return res
