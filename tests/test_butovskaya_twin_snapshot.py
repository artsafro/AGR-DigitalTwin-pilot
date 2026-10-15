"""Acceptance tests of the #118 step-0 mesh route (jobs/butovskaya-sosh1000/scripts/snapshot_twin.py).

Synthetic TwinPack exports only (no live Revit). Rows of the PR's Acceptance table (round 3) name these tests.
"""
import hashlib
import json
import random
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "jobs" / "butovskaya-sosh1000" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import evaluate as ev  # noqa: E402
import snapshot_twin as st  # noqa: E402
from twinqa.geometry.mesh import from_dump  # noqa: E402

QUADS = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]


def box_obj(name, lo, hi, base):
    """OBJ lines of a closed outward box, 1-based indices starting after `base` vertices."""
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    lines = [f"o {name}", "usemtl m1"] + [f"v {x} {y} {z}" for x, y, z in v]
    for a, b, c, d in QUADS:
        for t in ((a, b, c), (a, c, d)):
            lines.append("f " + " ".join(str(base + i + 1) for i in t))
    return lines


def make_export(root: Path, bands=None, twin=None):
    """A synthetic TwinPack export: band n holds box objects; returns root."""
    bands = bands if bands is not None else {1: [("wall_10", [0, 0, 0], [4, 1, 3]), ("window_11", [1, -0.1, 1], [2, 0, 2])],
                                              2: [("wall_10", [0, 0, 3], [4, 1, 6]), ("roof_12", [0, 0, 6], [4, 1, 6.3])]}
    root.mkdir(parents=True)
    index = []
    for n, objs in bands.items():
        d = root / f"band-{n}"
        d.mkdir()
        lines, base = ["# synthetic", "mtllib reference.mtl"], 0
        for name, lo, hi in objs:
            lines += box_obj(name, lo, hi, base)
            base += 8
        (d / "reference.obj").write_text("\n".join(lines) + "\n", encoding="utf-8")
        recs = [{"id": int(nm.split("_")[1]), "kind": nm.split("_")[0], "type": f"T{nm}", "function": "Exterior"}
                for nm, _, _ in objs]
        (d / "floor.json").write_text(json.dumps({"schema": "twin-floor/1", "mesh": {"triangles": 12 * len(objs),
                                                                                    "clipFallbacks": 0},
                                                  "walls": recs}), encoding="utf-8")
        index.append({"band": n, "dir": f"band-{n}"})
    data = {"kind": "revit-twin", "document": "SYNTHETIC", "modified_before": False, "modified_after": False,
            "bands": index, "revit_levels": [{"id": 1, "name": "L0", "elevation_m": 0.0},
                                             {"id": 2, "name": "L1", "elevation_m": 3.0}]}
    data.update(twin or {})
    (root / "twin-data.json").write_text(json.dumps(data), encoding="utf-8")
    return root


def run(src, out):
    st.main(["--src", str(src), "--out", str(out)])
    return out


def run_blocked(src, out, reason):
    with pytest.raises(SystemExit) as e:
        run(src, out)
    assert e.value.code == st.BLOCKED_EXIT
    for name in ("snapshot_dump.json", "hashes.json", "elements.json", "levels.json"):
        assert not (out / name).exists(), name
    rep = json.loads((out / "blocked.json").read_text(encoding="utf-8"))
    assert rep["complete"] is False and rep["reason"] == reason
    return rep


