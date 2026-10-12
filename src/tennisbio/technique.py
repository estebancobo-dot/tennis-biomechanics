"""The technique model of one stroke: every body part and the racket at each of the 8 moments,
plus timing, footwork and the classes that describe the variant of the stroke.

Units: lengths in % of her body height (scale tracked per frame, so moving towards the camera or
a zoom does not change them), angles in degrees, positions on the court in metres, times in
seconds relative to the impact. Lateral values are signed towards her dominant side (+), so a
left-hander reads the same as a right-hander.

Each descriptor has a reliability from the TV camera (behind and above the near player): see
DESCRIPTORS. Depth (towards / away from the camera) is invisible in 2D, so anything that depends
on it is marked low or left out.
"""
import math

import numpy as np

from .footwork import footwork
from .kinematics import joint_angle, line_turn, to_body_frame
from .skeleton import Skeleton

PHASES = ["ready", "takeback", "loaded", "acceleration", "impact", "extension", "finish", "recovery"]

# descriptor → (group, Spanish name, unit, reliability 1-3, description)
DESCRIPTORS = {
    # head and trunk
    "body_height": ("cuerpo", "Altura del cuerpo", "%", 3, "altura de la cabeza sobre el pie más bajo, % de su altura de pie"),
    "hip_height": ("piernas", "Altura de la cadera", "%", 3, "cadera sobre el pie más bajo, % de su altura"),
    "head_over_base": ("equilibrio", "Cabeza sobre la base", "%", 2, "cabeza respecto al centro de los pies (+ hacia su lado dominante), % de altura"),
    "head_vs_hips": ("equilibrio", "Cabeza respecto a la cadera", "%", 2, "lateral (+ lado dominante), % de altura"),
    "trunk_tilt": ("cuerpo", "Inclinación lateral del tronco", "°", 3, "eje cadera–hombros respecto a la vertical (+ hacia su lado dominante)"),
    "shoulder_tilt": ("cuerpo", "Inclinación de los hombros", "°", 3, "+ hombro dominante más bajo"),
    "hip_tilt": ("cuerpo", "Inclinación de la cadera", "°", 2, "+ cadera dominante más baja"),
    "shoulder_turn": ("cuerpo", "Giro de hombros", "°", 2, "0 = de espaldas a la cámara (paralelos a la red); 2D, solo magnitud"),
    "hip_turn": ("cuerpo", "Giro de cadera", "°", 2, "ídem"),
    "x_factor": ("cuerpo", "Separación hombros–cadera", "°", 2, "giro de hombros − giro de cadera"),
    "com_over_feet": ("equilibrio", "Peso entre los pies", "", 2, "centro de masas entre el pie dominante (0) y el otro (1)"),
    # legs
    "knee_dom": ("piernas", "Rodilla dominante", "°", 1, "ángulo 2D (180 = estirada); escorzo desde atrás"),
    "knee_non": ("piernas", "Rodilla no dominante", "°", 1, "ídem"),
    "base_width": ("piernas", "Anchura de la base", "%", 3, "distancia lateral entre tobillos, % de altura"),
    # arms
    "elbow_dom": ("brazo", "Codo dominante", "°", 2, "hombro–codo–muñeca (180 = estirado)"),
    "elbow_non": ("brazo", "Codo no dominante", "°", 2, "ídem"),
    "shoulder_abd_dom": ("brazo", "Separación del brazo dominante", "°", 2, "brazo respecto al tronco"),
    "shoulder_abd_non": ("brazo", "Separación del brazo libre", "°", 2, "ídem"),
    "wrist_dom_height": ("brazo", "Altura de la mano dominante", "%", 3, "sobre el pie más bajo, % de altura"),
    "wrist_dom_lateral": ("brazo", "Mano dominante, lateral", "%", 3, "respecto a la cadera (+ lado dominante)"),
    "wrist_dom_vs_shoulder": ("brazo", "Mano dominante respecto al hombro", "%", 3, "vertical (+ por encima)"),
    "wrist_dom_vs_hip": ("brazo", "Mano dominante respecto a la cadera", "%", 3, "vertical (+ por encima); en el impacto, altura del contacto respecto a la cadera"),
    "wrist_non_height": ("brazo", "Altura de la mano libre", "%", 3, "sobre el pie más bajo"),
    "wrist_non_lateral": ("brazo", "Mano libre, lateral", "%", 3, "respecto a la cadera (+ lado dominante)"),
    "hands_apart": ("brazo", "Separación entre manos", "%", 3, "pequeña = las dos manos en la raqueta"),
    "arm_extension": ("brazo", "Extensión del brazo dominante", "%", 2, "hombro–muñeca / longitud del brazo"),
    # racket (5 points, near side)
    "racket_head_vs_wrist": ("raqueta", "Cabeza de la raqueta respecto a la muñeca", "%", 1,
                             "vertical en la imagen (+ por encima); con la cámara inclinada, apuntar hacia la red también parece «arriba»"),
    "racket_angle": ("raqueta", "Inclinación de la raqueta", "°", 2, "eje empuñadura→punta respecto a la horizontal de la imagen"),
    "racket_forearm": ("raqueta", "Ángulo antebrazo–raqueta", "°", 2, "retraso de la muñeca (lag); 2D"),
    "racket_tip_height": ("raqueta", "Altura de la punta de la raqueta", "%", 2, "sobre el pie más bajo"),
    "face_tilt": ("raqueta", "Cierre de la cara", "°", 2, "+ cuerdas hacia el suelo; en el impacto es una estimación"),
    "face_yaw": ("raqueta", "Dirección de la cara", "°", 2, "0 = hacia la red"),
}
# per-stroke (not per phase)
STROKE_DESCRIPTORS = {
    "t_takeback": ("ritmo", "Inicio de la preparación", "s", 2, "antes del impacto"),
    "t_loaded": ("ritmo", "Armado completo", "s", 2, "antes del impacto"),
    "t_acceleration": ("ritmo", "Inicio de la aceleración", "s", 2, "antes del impacto"),
    "t_finish": ("ritmo", "Terminación", "s", 2, "después del impacto"),
    "dur_preparation": ("ritmo", "Duración de la preparación", "s", 2, "inicio de preparación → armado"),
    "dur_forward": ("ritmo", "Duración del swing hacia delante", "s", 2, "armado → impacto"),
    "tempo_ratio": ("ritmo", "Relación preparación / swing", "", 2, "duración de la preparación / del swing"),
    "takeback_after_opp": ("ritmo", "Preparación tras el golpe rival", "s", 2, "inicio de su preparación desde el golpe del rival"),
    "takeback_vs_bounce": ("ritmo", "Preparación respecto al bote", "s", 2, "− = empieza antes del bote"),
    "takeback_path": ("raqueta", "Recorrido de la mano en la preparación", "%", 2, "longitud del camino de la muñeca, % de altura"),
    "takeback_peak_vs_shoulder": ("raqueta", "Altura máxima de la mano en la preparación", "%", 2, "respecto al hombro (+ por encima)"),
    "swing_low_to_high": ("raqueta", "Trayectoria del swing (bajo → alto)", "°", 2, "dirección de la muñeca en los 100 ms previos al impacto"),
    "swing_rise_after": ("raqueta", "Subida tras el impacto", "%", 3, "subida de la muñeca en 150 ms tras el impacto"),
    "wrist_drop": ("raqueta", "Caída de la mano antes de acelerar", "%", 3, "del armado al punto más bajo"),
    "split_hop": ("pies", "Altura del split step", "%", 2, "salto, % de altura"),
    "loaded_vs_bounce": ("ritmo", "Armado completo respecto al bote", "s", 2, "− = ya armada cuando bota la bola"),
    "t_max_shoulder_turn": ("ritmo", "Máximo giro de hombros", "s", 2, "antes del impacto (élite ≈ 0,23 s, Landlinger 2010)"),
    "t_max_hip_turn": ("ritmo", "Máximo giro de cadera", "s", 2, "antes del impacto (élite ≈ 0,24 s, Landlinger 2010)"),
    "pause_at_loaded": ("ritmo", "Pausa en el armado", "s", 2, "mano casi quieta entre el armado y el swing"),
    "hand_on_handle": ("raqueta", "Mano en el mango", "%", 1, "distancia muñeca–final del mango, % de la longitud de la raqueta"),
    "racket_speed_rel": ("raqueta", "Velocidad de la raqueta (relativa)", "alt/s", 1, "punta antes y después del desenfoque, en alturas por segundo: solo para comparar sus golpes"),
}


