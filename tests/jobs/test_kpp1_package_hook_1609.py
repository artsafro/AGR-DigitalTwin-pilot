"""#1609 KPP1 package-input hook (review r1 P1-1): NPM package dir + V013 bounds, fail-closed.

Pattern: n/a | new-case: tests of jobs/KPP1/lattice-1609/hooks/kpp1_package.py (`npm-dir`, CLI arity).
"""
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / 'jobs/KPP1/lattice-1609/hooks/kpp1_package.py'
_spec = importlib.util.spec_from_file_location('kpp1_package_1609', HOOK)
kp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kp)


def _rb(path, meshes):
    path.write_text(json.dumps({'meshes': meshes}), encoding='utf-8')
    return path


def _inputs(tmp):
    d = tmp / 'in'
    (d / 'fbx').mkdir(parents=True)
    fbx = d / 'fbx' / '0000_Kpp_1_01.fbx'
    fbx.write_bytes(b'oks')
    (d / 'fbx' / 'export_meta.json').write_text(json.dumps({'fbx_records': [1]}), encoding='utf-8')
    ground = d / 'ground.fbx'
    ground.write_bytes(b'ground')
    thumb = d / 'thumb.jpg'
    thumb.write_bytes(b'jpg')
    rb = _rb(d / 'rb.json', [{'name': 'SM_Kpp_1_Main', 'bounds_m': [[0, 0, 0], [1, 2, 3]]},
                             {'name': 'UCX_SM_Kpp_1_Main_00', 'bounds_m': [[-9, -9, -9], [9, 9, 9]]}])
    grb = _rb(d / 'grb.json', [{'name': 'SM_Kpp_1_Ground', 'bounds_m': [[-5, -5, -1], [5, 5, 0]]},
                               {'name': 'SM_Kpp_1_Flora', 'bounds_m': [[-6, 0, 0], [0, 1, 4]]}])
    return [fbx, ground, thumb, rb, grb]


def test_npm_dir_copies_bytes_and_writes_bounds(tmp_path):
    ins = _inputs(tmp_path)
    pkg, v013 = tmp_path / 'out/pkg', tmp_path / 'out/v013.json'
    kp.npm_dir(*ins, pkg, v013)
    assert (pkg / '0000_Kpp_1_01.fbx').read_bytes() == b'oks'
    assert (pkg / kp.GROUND_NAME).read_bytes() == b'ground'
    meta = json.loads((pkg / 'export_meta.json').read_text(encoding='utf-8'))
    assert meta['exported_files'] == ['0000_Kpp_1_01.fbx', kp.GROUND_NAME] and meta['fbx_records'] == [1]
    b = json.loads(v013.read_text(encoding='utf-8'))
    assert b['0000_Kpp_1_01.fbx']['bounds_m'] == [[0, 0, 0], [1, 2, 3]]          # UCX never in the bounds
    assert b[kp.GROUND_NAME]['bounds_m'] == [[-6, -5, -1], [5, 5, 4]]
    assert b[kp.GROUND_NAME]['fbx_sha256'] == hashlib.sha256(b'ground').hexdigest()


@pytest.mark.parametrize('case', ['missing', 'pkg_exists', 'v013_exists', 'pkg_is_input_dir', 'v013_is_input',
                                  'v013_in_pkg', 'only_ucx', 'ground_named_oks', 'empty_meshes'])
def test_npm_dir_fails_closed_and_writes_nothing(tmp_path, case):
    ins = _inputs(tmp_path)
    pkg, v013 = tmp_path / 'out/pkg', tmp_path / 'out/v013.json'
    if case == 'missing':
        ins[2].unlink()
    elif case == 'pkg_exists':
        pkg.mkdir(parents=True)
    elif case == 'v013_exists':
        v013.parent.mkdir(parents=True)
        v013.write_text('{}', encoding='utf-8')
    elif case == 'pkg_is_input_dir':
        pkg = ins[0].parent
    elif case == 'v013_is_input':
        v013 = ins[3]
    elif case == 'v013_in_pkg':
        v013 = pkg / 'v013.json'
    elif case == 'only_ucx':
        _rb(ins[4], [{'name': 'UCX_x', 'bounds_m': [[0, 0, 0], [1, 1, 1]]}])
    elif case == 'ground_named_oks':
        new = ins[0].parent / kp.GROUND_NAME
        ins[0].rename(new)
        ins[0] = new
    elif case == 'empty_meshes':
        _rb(ins[3], [])
    before = {p: p.read_bytes() for p in ins if p.is_file()}
    with pytest.raises(ValueError):
        kp.npm_dir(*ins, pkg, v013)
    assert not v013.exists() or case == 'v013_exists' or case == 'v013_is_input'
    assert not pkg.exists() or case in ('pkg_exists', 'pkg_is_input_dir')          # no partial package dir
    assert {p: p.read_bytes() for p in ins if p.is_file()} == before           # nothing deletes or edits an input


def test_cli_arity_and_error_exit(tmp_path):
    r = subprocess.run([sys.executable, str(HOOK), 'npm-dir', 'a'], capture_output=True, text=True)
    assert r.returncode != 0
    r = subprocess.run([sys.executable, str(HOOK), 'nope'], capture_output=True, text=True)
    assert r.returncode != 0
    ins = _inputs(tmp_path)
    r = subprocess.run([sys.executable, str(HOOK), 'npm-dir', *map(str, ins), str(ins[0].parent), str(tmp_path / 'v')],
                       capture_output=True, text=True)
    assert r.returncode == 2 and 'ERROR' in r.stderr
