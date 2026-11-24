"""#1761: the native handoff harness bundle 001 must pass the #1730 work-FBX degree gate.

Bundle 001 of tests/max_tools/run_agr_tools_handoff_native.py is an 8-sided cylinder; its two 8-gon caps make the
Max FBX exporter triangulate the whole object, so handoff.export refuses it. The harness now splits every 6+-gon into
pieces of <= 5 corners (pure helper ngon_diagonal + polyop.createEdge) and keeps one negative row
(export_ngon_refused) that expects the gate to refuse an unsplit 8-gon prism.
The harness imports pymxs, so its pure helper is read with ast and executed alone.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.max_tools.test_handoff_work_fbx_degrees_1730 import binary_fbx, core

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / 'tests' / 'max_tools' / 'run_agr_tools_handoff_native.py'
TREE = ast.parse(HARNESS.read_text(encoding='utf-8'))
FUNCS = {n.name: n for n in TREE.body if isinstance(n, ast.FunctionDef)}


def _helper():
    assert 'ngon_diagonal' in FUNCS, 'harness has no ngon_diagonal helper (bundle 001 keeps its 8-gon caps)'
    ns = {}
    exec(compile(ast.Module(body=[FUNCS['ngon_diagonal']], type_ignores=[]), str(HARNESS), 'exec'), ns)
    return ns['ngon_diagonal']


def _split(face, diag):
    """face (corner list) -> pieces after repeatedly applying diag(n) as the harness loop does."""
    out, todo = [], [list(face)]
    while todo:
        f = todo.pop()
        d = diag(len(f))
        if d is None:
            out.append(f)
            continue
        a, b = d
        assert 0 <= a < b < len(f) and b - a >= 2 and not (a == 0 and b == len(f) - 1), (len(f), d)
        todo += [f[a:b + 1], f[b:] + f[:a + 1]]
    return out


def _cylinder(sides):
    """The poly faces of Cylinder(sides, heightsegs=1, capsegs=1): two caps + side quads."""
    caps = [list(range(sides)), list(range(2 * sides - 1, sides - 1, -1))]
    return caps + [[i, (i + 1) % sides, sides + (i + 1) % sides, sides + i] for i in range(sides)]


def _hist(faces):
    h = {}
    for f in faces:
        h[str(len(f))] = h.get(str(len(f)), 0) + 1
    return h


def _calls(fn):
    return [(c.func.id, c.lineno, c.args) for c in ast.walk(FUNCS[fn])
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)]


def test_octagon_cap_splits_into_two_pentagons():
    assert _split(list(range(8)), _helper()) and sorted(map(len, _split(list(range(8)), _helper()))) == [5, 5]


@pytest.mark.parametrize('n', range(3, 6))
def test_faces_up_to_five_corners_are_left_alone(n):
    assert _helper()(n) is None


def test_probe_every_ngon_splits_to_at_most_five_corners():
    """Invariant: for n in 6..96 every piece has 3..5 corners, every corner is kept and no corner is invented."""
    diag = _helper()
    for n in range(6, 97):
        pieces = _split(list(range(n)), diag)
        assert all(3 <= len(p) <= 5 for p in pieces), n
        assert set().union(*map(set, pieces)) == set(range(n)), n
        assert sum(len(p) for p in pieces) == n + 2 * (len(pieces) - 1), n


@pytest.mark.parametrize('n', [0, 1, 2, -1])
def test_degenerate_face_is_an_error(n):
    with pytest.raises(ValueError):
        _helper()(n)


def test_bundle_001_split_passes_the_gate_unsplit_is_refused():
    """Bundle 001 (8-sided cylinder, Max 2026 measurement): unsplit {'4': 8, '8': 2} is written as {'3': 28} and
    refused; split {'4': 8, '5': 4} is written face for face (Max keeps <= 5-gons, PR #1758 ngon/prism5) and passes."""
    raw = _cylinder(8)
    assert _hist(raw) == {'4': 8, '8': 2}
    split = [p for f in raw for p in _split(f, _helper())]
    assert _hist(split) == {'4': 8, '5': 4}
    verts = [0.0] * 48
    tris = [[f[0], f[k], f[k + 1]] for f in raw for k in range(1, len(f) - 1)]
    assert len(tris) == 28
    bad = core.check_work_fbx({'BODY_Brick_001': _hist(raw)}, binary_fbx([('BODY_Brick_001', verts, tris)]))
    assert [n for n, _d in bad] == ['BODY_Brick_001'] and 'triangulated' in bad[0][1]
    assert core.check_work_fbx({'BODY_Brick_001': _hist(split), 'BODY_Brick_002': _hist(split)},
                               binary_fbx([('BODY_Brick_001', verts, split), ('BODY_Brick_002', verts, split)])) == []


def test_harness_splits_bundle_001_before_uv_channel_2_and_instancing():
    calls = _calls('build_synthetic')
    split = [ln for name, ln, _a in calls if name == 'split_ngons']
    ch2 = [ln for name, ln, _a in calls if name == 'add_channel2']
    assert split and ch2 and min(split) < min(ch2), 'split_ngons must run before add_channel2 (map faces copied)'
    inst = [c.lineno for c in ast.walk(FUNCS['build_synthetic']) if isinstance(c, ast.Call)
            and isinstance(c.func, ast.Attribute) and c.func.attr == 'instance']
    assert inst and min(split) < min(inst), 'split before rt.instance so BODY_Brick_002 shares the split mesh'
    assert 'ngon_diagonal' in {name for name, _l, _a in _calls('split_ngons')}


def test_harness_keeps_a_negative_gate_row():
    """phase_export records export_ngon_refused, which expects handoff.export to refuse an unsplit 8-gon prism."""
    keys = [a[0].value for name, _l, a in _calls('phase_export')
            if name == 'check' and a and isinstance(a[0], ast.Constant)]
    assert 'export_ngon_refused' in keys
    src = ast.get_source_segment(HARNESS.read_text(encoding='utf-8'), FUNCS['export_ngon_refused'])
    assert 'handoff_export' in src and 'triangulated' in src and 'sides=8' in src and 'split_ngons' not in src
