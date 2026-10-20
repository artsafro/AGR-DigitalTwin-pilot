"""Orchestration of the Vatutino placement job (#296) on synthetic generated inputs (no user files).

The real ``jobs/VATUTINO-SITE/place_site.py`` run is driven end to end with a fake DCC (facts / instance
readback written from the plan and the engine report, optionally corrupted) so the exit code, the persisted
diagnostics, the scene quarantine, the Ground exceptions and the report triangles are checked on the job
itself, not only on the helpers. Regression rows of PR #344 review round 1:

- inside-boundary points over a Ground hole are not removed by handle: no exception -> the run stops;
  an approved exception bound to the Ground fingerprint excludes them; a repaired Ground (other fingerprint)
  places them;
- a scene with a 1 m translated instance or a 1 m wrong / missing sinking exits nonzero, keeps the
  diagnostics in results.json and quarantines the saved scene;
- report triangles are the placed (post bottom-deletion) scene triangles, not the library triangles.
"""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
OFFSET = [100.0, 200.0, 0.0]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


job = _load("place_site_job", "jobs/VATUTINO-SITE/place_site.py")
report = _load("placement_report_job", "jobs/VATUTINO-SITE/placement_report.py")

BUSH = ([-0.5, -0.5, 0.0], [0.5, 0.5, 1.0])
BENCH = ([-0.9, -0.25, 0.0], [0.9, 0.25, 0.8])
HOLE = ("HOLE1", 104.5, 204.5)   # inside the boundary, over the removed Ground cell (synthetic)


def ground(hole=False, n=10, size=20.0, z0=10.0):
    vs, ts = [], []
    for j in range(n + 1):
        for i in range(n + 1):
            vs.append([90.0 + size * i / n, 190.0 + size * j / n, z0])
    for j in range(n):
        for i in range(n):
            if hole and (i, j) == (7, 7):          # cell 104..106 x 204..206
                continue
            a = j * (n + 1) + i
            ts += [[a, a + 1, a + n + 2], [a, a + n + 2, a + n + 1]]
    return {"verts": vs, "faces": ts}


def box_facts(lo, hi, bottom):
    pts = [[lo[0], lo[1], lo[2]], [hi[0], lo[1], lo[2]], [hi[0], hi[1], lo[2]], [lo[0], hi[1], lo[2]]]
    return {"bbox_min": list(lo), "bbox_max": list(hi), "triangles": 12, "polygons": 6,
            "bottom_faces": [{"index": 0, "points": pts}] if bottom else []}


def make_inputs(tmp, hole=False):
    """Synthetic job inputs: 6 bushes + 3 benches + the bench point over the hole; one outside point."""
    tmp.mkdir(parents=True, exist_ok=True)
    pl = [{"x": 92.0 + 2.5 * k, "y": 193.0, "z": 0.0, "label": "Рябинник", "handle": f"F{k}", "inside": True,
           "rotation": 0.0, "position": None} for k in range(6)]
    pl.append({"x": 300.0, "y": 300.0, "z": 0.0, "label": "Рябинник", "handle": "OUT1", "inside": False,
               "rotation": 0.0, "position": None})
    mf = [{"x": 93.0 + 4.0 * k, "y": 199.0, "z": 0.0, "label": "Скамья", "handle": f"M{k}", "inside": True,
           "rotation": 30.0 * k, "position": None} for k in range(3)]
    mf.append({"x": HOLE[1], "y": HOLE[2], "z": 0.0, "label": "Скамья", "handle": HOLE[0], "inside": True,
               "rotation": 0.0, "position": None})
    (tmp / "adapter.json").write_text(json.dumps({"planting": pl, "maf": mf}), encoding="utf-8")
    parts = {"sources": {"ground": {"npm_triangles": 1000}},
             "flora": [{"pos": 11, "ru": "Рябинник", "latin": "Sorbaria sorbifolia", "block": "Рябинник",
                        "qty": 6, "h_cm": [90, 110], "spozu_in": 6, "spozu_total": 7,
                        "cands": [{"id": 212, "latin": "Sorbaria sorbifolia",
                                   "obj": {"NPM": "BUSH_NPM", "VPM": "BUSH_VPM"}}]}],
             "maf": [{"set_id": "M01", "schedule": "*T/1", "block": "Скамья", "catalogue_id": "MAF_X",
                      "points_in": 4}]}
    (tmp / "parts.json").write_text(json.dumps(parts, ensure_ascii=False), encoding="utf-8")
    fl = tmp / "flora_fbx"
    fl.mkdir()
    exp = {}
    for o in ("BUSH_NPM", "BUSH_VPM"):
        (fl / f"{o}.fbx").write_bytes(b"synthetic " + o.encode())
        exp[o] = {"ok": True, "bbmin": BUSH[0], "bbmax": BUSH[1]}
    (fl / "export.json").write_text(json.dumps({"objects": exp}), encoding="utf-8")
    pos = {"set_id": "M01", "spozu_block": "Скамья", "schedule_size_m": [1.8, 0.5, 0.8]}
    for var in ("npm", "vpm"):
        (tmp / f"M01_{var}.fbx").write_bytes(b"synthetic bench " + var.encode())
        pos[var] = {"fbx": str(tmp / f"M01_{var}.fbx")}
    (tmp / "maf_set.json").write_text(json.dumps({"positions": [pos]}, ensure_ascii=False), encoding="utf-8")
    g = tmp / "ground"
    for var in ("npm", "vpm"):
        (g / var).mkdir(parents=True)
        (g / var / "SM_Vatutino_Ground.fbx").write_bytes(b"synthetic ground " + var.encode())
        (g / f"ground_master_{var}.json").write_text(json.dumps(ground(hole)), encoding="utf-8")
        (g / f"readback_{var}.json").write_text(json.dumps({"placement_offset": OFFSET}), encoding="utf-8")
    return {"adapter": tmp / "adapter.json", "ground": g, "flora_fbx": fl, "site_parts": tmp / "parts.json",
            "maf_set": tmp / "maf_set.json", "exceptions": tmp / "ground-exceptions.json",
            "flora_library": "synthetic"}


