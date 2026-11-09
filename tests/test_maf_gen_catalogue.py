"""Library entries for generated «Верона» benches (#1046, [D202]) and the steel_ral7016 -> paint_ral7016 rename.

Pattern: new-case (tests of tools/library/maf_gen_catalogue.py, generated MAF rows into the MAF catalogue).
Synthetic build folders (marked SYNTHETIC in the build report) drive the fail-closed cases; the committed
library files are checked as they are.
"""
from __future__ import annotations

import copy
import importlib.util
import itertools
import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/library/maf_gen_catalogue.py"
_spec = importlib.util.spec_from_file_location("maf_gen_catalogue", TOOL)
gc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gc)

MATERIALS = json.loads((ROOT / "library/materials/materials_v001.json").read_text(encoding="utf-8"))
CATALOGUE = json.loads((ROOT / "library/maf/catalogue.json").read_text(encoding="utf-8"))
USED = ("larch_light_oak_boards", "paint_ral7016")


# ---- synthetic build folder ---------------------------------------------------------------------------------
def _geometry(length, materials=USED):
    return {"vertices": [[0, 0, 0], [length, 0, 0], [length, 0.6, 0.45]], "polygons": [[0, 1, 2]],
            "polygon_material": ["MAF_" + m for m in materials], "uv": [[0, 0]], "polygon_uv": [[0]]}


def _build(tmp_path, lengths, *, materials=USED):
    """SYNTHETIC build folder: one row per length (rows 1..n); equal lengths = identical models."""
    d = tmp_path / "build"
    (d / "readback").mkdir(parents=True)
    rows, checks = [], []
    for i, length in enumerate(lengths, 1):
        sid = f"VAT_MAF_T3508_{i:02d}"
        rows.append({"row": i, "set_id": sid, "block": f"SYNTHETIC block {i}",
                     "generator_facts": {"dims_m": [length, 0.6, 0.45], "faces": 10, "tris": 20},
                     "npm": {"tris": 20, "fbx": f"{d}/npm/{sid}.fbx", "sha256": f"{i:064x}"},
                     "vpm": {"tris": 20, "fbx": f"{d}/vpm/{sid}.fbx", "sha256": f"{i + 100:064x}"}})
        side = {"dimension": "pass", "maf_findings_counts": {"pass": 3},
                "uv_slots": {"faces_outside": 0, "materials": {m: {"faces": 5, "outside": 0} for m in materials}}}
        checks.append({"row": i, "set_id": sid, "npm": copy.deepcopy(side), "vpm": copy.deepcopy(side)})
        for p in ("npm", "vpm"):
            mesh = {"name": sid + "_GroundEl", "triangles": 20, "face_geometry": _geometry(length, materials)}
            (d / "readback" / f"{p}_{sid}.json").write_text(json.dumps({"meshes": [mesh]}), encoding="utf-8")
            (d / "readback" / f"xview_{p}_{sid}.json").write_text(json.dumps({"passed": True}), encoding="utf-8")
    (d / "build-report.json").write_text(json.dumps({"config": "SYNTHETIC", "form": "clad_box", "rows": rows}),
                                         encoding="utf-8")
    (d / "checks.json").write_text(json.dumps({"verdict": "pass", "failures": [], "rows": checks}), encoding="utf-8")
    return d


def _make(d, approved, materials=MATERIALS):
    return gc.build_generated(gc.load_build(d), approved, materials, decision="D202")


def _edit(path, fn):
    doc = json.loads(path.read_text(encoding="utf-8"))
    fn(doc)
    path.write_text(json.dumps(doc), encoding="utf-8")


# ---- committed library ---------------------------------------------------------------------------------------
def test_catalogue_has_rows_2_to_10_and_no_row_1():
    gen = CATALOGUE["generated"]
    rows = sorted(r for e in gen for r in e["schedule_rows"])
    assert rows == list(range(2, 11))
    assert [d["row"] for d in CATALOGUE["generated_dropped"]] == [1]
    assert "approved" in CATALOGUE["generated_dropped"][0]["reason"]
    ids = [e["id"] for e in gen] + [e["id"] for e in CATALOGUE["entries"]]
    assert len(ids) == len(set(ids))
    assert len(gen) == 8  # rows 9 and 10 are one model
    assert next(e for e in gen if 9 in e["schedule_rows"])["schedule_rows"] == [9, 10]
    assert all("[D202]" in e["approval"] for e in gen)


def test_catalogue_materials_exist_in_library():
    keys = {m["key"]: m["library_id"] for m in MATERIALS["materials"]}
    for e in CATALOGUE["generated"]:
        assert e["materials"] == {"larch_light_oak_boards": keys["larch_light_oak_boards"],
                                  "paint_ral7016": keys["paint_ral7016"]}
        assert "rows-v006p-3" in e["npm"]["fbx"] and len(e["npm"]["sha256"]) == 64


