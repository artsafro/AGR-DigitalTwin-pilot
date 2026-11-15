"""new-case: shared openings source readers and fail-closed manual CLI (#1511).

All generated fixtures are synthetic, not a real building.
"""
import copy
import importlib.util
import json
import os
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

from adapters.max.agr_tools import openings_core as core

ROOT = Path(__file__).resolve().parents[1]


def test_revit_reader_keeps_latin_c_glass_without_mutating_input(tmp_path):
    path = ROOT / 'tests/jobs/test_kpp1_extract_openings.py'
    spec = importlib.util.spec_from_file_location('kpp1_fixture_1511', path)
    assert spec is not None and spec.loader is not None
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    src, cen = fixture._write(tmp_path, [fixture._glass('Cтеклопакет', 0)])
    side = json.loads((src / 'curtain.export.json').read_text(encoding='utf-8'))
    groups = {g: json.loads((cen / (g + '.objects.json')).read_text(encoding='utf-8'))
              for g in ('curtain', 'openings')}
    original = copy.deepcopy((side, groups))
    result, dropped = core.read_revit_openings(side, groups, profile='KPP1')
    assert result['S']['surrounds'][0]['bays'][0]['glass'] == [[1.2, 1.6, 0.2, 1.5]]
    assert dropped == []
    assert (side, groups) == original


@pytest.mark.parametrize('bad', [None, {}, {'types': []}, {'types': [{'instances': []}]}])
def test_revit_empty_or_partial_is_an_error(bad):
    with pytest.raises(ValueError):
        core.read_revit_openings(bad, {'curtain': [], 'openings': []}, profile='KPP1')


@pytest.mark.parametrize('number', [float('nan'), float('inf'), -float('inf')])
def test_revit_nonfinite_bbox_is_an_error(number):
    side = {'types': [{'instances': [{'elementId': 1, 'type': 'X', 'boundingBox': {
        'min': dict(x=number, y=0, z=0), 'max': dict(x=2, y=2, z=2)}}]}]}
    with pytest.raises(ValueError, match='finite'):
        core.read_revit_openings(side, {'curtain': [], 'openings': []}, profile='KPP1')


