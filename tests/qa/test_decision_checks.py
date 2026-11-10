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
from twinqa.look import edge_loop_findings
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
    got = master_status("vpm", poly_mesh("SM_Test_K_1_Main", polys, verts))
    assert got["master quads"] == "pass" and got["master quad size"] == "pass"


def test_master_triangle_fails_quads():
    verts = [[0, 0, 0], [1, 0, 0], [0, 1, 0]]
    assert master_status("npm", poly_mesh("SM_Test_K_1_Main", [[0, 1, 2]], verts))["master quads"] == "fail"


def test_master_quad_over_4m_fails_and_padded_band_is_review():
    verts, polys = quads(4.5)
    assert master_status("vpm", poly_mesh("A", polys, verts))["master quad size"] == "fail"
    verts, polys = quads(3.95)  # between the padded side 3.9375 m and one tile 4.0 m
    assert master_status("vpm", poly_mesh("A", polys, verts))["master quad size"] == "review"


def test_master_npm_has_no_size_gate():
    verts, polys = quads(10.0)
    assert master_status("npm", poly_mesh("A", polys, verts))["master quads"] == "pass"


def test_master_ucx_ignored_and_degenerate_fails():
    ucx = poly_mesh("UCX_SM_Test_K_1_Main_001", [[0, 1, 2]], [[0, 0, 0], [9, 0, 0], [0, 9, 0]])
    flat = poly_mesh("A", [[0, 1, 2, 3]], [[0, 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0]])
    got = master_status("vpm", flat, ucx)
    assert got["master quads"] == "pass" and got["master quad size"] == "fail"


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


# --- Look-finished checks: decor embed [D199] and edge-loop continuity [D200] (report-only) -------------------

def _face_mesh(name, verts, polys):
    degrees = {}
    for p in polys:
        degrees[str(len(p))] = degrees.get(str(len(p)), 0) + 1
    return {"name": name, "polygon_degrees": degrees, "face_geometry": {"vertices": verts, "polygons": polys}}


def look_status(*meshes, kind="vpm"):
    return {f.name: f.status for f in master_findings(master_rb(*meshes), kind)}


FACADE = [[0, 0, 0], [4, 0, 0], [4, 4, 0], [0, 4, 0]]


def test_decor_touching_facade_passes_d199():
    main = _face_mesh("SM_Test_K_1_Main", FACADE, [[0, 1, 2, 3]])
    arch = _face_mesh("SM_Test_K_1_Arch", [[1, 1, 0], [2, 1, 0], [2, 2, 0], [1, 2, 0]], [[0, 1, 2, 3]])
    assert look_status(main, arch)["decor embed"] == "pass"


def test_decor_floating_standoff_is_review_never_fail_d199():
    main = _face_mesh("SM_Test_K_1_Main", FACADE, [[0, 1, 2, 3]])
    arch = _face_mesh("SM_Test_K_1_Arch", [[1, 1, 0.006], [2, 1, 0.006], [2, 2, 0.006], [1, 2, 0.006]],
                      [[0, 1, 2, 3]])
    assert look_status(main, arch)["decor embed"] == "review"


def test_decor_without_face_geometry_is_not_run_never_pass_d199():
    main = _face_mesh("SM_Test_K_1_Main", FACADE, [[0, 1, 2, 3]])
    bare = {"name": "SM_Test_K_1_Arch", "polygon_degrees": {"4": 1}}
    assert look_status(main, bare)["decor embed"] == "not_run"


def test_edge_loop_clean_grid_passes_d200():
    verts = [[x, y, 0.0] for y in range(3) for x in range(3)]
    polys = [[0, 1, 4, 3], [1, 2, 5, 4], [3, 4, 7, 6], [4, 5, 8, 7]]
    assert look_status(_face_mesh("SM_Test_K_1_Main", verts, polys))["edge loop continuity"] == "pass"


def test_edge_loop_t_junction_is_review_never_fail_d200():
    verts = [[0, 0, 0], [4, 0, 0], [4, 4, 0], [0, 4, 0], [2, 0, 0], [2, 2, 0], [0, 2, 0]]
    polys = [[0, 1, 2, 3], [0, 4, 5, 6]]
    assert look_status(_face_mesh("SM_Test_K_1_Main", verts, polys))["edge loop continuity"] == "review"


