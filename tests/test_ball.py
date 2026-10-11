import numpy as np

from tennisbio.ball import _peak, ball_hits, clean_track


def rally(fps=25):
    """Ball y in the image: far hit at the top, bounce on the near court, near hit at the bottom."""
    pts = []
    for t in range(150):
        s = (t % 75) / 75
        if t < 75:   # far hit (y=300) → bounce near (y=850, small kink) → near hit (y=900)
            y = 300 + 600 * s if s < 0.8 else 780 + 120 * (s - 0.8) / 0.2
        else:        # near hit → goes back up to the far player
            y = max(300, 900 - 1200 * s)
        pts.append((900 + 3 * t, y))
    return np.array([[x, y, 0.9] for x, y in pts])


def test_ball_hits_finds_near_hit_and_ignores_bounce():
    hits = ball_hits(rally(), 1080, 25)
    near = [h for h in hits if h.side == "near"]
    assert len(near) == 1 and abs(near[0].frame - 75) <= 1


def test_clean_track_drops_jumps():
    tr = rally()
    tr[40, :2] = (100, 100)
    assert np.isnan(clean_track(tr)[40]).all() and not np.isnan(clean_track(tr)[41]).any()


def test_peak():
    hm = np.zeros((288, 512), np.float32)
    hm[100:105, 200:205] = 0.9
    x, y, c = _peak(hm, 0.5)
    assert abs(x - 202.5) < 1 and abs(y - 102.5) < 1 and c > 0.8


def test_track_step_interpolates():
    from tennisbio.ball import BallTracker

    class FakeSess:
        def get_inputs(self):
            return [type("I", (), {"name": "frames"})()]

        def run(self, _, feed):
            n = feed["frames"].shape[0]
            hm = np.zeros((n, 1, 288, 512), np.float32)
            hm[:, 0, 100:103, 200:203] = 0.9
            return [hm]

    bt = BallTracker.__new__(BallTracker)
    bt.sess, bt.threshold, bt.batch = FakeSess(), 0.5, 4
    out = bt.track([np.zeros((576, 1024, 3), np.uint8)] * 7, step=2)
    assert out.shape == (7, 3) and not np.isnan(out[:7, 0]).any()
    assert abs(out[1, 0] - 201.5 * 2) < 1
