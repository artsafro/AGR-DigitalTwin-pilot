"""new-case: FLO-04 planting-schedule handoff evidence for `agr validate --scene` (#1700).

SYNTHETIC inputs only: a fake Ground FBX byte string, a mocked Blender readback (the test_npm_uv_1580 pattern)
and hand-written normalized schedule entries. No real object, project asset or DCC is used.

What the tests pin (no production code is changed by #1700):
- the shared validator route (tools/qa/validate_package.py, `agr validate`) calls `scene_findings` WITHOUT
  `flora_schedule`, so a recognized Flora plant yields V015 "Flora dimensions" = not_run in the JSON and text
  report, and no public CLI argument can supply a schedule;
- `twinqa.flora.dimension_findings` with normalized entries: pass inside D099 +-20 % (D100 10 cm sinking),
  fail outside, not_run without a schedule, review for a missing mesh / dimension;
- the Vatutino job-local caller passes its normalized schedule separately (keyword `flora_schedule`) and
  reads back a separate per-instance check FBX, not the delivery FBX.
"""
import ast
import json
import math
import random
from pathlib import Path

import pytest

import validate_package as vp
from test_scene import mesh
from twinqa.flora import DIM_TOL, SINK_M, dimension_findings

ROOT = Path(__file__).resolve().parents[2]
GROUND = "SM_Synth1700_Ground.fbx"  # synthetic name, not a real address
PLANT = "SM_Synth1700_Flora"        # recognized by the `Flora` name token


def plant(name=PLANT, height=3.0, crown=2.0):
    """Synthetic readback mesh whose bbox gives height (after the D100 sinking) and crown exactly."""
    m = mesh(name=name, tris=200, materials=("M_Synth1700_Flora_1",))
    m["bounds_m"] = [[0.0, 0.0, -SINK_M], [crown, crown * 0.5, height]]
    return m


def ground_rb(*meshes):
    return {"source": f"C:/x/{GROUND}", "readback_ok": True, "meshes": [mesh("SM_Synth1700_Ground", tris=100),
            *meshes], "other_objects": [], "images": [], "materials": [],
            "fbx_units": {"unit_scale_factor": 100.0, "original_unit_scale_factor": 100.0, "error": None}}


