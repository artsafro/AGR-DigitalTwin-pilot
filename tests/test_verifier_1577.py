"""new-case: verifier step before showing Artem (#1577): observe-mode VLM checklist + material rubric.

Acceptance table (every row is a test here):
- verifier stage right after readback in oks-vpm / ground-npm / ground-vpm, nowhere else -> test_skeleton_*
- material rubric fail-closed (missing / duplicate / unknown / non-integer / out of range / NaN / bad reason) -> test_rubric_*
- ONE main discrepancy, fix order missing -> base_color -> borders -> scale, threshold exactly at 3 -> test_main_*
- verifier.json schema (Python validator and schemas/Verifier.schema.json agree) -> test_report_*
- --mode fix refused without jobs/<ID>/skeleton.json opt-in, max 3 rounds -> test_mode_*
- CLI observe run with a fake VLM: writes verifier.json only, never touches inputs, overlap/exists refused -> test_cli_*
- summary: how often the main discrepancy matched Artem's correction, fail closed -> test_summary_*
- CrossProjection rule in model-maf / model-flora / scenario skills and SKELETONS.md -> test_docs_*
No real VLM call here.
"""
import hashlib
import importlib.util
import itertools
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


vf = _load("verifier", "tools/qa/verifier.py")
vs = _load("verifier_summary", "tools/qa/verifier_summary.py")
SK = json.loads((ROOT / "docs/agents/skeletons.json").read_text(encoding="utf-8"))
FAC = {"south": "2-1", "north": "1-2", "east": "Б-А", "west": "А-Б"}
CELLS = ("oks-vpm", "ground-npm", "ground-vpm")


def _scores(**over):
    out = []
    for axis in vf.MATERIAL_AXES:
        out.append({"axis": axis, "score": over.get(axis, 5), "reason": f"{axis} as on the slide"})
    return out


def _answers(defects=()):
    return [{"id": i["id"], "defect": i["id"] in defects, "note": ""} for i in vf.checklist_items(FAC)]


# ------------------------------------------------------------------ skeleton wiring

@pytest.mark.parametrize("cell", CELLS)
def test_skeleton_verifier_stage_right_after_readback(cell):
    stages = SK["cells"][cell]["stages"]
    assert stages.count("verifier") == 1
    assert stages.index("verifier") == stages.index("readback") + 1
    assert "verifier_mode" in SK["cells"][cell]["config_keys"]


def test_skeleton_verifier_stage_only_in_the_three_cells_and_is_shared():
    assert {c for c, s in SK["cells"].items() if "verifier" in s["stages"]} == set(CELLS)
    st = SK["stages"]["verifier"]
    assert st["gap"] is None and "tools/qa/verifier.py" in st["owners"]
    doc = (ROOT / "docs/agents/SKELETONS.md").read_text(encoding="utf-8")
    for cell in CELLS:
        table = doc.split(f"### `{cell}`", 1)[1].split("\n### ", 1)[0]
        assert "`verifier`" in table, cell


# ------------------------------------------------------------------ material rubric

def test_rubric_valid_scores_parse_in_axis_order():
    got = vf.parse_material_scores(_scores(scale=1, finish=3))
    assert list(got) == list(vf.MATERIAL_AXES)
    assert got["scale"] == {"score": 1, "reason": "scale as on the slide"}


@pytest.mark.parametrize("mutate,match", [
    (lambda s: s[1:], "missing"),
    (lambda s: s + [dict(s[0])], "duplicate"),
    (lambda s: s + [{"axis": "gloss", "score": 3, "reason": "x"}], "unknown"),
    (lambda s: [dict(s[0], score=3.5)] + s[1:], "integer"),
    (lambda s: [dict(s[0], score=3.0)] + s[1:], "integer"),
    (lambda s: [dict(s[0], score="3")] + s[1:], "integer"),
    (lambda s: [dict(s[0], score=True)] + s[1:], "integer"),
    (lambda s: [dict(s[0], score=None)] + s[1:], "integer"),
    (lambda s: [dict(s[0], score=math.nan)] + s[1:], "integer"),
    (lambda s: [dict(s[0], score=math.inf)] + s[1:], "integer"),
    (lambda s: [dict(s[0], score=0)] + s[1:], "1-5"),
    (lambda s: [dict(s[0], score=6)] + s[1:], "1-5"),
    (lambda s: [dict(s[0], reason="")] + s[1:], "reason"),
    (lambda s: [dict(s[0], reason="two\nlines")] + s[1:], "reason"),
    (lambda s: [{k: v for k, v in s[0].items() if k != "reason"}] + s[1:], "reason"),
    (lambda s: [], "missing"),
    (lambda s: {"axis": "missing"}, "list"),
    (lambda s: ["missing"] + s[1:], "object"),
])
def test_rubric_fail_closed(mutate, match):
    with pytest.raises(vf.VerifierError, match=match):
        vf.parse_material_scores(mutate(_scores()))


