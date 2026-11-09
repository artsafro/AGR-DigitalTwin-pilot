"""new-case: PNG decode isolation/continuation at public wrapper and validate seams.

All generated image fixtures are synthetic, not project/delivery acceptance.
"""
import hashlib
import json
import struct
import zipfile
import zlib

import pytest

import twinqa.png as png
import validate_package as vp
from twinqa.profiles import load_profiles

PROFILES = load_profiles()
ROUTES = [('npm', 128), ('Diffuse', 256), ('ERM', 256), ('Normal', 256),
          ('ERM', 2048), ('Normal', 2048)]


def chunk(kind, body=b''):
    return (struct.pack('>I', len(body)) + kind + body
            + struct.pack('>I', zlib.crc32(kind + body)))


def image(side, alpha=False, variant=None):
    header = png.SIGNATURE + chunk(
        b'IHDR', struct.pack('>IIBBBBB', side, side, 8, 6 if alpha else 2, 0, 0, 0))
    if variant == 'ihdr-only':
        return header
    if variant == 'no-idat':
        return header + chunk(b'IEND')
    pixel = b'\x12\x34\x56\x80' if alpha else b'\x12\x34\x56'
    data = b'not-zlib' if variant == 'bad-zlib' else zlib.compress((b'\x00' + pixel * side) * side)
    return header + chunk(b'IDAT', data) + chunk(b'IEND')


def filename(route, slot=1):
    return 'probe.png' if route == 'npm' else f'T_Probe_{route}_{slot}.1001.png'


def run(route, mapping):
    if route == 'npm':
        return png.npm_texture_findings(mapping, PROFILES.npm), {}
    return png.vpm_texture_findings(mapping, PROFILES.vpm, 'T_Probe')


def assert_unreadable(findings, name):
    matches = [f for f in findings if f.name == 'PNG readable']
    assert len(matches) == 1
    f = matches[0]
    assert (f.status, f.evidence) == ('fail', name)
    assert f.observed.startswith(name + ': ')
    assert not any(f.status == 'pass' for f in findings)


@pytest.mark.parametrize('route,side', ROUTES)
@pytest.mark.parametrize('variant', ['ihdr-only', 'no-idat', 'bad-zlib'])
def test_decode_isolation(route, side, variant):
    data = image(side, variant=variant)
    name = filename(route)
    snapshot = hashlib.sha256(data).hexdigest()
    assert png.png_facts(name, data).width == side  # parser acceptance is intentionally unchanged
    findings, sets = run(route, {name: data})
    assert_unreadable(findings, name)
    assert all(route not in maps for maps in sets.values())
    assert hashlib.sha256(data).hexdigest() == snapshot


@pytest.mark.parametrize('route', ['npm', 'Diffuse', 'ERM', 'Normal'])
def test_mixed_members(route):
    if route == 'npm':
        mapping = {'a_broken.png': image(128, variant='bad-zlib'),
                   'z_good.png': image(256, alpha=True)}
        broken, sibling = 'a_broken.png', 'z_good.png'
    else:
        mapping = {filename(role, slot): image(256, alpha=(slot == 2 and role == 'ERM'))
                   for slot in (1, 2) for role in ('Diffuse', 'ERM', 'Normal')}
        broken, sibling = filename(route), filename('ERM', 2)
        mapping[broken] = image(256, variant='bad-zlib')
    before = dict(mapping)
    findings, sets = run(route, mapping)
    assert_unreadable(findings, broken)
    assert any(f.status == 'fail' and f.evidence == sibling
               and f.name == ('no alpha' if route == 'npm' else 'no alpha in ERM/Normal')
               for f in findings)
    if route != 'npm':
        assert set(sets[(2, 1001)]) == {'Diffuse', 'ERM', 'Normal'}
        assert route not in sets[(1, 1001)]
        assert any(f.name == 'map set' and route in f.observed for f in findings)
    assert run(route, dict(reversed(list(mapping.items())))) == (findings, sets)
    assert mapping == before


@pytest.mark.parametrize('route,side', ROUTES)
@pytest.mark.parametrize('error', [MemoryError, RuntimeError, TypeError])
def test_unexpected_exceptions(monkeypatch, route, side, error):
    def fail(data):
        raise error('pixel boundary')
    monkeypatch.setattr(png, 'pixels', fail)
    with pytest.raises(error, match='pixel boundary'):
        run(route, {filename(route): image(side)})


@pytest.mark.parametrize('route,side', [('npm', 256), ('npm', 2048), ('Diffuse', 2048)])
@pytest.mark.parametrize('variant', ['ihdr-only', 'no-idat', 'bad-zlib'])
def test_header_only(route, side, variant):
    findings, sets = run(route, {filename(route): image(side, variant=variant)})
    assert not any(f.name == 'PNG readable' for f in findings)
    if route == 'npm':
        assert [f.status for f in findings] == ['pass']
    else:
        assert sets[(1, 1001)]['Diffuse'].width == side
        assert [f.name for f in findings] == ['map set']


@pytest.mark.parametrize('route', ['npm', 'Diffuse', 'ERM', 'Normal'])
@pytest.mark.parametrize('data', [b'', b'not a PNG', png.SIGNATURE + b'\x00\x00\x00\x0dIHDR'])
def test_invalid_headers(route, data):
    findings, sets = run(route, {filename(route): data})
    assert_unreadable(findings, filename(route))
    assert sets == {}


@pytest.mark.parametrize('kind', ['npm', 'vpm'])
@pytest.mark.parametrize('rep', [1, 2])
def test_outer_reports(tmp_path, kind, rep):
    if kind == 'npm':
        path = tmp_path / 'probe.png'
        path.write_bytes(image(128, variant='bad-zlib'))
    else:
        path = tmp_path / 'SM_Probe.zip'
        with zipfile.ZipFile(path, 'w') as archive:
            for slot in (1, 2):
                for role in ('Diffuse', 'ERM', 'Normal'):
                    archive.writestr(filename(role, slot), image(
                        256, alpha=(slot == 2 and role == 'ERM'),
                        variant='bad-zlib' if slot == 1 and role == 'Diffuse' else None))
    before = path.read_bytes()
    report = vp.validate(path, kind, PROFILES)
    assert report.passed is False
    assert report.exit_code != 0
    json.dumps(report.to_dict(), allow_nan=False)
    stage = next(s for s in report.stages if s.id == ('V006' if kind == 'npm' else 'V007'))
    assert stage.status == 'fail'
    assert_unreadable(stage.findings, 'probe.png' if kind == 'npm' else filename('Diffuse'))
    assert path.read_bytes() == before


def test_metadata_survives_decode_failure():
    name = filename('ERM')
    findings, sets = run('ERM', {name: image(256, alpha=True, variant='bad-zlib')})
    assert [f.name for f in findings] == ['no alpha in ERM/Normal', 'PNG readable', 'map set']
    assert sets == {(1, 1001): {}}


def test_heuristic_oserror_propagates(monkeypatch):
    def fail(rgb):
        raise OSError('heuristic, not pixel decode')
    monkeypatch.setattr(png, 'normal_convention', fail)
    with pytest.raises(OSError, match='heuristic, not pixel decode'):
        run('Normal', {filename('Normal'): image(2048)})