# --- Ground skirt >= 1 m [GND-03] (blocking) ----------------------------------------------------------------

def _ground_face_mesh(name, verts, polys, materials=None):
    m = mesh(name=name, tris=len(polys), degrees={"3": len(polys)})
    fg = {"vertices": verts, "polygons": polys}
    if materials is not None:
        fg["polygon_material"] = materials
    m["face_geometry"] = fg
    return m


def _skirt_finding(verts, polys, kind="npm", materials=None):
    found = scene_findings(rb(_ground_face_mesh("SM_Test_Ground", verts, polys, materials)), kind, "ground",
                           PROFILES.npm if kind == "npm" else PROFILES.vpm)
    return next(f for f in found["V003"] if f.name == "ground skirt depth")


FLAT = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]
FLAT_POLYS = [[0, 1, 2], [0, 2, 3]]
SKIRT = FLAT + [[0, 0, -1], [1, 0, -1], [1, 1, -1], [0, 1, -1]]
SKIRT_POLYS = [[0, 1, 2], [0, 2, 3], [0, 4, 5], [0, 5, 1], [1, 5, 6], [1, 6, 2],
               [2, 6, 7], [2, 7, 3], [3, 7, 4], [3, 4, 0]]


def test_ground_skirt_flat_no_skirt_fails_gnd03():
    assert _skirt_finding(FLAT, FLAT_POLYS).status == "fail"


def test_ground_skirt_exactly_one_metre_passes_gnd03():
    f = _skirt_finding(SKIRT, SKIRT_POLYS)
    assert f.status == "pass" and f.measured == pytest.approx(1.0)


def test_ground_skirt_just_under_one_metre_fails_gnd03():
    verts = FLAT + [[0, 0, -0.999], [1, 0, -0.999], [1, 1, -0.999], [0, 1, -0.999]]
    assert _skirt_finding(verts, SKIRT_POLYS).status == "fail"


def test_ground_skirt_non_finite_coord_fails_gnd03():
    verts = [v[:] for v in SKIRT]
    verts[4][2] = float("nan")
    assert _skirt_finding(verts, SKIRT_POLYS).status == "fail"


def test_ground_skirt_without_face_data_is_not_run_gnd03():
    found = scene_findings(rb(mesh(name="SM_Test_Ground")), "npm", "ground", PROFILES.npm)
    assert next(f for f in found["V003"] if f.name == "ground skirt depth").status == "not_run"


def test_ground_skirt_vpm_ground_also_checked():
    found = scene_findings(rb(_ground_face_mesh("SM_Test_Ground", SKIRT, SKIRT_POLYS)), "vpm", "ground",
                           PROFILES.vpm)
    assert next(f for f in found["V003"] if f.name == "ground skirt depth").status == "pass"


def test_ground_skirt_absent_for_oks():
    found = scene_findings(rb(_ground_face_mesh("SM_Test_K_1_Main", FLAT, FLAT_POLYS)), "npm", "oks",
                           PROFILES.npm)
    assert "ground skirt depth" not in {f.name for f in found["V003"]}


# --- UCX vs MAF/Flora intersection [FLO-15, MAF-22] (blocking) --------------------------------------------

BOX_TRIS = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1),
            (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]


def _box_verts(lo, hi):
    return [[hi[0] if i & 4 else lo[0], hi[1] if i & 2 else lo[1], hi[2] if i & 1 else lo[2]] for i in range(8)]


def _ucx_box(name, lo, hi):
    m = mesh(name=name, tris=12)
    m["hull"] = {"verts": _box_verts(lo, hi), "tris": [list(t) for t in BOX_TRIS]}
    return m


def _maf_mesh(name, lo, hi):
    m = mesh(name=name, tris=12)
    m["face_geometry"] = {"vertices": _box_verts(lo, hi), "polygons": [list(t) for t in BOX_TRIS]}
    return m


def _ucx_maf_status(ucx_lo, ucx_hi, maf_lo, maf_hi, name="SM_Test_GroundEl"):
    ground = mesh(name="SM_Test_Ground", materials=["M_Ground"])
    found = scene_findings(rb(ground, _ucx_box("UCX_SM_Test_Ground_001", ucx_lo, ucx_hi),
                              _maf_mesh(name, maf_lo, maf_hi)), "vpm", "ground", PROFILES.vpm)
    return next(f.status for f in found["V010"] if f.name == "UCX vs MAF/Flora intersection")


