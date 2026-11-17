"""#1513: the committed AC08 nine-stage receipt and the native D221 two-glass readback stay internally consistent.

Pattern: new-case (receipt consistency of one native Max 2026 run; no Max is started here). The validator is fail-closed:
an empty / partial / mutated receipt (a stage claimed passed, a glass face outside 1001, one glass id, a glass texture,
a NaN UV, passed=true) must give problems, never an empty list.
"""
import copy
import json
import math
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / 'jobs' / 'TEC26-OKS' / 'AC08' / 'agr-stages-v001'
RECEIPT = DIR / 'receipt.json'
MANIFEST = DIR / 'DRIVE-SHA256SUMS.txt'
DRIVER = ROOT / 'tests' / 'max_tools' / 'run_ac08_stages_native.py'
SOURCE_SHA = '9cae468e714118c501dfffa77531aabecd88662c4e34d0be57274d446bb3e5fd'
OK_STATUS = {'done', 'findings', 'ambiguous', 'refused', 'error', 'skipped', 'not_implemented', 'harness_error', 'n/a'}


def _tile(key):
    return int(str(key).split(':')[1])


def _finite(xs):
    return isinstance(xs, list) and len(xs) == 2 and all(isinstance(x, (int, float)) and math.isfinite(x) for x in xs)


def check_receipt(r):
    """Problems of one receipt (empty list = consistent). Never raises on a malformed receipt."""
    p = []
    try:
        if r.get('passed') is not False:
            p.append('passed must be literally false (mandatory gates open)')
        if 'REAL AC08' not in str(r.get('model')) or r.get('source_fbx_sha256') != SOURCE_SHA:
            p.append('model is not the pinned real AC08 source')
        st = r.get('stages') or []
        if [s.get('id') for s in st] != list(range(10)):
            p.append('stages must be 0..9 in order, got {}'.format([s.get('id') for s in st]))
        for s in st:
            if s.get('status') not in OK_STATUS:
                p.append('stage {} status {!r} is not a recorded button outcome'.format(s.get('id'), s.get('status')))
            if not s.get('buttons'):
                p.append('stage {} has no button receipt'.format(s.get('id')))
            elif s.get('big') not in [b.get('tool') for b in s['buttons']]:
                p.append('stage {} big button {} not pressed'.format(s.get('id'), s.get('big')))
        if r.get('harness_errors'):
            p.append('harness errors present')
        blocked = any(s.get('status') in ('refused', 'error', 'harness_error') for s in st)
        for key, dv in (r.get('deliver') or {}).items():
            if blocked and (dv.get('steps') or {}).get('export.zip') == 'done':
                p.append('deliver {} wrote a package although an earlier stage failed'.format(key))
        d = r.get('d221') or {}
        gids = d.get('glass_ids') or []
        if len(set(gids)) < 2:
            p.append('D221 needs at least two glass material ids')
        if 'SYNTHETIC' not in str(d.get('fixture')):
            p.append('D221 fixture must be labelled SYNTHETIC')
        g = d.get('glass_copy') or {}
        if sorted(int(k) for k in (g.get('mat_ids') or {})) != sorted(gids):
            p.append('glass copy ids {} != glass ids {}'.format(sorted(g.get('mat_ids') or {}), gids))
        tiles = g.get('matid_tile_faces') or {}
        if not tiles or any(_tile(k) != 1001 for k in tiles):
            p.append('glass faces outside UDIM 1001: {}'.format(tiles))
        if sum(tiles.values()) != g.get('faces_tri'):
            p.append('glass tile faces do not cover every glass face')
        table = g.get('agr_udim_table') or {}
        if sorted(int(k) for k in table) != sorted(gids) or set(table.values()) != {1001}:
            p.append('agr_udim_table of glass disagrees: {}'.format(table))
        if not (_finite(g.get('uv_u')) and _finite(g.get('uv_v'))) or not (
                0 <= g['uv_u'][0] and g['uv_u'][1] <= 1 and 0 <= g['uv_v'][0] and g['uv_v'][1] <= 1):
            p.append('glass UV bounds not finite inside 0..1: {} {}'.format(g.get('uv_u'), g.get('uv_v')))
        b = d.get('body_copy') or {}
        bt = {int(k): v for k, v in (b.get('agr_udim_table') or {}).items()}
        if not bt or [bt[k] for k in sorted(bt)] != list(range(1001, 1001 + len(bt))):
            p.append('body numbering is not dense by id: {}'.format(bt))
        if set(bt) & set(gids):
            p.append('glass id on the body copy')
        files = d.get('out_files')
        if not files or d.get('glass_maps') or any(re.search(r'T_.*Glass', f, re.I) for f in files):
            p.append('glass texture maps present or no file inventory: {}'.format(d.get('glass_maps')))
        rb = [n for n in d.get('readback') or [] if '_glass_' in str(n.get('name'))]
        if len(rb) != 1:
            p.append('independent FBX readback must contain exactly one glass node')
        else:
            n = rb[0]
            names = sorted((n.get('id_sub_names') or {}).values())
            if names != ['ID_{:03d}'.format(i) for i in sorted(gids)]:
                p.append('readback glass sub-materials {} do not name the glass ids'.format(names))
            if any(_tile(k) != 1001 for k in n.get('matid_tile_faces') or {'x:0': 0}):
                p.append('readback glass faces outside 1001')
            if n.get('faces_tri') != g.get('faces_tri') or n.get('scale') != [1.0, 1.0, 1.0]:
                p.append('readback glass topology/transform differs')
    except (TypeError, ValueError, AttributeError, KeyError, IndexError) as exc:
        p.append('malformed receipt: {}'.format(exc))
    return p


