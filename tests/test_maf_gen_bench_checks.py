"""maf_gen_bench_checks is a gate (#817): exit 1 on any fail, sizes checked against a per-row reference [D094]."""
from __future__ import annotations

import importlib.util
import json
import math
import random
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/library/maf_gen_bench_checks.py"
_spec = importlib.util.spec_from_file_location("maf_gen_bench_checks", TOOL)
chk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chk)

RECT = [0.0, 0.0, 0.5, 0.5]
SURFACE = {"soft_edge_dihedrals_deg": [], "components": 1, "undetermined_components": 0,
           "flipped_faces": 0, "inconsistent_edges": 0}


def _mesh(size, *, uv=(0.1, 0.1), surface=True):
    m = {"name": "SM_Bench_GroundEl", "triangles": 12, "bounds_m": [[0.0, 0.0, 0.0], list(size)],
         "face_geometry": {"polygon_material": ["MAF_seat"], "polygon_uv": [[list(uv), [0.2, 0.1], [0.2, 0.2]]]}}
    if surface:
        m["maf_surface"] = dict(SURFACE)
    return m


def make_case(tmp_path, dims, readback=None, *, uv=None, surface=None):
    """dims: {row: generator dims}; readback: {(row, role): size}; uv/surface: {(row, role): value}."""
    readback, uv, surface = readback or {}, uv or {}, surface or {}
    atlas = tmp_path / "atlas.json"
    atlas.write_text(json.dumps({"materials": {"seat": {"uv": RECT}}}), encoding="utf-8")
    rb_dir = tmp_path / "readback"
    rb_dir.mkdir()
    rows = []
    for row, d in dims.items():
        set_id = f"SET_{row:02d}"
        rows.append({"row": row, "set_id": set_id, "generator_facts": {"dims_m": list(d)}})
        for role in ("npm", "vpm"):
            mesh = _mesh(readback.get((row, role), d), uv=uv.get((row, role), (0.1, 0.1)),
                         surface=surface.get((row, role), True))
            (rb_dir / f"{role}_{set_id}.json").write_text(json.dumps({"meshes": [mesh]}), encoding="utf-8")
    report = tmp_path / "build-report.json"
    report.write_text(json.dumps({"smoothing_deg": 40, "atlas_uv_json": str(atlas), "rows": rows}), encoding="utf-8")
    return report, rb_dir, tmp_path / "checks.json"


def write_ref(tmp_path, rows, name="reference.json"):
    p = tmp_path / name
    p.write_text(json.dumps({"rows": rows}), encoding="utf-8")
    return p


def ref_row(size, basis="schedule", source="schedule T3508 row n"):
    return {"size_m": list(size), "basis": basis, "source": source}


DIMS = {1: [3.9, 2.5, 0.45], 2: [6.25, 0.6, 0.45]}


def run(report, rb, out, *extra):
    return chk.main([str(report), str(rb), str(out), *extra])


def test_all_pass_exit_0(tmp_path):
    report, rb, out = make_case(tmp_path, DIMS)
    assert run(report, rb, out) == 0
    res = json.loads(out.read_text(encoding="utf-8"))
    assert res["verdict"] == "pass" and res["failures"] == []
    assert res["rows"][0]["reference"]["basis"] == "generator"


def test_one_failing_dimension_exit_1(tmp_path):
    report, rb, out = make_case(tmp_path, DIMS, {(2, "vpm"): [6.45, 0.6, 0.45]})
    assert run(report, rb, out) == 1
    res = json.loads(out.read_text(encoding="utf-8"))
    assert res["verdict"] == "fail"
    assert res["rows"][1]["vpm"]["dimension"] == "fail" and res["rows"][1]["npm"]["dimension"] == "pass"
    assert any("SET_02" in f and "vpm" in f and "dimension" in f for f in res["failures"])


def test_maf_findings_not_run_exit_1(tmp_path):
    report, rb, out = make_case(tmp_path, DIMS, surface={(1, "npm"): False})
    assert run(report, rb, out) == 1
    res = json.loads(out.read_text(encoding="utf-8"))
    assert any("SET_01" in f and "npm" in f and "maf_findings" in f for f in res["failures"])


def test_uv_face_outside_slot_exit_1(tmp_path):
    report, rb, out = make_case(tmp_path, DIMS, uv={(1, "vpm"): (0.9, 0.9)})
    assert run(report, rb, out) == 1
    res = json.loads(out.read_text(encoding="utf-8"))
    assert res["rows"][0]["vpm"]["uv_slots"]["faces_outside"] == 1
    assert any("SET_01" in f and "uv" in f for f in res["failures"])


