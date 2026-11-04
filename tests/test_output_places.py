"""Requests #81 (the size of the outputs, and checks that cost no tokens) and #82 (where the outputs are written, what
goes to git, what is reused): videos and outputs live outside the repository at the paths of config/local.yaml, git
gets only code (the PC's logs go to their own branch, pc-logs, with each output folder's size), and the checks run in
Python on the PC without any assistant. The reuse (cache per stage) is test_pipeline. Run on the PC with the other
tests (pruebas.xml), so the audit ties both requests to this module."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tennisbio import config

ROOT = Path(__file__).resolve().parents[1]
WIN = ROOT / "scripts" / "windows"
MEDIA = (".mp4", ".mkv", ".mov", ".avi", ".webm", ".wav", ".npz", ".parquet")


def test_videos_outputs_and_the_local_config_never_go_to_git():
    ign = {ln.strip() for ln in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()}
    need = {"*.mp4", "*.mkv", "*.wav", "*.npz", "*.parquet", "output/", "videos/", "config/local.yaml", "config/matches.yaml"}
    assert need <= ign, need - ign


@pytest.mark.skipif(shutil.which("git") is None or not (ROOT / ".git").exists(), reason="sin git")
def test_no_video_or_data_file_is_in_the_repository():
    r = subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and r.stdout.strip(), r.stderr
    bad = [f for f in r.stdout.splitlines() if f.lower().endswith(MEDIA)]
    assert not bad, bad


def test_the_paths_come_from_the_local_config(tmp_path, monkeypatch):
    monkeypatch.delenv("TENNISBIO_SANDBOX", raising=False)
    ex =(ROOT / "config" / "local.example.yaml").read_text(encoding="utf-8")
    assert re.search(r"output:\s*['\"]?C:\\\\?tenis\\\\?output", ex), ex[:400]
    # the configuration in the repository names no folder of the PC; local.yaml (not versioned) does
    shutil.copy(ROOT / "config" / "default.yaml", tmp_path / "default.yaml")
    assert not (config.load_config(tmp_path).get("paths") or {}).get("output")
    (tmp_path / "local.yaml").write_text("paths:\n  videos: 'D:\\v'\n  output: 'D:\\o'\n", encoding="utf-8")
    assert config.load_config(tmp_path)["paths"] == {"videos": "D:\\v", "output": "D:\\o"}
    bad = []
    for f in (ROOT / "src" / "tennisbio").rglob("*.py"):
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            # a path built from C:\tenis in the code (messages and docstrings may name it)
            if re.search(r"Path\(\s*r?[\"'][A-Za-z]:[\\/]", code):
                bad.append(f"{f.name}:{i}: {line.strip()}")
    assert not bad, bad


def test_the_pcs_logs_go_to_their_own_branch_with_the_size_of_each_output_folder():
    com = (WIN / "comun.ps1").read_text(encoding="ascii")
    up = com[com.index("function Subir-Registros"):com.index("function Actualizar-Codigo")]
    assert "push -q origin pc-logs" in up and 'Copy-Item "$Base\\output\\*.log"' in up
    assert '$tam = "$d\\tamanos.txt"' in up and '"fecha: $(Get-Date -Format s)" | Set-Content $tam' in up
    assert re.search(r'"\{0,10\} MB  \{1\}" -f \$mb', up)              # each output folder in MB


def test_the_checks_run_in_python_on_the_pc_without_any_assistant():
    """The audit, the honest status and the cycle's own review read files only: no network, no assistant, no tokens."""
    files = [ROOT / "src" / "tennisbio" / "audit.py", ROOT / "src" / "tennisbio" / "real_status.py",
             ROOT / "scripts" / "auto_cycle.py", ROOT / "scripts" / "review_pc_run.py", ROOT / "scripts" / "real_status.py"]
    bad = []
    for f in files:
        if not f.exists():
            continue
        t = f.read_text(encoding="utf-8")
        for rx in (r"^\s*(import|from)\s+(anthropic|openai|requests|urllib|http\.client|socket)\b", r"\bclaude\s+-p\b"):
            if re.search(rx, t, re.M):
                bad.append(f"{f.name}: {rx}")
    assert not bad, bad
    for f in WIN.glob("*.ps1"):                                         # the PC never calls an assistant itself
        for line in f.read_text(encoding="ascii").splitlines():
            code = line.split("#", 1)[0]
            assert not re.search(r"(^|[&|;]\s*)claude(\.exe)?\s", code.strip()), f"{f.name}: {line.strip()}"
