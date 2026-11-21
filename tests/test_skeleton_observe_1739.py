"""new-case: observe week of the verifier + mesh-quality steps in the OKS skeletons (#1739).

Acceptance table (every row is a test here):
- `mesh-quality` stage at the end of `body` (right after it) in oks-vpm and oks-npm, nowhere else -> test_skeleton_mesh_*
- `verifier` right after `readback` in oks-npm with `verifier_mode` config key -> test_skeleton_oks_npm_verifier
- per-facade-cell defect signal (#1724 "would change"): a local corner defect is not averaged away -> test_cells_*
- every measured face ends in a facade cell, the non-facade bucket or the degenerate bucket -> test_cells_accounting
- empty / NaN / inf / bad cell size / unmapped object -> error, never a clean signal -> test_cells_fail_closed
- stage CLI writes mesh_quality.json, observe only: a failing master still exits 0 with returns_work=false;
  there is no return/threshold option at all -> test_stage_*
- output aliases the input or exists -> exit 2, nothing written -> test_stage_paths
- verifier fix mode in an oks-npm job is refused without the skeleton.json opt-in -> test_optin_*
- one sheet line (verifier + mesh-quality) for every sheet sent to Artem; bad report -> error -> test_sheet_line_*
- weekly digest line for the status push; empty root -> exit 2 -> test_digest_*
No Blender and no VLM call here (recorded geometry dumps, built verifier reports).
"""
import importlib.util
import json
import math
import random
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "qa"))


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


vf = _load("verifier", "tools/qa/verifier.py")
vs = _load("verifier_summary", "tools/qa/verifier_summary.py")
mqo = _load("mesh_quality_observe", "tools/qa/mesh_quality_observe.py")
core = mqo.mqs.load_core()
SK = json.loads((ROOT / "docs/agents/skeletons.json").read_text(encoding="utf-8"))
FAC = {"south": "2-1", "north": "1-2", "east": "Б-А", "west": "А-Б"}


# ------------------------------------------------------------------ fixtures

def _wall(nx=6, nz=3, skew=None, name="Body", tris=False):
    """A south facade (normal -Y) of nx x nz quads, 1 m each; skew={(i, k): dx} drags one top corner."""
    verts, faces = [], []
    idx = {}
    for i in range(nx + 1):
        for k in range(nz + 1):
            idx[i, k] = len(verts)
            verts.append([float(i), 0.0, float(k)])
    for i in range(nx):
        for k in range(nz):
            a, b, c, d = idx[i, k], idx[i + 1, k], idx[i + 1, k + 1], idx[i, k + 1]
            if skew and (i, k) in skew:
                verts.append([verts[c][0] + skew[i, k], 0.0, verts[c][2]])
                c = len(verts) - 1
            if tris:
                faces += [[a, b, c], [a, c, d]]
            else:
                faces.append([a, b, c, d])
    return {"name": name, "verts": verts, "faces": faces, "materials": ["M"] * len(faces)}


def _dump(tmp_path, objects, name="dump.json"):
    p = tmp_path / name
    p.write_text(json.dumps({"objects": objects}), encoding="utf-8")
    return p


def _verifier_doc():
    items = vf.checklist_items(FAC)
    ans = [{"id": i["id"], "defect": i["id"] == "A05", "note": ""} for i in items]
    fw = vf.parse_answers(items, ans)
    m = vf.parse_material_scores([{"axis": a, "score": 2 if a == "base_color" else 5, "reason": f"{a} ok"}
                                  for a in vf.MATERIAL_AXES])
    return vf.build_report(job="jobs/X", mode="observe", round_no=1, renders="R", slide="S.png", facades=FAC,
                           items=items, forward=fw, reverse=fw, mat_forward=m, mat_reverse=m,
                           vlm={"model": "fake", "cost_usd": 0.0, "duration_s": 0.0})


# ------------------------------------------------------------------ skeleton wiring

def test_skeleton_mesh_quality_right_after_body_only_in_oks_cells():
    assert "mesh-quality" in SK["stages"]
    st = SK["stages"]["mesh-quality"]
    assert st["gap"] is None and "tools/qa/mesh_quality_observe.py" in st["owners"]
    assert "observe" in st["ru"] and "mesh_quality_observe.py stage" in st["calls"]
    cells = {c for c, s in SK["cells"].items() if "mesh-quality" in s["stages"]}
    assert cells == {"oks-vpm", "oks-npm"}
    for cell in cells:
        stages = SK["cells"][cell]["stages"]
        assert stages.count("mesh-quality") == 1
        assert stages.index("mesh-quality") == stages.index("body") + 1


