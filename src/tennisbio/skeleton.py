"""Keypoint schemas and side-agnostic joint names ("dom_wrist", "non_shoulder", ...).

Metrics never refer to "right" or "left": the player's hand decides which side is dominant.
"""
COCO17 = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow", "left_wrist", "right_wrist",
    "left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle",
]
HALPE26 = COCO17 + [
    "head", "neck", "hip", "left_big_toe", "right_big_toe", "left_small_toe", "right_small_toe",
    "left_heel", "right_heel",
]
# the 6 Halpe26 foot points, in the order of the hybrid pose cache (pose.hybrid: `feet`, `feet_confs`)
FOOT_NAMES = HALPE26[20:26]
SCHEMAS = {"coco17": COCO17, "halpe26": HALPE26}
PAIRED = ["shoulder", "elbow", "wrist", "hip", "knee", "ankle"]
FOOT_PAIRED = ["big_toe", "small_toe", "heel"]

# Bones for drawing: (joint, joint, side) with side in {"left", "right", "center"}.
BONES = [
    ("left_shoulder", "right_shoulder", "center"), ("left_hip", "right_hip", "center"),
    ("left_shoulder", "left_hip", "left"), ("right_shoulder", "right_hip", "right"),
    ("left_shoulder", "left_elbow", "left"), ("left_elbow", "left_wrist", "left"),
    ("right_shoulder", "right_elbow", "right"), ("right_elbow", "right_wrist", "right"),
    ("left_hip", "left_knee", "left"), ("left_knee", "left_ankle", "left"),
    ("right_hip", "right_knee", "right"), ("right_knee", "right_ankle", "right"),
]


class Skeleton:
    """Index lookup for a keypoint schema, with dominant/non-dominant aliases.

    feet=True (COCO17 only): the 6 foot points (FOOT_NAMES) follow the 17 body points, indices 17-22,
    as in footpoints.with_feet. Halpe26 has them already. Foot aliases: dom_heel, non_big_toe, ..."""

    def __init__(self, schema: str = "coco17", hand: str = "right", feet: bool = False):
        if hand not in ("right", "left"):
            raise ValueError(f"hand must be 'right' or 'left', got {hand!r}")
        self.schema, self.hand = schema, hand
        self.names = list(SCHEMAS[schema])
        if feet and not all(n in self.names for n in FOOT_NAMES):
            self.names += FOOT_NAMES
        self.idx = {n: i for i, n in enumerate(self.names)}
        dom, non = (hand, "left" if hand == "right" else "right")
        for j in PAIRED + [f for f in FOOT_PAIRED if f"{dom}_{f}" in self.idx]:
            self.idx[f"dom_{j}"] = self.idx[f"{dom}_{j}"]
            self.idx[f"non_{j}"] = self.idx[f"{non}_{j}"]

    @property
    def has_feet(self) -> bool:
        return all(n in self.idx for n in FOOT_NAMES)

    def __getitem__(self, name: str) -> int:
        return self.idx[name]

    def __len__(self) -> int:
        return len(self.names)

    @property
    def dom_sign(self) -> int:
        """+1 if the dominant side is image-right when seen from behind, -1 otherwise."""
        return 1 if self.hand == "right" else -1
