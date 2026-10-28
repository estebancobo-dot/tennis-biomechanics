"""The iGPU lost in the middle of a run (DirectML 887A0005, PC 28-10): the session recovers and the call
is repeated, so no stroke is lost."""
import pytest

from tennisbio.pose import estimator

LOST = RuntimeError("[ONNXRuntimeError] : 1 : FAIL : DmlExecutionProvider ... 887A0005 "
                    "The GPU device instance has been suspended.")


class Sess:
    def __init__(self, device, fails):
        self.device, self.fails = device, fails

    def get_providers(self):
        return ["CPUExecutionProvider"] if self.device == "cpu" else ["DmlExecutionProvider", "CPUExecutionProvider"]

    def run(self, out, feed):
        if self.fails:
            self.fails -= 1
            raise LOST
        return [self.device]


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setattr(estimator, "_dml_lost", False)


def make(plan):
    made = []

    def f(device):
        made.append(device)
        return Sess(device, plan.pop(0) if device != "cpu" and plan else 0)
    return f, made


def test_recreates_on_the_igpu_when_the_driver_comes_back():
    f, made = make([1, 0])
    s = estimator.RecoveringSession(f, "dml")
    assert s.run(None, {}) == ["dml"] and made == ["dml", "dml"] and s.recoveries == 1
    assert estimator._dml_lost is False


def test_falls_back_to_the_cpu_and_new_sessions_skip_the_igpu(monkeypatch):
    f, made = make([1, 1])
    s = estimator.RecoveringSession(f, "dml")
    assert s.run(None, {}) == ["cpu"] and made == ["dml", "dml", "cpu"]
    assert estimator._dml_lost is True
    assert s.run(None, {}) == ["cpu"]                                       # stays on the CPU
    got = []
    monkeypatch.setattr(estimator, "_new_session", lambda p, d, *a: got.append(d) or Sess(d, 0))
    estimator._ort_session("m.onnx", "dml")
    assert got == ["cpu"]


def test_other_errors_are_not_hidden():
    class Bad(Sess):
        def run(self, out, feed):
            raise ValueError("wrong input shape")
    s = estimator.RecoveringSession(lambda d: Bad(d, 0), "dml")
    with pytest.raises(ValueError):
        s.run(None, {})


def test_lost_on_the_cpu_is_raised():
    s = estimator.RecoveringSession(lambda d: Sess(d, 5), "cpu")
    with pytest.raises(RuntimeError):
        s.run(None, {})


def test_wrapped_session_attributes_pass_through():
    s = estimator.RecoveringSession(lambda d: Sess(d, 0), "dml")
    assert s.get_providers()[0] == "DmlExecutionProvider"
