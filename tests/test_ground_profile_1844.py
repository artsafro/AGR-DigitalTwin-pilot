"""#1844: the Ground FBX export record carries an explicit NPM/VPM profile; the NPM ZIP never binds a VPM record.

Synthetic fixtures only. The profile lives in the `<FBX>.export_meta.json` sidecar beside the FBX (with the FBX
SHA-256), not inside the FBX. The Blender tests run the real exporter headless and skip without Blender 5.1.
"""
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.max.agr_tools import export_meta as em  # noqa: E402

OKS, GROUND = '0000_Synthetic_01.fbx', '0000_Synthetic_Ground.fbx'
CMD = [sys.executable, '-m', 'dt_ai.cli.agr', 'package-npm']
BLENDER = Path('C:/Program Files/Blender Foundation/Blender 5.1/blender.exe')
EXPORTER = ROOT / 'tools/blender/ground_json_to_fbx.py'


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _outputs(tmp):
    return sorted(p.name for p in tmp.iterdir() if p.is_file())


def _run(pkg, *extra):
    return subprocess.run(CMD + [str(pkg), *extra], capture_output=True, text=True, cwd=ROOT)


# ---- exporter profile resolution (shared helper the Blender exporter calls) ---------------------------------
def _fbx(tmp, name=GROUND, data=b'synthetic Ground'):
    path = tmp / name
    path.write_bytes(data)
    return path


def _canonical(tmp, profile):
    meta = {'address': 'Synthetic', 'h_otn_model_max_z_m': 1.0, 'thumbnail': 'unknown'}
    if profile is not None:
        meta['profile'] = profile
    (tmp / 'export_meta.json').write_text(json.dumps(meta), encoding='utf-8')


@pytest.mark.parametrize('profile', ['npm', 'vpm'])
def test_explicit_profile_is_recorded_with_the_fbx_hash(tmp_path, profile):
    fbx = _fbx(tmp_path)
    chosen, why = em.resolve_export_profile(profile, fbx, legacy_default='vpm', source='synthetic mesh.json')
    meta = em.load_meta(em.record_export(fbx, source='synthetic mesh.json', address='Synthetic_Ground',
                                         profile=chosen, profile_provenance=why))
    assert meta['profile'] == profile
    assert 'explicit' in meta['provenance']['profile']
    assert meta['exported_sha256'] == {GROUND: _sha(b'synthetic Ground')}


@pytest.mark.parametrize('canonical', [None, 'unknown'])
def test_legacy_call_without_profile_keeps_vpm_and_says_so(tmp_path, canonical):
    if canonical is not None:
        _canonical(tmp_path, canonical)
    fbx = _fbx(tmp_path)
    chosen, why = em.resolve_export_profile(None, fbx, legacy_default='vpm', source='synthetic mesh.json')
    assert chosen == 'vpm' and 'legacy default' in why and 'explicit' not in why


@pytest.mark.parametrize('explicit,canonical', [('vpm', 'npm'), ('npm', 'vpm'), (None, 'npm')])
def test_profile_contradicting_the_package_record_is_refused(tmp_path, explicit, canonical):
    _canonical(tmp_path, canonical)
    fbx = _fbx(tmp_path)
    with pytest.raises(ValueError, match='profile') as err:
        em.resolve_export_profile(explicit, fbx, legacy_default='vpm', source='synthetic mesh.json')
    assert 'export_meta.json' in str(err.value) and canonical in str(err.value)
    assert _outputs(tmp_path) == sorted(['export_meta.json', GROUND])


@pytest.mark.parametrize('profile', ['npm', 'vpm'])
def test_profile_matching_the_package_record_is_accepted(tmp_path, profile):
    _canonical(tmp_path, profile)
    chosen, why = em.resolve_export_profile(profile, _fbx(tmp_path), legacy_default='vpm', source='s')
    assert chosen == profile and 'export_meta.json' in why


def test_invalid_package_record_is_refused_not_ignored(tmp_path):
    (tmp_path / 'export_meta.json').write_text('{"address": "Synthetic"}', encoding='utf-8')
    with pytest.raises(ValueError, match='export_meta'):
        em.resolve_export_profile('npm', _fbx(tmp_path), legacy_default='vpm', source='s')


@pytest.mark.parametrize('bad', ['unknown', 'NPM', '', 'ifc', None])
def test_unsupported_explicit_profile_is_refused(tmp_path, bad):
    if bad is None:
        with pytest.raises(ValueError, match='legacy_default'):
            em.resolve_export_profile(None, _fbx(tmp_path), legacy_default=None, source='s')
        return
    with pytest.raises(ValueError, match=repr(bad)):
        em.resolve_export_profile(bad, _fbx(tmp_path), legacy_default='vpm', source='s')


