"""Sokolniki #1925 step 4 [D412, D413, D417, D418]: finish zones, UV report table, uv_config.json, windows + curtain walls as texture.

Pattern: n/a | new-case: tests of jobs/sokolniki-uvk1000/hooks/inset_build.py (body_finish, ring_relation),
inset_sheet.py (uv_rows) and uv_config.json against the shared atlas spec validator (no DCC).
Synthetic: all geometry and report numbers below are made up for the tests.
"""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / 'jobs/sokolniki-uvk1000'


def _load(name):
    spec = importlib.util.spec_from_file_location(name + '_1925', D / 'hooks' / (name + '.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ib = _load('inset_build')
sh = _load('inset_sheet')
CFG = json.loads((D / 'uv_config.json').read_text(encoding='utf-8'))
Z = CFG['zoning']
RING = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0], [0.0, 0.0]]


def test_ring_relation_facade_and_jamb():
    d, cos = ib.ring_relation((5.0, 0.0), (0.0, -1.0), RING)   # on the south line, facing out
    assert d == pytest.approx(0.0) and cos == pytest.approx(1.0)
    d, cos = ib.ring_relation((5.0, 0.2), (1.0, 0.0), RING)    # jamb across the south line, 0.2 m deep
    assert d == pytest.approx(0.2) and cos == pytest.approx(0.0)


@pytest.mark.parametrize('vol,z,finish', [
    ('N', (0.0, 0.3, 0.6), '02_porcelain_600_RAL7012'),
    ('N', (4.5, 6.0, 8.04), '01_brick_F301-80'),
    ('D', (0.6, 2.0, 3.84), '02_porcelain_600_RAL7012'),
    ('D', (4.5, 6.0, 8.04), '03_cassette_RAL9003'),
    ('S', (0.6, 1.8, 3.04), '01_brick_F301-80'),
    ('S', (3.6, 5.0, 6.64), '03_cassette_RAL9003'),
    ('H', (17.42, 20.0, 22.7), '03_cassette_RAL9003'),
])
def test_body_finish_dark_light_bands(vol, z, finish):
    assert ib.body_finish(vol, (0.0, -1.0, 0.0), z, 0.0, 1.0, 5.0, Z)[0] == finish


def test_body_finish_reveals_parapets_and_roof():
    up, down, side = (0.0, 0.0, 1.0), (0.0, 0.0, -1.0), (1.0, 0.0, 0.0)
    assert ib.body_finish('D', up, (18.97, 18.97, 18.97), 0.1, 0.0, 1.0, Z) == ('14_flashing_RAL7016', 'parapet_top')
    assert ib.body_finish('D', up, (0.9, 0.9, 0.9), 0.1, 0.0, 0.5, Z) == ('11_reveal_RAL9003', 'sill_head_soffit')
    assert ib.body_finish('D', down, (3.0, 3.0, 3.0), 0.1, 0.0, 9.0, Z) == ('11_reveal_RAL9003', 'sill_head_soffit')
    assert ib.body_finish('D', up, (7.5, 7.5, 7.5), 0.3, 0.0, 12.0, Z) == ('21_roof_membrane', 'ledge_roof')
    assert ib.body_finish('S', side, (11.12, 12.0, 13.5), 0.15, 1.0, 3.0, Z) == ('14_flashing_RAL7016', 'parapet_inner')
    assert ib.body_finish('S', side, (4.2, 5.0, 6.64), 0.1, 0.0, 1.0, Z) == ('11_reveal_RAL9003', 'jamb')
    # the outer parapet face stays cladding (on the ring line)
    assert ib.body_finish('S', (0.0, -1.0, 0.0), (11.12, 12.0, 13.5), 0.0, 1.0, 3.0, Z)[0] == '03_cassette_RAL9003'


def test_body_finish_refuses_a_face_across_a_finish_level():
    with pytest.raises(ValueError, match='crosses the finish level 3.84'):
        ib.body_finish('D', (0.0, -1.0, 0.0), (3.0, 4.0, 5.0), 0.0, 1.0, 5.0, Z)


