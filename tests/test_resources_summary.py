import importlib.util
from pathlib import Path

_f = Path(__file__).resolve().parents[1] / "scripts" / "resources_summary.py"
_spec = importlib.util.spec_from_file_location("resources_summary", _f)
rs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rs)

HEAD = "hora,partido,etapa,cpu_total,cpu_python,cpu_ffmpeg,ram_usada_gb,ram_total_gb,ram_python_gb,gpu_3d,gpu_compute,gpu_decode,disco\n"


def test_stages_and_what_limits_them(tmp_path):
    f = tmp_path / "r.csv"
    f.write_text(HEAD
                 + "t,zheng,views,10.0,6.0,4.0,8.0,19.8,1.0,0.0,0.0,5.0,3.0\n"
                 + "t,zheng,views,12.0,6.0,6.0,8.2,19.8,1.0,0.0,0.0,5.0,3.0\n"
                 + "t,zheng,fine,40.0,30.0,5.0,12.0,19.8,4.0,95.0,0.0,0.0,2.0\n"
                 + "t,zheng,fine,45.0,30.0,5.0,,19.8,4.0,90.0,0.0,0.0,2.0\n", encoding="ascii")
    s = {g["etapa"]: g for g in rs.summarize(rs.read([f]))}
    assert s["views"]["limite"].startswith("equipo infrautilizado") and s["views"]["minutos"] == 0.5
    assert s["views"]["stats"]["cpu_total"] == (10.0, 11.0, 12.0)
    assert s["fine"]["limite"] == "iGPU al límite"
    assert s["fine"]["stats"]["ram_usada_gb"] == (12.0, 12.0, 12.0)          # an empty sample is skipped
    assert "| zheng | views | 0.5 |" in rs.markdown(list(s.values()))
