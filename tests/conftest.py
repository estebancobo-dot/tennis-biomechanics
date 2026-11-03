import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


import pytest


@pytest.fixture(autouse=True)
def _court_by_its_lines(monkeypatch):
    """The court tests measure the line search: the 14-point detector (adopted 03-11) only where a test sets it
    (on the PC its model exists and the tests found its courts instead)."""
    from tennisbio import court
    monkeypatch.setitem(court._TCD, "m", None)