def test_nan_readback_bounds_fail_not_pass(tmp_path):
    report, rb, out = make_case(tmp_path, DIMS, {(1, "npm"): [float("nan"), 2.5, 0.45]})
    assert run(report, rb, out) == 1
    assert json.loads(out.read_text(encoding="utf-8"))["rows"][0]["npm"]["dimension"] == "fail"


def test_wrong_parameter_passes_self_check_but_fails_reference(tmp_path):
    # generator and readback agree (round trip ok) but the bench is 0.5 m longer than the schedule
    report, rb, out = make_case(tmp_path, {1: [4.4, 2.5, 0.45]})
    ref = write_ref(tmp_path, {"1": ref_row([3.9, 2.5, 0.45], source="T3508 row 1: 2500x3900x600 mm")})
    assert run(report, rb, out, "--reference", str(ref)) == 1
    row = json.loads(out.read_text(encoding="utf-8"))["rows"][0]
    assert row["reference"] == {"basis": "schedule", "source": "T3508 row 1: 2500x3900x600 mm",
                                "size_m": [3.9, 2.5, 0.45]}
    assert row["npm"]["dimension"] == "fail" and row["npm"]["maf_findings"]["MAF dimensions vs specification"]["status"] == "fail"


def test_reference_within_tolerance_records_basis(tmp_path):
    report, rb, out = make_case(tmp_path, {1: [3.919, 2.501, 0.45], 7: [4.921, 0.6, 0.45]})
    ref = write_ref(tmp_path, {"1": ref_row([3.9, 2.5, 0.45]),
                               "7": ref_row([4.921, 0.6, 0.45], "dwg_outline", "polyline 198ADA"),
                               "9": ref_row([2.0, 0.6, 0.45], "dwg_outline", "polyline 19865C")})
    assert run(report, rb, out, "--reference", str(ref)) == 0
    res = json.loads(out.read_text(encoding="utf-8"))
    assert [r["reference"]["basis"] for r in res["rows"]] == ["schedule", "dwg_outline"]
    assert res["reference_file"] and res["reference_rows_unused"] == ["9"]


@pytest.mark.parametrize("delta,code", [(0.099, 0), (0.101, 1)])
def test_reference_tolerance_edge(tmp_path, delta, code):
    report, rb, out = make_case(tmp_path, {1: [3.9 + delta, 2.5, 0.45]})
    ref = write_ref(tmp_path, {"1": ref_row([3.9, 2.5, 0.45])})
    assert run(report, rb, out, "--reference", str(ref)) == code


@pytest.mark.parametrize("rows,needle", [
    ({"2": ref_row([3.9, 2.5, 0.45])}, "row 1"),
    ({"1": ref_row([float("nan"), 2.5, 0.45])}, "row 1"),
    ({"1": ref_row([3.9, 2.5])}, "row 1"),
    ({"1": ref_row([3.9, -2.5, 0.45])}, "row 1"),
    ({"1": ref_row([3.9, 2.5, 0.45], basis="guess")}, "basis"),
    ({"1": ref_row([3.9, 2.5, 0.45], source="")}, "source"),
    ({}, "row 1"),
])
def test_bad_reference_is_an_error_and_writes_nothing(tmp_path, capsys, rows, needle):
    report, rb, out = make_case(tmp_path, {1: [3.9, 2.5, 0.45]})
    ref = write_ref(tmp_path, rows)
    assert run(report, rb, out, "--reference", str(ref)) == 2
    assert not out.exists()
    assert needle in capsys.readouterr().err


def test_empty_build_report_is_an_error(tmp_path):
    report, rb, out = make_case(tmp_path, {})
    assert run(report, rb, out) == 2
    assert not out.exists()


def test_missing_readback_is_an_error_naming_it(tmp_path, capsys):
    report, rb, out = make_case(tmp_path, DIMS)
    (rb / "vpm_SET_02.json").unlink()
    assert run(report, rb, out) == 2
    assert not out.exists() and "vpm_SET_02.json" in capsys.readouterr().err


@pytest.mark.parametrize("target", ["report", "existing", "reference"])
def test_output_onto_an_input_or_existing_file_is_refused(tmp_path, target):
    report, rb, out = make_case(tmp_path, DIMS)
    ref = write_ref(tmp_path, {"1": ref_row([3.9, 2.5, 0.45]), "2": ref_row([6.25, 0.6, 0.45])})
    if target == "existing":
        out.write_text("keep", encoding="utf-8")
    dest = {"report": report, "existing": out, "reference": ref}[target]
    before = dest.read_bytes()
    assert run(report, rb, dest, "--reference", str(ref)) == 2
    assert dest.read_bytes() == before