def test_skeleton_oks_npm_verifier():
    spec = SK["cells"]["oks-npm"]
    assert spec["stages"].count("verifier") == 1
    assert spec["stages"].index("verifier") == spec["stages"].index("readback") + 1
    assert "verifier_mode" in spec["config_keys"]
    assert "tools/blender/verifier_views.py" in SK["stages"]["verifier"]["owners"]


def test_skeleton_doc_rows():
    doc = (ROOT / "docs/agents/SKELETONS.md").read_text(encoding="utf-8")
    npm = doc.split("### `oks-npm`", 1)[1].split("###", 1)[0]
    vpm = doc.split("### `oks-vpm`", 1)[1].split("###", 1)[0]
    for part in (npm, vpm):
        assert "`mesh-quality`" in part
    assert "`verifier`" in npm
    assert "--sheet-line" in doc and "--digest" in doc


# ------------------------------------------------------------------ per-facade-cell defect signal

def test_cells_clean_wall_has_no_defect():
    sig = mqo.cell_defects([_wall()])
    assert sig["defect_faces"] == 0 and sig["max_cell_defect_faces"] == 0 and sig["worst"] == []
    assert sig["facade_faces"] == 18


def test_cells_local_corner_defect_is_not_averaged_away():
    """#1724: 63C v001 lost its corner defect in the whole-body area share; the cell keeps it."""
    skew = {(0, 0): 0.6, (0, 1): 0.6, (0, 2): 0.6}       # three skewed quads in the corner column
    big = _wall(nx=60, nz=3, skew=skew)
    sig = mqo.cell_defects([big], cell_m=3.0)
    assert sig["defect_faces"] == 3
    assert sig["max_cell_defect_faces"] == 3
    w = sig["worst"][0]
    assert w["side"] == "-Y" and w["u"] == 0 and w["z"] == 0 and w["defect_faces"] == 3
    # the body-wide share is small, the cell share is not
    assert sig["defect_faces"] / sig["facade_faces"] < 0.02 and w["defect_faces"] / w["faces"] > 0.3


def test_cells_triangles_in_quad_master_count_but_not_in_triangulated_input():
    mixed = _wall()
    mixed["faces"][0:1] = [[mixed["faces"][0][0], mixed["faces"][0][1], mixed["faces"][0][2]],
                           [mixed["faces"][0][0], mixed["faces"][0][2], mixed["faces"][0][3]]]
    mixed["materials"] = ["M"] * len(mixed["faces"])
    s1 = mqo.cell_defects([mixed])
    assert s1["triangulated_input"] is False and s1["defect_faces"] == 2
    s2 = mqo.cell_defects([_wall(tris=True)])
    assert s2["triangulated_input"] is True and s2["defect_faces"] == 0


def test_cells_accounting_generated_probe():
    rng = random.Random(1739)
    for _ in range(40):
        skew = {(rng.randrange(8), rng.randrange(4)): rng.choice([0.05, 0.4, 0.9]) for _ in range(rng.randrange(6))}
        w = _wall(nx=8, nz=4, skew=skew)
        roof = {"name": "Roof", "verts": [[0, 0, 4], [1, 0, 4], [1, 1, 4], [0, 1, 4], [0, 0, 4]],
                "faces": [[0, 1, 2, 3], [0, 1, 4]], "materials": ["R", "R"]}   # one degenerate (zero area)
        sig = mqo.cell_defects([w, roof], cell_m=rng.choice([1.0, 2.5, 3.0]))
        assert sig["facade_faces"] + sig["non_facade_faces"] + sig["degenerate_faces"] == sig["measured_faces"] == 34
        assert sum(c["defect_faces"] for c in sig["cells_all"]) == sig["facade_defect_faces"]
        # quad-only facade: irregular faces agree with the shared core
        ref = core.score([w])["objects"][0]["irregular_faces"]
        assert sig["facade_defect_faces"] == ref


@pytest.mark.parametrize("objects,kw,match", [
    ([], {}, "no measured faces"),
    ([{"name": "UCX_A", "verts": [[0, 0, 0], [1, 0, 0], [1, 0, 1]], "faces": [[0, 1, 2]], "materials": ["M"]}], {},
     "no measured faces"),
    ([{"name": "B", "verts": [[0, 0, 0], [1, 0, float("nan")], [1, 0, 1]], "faces": [[0, 1, 2]],
       "materials": ["M"]}], {}, "non-finite"),
    ([{"name": "B", "verts": [[0, 0, 0], [1, 0, float("inf")], [1, 0, 1]], "faces": [[0, 1, 2]],
       "materials": ["M"]}], {}, "non-finite"),
    ([{"name": "B", "verts": [[0, 0, 0], [1, 0, 0]], "faces": [[0, 1, 5]], "materials": ["M"]}], {}, "vertex index"),
    ([{"name": "B", "faces": [[0, 1, 2]]}], {}, "verts"),
    ([_wall()], {"cell_m": 0}, "cell_m"),
    ([_wall()], {"cell_m": float("nan")}, "cell_m"),
    ([_wall()], {"cell_m": float("inf")}, "cell_m"),
    ([_wall()], {"cell_m": -3.0}, "cell_m"),
    ([_wall()], {"cell_m": True}, "cell_m"),
])
def test_cells_fail_closed(objects, kw, match):
    with pytest.raises(ValueError, match=match):
        mqo.cell_defects(objects, **kw)


