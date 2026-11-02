"""new-case: independent absolute-versus-relative area tolerance controls for source_finish_report.

Characterization (baseline GREEN, not a historical RED). Synthetic technical QA only,
not delivery acceptance. The module is imported directly; no job inputs are read.

Acceptance table (literal; source area P -> delivered area T -> report), one triangle,
owners [(0,)], delivered [A]:
  P=0.0001, T=P +/- 0.0000005 -> ok true,  uncovered 0
  P=0.0001, T=P +/- 0.000002  -> ok false, uncovered 1, examples [0]
  P=1000,   T=P +/- 0.005     -> ok true,  uncovered 0
  P=1000,   T=P +/- 0.02      -> ok false, uncovered 1, examples [0]
  T=P at both scales          -> ok true
Mutations (process-local, on a copy of the function source) drop the absolute term or the
relative term; the small accepted case kills the first, the large accepted case the second.
"""
import copy
import inspect
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "jobs" / "TEC26-OKS" / "scripts"
sys.path.insert(0, str(_SCRIPTS))

import qa_packages  # noqa: E402

A = "A"
TRI = [[0, 1, 2]]
SMALL, LARGE = 0.0001, 1000.0

CASES = [
    (SMALL, SMALL + 0.0000005, True),
    (SMALL, SMALL - 0.0000005, True),
    (SMALL, SMALL + 0.000002, False),
    (SMALL, SMALL - 0.000002, False),
    (LARGE, LARGE + 0.005, True),
    (LARGE, LARGE - 0.005, True),
    (LARGE, LARGE + 0.02, False),
    (LARGE, LARGE - 0.02, False),
    (SMALL, SMALL, True),
    (LARGE, LARGE, True),
]


def _run(fn, src_faces, owners, delivered, t, p, expected=None):
    expected = expected if expected is not None else [A] * len(src_faces)
    snap = copy.deepcopy((expected, src_faces, owners, delivered, t, p))
    r = fn(expected, src_faces, owners, delivered, t_areas=t, p_areas=p)
    assert (expected, src_faces, owners, delivered, t, p) == snap
    return r


def _check_one(fn, P, T, ok):
    r = _run(fn, TRI, [(0,)], [A], [T], [P])
    assert r["tris"] == 1
    assert r["ok"] is ok
    assert r["source_polygons_not_covered"] == (0 if ok else 1)
    assert r["uncovered_examples"] == ([] if ok else [0])
    assert r["wrong_finish"] == 0 and r["unmatched"] == 0 and r["ambiguous"] == 0
    assert r["examples"] == []


@pytest.mark.parametrize("P,T,ok", CASES)
def test_acceptance_table(P, T, ok):
    _check_one(qa_packages.source_finish_report, P, T, ok)


@pytest.mark.parametrize("bad_small,bad_large", [(0.000002, 0.02), (-0.000002, -0.02)])
def test_two_polygons_mixed_scale_report_only_offender(bad_small, bad_large):
    faces = [[0, 1, 2], [3, 4, 5]]
    owners = [(0,), (1,)]
    fn = qa_packages.source_finish_report
    # small polygon (index 0) offends, large (index 1) within tolerance
    r = _run(fn, faces, owners, [A, A], [SMALL + bad_small, LARGE + 0.005 * (1 if bad_small > 0 else -1)],
             [SMALL, LARGE])
    assert (r["ok"], r["tris"], r["source_polygons_not_covered"], r["uncovered_examples"]) == (False, 2, 1, [0])
    # large polygon (index 1) offends, small within tolerance
    r = _run(fn, faces, owners, [A, A], [SMALL + 0.0000005 * (1 if bad_small > 0 else -1), LARGE + bad_large],
             [SMALL, LARGE])
    assert (r["ok"], r["tris"], r["source_polygons_not_covered"], r["uncovered_examples"]) == (False, 2, 1, [1])
    assert r["wrong_finish"] == r["unmatched"] == r["ambiguous"] == 0


def _mutant(old, new):
    src = inspect.getsource(qa_packages.source_finish_report)
    assert src.count(old) == 1
    ns = dict(vars(qa_packages))
    exec(compile(src.replace(old, new), "<mutant>", "exec"), ns)
    return ns["source_finish_report"]


def _killed_by(fn):
    killed = []
    for i, (P, T, ok) in enumerate(CASES):
        try:
            _check_one(fn, P, T, ok)
        except AssertionError:
            killed.append(i)
    return killed


def test_mutation_without_absolute_term_killed_by_small_accepted_case():
    fn = _mutant("> 1e-6 + 1e-5 * p_areas[i]", "> 1e-5 * p_areas[i]")
    killed = _killed_by(fn)
    assert 0 in killed and 1 in killed          # small accepted cases
    assert 4 not in killed and 5 not in killed  # large accepted cases survive


def test_mutation_without_relative_term_killed_by_large_accepted_case():
    fn = _mutant("> 1e-6 + 1e-5 * p_areas[i]", "> 1e-6")
    killed = _killed_by(fn)
    assert 4 in killed and 5 in killed          # large accepted cases
    assert 0 not in killed and 1 not in killed  # small accepted cases survive


def test_unmutated_function_kills_nothing():
    assert _killed_by(qa_packages.source_finish_report) == []