def test_ucx_covering_maf_fails_flo15():
    assert _ucx_maf_status((0, 0, 0), (1, 1, 1), (0.2, 0.2, 0.5), (0.8, 0.8, 1.5)) == "fail"


def test_ucx_below_maf_passes_flo15():
    assert _ucx_maf_status((0, 0, -1), (1, 1, -0.001), (0, 0, 0), (1, 1, 1)) == "pass"


def test_ucx_covering_flora_fails_flo15():
    assert _ucx_maf_status((0, 0, 0), (1, 1, 1), (0.2, 0.2, 0.5), (0.8, 0.8, 1.5),
                           name="SM_Test_Flora") == "fail"


def test_ucx_maf_flora_absent_for_oks():
    found = scene_findings(rb(mesh(), _ucx_box("UCX_SM_Test_K_1_Main_001", (0, 0, 0), (1, 1, 1))),
                           "vpm", "oks", PROFILES.vpm)
    assert "UCX vs MAF/Flora intersection" not in {f.name for f in found["V010"]}


def test_ucx_maf_flora_unsupported_hull_is_not_run_never_pass():
    ground = mesh(name="SM_Test_Ground", materials=["M_Ground"])
    bare_ucx = mesh(name="UCX_SM_Test_Ground_001")  # no hull -> not_run, never pass
    found = scene_findings(rb(ground, bare_ucx, _maf_mesh("SM_Test_GroundEl", (0, 0, 0), (1, 1, 1))),
                           "vpm", "ground", PROFILES.vpm)
    assert next(f for f in found["V010"] if f.name == "UCX vs MAF/Flora intersection").status == "not_run"


def test_ucx_maf_flora_never_fails_when_ucx_strictly_below():
    """Invariant probe: a UCX piece strictly below the MAF/Flora bbox never fails the check."""
    cases = 0
    for dz in (0.001, 0.01, 0.1, 0.5, 1.0):
        assert _ucx_maf_status((0, 0, -1 - dz), (1, 1, -dz), (0, 0, 0), (1, 1, 1)) == "pass"
        cases += 1
    assert cases == 5


# --- Reviewer round-1 P1 regressions ---------------------------------------------------------------


def test_ucx_seated_maf_sunk_10cm_passes_flo15():
    # UCX top flush with the ground surface; _GroundEl sunk 10 cm per [D095] -> the sunk band is
    # exempt from coverage, so this must not fail.
    assert _ucx_maf_status((0, 0, -1), (1, 1, 0), (0.2, 0.2, -0.1), (0.8, 0.8, 1)) == "pass"


def test_ucx_seated_flora_sunk_10cm_passes_flo15():
    # Same seating, _Flora sunk 10 cm per [D100].
    assert _ucx_maf_status((0, 0, -1), (1, 1, 0), (0.2, 0.2, -0.1), (0.8, 0.8, 1),
                           name="SM_Test_Flora") == "pass"


def test_ucx_thin_slab_through_maf_fails_flo15():
    # A thin UCX slab crossing the MAF interior has no MAF vertex inside it, but it intersects the
    # MAF mesh; the hull-triangle SAT test must catch it.
    assert _ucx_maf_status((0.4, -1, 0.4), (0.6, 2, 0.6), (0, 0, 0), (1, 1, 1)) == "fail"


def test_ucx_maf_without_face_geometry_is_not_run_names_mesh_flo15():
    ground = mesh(name="SM_Test_Ground", materials=["M_Ground"])
    bare = mesh(name="SM_Test_GroundEl")  # no face_geometry
    found = scene_findings(rb(ground, _ucx_box("UCX_SM_Test_Ground_001", (0, 0, 0), (1, 1, 1)), bare),
                           "vpm", "ground", PROFILES.vpm)
    f = next(f for f in found["V010"] if f.name == "UCX vs MAF/Flora intersection")
    assert f.status == "not_run"
    assert "SM_Test_GroundEl" in f.observed


