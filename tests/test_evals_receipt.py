"""Receipt CLI contract; all constructed reports/probes are synthetic (#302)."""
import itertools
import json
import math
from pathlib import Path

import pytest

from dt_ai.cli.main import main
from twinqa.evals import runner

ROOT = Path(__file__).resolve().parents[1]


def report_file(tmp_path, counts=(3, 0, 2)):
    p, f, n = counts
    report = {"selector": {"suite": "regression", "task": None, "references": False},
              "passed": p, "failed": f, "not_measured": n,
              "checks": [{"passed": v} for v, count in zip((True, False, None), counts)
                         for _ in range(count)]}
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    return path, report


def line(path, counts=(3, 0, 2), reason="no Claude transcript", separator=" / "):
    p, f, n = counts
    return (f"Regression evals: {path}; {p} passed{separator}{f} failed{separator}"
            f"{n} not measured ({reason})")


def check(tmp_path, receipt):
    return main(["evals", "--check-receipt", receipt, "--output", str(tmp_path)])


def rejected(tmp_path, receipt, capsys, reason):
    assert check(tmp_path, receipt) == 1
    output = capsys.readouterr()
    assert reason in output.err
    assert len(output.err.splitlines()) == 1


def test_receipt_matches_report(tmp_path):
    _, report, out = runner.run(ROOT / "evals", suite="regression", references=True,
                                main=tmp_path, branch="synthetic", output=tmp_path / "run")
    counts = tuple(report[k] for k in ("passed", "failed", "not_measured"))
    assert main(["evals", "--check-receipt", line(out / "report.json", counts),
                 "--output", str(out)]) == 0


def test_placeholder_without_report_rejected(tmp_path, capsys):
    rejected(tmp_path, line(tmp_path, (0, 0, 0), "not run"), capsys, "report missing")


def test_pytest_substitution_rejected(tmp_path, capsys):
    rejected(tmp_path, "127 pytest passed", capsys, "not a dt evals receipt")


def test_count_mismatch_rejected(tmp_path, capsys):
    path, _ = report_file(tmp_path)
    rejected(tmp_path, line(path, (5, 0, 0)), capsys, "counts differ")


def test_all_not_measured_valid(tmp_path):
    path, _ = report_file(tmp_path, (0, 0, 5))
    assert check(tmp_path, line(path, (0, 0, 5))) == 0


def test_wrong_suite_rejected(tmp_path, capsys):
    path, report = report_file(tmp_path)
    report["selector"]["suite"] = "capability"
    path.write_text(json.dumps(report), encoding="utf-8")
    rejected(tmp_path, line(path), capsys, "suite")


def test_empty_report_rejected(tmp_path, capsys):
    path, _ = report_file(tmp_path, (0, 0, 0))
    rejected(tmp_path, line(path, (0, 0, 0)), capsys, "empty report")


@pytest.mark.parametrize("counts", list(itertools.product(range(3), repeat=3)))
def test_generated_counts_are_exact_and_check_is_read_only(tmp_path, counts):
    path, _ = report_file(tmp_path, counts)
    before = path.read_bytes()
    for claimed in itertools.product(range(3), repeat=3):
        assert check(tmp_path, line(path, claimed)) == (0 if claimed == counts and sum(counts) else 1)
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("value", [None, True, -1, 1.0, "3", float("nan"), float("inf")])
@pytest.mark.parametrize("key", ["passed", "failed", "not_measured"])
def test_invalid_report_counts_fail_closed(tmp_path, capsys, key, value):
    path, report = report_file(tmp_path)
    report[key] = value
    path.write_text(json.dumps(report), encoding="utf-8")
    reason = "non-finite report value" if isinstance(value, float) and not math.isfinite(value) else key
    rejected(tmp_path, line(path), capsys, reason)


@pytest.mark.parametrize("number", ["1e309", "-1e309", "NaN", "Infinity", "-Infinity"])
def test_nonfinite_json_numbers_rejected(tmp_path, capsys, number):
    path, report = report_file(tmp_path)
    text = json.dumps(report).replace('"references": false', f'"references": {number}')
    path.write_text(text, encoding="utf-8")
    rejected(tmp_path, line(path), capsys, "non-finite report value")


@pytest.mark.parametrize("text", ["", "{", "null", "[]", "{}"])
def test_partial_or_unsupported_report_rejected(tmp_path, capsys, text):
    path = tmp_path / "report.json"
    path.write_text(text, encoding="utf-8")
    rejected(tmp_path, line(path), capsys, "report")


@pytest.mark.parametrize("mutation", ["missing-count", "missing-checks", "extra-row", "unknown-verdict",
                                      "missing-verdict", "bad-checks", "unknown-key", "row-counts"])
def test_inconsistent_report_rejected(tmp_path, capsys, mutation):
    path, report = report_file(tmp_path)
    if mutation == "missing-count":
        del report["failed"]
    elif mutation == "missing-checks":
        del report["checks"]
    elif mutation == "extra-row":
        report["checks"].append({"passed": True})
    elif mutation == "unknown-verdict":
        report["checks"][0]["passed"] = "pass"
    elif mutation == "missing-verdict":
        report["checks"][0] = {}
    elif mutation == "bad-checks":
        report["checks"] = {}
    elif mutation == "unknown-key":
        report["unmapped"] = 1
    else:
        report["checks"][0]["passed"] = False
    path.write_text(json.dumps(report), encoding="utf-8")
    rejected(tmp_path, line(path), capsys, "unmapped" if mutation == "unknown-key" else "report")


def test_receipt_cannot_name_a_different_report(tmp_path, capsys):
    path, _ = report_file(tmp_path)
    rejected(tmp_path, line(path.with_name("pytest.json")), capsys, "report path")


@pytest.mark.parametrize("option", [["--suite", "regression"], ["--task", "x"],
                                   ["--references"], ["--evidence", "x=y"],
                                   ["--branch", "x"], ["--main", "."], ["--evals-dir", "."]])
def test_run_options_rejected_without_writes(tmp_path, capsys, option):
    path, _ = report_file(tmp_path)
    before = path.read_bytes()
    assert main(["evals", "--check-receipt", line(path), "--output", str(tmp_path), *option]) == 1
    assert "not run options" in capsys.readouterr().err
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


def test_duplicate_report_key_rejected(tmp_path, capsys):
    path, _ = report_file(tmp_path)
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace('"passed": 3', '"passed": 3, "passed": 3', 1), encoding="utf-8")
    rejected(tmp_path, line(path), capsys, "duplicate report key: passed")


def test_output_alias_to_input_rejected_without_writes(tmp_path, capsys):
    path, _ = report_file(tmp_path)
    before = path.read_bytes()
    assert main(["evals", "--check-receipt", line(path), "--output", str(path)]) == 1
    assert "report missing" in capsys.readouterr().err
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


def test_missing_output_rejected(tmp_path, capsys):
    path, _ = report_file(tmp_path)
    assert main(["evals", "--check-receipt", line(path)]) == 1
    assert "report directory required" in capsys.readouterr().err


def test_workflow_comma_format_supported(tmp_path):
    path, _ = report_file(tmp_path)
    assert check(tmp_path, line(path, separator=", ")) == 0


@pytest.mark.parametrize("receipt", ["", "Regression evals: pytest; 127 pytest passed",
                                      "Regression evals: report.json; NaN passed / 0 failed / 0 not measured (x)",
                                      "Regression evals: report.json; 1 passed / 0 failed / 0 not measured ()"])
def test_malformed_receipt_rejected(tmp_path, capsys, receipt):
    rejected(tmp_path, receipt, capsys, "not a dt evals receipt")
