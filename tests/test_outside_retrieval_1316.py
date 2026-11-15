"""Regression for #1316 portable map routes and honest missing-byte states.

Pattern: n/a | new-case: version-bound A101 retrieval, approval and immutable v003 inputs.
"""
import hashlib
import os
import subprocess
import sys
from copy import deepcopy

import pytest
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_flora_map_routes_do_not_depend_on_deleted_workstation_cache():
    maps = json.loads((ROOT / 'library/flora/maps.json').read_text(encoding='utf-8'))
    assert maps
    for latin, record in maps.items():
        for slot in ('diffuse', 'opacity'):
            path = record[slot]
            assert path is None or path.startswith('G:/Мой диск/AGR-assets/flora/'), (latin, slot, path)
        if not record['diffuse'] or not record['opacity']:
            assert record['review_status'] == 'missing', latin
            assert record['evidence'], latin


def load(relative):
    return json.loads((ROOT / relative).read_text(encoding='utf-8'))


def identity_hash(identity):
    return hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def test_v003_snapshot_is_immutable():
    snapshot = ROOT / 'library/flora/maps-v003-snapshot.json'
    canonical = snapshot.read_text(encoding='utf-8').replace('\r\n', '\n').encode()
    assert hashlib.sha256(canonical).hexdigest() == 'a20972b8bd7e94240416d7c70035d107be71c4f58789159dbc5b069bdb67afd6'
    current = load('library/flora/maps.json')
    historical = load('library/flora/maps-v003-snapshot.json')
    assert current.keys() == historical.keys()
    for latin, old in historical.items():
        assert current[latin]['evidence'].endswith(old['evidence'])
        if old['diffuse'].startswith('C:/x/'):
            assert current[latin]['review_status'] == 'missing'
        else:
            assert current[latin] == old


def test_current_maps_cannot_silently_rebind_frozen_light_geometry():
    from dt_ai.materials.flora_catalogue import build
    with pytest.raises(ValueError, match='maps changed'):
        build(load('experiments/flora-library-audit/catalogue.json'),
              load('library/flora/species-curation.json'),
              load('library/flora/maps.json'), load('library/flora/catalogue.json'))


def test_tilia_approval_is_bound_to_exact_version():
    verdict = load('library/flora/visual-verdict-1316.json')
    release = load('library/flora/a101-native-v002.json')
    variant = next(v for v in release['variants'] if v['object'] == 'lipa_t1_h550_low')
    digest = identity_hash(variant['identity'])
    assert variant['version_sha256'] == verdict['version_sha256'] == digest
    assert verdict['identity'] == variant['identity']
    assert variant['review_status'] == verdict['status'] == 'approved'
    assert verdict['answer'] == 'Да, липа норм'
    assert verdict['answer_source']['in_reply_to'] == verdict['transport']['message_id'] == '4696'
    maps_version = load('library/flora/maps.json')['Tilia cordata']['versions'][digest]
    assert maps_version['review_status'] == 'approved'
    assert maps_version['object'] == variant['object']
    assert 'NOT Tilia_cordata_NPM/VPM' in maps_version['catalogue_geometry_compatibility']
    assert verdict['preview']['sha256'] == '8ceed9e2cca249b8565cff32f7ca3d7c89e5d855eb11e86d7d69f9bfbb295b64'


@pytest.mark.parametrize('field', ['scene_sha256', 'object', 'rgba_sha256', 'diffuse_sha256', 'opacity_sha256'])
def test_version_identity_mutations_do_not_reuse_approval(field):
    verdict = load('library/flora/visual-verdict-1316.json')
    changed = deepcopy(verdict['identity'])
    changed[field] += 'changed'
    assert identity_hash(changed) != verdict['version_sha256']


