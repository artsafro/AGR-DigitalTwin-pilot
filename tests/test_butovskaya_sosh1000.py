"""Acceptance tests of the #118 step-0 snapshot and the loop's guard (jobs/butovskaya-sosh1000/scripts).

Every Revit call is stubbed: no live Revit access. Rows of the PR's Acceptance table name these tests.
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "jobs" / "butovskaya-sosh1000" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import evaluate as ev  # noqa: E402
import snapshot_revit as sr  # noqa: E402
from twinqa.geometry.mesh import from_dump  # noqa: E402

FT = 0.3048


# ---------------------------------------------------------------- snapshot (step 0)

def mesh_ft(lo, hi):
    """A closed tessellated box in feet, the shape a mesh-capable geometry read returns."""
    v, t = sr.box_mesh(lo, hi)
    return {"vertices": [[c / FT for c in p] for p in v], "triangles": [list(x) for x in t]}


def bbox_ft(lo, hi):
    return {"min": dict(zip("xyz", (c / FT for c in lo))), "max": dict(zip("xyz", (c / FT for c in hi)))}


class FakeRevit:
    """geometry: element id -> response dict, or an Exception to raise."""

    def __init__(self, geometry, ids=None, levels=None):
        self.geometry = geometry
        self.ids = list(geometry) if ids is None else ids
        self.levels = [{"name": "L0", "elevationMeters": 0.0}] if levels is None else levels
        self.calls = []

    def call(self, cmd, params=None, **kw):
        self.calls.append(cmd)
        if cmd == "get_document_info":
            return {"name": "SYNTHETIC"}
        if cmd == "list_levels":
            return {"levels": self.levels}
        if cmd == "get_element_geometry":
            g = self.geometry[params["id"]]
            if isinstance(g, Exception):
                raise g
            return g
        raise AssertionError(cmd)


@pytest.fixture
def run_snapshot(monkeypatch, tmp_path):
    def run(fake, out=None):
        out = out or tmp_path / "snapshot"
        monkeypatch.setattr(sr, "CATEGORIES", ["OST_Walls"])
        monkeypatch.setattr(sr, "listing", lambda cat: [{"id": i} for i in fake.ids])
        monkeypatch.setattr(sr, "call", fake.call)
        monkeypatch.setattr(sys, "argv", ["snapshot_revit.py", "--out", str(out)])
        sr.main()
        return out
    return run


def assert_blocked(out: Path, reason: str) -> dict:
    assert not (out / "snapshot_dump.json").exists()
    assert not (out / "hashes.json").exists()
    assert not (out / "elements.json").exists()
    rep = json.loads((out / "blocked.json").read_text(encoding="utf-8"))
    assert rep["reason"] == reason
    assert rep["complete"] is False
    for key in ("elements_done", "elements_listed", "seconds", "elements_per_s", "failed"):
        assert key in rep
    return rep


def test_snapshot_valid_mesh_writes_complete_mesh_reference(run_snapshot):
    fake = FakeRevit({1: {"mesh": mesh_ft([0, 0, 0], [2, 3, 4]), "boundingBox": bbox_ft([0, 0, 0], [2, 3, 4])}})
    out = run_snapshot(fake)
    h = json.loads((out / "hashes.json").read_text(encoding="utf-8"))
    assert h["reference"] == "mesh" and h["complete"] is True and h["failed"] == 0
    assert h["counts"] == {"OST_Walls": 1}
    for name, digest in h["sha256"].items():
        assert hashlib.sha256((out / name).read_bytes()).hexdigest() == digest
    dump = json.loads((out / "snapshot_dump.json").read_text(encoding="utf-8"))
    soup = from_dump(dump)
    assert len(soup.triangles) == 12
    assert soup.levels == {"L0": 0.0}
    row = json.loads((out / "elements.json").read_text(encoding="utf-8"))["elements"][0]
    assert row["box"] == [[0.0, 0.0, 0.0], [2.0, 3.0, 4.0]]
    assert not (out / "blocked.json").exists()


def test_snapshot_bbox_only_response_blocks(run_snapshot):
    """R1: review round 1, P1-1 input A."""
    fake = FakeRevit({1: {"boundingBox": bbox_ft([0, 0, 0], [3, 3, 3])}})
    with pytest.raises(SystemExit) as e:
        run_snapshot(fake)
    assert e.value.code == 2
    rep = assert_blocked(fake_out(e), "unsupported_export")
    assert rep["elements_done"] == 0 and rep["elements_listed"] == 1


def test_snapshot_geometry_error_blocks(run_snapshot):
    """R2: review round 1, P1-1 input B."""
    fake = FakeRevit({1: RuntimeError("SYNTHETIC blocked geometry export")})
    with pytest.raises(SystemExit) as e:
        run_snapshot(fake)
    assert e.value.code == 2
    rep = assert_blocked(fake_out(e), "geometry_failed")
    assert rep["failed"][0]["id"] == 1 and "SYNTHETIC" in rep["failed"][0]["error"]


def test_snapshot_partial_failure_blocks(run_snapshot):
    ok = {"mesh": mesh_ft([0, 0, 0], [1, 1, 1])}
    fake = FakeRevit({1: ok, 2: RuntimeError("SYNTHETIC timeout"), 3: ok})
    with pytest.raises(SystemExit) as e:
        run_snapshot(fake)
    assert e.value.code == 2
    rep = assert_blocked(fake_out(e), "geometry_failed")
    assert rep["elements_done"] == 1 and rep["elements_listed"] == 3


def test_snapshot_malformed_mesh_blocks(run_snapshot):
    bad = mesh_ft([0, 0, 0], [1, 1, 1])
    bad["triangles"][0] = [0, 1, 99]
    with pytest.raises(SystemExit) as e:
        run_snapshot(FakeRevit({1: {"mesh": bad}}))
    assert e.value.code == 2
    assert_blocked(fake_out(e), "unsupported_export")


def test_snapshot_empty_listing_blocks(run_snapshot):
    with pytest.raises(SystemExit) as e:
        run_snapshot(FakeRevit({}, ids=[]))
    assert e.value.code == 2
    assert_blocked(fake_out(e), "no_elements")


def test_snapshot_no_levels_blocks(run_snapshot):
    with pytest.raises(SystemExit) as e:
        run_snapshot(FakeRevit({1: {"mesh": mesh_ft([0, 0, 0], [1, 1, 1])}}, levels=[]))
    assert e.value.code == 2
    assert_blocked(fake_out(e), "no_levels")


def test_snapshot_repeat_refused_before_any_call(run_snapshot, tmp_path):
    out = tmp_path / "snapshot"
    out.mkdir()
    (out / "hashes.json").write_text("{\"old\": true}", encoding="utf-8")
    fake = FakeRevit({1: {"mesh": mesh_ft([0, 0, 0], [1, 1, 1])}})
    with pytest.raises(SystemExit) as e:
        run_snapshot(fake, out)
    assert e.value.code == 2
    assert fake.calls == []
    assert (out / "hashes.json").read_text(encoding="utf-8") == "{\"old\": true}"


def test_snapshot_published_iff_every_element_has_mesh(monkeypatch, tmp_path):
    """Generated probe: 300 random element sequences (valid mesh / bbox-only / call error / malformed mesh,
    0-6 elements, with or without levels). A snapshot (hashes.json) is published iff the listing is non-empty,
    levels exist and every answer is a valid mesh; otherwise exit 2, blocked.json and no snapshot file."""
    import random
    rnd = random.Random(118)
    kinds = ["mesh", "mesh", "bbox", "error", "malformed"]
    monkeypatch.setattr(sr, "CATEGORIES", ["OST_Walls"])
    checked = 0
    for k in range(300):
        seq = [rnd.choice(kinds) for _ in range(rnd.randint(0, 6))]
        has_levels = rnd.random() > 0.1
        geo = {}
        for i, kind in enumerate(seq, 1):
            m = mesh_ft([i, 0, 0], [i + 1, 1, 1])
            if kind == "malformed":
                m["triangles"][3] = [0, 1]
            geo[i] = ({"mesh": m} if kind in ("mesh", "malformed") else
                      {"boundingBox": bbox_ft([i, 0, 0], [i + 1, 1, 1])} if kind == "bbox" else
                      RuntimeError("SYNTHETIC"))
        fake = FakeRevit(geo, levels=None if has_levels else [])
        out = tmp_path / f"s{k}"
        monkeypatch.setattr(sr, "listing", lambda cat, ids=list(geo): [{"id": i} for i in ids])
        monkeypatch.setattr(sr, "call", fake.call)
        monkeypatch.setattr(sys, "argv", ["snapshot_revit.py", "--out", str(out)])
        expect = bool(seq) and has_levels and all(s == "mesh" for s in seq)
        if expect:
            sr.main()
            h = json.loads((out / "hashes.json").read_text(encoding="utf-8"))
            assert h["counts"] == {"OST_Walls": len(seq)} and not (out / "blocked.json").exists()
        else:
            with pytest.raises(SystemExit) as e:
                sr.main()
            assert e.value.code == 2
            assert not any((out / n).exists() for n in ("hashes.json", "snapshot_dump.json", "elements.json"))
            assert (out / "blocked.json").exists()
        assert not out.with_name(out.name + ".partial").exists()
        checked += 1
    assert checked == 300


def fake_out(excinfo) -> Path:
    """The --out of the run (sys.argv is still patched inside the test)."""
    return Path(sys.argv[sys.argv.index("--out") + 1])


# ---------------------------------------------------------------- reference acceptance (evaluate)

def write_reference(run_snapshot, boxes):
    fake = FakeRevit({i + 1: {"mesh": mesh_ft(lo, hi)} for i, (lo, hi) in enumerate(boxes)})
    return run_snapshot(fake)


def test_evaluate_accepts_complete_mesh_reference_metric_zero(run_snapshot):
    snap = write_reference(run_snapshot, [([0, 0, 0], [2, 2, 2])])
    assert ev.require_mesh_reference(snap)["reference"] == "mesh"
    sil = ev.etalon_silhouettes(snap)
    model = from_dump(json.loads((snap / "snapshot_dump.json").read_text(encoding="utf-8")))
    assert ev.metric(model, sil)["silhouette_err_m2"] == 0.0


def test_evaluate_refuses_box_reference(tmp_path):
    snap = tmp_path / "box"
    snap.mkdir()
    for name in ("elements.json", "levels.json", "snapshot_dump.json"):
        (snap / name).write_text("{}", encoding="utf-8")
    sha = {n: hashlib.sha256((snap / n).read_bytes()).hexdigest() for n in ("elements.json", "levels.json", "snapshot_dump.json")}
    (snap / "hashes.json").write_text(json.dumps({"counts": {}, "failed": 0, "sha256": sha}), encoding="utf-8")
    with pytest.raises(SystemExit):
        ev.require_mesh_reference(snap)


def test_evaluate_refuses_blocked_or_missing_reference(tmp_path):
    snap = tmp_path / "blocked"
    snap.mkdir()
    (snap / "blocked.json").write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit):
        ev.require_mesh_reference(snap)


def test_evaluate_refuses_hash_mismatch(run_snapshot):
    snap = write_reference(run_snapshot, [([0, 0, 0], [2, 2, 2])])
    (snap / "snapshot_dump.json").write_text("{\"meshes\": []}", encoding="utf-8")
    with pytest.raises(SystemExit):
        ev.require_mesh_reference(snap)


# ---------------------------------------------------------------- guard

def model(level_z=0.0, helpers=True):
    v, t = sr.box_mesh([0, 0, 0], [2, 2, 2])
    return {"meshes": [{"name": "body", "vertices": v, "triangles": [list(x) for x in t],
                        "material_ids": [1] * 12, "polygon_sizes": [3] * 12}],
            "helpers": [{"name": "LEVEL_L0", "location": [0, 0, level_z]}] if helpers else []}


@pytest.fixture
def levels_snap(tmp_path):
    snap = tmp_path / "levels"
    snap.mkdir()
    (snap / "levels.json").write_text(json.dumps([{"name": "L0", "elevationMeters": 0.0}]), encoding="utf-8")
    return snap


@pytest.mark.parametrize("case,passed", [
    ("closed", True), ("open", False), ("flipped", False), ("broken_decor", False),
    ("missing_level", False), ("level_at_tol", True), ("level_over_tol", False)])
def test_guard_cases(case, passed, levels_snap):
    d = model()
    if case == "open":
        for key in ("triangles", "material_ids", "polygon_sizes"):
            d["meshes"][0][key].pop()
    if case == "flipped":
        d["meshes"][0]["triangles"][0] = d["meshes"][0]["triangles"][0][::-1]
    if case == "broken_decor":
        d["meshes"].append({"name": "facade_decor", "vertices": [[10, 0, 0], [11, 0, 0], [10, 1, 1]],
                            "triangles": [[0, 1, 2]], "material_ids": [26], "polygon_sizes": [3]})
    if case == "missing_level":
        d = model(helpers=False)
    if case == "level_at_tol":
        d = model(level_z=0.02)
    if case == "level_over_tol":
        d = model(level_z=0.0201)
    r = ev.guard(from_dump(d), levels_snap)
    assert r["guard_passed"] is passed
    assert r["delivery_passed"] is False


def tetra_dump(n_tetra, extra_triangle=False):
    verts, tris = [], []
    side = int(n_tetra ** 0.5) + 1
    for k in range(n_tetra):
        x, y = (k % side) * 2.0, (k // side) * 2.0
        b = len(verts)
        verts += [[x, y, 0], [x + 1, y, 0], [x, y + 1, 0], [x, y, 1]]
        tris += [[b, b + 2, b + 1], [b, b + 1, b + 3], [b + 1, b + 2, b + 3], [b, b + 3, b + 2]]
    if extra_triangle:
        b = len(verts)
        verts += [[-5, -5, 0], [-4, -5, 0], [-5, -4, 0]]
        tris.append([b, b + 1, b + 2])
    return {"meshes": [{"name": "body", "vertices": verts, "triangles": tris, "material_ids": [1] * len(tris),
                        "polygon_sizes": [3] * len(tris)}],
            "helpers": [{"name": "LEVEL_L0", "location": [0, 0, 0]}]}


@pytest.mark.parametrize("extra,status", [(False, "pass"), (True, "fail")])
def test_guard_triangle_budget_boundary(extra, status, levels_snap, monkeypatch):
    """150 000 triangles pass, 150 001 fail (check_budget, triangles_max of bench-b01-box).

    The topology checks are stubbed to "pass" here only to keep the test fast (check_mesh on 150 000 triangles
    takes minutes); they are exercised unstubbed by test_guard_cases. The budget check itself is the real one."""
    import numpy as np
    monkeypatch.setattr(ev, "check_mesh", lambda *a: {"status": "pass", "value": {}, "details": {}})
    monkeypatch.setattr(ev, "winding_bad_edges", lambda m, w: np.zeros(len(m.mesh_names), int))
    r = ev.guard(from_dump(tetra_dump(37500, extra)), levels_snap)
    assert r["triangles"] == 150000 + int(extra)
    assert r["budget_status"] == status
    assert r["guard_passed"] is (status == "pass")
    assert r["delivery_passed"] is False


def test_guard_budget_limit_is_150000():
    tol = json.loads(ev.TOL_FILE.read_text(encoding="utf-8"))["geometry"]
    assert tol["triangles_max"] == 150000
