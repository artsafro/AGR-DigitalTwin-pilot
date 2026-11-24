"""#1821: the shared Ground report separates measured checks from assumptions and advisories.

- UV parity across the relief stage is reported ``not_measured`` with a reason (relief adds vertices; UDIM tile
  assignment is not UV-parity proof), never a hard-coded ``True``.
- Project zero: the value supplied by the project, the zero Z assumed for the OBJ readback check and the
  unmeasured FBX zero are three distinct report entries.
- Geometry status / CLI exit code follow ``geometry_failures`` only; advisories (e.g. ``UCX not built``) never
  decide it, whatever their count.

All site data is SYNTHETIC (generated squares, planes and DXF from test_ground_site_1406), never a real object.
"""
import importlib.util
import json
import random

import pytest

from dt_ai.geometry import ground_site as gs
from tests.test_ground_site_1406 import SITE, build, make_spec, run

UCX = "UCX not built: " + gs.UCX_OWNER


def _cli():
    spec = importlib.util.spec_from_file_location("build_ground_site_1821", SITE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _patched(monkeypatch, cli, edit):
    real = gs.build_site

    def fake(*a, **kw):
        res = real(*a, **kw)
        edit(res.report)
        return res
    monkeypatch.setattr(cli.gs, "build_site", fake)


def test_minimal_built_case_reports_failures_and_advisories_apart():
    rep = build().report
    assert rep["geometry_failures"] == []
    assert rep["advisories"] == [UCX]
    assert rep["findings"] == rep["geometry_failures"] + rep["advisories"]
    assert rep["geometry_status"] == "built" and rep["passed"] is False


def test_uv_parity_is_not_measured_with_reason():
    rel = build().report["stages"]["relief"]
    assert "uv_unchanged_by_projection" not in rel
    uv = rel["uv_parity"]
    assert uv["status"] == "not_measured"
    assert "vertices" in uv["reason"] and "UDIM" in uv["reason"]
    assert uv["flat_vertices"] < uv["relief_vertices"]  # relief adds vertices: no row-by-row comparison


def test_zero_supplied_vs_fbx_not_measured_in_builder():
    z = build().report["stages"]["zero"]
    assert "fbx_z_of_zero_m" not in z
    assert z["project_zero_m"] == 100.0 and z["project_zero_role"] == "supplied by the project (caller input)"
    assert z["local_z_of_project_zero_m"] == 0.0
    assert z["fbx_z_of_zero"]["status"] == "not_measured" and "FBX" in z["fbx_z_of_zero"]["reason"]


@pytest.mark.parametrize("failures,advisories,status", [
    ([], [], "built"), ([], [UCX], "built"), ([], [UCX, "a2", "a3"], "built"),
    (["relief: 1 samples over 0.01 m"], [], "fail"), (["x"], [UCX], "fail"), (["x", "y"], [UCX, "a"], "fail")])
def test_finalize_status_counts_failures_only(failures, advisories, status):
    rep = {"geometry_failures": list(failures), "advisories": list(advisories)}
    assert gs.finalize_geometry(rep) is (status == "fail")
    assert rep["geometry_status"] == status and rep["findings"] == failures + advisories


def test_finalize_status_generated_probe():
    rnd = random.Random(1821)
    for _ in range(300):
        f = [f"f{i}" for i in range(rnd.randint(0, 3))]
        a = [f"a{i}" for i in range(rnd.randint(0, 4))]
        rep = {"geometry_failures": f, "advisories": a}
        assert gs.finalize_geometry(rep) is bool(f)
        assert rep["geometry_status"] == ("fail" if f else "built")


@pytest.mark.parametrize("bad", [{}, {"geometry_failures": []}, {"geometry_failures": "x", "advisories": []},
                                 {"geometry_failures": [""], "advisories": []},
                                 {"geometry_failures": [], "advisories": [None]}])
def test_finalize_status_fail_closed_on_malformed(bad):
    with pytest.raises((KeyError, ValueError)):
        gs.finalize_geometry(bad)


def test_cli_built_obj_readback_zero_is_qualified(tmp_path):
    spec, _ = make_spec(tmp_path)
    r = run(SITE, spec, tmp_path / "out")
    assert r.returncode == 0, r.stderr
    rep = json.loads((tmp_path / "out/ground-report.json").read_text(encoding="utf-8"))
    assert rep["geometry_status"] == "built" and rep["geometry_failures"] == [] and rep["advisories"] == [UCX]
    pz = rep["project_zero_check"]
    assert pz["status"] == "pass" and pz["checked_file"] == "SM_SYN_Ground.obj" and pz["checked_format"] == "OBJ"
    assert "project_zero_fbx_z_m" not in pz
    assert pz["obj_z_of_zero_m_assumed"] == 0.0 and pz["project_zero_m"] == 100.0
    assert pz["fbx_z_of_zero"]["status"] == "not_measured"
    assert rep["stages"]["zero"]["fbx_z_of_zero"]["status"] == "not_measured"
    assert json.loads(r.stdout)["geometry_failures"] == []


def test_cli_advisories_only_exit_0(tmp_path, monkeypatch):
    cli = _cli()
    _patched(monkeypatch, cli, lambda rep: rep["advisories"].extend(["advisory 2", "advisory 3"]))
    spec, _ = make_spec(tmp_path)
    assert cli.run(spec, tmp_path / "out") == 0
    rep = json.loads((tmp_path / "out/ground-report.json").read_text(encoding="utf-8"))
    assert rep["geometry_status"] == "built" and len(rep["advisories"]) == 3 and rep["passed"] is False


def test_cli_single_failure_without_advisories_exit_1_keeps_diagnostics(tmp_path, monkeypatch):
    cli = _cli()

    def edit(rep):
        rep["advisories"].clear()
        rep["geometry_failures"].append("relief: 1 samples over 0.01 m")
    _patched(monkeypatch, cli, edit)
    spec, _ = make_spec(tmp_path)
    assert cli.run(spec, tmp_path / "out") == 1
    out = tmp_path / "out"
    assert sorted(p.name for p in out.iterdir()) == ["SM_SYN_Ground.obj", "ground-flat.obj", "ground-report.json"]
    rep = json.loads((out / "ground-report.json").read_text(encoding="utf-8"))
    assert rep["geometry_status"] == "fail" and rep["passed"] is False
    assert rep["findings"] == ["relief: 1 samples over 0.01 m"] and rep["advisories"] == []
    assert not (tmp_path / "out.partial").exists()


def test_cli_readback_failure_is_a_geometry_failure(tmp_path, monkeypatch):
    """A failure the CLI itself measures (readback UDIM tiles) lands in geometry_failures and exits 1."""
    cli = _cli()
    real = cli.gs.read_obj

    def bad_tiles(path):
        back = real(path)
        back["tiles"] = {k: [9999] for k in back["tiles"]}
        return back
    monkeypatch.setattr(cli.gs, "read_obj", bad_tiles)
    spec, _ = make_spec(tmp_path)
    assert cli.run(spec, tmp_path / "out") == 1
    rep = json.loads((tmp_path / "out/ground-report.json").read_text(encoding="utf-8"))
    assert any(f.startswith("readback UDIM tiles") for f in rep["geometry_failures"])
    assert rep["advisories"] == [UCX] and rep["geometry_status"] == "fail"

