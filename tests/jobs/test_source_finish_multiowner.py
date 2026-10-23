"""new-case: same-label versus conflicting multiowner diagnostics of source_finish_report.

Acceptance table (A, B are finish strings; two source triangles
src_faces [(0,1,2),(1,2,3)]; positive finite literal areas; baseline GREEN
characterization of current behaviour, not a bug RED):

1. owners [(0,),(1,),(0,1)], t [.5,.5,.1], p [.5,.5], expected [A,A], delivered [A,A,A]
   -> ok true, tris 3, ambiguous = wrong = unmatched = uncovered = 0
   (the multiowner triangle is no error and adds no area).
2. same owners, expected [A,B], delivered [A,B,A] -> ok false, ambiguous 1,
   wrong = unmatched = uncovered = 0.
3. sole owner [(0,1)], delivered [A], t [.1], p [.5,.5]:
   expected [A,A] -> ambiguous 0, uncovered 2, ok false;
   expected [A,B] -> ambiguous 1, uncovered 2, wrong 0, ok false.
4. owners [(0,),(1,),()] with delivered [A,B,A], expected [A,B] -> unmatched 1,
   ambiguous = wrong = uncovered = 0, ok false.
5. delivered [A,A,A] with expected [A,B] and owners [(0,),(1,)]+... (two-triangle
   stream [(0,),(1,)], delivered [A,A]) -> wrong 1, example
   {tri 1, source_polygon 1, expected B, delivered A}; restoring B -> clean.
6. Areas omitted on the two singleton triangles give the same counters;
   a joint permutation of owners/delivered/areas and reversed multiowner tuples
   keep every counter; example indices are compared with remapped expectations.
7. Every input is unchanged. Mutants (every multiowner is ambiguous; a
   multiowner credits its area to a candidate) are caught by named controls.
"""

import copy
import itertools
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "jobs" / "TEC26-OKS" / "scripts"
sys.path.insert(0, str(_SCRIPTS))

import qa_packages  # noqa: E402

SRC = [(0, 1, 2), (1, 2, 3)]
COUNTERS = ("ok", "tris", "wrong_finish", "unmatched", "ambiguous", "source_polygons_not_covered")


def _run(fn, expected, owners, delivered, t=None, p=None):
    inputs = (expected, SRC, owners, delivered, t, p)
    before = copy.deepcopy(inputs)
    result = fn(expected, SRC, owners, delivered, t, p)
    assert inputs == before, "input mutated"
    return result


def _counts(r):
    return {k: r[k] for k in COUNTERS}


def _c(ok, tris, wrong, unm, amb, unc):
    return dict(zip(COUNTERS, (ok, tris, wrong, unm, amb, unc)))


OWN3 = [(0,), (1,), (0, 1)]
T3 = [0.5, 0.5, 0.1]
P2 = [0.5, 0.5]

# (name, expected, owners, delivered, t, p, counters)
CASES = [
    ("same_label_multi", ["A", "A"], OWN3, ["A", "A", "A"], T3, P2, _c(True, 3, 0, 0, 0, 0)),
    ("conflict_multi", ["A", "B"], OWN3, ["A", "B", "A"], T3, P2, _c(False, 3, 0, 0, 1, 0)),
    ("sole_same_label", ["A", "A"], [(0, 1)], ["A"], [0.1], P2, _c(False, 1, 0, 0, 0, 2)),
    ("sole_conflict", ["A", "B"], [(0, 1)], ["A"], [0.1], P2, _c(False, 1, 0, 0, 1, 2)),
    ("unmatched_third", ["A", "B"], [(0,), (1,), ()], ["A", "B", "A"], T3, P2, _c(False, 3, 0, 1, 0, 0)),
    ("wrong_label", ["A", "B"], [(0,), (1,)], ["A", "A"], [0.5, 0.5], P2, _c(False, 2, 1, 0, 0, 0)),
    ("clean_restored", ["A", "B"], [(0,), (1,)], ["A", "B"], [0.5, 0.5], P2, _c(True, 2, 0, 0, 0, 0)),
]
WRONG_EXAMPLE = [{"tri": 1, "source_polygon": 1, "expected": "B", "delivered": "A"}]


