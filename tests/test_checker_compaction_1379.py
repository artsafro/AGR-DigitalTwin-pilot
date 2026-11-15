"""#1379 compaction step 4: checks + the SINTEZ route command.

Pattern: n/a | new-case: tests of `agr checker`, the sintez-checker / master-qa guard rules and the job shims.

The 5 validation rows of the #1359 map: the SINTEZ checker launch (KPP1 + TEC26 copy) moved to the one owner
tools/blender/sintez_checker.py behind `agr checker` (tools/qa/sintez_checker.py, launched through blender_runner);
the master QA (KPP1 + TEC26 copy) moved to tools/blender/qa_master.py; the 4 job files are shims that run the owners.
TEC26 qa_packages.py stays listed with its reason. New guard rules `sintez-checker` and `master-qa`.
Acceptance table: PR body. No Blender here: run_blender is replaced by a fake that writes the checker JSON.
"""
import hashlib
import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "architecture"))
import duplicate_guard as guard  # noqa: E402
import mini_yaml  # noqa: E402
import route_map  # noqa: E402

from dt_ai.cli import agr  # noqa: E402
from dt_ai.core.blender_runner import BlenderRunError  # noqa: E402

SHIMS = {"jobs/KPP1/scripts/run_agr_checker.py": "tools/blender/sintez_checker.py",
         "jobs/TEC26-OKS/scripts/run_agr_checker.py": "tools/blender/sintez_checker.py",
         "jobs/KPP1/scripts/qa_master.py": "tools/blender/qa_master.py",
         "jobs/TEC26-OKS/scripts/qa_master.py": "tools/blender/qa_master.py"}
EVENTS = ["npm-oks-route", "vpm-oks-route", "ground-route", "package-route"]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


checker = _load("sintez_checker_host", "tools/qa/sintez_checker.py")


def _validation():
    ctx = mini_yaml.load(ROOT / route_map.CONTEXTS)
    return next(c for c in ctx["contexts"] if c["id"] == "validation"), ctx


# --- map + guard -------------------------------------------------------------------------------------------------

def test_merged_rows_left_the_map_and_the_kept_row_has_a_reason():
    validation, ctx = _validation()
    ats = [d["at"] for d in validation["duplicates"]]
    for shim in SHIMS:
        assert not any(a.startswith(shim) for a in ats), shim
    kept = next(d for d in validation["duplicates"] if d["at"].startswith("jobs/TEC26-OKS/scripts/qa_packages.py"))
    assert kept["issue"] == "#1379" and kept["ru"].startswith("остаётся")
    assert {r["id"]: r["owner"] for r in ctx["rules"]}["sintez-checker"] == guard.RULES["sintez-checker"]
    assert {r["id"]: r["owner"] for r in ctx["rules"]}["master-qa"] == guard.RULES["master-qa"]


def test_checker_merge_keeps_build_manifest_and_tightens_status_ratchet():
    """The #1424/#1423 main merge must keep both commands and remove only fixed bypasses."""
    assert agr.SCRIPTS["checker"] == "tools/qa/sintez_checker.py"
    assert agr.SCRIPTS["build-manifest"] == "tools/derive/build_manifest.py"
    rows = guard.rows_of(guard.load_maps(ROOT))
    assert not any(r.rel in SHIMS and r.context == "validation" for r in rows)
    assert not any(at == "jobs/KPP1/scripts/run_agr_checker.py:47"
                   for _, at, _ in guard.LIVE_BYPASS_BASELINE)
    retained = [r for r in rows if r.rule in ("sintez-checker", "master-qa")]
    assert len(retained) == 2
    assert {r.rel: r.status for r in retained} == {
        "jobs/elv-tc-vpm/scripts/run_agr_checker_v003.py": "own-duty",  # #1441: ELV is not delivered
        "jobs/PSU275/scripts/qa_master_psu275.py": "historical",
    }


