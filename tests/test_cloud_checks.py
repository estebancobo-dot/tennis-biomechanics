"""T3 (14-11): the audit's checks of B1, B7 and B8 in the cloud, read from the volume's own files (runs/, cola/)."""
import json
import sys
import time
from pathlib import Path

from tennisbio.audit import cloud_items, cloud_queue_item, cloud_root, cloud_use_item, progress_item

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cloud"))
import nube  # noqa: E402


def _w(p: Path, d) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d), encoding="utf-8")


def test_resources_of_each_stage():
    """The samples inside each stage's span (its end minus its seconds) are that stage's."""
    end = time.mktime(time.strptime("2026-11-14 18:00:00", "%Y-%m-%d %H:%M:%S"))
    man = {"scenes": {"seconds": 300.0, "finished": "2026-11-14 17:50:00"},
           "fine": {"seconds": 600.0, "finished": "2026-11-14 18:00:00"}, "probe": {"seconds": 2.0}, "x": "y"}
    rows = [{"t": end - 900, "cpu_pct": 90.0, "gpu_pct": 5.0}, {"t": end - 300, "cpu_pct": 40.0, "gpu_pct": 80.0},
            {"t": end - 60, "cpu_pct": 50.0, "gpu_pct": 90.0, "gpu1_pct": 0.0}]
    got = nube.per_stage(rows, man)
    assert set(got) == {"scenes", "fine"}
    assert got["scenes"]["muestras"] == 1 and got["scenes"]["cpu_pct"]["media"] == 90.0
    assert got["fine"]["muestras"] == 2 and got["fine"]["gpu_pct"] == {"media": 85.0, "max": 90.0}
    assert got["fine"]["gpu1_pct"]["max"] == 0.0 and got["fine"]["s"] == 600
    assert nube.per_stage([], {"fine": {"seconds": 5, "finished": "no es una fecha"}}) == {}


def test_cloud_use_per_stage(tmp_path):
    assert cloud_use_item(None, ["m"])["status"] == "aviso"                 # not the cloud
    assert cloud_use_item(tmp_path, ["m"])["status"] == "aviso"             # no run measured yet
    per = {"fine": {"s": 1800, "muestras": 30, "gpu_pct": {"media": 70, "max": 99}, "gpu1_pct": {"media": 0, "max": 3},
                    "cpu_pct": {"media": 55, "max": 90}, "ram_gb": {"media": 8, "max": 11.2}},
           "probe": {"s": 2, "muestras": 0}}
    _w(tmp_path / "runs" / "kaggle_m" / "estado.json",
       {"partido": "m", "estado": "hecho", "fin": "2026-11-14 19:00:00", "donde": "kaggle", "recursos_por_etapa": per})
    it = cloud_use_item(tmp_path, ["m", "n"])
    assert it["status"] == "ok" and "fine (30 min): GPU 70/99 %, 2.ª GPU 0/3 %, CPU 55/90 %, RAM máx 11.2 GB" in it["detail"]
    assert "1 de 2" in it["detail"]


def test_cloud_queue(tmp_path):
    now = time.time()
    assert cloud_queue_item(None, [])["status"] == "aviso"
    assert cloud_queue_item(tmp_path, ["m"])["status"] == "falta"           # the queue never wrote to the volume
    state = {"p_m": {"accion": "prueba", "partido": "m", "estado": "hecho"},
             "m": {"accion": "partido", "partido": "m", "estado": "hecho"},
             "x": {"accion": "medir", "estado": "error", "resultado": {"nota": "Kaggle sin GPU"}}}
    _w(tmp_path / "cola" / "estado.json", state)
    _w(tmp_path / "cola" / "vuelta.json", {"ts": now - 600})
    it = cloud_queue_item(tmp_path, ["m"], now)
    assert it["status"] == "ok" and "1 de 1" in it["detail"] and "Kaggle sin GPU" in it["detail"]
    assert cloud_queue_item(tmp_path, ["m", "n"], now)["status"] == "aviso"           # n not analysed by the queue
    assert cloud_queue_item(tmp_path, ["m"], now + 3 * 3600)["status"] == "aviso"      # the chain of passes broke
    _w(tmp_path / "cola" / "estado.json", {**state, "y": {"estado": "error"}})
    assert cloud_queue_item(tmp_path, ["m"], now)["status"] == "falta"               # an error that says nothing


def test_cloud_items_need_the_cloud_root(tmp_path):
    assert cloud_root({"paths": {"cloud": str(tmp_path)}}) == tmp_path
    assert cloud_root({"paths": {"output": "x"}}) is None
    items = cloud_items([tmp_path / "m"], {"paths": {"cloud": str(tmp_path)}})
    assert [i["name"] for i in items] == ["Uso de la nube por etapa (CPU, GPU y memoria)", "Cola de la nube"]
    # the names the packages' main tests look for (config/plan_peticiones.yaml: B1, B7, B8)
    import re

    import yaml
    plan = yaml.safe_load((ROOT / "config" / "plan_peticiones.yaml").read_text(encoding="utf-8"))
    pats = [p for k in ("B1", "B7", "B8") for p in plan["paquetes"][k].get("prueba") or []]
    for name in ("Uso de la nube por etapa", "Cola de la nube"):
        assert any(re.match(p, name) for p in pats)


def test_progress_seen_in_the_cloud_queue(tmp_path):
    """#291: in the cloud the progress of each job is in the queue's state (no progreso.json next to the matches)."""
    _w(tmp_path / "cola" / "estado.json", {"g": {"estado": "hecho", "progreso": "fine: 93 % (51/55) (18:42:10)"}})
    it = progress_item([tmp_path / "output", tmp_path])
    assert it["status"] == "ok" and "fine: 93 %" in it["detail"]
