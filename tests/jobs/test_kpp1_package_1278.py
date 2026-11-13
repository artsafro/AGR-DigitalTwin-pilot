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
    # Synthetic containers for publication tests only, not real delivery fixtures.
    import io
    import zipfile
    geojson = (ROOT / 'jobs/KPP1/site-1255/SM_Kpp_1.geojson').read_bytes()
    blobs = {'SM_Kpp_1.geojson': geojson}
    for name, members in [('0000_Kpp_1.zip', {'0000_Kpp_1_01.fbx': synthetic_fbx()}),
                          ('SM_Kpp_1.zip', {'SM_Kpp_1.fbx': b'synthetic VPM unchanged',
                                            'SM_Kpp_1.geojson': geojson})]:
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as package:
            for member, data in members.items():
                package.writestr(zipfile.ZipInfo(member), data)
        blobs[name] = stream.getvalue()
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
        artifacts = {name: (out / name).read_bytes() for name in blobs}
        assert set(artifacts) == set(blobs)
        import io
        import zipfile
        assert json.loads(artifacts['SM_Kpp_1.geojson']) == json.loads(blobs['SM_Kpp_1.geojson'])
        for name in ('0000_Kpp_1.zip', 'SM_Kpp_1.zip'):
            with zipfile.ZipFile(io.BytesIO(blobs[name])) as old, zipfile.ZipFile(io.BytesIO(artifacts[name])) as new:
                assert new.namelist() == old.namelist()
                for member in old.namelist():
                    if member == '0000_Kpp_1_01.fbx':
                        assert b'M_Glass_01\x00\x01Material' in new.read(member)
                    elif member == 'SM_Kpp_1.geojson':
                        assert b'-9581.270' in new.read(member)
                    else:
                        assert old.read(member) == new.read(member)
        receipt = json.loads((out / 'assembly.json').read_text())
        assert receipt['passed'] is False
        for line in (out / 'SHA256SUMS.txt').read_text().splitlines():
            digest, name = line.split('  ', 1)
            assert hashlib.sha256((out / name).read_bytes()).hexdigest() == digest
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


def node(name, props, children=(), start=27):
    import struct
    def prop(value):
        if isinstance(value, bytes):
            return b'S' + struct.pack('<I', len(value)) + value
        return b'D' + struct.pack('<d', value)
    raw = b''.join(prop(p) for p in props)
    body = bytes([len(name)]) + name + raw
    pos = start + 12 + len(body)
    for child in children:
        blob = node(*child, start=pos)
        body += blob
        pos += len(blob)
    if children:
        body += bytes(13)
    return struct.pack('<III', start + 12 + len(body), len(props), len(raw)) + body


def synthetic_fbx():
    import struct
    return (b'Kaydara FBX Binary  \x00\x1a\x00' + struct.pack('<I', 7400)
            + node(b'Objects', [], [(b'Material', [b'M_Kpp_1_MainGlass_1\x00\x01Material'], [
                (b'Properties70', [], [(b'P', [b'Opacity', b'Number', b'', b'A', .3]),
                                       (b'P', [b'TransparencyFactor', b'Number', b'', b'A', .7])])]),
                (b'Geometry', [b'untouched vertices UV normals material indices'])]) + bytes(13))


def test_fix_npm_glass_changes_only_material_properties():
    m = load()
    data = synthetic_fbx()
    fixed = m.fix_npm_glass(data)
    assert b'M_Glass_01\x00\x01Material' in fixed
    assert b'M_Kpp_1_MainGlass_1' not in fixed
    assert b'untouched vertices UV normals material indices' in fixed
    import struct
    assert fixed.count(b'D' + struct.pack('<d', .5)) == 2
    assert data == synthetic_fbx()


@pytest.mark.parametrize('data', [b'', b'partial', b'NaN', b'Infinity', bytes(27)])
def test_glass_fix_rejects_unsupported_fbx(data):
    m = load()
    with pytest.raises(ValueError):
        m.fix_npm_glass(data)


def test_geojson_three_literal_decimals_without_changing_values():
    m = load()
    data = (ROOT / 'jobs/KPP1/site-1255/SM_Kpp_1.geojson').read_bytes()
    fixed = m.fix_geojson(data)
    assert b'-9581.270' in fixed
    assert json.loads(fixed) == json.loads(data)


