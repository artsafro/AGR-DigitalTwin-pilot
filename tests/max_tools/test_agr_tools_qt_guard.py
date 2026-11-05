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
