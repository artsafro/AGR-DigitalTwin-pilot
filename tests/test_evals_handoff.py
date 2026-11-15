"""Handoff evidence check (#584); every body, report and repository here is synthetic."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from dt_ai.cli.main import main

ROOT = Path(__file__).resolve().parents[1]


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                          text=True).stdout.strip()


@pytest.fixture(scope="module")
def _repo_template(tmp_path_factory):
    """Synthetic repository: base -> test-first (RED) -> fix (head); `side` is not an ancestor."""
    path = tmp_path_factory.mktemp("handoff-template")
    git(path, "init", "-q")
    git(path, "config", "user.email", "t@example.invalid")
    git(path, "config", "user.name", "t")
    shas = {}
    for name in ("base", "red", "head"):
        (path / f"{name}.txt").write_text(name, encoding="utf-8")
        git(path, "add", "-A")
        git(path, "commit", "-q", "-m", name)
        shas[name] = git(path, "rev-parse", "HEAD")
    git(path, "checkout", "-q", "-b", "side", shas["base"])
    (path / "side.txt").write_text("side", encoding="utf-8")
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "side")
    shas["side"] = git(path, "rev-parse", "HEAD")
    git(path, "checkout", "-q", shas["head"])
    return path, shas


@pytest.fixture
def repo(tmp_path, monkeypatch, _repo_template):
    """Private, ordinary copies of the same history; no hardlinks or shared mutable refs."""
    template, shas = _repo_template
    path = tmp_path / "repo"
    shutil.copytree(template, path)
    monkeypatch.chdir(path)
    return path, dict(shas)


@pytest.fixture
def evals(tmp_path):
    out = tmp_path / "evals"
    out.mkdir()
    report = {"selector": {"suite": "regression", "task": None, "references": False},
              "passed": 0, "failed": 0, "not_measured": 10,
              "checks": [{"passed": None} for _ in range(10)]}
    (out / "report.json").write_text(json.dumps(report), encoding="utf-8")
    return out


def full_run(sha):
    """A real full-suite line (still accepted as evidence when the author has one) [D297]."""
    return (f"- Full suite: `python suite_slot.py --card t_x -- uv run pytest -q` on {sha[:9]}: "
            "13290 passed, 21 skipped, 179 deselected, 0 failed in 1400 s")


DEFERRED = "- Full suite: deferred to merge batch (D297)"


def lines(shas, evals):
    head, red = shas["head"][:9], shas["red"][:9]
    return {
        "full": DEFERRED,
        "affected": f"- Affected tests: {head} `uv run pytest -q tests/test_x.py tests/test_y.py` -> "
                    "40 passed, 0 failed",
        "evals": f"Regression evals: {evals / 'report.json'}; 0 passed / 0 failed / 10 not measured "
                 "(no Claude transcript)",
        "red": f"- Before (RED): {red} `uv run pytest -q tests/test_x.py` -> 3 failed, 1 passed",
        "green": f"- After (GREEN): {head} `uv run pytest -q tests/test_x.py` -> 4 passed, 0 failed",
        "sample": "- Sample output: tmp/hook-sample.txt (`OK: 3 rows`)",
    }


def body(parts, extra=""):
    return ("## Summary\n\nSynthetic body; reviewer: pending.\n\n## Evidence\n\n"
            + "\n".join(v for v in parts.values() if v is not None)
            + "\n\nThe review's input is the diff, not the full suite.\n" + extra)


def run(tmp_path, text, sha, evals, capsys, encoding="utf-8"):
    path = tmp_path / "pr-body.md"
    path.write_bytes(text.encode(encoding) if isinstance(text, str) else text)
    code = main(["evals", "--check-handoff", str(path), "--sha", sha, "--output", str(evals)])
    return code, capsys.readouterr()


def rejected(tmp_path, text, sha, evals, capsys, *reasons):
    code, out = run(tmp_path, text, sha, evals, capsys)
    assert code == 1, out
    for reason in reasons:
        assert reason in out.err, out.err
    assert "OK" not in out.out
    return out


def test_valid_body_passes(tmp_path, repo, evals, capsys):
    _, shas = repo
    code, out = run(tmp_path, body(lines(shas, evals)), shas["head"], evals, capsys)
    assert code == 0, out.err
    assert out.out.strip() == f"OK: handoff evidence complete for {shas['head']}"


@pytest.mark.parametrize("text", [
    "- Full suite: delegated to the reviewer",
    "- Full suite: left for the reviewer (suite_slot.py busy) on {head}: 1 passed",
])
def test_full_suite_delegation_rejected(tmp_path, repo, evals, capsys, text):
    _, shas = repo
    parts = lines(shas, evals)
    parts["full"] = text.format(head=shas["head"][:9])
    rejected(tmp_path, body(parts), shas["head"], evals, capsys, "full suite delegated to the reviewer")


@pytest.mark.parametrize("sentence", [
    "Reviewer please run the full suite.",
    "The full suite is delegated to the reviewer.",
    "Full-suite run deferred to the reviewer.",
])
def test_body_delegation_sentence_rejected(tmp_path, repo, evals, capsys, sentence):
    _, shas = repo
    rejected(tmp_path, body(lines(shas, evals), sentence + "\n"), shas["head"], evals, capsys,
             "full suite delegated to the reviewer")


def test_reviewer_negation_is_not_delegation(tmp_path, repo, evals, capsys):
    _, shas = repo
    extra = ("Verification boundary: reviewer did not run the full suite; reviewer ran 34 tests.\n"
             "Keep author full-suite counts separate from reviewer runs.\n"
             "Issue: do not invent results or ask reviewers to run the full suite.\n"
             "| A1 | `Full suite: delegated to the reviewer` | exit 1 |\n"
             "```\nReviewer please run the full suite.\n```\n")
    code, out = run(tmp_path, body(lines(shas, evals), extra), shas["head"], evals, capsys)
    assert code == 0, out.err


def test_full_suite_requires_suite_slot(tmp_path, repo, evals, capsys):
    _, shas = repo
    parts = lines(shas, evals)
    parts["full"] = f"- Full suite: uv run pytest -q on {shas['head'][:9]}: 13290 passed, 0 failed"
    rejected(tmp_path, body(parts), shas["head"], evals, capsys, "suite_slot.py")


def test_full_suite_must_be_head_or_ancestor(tmp_path, repo, evals, capsys):
    """A real full-suite line names the head or an ancestor (the Affected tests line on head is required
    anyway [D297]); a side commit is not evidence for this head."""
    _, shas = repo
    parts = lines(shas, evals)
    parts["full"] = full_run(shas["side"])
    rejected(tmp_path, body(parts), shas["head"], evals, capsys, "full suite not on head")
    parts["full"] = full_run(shas["red"])
    assert run(tmp_path, body(parts), shas["head"], evals, capsys)[0] == 0
    parts["full"] = "- Full suite: suite_slot.py on HEAD: 13290 passed, 0 failed"
    rejected(tmp_path, body(parts), shas["head"], evals, capsys, "full suite names no commit")


@pytest.mark.parametrize("counts,ok", [
    ("13290 passed, 0 failed", True),
    ("13290 passed", True),
    ("13290 passed, 2 failed", False),
    ("13290 passed, 1 error", False),
    ("13290 passed, 2 failed (known #361)", True),
    ("0 passed, 0 failed", False),
    ("nan passed, 0 failed", False),
    ("inf passed", False),
])
def test_full_suite_counts(tmp_path, repo, evals, capsys, counts, ok):
    _, shas = repo
    parts = lines(shas, evals)
    parts["full"] = f"- Full suite: suite_slot.py on {shas['head'][:9]}: {counts}"
    code, out = run(tmp_path, body(parts), shas["head"], evals, capsys)
    assert code == (0 if ok else 1), out.err


@pytest.mark.parametrize("word", ["not run", "not measured", "pending", "skipped", "n/a: busy",
                                  "TODO", "not rerun"])
def test_full_suite_omission_is_not_pass(tmp_path, repo, evals, capsys, word):
    _, shas = repo
    parts = lines(shas, evals)
    parts["full"] = f"- Full suite: {word}"
    rejected(tmp_path, body(parts), shas["head"], evals, capsys, "full suite")


def test_skipped_count_is_not_omission(tmp_path, repo, evals, capsys):
    _, shas = repo
    parts = lines(shas, evals)
    parts["full"] = f"- Full suite: suite_slot.py on {shas['head'][:9]}: 10 passed, 21 skipped"
    code, out = run(tmp_path, body(parts), shas["head"], evals, capsys)
    assert code == 0, out.err


def test_eval_receipt_validated(tmp_path, repo, evals, capsys):
    _, shas = repo
    parts = lines(shas, evals)
    parts["evals"] = parts["evals"].replace("0 passed / 0 failed / 10", "10 passed / 0 failed / 0")
    rejected(tmp_path, body(parts), shas["head"], evals, capsys, "regression evals: counts differ")
    parts["evals"] = "Regression evals: 13290 passed"
    rejected(tmp_path, body(parts), shas["head"], evals, capsys, "regression evals: not a dt evals receipt")
    code, out = run(tmp_path, body(lines(shas, evals)), shas["head"], tmp_path / "missing", capsys)
    assert code == 1 and "regression evals: report missing" in out.err


def test_all_not_measured_receipt_valid(tmp_path, repo, evals, capsys):
    _, shas = repo
    code, out = run(tmp_path, body(lines(shas, evals)), shas["head"], evals, capsys)
    assert code == 0, out.err


@pytest.mark.parametrize("key,value,reason", [
    ("red", None, "missing Before (RED)"),
    ("red", "- Before (RED): {red} -> 0 failed, 4 passed", "RED shows no failure"),
    ("red", "- Before (RED): {head} -> 3 failed", "RED is not on a commit before head"),
    ("red", "- Before (RED): {side} -> 3 failed", "RED is not on a commit before head"),
    ("red", "- Before (RED): tests failed", "RED names no commit"),
    ("green", None, "missing After (GREEN)"),
    ("green", "- After (GREEN): {red} -> 4 passed, 0 failed", "GREEN not on head"),
    ("green", "- After (GREEN): {head} -> 3 passed, 1 failed", "GREEN has failures"),
    ("green", "- After (GREEN): {head} -> all good", "GREEN shows no passed count"),
])
def test_red_green_required(tmp_path, repo, evals, capsys, key, value, reason):
    _, shas = repo
    parts = lines(shas, evals)
    parts[key] = None if value is None else value.format(**{k: v[:9] for k, v in shas.items()})
    rejected(tmp_path, body(parts), shas["head"], evals, capsys, reason)


def test_red_aliases_and_na(tmp_path, repo, evals, capsys):
    _, shas = repo
    parts = lines(shas, evals)
    parts["red"] = f"- RED: test-first commit `{shas['red'][:9]}`: 2 failed"
    parts["green"] = f"- GREEN: {shas['head']}: 2 passed"
    assert run(tmp_path, body(parts), shas["head"], evals, capsys)[0] == 0
    parts["red"] = "- Before (RED): n/a: docs-only change, no behaviour to regress"
    assert run(tmp_path, body(parts), shas["head"], evals, capsys)[0] == 0
    parts["red"] = "- Before (RED): n/a:"
    rejected(tmp_path, body(parts), shas["head"], evals, capsys, "n/a without a reason")


@pytest.mark.parametrize("value,ok", [
    (None, False),
    ("- Sample output: n/a: the acceptance asks for no sample output", True),
    ("- Sample output: tmp/hook.txt", True),
    ("- Sample output:", False),
    ("- Sample output: not run", False),
    ("- Sample output: pending", False),
])
def test_sample_output_line(tmp_path, repo, evals, capsys, value, ok):
    _, shas = repo
    parts = lines(shas, evals)
    parts["sample"] = value
    code, out = run(tmp_path, body(parts), shas["head"], evals, capsys)
    assert code == (0 if ok else 1), out.err
    if not ok:
        assert "Sample output" in out.err


def test_order_and_markup_independent(tmp_path, repo, evals, capsys):
    _, shas = repo
    parts = lines(shas, evals)
    marked = {k: "* **" + v.lstrip("- ").replace(":", ":**", 1) for k, v in reversed(parts.items())}
    code, out = run(tmp_path, body(marked), shas["head"], evals, capsys)
    assert code == 0, out.err


def test_lines_inside_code_fence_ignored(tmp_path, repo, evals, capsys):
    _, shas = repo
    parts = lines(shas, evals)
    fenced = "```\n" + parts.pop("affected") + "\n```"
    parts["fenced"] = fenced
    rejected(tmp_path, body(parts), shas["head"], evals, capsys, "missing Affected tests")


def test_rework_ancestor_needs_affected_tests(tmp_path, repo, evals, capsys):
    _, shas = repo
    parts = lines(shas, evals)
    parts["full"] = full_run(shas["red"])
    parts["affected"] = (f"- Affected tests: {shas['head'][:9]} `uv run pytest -q tests/test_x.py` "
                         "-> 40 passed, 0 failed")
    assert run(tmp_path, body(parts), shas["head"], evals, capsys)[0] == 0
    parts["affected"] = parts["affected"].replace("0 failed", "1 failed")
    rejected(tmp_path, body(parts), shas["head"], evals, capsys, "Affected tests has failures")
    del parts["affected"]
    rejected(tmp_path, body(parts), shas["head"], evals, capsys, "missing Affected tests")
    parts["full"] = full_run(shas["side"])
    parts["affected"] = f"- Affected tests: {shas['head'][:9]} -> 40 passed, 0 failed"
    rejected(tmp_path, body(parts), shas["head"], evals, capsys, "full suite not on head")


@pytest.mark.parametrize("key", ["full", "affected", "evals", "red", "green", "sample"])
def test_duplicate_lines_rejected(tmp_path, repo, evals, capsys, key):
    _, shas = repo
    parts = lines(shas, evals)
    parts["dup"] = parts[key]
    rejected(tmp_path, body(parts), shas["head"], evals, capsys, "duplicate")


@pytest.mark.parametrize("text", ["", "   \n\n"])
def test_empty_body_lists_every_missing_line(tmp_path, repo, evals, capsys, text):
    _, shas = repo
    out = rejected(tmp_path, text, shas["head"], evals, capsys)
    errors = [line for line in out.err.splitlines() if line.startswith("ERROR: ")]
    assert len(errors) == 5, out.err
    for label in ("Affected tests", "Regression evals", "Before (RED)", "After (GREEN)", "Sample output"):
        assert f"missing {label}" in out.err
    assert "missing Full suite" not in out.err  # D297: the full suite runs in the merge batch


def test_template_placeholders_rejected(tmp_path, repo, evals, capsys):
    _, shas = repo
    template = (ROOT / ".github" / "pull_request_template.md").read_text(encoding="utf-8")
    out = rejected(tmp_path, template, shas["head"], evals, capsys, "placeholder")
    assert "OK" not in out.out


def test_bad_sha_and_files(tmp_path, repo, evals, capsys):
    _, shas = repo
    text = body(lines(shas, evals))
    for sha in ("abc", shas["head"][:9], "0" * 40, ""):
        code, out = run(tmp_path, text, sha, evals, capsys)
        assert code == 1 and "sha" in out.err, (sha, out.err)
    code, out = run(tmp_path, text.encode("utf-16"), shas["head"], evals, capsys)
    assert code == 1 and "body" in out.err
    code = main(["evals", "--check-handoff", str(tmp_path / "nope.md"), "--sha", shas["head"],
                 "--output", str(evals)])
    assert code == 1 and "body" in capsys.readouterr().err
    code = main(["evals", "--check-handoff", str(tmp_path / "pr-body.md"), "--suite", "regression",
                 "--output", str(evals)])
    assert code == 1 and "--check-handoff accepts only" in capsys.readouterr().err


def test_default_sha_is_head(tmp_path, repo, evals, capsys):
    _, shas = repo
    path = tmp_path / "pr-body.md"
    path.write_text(body(lines(shas, evals)), encoding="utf-8")
    assert main(["evals", "--check-handoff", str(path), "--output", str(evals)]) == 0
    assert shas["head"] in capsys.readouterr().out


def test_cli_fresh_process_read_only(tmp_path, repo, evals):
    path_repo, shas = repo
    path = tmp_path / "pr-body.md"
    path.write_text(body(lines(shas, evals)), encoding="utf-8")
    before = {p: p.read_bytes() for p in (path, evals / "report.json")}
    listing = sorted(p.name for p in evals.iterdir())
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    proc = subprocess.run([sys.executable, "-m", "dt_ai.cli.main", "evals", "--check-handoff", str(path),
                           "--sha", shas["head"], "--output", str(evals)],
                          cwd=path_repo, capture_output=True, text=True, env=env, timeout=120)
    assert proc.returncode == 0, proc.stderr
    assert "OK: handoff evidence complete" in proc.stdout
    assert {p: p.read_bytes() for p in before} == before
    assert sorted(p.name for p in evals.iterdir()) == listing


MUTATIONS = {
    "drop": lambda v, s: None,
    "placeholder": lambda v, s: v + " <counts>",
    "not run": lambda v, s: v.split(":", 1)[0] + ": not run",
    "empty": lambda v, s: v.split(":", 1)[0] + ":",
    "pending": lambda v, s: v.split(":", 1)[0] + ": pending",
    "side commit": lambda v, s: v.replace(s["head"][:9], s["side"][:9]).replace(s["red"][:9], s["side"][:9]),
}


def test_generated_mutations_never_pass(tmp_path, repo, evals, capsys):
    """Probe: every single mutation of every required line (5 x 6, 'side commit' only where a sha
    stands) and every pair of dropped lines (10) exits 1, never 0. The optional deferred Full suite
    line is covered by test_deferred_full_suite_mutations_never_pass [D297]."""
    _, shas = repo
    base = lines(shas, evals)
    del base["full"]
    cases = []
    for key in base:
        for name, mutate in MUTATIONS.items():
            if name == "side commit" and key in ("evals", "sample"):
                continue
            parts = dict(base)
            parts[key] = mutate(base[key], shas)
            cases.append((key, name, parts))
    keys = list(base)
    for i, first in enumerate(keys):
        for second in keys[i + 1:]:
            cases.append((first, second, {k: (None if k in (first, second) else v) for k, v in base.items()}))
    passed = [(k, n) for k, n, parts in cases if run(tmp_path, body(parts), shas["head"], evals, capsys)[0] != 1]
    assert len(cases) == 38 and passed == []


def test_label_with_parenthetical_note(tmp_path, repo, evals, capsys):
    """`Full suite (suite_slot, head <sha>): ...` (the PR #583 form) is read; its note is evidence."""
    _, shas = repo
    parts = lines(shas, evals)
    parts["full"] = f"- Full suite (suite_slot, head {shas['head'][:7]}): 13290 passed, 0 failed"
    assert run(tmp_path, body(parts), shas["head"], evals, capsys)[0] == 0
    parts["full"] = f"- Full suite (head {shas['head'][:7]}): 13290 passed, 0 failed"
    rejected(tmp_path, body(parts), shas["head"], evals, capsys, "suite_slot")


def test_label_mentions_are_not_evidence(tmp_path, repo, evals, capsys):
    """A prose line that starts with a code-span label (`Before (RED):`, ...) is no second RED line,
    and a body made only of such mentions still misses every line (#584 dogfood on its own PR body)."""
    _, shas = repo
    mention = ("`Before (RED):`, `After (GREEN):`, `Full suite:`, `Affected tests:` and `Sample output:` "
               "lines are required.\n")
    code, out = run(tmp_path, body(lines(shas, evals), mention), shas["head"], evals, capsys)
    assert code == 0, out.err
    out = rejected(tmp_path, mention, shas["head"], evals, capsys, "missing Before (RED)",
                   "missing Affected tests")
    assert "duplicate" not in out.err


# Review round 1 (PR #612): GREEN/Affected omissions and malformed counts must not pass.
@pytest.mark.parametrize("key,value,reason", [
    ("green", "- After (GREEN): n/a: tests not run", "GREEN"),
    ("green", "- After (GREEN): n/a: docs-only change", "GREEN"),
    ("green", "- After (GREEN): {head} 4 passed, 0 failed; pending rerun", "GREEN is not evidence"),
    ("green", "- After (GREEN): {head} 4 passed, 0 failed; not run, copied old counts",
     "GREEN is not evidence"),
    ("affected", "- Affected tests: {head} 4 passed, 0 failed; not run, copied old counts",
     "Affected tests is not evidence"),
    ("affected", "- Affected tests: {head} 4 passed, 0 failed; pending rerun", "Affected tests is not evidence"),
    ("affected", "- Affected tests: n/a: nothing changed", "Affected tests"),
])
def test_green_affected_omission_rejected(tmp_path, repo, evals, capsys, key, value, reason):
    """Each witness alone, on top of the rework shape (full suite on an ancestor) for Affected tests."""
    _, shas = repo
    parts = lines(shas, evals)
    if key == "affected":
        parts["full"] = full_run(shas["red"])
    parts[key] = value.format(**{k: v[:9] for k, v in shas.items()})
    rejected(tmp_path, body(parts), shas["head"], evals, capsys, reason)


MALFORMED = ["nan", "NaN", "inf", "-inf", "infinity", "-1", "1.5", "0.0", "1e3", "+0", "1e+3", "0x1", "1,5"]


@pytest.mark.parametrize("token", MALFORMED)
@pytest.mark.parametrize("field", ["passed", "failed", "error", "errors"])
def test_count_parser_flags_malformed(token, field):
    """Generated, in-process: every malformed token before every count word is reported, never counted."""
    from twinqa.evals.handoff import parse_counts

    counts, bad = parse_counts(f"abc1234 -> 4 passed, {token} {field}, 0 failed")
    assert bad == [f"{token} {field}"]
    assert (counts["passed"], counts["failed"]) == (4, 0)


@pytest.mark.parametrize("value,expected", [
    ("13676 passed, 21 skipped, 179 deselected, 0 failed in 1374.5 s", {"passed": 13676, "failed": 0}),
    ("13,676 passed, 2 failed (known #361)", {"passed": 13676, "failed": 2}),
    ("4 passed, 1 error", {"passed": 4, "errors": 1}),
    ("all tests passed", {}),
    ("3ff7e37 failed: 3 failed", {"failed": 3}),
    ("", {}),
])
def test_count_parser_valid(value, expected):
    from twinqa.evals.handoff import parse_counts

    counts, bad = parse_counts(value)
    assert bad == []
    assert {k: v for k, v in counts.items() if v is not None} == expected


@pytest.mark.parametrize("key", ["full", "green", "affected", "red"])
@pytest.mark.parametrize("token,field", [("nan", "failed"), ("inf", "passed"), ("-1", "errors"),
                                         ("1.5", "failed")])
def test_malformed_counts_rejected(tmp_path, repo, evals, capsys, token, key, field):
    """CLI: a malformed count on any count-bearing line exits 1 naming it; no OK."""
    _, shas = repo
    head, red = shas["head"][:9], shas["red"][:9]
    counts = {"passed": "4 passed", "failed": "0 failed", "errors": "0 errors"}
    if key == "red":
        counts["failed"] = "3 failed"
    counts[field] = f"{token} {field}"
    tail = ", ".join(counts.values())
    parts = lines(shas, evals)
    if key == "full":
        parts["full"] = f"- Full suite: suite_slot.py on {head}: {tail}"
    elif key == "green":
        parts["green"] = f"- After (GREEN): {head} -> {tail}"
    elif key == "red":
        parts["red"] = f"- Before (RED): {red} -> {tail}"
    else:
        parts["full"] = parts["full"].replace(head, red)
        parts["affected"] = f"- Affected tests: {head} -> {tail}"
    rejected(tmp_path, body(parts), shas["head"], evals, capsys, "malformed count", f"{token} {field}")


@pytest.mark.parametrize("value", [
    "- After (GREEN): {head} 4 passed, nan failed",
    "- Full suite: suite_slot.py on {head}: 4 passed, nan failed",
])
def test_reviewer_nan_witnesses_rejected(tmp_path, repo, evals, capsys, value):
    _, shas = repo
    parts = lines(shas, evals)
    parts["green" if "GREEN" in value else "full"] = value.format(head=shas["head"][:9])
    rejected(tmp_path, body(parts), shas["head"], evals, capsys, "malformed count 'nan failed'")


@pytest.mark.parametrize("key,value", [
    ("green", "- After (GREEN): {head} -> 4 passed, 0 failed"),
    ("green", "- After (GREEN): {head} -> 4 passed, 0 failed, 0 errors"),
    ("green", "- After (GREEN): {head} -> 4 passed"),
    ("full", "- Full suite: suite_slot.py on {head}: 13,676 passed, 21 skipped, 0 failed"),
    ("full", "- Full suite: suite_slot.py on {head}: 13676 passed, 21 skipped, 179 deselected, 0 failed in 1374.5 s"),
    ("affected", "- Affected tests: {head} `pytest -q` -> 156 passed, 0 failed in 94.47s"),
])
def test_valid_integer_counts_and_rework_pass(tmp_path, repo, evals, capsys, key, value):
    """Controls: well-formed integer counts (and the rework shape) still pass."""
    _, shas = repo
    parts = lines(shas, evals)
    if key == "affected":
        parts["full"] = full_run(shas["red"])
    parts[key] = value.format(**{k: v[:9] for k, v in shas.items()})
    code, out = run(tmp_path, body(parts), shas["head"], evals, capsys)
    assert code == 0, out.err


def test_round1_fixes_combined(tmp_path, repo, evals, capsys):
    """Round-1 witnesses together with the earlier fixes (delegation, placeholders) all reported at once."""
    _, shas = repo
    head, red = shas["head"][:9], shas["red"][:9]
    parts = lines(shas, evals)
    parts["full"] = f"- Full suite: suite_slot.py on {red}: 4 passed, nan failed"
    parts["affected"] = f"- Affected tests: {head} 4 passed, 0 failed; not run, copied old counts"
    parts["green"] = "- After (GREEN): n/a: tests not run"
    out = rejected(tmp_path, body(parts, "The full suite is left to the reviewer.\n"), shas["head"], evals,
                   capsys, "malformed count", "Affected tests is not evidence", "GREEN",
                   "delegated to the reviewer")
    assert out.err.count("ERROR:") >= 4


# Review round 2 (PR #612): scientific tokens that also look like a short hex commit id are malformed counts.
SCIENTIFIC = [f"{m}{e}{z}{x}" for m in ("1", "12", "999") for e in ("e", "E") for z in ("", "0", "0000")
              for x in ("3", "10000", "1")]


@pytest.mark.parametrize("token", SCIENTIFIC)
@pytest.mark.parametrize("field", ["passed", "failed", "errors"])
def test_count_parser_flags_scientific(token, field):
    """Generated: mantissa/exponent length variants, incl. 7+ char hex-shaped ones (1e00003), never pass."""
    from twinqa.evals.handoff import parse_counts

    counts, bad = parse_counts(f"abc1234 -> 4 passed, {token} {field}, 0 failed")
    assert bad == [f"{token} {field}"]


@pytest.mark.parametrize("key", ["full", "green", "affected", "red"])
@pytest.mark.parametrize("token", ["1e00003", "1e10000", "12e0003", "1E00003", "999e00001"])
def test_scientific_counts_rejected(tmp_path, repo, evals, capsys, key, token):
    """CLI: hex-shaped scientific counts on every count-bearing line exit 1 naming them; no OK."""
    _, shas = repo
    head, red = shas["head"][:9], shas["red"][:9]
    tail = f"4 passed, {token} failed"
    parts = lines(shas, evals)
    if key == "full":
        parts["full"] = f"- Full suite: suite_slot.py on {head}: {tail}"
    elif key == "green":
        parts["green"] = f"- After (GREEN): {head} {tail}"
    elif key == "red":
        parts["red"] = f"- Before (RED): {red} -> 3 failed, {token} errors"
        token = f"{token} errors"
    else:
        parts["full"] = parts["full"].replace(head, red)
        parts["affected"] = f"- Affected tests: {head} -> {tail}"
    expected = token if key == "red" else f"{token} failed"
    out = rejected(tmp_path, body(parts), shas["head"], evals, capsys, "malformed count", expected)
    assert "OK" not in out.out


@pytest.mark.parametrize("value", [
    "- After (GREEN): {head} 4 passed, 1e00003 failed",
    "- Full suite: suite_slot.py on {head}: 4 passed, 1e10000 failed",
])
def test_reviewer_round2_witnesses_rejected(tmp_path, repo, evals, capsys, value):
    _, shas = repo
    parts = lines(shas, evals)
    parts["green" if "GREEN" in value else "full"] = value.format(head=shas["head"][:9])
    rejected(tmp_path, body(parts), shas["head"], evals, capsys, "malformed count")


@pytest.mark.parametrize("value,expected", [
    ("3ff7e37 failed: 3 failed", {"failed": 3}),
    ("abc1234 passed; 4 passed, 0 failed", {"passed": 4, "failed": 0}),
    ("on deadbeef0123: 13676 passed, 0 failed", {"passed": 13676, "failed": 0}),
    ("1e2f3a4 failed: 2 failed", {"failed": 2}),
])
def test_commit_annotations_still_not_counts(value, expected):
    """Controls: a real hex commit id (letters beyond a single e) before a count word is not a count."""
    from twinqa.evals.handoff import parse_counts

    counts, bad = parse_counts(value)
    assert bad == []
    assert {k: v for k, v in counts.items() if v is not None} == expected


def test_round2_fixes_combined(tmp_path, repo, evals, capsys):
    """Round-2 witness with every round-1 and earlier fix in one body: all reported, no OK."""
    _, shas = repo
    head, red = shas["head"][:9], shas["red"][:9]
    parts = lines(shas, evals)
    parts["full"] = f"- Full suite: suite_slot.py on {red}: 4 passed, 1e10000 failed"
    parts["affected"] = f"- Affected tests: {head} 4 passed, nan failed; pending rerun"
    parts["green"] = f"- After (GREEN): {head} 4 passed, 1e00003 failed"
    out = rejected(tmp_path, body(parts, "The full suite is left to the reviewer.\n"), shas["head"], evals,
                   capsys, "1e10000 failed", "1e00003 failed", "nan failed", "Affected tests is not evidence",
                   "delegated to the reviewer")
    assert out.err.count("ERROR:") >= 4  # the omitted Affected line is one error that quotes its nan
    assert "OK" not in out.out


# D297 (#1400): affected tests per card on the head; the full suite runs once in the merge batch.
def test_deferred_full_suite_with_affected_on_head_passes(tmp_path, repo, evals, capsys):
    """Acceptance: a valid Affected tests line on head + `Full suite: deferred to merge batch (D297)`."""
    _, shas = repo
    code, out = run(tmp_path, body(lines(shas, evals)), shas["head"], evals, capsys)
    assert code == 0, out.err
    assert out.out.strip() == f"OK: handoff evidence complete for {shas['head']}"


@pytest.mark.parametrize("value", [
    None,
    "- Full suite: deferred to merge batch (D297)",
    "- Full suite: deferred to merge batch (rule 68)",
    "- **Full suite:** `deferred to merge batch (D297)`",
])
def test_full_suite_line_optional_or_deferred(tmp_path, repo, evals, capsys, value):
    _, shas = repo
    parts = lines(shas, evals)
    parts["full"] = value
    code, out = run(tmp_path, body(parts), shas["head"], evals, capsys)
    assert code == 0, out.err


def test_real_full_suite_on_head_still_accepted(tmp_path, repo, evals, capsys):
    _, shas = repo
    parts = lines(shas, evals)
    parts["full"] = full_run(shas["head"])
    assert run(tmp_path, body(parts), shas["head"], evals, capsys)[0] == 0


def test_missing_affected_tests_fails(tmp_path, repo, evals, capsys):
    _, shas = repo
    parts = lines(shas, evals)
    del parts["affected"]
    rejected(tmp_path, body(parts), shas["head"], evals, capsys, "missing Affected tests")
    parts["full"] = full_run(shas["head"])  # even a real full suite on head does not replace it
    rejected(tmp_path, body(parts), shas["head"], evals, capsys, "missing Affected tests")


@pytest.mark.parametrize("at", ["red", "side"])
def test_affected_tests_on_old_sha_fails(tmp_path, repo, evals, capsys, at):
    _, shas = repo
    parts = lines(shas, evals)
    parts["affected"] = parts["affected"].replace(shas["head"][:9], shas[at][:9])
    rejected(tmp_path, body(parts), shas["head"], evals, capsys, "Affected tests not on head")


@pytest.mark.parametrize("value", [
    "- Full suite: deferred",
    "- Full suite: deferred to merge batch",
    "- Full suite: deferred to merge batch (D296)",
    "- Full suite: deferred to merge batch (D2970)",
    "- Full suite: deferred to merge batch (rule 49)",
    "- Full suite: deferred to merge batch (D297); 0 passed",
    "- Full suite: deferred to CI (D297)",
    "- Full suite: deferred to merge batch (D297) <reason>",
    "- Full suite: Deferred to the merge batch (D297)",  # review r1 P3: exact wording only
    "- Full suite: deferred to the merge batch (D297)",
    "- Full suite:",
])
def test_malformed_deferral_fails(tmp_path, repo, evals, capsys, value):
    _, shas = repo
    parts = lines(shas, evals)
    parts["full"] = value
    out = rejected(tmp_path, body(parts), shas["head"], evals, capsys)
    assert "full suite" in out.err.lower(), out.err


@pytest.mark.parametrize("value", [
    "- Full suite: deferred to the reviewer (D297)",
    "- Full suite: deferred to merge batch (D297), reviewer runs the full suite",
    "- Full suite: delegated to the reviewer",
])
def test_deferral_to_reviewer_still_fails(tmp_path, repo, evals, capsys, value):
    _, shas = repo
    parts = lines(shas, evals)
    parts["full"] = value
    rejected(tmp_path, body(parts), shas["head"], evals, capsys, "delegated to the reviewer")


def test_reviewer_delegation_sentence_with_deferred_line_fails(tmp_path, repo, evals, capsys):
    _, shas = repo
    rejected(tmp_path, body(lines(shas, evals), "Reviewer: please run the full suite for me.\n"),
             shas["head"], evals, capsys, "delegated to the reviewer")


def test_deferred_full_suite_mutations_never_pass(tmp_path, repo, evals, capsys):
    """Probe: each MUTATIONS entry except 'drop' (allowed) and 'side commit' (no sha) on the deferred line
    exits 1; the deferred line with each required line dropped exits 1 (4 + 5 = 9 cases)."""
    _, shas = repo
    base = lines(shas, evals)
    cases = []
    for name, mutate in MUTATIONS.items():
        if name in ("drop", "side commit"):
            continue
        parts = dict(base)
        parts["full"] = mutate(base["full"], shas)
        cases.append(parts)
    for key in ("affected", "evals", "red", "green", "sample"):
        parts = dict(base)
        parts[key] = None
        cases.append(parts)
    codes = [run(tmp_path, body(parts), shas["head"], evals, capsys)[0] for parts in cases]
    assert len(codes) == 9 and codes == [1] * 9


def test_template_evidence_follows_d297():
    template = (ROOT / ".github" / "pull_request_template.md").read_text(encoding="utf-8")
    assert "- Full suite: deferred to merge batch (D297)" in template
    assert "- Affected tests: <" in template
    assert "rule 49" not in template


# #1469: reviewer-led evidence is not shorthand delegation.
@pytest.mark.parametrize("text", [
    pytest.param("New tests: reviewer r1 witnesses (3 rows), 12 passed.", id="witnesses"),
    pytest.param("Regression tests: reviewer probes from round 1 now pass.", id="probes"),
    pytest.param("Tests to be run by the reviewer: none.", id="none"),
    pytest.param("The reviewer can check the tests I ran: 398 passed.", id="completed"),
])
def test_reviewer_clause_controls(tmp_path, repo, evals, capsys, text):
    from twinqa.evals.handoff import delegation

    assert delegation(text) is None
    _, shas = repo
    code, out = run(tmp_path, body(lines(shas, evals), text), shas["head"], evals, capsys)
    assert code == 0, out.err


@pytest.mark.parametrize("text", [
    pytest.param("Tests to be executed by the reviewer.", id="executed"),
    pytest.param("Tests are to be run by the reviewer.", id="are-to-be"),
    pytest.param("Tests will be run by the reviewer.", id="will-be"),
    pytest.param("Remaining tests: reviewer.", id="remaining"),
    pytest.param("Tests: Reviewer", id="end"),
])
def test_reviewer_clause_delegations(tmp_path, repo, evals, capsys, text):
    from twinqa.evals.handoff import delegation

    assert delegation(text) is not None
    _, shas = repo
    rejected(tmp_path, body(lines(shas, evals), text), shas["head"], evals, capsys,
             "tests delegated to the reviewer")


@pytest.mark.parametrize("action", ["rerun", "run"])
def test_reviewer_completed_reruns_rejected(tmp_path, repo, evals, capsys, action):
    from twinqa.evals.handoff import delegation

    text = f"The reviewer should {action} the tests I ran: 398 passed."
    assert delegation(text) is not None
    _, shas = repo
    rejected(tmp_path, body(lines(shas, evals), text), shas["head"], evals, capsys,
             "tests delegated to the reviewer")


def test_reviewer_inspection_then_execution_rejected(tmp_path, repo, evals, capsys):
    from twinqa.evals.handoff import delegation

    text = "The reviewer should check the tests I ran and then run the full suite."
    assert delegation(text) is not None
    _, shas = repo
    rejected(tmp_path, body(lines(shas, evals), text), shas["head"], evals, capsys,
             "full suite delegated to the reviewer")


def test_reviewer_clause_generated_probe():
    """Synthetic clause boundaries/passive matrix, including earlier negation/order controls."""
    from twinqa.evals.handoff import delegation

    cases = []
    for noun in ("tests", "test files", "test suite"):
        for recipient in ("reviewer", "the reviewer", "reviewers"):
            for end in ("", ".", ";", "!", "?", "\n"):
                cases.append((f"{noun}: {recipient}{end}", True))
            for tail in (" witnesses (3 rows), 12 passed.", " probes now pass.", " notes."):
                cases.append((f"{noun}: {recipient}{tail}", False))
            for auxiliary in ("to be", "are to be", "will be"):
                for verb in ("run", "executed", "checked", "verified"):
                    phrase = f"{noun} {auxiliary} {verb} by {recipient}"
                    cases.extend(((phrase + ".", True), ("No " + phrase + ".", False),
                                  (phrase + ": none.", False),
                                  (phrase + ": none. Tests: reviewer.", True),
                                  (phrase + ": none pending.", True)))
    for actor in ("I", "we", "the author"):
        for verb in ("ran", "executed", "checked", "verified"):
            for action in ("check", "verify"):
                cases.append((f"The reviewer can {action} the tests {actor} {verb}: 398 passed.", False))
    assert len(cases) == 645
    for text, expected in cases:
        for _ in range(2):
            assert (delegation(text) is not None) == expected, text
            assert delegation("") is None  # reset after every positive and negative


# Review r2 (PR #1401), #1403: shorthand and active verify are delegation.
@pytest.mark.parametrize("text", [
    pytest.param("Remaining tests: reviewer.", id="shorthand"),
    pytest.param("The reviewer should verify the test suite.", id="verify"),
    pytest.param("Tests to be run by the reviewer.", id="passive"),
])
def test_passive_verify_shorthand_rejected(tmp_path, repo, evals, capsys, text):
    _, shas = repo
    rejected(tmp_path, body(lines(shas, evals), text + "\n"),
             shas["head"], evals, capsys, "tests delegated to the reviewer")


@pytest.mark.parametrize("text", [
    pytest.param("The reviewer does not run the tests.", id="not-run"),
    pytest.param("No tests are handed to the reviewer.", id="no-handover"),
    pytest.param("The reviewer's P1 tests now pass.", id="possessive"),
])
def test_passive_verify_controls_pass(tmp_path, repo, evals, capsys, text):
    _, shas = repo
    code, out = run(tmp_path, body(lines(shas, evals), text), shas["head"], evals, capsys)
    assert code == 0, out.err


def test_passive_verify_generated_probe():
    """Synthetic exhaustive 3 nouns x 6 forms x 2 recipients x 2 polarities = 72 checks."""
    from twinqa.evals.handoff import delegation

    forms = [
        ("{r} should verify {n}.", "{r} should not verify {n}."),
        ("{r} should check {n}.", "{r} should not check {n}."),
        ("{n} to be run by {r}.", "No {n} to be run by {r}."),
        ("{n} to be checked by {r}.", "No {n} to be checked by {r}."),
        ("{n} to be verified by {r}.", "No {n} to be verified by {r}."),
        ("{n}: {r}.", "No {n}: {r}."),
    ]
    for noun in ("tests", "test files", "test suite"):
        for reviewer in ("the reviewer", "reviewers"):
            for positive, negative in forms:
                for form, expected in ((positive, True), (negative, False)):
                    text = form.format(n=noun, r=reviewer)
                    assert (delegation(text) is not None) == expected, text


def test_passive_verify_order_repeat_reset(tmp_path, repo, evals, capsys):
    _, shas = repo
    clean = "The reviewer does not verify the tests."
    bad = "Tests to be checked by the reviewer."
    for text in (clean + "; " + bad, bad + "; " + clean, bad + "\n" + bad):
        for _ in range(2):
            rejected(tmp_path, body(lines(shas, evals), text), shas["head"], evals, capsys,
                     "tests delegated to the reviewer")
        code, out = run(tmp_path, body(lines(shas, evals), clean), shas["head"], evals, capsys)
        assert code == 0, out.err


@pytest.mark.parametrize("partial", [False, True], ids=["empty", "partial"])
def test_passive_verify_empty_partial(tmp_path, repo, evals, capsys, partial):
    _, shas = repo
    text = lines(shas, evals)["affected"] if partial else ""
    rejected(tmp_path, text, shas["head"], evals, capsys, "missing Regression evals")


def test_passive_verify_combined_guards(tmp_path, repo, evals, capsys):
    _, shas = repo
    parts = lines(shas, evals)
    parts["green"] = f"- After (GREEN): {shas['head'][:9]} 4 passed, nan failed"
    parts["affected"] = parts["affected"].replace(shas["head"][:9], shas["red"][:9])
    text = ("Remaining tests: reviewer.\nThe reviewer should verify the test suite.\n"
            "Tests to be run by the reviewer.\nReviewer please run the tests.")
    out = rejected(tmp_path, body(parts, text), shas["head"], evals, capsys,
                   "malformed count 'nan failed'", "Affected tests not on head", "tests delegated to the reviewer")
    assert out.err.count("tests delegated to the reviewer") == 4


def test_passive_verify_quoted_paths_pass(tmp_path, repo, evals, capsys):
    _, shas = repo
    text = ("`Remaining tests: reviewer.`\n```\nTests to be verified by the reviewer.\n```\n"
            "The reviewer should check tests/test_x.py.\n"
            "The reviewer should verify test_x.\nThe reviewer’s P1 tests now pass.")
    code, out = run(tmp_path, body(lines(shas, evals), text), shas["head"], evals, capsys)
    assert code == 0, out.err


def test_passive_verify_fresh_process_read_only(tmp_path, repo, evals):
    """Exercise the real CLI in fresh processes, keeping aliased input and all files unchanged."""
    _, shas = repo
    path = tmp_path / "fresh-body.md"
    alias = tmp_path / "body-alias.md"
    path.write_text("", encoding="utf-8")
    os.link(path, alias)
    rows = [
        ("Remaining tests: reviewer.", 1),
        ("The reviewer should verify the test suite.", 1),
        ("Tests to be run by the reviewer.", 1),
        ("The reviewer does not run the tests.", 0),
        ("No tests are handed to the reviewer.", 0),
        ("The reviewer's P1 tests now pass.", 0),
    ]
    # Duplicate failing input then reset to the clean body in fresh processes.
    for text, expected in rows + [rows[0], ("", 0)]:
        path.write_text(body(lines(shas, evals), text), encoding="utf-8")
        before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        proc = subprocess.run(
            [sys.executable, "-m", "dt_ai.cli.main", "evals", "--check-handoff", str(alias),
             "--sha", shas["head"], "--output", str(evals)],
            capture_output=True, text=True, env=env, timeout=60,
        )
        assert proc.returncode == expected, (text, proc.stdout, proc.stderr)
        if expected:
            assert "tests delegated to the reviewer" in proc.stderr
            assert "OK" not in proc.stdout
        else:
            assert "OK: handoff evidence complete" in proc.stdout
        after = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
        assert after == before


# Review r1 (PR #1401) P1: handing ANY tests to the reviewer fails, not only the full suite.
@pytest.mark.parametrize("where, text", [
    ("affected", "; the reviewer runs the remaining test files"),
    ("prose", "The reviewer runs the affected tests.\n"),
    ("prose", "Reviewer: please run the tests.\n"),
    ("prose", "The tests are left to the reviewer.\n"),
    ("prose", "The remaining tests are for the reviewer to run.\n"),
    ("prose", "I leave the test files to the reviewer.\n"),
    ("prose", "Reviewers should rerun all tests.\n"),
    ("prose", "Tests delegated to the reviewer.\n"),
    ("affected", " (reviewer runs pytest on the rest)"),
    ("prose", "The reviewer does not run the lint; the reviewer runs the tests.\n"),
    ("prose", "The reviewer, not the author, runs the tests.\n"),
])
def test_tests_delegated_to_reviewer_fail(tmp_path, repo, evals, capsys, where, text):
    _, shas = repo
    parts = lines(shas, evals)
    extra = ""
    if where == "affected":
        parts["affected"] += text
    else:
        extra = text
    out = rejected(tmp_path, body(parts, extra), shas["head"], evals, capsys, "delegated to the reviewer")
    assert "OK" not in out.out


@pytest.mark.parametrize("text", [
    "The reviewer does not run the tests.\n",
    "The author never hands tests to the reviewer.\n",
    "Reviewer did not run the tests; reviewer ran 34 tests to spot-check.\n",
    "Added a regression test for the reviewer's P1.\n",
    "Review r1: the GREEN run on test_x failed before the fix.\n",
    "Do not leave the tests to the reviewer.\n",
])
def test_tests_reviewer_negation_controls_pass(tmp_path, repo, evals, capsys, text):
    _, shas = repo
    code, out = run(tmp_path, body(lines(shas, evals), text), shas["head"], evals, capsys)
    assert code == 0, out.err


def test_template_reviewer_sentences_pass(tmp_path, repo, evals, capsys):
    """Every template line that mentions the reviewer (e.g. 'never hands tests to the reviewer') passes."""
    _, shas = repo
    template = (ROOT / ".github" / "pull_request_template.md").read_text(encoding="utf-8")
    prose = [line for line in template.splitlines() if "reviewer" in line.lower() and "<" not in line]
    assert prose
    code, out = run(tmp_path, body(lines(shas, evals), "\n".join(prose) + "\n"), shas["head"], evals, capsys)
    assert code == 0, (prose, out.err)


def test_delegation_probe_generated():
    """Probe: 6 nouns x (3 run + 3 hand-over) phrasings = 36 delegations, each caught; the same 36 with a
    negation ('not'/'never') are all clean (36 + 36 = 72 cases)."""
    from twinqa.evals.handoff import delegation
    nouns = ["tests", "the affected tests", "the remaining test files", "the full suite", "pytest", "all tests"]
    run_forms = ["The reviewer runs {n}.", "Reviewer: please run {n}.", "Reviewers will rerun {n}."]
    hand_forms = ["{N} are left to the reviewer.", "I leave {n} to the reviewer.", "{N} go to the reviewer."]
    neg_run = ["The reviewer does not run {n}.", "Reviewer: never run {n}.", "Reviewers will not rerun {n}."]
    neg_hand = ["{N} are not left to the reviewer.", "I never leave {n} to the reviewer.",
                "No {n} go to the reviewer."]
    def fill(form, noun):
        return form.format(n=noun, N=noun[0].upper() + noun[1:])
    caught = [delegation(fill(f, n)) is not None for n in nouns for f in run_forms + hand_forms]
    clean = [delegation(fill(f, n)) is None for n in nouns for f in neg_run + neg_hand]
    assert (sum(caught), sum(clean)) == (36, 36), (
        [fill(f, n) for n in nouns for f in run_forms + hand_forms if delegation(fill(f, n)) is None],
        [fill(f, n) for n in nouns for f in neg_run + neg_hand if delegation(fill(f, n)) is not None])
