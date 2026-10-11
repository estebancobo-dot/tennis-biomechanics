import numpy as np

from tennisbio.court_metrics import court_metrics, stance
from tennisbio.skeleton import Skeleton


def test_stance_forehand_right_handed():
    right, left = np.array([1.0, 0.0]), np.array([0.0, 0.0])
    assert stance(right, left, "forehand")[0] == "abierto"                      # side by side
    assert stance(right, left + [0, 0.5], "forehand")[0] == "semiabierto"      # left foot 0.5 m ahead
    assert stance(right, np.array([0.8, 0.9]), "forehand")[0] == "cerrado"     # left foot in front
    assert stance(right, left - [0, 0.4], "forehand")[1] < 0                   # very open


def test_court_metrics_identity_homography():
    sk = Skeleton("coco17", "right")
    kp = np.full((5, 17, 2), np.nan)
    kp[:, sk["right_ankle"]] = [1.0, 0.0]
    kp[:, sk["left_ankle"]] = [0.0, 0.0]
    kp[0, sk["right_ankle"]], kp[0, sk["left_ankle"]] = [4.0, 0.0], [3.0, 0.0]
    m = court_metrics(kp, sk, np.eye(3), "forehand", impact=4, opponent_hit=0)
    assert m["stance"] == "abierto" and m["stance_width_m"] == 1.0
    assert m["court_pos_m"] == [0.5, 0.0] and m["displacement_m"] == 3.0


def test_shot_landing_picks_the_candidate_on_the_far_court():
    from tennisbio.court_metrics import shot_landing
    H = np.eye(3)                         # image px = court metres, to keep it readable
    cands = [[-1.4, 28.3, 50], [2.9, 18.2, 40]]          # sharpest is the opponent's hit in the air
    r = shot_landing(H, cands, contact_x=-2.5, fps=50, impact_frame=0)
    assert r["shot_bounce_m"] == [2.9, 18.2] and r["shot_in"] and r["shot_direction"] == "cruzada"
    assert abs(r["shot_depth_m"] - 5.57) < 1e-6 and r["impact_to_shot_bounce_s"] == 0.8
    long = shot_landing(H, [[0.5, 24.5, 30]], contact_x=0.3, fps=50, impact_frame=0)
    assert long["shot_in"] is False and long["shot_direction"] == "al centro"
    assert shot_landing(H, [[0, 30, 5]], 0, 50, 0) == {}


def test_player_frame_for_the_far_end():
    from tennisbio.court_metrics import player_frame_H, to_court
    H = np.eye(3)                                   # image = court metres
    Hf = player_frame_H(H, "far")
    # a point 1 m inside the far baseline, 2 m to the image left = her right (she faces the camera)
    assert np.allclose(to_court(Hf, np.array([[-2.0, 22.77]])), [[2.0, 1.0]])
    assert player_frame_H(H, "near") is H
