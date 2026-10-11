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
SCHEMAS = {"coco17": COCO17, "halpe26": HALPE26}
PAIRED = ["shoulder", "elbow", "wrist", "hip", "knee", "ankle"]

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
    """Index lookup for a keypoint schema, with dominant/non-dominant aliases."""

    def __init__(self, schema: str = "coco17", hand: str = "right"):
        if hand not in ("right", "left"):
            raise ValueError(f"hand must be 'right' or 'left', got {hand!r}")
        self.schema, self.hand = schema, hand
        self.names = SCHEMAS[schema]
        self.idx = {n: i for i, n in enumerate(self.names)}
        dom, non = (hand, "left" if hand == "right" else "right")
        for j in PAIRED:
            self.idx[f"dom_{j}"] = self.idx[f"{dom}_{j}"]
            self.idx[f"non_{j}"] = self.idx[f"{non}_{j}"]

    def __getitem__(self, name: str) -> int:
        return self.idx[name]

    def __len__(self) -> int:
        return len(self.names)

    @property
    def dom_sign(self) -> int:
        """+1 if the dominant side is image-right when seen from behind, -1 otherwise."""
        return 1 if self.hand == "right" else -1
