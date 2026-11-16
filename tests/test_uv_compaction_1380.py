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


def test_empty_geometry_fails_before_mutation(uv):
    for function in (uv.texel_cut, uv.pack_uv):
        with pytest.raises(ValueError, match='empty'):
            function(types.SimpleNamespace(faces=[]), [], {})


@pytest.mark.parametrize('kind', ['', None, 'unsupported'])
def test_unknown_finish_kind_is_not_placeholder(uv, kind):
    with pytest.raises(ValueError, match='finish.*kind'):
        uv.lmax({'size_full': 4096, 'finishes': {'finish': {'kind': kind}}}, 'finish')


@pytest.mark.parametrize('kwargs', [{'padding_px': math.nan}, {'padding_px': math.inf},
    {'density_px_per_m': 0}, {'density_px_per_m': math.nan}, {'padding_px': 2048},
    {'padding_px': -1}, {'density_px_per_m': True}])
def test_unmeasurable_quad_policy_is_an_error(kwargs):
    policy = load('tools/blender/vpm_uv_policy.py', 'uv_policy_negative_test')
    with pytest.raises(ValueError):
        policy.max_quad_side(4096, **kwargs)


def test_partial_and_nonfinite_full_finish_are_errors(uv):
    for finish in ({'kind': 'full', 'S': 4.096, 'P': [0.3], 'shift': [True, True]},
                   {'kind': 'full', 'S': 4.096, 'P': [0.0, 0.3], 'shift': [True, True]},
                   {'kind': 'full', 'S': 4.096, 'P': [math.nan, 0.3], 'shift': [True, True]}):
        with pytest.raises(ValueError, match='finish'):
            uv.lmax({'size_full': 4096, 'pad_m': 0.04, 'finishes': {'finish': finish}}, 'finish')


def test_qa_and_slicer_use_the_same_policy(uv):
    import ast
    tree = ast.parse((ROOT / 'tools/blender/qa_master.py').read_text(encoding='utf-8'))
    assignment = next(n for n in tree.body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == 'MAX_EDGE' for t in n.targets))
    for size, expected in ((2048, 1.96875), (4096, 3.9375)):
        scope = {'argv': ['report.json', 'input.fbx', str(size)], 'max_quad_side': uv.max_quad_side}
        exec(compile(ast.Module(body=[assignment], type_ignores=[]), '<qa-limit>', 'exec'), scope)
        assert scope['MAX_EDGE'] == uv.max_quad_side(size) == expected


def test_generated_tile_policy_probe():
    from fractions import Fraction
    policy = load('tools/blender/vpm_uv_policy.py', 'uv_policy_generated')
    for size in range(128, 8193, 128):
        assert policy.max_quad_side(size) == float(Fraction(size * 63, 65536))


@pytest.mark.parametrize('path,constant,reason', [
    ('jobs/vyatskaya-tow02/scripts/build_body_blender.py', 'MAX_SIDE_M = 3.8', 'closed job'),
    ('jobs/vyatskaya-tow02/scripts/build_decor_blender.py', 'MAX_EDGE_M = 3.8', 'closed job'),
    ('jobs/vyatskaya-tow02/scripts/build_review_fixes_blender.py', 'MAX_SIDE_M = 3.8', 'closed job'),
    ('jobs/PSU275/scripts/qa_master_psu275.py', 'MAX_EDGE = 4.0 + 1e-4', 'historical QA'),
])
def test_d320_leftovers_have_explicit_historical_reasons(path, constant, reason):
    report = (ROOT / 'docs/architecture/report-1380.md').read_text(encoding='utf-8')
    rows = [line for line in report.splitlines() if line.startswith(f'| `{path}` |')]
    assert len(rows) == 1, f'{path}: expected exactly one explicit exception row'
    assert f'`{constant}`' in rows[0]
    assert 'historical' in rows[0] and reason in rows[0]
    assert constant in (ROOT / path).read_text(encoding='utf-8')


def test_no_delivery_changes():
    base = subprocess.check_output(['git', 'merge-base', 'origin/main', 'HEAD'], cwd=ROOT, text=True).strip()
    paths = subprocess.check_output(['git', 'diff', '--name-only', base, '--', 'jobs'], cwd=ROOT, text=True).splitlines()
    # a delivery is a file a job produced (FBX, ZIP, textures, reports); job scripts are code. #1381 also edits job
    # scripts (KPP1 seal shim, build_kpp1.roof via roof_core), so the check is on the kind of file, not on #1380's names.
    # Job docs (STATE.md, REPORT.md) are not deliveries either (#1563 updates the KPP1 STATE row the card asks for).
    assert all(p.endswith(('.py', '.md')) for p in paths), [p for p in paths if not p.endswith(('.py', '.md'))]
