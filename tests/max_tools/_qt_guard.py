"""new-case: decide skip vs fail for the Qt panel tests from the uv dev group (#897).

The Qt panel tests need PySide6 + pytest-qt, pinned in pyproject.toml [dependency-groups] dev.
A missing Qt package is a visible failure when the rest of the dev group is installed (the uv suite
promised Qt and did not deliver it). It stays a skip only in an environment without the dev group
(for example a bare interpreter that runs a single test file), where nothing promised Qt.
"""
import re
import tomllib
from importlib import metadata

QT_DISTS = ('pyside6-essentials', 'pytest-qt')


def _norm(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def dev_group(pyproject_path):
    """Return {normalized name: requirement string} of the dev dependency group."""
    with open(pyproject_path, 'rb') as fh:
        data = tomllib.load(fh)
    reqs = data.get('dependency-groups', {}).get('dev', [])
    out = {}
    for req in reqs:
        if not isinstance(req, str):
            continue
        name = re.split(r'[\s<>=!~;\[]', req, maxsplit=1)[0]
        out[_norm(name)] = req
    return out


def installed(name):
    try:
        metadata.version(name)
    except metadata.PackageNotFoundError:
        return False
    return True


def qt_status(pyproject_path, is_installed=installed):
    """('ok' | 'skip' | 'fail', reason). Unpinned or absent Qt pins in the dev group are 'fail'."""
    group = dev_group(pyproject_path)
    unpinned = [d for d in QT_DISTS if '==' not in group.get(d, '')]
    if unpinned:
        return 'fail', 'dev group does not pin {} with =='.format(', '.join(unpinned))
    missing = [group[d] for d in QT_DISTS if not is_installed(d)]
    if not missing:
        return 'ok', ''
    others = [n for n in group if n not in QT_DISTS]
    if others and all(is_installed(n) for n in others):
        return 'fail', 'dev group installed but {} missing; run `uv sync`'.format(', '.join(missing))
    return 'skip', 'dev group not installed; {} missing'.format(', '.join(missing))