def _deg(v):
    return None if v is None or not np.isfinite(v) else round(float(v), 1)


def _pct(v):
    return None if v is None or not np.isfinite(v) else round(float(v) * 100, 1)


def segment_ok(body: np.ndarray, sk: Skeleton, a: str, b: str, f: int, min_frac=0.65) -> bool:
    """False when the segment a→b points towards / away from the camera at frame f: its length in
    the image is then much shorter than its true length (its longest over the stroke), and any 2D
    angle using it is meaningless."""
    L = np.linalg.norm(body[:, sk[a]] - body[:, sk[b]], axis=-1)
    if not np.isfinite(L[f]) or not np.isfinite(L).any():
        return False
    return L[f] >= min_frac * np.nanpercentile(L, 95)


def posture(body: np.ndarray, img: np.ndarray, sk: Skeleton, f: int, scale: float) -> dict:
    """Body descriptors at frame f (body frame: hip centre, body heights, y up). Angles whose
    segments are foreshortened at that frame are left out."""
    q = body[f]
    seg = lambda a, b: segment_ok(body, sk, a, b, f)
    ds = sk.dom_sign
    j = lambda n: q[sk[n]]
    ok = lambda *ns: all(np.isfinite(q[sk[n]]).all() for n in ns)
    out = {}
    feet_y = np.nanmin([j("left_ankle")[1], j("right_ankle")[1]])
    if ok("nose") and np.isfinite(feet_y):
        out["body_height"] = _pct((j("nose")[1] - feet_y) * 1.08)          # nose → top of the head ≈ +8 %
    if np.isfinite(feet_y):
        out["hip_height"] = _pct(-feet_y)
    if ok("nose", "left_ankle", "right_ankle"):
        base_mid = (j("left_ankle")[0] + j("right_ankle")[0]) / 2
        out["head_over_base"] = _pct((j("nose")[0] - base_mid) * ds)
    if ok("nose"):
        out["head_vs_hips"] = _pct(j("nose")[0] * ds)
    sh_mid = (j("left_shoulder") + j("right_shoulder")) / 2
    if np.isfinite(sh_mid).all():
        out["trunk_tilt"] = _deg(math.degrees(math.atan2(sh_mid[0] * ds, sh_mid[1])))
    if ok("dom_shoulder", "non_shoulder") and seg("dom_shoulder", "non_shoulder"):     # not when side-on
        d = j("non_shoulder") - j("dom_shoulder")
        out["shoulder_tilt"] = _deg(math.degrees(math.atan2(d[1], abs(d[0]) + 1e-9)))     # + = dominant one lower
    if ok("dom_hip", "non_hip") and seg("dom_hip", "non_hip"):
        d = j("non_hip") - j("dom_hip")
        out["hip_tilt"] = _deg(math.degrees(math.atan2(d[1], abs(d[0]) + 1e-9)))
    # centre of mass from segment weights (Dempster, simplified), lateral, between the feet
    if ok("left_ankle", "right_ankle", "left_hip", "right_hip", "left_shoulder", "right_shoulder", "nose"):
        parts = [(j("nose"), .08), ((sh_mid + (j("left_hip") + j("right_hip")) / 2) / 2, .50)]
        for side in ("left", "right"):
            if ok(f"{side}_elbow"):
                parts.append((j(f"{side}_elbow"), .05))
            if ok(f"{side}_knee"):
                parts.append((j(f"{side}_knee"), .16))
        w = sum(p[1] for p in parts)
        cx = sum(p[0][0] * p[1] for p in parts) / w
        dfo, nfo = j("dom_ankle")[0], j("non_ankle")[0]
        if abs(nfo - dfo) > 0.04:
            out["com_over_feet"] = round(float(np.clip((cx - dfo) / (nfo - dfo), -0.5, 1.5)), 2)
    for side, key in (("dom", "knee_dom"), ("non", "knee_non")):
        if ok(f"{side}_hip", f"{side}_knee", f"{side}_ankle") and seg(f"{side}_hip", f"{side}_knee") and seg(f"{side}_knee", f"{side}_ankle"):
            out[key] = _deg(joint_angle(j(f"{side}_hip")[None], j(f"{side}_knee")[None], j(f"{side}_ankle")[None])[0])
    if ok("left_ankle", "right_ankle"):
        out["base_width"] = _pct(abs(j("left_ankle")[0] - j("right_ankle")[0]))
    trunk_axis = sh_mid                                                     # hips are the origin
    for side, ek, ak in (("dom", "elbow_dom", "shoulder_abd_dom"), ("non", "elbow_non", "shoulder_abd_non")):
        if ok(f"{side}_shoulder", f"{side}_elbow", f"{side}_wrist") and seg(f"{side}_shoulder", f"{side}_elbow") \
                and seg(f"{side}_elbow", f"{side}_wrist"):
            out[ek] = _deg(joint_angle(j(f"{side}_shoulder")[None], j(f"{side}_elbow")[None], j(f"{side}_wrist")[None])[0])
        if ok(f"{side}_shoulder", f"{side}_elbow") and np.isfinite(trunk_axis).all() and seg(f"{side}_shoulder", f"{side}_elbow"):
            down = -trunk_axis                                               # from the shoulders towards the hips
            arm = j(f"{side}_elbow") - j(f"{side}_shoulder")
            c = float(down @ arm / (np.linalg.norm(down) * np.linalg.norm(arm) + 1e-9))
            out[ak] = _deg(math.degrees(math.acos(np.clip(c, -1, 1))))
    if ok("dom_wrist") and np.isfinite(feet_y):
        out["wrist_dom_height"] = _pct(j("dom_wrist")[1] - feet_y)
        out["wrist_dom_vs_hip"] = _pct(j("dom_wrist")[1])                 # the hips are the origin
        out["wrist_dom_lateral"] = _pct(j("dom_wrist")[0] * ds)
        if ok("dom_shoulder"):
            out["wrist_dom_vs_shoulder"] = _pct(j("dom_wrist")[1] - j("dom_shoulder")[1])
    if ok("non_wrist") and np.isfinite(feet_y):
        out["wrist_non_height"] = _pct(j("non_wrist")[1] - feet_y)
        out["wrist_non_lateral"] = _pct(j("non_wrist")[0] * ds)
    if ok("dom_wrist", "non_wrist"):
        out["hands_apart"] = _pct(np.linalg.norm(j("dom_wrist") - j("non_wrist")))
    if ok("dom_shoulder", "dom_elbow", "dom_wrist"):
        L = np.linalg.norm(j("dom_elbow") - j("dom_shoulder")) + np.linalg.norm(j("dom_wrist") - j("dom_elbow"))
        out["arm_extension"] = _pct(np.linalg.norm(j("dom_wrist") - j("dom_shoulder")) / (L + 1e-9))
    return {k: v for k, v in out.items() if v is not None}


