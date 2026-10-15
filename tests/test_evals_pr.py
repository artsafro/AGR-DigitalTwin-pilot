"""Pull-request graders (#125): Agent trace, numeric literals, review rounds, on recorded gh output."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from dt_ai.cli.main import main
from twinqa.evals.graders import EvidenceError, GRADERS
from twinqa.evals.pr_graders import (
    CEILING, TRACE_FIELDS, pr_agent_trace, pr_numeric_literals, pr_review_rounds, read_diff, read_view,
)
from twinqa.evals.runner import run

ROOT = Path(__file__).resolve().parents[1]
TRACE = ROOT / "evals/pr-agent-trace/fixtures"
NUM = ROOT / "evals/pr-numeric-literals/fixtures"
ROUNDS = ROOT / "evals/pr-review-rounds/fixtures"


def dt(tmp_path, *args):
    out = tmp_path / "run"
    code = main(["evals", *args, "--main", str(tmp_path / "main"), "--branch", "harness/task-x",
                 "--output", str(out)])
    report = json.loads((out / "report.json").read_text(encoding="utf-8")) if (out / "report.json").is_file() else None
    return code, report


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def view_file(path, body, comments=None):
    payload = {"comments": [] if comments is None else comments}
    if body is not None:
        payload["body"] = body
    return write(path, json.dumps(payload))


def diff_file(path, text):
    return write(path, text)


def py_diff(lines, path="src/dt_ai/a.py"):
    body = "\n".join(lines)
    return (f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
            f"@@ -1,1 +1,{max(len(lines), 1)} @@\n{body}\n")


def trace_body(**overrides):
    values = {name: "not measured (test)" for name in TRACE_FIELDS}
    values.update(overrides)
    lines = ["## Agent trace", ""]
    lines += [f"- {name}: {values[name]}" for name in TRACE_FIELDS]
    return "\n".join(lines) + "\n"


def test_trace_fields_match_the_hook_script():
    path = ROOT / "tools/hooks/agent_trace.py"
    spec = importlib.util.spec_from_file_location("agent_trace_fields", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert TRACE_FIELDS == module.FIELDS


def test_agent_trace_on_the_recorded_pull_requests():
    bad = pr_agent_trace({"pr": [TRACE / "agr-pr76.view.json"]})
    good = pr_agent_trace({"pr": [TRACE / "pilot-pr30.view.json"]})
    assert (bad["measured"], bad["passed"]) == ("absent", False)
    assert (good["measured"], good["passed"]) == ("present, 10 fields", True)


def test_a_placeholder_field_fails_and_a_missing_body_is_not_measured(tmp_path):
    placeholder = view_file(tmp_path / "ph.json", trace_body(**{"Sessions": "<session ids>"}))
    row = pr_agent_trace({"pr": [placeholder]})
    assert row["passed"] is False and "Sessions" in row["details"] and row["measured"].startswith("incomplete")
    missing = view_file(tmp_path / "nobody.json", None)
    row = pr_agent_trace({"pr": [missing]})
    assert row["passed"] is None and row["measured"] == "not measured"
    assert "fetch with gh pr view --json body,comments" in row["error"]


def test_numeric_literals_on_the_recorded_pull_requests():
    bad = pr_numeric_literals({"pr": [NUM / "agr-pr76.view.json"], "diff": [NUM / "agr-pr76.diff"]})
    good = pr_numeric_literals({"pr": [NUM / "pilot-pr30.view.json"], "diff": [NUM / "pilot-pr30.diff"]})
    assert bad["passed"] is False and bad["measured"] > 0
    assert any(item["file"] == "src/twinqa/geometry/checks.py" and item["literal"] == "0.5"
               and "STRAY_EMBED_MAX_M" in item["text"] for item in bad["details"])
    assert (good["measured"], good["passed"]) == (0, True)


def test_numeric_literals_ignore_comments_strings_and_out_of_scope_files(tmp_path):
    body = "see 0.25 m in the source [D090]\n"
    view = view_file(tmp_path / "v.json", body)
    clean = diff_file(tmp_path / "clean.diff", py_diff([
        '+"""docstring keeps 2.5"""',
        "+# comment keeps 2.5",
        '+s = "2.5"',
        "+name = x2",
        "+limit = 0.25  # [D073]",
    ]))
    row = pr_numeric_literals({"pr": [view], "diff": [clean]})
    assert (row["measured"], row["passed"]) == (0, True)

    cited = diff_file(tmp_path / "cited.diff", py_diff(["+gap = 0.25"]))
    row = pr_numeric_literals({"pr": [view], "diff": [cited]})
    assert (row["measured"], row["passed"]) == (0, True)

    tol = diff_file(tmp_path / "tol.diff", py_diff(["+GAP = 0.33"], "src/dt_ai/a.py")
                    + py_diff(['+  "gap": 0.33'], "benchmark/x/tolerances.json"))
    plain = view_file(tmp_path / "plain.json", "no numbers here")
    row = pr_numeric_literals({"pr": [plain], "diff": [tol]})
    assert (row["measured"], row["passed"]) == (0, True)

    moved = diff_file(tmp_path / "moved.diff", py_diff(["-OLD = 0.33", "+OLD = 0.33"]))
    row = pr_numeric_literals({"pr": [plain], "diff": [moved]})
    assert (row["measured"], row["passed"]) == (0, True)

    harness = diff_file(tmp_path / "harness.diff", py_diff(["+BAD = 2.5"], "src/twinqa/evals/g.py"))
    row = pr_numeric_literals({"pr": [plain], "diff": [harness]})
    assert (row["measured"], row["passed"], row["scanned_files"]) == (0, True, [])

    junk = diff_file(tmp_path / "junk.diff", "this is not a diff\n")
    row = pr_numeric_literals({"pr": [plain], "diff": [junk]})
    assert row["passed"] is None and row["measured"] == "not measured" and "not a gh pr diff" in row["error"]
    with pytest.raises(EvidenceError, match="not a gh pr diff"):
        read_diff(junk)


@pytest.mark.parametrize("line", [
    "+MAX_EMBED_M = 2",
    "+MAX_EMBED_M = 1",
    "+MAX_EMBED_M = 0",
    "+result = points[3:5]",
])
def test_numeric_literals_count_small_values_and_slices(tmp_path, line):
    plain = view_file(tmp_path / "v.json", "reviewed, no citation")
    row = pr_numeric_literals({"pr": [plain], "diff": [diff_file(tmp_path / "d.diff", py_diff([line]))]})
    assert row["passed"] is False and row["measured"] >= 1


def test_numeric_literals_same_value_on_a_different_line_is_new(tmp_path):
    plain = view_file(tmp_path / "v.json", "reviewed, no citation")
    diff = diff_file(tmp_path / "d.diff", py_diff(["-OLD_RETRY_DELAY = 0.33", "+MAX_EMBED_M = 0.33"]))
    row = pr_numeric_literals({"pr": [plain], "diff": [diff]})
    assert row["passed"] is False
    assert [item["literal"] for item in row["details"]] == ["0.33"]


@pytest.mark.parametrize("lines, ok, literal", [
    (['+result = f"{width * 0.37}"'], False, "0.37"),
    (['+s = f"{x:.2f} and {{0.5}}"'], True, None),
    (['+s = f"{x:{width}}"'], True, None),
    (['+s = f"{x:{3}}"'], False, "3"),
    (['+s = f"""', '+{a * 0.4}"""'], False, "0.4"),
])
def test_numeric_literals_scan_fstring_expressions(tmp_path, lines, ok, literal):
    plain = view_file(tmp_path / "v.json", "reviewed, no citation")
    row = pr_numeric_literals({"pr": [plain], "diff": [diff_file(tmp_path / "d.diff", py_diff(lines))]})
    if ok:
        assert (row["measured"], row["passed"]) == (0, True)
    else:
        assert row["passed"] is False and literal in [item["literal"] for item in row["details"]]


def test_numeric_literals_unparseable_fstring_is_not_measured(tmp_path):
    plain = view_file(tmp_path / "v.json", "reviewed, no citation")
    diff = diff_file(tmp_path / "d.diff", py_diff(['+s = f"{width * 0.37"']))
    row = pr_numeric_literals({"pr": [plain], "diff": [diff]})
    assert row["passed"] is None and row["measured"] == "not measured"
    assert row["error"].startswith("incomplete evidence:")
    assert "src/dt_ai/a.py" in row["error"] and ":1:" in row["error"]


def test_numeric_literals_a_cited_threshold_passes(tmp_path):
    plain = view_file(tmp_path / "v.json", "reviewed, no citation")
    diff = diff_file(tmp_path / "d.diff", py_diff(["+MAX_EMBED_M = 0.37  # [D090]"]))
    row = pr_numeric_literals({"pr": [plain], "diff": [diff]})
    assert (row["measured"], row["passed"]) == (0, True)


def test_review_rounds_on_the_recorded_pull_requests():
    synthetic = pr_review_rounds({"pr": [ROUNDS / "four-rounds.synthetic.view.json"]})
    pilot = pr_review_rounds({"pr": [ROUNDS / "pilot-pr30.view.json"]})
    agr = pr_review_rounds({"pr": [ROUNDS / "agr-pr76.view.json"]})
    assert (synthetic["measured"], synthetic["passed"]) == (4, False)
    assert CEILING == 3 and {item["round"] for item in synthetic["details"]} == {1, 2, 3, 4}
    assert all(item["round"] != 9 for item in synthetic["details"])
    assert (pilot["measured"], pilot["passed"]) == (2, True)
    assert (agr["measured"], agr["passed"]) == (0, True)


def test_review_round_edges(tmp_path):
    unrecognized = view_file(tmp_path / "u.json", "body",
                             [{"body": "## Codex review of #106: three rounds\n\nstill prose", "url": "https://example/106"}])
    row = pr_review_rounds({"pr": [unrecognized]})
    assert row["passed"] is None and row["measured"] == "not measured" and "https://example/106" in row["error"]

    missing = write(tmp_path / "c.json", json.dumps({"body": "no comments key"}))
    row = pr_review_rounds({"pr": [missing]})
    assert row["passed"] is None and "fetch with gh pr view --json body,comments" in row["error"]

    over = view_file(tmp_path / "over.json", "body",
                     [{"body": "**Round 4 verdict: clean**", "url": "https://example/4"}])
    row = pr_review_rounds({"pr": [over]})
    assert (row["measured"], row["passed"]) == (4, False)


def test_a_gh_rule_that_is_not_a_pr_command_stops_the_task(tmp_path):
    folder = tmp_path / "evals/bad-gh"
    write(folder / "task.json", json.dumps({
        "id": "bad-gh", "suite": "regression", "grader": "pr_agent_trace",
        "evidence": {"pr": {"root": "task", "path": "x.json", "gh": "git status"}},
        "references": [],
    }))
    code, report = dt(tmp_path, "--suite", "regression", "--evals-dir", str(tmp_path / "evals"))
    assert code == 2 and report["checks"][0]["error"].startswith("stopped:")


def test_missing_pr_evidence_names_the_gh_command(tmp_path):
    code, report = dt(tmp_path, "--task", "pr-agent-trace")
    assert code == 2
    assert "produce it with: gh pr view" in report["checks"][0]["error"]


def test_regression_references_pass(tmp_path):
    code, report, _folder = run(ROOT / "evals", suite="regression", references=True, output=tmp_path / "out",
                                main=tmp_path / "main", branch="harness/task-x")
    assert code == 0
    assert report["checks"] and all(row["passed"] is True for row in report["checks"])
    assert "pr_agent_trace" in GRADERS and "pr_numeric_literals" in GRADERS and "pr_review_rounds" in GRADERS


def test_importing_pr_graders_first_does_not_cycle():
    script = ("import twinqa.evals.pr_graders as pr\n"
              "import twinqa.evals.graders as graders\n"
              "assert set(pr.PR_GRADERS) <= set(graders.GRADERS)\n")
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_read_view_rejects_a_non_object(tmp_path):
    path = write(tmp_path / "v.json", "[1, 2]")
    with pytest.raises(EvidenceError):
        read_view(path)


def test_numeric_literals_catch_unreferenced_values_around_skipped_text(tmp_path):
    """Positive control: the skips above must not hide real literals (multi-line docstring, after a comment line)."""
    plain = view_file(tmp_path / "plain.json", "no numbers here; [D090] cites 0.75 only")
    diff = diff_file(tmp_path / "d.diff", py_diff([
        '+"""Doc opens',
        "+still doc 9.5",
        '+closes"""',
        "+gap = 0.25",
        "+# 7.5 in a comment",
        "+n = 3  # no reference",
        "+half = w / 2",
        "+ok = 0.75",
        "+cited = 4.5  # [D073]",
    ]))
    row = pr_numeric_literals({"pr": [plain], "diff": [diff]})
    assert row["passed"] is False
    assert sorted(item["literal"] for item in row["details"]) == ["0.25", "2", "3"]
