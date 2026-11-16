"""new-case: synthetic INSERT placement regressions for the Ground DXF adapter (#1535)."""
import ezdxf
import pytest
from shapely.geometry import Polygon
from dt_ai.geometry import ground_site as gs


def fixture():
    doc = ezdxf.new()
    block = doc.blocks.new('COVER', base_point=(1, 2, 0))
    hatch = block.add_hatch()
    hatch.bgcolor = (10, 20, 30)
    hatch.paths.add_polyline_path([(1, 2), (4, 2), (4, 4), (1, 4)], is_closed=True)
    ins = doc.modelspace().add_blockref('COVER', (10, 20))
    return doc, hatch, ins


def row(hatch, chain):
    return {'id': 1, 'name': 'Paving', 'hatches': [
        {'handle': hatch.dxf.handle, 'insert_chain': chain}]}


@pytest.mark.parametrize('sx,sy,angle', [(1, 1, 0), (2, 2, 90), (-2, 2, 30), (2, -2, -45)])
def test_placed_hatch_full_transform(sx, sy, angle):
    doc, hatch, ins = fixture()
    ins.dxf.xscale, ins.dxf.yscale, ins.dxf.rotation = sx, sy, angle
    cover = gs.covers_from_dxf(doc, [row(hatch, [ins.dxf.handle])], .002)[0]
    # Independent oracle from analytic scale/rotation about the block base point.
    import math
    a = math.radians(angle)
    pts = [(10 + sx*x*math.cos(a) - sy*y*math.sin(a),
            20 + sx*x*math.sin(a) + sy*y*math.cos(a)) for x, y in [(0, 0), (3, 0), (3, 2), (0, 2)]]
    assert cover.polygons[0].symmetric_difference(Polygon(pts)).area < 1e-10
    assert sum(p.area for p in cover.polygons) == pytest.approx(6*abs(sx*sy))
    assert cover.colour == (10, 20, 30)
    assert cover.sources == row(hatch, [ins.dxf.handle])['hatches']


def test_self_touching_even_odd_requires_explicit_opt_in():
    doc, hatch, ins = fixture()
    hatch.paths.clear()
    # Two lobes sharing a point: all edges must survive decomposition.
    hatch.paths.add_polyline_path([(1, 2), (3, 2), (3, 4), (1, 4), (1, 2),
                                   (-1, 2), (-1, 0), (1, 0)], is_closed=True)
    spec = row(hatch, [ins.dxf.handle])
    with pytest.raises(ValueError, match='not repaired'):
        gs.covers_from_dxf(doc, [spec], .002)
    spec['self_touching'] = 'even-odd'
    cover = gs.covers_from_dxf(doc, [spec], .002)[0]
    assert len(cover.polygons) == 2
    assert sum(p.area for p in cover.polygons) == pytest.approx(8)
    expected = Polygon([(10, 20), (12, 20), (12, 22), (10, 22)]).union(
        Polygon([(8, 18), (10, 18), (10, 20), (8, 20)]))
    from shapely.ops import unary_union
    actual = unary_union(cover.polygons)
    assert actual.symmetric_difference(expected).area == pytest.approx(0)
    assert actual.boundary.equals(expected.boundary)


def test_nested_mirror_and_minsert_cells():
    doc, hatch, inner = fixture()
    doc.modelspace().delete_entity(inner)
    parent = doc.blocks.new('PARENT', base_point=(5, 7, 0))
    inner = parent.add_blockref('COVER', (5, 7), dxfattribs={'xscale': -2, 'yscale': 2, 'rotation': 90})
    outer = doc.modelspace().add_blockref('PARENT', (100, 200), dxfattribs={
        'xscale': 3, 'yscale': 3, 'rotation': 90, 'row_count': 2, 'column_count': 3,
        'row_spacing': 30, 'column_spacing': 20})
    for r in range(2):
        for c in range(3):
            chain = [{'handle': outer.dxf.handle, 'cell': [r, c]}, inner.dxf.handle]
            cover = gs.covers_from_dxf(doc, [row(hatch, chain)], .002)[0]
            expected = Polygon([(100-30*r+6*x, 200+20*c-6*y)
                                for x, y in [(0, 0), (3, 0), (3, 2), (0, 2)]])
            assert cover.polygons[0].symmetric_difference(expected).area < 1e-9
            assert sum(p.area for p in cover.polygons) == pytest.approx(216)