def racket_at(kps: dict, img: np.ndarray, sk: Skeleton, f: int, scale: float, feet_img_y: float, faces: dict | None,
              first_face: int | None) -> dict:
    """Racket descriptors at clip frame f from its 5 keypoints (0 tip, 1 throat, 2 butt, 3/4 sides)."""
    out = {}
    k = kps.get(str(f)) if kps else None
    w = img[f, sk["dom_wrist"]]
    if k is not None and np.isfinite(w).all():
        k = np.asarray(k, float)
        tip, butt = k[0], k[2]
        head = (k[0] + k[1]) / 2
        out["racket_head_vs_wrist"] = _pct((w[1] - head[1]) / scale)
        d = tip - butt
        out["racket_angle"] = _deg(math.degrees(math.atan2(-d[1], abs(d[0]) + 1e-9)))
        e = img[f, sk["dom_elbow"]]
        if np.isfinite(e).all():
            fa = w - e
            c = float(fa @ d / (np.linalg.norm(fa) * np.linalg.norm(d) + 1e-9))
            out["racket_forearm"] = _deg(math.degrees(math.acos(np.clip(c, -1, 1))))
        if np.isfinite(feet_img_y):
            out["racket_tip_height"] = _pct((feet_img_y - tip[1]) / scale)
    if faces and first_face is not None:
        i = f - first_face
        if 0 <= i < len(faces.get("tilt", [])):
            if faces["tilt"][i] is not None:
                out["face_tilt"] = _deg(faces["tilt"][i])
            if faces["yaw"][i] is not None:
                out["face_yaw"] = _deg(faces["yaw"][i])
            if faces["label"][i]:
                out["face_points_to"] = faces["label"][i]
                out["face_observed"] = bool(faces["observed"][i])
    return {k: v for k, v in out.items() if v is not None}


