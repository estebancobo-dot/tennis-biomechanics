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
    racket_track: list = field(default_factory=list)  # per frame in window: [t_rel, elevation, head_above_wrist_cm]
    chain: dict = field(default_factory=dict)
    review: list = field(default_factory=list)   # reasons to send to manual review

    def to_dict(self):
        return asdict(self)


def classify_side(body: np.ndarray, sk: Skeleton, f: int) -> str:
    """Forehand if contact is on the dominant side of the body, backhand otherwise."""
    dw, nw = body[f, sk["dom_wrist"]], body[f, sk["non_wrist"]]
    two_hands = np.linalg.norm(dw - nw) < 0.08
    on_dom_side = dw[0] * sk.dom_sign > 0
    return "forehand" if on_dom_side and not two_hands else "backhand"


def analyze_stroke(img: np.ndarray, conf: np.ndarray, sk: Skeleton, fps: float, height_px: float,
                   impact: int, impact_source: str, rackets: list | None = None, height_m: float = 1.84,
                   opponent_impact: int | None = None, window=(1.0, 0.8)) -> StrokeResult:
    """Analyse one stroke. img/conf cover the whole clip; work happens in a window around impact."""
    a = max(0, impact - int(window[0] * fps))
    b = min(len(img), impact + int(window[1] * fps) + 1)
    w_img, w_conf = img[a:b], conf[a:b]
    body = to_body_frame(w_img, sk, height_px)
    i = impact - a
    opp = None if opponent_impact is None else opponent_impact - a
    cm = height_m * 100                               # body heights -> cm

    events = detect_phases(w_img, body, w_conf, sk, fps, height_px, i, opp)
    res = StrokeResult(impact_frame=impact, impact_source=impact_source, stroke=classify_side(body, sk, i))
    for e in events:
        res.phases[e.name] = dict(frame=None if e.frame is None else a + e.frame,
                                  t_rel=None if e.frame is None else round((e.frame - i) / fps, 3),
                                  method=e.method, confidence=e.confidence)
        if e.frame is None or e.confidence < 0.4:
            res.review.append(f"phase:{e.name}")
    if impact_source != "audio+swing":
        res.review.append("impact_without_audio")

    ev = {e.name: e.frame for e in events}
    sh, hp = line_turn(w_img, sk, "shoulder"), line_turn(w_img, sk, "hip")
    g = lambda arr, f: None if f is None or np.isnan(arr[f]) else float(arr[f])
    dsh, del_, dw = sk["dom_shoulder"], sk["dom_elbow"], sk["dom_wrist"]
    elbow = joint_angle(body[:, dsh], body[:, del_], body[:, dw])
    feet_y = np.fmin(body[:, sk["left_ankle"], 1], body[:, sk["right_ankle"], 1])
    base = np.abs(body[:, sk["left_ankle"], 0] - body[:, sk["right_ankle"], 0])
    hip_y_img = (w_img[:, sk["left_hip"], 1] + w_img[:, sk["right_hip"], 1]) / 2
    m = res.metrics
    m["shoulder_turn_loaded_deg"] = g(sh, ev["loaded"])
    m["hip_turn_loaded_deg"] = g(hp, ev["loaded"])
    if m["shoulder_turn_loaded_deg"] is not None and m["hip_turn_loaded_deg"] is not None:
        m["x_factor_deg"] = m["shoulder_turn_loaded_deg"] - m["hip_turn_loaded_deg"]
    m["elbow_impact_deg"] = g(elbow, i)
    if m["elbow_impact_deg"] is not None and m["elbow_impact_deg"] < 60:
        res.review.append("elbow_implausible_at_impact")   # usually a blurred or swapped arm keypoint
    m["contact_height_pct"] = None if np.isnan(body[i, dw, 1] - feet_y[i]) else float((body[i, dw, 1] - feet_y[i]) * 100)
    m["contact_lateral_pct"] = None if np.isnan(body[i, dw, 0]) else float(abs(body[i, dw, 0]) * 100)
    m["base_width_loaded_pct"] = None if ev["loaded"] is None else g(base * 100, ev["loaded"])
    if ev["ready"] is not None and ev["loaded"] is not None:
        m["hip_drop_pct"] = float((hip_y_img[ev["loaded"]] - hip_y_img[ev["ready"]]) / height_px * 100)
    m["finish_wrist_height_pct"] = None if ev["finish"] is None else g(body[:, dw, 1] * 100, ev["finish"])
    n0, n1 = max(0, i - 2), min(len(body) - 1, i + 2)
    nose = w_img[:, sk["nose"]]
    m["head_motion_impact_cm"] = None if np.isnan(nose[[n0, n1]]).any() else float(np.linalg.norm(nose[n1] - nose[n0]) / height_px * cm)
    for name in ("ready", "takeback", "loaded", "acceleration"):
        if ev[name] is not None:
            m[f"time_{name}_to_impact_s"] = round((i - ev[name]) / fps, 3)
    if ev["finish"] is not None:
        m["time_impact_to_finish_s"] = round((ev["finish"] - i) / fps, 3)

    peaks, order = kinetic_chain(w_img, body, sk, fps, ev["loaded"] if ev["loaded"] is not None else i - int(0.4 * fps), i)
    res.chain = {"peaks_s": peaks, "order": order,
                 "proximal_to_distal": order == [s for s in ["pelvis", "trunk", "upper_arm", "forearm"] if s in order]}

    # racket through the whole window
    if rackets is not None:
        for f in range(len(w_img)):
            wrist = w_img[f, dw]
            poly = pick_racket(rackets[a + f], wrist, max_dist=0.25 * height_px)
            obs = racket_from_polygon(poly, wrist) if poly is not None else None
            if obs is None:
                res.racket_track.append([round((f - i) / fps, 3), None, None])
            else:
                above = (wrist[1] - obs.head[1]) / height_px * cm
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