def test_ucx_maf_empty_vertices_is_not_run_flo15():
    ground = mesh(name="SM_Test_Ground", materials=["M_Ground"])
    empty = mesh(name="SM_Test_GroundEl")
    empty["face_geometry"] = {"vertices": [], "polygons": [[0, 1, 2]]}
    found = scene_findings(rb(ground, _ucx_box("UCX_SM_Test_Ground_001", (0, 0, 0), (1, 1, 1)), empty),
                           "vpm", "ground", PROFILES.vpm)
    f = next(f for f in found["V010"] if f.name == "UCX vs MAF/Flora intersection")
    assert f.status == "not_run"


def test_ucx_maf_non_finite_vertices_is_not_run_flo15():
    ground = mesh(name="SM_Test_Ground", materials=["M_Ground"])
    bad = mesh(name="SM_Test_GroundEl")
    bad["face_geometry"] = {"vertices": [[0, 0, float("nan")], [1, 0, 0], [1, 1, 0]], "polygons": [[0, 1, 2]]}
    found = scene_findings(rb(ground, _ucx_box("UCX_SM_Test_Ground_001", (0, 0, 0), (1, 1, 1)), bad),
                           "vpm", "ground", PROFILES.vpm)
    f = next(f for f in found["V010"] if f.name == "UCX vs MAF/Flora intersection")
    assert f.status == "not_run"


def test_ground_skirt_sloped_quad_without_skirt_fails_gnd03():
    # 2 m of relief but no perimeter extrusion: the old total-Z-extent measure passed this; the
    # perimeter-drop measure must fail it (GND-03).
    verts = [[0, 0, 0], [10, 0, 0], [10, 10, 2], [0, 10, 2]]
    polys = [[0, 1, 2], [0, 2, 3]]
    assert _skirt_finding(verts, polys).status == "fail"


def test_ground_skirt_sloped_surface_with_skirt_passes_gnd03():
    # A sloped surface WITH a 1 m vertical skirt passes: the drop is measured at the perimeter
    # corners, not the whole Z-extent (surface z 2..4 -> skirt bottom z 1..3 -> drop 1 m).
    verts = [[0, 0, 2], [10, 0, 2], [10, 10, 4], [0, 10, 4],
             [0, 0, 1], [10, 0, 1], [10, 10, 3], [0, 10, 3]]
    f = _skirt_finding(verts, SKIRT_POLYS)
    assert f.status == "pass" and f.measured == pytest.approx(1.0)


def test_ground_skirt_partial_skirt_fails_gnd03():
    # Round-2 P1: a skirt on two sides (y=0, y=10) leaves the x=0 and x=10 perimeter edges
    # uncovered, yet every convex-hull corner still carries a 1 m drop. The per-edge measure
    # must see the two bare perimeter edges and fail.
    verts = [[0, 0, 0], [10, 0, 0], [10, 10, 0], [0, 10, 0],
             [0, 0, -1], [10, 0, -1], [10, 10, -1], [0, 10, -1]]
    polys = [[0, 1, 2], [0, 2, 3],            # top surface
             [0, 4, 5], [0, 5, 1],            # y=0 skirt
             [2, 6, 7], [2, 7, 3]]            # y=10 skirt
    f = _skirt_finding(verts, polys)
    assert f.status == "fail" and f.measured == pytest.approx(0.0)


def test_ground_skirt_judges_every_ground_mesh_names_worst():
    # Round-2 P1: S_Ground has a full 1 m skirt, T_Ground is a bare flat quad. The check must
    # judge BOTH Ground meshes and fail naming T_Ground (the worst), never stop at the first.
    s = _ground_face_mesh("SM_Test_S_Ground", SKIRT, SKIRT_POLYS)
    t = _ground_face_mesh("SM_Test_T_Ground", [[20, 0, 0], [30, 0, 0], [30, 10, 0], [20, 10, 0]],
                          [[0, 1, 2], [0, 2, 3]])
    found = scene_findings(rb(s, t), "npm", "ground", PROFILES.npm)
    f = next(f for f in found["V003"] if f.name == "ground skirt depth")
    assert f.status == "fail"
    assert "T_Ground" in f.observed


# #1133 case 1: a skirt whose ONE bottom edge spans several collinear perimeter edges of a
# subdivided surface. Grid (0,0,0)-(10,10,0), 4x4 quads; perimeter walked corner to corner.

