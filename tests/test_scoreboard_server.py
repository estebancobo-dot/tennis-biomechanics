"""Who serves, on scoreboard layouts other than the US Open's (09-11: the Indian Wells and Miami 2026 broadcasts
gave 0 serve votes to the identity stage). Synthetic scoreboard crops: country flags and highlighted points cells on
both rows, and a serve marker that is not a saturated colour blob."""
import cv2
import numpy as np

from tennisbio.scoreboard import learn_server, parse, serve_marker, serve_parity

NAMES = ("Rybakina", "Pegula")
X_NAME, X_GAMES, X_PTS, ROW_Y, GAP = 60, 250, 330, 30, 40


def box(x, y, w=40, h=20):
    return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]


def board(games, pts, server, marker="white", flags=True, cells=True, seed=0):
    """(crop, OCR items) of a world-feed-like scoreboard: dark panel, a flag left of each name (different
    countries), the current points in a teal cell on both rows, and the server's marker right of her name."""
    rng = np.random.default_rng(seed)
    img = np.full((2 * GAP + 20, 400, 3), (60, 20, 40), np.uint8)            # dark purple panel (BGR)
    items = []
    for k, name in enumerate(("RYBAKINA", "PEGULA")):
        y = ROW_Y + GAP * k
        if flags:
            if k == 0:
                cv2.rectangle(img, (14, y - 9), (44, y + 9), (200, 175, 0), -1)            # light blue flag
                cv2.circle(img, (29, y), 4, (0, 210, 255), -1)                          # with a yellow sun
            else:
                for j in range(5):                                                       # red and white stripes
                    cv2.rectangle(img, (14, y - 9 + 4 * j), (44, y - 7 + 4 * j), (40, 40, 220) if j % 2 == 0 else (240, 240, 240), -1)
                cv2.rectangle(img, (14, y - 9), (26, y - 1), (120, 40, 30), -1)
        cv2.putText(img, name, (X_NAME, y + 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
        w_name = 15 * len(name)
        items.append((box(X_NAME, y - 10, w_name, 20), name, .99))
        if server == k:
            cx = X_NAME + w_name + 14
            col = {"white": (235, 235, 235), "yellow": (40, 230, 230)}[marker]
            cv2.circle(img, (cx, y), 5, col, -1)
        gs = "".join(str(g[k]) for g in games)
        cv2.putText(img, gs, (X_GAMES, y + 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
        items.append((box(X_GAMES, y - 10, 14 * len(gs), 20), gs, .99))
        if cells:
            cv2.rectangle(img, (X_PTS - 6, y - 15), (X_PTS + 40, y + 15), (170, 200, 0), -1)  # teal points cell
        cv2.putText(img, pts[k], (X_PTS, y + 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (30, 30, 30), 2, cv2.LINE_AA)
        items.append((box(X_PTS - 2, y - 10, 34, 20), pts[k], .99))
    noise = rng.normal(0, 3.0, img.shape)
    return np.clip(img + noise, 0, 255).astype(np.uint8), items


def match_readings(first_server=0, **kw):
    """Three readings per game over a set and a half; the serve alternates every game."""
    seq, games = [], [[0, 0]]
    order = [0, 1, 1, 0, 0, 1, 0, 1, 1, 0, 0, 1, 0]          # who wins each game
    for n, w in enumerate(order + [None]):
        tot = sum(a + b for a, b in games)
        srv = first_server ^ (tot % 2)
        for j, pts in enumerate((("15", "0"), ("30", "15"), ("40", "30"))):
            crop, items = board([list(g) for g in games], pts, srv, seed=100 * n + j, **kw)
            st = parse(items, NAMES, crop)
            assert st is not None
            seq.append(({"t": float(len(seq)), **st.to_dict()}, st.profile, srv))
        if w is None:
            break
        games[-1][w] += 1
        if max(games[-1]) == 6 and abs(games[-1][0] - games[-1][1]) >= 2:
            games.append([0, 0])
    return seq


def test_serve_marker_ignores_highlighted_cells_on_both_rows():
    """A teal points cell on both rows is not a marker: before 09-11 it balanced the two rows and the reading
    was None, even with a yellow serve ball."""
    for srv in (0, 1):
        crop, items = board([[2, 1]], ("15", "30"), srv, marker="yellow", flags=False)
        assert serve_marker(crop, items, (ROW_Y, ROW_Y + GAP)) == srv


def test_white_marker_and_flags_learned_over_the_match():
    """A white serve dot (no saturated colour) next to the name, different flags on the two rows: the colour rule
    reads the flags, not the server; the marker learned from the alternation of the serve reads every reading."""
    for first in (0, 1):
        seq = match_readings(first_server=first)
        readings, profiles, truth = [s[0] for s in seq], [s[1] for s in seq], [s[2] for s in seq]
        raw = [r["server"] for r in readings]
        assert sum(v == t for v, t in zip(raw, truth)) < 0.8 * len(truth)        # the colour rule does not read it
        out, summ = learn_server(readings, profiles)
        assert summ["learned"] and summ["source"] == "aprendido"
        assert sum(v == t for v, t in zip(out, truth)) >= 0.95 * len(truth)
        assert all(-1.0 <= a < b <= 6.0 for a, b in summ["bins"])               # right of the names, where it is drawn


def test_no_marker_on_the_scoreboard_gives_no_server():
    """Nothing invented: with no marker the alternation alone never says who serves."""
    seq = match_readings(first_server=0, marker="white")
    readings = [dict(s[0], server=None) for s in seq]
    rng = np.random.default_rng(3)
    profiles = [rng.normal(0, 5, len(s[1])) for s in seq]
    out, summ = learn_server(readings, profiles)
    assert not summ["learned"] and all(v is None for v in out)


def test_a_colour_marker_that_follows_the_serve_is_kept():
    """The US Open case: a yellow ball read frame by frame and following the alternation stays as read."""
    seq = match_readings(first_server=1, marker="yellow", flags=False, cells=False)
    readings, profiles, truth = [s[0] for s in seq], [s[1] for s in seq], [s[2] for s in seq]
    assert [r["server"] for r in readings] == truth
    out, summ = learn_server(readings, profiles)
    assert out == truth and summ["source"].startswith("marker") and summ["marker_agree"] == 1.0


def test_a_colour_reading_against_the_alternation_is_not_trusted():
    """A per-frame «server» that is always the same row (a coloured flag) does not follow the alternation: it is
    replaced by the learned marker or dropped, never passed on as votes."""
    seq = match_readings(first_server=0)
    readings = [dict(s[0], server=0) for s in seq]
    out, summ = learn_server(readings, [None] * len(seq))
    assert summ["marker_agree"] < 0.7 and all(v is None for v in out)


def test_serve_parity_counts_every_game_and_skips_tiebreaks():
    assert serve_parity({"games": [[6, 4], [2, 1]]}) == 1
    assert serve_parity({"games": [[7, 6], [0, 0]]}) == 1
    assert serve_parity({"games": [[6, 6]], "tiebreak": True}) is None
    assert serve_parity({"games": []}) is None


def test_flag_stripes_are_not_the_serve_marker():
    """09-11 (Miami 2026): the red stripes of the US flag on the opponent's row were read as her serve in 379 of 407
    readings; the real marker, a small green dot by the server's score, is a compact mark."""
    import cv2
    import numpy as np
    from tennisbio.scoreboard import serve_marker

    img = np.full((120, 600, 3), (90, 70, 20), np.uint8)               # dark teal background (BGR)
    for k in range(6):                                                    # US-flag-like stripes on row 1 (y ~ 80)
        cv2.rectangle(img, (5, 62 + 6 * k), (60, 64 + 6 * k), (40, 40, 220), -1)
    cv2.circle(img, (480, 30), 7, (40, 220, 60), -1)                      # green dot on row 0 (y ~ 30)
    assert serve_marker(img, [], (30.0, 80.0)) == 0
    img2 = np.full((120, 600, 3), (90, 70, 20), np.uint8)
    for k in range(6):
        cv2.rectangle(img2, (5, 62 + 6 * k), (60, 64 + 6 * k), (40, 40, 220), -1)
    cv2.circle(img2, (480, 80), 7, (40, 220, 60), -1)                     # the dot on row 1
    assert serve_marker(img2, [], (30.0, 80.0)) == 1


def _osaka_like(first_server=0, wrong_games=(1, 5, 9, 11), per_game=4, n_games=18):
    """Readings of a match where each game's server follows the alternation, but in some of the opponent's service
    games every reading says the wrong row (12-11, Osaka – Rybakina: the learned marker, 87 % right, read 4 of Osaka's
    8 service games as Rybakina's)."""
    from tennisbio.scoreboard import serve_parity
    rows, truth = [], []
    games = [[0, 0]]
    for g in range(n_games):
        srv = first_server ^ (g % 2)
        for j in range(per_game):
            r = {"t": float(len(rows)), "games": [list(x) for x in games], "points": ["15", "0"], "tiebreak": False}
            rows.append(r)
            truth.append(srv)
        games[-1][g % 2] += 1
        if max(games[-1]) == 6:
            games.append([0, 0])
    servers = [(1 - t) if sum(sum(x) for x in r["games"]) in wrong_games else t for r, t in zip(rows, truth)]
    return rows, servers, truth, [serve_parity(r) for r in rows]


def test_alternation_corrects_whole_games_read_on_the_wrong_row():
    """12-11 (B4, Osaka): 8 of the 9 points «of her serve without her serve» were Osaka's service games read as hers;
    the first server of the set, voted by every reading, gives each game's server."""
    from tennisbio.scoreboard import by_alternation
    for first in (0, 1):
        rows, servers, truth, par = _osaka_like(first)
        assert sum(v != t for v, t in zip(servers, truth)) == 16                # 4 games × 4 readings wrong
        out, summ = by_alternation(rows, servers, par)
        assert out == truth and summ["changed"] == 16 and summ["first_server"] == first


def test_alternation_fills_readings_without_a_marker_and_leaves_tiebreaks():
    from tennisbio.scoreboard import by_alternation
    rows, _, truth, par = _osaka_like(0, wrong_games=())
    servers = [None if i % 3 == 0 else t for i, t in enumerate(truth)]
    tb = {"t": 999.0, "games": [[6, 6]], "points": ["3", "2"], "tiebreak": True}
    out, summ = by_alternation(rows + [tb], servers + [1], par + [None])
    assert out[:-1] == truth and summ["filled"] == sum(v is None for v in servers)
    assert out[-1] == 1                                   # a tie-break reading keeps the marker: it changes every 2 points


def test_alternation_changes_nothing_when_the_readings_do_not_agree():
    """Nothing invented: half the readings each way gives no first server, and no reading changes."""
    from tennisbio.scoreboard import by_alternation
    rows, _, truth, par = _osaka_like(0, wrong_games=())
    servers = [t if (i // 4) % 4 < 2 else 1 - t for i, t in enumerate(truth)]    # every other pair of games flipped
    out, summ = by_alternation(rows, servers, par)
    assert out == servers and summ["changed"] == 0
    out, summ = by_alternation(rows, [None] * len(rows), par)
    assert all(v is None for v in out) and summ["first_server"] is None


def test_learn_server_says_what_the_alternation_corrected():
    rows, servers, truth, _ = _osaka_like(1)
    out, summ = learn_server([dict(r, server=s) for r, s in zip(rows, servers)], [None] * len(rows))
    assert out == truth and summ["alternation"]["changed"] == 16 and summ["source"].endswith("+ alternancia")


def test_alternation_votes_by_games_and_the_colour_marker_wins_inside_a_game():
    """A game whose readings were mostly filled by the learned marker (wrong) but with one colour reading (right) votes
    with the colour one; voting by readings, games read many times weighed more than the rest (Osaka: 61 %)."""
    from tennisbio.scoreboard import by_alternation
    rows, servers, truth, par = _osaka_like(0, wrong_games=(1, 3, 5, 7, 9, 11, 13, 15))   # 8 of the opponent's 9 wrong
    marker = [t if i % 4 == 0 else None for i, t in enumerate(truth)]                      # one colour reading a game
    out, summ = by_alternation(rows, servers, par)
    assert summ["first_server"] is None and out == servers        # without the colour readings: 10 of 18, not clear
    out, summ = by_alternation(rows, servers, par, marker=marker)
    assert out == truth and summ["share"] == 1.0 and summ["games"] == 18