def run_validate(tmp_path, monkeypatch, capsys, rb, as_json=True, extra=()):
    fbx = tmp_path / GROUND
    fbx.write_bytes(b"synthetic FBX bytes (#1700 test, not a real object)")
    monkeypatch.setattr(vp, "readback", lambda p: rb)
    calls = []
    real = vp.scene_findings

    def spy(*args, **kwargs):
        calls.append(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(vp, "scene_findings", spy)
    code = vp.main([str(fbx), "--profile", "npm", "--scene", *(["--json"] if as_json else []), *extra])
    out = capsys.readouterr()
    return code, out, calls


def v015(report):
    return [(f["name"], f["status"], f["observed"]) for s in report["stages"] if s["id"] == "V015"
            for f in s["findings"]]


# ---- AC1: where `agr validate --scene` loses the schedule ----------------------------------------------------

def test_validate_scene_drops_schedule_and_reports_not_run_json(tmp_path, monkeypatch, capsys):
    code, out, calls = run_validate(tmp_path, monkeypatch, capsys, ground_rb(plant()))
    assert len(calls) == 1 and "flora_schedule" not in calls[0]  # the handoff point: keyword never passed
    report = json.loads(out.out)
    rows = v015(report)
    assert rows == [("Flora dimensions", "not_run", f"{GROUND}: no planting schedule supplied")]
    stage = [s for s in report["stages"] if s["id"] == "V015"][0]
    # V015 is a manual_review gate: the not_run row never counts as pass, and manual review stays pending
    assert (stage["gate"], stage["status"]) == ("manual_review", "not_run")
    assert report["passed"] is False and code != 0


def test_validate_scene_text_report_exposes_not_run(tmp_path, monkeypatch, capsys):
    _, out, _ = run_validate(tmp_path, monkeypatch, capsys, ground_rb(plant()), as_json=False)
    line = [ln for ln in out.out.splitlines() if "Flora dimensions" in ln]
    assert len(line) == 1 and "not_run" in line[0] and "no planting schedule supplied" in line[0]


def test_validate_scene_without_flora_has_no_v015_finding(tmp_path, monkeypatch, capsys):
    _, out, _ = run_validate(tmp_path, monkeypatch, capsys, ground_rb())
    assert not [r for r in v015(json.loads(out.out)) if r[0].startswith("Flora dimensions")]


@pytest.mark.parametrize("flag", ["--flora-schedule", "--planting-schedule", "--schedule"])
def test_no_public_schedule_argument(tmp_path, monkeypatch, capsys, flag):
    sched = tmp_path / "schedule.json"
    sched.write_text(json.dumps({PLANT: {"height_m": 3.0, "crown_m": 2.0}}), encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        run_validate(tmp_path, monkeypatch, capsys, ground_rb(plant()), extra=[flag, str(sched)])
    assert exc.value.code == 2  # argparse: unrecognized argument -> unavailable input path


def _calls_to(path: Path, func: str):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", None) == func]


def test_shared_route_source_omits_flora_schedule():
    calls = _calls_to(ROOT / "tools/qa/validate_package.py", "scene_findings")
    assert calls and all("flora_schedule" not in {k.arg for k in c.keywords} and len(c.args) <= 4 for c in calls)


# ---- AC2: the dimension_findings contract with normalized entries ---------------------------------------------

def statuses(found):
    return {f.name: f.status for f in found}


def test_contract_inside_outside_and_missing():
    meshes = [plant("SM_A_Flora", 3.0 * 1.15, 2.0 * 0.85),   # +15 % / -15 %: inside D099
              plant("SM_B_Flora", 3.0 * 1.30, 2.0)]           # +30 % height: outside
    sched = {"SM_A_Flora": {"height_m": 3.0, "crown_m": 2.0}, "SM_B_Flora": {"height_m": 3.0, "crown_m": 2.0},
             "SM_C_Flora": {"height_m": 3.0, "crown_m": 2.0},  # no mesh with that name
             "SM_D_Flora": {"height_m": 3.0}}                  # crown missing in the schedule
    got = statuses(dimension_findings(meshes, sched, "synthetic.fbx"))
    assert got == {"Flora dimensions: SM_A_Flora": "pass", "Flora dimensions: SM_B_Flora": "fail",
                   "Flora dimensions: SM_C_Flora": "review", "Flora dimensions: SM_D_Flora": "review"}
    assert statuses(dimension_findings(meshes, None, "synthetic.fbx")) == {"Flora dimensions": "not_run"}


def test_mesh_without_bounds_is_review_not_invented():
    m = plant()
    del m["bounds_m"]
    assert statuses(dimension_findings([m], {PLANT: {"height_m": 3.0, "crown_m": 2.0}}, "s.fbx")) == {
        f"Flora dimensions: {PLANT}": "review"}


@pytest.mark.parametrize("bad", [None, 0, -1.0, float("nan"), "3.0"])
def test_unusable_schedule_value_is_review(bad):
    got = dimension_findings([plant()], {PLANT: {"height_m": bad, "crown_m": 2.0}}, "s.fbx")
    assert [f.status for f in got] == ["review"]


def test_infinite_schedule_value_fails():
    got = dimension_findings([plant()], {PLANT: {"height_m": float("inf"), "crown_m": 2.0}}, "s.fbx")
    assert [f.status for f in got] == ["fail"]


@pytest.mark.parametrize("factor, expected", [(1.2, "pass"), (0.8, "pass"), (1.2 + 1e-6, "fail"),
                                              (0.8 - 1e-6, "fail")])
def test_d099_boundary_semantics_unchanged(factor, expected):
    """D099 allows +-20 %: exactly 20 % passes (existing EPS semantics), anything beyond fails."""
    got = dimension_findings([plant(height=3.0 * factor)], {PLANT: {"height_m": 3.0, "crown_m": 2.0}}, "s.fbx")
    assert [f.status for f in got] == [expected]


def test_generated_probe_matches_brute_force_tolerance():
    rng = random.Random(1700)
    for _ in range(500):
        h_want, d_want = rng.uniform(0.3, 25.0), rng.uniform(0.2, 15.0)
        fh, fd = rng.uniform(0.5, 1.5), rng.uniform(0.5, 1.5)
        got = dimension_findings([plant(height=h_want * fh, crown=d_want * fd)],
                                 {PLANT: {"height_m": h_want, "crown_m": d_want}}, "s.fbx")
        ok = abs(fh - 1) <= DIM_TOL + 1e-9 and abs(fd - 1) <= DIM_TOL + 1e-9
        assert [f.status for f in got] == ["pass" if ok else "fail"], (h_want, fh, d_want, fd)


def test_schedule_through_scene_findings_changes_not_run_to_pass_and_fail():
    from test_scene import PROFILES
    from twinqa.scene import scene_findings
    rb = ground_rb(plant("SM_A_Flora", 3.0), plant("SM_B_Flora", 4.0))
    sched = {"SM_A_Flora": {"height_m": 3.0, "crown_m": 2.0}, "SM_B_Flora": {"height_m": 3.0, "crown_m": 2.0}}
    npm = PROFILES.profile("npm")
    assert statuses(scene_findings(rb, "npm", "ground", npm)["V015"]) == {"Flora dimensions": "not_run"}
    assert statuses(scene_findings(rb, "npm", "ground", npm, flora_schedule=sched)["V015"]) == {
        "Flora dimensions: SM_A_Flora": "pass", "Flora dimensions: SM_B_Flora": "fail"}


# ---- AC2/AC3: the Vatutino job-local caller and the name tie ----------------------------------------------------

def test_vatutino_caller_passes_normalized_schedule_separately():
    calls = _calls_to(ROOT / "jobs/VATUTINO-SITE/scene_checks.py", "scene_findings")
    assert len(calls) == 1
    kw = {k.arg: k.value for k in calls[0].keywords}
    assert isinstance(kw.get("flora_schedule"), ast.Name) and kw["flora_schedule"].id == "flora"
    # it reads back its own per-instance check FBX, not the delivery FBX (one merged Flora mesh)
    src = (ROOT / "jobs/VATUTINO-SITE/scene_checks.py").read_text(encoding="utf-8")
    assert 'fbx = a.out / "site_instances_check.fbx"' in src and "rb = readback(fbx)" in src
    assert "crown: NOT in the schedule" in src


def test_one_merged_flora_mesh_cannot_tie_per_plant_names():
    """A delivery-style Ground FBX holds all vegetation in one Flora object (FLO-05): per-plant names do not exist."""
    merged = plant(PLANT, 6.0, 30.0)  # bbox of many plants together
    sched = {"Flora_Tree_A__C1": {"height_m": 5.0, "crown_m": 4.0}}
    assert statuses(dimension_findings([merged], sched, "s.fbx")) == {
        "Flora dimensions: Flora_Tree_A__C1": "review",
        f"Flora dimensions: {PLANT}": "not_run"}
    assert all(math.isfinite(v) for v in merged["bounds_m"][1])