def test_cells_collision_hull_is_reported_dropped():
    ucx = {"name": "UCX_Body", "verts": [[0, 0, 0], [1, 0, 0], [1, 0, 1]], "faces": [[0, 1, 2]], "materials": ["M"]}
    sig = mqo.cell_defects([_wall(), ucx])
    assert sig["dropped"] == [{"name": "UCX_Body", "reason": "collision hull (UCX_)"}]


# ------------------------------------------------------------------ stage CLI (observe only)

def _stage(argv):
    return subprocess.run([sys.executable, str(ROOT / "tools/qa/mesh_quality_observe.py"), "stage", *argv],
                          capture_output=True, text=True, encoding="utf-8", cwd=ROOT)


def test_stage_writes_observe_report_fresh_cli(tmp_path):
    src = _dump(tmp_path, [_wall(skew={(0, 0): 0.6})])
    out = tmp_path / "mesh_quality.json"
    p = _stage([str(src), "--out", str(out)])
    assert p.returncode == 0, p.stderr
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["schema"] == mqo.STAGE_SCHEMA and doc["mode"] == "observe" and doc["returns_work"] is False
    assert doc["status"] == "measured" and 0 <= doc["score"] <= 100
    assert doc["cells"]["max_cell_defect_faces"] == 1 and doc["input"]["sha256"]
    assert mqo.validate_stage_report(doc) is doc
    assert not list(tmp_path.glob("*.partial"))


def test_stage_failing_master_still_observe_exit_0(tmp_path):
    ngon = {"name": "Body", "verts": [[0, 0, 0], [1, 0, 0], [2, 0, 0.5], [1, 0, 1], [0, 0, 1]],
            "faces": [[0, 1, 2, 3, 4]], "materials": ["M"]}
    out = tmp_path / "mq.json"
    p = _stage([str(_dump(tmp_path, [ngon])), "--out", str(out)])
    assert p.returncode == 0, p.stderr
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["status"] == "fail" and doc["returns_work"] is False


@pytest.mark.parametrize("opt", [["--mode", "return"], ["--threshold", "80"], ["--return-below", "80"]])
def test_stage_has_no_return_option(tmp_path, opt):
    out = tmp_path / "mq.json"
    p = _stage([str(_dump(tmp_path, [_wall()])), "--out", str(out), *opt])
    assert p.returncode == 2 and not out.exists()


def test_stage_paths(tmp_path):
    src = _dump(tmp_path, [_wall()])
    before = src.read_bytes()
    p = _stage([str(src), "--out", str(src)])
    assert p.returncode == 2 and src.read_bytes() == before
    alias = tmp_path / "sub" / ".." / "dump.json"
    (tmp_path / "sub").mkdir()
    p = _stage([str(src), "--out", str(alias)])
    assert p.returncode == 2 and src.read_bytes() == before
    out = tmp_path / "mq.json"
    out.write_text("{}", encoding="utf-8")
    p = _stage([str(src), "--out", str(out)])
    assert p.returncode == 2 and out.read_text(encoding="utf-8") == "{}"
    p = _stage([str(tmp_path / "missing.json"), "--out", str(tmp_path / "n.json")])
    assert p.returncode == 2 and not (tmp_path / "n.json").exists()


def test_stage_report_validator_fail_closed(tmp_path):
    src = _dump(tmp_path, [_wall()])
    out = tmp_path / "mq.json"
    assert _stage([str(src), "--out", str(out)]).returncode == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    for bad in ({"returns_work": True}, {"mode": "return"}, {"schema": "x"}, {"score": float("nan")},
                {"score": None}, {"cells": {}}):
        with pytest.raises(ValueError):
            mqo.validate_stage_report({**doc, **bad})


# ------------------------------------------------------------------ explicit opt-in (verifier in oks-npm)

def _npm_job(tmp_path, config):
    job = tmp_path / "jobs" / "J"
    job.mkdir(parents=True)
    (job / "skeleton.json").write_text(json.dumps({"scenario": "oks-npm", "config": config, "hooks": []}),
                                       encoding="utf-8")
    return job


