"""AGR Tools 1.0 (#1024, branch T): `ucx.stairs`, `qa.omk_te`, `export.place_by_passport`; no Max, no pymxs.

Every named defect has a test that is RED on a MODEL of the source behaviour (written from the measured behaviour, no
source code copied, #853) and GREEN on the new core:
  - qa.omk_te: Copy with an active filter takes row N of the whole sorted table (GeoAGR Get OMK TE Code
    `GeoAGR.ms:66134`, lab L15 docs/experiments/qa.omk_te.md);
  - export.place_by_passport: new-telegram `Import_HP_from_coordinates.ms` SHA256
    ecb001a9b2a5447ee7f7cc696a3af5412aad01348b249f088c0cf590f9778675: GeoJSON values go through MAXScript `execute`;
    a `Dummy` stays after an error (lab T06, Max 2026);
  - ucx.stairs: new code (GeoAGR gap #8), the acceptance cases of issue #1024 section 24.
The Max glue is exercised on a fake `pymxs` scene (nodes, importFile, delete, selection, one undo counter).
"""
import contextlib
import importlib.util
import json
import math
import struct
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ec = sys.modules.get('agr_tools_edit_core') or _load(PKG / 'edit_core.py', 'agr_tools_edit_core')
omk = _load(PKG / 'omk_core.py', 'agr_tools_omk_core_t')
omkm = _load(PKG / 'omk_max.py', 'agr_tools_omk_max_t')
pg = _load(PKG / 'placegeo_core.py', 'agr_tools_placegeo_core_t')
pgm = _load(PKG / 'placegeo_max.py', 'agr_tools_placegeo_max_t')
us = _load(PKG / 'ucxstairs_core.py', 'agr_tools_ucxstairs_core_t')
usm = _load(PKG / 'ucxstairs_max.py', 'agr_tools_ucxstairs_max_t')


# =====================================================================================================
# qa.omk_te
# =====================================================================================================
def synthetic_table(n=50):
    """50 rows `place<TAB>code`. 'стена' appears in 4 rows spread over the sorted table (not at the top)."""
    names = ['Здание', 'Окно', 'Крыша', 'Дверь', 'Пол', 'Потолок', 'Лестница', 'Колонна', 'Балка', 'Фундамент']
    lines = ['place\tcode']
    for i in range(n):
        name = names[i % len(names)] + ' {:02d}'.format(i)
        if i in (7, 19, 31, 43):
            name = 'Стена {:02d}'.format(i)
        lines.append('{}\t{}'.format(name, 1000 + i * 7))
    return '\n'.join(lines) + '\n'


def source_pick(rows, text, index):
    return omk.source_copy_code(rows, text, index)


def new_pick(rows, text, index):
    return omk.choose_code(omk.pick_visible(rows, text, index))


@pytest.mark.parametrize('impl', [
    pytest.param(source_pick, marks=pytest.mark.xfail(strict=True, reason='GeoAGR.ms:66134 row N of the whole table')),
    new_pick])
def test_omk_copy_with_filter_takes_the_visible_row(impl):
    rows, _ = omk.parse_table(synthetic_table())
    visible = omk.filter_rows(omk.sort_rows(rows), 'стена')
    assert len(visible) == 4
    assert impl(rows, 'стена', 2) == visible[1]['code']
    assert visible[1]['code'] != omk.sort_rows(rows)[1]['code']


def test_omk_code_comes_from_the_row_key_not_from_an_index():
    rows, _ = omk.parse_table(synthetic_table())
    row = omk.pick_visible(rows, 'стена', 3)
    by_key = {r['key']: r for r in rows}
    assert omk.choose_code(row) == by_key[row['key']]['code']
    assert row['place'].startswith('Стена')


def test_omk_filter_is_case_insensitive_in_place_and_code():
    rows, _ = omk.parse_table('place\tcode\nСтена наружная\t0905\nОкно\t1234\nполы\t9050\n')
    assert [r['place'] for r in omk.filter_rows(rows, 'СТЕНА')] == ['Стена наружная']
    assert sorted(r['place'] for r in omk.filter_rows(rows, '905')) == ['Стена наружная', 'полы']


def test_omk_short_code_is_padded_and_reported():
    rows, problems = omk.parse_table('place\tcode\nСтена\t905\n')
    assert rows[0]['code'] == '0905'
    assert [p['kind'] for p in problems] == ['short_code']


