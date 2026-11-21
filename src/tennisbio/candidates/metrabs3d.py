"""MeTRAbs for the candidate bench (scripts/bench_candidates.py «metrabs_model»). 21-11 (#309): it passed its measure on
CalTennis and moved to the pose (tennisbio.pose.metrabs3d); this name stays for the bench."""
from ..pose.metrabs3d import SKELETON, TRUNK, URL, Metrabs

__all__ = ["SKELETON", "TRUNK", "URL", "Metrabs"]