def test_rubric_probe_every_score_value_and_every_dropped_axis():
    """Brute force: scores -2..8 on every axis, every single axis dropped or doubled."""
    ok = bad = 0
    for axis, value in itertools.product(vf.MATERIAL_AXES, range(-2, 9)):
        s = _scores(**{axis: value})
        if 1 <= value <= 5:
            assert vf.parse_material_scores(s)[axis]["score"] == value
            ok += 1
        else:
            with pytest.raises(vf.VerifierError):
                vf.parse_material_scores(s)
            bad += 1
    for i in range(len(vf.MATERIAL_AXES)):
        s = _scores()
        with pytest.raises(vf.VerifierError, match="missing"):
            vf.parse_material_scores(s[:i] + s[i + 1:])
        with pytest.raises(vf.VerifierError, match="duplicate"):
            vf.parse_material_scores(s + [s[i]])
    assert (ok, bad) == (30, 36)


def test_rubric_order_consistency_keeps_the_lower_score():
    fwd = vf.parse_material_scores(_scores(base_color=4))
    rev = vf.parse_material_scores(_scores(base_color=2))
    got = vf.combine_material(fwd, rev)
    assert got["base_color"]["score"] == 2 and got["base_color"]["forward"] == 4 and got["base_color"]["reverse"] == 2


# ------------------------------------------------------------------ main discrepancy

def _findings(defects=(), **mat):
    items = vf.checklist_items(FAC)
    kept = {i["id"]: i["id"] in defects for i in items}
    m = vf.parse_material_scores(_scores(**mat))
    return vf.findings(items, kept, vf.combine_material(m, m))


def test_main_fix_order_beats_lower_score():
    f = _findings(base_color=1, missing=3, scale=1)
    assert vf.main_discrepancy(f)["key"] == "material:missing"
    assert [x["key"] for x in f if x["source"] == "material"] == ["material:missing", "material:base_color",
                                                                  "material:scale"]


def test_main_threshold_exactly_at_three_is_a_discrepancy_four_is_not():
    assert vf.main_discrepancy(_findings(borders=3))["key"] == "material:borders"
    assert vf.main_discrepancy(_findings(borders=4)) is None


def test_main_materials_first_then_checklist_then_none():
    assert vf.main_discrepancy(_findings(defects=("A05",), finish=2))["key"] == "material:finish"
    m = vf.main_discrepancy(_findings(defects=("A05", "A02")))
    assert m["key"] == "checklist:frame_color"
    rib = [x for x in _findings(defects=("A05",)) if x["id"] == "A05"][0]
    assert rib["key"] == "checklist:rib_count:2-1" and "geometry" in rib["locate_with"]
    assert vf.main_discrepancy(_findings()) is None


def test_main_probe_exactly_one_main_and_it_is_a_finding():
    """Generated: all 2^4 subsets of 4 checklist defects x 3 scores on 3 axes."""
    n = 0
    for k in range(5):
        for defects in itertools.combinations(("A01", "A04", "A09", "A11"), k):
            for a, b, c in itertools.product((2, 3, 4), repeat=3):
                f = _findings(defects=defects, missing=a, scale=b, consistency=c)
                main = vf.main_discrepancy(f)
                assert (main is None) == (not f)
                assert main is None or main == f[0]
                n += 1
    assert n == 16 * 27


# ------------------------------------------------------------------ verifier.json schema

def _report(**over):
    items = vf.checklist_items(FAC)
    fw = vf.parse_answers(items, _answers(("A05",)))
    rv = vf.parse_answers(items, _answers(("A05", "A09")))
    m1 = vf.parse_material_scores(_scores(base_color=2))
    doc = vf.build_report(job="jobs/X", mode="observe", round_no=1, renders="R", slide="S.png", facades=FAC,
                          items=items, forward=fw, reverse=rv, mat_forward=m1, mat_reverse=m1,
                          vlm={"model": "fake", "cost_usd": 0.0, "duration_s": 0.0})
    doc.update(over)
    return doc


