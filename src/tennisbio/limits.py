"""Physical limits of the per-stroke measurements. A value outside them is a measurement error (a
swapped or blurred keypoint, a misdetected ankle), never her technique: it is dropped before
anything uses it (nothing invented), the stroke keeps a note of it, and the audit checks that none
reaches the report."""
from __future__ import annotations

METRIC_LIMITS = {
    "contact_height_pct": (10, 140),          # % of her height above the ground
    "elbow_impact_deg": (50, 180),            # a forehand contact with the elbow under 50° does not exist
    "non_elbow_impact_deg": (20, 180),
    "x_factor_deg": (-60, 90),
    "shoulder_turn_loaded_deg": (-30, 200),
    "hip_turn_loaded_deg": (-60, 160),
    "time_available_s": (0.25, 4.0),
    "head_motion_impact_cm": (0, 40),
    "base_width_loaded_pct": (5, 90),         # feet apart, % of her height
    "contact_lateral_pct": (0, 120),
    "finish_wrist_height_pct": (-40, 120),
}


def sanitize(metrics: dict) -> list[str]:
    """Drops (sets to None) the values outside their limits; returns the names dropped."""
    dropped = []
    for k, (lo, hi) in METRIC_LIMITS.items():
        v = metrics.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and not lo <= v <= hi:
            metrics[k] = None
            dropped.append(k)
    if "x_factor_deg" not in dropped and ("shoulder_turn_loaded_deg" in dropped or "hip_turn_loaded_deg" in dropped):
        metrics["x_factor_deg"] = None                  # made of a dropped value
        dropped.append("x_factor_deg")
    return dropped
