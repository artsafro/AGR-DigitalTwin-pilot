"""Synthetic #298 v015 site rules: MAF atlas slot remap and «Верона» insert -> placement point."""
import importlib.util
import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rules = _load('site_assembly_rules_v015', 'jobs/VATUTINO-SITE/assembly_rules.py')
gen = _load('maf_gen_bench_t', 'tools/library/maf_gen_bench.py')
CFG = json.loads((ROOT / 'jobs/VATUTINO-SITE/maf/verona-gen.config.json').read_text(encoding='utf-8'))


def test_remap_rect_maps_corners_and_centre():
    src, dst = [0.0, 0.5, 0.25, 0.75], [0.5, 0.0, 1.0, 0.5]
    assert rules.remap_rect([0.0, 0.5], src, dst) == pytest.approx([0.5, 0.0])
    assert rules.remap_rect([0.25, 0.75], src, dst) == pytest.approx([1.0, 0.5])
    assert rules.remap_rect([0.125, 0.625], src, dst) == pytest.approx([0.75, 0.25])


def test_remap_rect_refuses_uv_outside_its_reviewed_slot():
    with pytest.raises(ValueError, match='outside'):
        rules.remap_rect([0.3, 0.6], [0.0, 0.5, 0.25, 0.75], [0.5, 0.0, 1.0, 0.5])


def _rot(p, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c)


@pytest.mark.parametrize('path,insert_rot', [
    ([[0.0, 0.0], [3.0, 1.0]], 30.0),
    ([[0.0, 0.0], [-1.5, -1.2], [0.5, -4.0]], 0.0),       # L-shape, longest segment second
    ([[0.0, 0.0], [0.0, -2.0], [2.5, -2.0]], 354.6),
])
def test_verona_point_puts_the_generated_mesh_on_the_dwg_strip(path, insert_rot):
    insert = [-7600.0, -15300.0]
    spec = dict(CFG['params'], path=path, materials={r: i + 1 for i, r in enumerate(CFG['materials'])}, name='T')
    mesh = gen.build_clad_box(spec)
    shape = {'centreline_block_m': path, 'inserts_in_568BF': [
        {'handle': 'H1', 'insert_m': insert, 'rotation_deg': insert_rot}]}
    pt = rules.verona_point(shape, mesh['plan_rotation_deg'], CFG['params']['depth'], 'VAT_MAF_T3508_99')
    assert pt['label'] == 'VAT_MAF_T3508_99' and pt['handle'] == 'H1' and pt['inside'] is True
    # engine: world = T(point) . Rz(rotation) . v_local (bbox centre anchor = local origin)
    world = [(pt['x'] + q[0], pt['y'] + q[1]) for q in (_rot(v, pt['rotation']) for v in mesh['verts'])]
    # expected: the strip of the block centreline, block -> world by the DWG insert
    lp, _, _ = gen._offsets([tuple(p) for p in path], CFG['params']['depth'] / 2)
    _, rp, _ = gen._offsets([tuple(p) for p in path], CFG['params']['depth'] / 2)
    strip = [(insert[0] + q[0], insert[1] + q[1]) for q in (_rot(p, insert_rot) for p in lp + rp)]
    for axis in (0, 1):
        assert min(w[axis] for w in world) == pytest.approx(min(s[axis] for s in strip), abs=1e-6)
        assert max(w[axis] for w in world) == pytest.approx(max(s[axis] for s in strip), abs=1e-6)


def test_verona_points_relabel_adapter_inserts_and_add_missing_ones():
    shapes = {'rows': {
        '1': {'status': 'found', 'block': 'B1', 'centreline_block_m': [[0, 0], [2, 0]],
              'inserts_in_568BF': [{'handle': 'A', 'insert_m': [1.0, 2.0], 'rotation_deg': 0}]},
        '2': {'status': 'found', 'block': 'B2', 'centreline_block_m': [[0, 0], [2, 0]],
              'inserts_in_568BF': [{'handle': 'B', 'insert_m': [5.0, 6.0], 'rotation_deg': 90}]}}}
    report = {'rows': [{'row': 1, 'set_id': 'S1', 'plan_rotation_deg': 0.0},
                       {'row': 2, 'set_id': 'S2', 'plan_rotation_deg': 0.0}]}
    adapter = [{'handle': 'A', 'label': 'B1', 'x': 1.0, 'y': 2.0, 'z': 7.5, 'rotation': 0, 'inside': True},
               {'handle': 'Z', 'label': 'Other', 'x': 0, 'y': 0, 'z': 0, 'rotation': 0, 'inside': True}]
    pts, log = rules.verona_points(shapes, report, adapter, 0.6)
    by = {p['handle']: p for p in pts}
    assert set(by) == {'A', 'B', 'Z'} and len(pts) == 3
    assert by['A']['label'] == 'S1' and by['A']['z'] == 7.5 and by['A']['x'] == pytest.approx(2.0)
    assert by['B']['label'] == 'S2' and by['B']['z'] == 0.0 and by['B']['y'] == pytest.approx(7.0)
    assert by['Z']['label'] == 'Other'
    assert {r['handle']: r['source'] for r in log} == {'A': 'adapter insert relabelled', 'B': 'plan-shapes insert added'}