def test_omk_many_codes_in_a_cell_is_ambiguous_and_never_written_silently():
    rows, problems = omk.parse_table('place\tcode\nСтена\t9047 9048\nОкно\t1111\n')
    assert any(p['kind'] == 'many_codes' for p in problems)
    row = omk.pick_visible(rows, 'стена', 1)
    with pytest.raises(omk.OmkError) as e:
        omk.choose_code(row)
    assert e.value.code == 'many_codes'
    assert omk.choose_code(row, 2) == '9048'
    assert omk.choose_code(row, '9047') == '9047'


def test_omk_empty_and_codeless_rows_do_not_break_the_sort():
    rows, problems = omk.parse_table('place\tcode\nБ\t2222\n\nА\t\nВ\t1111\n\t3333\n')
    ordered = omk.sort_rows(rows)
    places = [r['place'].casefold() for r in ordered]
    assert places == sorted(places)
    assert sorted(p['kind'] for p in problems) == ['empty_row', 'no_code', 'no_place']


def test_omk_encodings_and_errors_are_russian_and_clear():
    text = 'place\tcode\nСтена\t1234\n'
    for data in (text.encode('utf-8'), text.encode('utf-8-sig'), text.encode('utf-16')):
        assert omk.parse_table(omk.decode_table(data))[0][0]['code'] == '1234'
    with pytest.raises(omk.OmkError) as e:
        omk.decode_table(text.encode('cp1251'))
    assert e.value.code == 'table_encoding' and 'UTF-8' in e.value.message and '\ufffd' not in e.value.message
    with pytest.raises(omk.OmkError) as e:
        omk.parse_table('x\ty\nСтена\t1234\n')
    assert e.value.code == 'table_header'


def test_omk_pick_out_of_range_is_an_error():
    rows, _ = omk.parse_table(synthetic_table())
    with pytest.raises(omk.OmkError) as e:
        omk.pick_visible(rows, 'стена', 5)
    assert e.value.code == 'pick_range'


class FakeRT:
    def __init__(self):
        self.clip = None
        self.objects = []

    def setclipboardText(self, text):
        self.clip = text


@pytest.fixture
def fake_rt(monkeypatch):
    rt = FakeRT()
    monkeypatch.setitem(sys.modules, 'pymxs', types.SimpleNamespace(runtime=rt))
    return rt


def omk_ctx(options):
    core = sys.modules['agr_tools_omk_core_t']
    return types.SimpleNamespace(core=core, edit=ec, options=options)


def test_omk_tool_reports_code_of_second_visible_row_and_copies_it(tmp_path, fake_rt):
    table = tmp_path / 'omk.tsv'
    table.write_text(synthetic_table(), encoding='utf-8')
    rep = omkm.qa_omk_te(omk_ctx({'table': str(table), 'filter': 'стена', 'pick': 2}), 'preview', None, None)
    rows, _ = omk.parse_table(synthetic_table())
    want = omk.sort_rows([r for r in rows if r['place'].startswith('Стена')])[1]['code']
    assert rep['status'] == 'pass' and rep['plan']['code'] == want == fake_rt.clip
    assert rep['plan']['visible'] == 4 and rep['plan']['rows'] == 50
    assert rep['objects'] == [] and ec.validate_report(rep)


def test_omk_tool_without_table_names_the_path(tmp_path, fake_rt):
    missing = tmp_path / 'нет.tsv'
    rep = omkm.qa_omk_te(omk_ctx({'table': str(missing)}), 'preview', None, None)
    assert rep['status'] == 'fail' and rep['plan']['code'] is None and fake_rt.clip is None
    item = rep['plan']['ambiguous'][0]
    assert item['code'] == 'table_missing' and str(missing) in item['message']
    rep = omkm.qa_omk_te(omk_ctx({}), 'preview', None, None)
    assert rep['status'] == 'fail' and rep['plan']['ambiguous'][0]['code'] == 'table_path'


def test_omk_tool_busy_file_and_bad_encoding_are_reports_not_crashes(tmp_path, fake_rt, monkeypatch):
    bad = tmp_path / 'cp.tsv'
    bad.write_bytes('place\tcode\nСтена\t1234\n'.encode('cp1251'))
    rep = omkm.qa_omk_te(omk_ctx({'table': str(bad)}), 'preview', None, None)
    assert rep['status'] == 'fail' and rep['plan']['ambiguous'][0]['code'] == 'table_encoding'
    ok = tmp_path / 'ok.tsv'
    ok.write_text(synthetic_table(), encoding='utf-8')
    real_open = open

    def busy(path, *a, **k):
        if str(path) == str(ok):
            raise PermissionError(13, 'Permission denied')
        return real_open(path, *a, **k)
    monkeypatch.setattr('builtins.open', busy)
    rep = omkm.qa_omk_te(omk_ctx({'table': str(ok)}), 'preview', None, None)
    assert rep['plan']['ambiguous'][0]['code'] == 'table_busy' and fake_rt.clip is None


