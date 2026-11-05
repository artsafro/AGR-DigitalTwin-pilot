"""AGR Tools builder tests: SYNTHETIC placeholder PNG icons unless AGR_ICON_PNG_DIR is set.

Real PNGs are rendered from the SVG sources with PySide6 at release build time (tools/max/agr_icons.py);
they are never committed (*.png is LFS-tracked, LFS is not used).
QT_QPA_PLATFORM=offscreen is set here, before any PySide6 import in this directory (#897).
"""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import struct  # noqa: E402
import zlib  # noqa: E402

import pytest  # noqa: E402


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
