"""Pattern: new-case: explicit facade-DXF schedule regression and synthetic adversarial probes."""
import importlib.util
import json
from pathlib import Path

import ezdxf
import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / 'tools/methods/body/facade_openings_from_dxf.py'


def load():
    assert TOOL.exists(), 'F16: no reusable facade DXF opening schedule tool'
    spec = importlib.util.spec_from_file_location('facade_schedule', TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture(tmp_path):
    doc = ezdxf.new()
    doc.units = 4
    ent = doc.modelspace().add_lwpolyline([(1000, 2000), (2200, 2000), (2200, 3500), (1000, 3500)], close=True)
    note = doc.modelspace().add_text('synthetic')
    source = tmp_path / 'facade.dxf'
    doc.saveas(source)
    config = {'facades': {'north': {'origin_mm': [1000, 1000], 'direction': 1, 'datum_m': 0.5}},
              'openings': [{'id': 'W1', 'kind': 'window', 'facade': 'north', 'handles': [ent.dxf.handle]}],
              'drop': {note.dxf.handle: 'annotation'}}
    mapping = tmp_path / 'map.json'
    mapping.write_text(json.dumps(config), encoding='utf-8')
    return source, mapping, config, doc


def test_facade_schedule(tmp_path):
    source, mapping, config, doc = fixture(tmp_path)
    tool = load()
    result = tool.extract(source, mapping)
    row = result['openings'][0]
    assert {k: row[k] for k in ('id', 'kind', 'facade', 'left_m', 'right_m', 'sill_m', 'head_m', 'width_m', 'height_m')} == {
        'id': 'W1', 'kind': 'window', 'facade': 'north', 'left_m': 0, 'right_m': 1.2,
        'sill_m': 1.5, 'head_m': 3, 'width_m': 1.2, 'height_m': 1.5}
    assert len(result['entities']) == len(doc.modelspace()) == 2
    assert [r['status'] for r in result['entities']] == ['used', 'dropped']
    assert len(result['source']['sha256']) == len(result['mapping']['sha256']) == 64
    assert result['status'] == 'measured' and 'passed' not in result


@pytest.mark.parametrize('case', ['empty', 'partial', 'circle', 'bulge', 'elevation', 'extrusion',
                                 'zero', 'diagonal', 'unmapped', 'unknown_handle', 'unknown_kind',
                                 'unknown_facade', 'unknown_key', 'units', 'nan', 'inf', 'direction',
                                 'empty_openings', 'empty_facades', 'drop_reason', 'duplicate_json'])
def test_reject_invalid(tmp_path, case):
    source, mapping, config, doc = fixture(tmp_path)
    ent = list(doc.modelspace())[0]
    if case == 'empty':
        doc.modelspace().delete_all_entities()
    elif case == 'partial':
        ent.closed = False
    elif case == 'circle':
        circle = doc.modelspace().add_circle((0, 0), 100)
        config['openings'][0]['handles'] = [circle.dxf.handle]
    elif case == 'bulge':
        ent.set_points([(1000, 2000, 1), (2200, 2000, 0), (2200, 3500, 0), (1000, 3500, 0)], format='xyb')
    elif case == 'elevation':
        ent.dxf.elevation = 2
    elif case == 'extrusion':
        ent.dxf.extrusion = (0, 0, -1)
    elif case == 'zero':
        ent.set_points([(0, 0), (0, 0), (0, 10), (0, 20)])
    elif case == 'diagonal':
        ent.set_points([(0, 0), (10, 1), (10, 10), (0, 10)])
    elif case == 'unmapped':
        config['drop'] = {}
    elif case == 'unknown_handle':
        config['openings'][0]['handles'] = ['FFFF']
    elif case == 'unknown_kind':
        config['openings'][0]['kind'] = 'guess'
    elif case == 'unknown_facade':
        config['openings'][0]['facade'] = 'absent'
    elif case == 'unknown_key':
        config['openings'][0]['default'] = True
    elif case == 'units':
        doc.units = 0
    elif case in ('nan', 'inf'):
        config['facades']['north']['datum_m'] = float(case)
    elif case == 'direction':
        config['facades']['north']['direction'] = 0
    elif case == 'empty_openings':
        config['openings'] = []
    elif case == 'empty_facades':
        config['facades'] = {}
    elif case == 'drop_reason':
        config['drop'] = {next(iter(config['drop'])): ''}
    doc.saveas(source)
    raw = json.dumps(config)
    if case == 'duplicate_json':
        raw = raw.replace('"kind": "window"', '"kind": "door", "kind": "window"')
    mapping.write_text(raw, encoding='utf-8')
    before = {p: p.read_bytes() for p in tmp_path.iterdir()}
    output = tmp_path / 'output.json'
    assert load().main([str(source), str(mapping), str(output)]) == 2
    assert not output.exists()
    assert before == {p: p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize('duplicate', ['handle', 'id', 'drop', 'geometry'])
def test_duplicate_and_reset(tmp_path, duplicate):
    import copy
    source, mapping, config, doc = fixture(tmp_path)
    good = json.dumps(config)
    if duplicate == 'handle':
        config['openings'][0]['handles'] *= 2
    elif duplicate == 'id':
        config['openings'].append(copy.deepcopy(config['openings'][0]))
    elif duplicate == 'drop':
        config['drop'][config['openings'][0]['handles'][0]] = 'conflicting drop'
    else:
        ent = doc.modelspace().add_lwpolyline([(1000, 2000), (2200, 2000), (2200, 3500), (1000, 3500)], close=True)
        config['openings'][0]['handles'].append(ent.dxf.handle)
        doc.saveas(source)
    mapping.write_text(json.dumps(config), encoding='utf-8')
    with pytest.raises(ValueError, match='duplicate'):
        load().extract(source, mapping)
    if duplicate == 'geometry':
        config = json.loads(good)
        config['drop'][ent.dxf.handle] = 'explicit duplicate outline'
        good = json.dumps(config)
    mapping.write_text(good, encoding='utf-8')
    assert len(load().extract(source, mapping)['openings']) == 1


@pytest.mark.parametrize('alias', ['source', 'mapping', 'relative', 'hardlink', 'existing'])
def test_cli_paths(tmp_path, alias):
    import os
    source, mapping, config, doc = fixture(tmp_path)
    output = tmp_path / 'out.json'
    if alias == 'source':
        output = source
    elif alias == 'mapping':
        output = mapping
    elif alias == 'relative':
        output = tmp_path / '.' / 'facade.dxf'
    elif alias == 'hardlink':
        os.link(source, output)
    else:
        output.write_text('stale success', encoding='utf-8')
    before = {p: p.read_bytes() for p in tmp_path.iterdir()}
    assert load().main([str(source), str(mapping), str(output)]) == 2
    assert before == {p: p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize('target', ['source', 'mapping'])
def test_source_changes(tmp_path, monkeypatch, target):
    source, mapping, config, doc = fixture(tmp_path)
    tool = load()
    original = tool.ezdxf.readfile
    def changed(path):
        result = original(path)
        (source if target == 'source' else mapping).write_bytes(b'changed')
        return result
    monkeypatch.setattr(tool.ezdxf, 'readfile', changed)
    output = tmp_path / 'out.json'
    assert tool.main([str(source), str(mapping), str(output)]) == 2
    assert not output.exists()


def test_cli_fresh_process(tmp_path):
    import subprocess
    import sys
    source, mapping, config, doc = fixture(tmp_path)
    output = tmp_path / 'schedule.json'
    partial = tmp_path / 'schedule.json.partial'
    partial.write_bytes(b'foreign partial')
    command = [sys.executable, str(TOOL), str(source), str(mapping), str(output)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert 'architectural review required' in result.stdout
    assert json.loads(output.read_text(encoding='utf-8'))['openings'][0]['width_m'] == 1.2
    before = output.read_bytes()
    assert subprocess.run(command, capture_output=True).returncode == 2
    assert output.read_bytes() == before and partial.read_bytes() == b'foreign partial'


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf')])
def test_nonfinite_dxf_coordinates(tmp_path, monkeypatch, value):
    source, mapping, config, doc = fixture(tmp_path)
    ent = list(doc.modelspace())[0]
    ent.set_points([(value, 2000), (2200, 2000), (2200, 3500), (1000, 3500)])
    tool = load()
    monkeypatch.setattr(tool.ezdxf, 'readfile', lambda path: doc)
    with pytest.raises(ValueError, match='finite'):
        tool.extract(source, mapping)


def test_multiple_facades_door_and_split_edges(tmp_path):
    source, mapping, config, doc = fixture(tmp_path)
    config['facades']['south'] = {'origin_mm': [10000, 1000], 'direction': -1, 'datum_m': 0}
    points = [(10000, 1000), (10500, 1000), (11000, 1000), (11000, 3100), (10000, 3100), (10000, 1000)]
    handles = [doc.modelspace().add_line(a, b).dxf.handle for a, b in zip(points, points[1:])]
    config['openings'].append({'id': 'D1', 'kind': 'door', 'facade': 'south', 'handles': handles})
    doc.saveas(source)
    mapping.write_text(json.dumps(config), encoding='utf-8')
    result = load().extract(source, mapping)
    row = result['openings'][1]
    assert (row['left_m'], row['right_m'], row['sill_m'], row['head_m']) == (-1, 0, 0, 2.1)
    assert row['kind'] == 'door'
    assert len(result['entities']) == len(doc.modelspace())


def test_racing_output_writer(tmp_path, monkeypatch):
    source, mapping, config, doc = fixture(tmp_path)
    tool = load()
    original = tool.extract
    output = tmp_path / 'out.json'
    def race(*args):
        result = original(*args)
        output.write_bytes(b'foreign writer')
        return result
    monkeypatch.setattr(tool, 'extract', race)
    assert tool.main([str(source), str(mapping), str(output)]) == 2
    assert output.read_bytes() == b'foreign writer'


def test_generated_rectangles(tmp_path):
    import random
    rng = random.Random(1312)
    source, mapping, config, doc = fixture(tmp_path)
    ent = list(doc.modelspace())[0]
    for _ in range(40):
        x, y, w, h = [rng.randint(1, 10000) for _ in range(4)]
        # Use independent LINE outline groups and reversed horizontal orientation too.
        doc.modelspace().delete_all_entities()
        edges = [((x, y), (x+w, y)), ((x+w, y), (x+w, y+h)),
                 ((x+w, y+h), (x, y+h)), ((x, y+h), (x, y))]
        handles = [doc.modelspace().add_line(a, b).dxf.handle for a, b in edges]
        config['drop'] = {}
        config['openings'][0]['handles'] = handles
        config['facades']['north']['direction'] = rng.choice((-1, 1))
        doc.saveas(source)
        mapping.write_text(json.dumps(config), encoding='utf-8')
        row = load().extract(source, mapping)['openings'][0]
        assert row['width_m'] == pytest.approx(w / 1000)
        assert row['height_m'] == pytest.approx(h / 1000)
        assert row['sill_m'] == pytest.approx((y - 1000) / 1000 + .5)
        assert row['head_m'] == pytest.approx((y+h - 1000) / 1000 + .5)