def test_catalogue_md_lists_every_generated_entry():
    md = (ROOT / "library/maf/catalogue.md").read_text(encoding="utf-8")
    section = md.split(gc.MD_BEGIN)[1].split(gc.MD_END)[0]
    for e in CATALOGUE["generated"]:
        assert f"| {e['id']} |" in section
    assert "VAT_MAF_T3508_01" in section and "not approved" in section


def test_materials_library_has_boards_once_and_pointer_matches():
    keys = [m["key"] for m in MATERIALS["materials"]]
    assert keys.count("larch_light_oak_boards") == 1 and "paint_ral7016" in keys
    ids = [m["library_id"] for m in MATERIALS["materials"]]
    assert len(ids) == len(set(ids))
    spec = importlib.util.spec_from_file_location("agr_tools_matlib_core_1046",
                                                  ROOT / "adapters/max/agr_tools/matlib_core.py")
    ml = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ml)
    ral = ml.ral_table(ROOT / "tools/materials/ral_classic.json")
    ml.validate_library(MATERIALS, ral)
    ml.load_library(ROOT / "library/materials/materials.json")  # pointer sha256 matches the edited file


def test_generator_config_and_proposal_use_paint_ral7016():
    cfg = json.loads((ROOT / "jobs/VATUTINO-SITE/maf/verona-gen.config.json").read_text(encoding="utf-8"))
    assert cfg["materials"] == {"seat": "larch_light_oak_boards", "frame": "paint_ral7016"}
    prop = json.loads((ROOT / "jobs/VATUTINO-SITE/maf/verona-material-ids-v006-proposal.json")
                      .read_text(encoding="utf-8"))
    names = [m["name"] for m in prop["added"]] + [m["name"] for m in prop["material_list"]["materials"]]
    assert "steel_ral7016" not in names and "paint_ral7016" in names


# ---- tool: happy path and dedupe -----------------------------------------------------------------------------
def test_identical_rows_make_one_entry(tmp_path):
    d = _build(tmp_path, [2.0, 6.25, 2.0, 4.9])
    out = _make(d, {1, 2, 3, 4})
    assert [e["schedule_rows"] for e in out["generated"]] == [[1, 3], [2], [4]]
    assert out["generated_dropped"] == []


def test_unapproved_rows_go_to_drop_list(tmp_path):
    d = _build(tmp_path, [3.9, 6.7, 6.25])
    out = _make(d, {2, 3})
    assert [r["row"] for r in out["generated_dropped"]] == [1]
    assert sorted(r for e in out["generated"] for r in e["schedule_rows"]) == [2, 3]


def test_probe_every_row_ends_in_entry_or_drop(tmp_path):
    """Brute force: every subset of 5 rows with random duplicate lengths; each row exactly once in the output."""
    rng = random.Random(1046)
    d = _build(tmp_path, [rng.choice([2.0, 4.0, 6.0]) for _ in range(5)])
    build = gc.load_build(d)
    n = 0
    for k in range(1, 6):
        for approved in itertools.combinations(range(1, 6), k):
            out = gc.build_generated(build, set(approved), MATERIALS, decision="D202")
            got = [r for e in out["generated"] for r in e["schedule_rows"]] + [r["row"] for r in
                                                                               out["generated_dropped"]]
            assert sorted(got) == [1, 2, 3, 4, 5]
            ids = [e["id"] for e in out["generated"]]
            assert len(ids) == len(set(ids))
            n += 1
    assert n == 31


# ---- tool: fail closed ---------------------------------------------------------------------------------------
def test_unmapped_material_is_error_naming_it(tmp_path):
    d = _build(tmp_path, [2.0], materials=("larch_light_oak_boards", "steel_ral7016"))
    with pytest.raises(ValueError, match="steel_ral7016"):
        _make(d, {1})


@pytest.mark.parametrize("approved,match", [(set(), "no approved rows"), ({0}, "not in the build"),
                                            ({11}, "not in the build")])
def test_approved_rows_must_exist(tmp_path, approved, match):
    d = _build(tmp_path, [2.0, 3.0])
    with pytest.raises(ValueError, match=match):
        _make(d, approved)