def test_twin_valid_export_writes_complete_mesh_reference(tmp_path):
    out = run(make_export(tmp_path / "src"), tmp_path / "snap")
    h = json.loads((out / "hashes.json").read_text(encoding="utf-8"))
    assert h["reference"] == "mesh" and h["complete"] is True and h["failed"] == 0 and h["route"] == "twinpack"
    assert h["counts"] == {"OST_Walls": 2, "OST_Windows": 1, "OST_Roofs": 1}
    assert h["elements"] == {"OST_Walls": 1, "OST_Windows": 1, "OST_Roofs": 1}
    assert h["triangles_total"] == 48 and h["bands"] == 2
    for name, digest in h["sha256"].items():
        assert hashlib.sha256((out / name).read_bytes()).hexdigest() == digest
    assert set(h["source_sha256"]) == {"twin-data.json", "band-1/reference.obj", "band-1/floor.json",
                                       "band-2/reference.obj", "band-2/floor.json"}
    rows = json.loads((out / "elements.json").read_text(encoding="utf-8"))["elements"]
    w = rows[0]
    assert w["name"] == "band-1/wall_10" and w["band"] == 1 and w["category"] == "OST_Walls"
    assert w["box"] == [[0.0, 0.0, 0.0], [4.0, 1.0, 3.0]] and w["type"] == "Twall_10" and w["function"] == "Exterior"
    soup = from_dump(json.loads((out / "snapshot_dump.json").read_text(encoding="utf-8")))
    assert len(soup.triangles) == 48 and soup.levels == {"L0": 0.0, "L1": 3.0}
    assert not (out / "blocked.json").exists()


def test_twin_reference_accepted_by_evaluate_metric_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(ev, "ZONE", ((-100.0, -100.0), (100.0, 100.0)))
    out = run(make_export(tmp_path / "src"), tmp_path / "snap")
    assert ev.require_mesh_reference(out)["reference"] == "mesh"
    sil = ev.etalon_silhouettes(out)
    model = from_dump(json.loads((out / "snapshot_dump.json").read_text(encoding="utf-8")))
    m = ev.metric(model, sil)
    assert m["silhouette_err_m2"] == 0.0
    assert sil["y"].area == pytest.approx(4 * 6.3)


def test_twin_reference_metric_sees_a_missing_piece(tmp_path, monkeypatch):
    monkeypatch.setattr(ev, "ZONE", ((-100.0, -100.0), (100.0, 100.0)))
    out = run(make_export(tmp_path / "src"), tmp_path / "snap")
    dump = json.loads((out / "snapshot_dump.json").read_text(encoding="utf-8"))
    dump["meshes"] = [m for m in dump["meshes"] if m["name"] != "band-2/roof_12"]
    err = ev.metric(from_dump(dump), ev.etalon_silhouettes(out))
    assert err["per_view_m2"]["y"] == pytest.approx(4 * 0.3, abs=1e-3)       # the roof's 4 x 0.3 m strip


def test_twin_no_export_blocks(tmp_path):
    run_blocked(tmp_path / "missing", tmp_path / "snap", "no_export")


@pytest.mark.parametrize("before,after", [(False, True), (True, False), (None, False), (False, None)])
def test_twin_modified_document_blocks(tmp_path, before, after):
    src = make_export(tmp_path / "src", twin={"modified_before": before, "modified_after": after})
    run_blocked(src, tmp_path / "snap", "document_modified")


def test_twin_no_levels_blocks(tmp_path):
    run_blocked(make_export(tmp_path / "src", twin={"revit_levels": []}), tmp_path / "snap", "no_levels")


def test_twin_no_bands_blocks(tmp_path):
    run_blocked(make_export(tmp_path / "src", twin={"bands": []}), tmp_path / "snap", "no_bands")


def test_twin_missing_band_obj_blocks(tmp_path):
    src = make_export(tmp_path / "src")
    (src / "band-2" / "reference.obj").unlink()
    run_blocked(src, tmp_path / "snap", "band_incomplete")


def test_twin_truncated_obj_blocks(tmp_path):
    """A partial OBJ (last triangles cut off) disagrees with floor.json's triangle count."""
    src = make_export(tmp_path / "src")
    p = src / "band-1" / "reference.obj"
    p.write_text("\n".join(p.read_text(encoding="utf-8").splitlines()[:-2]) + "\n", encoding="utf-8")
    run_blocked(src, tmp_path / "snap", "band_incomplete")


@pytest.mark.parametrize("bad", ["f 1 2 3 4", "f 1 2 999", "f 0 1 2", "f a b c"])
def test_twin_malformed_face_blocks(tmp_path, bad):
    src = make_export(tmp_path / "src")
    p = src / "band-1" / "reference.obj"
    p.write_text(p.read_text(encoding="utf-8") + bad + "\n", encoding="utf-8")
    run_blocked(src, tmp_path / "snap", "malformed_obj")


