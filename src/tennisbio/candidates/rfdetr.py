"""RF-DETR Medium person detector (candidate of the bench, scripts/bench_candidates.py «rfdetr»). 21-11 (T25): it passed
its measure and moved to the pose (tennisbio.pose.rfdetr); this name stays for the bench."""
from ..pose.rfdetr import MEAN, PERSON, STD, RfDetrPeople, decode_people

__all__ = ["MEAN", "PERSON", "STD", "RfDetrPeople", "decode_people"]
