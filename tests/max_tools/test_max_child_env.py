"""new-case: #1024 1.0.1 - a child 3ds Max never inherits Qt variables from a test/driver process."""
import ast
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from dt_ai.core.max_env import MAX_UNSAFE_ENV, max_child_env  # noqa: E402

KEYS = ('QT_QPA_PLATFORM', 'QT_PLUGIN_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH', 'QT_API')
SITES = [
    'test-polygon/build/guide_drive.py', 'test-polygon/run_polygon.py',
    'tests/max_tools/drive_agr_tools_suite_native.py', 'tests/max_tools/drive_agr_tools_ui_native.py',
    'tests/dcc/test_batch_export_max.py', 'tests/dcc/test_flora_atlas_max.py',
    'tools/export/batch_export_plan.py', 'tools/flora/build_flora_npm_light.py',
    'tools/flora/rebind_flora_library_maps.py', 'tools/methods/body/run_benchmarks.py',
    'tools/review/maf_showcase.py',
]
LAUNCH_WORDS = ('DCC_BATCH', 'DCC', 'dcc_batch', '3dsmax.exe')


def test_helper_strips_exactly_the_four_keys():
    assert MAX_UNSAFE_ENV == KEYS
    base = {k: 'x' for k in KEYS}
    base.update(PATH='p', AGR_X='1', QT_OTHER='keep')
    out = max_child_env(base)
    assert out == {'PATH': 'p', 'AGR_X': '1', 'QT_OTHER': 'keep'}
    assert out is not base and set(KEYS) <= set(base)  # a copy; the input is untouched


def test_helper_default_is_a_copy_of_os_environ(monkeypatch):
    for key in KEYS:
        monkeypatch.setenv(key, 'x')
    monkeypatch.setenv('AGR_KEEP_ME', '1')
    out = max_child_env()
    assert not set(KEYS) & set(out) and out['AGR_KEEP_ME'] == '1'
    assert os.environ['QT_QPA_PLATFORM'] == 'x'


def test_conftest_import_does_not_set_qt_platform():
    code = ('import os, importlib.util, sys\n'
            'spec = importlib.util.spec_from_file_location("c", sys.argv[1])\n'
            'importlib.util.module_from_spec(spec); spec.loader.exec_module(importlib.util.module_from_spec(spec))\n'
            'print("QT=" + repr(os.environ.get("QT_QPA_PLATFORM")))\n')
    env = {k: v for k, v in os.environ.items() if k != 'QT_QPA_PLATFORM'}
    r = subprocess.run([sys.executable, '-c', code, str(Path(__file__).with_name('conftest.py'))],
                       env=env, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    assert 'QT=None' in r.stdout


def test_offscreen_fixture_is_scoped_and_requested_only_by_pyside_modules():
    text = (Path(__file__).with_name('conftest.py')).read_text(encoding='utf-8')
    tree = ast.parse(text)
    top_level_setenv = [n for n in tree.body if 'QT_QPA_PLATFORM' in (ast.get_source_segment(text, n) or '')
                        and not isinstance(n, (ast.FunctionDef, ast.Expr))]
    assert not top_level_setenv
    assert 'pytest.MonkeyPatch.context()' in text


def _launch_calls(path):
    text = path.read_text(encoding='utf-8')
    tree = ast.parse(text)
    funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    calls = []
    for fn in funcs:
        fn_text = ast.get_source_segment(text, fn)
        if not any(w in fn_text for w in LAUNCH_WORDS):
            continue
        for node in ast.walk(fn):
            if isinstance(node, ast.Call):
                seg = ast.get_source_segment(text, node)
                name = ast.unparse(node.func)
                if name in ('subprocess.run', 'subprocess.Popen', 'run') and 'tasklist' not in seg \
                        and 'blender' not in seg.lower()                         and any(w in seg for w in ('DCC', 'dcc_batch', 'str(exe)', 'command', 'cmd')):
                    calls.append((node, text, fn))
    return calls


def _env_of(node):
    for kw in node.keywords:
        if kw.arg == 'env':
            return kw.value
    if node.args and isinstance(node.args[-1], ast.Name) and node.args[-1].id == 'env':
        return node.args[-1]
    return None


def _uses_helper(expr, tree):
    if expr is None:
        return False
    if any(isinstance(n, ast.Call) and ast.unparse(n.func) == 'max_child_env' for n in ast.walk(expr)):
        return True
    if isinstance(expr, ast.Name):
        rhs = [n.value for n in ast.walk(tree) if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == expr.id for t in n.targets)]
        return bool(rhs) and all(_uses_helper(r, tree) for r in rhs)
    return False


@pytest.mark.parametrize('site', SITES)
def test_every_max_launch_site_passes_a_qt_free_env(site):
    calls = _launch_calls(ROOT / site)
    assert calls, 'no launch call recognised in ' + site
    for node, text, fn in calls:
        assert _uses_helper(_env_of(node), fn), '{}:{} launches Max without max_child_env()'.format(site, node.lineno)


def _load(rel, name):
    sys.path.insert(0, str(ROOT / 'tools' / 'review'))
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize('rel,call', [
    ('tools/review/max_adapter.py', lambda m: m._call(['x.py'])),
    ('tools/review/maf_showcase.py', lambda m: m._run_job(Path('job.py'), 'card')),
])
def test_review_launchers_hand_a_qt_free_env_to_the_child(monkeypatch, rel, call):
    for key in KEYS:
        monkeypatch.setenv(key, 'parent')
    mod = _load(rel, 'launch_' + Path(rel).stem)
    seen = {}

    def fake_run(cmd, **kw):
        seen.update(kw)
        return subprocess.CompletedProcess(cmd, 0, '', '')
    monkeypatch.setattr(mod.subprocess, 'run', fake_run)
    call(mod)
    assert 'env' in seen and not set(KEYS) & set(seen['env'])
    assert seen['env'].get('PATH') == os.environ.get('PATH')
