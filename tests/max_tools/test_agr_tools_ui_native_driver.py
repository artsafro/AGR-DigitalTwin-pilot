"""new-case: offline checks for the #868 quit-baseline switches of the native AGR Tools UI driver.

The run script needs pymxs, so its step selector is lifted out by AST and executed with stubs.
The driver is started as a fresh process; argument errors must exit before it touches Max or plugins.
"""
import ast
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
RUN = HERE / 'run_agr_tools_ui_native.py'
DRIVER = HERE / 'drive_agr_tools_ui_native.py'
ALL = ['env', 'globals', 'menu', 'icons', 'panel_open', 'dock_memory', 'boxes', 'progress',
       'row_click', 'shot', 'cancel']


def _selector():
    tree = ast.parse(RUN.read_text(encoding='utf-8'))
    keep = [n for n in tree.body
            if (isinstance(n, ast.Assign) and any(getattr(t, 'id', '') == 'STEPS' for t in n.targets))
            or (isinstance(n, ast.FunctionDef) and n.name == 'selected_steps')]
    ns = {}
    exec(compile(ast.Module(body=list(keep), type_ignores=[]), str(RUN), 'exec'), ns)
    return ns


def test_steps_keep_the_original_order():
    assert [k for k, _ in _selector()['STEPS']] == ALL


@pytest.mark.parametrize('spec,expected', [
    (None, ALL),
    ('', []),
    ('none', []),
    ('env,panel_open', ['env', 'panel_open']),
    (' env , progress ,', ['env', 'progress']),
])
def test_selected_steps(spec, expected):
    assert _selector()['selected_steps'](spec) == expected


@pytest.mark.parametrize('spec', ['bogus', 'env,Progress', 'env;panel_open'])
def test_unknown_step_is_an_error_naming_it(spec):
    with pytest.raises(SystemExit) as exc:
        _selector()['selected_steps'](spec)
    assert 'unknown AGR_UI_STEPS' in str(exc.value)


def test_main_run_quits_even_on_unknown_steps():
    """An unknown step list must still reach finish() (quitMax), not hang Max until the driver timeout."""
    src = RUN.read_text(encoding='utf-8')
    body = src[src.index('def main_run():'):src.index('QtCore.QTimer.singleShot(8000, main_run)')]
    assert 'except SystemExit' in body and body.rstrip().endswith('finish()')


# Windows STATUS_DLL_INIT_FAILED: under full-suite load the desktop heap runs out and a fresh child
# dies before running any Python, with no stderr (docs/research/full-suite-wall-time-601s-vs-4000s.md).
# That says nothing about the driver, so only that exit code is retried; every other exit is judged.
WIN_LOADER_FAILURE = 0xC0000142


def _run_fresh(cmd, run=subprocess.run, attempts=3):
    for _ in range(attempts - 1):
        proc = run(cmd, capture_output=True, text=True, timeout=60)
        if (proc.returncode & 0xFFFFFFFF) != WIN_LOADER_FAILURE or proc.stderr:
            return proc
    return run(cmd, capture_output=True, text=True, timeout=60)


def test_run_fresh_retries_only_the_loader_failure():
    seen = []

    def flaky(cmd, **kw):
        seen.append(cmd)
        if len(seen) == 1:
            return subprocess.CompletedProcess(cmd, WIN_LOADER_FAILURE, '', '')
        return subprocess.CompletedProcess(cmd, 2, '', 'err')

    assert _run_fresh(['x'], run=flaky).returncode == 2 and len(seen) == 2

    seen.clear()

    def failing(cmd, **kw):
        seen.append(cmd)
        return subprocess.CompletedProcess(cmd, 1, '', '')

    assert _run_fresh(['x'], run=failing).returncode == 1 and len(seen) == 1


@pytest.mark.parametrize('args', [
    [],
    ['--no-bundle', '--bundle', 'x.zip'],
])
def test_driver_rejects_bundle_flag_mix_before_any_side_effect(tmp_path, args):
    out = tmp_path / 'out'
    proc = _run_fresh([sys.executable, str(DRIVER), '--out', str(out)] + args)
    assert proc.returncode == 2, (hex(proc.returncode & 0xFFFFFFFF), proc.stderr)
    assert 'exactly one of --bundle and --no-bundle' in proc.stderr
    assert not out.exists()
