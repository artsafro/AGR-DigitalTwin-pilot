"""#1546 scalpel agent: scenario skeletons, job hooks, historical job scripts hidden from agent search.

Pattern: n/a | new-case: regression tests of skeleton_guard and the duplicate_guard historical class (#1546).

Acceptance table (PR body) -> tests:
- every scenario cell has a skeleton, its owners/entry names are real, docs list it  -> test_skeleton_*
- a synthetic job that re-implements a skeleton stage fails, calling it passes       -> test_job_*
- job contract: hooks/ only, listed once, <= max_hooks, known scenario/stage/point   -> test_contract_*
- repo: new job with scripts needs skeleton.json; legacy/historical/no-script jobs ok -> test_repo_*
- historical delivered-job scripts hidden from rg, still scanned by duplicate_guard   -> test_historical_*
- agent start docs point to SKELETONS.md first; D324-D327 exist and are cited         -> test_docs_*
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "architecture"))
import call_chains  # noqa: E402
import duplicate_guard as dg  # noqa: E402
import mini_yaml  # noqa: E402
import skeleton_guard as sg  # noqa: E402

SK = sg.load_skeletons(ROOT)
GUARD = ROOT / "tools/architecture/skeleton_guard.py"


def _defs(path):
    import ast
    tree = ast.parse((ROOT / path).read_bytes())
    return {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}


def _job(tmp_path, cfg, files, name="NEWJOB"):
    job = tmp_path / "jobs" / name
    job.mkdir(parents=True)
    if cfg is not None:
        (job / "skeleton.json").write_text(cfg if isinstance(cfg, str) else json.dumps(cfg), encoding="utf-8")
    for rel, text in files.items():
        (job / rel).parent.mkdir(parents=True, exist_ok=True)
        (job / rel).write_text(text, encoding="utf-8")
    return job


def _cfg(cell="oks-vpm", hooks=(), config=None):
    return {"scenario": cell, "config": config or {}, "hooks": [dict(h) for h in hooks]}


def _hook(script="hooks/fix.py", stage="master-qa", point="after"):
    return {"script": script, "stage": stage, "point": point}


# --- skeleton inventory --------------------------------------------------------------------------------------------

def test_skeleton_every_scenario_cell_has_a_skeleton():
    cells = {c["id"] for c in json.loads((ROOT / "docs/scenarios/scenarios.json").read_text(encoding="utf-8"))["cells"]}
    assert cells and cells == set(SK["cells"])
    for cell, spec in SK["cells"].items():
        assert spec["stages"], cell
        assert all(s in SK["stages"] for s in spec["stages"])


def test_skeleton_owners_exist_and_entry_names_are_defined_by_them():
    stages = list(SK["stages"].items()) + [(s["id"], s) for s in SK["shared"]]
    checked = 0
    for sid, st in stages:
        for owner in st["owners"]:
            assert (ROOT / owner).is_file(), f"{sid}: owner {owner} missing"
        defined = set().union(*[_defs(o) for o in st["owners"] if o.endswith(".py")]) if st["owners"] else set()
        for name in st["entry_defs"]:
            assert name in defined, f"{sid}: {name} is not defined by {st['owners']}"
            checked += 1
        assert all(r in dg.RULES for r in st["dup_rules"]), sid
        if st["gap"] is None:
            assert st["calls"] and st["owners"], f"{sid}: shared stage needs calls + owners"
        else:
            assert isinstance(st["gap"], str) and "\n" not in st["gap"] and st["gap"].strip(), sid
    assert checked >= 30


def test_skeleton_doc_lists_every_cell_stage_and_gap():
    doc = (ROOT / "docs/agents/SKELETONS.md").read_text(encoding="utf-8")
    assert doc.lstrip().startswith("# ") and re.search(r"[а-яА-Я]", doc.split("\n## ")[0])  # Russian summary first
    for cell in SK["cells"]:
        assert f"`{cell}`" in doc, cell
    for sid, st in SK["stages"].items():
        assert f"`{sid}`" in doc, sid
    gaps = doc.split("## Пробелы", 1)[1]
    for sid, st in SK["stages"].items():
        assert (f"`{sid}`" in gaps) == (st["gap"] is not None), sid


def test_skeleton_unknown_stage_in_cell_is_a_config_error(tmp_path):
    data = json.loads((ROOT / sg.SKELETONS).read_text(encoding="utf-8"))
    data["cells"]["oks-vpm"]["stages"].append("no-such-stage")
    (tmp_path / "docs/agents").mkdir(parents=True)
    (tmp_path / sg.SKELETONS).write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(sg.ConfigError, match="no-such-stage"):
        sg.load_skeletons(tmp_path)


# --- re-implementation (RED -> GREEN core) -------------------------------------------------------------------------

def test_job_reimplementing_a_skeleton_stage_fails(tmp_path):
    job = _job(tmp_path, _cfg(hooks=[_hook()]), {
        "hooks/fix.py": "import bmesh\n\ndef world_bm(obj):\n    return bmesh.new()\n"})
    problems = sg.check_job(tmp_path, job, SK)
    assert len(problems) == 1 and "world_bm" in problems[0] and "master-qa" in problems[0], problems


def test_job_calling_the_skeleton_passes(tmp_path):
    job = _job(tmp_path, _cfg(hooks=[_hook()]), {
        "hooks/fix.py": "from tools.blender.qa_master import world_bm\n\ndef fix(obj):\n    return world_bm(obj)\n"})
    assert sg.check_job(tmp_path, job, SK) == []


def _entry_cases():
    for cell, spec in SK["cells"].items():
        for sid in spec["stages"]:
            for name in SK["stages"][sid]["entry_defs"]:
                yield cell, sid, name
    for s in SK["shared"]:
        for name in s["entry_defs"]:
            yield "oks-vpm", s["id"], name


@pytest.mark.parametrize("cell,sid,name", sorted(set(_entry_cases())))
def test_job_probe_every_entry_name_of_every_cell_is_flagged(tmp_path, cell, sid, name):
    hook = _hook(stage=SK["cells"][cell]["stages"][0])
    job = _job(tmp_path, _cfg(cell, [hook]), {"hooks/fix.py": f"class Box:\n    def {name}(self):\n        pass\n"})
    problems = sg.check_job(tmp_path, job, SK)
    assert any(f"'{name}'" in p and sid in p for p in problems), problems


@pytest.mark.parametrize("rule,text", [
    ("delivery-zip", "import zipfile\nwith zipfile.ZipFile('o.zip', 'w') as z:\n    pass\n"),
    ("udim-tile", "def t(u, v):\n    return 1001 + u + 10 * v\n"),
    ("blender-launch", "import subprocess\nsubprocess.run(['blender', '--background', '--python', 'x.py'])\n"),
    ("sintez-checker", "import m\nm.calculate_all_checks()\n"),
])
def test_job_duplicate_guard_copy_of_a_stage_fails(tmp_path, rule, text):
    stage = next(s for s in SK["cells"]["oks-vpm"]["stages"])
    job = _job(tmp_path, _cfg(hooks=[_hook(stage=stage)]), {"hooks/fix.py": text})
    problems = sg.check_job(tmp_path, job, SK)
    assert any(rule in p and "re-implements stage" in p for p in problems), problems


# --- job contract --------------------------------------------------------------------------------------------------

def test_contract_script_outside_hooks_or_unlisted_fails(tmp_path):
    job = _job(tmp_path, _cfg(hooks=[_hook()]), {"hooks/fix.py": "x = 1\n", "hooks/extra.py": "y = 2\n",
                                                 "pipeline/run_all.py": "z = 3\n", "run.sh": "echo\n"})
    problems = "\n".join(sg.check_job(tmp_path, job, SK))
    assert "extra.py: script not listed in hooks" in problems
    assert "run_all.py: script outside hooks/" in problems and "run.sh: script outside hooks/" in problems


@pytest.mark.parametrize("n,ok", [(0, True), (1, True), (5, True), (6, False), (12, False)])
def test_contract_max_hooks_boundary(tmp_path, n, ok):
    hooks = [_hook(f"hooks/h{i}.py") for i in range(n)]
    job = _job(tmp_path, _cfg(hooks=hooks), {f"hooks/h{i}.py": "x = 1\n" for i in range(n)})
    problems = sg.check_job(tmp_path, job, SK)
    assert (problems == []) == ok, problems
    if not ok:
        assert any("parallel pipeline" in p for p in problems)


@pytest.mark.parametrize("cfg,match", [
    ("", "cannot read"), ("{not json", "cannot read"), ("[]", "non-empty object"), ("{}", "non-empty object"),
    (_cfg("oks-xyz"), "oks-xyz"), ({"scenario": ["oks-vpm"]}, "is not a cell"),
    ({"scenario": "oks-vpm", "hooks": [{"script": "hooks/fix.py", "stage": ["x"], "point": "after"}]}, "not a stage"),
    (_cfg(hooks=[_hook(stage="zero")]), "'zero' is not a stage of oks-vpm"),
    (_cfg(hooks=[_hook(point="instead")]), "'instead' unknown"),
    (_cfg(config={"texel": 1}), r"\['texel'\]"), ({"scenario": "oks-vpm", "pipeline": []}, "unknown keys"),
    (_cfg(hooks=[{"script": "hooks/fix.py"}]), "exactly script, stage, point"),
])
def test_contract_unreadable_or_unmapped_config_is_an_error(tmp_path, cfg, match):
    job = _job(tmp_path, cfg, {"hooks/fix.py": "x = 1\n"})
    with pytest.raises(sg.ConfigError, match=match):
        sg.check_job(tmp_path, job, SK)


def test_contract_gap_point_only_on_a_gap_stage(tmp_path):
    job = _job(tmp_path, _cfg("ground-vpm", [_hook(stage="zero", point="gap")]), {"hooks/fix.py": "x = 1\n"})
    assert sg.check_job(tmp_path, job, SK) == []
    job2 = _job(tmp_path, _cfg("ground-vpm", [_hook(stage="validate", point="gap")]), {"hooks/fix.py": "x = 1\n"},
                name="J2")
    problems = sg.check_job(tmp_path, job2, SK)
    assert len(problems) == 1 and "replaces stage validate" in problems[0]


def test_contract_alias_duplicate_escape_and_missing_hooks(tmp_path):
    hooks = [_hook(), _hook("hooks/./fix.py"), _hook("hooks/../../x.py"), _hook("hooks/gone.py")]
    job = _job(tmp_path, _cfg(hooks=hooks), {"hooks/fix.py": "x = 1\n"})
    problems = "\n".join(sg.check_job(tmp_path, job, SK))
    assert "listed twice" in problems and "not inside hooks/" in problems and "gone.py does not exist" in problems


def test_contract_hook_that_does_not_parse_is_an_error_naming_it(tmp_path):
    job = _job(tmp_path, _cfg(hooks=[_hook()]), {"hooks/fix.py": "def (:\n"})
    with pytest.raises(sg.ConfigError, match="fix.py: cannot parse"):
        sg.check_job(tmp_path, job, SK)


def test_contract_template_skeleton_is_valid(tmp_path):
    text = (ROOT / "docs/agents/skeleton.template.json").read_text(encoding="utf-8")
    assert json.loads(text)["scenario"] in SK["cells"]
    assert sg.check_job(tmp_path, _job(tmp_path, text, {}), SK) == []


# --- repo scan -----------------------------------------------------------------------------------------------------

def _repo(tmp_path, baseline=("jobs/DELIVERED/old.py",)):
    (tmp_path / "docs/agents").mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / sg.SKELETONS, tmp_path / sg.SKELETONS)
    (tmp_path / dg.JOB_BASELINE).write_text("# frozen\n" + "".join(f"{b}\n" for b in baseline), encoding="utf-8")
    return sg.load_skeletons(tmp_path)


WORLD_BM = "def world_bm(o):\n    return o\n"   # the master-QA owner's helper name: a re-implemented stage
OUTSIDE = ": script outside a skeleton.json folder and not in the frozen #1546 baseline"


def test_repo_new_job_with_scripts_needs_a_skeleton_config(tmp_path):
    sk = _repo(tmp_path, baseline=("jobs/DELIVERED/old.py", "jobs/elv-tc-vpm/old.py"))
    _job(tmp_path, None, {"analyse_seams.py": "x = 1\n"}, name="SINTEZ-FIX")
    _job(tmp_path, None, {"notes.md": "text\n"}, name="DOCS-ONLY")
    _job(tmp_path, None, {"old.py": "x = 1\n"}, name="DELIVERED")
    _job(tmp_path, None, {"old.py": "x = 1\n"}, name="elv-tc-vpm")
    _job(tmp_path, None, {"job.yaml": "id: TEMPLATE\n", "README.md": "Job template\n"}, name="_template")
    problems = sg.check_repo(tmp_path, sk)
    assert len(problems) == 1 and problems[0].startswith("jobs/SINTEZ-FIX/analyse_seams.py" + OUTSIDE)


def test_repo_configured_legacy_job_is_checked(tmp_path):
    sk = _repo(tmp_path, baseline=("jobs/elv-tc-vpm/hooks/fix.py",))
    _job(tmp_path, _cfg(hooks=[_hook()]), {"hooks/fix.py": WORLD_BM}, name="elv-tc-vpm")
    problems = sg.check_repo(tmp_path, sk)
    assert len(problems) == 1 and "world_bm" in problems[0]


# PR #1553 r1 (P1): new work lands in sub-folders of finished/legacy jobs; a whole-folder exemption hid it.
@pytest.mark.parametrize("rel", ["jobs/KPP1/fix-1600/run_all.py", "jobs/4bk-k3/fix-1601/run_all.py",
                                 "jobs/KPP1/run_new.py", "jobs/4bk-k3/a/b/c/deep.ms",
                                 "jobs/KPP1/_template/run_all.py", "jobs/_template/run_all.py"])
def test_repo_new_script_in_a_finished_or_legacy_job_is_flagged(tmp_path, rel):
    sk = _repo(tmp_path, baseline=("jobs/KPP1/scripts/old.py", "jobs/4bk-k3/old.py"))
    for f in ("jobs/KPP1/scripts/old.py", "jobs/4bk-k3/old.py", rel):
        (tmp_path / f).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / f).write_text(WORLD_BM, encoding="utf-8")
    problems = sg.check_repo(tmp_path, sk)
    assert len(problems) == 1 and problems[0].startswith(rel + OUTSIDE)


def test_repo_nested_skeleton_config_in_a_finished_job_is_read(tmp_path):
    sk = _repo(tmp_path, baseline=("jobs/KPP1/scripts/old.py",))
    _job(tmp_path, None, {"scripts/old.py": "x = 1\n"}, name="KPP1")
    _job(tmp_path, _cfg(hooks=[_hook()]), {"hooks/fix.py": WORLD_BM}, name="KPP1/fix-1602")
    problems = sg.check_repo(tmp_path, sk)
    assert len(problems) == 1 and problems[0].startswith("jobs/KPP1/fix-1602/hooks/fix.py:1: defines 'world_bm'")
    (tmp_path / "jobs/KPP1/fix-1602/hooks/fix.py").write_text("x = 1\n", encoding="utf-8")
    assert sg.check_repo(tmp_path, sk) == []
    (tmp_path / "jobs/KPP1/fix-1602/skeleton.json").write_text("{", encoding="utf-8")
    with pytest.raises(sg.ConfigError, match="fix-1602/skeleton.json"):
        sg.check_repo(tmp_path, sk)


def test_repo_nested_skeleton_inside_a_skeleton_job_is_its_own_job(tmp_path):
    sk = _repo(tmp_path)
    _job(tmp_path, _cfg(hooks=[_hook()]), {"hooks/fix.py": "x = 1\n"}, name="OUTER")
    _job(tmp_path, _cfg(hooks=[_hook()]), {"hooks/fix.py": "x = 1\n"}, name="OUTER/sub-1")
    assert sg.check_repo(tmp_path, sk) == []
    (tmp_path / "jobs/OUTER/sub-1/hooks/extra.py").write_text("x = 1\n", encoding="utf-8")
    assert sg.check_repo(tmp_path, sk) == ["jobs/OUTER/sub-1/hooks/extra.py: script not listed in hooks; "
                                          "a job holds skeleton.json + listed hooks only [D324]"]


def test_repo_control_baseline_historical_script_stays_hidden_and_unflagged(tmp_path):
    sk = _repo(tmp_path, baseline=("jobs/KPP1/scripts/old.py",))
    _job(tmp_path, None, {"scripts/old.py": WORLD_BM, "fix-1600/run_all.py": WORLD_BM}, name="KPP1")
    finished = {"jobs/KPP1": "x"}
    hidden = dg.historical_scripts(tmp_path, finished, chains={})
    assert hidden == ["jobs/KPP1/scripts/old.py"]   # the new script is never historical
    dg.write_ignore(tmp_path, hidden)
    assert "fix-1600" not in (tmp_path / ".ignore").read_text(encoding="utf-8")
    problems = sg.check_repo(tmp_path, sk)
    assert len(problems) == 1 and problems[0].startswith("jobs/KPP1/fix-1600/run_all.py" + OUTSIDE)
    rg = shutil.which("rg")
    if rg:
        out = subprocess.run([rg, "--files", "jobs"], cwd=tmp_path, capture_output=True, text=True).stdout
        listed = {line.replace("\\", "/") for line in out.splitlines()}
        assert "jobs/KPP1/fix-1600/run_all.py" in listed and "jobs/KPP1/scripts/old.py" not in listed
    # opting in: a skeleton.json folder above a baseline script makes it a checked, visible job script
    (tmp_path / "jobs/KPP1/scripts/skeleton.json").write_text(json.dumps(_cfg()), encoding="utf-8")
    assert dg.historical_scripts(tmp_path, finished, chains={}) == []


@pytest.mark.parametrize("text, match", [
    (None, "missing"), ("# only comments\n\n", "empty"), ("jobs/A/a.py\njobs/A/a.py\n", "twice"),
    ("tools/x.py\n", "not a jobs/"), ("jobs/a.py\n", "not a jobs/"), ("jobs/A/../B/x.py\n", "not a jobs/"),
    ("jobs/A/notes.md\n", "not a jobs/"), (" jobs/A/a.py\n", "not a jobs/"), ("jobs\\A\\a.py\n", "not a jobs/"),
])
def test_repo_baseline_fail_closed(tmp_path, text, match):
    sk = _repo(tmp_path)
    if text is None:
        (tmp_path / dg.JOB_BASELINE).unlink()
    else:
        (tmp_path / dg.JOB_BASELINE).write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match=match):
        sg.check_repo(tmp_path, sk)
    with pytest.raises(ValueError, match=match):
        dg.historical_scripts(tmp_path, {}, {})
    (tmp_path / "jobs").mkdir(exist_ok=True)
    r = subprocess.run([sys.executable, str(GUARD), "--root", str(tmp_path)], capture_output=True, text=True)
    assert r.returncode == 2 and match in r.stderr


def test_repo_real_baseline_is_frozen_at_the_cut():
    base = dg.load_job_baseline(ROOT)
    assert len(base) == 358 and "jobs/KPP1/scripts/build_kpp1.py" in base
    assert not [b for b in base if dg.in_skeleton_job(ROOT, b)]


def test_repo_real_repository_is_clean_and_cli_exit_codes(tmp_path):
    assert sg.check_repo(ROOT) == []
    run = lambda *a: subprocess.run([sys.executable, str(GUARD), *a], capture_output=True, text=True)  # noqa: E731
    assert run().returncode == 0
    _repo(tmp_path)
    _job(tmp_path, _cfg(hooks=[_hook()]), {"hooks/fix.py": "def world_bm(o):\n    return o\n"})
    r = run("--root", str(tmp_path), "--job", "jobs/NEWJOB")
    assert r.returncode == 1 and "world_bm" in r.stdout
    assert run("--root", str(tmp_path), "--job", "jobs/NOPE").returncode == 2
    (tmp_path / "jobs/NEWJOB/skeleton.json").write_text("{", encoding="utf-8")
    assert run("--root", str(tmp_path), "--job", "jobs/NEWJOB").returncode == 2


# --- historical delivered-job scripts ------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def hist():
    contexts = mini_yaml.load(ROOT / "docs/architecture/contexts.yaml")
    finished = dg.finished_jobs(ROOT, contexts)
    roots, chains = call_chains.load_live(ROOT)
    evidence = {str(e.get("evidence", "")) for e in contexts.get("entrypoints", [])}
    return finished, chains, evidence, dg.historical_scripts(ROOT, finished, chains, evidence)


def test_historical_scripts_are_exactly_the_unreached_delivered_job_scripts(hist):
    finished, chains, evidence, scripts = hist
    assert len(scripts) >= 150 and len(set(scripts)) == len(scripts)
    assert all(s.startswith(tuple(f"{j}/" for j in finished)) for s in scripts)
    assert not [s for s in scripts if s in chains or s in evidence]
    assert "jobs/KPP1/scripts/build_kpp1.py" not in scripts and "jobs/KPP1/scripts/run_stage.sh" not in scripts
    assert dg.ignore_problems(ROOT, scripts) == []


def test_historical_rg_from_repo_root_hides_them_and_keeps_live_scripts(hist):
    rg = shutil.which("rg")
    if rg is None:
        pytest.skip("ripgrep not installed")
    _, _, _, scripts = hist
    out = subprocess.run([rg, "--files", "jobs"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout
    listed = {line.replace("\\", "/") for line in out.splitlines()}
    assert not set(scripts) & listed
    assert {"jobs/KPP1/scripts/build_kpp1.py", "jobs/VATUTINO-SITE/place_site.py"} <= listed
    hits = subprocess.run([rg, "-l", "def ", "jobs/OBR22-K02"], cwd=ROOT, capture_output=True, text=True).stdout
    assert hits.strip() == ""


def test_historical_scripts_are_still_scanned_by_duplicate_guard(hist):
    _, _, _, scripts = hist
    found = {f.path for f in dg.scan(ROOT, "jobs")}
    assert found & set(scripts), "duplicate_guard must still read historical scripts"


def test_historical_ignore_block_missing_stale_extra_and_rewrite(tmp_path):
    scripts = ["jobs/A/a.py", "jobs/A/s p[1].py", "jobs/B/b.sh"]
    assert "no single" in dg.ignore_problems(tmp_path, scripts)[0]
    (tmp_path / ".ignore").write_text("keep-me/\n", encoding="utf-8")
    dg.write_ignore(tmp_path, scripts)
    text = (tmp_path / ".ignore").read_text(encoding="utf-8")
    assert text.startswith("keep-me/\n") and text.count("# HISTORICAL [D327]") == 2
    assert "/jobs/A/s\\ p\\[1\\].py" in text and dg.ignore_problems(tmp_path, scripts) == []
    assert "missing" in dg.ignore_problems(tmp_path, scripts + ["jobs/C/c.py"])[0]
    assert "extra" in dg.ignore_problems(tmp_path, scripts[:1])[0]
    dg.write_ignore(tmp_path, scripts[:1])
    assert dg.ignore_problems(tmp_path, scripts[:1]) == [] and "keep-me/" in (tmp_path / ".ignore").read_text()
    assert not (tmp_path / ".ignore.partial").exists()
    (tmp_path / ".ignore").write_text(dg.IGNORE_BEGIN + "\n/x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="broken"):
        dg.write_ignore(tmp_path, scripts)


def test_historical_rg_honours_the_escaped_block(tmp_path):
    rg = shutil.which("rg")
    if rg is None:
        pytest.skip("ripgrep not installed")
    scripts = ["jobs/A/a.py", "jobs/A/s p[1].py", "jobs/A/!x#.py"]
    for s in scripts + ["jobs/A/live.py"]:
        (tmp_path / s).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / s).write_text("x = 1\n", encoding="utf-8")
    dg.write_ignore(tmp_path, scripts)
    out = subprocess.run([rg, "--files"], cwd=tmp_path, capture_output=True, text=True).stdout
    assert {line.replace("\\", "/") for line in out.splitlines()} == {"jobs/A/live.py"}


# --- docs ----------------------------------------------------------------------------------------------------------

def test_docs_start_docs_point_to_skeletons_first():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    first = agents.index("docs/agents/SKELETONS.md")
    assert first < agents.index("docs/domain/areas/<area>.md") and first < agents.index("## Goal")
    for name in ("CLAUDE.md", "GEMINI.md", "docs/agents/codex.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "docs/agents/SKELETONS.md" in text.split("\n## ")[0], name


def test_docs_decisions_d324_d327_exist_and_are_cited():
    decisions = (ROOT / "docs/decisions.md").read_text(encoding="utf-8")
    doc = (ROOT / "docs/agents/SKELETONS.md").read_text(encoding="utf-8")
    for d in ("D324", "D325", "D326", "D327"):
        assert len(re.findall(rf"^\| {d} \| 2026-11-16 \|", decisions, re.M)) == 1, d
        assert f"[{d}]" in doc, d
    assert "[D325]" in (ROOT / "docs/agents/REVIEW_CHECKLIST.md").read_text(encoding="utf-8")
