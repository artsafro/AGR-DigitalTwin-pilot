"""#1381 compaction step 6: BODY seam/assembly copies -> owners, one roof/parapet seam check.

Pattern: n/a | new-case: tests of the seam-seal guard rule, the KPP1 seal shim, the roof plate through roof_core and the
shared roof/parapet seam check (VPM red block `parapet-seam`).

The 3 #1359 rows of step #1381: jobs/KPP1/scripts/seal.py `seal` + `t_junctions` (moved unchanged to the one Blender
seam owner tools/blender/seam_seal.py; the job file is an import shim) and build_kpp1.py `roof` (the parapet plate
outline and height now come from adapters/max/agr_tools/roof_core.py, R6 #1352 / D292: wrapper). No Blender here.
"""
import ast
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "architecture"))
import duplicate_guard as guard  # noqa: E402
import mini_yaml  # noqa: E402
import route_map  # noqa: E402

OWNER = "tools/blender/seam_seal.py"
SHIM = "jobs/KPP1/scripts/seal.py"
BUILD = "jobs/KPP1/scripts/build_kpp1.py"
CHECK = "tools/qa/roof_parapet_seam.py"
# sha1 of ast.unparse(module without its docstring) of jobs/KPP1/scripts/seal.py on origin/main 6519a3d8 (before the move)
SEAL_CODE_SHA1 = "743d7547df7d36442f7ace0000ebcfe2e8dfd2b0"


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


roof_core = _load("roof_core_1381", "adapters/max/agr_tools/roof_core.py")