def stance_class(dom: np.ndarray, non: np.ndarray, stroke: str, dom_sign: int) -> tuple[str, float]:
    """4 stances from the feet on the court (see court_metrics.stance: one definition everywhere)."""
    from .court_metrics import stance

    kind, a = stance(dom, non, stroke, dom_sign)
    return kind, round(a, 1)


def finish_class(body: np.ndarray, sk: Skeleton, f: int, racket: dict, stroke: str = "forehand") -> str | None:
    """Where the swing ends: over the shoulder, around the body, windshield-wiper or reverse."""
    q = body[f]
    w, ns, ds_ = q[sk["dom_wrist"]], q[sk["non_shoulder"]], q[sk["dom_shoulder"]]
    if not (np.isfinite(w).all() and np.isfinite(ns).all() and np.isfinite(ds_).all()):
        return None
    lat = w[0] * sk.dom_sign                        # + = still on her dominant side
    above_sh = w[1] - max(ns[1], ds_[1])
    if stroke == "backhand":                        # a backhand ends on her dominant side: mirrored,
        lat = -lat                                  # and it has no "reverse" finish
        if lat > -0.03:
            return "corta (delante)"
        return "sobre el hombro" if above_sh > -0.03 else "baja"
    if lat > 0.05 and above_sh > 0.08:
        return "invertida"                          # reverse / buggy whip: ends above the head, on the hitting side
    if lat > -0.03:
        return "limpiaparabrisas"                   # wrist stays in front, the racket turns over
    if above_sh > -0.03:
        return "sobre el hombro"
    return "alrededor del cuerpo"