@pytest.mark.parametrize('argv,rest,profile', [
    (['a', 'b', 'C'], ['a', 'b', 'C'], None),
    (['a', 'b', 'C', '--profile', 'npm'], ['a', 'b', 'C'], 'npm'),
    (['--profile=vpm', 'a', 'b', 'C', 'MSK-77'], ['a', 'b', 'C', 'MSK-77'], 'vpm'),
])
def test_pop_profile_option(argv, rest, profile):
    assert em.pop_profile_option(argv) == (rest, profile)


@pytest.mark.parametrize('argv', [['a', '--profile'], ['--profile', 'npm', '--profile', 'npm'],
                                  ['--profile', 'unknown'], ['--profile='], ['--profile', 'Npm']])
def test_pop_profile_option_fails_closed(argv):
    with pytest.raises(ValueError, match='--profile'):
        em.pop_profile_option(argv)


# ---- NPM ZIP binding ----------------------------------------------------------------------------------------
def _pkg(tmp, ground_profile, *, oks_profile='npm', ground_data=b'synthetic Ground'):
    pkg = tmp / 'fbx'
    pkg.mkdir()
    (pkg / OKS).write_bytes(b'synthetic OKS')
    (pkg / GROUND).write_bytes(ground_data)
    em.record_export(pkg / OKS, source='synthetic max scene', top=3.5, profile=oks_profile)
    if ground_profile == 'absent':  # genuinely unprofiled legacy record (pre-profile exporter shape)
        meta = {'address': 'Synthetic_Ground', 'h_otn_model_max_z_m': 0.2, 'thumbnail': 'unknown',
                'exported_files': [GROUND], 'exported_sha256': {GROUND: _sha(ground_data)}}
        (pkg / (GROUND + '.export_meta.json')).write_text(json.dumps(meta), encoding='utf-8')
    else:
        em.record_export(pkg / GROUND, source='synthetic ground.json', top=0.2, address='Synthetic_Ground',
                         profile=ground_profile)
    return pkg


def test_vpm_ground_record_with_matching_hash_is_refused(tmp_path):
    pkg = _pkg(tmp_path, 'vpm')
    r = _run(pkg)
    assert r.returncode == 1, r.stdout
    assert GROUND in r.stderr and "profile 'vpm'" in r.stderr and 'not NPM binding evidence' in r.stderr
    assert _outputs(tmp_path) == []


@pytest.mark.parametrize('selected', ['canonical', 'sidecar'])
def test_vpm_ground_record_selected_as_address_sidecar_is_refused(tmp_path, selected):
    """The VPM Ground record is the address record package_npm selects (canonical, or the sidecar via --meta)."""
    pkg = tmp_path / 'fbx'
    pkg.mkdir()
    (pkg / OKS).write_bytes(b'synthetic OKS')
    (pkg / GROUND).write_bytes(b'synthetic Ground')
    em.record_export(pkg / OKS, source='synthetic max scene', top=3.5, profile='npm')
    meta = em.record_export(pkg / GROUND, source='synthetic ground.json', top=0.2, address='Synthetic', profile='vpm',
                            metadata_path=pkg / 'export_meta.json' if selected == 'canonical' else None)
    extra = () if selected == 'canonical' else ('--meta', str(meta))
    assert em.address_meta_path(pkg, *([str(meta)] if extra else [])) == meta
    r = _run(pkg, *extra)
    assert r.returncode == 1 and GROUND in r.stderr and 'not NPM binding evidence' in r.stderr, r.stderr
    assert _outputs(tmp_path) == []


def test_vpm_ground_diagnostic_zip_is_incomplete_not_promoted(tmp_path):
    pkg = _pkg(tmp_path, 'vpm')
    r = _run(pkg, '--allow-incomplete')
    assert r.returncode == 1, r.stderr
    report = json.loads((tmp_path / '0000_Synthetic.zip.delivery.json').read_text(encoding='utf-8'))
    assert report['passed'] is False and report['status'] == 'incomplete'
    assert any('not NPM binding evidence' in p and GROUND in p for p in report['problems'])
    rows = {m['name']: m['status'] for m in report['export_binding']['members']}
    assert rows == {OKS: 'match', GROUND: 'not_recorded'}
    assert report['export_binding']['excluded_records'] == [
        {'record': GROUND + '.export_meta.json', 'profile': 'vpm', 'files': [GROUND]}]
    with zipfile.ZipFile(tmp_path / '0000_Synthetic.zip') as z:  # diagnostics unchanged: members still packed
        assert sorted(z.namelist()) == [OKS, GROUND]


