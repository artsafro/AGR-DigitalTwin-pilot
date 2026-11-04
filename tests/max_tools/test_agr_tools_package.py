"""new-case: AGR Tools 0.8 branch D (#908): qa.package, export.zip (and the package grammar), plain pytest, no pymxs.

Every named lab defect (docs/experiments/qa.package.md, export.zip.md) has a regression test that is RED on a small
model of the source behaviour (`geoagr_*` below: the behaviour measured in lab L04, not GeoAGR code, #853) and GREEN
on package_core. The models run as strict xfail, so a model that stops failing is itself an error.
The validator runs for real (tools/qa/validate_package.py in this interpreter, as the button runs it via AGR_PYTHON).
"""
import hashlib
import importlib.util
import json
import os
import struct
import sys
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'
sys.path.insert(0, str(ROOT / 'tests' / 'qa'))
from test_validator import geojson as good_geojson  # noqa: E402

sys.path.pop(0)


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ec = _load(PKG / 'edit_core.py', 'agr_tools_edit_core_pkg')
pc = _load(PKG / 'package_core.py', 'agr_tools_package_core_t')
FBX = b'Kaydara FBX Binary  \x00\x1a\x00' + struct.pack('<I', 7400) + b'\x00' * 64
PY, RUN = sys.executable, pc.subprocess_runner


def _png(colour):
    b = BytesIO()
    Image.new('RGB', (256, 256), colour).save(b, 'PNG')
    return b.getvalue()


MAPS = {'Diffuse': (120, 110, 100), 'ERM': (0, 170, 0), 'Normal': (128, 128, 255)}


def acceptance_folder(tmp_path):
    """export.zip.md minimal acceptance: NPM (2 parts + Ground), VPM OKS (fbx, _Light, geojson, 3 PNG), VPM Ground
    (same) and decoys SM_X_0011.*, 0123_Other_01.fbx, notes.txt."""
    d = tmp_path / 'delivery'
    d.mkdir()
    files = {'0123_X_01.fbx': FBX, '0123_X_02.fbx': FBX, '0123_X_Ground.fbx': FBX,
             'SM_X.fbx': FBX, 'SM_X_Light.fbx': FBX, 'SM_X.geojson': good_geojson(),
             'SM_X_Ground.fbx': FBX, 'SM_X_Ground_Light.fbx': FBX, 'SM_X_Ground.geojson': good_geojson(),
             'SM_X_0011.fbx': FBX, 'SM_X_0011.geojson': good_geojson(), 'T_X_0011_Diffuse_1.1001.png': _png((1, 2, 3)),
             '0123_Other_01.fbx': FBX, 'notes.txt': b'decoy'}
    for m, c in MAPS.items():
        files['T_X_{}_1.1001.png'.format(m)] = _png(c)
        files['T_X_Ground_{}_1.1001.png'.format(m)] = _png(c)
    for n, data in files.items():
        (d / n).write_bytes(data)
    return d


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _validate(target):
    return pc.validate(target, RUN, PY, ROOT, profile=None, scene=False)


def _stage(table, sid):
    return next(s for s in table['stages'] if s['id'] == sid)


# ---- source behaviour models (lab L04 measurements; no GeoAGR code) ------------------------------------------
def geoagr_members(names, stem):
    """GeoAGR Archivate All picks VPM members by substring of the set stem (GeoAGR.ms:66292-66305)."""
    return sorted(n for n in names if stem in n and not n.endswith('_Light.fbx'))  # _Light never matches (66307)


def geoagr_npm_archive(names):
    """All NPM FBX of the folder in one archive named after the last _Ground FBX (GeoAGR.ms:66246-66253)."""
    fbx = sorted(n for n in names if n[:4].isdigit() and n.endswith('.fbx'))
    ground = [n for n in fbx if '_Ground' in n]
    return ground[-1].replace('_Ground.fbx', '.zip'), fbx


def geoagr_ground_vpm_ok(size):
    return size < 500 * pc.MIB  # GeoAGR.ms:66340: 500 MiB for Ground too, and exactly 500 MiB fails


def core_members(names, stem):
    plan = pc.classify_folder(names)['vpm'][stem]
    return sorted([plan['fbx']] + ([plan['light']] if plan['light'] else []) + [plan['geojson']] + plan['png'])


def core_npm_archive(names):
    cls = pc.classify_folder(names)
    addr = pc.delivery_address(cls)
    (code,) = [c for c, a in cls['npm'] if a == addr]
    parts = cls['npm'][(code, addr)]
    return '{}_{}.zip'.format(code, addr), sorted(parts.values())


def core_ground_vpm_ok(size):
    return pc.size_status(size, pc.LIMITS['vpm_ground']) == 'pass'