def test_uv_config_is_a_valid_shared_atlas_spec():
    import sys
    sys.path.insert(0, str(ROOT))
    from tools.derive import finish_map
    finish_map.validate_spec(CFG)
    udims = sorted(t['udim'] for t in CFG['finishes'].values())
    assert udims == list(range(1001, 1001 + len(udims)))
    used = set(CFG['material_map'].values()) | {Z['reveal'], Z['parapet_top'], Z['parapet_inner'], Z['ledge_roof']}
    used |= {f for v in Z['volumes'].values() for _, f in v['bands']}
    assert used <= set(CFG['finishes'])
    for t in CFG['finishes'].values():   # tools/blender/vpm_uv.lmax contract for textured finishes
        if t['kind'] == 'full':
            assert len(t['P']) == 2 and all(type(s) is bool for s in t['shift'])
            per = max([p for p, s in zip(t['P'], t['shift']) if s] or [0.0])
            assert t['S'] - 2 * CFG['pad_m'] - per > 1.5


def test_uv_rows_scales_texel_to_the_atlas_region():
    rep = {'objects': {
        'A': {'tris_before': 10, 'tris_after': 14, 'overflow_ngons_split': 1,
              'edges_before': {'open': 4, 'open_len_m': 8.0, 'nonmanifold': 0},
              'edges_after': {'open': 6, 'open_len_m': 8.0, 'nonmanifold': 0},
              'uv_qa': {'01_brick_F301-80': {'faces': 5, 'overflow': 0}},
              'density_px_per_m': {'01_brick_F301-80': [913, 1024]}},
        'B': {'tris_before': 4, 'tris_after': 4,
              'edges_before': {'open': 4, 'open_len_m': 4.0, 'nonmanifold': 0},
              'edges_after': {'open': 4, 'open_len_m': 4.5, 'nonmanifold': 0},
              'uv_qa': {'12_frame_RAL9003': {'faces': 2, 'overflow': 1}}, 'density_px_per_m': {}}}}
    rows, tot = sh.uv_rows(rep, CFG, {'region': 377})
    brick = next(r for r in rows if r['finish'] == '01_brick_F301-80')
    assert brick['faces'] == 5 and brick['npm_px_per_m'] == [84.0, 94.2]
    assert next(r for r in rows if r['finish'] == '12_frame_RAL9003')['npm_px_per_m'] is None
    assert tot == {'tris_before': 14, 'tris_after': 18, 'overflow': 1, 'ngons_split': 1,
                   'open_len_changed': ['B'], 'nonmanifold_after': 0}


def test_before_after_pairs_v009_vs_atlas_same_views(tmp_path):
    # review r1 P1-3: the sheet shows «До» v009 | «После» atlas for F01, F05 and the iso from the same cameras
    for tag in ('v009', 'atlas'):
        for fid in ('F01', 'F05', 'iso'):
            (tmp_path / ('%s_%s.png' % (tag, fid))).write_bytes(b'png')
    pairs = sh.before_after_pairs(str(tmp_path))
    assert [p[0] for p in pairs] == ['F01', 'F05', 'iso']
    assert all(Path(b).name.startswith('v009_') and Path(a).name.startswith('atlas_') for _, _, b, a in pairs)
    (tmp_path / 'v009_F05.png').unlink()
    with pytest.raises(FileNotFoundError, match='v009_F05'):
        sh.before_after_pairs(str(tmp_path))


# ---------------------------------------------------------------- #1925 r4 [D417]: windows shown as texture
W1 = {'type': 'WB_Окно_2Створки_1Фрамуга_Слева', 'c': [0.0, 0.0], 'r': [1.0, 0.0], 'box': [-1.15, 1.15, 0.6, 3.04],
      'panes': [[-1.06, 0.19, 0.71, 2.95], [0.26, 1.06, 0.71, 1.2], [0.31, 1.01, 1.32, 2.9]]}


def _mirror(it):
    u0, u1 = it['box'][:2]
    return dict(it, panes=[[u0 + u1 - b, u0 + u1 - a, c, d] for a, b, c, d in it['panes']])


def test_window_hand_and_panes_seen_from_outside():
    assert not ib.window_hand(W1['box'], W1['panes'])            # big fixed pane left = Revit 'Слева'
    assert ib.window_hand(W1['box'], _mirror(W1)['panes'])
    assert ib.window_panes(W1['box'], W1['panes'], False)[0] == [0.09, 1.34, 0.11, 2.35]
    assert ib.window_panes(W1['box'], W1['panes'], True)[-1] == [0.96, 2.21, 0.11, 2.35]


