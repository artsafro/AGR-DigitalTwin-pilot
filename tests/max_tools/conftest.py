"""AGR Tools builder tests: SYNTHETIC placeholder PNG icons unless AGR_ICON_PNG_DIR is set.

Real PNGs are rendered from the SVG sources with PySide6 at release build time (tools/max/agr_icons.py);
they are never committed (*.png is LFS-tracked, LFS is not used).
QT_QPA_PLATFORM=offscreen (#897) is applied only by the session fixture `offscreen_qt`, which is requested by the
test modules that mention PySide6 and is rolled back at session end. It is never set at import: a 3ds Max started
from this process must not inherit it ("no Qt platform plugin could be initialized", #1024 1.0.1).
"""
import os
import struct
import zlib
from pathlib import Path

import pytest

_QT_MODULES = {}


def _needs_qt(path):
    key = str(path)
    if key not in _QT_MODULES:
        try:
            _QT_MODULES[key] = 'PySide6' in Path(key).read_text(encoding='utf-8', errors='replace')
        except OSError:
            _QT_MODULES[key] = False
    return _QT_MODULES[key]


@pytest.fixture(scope='session')
def offscreen_qt():
    """Offscreen Qt for the PySide6 tests only; the previous value is restored at session end."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv('QT_QPA_PLATFORM', 'offscreen')
        yield


def pytest_collection_modifyitems(items):
    here = Path(__file__).resolve().parent
    for item in items:
        path = Path(str(item.fspath)).resolve()
        if here in path.parents and path.name != Path(__file__).name and _needs_qt(path):
            item.fixturenames.insert(0, 'offscreen_qt')


def _png(size):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    raw = b''.join(b'\x00' + b'\x00\x00\x00\x00' * size for _ in range(size))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


@pytest.fixture(scope='session', autouse=True)
def synthetic_icon_pngs(tmp_path_factory):
    if os.environ.get('AGR_ICON_PNG_DIR'):
        yield os.environ['AGR_ICON_PNG_DIR']
        return
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / 'tools/max/agr_icons.py'
    spec = importlib.util.spec_from_file_location('agr_icons_conftest', path)
    icons = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(icons)
    root = tmp_path_factory.mktemp('synthetic_icons')
    for theme in icons.THEMES:
        folder = root / theme / 'AgrIcons'
        folder.mkdir(parents=True)
        for name in icons.names():
            for size in icons.SIZES:
                (folder / 'agr_{}_{}.png'.format(name, size)).write_bytes(_png(size))
    os.environ['AGR_ICON_PNG_DIR'] = str(root)
    yield str(root)
    del os.environ['AGR_ICON_PNG_DIR']


@pytest.fixture(scope='session', autouse=True)
def isolated_journal(tmp_path_factory):
    """#1024 branch 0: every edits_080/090/100 call journals a line; tests never write the user's journal."""
    old = os.environ.get('AGR_JOURNAL_DIR')
    os.environ['AGR_JOURNAL_DIR'] = str(tmp_path_factory.mktemp('agr_journal'))
    yield os.environ['AGR_JOURNAL_DIR']
    if old is None:
        os.environ.pop('AGR_JOURNAL_DIR', None)
    else:
        os.environ['AGR_JOURNAL_DIR'] = old