NAMES = sorted(['0123_X_01.fbx', '0123_X_02.fbx', '0123_X_Ground.fbx', '0123_Other_01.fbx', 'SM_X_001.fbx',
                'SM_X_001_Light.fbx', 'SM_X_001.geojson', 'SM_X_0011.fbx', 'SM_X_0011.geojson',
                'T_X_001_Diffuse_1.1001.png', 'T_X_0011_Diffuse_1.1001.png', 'T_X_001_ERM_1.1001.png',
                'T_X_001_Normal_1.1001.png'])
MODEL = pytest.param('geoagr', marks=pytest.mark.xfail(strict=True, reason='source behaviour (lab L04)'))


@pytest.mark.parametrize('impl', [MODEL, 'core'])
def test_members_by_exact_stem_not_substring(impl):
    """export.zip defect 3: SM_X_001 also took SM_X_0011.fbx and its textures."""
    got = (geoagr_members if impl == 'geoagr' else core_members)(NAMES, 'SM_X_001' if impl == 'geoagr' else 'X_001')
    assert not any('0011' in n for n in got)


@pytest.mark.parametrize('impl', [MODEL, 'core'])
def test_vpm_oks_archive_keeps_its_light_fbx(impl):
    """export.zip defect 2: the extra-FBX filter never matched, so `_Light` was missing from the OKS archive."""
    got = (geoagr_members if impl == 'geoagr' else core_members)(NAMES, 'SM_X_001' if impl == 'geoagr' else 'X_001')
    assert 'SM_X_001_Light.fbx' in got


@pytest.mark.parametrize('impl', [MODEL, 'core'])
def test_npm_archive_per_address_not_every_fbx_of_the_folder(impl):
    """export.zip defect 4: all NPM FBX of the folder went into one archive (0123_Other_01.fbx too)."""
    name, members = (geoagr_npm_archive if impl == 'geoagr' else core_npm_archive)(NAMES)
    assert name == '0123_X.zip' and '0123_Other_01.fbx' not in members


@pytest.mark.parametrize('impl', [MODEL, 'core'])
def test_vpm_ground_limit_is_1_gib_and_inclusive(impl):
    """export.zip defect 5: the Ground VPM archive was limited to 500 MiB and exactly 500 MiB failed."""
    ok = geoagr_ground_vpm_ok if impl == 'geoagr' else core_ground_vpm_ok
    assert ok(500 * pc.MIB) and ok(1024 * pc.MIB) and not ok(1024 * pc.MIB + 1)


def test_limits_match_the_standards_in_binary_units():
    import yaml
    npm = yaml.safe_load((ROOT / 'standards/NPM_STANDARD.yaml').read_text(encoding='utf-8'))['archive']
    vpm = yaml.safe_load((ROOT / 'standards/VPM_STANDARD.yaml').read_text(encoding='utf-8'))['archive']
    assert pc.LIMITS == {'npm': npm['max_bytes'], 'vpm_oks': vpm['oks_max_bytes'], 'vpm_ground': vpm['ground_max_bytes']}
    for limit in pc.LIMITS.values():
        assert [pc.size_status(n, limit) for n in (limit - 1, limit, limit + 1)] == ['pass', 'pass', 'fail']


def test_writer_is_in_process_without_an_external_archiver():
    """export.zip defect 1: the bundled 7-Zip without its codec library created nothing and its exit code was unread."""
    src = (PKG / 'package_core.py').read_text(encoding='utf-8')
    assert 'import zipfile' in src and '7z' not in src.replace('7-Zip', '') and 'Popen' not in src


