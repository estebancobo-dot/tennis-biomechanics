"""Moved to tennisbio.pose.motionagformer when it was adopted (03-11, request 83); kept for the benchmark."""
from ..pose.motionagformer import *  # noqa: F401,F403
from ..pose.motionagformer import (COCO_TO_H36M, H36M_FROM_COCO, H36M_L_HIP, H36M_L_SH, H36M_R_HIP,  # noqa: F401
                                   H36M_R_SH, LEFT, RIGHT, MotionAGFormerLifter, clips, coco_to_h36m, flip,
                                   line_yaw_world, normalise)