def test_omk_tool_is_read_only_and_ships_no_table():
    with pytest.raises(ValueError, match='read-only'):
        omkm.qa_omk_te(omk_ctx({}), 'apply', None, None)
    omk_dir = ROOT / 'adapters/max/agr_tools/data/omk'
    shipped = [p.name for p in omk_dir.glob('*')] if omk_dir.exists() else []
    assert not [n for n in shipped if n.lower().endswith(('.csv', '.tsv', '.txt'))]
    assert not (ROOT / 'adapters/max/agr_tools/data/OMK_TE3.csv').exists()


# =====================================================================================================
# export.place_by_passport
# =====================================================================================================
def passport(x=12345.678, y=-6789.012, h='152,3', **props):
    p = {'address': 'synthetic', 'h_relief': h}
    p.update(props)
    return json.dumps({'type': 'FeatureCollection', 'features': [
        {'type': 'ObjectFeature', 'geometry': {'type': 'Point', 'coordinates': [x, y]}, 'properties': p, 'Glasses': []}]},
        ensure_ascii=False).encode('utf-8')


def source_execute_model(text, executed):
    """Model of the source: the value after the colon of the `h_relief` / `coordinates` lines is trimmed and run
    through MAXScript `execute` (every executed string is recorded)."""
    for line in text.splitlines():
        if '"h_relief"' in line:
            value = line.split(':', 1)[1].strip().replace('"', '').replace(',', '.')
            executed.append(value)
        if '"coordinates"' in line:
            executed.append(line.split(':', 1)[1])


def test_passport_values_are_data_not_code():
    bait = 'x" ; createFile "C:/marker.txt'
    values = pg.read_passport(passport(address=bait, name='(createFile "marker")'))
    assert values == {'x': 12345.678, 'y': -6789.012, 'h': 152.3}


def test_source_executes_the_bait_the_new_reader_refuses_it():
    executed = []
    text = json.dumps({'features': [{'properties': {'h_relief': '1; createFile "m.txt"'}}]}, indent=1)
    source_execute_model(text, executed)
    assert any('createFile' in e for e in executed)  # RED: the source model hands the bait to execute
    doc = passport(h='1; createFile "m.txt"')
    with pytest.raises(pg.PassportError) as e:
        pg.read_passport(doc)
    assert e.value.code == 'schema'


@pytest.mark.parametrize('data,code', [
    (b'{"type": ', 'json'),
    (b'\xff\xfe\x00', 'encoding'),
    (b'[]', 'schema'),
    (json.dumps({'type': 'FeatureCollection', 'features': []}).encode(), 'schema'),
    (b'{"type":"FeatureCollection","type":"x","features":[]}', 'json'),
    (b'{"type":"FeatureCollection","features":[{"type":"ObjectFeature","geometry":{"type":"Point","coordinates":[1,NaN]},'
     b'"properties":{"h_relief":1}}]}', 'json'),
])
def test_passport_bad_inputs(data, code):
    with pytest.raises(pg.PassportError) as e:
        pg.read_passport(data)
    assert e.value.code == code


def test_passport_h_relief_forms():
    for raw, want in ((152.3, 152.3), ('152,3', 152.3), ('152.3', 152.3), (' -3 ', -3.0), (0, 0.0)):
        assert pg.read_passport(passport(h=raw))['h'] == pytest.approx(want)
    for raw in ('', 'synthetic', None, True, '1e3', '1 2'):
        with pytest.raises(pg.PassportError):
            pg.read_passport(passport(h=raw))


def test_find_passport_zero_one_many(tmp_path):
    with pytest.raises(pg.PassportError) as e:
        pg.find_passport(str(tmp_path), ['a.fbx'])
    assert e.value.code == 'passport_missing'
    assert pg.find_passport(str(tmp_path), ['a.fbx', 'p.GeoJSON']).endswith('p.GeoJSON')
    with pytest.raises(pg.PassportError) as e:
        pg.find_passport(str(tmp_path), ['a.geojson', 'b.geojson'])
    assert e.value.code == 'passport_many'


