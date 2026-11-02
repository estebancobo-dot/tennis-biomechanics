"""Every user request is in exactly one work package of the plan (config/plan_peticiones.yaml)."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("real_status", ROOT / "scripts" / "real_status.py")
rs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rs)


def test_every_request_in_one_package():
    ids = [rid for rid, _, st in rs.registry() if st != "NO APLICA"]
    seen = [i for p in rs.packages().values() for i in p["peticiones"]]
    assert sorted(set(ids) - set(seen)) == []                       # none left out
    assert sorted({i for i in seen if seen.count(i) > 1}) == []      # none in two packages
    assert sorted(set(seen) - set(ids)) == []                       # no package names a request that is not there