def test_new_rules_guard_jobs_tools_src_and_need_a_reason():
    for rule in ("sintez-checker", "master-qa"):
        assert guard.GUARDED[rule] == ("jobs", "tools", "src")
        assert rule in guard.REASON_REQUIRED
        assert (ROOT / guard.RULES[rule]).is_file()


def test_guard_green_on_repo_and_no_finding_in_the_shims():
    allowed = guard.allowlist(mini_yaml.load(ROOT / route_map.CONTEXTS))
    findings = guard.scan_for(ROOT, allowed)
    assert guard.compare(findings, allowed) == ([], [])
    mine = {f.path for f in findings if f.rule in ("sintez-checker", "master-qa")}
    assert mine == {"jobs/elv-tc-vpm/scripts/run_agr_checker_v003.py", "jobs/PSU275/scripts/qa_master_psu275.py"}
    assert not mine & set(SHIMS)


@pytest.mark.parametrize("code,rule", [
    ("import x\nx.calculate_all_checks(ctx, op)\n", "sintez-checker"),
    ("from m import calculate_all_checks\ncalculate_all_checks(ctx, op)\n", "sintez-checker"),
    ("def f(m):\n    return m.scripts.check.calculate_all_checks(c, o)\n", "sintez-checker"),
    ("def world_bm(o):\n    return o\n", "master-qa"),
    ("class Q:\n    def world_bm(self, o):\n        pass\n", "master-qa"),
])
def test_guard_red_on_synthetic_copy(tmp_path, code, rule, capsys):
    for top in ("jobs", "tools", "src"):
        (tmp_path / top).mkdir()
    (tmp_path / "jobs/NEW").mkdir()
    (tmp_path / "jobs/NEW/copy.py").write_text(code, encoding="utf-8")
    ctx = tmp_path / "contexts.yaml"
    ctx.write_text("contexts:\n  - id: x\n", encoding="utf-8")
    assert guard.main(["--root", str(tmp_path), "--contexts", str(ctx), "--copies-only"]) == 1
    assert f"NEW COPY [{rule}]" in capsys.readouterr().out


@pytest.mark.parametrize("code", [
    '"""calls calculate_all_checks(ctx, op) inside Blender"""\n',   # prose
    "def calculate_all_checks(ctx, op):\n    pass\n",               # a definition is not a launch
    "x = m.calculate_all_checks\n",                                 # a reference is not a call
    "def world_bm2(o):\n    pass\n",
    "world_bm = None\n",
])
def test_guard_ignores_non_copies(code):
    assert [f for f in guard.scan_text(code, "jobs/x.py") if f.rule in ("sintez-checker", "master-qa")] == []


@pytest.mark.parametrize("rule,code", [("sintez-checker", "m.calculate_all_checks(c, o)\n"),
                                       ("master-qa", "def world_bm(o):\n    pass\n")])
def test_owner_file_is_not_a_copy_of_itself(rule, code):
    assert [f for f in guard.scan_text(code, guard.RULES[rule]) if f.rule == rule] == []


def test_row_without_reason_is_an_error():
    ctx = {"contexts": [{"id": "x", "duplicates": [
        {"at": "jobs/PSU275/scripts/qa_master_psu275.py::world_bm", "rule": "master-qa", "issue": "#1379"}]}]}
    with pytest.raises(ValueError, match="no reason"):
        guard.allowlist(ctx)


# --- shims -------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("shim,owner", sorted(SHIMS.items()))
def test_shim_runs_the_owner_with_unchanged_argv_in_a_fresh_process(tmp_path, shim, owner):
    (tmp_path / shim).parent.mkdir(parents=True)
    shutil.copyfile(ROOT / shim, tmp_path / shim)
    (tmp_path / owner).parent.mkdir(parents=True)
    probe = tmp_path / "ran.json"
    (tmp_path / owner).write_text(
        "import json, sys\njson.dump({'argv': sys.argv[1:], 'name': __name__}, open(%r, 'w'))\n" % str(probe),
        encoding="utf-8")
    subprocess.run([sys.executable, str(tmp_path / shim), "--", "a b", "c.json"], check=True, timeout=60)
    assert json.loads(probe.read_text()) == {"argv": ["--", "a b", "c.json"], "name": "__main__"}


