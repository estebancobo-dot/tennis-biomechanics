import numpy as np

from tennisbio.ball3d import G, NET_Y, _path, camera, flights, project


def _broadcast_camera(w=1920, h=1080, f=1800.0, pitch_deg=18.0, height=8.0, back=12.0):
    """A camera behind the near baseline, elevated and tilted down, like the main TV camera."""
    p = np.radians(pitch_deg)
    fwd = np.array([0, np.cos(p), -np.sin(p)])        # camera axes in court coordinates
    right = np.array([1.0, 0, 0])
    down = np.cross(fwd, right)
    R = np.vstack([right, down, fwd])
    C = np.array([0, -back, height])
    K = np.array([[f, 0, w / 2], [0, f, h / 2], [0, 0, 1]])
    P = K @ np.column_stack([R, -R @ C])
    H = P[:, [0, 1, 3]]
    return P, H / H[2, 2]


def _rally(v_out, fb, fi, opp=5, fps=50.0, noise=1.0, seed=0):
    """Ball track of an incoming ball from the far baseline, bouncing at 5 m, hit at frame fi."""
    P, H = _broadcast_camera()
    bounce = np.array([0.8, 5.0, 0.0])
    S = np.array([-1.0, 24.5, 1.0])                   # the opponent's contact
    T_in = (fb - opp) / fps
    v_in = (bounce - S) / T_in + np.array([0, 0, 0.5 * G * T_in])
    rng = np.random.default_rng(seed)
    track = np.full((fi + 10, 3), np.nan)
    for k in range(opp, fi + 1):
        t = (k - fb) / fps
        X = S + v_in * (t + T_in) - np.array([0, 0, 0.5 * G * (t + T_in) ** 2]) if t < 0 else _path(bounce, v_out, np.array([t]))[0]
        track[k, :2] = project(P, X[None])[0] + rng.normal(0, noise, 2)
    zc = float(_path(bounce, v_out, np.array([(fi - fb) / fps]))[0, 2])
    t_net = -T_in * (NET_Y - bounce[1]) / (S[1] - bounce[1])
    return P, H, track, zc, fb + t_net * fps


def test_camera_from_the_court_lines_matches_the_true_one():
    P_true, H = _broadcast_camera()
    P = camera(H, (1080, 1920))
    X = np.array([[1.0, 3.0, 1.2], [-3.0, 20.0, 2.5], [0.5, 11.885, 0.9]])
    assert np.max(np.linalg.norm(project(P, X) - project(P_true, X), axis=1)) < 1.0


def test_rising_dropping_and_top_with_hand_height_error():
    fps = 50.0
    v_out = np.array([0.4, -9.0, 4.0])                # top of the bounce 0.41 s after it
    for fi, phase in ((52, "subiendo"), (60, "arriba"), (72, "cayendo")):
        P, H, track, zc, net = _rally(v_out, 40, fi)
        for err in (-0.15, 0.0, 0.15):                # her hand is not exactly the ball
            out = flights(track, fps, H, (1080, 1920), 40, fi, 5, zc + err)
            assert out["contact_phase"] == phase, (fi, err, out)
            # the top of the bounce follows the hand-height error (±0.15 m → about ±0.3 m)
            assert abs(out["apex_height_m"] - v_out[2] ** 2 / (2 * G)) < (0.1 if err == 0 else 0.35)
        assert abs(out["net_frame"] - net) <= 2


def test_garbage_track_is_not_shown():
    fps = 50.0
    P, H, track, zc, _ = _rally(np.array([0.4, -9.0, 4.0]), 40, 60, noise=60.0, seed=3)
    assert "contact_phase" not in flights(track, fps, H, (1080, 1920), 40, 60, 5, zc)


def test_incoming_speed_nominal_and_edge_of_the_limit():
    fps = 50.0
    v_out = np.array([0.4, -9.0, 4.0])
    _, H, track, zc, _ = _rally(v_out, 40, 60, opp=5, noise=0.0)       # 19.6 m in 0.70 s ≈ 101 km/h
    out = flights(track, fps, H, (1080, 1920), 40, 60, 5, zc, player_y_m=0.0)
    assert 95 <= out["incoming_speed_kmh"] <= 105
    _, H, track, zc, _ = _rally(v_out, 40, 60, opp=25, noise=0.0)      # 0.30 s ≈ 235 km/h: just inside
    out = flights(track, fps, H, (1080, 1920), 40, 60, 25, zc)
    assert 225 <= out["incoming_speed_kmh"] <= 240 and "net_frame" in out


def test_impossible_incoming_speed_is_not_measured():
    """Long run: one stroke had 763 km/h. A speed over the physical limit, or an opponent's contact
    placed far behind the court (a ball high in the image cut at 1 m), is not measured; the rest of
    the flight stays."""
    fps = 50.0
    v_out = np.array([0.4, -9.0, 4.0])
    _, H, track, zc, _ = _rally(v_out, 40, 60, opp=26, noise=0.0)      # 0.28 s for 19.6 m ≈ 252 km/h
    out = flights(track, fps, H, (1080, 1920), 40, 60, 26, zc)
    assert "incoming_speed_kmh" not in out and "net_frame" not in out and out["contact_phase"] == "arriba"
    P, H, track, zc, _ = _rally(v_out, 40, 60, opp=5, noise=0.0)
    track[5, :2] = project(P, np.array([[-1.0, 60.0, 1.0]]))[0]       # 60 m away: nobody plays from there
    out = flights(track, fps, H, (1080, 1920), 40, 60, 5, zc)
    assert "incoming_speed_kmh" not in out and "contact_phase" in out


def test_a_bounce_too_far_for_the_time_left_measures_nothing():
    """The 763 km/h stroke: a bounce 8.7 m in front of her 3 frames before the contact is not the
    bounce of the incoming ball; nothing is measured from it."""
    fps = 50.0
    P, H, track, zc, _ = _rally(np.array([0.4, -9.0, 4.0]), 40, 60, noise=0.0)
    track[57, :2] = project(P, np.array([[-2.5, 8.7, 0.0]]))[0]
    assert flights(track, fps, H, (1080, 1920), 57, 60, 5, zc, player_y_m=0.7) == {}
    assert flights(track, fps, H, (1080, 1920), 40, 60, 5, zc, player_y_m=0.7)     # the true bounce still measures