def _grid_4x4():
    n, step = 4, 2.5
    verts = [[x * step, y * step, 0.0] for y in range(n + 1) for x in range(n + 1)]
    polys = [[y * (n + 1) + x, y * (n + 1) + x + 1, (y + 1) * (n + 1) + x + 1, (y + 1) * (n + 1) + x]
             for y in range(n) for x in range(n)]
    idx = lambda x, y: y * (n + 1) + x  # noqa: E731
    sides = [[idx(k, 0) for k in range(n + 1)], [idx(n, k) for k in range(n + 1)],
             [idx(n - k, n) for k in range(n + 1)], [idx(0, n - k) for k in range(n + 1)]]
    return verts, polys, sides


def _fan_skirt(depth, last_span=1.0):
    """One bottom edge per side, fanned to the side's top vertices (``last_span`` < 1: the last
    side's bottom edge covers only that fraction of the side, from its first corner)."""
    verts, polys, sides = _grid_4x4()
    for i, side in enumerate(sides):
        span = last_span if i == len(sides) - 1 else 1.0
        a, b = verts[side[0]], verts[side[-1]]
        end = [a[0] + (b[0] - a[0]) * span, a[1] + (b[1] - a[1]) * span]
        b0, b1 = len(verts), len(verts) + 1
        verts += [[a[0], a[1], -depth], [end[0], end[1], -depth]]
        polys.append([b0, b1, side[-1]])
        for k in range(len(side) - 1, 0, -1):
            polys.append([b0, side[k], side[k - 1]])
    return verts, polys


def test_ground_skirt_one_bottom_edge_spans_collinear_perimeter_edges_passes_1133():
    verts, polys = _fan_skirt(1.0)
    f = _skirt_finding(verts, polys)
    assert f.status == "pass" and f.measured == pytest.approx(1.0)


def test_ground_skirt_per_edge_skirt_on_subdivided_surface_passes_1133():
    verts, polys, sides = _grid_4x4()
    for side in sides:
        base = len(verts)
        verts += [[verts[v][0], verts[v][1], -1.0] for v in side]
        for k in range(len(side) - 1):
            polys.append([side[k + 1], side[k], base + k, base + k + 1])
    f = _skirt_finding(verts, polys)
    assert f.status == "pass" and f.measured == pytest.approx(1.0)


def test_ground_skirt_subdivided_surface_without_skirt_fails_1133():
    verts, polys, _ = _grid_4x4()
    f = _skirt_finding(verts, polys)
    assert f.status == "fail" and f.measured == pytest.approx(0.0)


def test_ground_skirt_spanning_half_metre_fails_1133():
    verts, polys = _fan_skirt(0.5)
    f = _skirt_finding(verts, polys)
    assert f.status == "fail" and f.measured == pytest.approx(0.5)


def test_ground_skirt_spanning_bottom_edge_covering_half_a_side_fails_1133():
    # fail-closed: the bottom edge of one side stops half way; the rest of that side has no skirt
    verts, polys = _fan_skirt(1.0, last_span=0.5)
    f = _skirt_finding(verts, polys)
    assert f.status == "fail" and f.measured == pytest.approx(0.0)


def _step_band_ground(skirt_sides=4):
    """A 10x10 quad Ground with a closed ~76 deg interior step band (a raised 4x4 plateau) and a
    1 m skirt on the outer boundary. ``skirt_sides`` < 4 removes one side of the skirt."""
    verts = []

    def V(x, y, z):
        verts.append([x, y, z])
        return len(verts) - 1

    a = V(0, 0, 0); b = V(10, 0, 0); c = V(10, 10, 0); d = V(0, 10, 0)
    a_ = V(0, 0, -1); b_ = V(10, 0, -1); c_ = V(10, 10, -1); d_ = V(0, 10, -1)
    e = V(4, 4, 0); f = V(6, 4, 0); g = V(6, 6, 0); h = V(4, 6, 0)
    i = V(4.5, 4.5, 2); j = V(5.5, 4.5, 2); k = V(5.5, 5.5, 2); l = V(4.5, 5.5, 2)
    polys, mats = [], []

    def add(p, m):
        polys.append(p)
        mats.append(m)

    tile = "M_Ground_Tile"
    for q in ([a, b, f, e], [b, c, g, f], [c, d, h, g], [d, a, e, h]):
        add([q[0], q[1], q[2]], tile)
        add([q[0], q[2], q[3]], tile)
    for q in ([e, f, j, i], [f, g, k, j], [g, h, l, k], [h, e, i, l]):
        add([q[0], q[1], q[2]], tile)
        add([q[0], q[2], q[3]], tile)
    add([i, j, k], tile)
    add([i, k, l], tile)
    for q in ([a, b, b_, a_], [b, c, c_, b_], [c, d, d_, c_], [d, a, a_, d_])[:skirt_sides]:
        add([q[0], q[1], q[2]], "M_Ground_Skirt")
        add([q[0], q[2], q[3]], "M_Ground_Skirt")
    return verts, polys, mats