@pytest.mark.parametrize("config", [{}, {"verifier_mode": "observe"}, {"verifier_mode": "FIX"}])
def test_optin_oks_npm_fix_refused_without_opt_in(tmp_path, config):
    with pytest.raises(vf.VerifierError, match="refused"):
        vf.resolve_mode(_npm_job(tmp_path, config), "fix", 1)


def test_optin_oks_npm_observe_default_and_explicit_fix(tmp_path):
    assert vf.resolve_mode(_npm_job(tmp_path, {}), "observe", 1) == ("observe", 1)
    assert vf.resolve_mode(_npm_job(tmp_path / "b", {"verifier_mode": "fix"}), "fix", 2) == ("fix", 2)


def test_optin_job_configs_of_this_card_are_observe():
    for rel in ("jobs/KPP1/verifier-1739/skeleton.json", "jobs/G22/verifier-1739/skeleton.json"):
        cfg = json.loads((ROOT / rel).read_text(encoding="utf-8"))
        assert cfg["config"].get("verifier_mode") == "observe", rel


# ------------------------------------------------------------------ sheet line + weekly digest

def _mq_doc(tmp_path, objects=None):
    out = tmp_path / "mesh_quality.json"
    assert _stage([str(_dump(tmp_path, objects or [_wall(skew={(0, 0): 0.6})])), "--out", str(out)]).returncode == 0
    return json.loads(out.read_text(encoding="utf-8"))


def test_sheet_line_one_line_with_both_results(tmp_path):
    line = vs.sheet_line(_verifier_doc(), _mq_doc(tmp_path))
    assert "\n" not in line and line.startswith("Verifier (observe):")
    assert "material:base_color" in line and "Mesh quality (observe):" in line
    assert "-Y u0 z0" in line and "1 defect" in line


def test_sheet_line_no_findings_and_clean_mesh(tmp_path):
    v = _verifier_doc()
    v["findings"], v["main_discrepancy"] = [], None
    line = vs.sheet_line(v, _mq_doc(tmp_path, [_wall()]))
    assert "main=none" in line and "worst cell none" in line


def test_sheet_line_fail_closed(tmp_path):
    good_v, good_m = _verifier_doc(), _mq_doc(tmp_path)
    with pytest.raises(vf.VerifierError):
        vs.sheet_line({**good_v, "edits_model": True}, good_m)
    with pytest.raises(vf.VerifierError):
        vs.sheet_line(good_v, {**good_m, "returns_work": True})


def test_sheet_line_cli(tmp_path):
    vp = tmp_path / "verifier.json"
    vp.write_text(json.dumps(_verifier_doc()), encoding="utf-8")
    _mq_doc(tmp_path)
    cmd = [sys.executable, str(ROOT / "tools/qa/verifier_summary.py"), "--sheet-line", "--verifier", str(vp),
           "--mesh-quality", str(tmp_path / "mesh_quality.json")]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 0 and p.stdout.count("\n") == 1 and p.stdout.startswith("Verifier (observe):")
    cmd[-1] = str(tmp_path / "missing.json")
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 2


def test_digest_line(tmp_path):
    job = tmp_path / "jobs" / "A"
    job.mkdir(parents=True)
    (job / "verifier.json").write_text(json.dumps(_verifier_doc()), encoding="utf-8")
    (job / "verifier_review.json").write_text(json.dumps(
        {"reviews": [{"verifier": "verifier.json", "artem_corrected": ["material:base_color"]}]}), encoding="utf-8")
    mq = _mq_doc(tmp_path)
    (job / "mesh_quality.json").write_text(json.dumps(mq), encoding="utf-8")
    line = vs.digest_line(tmp_path / "jobs")
    assert "\n" not in line and "1 runs" in line and "matched 1/1" in line and "mesh-quality 1" in line


def test_digest_empty_root_is_an_error(tmp_path):
    (tmp_path / "jobs").mkdir()
    p = subprocess.run([sys.executable, str(ROOT / "tools/qa/verifier_summary.py"), "--jobs",
                        str(tmp_path / "jobs"), "--digest"], capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 2


def test_digest_invalid_mesh_quality_report_is_an_error(tmp_path):
    job = tmp_path / "jobs" / "A"
    job.mkdir(parents=True)
    (job / "verifier.json").write_text(json.dumps(_verifier_doc()), encoding="utf-8")
    (job / "mesh_quality.json").write_text(json.dumps({"schema": "x"}), encoding="utf-8")
    with pytest.raises(vf.VerifierError, match="mesh_quality"):
        vs.digest_line(tmp_path / "jobs")