def test_bounded_relief_continuation_explicit_and_reported():
    from shapely.geometry import box
    boundary = box(0, 0, 4, 4)
    covers = [gs.Cover(1, 'Lawn', [boundary], (1, 2, 3), 'spec')]
    points = [(0, 0, 100), (3.9, 0, 100), (3.9, 4, 100), (0, 4, 100)]
    with pytest.raises(ValueError, match='outside the relief TIN'):
        gs.build_site(boundary, covers, 1, points, 100)
    result = gs.build_site(boundary, covers, 1, points, 100,
                          relief_extension={'max_m': .11, 'reason': 'synthetic explicit permission'})
    evidence = result.report['stages']['relief']['continuation']
    assert evidence['max_m'] == .11 and evidence['sampled_points'] > 0
    assert evidence['max_used_m'] == pytest.approx(.1)
    assert result.report['passed'] is False
    with pytest.raises(ValueError, match='outside the relief TIN'):
        gs.build_site(boundary, covers, 1, points, 100,
                      relief_extension={'max_m': .05, 'reason': 'insufficient bound'})


def test_source_bound_skinny_relief_refinement_does_not_round_off_shared_edge():
    import numpy as np
    pts = [(-96.47200000000001,47.026,-.9000000000000057),
           (-89.46300000000001,41.827,-1),
           (-85.33200000000001,38.762,-.7000000000001023),
           (-73.006,29.618000000000002,-.7000000000001023)]
    sampler = gs.gc.ReliefSampler(gs.gc.build_tin(pts))
    v = [(-88.469677,41.089627),(-88.739451,41.290162),(-88.45,41.075),(-88.469703,41.089646)]
    t = [[0,1,2],[3,2,1]]
    out_v, out_t, rep = gs.gc._refine_relief(v,t,sampler,.01)
    xy = np.asarray(out_v)[np.asarray(out_t)]
    assert sampler.max_error(xy).max() <= .01
    assert Polygon(v[:3]).union(Polygon([v[j] for j in t[1]])).symmetric_difference(
        __import__('shapely').ops.unary_union([Polygon(x) for x in xy])).area < 1e-12


@pytest.mark.parametrize('tiny', [1e-3, 1e-6, 1e-9])
def test_even_odd_retains_every_positive_lobe_and_hole(tiny):
    # Synthetic figure-eight with a much smaller non-zero lobe: no area cutoff is licensed.
    g = gs._even_odd_ring([(0,0),(1,0),(1,1),(0,1),(0,0),(-tiny,0),(-tiny,-tiny),(0,-tiny)])
    assert len(g.geoms) == 2
    assert min(p.area for p in g.geoms) == pytest.approx(tiny*tiny, rel=1e-12, abs=0)
    assert g.boundary.distance(Polygon([(0,0),(1,0),(1,1),(0,1)]).boundary) == 0


