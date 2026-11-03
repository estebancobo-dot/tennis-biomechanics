"""TennisCourtDetector: adopted on 03-11 (tennisbio.court_tcd); kept here so the trial (scripts/bench_candidates.py)
runs unchanged."""
from ..court_tcd import *  # noqa: F401,F403
from ..court_tcd import CourtTcd, _intersection, _merge_lines, best_homography, heatmap_point, refine_point  # noqa: F401