@pytest.fixture(scope='module')
def receipt():
    return json.loads(RECEIPT.read_text(encoding='utf-8'))


def test_receipt_is_consistent(receipt):
    assert check_receipt(receipt) == []


def test_stage6_refusal_is_kept_and_not_caused_by_the_material_decision(receipt):
    st6 = receipt['stages'][6]
    assert st6['status'] == 'refused'
    assert st6['buttons'][0]['preview_codes'] == {'seam': 1, 'texel': 1}
    diag = receipt['diagnostic_run']
    assert diag['label'].startswith('DIAGNOSTIC') and dict(diag['stages'])[6] == 'refused'
    assert receipt['final']['qa_package']['status'] == 'skipped'


def test_manifest_seals_the_retained_runs():
    lines = MANIFEST.read_text(encoding='utf-8').splitlines()
    names = {ln.split(' *', 1)[1] if ' *' in ln else ln.split('  ', 1)[1] for ln in lines}
    for need in ('./run-v004/summary.json', './run-v004/d221.json', './run-v004/readback.json',
                 './run-v004/table.md', './run-v003/summary.json', './AGR-Tools.mzp', './run_ac08_stages_native.py'):
        assert need in names, need
    assert all(re.fullmatch(r'[0-9a-f]{64}', ln.split(' ', 1)[0]) for ln in lines)


def test_driver_lives_outside_jobs_and_matches_sealed_copy():
    # D324 skeleton gate: no driver script under jobs/; the moved bytes stay the Drive-sealed ones.
    assert not list(DIR.glob('*.py'))
    sealed = {ln.split(' *', 1)[1]: ln.split(' ', 1)[0]
              for ln in MANIFEST.read_text(encoding='utf-8').splitlines() if ' *' in ln}
    import hashlib
    assert hashlib.sha256(DRIVER.read_bytes()).hexdigest() == sealed['./run_ac08_stages_native.py']


def test_driver_maps_ids_without_default():
    text = DRIVER.read_text(encoding='utf-8')
    assert "ID_MAP = {1: 999, 2: 11, 3: 2}" in text and 'unmapped source face id' in text
    lib = json.loads((ROOT / 'library' / 'materials' / 'materials_v002.json').read_text(encoding='utf-8'))
    assert 999 not in {m['library_id'] for m in lib['materials']}   # the sentinel can never resolve silently


MUTATIONS = {
    'empty': lambda r: r.clear(),
    'passed_true': lambda r: r.update(passed=True),
    'stage_missing': lambda r: r['stages'].pop(7),
    'stage_passed': lambda r: r['stages'][6].update(status='passed'),
    'glass_tile_1002': lambda r: r['d221']['glass_copy']['matid_tile_faces'].update({'48:1001': 0, '48:1002': 64}),
    'one_glass_id': lambda r: r['d221'].update(glass_ids=[39]),
    'glass_map': lambda r: r['d221']['out_files'].append('maps/T_Synth_1_MainGlass_1.1001.png'),
    'nan_uv': lambda r: r['d221']['glass_copy'].update(uv_u=[0.0, float('nan')]),
    'uv_at_threshold_out': lambda r: r['d221']['glass_copy'].update(uv_v=[0.0, 1.0000001]),
    'body_gap': lambda r: r['d221']['body_copy'].update(agr_udim_table={'2': 1001, '11': 1003}),
    'readback_unmapped': lambda r: r['d221']['readback'][1].update(id_sub_names={'1': 'ID_039', '2': 'Material #5'}),
    'synthetic_unlabelled': lambda r: r['d221'].update(fixture='AC08'),
    'other_source': lambda r: r.update(source_fbx_sha256='0' * 64),
    'package_after_refusal': lambda r: r['deliver']['A']['steps'].update({'export.zip': 'done'}),
}


@pytest.mark.parametrize('name', sorted(MUTATIONS))
def test_fail_closed_mutations(receipt, name):
    r = copy.deepcopy(receipt)
    MUTATIONS[name](r)
    assert check_receipt(r), name