def test_pack_cells_largest_common_scale_without_overlap():
    sizes = {'a': (3.7, 2.94), 'b': (2.3, 2.44), 'c': (1.1, 2.44), 'd': (2.8, 3.24)}
    k, boxes = ib.pack_cells(sizes, 4.0, 0.04)
    assert 0.3 < k < 1.0
    for n, (x0, y0, x1, y1) in boxes.items():
        assert 0 < x0 < x1 < 4.0 and 0 < y0 < y1 < 4.0
        assert x1 - x0 == pytest.approx(sizes[n][0] * k, abs=1e-3)
        for m, b in boxes.items():
            assert m == n or not (x0 < b[2] and b[0] < x1 and y0 < b[3] and b[1] < y1)
    assert ib.pack_cells({'a': (1.0, 1.0)}, 4.0, 0.04)[0] == 1.0


def _cfg():
    cfg = json.loads(json.dumps(CFG))
    for f in ('07_window_RAL7016', '08_door_RAL7016'):
        for k in ('cells', 'cell_scale'):
            cfg['finishes'][f].pop(k, None)
    cfg['window_texture'].pop('instances', None)
    return cfg


def test_wintex_one_drawing_per_type_size_and_hand():
    scan = {'a': W1, 'b': dict(W1, c=[10.0, 0.0]), 'm': dict(_mirror(W1), c=[20.0, 0.0])}
    out = ib.wintex(scan, _cfg())
    t = out['finishes']['07_window_RAL7016']
    assert t['pattern'] == 'elevations' and t['shift'] == [False, False]
    assert set(t['cells']) == {'W1_2.3x2.4', 'W1_2.3x2.4_M', '_face'}
    assert t['cells']['W1_2.3x2.4']['instances'] == 2
    assert t['cells']['W1_2.3x2.4']['panes'][0] == [0.09, 1.34, 0.11, 2.35]
    assert t['cells']['W1_2.3x2.4_M']['panes'][-1] == [0.96, 2.21, 0.11, 2.35]
    assert [r[0] for r in out['window_texture']['instances']] == ['W1_2.3x2.4', 'W1_2.3x2.4', 'W1_2.3x2.4_M']
    import sys
    sys.path.insert(0, str(ROOT))
    from tools.derive import finish_map
    finish_map.validate_spec(out)


def test_match_window_maps_the_instance_box_onto_its_drawing():
    out = ib.wintex({'a': W1}, _cfg())
    cells = out['finishes']['07_window_RAL7016']['cells']
    rows = out['window_texture']['instances']
    row = ib.match_window((0.6, 0.15, 1.8), (0.0, -1.0, 0.0), cells, rows, 0.6)   # right strip, 0.15 m set back
    assert row is rows[0]
    assert ib.match_window((0.6, 0.15, 1.8), (1.0, 0.0, 0.0), cells, rows, 0.6) is None   # jamb, not the window
    assert ib.match_window((0.6, 0.9, 1.8), (0.0, -1.0, 0.0), cells, rows, 0.6) is None   # too deep
    b = cells[row[0]]['box']
    assert ib.window_uv((-1.15, 0.15, 0.6), row, cells[row[0]]) == pytest.approx((b[0], b[1]))
    assert ib.window_uv((1.15, 0.15, 3.04), row, cells[row[0]]) == pytest.approx((b[2], b[3]))
    assert ib.window_uv((0.0, 0.15, 1.82), row, cells[row[0]]) == pytest.approx(((b[0] + b[2]) / 2, (b[1] + b[3]) / 2))


def test_uv_config_window_rows_point_at_drawn_cells():
    wt = CFG['window_texture']
    cells = {n: f for f, t in CFG['finishes'].items() if t.get('pattern') == 'elevations' for n in t['cells']}
    assert set(cells) and all(r[0] in cells for r in wt['instances'])
    assert sum(1 for r in wt['instances'] if r[0][0] in 'WD') == 244 and wt['source']['sha256'].startswith('feaae527')