def _code_sha1(rel):
    tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    body = [n for n in tree.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
    return hashlib.sha1(ast.unparse(ast.Module(body=body, type_ignores=[])).encode()).hexdigest()


def _rows():
    return guard.rows_of(guard.load_maps(ROOT))


# --- map + guard -------------------------------------------------------------------------------------------------

def test_seal_rows_left_the_map_and_the_roof_row_is_a_wrapper():
    rows = _rows()
    assert not any(r.rel == SHIM for r in rows), [r.at for r in rows if r.rel == SHIM]
    roof = [r for r in rows if r.rel == BUILD and r.context == "roof"]
    assert [(r.at, r.status) for r in roof] == [(BUILD + "::roof", "wrapper")]
    assert guard.calls_owner(ROOT, roof[0])
    step = [r for r in rows if r.status == "live-bypass" and r.step == "#1381"]
    assert step == []


def test_baseline_has_no_step_1381_rows_and_report_order_drops_the_step():
    keys = {at for _, at, _ in guard.LIVE_BYPASS_BASELINE}
    assert not {k for k in keys if k.startswith((SHIM, BUILD))}
    assert "#1381" not in guard.bypass_table(_rows()).split("Порядок")[-1]


def test_seam_seal_rule_is_registered_and_guards_jobs_tools_src():
    assert guard.RULES["seam-seal"] == OWNER
    assert guard.GUARDED["seam-seal"] == ("jobs", "tools", "src")
    assert "seam-seal" in guard.REASON_REQUIRED
    ctx = mini_yaml.load(ROOT / route_map.CONTEXTS)
    assert {r["id"]: r["owner"] for r in ctx["rules"]}["seam-seal"] == OWNER
    assert (ROOT / OWNER).is_file()


def test_guard_green_on_repo_and_no_seam_seal_copy_anywhere():
    allowed = guard.allowlist(mini_yaml.load(ROOT / route_map.CONTEXTS))
    findings = guard.scan_for(ROOT, allowed)
    assert guard.compare(findings, allowed) == ([], [])
    assert [f for f in findings if f.rule == "seam-seal"] == []


def test_guard_cli_exit_0_on_repo_in_a_fresh_process():
    out = subprocess.run([sys.executable, str(ROOT / "tools/architecture/duplicate_guard.py"), "--root", str(ROOT)],
                         capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stdout[-2000:] + out.stderr[-2000:]


@pytest.mark.parametrize("code", [
    "def seal(bm, max_iter=12, log=None):\n    return bm\n",
    "def ring_split(bm, cuts):\n    return bm\n",
    "def t_junctions(bm, tol=0.001):\n    return {}\n",
    "class S:\n    def ring_split(self, bm, cuts):\n        pass\n",
    "async def seal(bm):\n    pass\n",
])
def test_guard_red_on_synthetic_copy(tmp_path, code, capsys):
    for top in ("jobs", "tools", "src"):
        (tmp_path / top).mkdir()
    (tmp_path / "jobs/NEW").mkdir()
    (tmp_path / "jobs/NEW/copy.py").write_text(code, encoding="utf-8")
    ctx = tmp_path / "contexts.yaml"
    ctx.write_text("contexts:\n  - id: x\n", encoding="utf-8")
    assert guard.main(["--root", str(tmp_path), "--contexts", str(ctx), "--copies-only"]) == 1
    assert "NEW COPY [seam-seal]" in capsys.readouterr().out


@pytest.mark.parametrize("code", [
    '"""def seal(bm): prose"""\n',
    "seal = None\n",
    "def seal2(bm):\n    pass\n",
    "def sealed(bm):\n    pass\n",
    "import seal\nbm = seal.seal(bm)\n",          # a call of the owner is not a copy
    "def t_junction_count(v, t, tol):\n    pass\n",
])
def test_guard_ignores_non_copies(code):
    assert [f for f in guard.scan_text(code, "jobs/x.py") if f.rule == "seam-seal"] == []


def test_owner_file_is_not_a_copy_of_itself():
    assert [f for f in guard.scan_text("def seal(bm):\n    pass\n", OWNER) if f.rule == "seam-seal"] == []


def test_seam_seal_row_without_reason_is_an_error():
    ctx = {"contexts": [{"id": "x", "duplicates": [
        {"at": "jobs/NEW/copy.py::seal", "rule": "seam-seal", "issue": "#1381"}]}]}
    with pytest.raises(ValueError, match="no reason"):
        guard.allowlist(ctx)


# --- owner + shim ------------------------------------------------------------------------------------------------

def test_owner_is_the_kpp1_seal_moved_unchanged():
    assert _code_sha1(OWNER) == SEAL_CODE_SHA1
    doc = ast.get_docstring(ast.parse((ROOT / OWNER).read_text(encoding="utf-8")))
    assert "new-case" in doc and "#1381" in doc


def test_shim_defines_nothing_and_names_the_owner():
    tree = ast.parse((ROOT / SHIM).read_text(encoding="utf-8"))
    assert not [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    assert "seam_seal.py" in (ROOT / SHIM).read_text(encoding="utf-8")


STUBS = {"bmesh.py": "ops = None\nnew = None\n", "mathutils/__init__.py": "class Vector(tuple):\n    pass\n",
         "mathutils/kdtree.py": "class KDTree:\n    pass\n"}


@pytest.mark.parametrize("importer", ["import seal as m", "import importlib; m = importlib.import_module('seal')"])
def test_shim_import_gives_the_owner_module_in_a_fresh_process(tmp_path, importer):
    """build_kpp1.py and PSU275 vpm_stage5.py `import seal` from jobs/KPP1/scripts: they must get the owner's code."""
    for rel, text in STUBS.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    code = (f"import sys; sys.path[:0] = [{str(ROOT / 'jobs/KPP1/scripts')!r}, {str(tmp_path)!r}]\n{importer}\n"
            "import json; print(json.dumps({n: getattr(m, n).__code__.co_filename for n in "
            "('seal', 't_junctions', 'ring_split', 'quadify', 'weld')} | {'WELD': m.WELD, 'TOL': m.TOL, "
            "'same': sys.modules['seal'] is m}))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=tmp_path)
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout)
    assert got.pop("WELD") == 0.0025 and got.pop("TOL") == 0.001 and got.pop("same") is True
    assert {Path(p).resolve() for p in got.values()} == {(ROOT / OWNER).resolve()}


def test_build_kpp1_still_seals_through_the_shim_name():
    src = (ROOT / BUILD).read_text(encoding="utf-8")
    assert "import seal  #" in src and "seal.seal(bm" in src and "seal.quadify(bm" in src


# --- roof plate through roof_core (R6 #1352 / D292) ---------------------------------------------------------------

def _kpp1():
    tree = ast.parse((ROOT / BUILD).read_text(encoding="utf-8"))
    env = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and all(isinstance(t, (ast.Name, ast.Tuple)) for t in node.targets):
            names = {n.id for t in node.targets for n in ast.walk(t) if isinstance(n, ast.Name)}
            if names & {"X0", "PARAPET_IN", "PARAPET_TOP_IN", "Z_ROOF", "PLATE_GAP", "PLATE_OVERLAP", "SHAFT"}:
                exec(compile(ast.Module(body=[node], type_ignores=[]), BUILD, "exec"), env)
    return env


def _kpp1_hole(k):
    d = 0.33 + k["PARAPET_IN"]
    xi0, xi1, yi0, yi1 = k["X0"] + d, k["X1"] - d, k["Y0"] + d, k["Y1"] - d
    x0, x1, y0, y1, _ = k["SHAFT"]
    loop = [(xi0, yi0), (x0, yi0), (x1, yi0), (xi1, yi0), (xi1, y0), (xi1, y1), (xi1, yi1), (x1, yi1), (x0, yi1),
            (xi0, yi1), (xi0, y1), (xi0, y0)]
    outer = [(k["X0"], k["Y0"]), (k["X1"], k["Y0"]), (k["X1"], k["Y1"]), (k["X0"], k["Y1"])]
    return loop, outer, (xi0, xi1, yi0, yi1)


def test_kpp1_plate_from_roof_core_equals_the_delivered_plate():
    """The delivered KPP1 plate: hole grown by PLATE_OVERLAP (20 mm), PLATE_GAP (5 mm) above LEVEL_roof."""
    k = _kpp1()
    loop, outer, (xi0, xi1, yi0, yi1) = _kpp1_hole(k)
    s = roof_core.hole_plate(loop, k["Z_ROOF"], k["PARAPET_TOP_IN"], outer,
                             {"lift_m": k["PLATE_GAP"], "inset_m": k["PLATE_OVERLAP"]})
    o = k["PLATE_OVERLAP"]
    xs, ys, zs = [p[0] for p in s["verts"]], [p[1] for p in s["verts"]], {p[2] for p in s["verts"]}
    assert len(s["verts"]) == 4 and s["gaps"] == 0 and s["outside"] == []
    for got, want in ((min(xs), xi0 - o), (max(xs), xi1 + o), (min(ys), yi0 - o), (max(ys), yi1 + o)):
        assert abs(got - want) <= 1e-9
    assert all(abs(z - (k["Z_ROOF"] + k["PLATE_GAP"])) <= 1e-9 for z in zs)


def test_roof_uses_roof_core_and_the_kpp1_values():
    tree = ast.parse((ROOT / BUILD).read_text(encoding="utf-8"))
    roof = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "roof")
    src = ast.unparse(roof)
    assert "hole_plate(" in src and "PLATE_GAP" in src and "PLATE_OVERLAP" in src and "PARAPET_TOP_IN" in src


def _square(n=1.0):
    return [(0.0, 0.0), (n, 0.0), (n, n), (0.0, n)]


@pytest.mark.parametrize("loop,level,top,outer,exc", [
    ([], 0.0, 1.0, None, ValueError),
    ([(0.0, 0.0), (1.0, 0.0)], 0.0, 1.0, None, ValueError),
    ([(0.0, 0.0), (1.0, float("nan")), (1.0, 1.0)], 0.0, 1.0, None, ValueError),
    (_square(), float("inf"), 1.0, None, ValueError),
    (_square(), 0.0, 0.0, None, ValueError),                       # parapet face of zero height
    (_square(), 1.0, 0.5, None, ValueError),                       # top below the foot
    (_square(), 0.0, 1.0, _square(1.0), roof_core.G.Ambiguous),    # inset beyond the outer parapet line
    ([(0.0, 0.0), (1.0, 0.0), (1.0, 0.0), (0.0, 1.0)], 0.0, 1.0, None, ValueError),  # repeated point
])
def test_hole_plate_fails_closed(loop, level, top, outer, exc):
    with pytest.raises(exc):
        roof_core.hole_plate(loop, level, top, outer, {"inset_m": 0.02})


def test_hole_plate_exactly_on_the_outer_line_is_accepted_and_winding_does_not_matter():
    d = 0.02
    outer = [(-d, -d), (1 + d, -d), (1 + d, 1 + d), (-d, 1 + d)]
    a = roof_core.hole_plate(_square(), 0.0, 1.0, outer, {"inset_m": d})
    b = roof_core.hole_plate(list(reversed(_square())), 0.0, 1.0, outer, {"inset_m": d})
    for s in (a, b):
        assert s["outside"] == [] and s["gaps"] == 0 and s["lift_m"] == 0.005
        assert sorted(round(c, 9) for p in s["verts"] for c in p[:2]) == sorted([-d, -d, 1 + d, -d, 1 + d, 1 + d,
                                                                                    -d, 1 + d])


def test_hole_plate_rejects_unknown_options():
    with pytest.raises(ValueError, match="unknown option"):
        roof_core.hole_plate(_square(), 0.0, 1.0, None, {"plate_gap": 0.005})


# --- one roof/parapet seam check (VPM red block parapet-seam) -----------------------------------------------------

class _Lazy:   # loaded on first use, so a missing module fails the tests that need it, not the collection
    mod = None

    def __getattr__(self, name):
        if _Lazy.mod is None:
            _Lazy.mod = _load("roof_parapet_seam_1381", CHECK)
        return getattr(_Lazy.mod, name)


seam = _Lazy()
KEYS = ("t_junctions", "non_manifold", "slabs_not_inset", "open_loops_not_allowed", "open_loops_not_closed",
        "texture_joint_unmatched")


def _counts(**kw):
    c = {k: 0 for k in KEYS}
    c.update(kw)
    return c


def test_verdict_pass_only_when_every_count_is_zero():
    assert seam.verdict(_counts())["status"] == "pass"
    for k in KEYS:
        v = seam.verdict(_counts(**{k: 1}))
        assert v["status"] == "fail" and [p["key"] for p in v["problems"]] == [k]


@pytest.mark.parametrize("bad", [{"t_junctions": -1}, {"t_junctions": 1.5}, {"t_junctions": float("nan")},
                                 {"t_junctions": True}, {"t_junctions": "0"}, {"t_junctions": float("inf")}])
def test_verdict_rejects_bad_counts_naming_the_key(bad):
    with pytest.raises(ValueError, match="t_junctions"):
        seam.verdict(_counts(**bad))


def test_verdict_missing_or_unknown_key_is_an_error_and_empty_input_never_passes():
    c = _counts()
    del c["texture_joint_unmatched"]
    with pytest.raises(ValueError, match="texture_joint_unmatched"):
        seam.verdict(c)
    with pytest.raises(ValueError, match="bogus"):
        seam.verdict(_counts(bogus=0))
    with pytest.raises(ValueError):
        seam.verdict({})


def test_not_measured_is_incomplete_never_pass():
    v = seam.verdict(_counts(texture_joint_unmatched=None))
    assert v["status"] == "incomplete" and v["not_measured"] == ["texture_joint_unmatched"]
    assert seam.verdict(_counts(t_junctions=2, texture_joint_unmatched=None))["status"] == "fail"


def test_measured_input_kpp1_1339_and_sreda():
    """KPP1 #1339 seam-report (welded before / separate after) and SREDA elv-tc-vpm v004/v005 joint crossings."""
    rep = json.loads((ROOT / "jobs/KPP1/seam-1339/seam-report.json").read_text(encoding="utf-8"))
    by = {v["variant"]: seam.from_seam_report(v) for v in rep["variants"]}
    assert by["separate"] == _counts(texture_joint_unmatched=None)
    assert seam.verdict(by["separate"])["status"] == "incomplete"     # geometry clean, texture joint not measured
    assert seam.verdict(by["welded"])["status"] == "fail"
    assert by["welded"]["slabs_not_inset"] == 1
    for unmatched in (423, 4):   # SREDA v004 Max review / v005 after the joint rework (retro 2026-11-05)
        assert seam.verdict(_counts(texture_joint_unmatched=unmatched))["status"] == "fail"
    measured = {m["object"]: m for m in seam.MEASURED_INPUT}
    assert measured["SREDA elv-tc-vpm v004"]["texture_joint_unmatched"] == 423
    assert measured["SREDA elv-tc-vpm v005"]["texture_joint_unmatched"] == 4


def test_joint_report_total_reads_unmatched_crossings_and_fails_closed():
    assert seam.joint_unmatched({"total": {"unmatched_crossings": 4, "crossings": 900}}) == 4
    for bad in ({}, {"total": {}}, {"total": {"unmatched_crossings": -1}}, {"total": {"unmatched_crossings": None}}):
        with pytest.raises(ValueError):
            seam.joint_unmatched(bad)


def test_measure_roof_seam_uses_the_shared_geometry_measure():
    mrs = _load("measure_roof_seam_1381", "jobs/KPP1/seam-1339/measure_roof_seam.py")
    assert mrs.measure.__code__.co_filename == str((ROOT / CHECK)) or \
        Path(mrs.measure.__code__.co_filename).resolve() == (ROOT / CHECK).resolve()


def _cli(*args, cwd=None):
    return subprocess.run([sys.executable, str(ROOT / CHECK), *map(str, args)], capture_output=True, text=True,
                          cwd=cwd or ROOT)


def test_cli_pass_fail_incomplete_and_error_exit_codes(tmp_path):
    cases = {"pass": (_counts(), 0), "fail": (_counts(t_junctions=3), 1),
             "incomplete": (_counts(texture_joint_unmatched=None), 1), "bad": (_counts(t_junctions=-1), 2)}
    for name, (counts, code) in cases.items():
        src = tmp_path / f"{name}.json"
        src.write_text(json.dumps(counts), encoding="utf-8")
        out = tmp_path / f"{name}-out.json"
        r = _cli("--counts", src, "--output", out)
        assert r.returncode == code, (name, r.stdout, r.stderr)
        if code == 2:
            assert not out.exists()
        else:
            assert json.loads(out.read_text(encoding="utf-8"))["status"] == name


def test_cli_never_overwrites_and_output_alias_of_input_writes_nothing(tmp_path):
    src = tmp_path / "c.json"
    text = json.dumps(_counts())
    src.write_text(text, encoding="utf-8")
    for out in (src, tmp_path / "." / "c.json", tmp_path / "sub" / ".." / "c.json"):
        assert _cli("--counts", src, "--output", out).returncode == 2
        assert src.read_text(encoding="utf-8") == text
    existing = tmp_path / "old.json"
    existing.write_text("keep", encoding="utf-8")
    assert _cli("--counts", src, "--output", existing).returncode == 2
    assert existing.read_text(encoding="utf-8") == "keep"
    assert not list(tmp_path.glob("*.partial"))


def test_cli_rejects_missing_empty_and_non_json_input(tmp_path):
    empty = tmp_path / "e.json"
    empty.write_text("", encoding="utf-8")
    junk = tmp_path / "j.json"
    junk.write_text("[1, 2]", encoding="utf-8")
    nan = tmp_path / "n.json"
    nan.write_text('{"t_junctions": NaN}', encoding="utf-8")
    for src in (tmp_path / "missing.json", empty, junk, nan):
        out = tmp_path / (src.stem + "-out.json")
        assert _cli("--counts", src, "--output", out).returncode == 2
        assert not out.exists()


# --- route map: the red block is closed ---------------------------------------------------------------------------

def test_parapet_seam_hotspot_closed_and_roof_stage_names_the_shared_check():
    ev = mini_yaml.load(ROOT / "docs/architecture/vpm-oks-route.events.yaml")
    assert "parapet-seam" not in {h["id"] for h in ev.get("hotspots", [])}
    roof = next(s for s in ev["stages"] if s["id"] == "roof")
    assert CHECK in roof["evidence"]
    assert OWNER in roof["evidence"]
