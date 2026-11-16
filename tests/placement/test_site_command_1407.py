"""#1407: one placement command over dt_ai.placement - MAF + Flora low-poly (NPM) and high-poly (VPM) at the same
points in one run [D293], fail-closed spec, CLI routing, duplicate-guard rule `site-placement`.

Pattern: n/a | new-case: tests of the site placement command (synthetic inputs, fake DCC; no user files).
"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
from dt_ai.placement import site  # noqa: E402


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tj = _load("site_job_fixtures_1407", "tests/placement/test_site_job.py")
OFFSET = tj.OFFSET


def make_spec(tmp, hole=False, vpm_bush=True, with_exception=False):
    """Generic spec: 6 bushes + 4 benches (one over a hole when hole=True) + one outside point."""
    tmp.mkdir(parents=True, exist_ok=True)
    pts = [{"x": 92.0 + 2.5 * k, "y": 193.0, "z": 0.0, "label": "Bush", "handle": f"F{k}", "inside": True,
            "rotation": 0.0, "position": None} for k in range(6)]
    pts.append({"x": 300.0, "y": 300.0, "z": 0.0, "label": "Bush", "handle": "OUT1", "inside": False,
                "rotation": 0.0, "position": None})
    pts += [{"x": 93.0 + 4.0 * k, "y": 199.0, "z": 0.0, "label": "Bench", "handle": f"M{k}", "inside": True,
             "rotation": 30.0 * k, "position": None} for k in range(3)]
    pts.append({"x": tj.HOLE[1], "y": tj.HOLE[2], "z": 0.0, "label": "Bench", "handle": tj.HOLE[0], "inside": True,
                "rotation": 0.0, "position": None})
    (tmp / "points.json").write_text(json.dumps({"points": pts}), encoding="utf-8")
    libs = {"Bush": {"kind": "flora", "h_m": [0.9, 1.1]}, "Bench": {"kind": "maf", "spec": [1.8, 0.5, 0.8]}}
    for var in ("npm", "vpm"):
        (tmp / f"BUSH_{var}.fbx").write_bytes(b"synthetic bush " + var.encode())
        (tmp / f"M01_{var}.fbx").write_bytes(b"synthetic bench " + var.encode())
        if var == "npm" or vpm_bush:
            libs["Bush"][var] = {"id": f"BUSH_{var.upper()}", "fbx": f"BUSH_{var}.fbx", "model_h_m": 1.0}
        libs["Bench"][var] = {"id": "M01", "fbx": f"M01_{var}.fbx"}
        g = tmp / "ground" / var
        g.mkdir(parents=True)
        (g / "ground.fbx").write_bytes(b"synthetic ground " + var.encode())
        (g / "master.json").write_text(json.dumps(tj.ground(hole)), encoding="utf-8")
    spec = {"schema": site.SCHEMA, "job": "SYNTH-SITE", "version": "v001", "issue": 1407,
            "points": "points.json", "assign": {"Bush": "Bush", "Bench": "Bench"}, "libraries": libs,
            "ground": {v: {"master": f"ground/{v}/master.json", "offset": OFFSET, "fbx": f"ground/{v}/ground.fbx"}
                       for v in ("npm", "vpm")}}
    if with_exception:
        p = next(x for x in pts if x["handle"] == tj.HOLE[0])
        snap = {k: p[k] for k in tj.ps.EXCEPTION_POINT_KEYS}
        snap["library_id"] = "M01"
        shas = {v: tj.job.sha(tmp / "ground" / v / "master.json") for v in ("npm", "vpm")}
        (tmp / "exc.json").write_text(json.dumps({"exceptions": [
            {"handle": tj.HOLE[0], "reason": "Ground hole (synthetic)", "point": snap, "ground_master_sha256": shas,
             "approved": {"by": "synthetic approver", "date": "2000-01-01",
                          "quote": "do not place (synthetic)"}}]}),
            encoding="utf-8")
        spec["exceptions"] = "exc.json"
    (tmp / "spec.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    return tmp / "spec.json"


def res(out):
    return json.loads((out / "results.json").read_text(encoding="utf-8"))


def placed(out, var):
    rep = json.loads((out / var / "engine_report.json").read_text(encoding="utf-8"))
    return [(i["handle"], i["label"]) for i in rep["instances"]]


# ---------------------------------------------------------------- acceptance: one run, both versions, same points
def test_one_run_places_npm_and_vpm_at_identical_points(tmp_path):
    spec = make_spec(tmp_path / "in")
    dcc = tj.FakeDCC()
    rc = site.run_file(spec, tmp_path / "out", 1407, dcc=dcc)
    r = res(tmp_path / "out")
    assert rc == 0 and r["status"] == "pass", r.get("parity")
    assert dcc.calls == ["facts", "facts", "instance", "instance"]
    assert placed(tmp_path / "out", "npm") == placed(tmp_path / "out", "vpm")
    assert len(placed(tmp_path / "out", "npm")) == 10
    par = r["parity"]
    assert par["identical"] is True and par["selected"]["npm"] == par["selected"]["vpm"]
    assert par["placed"]["npm"]["sha256"] == par["placed"]["vpm"]["sha256"] and par["placed"]["npm"]["count"] == 10
    for var in ("npm", "vpm"):
        assert tj.blends(tmp_path / "out", var) == [f"SYNTH-SITE_placement_{var}_v001.blend"]
    # the two versions carry their own models at the same points
    lib_npm = {i["library_id"] for i in json.loads((tmp_path / "out/npm/plan.json").read_text())["instances"]}
    lib_vpm = {i["library_id"] for i in json.loads((tmp_path / "out/vpm/plan.json").read_text())["instances"]}
    assert lib_npm == {"BUSH_NPM", "M01"} and lib_vpm == {"BUSH_VPM", "M01"}


def test_same_seed_same_spec_gives_identical_plans(tmp_path):
    spec = make_spec(tmp_path / "in")
    for k in (1, 2):
        assert site.run_file(spec, tmp_path / f"out{k}", 7, dcc=tj.FakeDCC()) == 0
    for var in ("npm", "vpm"):
        assert (tmp_path / f"out1/{var}/plan.json").read_bytes() == (tmp_path / f"out2/{var}/plan.json").read_bytes()


def test_approved_exception_excludes_the_point_in_both_versions(tmp_path):
    spec = make_spec(tmp_path / "in", hole=True, with_exception=True)
    assert site.run_file(spec, tmp_path / "out", 1, dcc=tj.FakeDCC()) == 0
    a, b = placed(tmp_path / "out", "npm"), placed(tmp_path / "out", "vpm")
    assert a == b and tj.HOLE[0] not in [h for h, _ in a] and len(a) == 9


# ---------------------------------------------------------------- strict parity / fail-closed spec
def test_library_without_vpm_model_is_an_error_naming_it_and_writes_nothing(tmp_path):
    spec = make_spec(tmp_path / "in", vpm_bush=False)
    dcc = tj.FakeDCC()
    with pytest.raises(site.SpecError, match="Bush.*vpm"):
        site.run_file(spec, tmp_path / "out", 1, dcc=dcc)
    assert dcc.calls == [] and not (tmp_path / "out").exists()


def test_legacy_mode_records_the_parity_gap_instead(tmp_path):
    spec = make_spec(tmp_path / "in", vpm_bush=False)
    rc = site.run_file(spec, tmp_path / "out", 1, dcc=tj.FakeDCC(), strict=False)
    r = res(tmp_path / "out")
    assert rc == 0 and r["parity"]["identical"] is False and r["parity"]["mode"] == "legacy"
    assert sorted(r["parity"]["only_npm"]) == [f"F{k}" for k in range(6)]
    assert {x["reason"] for x in r["variants"]["vpm"]["excluded"] if x["label"] == "Bush"} == {
        "no_confirmed_vpm", "outside_boundary"}


def test_ground_hole_without_exception_in_one_version_stops_before_any_instance(tmp_path):
    spec = make_spec(tmp_path / "in")
    tj_hole = json.dumps(tj.ground(True))
    (tmp_path / "in/ground/vpm/master.json").write_text(tj_hole, encoding="utf-8")   # only VPM Ground has the hole
    dcc = tj.FakeDCC()
    rc = site.run_file(spec, tmp_path / "out", 1, dcc=dcc)
    r = res(tmp_path / "out")
    assert rc != 0 and r["status"] in ("stopped", "parity_failed")
    assert "instance" not in dcc.calls
    assert tj.blends(tmp_path / "out", "npm") == [] and tj.blends(tmp_path / "out", "vpm") == []


@pytest.mark.parametrize("mutate,needle", [
    (lambda s: s["assign"].update({"Bench": "Chair"}), "Chair"),                         # unknown library key
    (lambda s: s["assign"].pop("Bench"), "Bench"),                                       # unmapped point label
    (lambda s: s["ground"].pop("vpm"), "vpm"),                                           # one version only
    (lambda s: s["ground"].update({"ipm": s["ground"]["npm"]}), "ipm"),                  # unsupported version
    (lambda s: s["libraries"]["Bush"].update({"kind": "tree"}), "tree"),                 # unsupported kind
    (lambda s: s["libraries"]["Bush"].update({"h_m": [0.9, float("nan")]}), "h_m"),      # NaN band
    (lambda s: s["libraries"]["Bush"]["npm"].update({"model_h_m": float("inf")}), "model_h_m"),
    (lambda s: s["libraries"]["Bush"]["npm"].update({"model_h_m": 0.0}), "model_h_m"),   # exactly at threshold
    (lambda s: s["libraries"]["Bench"].update({"spec": [1.8, 0.0, 0.8]}), "spec"),
    (lambda s: s["libraries"]["Bench"]["vpm"].update({"fbx": "missing.fbx"}), "missing.fbx"),
    (lambda s: s["libraries"].update({"Unused": {"kind": "maf", "spec": None, "npm": {"id": "U", "fbx": "M01_npm.fbx"},
                                                 "vpm": {"id": "U", "fbx": "M01_vpm.fbx"}}}), "Unused"),
    (lambda s: s["libraries"]["Bench"]["npm"].update({"id": "BUSH_NPM"}), "BUSH_NPM"),   # one id, two models
    (lambda s: s["ground"]["npm"].update({"offset": [0.0, float("nan"), 0.0]}), "offset"),
    (lambda s: s.update({"schema": "other/1"}), "schema"),
    (lambda s: s.update({"points": []}), "points"),                                      # empty input
    (lambda s: s.update({"version": "../v001"}), "version"),
    (lambda s: s.update({"job": "a/b"}), "job"),
])
def test_bad_spec_is_an_error_naming_the_key_before_any_write(tmp_path, mutate, needle):
    path = make_spec(tmp_path / "in")
    spec = json.loads(path.read_text(encoding="utf-8"))
    mutate(spec)
    path.write_text(json.dumps(spec), encoding="utf-8")
    dcc = tj.FakeDCC()
    with pytest.raises(site.SpecError) as exc:
        site.run_file(path, tmp_path / "out", 1, dcc=dcc)
    assert needle in str(exc.value)
    assert dcc.calls == [] and not (tmp_path / "out").exists()


def test_nan_point_stops_before_any_dcc(tmp_path):
    path = make_spec(tmp_path / "in")
    pts = json.loads((tmp_path / "in/points.json").read_text(encoding="utf-8"))
    pts["points"][2]["x"] = float("nan")
    (tmp_path / "in/points.json").write_text(json.dumps(pts), encoding="utf-8")
    dcc = tj.FakeDCC()
    assert site.run_file(path, tmp_path / "out", 1, dcc=dcc) == 1
    assert dcc.calls == [] and res(tmp_path / "out")["status"] == "stopped"


def test_inputs_are_never_written(tmp_path):
    path = make_spec(tmp_path / "in", hole=True, with_exception=True)
    before = tj_snapshot(tmp_path / "in")
    site.run_file(path, tmp_path / "out", 1, dcc=tj.FakeDCC())
    assert tj_snapshot(tmp_path / "in") == before


def tj_snapshot(d):
    return {str(p.relative_to(d)): p.read_bytes() for p in sorted(Path(d).rglob("*")) if p.is_file()}


# ---------------------------------------------------------------- CLI: fresh process, output aliases
def cli(*args):
    return subprocess.run([sys.executable, "-m", "dt_ai.cli.main", *map(str, args)], capture_output=True, text=True,
                          cwd=ROOT, env=dict(os.environ, PYTHONIOENCODING="utf-8"))


@pytest.mark.parametrize("out_of", ["spec", "input_dir", "existing"])
def test_cli_refuses_an_output_that_is_an_input_or_exists_and_writes_nothing(tmp_path, out_of):
    path = make_spec(tmp_path / "in")
    out = {"spec": path, "input_dir": tmp_path / "in" / "new_run", "existing": tmp_path / "in" / "ground"}[out_of]
    before = tj_snapshot(tmp_path / "in")
    r = cli("place", "site", path, "--out", out, "--seed", 1)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "ERROR" in r.stderr and tj_snapshot(tmp_path / "in") == before


def test_cli_bad_spec_exits_2_naming_the_key(tmp_path):
    path = make_spec(tmp_path / "in", vpm_bush=False)
    r = cli("place", "site", path, "--out", tmp_path / "out", "--seed", 1)
    assert r.returncode == 2 and "Bush" in r.stderr and not (tmp_path / "out").exists()


def test_agr_place_is_an_alias_of_dt_place_site():
    from dt_ai.cli import agr
    assert agr.ALIASES["place"] == ["place", "site"]
    from dt_ai.cli import shared_tools
    from dt_ai.cli.main import parser
    ns = parser().parse_args(["place", "site", "--", "x.json", "--out", "o"])
    argv = shared_tools.command(ROOT, ns.command, ns.step, ns.args)
    assert Path(argv[1]) == ROOT / "src/dt_ai/placement/site.py" and argv[2:] == ["x.json", "--out", "o"]


# ---------------------------------------------------------------- duplicate guard: one placement run
def test_guard_flags_an_engine_place_call_outside_the_command():
    guard = _load("dup_guard_1407", "tools/architecture/duplicate_guard.py")
    src = "from dt_ai.placement import engine\n\ndef run():\n    return engine.place([], [], [], [], 1)\n"
    assert [f.rule for f in guard.scan_text(src, "jobs/X/place.py")] == ["site-placement"]
    src2 = "from dt_ai.placement.engine import place\nplace([], [], [], [], 1)\n"
    assert [f.rule for f in guard.scan_text(src2, "jobs/X/place.py")] == ["site-placement"]
    owner = (ROOT / guard.RULES["site-placement"]).read_text(encoding="utf-8")
    assert guard.scan_text(owner, guard.RULES["site-placement"]) == []
    assert guard.GUARDED["site-placement"] == ("jobs", "tools", "src")


# ---------------------------------------------------------------- real Blender (opt-in `-m blender`)
def _box(lo, hi):
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    v = [[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0], [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]]
    return {"vertices": v, "faces": [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]}


@pytest.mark.blender
def test_real_blender_cli_places_both_versions_at_the_same_points(tmp_path):
    from dt_ai.core.blender_runner import blender_executable
    if not Path(blender_executable()).is_file():
        pytest.skip("pinned Blender not installed")
    d = tmp_path / "in"
    d.mkdir()
    g = tj.ground()
    (d / "master.json").write_text(json.dumps(g), encoding="utf-8")
    mesh = {"vertices": [[x - OFFSET[0], y - OFFSET[1], z - OFFSET[2]] for x, y, z in g["verts"]], "faces": g["faces"]}
    pts = [{"x": 92.0 + 2.0 * k, "y": 195.0 + (k % 3), "z": 0.0, "label": ["Bush", "Bench"][k % 2],
            "handle": f"P{k}", "inside": True, "rotation": 20.0 * k, "position": None} for k in range(6)]
    bench = _box([-0.9, -0.25, 0], [0.9, 0.25, 0.8])
    spec = {"schema": site.SCHEMA, "job": "SYNTH-1407", "version": "v001", "issue": 1407, "points": pts,
            "assign": {"Bush": "bush", "Bench": "bench"},
            "libraries": {"bush": {"kind": "flora", "h_m": [0.9, 1.1],
                                   "npm": {"id": "BUSH_NPM", "mesh": _box([-.5, -.5, 0], [.5, .5, 1]), "model_h_m": 1.0},
                                   "vpm": {"id": "BUSH_VPM", "mesh": _box([-.5, -.5, 0], [.5, .5, 1]), "model_h_m": 1.0}},
                          "bench": {"kind": "maf", "spec": [1.8, 0.5, 0.8], "npm": {"id": "BENCH", "mesh": bench},
                                    "vpm": {"id": "BENCH", "mesh": bench}}},
            "ground": {v: {"master": "master.json", "offset": OFFSET, "mesh": mesh} for v in ("npm", "vpm")}}
    (d / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
    r = cli("place", "site", d / "spec.json", "--out", tmp_path / "out", "--seed", 1407)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    rb = {v: json.loads((tmp_path / "out" / v / "readback.json").read_text(encoding="utf-8")) for v in ("npm", "vpm")}
    assert sorted(i["handle"] for i in rb["npm"]["instances"]) == sorted(i["handle"] for i in rb["vpm"]["instances"])
    assert len(rb["npm"]["instances"]) == 6 and res(tmp_path / "out")["parity"]["identical"] is True