@pytest.mark.parametrize("mutate,match", [
    (lambda c: c.update(verdict="fail"), "verdict"),
    (lambda c: c["rows"][0]["npm"].update(dimension="fail"), "dimension"),
    (lambda c: c["rows"][0]["vpm"]["maf_findings_counts"].update(not_run=1), "maf_findings"),
    (lambda c: c["rows"][0]["npm"]["uv_slots"].update(faces_outside=1), "outside"),
    (lambda c: c["rows"].pop(0), "no checks row"),
])
def test_failing_or_missing_checks_are_errors(tmp_path, mutate, match):
    d = _build(tmp_path, [2.0])
    _edit(d / "checks.json", mutate)
    with pytest.raises(ValueError, match=match):
        _make(d, {1})


def test_unapproved_row_may_fail_checks(tmp_path):
    d = _build(tmp_path, [2.0, 3.0])
    _edit(d / "checks.json", lambda c: c["rows"][0]["npm"].update(dimension="fail"))
    assert [r["row"] for r in _make(d, {2})["generated_dropped"]] == [1]


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), 0.0, -1.0])
def test_non_finite_or_non_positive_dims_are_errors(tmp_path, bad):
    d = _build(tmp_path, [2.0])
    _edit(d / "build-report.json", lambda r: r["rows"][0]["generator_facts"].update(dims_m=[bad, 0.6, 0.45]))
    with pytest.raises(ValueError, match="dims_m"):
        _make(d, {1})


def test_xview_not_passed_or_missing_is_error(tmp_path):
    d = _build(tmp_path, [2.0])
    (d / "readback" / "xview_vpm_VAT_MAF_T3508_01.json").write_text(json.dumps({"passed": False}), encoding="utf-8")
    with pytest.raises(ValueError, match="xview"):
        _make(d, {1})
    (d / "readback" / "xview_vpm_VAT_MAF_T3508_01.json").unlink()
    with pytest.raises(ValueError, match="xview"):
        _make(d, {1})


def test_duplicate_row_in_report_is_error(tmp_path):
    d = _build(tmp_path, [2.0, 3.0])
    _edit(d / "build-report.json", lambda r: r["rows"][1].update(row=1))
    with pytest.raises(ValueError, match="duplicate row"):
        _make(d, {1})


def test_readback_material_disagreeing_with_checks_is_error(tmp_path):
    d = _build(tmp_path, [2.0])
    _edit(d / "readback" / "npm_VAT_MAF_T3508_01.json",
          lambda r: r["meshes"][0]["face_geometry"].update(polygon_material=["MAF_steel_ral7047"]))
    with pytest.raises(ValueError, match="readback materials"):
        _make(d, {1})


def test_parse_rows():
    assert gc.parse_rows("2-4,7") == {2, 3, 4, 7}
    for bad in ("", "4-2", "a", "0", "1-"):
        with pytest.raises(ValueError):
            gc.parse_rows(bad)


# ---- CLI: paths ----------------------------------------------------------------------------------------------
def _cli(*args):
    return subprocess.run([sys.executable, str(TOOL), *map(str, args)], capture_output=True, text=True)


def _inputs(tmp_path):
    cat = tmp_path / "catalogue.json"
    cat.write_text(json.dumps({"entries": [{"id": "MAF_0001"}], "counts": {}}), encoding="utf-8")
    md = tmp_path / "catalogue.md"
    md.write_text("# MAF catalogue\n", encoding="utf-8")
    mats = tmp_path / "materials.json"
    mats.write_text(json.dumps(MATERIALS), encoding="utf-8")
    return cat, md, mats


def test_cli_writes_and_rerun_replaces_section(tmp_path):
    d = _build(tmp_path, [2.0, 6.0, 2.0])
    cat, md, mats = _inputs(tmp_path)
    out_j, out_m = tmp_path / "o.json", tmp_path / "o.md"
    args = ["--build-dir", d, "--approve", "2-3", "--decision", "D202", "--materials", mats, "--catalogue", cat,
            "--catalogue-md", md, "--out-json", out_j, "--out-md", out_m]
    r = _cli(*args)
    assert r.returncode == 0, r.stderr
    doc = json.loads(out_j.read_text(encoding="utf-8"))
    assert doc["entries"] == [{"id": "MAF_0001"}] and [e["schedule_rows"] for e in doc["generated"]] == [[2], [3]]
    # second run from the first output: one section, not two
    out_j2, out_m2 = tmp_path / "o2.json", tmp_path / "o2.md"
    r = _cli("--build-dir", d, "--approve", "2-3", "--decision", "D202", "--materials", mats, "--catalogue", out_j,
             "--catalogue-md", out_m, "--out-json", out_j2, "--out-md", out_m2)
    assert r.returncode == 0, r.stderr
    assert out_m2.read_text(encoding="utf-8").count(gc.MD_BEGIN) == 1
    assert json.loads(out_j2.read_text(encoding="utf-8")) == doc


