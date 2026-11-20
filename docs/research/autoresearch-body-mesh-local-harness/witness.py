"""Synthetic calibration witness; not native mesh or acceptance evidence."""
import copy
import math


def canonical(report):
    report = copy.deepcopy(report)
    report.pop('score')
    report.pop('local_irregular_area_share', None)
    report['penalties'].pop('irregular_area_share')
    return report


def witness(base, variant):
    clean = {'name': 'panels', 'verts': [[0, 0, 0], [2, 0, 0], [2, 0, 2], [0, 0, 2],
                                         [8, 0, 0], [11, 0, 0], [11, 0, 3], [8, 0, 3]],
             'faces': [[0, 1, 2, 3], [4, 5, 6, 7]]}
    injected = copy.deepcopy(clean)
    injected['verts'][2][0] += 1
    for obj in (clean, injected, clean):
        a, b = base([obj]), variant([obj])
        assert canonical(a) == canonical(b)
        p = b['penalties']['irregular_area_share']
        expected = 0.0 if obj is clean else (5 / 14 + 1.0) / 2
        assert math.isclose(p, expected, abs_tol=5e-7), (p, expected)
        if obj is clean:
            assert a['score'] == b['score']