@pytest.mark.parametrize("parent_kind", ["missing", "file"])
@pytest.mark.parametrize("gate_fails", [False, True])
def test_unwritable_output_is_refused(tmp_path, parent_kind, gate_fails):
    readback = {(1, "npm"): [3.9, 2.9, 0.45]} if gate_fails else None
    report, rb, _ = make_case(tmp_path, DIMS, readback)
    parent = tmp_path / "blocked"
    if parent_kind == "file":
        parent.write_text("keep", encoding="utf-8")
    out = parent / "checks.json"
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    proc = subprocess.run([sys.executable, str(TOOL), str(report), str(rb), str(out)],
                          capture_output=True, text=True, cwd=ROOT)
    assert proc.returncode == 2, proc.stderr
    assert proc.stderr.startswith("error: ") and str(out) in proc.stderr
    assert "Traceback" not in proc.stderr and not proc.stdout
    assert not out.exists()
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before


def test_fresh_process_exit_codes(tmp_path):
    ok_dir, bad_dir = tmp_path / "ok", tmp_path / "bad"
    ok_dir.mkdir(), bad_dir.mkdir()
    cases = [(make_case(ok_dir, DIMS), 0), (make_case(bad_dir, DIMS, {(1, "npm"): [3.9, 2.9, 0.45]}), 1)]
    for (report, rb, out), code in cases:
        proc = subprocess.run([sys.executable, str(TOOL), str(report), str(rb), str(out)],
                              capture_output=True, text=True, cwd=ROOT)
        assert proc.returncode == code, proc.stderr
        assert json.loads(out.read_text(encoding="utf-8"))["verdict"] == ("pass" if code == 0 else "fail")


def test_probe_exit_code_iff_any_axis_over_tolerance(tmp_path):
    """Generated probe: 120 random cases, 2 rows x 2 roles, readback deviates up to 0.2 m on random axes."""
    rng = random.Random(817)
    for i in range(120):
        case = tmp_path / f"c{i}"
        case.mkdir()
        readback, want_fail = {}, False
        for row, d in DIMS.items():
            for role in ("npm", "vpm"):
                dev = [rng.choice([0.0, rng.uniform(-0.2, 0.2)]) for _ in range(3)]
                if any(abs(x) > 0.1 + 1e-9 for x in dev):
                    want_fail = True
                elif any(abs(abs(x) - 0.1) < 1e-6 for x in dev):
                    dev = [0.0, 0.0, 0.0]  # skip the float-ambiguous exact threshold in the random probe
                readback[(row, role)] = [max(0.01, d[k] + dev[k]) for k in range(3)]
        report, rb, out = make_case(case, DIMS, readback)
        assert run(report, rb, out) == (1 if want_fail else 0), (i, readback)


def test_verona_reference_matches_recorded_plan_shapes():
    """The committed Verona reference: rows 1-6 = schedule (axis order of the plan), 7-10 = DWG outline."""
    ref = json.loads((ROOT / "jobs/VATUTINO-SITE/maf/verona-reference-sizes.json").read_text(encoding="utf-8"))
    shapes = json.loads((ROOT / "jobs/VATUTINO-SITE/maf/verona-plan-shapes.json").read_text(encoding="utf-8"))
    cfg = json.loads((ROOT / "jobs/VATUTINO-SITE/maf/verona-gen.config.json").read_text(encoding="utf-8"))
    assert sorted(ref["rows"], key=int) == [str(r["row"]) for r in cfg["rows"]]
    for key, r in ref["rows"].items():
        shape = shapes["rows"][key]
        dwg = "size_basis" in shape
        assert r["basis"] == ("dwg_outline" if dwg else "schedule"), key
        assert r["size_m"][2] == 0.45 and r["source"]
        sched = sorted(v / 1000 for v in shape["schedule_LxWxH_mm"][:2] if v)
        if not dwg:
            assert sorted(r["size_m"][:2]) == pytest.approx(sched), key
        else:
            assert r["size_m"][:2] == shape["plan_dims_m"] and shape["polyline_handle"] in r["source"], key
        assert all(abs(a - b) <= 0.10 for a, b in zip(r["size_m"][:2], shape["plan_dims_m"])), key
        assert all(math.isfinite(v) and v > 0 for v in r["size_m"])