def _tilted_skirt_ground(lean):
    """A flat 10x10 quad with a full skirt whose walls lean outward by ``lean`` (XY), giving each
    skirt face an upward normal ratio ~ ``lean``. ``lean`` < 1e-4 keeps the skirt-bottom XY inside
    the 0.1 mm pairing tolerance so the drop still measures 1 m."""
    verts = []

    def V(x, y, z):
        verts.append([x, y, z])
        return len(verts) - 1

    t0 = V(0, 0, 0); t1 = V(10, 0, 0); t2 = V(10, 10, 0); t3 = V(0, 10, 0)
    s0 = V(-lean, -lean, -1); s1 = V(10 + lean, -lean, -1)
    s2 = V(10 + lean, 10 + lean, -1); s3 = V(-lean, 10 + lean, -1)
    polys, mats = [], []

    def add(p, m):
        polys.append(p)
        mats.append(m)

    add([t0, t1, t2], "M_Ground_Tile")
    add([t0, t2, t3], "M_Ground_Tile")
    for q in ([t0, t1, s1, s0], [t1, t2, s2, s1], [t2, t3, s3, s2], [t3, t0, s0, s3]):
        add([q[0], q[1], q[2]], "M_Ground_Skirt")
        add([q[0], q[2], q[3]], "M_Ground_Skirt")
    return verts, polys, mats


def test_ground_skirt_steep_interior_step_band_passes_gnd03():
    # A closed ~76 deg interior step band is surface, not perimeter: its rim must not detour the
    # outer loop. The full 1 m skirt then makes every outer edge drop 1 m.
    verts, polys, mats = _step_band_ground()
    f = _skirt_finding(verts, polys, materials=mats)
    assert f.status == "pass" and f.measured == pytest.approx(1.0)


def test_ground_skirt_steep_step_band_skirt_removed_one_side_fails_gnd03():
    # Same ground with one skirt side removed: the bare outer edge still fails (unchanged behaviour).
    verts, polys, mats = _step_band_ground(skirt_sides=3)
    f = _skirt_finding(verts, polys, materials=mats)
    assert f.status == "fail" and f.measured == pytest.approx(0.0)


def test_ground_skirt_float_noise_tilted_skirt_stays_skirt_gnd03():
    # A *_Skirt wall tilted by float noise (nz/|n| ~ 1e-9) must stay a skirt, not become surface:
    # the full skirt still measures a 1 m drop.
    verts, polys, mats = _tilted_skirt_ground(lean=1e-9)
    f = _skirt_finding(verts, polys, materials=mats)
    assert f.status == "pass" and f.measured == pytest.approx(1.0)


def test_ground_skirt_upward_skirt_face_excluded_by_material_gnd03():
    # Material guard: a flat upward face (nz/|n| = 1) named *_Skirt is excluded from the surface
    # even though the geometry alone (nz > eps*|n|) would admit it.
    verts = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]
    polys = [[0, 1, 2], [0, 2, 3]]
    assert _skirt_finding(verts, polys).status == "fail"  # geometry alone: surface, no skirt
    assert _skirt_finding(verts, polys, materials=["M_Ground_Skirt"] * 2).status == "not_run"


def test_edge_loop_100x100_grid_runtime_bounded_d200():
    import time

    n = 100
    verts = [[x, y, 0.0] for y in range(n + 1) for x in range(n + 1)]
    polys = [[y * (n + 1) + x, y * (n + 1) + x + 1, (y + 1) * (n + 1) + x + 1, (y + 1) * (n + 1) + x]
             for y in range(n) for x in range(n)]
    mesh_ = _face_mesh("SM_Test_K_1_Main", verts, polys)
    start = time.perf_counter()
    got = edge_loop_findings([mesh_], "grid.fbx")
    elapsed = time.perf_counter() - start
    assert got[0].status == "pass"
    assert elapsed < 5.0
