import os
import sys
from pathlib import Path

# 11-11: with the tests on several cores (pytest -n, pytest-xdist) each worker gets one thread for the numeric
# libraries; otherwise every worker starts as many as there are cores and they fight (2 s alone, 216 s at once)
if os.environ.get("PYTEST_XDIST_WORKER"):
    for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ.setdefault(_v, "1")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# 11-11 (R1 of the review of the Base): on the PC the background tests record which audit checks they make fail
_REC_DUMP = None
if os.environ.get("TENNISBIO_REC_CHECKS"):
    from tennisbio.check_coverage import install as _install_rec
    _REC_DUMP = _install_rec(os.environ["TENNISBIO_REC_CHECKS"])


def pytest_unconfigure(config):
    if _REC_DUMP is not None:
        _REC_DUMP()


import pytest


@pytest.fixture(autouse=True)
def _court_by_its_lines(monkeypatch):
    """The court tests measure the line search: the 14-point detector (adopted 03-11) only where a test sets it
    (on the PC its model exists and the tests found its courts instead)."""
    from tennisbio import court
    monkeypatch.setitem(court._TCD, "m", None)
