"""new-case: #1380 VPM UV extraction and tile-size limit; synthetic inputs, no delivery writes."""
import importlib.util
import math
import subprocess
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/architecture'))
import duplicate_guard as guard


def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def uv(monkeypatch):
    monkeypatch.setitem(sys.modules, 'bmesh', types.ModuleType('bmesh'))
    mathutils = types.ModuleType('mathutils')
    mathutils.Vector = tuple
    monkeypatch.setitem(sys.modules, 'mathutils', mathutils)
    return load('tools/blender/vpm_uv.py', 'vpm_uv_1380_test')


def test_job_shims_share_owner(uv):
    for job in ('KPP1', 'TEC26-OKS'):
        shim = load(f'jobs/{job}/scripts/vpm_uv.py', f'{job}_uv_1380')
        assert shim.pack_uv.__code__.co_filename == str(ROOT / 'tools/blender/vpm_uv.py')
        assert shim.texel_cut.__code__.co_filename == str(ROOT / 'tools/blender/vpm_uv.py')
    for name in ('vpm_stage5.py', 'vpm_stage5_oks.py'):
        src = (ROOT / 'jobs/PSU275/scripts' / name).read_text(encoding='utf-8')
        assert 'tools" / "blender' in src or "tools' / 'blender" in src


@pytest.mark.parametrize('size,expected', [(2048, 1.96875), (4096, 3.9375)])
def test_quad_limit(size, expected):
    policy = load('tools/blender/vpm_uv_policy.py', 'uv_policy_test')
    assert policy.max_quad_side(size) == expected


@pytest.mark.parametrize('size', [None, '', True, 0, -1, math.nan, math.inf, 2048.5, '4096'])
def test_invalid_quad_limit(size):
    policy = load('tools/blender/vpm_uv_policy.py', 'uv_policy_test')
    with pytest.raises(ValueError, match='tile'):
        policy.max_quad_side(size)


@pytest.mark.parametrize('size,expected', [(2048, 1.96875), (4096, 3.9375)])
def test_lmax(uv, size, expected):
    spec = {'size_full': size, 'pad_m': 0.032, 'finishes': {
        'plain': {'kind': 'placeholder'},
        'full': {'kind': 'full', 'S': 8.0, 'P': [0.3, 0.3], 'shift': [True, True]},
        'small': {'kind': 'full', 'S': 1.0, 'P': [0.3, 0.3], 'shift': [True, True]}}}
    assert uv.lmax(spec, 'plain') == expected
    assert uv.lmax(spec, 'full') == expected
    assert uv.lmax(spec, 'small') == pytest.approx(0.636)
    with pytest.raises(ValueError, match='unmapped'):
        uv.lmax(spec, 'missing')


@pytest.mark.parametrize('top', ['jobs', 'tools', 'src'])
@pytest.mark.parametrize('name', ['pack_uv', 'texel_cut'])
def test_uv_copy_guard(top, name):
    findings = guard.scan_text(f'def {name}(*args):\n    pass\n', f'{top}/copy.py')
    assert any(f.rule == 'vpm-uv' for f in findings)


def test_uv_copy_guard_controls():
    for text in ('', 'def pack_uv2():\n    pass\n', 'pack_uv = None\n'):
        assert not [f for f in guard.scan_text(text, 'jobs/copy.py') if f.rule == 'vpm-uv']
    text = 'def pack_uv():\n    pass\ndef pack_uv():\n    pass\n'
    assert len([f for f in guard.scan_text(text, 'jobs/copy.py') if f.rule == 'vpm-uv']) == 2
    assert not [f for f in guard.scan_text(text, 'tools/blender/vpm_uv.py') if f.rule == 'vpm-uv']


def test_no_delivery_changes():
    paths = subprocess.check_output(['git', 'diff', '--name-only', 'origin/main', '--', 'jobs'], cwd=ROOT, text=True).splitlines()
    assert all(p.endswith('/vpm_uv.py') or p.endswith('/vpm_stage5.py') or p.endswith('/vpm_stage5_oks.py') for p in paths)
