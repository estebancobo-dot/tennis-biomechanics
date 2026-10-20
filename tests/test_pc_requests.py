"""The queue of requests for the PC (config/peticion_pc.txt), read as ciclo_automatico.ps1 reads it."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import pc_requests as Q  # noqa: E402


def test_single_block_as_before():
    blocks = Q.parse("id: 39\naccion: entreno\npartidos: 16\nhoras: 14\nfps: 25\n# comentario: con dos puntos\n")
    assert blocks == [{"id": "39", "accion": "entreno", "partidos": "16", "horas": "14", "fps": "25"}]
    assert Q.pending(blocks, []) == blocks
    assert Q.pending(blocks, ["39"]) == []


def test_several_blocks_in_order():
    text = "id: 40\naccion: recall\npuntos: 5\n---\nid: 41\naccion: diag\n  ---  \nid: 42\naccion: informe\ncarpeta: _poc9_largo\n"
    blocks = Q.parse(text)
    assert [b["id"] for b in blocks] == ["40", "41", "42"]
    assert blocks[0] == {"id": "40", "accion": "recall", "puntos": "5"}
    assert "puntos" not in blocks[1]                         # parameters do not leak between blocks
    assert blocks[2]["carpeta"] == "_poc9_largo"
    assert [b["id"] for b in Q.pending(blocks, {"40"})] == ["41", "42"]
    assert [b["id"] for b in Q.pending(blocks, ["41"])] == ["40", "42"]   # order kept, done ones skipped
    assert Q.pending(blocks, ["40", "41", "42"]) == []


def test_comments_blank_lines_and_separators():
    text = ("# cabecera\n\n---\n---\nid: 1\n# id: 99\n#     ---\naccion: poc\n\n# ejemplo:\n#   accion: borrar\n---\n"
            "# solo comentarios\n---\n")
    assert Q.parse(text) == [{"id": "1", "accion": "poc"}]   # empty blocks and commented keys/separators ignored


def test_unknown_keys_values_and_case():
    b = Q.parse("ID: 7\nAccion: youtube\nurls: https://a.b/x?v=1, https://c.d/y\nraro_param: 3 \nsin valor:\nid: 8\n")[0]
    assert b["id"] == "8"                                    # last value wins, keys case-insensitive
    assert b["accion"] == "youtube"
    assert b["urls"] == "https://a.b/x?v=1, https://c.d/y"   # only the first colon splits
    assert b["raro_param"] == "3"
    assert "sin" not in b and "sin valor" not in b           # empty value or key with a space: not a parameter


def test_blocks_that_never_run():
    blocks = Q.parse("id: 1\naccion: ninguna\n---\naccion: poc\n---\nid: 3\n---\nid: 4\naccion: Ninguna\n---\nid: 5\naccion: largo\n")
    assert [b["id"] for b in Q.pending(blocks, [])] == ["5"]


def test_done_list_and_old_done_file(tmp_path):
    (tmp_path / "peticiones_hechas.txt").write_text("39\r\n40\n\n", encoding="utf-8")
    (tmp_path / "peticion_hecha.txt").write_text(" 41 \n", encoding="utf-8")
    done = Q.read_done(tmp_path / "peticiones_hechas.txt", tmp_path / "peticion_hecha.txt", tmp_path / "falta.txt")
    assert done == {"39", "40", "41"}
    blocks = Q.parse("\n---\n".join(f"id: {i}\naccion: diag" for i in (39, 40, 41, 42)))
    assert [b["id"] for b in Q.pending(blocks, done)] == ["42"]


def test_param_for_scripts_launched_by_an_older_cycle(tmp_path):
    f = tmp_path / "peticion_pc.txt"
    f.write_text("id: 40\naccion: recall\nfps: 50\n---\nid: 41\naccion: entreno\nfps: 25\n---\nid: 42\naccion: entreno\n",
                 encoding="utf-8")
    assert Q.param("fps", "entreno", f) == "25"
    assert Q.param("fps", "diag", f) is None
    assert Q.param("fps", "entreno", tmp_path / "no.txt") is None


def test_current_request_file_parses():
    blocks = Q.load()
    assert blocks and all(b.get("id") and b.get("accion") for b in blocks)
    assert len({b["id"] for b in blocks}) == len(blocks)     # ids unique in the queue
    assert (ROOT / "config" / "peticion_pc.txt").read_text(encoding="utf-8").isascii()


def test_cycle_script_reads_the_queue():
    """ciclo_automatico.ps1 uses the same separator and key regex, a done list, and loops over the queue."""
    ps1 = (ROOT / "scripts" / "windows" / "ciclo_automatico.ps1").read_text(encoding="utf-8")
    assert ps1.isascii()
    assert '"^\\s*---\\s*$"' in ps1 and '"^\\s*(\\w+)\\s*:\\s*(.+?)\\s*$"' in ps1
    assert Q.SEPARATOR.pattern == r"^\s*---\s*$" and Q.KEY_VALUE.pattern == r"^\s*(\w+)\s*:\s*(.+?)\s*$"
    assert "peticiones_hechas.txt" in ps1 and "peticion_hecha.txt" in ps1
    loop = ps1[ps1.index("function Hacer-Peticiones"):ps1.index("function Hacer-Peticion(")]
    assert "PeticionDesconocida" in loop and "FETCH_HEAD" in loop
    body = ps1[ps1.index("function Hacer-Peticion("):ps1.index("# el equipo no se suspende")]
    unknown = body[body.index("una accion nueva llega"):]
    assert "$script:PeticionDesconocida = $true" in unknown   # unknown action: not done, the queue stops
    assert "Hacer-Peticion " not in ps1.replace("Hacer-Peticion $p", "")   # every call goes through the loop
