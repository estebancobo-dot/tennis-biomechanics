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