def test_unanswered_variants_are_not_approved():
    release = load('library/flora/a101-native-v002.json')
    assert len(release['variants']) == 4
    for variant in release['variants']:
        assert variant['version_sha256'] == identity_hash(variant['identity'])
        assert variant['catalogue_geometry_compatibility'] == 'not_established'
        if variant['object'].endswith('_high'):
            assert variant['review_status'] == 'pending'
            assert 'verdict' not in variant
        if variant['cultivar']:
            assert variant['cultivar'] == 'Royal Red'
        assert len(variant['files']) == 3
        assert len({f['path'] for f in variant['files']}) == 3
        assert all(f['bytes'] > 0 and len(f['sha256']) == 64 for f in variant['files'])


def test_three_asset_selection_has_complete_explicit_boundaries():
    selection = load('library/outside-retrieval-v001.json')
    assert len(selection['assets']) == 3
    assert [len(a['files']) for a in selection['assets']] == [1, 4, 1]
    paths = []
    for asset in selection['assets']:
        assert asset['boundary'] and asset['authority']
        for record in asset['files']:
            assert record['download_url'].startswith('https://drive.usercontent.google.com/download?id=')
            assert record['bytes'] > 0
            assert len(record['sha256']) == 64
            assert not record['path'].startswith(('/', 'C:', 'G:'))
            assert '..' not in Path(record['path']).parts
            paths.append(record['path'])
    assert len(paths) == len(set(paths)) == 6


def test_acer_request_is_separate_and_pending_without_an_answer():
    verdict = load('library/flora/visual-verdict-acer-1316.json')
    variant = next(v for v in load('library/flora/a101-native-v002.json')['variants']
                   if v['object'] == 'klen_t7_h550_low')
    assert verdict['version_sha256'] == variant['version_sha256'] == identity_hash(variant['identity'])
    assert verdict['status'] == variant['review_status'] == 'pending'
    assert verdict['answer'] is None and verdict['answer_source'] is None
    assert verdict['transport']['success'] is True
    assert verdict['transport']['message_id'] == '4701'
    assert 'Royal Red' in verdict['asset']
    assert 'not an approved substitution' in verdict['native_preview']['scope']


def _cold_snippet():
    text = (ROOT / 'docs/library/outside-retrieval-1316.md').read_text(encoding='utf-8')
    return text.split('```python', 1)[1].split('```', 1)[0]


def _run_cold_snippet(tmp_path, mode, prefix=''):
    env = os.environ.copy()
    env.pop('PYTHONOPTIMIZE', None)
    flags = ['-O'] if mode == 'flag' else []
    if mode == 'environment':
        env['PYTHONOPTIMIZE'] = '1'
    return subprocess.run([sys.executable, *flags, '-c', prefix + _cold_snippet()],
                          cwd=tmp_path, env=env, capture_output=True, text=True)


@pytest.mark.parametrize('mode', ['normal', 'flag', 'environment'])
@pytest.mark.parametrize('bad', ['empty', 'partial', 'unsupported', 'nan', 'infinity', 'zero', 'duplicate', 'traversal', 'absolute'])
def test_documented_download_refuses_invalid_manifest_before_writes(tmp_path, bad, mode):
    # Synthetic refusal probes: network is forbidden, never pretend these are real assets.
    manifest = deepcopy(load('library/outside-retrieval-v001.json'))
    first = manifest['assets'][0]['files'][0]
    if bad == 'empty':
        manifest['assets'] = []
    elif bad == 'partial':
        first.pop('sha256')
    elif bad == 'unsupported':
        manifest['schema'] = 'unsupported'
    elif bad in {'nan', 'infinity', 'zero'}:
        first['bytes'] = {'nan': float('nan'), 'infinity': float('inf'), 'zero': 0}[bad]
    elif bad == 'duplicate':
        manifest['assets'][2]['files'][0]['path'] = first['path'].upper()
    elif bad == 'traversal':
        first['path'] = '../input.png'
    else:
        first['path'] = 'C:/input.png'
    library = tmp_path / 'library'
    library.mkdir()
    input_path = library / 'outside-retrieval-v001.json'
    input_path.write_text(json.dumps(manifest), encoding='utf-8')
    before = input_path.read_bytes()
    prefix = "import urllib.request\ndef denied(*a, **kw): raise RuntimeError('NETWORK_MUST_NOT_RUN')\nurllib.request.urlopen = denied\n"
    result = _run_cold_snippet(tmp_path, mode, prefix)
    assert result.returncode != 0
    assert not (tmp_path / 'cold-download-v001').exists(), result.stderr
    assert 'NETWORK_MUST_NOT_RUN' not in result.stderr
    assert input_path.read_bytes() == before