@pytest.mark.parametrize("which", ["json", "md", "json_md_same", "alias"])
def test_cli_output_aliasing_an_input_exits_nonzero_and_writes_nothing(tmp_path, which):
    d = _build(tmp_path, [2.0])
    cat, md, mats = _inputs(tmp_path)
    before = {p: p.read_bytes() for p in (cat, md, mats)}
    out_j, out_m = tmp_path / "o.json", tmp_path / "o.md"
    if which == "json":
        out_j = cat
    elif which == "md":
        out_m = md
    elif which == "json_md_same":
        out_m = out_j
    else:
        out_j = tmp_path / "sub" / ".." / "catalogue.json"
    r = _cli("--build-dir", d, "--approve", "1", "--decision", "D202", "--materials", mats, "--catalogue", cat,
             "--catalogue-md", md, "--out-json", out_j, "--out-md", out_m)
    assert r.returncode != 0
    assert {p: p.read_bytes() for p in (cat, md, mats)} == before
    assert not (tmp_path / "o.json").exists() and not (tmp_path / "o.md").exists()


def test_cli_error_exits_nonzero_and_writes_nothing(tmp_path):
    d = _build(tmp_path, [2.0], materials=("larch_light_oak_boards", "steel_ral7016"))
    cat, md, mats = _inputs(tmp_path)
    out_j, out_m = tmp_path / "o.json", tmp_path / "o.md"
    r = _cli("--build-dir", d, "--approve", "1", "--decision", "D202", "--materials", mats, "--catalogue", cat,
             "--catalogue-md", md, "--out-json", out_j, "--out-md", out_m)
    assert r.returncode != 0 and "steel_ral7016" in r.stderr
    assert not out_j.exists() and not out_m.exists()


@pytest.mark.parametrize("which", ["catalogue", "catalogue_md", "materials"])
def test_cli_input_named_like_out_partial_is_untouched(tmp_path, which):
    """P1-1 (PR #1093 review): an input at <out>.partial survives; temp names are unique, never <out>.partial."""
    d = _build(tmp_path, [2.0, 6.0, 2.0])
    cat, md, mats = _inputs(tmp_path)
    out_j, out_m = tmp_path / "o.json", tmp_path / "o.md"
    target = {"catalogue": out_j, "catalogue_md": out_m, "materials": out_j}[which]
    src = {"catalogue": cat, "catalogue_md": md, "materials": mats}[which]
    moved = target.with_name(target.name + ".partial")
    src.replace(moved)
    cat, md, mats = (moved if p == src else p for p in (cat, md, mats))
    # an unrelated pre-existing <out>.partial of the other output must not be clobbered either
    other = out_m if target == out_j else out_j
    other_partial = other.with_name(other.name + ".partial")
    other_partial.write_bytes(b"unrelated")
    watched = (cat, md, mats, other_partial)
    before = {p: p.read_bytes() for p in watched}
    r = _cli("--build-dir", d, "--approve", "2-3", "--decision", "D202", "--materials", mats, "--catalogue", cat,
             "--catalogue-md", md, "--out-json", out_j, "--out-md", out_m)
    assert r.returncode == 0, r.stderr
    assert {p: p.read_bytes() for p in watched} == before
    assert [e["schedule_rows"] for e in json.loads(out_j.read_text(encoding="utf-8"))["generated"]] == [[2], [3]]
    left = {p.name for p in tmp_path.iterdir() if p.is_file()} - {p.name for p in (*watched, out_j, out_m)}
    assert not left, f"temp files left behind: {left}"


@pytest.mark.parametrize("which", ["json", "md", "json_md_same", "alias"])
def test_cli_alias_with_input_named_like_out_partial(tmp_path, which):
    """P1-1 combined with the earlier alias fixes: the alias is still rejected, the .partial-named input untouched."""
    d = _build(tmp_path, [2.0])
    cat, md, mats = _inputs(tmp_path)
    out_j, out_m = tmp_path / "o.json", tmp_path / "o.md"
    cat.replace(tmp_path / "o.json.partial")
    cat = tmp_path / "o.json.partial"
    if which == "json":
        out_j = cat
    elif which == "md":
        out_m = md
    elif which == "json_md_same":
        out_m = out_j
    else:
        out_j = tmp_path / "sub" / ".." / "o.json.partial"
    before = {p: p.read_bytes() for p in (cat, md, mats)}
    r = _cli("--build-dir", d, "--approve", "1", "--decision", "D202", "--materials", mats, "--catalogue", cat,
             "--catalogue-md", md, "--out-json", out_j, "--out-md", out_m)
    assert r.returncode != 0
    assert {p: p.read_bytes() for p in (cat, md, mats)} == before
    assert not (tmp_path / "o.json").exists() and not (tmp_path / "o.md").exists()