def test_vpm_record_claiming_a_member_beside_an_npm_record_is_refused(tmp_path):
    """Contradictory profiles for one archived FBX: refused, not resolved by picking the NPM record."""
    pkg = _pkg(tmp_path, 'npm')
    extra = em.load_meta(pkg / (GROUND + '.export_meta.json'))
    extra.update(profile='vpm')
    (pkg / 'SM_Synthetic_Ground.fbx.export_meta.json').write_text(json.dumps(extra), encoding='utf-8')
    r = _run(pkg)
    assert r.returncode == 1 and GROUND in r.stderr and 'not NPM binding evidence' in r.stderr, r.stderr


@pytest.mark.parametrize('ground_profile', ['npm', 'unknown', 'absent'])
def test_npm_and_legacy_unprofiled_ground_records_still_bind(tmp_path, ground_profile):
    pkg = _pkg(tmp_path, ground_profile)
    r = _run(pkg)
    assert r.returncode == 0, r.stderr
    report = json.loads((tmp_path / '0000_Synthetic.zip.delivery.json').read_text(encoding='utf-8'))
    assert report['problems'] == [] and report['status'] == 'packaged_not_validated' and report['passed'] is False
    assert {m['status'] for m in report['export_binding']['members']} == {'match'}
    assert report['export_binding'].get('excluded_records', []) == []


def test_npm_ground_record_with_changed_bytes_is_still_refused(tmp_path):
    pkg = _pkg(tmp_path, 'npm')
    (pkg / GROUND).write_bytes(b'edited after export')
    r = _run(pkg)
    assert r.returncode == 1 and GROUND in r.stderr and 'SHA-256' in r.stderr


def test_random_profile_mixes_bind_only_with_npm_or_unprofiled(tmp_path):
    """Probe: for every OKS/Ground profile pair the ZIP binds iff neither record declares another profile."""
    import itertools
    choices = ['npm', 'vpm', 'unknown', 'absent']
    for i, (oks, ground) in enumerate(itertools.product(['npm', 'vpm', 'unknown'], choices)):
        case = tmp_path / str(i)
        case.mkdir()
        pkg = _pkg(case, ground, oks_profile=oks)
        r = _run(pkg, '--meta', str(pkg / (OKS + '.export_meta.json')))
        ok = oks != 'vpm' and ground != 'vpm'
        assert (r.returncode == 0) is ok, (oks, ground, r.stderr)
        if not ok:
            assert 'not NPM binding evidence' in r.stderr and _outputs(case) == []


# ---- the real Blender exporter -------------------------------------------------------------------------------
MESH = dict(verts=[[10, 20, 169.65], [12, 20, 171.05], [10, 22, 170.0]], faces=[[0, 1, 2]],
            slots=['Tile'], mat=[0], level=[0], uv=[[[0, 0], [1, 0], [0, 1]]])


def _build(tmp, *extra):
    if not BLENDER.exists():
        pytest.skip('Blender 5.1 required')
    src = tmp / 'mesh.json'
    if not src.exists():
        src.write_text(json.dumps(MESH), encoding='utf-8')
    out = tmp / GROUND
    run = subprocess.run([str(BLENDER), '--background', '--factory-startup', '--threads', '1', '--python-exit-code',
                          '1', '--python', str(EXPORTER), '--', 'build', str(src), str(out), 'Synthetic', *extra],
                         capture_output=True, text=True)
    return run, out


@pytest.mark.parametrize('profile', ['npm', 'vpm'])
def test_blender_exporter_records_the_explicit_profile(tmp_path, profile):
    run, out = _build(tmp_path, 'SYNTHETIC_LOCAL', '--profile', profile)
    assert run.returncode == 0, run.stdout[-2000:] + run.stderr[-2000:]
    meta = em.load_meta(Path(str(out) + '.export_meta.json'))
    assert meta['profile'] == profile and 'explicit' in meta['provenance']['profile']
    assert meta['exported_sha256'] == {GROUND: _sha(out.read_bytes())}


def test_blender_exporter_legacy_call_records_vpm_as_legacy_default(tmp_path):
    run, out = _build(tmp_path, 'SYNTHETIC_LOCAL')
    assert run.returncode == 0, run.stdout[-2000:] + run.stderr[-2000:]
    meta = em.load_meta(Path(str(out) + '.export_meta.json'))
    assert meta['profile'] == 'vpm' and 'legacy default' in meta['provenance']['profile']


def test_blender_exporter_refuses_profile_contradicting_package_record(tmp_path):
    _canonical(tmp_path, 'npm')
    run, out = _build(tmp_path, '--profile', 'vpm')
    assert run.returncode != 0 and "'npm'" in run.stderr + run.stdout
    assert _outputs(tmp_path) == ['export_meta.json', 'mesh.json']
