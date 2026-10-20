"""The situations the user named (plan block 3): angled shot, short ball near the net (low / high),
mid-court volley with a groundstroke swing, volley behind the service line and half volley. Synthetic
strokes for each class, boundaries exactly at the thresholds, missing data (None) and the classes that
existed before, unchanged."""
import json

import numpy as np
import pytest

from tennisbio import situations as S
from tennisbio.technique import (BALL_GAP_MAX_S, BALL_SEEN_MIN, HALF_VOLLEY_PCT, HALF_VOLLEY_S, MIDCOURT_BACK_M,
                                 SERVICE_LINE_M, contact_type, half_volley, height_class)

FOLLOWED = dict(ball_gap_s=0.04, ball_seen=0.95)          # the ball seen all the way before the impact


# ---------- 1. angled shot ----------

def test_angled_cross_court_short_and_wide():
    assert S.angled_shot([3.0, -1.0], [-3.5, 16.0], True) == "angulado"        # from her forehand corner
    assert S.angled_shot([-3.0, 0.0], [3.6, 17.0], True) == "angulado"         # from her backhand corner
    assert S.angled_shot([0.4, 1.0], [3.2, 15.0], True) == "angulado"          # from the centre: any side


def test_not_angled():
    assert S.angled_shot([3.0, -1.0], [-3.5, 22.0], True) == "no angulado"     # deep cross-court
    assert S.angled_shot([3.0, -1.0], [-1.5, 16.0], True) == "no angulado"     # short but in the middle
    assert S.angled_shot([3.0, -1.0], [3.5, 16.0], True) == "no angulado"      # short down the line


def test_angled_boundaries_exactly_at_the_thresholds():
    assert S.FAR_SERVICE_Y == pytest.approx(18.285) and S.ANGLE_WIDE_M == pytest.approx(2.7433, abs=1e-3)
    assert S.angled_shot([3.0, 0], [-S.ANGLE_WIDE_M, S.FAR_SERVICE_Y], True) == "angulado"      # both inclusive
    assert S.angled_shot([3.0, 0], [-S.ANGLE_WIDE_M + 0.01, 16.0], True) == "no angulado"
    assert S.angled_shot([3.0, 0], [-3.5, S.FAR_SERVICE_Y + 0.01], True) == "no angulado"
    # the centre band of shot_landing (|x| ≤ 1 m): exactly 1 m is the centre, any wide short ball is an angle
    assert S.angled_shot([S.CENTRE_X_M, 0], [3.5, 16.0], True) == "angulado"
    assert S.angled_shot([S.CENTRE_X_M + 0.01, 0], [3.5, 16.0], True) == "no angulado"


def test_angled_missing_data_is_none():
    assert S.angled_shot(None, [-3.5, 16.0], True) is None
    assert S.angled_shot([3.0, 0], None, True) is None
    assert S.angled_shot([3.0, 0], [-3.5, 16.0], None) is None                 # in or out unknown
    assert S.angled_shot([3.0, 0], [-4.6, 16.0], False) is None                # out: not an angle of hers
    assert S.angled_shot([3.0, 0], [-3.5], True) is None                      # malformed


# ---------- 2-3. short ball near the net ----------

def test_net_ball_levels_by_height():
    y = S.NEAR_NET_Y_M + 0.5
    assert S.net_ball([0, y], 20, True) == "corta baja cerca de la red"
    assert S.net_ball([0, y], 50, True) == "corta a media altura cerca de la red"
    assert S.net_ball([0, y], 70, True) == "corta alta cerca de la red"
    assert S.net_ball([0, y], 95, True) == "corta alta cerca de la red"


def test_net_ball_boundaries_exactly_at_the_thresholds():
    assert S.NEAR_NET_Y_M == pytest.approx(SERVICE_LINE_M - 1.0) and SERVICE_LINE_M == pytest.approx(5.485)
    assert S.net_ball([0, S.NEAR_NET_Y_M], 50, True) is not None              # exactly 1 m behind the service line
    assert S.net_ball([0, S.NEAR_NET_Y_M - 0.01], 50, True) is None
    # heights: the boundaries of the class ball_height (35 % knee, 65 % chest-shoulder)
    assert S.net_ball([0, 6.0], 34.99, True) == "corta baja cerca de la red"
    assert S.net_ball([0, 6.0], 35.0, True) == "corta a media altura cerca de la red"
    assert S.net_ball([0, 6.0], 64.99, True) == "corta a media altura cerca de la red"
    assert S.net_ball([0, 6.0], 65.0, True) == "corta alta cerca de la red"


def test_net_ball_missing_data_is_none():
    assert S.net_ball(None, 30, True) is None
    assert S.net_ball([0, 6.0], None, True) is None
    assert S.net_ball([0, 6.0], 30, None) is None          # no bounce seen: may be a volley, not a short ball
    assert S.net_ball([0, 2.0], 30, True) is None          # at the baseline: not this situation