# ---- export.zip acceptance (export.zip.md "Minimal acceptance test") -----------------------------------------
def test_export_zip_acceptance(tmp_path):
    d = acceptance_folder(tmp_path)
    before = {p.name: _sha(p) for p in d.iterdir()}
    p = pc.zip_preview(ec, d)
    assert p['plan']['done'] == ['0123_X.zip', 'SM_X.zip', 'SM_X_Ground.zip'] and p['status'] == 'pass'
    assert sorted(os.listdir(d)) == sorted(before)  # preview writes nothing
    skipped = {s['item']: s['reason'] for s in p['plan']['skipped']}
    assert set(skipped) == {'SM_X_0011.fbx', 'SM_X_0011.geojson', 'T_X_0011_Diffuse_1.1001.png',
                            '0123_Other_01.fbx', 'notes.txt'}
    assert '3 digits' in skipped['SM_X_0011.fbx'] and 'not the delivery address X' in skipped['0123_Other_01.fbx']

    ec.check_preview('export.zip', p)
    r = pc.zip_apply(ec, p, _validate)
    assert r['status'] == 'pass', r['objects']
    assert r['plan']['done'] == ['0123_X.zip', 'SM_X.zip', 'SM_X_Ground.zip']
    new = sorted(set(os.listdir(d)) - set(before))
    assert new == ['0123_X.zip', 'SM_X.zip', 'SM_X_Ground.zip']  # exactly 3, no .partial left
    with zipfile.ZipFile(d / 'SM_X.zip') as z:
        names = z.namelist()
    assert 'SM_X_Light.fbx' in names and not any('0011' in n for n in names)
    with zipfile.ZipFile(d / 'SM_X_Ground.zip') as z:
        assert sorted(z.namelist()) == sorted(['SM_X_Ground.fbx', 'SM_X_Ground_Light.fbx', 'SM_X_Ground.geojson'] +
                                              ['T_X_Ground_{}_1.1001.png'.format(m) for m in MAPS])
    with zipfile.ZipFile(d / '0123_X.zip') as z:
        assert sorted(z.namelist()) == ['0123_X_01.fbx', '0123_X_02.fbx', '0123_X_Ground.fbx']
    assert {n: _sha(d / n) for n in before} == before  # decoys and sources untouched
    for table in r['plan']['reports']:
        assert _stage(table, 'V001')['status'] == 'pass', table
        assert _stage(table, 'V012')['status'] != 'fail', table  # VPM OKS name is review (conflict #20)

    # a second run refuses to overwrite: nothing to do, the existing archives are named
    p2 = pc.zip_preview(ec, d)
    assert p2['plan']['done'] == [] and p2['status'] == 'fail'
    assert all('refusing to overwrite' in s['reason'] for s in p2['plan']['skipped'] if s['item'].endswith('.zip')
               and s['item'] in ('0123_X.zip', 'SM_X.zip', 'SM_X_Ground.zip'))
    stamp = {n: _sha(d / n) for n in new}
    r2 = pc.zip_apply(ec, p2, _validate)
    assert r2['plan']['done'] == [] and {n: _sha(d / n) for n in new} == stamp


def test_stale_preview_writes_nothing(tmp_path):
    d = acceptance_folder(tmp_path)
    p = pc.zip_preview(ec, d)
    (d / 'SM_X_Light.fbx').write_bytes(FBX + b'\x01')
    with pytest.raises(ec.StalePreview):
        pc.zip_apply(ec, p, _validate)
    assert not list(d.glob('*.zip')) and not list(d.glob('*.partial'))


def test_over_limit_archives_are_flagged_and_not_written(tmp_path):
    """500 MiB + 1 B OKS and 1 GiB + 1 B Ground: the limits are scaled down here, the comparison is the same."""
    d = acceptance_folder(tmp_path)
    limits = {'vpm_oks': 200, 'vpm_ground': 300}
    p = pc.zip_preview(ec, d, limits=limits)
    r = pc.zip_apply(ec, p, _validate, limits=limits)
    assert r['plan']['done'] == ['0123_X.zip'] and r['status'] == 'fail'
    flagged = {o['name']: o['findings'][0]['code'] for o in r['objects'] if o['findings']}
    assert flagged == {'SM_X.zip': 'size', 'SM_X_Ground.zip': 'size'}
    assert sorted(x.name for x in d.glob('*.zip')) == ['0123_X.zip'] and not list(d.glob('*.partial'))


def test_mixed_addresses_and_codes_are_refused(tmp_path):
    d = tmp_path / 'mixed'
    d.mkdir()
    for n in ('0123_X_01.fbx', '0123_X_Ground.fbx', '0123_Y_01.fbx', '0123_Y_Ground.fbx'):
        (d / n).write_bytes(FBX)
    with pytest.raises(ValueError, match='mixed addresses'):
        pc.zip_preview(ec, d)
    assert pc.zip_preview(ec, d, address='Y')['plan']['done'] == ['0123_Y.zip']
    (d / '0124_X_Ground.fbx').write_bytes(FBX)
    p = pc.zip_preview(ec, d, address='X')
    assert p['plan']['done'] == [] and any('mixed territory codes' in s['reason'] for s in p['plan']['skipped'])


def test_npm_parts_need_ground_and_no_gaps(tmp_path):
    d = tmp_path / 'gaps'
    d.mkdir()
    for n in ('0123_X_01.fbx', '0123_X_03.fbx', '0123_X_Ground.fbx', '0123_X__Ground.fbx'):
        (d / n).write_bytes(FBX)
    p = pc.zip_preview(ec, d)
    (obj,) = p['objects']
    assert 'without gaps' in obj['findings'][0]['detail'] and p['plan']['done'] == []
    assert any(s['item'] == '0123_X__Ground.fbx' for s in p['plan']['skipped'])  # A101 double underscore


def test_address_with_underscores_and_digits(tmp_path):
    d = tmp_path / 'nansena'
    d.mkdir()
    for n in ('0313_ProezdNansena_ZU_8_01.fbx', '0313_ProezdNansena_ZU_8_Ground.fbx'):
        (d / n).write_bytes(FBX)
    p = pc.zip_preview(ec, d)
    assert p['plan']['address'] == 'ProezdNansena_ZU_8' and p['plan']['done'] == ['0313_ProezdNansena_ZU_8.zip']


