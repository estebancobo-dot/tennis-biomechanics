"""«Pausa arriba» (technique.loaded_pause): synthetic strokes with a known stop of the hand, no stop,
and slow continuous loops, at 25 and 50 fps (validation in docs/validacion.md)."""
import numpy as np
import pytest

from tennisbio.technique import LOOP_PAUSE_S, loaded_pause
from tennisbio.validation.pause_eval import _loaded_from, dwell, loaded_pause_v1, synth_wrist, synthetic


@pytest.mark.parametrize("fps", [25, 50])
@pytest.mark.parametrize("pause", [0.08, 0.16, 0.3])
def test_known_pause_is_measured(fps, pause):
    dw, tb, top, imp = synth_wrist(fps, pause_s=pause, seed=1, noise=0.004)
    ld = _loaded_from(dw, fps, imp)
    m = loaded_pause(dw, fps, ld, tb, imp)
    assert abs(m - pause) <= 0.04 + 1e-9          # ±1 frame at 25 fps, ±2 at 50 fps


@pytest.mark.parametrize("fps", [25, 50])
def test_no_pause_reads_zero(fps):
    dw, tb, top, imp = synth_wrist(fps, seed=2, noise=0.004)
    assert loaded_pause(dw, fps, _loaded_from(dw, fps, imp), tb, imp) == 0


@pytest.mark.parametrize("fps", [25, 50])
@pytest.mark.parametrize("loop", [0.6, 1.0, 1.5])
def test_slow_continuous_loop_is_not_a_pause(fps, loop):
    dw, tb, top, imp = synth_wrist(fps, loop_speed=loop, seed=3, noise=0.004)
    assert loaded_pause(dw, fps, _loaded_from(dw, fps, imp), tb, imp) < LOOP_PAUSE_S


def test_former_threshold_took_the_loop_for_a_pause():
    """The defect that motivated the change: 30 % of the swing peak is above a slow backswing."""
    dw, tb, top, imp = synth_wrist(50, loop_speed=1.0, seed=3)
    assert loaded_pause_v1(dw, 50, _loaded_from(dw, 50, imp), tb, imp) >= LOOP_PAUSE_S


def test_same_pause_at_25_and_50_fps():
    a = synth_wrist(50, pause_s=0.2, seed=4, noise=0.003)
    dw, tb, _, imp = a
    m50 = loaded_pause(dw, 50, _loaded_from(dw, 50, imp), tb, imp)
    d25 = dw[::2]
    m25 = loaded_pause(d25, 25, _loaded_from(d25, 25, imp // 2), tb // 2, imp // 2)
    assert abs(m50 - m25) <= 0.04 + 1e-9


def test_stillness_of_the_ready_position_is_not_a_pause():
    """No takeback found and the hand still all the way back: unbounded, not measured."""
    fps = 25
    dw = np.zeros((60, 2))
    dw[45:, 0] = -np.linspace(0, 0.8, 15)            # only the forward swing moves
    assert loaded_pause(dw, fps, 40, None, 52) is None


def test_unmeasurable_without_wrist():
    dw = np.full((60, 2), np.nan)
    assert loaded_pause(dw, 25, 40, 30, 52) is None


def test_dwell_reference():
    pos = np.zeros((30, 2))
    pos[:10, 0] = np.linspace(-1, -0.1, 10)
    pos[20:, 0] = np.linspace(0.1, 1, 10)
    assert dwell(pos, 25, 15, 0, 30, 0.05, 2) == pytest.approx(9 / 25)     # frames 10-19 inside the disc
    pos[12:18] = np.nan
    assert dwell(pos, 25, 15, 10, 20, 0.05, 2) is None                       # mostly unseen


def test_synthetic_summary():
    r = synthetic(seeds=range(2), noise_list=(0.004,))
    for v in r.values():
        assert v["pause_within_40ms"] >= 0.9 and v["no_pause_max_s"] == 0 and v["loop_flagged"] == 0