def test_net_ball_and_ball_height_are_one_calculation():
    for h in (10, 34.9, 35, 49.9, 50, 64.9, 65, 79.9, 80, 120):
        lv = S.net_ball([0, 6.0], h, True)
        hc = height_class(h)
        assert (lv == "corta baja cerca de la red") == (hc == "rodilla")
        assert (lv == "corta alta cerca de la red") == (hc in ("pecho-hombro", "por encima del hombro"))


# ---------- 3-4. volleys behind the service line ----------

def test_midcourt_volley_with_groundstroke_swing():
    full = S.groundstroke_swing({"takeback": "amplia", "finish": "sobre el hombro"}, 5.0)
    assert full is True
    assert contact_type(None, 70, True, (0, 3.0), full_swing=full, **FOLLOWED) == "volea de fondo a media pista"


def test_volley_behind_the_service_line_compact():
    comp = S.groundstroke_swing({"takeback": "compacta", "finish": "limpiaparabrisas"}, -10.0)
    assert comp is False
    assert contact_type(None, 60, True, (0, 4.0), full_swing=comp, **FOLLOWED) == "volea fuera de la línea de saque"
    # swing not measured: still a volley behind the service line, never the groundstroke one
    assert contact_type(None, 60, True, (0, 4.0), full_swing=None, **FOLLOWED) == "volea fuera de la línea de saque"


def test_groundstroke_swing_rules():
    assert S.groundstroke_swing({"takeback": "en bucle alto", "finish": "limpiaparabrisas"}, 2.0) is True
    # wide preparation and a short finish (in front, below the shoulder): not a groundstroke swing
    assert S.groundstroke_swing({"takeback": "amplia", "finish": "limpiaparabrisas"}, -10.0) is False
    assert S.groundstroke_swing({"takeback": "amplia", "finish": "limpiaparabrisas"}, -3.0) is True    # at the boundary
    assert S.groundstroke_swing({}, 5.0) is None
    assert S.groundstroke_swing({"takeback": "amplia"}, None) is None
    assert S.groundstroke_swing(None, None) is None


def test_midcourt_volley_boundaries():
    # the service line: beyond it the old «volea»; on it and behind it the new classes
    assert contact_type(None, 70, True, (0, SERVICE_LINE_M + 0.01), **FOLLOWED) == "volea"
    assert contact_type(None, 70, True, (0, SERVICE_LINE_M), **FOLLOWED) == "volea fuera de la línea de saque"
    assert contact_type(None, 70, True, (0, MIDCOURT_BACK_M), **FOLLOWED) == "volea fuera de la línea de saque"
    assert contact_type(None, 70, True, (0, MIDCOURT_BACK_M - 0.01), **FOLLOWED) is None
    # the ball followed: exactly at the thresholds counts, just beyond does not
    assert contact_type(None, 70, True, (0, 3.0), ball_gap_s=BALL_GAP_MAX_S, ball_seen=BALL_SEEN_MIN) is not None
    assert contact_type(None, 70, True, (0, 3.0), ball_gap_s=BALL_GAP_MAX_S + 0.01, ball_seen=0.9) is None
    assert contact_type(None, 70, True, (0, 3.0), ball_gap_s=0.04, ball_seen=BALL_SEEN_MIN - 0.01) is None
    # the hand: from the half-volley boundary up; lower may be a half volley with an unseen bounce
    assert contact_type(None, HALF_VOLLEY_PCT, True, (0, 3.0), **FOLLOWED) is not None
    assert contact_type(None, HALF_VOLLEY_PCT - 0.1, True, (0, 3.0), **FOLLOWED) is None


def test_midcourt_volley_missing_data_is_none():
    assert contact_type(None, 70, True, (0, 3.0)) is None                       # ball coverage not measured
    assert contact_type(None, 70, True, (0, 3.0), ball_gap_s=0.04) is None
    assert contact_type(None, 70, False, (0, 3.0), **FOLLOWED) is None          # impact not from the ball
    assert contact_type(None, 70, True, None, **FOLLOWED) is None
    assert contact_type(None, None, True, (0, 3.0), **FOLLOWED) is None


# ---------- 5. half volley ----------

def test_half_volley_rule_and_boundaries():
    assert HALF_VOLLEY_S == 0.15 and HALF_VOLLEY_PCT == 45.0
    assert half_volley(0.08, 30) is True
    assert half_volley(HALF_VOLLEY_S, 30) is False                  # strict: 0.15 s is a normal ball
    assert half_volley(HALF_VOLLEY_S - 0.001, 30) is True
    assert half_volley(0.08, HALF_VOLLEY_PCT) is False
    assert half_volley(0.08, HALF_VOLLEY_PCT - 0.1) is True
    assert half_volley(0.08, None) is False                         # hand height unknown: not low
    assert half_volley(None, 20) is None                            # no bounce: nothing to say
    assert contact_type(0.08, 30, True, (0, 4.0)) == "media volea"
    assert contact_type(0.08, 30, True, (0, 4.0), full_swing=True, **FOLLOWED) == "media volea"   # the bounce decides


