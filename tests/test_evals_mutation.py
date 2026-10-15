"""Contract tests for the frozen benchmark, through its corpus/report/CLI seams."""
import importlib.util
import json
from pathlib import Path
import random
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("evals_mutation", ROOT / "tools/evals_mutation.py")
bench = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bench)


@pytest.fixture(scope="module")
def report():
    return bench.evaluate()


def test_corpus_coverage():
    cases = bench.corpus()
    refs = {(g, n) for g, n, v, _ in bench.references() if v == "pass"}
    assert len(refs) == 11
    assert len({g for g, _ in refs}) == 10
    assert {(c["grader"], c["reference"]) for c in cases} == refs
    for grader, name in refs:
        subset = [c for c in cases if c["grader"] == grader and c["reference"] == name]
        assert len({c["kind"] for c in subset if c["violating"]}) >= 5
        assert {c["kind"] for c in subset if not c["violating"]} >= {"key_order", "unrelated_reordering"}
        if grader not in ("no_hook_denial", "pr_agent_trace", "pr_numeric_literals", "pr_review_rounds"):
            assert "sidechain" in {c["kind"] for c in subset if not c["violating"]}


def test_provenance_and_opaque_paths(tmp_path):
    originals = {(g, n): b for g, n, v, b in bench.references() if v == "pass"}
    for i, case in enumerate(bench.corpus()):
        original = originals[case["grader"], case["reference"]]
        assert case["original_sha256"] == bench.digest(bench.encode(original))
        assert set(case["bundle"]) == set(original)
        assert case["bundle"] != original  # no unchanged control masquerades as an edit
        directory = tmp_path / str(i)
        directory.mkdir()
        bench.grade(case["grader"], case["bundle"], directory, random.Random(i))
        assert sorted(p.read_text(encoding="utf-8") for p in directory.iterdir()) == sorted(case["bundle"].values())
        assert all(len(p.name) == 32 and all(c in "0123456789abcdef" for c in p.name) for p in directory.iterdir())
        for key in original.keys() - {"transcript", "pr", "diff"}:
            assert case["bundle"][key] == original[key]
        if "transcript" in original:
            old = bench.records_of(original)
            new = bench.records_of(case["bundle"])
            # At most two prerequisite records are edited/moved; the rest of the evidence survives.
            assert sum(r in new for r in old) >= len(old) - 2
        else:
            old_view = json.loads(original["pr"])
            new_view = json.loads(case["bundle"]["pr"])
            assert set(new_view) == set(old_view)
            for key in old_view.keys() - {"body", "comments"}:
                assert new_view[key] == old_view[key]
            if case["grader"] == "pr_numeric_literals":
                assert case["bundle"]["diff"].startswith(original["diff"])


def test_uncertainty_is_not_success():
    out = [{"violating": violating, "passed": passed}
           for violating in (True, False) for passed in (True, False, None)]
    summary = bench.summarize(out)
    assert summary["killed"] == 1 / 3
    assert summary["false_fail"] == 1 / 3
    assert summary["uncertain"] == 2
    clean = {"false_fail": 0, "uncertain": 0, "reference_mismatches": 0,
             "tool_sha256": "fixed", "corpus_sha256": "fixed", "seed": 117}
    assert bench.guard(clean, clean)
    for key in ("uncertain", "false_fail", "reference_mismatches"):
        assert not bench.guard(clean | {key: 1}, clean)
    for key in ("tool_sha256", "corpus_sha256", "seed"):
        assert not bench.guard(clean | {key: "changed"}, clean)


def test_seed_reproducibility():
    assert bench.corpus(117) == bench.corpus(117)
    assert bench.digest(bench.encode(bench.corpus(117))) != bench.digest(bench.encode(bench.corpus(118)))


def test_unrelated_reordering_changes_order_only():
    originals = {(g, n): b for g, n, v, b in bench.references() if v == "pass"}
    for case in bench.corpus():
        if case["kind"] != "unrelated_reordering":
            continue
        original = originals[case["grader"], case["reference"]]
        if "transcript" in original:
            before, after = bench.records_of(original), bench.records_of(case["bundle"])
            assert before != after
            assert sorted(map(bench.encode, before)) == sorted(map(bench.encode, after))
            assert [r for r in before if r["type"] in ("assistant", "user")] == [
                r for r in after if r["type"] in ("assistant", "user")]
        else:
            before = json.loads(original["pr"])
            after = json.loads(case["bundle"]["pr"])
            assert before["body"] == after["body"]
            assert len(after["comments"]) == len(before.get("comments", [])) + 2
            assert after["comments"][0]["body"] == "The attachment is readable."


def test_reference_verdicts(report):
    assert len(report["references"]) == 21
    assert report["reference_mismatches"] == 0
    assert all(r["passed"] is r["expected"] for r in report["references"])


def test_controls_pass(report):
    controls = [o for o in report["outcomes"] if not o["violating"]]
    assert len(controls) == 28
    assert all(o["passed"] is True for o in controls)


def test_json_command(tmp_path):
    completed = subprocess.run([sys.executable, str(ROOT / "tools/evals_mutation.py"), "--json"],
                               cwd=tmp_path, capture_output=True, text=True, encoding="utf-8")
    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout.splitlines()[-1])
    assert report["mutants"] == 55
    assert report["controls"] == 28
    assert report["runtime"] > 0
    assert len(report["tool_sha256"]) == len(report["corpus_sha256"]) == 64
