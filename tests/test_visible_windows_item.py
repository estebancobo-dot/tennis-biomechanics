"""#261 (12-11): no empty console of ours on the PC's screen, read from scripts/ventanas_visibles.py's list."""
import json

from tennisbio.audit import WINDOWS_ITEM, infrastructure_items, visible_windows_item

# what request 242 found on the PC on 12-11 (the worker's successor in a Windows Terminal window)
TERMINAL = {"name": "WindowsTerminal", "title": "C:\\tenis\\tennis-biomech\\.venv\\Scripts\\python.exe", "pid": 7592,
            "cmd": "\"C:\\Program Files\\WindowsApps\\Microsoft.WindowsTerminal_1.24\\WindowsTerminal.exe\" -Embedding",
            "parent": "svchost.exe", "start": "11/12/2026 11:08:21"}
OTHERS = [{"name": "claude", "title": "Claude", "cmd": "claude.exe"},
          {"name": "python", "title": "Tennisbio", "cmd": "python -m tennisbio.cli app ventana"},     # the application
          {"name": "WindowsTerminal", "title": "Windows PowerShell", "cmd": "WindowsTerminal.exe"},   # one of the user's
          {"name": "explorer", "title": "", "cmd": "C:\\WINDOWS\\Explorer.EXE"}]


def _write(base, rep):
    (base / "capturas_diag").mkdir(parents=True, exist_ok=True)
    (base / "capturas_diag" / "ventanas_visibles.json").write_text(json.dumps(rep), encoding="utf-8")


def test_the_empty_terminal_of_12_11_fails(tmp_path):
    _write(tmp_path, {"fecha": "2026-11-12 11:40:00", "ventanas": OTHERS + [TERMINAL]})
    it = visible_windows_item([tmp_path], today="2026-11-12")
    assert it["name"] == WINDOWS_ITEM and it["status"] == "falta", it
    assert "WindowsTerminal" in it["detail"] and "11:08:21" in it["detail"]


def test_the_list_of_242_without_date_fails_too(tmp_path):
    _write(tmp_path, OTHERS + [TERMINAL])               # the first version of the script wrote a bare list
    assert visible_windows_item([tmp_path], today="2026-11-12")["status"] == "falta"


def test_the_app_window_and_the_users_own_terminal_do_not_count(tmp_path):
    _write(tmp_path, {"fecha": "2026-11-12 12:00:00", "ventanas": OTHERS})
    assert visible_windows_item([tmp_path], today="2026-11-12")["status"] == "ok"


def test_a_single_window_object_and_an_old_list(tmp_path):
    _write(tmp_path, {"fecha": "2026-11-12 12:00:00", "ventanas": TERMINAL})   # ConvertTo-Json of one item: an object
    assert visible_windows_item([tmp_path], today="2026-11-12")["status"] == "falta"
    _write(tmp_path, {"fecha": "2026-11-01 12:00:00", "ventanas": OTHERS})
    assert visible_windows_item([tmp_path], today="2026-11-12")["status"] == "aviso"


def test_without_the_list(tmp_path):
    assert visible_windows_item([tmp_path], today="2026-11-12")["status"] == "pocos datos"


def test_in_the_infrastructure_checks(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    _write(out, {"fecha": "2026-11-12 11:40:00", "ventanas": [TERMINAL]})
    it = next(i for i in infrastructure_items(out) if i["name"] == WINDOWS_ITEM)
    assert it["status"] == "falta"