@pytest.mark.parametrize('mode', ['normal', 'flag', 'environment'])
def test_documented_download_refuses_input_output_alias_without_changes(tmp_path, mode):
    library = tmp_path / 'library'
    library.mkdir()
    source = library / 'outside-retrieval-v001.json'
    source.write_text(json.dumps(load('library/outside-retrieval-v001.json')), encoding='utf-8')
    before = source.read_bytes()
    # A directory destination already naming an input file is rejected by mkdir,
    # before network or file writes. No destructive symlink/real library fixture.
    (tmp_path / 'cold-download-v001').hardlink_to(source)
    result = _run_cold_snippet(tmp_path, mode)
    assert result.returncode != 0
    assert source.read_bytes() == before
    assert (tmp_path / 'cold-download-v001').read_bytes() == before


def _synthetic_download(tmp_path, mismatch=None, position=0):
    """Exercise the published fence with synthetic bytes, never network assets."""
    manifest = load('library/outside-retrieval-v001.json')
    records = [r for a in manifest['assets'] for r in a['files']]
    payloads = {}
    for index, record in enumerate(records):
        data = bytes(range(index + 1))
        record['bytes'] = len(data)
        record['sha256'] = hashlib.sha256(data).hexdigest()
        payloads[record['download_url']] = data
    if mismatch:
        record = records[position]
        data = payloads[record['download_url']]
        payloads[record['download_url']] = (data + b'!') if mismatch == 'size' else bytes(b ^ 255 for b in data)
    library = tmp_path / 'library'
    library.mkdir()
    source = library / 'outside-retrieval-v001.json'
    source.write_text(json.dumps(manifest), encoding='utf-8')
    prefix = (
        'import io, urllib.request\n'
        f'payloads = {payloads!r}\n'
        'urllib.request.urlopen = lambda url, **kw: io.BytesIO(payloads[url])\n'
    )
    return records, source, prefix


@pytest.mark.parametrize('mode', ['normal', 'flag', 'environment'])
@pytest.mark.parametrize('mismatch', ['size', 'hash'])
@pytest.mark.parametrize('position', range(6))
def test_documented_download_refuses_corrupt_payload_before_file_write(tmp_path, mode, mismatch, position):
    records, source, prefix = _synthetic_download(tmp_path, mismatch, position)
    before = source.read_bytes()
    result = _run_cold_snippet(tmp_path, mode, prefix)
    assert result.returncode != 0
    assert records[position]['path'] in result.stderr
    root = tmp_path / 'cold-download-v001'
    # Earlier verified records may remain; the bad record and all later ones must not exist.
    written = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    assert written == {r['path'] for r in records[:position]}
    assert len(result.stdout.splitlines()) == position
    assert source.read_bytes() == before


@pytest.mark.parametrize('mode', ['normal', 'flag', 'environment'])
def test_documented_download_receipt_matches_written_bytes_and_refuses_reuse(tmp_path, mode):
    records, source, prefix = _synthetic_download(tmp_path)
    before = source.read_bytes()
    result = _run_cold_snippet(tmp_path, mode, prefix)
    assert result.returncode == 0, result.stderr
    root = tmp_path / 'cold-download-v001'
    expected = []
    for record in records:
        data = (root / record['path']).read_bytes()
        expected.append(f"{hashlib.sha256(data).hexdigest()} {len(data)} {record['path']}")
    assert result.stdout.splitlines() == expected
    snapshot = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
    # Repeat twice: stale receipts and pre-existing payloads cannot become a new success.
    for _ in range(2):
        refused = _run_cold_snippet(tmp_path, mode, prefix)
        assert refused.returncode != 0
        assert not refused.stdout
        assert {p: p.read_bytes() for p in root.rglob('*') if p.is_file()} == snapshot
    assert source.read_bytes() == before

