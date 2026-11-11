"""Pytest plugin (11-11, review of the Base #260): records every audit check the tests produce and its status
(tennisbio.audit._item), to find the checks no test ever drives to a failing status. Use:
REC_OUT=<dir> PYTHONPATH=scripts/dev uv run pytest -q -n 4 -p rec_audit_items; then compare <dir>/rec_*.json with
the real audit (auditoria_partidos.json). Seed of task R1."""
import json, os, re
_REC = set()

def _norm(name):
    n = str(name).split(":")[0]
    n = re.sub(r"\d+", "N", n)
    return n.strip()

def pytest_configure(config):
    import tennisbio.audit as a
    orig = a._item
    def wrapped(req, area, name, status, detail, **kw):
        _REC.add((str(area), _norm(name), str(status)))
        return orig(req, area, name, status, detail, **kw)
    a._item = wrapped

def pytest_unconfigure(config):
    wid = os.environ.get("PYTEST_XDIST_WORKER", "main")
    out = os.environ["REC_OUT"]
    with open(f"{out}/rec_{wid}.json", "w", encoding="utf-8") as f:
        json.dump(sorted(_REC), f, ensure_ascii=False)
