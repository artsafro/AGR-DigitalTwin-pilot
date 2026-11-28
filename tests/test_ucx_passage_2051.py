"""new-case: exact synthetic portal probes for the shared local UCX pass (#2051)."""
import copy
import importlib.util
from pathlib import Path

import pytest

from test_ucx_resolve_1540 import box, row

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('ucx10_passage', ROOT / 'adapters/max/agr_tools/ucx10_core.py')
core = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(core)


@pytest.mark.parametrize('shift', [-170.0, 0.0, 200.0])
def test_passage_keeps_wall_and_preserves_unrelated_overlapping_frozen_bodies(shift):
    def body(i, x0, x1, y0, y1, z0, z1):
        return row(i, str(i), box(x0 + shift, x1 + shift, y0, y1, z0, z1))

    wall = body(1, -3, 3, -1, 1, -1, 4)
    frozen = [wall, body(2, 4, 5, -1, 1, 0, 3), body(3, 4.5, 6, -1, 1, 0, 3)]
    cutter = body(0, -1, 1, -2, 2, 0, 3)
    fill = body(4, -3.5, -2.5, -1, 1, 0, 3)
    snapshot = copy.deepcopy(frozen)
    result = core.cut_passage(frozen, cutter, [fill])
    assert result['replaced'] == [1]
    assert result['unchanged'] == [2, 3]
    assert frozen == snapshot
    assert result['passage_blockers'] == []
    assert result['pairs']['intersections'] == 0
    assert result['pairs']['min_gap_m'] >= 0.002
    new = [core.piece(p['verts'], p['tris']) for p in result['new']]
    for x, z in [(-2, 1), (2, 1), (0, -0.5), (0, 3.5), (-3.25, 1)]:
        probe = core.piece(*box(x + shift - .01, x + shift + .01, -.01, .01, z - .01, z + .01))
        assert any(core.separation(p, probe)[0] < 0 for p in new), (x, z)
    for x in (-.95, 0, .95):
        probe = core.piece(*box(x + shift - .01, x + shift + .01, -2, 2, 0.01, 2.99))
        assert all(core.separation(p, probe)[0] > 0 for p in new)


def test_unsupported_frozen_blocker_requires_a_partition():
    verts, tris = box(-2, 2, -1, 1, -1, 4)
    with pytest.raises(ValueError, match='partition'):
        core.cut_passage([row(1, 'open', (verts, tris[:-1]))], row(0, 'clearance', box(-1, 1, -2, 2, 0, 3)))


def test_nested_body_is_removed_but_touching_body_is_not_replaced():
    cutter = row('opening', 'opening', box(0, 3, 0, 3, 0, 3))
    nested = row('nested', 'nested', box(1, 2, 1, 2, 1, 2))
    touching = row('touching', 'touching', box(3, 4, 1, 2, 1, 2))
    sliver = row('sliver', 'sliver', box(4, 4.005, 1, 1.005, 1, 1.005))
    result = core.cut_passage([nested, touching], cutter, [sliver])
    assert result['replaced'] == ['nested']
    assert result['unchanged'] == ['touching']
    assert result['new'] == result['passage_blockers'] == []
    assert [r['source'] for r in result['discarded_slivers']] == ['sliver']
    assert result['source_volumes']['nested'] == {'seed_m3': 1.0, 'kept_m3': 0.0}


def test_partition_with_an_omitted_external_face_does_not_certify_open_mesh():
    verts, tris = box(-2, 2, -1, 1, -1, 4)
    fake = dict(row(1, 'open', (verts, tris[:-1])), partition=[tris])
    with pytest.raises(ValueError, match='changes its oriented boundary'):
        core.cut_passage([fake], row(0, 'clearance', box(-1, 1, -2, 2, 0, 3)))