def test_report_valid_and_matches_json_schema():
    import jsonschema
    doc = _report()
    assert vf.validate_report(doc) is doc
    assert doc["edits_model"] is False and doc["mode"] == "observe"
    assert doc["checklist"]["dropped"] == ["A09"]
    assert doc["main_discrepancy"]["key"] == "material:base_color"
    schema = json.loads((ROOT / "schemas/Verifier.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(json.loads(json.dumps(doc)), schema)


@pytest.mark.parametrize("over,match", [
    ({"edits_model": True}, "edits_model"),
    ({"mode": "auto"}, "mode"),
    ({"round": 0}, "round"),
    ({"round": 4}, "round"),
    ({"round": 2}, "round"),            # observe is a single round
    ({"main_discrepancy": None}, "main"),
    ({"main_discrepancy": {"key": "material:scale"}}, "main"),
    ({"extra": 1}, "keys"),
    ({"schema": "agr.verifier/0"}, "schema"),
])
def test_report_fail_closed(over, match):
    import jsonschema
    doc = _report(**over)
    with pytest.raises(vf.VerifierError, match=match):
        vf.validate_report(doc)
    if over.get("round") != 2 and "main_discrepancy" not in over:   # cross-field rules live in Python only
        schema = json.loads((ROOT / "schemas/Verifier.schema.json").read_text(encoding="utf-8"))
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(json.loads(json.dumps(doc)), schema)


def test_report_missing_key_and_clean_report():
    doc = _report()
    del doc["scores"]
    with pytest.raises(vf.VerifierError, match="keys"):
        vf.validate_report(doc)
    clean = _report(findings=[], main_discrepancy=None)
    vf.validate_report(clean)
    with pytest.raises(vf.VerifierError, match="main"):
        vf.validate_report(_report(findings=[]))


# ------------------------------------------------------------------ mode gate

def _job(tmp_path, skeleton=None):
    job = tmp_path / "jobs" / "J1"
    job.mkdir(parents=True)
    if skeleton is not None:
        (job / "skeleton.json").write_text(skeleton if isinstance(skeleton, str) else json.dumps(skeleton),
                                           encoding="utf-8")
    return job


def test_mode_observe_needs_no_opt_in(tmp_path):
    assert vf.resolve_mode(_job(tmp_path), "observe", 1) == ("observe", 1)


@pytest.mark.parametrize("skeleton", [
    None,
    {"scenario": "oks-vpm", "config": {}},
    {"scenario": "oks-vpm", "config": {"verifier_mode": "observe"}},
    {"scenario": "oks-vpm", "config": {"verifier_mode": "FIX"}},
    {"scenario": "oks-vpm", "verifier_mode": "fix"},
    "{not json",
    "[]",
])
def test_mode_fix_refused_without_skeleton_opt_in(tmp_path, skeleton):
    with pytest.raises(vf.VerifierError, match="fix"):
        vf.resolve_mode(_job(tmp_path, skeleton), "fix", 1)


def test_mode_fix_with_opt_in_max_three_rounds(tmp_path):
    job = _job(tmp_path, {"scenario": "oks-vpm", "config": {"verifier_mode": "fix"}})
    for r in (1, 2, 3):
        assert vf.resolve_mode(job, "fix", r) == ("fix", r)
    for r in (0, 4, -1):
        with pytest.raises(vf.VerifierError, match="round"):
            vf.resolve_mode(job, "fix", r)
    with pytest.raises(vf.VerifierError, match="round"):
        vf.resolve_mode(job, "observe", 2)
    with pytest.raises(vf.VerifierError, match="mode"):
        vf.resolve_mode(job, "auto", 1)


# ------------------------------------------------------------------ CLI with a fake VLM

def _renders(tmp_path):
    rd = tmp_path / "ev" / "renders"
    rd.mkdir(parents=True)
    for v in vf.VIEWS:
        (rd / f"{v}.png").write_bytes(v.encode())
    slide = tmp_path / "ev" / "slide.png"
    slide.write_bytes(b"slide")
    return rd, slide


def _tree_hash(*paths):
    h = hashlib.sha256()
    for p in paths:
        for f in sorted(Path(p).rglob("*")) if Path(p).is_dir() else [Path(p)]:
            if f.is_file():
                h.update(f.as_posix().encode() + f.read_bytes())
    return h.hexdigest()


def _fake_vlm(monkeypatch, fwd_defects=("A05",), rev_defects=("A05",), mat=None, fail=False):
    calls = []

    def fake(prompt, workdir, model):
        calls.append(prompt)
        if fail:
            raise vf.ChecklistError("claude exit 1: boom")
        rev = prompt.index("npm_iso.png") < prompt.index("vpm_south.png")
        d = rev_defects if rev else fwd_defects
        return {"parsed": {"answers": _answers(d), "materials": _scores(**(mat or {}))}, "cost_usd": 0.01,
                "duration_s": 1.0, "models": [model]}
    monkeypatch.setattr(vf, "call_vlm", fake)
    return calls


def _argv(job, rd, slide, *extra):
    return ["--job", str(job), "--renders", str(rd), "--slide", str(slide),
            "--facades", "south=2-1,north=1-2,east=Б-А,west=А-Б", *extra]


def test_cli_observe_writes_verifier_json_and_touches_nothing_else(tmp_path, monkeypatch):
    job, (rd, slide) = _job(tmp_path), _renders(tmp_path)
    before = _tree_hash(rd, slide)
    calls = _fake_vlm(monkeypatch, fwd_defects=("A05", "A10"), rev_defects=("A05",), mat={"scale": 2})
    assert vf.main(_argv(job, rd, slide)) == 0
    doc = json.loads((job / "verifier.json").read_text(encoding="utf-8"))
    vf.validate_report(doc)
    assert doc["mode"] == "observe" and doc["checklist"]["dropped"] == ["A10"]
    assert doc["main_discrepancy"]["key"] == "material:scale"
    assert len(calls) == 2 and "confirm" in calls[0].lower()
    assert sorted(p.name for p in job.iterdir()) == ["verifier.json"]
    assert _tree_hash(rd, slide) == before


def test_cli_fix_refused_without_opt_in_writes_nothing(tmp_path, monkeypatch):
    job, (rd, slide) = _job(tmp_path), _renders(tmp_path)
    calls = _fake_vlm(monkeypatch)
    assert vf.main(_argv(job, rd, slide, "--mode", "fix")) == 2
    assert calls == [] and list(job.iterdir()) == []


def test_cli_fix_with_opt_in_round_four_refused(tmp_path, monkeypatch):
    job, (rd, slide) = _job(tmp_path, {"scenario": "oks-vpm", "config": {"verifier_mode": "fix"}}), \
        _renders(tmp_path)
    _fake_vlm(monkeypatch)
    assert vf.main(_argv(job, rd, slide, "--mode", "fix", "--round", "4")) == 2
    assert vf.main(_argv(job, rd, slide, "--mode", "fix", "--round", "3",
                         "--out", str(job / "verifier.r3.json"))) == 0
    doc = json.loads((job / "verifier.r3.json").read_text(encoding="utf-8"))
    assert (doc["mode"], doc["round"], doc["edits_model"]) == ("fix", 3, False)


@pytest.mark.parametrize("case", ["out_is_render", "out_in_renders", "out_is_slide", "exists", "missing_view",
                                  "vlm_error", "bad_answers", "bad_facades", "out_is_skeleton"])
def test_cli_fail_closed_writes_nothing(tmp_path, monkeypatch, case):
    job, (rd, slide) = _job(tmp_path, {"scenario": "oks-vpm", "config": {}}), _renders(tmp_path)
    extra, kw = [], {}
    if case == "out_is_render":
        extra = ["--out", str(rd / "vpm_iso.png")]
    elif case == "out_in_renders":
        extra = ["--out", str(rd / "verifier.json")]
    elif case == "out_is_slide":
        extra = ["--out", str(slide)]
    elif case == "out_is_skeleton":
        extra = ["--out", str(job / "skeleton.json")]
    elif case == "exists":
        (job / "verifier.json").write_text("{}", encoding="utf-8")
    elif case == "missing_view":
        (rd / "npm_iso.png").unlink()
    elif case == "vlm_error":
        kw = {"fail": True}
    elif case == "bad_answers":
        kw = {"mat": {"scale": 2.5}}
    argv = _argv(job, rd, slide, *extra)
    if case == "bad_facades":
        argv[argv.index("--facades") + 1] = "south=2-1,north=1-2"
    _fake_vlm(monkeypatch, **kw)
    before = _tree_hash(rd, slide, job)
    assert vf.main(argv) != 0
    assert _tree_hash(rd, slide, job) == before
    assert not list(job.glob("*.partial")) and not list(rd.glob("*.partial"))


def test_cli_fresh_process_help_and_fix_refusal(tmp_path):
    job, (rd, slide) = _job(tmp_path), _renders(tmp_path)
    p = subprocess.run([sys.executable, str(ROOT / "tools/qa/verifier.py"), *_argv(job, rd, slide, "--mode", "fix")],
                       capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
    assert p.returncode == 2 and "skeleton.json" in p.stdout + p.stderr
    assert list(job.iterdir()) == []


# ------------------------------------------------------------------ summary

def _write(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


def test_summary_counts_matches_per_job(tmp_path):
    jobs = tmp_path / "jobs"
    _write(jobs / "A" / "verifier.json", _report())                       # main material:base_color
    _write(jobs / "A" / "verifier.r2.json", _report())
    _write(jobs / "A" / "verifier_review.json", {"reviews": [
        {"verifier": "verifier.json", "artem_corrected": ["material:base_color"]},
        {"verifier": "verifier.r2.json", "artem_corrected": ["checklist:rib_count"]}]})
    _write(jobs / "B" / "verifier.json", _report())
    rib = _report()
    rib["findings"] = rib["findings"][-1:]
    rib["main_discrepancy"] = rib["findings"][0]
    _write(jobs / "C" / "verifier.json", rib)
    _write(jobs / "C" / "verifier_review.json", {"reviews": [
        {"verifier": "verifier.json", "artem_corrected": ["checklist:rib_count"]}]})
    s = vs.summarize(jobs)
    assert s["jobs"]["A"] == {"runs": 2, "reviewed": 2, "matched": 1, "match_rate": 0.5, "unreviewed": []}
    assert s["jobs"]["B"] == {"runs": 1, "reviewed": 0, "matched": 0, "match_rate": None,
                              "unreviewed": ["verifier.json"]}
    assert s["jobs"]["C"]["matched"] == 1       # checklist:rib_count:2-1 matches the category Artem named
    assert s["total"] == {"runs": 4, "reviewed": 3, "matched": 2, "match_rate": 2 / 3}


def test_summary_clean_report_matches_only_an_empty_correction(tmp_path):
    jobs = tmp_path / "jobs"
    _write(jobs / "A" / "verifier.json", _report(findings=[], main_discrepancy=None))
    _write(jobs / "A" / "verifier_review.json", {"reviews": [{"verifier": "verifier.json", "artem_corrected": []}]})
    assert vs.summarize(jobs)["jobs"]["A"]["matched"] == 1
    _write(jobs / "A" / "verifier_review.json",
           {"reviews": [{"verifier": "verifier.json", "artem_corrected": ["material:scale"]}]})
    assert vs.summarize(jobs)["jobs"]["A"]["matched"] == 0


@pytest.mark.parametrize("review,match", [
    ({"reviews": [{"verifier": "nope.json", "artem_corrected": []}]}, "nope.json"),
    ({"reviews": [{"verifier": "verifier.json", "artem_corrected": []}] * 2}, "duplicate"),
    ({"reviews": [{"verifier": "verifier.json", "artem_corrected": "material:scale"}]}, "artem_corrected"),
    ({"reviews": [{"verifier": "verifier.json", "artem_corrected": ["paint:scale"]}]}, "paint:scale"),
    ({"reviews": [{"verifier": "verifier.json"}]}, "artem_corrected"),
    ({"reviews": []}, "empty"),
    ({}, "reviews"),
])
def test_summary_fail_closed(tmp_path, review, match):
    jobs = tmp_path / "jobs"
    _write(jobs / "A" / "verifier.json", _report())
    _write(jobs / "A" / "verifier_review.json", review)
    with pytest.raises(vf.VerifierError, match=match):
        vs.summarize(jobs)


def test_summary_invalid_verifier_and_empty_root(tmp_path):
    jobs = tmp_path / "jobs"
    _write(jobs / "A" / "verifier.json", _report(edits_model=True))
    with pytest.raises(vf.VerifierError, match="edits_model"):
        vs.summarize(jobs)
    with pytest.raises(vf.VerifierError, match="no verifier"):
        vs.summarize(tmp_path / "empty")
    assert vs.main(["--jobs", str(tmp_path / "empty")]) == 2


# ------------------------------------------------------------------ docs

@pytest.mark.parametrize("rel", [".agents/skills/model-maf/SKILL.md", ".agents/skills/model-flora/SKILL.md",
                                 ".agents/skills/scenario/SKILL.md", "docs/agents/SKELETONS.md"])
def test_docs_crossprojection_rule_present(rel):
    text = (ROOT / rel).read_text(encoding="utf-8")
    assert "CrossProjection" in text and "VLM confirms" in text and "tools/qa/verifier.py" in text