# ---- qa.package ----------------------------------------------------------------------------------------------
def _npm_zip(folder, name, members):
    path = folder / name
    with zipfile.ZipFile(path, 'w') as z:
        for n, data in members:
            z.writestr(n, data)
    return path


def test_qa_package_default_scene_and_stage_table(tmp_path):
    argv = pc.validator_argv(PY, ROOT, tmp_path / '0127_X.zip')
    assert argv[-2:] == ['--json', '--scene'] and '--profile' not in argv
    assert pc.validator_argv(PY, ROOT, 'a.zip', 'npm', scene=False)[-2:] == ['--profile', 'npm']


def test_qa_package_stray_png_report(tmp_path):
    """qa.package acceptance: 0127_X.zip + stray PNG without --profile -> NPM, V001 'foreign files: preview.png';
    exit code and the V001-V017 stage table in the report."""
    z = _npm_zip(tmp_path, '0127_X.zip', [('0127_X_01.fbx', FBX), ('0127_X_Ground.fbx', FBX),
                                          ('preview.png', _png((1, 1, 1)))])
    r = pc.qa_package(ec, z, RUN, PY, ROOT, scene=False)
    (table,) = r['plan']['reports']
    assert table['profile'] == 'npm' and table['exit_code'] == 1 == r['plan']['exit_code']
    assert [s['id'] for s in table['stages']][0] == 'V001' and len(table['stages']) >= 10
    assert any('foreign files: preview.png' in f for f in _stage(table, 'V001')['non_pass'])
    (obj,) = r['objects']
    assert obj['name'] == '0127_X.zip' and 'V001' in [f['code'] for f in obj['findings']] and r['status'] == 'fail'
    assert r['plan']['mode'] == 'preview' and ec.check_preview('qa.package', r)


def test_qa_package_folder_checks_every_zip(tmp_path):
    _npm_zip(tmp_path, '0123_X.zip', [('0123_X_01.fbx', FBX), ('0123_X_Ground.fbx', FBX)])
    _npm_zip(tmp_path, '0124_X.zip', [('0124_X_01.fbx', FBX)])
    r = pc.qa_package(ec, tmp_path, RUN, PY, ROOT, scene=False)
    assert [o['name'] for o in r['objects']] == ['0123_X.zip', '0124_X.zip']
    assert [t['exit_code'] for t in r['plan']['reports']] == [2, 1] and r['plan']['exit_code'] == 1
    assert r['objects'][0]['findings'] == [] and r['objects'][1]['findings']
    with pytest.raises(ValueError, match='no ZIP'):
        (tmp_path / 'empty').mkdir()
        pc.qa_package(ec, tmp_path / 'empty', RUN, PY, ROOT)


def test_validator_errors_are_named_not_a_pass(tmp_path):
    def broken(argv):
        return 0, 'not json'
    with pytest.raises(ValueError):
        pc.validate(tmp_path / 'a.zip', broken, PY, ROOT)

    def lying(argv):
        return 0, json.dumps({'stages': [], 'exit_code': 1})
    with pytest.raises(RuntimeError, match='exit'):
        pc.validate(tmp_path / 'a.zip', lying, PY, ROOT)
    with pytest.raises(RuntimeError, match='validator failed'):
        pc.subprocess_runner([PY, '-c', 'import sys; sys.exit(3)'])


# ---- through the dispatcher (runtime.edits_080, glue package_max) -------------------------------------------
def test_dispatcher_runs_the_package_glue(tmp_path, monkeypatch):
    rt = _load(PKG / 'runtime.py', 'agr_runtime_pkg')
    monkeypatch.setenv('AGR_PYTHON', PY)
    d = acceptance_folder(tmp_path)
    z = _npm_zip(tmp_path, '0123_X.zip', [('0123_X_01.fbx', FBX), ('0123_X_Ground.fbx', FBX)])
    q = rt.edits_080('qa.package', 'preview', options={'path': str(z), 'scene': False})
    assert q['tool'] == 'qa.package' and q['plan']['options']['scene'] is False
    p = rt.edits_080('export.zip', 'preview', options={'folder': str(d)})
    assert p['plan']['done'] == ['0123_X.zip', 'SM_X.zip', 'SM_X_Ground.zip']
    r = rt.edits_080('export.zip', 'apply', p)
    assert r['status'] == 'pass' and r['plan']['done'] == p['plan']['done']
    assert rt.parse_report(json.dumps(r)) == r
    with pytest.raises(ValueError, match='read-only'):
        rt.edits_080('qa.package', 'apply', q)
