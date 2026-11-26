"""new-case: r103 reachability oracle — review round 1 inputs as regression rows (synthetic, no sources)."""
import importlib.util
from pathlib import Path

import ezdxf
import pytest

SCRIPT = Path(__file__).resolve().parents[2] / 'docs/research/trainer_bounds_r103/measure.py'


@pytest.fixture(scope='module')
def m():
    spec = importlib.util.spec_from_file_location('r103_measure', SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _doc():
    doc = ezdxf.new()
    return doc, doc.modelspace()


def test_insert_without_definition_makes_p_incomplete_and_inconclusive(m):
    doc, msp = _doc()
    doc.blocks.new('GONE').add_line((0, 0), (1, 0))
    msp.add_blockref('GONE', (0, 0), dxfattribs={'layer': 'A-WALL-____-MCUT'})
    msp.add_line((0, 0), (1000, 0), dxfattribs={'layer': 'A-WALL-____-MCUT'})
    doc.blocks.delete_block('GONE', safe=False)
    inv = m.inventory(msp, m.layer_sets()['P'])
    assert inv['counts'] == {'missing_def': 1, 'ok': 1}
    assert inv['complete'] is False and inv['unread'][0]['status'] == 'missing_def'
    assert m.decide({f: [0.5] * 3 for f in m.FACES}, True, inv['complete'])[0] == 'inconclusive'


def test_empty_definition_is_inventoried_not_unread(m):
    doc, msp = _doc()
    doc.blocks.new('EMPTY')
    msp.add_blockref('EMPTY', (0, 0), dxfattribs={'layer': 'A-GLAZ-CURT-OTLN'})
    inv = m.inventory(msp, m.layer_sets()['P'])
    assert inv['counts'] == {'empty_def': 1}
    assert inv['empty_def_blocks'] == {'EMPTY': 1} and inv['complete'] is True


def test_bbox_error_is_unread(m, monkeypatch):
    _doc_, msp = _doc()
    msp.add_line((0, 0), (1, 0), dxfattribs={'layer': 'A-WALL-____-MCUT'})

    def boom(*_a, **_k):
        raise RuntimeError('bbox')
    monkeypatch.setattr(m.bbox, 'extents', boom)
    inv = m.inventory(msp, m.layer_sets()['P'])
    assert inv['counts'] == {'bbox_error': 1} and inv['complete'] is False


@pytest.mark.parametrize('dist, oracle, native', [(0.10004, 'refuted', 'fail'), (0.10000, 'confirmed', 'pass')])
def test_tolerance_boundary_uses_raw_distance_and_matches_native_bounds(m, dist, oracle, native):
    _d, msp = _doc()
    wall = msp.add_line((0, 0), (1, 0), dxfattribs={'layer': 'A-WALL-____-MCUT'})
    key = dict.fromkeys(m.FACES, 0.0)
    got = m.reach([('L03', wall, 'plan', {**key, 'x_min': dist})], key, lambda layer: True)
    assert got['x_min']['abs_m'] == pytest.approx(round(dist, 4))  # display value may equal the tolerance
    verdict, unreachable = m.decide({f: [got[f]['abs_raw_m']] * 3 for f in m.FACES}, True, True)
    assert verdict.startswith(oracle) and unreachable == (['x_min'] if oracle == 'refuted' else [])
    built = {'meshes': [{'bounds_m': [[dist, 0, 0], [0, 0, 0]]}]}
    zero = {'meshes': [{'bounds_m': [[0, 0, 0], [0, 0, 0]]}]}
    assert m.trainer.bounds_step(built, zero)['status'] == native


def test_selection_envelope_feeds_native_bounds_and_flags_missing_handles(m):
    _d, msp = _doc()
    a = msp.add_line((0, 0), (1, 0), dxfattribs={'layer': 'A-DOOR-____-OTLN'})
    b = msp.add_line((0, 0), (1, 0), dxfattribs={'layer': 'A-WALL-____-PATT'})
    rows = [('L03', a, 'plan', {'x_min': -1.02, 'x_max': 1.0, 'y_min': -2.0, 'y_max': 2.0}),
            ('L01', b, 'view-X+', {'x_min': -0.5, 'x_max': 0.5, 'z_min': 0.0, 'z_max': 3.0})]
    rb, missing = m.selection_envelope(rows, {'L03': (a.dxf.handle,), 'L01': (b.dxf.handle,)})
    assert missing == [] and rb['meshes'][0]['bounds_m'] == [[-1.02, -2.0, 0.0], [1.0, 2.0, 3.0]]
    key = {'meshes': [{'bounds_m': [[-1.0, -2.0, 0.0], [1.0, 2.0, 3.0]]}]}
    assert m.trainer.bounds_step(rb, key)['status'] == 'pass'
    none, missing = m.selection_envelope(rows, {'L03': (a.dxf.handle, 'FFFF')})
    assert none is None and missing == ['L03:FFFF']


def test_in_run_review_checks_pass(m):
    assert m.review_checks()['ok'] is True
