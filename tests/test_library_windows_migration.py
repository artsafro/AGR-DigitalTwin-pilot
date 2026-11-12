"""new-case: reproducible windows-library migration preserves #246 unconfirmed sash evidence."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_rebuild_applies_sashes_after_census_without_confirming(tmp_path):
    target = tmp_path/'types.json'
    cmd = [sys.executable, str(ROOT/'tools/library/build_window_types.py'),
           '--base', 'library/windows/window_types.json',
           '--census-source', 'library/windows/sources/elv-tc-vpm-census-v001.json',
           '--sashes', 'library/windows/sources/win-typical-max-sashes-v001.json', '--output', str(target)]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    old = json.loads((ROOT/'library/windows/window_types.json').read_text(encoding='utf-8'))
    new = json.loads(target.read_text(encoding='utf-8'))
    assert [t['id'] for t in new['types']] == [t['id'] for t in old['types']]
    for a, b in zip(old['types'], new['types']):
        assert b['unconfirmed'] == a['unconfirmed'], a['id']
        assert b['sashes'] is b['handing'] is None
        assert b['status'] == a['status']


def migrate():
    spec = importlib.util.spec_from_file_location('migrate_windows_test', ROOT/'tools/library/migrate_windows.py')
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_sash_rebuild_refuses_output_alias_without_writes(tmp_path):
    import os
    base = tmp_path/'base.json'
    base.write_bytes((ROOT/'library/windows/window_types.json').read_bytes())
    alias = tmp_path/'alias.json'
    os.link(base, alias)
    before = base.read_bytes()
    result = subprocess.run([sys.executable, str(ROOT/'tools/library/build_window_types.py'),
                             '--base', str(base), '--sashes', 'library/windows/sources/win-typical-max-sashes-v001.json',
                             '--output', str(alias)], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode != 0 and 'alias' in result.stderr
    assert base.read_bytes() == alias.read_bytes() == before


def test_migration_accounts_for_all_types_and_profiles():
    plan = migrate().prepare(ROOT)
    assert len(plan['assets']) == 67
    ready = [a for a in plan['assets'] if a['status'] == 'ready']
    blocked = [a for a in plan['assets'] if a['status'] == 'quarantine']
    assert len(ready) == 59 and len(blocked) == 8
    assert {a['id'] for a in blocked} == {'D04', 'CW_021', 'CW_022', 'WT-02', 'ELV-16', 'ELV-17', 'D03', 'D03_W'}
    assert all('2 mm' in ' '.join(a['reason']) for a in blocked if a['id'] in ('D03', 'D03_W'))
    assert all(a['reason'] and not a['meshes'] for a in blocked)
    assert all(isinstance(a['name'], str) and a['name'] for a in plan['assets'])
    original = json.loads((ROOT/'library/windows/window_types.json').read_text(encoding='utf-8'))['types']
    assert [a['source']['original_name'] for a in plan['assets']] == [t['name'] for t in original]
    assert any(a['source']['original_name'] is None for a in blocked)
    for a in ready:
        assert set(a['meshes']) == {'npm', 'vpm'}
        assert len(a['meshes']['npm']['faces']) == 1
        assert a['meshes']['vpm']['status'] == 'ok'
    wt = next(a for a in ready if a['id'] == 'WT-01')
    assert wt['source']['unconfirmed']['sashes']['candidate'] is not None


def test_committed_catalogue_is_complete_and_source_bound():
    import hashlib
    spec = importlib.util.spec_from_file_location('migration_catalogue_check', ROOT/'tools/library/check_library.py')
    assert spec and spec.loader
    check = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check)
    doc = json.loads((ROOT/'library/windows/catalogue.json').read_text(encoding='utf-8'))
    check.validate_catalogue(doc)
    original = json.loads((ROOT/'library/windows/window_types.json').read_text(encoding='utf-8'))['types']
    assert [a['id'] for a in doc['assets']] == [t['id'] for t in original]
    for a, t in zip(doc['assets'], original):
        assert a['source']['unconfirmed'] == t['unconfirmed']
        assert a['confirmation'] == t['status']
    for source in doc['inputs']:
        assert hashlib.sha256((ROOT/source['path']).read_bytes()).hexdigest() == source['sha256'], source['path']


def test_migration_rejects_unknown_role_instead_of_f100_fallback():
    doc = json.loads((ROOT/'library/windows/window_types.json').read_text(encoding='utf-8'))
    doc['types'][0]['role'] = 'mystery'
    with pytest.raises(ValueError, match='mystery'):
        migrate().prepare(ROOT, types_doc=doc)
