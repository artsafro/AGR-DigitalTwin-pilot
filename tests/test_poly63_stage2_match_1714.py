"""#1714: one POLY63 stage-2 window-type matcher (`claim_openings` in the 63A stage2_plan.py) for 63A and 63C.

Shared negative fixture: the same synthetic wall + Revit window; an unresolved window type must stop BEFORE any
plan is written, for both towers (the #1676/#1695 stop logic). Synthetic geometry only.

Pattern: n/a | new-case: shared negative fixture of the POLY63 stage-2 opening -> window-type matcher.
"""

import ast
import csv
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOKS_A = ROOT / "jobs" / "POLY63-A" / "stage2-1619" / "hooks"
HOOK_C = ROOT / "jobs" / "POLY63-C" / "hooks" / "stage2_63c.py"
sys.path.insert(0, str(Path(__file__).resolve().parent))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fx = _load(Path(__file__).resolve().parent / "test_poly63a_stage2_1619.py", "poly63a_fixture_1714")
s2 = fx.s2
c63 = _load(HOOK_C, "stage2_63c_1714")
NAME = "Окн_Окн_1 Ств Комфорт Комфорт ОК-10-19"


def _window_with_jamb():
    """The 63A fixture window plus the continuous outer jamb the 63C depth measure reads (68 mm)."""
    x, z, y, w, h, fd = fx.X0, fx.Z0, fx.REVEAL, fx.W, fx.H, fx.FD
    jamb = []
    for (a, b) in (((x, z), (x, z + h)), ((x + w, z), (x + w, z + h)), ((x, z), (x + w, z)), ((x, z + h), (x + w, z + h))):
        p, q = (a[0], y, a[1]), (b[0], y, b[1])
        pb, qb = (a[0], y + fd, a[1]), (b[0], y + fd, b[1])
        jamb += [[p, q, qb], [p, qb, pb], [q, qb, pb], [q, pb, p]]   # both diagonals: no PCA tilt
    return np.concatenate([fx._window_tris(), np.array(jamb, float)])


def _inputs(tmp, shift=0.0, name=NAME, sill_shift=0.0):
    """Body (one opening), Revit crop, 63C registry/floor; `shift` moves the body opening along x."""
    verts, fn, fi = fx._body()
    verts[:, 0] += shift
    np.savez(tmp / "body.npz", verts=verts, fn=fn, fi=fi)
    tri = _window_with_jamb()
    crop_name = "Окн_Окн_1 Ств Комфорт_abc"
    np.savez(tmp / "crop.npz", tri=tri, obj=np.zeros(len(tri), np.int32), mat=np.zeros(len(tri), np.int32),
             names=np.array([crop_name]), mats=np.array([""]))
    centre = tri.reshape(-1, 3).mean(0)
    with (tmp / "types.csv").open("w", encoding="utf-8", newline="") as f:
        wr = csv.DictWriter(f, ["sill_m", "module_opening_1based", "fbx_model", "ref_centroid_x", "ref_centroid_y"])
        wr.writeheader()
        wr.writerow({"sill_m": fx.Z0 + sill_shift, "module_opening_1based": 1, "fbx_model": name + " [22038485]",
                     "ref_centroid_x": centre[0], "ref_centroid_y": centre[1]})
    (tmp / "floor.json").write_text(json.dumps({"opening_sources": [crop_name]}), encoding="utf-8")
    return tmp


def _run(tower, tmp, monkeypatch):
    out = tmp / "plan.json"
    if tower == "63A":
        return out, lambda: s2.main([str(tmp / "body.npz"), str(tmp / "crop.npz"), str(out), "--band", "0", "3.15"])
    monkeypatch.setattr(c63, "OPENINGS", 1)
    std = ROOT / "library" / "windows" / "standard.json"
    return out, lambda: c63.build(str(HOOKS_A), str(tmp / "body.npz"), str(tmp / "crop.npz"), str(tmp / "types.csv"),
                                  str(tmp / "floor.json"), str(std), str(out))


@pytest.mark.parametrize("tower", ["63A", "63C"])
def test_positive_control_writes_one_window(tmp_path, monkeypatch, tower):
    out, run = _run(tower, _inputs(tmp_path), monkeypatch)
    run()
    rows = json.loads(out.read_text(encoding="utf-8"))["report"]["rows"]
    assert [r["opening"] for r in rows] == [1]


