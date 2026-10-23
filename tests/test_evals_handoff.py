"""Handoff evidence check (#584); every body, report and repository here is synthetic."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from dt_ai.cli.main import main

ROOT = Path(__file__).resolve().parents[1]


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                          text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """Synthetic repository: base -> test-first (RED) -> fix (head); `side` is not an ancestor."""
    path = tmp_path / "repo"
    path.mkdir()
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
    monkeypatch.chdir(path)
    return path, shas


@pytest.fixture
def evals(tmp_path):
    out = tmp_path / "evals"
    out.mkdir()
    report = {"selector": {"suite": "regression", "task": None, "references": False},
              "passed": 0, "failed": 0, "not_measured": 10,
              "checks": [{"passed": None} for _ in range(10)]}
    (out / "report.json").write_text(json.dumps(report), encoding="utf-8")
    return out


def lines(shas, evals):
    head, red = shas["head"][:9], shas["red"][:9]
    return {
        "full": f"- Full suite: `python suite_slot.py --card t_x -- uv run pytest -q` on {head}: "
                "13290 passed, 21 skipped, 179 deselected, 0 failed in 1400 s",
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


def test_full_suite_must_be_exact_head(tmp_path, repo, evals, capsys):
    _, shas = repo
    parts = lines(shas, evals)
    for other in ("side", "red"):
        parts["full"] = lines(shas, evals)["full"].replace(shas["head"][:9], shas[other][:9])
        rejected(tmp_path, body(parts), shas["head"], evals, capsys, "full suite not on head")
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
    fenced = "```\n" + parts.pop("full") + "\n```"
    parts["fenced"] = fenced
    rejected(tmp_path, body(parts), shas["head"], evals, capsys, "missing Full suite")


def test_rework_ancestor_needs_affected_tests(tmp_path, repo, evals, capsys):
    _, shas = repo
    parts = lines(shas, evals)
    parts["full"] = parts["full"].replace(shas["head"][:9], shas["red"][:9])
    parts["affected"] = (f"- Affected tests: {shas['head'][:9]} `uv run pytest -q tests/test_x.py` "
                         "-> 40 passed, 0 failed")
    assert run(tmp_path, body(parts), shas["head"], evals, capsys)[0] == 0
    parts["affected"] = parts["affected"].replace("0 failed", "1 failed")
    rejected(tmp_path, body(parts), shas["head"], evals, capsys, "Affected tests has failures")
    del parts["affected"]
    rejected(tmp_path, body(parts), shas["head"], evals, capsys, "full suite not on head")
    parts["full"] = lines(shas, evals)["full"].replace(shas["head"][:9], shas["side"][:9])
    parts["affected"] = f"- Affected tests: {shas['head'][:9]} -> 40 passed, 0 failed"
    rejected(tmp_path, body(parts), shas["head"], evals, capsys, "full suite not on head")


@pytest.mark.parametrize("key", ["full", "evals", "red", "green", "sample"])
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
    for label in ("Full suite", "Regression evals", "Before (RED)", "After (GREEN)", "Sample output"):
        assert f"missing {label}" in out.err


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
    stands) and every pair of dropped lines (10) exits 1, never 0."""
    _, shas = repo
    base = lines(shas, evals)
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
    mention = "`Before (RED):`, `After (GREEN):`, `Full suite:` and `Sample output:` lines are required.\n"
    code, out = run(tmp_path, body(lines(shas, evals), mention), shas["head"], evals, capsys)
    assert code == 0, out.err
    out = rejected(tmp_path, mention, shas["head"], evals, capsys, "missing Before (RED)", "missing Full suite")
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
        parts["full"] = parts["full"].replace(shas["head"][:9], shas["red"][:9])
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
        parts["full"] = parts["full"].replace(shas["head"][:9], shas["red"][:9])
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
    assert out.err.count("ERROR:") >= 5
    assert "OK" not in out.out