def test_single_precision_error_is_reported_not_hidden():
    near = pg.plan_target({'x': 12345.678, 'y': -6789.012, 'h': 152.3}, 1.0)
    assert near['precision_m'] < pg.PRECISION_TOL_M
    far = pg.plan_target({'x': 2345678.123, 'y': 1234567.456, 'h': 152.3}, 1.0)
    assert far['precision_m'] > pg.PRECISION_TOL_M  # float32 holds ~0.25 m at 2.3e6: cannot be 1 mm
    mm = pg.plan_target({'x': 12345.678, 'y': 0.0, 'h': 0.0}, 0.001)
    assert mm['target_units'][0] == pytest.approx(12345678.0)


# ---- a fake pymxs scene ------------------------------------------------------------------------------
class P3:  # single-precision positions like Max (Point3 is float32)
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


class Node:
    def __init__(self, handle, name, pos=(0.0, 0.0, 0.0), parent=None):
        self.handle, self.name, self.parent, self.deleted = handle, name, parent, False
        self.pos = P3(*[struct.unpack('f', struct.pack('f', c))[0] for c in pos])


class Scene:
    def __init__(self):
        self.nodes = []
        self.selected = []
        self.next = 100
        self.undo_records = 0
        self.import_calls = 0

    # --- pymxs.runtime surface used by the glue
    @property
    def objects(self):
        return [n for n in self.nodes if not n.deleted]

    @property
    def selection(self):
        return list(self.selected)

    def Point3(self, x, y, z):
        return Node(0, 'p', (x, y, z)).pos

    def name(self, text):
        return text

    def getHandleByAnim(self, n):
        return n.handle

    def isValidNode(self, n):
        return not n.deleted

    def delete(self, n):
        n.deleted = True

    def clearSelection(self):
        self.selected = []

    def selectMore(self, n):
        self.selected.append(n)

    def importFile(self, path, flag):
        self.import_calls += 1
        spec = json.loads(Path(path).read_text(encoding='utf-8').split(chr(10), 1)[1])
        made = []
        for item in spec['nodes']:
            self.next += 1
            parent = made[item['parent']] if item.get('parent') is not None else None
            n = Node(self.next, item['name'], item.get('pos', (0, 0, 0)), parent)
            self.nodes.append(n)
            made.append(n)
            if item.get('fail_after'):
                raise RuntimeError('importer crashed after creating ' + item['name'])
        self.selected = list(made)


class FakeHost:
    def __init__(self, scene, unit_m=1.0):
        self.scene, self.unit_m = scene, unit_m

    def m_per_unit(self):
        return self.unit_m

    def refs(self, nodes):
        return [{'host': 'max', 'doc': 'untitled', 'handle': n.handle, 'name': n.name} for n in nodes]

    @contextlib.contextmanager
    def undo(self, label):
        self.scene.undo_records += 1
        yield


@pytest.fixture
def scene(monkeypatch):
    sc = Scene()
    sc.nodes.append(Node(1, 'Existing', (5, 5, 5)))
    sc.selected = [sc.nodes[0]]
    monkeypatch.setitem(sys.modules, 'pymxs', types.SimpleNamespace(runtime=sc))
    return sc


def put(tmp_path, nodes=None, doc=None, name='model'):
    fbx = tmp_path / (name + '.fbx')
    fbx.write_text('; FBX 7.4 fake' + chr(10) + json.dumps({'nodes': nodes if nodes is not None else [{'name': 'Block', 'pos': [0, 0, 0]},
                                                                           {'name': 'Child', 'parent': 0, 'pos': [1, 1, 1]}]}),
                   encoding='utf-8')
    if doc is not None:
        (tmp_path / (name + '.geojson')).write_bytes(doc)
    return fbx


def run(scene, mode, options=None, preview=None, unit_m=1.0):
    ctx = types.SimpleNamespace(core=pg, edit=ec, options=options or {}, host=FakeHost(scene, unit_m))
    return pgm.export_place_by_passport(ctx, mode, None, preview)


def live(scene):
    return {n.name for n in scene.objects}


def test_place_preview_touches_nothing_and_reports_the_target(tmp_path, scene):
    fbx = put(tmp_path, doc=passport())
    rep = run(scene, 'preview', {'fbx': str(fbx)})
    assert rep['status'] == 'pass' and rep['plan']['target_units'] == pytest.approx([12345.678, -6789.012, 152.3])
    assert scene.import_calls == 0 and live(scene) == {'Existing'} and scene.undo_records == 0