def test_twin_face_before_object_blocks(tmp_path):
    src = make_export(tmp_path / "src")
    p = src / "band-1" / "reference.obj"
    p.write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n" + p.read_text(encoding="utf-8"), encoding="utf-8")
    run_blocked(src, tmp_path / "snap", "malformed_obj")


def test_twin_object_without_triangles_blocks(tmp_path):
    src = make_export(tmp_path / "src")
    p = src / "band-2" / "reference.obj"
    p.write_text(p.read_text(encoding="utf-8") + "o cornice_99\n", encoding="utf-8")
    run_blocked(src, tmp_path / "snap", "empty_object")


def test_twin_clip_fallback_blocks(tmp_path):
    src = make_export(tmp_path / "src")
    f = src / "band-1" / "floor.json"
    d = json.loads(f.read_text(encoding="utf-8"))
    d["mesh"]["clipFallbacks"] = 1
    f.write_text(json.dumps(d), encoding="utf-8")
    run_blocked(src, tmp_path / "snap", "clip_fallback")


def test_twin_repeat_refused_and_snapshot_unchanged(tmp_path):
    src = make_export(tmp_path / "src")
    out = run(src, tmp_path / "snap")
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    (src / "twin-data.json").unlink()                     # even a broken source is not read: refused first
    with pytest.raises(SystemExit) as e:
        run(src, out)
    assert e.value.code == st.BLOCKED_EXIT
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before


def test_twin_success_after_blocked_clears_report(tmp_path):
    out = tmp_path / "snap"
    run_blocked(tmp_path / "missing", out, "no_export")
    run(make_export(tmp_path / "src"), out)
    assert (out / "hashes.json").exists() and not (out / "blocked.json").exists()
    assert not (tmp_path / "snap.partial").exists()