def test_elevations_painter_draws_glass_panes_inside_the_profile():
    import sys
    sys.path.insert(0, str(ROOT))
    from tools.derive import finish_painter
    t = {'S': 4.0, 'rgb': [56, 62, 66], 'glass_rgb': [92, 120, 138], 'rough': 0.1, 'metal': 0.0,
         'pattern': 'elevations', 'cells': {'w': {'box': [0.0, 0.0, 2.0, 2.0], 'size': [2.0, 2.0],
                                                  'panes': [[0.1, 0.9, 0.1, 1.9], [1.1, 1.9, 0.1, 1.9]]}}}
    dif, alpha, _, _ = finish_painter.make_full(t, 400)
    assert alpha is None
    px = 100                                           # px per metre; image rows from the top, v up
    glass = dif[400 - 1 * px, int(0.5 * px)]
    mullion = dif[400 - 1 * px, int(1.0 * px)]
    assert glass[2] > 110 and abs(int(mullion[0]) - 56) < 8
    assert abs(int(dif[100, 300][0]) - 56) < 8          # outside every cell = profile colour


# ------------------------------------------------ #1925 r5 [D418]: curtain walls drawn by their Revit panels
def _cw(fin, c, box, panes):
    return {'obj': 'G', 'i': int(c[0]), 'finish': fin, 'c': c, 'r': [1.0, 0.0], 'box': box, 'panes': panes}


def test_cw_panes_clip_to_the_face_and_drop_slivers():
    box = [-1.0, 1.0, 0.0, 3.0]
    panes = [[-0.95, -0.05, 0.05, 2.95], [0.05, 0.95, 0.05, 2.95], [0.98, 1.9, 0.05, 2.95], [-1.9, -0.95, 0.0, 3.0]]
    assert ib.cw_panes(box, panes) == [[0.05, 0.95, 0.05, 2.95], [1.05, 1.95, 0.05, 2.95]]


def test_cw_grid_has_about_one_metre_mullions_and_transoms_at_the_levels():
    p = ib.cw_grid([0.0, 4.1, 0.0, 9.0], [3.0, 6.0, 9.5], 1.0, 0.05)
    xs = sorted({(a, b) for a, b, _, _ in p})
    zs = sorted({(c, d) for _, _, c, d in p})
    assert len(xs) == 4 and len(zs) == 3 and len(p) == 12
    assert xs[0] == pytest.approx((0.025, 1.0), abs=1e-3) and zs[1] == pytest.approx((3.025, 5.975), abs=1e-3)


def test_wintex_curtain_walls_small_like_windows_large_on_the_revit_grid():
    fin = '06_cw_stick_RAL7016'
    small = [[0.05, 0.95, 0.05, 2.95]]
    big = [[x + 0.025, x + 0.875, z + 0.025, z + 2.875] for x in (0.0, 0.9, 1.8) for z in (0.0, 2.9)]
    faces = [_cw(fin, [0.0, 0.0], [-0.5, 0.5, 0.0, 3.0], [[a - 0.5, b - 0.5, c, d] for a, b, c, d in small]),
             _cw(fin, [5.0, 0.0], [-0.5, 0.5, 0.0, 3.0], [[a - 0.5, b - 0.5, c, d] for a, b, c, d in small]),
             _cw(fin, [9.0, 0.0], [-1.35, 1.35, 0.0, 5.8], [[a - 1.35, b - 1.35, c, d] for a, b, c, d in big]),
             _cw(fin, [20.0, 0.0], [-2.0, 2.0, 0.0, 5.8], [])]
    out = ib.wintex({'a': W1}, _cfg(), cw=faces)
    t = out['finishes'][fin]
    assert t['pattern'] == 'elevations'
    assert set(t['cells']) == {'CWs_1.0x3.0', 'CW_2.7x5.8', 'CW_4.0x5.8', '_face'}
    assert t['cells']['CWs_1.0x3.0']['instances'] == 2 and t['cells']['CWs_1.0x3.0']['panes'] == small
    assert len(t['cells']['CW_2.7x5.8']['panes']) == 6
    grid = t['cells']['CW_4.0x5.8']['panes']                       # no Revit panels: 1 m grid, transoms at 2.9
    assert len({p[0] for p in grid}) == 4 and len({p[2] for p in grid}) == 2
    rows = [r for r in out['window_texture']['instances'] if r[0].startswith('CW')]
    assert [r[0] for r in rows] == ['CWs_1.0x3.0', 'CWs_1.0x3.0', 'CW_2.7x5.8', 'CW_4.0x5.8']
    row = ib.match_window((9.0, 0.0, 2.0), (0.0, -1.0, 0.0), t['cells'], out['window_texture']['instances'], 0.6)
    assert row[0] == 'CW_2.7x5.8'
    import sys
    sys.path.insert(0, str(ROOT))
    from tools.derive import finish_map
    finish_map.validate_spec(out)


