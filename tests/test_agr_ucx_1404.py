"""#1404 [D325]: `agr ucx` = ucx_build (build) -> fresh readback -> ucx10_core.plan gap check + V010.

Pattern: n/a | new-case: CLI chain tests with mocked Blender steps, synthetic convex boxes (synthetic data).
"""
import importlib
import json
import math
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from dt_ai.core.blender_runner import BlenderRunError
from dt_ai.geometry import ucx_command as uc

ROOT = Path(__file__).resolve().parents[1]


def box(x0, x1, y0=0.0, y1=1.0, z0=0.0, z1=1.0):
    v = [[x, y, z] for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    t = [[0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5], [0, 4, 5], [0, 5, 1],
         [2, 3, 7], [2, 7, 6], [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3]]
    return {"verts": v, "tris": t}


def mesh(name, hull):
    return {"name": name, "hull": hull}


def two(gap):
    return [mesh("UCX_SM_T_Ground_001", box(0, 1)), mesh("UCX_SM_T_Ground_002", box(1 + gap, 2))]


# --- agr dispatch (RED before #1404: the stub returned 2 with a pointer) ---------------------------------------
def test_agr_ucx_is_a_real_command(capsys):
    agr = importlib.import_module("dt_ai.cli.agr")
    assert "ucx" not in agr.STUBS
    assert agr.main(["ucx", "--help"]) == 0
    out = capsys.readouterr().out
    assert "ucx_build" in out and "ucx10_core" in out and "V010" in out


def test_agr_ucx_dispatches_to_command(monkeypatch):
    agr = importlib.import_module("dt_ai.cli.agr")
    main = Mock(return_value=1)
    monkeypatch.setattr(uc, "main", main)
    assert agr.main(["ucx", "a.fbx", "b.fbx", "Main", "cell=0.5"]) == 1
    main.assert_called_once_with(["a.fbx", "b.fbx", "Main", "cell=0.5"])


# --- refusals: exit 4, nothing written ---------------------------------------------------------------------------
@pytest.fixture
def model(tmp_path):
    p = tmp_path / "SM_T_Ground.fbx"
    p.write_bytes(b"synthetic model")
    return p


@pytest.mark.parametrize("make", [
    lambda m, d: [],
    lambda m, d: [str(m)],
    lambda m, d: [str(m), str(d / "o.fbx")],
    lambda m, d: [str(m), str(d / "o.fbx"), "Roof"],
    lambda m, d: [str(m), str(d / "o.fbx"), "main"],
    lambda m, d: [str(m), str(d / "o.obj"), "Main"],
    lambda m, d: [str(m), str(m), "Ground"],
    lambda m, d: [str(m), str(d / "o.fbx"), "Main", "cell"],
    lambda m, d: [str(m), str(d / "o.fbx"), "Main", "--gap-m", "NaN"],
    lambda m, d: [str(m), str(d / "o.fbx"), "Main", "--gap-m", "inf"],
    lambda m, d: [str(m), str(d / "o.fbx"), "Main", "--gap-m", "0.0019"],
    lambda m, d: [str(m), str(d / "o.fbx"), "Main", "--gap-m", "0.0101"],
    lambda m, d: [str(m), str(d / "o.fbx"), "Main", "--gap-m"],
    lambda m, d: [str(m), str(d / "o.fbx"), "Main", "--gap-m", "0.004", "--gap-m", "0.004"],
    lambda m, d: [str(m), str(d / "o.fbx"), "Main", "--force"],
    lambda m, d: [str(d / "missing.fbx"), str(d / "o.fbx"), "Main"],
    lambda m, d: [str(d / "model.txt"), str(d / "o.fbx"), "Main"],
])
def test_refused_before_any_write(make, model, tmp_path, monkeypatch, capsys):
    run = Mock()
    monkeypatch.setattr(uc, "run", run)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert uc.main(make(model, tmp_path)) == 4
    assert "refused" in capsys.readouterr().err
    run.assert_not_called()
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


@pytest.mark.parametrize("existing", ["o.fbx", "o.fbx.ucx_build.json", "o.fbx.agr_ucx.json"])
def test_existing_output_or_report_is_never_overwritten(existing, model, tmp_path, monkeypatch):
    (tmp_path / existing).write_text("approved")
    monkeypatch.setattr(uc, "run", Mock())
    assert uc.main([str(model), str(tmp_path / "o.fbx"), "Main"]) == 4
    assert (tmp_path / existing).read_text() == "approved"


def test_alias_through_dotdot_is_refused(model, tmp_path, monkeypatch):
    monkeypatch.setattr(uc, "run", Mock())
    alias = tmp_path / "sub" / ".." / model.name
    (tmp_path / "sub").mkdir()
    assert uc.main([str(model), str(alias), "Ground"]) == 4
    assert model.read_bytes() == b"synthetic model"


def test_fresh_process_refusal(model, tmp_path):
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    r = subprocess.run([sys.executable, "-m", "dt_ai.cli.agr", "ucx", str(model), str(model), "Ground"],
                       capture_output=True, text=True)
    assert r.returncode == 4 and "nothing written" in r.stderr, r.stderr
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


# --- gap check through ucx10_core.plan ----------------------------------------------------------------------------
@pytest.mark.parametrize("gap,ok", [(0.004, True), (0.0041, True), (0.01, True), (0.5, True),
                                    (0.0039, False), (0.002, False), (0.0, False), (-0.005, False),
                                    (-0.05, False)])
def test_gap_check_measures_only(gap, ok):
    meshes = two(gap)
    snapshot = json.dumps(meshes)
    res = uc.gap_check(meshes, 0.004)
    assert res["ok"] is ok
    assert bool(res["pairs_under_gap"]) is (not ok)
    assert json.dumps(meshes) == snapshot  # the readback is never modified


def test_gap_check_generated_pairs():
    # generated probe: 200 gaps across the threshold; ok iff gap >= 4 mm - 0.01 mm (ucx10_core TOL_M)
    for i in range(200):
        gap = -0.01 + i * 0.0001
        res = uc.gap_check(two(gap), 0.004)
        assert res["ok"] is (gap >= 0.004 - 1e-5), gap


def test_gap_check_empty_and_missing_hull_fail_closed():
    assert uc.gap_check([], 0.004)["ok"] is False
    res = uc.gap_check([mesh("UCX_SM_T_Main_001", None)], 0.004)
    assert res["ok"] is False and res["dropped"][0]["name"] == "UCX_SM_T_Main_001"
    res = uc.gap_check([mesh("UCX_SM_T_Main_001", box(0, 1)), {"name": "UCX_SM_T_Main_002", "hull": {}}], 0.004)
    assert res["ok"] is False and [d["name"] for d in res["dropped"]] == ["UCX_SM_T_Main_002"]


def test_gap_check_non_convex_and_bad_name_fail():
    open_box = box(0, 1)
    open_box["tris"] = open_box["tris"][:-2]
    res = uc.gap_check([mesh("UCX_SM_T_Main_001", open_box)], 0.004)
    assert res["ok"] is False and "UCX_SM_T_Main_001" in res["findings"]
    res = uc.gap_check([mesh("UCX_SM_T_Main_001", box(0, 1)), mesh("UCX_noindex", box(3, 4))], 0.004)
    assert res["ok"] is False and res["skipped"]


@pytest.mark.parametrize("bad", [float("nan"), math.inf, 0.0, 0.02, None])
def test_gap_check_bad_gap_raises(bad):
    with pytest.raises(ValueError):
        uc.gap_check(two(0.004), bad)


# --- chain statuses (Blender steps mocked) --------------------------------------------------------------------------
def _args(model, tmp_path, gap=None):
    a = uc.parse([str(model), str(tmp_path / "o.fbx"), "Ground", "cell=16"] +
                 (["--gap-m", str(gap)] if gap else []))
    return a


def _wire(monkeypatch, build, rb, v010):
    import dt_ai.core.blender_runner as br
    import twinqa.scene as sc
    monkeypatch.setattr(br, "run_blender", build)
    monkeypatch.setattr(sc, "readback", Mock(return_value=rb))
    monkeypatch.setattr(uc, "_v010", Mock(return_value=v010))


BUILD = {"ok": True, "pieces": 2, "triangles": 24, "gap_m": 0.004, "within_tol": True}
RB = {"readback_ok": True, "meshes": [{"name": "SM_T_Ground"}] + two(0.004)}
V_OK = [{"name": "UCX present", "status": "pass"}, {"name": "UCX shape", "status": "pass"}]


@pytest.mark.parametrize("build,rb,v010,code", [
    (Mock(return_value=BUILD), RB, V_OK, 0),
    (Mock(return_value=dict(BUILD, within_tol=False)), RB, V_OK, 1),
    (Mock(return_value=BUILD), {"readback_ok": True, "meshes": [{"name": "SM_T_Ground"}] + two(0.001)}, V_OK, 1),
    (Mock(return_value=BUILD), {"readback_ok": True, "meshes": [{"name": "SM_T_Ground"}]}, V_OK, 1),
    (Mock(return_value=BUILD), RB, V_OK + [{"name": "UCX material slots", "status": "fail"}], 1),
    (Mock(return_value=BUILD), RB, [], 1),
    (Mock(return_value=BUILD), {"readback_ok": False, "error": "import failed"}, V_OK, 2),
    (Mock(return_value=dict(BUILD, ok=False)), RB, V_OK, 2),
    (Mock(return_value=dict(BUILD, gap_m=None)), RB, V_OK, 2),
    (Mock(side_effect=BlenderRunError({"code": "nonzero_exit", "returncode": 2, "message": "build failed"})),
     RB, V_OK, 2),
    (Mock(side_effect=BlenderRunError({"code": "nonzero_exit", "returncode": 3, "message": "tol"})),
     RB, V_OK, 2),  # exit 3 but no FBX/report on disk: never taken as built
])
def test_chain_status(build, rb, v010, code, model, tmp_path, monkeypatch):
    _wire(monkeypatch, build, rb, v010)
    got, report = uc.run(_args(model, tmp_path))
    assert got == code, report
    assert model.read_bytes() == b"synthetic model"


def test_build_exit3_with_outputs_is_a_check_failure(model, tmp_path, monkeypatch):
    a = _args(model, tmp_path)

    def build(*_a, **_k):
        a["out"].write_bytes(b"fbx")
        a["build_report"].write_text(json.dumps(dict(BUILD, within_tol=False)))
        raise BlenderRunError({"code": "nonzero_exit", "returncode": 3, "message": "tol"})
    _wire(monkeypatch, build, RB, V_OK)
    code, report = uc.run(a)
    assert code == 1 and report["passed_checks"]["build_within_tol"] is False


def test_main_writes_report_once(model, tmp_path, monkeypatch):
    _wire(monkeypatch, Mock(return_value=BUILD), RB, V_OK)
    assert uc.main([str(model), str(tmp_path / "o.fbx"), "Ground"]) == 0
    rep = json.loads((tmp_path / "o.fbx.agr_ucx.json").read_text(encoding="utf-8"))
    assert rep["exit"] == 0 and rep["steps"]["gap_check"]["pieces"] == 2 and rep["decision"] == "D325"
    assert uc.main([str(model), str(tmp_path / "o.fbx"), "Ground"]) == 4  # second run: report exists


def test_explicit_gap_overrides_build_gap(model, tmp_path, monkeypatch):
    _wire(monkeypatch, Mock(return_value=BUILD), RB, V_OK)
    code, report = uc.run(_args(model, tmp_path, gap=0.006))
    assert code == 1 and report["steps"]["gap_check"]["gap_m"] == 0.006


def test_driver_and_cores_are_the_owners():
    assert uc.DRIVER == ROOT / "tools/blender/ucx_build.py" and uc.DRIVER.is_file()
    assert uc.UCX10 == ROOT / "adapters/max/agr_tools/ucx10_core.py" and uc.UCX10.is_file()
    src = uc.DRIVER.read_text(encoding="utf-8")
    assert "src/dt_ai/geometry/ucx_build.py" in src