def ground_sha(cfg, var):
    return job.sha(cfg["ground"] / f"ground_master_{var}.json")


def write_exception(cfg, approved=True, bind_to=None):
    e = {"handle": HOLE[0], "reason": "Ground hole under the point (synthetic)",
         "ground_master_sha256": bind_to or {v: ground_sha(cfg, v) for v in ("npm", "vpm")}}
    if approved:
        e["approved"] = {"by": "user (synthetic)", "date": "2026-10-20", "quote": "do not place (synthetic)"}
    cfg["exceptions"].write_text(json.dumps({"exceptions": [e]}), encoding="utf-8")


class FakeDCC:
    """facts: synthetic boxes; instance: exact readback from plan + engine report, then ``mutate``."""

    def __init__(self, mutate=None):
        self.mutate = mutate
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args[0])
        spec = json.loads(Path(args[1]).read_text(encoding="utf-8"))
        if args[0] == "facts":
            out = {}
            for lib in spec["libraries"]:
                bush = lib["id"].startswith("BUSH")
                f = box_facts(*(BUSH if bush else BENCH), bottom=not bush)
                out[lib["id"]] = {**f, "base_scale": float(lib.get("base_scale", 1.0))}
            Path(args[2]).write_text(json.dumps(out), encoding="utf-8")
            return {"cmd": "fake facts", "exit_code": 0, "seconds": 0.0}
        plan = json.loads(Path(args[2]).read_text(encoding="utf-8"))
        rep = json.loads((Path(args[1]).parent / "engine_report.json").read_text(encoding="utf-8"))
        eng = {i["handle"]: i for i in rep["instances"]}
        rows = []
        for it in plan["instances"]:
            e = eng[it["handle"]]
            rows.append({"name": it["name"], "handle": it["handle"], "library_id": it["library_id"],
                         "matrix": copy.deepcopy(it["matrix"]), "polygons": 6 - len(it["delete_polygons"]),
                         "triangles": 12 - 2 * len(it["delete_polygons"]),
                         "lowest_z": e["ground_z"] - e["sink_m"] - OFFSET[2],
                         "ground_z_at_pivot": e["ground_z"] - OFFSET[2]})
        rb = {"seed": plan["seed"], "instances": rows, "run_record": spec.get("run_record"),
              "library_polygons": {lib["id"]: 6 for lib in spec["libraries"]},
              "library_triangles": {lib["id"]: 12 for lib in spec["libraries"]}}
        if self.mutate:
            self.mutate(rb)
        Path(args[3]).write_bytes(b"synthetic blend")
        Path(args[4]).write_text(json.dumps(rb), encoding="utf-8")
        return {"cmd": "fake instance", "exit_code": 0, "seconds": 0.0}


def results(out):
    return json.loads((out / "results.json").read_text(encoding="utf-8"))


def blends(out, var):
    return sorted(p.name for p in (out / var).glob("*.blend"))


# ---------------------------------------------------------------- clean control
def test_clean_run_exits_zero_and_keeps_scenes(tmp_path):
    cfg = make_inputs(tmp_path / "in")
    out = tmp_path / "run"
    assert job.run(cfg, out, 296, dcc=FakeDCC()) == 0
    res = results(out)
    assert res["status"] == "pass"
    for var in ("npm", "vpm"):
        v = res["variants"][var]
        assert v["scene_mismatches"] == [] and v["sinking_scene"]["ok"] and v["qa_failed"] == []
        assert blends(out, var) == [f"VATUTINO-SITE_placement_{var}_v001.blend"]
        assert v["counts"]["M01"]["placed"] == 4 and v["counts"][f"BUSH_{var.upper()}"]["placed"] == 6