def situation(m: dict, court_pos, displacement, t_avail, contact_h, dom_sign: int) -> dict:
    """Detailed situation of the ball she receives and of her position (classes used by the model)."""
    out = {}
    if t_avail is not None:
        out["ball_speed"] = "muy rápida" if t_avail < 0.9 else "rápida" if t_avail < 1.15 else "media" if t_avail < 1.5 else "lenta"
    if contact_h is not None:
        out["ball_height"] = ("rodilla" if contact_h < 35 else "cadera" if contact_h < 50 else "cintura-pecho" if contact_h < 65
                              else "pecho-hombro" if contact_h < 80 else "por encima del hombro")
    if court_pos is not None:
        x, y = court_pos
        out["depth"] = ("dentro de la pista" if y > 0.5 else "sobre la línea" if y > -0.5 else "1-2 m detrás" if y > -2
                        else "2-4 m detrás" if y > -4 else "muy atrás")
        lat = x * dom_sign
        out["court_side"] = "lado de su derecha" if lat > 0.5 else "lado de su revés" if lat < -0.5 else "centro"
    if displacement is not None:
        out["width"] = "centrada" if displacement < 1.2 else "abierta" if displacement < 2.6 else "muy abierta"
    defence = ((t_avail is not None and t_avail < 0.9) or (displacement or 0) > 3.0
               or (court_pos is not None and court_pos[1] < -3.5 and (t_avail or 9) < 1.2))
    attack = ((court_pos is not None and court_pos[1] > 0.5) or
              (contact_h is not None and contact_h > 60 and (t_avail or 0) > 1.3 and (displacement or 0) < 1.5))
    out["intent"] = "defensa" if defence else "ataque" if attack else "neutra"
    return out