@pytest.mark.parametrize('tile', range(1004, 1008))
@pytest.mark.parametrize('role', ['Diffuse', 'ERM', 'Normal'])
def test_flat_vpm_triplet_is_exact_colour_256_placeholder(tile, role):
    from PIL import Image
    import io
    m = load()
    image = Image.new('RGB', (2048, 2048), (128, 140, 255))
    stream = io.BytesIO()
    image.save(stream, format='PNG')
    out = Image.open(io.BytesIO(m.fix_placeholder_png(f'T_Kpp_1_{role}_1.{tile}.png', stream.getvalue())))
    assert out.size == (256, 256)
    assert out.mode == 'RGB'
    assert out.getextrema() == ((128, 128), (140, 140), (255, 255))


@pytest.mark.parametrize('kind', ['nonflat', 'alpha', 'wrong_tile', 'wrong_size', 'partial'])
def test_placeholder_repair_does_not_guess_or_destroy_texture_detail(kind):
    from PIL import Image
    import io
    m = load()
    image = Image.new('RGBA' if kind == 'alpha' else 'RGB', (512, 512) if kind == 'wrong_size' else (2048, 2048))
    if kind == 'nonflat':
        image.putpixel((10, 10), (1, 2, 3))
    stream = io.BytesIO()
    image.save(stream, format='PNG')
    data = stream.getvalue() if kind != 'partial' else b'partial PNG'
    name = 'T_Kpp_1_Diffuse_1.1003.png' if kind == 'wrong_tile' else 'T_Kpp_1_Diffuse_1.1004.png'
    with pytest.raises(ValueError):
        m.fix_placeholder_png(name, data)


def test_generated_opaque_geometry_payloads_are_preserved():
    import random
    m = load()
    rng = random.Random(1278)
    marker = b'untouched vertices UV normals material indices'
    for _ in range(64):
        payload = rng.randbytes(len(marker))
        source = synthetic_fbx().replace(marker, payload)
        result = m.fix_npm_glass(source)
        assert result.count(payload) == 1
        assert b'M_Glass_01\x00\x01Material' in result


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf'), -0.01, 1.01])
def test_nonfinite_or_out_of_range_material_never_passes(value):
    import struct
    m = load()
    source = synthetic_fbx().replace(b'D' + struct.pack('<d', .3), b'D' + struct.pack('<d', value))
    with pytest.raises(ValueError, match='glass property'):
        m.fix_npm_glass(source)


def test_output_hardlink_to_input_preserves_all_bytes(tmp_path):
    import os
    m = load()
    src, _ = fixture(m, tmp_path)
    alias = tmp_path / 'hardlink-output'
    os.link(src / 'SM_Kpp_1.zip', alias)
    before = snapshot(tmp_path)
    with pytest.raises(ValueError):
        m.build(src, alias)
    assert snapshot(tmp_path) == before


def test_latest_r1_v003_is_an_explicit_placement_source():
    spec = importlib.util.spec_from_file_location('latest_placement', ROOT / 'jobs/KPP1/site-1255/place_package.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert {
        'SM_Kpp_1.fbx': '76a7c97e523d6ac6475443a84f51e4b2ec588de3cbeb1b300d08adf07e97dc50',
        '0000_Kpp_1_01.fbx': 'ee3ac5994e298c476f63e0a40b7c977718c88127103d8078860cc07900d980b9',
        'SM_Kpp_1.zip': '350518df6d2e6e7b39c4348addc6fd88cc5bed118991440d1365be75406c6fb2',
    } in module.ADDITIONAL_APPROVED_R1_HASHES


def test_production_pins_match_approved_site_manifest():
    m = load()
    manifest = (ROOT / 'jobs/KPP1/site-1255/evidence-SHA256SUMS.txt').read_text(encoding='utf-8')
    for name, digest in m.EXPECTED.items():
        assert f'{digest}  G:/Мой диск/AGR-evidence/1255-kpp1-msk77/site-v004/{name}' in manifest
    assert len(m.EXPECTED) == 3