@pytest.mark.parametrize("tower", ["63A", "63C"])
@pytest.mark.parametrize("shift", [1.0, -1.0, 0.9])
def test_unresolved_window_type_stops_before_writing(tmp_path, monkeypatch, tower, shift):
    """Shared negative fixture (#1714): the same moved opening is unresolved for both towers."""
    out, run = _run(tower, _inputs(tmp_path, shift=shift), monkeypatch)
    monkeypatch.setattr(s2.windowgen_core, "build_type", lambda *a: pytest.fail("geometry built before preflight"))
    with pytest.raises(SystemExit) as exc:
        run()
    text = str(exc.value)
    assert "Stage 2 STOP" in text and "opening 1" in text and "unused" in text
    assert not out.exists()


@pytest.mark.parametrize("case", ["name", "sill", "name+sill"])
def test_63c_unresolved_registry_stops_before_writing(tmp_path, monkeypatch, case):
    kw = {"name": "Окн_Окн_1 Ств без типа" if "name" in case else NAME, "sill_shift": 0.01 if "sill" in case else 0}
    out, run = _run("63C", _inputs(tmp_path, **kw), monkeypatch)
    with pytest.raises(SystemExit) as exc:
        run()
    text = str(exc.value)
    assert "Stage 2 STOP" in text
    if case == "sill":
        assert "opening 1" in text and "no registry row" in text
    if case == "name":
        assert "Unresolved Revit family/type" in text and "instance 22038485" in text
    if case == "name+sill":   # the name of an unclaimed row is never reached: the opening is the blocker
        assert "no registry row" in text and "unused" in text
    assert not out.exists()


def _sources(row):
    return [{"name": n} for n in row]


def test_claim_openings_one_owner_per_source_and_all_problems_listed():
    ops = [{"id": k, "status": "ok", "why": [], "border": [[k, 0, 0], [k + 1, 0, 0], [k + 1, 0, 1]]} for k in (1, 2, 3)]
    picks = {1: (0, None), 2: (0, None), 3: (None, "no candidate")}
    with pytest.raises(SystemExit) as exc:
        s2.claim_openings(ops, 2, lambda o, c: picks[o["id"]], lambda j: f"source #{j + 1}")
    text = str(exc.value)
    for part in ("opening 1 ", "opening 2 ", "opening 3 ", "no candidate", "source #1: matched more than once",
                 "source #2: unused"):
        assert part in text
    got = s2.claim_openings(ops[:2], 2, lambda o, c: (o["id"] - 1, o["id"] * 10), lambda j: str(j))
    assert [(o["id"], j, info) for o, j, info in got] == [(1, 0, 10), (2, 1, 20)]


@pytest.mark.parametrize("bad", ["empty", "nan", "status", "none"])
def test_claim_openings_fail_closed(bad):
    op = {"id": 1, "status": "ok", "why": [], "border": [[0, 0, 0], [1, 0, 0], [1, 0, 1]]}
    if bad == "empty":
        op["border"] = []
    if bad == "nan":
        op["border"][0][0] = float("nan")
    if bad == "status":
        op.update(status="ambiguous", why=["nonrect"])
    with pytest.raises(SystemExit, match="STOP"):
        s2.claim_openings([] if bad == "none" else [op], 1, lambda o, c: (0, None), str)


def test_check_claimed_problem_stops():
    op = {"id": 1, "status": "ok", "why": [], "border": [[0, 0, 0], [1, 0, 0], [1, 0, 1]]}
    with pytest.raises(SystemExit, match="bad type"):
        s2.claim_openings([op], 1, lambda o, c: (0, None), str, check_claimed=lambda j, owners: "bad type")


def test_63c_hook_has_no_own_matcher():
    """63C calls the 63A owner: no own candidate loop, no own claim/stop definitions."""
    tree = ast.parse(HOOK_C.read_text(encoding="utf-8"))
    assert "claim_openings" in {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    defs = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert not defs & {"claim_openings", "match_openings", "stop", "registry_types"}


def test_duplicate_guard_one_owner_for_the_matcher():
    sys.path.insert(0, str(ROOT))
    from tools.architecture import duplicate_guard as dg
    rule = "poly63-window-match"
    assert dg.RULES[rule] == "jobs/POLY63-A/stage2-1619/hooks/stage2_plan.py"
    copy = "def claim_openings(o, s, p, l):\n    return []\n\ndef match_openings(o, w):\n    return []\n"
    assert [f.rule for f in dg.scan_text(copy, "jobs/POLY63-B/stage2/hooks/plan.py")].count(rule) == 2
    assert [f for f in dg.scan_text(copy, dg.RULES[rule]) if f.rule == rule] == []
    owner = (ROOT / dg.RULES[rule]).read_text(encoding="utf-8")
    assert [f.rule for f in dg.scan_text(owner, "jobs/POLY63-C/hooks/x.py")].count(rule) == 2
    hook = HOOK_C.read_text(encoding="utf-8")
    assert [f for f in dg.scan_text(hook, "jobs/POLY63-C/hooks/stage2_63c.py") if f.rule == rule] == []
