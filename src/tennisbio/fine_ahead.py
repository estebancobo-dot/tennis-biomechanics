"""Ball tracks of the fine pass computed ahead, on the CPU, while the pose runs on the iGPU.

The fine pass spends about as long in the ball model (TrackNetV3) as in the pose, one after the
other, both on the iGPU, while most CPU cores wait. Here a background thread cuts the windows and
runs the ball model on them on the CPU (`fine_speed.ball_ahead`), at the same time as the main thread
runs the pose. The two walk the list of windows from opposite ends: the main thread from the first
window as always, the background thread from the last one backwards. Each window is done by
whichever claims it first, so they meet once, somewhere in the middle; nothing is computed twice
and the main thread never waits for the background thread except on the one window it may be
finishing when they meet. Without the background thread (or if it fails on a window) the main
thread computes that window's ball itself, on the iGPU, exactly as before.

Each job writes the ball cache the fine pass reads (clip_pipeline.window_ball), so what the main
thread then does with the window is unchanged: the same gate decision, pose, strokes. The ball is
the same model with the same inputs; only the device (CPU instead of the iGPU) differs, which
changes the heatmap by float rounding at most.
"""
import threading
import time
from typing import Callable


class BallAhead:
    """Background worker over the windows 0..n-1. job(i) cuts window i and caches its ball.

    claim(i), called by the main thread before it starts window i, returns once window i is either
    done by the worker (its ball cache is there) or will not be touched by it (the main thread does it).
    The worker never starts a window at or right after the one the main thread is on (gap)."""

    def __init__(self, n: int, job: Callable[[int], None], gap: int = 1):
        self.n, self.job, self.gap = n, job, max(0, int(gap))
        self.state = ["todo"] * n            # todo | running | done | failed | main
        self.seconds: dict[int, float] = {}  # time the worker spent on each window it did
        self.errors: dict[int, str] = {}
        self.waited = 0.0                    # time the main thread waited for the worker
        self.main_at = -1
        self._stop = False
        self._cv = threading.Condition()
        self._thread = threading.Thread(target=self._run, name="bola-en-paralelo", daemon=True)

    def start(self) -> "BallAhead":
        self._thread.start()
        return self

    def _next(self) -> int | None:
        with self._cv:
            if self._stop:
                return None
            for j in range(self.n - 1, -1, -1):
                st = self.state[j]
                if st in ("done", "failed", "running"):
                    continue
                if st == "main" or j <= self.main_at + self.gap:
                    return None              # met the main thread: the rest is its
                self.state[j] = "running"
                return j
            return None

    def _run(self):
        while True:
            j = self._next()
            if j is None:
                break
            t_ = time.time()
            ok = True
            try:
                self.job(j)
            except Exception as e:           # this window is left to the main thread, as without the worker
                ok = False
                self.errors[j] = f"{type(e).__name__}: {e}"
            with self._cv:
                self.state[j] = "done" if ok else "failed"
                self.seconds[j] = time.time() - t_
                self._cv.notify_all()
            if not ok and len(self.errors) >= 3:
                break                        # something is wrong with the worker itself: stop trying

    def claim(self, i: int) -> bool:
        """The main thread is about to do window i. True when the worker did it (its ball is cached)."""
        with self._cv:
            self.main_at = max(self.main_at, i)
            t_ = time.time()
            while self.state[i] == "running":
                self._cv.wait()
            self.waited += time.time() - t_
            if self.state[i] in ("todo", "failed"):
                self.state[i] = "main"
            return self.state[i] == "done"

    def close(self, timeout: float | None = None):
        """No new windows; the one being done is finished (its files are written whole)."""
        with self._cv:
            self._stop = True
        if self._thread.is_alive():
            self._thread.join(timeout)

    @property
    def done(self) -> list[int]:
        return [i for i, s in enumerate(self.state) if s == "done"]


def ahead_enabled(cfg: dict, n_windows: int, has_ball: bool) -> bool:
    """`fine_speed.ball_ahead` (default on) with the pose on the iGPU (`device: dml`), the ball model
    present and at least two windows. With the pose on the CPU both models would share the same
    cores (as pipeline.py pairs stages only when they use different resources)."""
    fs = cfg.get("fine_speed") or {}
    return bool(fs.get("ball_ahead", True)) and cfg.get("device", "cpu") == "dml" and has_ball and n_windows >= 2