def stroke_technique(img: np.ndarray, conf: np.ndarray, sk: Skeleton, fps: float, scale: np.ndarray, impact: int,
                     phases: dict, stroke: str, H: np.ndarray | None = None, opp: int | None = None,
                     bounce: int | None = None, faces: dict | None = None, split_hop: float | None = None,
                     context: dict | None = None) -> dict:
    """Everything that describes one stroke. phases: {name: clip frame or None}."""
    body = to_body_frame(img, sk, scale)
    T = len(img)
    ev = {p: (phases.get(p) if phases.get(p) is not None and 0 <= phases.get(p) < T else None) for p in PHASES}
    kps = (faces or {}).get("keypoints") or {}
    first_face = (faces or {}).get("first")
    out = {"phases": {}, "stroke": {}, "classes": {}, "footwork": {}}
    sh = line_turn(img, sk, "shoulder", scale=scale)
    hp = line_turn(img, sk, "hip", scale=scale)
    for p, f in ev.items():
        if f is None:
            continue
        d = posture(body, img, sk, f, float(scale[f]))
        if np.isfinite(sh[f]):
            d["shoulder_turn"] = _deg(sh[f])
        if np.isfinite(hp[f]):
            d["hip_turn"] = _deg(hp[f])
        if "shoulder_turn" in d and "hip_turn" in d and p in ("takeback", "loaded", "acceleration"):
            d["x_factor"] = round(d["shoulder_turn"] - d["hip_turn"], 1)     # meaningful only while coiled
        fy = np.nanmax(img[f, [sk["left_ankle"], sk["right_ankle"]], 1])
        d.update(racket_at(kps, img, sk, f, float(scale[f]), fy, faces, first_face))
        out["phases"][p] = d
        # the pose itself, hip-centred, in body heights, dominant side to the right (+x): averaged
        # over strokes it gives the "mean skeleton" of each moment
        q = body[f] * np.array([sk.dom_sign, 1.0])
        if sk.dom_sign < 0:                       # left-hander: swap left/right joints so "right" = dominant
            q = q[[0, 2, 1, 4, 3, 6, 5, 8, 7, 10, 9, 12, 11, 14, 13, 16, 15]]
        out.setdefault("pose", {})[p] = [None if not np.isfinite(v).all() else [round(float(v[0]), 3), round(float(v[1]), 3)]
                                         for v in q]
    # timing
    s = out["stroke"]
    for p in ("takeback", "loaded", "acceleration"):
        if ev[p] is not None:
            s[f"t_{p}"] = round((impact - ev[p]) / fps, 3)
    if ev["finish"] is not None:
        s["t_finish"] = round((ev["finish"] - impact) / fps, 3)
    if ev["takeback"] is not None and ev["loaded"] is not None:
        s["dur_preparation"] = round((ev["loaded"] - ev["takeback"]) / fps, 3)
    if ev["loaded"] is not None:
        s["dur_forward"] = round((impact - ev["loaded"]) / fps, 3)
        if s.get("dur_preparation"):
            s["tempo_ratio"] = round(s["dur_preparation"] / max(s["dur_forward"], 1e-3), 2)
    if ev["takeback"] is not None and opp is not None:
        s["takeback_after_opp"] = round((ev["takeback"] - opp) / fps, 3)
    if ev["takeback"] is not None and bounce is not None:
        s["takeback_vs_bounce"] = round((ev["takeback"] - bounce) / fps, 3)
    dw, dsh = body[:, sk["dom_wrist"]], body[:, sk["dom_shoulder"]]
    if ev["takeback"] is not None and ev["loaded"] is not None and ev["loaded"] > ev["takeback"]:
        seg = dw[ev["takeback"]:ev["loaded"] + 1]
        seg = seg[np.isfinite(seg).all(axis=1)]
        if len(seg) > 1:
            s["takeback_path"] = _pct(np.sum(np.linalg.norm(np.diff(seg, axis=0), axis=1)))
        rel = (dw[ev["takeback"]:ev["loaded"] + 1, 1] - dsh[ev["takeback"]:ev["loaded"] + 1, 1])
        if np.isfinite(rel).any():
            s["takeback_peak_vs_shoulder"] = _pct(np.nanmax(rel))
    k = max(1, int(round(0.1 * fps)))
    a = impact - k
    if a >= 0 and np.isfinite(dw[[a, impact]]).all():
        dv = dw[impact] - dw[a]
        s["swing_low_to_high"] = _deg(math.degrees(math.atan2(dv[1], abs(dv[0]) + 1e-9)))
    k2 = max(1, int(round(0.15 * fps)))
    if impact + k2 < T and np.isfinite(dw[[impact, impact + k2], 1]).all():
        s["swing_rise_after"] = _pct(dw[impact + k2, 1] - dw[impact, 1])
    if ev["loaded"] is not None and ev["acceleration"] is not None and np.isfinite(dw[[ev["loaded"], ev["acceleration"]], 1]).all():
        s["wrist_drop"] = _pct(dw[ev["loaded"], 1] - dw[ev["acceleration"], 1])
    if split_hop is not None:
        s["split_hop"] = _pct(split_hop)
    lo = ev["takeback"] if ev["takeback"] is not None else max(0, impact - int(0.8 * fps))
    for key, sig in (("t_max_shoulder_turn", sh), ("t_max_hip_turn", hp)):
        w = sig[lo:impact + 1]
        if np.isfinite(w).sum() >= 3:
            s[key] = round((impact - (lo + int(np.nanargmax(w)))) / fps, 3)
    if ev["loaded"] is not None and bounce is not None:
        s["loaded_vs_bounce"] = round((ev["loaded"] - bounce) / fps, 3)
    if ev["loaded"] is not None:                 # how long the hand stays (almost) still at the end of the backswing
        from .kinematics import smooth, speed
        wv = smooth(speed(dw, fps), fps, 0.06)
        if np.isfinite(wv[ev["loaded"]:impact + 1]).any():
            thr = 0.3 * np.nanmax(wv[ev["loaded"]:impact + 1])
            a = b = ev["loaded"]
            lo_p = ev["takeback"] if ev["takeback"] is not None else max(0, ev["loaded"] - int(0.4 * fps))
            while a - 1 >= lo_p and np.isfinite(wv[a - 1]) and wv[a - 1] < thr:
                a -= 1
            while b + 1 < impact and np.isfinite(wv[b + 1]) and wv[b + 1] < thr:
                b += 1
            if a > lo_p or ev["takeback"] is not None:     # otherwise the stillness is the ready position
                s["pause_at_loaded"] = round((b - a + 1) / fps, 3)
    # racket: hand position on the handle and relative speed of the tip around the blur
    if kps:
        ratios, tips = [], {}
        for key, k in kps.items():
            f = int(key)
            if not 0 <= f < T:
                continue
            k = np.asarray(k, float)
            tips[f] = k[0]
            w = img[f, sk["dom_wrist"]]
            L = np.linalg.norm(k[0] - k[2])
            if np.isfinite(w).all() and L > 0.08 * scale[f]:               # racket seen long, not end-on
                ratios.append(np.linalg.norm(w - k[2]) / L)
        if len(ratios) >= 3:
            s["hand_on_handle"] = _pct(float(np.median(ratios)))
        before = [f for f in tips if impact - int(0.25 * fps) <= f < impact]
        after = [f for f in tips if impact < f <= impact + int(0.25 * fps)]
        if before and after:
            f0, f1 = max(before), min(after)
            d = np.linalg.norm(tips[f1] - tips[f0]) / np.mean(scale[[f0, f1]])
            s["racket_speed_rel"] = round(float(d / ((f1 - f0) / fps)), 2)
    s = {k: v for k, v in s.items() if v is not None}
    out["stroke"] = s
    # classes
    c = out["classes"]
    fin = ev["finish"]
    if fin is not None:
        fc = finish_class(body, sk, fin, out["phases"].get("finish", {}), stroke)
        if fc:
            c["finish"] = fc
    lh = s.get("swing_low_to_high")
    if lh is not None:                    # the swing path just before contact says the spin she gives
        c["swing"] = "liftado (de abajo arriba)" if lh > 20 else "cortado (de arriba abajo)" if lh < -5 else "plano"
    e = out["phases"].get("impact", {}).get("elbow_dom")
    if e is not None:
        c["arm"] = "brazo recto" if e >= 150 else "doble flexión" if e < 135 else "intermedio"
    tp = s.get("takeback_path")
    ld = out["phases"].get("loaded", {})
    if tp is not None:
        hi = s.get("takeback_peak_vs_shoulder", -99)
        c["takeback"] = ("compacta" if tp < 35 else "en bucle alto" if hi > 5 else "amplia")
    if ld.get("face_tilt") is not None and ld["face_tilt"] > 45 and ld.get("racket_head_vs_wrist", 0) > 0:
        c["takeback_face"] = "cara al suelo (pat the dog)"
    elif ld.get("face_tilt") is not None:
        c["takeback_face"] = "cara cerrada" if ld["face_tilt"] > 10 else "cara abierta" if ld["face_tilt"] < -10 else "cara vertical"
    fn = out["phases"].get("finish", {})
    if fn.get("shoulder_abd_dom") is not None and fn.get("elbow_dom") is not None:
        c["finish_3x90"] = bool(abs(fn["shoulder_abd_dom"] - 90) <= 25 and abs(fn["elbow_dom"] - 90) <= 30)
    rd = out["phases"].get("ready", {})
    if "hands_apart" in rd:
        c["ready_hands"] = "dos manos en la raqueta" if rd["hands_apart"] < 12 else "mano libre separada"
    if H is not None:
        from .footwork import feet_track
        fw = footwork(img, sk, H, scale, fps, impact, opp, ev["ready"] if (context or {}).get("split") else None,
                      ev["finish"], ev["loaded"], (context or {}).get("surface", ""), (context or {}).get("next_opp"), stroke)
        out["footwork"] = fw
        if fw.get("movement"):
            c["movement"] = fw["movement"]
        # feet_at_impact is kept in the footwork data but not used as a class: at 50 fps the ankle
        # keypoints jitter enough to look like a moving foot (user's PC: 8 of 10 "no foot still")
        ft = feet_track(img, sk, H)
        for p in ("loaded", "impact"):
            f = ev[p]
            if f is not None and np.isfinite(ft[f]).all():
                kind, ang = stance_class(ft[f, 0], ft[f, 1], stroke, sk.dom_sign)
                c[f"stance_{p}"] = kind
                out["phases"][p]["stance_angle"] = ang
                out["phases"][p]["base_m"] = round(float(np.linalg.norm(ft[f, 0] - ft[f, 1])), 2)
        if fw.get("moves_to_net"):
            c["approach"] = True
        if fw.get("move_direction"):
            c["move_direction"] = fw["move_direction"]
    if context:
        c.update(situation(out, context.get("court_pos"), context.get("displacement"), context.get("t_avail"),
                           context.get("contact_h"), sk.dom_sign))
        if context.get("shot_direction") and c.get("court_side") == "lado de su revés" and stroke == "forehand":
            c["shot_type"] = "invertida cruzada" if context["shot_direction"] == "cruzada" else "invertida paralela" \
                if context["shot_direction"] == "paralela" else "invertida al centro"
        elif context.get("shot_direction"):
            c["shot_type"] = context["shot_direction"]
        if context.get("return") is not None:
            c["play"] = "resto" if context["return"] else "inicio del punto"      # refined later with its shot number
        # role of the stance (Martin et al. 2021): open attacking / open defensive / neutral attacking
        st_ = c.get("stance_impact")
        if st_:
            fast_run = c.get("movement") in ("en carrera", "deslizando") or c.get("intent") == "defensa"
            c["stance_role"] = (f"{st_} defensivo" if st_ in ("abierto", "semiabierto") and fast_run else
                                f"{st_} de ataque" if c.get("intent") == "ataque" or st_ in ("neutro", "cerrado") else
                                f"{st_} neutro")
    return out


def flatten(tech: dict) -> dict:
    """{"loaded.shoulder_turn": 85.0, "stroke.dur_forward": 0.31, "footwork.steps_to_impact": 4, ...}
    (numbers only), for the statistics of the model."""
    out = {}
    for p, d in (tech.get("phases") or {}).items():
        for k, v in d.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out[f"{p}.{k}"] = v
    for k, v in (tech.get("stroke") or {}).items():
        out[f"stroke.{k}"] = v
    for k, v in (tech.get("footwork") or {}).items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[f"footwork.{k}"] = v
    return out
