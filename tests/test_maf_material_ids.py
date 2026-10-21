"""Synthetic tests for the MAF library material ID list (issue #488)."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "maf_material_ids", ROOT / "tools" / "library" / "maf_material_ids.py"
)
mat_ids = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mat_ids)

TOOL = ROOT / "tools" / "library" / "maf_material_ids.py"


def _materials(*files):
    return {"blender": "5.1.2", "files": list(files)}


def _file(fbx, *mats):
    return {"fbx": fbx, "materials": [dict(m) for m in mats]}


def _mat(name, hexc=None, textures=()):
    m = {"name": name, "hex": hexc, "textures": [{"filepath": t} for t in textures]}
    return m


def _catalogue(n=931):
    return {"entries": [{"id": f"MAF_{i:04d}"} for i in range(n)]}


def _seed():
    return {"atlas": {"materials": [
        {"name": "steel_ral7047"}, {"name": "larch_light_oak"},
        {"name": "hpl_satin_wood"}, {"name": "rope_pp"},
    ]}}


def _ral():
    return {"note": "display only", "colors": {"7047": "#D0D0D0", "9005": "#0A0A0A"}}


def _write(tmp, name, doc):
    p = tmp / name
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return p


def _run(tmp, materials, extra_args=(), expect_ok=True):
    catalogue = _write(tmp, "catalogue.json", _catalogue())
    seed = _write(tmp, "seed.json", _seed())
    ral = _write(tmp, "ral.json", _ral())
    mats = _write(tmp, "materials.json", materials)
    out = tmp / "out"
    cmd = [sys.executable, str(TOOL),
           "--materials", str(mats), "--catalogue", str(catalogue),
           "--seed", str(seed), "--ral", str(ral),
           "--out-json", str(out / "ids.json"),
           "--out-md", str(out / "ids.md"),
           "--out-html", str(out / "ids.html"),
           *extra_args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if expect_ok:
        assert proc.returncode == 0, proc.stderr
    return proc, out


# --- unit tests ---------------------------------------------------------------

def test_is_placeholder_hex():
    assert mat_ids._is_placeholder_hex("#31CC22") is True
    assert mat_ids._is_placeholder_hex("#CCCCCC") is False
    assert mat_ids._is_placeholder_hex("#808080") is False
    assert mat_ids._is_placeholder_hex("#000000") is False
    assert mat_ids._is_placeholder_hex("#1D1108") is False


def test_tex_stems_normalises_and_drops_broken():
    assert mat_ids._tex_stems([r"C:/maps/ID_2_Лиственница_Черная_f.png"]) == ("id_2_лиственница_черная_f",)
    assert mat_ids._tex_stems([r"C:/maps/T_Atlas_MAF.png"]) == ("t_atlas_maf",)
    assert mat_ids._tex_stems([r"C:/maps/foo.1001.png"]) == ("foo",)
    assert mat_ids._tex_stems([r"C:\x\fbx\..\.."]) == ()
    assert mat_ids._tex_stems([]) == ()


def test_classify_solid_seed():
    kind, key, seed = mat_ids.classify("нержа", "#808080", [])
    assert (kind, key) == ("solid", "steel_stainless")


def test_classify_bright_placeholder():
    kind, key, _ = mat_ids.classify("Material #2125652641", "#31CC22", [])
    assert (kind, key) == ("placeholder", "#31CC22")


def test_classify_bare_integer_placeholder():
    kind, key, _ = mat_ids.classify("1", "#CC2006", [])
    assert kind == "placeholder"


def test_classify_default_grey_generic_placeholder():
    kind, key, _ = mat_ids.classify("Material #2125652648", "#CCCCCC", [])
    assert (kind, key) == ("placeholder", "#CCCCCC")


def test_classify_family_merge_dark_wood():
    kind, key, _ = mat_ids.classify("Material #2125652664", "#1D1108", [])
    assert (kind, key) == ("solid", "wood_dark")


def test_classify_patterned_seed():
    kind, key, _ = mat_ids.classify("ID_2 Лиственница (Тёмная)", "#969696",
                                    [r"C:/maps/ID_2_Лиственница_Черная_f.png"])
    assert (kind, key) == ("patterned", "wood_larch_dark")


def test_classify_patterned_by_texture():
    kind, key, _ = mat_ids.classify("MAF", "#969696", [r"C:/maps/T_Atlas_MAF.png"])
    assert (kind, key) == ("patterned", "pattern:t_atlas_maf")


def test_classify_broken_texture_unresolved():
    kind, key, _ = mat_ids.classify("Untitled_Diffuse_1.1001", "#969696",
                                    [r"C:\x\fbx\..\.."])
    assert (kind, key) == ("patterned", "pattern:unresolved")


# --- integration + acceptance -------------------------------------------------

def test_end_to_end_counts_and_no_silent_drop(tmp_path):
    mats = _materials(
        _file("MAF_0001_A.fbx", _mat("нержа", "#808080"),
              _mat("Material #2125652641", "#31CC22")),
        _file("MAF_0002_B.fbx", _mat("Material #2125652664", "#1D1108")),
        _file("MAF_0003_C.fbx", _mat("ID_2 Лиственница (Тёмная)", "#969696",
                                     [r"C:/maps/ID_2_Лиственница_Черная_f.png"])),
    )
    _, out = _run(tmp_path, mats)
    doc = json.loads((out / "ids.json").read_text(encoding="utf-8"))
    ids = {m["id"]: m for m in doc["materials"]}
    # real candidates
    assert ids["steel_stainless"]["maf_count"] == 1
    assert ids["wood_dark"]["maf_count"] == 1
    assert ids["wood_larch_dark"]["kind"] == "patterned"
    # 4 PR #414 seed ids always present, status proposed
    for sid in ("steel_ral7047", "larch_light_oak", "hpl_satin_wood", "rope_pp"):
        assert ids[sid]["status"] == "proposed"
    # placeholder reported, never assigned
    assert doc["placeholders"][0]["hex"] == "#31CC22"
    assert all(m["status"] == "proposed" for m in doc["materials"])
    # no silent drop: every source name lands in a material or placeholder
    accounted = set()
    for m in doc["materials"]:
        accounted |= set(m["merged_sources"])
    for p in doc["placeholders"]:
        accounted |= set(p["sources"])
    assert accounted == {"нержа", "Material #2125652641", "Material #2125652664",
                         "ID_2 Лиственница (Тёмная)"}
    # extraction command + input hashes present
    assert doc["extraction"]["command"]
    assert "library/maf/catalogue.json" in doc["extraction"]["input_hashes"]
    # contact sheet + md written
    assert (out / "ids.html").exists() and (out / "ids.md").exists()


def test_atlas_cell_rules(tmp_path):
    big = _materials(*[
        _file(f"MAF_{i:04d}_X.fbx", _mat("Material #2125652664", "#1D1108"))
        for i in range(100)
    ])
    _, out = _run(tmp_path, big)
    doc = json.loads((out / "ids.json").read_text(encoding="utf-8"))
    by_id = {m["id"]: m for m in doc["materials"]}
    assert by_id["wood_dark"]["atlas_cell"] == 128  # >= 100 MAFs -> 128
    assert by_id["steel_ral7047"]["atlas_cell"] == 64  # seed solid -> 64


def test_overwrite_refusal(tmp_path):
    mats = _materials(_file("MAF_0001_A.fbx", _mat("нержа", "#808080")))
    _, out = _run(tmp_path, mats)
    # second run without --overwrite must fail and leave outputs intact
    before = (out / "ids.json").read_text(encoding="utf-8")
    _, out2 = _run(tmp_path, mats, expect_ok=False)
    assert (out / "ids.json").read_text(encoding="utf-8") == before


def test_output_resolves_to_input_rejected(tmp_path):
    mats = _materials(_file("MAF_0001_A.fbx", _mat("нержа", "#808080")))
    catalogue = _write(tmp_path, "catalogue.json", _catalogue())
    seed = _write(tmp_path, "seed.json", _seed())
    ral = _write(tmp_path, "ral.json", _ral())
    mats_path = _write(tmp_path, "materials.json", mats)
    cmd = [sys.executable, str(TOOL),
           "--materials", str(mats_path), "--catalogue", str(catalogue),
           "--seed", str(seed), "--ral", str(ral),
           "--out-json", str(mats_path),  # output == input
           "--out-md", str(tmp_path / "ids.md"),
           "--out-html", str(tmp_path / "ids.html")]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode != 0
    assert "resolves to an input" in proc.stderr
    # input untouched
    assert json.loads(mats_path.read_text(encoding="utf-8"))["files"][0]["materials"][0]["name"] == "нержа"


def test_invalid_hex_rejected(tmp_path):
    mats = _materials(_file("MAF_0001_A.fbx", _mat("bad", "#GGGGGG")))
    proc, _ = _run(tmp_path, mats, expect_ok=False)
    assert proc.returncode != 0
    assert "invalid hex colour" in proc.stderr


def test_empty_input_closed(tmp_path):
    # empty catalogue + empty materials -> zero candidate ids, no crash
    mats = _materials()
    proc, out = _run(tmp_path, mats)
    assert proc.returncode == 0
    doc = json.loads((out / "ids.json").read_text(encoding="utf-8"))
    # the 4 known seed ids survive an empty library
    assert doc["counts"]["candidate_ids"] == 4