def test_owner_keeps_the_report_shape_and_adds_versions():
    src = (ROOT / "tools/blender/sintez_checker.py").read_text(encoding="utf-8")
    for key in ('"hp": dump(', '"lp": dump(', '"error": err', '"extension_version": version', '"blender": bpy'):
        assert key in src
    assert "def dump(" in src and "calculate_all_checks(bpy.context, op)" in src


# --- the route command -------------------------------------------------------------------------------------------

def test_agr_checker_is_a_route_command_on_every_route_sintez_stage():
    assert agr.SCRIPTS["checker"] == "tools/qa/sintez_checker.py"
    assert route_map.command_exists("agr checker") is True
    for name in EVENTS:
        events = mini_yaml.load(ROOT / "docs/architecture" / f"{name}.events.yaml")
        stage = next(s for s in events["stages"] if s["id"] == "sintez")
        assert stage.get("commands") == ["agr checker"], name


def test_agr_checker_help_in_a_fresh_process():
    out = subprocess.run([sys.executable, "-m", "dt_ai.cli.agr", "checker", "--help"], capture_output=True,
                         text=True, timeout=120, cwd=ROOT)
    assert out.returncode == 0 and "--output" in out.stdout
    top = subprocess.run([sys.executable, "-m", "dt_ai.cli.agr", "--help"], capture_output=True, text=True,
                         timeout=120, cwd=ROOT)
    assert "checker" in top.stdout


# --- agr checker: fail closed ------------------------------------------------------------------------------------

def _row(req, state="verified", errors=0, recs=0, auto=True):
    return {"category": "c", "req_num": req, "name": "n" + req, "state": state, "auto": auto,
            "errors_count": errors, "errors": "", "recommendations_count": recs, "recommendations": ""}


def _report(**over):
    doc = {"extension": "bl_ext.user_default.sintez_agr_checker", "extension_version": "1.6.1", "blender": "5.1.2",
           "address_detected": "", "has_hp": True, "has_lp": True, "error": None, "messages": [],
           "hp": [_row("2.1"), _row("2.2", "undefined", auto=False)], "lp": [_row("3.1")]}
    doc.update(over)
    return doc


def _folder(tmp_path, names=("SM_Synthetic.zip", "0000_Synthetic.zip")):
    folder = tmp_path / "in"
    folder.mkdir()
    for n in names:
        (folder / n).write_bytes(b"PK synthetic " + n.encode())
    return folder


def _snapshot(folder):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()}


@pytest.fixture
def fake_blender(monkeypatch):
    calls = []

    def install(report=None, mutate=None, raise_error=None):
        def run_blender(script, args, *, executable=None, output_json=None, log_path=None, timeout=900, **kw):
            calls.append(dict(script=Path(script), args=[Path(a) for a in args], output_json=Path(output_json),
                              log=Path(log_path)))
            Path(log_path).write_text("fake", encoding="utf-8")
            if mutate:
                mutate(Path(args[0]))
            if raise_error:
                raise BlenderRunError(dict(code=raise_error, message="fake failure"))
            Path(output_json).write_text(json.dumps(report), encoding="utf-8")
            return json.loads(Path(output_json).read_text(encoding="utf-8"))
        monkeypatch.setattr(checker, "run_blender", run_blender)
        return calls
    return install


