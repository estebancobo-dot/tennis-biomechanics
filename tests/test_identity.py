import numpy as np

from tennisbio.identity import assign, cluster_two, near_serves


def test_cluster_two_separates_outfits():
    rng = np.random.default_rng(0)
    yellow, orange = np.eye(32)[3] * 0.7 + 0.01, np.eye(32)[1] * 0.7 + 0.01
    feats = np.array([(yellow if i % 2 else orange) + rng.normal(0, .01, 32).clip(0) for i in range(12)])
    lab = cluster_two(feats)
    assert len(set(lab[::2])) == 1 and len(set(lab[1::2])) == 1 and lab[0] != lab[1]


def test_assign_votes_and_uncertainty():
    lab = np.array([0, 1, 0, 1, 0, 1])
    # near player serving & scoreboard says target serves → target; cluster 1 near when opponent served
    r = assign(lab, [(0, True), (2, True), (1, False), (4, False)])
    assert r["target_cluster"] == 0 and r["confidence"] == 0.75
    assert assign(lab, [(0, True)])["target_cluster"] is None                  # too few votes
    assert assign(lab, [(0, True), (2, False)])["target_cluster"] is None      # contradictory


def test_near_serves_detects_arm_above_head():
    T, kps, conf = 20, np.zeros((20, 17, 2)), np.ones((20, 17))
    kps[:, 0] = [100, 100]
    kps[:, 9], kps[:, 10] = [90, 150], [110, 150]
    kps[8, 10] = [110, 50]                     # wrist 50 px above the nose (height 200 px → 0.25)
    assert near_serves(kps, conf, 10, 200) == 8
    kps[8, 10] = [110, 150]
    assert near_serves(kps, conf, 10, 200) is None
