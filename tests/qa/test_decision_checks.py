"""Validator checks for decided rules that had no automatic check before ([D160], [D021], [D198], [D221]).

V009 texel density per UDIM tile with the archive Diffuse side [D160], PNG count 3..2100 per VPM ZIP
(TEX-04, reg p.26 §1.2), quad master <= 4 m (DER-03, [D021], twinqa.master) and the VPM OKS MainGlass
object and glass material names (#1029, DER-18/19, reg 2.8-2.8.2).
All readbacks, meshes and packages below are SYNTHETIC fixtures, not data of a real object.
"""
import zipfile

import pytest

import validate_package as vp
from test_scene import mesh, rb, statuses
from test_validator import PROFILES, STEM, good_files, png
from twinqa.master import master_findings
from twinqa.scene import main_glass_findings, scene_findings

# --- SYNTHETIC geometry helpers --------------------------------------------------------------------------------


def _quad(x0, side, z=0.0):
    return [[x0, 0.0, z], [x0 + side, 0.0, z], [x0 + side, side, z], [x0, side, z]]


def textured(name="SM_Test_K_1_Main", side_m=1.0, uv_side=0.25, tile=1001, material="M_Test_K_1_Main_1"):
    """SYNTHETIC one-quad mesh: side_m metres mapped to uv_side UV units inside `tile`."""
    u0, v0 = (tile - 1001) % 10, (tile - 1001) // 10
    uv = [[u0 + 0.1, v0 + 0.1], [u0 + 0.1 + uv_side, v0 + 0.1], [u0 + 0.1 + uv_side, v0 + 0.1 + uv_side],
          [u0 + 0.1, v0 + 0.1 + uv_side]]
    m = mesh(name=name, tris=2, materials=(material,))
    m["face_geometry"] = {"vertices": _quad(0.0, side_m), "polygons": [[0, 1, 2, 3]], "polygon_uv": [uv],
                          "uv": uv, "polygon_material": [material]}
    return m


def v009(*meshes, diffuse_px):
    found = scene_findings(rb(*meshes), "vpm", "oks", PROFILES.vpm, diffuse_px=diffuse_px)
    return found["V009"]


# --- V009 texel density [D160] ---------------------------------------------------------------------------------

def test_v009_density_inside_band_passes():
    # 0.25 UV x 4096 px over 1 m = 1024 px/m
    got = {f.name: f for f in v009(textured(), diffuse_px={(1, 1001): 4096})}
    assert got["texel density"].status == "pass" and got["texel density"].measured == pytest.approx(1024)
    assert got["texel density upper"].status == "pass"


@pytest.mark.parametrize("uv_side, name", [(0.12, "texel density"), (0.42, "texel density upper")])
def test_v009_density_outside_band_fails(uv_side, name):
    # 0.12 x 4096 = 491.5 px/m < 512; 0.42 x 4096 = 1720.3 px/m > 1706
    got = {f.name: f.status for f in v009(textured(uv_side=uv_side), diffuse_px={(1, 1001): 4096})}
    assert got[name] == "fail"


def test_v009_uses_the_side_of_each_tile():
    # same UV scale: 1024 px/m on a 4096 tile, 512 px/m (exactly the bound) on a 2048 tile
    meshes = [textured(tile=1001), textured(name="SM_Test_K_1_Main_b", tile=1002)]
    got = {f.name: f for f in v009(*meshes, diffuse_px={(1, 1001): 4096, (1, 1002): 2048})}
    assert got["texel density"].measured == pytest.approx(512)
    assert got["texel density upper"].measured == pytest.approx(1024)


def test_v009_slot_from_material_when_slots_differ_on_a_tile():
    meshes = [textured(material="M_Test_K_1_Main_2")]
    got = {f.name: f for f in v009(*meshes, diffuse_px={(1, 1001): 2048, (2, 1001): 4096})}
    assert got["texel density"].measured == pytest.approx(1024)


def test_v009_placeholder_tile_is_exempt():
    got = {f.name: f.status for f in v009(textured(uv_side=0.01), diffuse_px={(1, 1001): 256})}
    assert got == {"texel density": "pass", "texel density upper": "pass"}


def test_v009_glass_mesh_is_exempt():
    glass = textured(name="SM_Test_K_1_MainGlass", uv_side=0.01, material="M_Test_K_1_MainGlass_1")
    got = {f.name: f.status for f in v009(textured(), glass, diffuse_px={(1, 1001): 4096})}
    assert got["texel density"] == "pass"