def test_clean_run_exits_0_writes_summary_and_never_writes_the_input(tmp_path, fake_blender):
    folder = _folder(tmp_path)
    before = _snapshot(folder)
    calls = fake_blender(_report())
    out = tmp_path / "out" / "sintez.json"
    out.parent.mkdir()
    assert checker.main([str(folder), "--output", str(out)]) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["checker_verdict"] == "no_failed_automatic_rule" and doc["failed"] == []
    assert doc["counts"] == {"hp": {"not_measured": 1, "pass": 1}, "lp": {"pass": 1}}
    assert "passed" not in doc
    assert _snapshot(folder) == before
    assert calls[0]["script"] == checker.OWNER and calls[0]["args"][0] == out.parent / "sintez.checker"
    assert sorted(p.name for p in (out.parent / "sintez.checker").iterdir()) == sorted([*before, "checker.json"])
    assert not Path(str(out) + ".partial").exists()


def test_failed_rule_exits_1_and_names_it(tmp_path, fake_blender):
    folder = _folder(tmp_path)
    fake_blender(_report(lp=[_row("3.1", "failed", errors=2)]))
    out = tmp_path / "s.json"
    assert checker.main([str(folder), "--output", str(out)]) == 1
    assert json.loads(out.read_text(encoding="utf-8"))["failed"] == ["lp 3.1"]


def test_one_side_only_ignores_the_empty_template_of_the_other(tmp_path, fake_blender):
    folder = _folder(tmp_path, ("0000_Synthetic.zip",))
    fake_blender(_report(has_hp=False, hp=[_row("2.1", "undefined", auto=False)]))
    out = tmp_path / "s.json"
    assert checker.main([str(folder), "--output", str(out)]) == 0
    assert set(json.loads(out.read_text(encoding="utf-8"))["counts"]) == {"lp"}


def _bad(tmp_path, args, capsys, needle):
    assert checker.main(args) == 2
    err = capsys.readouterr().err
    assert needle in err, err


@pytest.mark.parametrize("names,needle", [
    ((), "no AGR ZIP"),
    (("notes.zip",), "unsupported ZIP name 'notes.zip'"),
    (("SM_A.zip", "SM_B.zip"), "two hp ZIPs"),
    (("0000_A.zip", "0001_B.ZIP"), "two lp ZIPs"),
    (("SM_A.zip", "readme.Zip"), "unsupported ZIP name 'readme.Zip'"),
])
def test_bad_folder_contents_exit_2_and_write_nothing(tmp_path, names, needle, capsys, fake_blender):
    calls = fake_blender(_report())
    folder = _folder(tmp_path, names)
    out = tmp_path / "s.json"
    _bad(tmp_path, [str(folder), "--output", str(out)], capsys, needle)
    assert not out.exists() and calls == [] and not (tmp_path / "s.checker").exists()


def test_missing_folder_exits_2(tmp_path, capsys):
    _bad(tmp_path, [str(tmp_path / "nope"), "--output", str(tmp_path / "s.json")], capsys, "input folder not found")


@pytest.mark.parametrize("make_out,needle", [
    (lambda t, f: f / "s.json", "outside the input folder"),
    (lambda t, f: f / "SM_Synthetic.zip", "new .json"),
    (lambda t, f: f, "new .json"),
    (lambda t, f: t / "s.txt", "new .json"),
    (lambda t, f: t / "missing" / "s.json", "folder not found"),
])
def test_output_aliasing_the_input_exits_2_and_writes_nothing(tmp_path, make_out, needle, capsys, fake_blender):
    calls = fake_blender(_report())
    folder = _folder(tmp_path)
    before = _snapshot(folder)
    _bad(tmp_path, [str(folder), "--output", str(make_out(tmp_path, folder))], capsys, needle)
    assert _snapshot(folder) == before and calls == []


@pytest.mark.parametrize("existing", ["s.json", "s.checker", "s.blender.log", "s.json.partial"])
def test_existing_evidence_path_is_never_reused(tmp_path, existing, capsys, fake_blender):
    calls = fake_blender(_report())
    folder = _folder(tmp_path)
    (tmp_path / existing).write_text("old", encoding="utf-8")
    _bad(tmp_path, [str(folder), "--output", str(tmp_path / "s.json")], capsys, "refusing to reuse")
    assert (tmp_path / existing).read_text(encoding="utf-8") == "old" and calls == []


