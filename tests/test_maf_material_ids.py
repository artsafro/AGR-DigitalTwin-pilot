"""Synthetic tests for the MAF library material ID list (issue #488)."""
from __future__ import annotations

import importlib.util
import json
import os
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
    return {"name": name, "hex": hexc, "textures": [{"filepath": t} for t in textures]}


def _catalogue(fbx_names, previews=None):
    previews = previews or {}
    entries = []
    for i, fbx in enumerate(fbx_names):
        entries.append({
            "id": "MAF_%04d" % i,
            "fbx_path": "C:/x/lib/fbx/" + fbx,
            "preview_path": previews.get(fbx, "C:/x/lib/preview/" + fbx.replace(".fbx", ".png")),
            "preview_style": "source-material",
        })
    return {"entries": entries}


def _write(tmp, name, doc):
    p = tmp / name
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return p


def _seed():
    return {"atlas": {"materials": [
        {"name": "steel_ral7047"}, {"name": "larch_light_oak"},
        {"name": "hpl_satin_wood"}, {"name": "rope_pp"},
    ]}}


def _ral():
    return {"note": "display only", "colors": {"7047": "#D0D0D0", "9005": "#0A0A0A"}}


def _run(tmp, materials, catalogue=None, extra_args=(), expect_ok=True):
    if catalogue is None:
        catalogue = _catalogue([f["fbx"] for f in materials["files"]])
    cat_p = _write(tmp, "catalogue.json", catalogue)
    seed = _write(tmp, "seed.json", _seed())
    ral = _write(tmp, "ral.json", _ral())
    mats = _write(tmp, "materials.json", materials)
    out = tmp / "out"
    cmd = [sys.executable, str(TOOL),
           "--materials", str(mats), "--catalogue", str(cat_p),
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


def test_norm_tex_keeps_full_path():
    assert mat_ids._norm_tex(r"C:\oak\diffuse.png") == "C:/oak/diffuse.png"
    assert mat_ids._norm_tex("C:/steel/diffuse.png") == "C:/steel/diffuse.png"


def test_tex_readable_strips_ext_and_hash():
    assert mat_ids._tex_readable("C:/maps/T_Atlas_MAF.png") == "T_Atlas_MAF"
    assert mat_ids._tex_readable("C:/maps/foo.1001.png") == "foo.1001"  # UDIM tile kept
    assert mat_ids._tex_readable("C:/x/Untitled_Diffuse_1.1001_ngosp2lcps3p.png") == \
        "Untitled_Diffuse_1.1001"


def test_appearance_key_solid_seed():
    kind, key = mat_ids._appearance_key("нержа", "#808080", [])
    assert kind == "seed"
    # colour stays in the identity so two differing "нержа" probes never merge
    assert key == ("seed", "steel_stainless", "#808080")


def test_appearance_key_solid_seed_authoritative_colour():
    kind, key = mat_ids._appearance_key("ID_1_RAL 9005", "#969696", [])
    assert kind == "seed"
    assert key == ("seed", "cap_black", "#0A0A0A")


def test_appearance_key_bright_placeholder():
    kind, key = mat_ids._appearance_key("Material #2125652641", "#31CC22", [])
    assert (kind, key) == ("placeholder", ("placeholder", "#31CC22"))


def test_appearance_key_bare_integer_placeholder():
    kind, key = mat_ids._appearance_key("1", "#CC2006", [])
    assert kind == "placeholder"


def test_appearance_key_default_grey_generic_placeholder():
    kind, key = mat_ids._appearance_key("Material #2125652648", "#CCCCCC", [])
    assert (kind, key) == ("placeholder", ("placeholder", "#CCCCCC"))


def test_appearance_key_family_merge_dark_wood():
    kind, key = mat_ids._appearance_key("Material #2125652664", "#1D1108", [])
    assert (kind, key) == ("family", ("family", "wood_dark"))


def test_appearance_key_patterned_keyed_by_full_path():
    kind, key = mat_ids._appearance_key("MAF", "#969696", [r"C:/maps/T_Atlas_MAF.png"])
    assert kind == "patterned"
    assert key[2] == ("C:/maps/T_Atlas_MAF.png",)
    assert key[3] == "#969696"  # base colour is part of the appearance identity


def test_appearance_key_same_name_different_colour_are_distinct():
    k1 = mat_ids._appearance_key("shared", "#111111", [])
    k2 = mat_ids._appearance_key("shared", "#EEEEEE", [])
    assert k1[1] != k2[1]


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
    assert ids["steel_stainless"]["maf_count"] == 1
    assert ids["wood_dark"]["maf_count"] == 1
    assert ids["wood_larch_dark"]["kind"] == "patterned"
    for sid in ("steel_ral7047", "larch_light_oak", "hpl_satin_wood", "rope_pp"):
        assert ids[sid]["status"] == "proposed"
    assert any(p["hex"] == "#31CC22" for p in doc["placeholders"])
    assert all(m["status"] == "proposed" for m in doc["materials"])
    accounted = set()
    for m in doc["materials"]:
        accounted |= set(m["merged_sources"])
    for p in doc["placeholders"]:
        accounted |= set(p["sources"])
    assert accounted == {"нержа", "Material #2125652641", "Material #2125652664",
                         "ID_2 Лиственница (Тёмная)"}
    assert doc["extraction"]["command"]
    assert "library/maf/catalogue.json" in doc["extraction"]["input_hashes"]
    assert (out / "ids.html").exists() and (out / "ids.md").exists()


def test_atlas_cell_rules(tmp_path):
    big = _materials(*[
        _file(f"MAF_{i:04d}_X.fbx", _mat("Material #2125652664", "#1D1108"))
        for i in range(100)
    ])
    _, out = _run(tmp_path, big)
    doc = json.loads((out / "ids.json").read_text(encoding="utf-8"))
    by_id = {m["id"]: m for m in doc["materials"]}
    assert by_id["wood_dark"]["atlas_cell"] == 128
    assert by_id["steel_ral7047"]["atlas_cell"] == 64


def test_overwrite_refusal(tmp_path):
    mats = _materials(_file("MAF_0001_A.fbx", _mat("нержа", "#808080")))
    _, out = _run(tmp_path, mats)
    before = (out / "ids.json").read_text(encoding="utf-8")
    _, out2 = _run(tmp_path, mats, expect_ok=False)
    assert (out / "ids.json").read_text(encoding="utf-8") == before


def test_output_resolves_to_input_rejected(tmp_path):
    mats = _materials(_file("MAF_0001_A.fbx", _mat("нержа", "#808080")))
    catalogue = _write(tmp_path, "catalogue.json", _catalogue(["MAF_0001_A.fbx"]))
    seed = _write(tmp_path, "seed.json", _seed())
    ral = _write(tmp_path, "ral.json", _ral())
    mats_path = _write(tmp_path, "materials.json", mats)
    cmd = [sys.executable, str(TOOL),
           "--materials", str(mats_path), "--catalogue", str(catalogue),
           "--seed", str(seed), "--ral", str(ral),
           "--out-json", str(mats_path),
           "--out-md", str(tmp_path / "ids.md"),
           "--out-html", str(tmp_path / "ids.html")]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode != 0
    assert "resolves to an input" in proc.stderr
    assert json.loads(mats_path.read_text(encoding="utf-8"))["files"][0]["materials"][0]["name"] == "нержа"


def test_invalid_hex_rejected(tmp_path):
    mats = _materials(_file("MAF_0001_A.fbx", _mat("bad", "#GGGGGG")))
    proc, _ = _run(tmp_path, mats, expect_ok=False)
    assert proc.returncode != 0
    assert "invalid hex colour" in proc.stderr


# --- P1 regression tests (reviewer findings) ----------------------------------

def test_empty_extraction_rejected(tmp_path):
    mats = _materials()  # files == []
    catalogue = _catalogue(["MAF_0001_A.fbx"])
    proc, _ = _run(tmp_path, mats, catalogue=catalogue, expect_ok=False)
    assert proc.returncode != 0
    assert "no files" in proc.stderr


def test_error_record_rejected(tmp_path):
    mats = {"blender": "5.1.2", "files": [{"fbx": "MAF_0001_A.fbx", "error": "unsupported FBX"}]}
    catalogue = _catalogue(["MAF_0001_A.fbx"])
    proc, _ = _run(tmp_path, mats, catalogue=catalogue, expect_ok=False)
    assert proc.returncode != 0
    assert "failed for FBX" in proc.stderr


def test_partial_extraction_rejected(tmp_path):
    mats = _materials(_file("MAF_0001_A.fbx", _mat("нержа", "#808080")))
    catalogue = _catalogue(["MAF_0001_A.fbx", "MAF_0002_B.fbx"])
    proc, _ = _run(tmp_path, mats, catalogue=catalogue, expect_ok=False)
    assert proc.returncode != 0
    assert "incomplete extraction" in proc.stderr


def test_duplicate_record_rejected(tmp_path):
    mats = {"blender": "5.1.2", "files": [
        {"fbx": "MAF_0001_A.fbx", "materials": [_mat("нержа", "#808080")]},
        {"fbx": "MAF_0001_A.fbx", "materials": [_mat("нержа", "#808080")]},
    ]}
    catalogue = _catalogue(["MAF_0001_A.fbx"])
    proc, _ = _run(tmp_path, mats, catalogue=catalogue, expect_ok=False)
    assert proc.returncode != 0
    assert "duplicate" in proc.stderr


def test_unknown_record_rejected(tmp_path):
    mats = _materials(_file("MAF_9999_Z.fbx", _mat("нержа", "#808080")))
    catalogue = _catalogue(["MAF_0001_A.fbx"])
    proc, _ = _run(tmp_path, mats, catalogue=catalogue, expect_ok=False)
    assert proc.returncode != 0
    assert "unknown FBX" in proc.stderr


def test_same_name_different_colour_not_merged(tmp_path):
    mats = _materials(
        _file("MAF_0001_A.fbx", _mat("shared", "#111111")),
        _file("MAF_0002_B.fbx", _mat("shared", "#EEEEEE")),
    )
    _, out = _run(tmp_path, mats)
    doc = json.loads((out / "ids.json").read_text(encoding="utf-8"))
    solids = [m for m in doc["materials"] if m["kind"] == "solid" and m["maf_count"] > 0]
    assert len(solids) == 2
    assert {m["color"] for m in solids} == {"#111111", "#EEEEEE"}


def test_same_basename_different_dir_not_merged(tmp_path):
    mats = _materials(
        _file("MAF_0001_A.fbx", _mat("a", None, ["C:/oak/diffuse.png"])),
        _file("MAF_0002_B.fbx", _mat("b", None, ["C:/steel/diffuse.png"])),
    )
    _, out = _run(tmp_path, mats)
    doc = json.loads((out / "ids.json").read_text(encoding="utf-8"))
    patterned = [m for m in doc["materials"] if m["kind"] == "patterned" and m["maf_count"] > 0]
    assert len(patterned) == 2
    assert {t for m in patterned for t in m["textures"]} == \
        {"C:/oak/diffuse.png", "C:/steel/diffuse.png"}


def test_unresolved_textures_not_collapsed(tmp_path):
    mats = _materials(
        _file("MAF_0001_A.fbx", _mat("x", None, ["C:/a/broken1.png"])),
        _file("MAF_0002_B.fbx", _mat("y", None, ["C:/a/broken2.png"])),
    )
    _, out = _run(tmp_path, mats)
    doc = json.loads((out / "ids.json").read_text(encoding="utf-8"))
    patterned = [m for m in doc["materials"] if m["kind"] == "patterned" and m["maf_count"] > 0]
    assert len(patterned) == 2
    assert all(m["texture_status"] == "unresolved" for m in patterned)
    assert not any(m["id"] == "pattern:unresolved" for m in doc["materials"])


def test_identical_material_merges_control(tmp_path):
    mats = _materials(
        _file("MAF_0001_A.fbx", _mat("wood", None, ["C:/maps/wood.png"])),
        _file("MAF_0002_B.fbx", _mat("wood", None, ["C:/maps/wood.png"])),
    )
    _, out = _run(tmp_path, mats)
    doc = json.loads((out / "ids.json").read_text(encoding="utf-8"))
    patterned = [m for m in doc["materials"] if m["kind"] == "patterned" and m["maf_count"] > 0]
    assert len(patterned) == 1
    assert patterned[0]["maf_count"] == 2


def test_output_alias_of_implicit_audit_rejected(tmp_path):
    mats = _materials(_file("MAF_0001_A.fbx", _mat("нержа", "#808080")))
    catalogue = _catalogue(["MAF_0001_A.fbx"])
    cat_p = _write(tmp_path, "catalogue.json", catalogue)
    audit_p = _write(tmp_path, "audit.json", {"source_hashes": [], "sentinel": "audit"})
    seed = _write(tmp_path, "seed.json", _seed())
    ral = _write(tmp_path, "ral.json", _ral())
    mats_path = _write(tmp_path, "materials.json", mats)
    cmd = [sys.executable, str(TOOL),
           "--materials", str(mats_path), "--catalogue", str(cat_p),
           "--seed", str(seed), "--ral", str(ral),
           "--out-json", str(audit_p),
           "--out-md", str(tmp_path / "ids.md"),
           "--out-html", str(tmp_path / "ids.html"),
           "--overwrite"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode != 0
    assert "resolves to an input" in proc.stderr
    assert json.loads(audit_p.read_text(encoding="utf-8"))["sentinel"] == "audit"


def test_patterned_swatch_has_image(tmp_path):
    from PIL import Image
    png = tmp_path / "preview_MAF_0001.png"
    Image.new("RGB", (16, 16), (200, 0, 0)).save(png)
    mats = _materials(_file("MAF_0001_A.fbx", _mat("wood", None, ["C:/maps/wood.png"])))
    catalogue = _catalogue(["MAF_0001_A.fbx"], previews={"MAF_0001_A.fbx": str(png)})
    _, out = _run(tmp_path, mats, catalogue=catalogue)
    html = (out / "ids.html").read_text(encoding="utf-8")
    assert "<img" in html
    assert "data:image/jpeg;base64," in html


def test_unavailable_preview_marks_missing(tmp_path):
    mats = _materials(_file("MAF_0001_A.fbx", _mat("wood", None, ["C:/maps/wood.png"])))
    catalogue = _catalogue(["MAF_0001_A.fbx"])
    _, out = _run(tmp_path, mats, catalogue=catalogue)
    html = (out / "ids.html").read_text(encoding="utf-8")
    assert "no&nbsp;image" in html
    assert "[texture unresolved]" in html


# --- round-3 P1 regression tests (reviewer findings) ---------------------------

def test_empty_material_file_reported_as_gap(tmp_path):
    mats = _materials(_file("MAF_0001_A.fbx"))  # materials == []
    _, out = _run(tmp_path, mats)
    doc = json.loads((out / "ids.json").read_text(encoding="utf-8"))
    gaps = [g for g in doc["gaps"] if g["kind"] == "empty_materials"]
    assert len(gaps) == 1
    assert gaps[0]["fbx"] == "MAF_0001_A.fbx"
    assert gaps[0]["maf_id"] == "MAF_0000"
    assert doc["counts"]["empty_material_files"] == 1
    # no source material is silently claimed: only the 4 site seeds remain, all 0 count
    assert doc["counts"]["candidate_ids"] == 4
    assert all(m["maf_count"] == 0 for m in doc["materials"])


def test_null_appearance_material_reported_not_proposed(tmp_path):
    mats = _materials(_file("MAF_0001_A.fbx", _mat("unknown", None)))
    _, out = _run(tmp_path, mats)
    doc = json.loads((out / "ids.json").read_text(encoding="utf-8"))
    gaps = [g for g in doc["gaps"] if g["kind"] == "null_appearance"]
    assert len(gaps) == 1
    assert gaps[0]["material"] == "unknown"
    assert doc["counts"]["null_appearance_materials"] == 1
    # no solid proposal with color:null is emitted
    assert not any(m["kind"] == "solid" and m["color"] is None for m in doc["materials"])


def test_seed_name_different_colour_distinct(tmp_path):
    mats = _materials(
        _file("MAF_0001_A.fbx", _mat("нержа", "#111111")),
        _file("MAF_0002_B.fbx", _mat("нержа", "#EEEEEE")),
    )
    _, out = _run(tmp_path, mats)
    doc = json.loads((out / "ids.json").read_text(encoding="utf-8"))
    solids = [m for m in doc["materials"] if m["kind"] == "solid" and m["maf_count"] > 0]
    assert len(solids) == 2
    assert {m["color"] for m in solids} == {"#111111", "#EEEEEE"}


def test_same_name_same_texture_different_colour_distinct(tmp_path):
    mats = _materials(
        _file("MAF_0001_A.fbx", _mat("wood", "#111111", ["C:/missing/wood.png"])),
        _file("MAF_0002_B.fbx", _mat("wood", "#EEEEEE", ["C:/missing/wood.png"])),
    )
    _, out = _run(tmp_path, mats)
    doc = json.loads((out / "ids.json").read_text(encoding="utf-8"))
    patterned = [m for m in doc["materials"] if m["kind"] == "patterned" and m["maf_count"] > 0]
    assert len(patterned) == 2
    assert {m["color"] for m in patterned} == {"#111111", "#EEEEEE"}


def test_output_alias_of_preview_rejected(tmp_path):
    from PIL import Image
    png = tmp_path / "preview.png"
    Image.new("RGB", (16, 16), (0, 200, 0)).save(png)
    mats = _materials(_file("MAF_0001_A.fbx", _mat("wood", None, ["C:/maps/wood.png"])))
    catalogue = _catalogue(["MAF_0001_A.fbx"], previews={"MAF_0001_A.fbx": str(png)})
    cat_p = _write(tmp_path, "catalogue.json", catalogue)
    seed = _write(tmp_path, "seed.json", _seed())
    ral = _write(tmp_path, "ral.json", _ral())
    mats_path = _write(tmp_path, "materials.json", mats)
    before = png.read_bytes()
    cmd = [sys.executable, str(TOOL),
           "--materials", str(mats_path), "--catalogue", str(cat_p),
           "--seed", str(seed), "--ral", str(ral),
           "--out-json", str(tmp_path / "ids.json"),
           "--out-md", str(tmp_path / "ids.md"),
           "--out-html", str(png),
           "--overwrite"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode != 0
    assert "resolves to an input" in proc.stderr
    assert png.read_bytes() == before


def test_output_hardlink_to_materials_rejected(tmp_path):
    mats = _materials(_file("MAF_0001_A.fbx", _mat("нержа", "#808080")))
    catalogue = _catalogue(["MAF_0001_A.fbx"])
    cat_p = _write(tmp_path, "catalogue.json", catalogue)
    seed = _write(tmp_path, "seed.json", _seed())
    ral = _write(tmp_path, "ral.json", _ral())
    mats_path = _write(tmp_path, "materials.json", mats)
    link = tmp_path / "out.html"
    os.link(mats_path, link)
    before = mats_path.read_bytes()
    cmd = [sys.executable, str(TOOL),
           "--materials", str(mats_path), "--catalogue", str(cat_p),
           "--seed", str(seed), "--ral", str(ral),
           "--out-json", str(tmp_path / "ids.json"),
           "--out-md", str(tmp_path / "ids.md"),
           "--out-html", str(link),
           "--overwrite"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode != 0
    assert "resolves to an input" in proc.stderr
    assert mats_path.read_bytes() == before
    assert link.read_bytes() == before


def test_combined_gaps_and_conflicts_all_accounted(tmp_path):
    mats = _materials(
        _file("MAF_0001_A.fbx"),                                    # empty materials
        _file("MAF_0002_B.fbx", _mat("unknown", None)),             # null appearance
        _file("MAF_0003_C.fbx", _mat("нержа", "#111111")),
        _file("MAF_0004_D.fbx", _mat("нержа", "#EEEEEE")),
        _file("MAF_0005_E.fbx", _mat("wood", "#111111", ["C:/m/wood.png"])),
        _file("MAF_0006_F.fbx", _mat("wood", "#EEEEEE", ["C:/m/wood.png"])),
    )
    _, out = _run(tmp_path, mats)
    doc = json.loads((out / "ids.json").read_text(encoding="utf-8"))
    assert doc["counts"]["empty_material_files"] == 1
    assert doc["counts"]["null_appearance_materials"] == 1
    solids = [m for m in doc["materials"] if m["kind"] == "solid" and m["maf_count"] > 0]
    assert {m["color"] for m in solids} == {"#111111", "#EEEEEE"}
    patterned = [m for m in doc["materials"] if m["kind"] == "patterned" and m["maf_count"] > 0]
    assert {m["color"] for m in patterned} == {"#111111", "#EEEEEE"}