def test_v009_tile_without_diffuse_is_not_run_never_pass():
    got = {f.name: f.status for f in v009(textured(tile=1003), diffuse_px={(1, 1001): 4096})}
    assert got["texel density coverage"] == "not_run"
    assert "pass" not in {got["texel density"], got["texel density upper"]}


def test_v009_density_is_no_longer_reported_in_v008():
    found = scene_findings(rb(textured()), "vpm", "oks", PROFILES.vpm, diffuse_px={(1, 1001): 4096})
    assert not any(f.name.startswith("texel density") for f in found["V008"])


def test_package_without_scene_leaves_v009_not_run(tmp_path):
    report = vp.validate(_zip(tmp_path, good_files()), None, PROFILES)
    st = {s.id: s for s in report.stages}
    assert statuses({"V009": st["V009"].findings}, "V009") == {"texel density": "not_run"}


def test_package_scene_passes_archive_diffuse_sides(monkeypatch, tmp_path):
    seen = {}

    def fake_scene_findings(rb_, kind, role, profile, **kwargs):
        seen.update(kwargs)
        return {}

    monkeypatch.setattr(vp, "readback", lambda path, blender=None, timeout=600: rb(mesh()))
    monkeypatch.setattr(vp, "scene_findings", fake_scene_findings)
    vp.validate(_zip(tmp_path, good_files()), None, PROFILES, scene=True)
    assert seen["diffuse_px"] == {(1, 1001): 256}


# --- V001 PNG count 3..2100 (TEX-04, reg p.26 §1.2) ------------------------------------------------------------