def _failures(fn):
    bad = []
    for name, exp, own, dl, t, p, want in CASES:
        r = _run(fn, exp, own, dl, t, p)
        if _counts(r) != want:
            bad.append(name)
    r = _run(fn, ["A", "B"], [(0,), (1,)], ["A", "A"], [0.5, 0.5], P2)
    if r["examples"] != WRONG_EXAMPLE:
        bad.append("wrong_example")
    return bad


def _mutant(multi_ambiguous=False, credit=False):
    def fn(expected, src_faces, owners, delivered, t_areas=None, p_areas=None):
        wrong = unmatched = ambiguous = 0
        exs = []
        per = [0.0] * len(src_faces)
        cnt = [0] * len(src_faces)
        for t, (own, got) in enumerate(zip(owners, delivered)):
            if not own:
                unmatched += 1
                continue
            if len(own) == 1 or credit:
                cnt[own[0]] += 1
                if t_areas is not None:
                    per[own[0]] += t_areas[t]
            want = {expected[i] for i in own}
            if len(want) != 1 or (multi_ambiguous and len(own) > 1):
                ambiguous += 1
                continue
            if got != next(iter(want)):
                wrong += 1
                exs.append({"tri": t, "source_polygon": own[0], "expected": next(iter(want)), "delivered": got})
        if t_areas is not None and p_areas is not None:
            unc = [i for i in range(len(src_faces)) if abs(per[i] - p_areas[i]) > 1e-6 + 1e-5 * p_areas[i]]
        else:
            unc = [i for i, f in enumerate(src_faces) if cnt[i] != len(f) - 2]
        return {
            "ok": not (wrong or unmatched or ambiguous or unc) and len(owners) > 0,
            "tris": len(owners), "wrong_finish": wrong, "unmatched": unmatched,
            "ambiguous": ambiguous, "source_polygons_not_covered": len(unc),
            "examples": exs,
        }
    return fn


def test_acceptance_table_counters():
    for name, exp, own, dl, t, p, want in CASES:
        assert _counts(_run(qa_packages.source_finish_report, exp, own, dl, t, p)) == want, name


def test_wrong_label_example_exact():
    r = _run(qa_packages.source_finish_report, ["A", "B"], [(0,), (1,)], ["A", "A"], [0.5, 0.5], P2)
    assert r["examples"] == WRONG_EXAMPLE


def test_multiowner_is_not_itself_an_error_and_adds_no_area():
    r = _run(qa_packages.source_finish_report, ["A", "A"], OWN3, ["A", "A", "A"], [0.5, 0.5, 9.0], P2)
    assert r["ok"] is True and r["source_polygons_not_covered"] == 0


def test_areas_omitted_matches_for_singleton_streams():
    for name in ("wrong_label", "clean_restored"):
        _, exp, own, dl, t, p, want = next(c for c in CASES if c[0] == name)
        assert _counts(_run(qa_packages.source_finish_report, exp, own, dl)) == want, name


def test_permutation_and_tuple_reversal_stable():
    for name, exp, own, dl, t, p, want in CASES:
        n = len(own)
        for perm in itertools.permutations(range(n)):
            o = [tuple(reversed(own[i])) for i in perm]
            d = [dl[i] for i in perm]
            ta = [t[i] for i in perm]
            r = _run(qa_packages.source_finish_report, exp, o, d, ta, p)
            assert _counts(r) == want, (name, perm)
            if name == "wrong_label":
                # remapped: original tri 1 now sits at perm.index(1)
                ex = r["examples"]
                assert ex == [dict(WRONG_EXAMPLE[0], tri=perm.index(1))], (name, perm)


def test_mutants_are_caught():
    assert _failures(qa_packages.source_finish_report) == []
    assert _failures(_mutant()) == []  # reference copy agrees with production
    m1 = _failures(_mutant(multi_ambiguous=True))
    assert "same_label_multi" in m1 and "sole_same_label" in m1
    m2 = _failures(_mutant(credit=True))
    assert "same_label_multi" in m2 and "conflict_multi" in m2