# ---------------------------------------------------------------- P1-2: scene QA gates the exit code
def _shift_first(rb):
    rb["instances"][0]["matrix"][0][3] += 1.0


def _sink_1m(rb):
    rb["instances"][0]["lowest_z"] -= 1.0


def _sink_missing(rb):
    rb["instances"][0]["ground_z_at_pivot"] = None


@pytest.mark.parametrize("mutate,what", [(_shift_first, "scene_mismatches"), (_sink_1m, "sinking"),
                                         (_sink_missing, "sinking")])
def test_scene_qa_failure_exits_nonzero_persists_and_quarantines(tmp_path, mutate, what):
    cfg = make_inputs(tmp_path / "in")
    out = tmp_path / "run"
    rc = job.run(cfg, out, 296, dcc=FakeDCC(mutate))
    assert rc == 3
    res = results(out)
    assert res["status"] == "qa_failed"
    for var in ("npm", "vpm"):
        v = res["variants"][var]
        assert v["qa_failed"], v
        if what == "scene_mismatches":
            assert len(v["scene_mismatches"]) == 2          # pivot + matrix of the shifted instance
        else:
            assert v["sinking_scene"]["ok"] is False and len(v["sinking_scene"]["out_of_tol"]) == 1
        assert blends(out, var) == [f"VATUTINO-SITE_placement_{var}_v001.QA_FAILED.blend"]
        assert v["blend"]["path"].endswith(".QA_FAILED.blend")
    with pytest.raises(SystemExit):
        report.build(res, json.loads(cfg["site_parts"].read_text(encoding="utf-8")))


# ---------------------------------------------------------------- P1-1: no permanent handle exclusion
def test_hole_without_exception_stops_the_run(tmp_path):
    cfg = make_inputs(tmp_path / "in", hole=True)
    out = tmp_path / "run"
    dcc = FakeDCC()
    assert job.run(cfg, out, 296, dcc=dcc) == 1
    assert "instance" not in dcc.calls
    stopped = results(out)["variants"]["npm"]["stopped"]
    assert any(HOLE[0] in r and "point_over_ground_hole" in r for r in stopped)


def test_approved_exception_bound_to_ground_excludes_and_lists(tmp_path):
    cfg = make_inputs(tmp_path / "in", hole=True)
    write_exception(cfg)
    out = tmp_path / "run"
    assert job.run(cfg, out, 296, dcc=FakeDCC()) == 0
    for var in ("npm", "vpm"):
        v = results(out)["variants"][var]
        ex = [x for x in v["excluded"] if x["handle"] == HOLE[0]]
        assert len(ex) == 1 and ex[0]["reason"] == "ground_exception" and ex[0]["approved"]["by"]
        assert v["counts"]["M01"]["placed"] == 3


def test_repaired_ground_places_the_points_despite_a_stale_exception(tmp_path):
    cfg = make_inputs(tmp_path / "in", hole=False)        # repaired Ground: other fingerprint
    write_exception(cfg, bind_to={"npm": "0" * 64, "vpm": "0" * 64})
    out = tmp_path / "run"
    assert job.run(cfg, out, 296, dcc=FakeDCC()) == 0
    for var in ("npm", "vpm"):
        v = results(out)["variants"][var]
        assert v["counts"]["M01"]["placed"] == 4
        assert not any(x["handle"] == HOLE[0] for x in v["excluded"])
        assert v["ground_exceptions_stale"] == [HOLE[0]]


def test_unapproved_exception_stops_the_run(tmp_path):
    cfg = make_inputs(tmp_path / "in", hole=True)
    write_exception(cfg, approved=False)
    out = tmp_path / "run"
    assert job.run(cfg, out, 296, dcc=FakeDCC()) == 1
    assert any("not user-approved" in r for r in results(out)["variants"]["npm"]["stopped"])


# ---------------------------------------------------------------- P1-3: report triangles = placed scene
def test_report_triangles_are_post_deletion_scene_triangles(tmp_path):
    cfg = make_inputs(tmp_path / "in")
    out = tmp_path / "run"
    assert job.run(cfg, out, 296, dcc=FakeDCC()) == 0
    res = results(out)
    rep, md = report.build(res, json.loads(cfg["site_parts"].read_text(encoding="utf-8")))
    n = rep["variants"]["npm"]
    maf = n["maf"][0]
    deleted = res["variants"]["npm"]["bottom_faces"]["deleted"]
    assert deleted == 4                                   # every bench bottom proven on flat Ground
    assert maf["tris_library"] == 12 and maf["tris_total_library"] == 48
    assert maf["tris_instance"] == {"min": 10, "max": 10} and maf["tris_total"] == 40
    fl = n["flora"][0]
    assert fl["tris_total"] == 72                         # 6 x 12, nothing deleted
    assert n["triangles"]["maf"] == 40 and n["triangles"]["flora"] == 72
    assert n["triangles"]["total"] == 40 + 72 + 1000
    assert "| 40 |" in md and "| 48 |" not in md.split("## NPM budget")[1]