def test_fresh_agr_pdf_is_explicitly_unimplemented(tmp_path):
    result = subprocess.run([sys.executable, '-m', 'dt_ai.cli.agr', 'openings',
                             '--pdf', str(tmp_path / 'source.pdf'), '--output', str(tmp_path / 'out.json')],
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert 'PDF input: not implemented, needs an agreed sample' in result.stderr
    assert not (tmp_path / 'out.json').exists()


def drawing_payload():
    return {'status': 'measured', 'units': 'm',
            'openings': [{'id': 'W1', 'kind': 'window', 'facade': 'south', 'source_handles': ['A'],
                          'left_m': 1, 'right_m': 2, 'sill_m': 0, 'head_m': 2,
                          'width_m': 1, 'height_m': 2}],
            'source': {'path': 'synthetic.dxf', 'sha256': 'a' * 64},
            'mapping': {'path': 'synthetic-map.json', 'sha256': 'b' * 64},
            'entities': [{'handle': 'A', 'type': 'LWPOLYLINE', 'layer': '0', 'status': 'used', 'opening': 'W1'}]}


def test_drawing_reader_preserves_schedule_and_binding():
    payload = drawing_payload()
    frames = {'south': {'origin_mm': [0, 0], 'direction': 1, 'datum_m': 0}}
    result = core.read_drawing_openings(payload, frames)
    assert result['format'] == 'agr-openings/1'
    assert result['data'] == payload
    assert result['facade_binding'] == frames
    assert result['units'] == 'm' and result['status'] == 'measured'
    result['data']['openings'].clear()
    assert payload['openings']


@pytest.mark.parametrize('field,value', [('units', 'mm'), ('status', 'pass'), ('status', 'not_run'),
                                         ('openings', []), ('entities', []), ('extra', 'unmapped')])
def test_drawing_reader_rejects_partial_or_failing_schedule(field, value):
    payload = drawing_payload()
    payload[field] = value
    with pytest.raises(ValueError):
        core.read_drawing_openings(payload, {'south': {'origin_mm': [0, 0], 'direction': 1, 'datum_m': 0}})


def dxf_fixture(tmp_path):
    import ezdxf
    doc = ezdxf.new()
    doc.units = 4
    entity = doc.modelspace().add_lwpolyline([(0, 0), (1000, 0), (1000, 2000), (0, 2000)], close=True)
    source = tmp_path / 'synthetic.dxf'
    doc.saveas(source)
    mapping = tmp_path / 'mapping.json'
    mapping.write_text(json.dumps({'facades': {'south': {'origin_mm': [0, 0], 'direction': 1, 'datum_m': 0}},
                                   'openings': [{'id': 'W1', 'kind': 'window', 'facade': 'south',
                                                 'handles': [entity.dxf.handle]}], 'drop': {}}), encoding='utf-8')
    return source, mapping


def cli(*args):
    return subprocess.run([sys.executable, '-m', 'dt_ai.cli.agr', 'openings', *map(str, args)],
                          capture_output=True, text=True, encoding='utf-8')


def test_fresh_dxf_command_measures_and_refuses_stale_output(tmp_path):
    source, mapping = dxf_fixture(tmp_path)
    output = tmp_path / 'out.json'
    args = ['--dxf', source, '--mapping', mapping, '--output', output]
    result = cli(*args)
    assert result.returncode == 0, result.stderr
    doc = json.loads(output.read_text(encoding='utf-8'))
    assert doc['data']['openings'][0]['width_m'] == 1
    assert doc['data']['openings'][0]['height_m'] == 2
    before = {p: p.read_bytes() for p in (source, mapping, output)}
    assert cli(*args).returncode != 0
    assert all(p.read_bytes() == data for p, data in before.items())


@pytest.mark.parametrize('alias', ['exact', 'relative', 'case', 'hardlink'])
def test_cli_output_alias_refused_before_writes(tmp_path, alias, monkeypatch):
    source, mapping = dxf_fixture(tmp_path)
    output = source
    if alias == 'relative':
        output = source.parent / '.' / source.name
    elif alias == 'case':
        if os.name != 'nt':
            pytest.skip('Windows case-insensitive spelling')
        output = Path(str(source).upper())
    elif alias == 'hardlink':
        output = tmp_path / 'hardlink.json'
        os.link(mapping, output)
    before = {p: p.read_bytes() for p in tmp_path.iterdir()}
    result = cli('--dxf', source, '--mapping', mapping, '--output', output)
    assert result.returncode != 0
    assert set(tmp_path.iterdir()) == set(before)
    assert all(p.read_bytes() == data for p, data in before.items())


@pytest.mark.parametrize('value', [0, -1, float('nan'), float('inf')])
def test_drawing_degenerate_and_nonfinite_dimensions_fail(value):
    payload = drawing_payload()
    payload['openings'][0]['width_m'] = value
    with pytest.raises(ValueError):
        core.read_drawing_openings(payload, {'south': {'origin_mm': [0, 0], 'direction': 1, 'datum_m': 0}})


def test_duplicate_json_key_is_not_last_entry_wins(tmp_path):
    source, mapping = dxf_fixture(tmp_path)
    mapping.write_text('{"facades":{},"facades":{}}', encoding='utf-8')
    result = cli('--dxf', source, '--mapping', mapping, '--output', tmp_path / 'out.json')
    assert result.returncode != 0 and 'duplicate JSON key' in result.stderr
    assert not (tmp_path / 'out.json').exists()


def test_input_mutation_is_not_published(tmp_path, monkeypatch):
    from tools.source import openings
    source, mapping = dxf_fixture(tmp_path)
    original = core.read_drawing_openings
    def mutate(*args):
        result = original(*args)
        mapping.write_bytes(mapping.read_bytes() + b' ')
        return result
    monkeypatch.setattr(core, 'read_drawing_openings', mutate)
    assert openings.main(['--dxf', str(source), '--mapping', str(mapping), '--output', str(tmp_path / 'out.json')]) != 0
    assert not (tmp_path / 'out.json').exists()


def test_foreign_partial_and_racing_writer_are_preserved(tmp_path, monkeypatch):
    from tools.source import openings
    source, mapping = dxf_fixture(tmp_path)
    output = tmp_path / 'out.json'
    partial = tmp_path / 'out.json.partial'
    partial.write_bytes(b'foreign')
    original = core.read_drawing_openings
    def race(*args):
        result = original(*args)
        output.write_bytes(b'competing writer')
        return result
    monkeypatch.setattr(core, 'read_drawing_openings', race)
    assert openings.main(['--dxf', str(source), '--mapping', str(mapping), '--output', str(output)]) != 0
    assert output.read_bytes() == b'competing writer'
    assert partial.read_bytes() == b'foreign'


def test_kpp1_shim_refuses_output_hardlinked_to_input(tmp_path):
    # Use the same synthetic source as the legacy compatibility tests.
    fixture = __import__('runpy').run_path(str(ROOT / 'tests/jobs/test_kpp1_extract_openings.py'))
    src, cen = fixture['_write'](tmp_path, [fixture['_glass']('Cтеклопакет', 0)])
    original = (cen / 'curtain.objects.json').read_bytes()
    os.link(cen / 'curtain.objects.json', cen / 'openings_spec.json')
    with pytest.raises((ValueError, OSError)):
        runpy.run_path(str(ROOT / 'jobs/KPP1/scripts/extract_openings.py'))['main'](src, cen)
    assert (cen / 'curtain.objects.json').read_bytes() == original
    assert not (cen / 'openings_dropped.json').exists()


def test_fresh_revit_command_matches_legacy_fields(tmp_path):
    fixture = runpy.run_path(str(ROOT / 'tests/jobs/test_kpp1_extract_openings.py'))
    src, cen = fixture['_write'](tmp_path, [fixture['_glass']('Cтеклопакет', 0)])
    side_path = src / 'curtain.export.json'
    side = json.loads(side_path.read_text(encoding='utf-8'))
    side['types'][0]['instances'].append({'elementId': 99, 'type': 'unlocated reference'})
    side_path.write_text(json.dumps(side), encoding='utf-8')
    output = tmp_path / 'out.json'
    result = cli('--revit', src / 'curtain.export.json', '--census', cen, '--profile', 'KPP1', '--output', output)
    assert result.returncode == 0, result.stderr
    document = json.loads(output.read_text(encoding='utf-8'))
    runpy.run_path(str(ROOT / 'jobs/KPP1/scripts/extract_openings.py'))['main'](src, cen)
    assert document['data']['spec'] == json.loads((cen / 'openings_spec.json').read_text(encoding='utf-8'))
    assert document['data']['dropped'] == json.loads((cen / 'openings_dropped.json').read_text(encoding='utf-8'))
    assert len(document['source_refs']) == 3
    assert document['facade_binding']['profile'] == 'KPP1'
    assert document['data']['unlocated_references'] == [
        {'elementId': 99, 'type': 'unlocated reference', 'reason': 'no boundingBox'}]


@pytest.mark.parametrize('case', ['duplicate_id', 'duplicate_handle', 'missing_entity', 'unknown_facade', 'fail_entity', 'unmapped_used'])
def test_drawing_accounting_is_fail_closed(case):
    payload = drawing_payload()
    if case == 'duplicate_id':
        payload['openings'].append(copy.deepcopy(payload['openings'][0]))
    elif case == 'duplicate_handle':
        payload['entities'].append(copy.deepcopy(payload['entities'][0]))
    elif case == 'missing_entity':
        payload['entities'][0]['handle'] = 'B'
    elif case == 'unknown_facade':
        payload['openings'][0]['facade'] = 'missing'
    elif case == 'unmapped_used':
        payload['entities'].append({'handle': 'B', 'type': 'LINE', 'layer': '0', 'status': 'used', 'opening': None})
    else:
        payload['entities'][0]['status'] = 'fail'
    with pytest.raises(ValueError):
        core.read_drawing_openings(payload, {'south': {'origin_mm': [0, 0], 'direction': 1, 'datum_m': 0}})


@pytest.mark.parametrize('exitcode,receipt_status', [(7, None), (0, 'fail'), (0, 'pass')])
def test_dwg_chain_delegates_converter_and_existing_extractor(tmp_path, monkeypatch, exitcode, receipt_status):
    """Synthetic converter only: no AutoCAD process, no native DWG claim."""
    from types import SimpleNamespace
    from tools.source import openings
    source, mapping = dxf_fixture(tmp_path)
    dwg = tmp_path / 'synthetic.dwg'
    dwg.write_bytes(b'synthetic converter fixture, not a real DWG')
    workdir = tmp_path / 'conversion'
    calls = []
    def convert(command, **kwargs):
        calls.append(command)
        if receipt_status is not None:
            Path(command[3]).write_bytes(source.read_bytes())
            Path(command[4]).write_text(json.dumps({'status': receipt_status}), encoding='utf-8')
        return SimpleNamespace(returncode=exitcode)
    monkeypatch.setattr(openings.subprocess, 'run', convert)
    output = tmp_path / 'out.json'
    status = openings.main(['--dwg', str(dwg), '--mapping', str(mapping), '--workdir', str(workdir), '--output', str(output)])
    assert len(calls) == 1 and calls[0][1].endswith('dwg_to_dxf.py')
    if exitcode != 0 or receipt_status != 'pass':
        assert status != 0 and not output.exists()
    else:
        assert status == 0
        document = json.loads(output.read_text(encoding='utf-8'))
        assert document['data']['openings'][0]['width_m'] == 1
        assert document['conversion']['status'] == 'pass'
        assert len(document['source_refs']) == 3