def test_twin_export_refuses_existing_folder(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(st.subprocess, "run", lambda *a, **k: called.append(a))
    src = make_export(tmp_path / "src")
    with pytest.raises(SystemExit):
        st.export(src)
    assert called == []


CORRUPTIONS = ["none", "modified_after", "drop_obj", "truncate", "quad", "oob", "empty_object", "clip", "no_levels"]


def corrupt(src: Path, kind: str):
    obj = src / "band-1" / "reference.obj"
    if kind == "modified_after":
        d = json.loads((src / "twin-data.json").read_text(encoding="utf-8"))
        d["modified_after"] = True
        (src / "twin-data.json").write_text(json.dumps(d), encoding="utf-8")
    elif kind == "no_levels":
        d = json.loads((src / "twin-data.json").read_text(encoding="utf-8"))
        d["revit_levels"] = []
        (src / "twin-data.json").write_text(json.dumps(d), encoding="utf-8")
    elif kind == "drop_obj":
        obj.unlink()
    elif kind == "truncate":
        obj.write_text("\n".join(obj.read_text(encoding="utf-8").splitlines()[:-1]) + "\n", encoding="utf-8")
    elif kind == "quad":
        obj.write_text(obj.read_text(encoding="utf-8") + "f 1 2 3 4\n", encoding="utf-8")
    elif kind == "oob":
        obj.write_text(obj.read_text(encoding="utf-8") + "f 1 2 10000\n", encoding="utf-8")
    elif kind == "empty_object":
        obj.write_text(obj.read_text(encoding="utf-8") + "o wall_77\n", encoding="utf-8")
    elif kind == "clip":
        f = src / "band-1" / "floor.json"
        d = json.loads(f.read_text(encoding="utf-8"))
        d["mesh"]["clipFallbacks"] = 2
        f.write_text(json.dumps(d), encoding="utf-8")


def test_twin_published_iff_export_valid_generated(tmp_path):
    """Generated probe: 60 random exports (1-3 bands, 1-4 boxes each) x a random corruption; the snapshot is
    published exactly when nothing was corrupted, and then its hashes match and its triangles are 12 per box."""
    rng = random.Random(118)
    for k in range(60):
        bands = {}
        for n in range(1, rng.randint(1, 3) + 1):
            objs = []
            for j in range(rng.randint(1, 4)):
                x, y = rng.uniform(-10, 10), rng.uniform(-10, 10)
                kind = rng.choice(["wall", "panel", "mullion", "window", "door", "roof", "floor", "cornice"])
                objs.append((f"{kind}_{100 * n + j}", [x, y, 3 * (n - 1)], [x + rng.uniform(0.1, 3),
                                                                            y + rng.uniform(0.1, 3), 3 * n]))
            bands[n] = objs
        src = make_export(tmp_path / f"src{k}", bands=bands)
        kind = rng.choice(CORRUPTIONS)
        corrupt(src, kind)
        out = tmp_path / f"snap{k}"
        if kind == "none":
            run(src, out)
            h = json.loads((out / "hashes.json").read_text(encoding="utf-8"))
            assert h["triangles_total"] == 12 * sum(len(o) for o in bands.values())
            assert all(hashlib.sha256((out / n).read_bytes()).hexdigest() == d for n, d in h["sha256"].items())
        else:
            with pytest.raises(SystemExit):
                run(src, out)
            assert not (out / "hashes.json").exists() and not (out / "snapshot_dump.json").exists(), kind
            assert (out / "blocked.json").exists()


# ---------------------------------------------------------------- loop step (keep rule)

import loop_step as ls  # noqa: E402


@pytest.fixture
def loop(tmp_path, monkeypatch):
    """loop_step.main with a prebuilt dump, metric and guard stubbed; returns run(err, guard_ok, *flags) -> row."""
    monkeypatch.setattr(ls, "RESULTS", tmp_path / "results.json")
    monkeypatch.setattr(ls, "OUT", tmp_path)
    dump = tmp_path / "pre.json"
    dump.write_text(json.dumps({"meshes": [], "helpers": []}), encoding="utf-8")
    monkeypatch.setattr(ls, "from_dump", lambda d: object())
    monkeypatch.setattr(ls.ev, "etalon_silhouettes", lambda snap: {})
    calls = []

    def run(err, guard_ok, *flags):
        monkeypatch.setattr(ls.ev, "metric", lambda m, s: {"silhouette_err_m2": err, "per_view_m2": {}, "iou": {}})

        def guard(m, snap):
            calls.append(err)
            return {"guard_passed": guard_ok, "delivery_passed": False, "mesh": {"status": "pass", "value": {}},
                    "mesh_per_mesh": {}, "winding_bad_edges": {"body": 0}, "triangles": 12, "budget_status": "pass",
                    "levels": {"status": "pass", "worst_m": 0.0}}
        monkeypatch.setattr(ls.ev, "guard", guard)
        n = str(len(calls) + 100 + len(json.loads(ls.RESULTS.read_text())) if ls.RESULTS.exists() else 100)
        monkeypatch.setattr(sys, "argv", ["loop_step.py", "--n", n, "--desc", "t", "--prebuilt", str(dump),
                                          "--prebuilt-info", '{"triangles": 12}', *flags])
        ls.main()
        return json.loads(ls.RESULTS.read_text(encoding="utf-8"))[-1]
    run.calls = calls
    return run


def test_loop_keep_rule(loop):
    assert loop(100.0, True, "--baseline")["status"] == "baseline"
    better_fail = loop(90.0, False)
    assert better_fail["status"] == "discard" and better_fail["guard_passed"] is False
    equal = loop(100.0, True)                           # not strictly better: discarded, guard not run
    assert equal["status"] == "discard" and equal["guard_passed"] is None
    worse = loop(120.0, True)
    assert worse["status"] == "discard" and worse["guard_passed"] is None
    kept = loop(90.0, True)
    assert kept["status"] == "keep" and kept["best_before"] == 100.0
    assert loop(90.0, True)["status"] == "discard"      # the new best is 90: equal again
    assert loop(89.999, True)["status"] == "keep"
    assert loop.calls == [100.0, 90.0, 90.0, 89.999]     # the guard ran for the baseline and every better metric only
    assert all(r["delivery_passed"] is False for r in json.loads(ls.RESULTS.read_text()))
