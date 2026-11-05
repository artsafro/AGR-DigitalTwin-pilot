"""Team audit T04 (GeoAGR-private PR #72, work/team-scripts-audit/T04/REPORT.md, measured on the PC) findings on the
pilot validator, fixed for qa.package in AGR Tools 0.8 (#908 branch D). Each test is RED on main 6c7a04c3.

1. Blender 5.1.2 cannot import a FBX with lights (`lamp.cycles.cast_shadow`); reproduced in lab job
   20261105-015046-6f7cf91b, fixed in tools/blender/fbx_readback.py (static test here; measured in a Blender job).
2. add_scene stopped at the first unreadable FBX, so the other FBX of the archive were never checked.
3. V004 'applied transforms' was inverted on Blender-exported FBX (baked export failed, default passed).
4. V010 UCX shape (open / concave pieces) stayed not_run.
5. The readback's Blender log went to `<cwd>/logs/blender`.
"""
import zipfile
from pathlib import Path

import validate_package as vp
from test_scene import BOX_TRIS, mesh, rb, statuses, ucx_box
from test_validator import PROFILES, STEM, good_files
from twinqa import scene
from twinqa.scene import scene_findings

ROOT = Path(__file__).resolve().parents[2]


# ---- 2. one unreadable FBX does not hide the others --------------------------------------------------------
def test_scene_readback_continues_after_one_unreadable_fbx(monkeypatch, tmp_path):
    files = good_files()
    files[f"{STEM}_Light.fbx"] = files[f"{STEM}.fbx"]
    package = tmp_path / f"{STEM}.zip"
    with zipfile.ZipFile(package, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    seen = []

    def readback(path, blender=None, timeout=600):
        seen.append(Path(path).name)
        if len(seen) == 1:  # the first FBX read fails (as the _Light import did in T04)
            raise RuntimeError("AttributeError: 'CyclesLightSettings' object has no attribute 'cast_shadow'")
        return rb(mesh(), ucx_box("UCX_SM_Test_K_1_Main_001", (0, 0, 0), (1, 1, 1)))
    monkeypatch.setattr(vp, "readback", readback)
    report = vp.validate(package, "vpm", PROFILES, scene=True)
    assert sorted(seen) == sorted([f"{STEM}.fbx", f"{STEM}_Light.fbx"]), seen  # both read, not only the first
    assert any(n.startswith(f"scene readback skipped for {seen[0]}") for n in report.notes)
    assert any(n.startswith(f"scene readback: {seen[1]}") for n in report.notes)

def test_add_scene_does_not_return_on_the_first_error():
    src = (ROOT / "tools/qa/validate_package.py").read_text(encoding="utf-8")
    block = src[src.index("def add_scene"):src.index("def validate(")]
    assert "continue" in block and "                return\n" not in block


# ---- 3. V004 measured on both import modes ------------------------------------------------------------------
def _v004(m):
    return statuses(scene_findings(rb(m), "vpm", "oks", PROFILES.vpm), "V004")["applied transforms"]


def test_v004_baked_blender_export_passes():
    """Blender export with bake_space_transform: default import +90 X / 0.01, baked import identity -> pass."""
    m = mesh(rot=(90, 0, 0), scale=(0.01, 0.01, 0.01))
    m["baked_rotation_euler_deg"], m["baked_scale"] = [0.0, 0.0, 0.0], [1.0, 1.0, 1.0]
    assert _v004(m) == "pass"


def test_v004_real_rotation_fails_in_both_import_modes():
    """A node turned 30 deg about Z keeps that rotation in both modes (Max/Blender default and baked) -> fail."""
    m = mesh(rot=(0, 0, 30))
    m["baked_rotation_euler_deg"], m["baked_scale"] = [-90.0, 0.0, 30.0], [1.0, 1.0, 1.0]
    assert _v004(m) == "fail"
    baked = mesh(rot=(90, 0, 30), scale=(0.01, 0.01, 0.01))
    baked["baked_rotation_euler_deg"], baked["baked_scale"] = [0.0, 0.0, 30.0], [1.0, 1.0, 1.0]
    assert _v004(baked) == "fail"


def test_v004_max_export_identity_needs_no_second_import():
    assert _v004(mesh()) == "pass"  # Max FBX, rotation 0: identity in the default import (lab job c6e23463)


# ---- 4. V010 UCX shape ------------------------------------------------------------------------------------------
def _shape(ucx):
    found = scene_findings(rb(mesh(), ucx), "vpm", "oks", PROFILES.vpm)
    return next(f for f in found["V010"] if f.name == "UCX shape")


def test_v010_ucx_shape_closed_convex_passes():
    f = _shape(ucx_box("UCX_SM_Test_K_1_Main_001", (0, 0, 0), (1, 1, 1)))
    assert f.status == "pass"


def test_v010_open_ucx_fails():
    u = ucx_box("UCX_SM_Test_K_1_Main_001", (0, 0, 0), (1, 1, 1))
    u["hull"]["tris"] = u["hull"]["tris"][2:]  # two triangles removed: an open box
    f = _shape(u)
    assert f.status == "fail" and "open" in f.observed


def test_v010_concave_ucx_fails():
    u = ucx_box("UCX_SM_Test_K_1_Main_001", (0, 0, 0), (1, 1, 1))
    u["hull"]["verts"][7] = [0.45, 0.45, 0.45]  # the (1,1,1) corner pushed inside: a dented, non-convex hull
    f = _shape(u)
    assert f.status == "fail" and "non-convex" in f.observed, f.observed


def test_v010_without_hull_data_is_not_run_not_pass():
    f = _shape(mesh(name="UCX_SM_Test_K_1_Main_001"))
    assert f.status == "not_run"
    assert len(BOX_TRIS) == 12


# ---- 5. readback logs never land in the caller's cwd -------------------------------------------------------
def test_readback_log_goes_to_twinqa_log_dir_not_cwd(monkeypatch, tmp_path):
    got = {}

    def fake_run(script, args, executable=None, output_json=None, timeout=600, log_path=None, **kw):
        got['log'] = log_path
        return {"source": str(args[0]), "readback_ok": True, "meshes": [], "other_objects": [], "images": []}
    monkeypatch.setattr(scene, "run_blender", fake_run)
    monkeypatch.setenv("TWINQA_LOG_DIR", str(tmp_path / "logs"))
    fbx = tmp_path / "a.fbx"
    fbx.write_bytes(b"x")
    monkeypatch.chdir(tmp_path)
    scene.readback(fbx)
    assert got['log'] is not None and Path(got['log']).parent == tmp_path / "logs"
    monkeypatch.delenv("TWINQA_LOG_DIR")
    scene.readback(fbx)
    assert "twinqa" in str(got['log']) and not Path(got['log']).is_relative_to(tmp_path)


# ---- 1. light FBX import (static; the import itself is measured in a Blender-slot job) ---------------------
def test_readback_restores_the_cycles_flag_and_accepts_lights_only_fbx():
    src = (ROOT / "tools/blender/fbx_readback.py").read_text(encoding="utf-8")
    assert "def light_import_compat" in src and "cast_shadow" in src
    assert src.index("light_import_compat()") < src.index("bpy.ops.import_scene.fbx(filepath=str(source))")
    assert "lights_only" in src
