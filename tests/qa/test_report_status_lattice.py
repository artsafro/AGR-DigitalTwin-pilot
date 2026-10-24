"""new-case: synthetic blocking-status lattice and stage-count controls.

Acceptance table (fixed before implementation; not real delivery data):
Input                         | Stage/count expectation       | passed/exit
empty blocking stage          | not_run:1                     | False/2
16 ordered finding pairs      | literal PAIRS, one stage      | VERDICTS
permuted/duplicated findings   | same status, still one stage  | unchanged
no stages                     | four zeros                    | False/2
two blocking pass stages       | pass:2                        | True/0
pass + review                 | pass:1, review:1              | False/2
pass + empty                  | pass:1, not_run:1             | False/2
fail + review/not_run          | fail:1, other:1               | False/1
pass + empty manual            | counts unchanged, pending ID  | True/0
manual-only empty             | four zeros, pending ID        | False/2
repeated reads / edited dict   | original and second dict unchanged

Manual-fail precedence, unknown gates and notes aliasing are out of scope.
"""
from copy import deepcopy

import pytest

from twinqa.report import Finding, Stage, ValidationReport

# Literal independent oracle: never import production RANK or STATUSES.
PAIRS = [
    ("pass", "pass", "pass"),
    ("pass", "not_run", "not_run"),
    ("pass", "review", "review"),
    ("pass", "fail", "fail"),
    ("not_run", "pass", "not_run"),
    ("not_run", "not_run", "not_run"),
    ("not_run", "review", "review"),
    ("not_run", "fail", "fail"),
    ("review", "pass", "review"),
    ("review", "not_run", "review"),
    ("review", "review", "review"),
    ("review", "fail", "fail"),
    ("fail", "pass", "fail"),
    ("fail", "not_run", "fail"),
    ("fail", "review", "fail"),
    ("fail", "fail", "fail"),
]
VERDICTS = {"pass": (True, 0), "not_run": (False, 2),
            "review": (False, 2), "fail": (False, 1)}


def stage(sid, statuses=(), gate="blocking"):
    return Stage(sid, "synthetic check", gate, [1], [
        Finding(f"finding-{i}", status, "synthetic", "expected", [1, 2],
                evidence="synthetic evidence", conflicts=[3])
        for i, status in enumerate(statuses)
    ])


def report(stages):
    return ValidationReport("vpm", "synthetic.fbx", "a" * 64, "b" * 64, True, stages)


def assert_report(actual, statuses, counts, passed, exit_code, pending=()):
    """Assert exact public and serialized results; reads must be side-effect free."""
    before = deepcopy(actual)
    payload = actual.to_dict()
    for _ in range(3):
        payload = actual.to_dict()
        assert [(s.id, s.status) for s in actual.stages] == statuses
        assert [(s["id"], s["status"]) for s in payload["stages"]] == statuses
        assert payload["machine_stage_counts"] == counts
        assert payload["manual_reviews_pending"] == list(pending)
        assert actual.passed is passed
        assert payload["passed"] is passed
        assert actual.exit_code == payload["exit_code"] == exit_code
        assert (actual.exit_code == 0) is actual.passed
        assert actual.machine_stages == [s for s in actual.stages if s.gate == "blocking"]
        assert actual == before  # finding fields and nested lists included
    return payload


@pytest.mark.parametrize("left,right,expected", PAIRS)
@pytest.mark.parametrize("variant", ["original", "reversed", "duplicated"])
def test_ordered_pairs_and_duplicate_findings(left, right, expected, variant):
    statuses = {"original": [left, right], "reversed": [right, left],
                "duplicated": [right, left, right, left]}[variant]
    counts = {"pass": 0, "fail": 0, "review": 0, "not_run": 0}
    counts[expected] = 1  # a stage, not two/four findings
    assert_report(report([stage("V001", statuses)]), [("V001", expected)],
                  counts, *VERDICTS[expected])