def test_place_apply_moves_the_origin_to_the_passport_in_one_undo(tmp_path, scene):
    fbx = put(tmp_path, doc=passport())
    prev = run(scene, 'preview', {'fbx': str(fbx)})
    rep = run(scene, 'apply', preview=prev)
    block = next(n for n in scene.objects if n.name == 'Block')
    child = next(n for n in scene.objects if n.name == 'Child')
    assert (block.pos.x, block.pos.y, block.pos.z) == pytest.approx((12345.678, -6789.012, 152.3), abs=0.001)
    assert child.pos.x == pytest.approx(1.0, abs=1e-6)  # the child follows its parent, it is not moved twice
    assert scene.undo_records == 1 and rep['status'] == 'pass' and [o['name'] for o in rep['objects']] == ['Block']
    assert scene.selected == [scene.nodes[0]]  # the previous selection is back
    assert rep['plan']['readback_m'] < 0.001


def test_place_in_millimetre_scene_uses_the_unit_scale(tmp_path, scene):
    fbx = put(tmp_path, doc=passport(x=100.0, y=200.0, h='3'))
    prev = run(scene, 'preview', {'fbx': str(fbx)}, unit_m=0.001)
    run(scene, 'apply', preview=prev, unit_m=0.001)
    block = next(n for n in scene.objects if n.name == 'Block')
    assert (block.pos.x, block.pos.y, block.pos.z) == pytest.approx((100000.0, 200000.0, 3000.0), abs=1)


def test_place_large_msk_coordinates_need_an_explicit_decision(tmp_path, scene):
    fbx = put(tmp_path, doc=passport(x=2345678.123, y=1234567.456, h='152,3'))
    prev = run(scene, 'preview', {'fbx': str(fbx)})
    assert prev['status'] == 'fail' and prev['plan']['ambiguous'][0]['code'] == 'precision'
    with pytest.raises(ValueError, match='open problems'):
        run(scene, 'apply', preview=prev)
    assert live(scene) == {'Existing'}
    prev = run(scene, 'preview', {'fbx': str(fbx), 'accept_precision_loss': True})
    rep = run(scene, 'apply', preview=prev)
    block = next(n for n in scene.objects if n.name == 'Block')
    assert abs(block.pos.x - 2345678.123) <= 0.25 + 1e-9  # single precision: the honest limit of Max
    assert rep['plan']['precision_m'] > 0.001


def test_source_leaves_a_dummy_after_an_error_the_new_tool_leaves_nothing(tmp_path, scene):
    # MODEL OF THE SOURCE: import, group under a Dummy, then a broken GeoJSON -> "print" and stop, Dummy stays
    model_scene = Scene()
    model_scene.nodes.append(Node(1, 'Dummy'))
    assert live(model_scene) == {'Dummy'}  # RED side: garbage after the failed run
    fbx = put(tmp_path, doc=b'{"type": ')
    prev = run(scene, 'preview', {'fbx': str(fbx)})
    assert prev['status'] == 'fail' and prev['plan']['ambiguous'][0]['code'] == 'json'
    with pytest.raises(ValueError):
        run(scene, 'apply', preview=prev)
    assert live(scene) == {'Existing'}


def test_place_importer_crash_after_partial_import_rolls_back(tmp_path, scene):
    fbx = put(tmp_path, nodes=[{'name': 'A'}, {'name': 'B', 'fail_after': True}], doc=passport())
    prev = run(scene, 'preview', {'fbx': str(fbx)})
    with pytest.raises(RuntimeError, match='crashed'):
        run(scene, 'apply', preview=prev)
    assert live(scene) == {'Existing'}


def test_place_empty_import_is_an_error_with_zero_new_nodes(tmp_path, scene):
    fbx = put(tmp_path, nodes=[], doc=passport())
    prev = run(scene, 'preview', {'fbx': str(fbx)})
    with pytest.raises(ValueError, match='ни одного объекта'):
        run(scene, 'apply', preview=prev)
    assert live(scene) == {'Existing'}


def test_place_changed_passport_makes_the_preview_stale(tmp_path, scene):
    fbx = put(tmp_path, doc=passport())
    prev = run(scene, 'preview', {'fbx': str(fbx)})
    (tmp_path / 'model.geojson').write_bytes(passport(x=1.0))
    with pytest.raises(ec.StalePreview):
        run(scene, 'apply', preview=prev)
    assert live(scene) == {'Existing'}


