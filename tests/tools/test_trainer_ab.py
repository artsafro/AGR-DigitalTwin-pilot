"""Trainer A/B probe of harness edits [D411] (#1924): variant check, overlay, contrast report, CLI refusals.

Pattern: n/a | new-case: tests of the trainer A/B contrast of two harness variants on one etalon.
"""
import itertools
import json
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/trainer"))
import trainer as T  # noqa: E402
import trainer_ab as AB  # noqa: E402

E = {"id": "g22-k2-stage1", "scenario": "oks-vpm", "key": {"path": "C:/x/review-k2/K2_v002r1_body_quad.fbx",
                                                           "sha256": "ab" * 32},
     "rejected": [], "hidden_repo_paths": ["jobs/G22"]}


def _w(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _variants(tmp_path, old=None, new=None):
    o, n = tmp_path / "old", tmp_path / "new"
    o.mkdir()
    n.mkdir()
    for rel, text in (old or {}).items():
        _w(o / rel, text)
    for rel, text in (new or {}).items():
        _w(n / rel, text)
    return o, n


# ---------------------------------------------------------------- variants: fail closed
def test_check_variants_lists_the_edit_and_scope(tmp_path):
    o, n = _variants(tmp_path, {}, {"docs/agents/SKELETONS.md": "edited\n"})
    v = AB.check_variants(o, n, tmp_path / "out", "INVARIANT", E)
    assert v["edits"] == ["docs/agents/SKELETONS.md"] and v["scope"] == "INVARIANT"
    assert v["old_files"] == {} and list(v["new_files"]) == ["docs/agents/SKELETONS.md"]
    assert v["scope_warnings"] == []


@pytest.mark.parametrize("old,new,needle", [
    ({}, {}, "identical"),                                            # empty input: nothing to probe
    ({"a.md": "x"}, {"a.md": "x"}, "identical"),                     # same bytes in both arms
    ({}, {"docs/trainer/etalons.json": "{}"}, "hidden"),             # would re-add the hidden bank
    ({}, {"jobs/G22/README.md": "x"}, "hidden"),                     # etalon hidden_repo_paths
    ({}, {".git/config": "x"}, ".git"),                              # repository internals
])
def test_check_variants_refuses(tmp_path, old, new, needle):
    o, n = _variants(tmp_path, old, new)
    with pytest.raises(AB.AbError, match=needle):
        AB.check_variants(o, n, tmp_path / "out", "INVARIANT", E)


def test_check_variants_refuses_unknown_scope_alias_and_bad_out(tmp_path):
    o, n = _variants(tmp_path, {}, {"a.md": "x"})
    with pytest.raises(AB.AbError, match="BOTH"):
        AB.check_variants(o, n, tmp_path / "out", "BOTH", E)
    with pytest.raises(AB.AbError, match="same folder"):
        AB.check_variants(o, tmp_path / "old" / ".", tmp_path / "out", "INVARIANT", E)
    with pytest.raises(AB.AbError, match="not a folder"):
        AB.check_variants(o, tmp_path / "missing", tmp_path / "out", "INVARIANT", E)
    (tmp_path / "exists").mkdir()
    with pytest.raises(AB.AbError, match="exists"):
        AB.check_variants(o, n, tmp_path / "exists", "INVARIANT", E)
    with pytest.raises(AB.AbError, match="inside"):
        AB.check_variants(o, n, n / "out", "INVARIANT", E)
    with pytest.raises(AB.AbError, match="inside"):
        AB.check_variants(tmp_path / "old", n, tmp_path, "INVARIANT", E)


def test_scope_warning_when_paths_disagree_with_the_tag(tmp_path):
    o, n = _variants(tmp_path, {}, {"docs/scenarios/oks-vpm.md": "x", "AGENTS.md": "y"})
    inv = AB.check_variants(o, n, tmp_path / "o1", "INVARIANT", E)["scope_warnings"]
    dom = AB.check_variants(o, n, tmp_path / "o2", "DOMAIN", E)["scope_warnings"]
    assert inv == ["docs/scenarios/oks-vpm.md"] and dom == ["AGENTS.md"]


# ---------------------------------------------------------------- overlay into the practice tree
def _src(tmp_path):
    src = tmp_path / "src"
    _w(src / "docs/agents/SKELETONS.md", "original\n")
    _w(src / "tools/x.py", "a = 1\n")
    subprocess.run(["git", "init", "-q", str(src)], check=True)
    for args in (["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "c"]):
        subprocess.run(["git", "-C", str(src), *args], check=True)
    return src


def test_overlay_is_committed_and_not_counted_as_agent_code(tmp_path):
    src = _src(tmp_path)
    wt = tmp_path / "wt"
    T.practice_tree(src, "HEAD", wt, E)
    _, n = _variants(tmp_path, {}, {"docs/agents/SKELETONS.md": "edited\n", "tools/x.py": "a = 2\nb = 3\n"})
    files = T.apply_overlay(wt, n, E)
    assert sorted(files) == ["docs/agents/SKELETONS.md", "tools/x.py"]
    assert (wt / "docs/agents/SKELETONS.md").read_text(encoding="utf-8") == "edited\n"
    log = subprocess.run(["git", "-C", str(wt), "log", "--oneline"], capture_output=True, text=True).stdout
    assert len(log.splitlines()) == 2
    assert subprocess.run(["git", "-C", str(wt), "status", "--porcelain"], capture_output=True,
                          text=True).stdout == ""
    assert T.new_code_lines(wt) == (0, [])


def test_overlay_naming_the_key_is_refused(tmp_path):
    src = _src(tmp_path)
    wt = tmp_path / "wt"
    T.practice_tree(src, "HEAD", wt, E)
    _, n = _variants(tmp_path, {}, {"docs/hint.md": "use K2_v002r1_body_quad.fbx\n"})
    with pytest.raises(T.TrainerError, match="docs/hint.md"):
        T.apply_overlay(wt, n, E)


def test_empty_overlay_is_a_noop_baseline(tmp_path):
    src = _src(tmp_path)
    wt = tmp_path / "wt"
    T.practice_tree(src, "HEAD", wt, E)
    o, _ = _variants(tmp_path)
    assert T.apply_overlay(wt, o, E) == {}
    log = subprocess.run(["git", "-C", str(wt), "log", "--oneline"], capture_output=True, text=True).stdout
    assert len(log.splitlines()) == 1


# ---------------------------------------------------------------- arm records and the contrast report
def _ev(cmd, code):
    return json.dumps({"type": "item.completed", "item": {"type": "command_execution", "command": cmd,
                                                         "exit_code": code, "status": "completed"}})


def _arm(tmp_path, name, cmds, used, bypassed, built=None, exit_=0, tokens=100):
    d = tmp_path / name
    (d / "built").mkdir(parents=True)
    for fn, text in (built or {}).items():
        _w(d / "built" / fn, text)
    lines = [_ev(c, rc) for c, rc in cmds]
    lines.append(json.dumps({"type": "turn.completed", "usage": {"input_tokens": tokens, "output_tokens": 5}}))
    _w(d / "events.jsonl", "\n".join(lines) + "\n")
    _w(d / "run.json", json.dumps({"schema": "trainer-run/1", "etalon": E["id"], "lane": "codex",
                                   "model": "m", "origin_main": "abc", "exit": exit_, "stages_used": used,
                                   "stages_bypassed": bypassed, "tokens": {"input_tokens": tokens},
                                   "questions": 0}))
    return d


def _score(**st):
    steps = {s: {"status": "not_run"} for s in T.STEPS}
    for k, v in st.items():
        steps[k] = {"status": v}
    return {"schema": "trainer-score/1", "steps": steps, "first_failing_step": T.first_failing(steps),
            "score": sum(v["status"] == "pass" for v in steps.values())}


def test_arm_record_first_command_wrong_turns_and_deliverable(tmp_path):
    d = _arm(tmp_path, "a", [('"C:\\\\WINDOWS\\\\powershell.exe" -Command \'Get-Content -Raw AGENTS.md | x\'', 0),
                             ("python bad.py", 1), ("agr inspect x", "0"), ("rg y", 2)],
             ["inspect"], ["body"], built={"m.fbx": "fbx", "QUESTIONS.md": "q"})
    r = AB.arm_record(d, _score(artifact="fail"))
    assert r["first_command_tokens"] == ["Get-Content", "-Raw", "AGENTS.md", "|"]
    assert r["wrong_turns"] == 2 and r["commands"] == 4 and r["tokens_in"] == 100
    assert sorted(r["deliverable"]) == ["QUESTIONS.md", "m.fbx"]


def test_arm_record_fail_closed(tmp_path):
    with pytest.raises(AB.AbError, match="run.json"):
        AB.arm_record(tmp_path / "none", _score())
    d = _arm(tmp_path, "a", [], [], [])
    _w(d / "run.json", "{not json")
    with pytest.raises(AB.AbError, match="run.json"):
        AB.arm_record(d, _score())


def _pair(tmp_path, old_score, new_score, old_used=("inspect",), new_used=("inspect",), new_exit=0,
          old_built=None, new_built=None, scen=("inspect", "body")):
    o = _arm(tmp_path, "o", [("agr inspect", 0), ("x", 1)], list(old_used),
             [s for s in scen if s not in old_used], built=old_built)
    n = _arm(tmp_path, "n", [("agr inspect", 0)], list(new_used), [s for s in scen if s not in new_used],
             built=new_built, exit_=new_exit, tokens=60)
    var = {"scope": "INVARIANT", "edits": ["AGENTS.md"], "old_files": {}, "new_files": {"AGENTS.md": "h"},
           "scope_warnings": []}
    return AB.contrast(AB.arm_record(o, old_score), AB.arm_record(n, new_score), var)


def test_contrast_fixed_unchanged_regressed(tmp_path):
    rep = _pair(tmp_path / "1", _score(artifact="fail"), _score(artifact="pass", readback="pass"))
    assert rep["verdict"] == "fixed" and rep["steps"]["artifact"]["verdict"] == "fixed"
    assert rep["wrong_turns"] == {"old": 1, "new": 0, "delta": -1}
    assert rep["tokens_in"] == {"old": 100, "new": 60, "delta": -40}
    rep = _pair(tmp_path / "2", _score(artifact="fail"), _score(artifact="fail"))
    assert rep["verdict"] == "unchanged"
    rep = _pair(tmp_path / "3", _score(artifact="pass"), _score(artifact="fail"))
    assert rep["verdict"] == "regressed" and rep["steps"]["artifact"]["verdict"] == "regressed"


def test_contrast_skeleton_stage_verdicts(tmp_path):
    rep = _pair(tmp_path / "1", _score(), _score(), old_used=("inspect",), new_used=("inspect", "body"))
    assert rep["stages"]["body"] == {"old": "bypassed", "new": "used", "verdict": "fixed"}
    assert rep["verdict"] == "fixed"
    rep = _pair(tmp_path / "2", _score(), _score(), old_used=("inspect", "body"), new_used=("inspect",))
    assert rep["verdict"] == "regressed"


def test_mixed_fix_and_regression_is_regressed(tmp_path):
    rep = _pair(tmp_path, _score(artifact="pass"), _score(artifact="fail"), old_used=("inspect",),
                new_used=("inspect", "body"))
    assert rep["verdict"] == "regressed"


def test_deliverable_diff(tmp_path):
    rep = _pair(tmp_path, _score(), _score(), old_built={"a.fbx": "1", "b.md": "x", "gone.txt": "g"},
                new_built={"a.fbx": "2", "b.md": "x", "new.json": "{}"})
    assert rep["deliverable"] == {"added": ["new.json"], "removed": ["gone.txt"], "changed": ["a.fbx"],
                                  "same": ["b.md"]}


@pytest.mark.parametrize("new_exit", ["timeout", 1])
def test_incomplete_arm_is_inconclusive_never_unchanged(tmp_path, new_exit):
    rep = _pair(tmp_path, _score(artifact="fail"), _score(artifact="fail"), new_exit=new_exit)
    assert rep["verdict"] == "inconclusive" and "new" in rep["inconclusive_reason"]


def test_score_error_arm_is_inconclusive(tmp_path):
    rep = _pair(tmp_path, _score(artifact="fail"), {"error": "several FBX"})
    assert rep["verdict"] == "inconclusive" and "several FBX" in rep["inconclusive_reason"]


def test_step_verdict_brute_force_over_all_status_pairs():
    """Invariant: fixed iff non-pass -> pass, regressed iff pass -> non-pass; never fixed/regressed otherwise."""
    n = 0
    for o, nw in itertools.product(sorted(T.STATUSES), repeat=2):
        v = AB.step_verdict(o, nw)
        want = "fixed" if o != "pass" and nw == "pass" else "regressed" if o == "pass" and nw != "pass" \
            else "unchanged"
        assert v == want, (o, nw)
        n += 1
    assert n == len(T.STATUSES) ** 2
    with pytest.raises(AB.AbError, match="bogus"):
        AB.step_verdict("bogus", "pass")


def test_markdown_report_names_verdict_and_every_step(tmp_path):
    rep = _pair(tmp_path, _score(artifact="fail"), _score(artifact="pass"))
    md = AB.render_md(rep)
    assert "Verdict: **fixed**" in md and all(f"| {s} |" in md for s in T.STEPS)


# ---------------------------------------------------------------- cmd_ab orchestration (stubbed run / score)
def test_cmd_ab_runs_both_arms_on_one_head_and_writes_one_report(tmp_path):
    o, n = _variants(tmp_path, {}, {"AGENTS.md": "edited\n"})
    out = tmp_path / "ab"
    calls = []

    def run_fn(a, bank):
        calls.append((a.etalon, a.lane, a.head, Path(a.overlay).name, Path(a.out).name))
        _arm(Path(a.out).parent, Path(a.out).name, [("agr inspect", 0)], ["inspect"], ["body"])
        return 0

    def score_fn(e, built, work):
        return _score(artifact="fail")

    a = Namespace(etalon="g22-k2-stage1", lane="codex", old=str(o), new=str(n), out=str(out), scope="INVARIANT",
                  timeout_s=10, dry_run=False)
    bank = {"etalons": [dict(E, practice_ready=True)]}
    assert AB.cmd_ab(a, bank, run_fn=run_fn, score_fn=score_fn, head_fn=lambda: "deadbeef") == 0
    assert calls == [("g22-k2-stage1", "codex", "deadbeef", "old", "old"),
                     ("g22-k2-stage1", "codex", "deadbeef", "new", "new")]
    rep = json.loads((out / "ab.json").read_text(encoding="utf-8"))
    assert rep["schema"] == "trainer-ab/1" and rep["verdict"] == "unchanged" and rep["origin_main"] == "deadbeef"
    assert (out / "ab.md").is_file() and (out / "old" / "score.json").is_file()


def test_cmd_ab_refusal_writes_nothing(tmp_path):
    o, n = _variants(tmp_path, {"a.md": "x"}, {"a.md": "x"})
    a = Namespace(etalon="g22-k2-stage1", lane="codex", old=str(o), new=str(n), out=str(tmp_path / "ab"),
                  scope="INVARIANT", timeout_s=10, dry_run=False)
    with pytest.raises(AB.AbError):
        AB.cmd_ab(a, {"etalons": [dict(E, practice_ready=True)]}, run_fn=None, score_fn=None, head_fn=None)
    assert not (tmp_path / "ab").exists()


def test_cli_ab_fresh_process_refusal(tmp_path):
    o, n = _variants(tmp_path, {}, {})
    p = subprocess.run([sys.executable, str(ROOT / "tools/trainer/trainer.py"), "ab", "g22-k2-stage1",
                        "--ab", str(o), str(n), "--scope", "INVARIANT", "--out", str(tmp_path / "ab")],
                       capture_output=True, text=True, cwd=ROOT)
    assert p.returncode == 2 and "identical" in p.stderr and not (tmp_path / "ab").exists()


def test_d411_row_recorded_once():
    rows = [ln for ln in (ROOT / "docs/decisions.md").read_text(encoding="utf-8").splitlines()
            if ln.startswith("| D411 |")]
    assert len(rows) == 1 and "A/B" in rows[0] and "LESSONS" in rows[0]