@pytest.mark.parametrize('alias', ['resolved_spec', 'hardlink_dxf', 'partial', 'stale'])
def test_placed_cli_alias_and_stale_refusals(tmp_path, alias):
    import json, os, subprocess, sys
    from pathlib import Path
    from test_ground_site_1406 import make_spec, SITE
    spec, data = make_spec(tmp_path)
    dxf = Path(data['dxf']['path'])
    doc = ezdxf.readfile(dxf)
    hatch = doc.entitydb[data['covers'][1]['hatches'][0]]
    block = doc.blocks.new('PLACED')
    doc.modelspace().move_to_layout(hatch, block)
    ins = doc.modelspace().add_blockref('PLACED', (0,0))
    data['covers'][1]['hatches'] = [{'handle':hatch.dxf.handle, 'insert_chain':[ins.dxf.handle]}]
    doc.saveas(dxf)
    data['dxf']['sha256'] = gs.sha256(dxf)
    spec.write_text(json.dumps(data),encoding='utf-8')
    out = tmp_path/'out'
    if alias == 'resolved_spec':
        out = tmp_path/'unused'/'..'/spec.name
    elif alias == 'hardlink_dxf':
        os.link(dxf, out)
    elif alias == 'partial':
        (tmp_path/'out.partial').mkdir()
        (tmp_path/'out.partial'/'foreign.txt').write_text('preserve')
    else:
        r = subprocess.run([sys.executable,str(SITE),str(spec),str(out)],capture_output=True,text=True)
        assert r.returncode == 0, r.stderr
    before = {str(p.relative_to(tmp_path)):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    r = subprocess.run([sys.executable,str(SITE),str(spec),str(out)],capture_output=True,text=True)
    assert r.returncode == 2
    assert {str(p.relative_to(tmp_path)):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()} == before


@pytest.mark.parametrize('mutation', ['unknown_row', 'changed_spec', 'changed_dxf'])
def test_publication_refuses_unknown_mapping_and_changed_inputs(tmp_path, monkeypatch, mutation):
    from test_ground_site_1406 import make_spec
    from tools.ground import build_ground_site as cli
    import json
    from pathlib import Path
    spec, data = make_spec(tmp_path)
    if mutation == 'unknown_row':
        data['covers'][0]['insert_chian'] = ['typo']
        spec.write_text(json.dumps(data), encoding='utf-8')
        with pytest.raises(ValueError, match='insert_chian'):
            cli.run(spec, tmp_path/'out')
    else:
        original = gs.build_site
        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            path = spec if mutation == 'changed_spec' else Path(data['dxf']['path'])
            path.write_bytes(path.read_bytes()+b'\n')
            return result
        monkeypatch.setattr(gs, 'build_site', changed)
        with pytest.raises(ValueError, match='changed during'):
            cli.run(spec, tmp_path/'out')
    assert not (tmp_path/'out').exists()
    assert not (tmp_path/'out.partial').exists()


@pytest.mark.parametrize('bound', [0, -1, .001, float('nan'), float('inf'), True])
def test_relief_extension_invalid_or_at_snap_bound(bound):
    with pytest.raises(ValueError, match='relief_extension'):
        gs.relief_margin(.001, {'max_m': bound, 'reason':'synthetic'})


def test_same_hatch_two_placements_refused():
    doc, hatch, ins = fixture()
    other = doc.modelspace().add_blockref('COVER', (50, 60))
    spec = row(hatch, [ins.dxf.handle])
    spec['hatches'] += row(hatch, [other.dxf.handle])['hatches']
    with pytest.raises(ValueError, match=f'hatch {hatch.dxf.handle} listed'):
        gs.covers_from_dxf(doc, [spec], .002)


@pytest.mark.parametrize('attr,value', [('xscale', 2), ('xscale', float('nan')),
    ('rotation', float('inf')), ('insert', (float('inf'), 0, 0)), ('extrusion', (0, 1, 0))])
def test_named_unsupported_insert_transform(attr, value):
    doc, hatch, ins = fixture()
    setattr(ins.dxf, attr, value)
    with pytest.raises(ValueError, match=f'INSERT {ins.dxf.handle}'):
        gs.covers_from_dxf(doc, [row(hatch, [ins.dxf.handle])], .002)


@pytest.mark.parametrize('chain', [None, [], ['missing'], [{'handle': 'missing', 'other': 1}]])
def test_partial_chain_refused(chain):
    doc, hatch, ins = fixture()
    with pytest.raises(ValueError):
        gs.covers_from_dxf(doc, [row(hatch, chain)], .002)


@pytest.mark.parametrize('cell', [None, [-1, 0], [2, 0], [0, 3], [True, 0], [0]])
def test_minsert_requires_exact_valid_cell(cell):
    doc, hatch, ins = fixture()
    ins.dxf.row_count, ins.dxf.column_count = 2, 3
    step = ins.dxf.handle if cell is None else {'handle': ins.dxf.handle, 'cell': cell}
    with pytest.raises(ValueError, match=f'INSERT {ins.dxf.handle}.*cell'):
        gs.covers_from_dxf(doc, [row(hatch, [step])], .002)


def test_generated_similarity_area_and_contour():
    import math
    from shapely.ops import unary_union
    for scale in [.125, .5, 1., 3., 16.]:
        for angle in range(-180, 181, 30):
            for mirror in [-1, 1]:
                doc, hatch, ins = fixture()
                ins.dxf.xscale, ins.dxf.yscale = mirror*scale, scale
                ins.dxf.rotation = angle
                cover = gs.covers_from_dxf(doc, [row(hatch, [ins.dxf.handle])], .002)[0]
                a = math.radians(angle)
                expected = Polygon([(10+scale*(mirror*x*math.cos(a)-y*math.sin(a)),
                                     20+scale*(mirror*x*math.sin(a)+y*math.cos(a)))
                                    for x,y in [(0,0),(3,0),(3,2),(0,2)]])
                actual = unary_union(cover.polygons)
                assert actual.area == pytest.approx(6*scale**2)
                assert actual.symmetric_difference(expected).area < 1e-8


@pytest.mark.parametrize('policy', [True, '', 'repair', 'buffer', 1])
def test_unknown_even_odd_policy_refused(policy):
    doc, hatch, ins = fixture()
    spec = row(hatch, [ins.dxf.handle])
    spec['self_touching'] = policy
    with pytest.raises(ValueError, match='self_touching'):
        gs.covers_from_dxf(doc, [spec], .002)