def test_half_volley_bounce_is_found_at_the_smallest_visible_distance():
    """A synthetic ball path at 50 fps: down to a bounce, up for a few frames, hit back. The bounce is
    found when it is at least min_bounce_to_impact_s before the hit, and the stroke is a half volley."""
    from tennisbio.ball import bounce_before, min_bounce_to_impact_s, seen_before

    fps = 50.0
    assert min_bounce_to_impact_s(50) == pytest.approx(0.06) and min_bounce_to_impact_s(25) == pytest.approx(0.08)
    for gap in (3, 4, 6):                                         # frames from the bounce to the hit
        hit, b = 60, 60 - gap
        tr = np.full((80, 3), np.nan)
        for f in range(80):
            if f <= b:                    # coming towards the camera, going down the image
                tr[f] = (400 + 2 * (f - b), 600 + 8 * (f - b) + 10 * (f - b), 0.9)
            elif f <= hit:                # after the bounce: still coming, now rising in the image
                tr[f] = (400 + 2 * (f - b), 600 + 2 * (f - b), 0.9)
            else:                         # hit back: up the image, away
                tr[f] = (400 + 2 * (hit - b) - 3 * (f - hit), 600 + 2 * (hit - b) - 25 * (f - hit), 0.9)
        bo = bounce_before(tr, hit, fps)
        assert bo is not None and abs(bo.frame - b) <= 1, (gap, bo)
        bti = (hit - bo.frame) / fps
        assert bti >= min_bounce_to_impact_s(fps) - 1e-9
        assert contact_type(round(bti, 3), 25, True, (0, 4.0)) == "media volea"
        share, longest = seen_before(tr, hit, fps)
        assert share == 1.0 and longest == 0.0


def test_seen_before_measures_the_longest_gap():
    from tennisbio.ball import seen_before

    tr = np.zeros((100, 3))
    tr[40:46, :2] = np.nan                                    # 6 frames lost at 50 fps = 0.12 s
    share, gap = seen_before(tr, 90, 50.0)
    assert gap == pytest.approx(0.12) and 0.9 < share < 1.0
    assert seen_before(tr, 1, 50.0) == (None, None)           # too short a stretch to tell


# ---------- the existing classes, unchanged ----------

def test_existing_contact_classes_unchanged():
    assert contact_type(0.08, 30, True, (0, -1)) == "media volea"
    assert contact_type(0.08, 70, True, (0, -1)) == "tras el bote"
    assert contact_type(0.6, 60, True, (0, -1)) == "tras el bote"
    assert contact_type(None, 80, True, (0, 9.0)) == "volea"
    assert contact_type(None, 80, True, (0, 2.0)) is None          # no coverage measured: unknown, as before
    assert contact_type(None, 80, False, (0, 9.0)) is None


def test_ball_height_class_unchanged():
    from tennisbio.technique import situation
    for h, lv in ((20, "rodilla"), (40, "cadera"), (55, "cintura-pecho"), (70, "pecho-hombro"), (90, "por encima del hombro")):
        assert situation({}, None, None, None, h, 1)["ball_height"] == lv


# ---------- apply on a stroke of strokes.json ----------

def _stroke(**kw):
    s = {"stroke": "forehand", "side": "near", "impact_source": "ball+swing", "court_pos_m": [3.0, 5.0],
         "shot_bounce_m": [-3.4, 16.5], "shot_in": True,
         "metrics": {"contact_height_pct": 25.0, "bounce_to_impact_s": 0.4},
         "technique": {"classes": {"ball_height": "rodilla", "contact_type": "tras el bote", "shot_type": "cruzada"},
                       "phases": {}, "stroke": {}, "footwork": {}}}
    s.update(kw)
    return s


def test_apply_writes_the_new_classes_and_keeps_the_others():
    s = _stroke()
    got = S.apply(s)
    cl = s["technique"]["classes"]
    assert got == {"shot_angle": "angulado", "net_ball": "corta baja cerca de la red"}
    assert cl["contact_type"] == "tras el bote" and cl["shot_type"] == "cruzada" and cl["ball_height"] == "rodilla"


def test_apply_without_signals_leaves_no_class():
    s = _stroke(court_pos_m=None, shot_bounce_m=None, shot_in=None, metrics={})
    s["technique"]["classes"]["shot_angle"] = "angulado"          # a stale value from an older run
    S.apply(s)
    assert "shot_angle" not in s["technique"]["classes"] and "net_ball" not in s["technique"]["classes"]
    assert S.apply({"stroke": "forehand"}) == {}                  # no technique: nothing to write