def test_output_path_alias_through_dotdot_is_refused(tmp_path, capsys, fake_blender):
    fake_blender(_report())
    folder = _folder(tmp_path)
    alias = folder / ".." / "in" / "s.json"
    _bad(tmp_path, [str(folder), "--output", str(alias)], capsys, "outside the input folder")


@pytest.mark.parametrize("over,needle", [
    (dict(extension_version="1.6.0"), "SINTEZ 1.6.1 required"),
    (dict(extension_version=None), "SINTEZ 1.6.1 required"),
    (dict(blender="5.1.1"), "Blender 5.1.2"),
    (dict(has_hp=False), "did not detect SM_Synthetic.zip"),
    (dict(has_lp=None), "did not detect 0000_Synthetic.zip"),
    (dict(lp=[]), "no lp rows"),
    (dict(hp=None), "no hp rows"),
    (dict(error="Traceback ... boom"), "run error"),
    (dict(lp=[_row("3.1", "undefined", auto=False)]), "no measured automatic rule for 0000_Synthetic.zip"),
    (dict(lp=[_row("3.1", "verified", errors=math.nan)]), "invalid counts"),
    (dict(lp=[_row("3.1", "verified", errors=-1)]), "invalid counts"),
    (dict(lp=[_row("3.1", "verified", errors=3)]), "verified with errors"),
])
def test_unusable_evidence_exits_2_and_writes_no_summary(tmp_path, over, needle, capsys, fake_blender):
    fake_blender(_report(**over))
    folder = _folder(tmp_path)
    out = tmp_path / "s.json"
    _bad(tmp_path, [str(folder), "--output", str(out)], capsys, needle)
    assert not out.exists() and not Path(str(out) + ".partial").exists()


def test_report_not_an_object_exits_2(tmp_path, capsys, fake_blender):
    fake_blender(["hp", "lp"])
    _bad(tmp_path, [str(_folder(tmp_path)), "--output", str(tmp_path / "s.json")], capsys, "not a JSON object")


def test_blender_failure_exits_2_naming_the_log(tmp_path, capsys, fake_blender):
    fake_blender(raise_error="nonzero_exit")
    _bad(tmp_path, [str(_folder(tmp_path)), "--output", str(tmp_path / "s.json")], capsys, "s.blender.log")
    assert not (tmp_path / "s.json").exists()


def test_input_changed_during_the_run_exits_2(tmp_path, capsys, fake_blender):
    folder = _folder(tmp_path)
    fake_blender(_report(), mutate=lambda work: (folder / "SM_Synthetic.zip").write_bytes(b"changed"))
    _bad(tmp_path, [str(folder), "--output", str(tmp_path / "s.json")], capsys, "input ZIP changed")
    assert not (tmp_path / "s.json").exists()


def test_working_copy_changed_by_the_checker_exits_2(tmp_path, capsys, fake_blender):
    folder = _folder(tmp_path)
    fake_blender(_report(), mutate=lambda work: (work / "0000_Synthetic.zip").write_bytes(b"x"))
    _bad(tmp_path, [str(folder), "--output", str(tmp_path / "s.json")], capsys, "working copy")


def test_fresh_process_cli_bad_input_exits_2(tmp_path):
    (tmp_path / "in").mkdir()
    env = {k: v for k, v in os.environ.items()}
    out = subprocess.run([sys.executable, str(ROOT / "tools/qa/sintez_checker.py"), str(tmp_path / "in"),
                          "--output", str(tmp_path / "s.json")], capture_output=True, text=True, timeout=120, env=env)
    assert out.returncode == 2 and "no AGR ZIP" in out.stderr and not (tmp_path / "s.json").exists()