def test_cw_groups_join_touching_coplanar_strips_into_one_wall():
    fin = '06_cw_stick_RAL7016'
    a = _cw(fin, [0.0, 0.0], [-0.5, 0.5, 0.0, 3.0], [[-0.45, 0.6, 0.05, 2.95]])
    b = _cw(fin, [1.0, 0.0], [-0.5, 0.5, 0.0, 3.0], [[-0.4, 0.45, 0.05, 2.95]])
    c = _cw(fin, [1.0, 0.5], [-0.5, 0.5, 0.0, 3.0], [])              # parallel, 0.5 m deeper: another wall
    g = ib.cw_groups([a, b, c])
    assert [x['faces'] for x in g] == [2, 1]
    assert g[0]['box'] == [-0.5, 1.5, 0.0, 3.0]
    assert ib.cw_panes(g[0]['box'], g[0]['panes']) == [[0.05, 1.1, 0.05, 2.95], [1.1, 1.95, 0.05, 2.95]]


def test_uv_config_curtain_walls_are_drawn_from_revit():
    cells = {n: f for f, t in CFG['finishes'].items() if t.get('pattern') == 'elevations' for n in t['cells']}
    rows = [r for r in CFG['window_texture']['instances'] if r[0].startswith('C')]
    assert sorted(set(cells.values())) == ['05_cw_structural_RAL7016', '06_cw_stick_RAL7016',
                                           '07_window_RAL7016', '08_door_RAL7016']
    assert len(rows) == 60 and all(r[0] in cells for r in rows)       # 97 v009 faces -> 60 Revit walls
    assert sum(1 for r in rows if r[0].startswith('CWs')) == 11
    assert CFG['finishes']['06_cw_stick_RAL7016']['rgb'] == CFG['finishes']['07_window_RAL7016']['rgb']   # RAL 7016


def test_elevations_spec_refuses_overlap_and_panes_outside():
    import sys
    sys.path.insert(0, str(ROOT))
    from tools.derive import finish_map
    t = {'S': 4.0, 'glass_rgb': [1, 2, 3], 'cells': {'a': {'box': [0, 0, 2, 2], 'size': [1, 1], 'panes': []},
                                                    'b': {'box': [1, 1, 3, 3], 'size': [1, 1], 'panes': []}}}
    with pytest.raises(ValueError, match='overlaps'):
        finish_map.validate_elevations('x', t)
    t['cells'] = {'a': {'box': [0, 0, 2, 2], 'size': [1, 1], 'panes': [[0.5, 1.5, 0, 1]]}}
    with pytest.raises(ValueError, match='outside'):
        finish_map.validate_elevations('x', t)


PR_FILES_1925 = (
    "jobs/sokolniki-uvk1000/README.md",
    "jobs/sokolniki-uvk1000/uv_config.json",
    "jobs/sokolniki-uvk1000/hooks/inset_build.py",
    "jobs/sokolniki-uvk1000/hooks/inset_sheet.py",
    "jobs/sokolniki-uvk1000/hooks/inset_write_blender.py",
    "tests/test_uv_compaction_1380.py",
    "tools/derive/finish_map.py",
    "tools/derive/finish_painter.py",
)


STALE_ID = "D" + "416"  # main's #1951 batch-5b row; spelled split so the PR diff never cites it


@pytest.mark.parametrize("rel", PR_FILES_1925)
def test_no_stale_d416_citation_after_renumber_to_d417(rel):
    """This card's windows decision was renumbered to [D417] (rule 42)."""
    assert f"[{STALE_ID}]" not in (ROOT / rel).read_text(encoding="utf-8")


def test_d416_row_is_not_this_cards_decision():
    rows = [l for l in (ROOT / "docs/decisions.md").read_text(encoding="utf-8").splitlines() if l.startswith(f"| {STALE_ID} |")]
    assert len(rows) == 1 and "#1925" not in rows[0]
