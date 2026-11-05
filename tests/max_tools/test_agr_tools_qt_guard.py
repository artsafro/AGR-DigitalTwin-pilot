"""new-case: the Qt panel tests fail visibly, not skip, when the uv dev group lacks Qt (#897)."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('agr_qt_guard', Path(__file__).with_name('_qt_guard.py'))
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)


def _pyproject(tmp_path, dev):
    path = tmp_path / 'pyproject.toml'
    path.write_text('[dependency-groups]\ndev = [{}]\n'.format(', '.join('"{}"'.format(r) for r in dev)),
                    encoding='utf-8')
    return path


PINNED = ['pytest==9.1.1', 'ezdxf==1.4.3', 'PySide6-Essentials==6.12.0', 'pytest-qt==4.5.0']


def test_repo_dev_group_pins_qt_exactly():
    group = guard.dev_group(ROOT / 'pyproject.toml')
    for dist in guard.QT_DISTS:
        assert '==' in group.get(dist, ''), (dist, group)


def test_repo_qt_status_is_ok_in_the_uv_env():
    assert guard.qt_status(ROOT / 'pyproject.toml') == ('ok', '')


def test_missing_qt_with_dev_group_installed_fails(tmp_path):
    path = _pyproject(tmp_path, PINNED)
    status, reason = guard.qt_status(path, lambda n: n not in ('pyside6-essentials',))
    assert status == 'fail'
    assert 'PySide6-Essentials==6.12.0' in reason


def test_missing_qt_without_dev_group_skips(tmp_path):
    path = _pyproject(tmp_path, PINNED)
    status, reason = guard.qt_status(path, lambda n: n == 'pytest')
    assert status == 'skip'
    assert 'pytest-qt==4.5.0' in reason


def test_unpinned_or_absent_qt_fails(tmp_path):
    loose = _pyproject(tmp_path, ['pytest==9.1.1', 'PySide6-Essentials>=6', 'pytest-qt==4.5.0'])
    assert guard.qt_status(loose, lambda n: True)[0] == 'fail'
    absent = _pyproject(tmp_path, ['pytest==9.1.1'])
    status, reason = guard.qt_status(absent, lambda n: True)
    assert status == 'fail' and 'pyside6-essentials' in reason and 'pytest-qt' in reason


def test_empty_dev_group_fails(tmp_path):
    path = tmp_path / 'pyproject.toml'
    path.write_text('[project]\nname = "x"\n', encoding='utf-8')
    assert guard.qt_status(path, lambda n: False)[0] == 'fail'


_BLOCKER = """
import importlib.abc, os, sys
import importlib.metadata as md
BLOCK = [n for n in os.environ.get('QT_BLOCK', '').split(',') if n]
MISSING = [n for n in os.environ.get('QT_DIST_MISSING', '').split(',') if n]
_real = md.version
def _version(name):
    if name.lower() in MISSING:
        raise md.PackageNotFoundError(name)
    return _real(name)
md.version = _version
class _F(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name.split('.')[0] in BLOCK:
            raise ModuleNotFoundError("No module named '%s'" % name, name=name)
def _drop():
    for m in [m for m in sys.modules if m.split('.')[0] in BLOCK]:
        del sys.modules[m]
_drop()
sys.meta_path.insert(0, _F())
def pytest_collectstart(collector):
    _drop()
"""


def _run_header(tmp_path, block='', dist_missing='', pytestqt=False):
    """Run the real test_agr_tools_ui_qt.py header (up to PKG) in a subprocess pytest."""
    import os
    import shutil
    import subprocess
    import sys
    here = Path(__file__).parent
    tdir = tmp_path / 'tests' / 'max_tools'
    tdir.mkdir(parents=True)
    shutil.copy(here / '_qt_guard.py', tdir / '_qt_guard.py')
    shutil.copy(ROOT / 'pyproject.toml', tmp_path / 'pyproject.toml')
    head = (here / 'test_agr_tools_ui_qt.py').read_text(encoding='utf-8').split('PKG = ROOT', 1)[0]
    (tdir / 'test_hdr.py').write_text(head + '\n\ndef test_body():\n    pass\n', encoding='utf-8')
    (tmp_path / 'qtblock.py').write_text(_BLOCKER, encoding='utf-8')
    env = dict(os.environ, QT_BLOCK=block, QT_DIST_MISSING=dist_missing,
               PYTHONPATH=str(tmp_path) + os.pathsep + os.environ.get('PYTHONPATH', ''))
    cmd = [sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '-p', 'qtblock',
           '--rootdir', str(tmp_path), str(tdir / 'test_hdr.py')]
    if not pytestqt:
        cmd[3:3] = ['-p', 'no:pytestqt', '-p', 'no:pytest-qt']
    return subprocess.run(cmd, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=300)


def _out(r):
    return r.stdout + r.stderr


def test_guard_ok_but_pyside6_import_raises_is_error_not_skip(tmp_path):
    r = _run_header(tmp_path, block='PySide6')
    assert r.returncode != 0 and 'skipped' not in _out(r), _out(r)
    assert 'error' in _out(r).lower() and 'PySide6' in _out(r)


def test_guard_ok_but_pytestqt_import_raises_is_error(tmp_path):
    r = _run_header(tmp_path, block='pytestqt')
    assert r.returncode != 0 and 'skipped' not in _out(r), _out(r)
    assert 'error' in _out(r).lower() and 'pytestqt' in _out(r)


def test_guard_skip_with_pyside6_missing_skips(tmp_path):
    # dev group not installed: a non-Qt dist and both Qt dists look missing
    r = _run_header(tmp_path, block='PySide6', dist_missing='pyside6-essentials,pytest-qt,pytest')
    assert r.returncode == 5 and '1 skipped' in _out(r), _out(r)


def test_guard_fail_fails_before_imports(tmp_path):
    # rest of the dev group installed, Qt dist missing -> fail, even though imports would work
    r = _run_header(tmp_path, dist_missing='pyside6-essentials')
    assert r.returncode != 0 and 'Qt panel tests' in _out(r) and 'uv sync' in _out(r), _out(r)
    assert 'skipped' not in _out(r)


def test_pytest_qt_installed_pyside6_missing_aborts_session_exit_4(tmp_path):
    r = _run_header(tmp_path, block='PySide6', pytestqt=True)
    assert r.returncode == 4, (r.returncode, _out(r))
    assert 'PySide6' in _out(r)