def _zip(tmp_path, files):
    package = tmp_path / f"{STEM}.zip"
    with zipfile.ZipFile(package, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return package


def _png_count(tmp_path, files):
    report = vp.validate(_zip(tmp_path, files), None, PROFILES)
    st = {s.id: s for s in report.stages}
    return next((f.status for f in st["V001"].findings if f.name == "PNG count"), "pass")


def test_png_count_three_passes(tmp_path):
    assert _png_count(tmp_path, good_files()) == "pass"


def test_png_count_two_fails(tmp_path):
    files = good_files()
    del files["T_Test_K_1_Normal_1.1001.png"]
    assert _png_count(tmp_path, files) == "fail"


def test_png_count_2101_fails(tmp_path):
    files = good_files()
    tiny = png()
    for i in range(2098):  # 3 + 2098 = 2101 SYNTHETIC PNG members
        files[f"X_{i}.png"] = tiny
    assert _png_count(tmp_path, files) == "fail"


# --- DER-03 quad master (twinqa.master; [D021]) ----------------------------------------------------------------

def master_rb(*meshes, ok=True):
    return {"source": "C:/x/SM_Test_K_1_work.fbx", "readback_ok": ok, "meshes": list(meshes)}


def poly_mesh(name, polys, verts):
    degrees = {}
    for p in polys:
        degrees[str(len(p))] = degrees.get(str(len(p)), 0) + 1
    return {"name": name, "polygon_degrees": degrees, "face_geometry": {"vertices": verts, "polygons": polys}}


def quads(*sides):
    verts, polys, x = [], [], 0.0
    for side in sides:
        base = len(verts)
        verts += _quad(x, side)
        polys.append([base, base + 1, base + 2, base + 3])
        x += side + 1.0
    return verts, polys


def master_status(kind, *meshes):
    return {f.name: f.status for f in master_findings(master_rb(*meshes), kind)}


def test_master_all_quads_under_4m_pass():
    verts, polys = quads(3.9, 1.0)
    assert master_status("vpm", poly_mesh("SM_Test_K_1_Main", polys, verts)) == {
        "master quads": "pass", "master quad size": "pass"}


def test_master_triangle_fails_quads():
    verts = [[0, 0, 0], [1, 0, 0], [0, 1, 0]]
    assert master_status("npm", poly_mesh("SM_Test_K_1_Main", [[0, 1, 2]], verts)) == {"master quads": "fail"}


def test_master_quad_over_4m_fails_and_padded_band_is_review():
    verts, polys = quads(4.5)
    assert master_status("vpm", poly_mesh("A", polys, verts))["master quad size"] == "fail"
    verts, polys = quads(3.95)  # between the padded side 3.9375 m and one tile 4.0 m
    assert master_status("vpm", poly_mesh("A", polys, verts))["master quad size"] == "review"


def test_master_npm_has_no_size_gate():
    verts, polys = quads(10.0)
    assert master_status("npm", poly_mesh("A", polys, verts)) == {"master quads": "pass"}


def test_master_ucx_ignored_and_degenerate_fails():
    ucx = poly_mesh("UCX_SM_Test_K_1_Main_001", [[0, 1, 2]], [[0, 0, 0], [9, 0, 0], [0, 9, 0]])
    flat = poly_mesh("A", [[0, 1, 2, 3]], [[0, 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0]])
    got = master_status("vpm", flat, ucx)
    assert got == {"master quads": "pass", "master quad size": "fail"}


def test_master_unreadable_fails():
    assert {f.status for f in master_findings(master_rb(ok=False), "vpm")} == {"fail"}


def test_package_scene_without_master_leaves_master_not_run(monkeypatch, tmp_path):
    monkeypatch.setattr(vp, "readback", lambda path, blender=None, timeout=600: rb(mesh()))
    report = vp.validate(_zip(tmp_path, good_files()), None, PROFILES, scene=True)
    st = {s.id: s for s in report.stages}
    assert statuses({"V003": st["V003"].findings}, "V003")["master quads"] == "not_run"
    assert report.exit_code != 0


def test_package_scene_with_master_reads_it_back(monkeypatch, tmp_path):
    verts, polys = quads(4.5)
    work = tmp_path / "SM_Test_K_1_work.fbx"
    work.write_bytes(b"SYNTHETIC")

    def fake(path, blender=None, timeout=600):
        return master_rb(poly_mesh("SM_Test_K_1_Main", polys, verts)) if path == work else rb(mesh())

    monkeypatch.setattr(vp, "readback", fake)
    report = vp.validate(_zip(tmp_path, good_files()), None, PROFILES, scene=True, master=work)
    st = {s.id: s for s in report.stages}
    got = statuses({"V003": st["V003"].findings}, "V003")
    assert got["master quads"] == "pass" and got["master quad size"] == "fail"
    assert any("master readback" in n for n in report.notes)


def test_master_without_scene_is_noted_unused(tmp_path):
    work = tmp_path / "w.fbx"
    work.write_bytes(b"SYNTHETIC")
    report = vp.validate(_zip(tmp_path, good_files()), None, PROFILES, master=work)
    assert any("unused" in n for n in report.notes)


# --- MainGlass object and materials (#1029; DER-18/19; reg 2.8-2.8.2) ------------------------------------------

def glass_status(*meshes, stem="SM_Test_K_1"):
    return {f.name: f.status for f in main_glass_findings(list(meshes), stem, f"{stem}.fbx")}


def test_main_and_glass_with_glass_material_pass():
    got = glass_status(mesh(), mesh(name="SM_Test_K_1_MainGlass", materials=("M_Test_K_1_MainGlass_1",)))
    assert got == {"MainGlass object": "pass", "MainGlass materials": "pass"}


def test_main_without_glass_is_review_never_pass():
    # reg 2.8: glass is mandatory where the building has glazing; a building without glazing is valid
    assert glass_status(mesh()) == {"MainGlass object": "review"}


def test_glass_with_wrong_material_fails():
    got = glass_status(mesh(), mesh(name="SM_Test_K_1_MainGlass", materials=("M_Test_K_1_Main_1",)))
    assert got["MainGlass materials"] == "fail"


def test_glass_with_eighth_material_fails():
    mats = tuple(f"M_Test_K_1_MainGlass_{i}" for i in range(1, 9))
    assert glass_status(mesh(), mesh(name="SM_Test_K_1_MainGlass", materials=mats))["MainGlass materials"] == "fail"


def test_glass_materials_missing_from_readback_is_review():
    glass = mesh(name="SM_Test_K_1_MainGlass")
    del glass["materials"]
    assert glass_status(mesh(), glass)["MainGlass materials"] == "review"


def test_glass_check_reaches_v012_for_vpm_oks_only():
    oks = scene_findings(rb(mesh()), "vpm", "oks", PROFILES.vpm)
    assert statuses(oks, "V012")["MainGlass object"] == "review"
    ground = scene_findings(rb(mesh(name="SM_Test_K_1_Ground")), "vpm", "ground", PROFILES.vpm)
    assert "MainGlass object" not in statuses(ground, "V012")


# --- V008 glass tile [D221]: all glass UVs in 1001 whatever the number of glass materials (conflict #47) ---------

def test_glass_with_two_materials_on_1002_fails_v008():
    glass = mesh(name="SM_Test_K_1_MainGlass", tiles=(1001, 1002),
                 materials=("M_Test_K_1_MainGlass_1", "M_Test_K_1_MainGlass_2"))
    found = scene_findings(rb(mesh(), glass), "vpm", "oks", PROFILES.vpm)
    assert statuses(found, "V008")["glass tile"] == "fail"
