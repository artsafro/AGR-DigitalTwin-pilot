"""Reducer isolation for tools/methods/methods_metrics.py:ucx_check.

Pattern: new-case: ucx_check status aggregation controls.

These tests pin how the methods adapter reduces already-built findings into
``ucx.status`` and ``ucx.checks``. ``scene_findings`` is monkeypatched on this
module only. The readback has no UCX pieces, so a monkeypatched ``pass`` is a
reducer-isolation input, not a claim that an empty UCX scene passes and not
delivery acceptance. The real no-UCX integration test stays in
tests/methods/test_methods_catalog.py.

Acceptance (input -> status):

| input | status | checks |
|---|---|---|
| no findings | open | {} |
| advisory-only V010 ``UCX piece gap (advisory)`` review | open | advisory status kept |
| one ordinary V010 pass | pass | that pass |
| ordinary pass + ordinary review, or pass + not_run | open | both kept |
| any ordinary fail alongside pass / review / not_run | fail | all of them kept |
| ordinary pass + ``UCX piece gap (advisory)`` review | pass | advisory review kept |
| ordinary pass + ``UCX piece gap (advisory)`` synthetic fail | pass | advisory fail kept |
| V012 ``UCX names`` fail | fail | that fail |
| profile key injected before scene_findings (in-memory witness) | rejected (AssertionError) | n/a |
| V010 pass + V012 name without ``UCX`` fail + V003 fail | pass | only the V010 pass |

Ordered-pair oracle over ordinary statuses ``pass``, ``review``, ``not_run``,
``fail`` (hand-written; not derived from production code). Unique names, so
duplicate-name overwrite is not decided here.

| left \\ right | pass | review | not_run | fail |
|---|---|---|---|---|
| pass | pass | open | open | fail |
| review | open | open | open | fail |
| not_run | open | open | open | fail |
| fail | fail | fail | fail | fail |

Finding order and stage-dict insertion order do not change the complete output.
``scene_findings`` receives the same readback, ``vpm``, ``oks`` and the supplied
profile. Repeated calls leave the readback and the findings unchanged. The
isolated fixture reports zero UCX pieces and zero UCX triangles.
"""
from __future__ import annotations

import copy
import itertools

import pytest

from tests.methods.test_methods_catalog import mm

# Literal independent precedence oracle. Each cell is written by hand from the
# acceptance table above. This dict does not call ucx_check and does not repeat
# the production if/elif.
PAIR_STATUS = {
    ("pass", "pass"): "pass",
    ("pass", "review"): "open",
    ("pass", "not_run"): "open",
    ("pass", "fail"): "fail",
    ("review", "pass"): "open",
    ("review", "review"): "open",
    ("review", "not_run"): "open",
    ("review", "fail"): "fail",
    ("not_run", "pass"): "open",
    ("not_run", "review"): "open",
    ("not_run", "not_run"): "open",
    ("not_run", "fail"): "fail",
    ("fail", "pass"): "fail",
    ("fail", "review"): "fail",
    ("fail", "not_run"): "fail",
    ("fail", "fail"): "fail",
}

_ORDINARY = ("pass", "review", "not_run", "fail")
_ADVISORY = "UCX piece gap (advisory)"


class FindingDouble:
    """Name/status double. Not a scene verdict and not a ValidationReport row."""

    def __init__(self, name, status):
        self.name = name
        self.status = status


def _readback():
    return {"meshes": [], "other_objects": []}


def _snapshot(stages):
    return {stage: [(item.name, item.status) for item in items] for stage, items in stages.items()}


def _reduce(monkeypatch, stages, adapter=None):
    """Call ucx_check twice. Return the result after checking the isolation contract.

    readback, profile and findings are snapshotted independently (deepcopy) and
    compared at the scene_findings call boundary and after each call.
    """
    adapter = adapter or mm.ucx_check
    rb = _readback()
    profile = {"profile": "reducer-isolation"}
    rb_before = copy.deepcopy(rb)
    profile_before = copy.deepcopy(profile)
    before = _snapshot(stages)
    calls = []

    def fake(readback, kind, role, prof):
        assert readback is rb and readback == rb_before, "readback changed before scene_findings"
        assert prof is profile and prof == profile_before, "profile changed before scene_findings"
        assert _snapshot(stages) == before, "findings changed before scene_findings"
        calls.append((readback, kind, role, prof))
        return stages

    monkeypatch.setattr(mm, "scene_findings", fake)
    results = []
    for _ in range(2):
        results.append(adapter(rb, profile))
        assert rb == rb_before, "readback changed by call"
        assert profile == profile_before, "profile changed by call"
        assert _snapshot(stages) == before, "findings changed by call"
    first, second = results
    assert first == second
    assert [(c[1], c[2]) for c in calls] == [("vpm", "oks")] * 2
    assert first["pieces"] == 0
    assert first["triangles"] == 0
    assert first["closed_convex"] == 0
    assert first["piece_reasons"] == {}
    return first


