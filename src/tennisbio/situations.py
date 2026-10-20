"""Situations of a stroke the user asked for by name (plan block 3; register #132, #157-#159, #16).

Each one is a class of the stroke built only from what the stroke already has (her feet on the court at
the impact through the homography, where her ball bounced on the far court, the height of her hand at
the impact, the bounce of the incoming ball, the shape of her swing). When a signal is missing the class
is None: never guessed. Court frame: her own (her baseline at y = 0, the net at y = 11.885 m, x + = her
right), the same for the near and the far player.

- shot_angle («Golpe angulado», #132): «angulado» when her ball
    * was in (`shot_in` True; an out ball or an unknown one gives None),
    * bounced short: no deeper than the far service line (bounce y ≤ NET + 6.40 = 18.285 m), and
    * near the sideline: in the outer third of the half-court width (|bounce x| ≥ 2/3 × 4.115 = 2.743 m,
      i.e. within 1.37 m of the singles sideline: half of the side third of `court_metrics.shot_landing`,
      which splits the whole width in thirds of 2.74 m), and
    * crossed the court: from the centre (|her x| ≤ 1.0 m, the band where `shot_landing` gives no
      direction) or to the side opposite to the one she hit from (a cross-court ball).
  «no angulado» when the same signals are known and one of the three conditions fails (a short ball
  down the line is not an angle). Bounce on the far court: the homography is exact on the ground, its
  error is that of the ball's image position (≈ 0.3-0.5 m at that distance), small next to 1.37 m.

- net_ball («Bola corta cerca de la red», #157, #158): she hit a ball that bounced on her side (a bounce
  was seen: a volley is not a short ball) with her feet at most 1 m behind the service line (court y ≥
  5.485 − 1.00 = 4.485 m from her baseline, ≤ 7.40 m from the net). 1 m: the contact is in front of the
  feet and the feet are measured to ±0.3 m. Its level is the height of the contact with the boundaries of
  the class `ball_height` (technique.height_class) grouped as in the report: «baja» = knee (< 35 % of her
  height), «alta» = chest-shoulder or above (≥ 65 %), «a media altura» in between. The video library's
  «cerca de la red» uses the same boundary (`near_net`; before 20-10 it was 8 m from the net).

- contact_type (technique.contact_type), two new levels for the impacts with no bounce on her side
  behind the service line (before, they had no class), #159 and «volea fuera de la línea de saque»:
    * the ball was followed before the impact (else a bounce the ball tracker did not see would make a
      volley out of a normal stroke): over the frames where `ball.bounce_before` looks for the bounce,
      the ball was seen in ≥ 70 % of them and never lost for more than 0.12 s (2 × the 0.06 s each side
      that the bounce detector needs: a bounce in a shorter gap still turns the path it measures);
    * her feet between 0.5 m behind her baseline (the «sobre la línea» band of `depth`) and the service
      line (5.485 m from her baseline; technique.SERVICE_LINE_M, which until 20-10 was wrongly 6.40 m);
    * the hand at the contact at or above 45 % of her height (the half-volley boundary): lower, the ball
      may have bounced too close to the impact for the tracker to see it (`ball.min_bounce_to_impact_s`),
      a half volley, so no class;
    * «volea de fondo a media pista» when the swing is that of a groundstroke (`groundstroke_swing`:
      a preparation that is not compact, hand path ≥ 35 % of her height, and a full finish, not the
      short one in front of her below the shoulder that `returns` calls a short finish); otherwise
      «volea fuera de la línea de saque». The grip itself is not visible from TV (20-40 px hand): the
      groundstroke swing is what is measured.

- half volley («media volea», #16): unchanged rule (technique.half_volley: bounce < 0.15 s before the
  impact and hand < 45 % of her height), shared now by the class and the review flag. The tracker cannot
  see a bounce closer to the impact than `ball.min_bounce_to_impact_s` (0.06 s at 50 fps, 0.08 s at 25),
  which is why the audit says how many candidates there are and not only how many classes.

`apply(d)` writes shot_angle and net_ball into a stroke of strokes.json (technique.classes); the fine pass
calls it, and the report and the audit call it on strokes analysed before (without overwriting).
"""
from __future__ import annotations

from .technique import SERVICE_FROM_NET_M, SERVICE_LINE_M, contact_type, height_class

NET_Y = 11.885                       # her frame: her baseline at y = 0
SINGLES_HALF = 4.115
FAR_SERVICE_Y = NET_Y + SERVICE_FROM_NET_M     # 18.285 m: the far service line
ANGLE_WIDE_M = 2 * SINGLES_HALF / 3  # 2.743 m: the outer third of the half-court width
CENTRE_X_M = 1.0                     # court_metrics.shot_landing: no direction from |x| ≤ 1 m
NEAR_NET_Y_M = SERVICE_LINE_M - 1.0  # 4.485 m from her baseline (7.40 m from the net)
LOW_LEVELS = ("rodilla",)
HIGH_LEVELS = ("pecho-hombro", "por encima del hombro")
NET_BALL_LEVELS = ("corta baja cerca de la red", "corta a media altura cerca de la red", "corta alta cerca de la red")
ANGLE_LEVELS = ("angulado", "no angulado")