def test_place_file_that_is_not_an_fbx_is_refused_before_the_importer(tmp_path, scene):
    fbx = tmp_path / 'model.fbx'
    fbx.write_bytes(b'MZ not an fbx')
    (tmp_path / 'model.geojson').write_bytes(passport())
    rep = run(scene, 'preview', {'fbx': str(fbx)})
    assert rep['status'] == 'fail' and rep['plan']['ambiguous'][0]['code'] == 'fbx_invalid'
    assert [f['status'] for f in rep['plan']['findings']] == ['fail']
    assert scene.import_calls == 0


def test_place_missing_inputs_are_reports(tmp_path, scene):
    rep = run(scene, 'preview', {'fbx': str(tmp_path / 'none.fbx')})
    assert rep['status'] == 'fail' and rep['plan']['ambiguous'][0]['code'] == 'fbx_missing'
    fbx = put(tmp_path)  # no passport beside it
    rep = run(scene, 'preview', {'fbx': str(fbx)})
    assert rep['plan']['ambiguous'][0]['code'] == 'passport_missing'
    with pytest.raises(ValueError):
        run(scene, 'preview', {})
    with pytest.raises(ValueError):
        run(scene, 'preview', {'fbx': 'a.obj'})


def test_place_bait_in_a_text_field_is_only_data(tmp_path, scene):
    marker = tmp_path / 'marker.txt'
    fbx = put(tmp_path, doc=passport(address='" ; createFile "{}"'.format(marker.as_posix())))
    prev = run(scene, 'preview', {'fbx': str(fbx)})
    run(scene, 'apply', preview=prev)
    assert not marker.exists() and prev['status'] == 'pass'


# =====================================================================================================
# ucx.stairs
# =====================================================================================================
RISE, RUN, WIDTH, STEPS = 0.17, 0.28, 1.2, 10


def box(x0, x1, y0, y1, z0, z1):
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    t = [(0, 3, 2), (0, 2, 1), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6),
         (3, 0, 4), (3, 4, 7)]
    return v, t


def merge(parts):
    verts, tris = [], []
    for v, t in parts:
        base = len(verts)
        verts += [list(p) for p in v]
        tris += [[a + base, b + base, c + base] for a, b, c in t]
    return verts, tris


def rot(verts, deg, origin=(3.0, 2.0)):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [[origin[0] + (v[0]) * c - v[1] * s, origin[1] + v[0] * s + v[1] * c, v[2]] for v in verts]


def stair_mesh(steps=STEPS):
    return merge([box(k * RUN, (k + 1) * RUN, 0, WIDTH, 0, (k + 1) * RISE) for k in range(steps)])


def prism(profile, width=WIDTH):
    """Extrude a CCW (s, z) profile across y in [0, width] into a closed outward-wound solid."""
    n = len(profile)
    v = [(s, 0.0, z) for s, z in profile] + [(s, width, z) for s, z in profile]
    t = []
    for i in range(1, n - 1):
        t.append((0, i, i + 1))
        t.append((n, n + i + 1, n + i))
    for i in range(n):
        j = (i + 1) % n
        t.append((i, n + j, j))
        t.append((i, n + i, n + j))
    return v, t


def wedge(lift=0.0, steps=STEPS):
    last = (steps - 1) * RUN
    top = steps * RISE
    return prism([(0.0, 0.0), (last, 0.0), (last, top + lift), (0.0, RISE + lift)])


def stair(ucx, deg=0.0, steps=STEPS):
    sv, st = stair_mesh(steps)
    if deg:
        sv = rot(sv, deg)
    pieces = []
    for i, (v, t) in enumerate(ucx):
        pieces.append({'name': 'UCX_Stair_{:02d}'.format(i + 1), 'verts': rot(v, deg) if deg else [list(p) for p in v],
                       'tris': [list(f) for f in t]})
    return {'verts': sv, 'tris': st, 'ucx': pieces}


def codes(res):
    return [f['code'] for f in res[0]]


def test_stairs_ten_steps_with_a_correct_pyramid_pass():
    res = us.evaluate_stair(stair([wedge()]), 0.30)
    assert res[0] == [] and res[1]['nosings'] == STEPS * 2 and res[1]['max_excess_cm'] < 0.1


def test_stairs_correct_pyramid_passes_rotated_in_plan():
    for deg in (35.0, 90.0, 200.0):
        assert us.evaluate_stair(stair([wedge()], deg), 0.10)[0] == [], deg


