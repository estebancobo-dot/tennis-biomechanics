"""What happened with the shot: out, into the net, probable winner, or the rally went on.

Decided from the ball (where it bounced, whether it crossed the net, whether the opponent hit it
back) and from the match context (impact sounds after it, the end of the main-camera shot). When
the evidence is not clear the outcome stays unknown rather than guessed.
"""
import numpy as np

OUTCOMES_ES = {"out": "error (fuera)", "net": "error (red)", "winner": "ganador (probable)", "rally": "sigue"}


def crossed_net(ball: np.ndarray | None, impact: int, fps: float, net_y: float, side="near",
                within_s=1.0, margin_px=6.0) -> bool | None:
    """Did her shot get past the net in the image? None when the ball is barely seen."""
    if ball is None:
        return None
    seg = ball[impact + 1:impact + 1 + int(within_s * fps), 1]
    seg = seg[np.isfinite(seg)]
    if len(seg) < max(3, int(0.2 * fps)):
        return None
    return bool((seg < net_y - margin_px).any()) if side == "near" else bool((seg > net_y + margin_px).any())


def shot_outcome(impact_t: float, shot_in: bool | None, shot_bounce_t: float | None, opp_return_t: float | None,
                 onsets: np.ndarray, shot_end_t: float | None, crossed: bool | None,
                 return_window=(0.35, 2.6), end_s=5.0) -> str | None:
    """'out' | 'net' | 'winner' | 'rally' | None (unknown).

    onsets: impact-like sound times of the match (s); shot_end_t: end of the main-camera shot
    that contains the stroke (a cut usually means the point is over)."""
    if shot_in is False:
        return "out"
    onsets = np.asarray(onsets, float)
    after = onsets[(onsets > impact_t + 0.3) & (onsets < impact_t + end_s)]
    point_over = (shot_end_t is not None and shot_end_t - impact_t < end_s) or len(after) == 0
    if crossed is False and shot_bounce_t is None:
        return "net" if point_over else None
    if opp_return_t is not None:
        return "rally"
    lo, hi = impact_t + return_window[0], impact_t + return_window[1]
    sounds = onsets[(onsets > lo) & (onsets < hi)]
    if shot_bounce_t is not None:              # the bounce of her own ball also makes a sound
        sounds = sounds[np.abs(sounds - shot_bounce_t) > 0.15]
    if len(sounds):
        return "rally"
    if shot_in is True and point_over:
        return "winner"
    return None
