"""new-case: immutable copy-only KPP1 package publication, not delivery approval."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'jobs/KPP1/package-1278/build_package.py'


def load():
    assert SCRIPT.is_file(), 'copy-only package command missing'
    spec = importlib.util.spec_from_file_location('kpp1_package1278', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture(module, tmp_path):
    src = tmp_path / 'source'
    src.mkdir()
    # Synthetic bytes for copy/immutability tests only, not real delivery fixtures.
    blobs = {name: ('synthetic ' + name).encode() for name in module.EXPECTED}
    for name, blob in blobs.items():
        (src / name).write_bytes(blob)
    module.EXPECTED = {name: hashlib.sha256(blob).hexdigest() for name, blob in blobs.items()}
    return src, blobs


def snapshot(path):
    return {str(p.relative_to(path)): p.read_bytes() for p in path.rglob('*') if p.is_file()}


def test_copy_snapshot_reproducible_and_never_delivery_pass(tmp_path):
    m = load()
    src, blobs = fixture(m, tmp_path)
    before = snapshot(src)
    for tag in ('v001', 'v002'):
        out = tmp_path / tag
        m.build(src, out)
        assert {name: (out / name).read_bytes() for name in blobs} == blobs
        receipt = json.loads((out / 'assembly.json').read_text())
        assert receipt['passed'] is False
        assert receipt['source_sha256'] == m.EXPECTED
        assert receipt['zero_abs_m'] == 171.050
        assert 'entrance orientation not independently confirmed' in receipt['placement']
        assert set(snapshot(out)) == set(blobs) | {'assembly.json', 'SHA256SUMS.txt'}
    assert snapshot(tmp_path / 'v001') == snapshot(tmp_path / 'v002')
    assert snapshot(src) == before


@pytest.mark.parametrize('kind', ['empty', 'partial', 'wrong', 'unsupported', 'nan', 'inf', 'threshold'])
def test_bad_or_changed_source_fails_before_any_write(tmp_path, kind):
    m = load()
    src, blobs = fixture(m, tmp_path)
    first = src / next(iter(blobs))
    if kind == 'empty':
        for name in blobs:
            (src / name).unlink()
    elif kind == 'partial':
        first.unlink()
    else:
        first.write_bytes({'wrong': b'bad', 'unsupported': b'{}', 'nan': b'NaN',
                           'inf': b'Infinity', 'threshold': b''}[kind])
    before = snapshot(tmp_path)
    with pytest.raises(ValueError, match='input'):
        m.build(src, tmp_path / 'output')
    assert snapshot(tmp_path) == before
    assert not (tmp_path / 'output').exists()


@pytest.mark.parametrize('kind', ['same', 'relative', 'child', 'parent', 'existing', 'partial'])
def test_output_alias_or_existing_path_preserves_every_byte(tmp_path, kind):
    m = load()
    src, _ = fixture(m, tmp_path)
    out = {'same': src, 'relative': src / '..' / 'source', 'child': src / 'new',
           'parent': tmp_path, 'existing': tmp_path / 'existing',
           'partial': tmp_path / 'sentinel.partial'}[kind]
    if kind in ('existing', 'partial'):
        out.mkdir()
        (out / 'keep.partial').write_bytes(b'do not clobber')
    before = snapshot(tmp_path)
    with pytest.raises((ValueError, FileExistsError)):
        m.build(src, out)
    assert snapshot(tmp_path) == before


def test_state_changes_during_snapshot_fail_before_output(tmp_path, monkeypatch):
    m = load()
    src, blobs = fixture(m, tmp_path)
    original = Path.read_bytes
    first = src / next(iter(blobs))
    calls = 0

    def changed(path):
        nonlocal calls
        data = original(path)
        calls += 1
        if calls == len(blobs):
            first.write_bytes(b'concurrent writer')
        return data

    monkeypatch.setattr(Path, 'read_bytes', changed)
    with pytest.raises(ValueError, match='input'):
        m.build(src, tmp_path / 'out')
    assert not (tmp_path / 'out').exists()


def test_fresh_process_alias_refused_without_writes(tmp_path):
    m = load()
    src, _ = fixture(m, tmp_path)
    before = snapshot(src)
    result = subprocess.run([sys.executable, str(SCRIPT), str(src), str(src)], capture_output=True)
    assert result.returncode != 0
    assert b'alias' in result.stderr
    assert snapshot(src) == before


def test_production_pins_match_approved_site_manifest():
    m = load()
    manifest = (ROOT / 'jobs/KPP1/site-1255/evidence-SHA256SUMS.txt').read_text(encoding='utf-8')
    for name, digest in m.EXPECTED.items():
        assert f'{digest}  G:/Мой диск/AGR-evidence/1255-kpp1-msk77/site-v004/{name}' in manifest
    assert len(m.EXPECTED) == 3