def test_stairs_step_by_step_ucx_fails_not_one_pyramid():
    boxes = [box(k * RUN, (k + 1) * RUN, 0, WIDTH, 0, (k + 1) * RISE) for k in range(STEPS)]
    res = us.evaluate_stair(stair(boxes), 1.0)
    assert codes(res) == ['ucx_not_single']
    apart = [box(k * RUN, (k + 1) * RUN - 0.002, 0, WIDTH, 0, (k + 1) * RISE) for k in range(STEPS)]
    one_object = us.evaluate_stair(stair([merge(apart)]), 1.0)  # ten solids attached into one object
    assert codes(one_object) == ['ucx_not_single'] and one_object[1]['ucx_parts'] == STEPS
    welded = us.evaluate_stair(stair([merge(boxes)]), 1.0)  # touching boxes weld into one non-convex lump
    assert 'ucx_not_convex' in codes(welded)


def test_stairs_ucx_40_cm_above_the_nosings_fails_at_30_passes_at_100():
    res = us.evaluate_stair(stair([wedge(lift=0.4)]), 0.30)
    assert codes(res) == ['ucx_too_high'] and '40.0' in res[0][0]['detail']
    assert us.evaluate_stair(stair([wedge(lift=0.4)]), 1.0)[0] == []


def test_stairs_tolerance_classes_10_30_100():
    lift = 0.2
    assert codes(us.evaluate_stair(stair([wedge(lift=lift)]), 0.10)) == ['ucx_too_high']
    assert us.evaluate_stair(stair([wedge(lift=lift)]), 0.30)[0] == []


def test_stairs_ucx_below_the_nosings_fails_stairs_outside():
    res = us.evaluate_stair(stair([wedge(lift=-0.12)]), 0.10)
    assert codes(res) == ['stairs_outside'] and '12.0' in res[0][0]['detail']
    assert us.evaluate_stair(stair([wedge(lift=-0.12)]), 0.30)[0] == []


def test_stairs_without_ucx_fail():
    assert codes(us.evaluate_stair(stair([]), 0.30)) == ['ucx_missing']


def test_stairs_open_or_concave_ucx_fail():
    v, t = wedge()
    open_ = us.evaluate_stair(stair([(v, t[:-2])]), 0.30)
    assert 'ucx_not_closed' in codes(open_)
    last = (STEPS - 1) * RUN
    concave = prism([(0.0, 0.0), (last, 0.0), (last, STEPS * RISE), (last / 2, 0.3), (0.0, RISE)])
    assert codes(us.evaluate_stair(stair([concave]), 1.0)) == ['ucx_not_convex']


def test_stairs_split_vertices_are_welded():
    v, t = wedge()
    verts, tris = [], []
    for a, b, c in t:
        base = len(verts)
        verts += [v[a], v[b], v[c]]
        tris.append((base, base + 1, base + 2))
    assert us.evaluate_stair(stair([(verts, tris)]), 0.30)[0] == []


def test_stairs_flat_object_is_skipped_not_passed():
    flat = merge([box(0, 2, 0, 1, 0, 0.02)])
    res = us.evaluate_stair({'verts': flat[0], 'tris': flat[1], 'ucx': []}, 0.30)
    assert res[0] == [] and 'skipped' in res[1]


def test_stairs_options_validate():
    assert us.stair_options({})['tolerance_cm'] == 30
    for bad in ({'tolerance_cm': 20}, {'tolerance_cm': True}, {'x': 1}):
        with pytest.raises(ValueError):
            us.stair_options(bad)
    assert us.is_stair_name('Лестница_01') and us.is_stair_name('Stair_A')
    assert not us.is_stair_name('UCX_Stair_A_01') and not us.is_stair_name('Wall')
    names = ['UCX_Stair_A', 'UCX_Stair_A_01', 'UCX_Stair_A_02', 'UCX_Stair_AB_01', 'UCX_Stair_A_x']
    assert us.ucx_of('Stair_A', names) == ['UCX_Stair_A', 'UCX_Stair_A_01', 'UCX_Stair_A_02']


