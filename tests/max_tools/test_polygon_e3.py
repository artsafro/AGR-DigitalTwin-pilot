"""new-case: polygon stations of branch E3 (#979): the fragment's expected rows hold for the same synthetic bytes
(test-polygon/stations/E3_build.py) through the same cores the live run presses (preview only)."""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'
POLY = ROOT / 'test-polygon'


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ec = _load(PKG / 'edit_core.py', 'agr_tools_edit_core_poly_e3')
pc = _load(PKG / 'package_core.py', 'agr_tools_package_core_poly_e3')
build = _load(POLY / 'stations' / 'E3_build.py', 'agr_polygon_E3_build_t')
FRAG = json.loads((POLY / 'stations' / 'E3.json').read_text(encoding='utf-8'))
ST = {s['button']: s for s in FRAG['stations']}


def _codes(report):
    return {o['name']: sorted({f['code'] for f in o['findings']}) for o in report['objects']}


def _expected(button):
    return {r['name']: r['codes'] for r in ST[button]['expected']}


def _folder(tmp_path, kind):
    d = tmp_path / kind
    build.write_files(str(d), build.delivery_files(kind))
    return d


def test_every_e3_station_has_a_pass_and_a_fail_row():
    assert set(ST) == {'export.zip', 'qa.package', 'export.ground_fbx', 'export.geojson_write'}
    for st in FRAG['stations']:
        kinds = {r['expect'] for r in st['expected']}
        assert {'pass', 'fail'} <= kinds, st['button']
        names = {o['name'] for o in st['objects']}
        assert {r['name'] for r in st['expected']} <= names, st['button']


def test_export_zip_station(tmp_path):
    rep = pc.zip_preview(ec, _folder(tmp_path, 'zip'))
    assert _codes(rep) == _expected('export.zip')


def test_qa_package_station(tmp_path):
    rep = pc.qa_package(ec, _folder(tmp_path, 'pkg'), pc.subprocess_runner, sys.executable, ROOT, scene=False)
    got = {o['name']: sorted({f['code'] for f in o['findings']}) for o in rep['objects']}
    assert got == _expected('qa.package'), rep['plan']['reports']


def test_ground_fbx_station():
    objs = {o['name']: o for o in ST['export.ground_fbx']['objects']}
    cls = {'std': 'Standardmaterial', 'ray': 'RaytraceMaterial'}
    facts = [{'handle': i, 'name': n, 'geometry': True, 'material': cls[o['mat']],
              'pivot_m': sum(v * v for v in o['pivot']) ** 0.5, 'hidden': False}
             for i, (n, o) in enumerate(sorted(objs.items()), 1)]
    plan = pc.ground_plan(facts, ST['export.ground_fbx']['options']['code'], None, 'C:/nowhere')
    rep = pc.ground_report(ec, 'preview', plan, facts, {'facts': facts})
    assert _codes(rep) == _expected('export.ground_fbx')


def test_geojson_write_station():
    opts = ST['export.geojson_write']['options']
    names = [o['name'] for o in ST['export.geojson_write']['objects']]
    pivot = {'status': 'pass', 'plan': {'pivot_value': [2500.0, 7000.0, 150.0], 'floor': 150.0}}
    glass = [{'name': 'M_GjX_MainGlass_1', 'diffuse': [180, 160, 140], 'opacity': 50.0}]
    plan = pc.geojson_plan(names, opts['properties'], build.JPEG_256, pivot, glass, 'C:/nowhere')
    assert sorted({c for c, _d in plan['findings']}) == _expected('export.geojson_write')['SM_GjX_Main']
    assert pc.preview_image(build.JPEG_256)[1] == []  # the embedded picture is a 256x256 JPG