def angled_shot(court_pos, shot_bounce, shot_in) -> str | None:
    """«angulado» / «no angulado» from where she hit (court_pos: [x, y] of her feet) and where her ball
    bounced (shot_bounce: [x, y] on the far court, her frame). None when either is unknown or the ball
    was not in."""
    if court_pos is None or shot_bounce is None or shot_in is not True:
        return None
    try:
        px, bx, by = float(court_pos[0]), float(shot_bounce[0]), float(shot_bounce[1])
    except (TypeError, ValueError, IndexError):
        return None
    short = by <= FAR_SERVICE_Y + 1e-9
    wide = abs(bx) >= ANGLE_WIDE_M - 1e-9
    crosses = abs(px) <= CENTRE_X_M + 1e-9 or (bx > 0) != (px > 0)
    return "angulado" if short and wide and crosses else "no angulado"


def near_net(court_pos) -> bool | None:
    """Her feet at the impact at most 1 m behind the service line (None when unknown)."""
    if court_pos is None:
        return None
    try:
        return float(court_pos[1]) >= NEAR_NET_Y_M - 1e-9
    except (TypeError, ValueError, IndexError):
        return None


def net_ball(court_pos, contact_h, bounced: bool | None) -> str | None:
    """Short ball near the net: low / medium / high, or None (not near the net, no bounce seen, or a
    signal missing). contact_h: hand height at the impact, % of her height."""
    nn = near_net(court_pos)
    if not nn or bounced is not True:
        return None
    hc = height_class(contact_h)
    if hc is None:
        return None
    return NET_BALL_LEVELS[0] if hc in LOW_LEVELS else NET_BALL_LEVELS[2] if hc in HIGH_LEVELS else NET_BALL_LEVELS[1]


def groundstroke_swing(classes: dict, finish_wrist_vs_shoulder) -> bool | None:
    """True when the swing is that of a groundstroke (preparation not compact and a full finish), False
    for a compact preparation or a short finish, None when the shape of the swing was not measured."""
    from .returns import FINISH_SHOULDER_PCT, SHORT_FINISH

    tb, fin = (classes or {}).get("takeback"), (classes or {}).get("finish")
    if tb is None:
        return None
    if tb == "compacta":
        return False
    if fin is None or not isinstance(finish_wrist_vs_shoulder, (int, float)):
        return None
    return not (fin in SHORT_FINISH and finish_wrist_vs_shoulder < FINISH_SHOULDER_PCT)


def apply(d: dict, overwrite: bool = True) -> dict:
    """Writes the situation classes into a stroke of strokes.json (technique.classes) and returns them.
    overwrite=False (report, audit on older outputs): a class already there is kept."""
    tech = d.get("technique")
    if tech is None:
        return {}
    cl = tech.setdefault("classes", {})
    m = d.get("metrics") or {}
    bti = m.get("bounce_to_impact_s")
    new = {"shot_angle": angled_shot(d.get("court_pos_m"), d.get("shot_bounce_m"), d.get("shot_in")),
           "net_ball": net_ball(d.get("court_pos_m"), m.get("contact_height_pct"), None if bti is None else True)}
    if not overwrite and "contact_type" not in cl:
        # the fine pass computes it inside technique (with the shape of the swing at each shifted phase,
        # for its repeatability); here only for strokes analysed before that never had it
        new["contact_type"] = contact_type(
            bti, m.get("contact_height_pct"), "ball" in (d.get("impact_source") or ""), d.get("court_pos_m"),
            m.get("ball_gap_pre_s"), m.get("ball_seen_pre_share"),
            groundstroke_swing(cl, ((tech.get("phases") or {}).get("finish") or {}).get("wrist_dom_vs_shoulder")))
    out = {}
    for k, v in new.items():
        if not overwrite and k in cl:
            continue
        if v is None:
            if overwrite:
                cl.pop(k, None)
            continue
        cl[k] = v
        out[k] = v
    return out


# the situations the user named (plan block 3), as the audit counts them: label → (class, levels)
ASKED = {
    "Golpe angulado (#132)": ("shot_angle", ("angulado",)),
    "Bola corta baja cerca de la red (#157)": ("net_ball", ("corta baja cerca de la red",)),
    "Bola corta alta cerca de la red (#158)": ("net_ball", ("corta alta cerca de la red",)),
    "Volea a media pista con golpe de fondo (#159)": ("contact_type", ("volea de fondo a media pista",)),
    "Volea fuera de la línea de saque": ("contact_type", ("volea fuera de la línea de saque", "volea de fondo a media pista")),
    "Botepronto / media volea: casos (#16)": ("contact_type", ("media volea",)),
}