def test_stairs_report_is_readonly_valid_and_empty_input_is_an_error():
    opts = us.stair_options({})
    ok = us.evaluate_stair(stair([wedge()]), 0.3)
    bad = us.evaluate_stair(stair([]), 0.3)
    rows = [{'handle': 5, 'name': 'Stair_ok', 'findings': ok[0], 'metrics': ok[1]},
            {'handle': 6, 'name': 'Stair_bad', 'findings': bad[0], 'metrics': bad[1]}]
    rep = us.ucx_stairs_report(ec, opts, rows, 'h' * 8)
    assert rep['status'] == 'fail' and rep['plan']['mode'] == 'preview' and ec.validate_report(rep)
    assert [d['item'] for d in rep['plan']['done']] == ['Stair_ok']
    with pytest.raises(ValueError, match='no stairs'):
        us.ucx_stairs_report(ec, opts, [], 'h')
    with pytest.raises(ValueError, match='read-only'):
        usm.ucx_stairs(types.SimpleNamespace(core=us, edit=ec, options={}, host=None), 'apply', None, None)


# ---- the Max glue on the fake scene -----------------------------------------------------------------------
class MeshNode:
    def __init__(self, handle, name, verts, tris):
        self.handle, self.name, self.verts, self.tris, self.deleted = handle, name, verts, tris, False


class StairScene:
    GeometryClass = 'geo'

    def __init__(self, meshes):
        self.nodes = [MeshNode(10 + i, n, v, t) for i, (n, v, t) in enumerate(meshes)]

    @property
    def objects(self):
        return self.nodes

    def isValidNode(self, n):
        return True

    def superClassOf(self, n):
        return 'geo'

    def getNodeByName(self, name):
        return next(n for n in self.nodes if n.name == name)


class MeshHost(FakeHost):
    def refs(self, nodes):
        return [{'host': 'max', 'doc': 'untitled', 'handle': n.handle, 'name': n.name, 'node': n} for n in nodes]

    def mesh(self, ref):
        n = ref['node']
        return {'verts': n.verts, 'faces': n.tris, 'mat_ids': [], 'ref': ref}


def test_stairs_glue_checks_every_stair_by_name_and_changes_nothing(monkeypatch):
    sv, st = stair_mesh()
    wv, wt = wedge()
    meshes = [('Stair_A', sv, st), ('UCX_Stair_A_01', wv, wt), ('Лестница_B', sv, st), ('Wall', sv, st)]
    sc = StairScene(meshes)
    monkeypatch.setitem(sys.modules, 'pymxs', types.SimpleNamespace(runtime=sc))
    ctx = types.SimpleNamespace(core=us, edit=ec, options={}, host=MeshHost(sc))
    rep = usm.ucx_stairs(ctx, 'preview', None, None)
    by = {o['name']: [f['code'] for f in o['findings']] for o in rep['objects']}
    assert by == {'Stair_A': [], 'Лестница_B': ['ucx_missing']} and rep['status'] == 'fail'
    assert [n.name for n in sc.nodes] == ['Stair_A', 'UCX_Stair_A_01', 'Лестница_B', 'Wall']
    assert rep['plan']['metrics']['Stair_A']['max_excess_cm'] < 0.1


# ---- the polygon stations of branch T: the same fixtures the live run builds, judged offline --------------------
def _t_build():
    return _load(ROOT / 'test-polygon/stations/T_build.py', 'agr_tools_t_build')


def test_polygon_stairs_fixtures_give_the_expected_codes():
    tb = _t_build()
    station = {s['button']: s for s in json.loads((ROOT / 'test-polygon/stations/T.json').read_text(encoding='utf-8'))['stations']}
    want = {r['name']: r['codes'] for r in station['ucx.stairs']['expected']}
    for obj in station['ucx.stairs']['objects']:
        stair, pieces = tb.stair_parts(obj['extra']['variant'])
        got = us.evaluate_stair({'verts': stair[0], 'tris': stair[1],
                                 'ucx': [{'name': 'UCX_x_{:02d}'.format(i), 'verts': v, 'tris': t}
                                         for i, (v, t) in enumerate(pieces, 1)]}, 0.30)
        assert [f['code'] for f in got[0]] == want[obj['name']], obj['name']


def test_polygon_omk_and_place_fixtures_pass(tmp_path, fake_rt):
    tb = _t_build()
    table = tmp_path / 'OMK_synth.tsv'
    table.write_bytes(tb.omk_table())
    opts = json.loads((ROOT / 'test-polygon/stations/T.json').read_text(encoding='utf-8'))['stations'][1]['options']
    rep = omkm.qa_omk_te(omk_ctx(dict(opts, table=str(table))), 'preview', None, None)
    assert rep['status'] == 'pass' and rep['plan']['findings'] == [{'name': 'code', 'status': 'pass'}]
    assert pg.read_passport(tb.passport_bytes())['h'] == pytest.approx(152.3)
    pg.check_fbx_header(tb.fbx_bytes())