def test_apply_on_older_outputs_never_overwrites():
    s = _stroke()
    s["technique"]["classes"]["shot_angle"] = "no angulado"
    S.apply(s, overwrite=False)
    assert s["technique"]["classes"]["shot_angle"] == "no angulado"
    assert s["technique"]["classes"]["net_ball"] == "corta baja cerca de la red"
    # a stroke without contact_type (older output with the coverage measured) gets the new volley class
    v = _stroke(court_pos_m=[0.5, 3.0], metrics={"contact_height_pct": 70.0, "ball_gap_pre_s": 0.02, "ball_seen_pre_share": 1.0})
    del v["technique"]["classes"]["contact_type"]
    v["technique"]["classes"].update(takeback="amplia", finish="sobre el hombro")
    v["technique"]["phases"]["finish"] = {"wrist_dom_vs_shoulder": 8.0}
    S.apply(v, overwrite=False)
    assert v["technique"]["classes"]["contact_type"] == "volea de fondo a media pista"
    assert "net_ball" not in v["technique"]["classes"]             # no bounce: not a short ball


# ---------- «Aprende», the video library, the model and the audit ----------

def test_each_situation_is_a_learn_condition_with_cue_and_drill():
    from tennisbio.learn import CONDITIONS, RELAX_ORDER
    from tennisbio.model import CLASS_KEYS, FACTORS

    for label, (key, levels) in S.ASKED.items():
        assert key in CONDITIONS and key in RELAX_ORDER, label
        for lv in levels:
            assert lv in CONDITIONS[key][1], (label, lv)
            assert all(CONDITIONS[key][1][lv]), (label, lv)          # what changes, how, drill
    assert set(CONDITIONS["net_ball"][1]) == set(S.NET_BALL_LEVELS)
    assert set(CONDITIONS["shot_angle"][1]) == set(S.ANGLE_LEVELS)
    assert "shot_angle" in CLASS_KEYS and "net_ball" in CLASS_KEYS
    assert set(FACTORS["contact_type"][1]) >= {"volea fuera de la línea de saque", "volea de fondo a media pista"}


def test_video_library_has_the_filters():
    from tennisbio.report import TEMPLATE
    html = TEMPLATE.read_text(encoding="utf-8")
    for chip in ('"angulado", s => s.shotAngle', '"Corta cerca de la red"', 's.netBall === "corta baja cerca de la red"',
                 's.netBall === "corta alta cerca de la red"', '"volea fuera de la línea de saque"', '"volea de fondo a media pista"',
                 's => s.nearNet === true'):
        assert chip in html, chip


def test_report_record_carries_the_situations(tmp_path):
    from tennisbio.catalog import Match, Player
    from tennisbio.report import collect

    d = tmp_path / "m1"
    d.mkdir()
    s = _stroke(match_time_s=12.0)
    del s["technique"]["classes"]["contact_type"]
    (d / "strokes.json").write_text(json.dumps([s]), encoding="utf-8")
    data = collect([Match("m1", None, Player("p", "P"))], tmp_path)
    r = data["strokes"][0]
    assert r["shotAngle"] == "angulado" and r["netBall"] == "corta baja cerca de la red" and r["nearNet"] is True


def test_audit_counts_each_situation(tmp_path):
    from tennisbio import audit as A
    from tennisbio.model import MIN_N

    rows = [_stroke(match_time_s=float(i)) for i in range(MIN_N)]
    rows += [_stroke(match_time_s=100.0, shot_bounce_m=[-3.4, 22.0], court_pos_m=[3.0, 1.0])]
    d = tmp_path / "m1"
    d.mkdir()
    (d / "strokes.json").write_text(json.dumps(rows), encoding="utf-8")
    res = A.audit([d], None)
    it = {i["name"]: i for i in res["items"] if i["area"] == "Situaciones"}
    assert it["Golpe angulado (#132)"]["status"] == "ok" and it["Golpe angulado (#132)"]["n"] == MIN_N
    assert it["Bola corta baja cerca de la red (#157)"]["n"] == MIN_N
    alta = it["Bola corta alta cerca de la red (#158)"]
    assert alta["status"] == "pocos datos" and "sin golpes suficientes" in alta["detail"] and alta["n"] == 0
    hv = it["Botepronto / media volea: casos (#16)"]
    assert hv["status"] == "pocos datos" and "0,06 s" in hv["detail"]
    for label in S.ASKED:
        assert label in it
    assert not A.VARIANTS_NOT_BUILT


def test_audit_item_names_match_the_register_rules():
    import re

    from tennisbio.audit import PETITIONS
    names = list(S.ASKED)
    for n in (132, 157, 158, 159, 16):
        assert any(re.search(PETITIONS[n], x) for x in names), n
