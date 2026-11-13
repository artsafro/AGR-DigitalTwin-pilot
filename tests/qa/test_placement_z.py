"""new-case: Z bounds comparison through scene QA, independent of XY pivot checks."""
import pytest
from test_scene import mesh, rb, PROFILES
from twinqa.scene import scene_findings


def check(meta, bounds=((-1, -1, -0.3), (1, 1, 8.35))):
    m = mesh()
    m['bounds_m'] = bounds
    found = scene_findings(rb(m), 'vpm', 'oks', PROFILES.vpm, export_meta=meta)
    return next(f for f in found['V013'] if f.name == 'Z bounds vs export_meta')


@pytest.mark.parametrize('maximum,status', [(8.35, 'pass'), (9.75, 'fail')])
def test_z_readback(maximum, status):
    assert check({'bounds_m': [[-1, -1, -0.3], [1, 1, maximum]]}).status == status


def test_z_unknown():
    assert check(None).status == 'not_run'


@pytest.mark.parametrize('shift', [-1.4, -0.01, -0.001, 0, 0.001, 0.01, 1.4])
def test_generated_z_shift(shift):
    from decimal import Decimal
    target = {'bounds_m': [[0, 0, 0], [1, 1, 10]]}
    maximum = float(Decimal('10') + Decimal(str(shift)))
    assert check(target, ((0, 0, 0), (1, 1, maximum))).status == ('pass' if shift == 0 else 'fail')


@pytest.mark.parametrize('meta', [{}, {'bounds_m': []}, {'bounds_m': [[0, 0, 0]]},
    {'bounds_m': [[0, 0, float('nan')], [1, 1, 8.35]]},
    {'bounds_m': [[0, 0, 10], [1, 1, 8.35]]}])
def test_z_invalid(meta):
    assert check(meta).status == 'fail'


def test_z_threshold():
    assert check({'bounds_m': [[0, 0, 0], [1, 1, 1]]}, ((0, 0, 0.001), (1, 1, 1))).status == 'fail'


@pytest.mark.parametrize('maximum,status', [(8.35, 'pass'), (9.75, 'fail')])
def test_validate_wires_export_meta(tmp_path, monkeypatch, maximum, status):
    import hashlib
    import validate_package as vp
    target = tmp_path / 'SM_Test_K_1.fbx'
    target.write_bytes(b'synthetic FBX')
    m = mesh()
    m['bounds_m'] = [[-1, -1, -0.3], [1, 1, 8.35]]
    monkeypatch.setattr(vp, 'readback', lambda p: rb(m))
    report = vp.validate(target, 'vpm', PROFILES, scene=True,
        export_meta={'SM_Test_K_1.fbx': {'bounds_m': [[-1, -1, -0.3], [1, 1, maximum]],
                                      'fbx_sha256': hashlib.sha256(target.read_bytes()).hexdigest()}})
    assert any(f.name == 'Z bounds vs export_meta' and f.status == status
               for s in report.stages for f in s.findings)


@pytest.mark.parametrize('mode', ['stale', 'null', 'unknown_key'])
def test_export_meta_fail_closed(tmp_path, monkeypatch, mode):
    import hashlib
    import validate_package as vp
    target = tmp_path / 'SM_Test_K_1.fbx'
    target.write_bytes(b'synthetic changed FBX')
    m = mesh()
    m['bounds_m'] = [[-1, -1, -0.3], [1, 1, 8.35]]
    monkeypatch.setattr(vp, 'readback', lambda p: rb(m))
    record = {'bounds_m': m['bounds_m'], 'fbx_sha256': hashlib.sha256(b'old FBX').hexdigest()}
    meta = {target.name: record}
    if mode == 'null':
        meta[target.name] = None
    elif mode == 'unknown_key':
        meta['wrong.fbx'] = record
    report = vp.validate(target, 'vpm', PROFILES, scene=True, export_meta=meta)
    assert any(f.name == 'Z bounds vs export_meta' and f.status == 'fail'
               for s in report.stages for f in s.findings)