@pytest.mark.parametrize("statuses,expected", [
    ([], "not_run"), (["pass"], "pass"), (["not_run"], "not_run"),
    (["review"], "review"), (["fail"], "fail"),
])
def test_empty_and_single_finding_stages(statuses, expected):
    counts = {"pass": 0, "fail": 0, "review": 0, "not_run": 0}
    counts[expected] = 1
    assert_report(report([stage("V001", statuses)]), [("V001", expected)],
                  counts, *VERDICTS[expected])


@pytest.mark.parametrize("inputs,statuses,counts,passed,exit_code", [
    ([], [], {"pass": 0, "fail": 0, "review": 0, "not_run": 0}, False, 2),
    ([["pass"] * 3, ["pass"] * 2], ["pass", "pass"],
     {"pass": 2, "fail": 0, "review": 0, "not_run": 0}, True, 0),
    ([["pass"], ["review"] * 3], ["pass", "review"],
     {"pass": 1, "fail": 0, "review": 1, "not_run": 0}, False, 2),
    ([["pass"], []], ["pass", "not_run"],
     {"pass": 1, "fail": 0, "review": 0, "not_run": 1}, False, 2),
    ([["fail", "pass", "fail"], ["review"]], ["fail", "review"],
     {"pass": 0, "fail": 1, "review": 1, "not_run": 0}, False, 1),
    ([["fail"], ["not_run"]], ["fail", "not_run"],
     {"pass": 0, "fail": 1, "review": 0, "not_run": 1}, False, 1),
    ([["fail"], ["review"], []], ["fail", "review", "not_run"],
     {"pass": 0, "fail": 1, "review": 1, "not_run": 1}, False, 1),
])
def test_blocking_report_controls(inputs, statuses, counts, passed, exit_code):
    stages = [stage(f"V{i:03}", findings) for i, findings in enumerate(inputs, 1)]
    assert_report(report(stages), [(s.id, expected) for s, expected in zip(stages, statuses)],
                  counts, passed, exit_code)


def test_empty_manual_stage_is_pending_not_machine_approval():
    actual = report([stage("V001", ["pass", "pass"])])
    counts = {"pass": 1, "fail": 0, "review": 0, "not_run": 0}
    before = assert_report(actual, [("V001", "pass")], counts, True, 0)
    actual.stages.append(stage("V016", gate="manual_review"))
    after = assert_report(actual, [("V001", "pass"), ("V016", "not_run")],
                          counts, True, 0, pending=["V016"])
    assert after["machine_stage_counts"] == before["machine_stage_counts"]


def test_manual_only_empty_report_is_not_passed():
    assert_report(report([stage("V016", gate="manual_review")]), [("V016", "not_run")],
                  {"pass": 0, "fail": 0, "review": 0, "not_run": 0},
                  False, 2, pending=["V016"])


@pytest.mark.parametrize("collection", ["stages", "findings", "stage_pages", "finding_pages", "conflicts"])
def test_serialized_stage_payload_has_no_mutable_aliases(collection):
    actual = report([stage("V001", ["pass", "review"])])
    counts = {"pass": 0, "fail": 0, "review": 1, "not_run": 0}
    first = assert_report(actual, [("V001", "review")], counts, False, 2)
    second = actual.to_dict()
    snapshot = deepcopy(second)
    serialized_stage = first["stages"][0]
    serialized_finding = serialized_stage["findings"][0]
    target = {"stages": first["stages"], "findings": serialized_stage["findings"],
              "stage_pages": serialized_stage["source_pdf_pages"],
              "finding_pages": serialized_finding["source_pdf_pages"],
              "conflicts": serialized_finding["conflicts"]}[collection]
    target.clear()
    serialized_stage["check"] = "changed serialization"
    serialized_finding["status"] = "fail"
    assert second == snapshot
    assert actual.to_dict() == snapshot
    assert_report(actual, [("V001", "review")], counts, False, 2)

