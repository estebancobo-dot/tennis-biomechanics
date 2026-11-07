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


HEAD2 = HEAD.strip() + ",progreso_hora,progreso_pct\n"
RUN = "2026-11-07T16:05:20,final,fine_doubtful,80.0,60.0,5.0,12.0,19.8,4.0,90.0,0.0,0.0,2.0,2026-11-07 16:05:10,40.0\n"
END = "2026-11-07T16:05:50,final,fine_doubtful,80.0,60.0,5.0,12.0,19.8,4.0,90.0,0.0,0.0,2.0,2026-11-07 16:05:45,100.0\n"
LATE = "2026-11-07T16:40:04,final,fine_doubtful,20.0,10.0,0.0,19.1,19.8,1.0,0.0,0.0,0.0,2.0,2026-11-07 16:05:45,100.0\n"


def test_samples_after_the_stage_ended_are_not_the_stage(tmp_path):
    """07-11 (#230): progreso.json keeps the last stage at 100 %; what runs after (report, audit, another job) is
    not that stage: the final's fine_doubtful took 36 s, but 71.8 min of samples carried its name."""
    f = tmp_path / "r.csv"
    f.write_text(HEAD2 + RUN + END + LATE + LATE.replace("16:40:04", "16:40:19"), encoding="ascii")
    s = {g["etapa"]: g for g in rs.summarize(rs.read([f]))}
    assert s["fine_doubtful"]["minutos"] == 0.5 and s["fine_doubtful"]["limite"] == "iGPU al límite"
    assert s["fine_doubtful"]["stats"]["ram_usada_gb"][2] == 12.0                # the RAM of later work is not hers
    assert s["tras fine_doubtful"]["after"] and s["tras fine_doubtful"]["limite"].startswith("fuera de la etapa")
    assert s["tras fine_doubtful"]["minutos"] == 0.5
    assert not rs.stale({"hora": "t", "progreso_pct": ""})                       # old CSVs: as before


def test_the_audit_leaves_them_apart(tmp_path):
    from tennisbio import audit
    d = tmp_path / "recursos"
    d.mkdir()
    (d / "recursos_2026-11-07_1640.csv").write_text(HEAD2 + RUN + LATE, encoding="ascii")
    it = audit.resources_items(tmp_path)[0]
    assert it["status"] == "ok" and "fine_doubtful (0.2 min)" in it["detail"], it
    assert "tras fine_doubtful" not in it["detail"] and "etapa ya terminada" in it["detail"], it
