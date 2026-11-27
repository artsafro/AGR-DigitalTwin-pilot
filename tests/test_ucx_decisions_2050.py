"""#2050: UCX decisions of 2026-11-27 (Artem) - budget vs form [D427], convexity tolerance [D430], decision rows,
Codex etalons in the trainer bank. SYNTHETIC meshes only.

Pattern: n/a | new-case: tests/test_ucx_decisions_2050.py - regressions of the #2050 UCX decisions."""
from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest

from dt_ai.geometry import ucx_build as ub
from dt_ai.geometry import ucx_command as uc
from twinqa.geometry import ucx_audit as ua

ROOT = Path(__file__).resolve().parents[1]
LINE = re.compile(r"over D012 budget by (\d+) tris, allowed by \[D427\] when form needs it")


def box(x0, x1, y0, y1, z0, z1):
    v = np.array([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                  (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], float)
    return v, ub._BOX_TRIS.copy()


def dented_box(dent, x0=0.0):
    """1 m cube whose top face is a fan around a centre vertex sunk by `dent` metres (non-convex by ~2 x dent)."""
    v, t = box(x0, x0 + 1, 0, 1, 0, 1)
    v = np.vstack([v, [(x0 + 0.5, 0.5, 1 - dent)]])
    top = [(4, 5, 8), (5, 6, 8), (6, 7, 8), (7, 4, 8)]
    t = np.array([tri for i, tri in enumerate(t.tolist()) if i not in (2, 3)] + top)
    return v, t


def two_cubes():
    a, b = box(0, 1, 0, 1, 0, 1), box(20, 21, 0, 1, 0, 1)
    return np.vstack([a[0], b[0]]), np.vstack([a[1], b[1] + 8])


# ---- [D427] budget is a reported number, never a refusal ------------------------------------------------------
def test_budget_report_over_and_within():
    over = ua.d012_budget_report(50200, 2520)
    assert over["limit_D012"] == 2510 and over["within_D012"] is False and over["over_by"] == 10
    assert LINE.fullmatch(over["line"]) and LINE.fullmatch(over["line"]).group(1) == "10"
    ok = ua.d012_budget_report(50200, 2510)
    assert ok["within_D012"] is True and ok["over_by"] == 0 and "within D012 budget" in ok["line"]


def test_file_budget_never_refuses():
    assert ub.file_budget_available(50200, 2511) == -1
    rep = ub.check_file_budget(50200, 2511)
    assert rep["within_D012"] is False and rep["over_by"] == 1


def test_main_over_budget_builds_and_reports():
    v, t = two_cubes()
    res = ub.build_main(v, t, model_triangles=50200, reserved_triangles=2508)
    assert res.triangles == 24 and res.budget == 2 and res.over_budget_by == 22


def test_main_form_mode_keeps_the_cell():
    v, t = two_cubes()
    res = ub.build_main(v, t, cell=0.25, model_triangles=100, reserved_triangles=14990, budget_mode="form")
    assert len(res.attempts) == 1 and res.cell_m == 0.25 and res.over_budget_by == 24 - 10
    with pytest.raises(ub.UcxBuildError, match="budget_mode"):
        ub.build_main(v, t, budget_mode="tight")


def test_ground_over_budget_builds_and_reports():
    xs = np.arange(11.0)
    g = np.array([(x, y, 0.1 * x) for x in xs for y in xs])
    t = [(i * 11 + j, (i + 1) * 11 + j, i * 11 + j + 1) for i in range(10) for j in range(10)]
    t += [((i + 1) * 11 + j, (i + 1) * 11 + j + 1, i * 11 + j + 1) for i in range(10) for j in range(10)]
    free = ub.build_ground(g, np.array(t), cell=5.0, min_cell=0.5, model_triangles=50200)
    res = ub.build_ground(g, np.array(t), cell=5.0, min_cell=0.5, model_triangles=50200,
                          reserved_triangles=2510 - free.triangles + 3)
    assert res.triangles == free.triangles and res.over_budget_by == 3


GAP = 0.003
RESOLVE_OK = {"ok": True, "gap_m": GAP, "pairs_resolved": 0, "pairs_ambiguous": 0, "left": [],
              "ucx_triangles": 2520, "model_triangles_excl_ucx": 50200, "file_ucx_limit_D012": 2510,
              "model_to_ucx_max_m": 0.02, "model_to_ucx_limit_m": 1.0, "within_D012": False, "within_D134": True}


@pytest.fixture
def model(tmp_path):
    p = tmp_path / "in.fbx"
    p.write_bytes(b"x")
    return p


def _rb(*meshes):
    return {"readback_ok": True, "meshes": [{"name": "SM_T_Main"}] + [
        {"name": n, "hull": {"verts": v.tolist(), "tris": t.tolist()}} for n, (v, t) in meshes]}


def test_resolve_over_budget_passes_with_line(model, tmp_path, monkeypatch):
    from dt_ai.core import blender_runner as br
    from twinqa import scene as sc

    monkeypatch.setattr(br, "run_blender", Mock(return_value=dict(RESOLVE_OK)))
    monkeypatch.setattr(sc, "readback", Mock(return_value=_rb(("UCX_SM_T_Main_001", box(0, 1, 0, 1, 0, 1)))))
    monkeypatch.setattr(uc, "_v010", Mock(return_value=[{"name": "x", "status": "pass"}]))
    code, report = uc.run(uc.parse([str(model), str(tmp_path / "o.fbx"), "Main", "--resolve"]))
    assert code == 0, report
    assert LINE.fullmatch(report["budget_D012"]["line"]).group(1) == "10"


def test_build_report_carries_budget_line(model, tmp_path, monkeypatch):
    from dt_ai.core import blender_runner as br
    from twinqa import scene as sc

    build = {"ok": True, "pieces": 1, "triangles": 12, "gap_m": GAP, "within_tol": True,
             "model_triangles_excl_ucx": 100, "file_ucx_triangles": 15012, "file_ucx_limit_D012": 15000}
    monkeypatch.setattr(br, "run_blender", Mock(return_value=build))
    monkeypatch.setattr(sc, "readback", Mock(return_value=_rb(("UCX_SM_T_Main_001", box(0, 1, 0, 1, 0, 1)))))
    monkeypatch.setattr(uc, "_v010", Mock(return_value=[{"name": "x", "status": "pass"}]))
    code, report = uc.run(uc.parse([str(model), str(tmp_path / "o.fbx"), "Main"]))
    assert code == 0, report
    assert LINE.fullmatch(report["budget_D012"]["line"]).group(1) == "12"


def test_v010_budget_fail_does_not_fail_agr_ucx(model, tmp_path, monkeypatch):
    """Real Polyani run (cell 0.85, budget=form): every V010 finding passed except 'UCX triangle budget'; in
    `agr ucx` that one is the reported budget line [D427], any other V010 fail still fails the command."""
    from dt_ai.core import blender_runner as br
    from twinqa import scene as sc

    build = {"ok": True, "pieces": 1, "triangles": 12, "gap_m": GAP, "within_tol": True,
             "model_triangles_excl_ucx": 100, "file_ucx_triangles": 15012}
    monkeypatch.setattr(br, "run_blender", Mock(return_value=build))
    monkeypatch.setattr(sc, "readback", Mock(return_value=_rb(("UCX_SM_T_Main_001", box(0, 1, 0, 1, 0, 1)))))
    v010 = [{"name": "UCX present", "status": "pass"}, {"name": "UCX triangle budget", "status": "fail"}]
    monkeypatch.setattr(uc, "_v010", Mock(return_value=v010))
    code, report = uc.run(uc.parse([str(model), str(tmp_path / "o.fbx"), "Main"]))
    assert code == 0 and report["passed_checks"]["V010_no_fail"] is True, report
    v010.append({"name": "UCX material slots", "status": "fail"})
    code, report = uc.run(uc.parse([str(model), str(tmp_path / "o2.fbx"), "Main"]))
    assert code == 1


# ---- [D430] convexity tolerance 1 mm -------------------------------------------------------------------------
def test_twinqa_convex_tolerance_is_1mm():
    assert ua.CONVEX_TOL_M == pytest.approx(1e-3)
    assert ua.is_convex(*dented_box(0.0004))
    assert not ua.is_convex(*dented_box(0.0008))


@pytest.mark.parametrize("dent,ok", [(0.0004, True), (0.0008, False)])
def test_gap_check_counts_within_1mm_as_convex(dent, ok):
    v, t = dented_box(dent)
    w, s = box(1.005, 2.005, 0, 1, 0, 1)
    meshes = [{"name": "UCX_SM_T_Main_001", "hull": {"verts": v.tolist(), "tris": t.tolist()}},
              {"name": "UCX_SM_T_Main_002", "hull": {"verts": w.tolist(), "tris": s.tolist()}}]
    got = uc.gap_check(meshes, GAP)
    assert got["ok"] is ok, got
    if ok:
        assert [r["name"] for r in got["convex_within_D430"]] == ["UCX_SM_T_Main_001"]
        assert got["convex_within_D430"][0]["worst_m"] == pytest.approx(2 * dent, abs=2e-5)


# ---- decision rows and the etalon bank -----------------------------------------------------------------------
def test_decision_rows_and_d012_backlink():
    text = (ROOT / "docs/decisions.md").read_text(encoding="utf-8")
    rows = {m.group(1): m.group(0) for m in re.finditer(r"^\| (D\d+) \|.*$", text, re.M)}
    for d in ("D427", "D428", "D429", "D430", "D431"):
        assert d in rows and "2026-11-27" in rows[d]
    assert "D012" in rows["D427"] and "partly supersede" in rows["D427"]
    assert "D427" in rows["D012"] and "partly superseded" in rows["D012"]
    assert "D134" in rows["D428"] and "R14" in rows["D429"] and "1 mm" in rows["D430"]
    assert "D098" in rows["D431"] and "D339" in rows["D431"]


CODEX = {"ucx-codex-02-garibaldi-k2", "ucx-codex-10-polyani", "ucx-codex-06-geo019-slope",
         "ucx-codex-07-geo004-arch", "ucx-codex-08-geo004-round"}


def test_codex_ucx_etalons_in_bank():
    from tools.trainer import trainer as T

    bank = json.loads((ROOT / "docs/trainer/etalons.json").read_text(encoding="utf-8"))
    assert T.bank_problems(bank) == []
    got = {e["id"]: e for e in bank["etalons"] if e["id"] in CODEX}
    assert set(got) == CODEX
    for e in got.values():
        assert e["split"] == "held_out" and e["practice_ready"] is False
        assert e["accepted_by"] == "ACCEPTED-BY-CODEX" and e["caveat"]
        assert e["key"]["path"].startswith("G:/Мой диск/AGR-evidence/ucx-etalons-codex/")
        assert re.fullmatch(r"[0-9a-f]{64}", e["key"]["sha256"])