def test_profile_mutation_before_scene_findings_is_detected(monkeypatch):
    """Witness: an in-memory adapter that injects a profile key is rejected."""

    def mutating(readback, profile):
        profile["reviewer_injected_mutation"] = True
        return mm.ucx_check(readback, profile)

    with pytest.raises(AssertionError, match="profile changed"):
        _reduce(monkeypatch, {}, adapter=mutating)


def _v010(*pairs):
    return {"V010": [FindingDouble(name, status) for name, status in pairs]}


def test_oracle_lists_every_ordered_pair_once():
    assert set(PAIR_STATUS) == {(left, right) for left in _ORDINARY for right in _ORDINARY}
    assert len(PAIR_STATUS) == 16
    assert all(status in ("pass", "open", "fail") for status in PAIR_STATUS.values())


def test_no_findings_is_open(monkeypatch):
    out = _reduce(monkeypatch, {})
    assert out["status"] == "open"
    assert out["checks"] == {}


def test_advisory_only_stays_open(monkeypatch):
    out = _reduce(monkeypatch, _v010((_ADVISORY, "review")))
    assert out["status"] == "open"
    assert out["checks"] == {_ADVISORY: "review"}


def test_one_ordinary_pass(monkeypatch):
    out = _reduce(monkeypatch, _v010(("UCX present", "pass")))
    assert out["status"] == "pass"
    assert out["checks"] == {"UCX present": "pass"}


@pytest.mark.parametrize("other", ["review", "not_run"])
def test_pass_plus_review_or_not_run_is_open(monkeypatch, other):
    out = _reduce(monkeypatch, _v010(("UCX present", "pass"), ("UCX shape", other)))
    assert out["status"] == "open"
    assert out["checks"] == {"UCX present": "pass", "UCX shape": other}


def test_ordinary_fail_alongside_pass_review_and_not_run(monkeypatch):
    out = _reduce(monkeypatch, _v010(
        ("UCX present", "pass"),
        ("UCX intersections coverage", "review"),
        ("UCX shape", "not_run"),
        ("UCX material slots", "fail"),
    ))
    assert out["status"] == "fail"
    assert out["checks"] == {
        "UCX present": "pass",
        "UCX intersections coverage": "review",
        "UCX shape": "not_run",
        "UCX material slots": "fail",
    }


@pytest.mark.parametrize(("left", "right"), list(PAIR_STATUS))
def test_ordered_pair_matches_hand_written_oracle(monkeypatch, left, right):
    out = _reduce(monkeypatch, _v010(("left-check", left), ("right-check", right)))
    assert out["status"] == PAIR_STATUS[(left, right)]
    assert out["checks"] == {"left-check": left, "right-check": right}


@pytest.mark.parametrize("advisory_status", ["review", "fail"])
def test_advisory_gap_does_not_gate_an_ordinary_pass(monkeypatch, advisory_status):
    """``fail`` here is a reducer-isolation double, not a reachable scene gap verdict."""
    out = _reduce(monkeypatch, _v010(("UCX present", "pass"), (_ADVISORY, advisory_status)))
    assert out["status"] == "pass"
    assert out["checks"] == {"UCX present": "pass", _ADVISORY: advisory_status}


def test_v012_ucx_names_fail(monkeypatch):
    out = _reduce(monkeypatch, {"V012": [FindingDouble("UCX names", "fail")]})
    assert out["status"] == "fail"
    assert out["checks"] == {"UCX names": "fail"}


def test_non_ucx_v012_and_v003_are_excluded(monkeypatch):
    out = _reduce(monkeypatch, {
        "V010": [FindingDouble("UCX present", "pass")],
        "V012": [FindingDouble("Mesh names", "fail")],
        "V003": [FindingDouble("Triangulation", "fail")],
    })
    assert out["status"] == "pass"
    assert out["checks"] == {"UCX present": "pass"}
    assert "Mesh names" not in out["checks"]
    assert "Triangulation" not in out["checks"]


def test_finding_and_stage_order_do_not_change_output(monkeypatch):
    v010 = (
        ("UCX present", "pass"),
        ("UCX intersections coverage", "review"),
        (_ADVISORY, "review"),
    )
    v012 = (("UCX names", "fail"), ("Mesh names", "fail"))
    v003 = (("Triangulation", "fail"),)
    seen = []
    for order10 in itertools.permutations(v010):
        for order12 in itertools.permutations(v012):
            for key_order in itertools.permutations(("V010", "V012", "V003")):
                chosen = {"V010": order10, "V012": order12, "V003": v003}
                stages = {
                    stage: [FindingDouble(name, status) for name, status in chosen[stage]]
                    for stage in key_order
                }
                seen.append(_reduce(monkeypatch, stages))
    assert len(seen) == 6 * 2 * 6
    assert all(item == seen[0] for item in seen)
    assert seen[0]["status"] == "fail"
    assert seen[0]["pieces"] == 0 and seen[0]["triangles"] == 0
    assert seen[0]["checks"] == {
        "UCX present": "pass",
        "UCX intersections coverage": "review",
        _ADVISORY: "review",
        "UCX names": "fail",
    }
