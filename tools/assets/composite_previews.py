"""new-case: lay alpha previews (max_render_flora_previews.py) over the vertical grey gradient of the A101
PreviewFlora images and save `<base>_PREVIEW.png` (24-bit, like the originals). Never overwrites.

uv run --with PySide6 python tools/assets/composite_previews.py --alpha <dir> --out <dir> [--reference <A101 png>]
With --reference the gradient colours are sampled from that image's left column (top / bottom rows).
"""
import argparse
import os
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6 import QtCore, QtGui  # noqa: E402


def sample(ref):
    img = QtGui.QImage(str(ref))
    h = img.height()
    top = QtGui.QColor(img.pixel(3, 3))
    bottom = QtGui.QColor(img.pixel(3, h - 4))
    return top, bottom


def composite(src, dst, top, bottom, premultiplied=True):
    fg = QtGui.QImage(str(src)).convertToFormat(QtGui.QImage.Format_ARGB32)
    if premultiplied:  # Scanline writes colour already multiplied by alpha: do not darken it a second time
        fg.reinterpretAsFormat(QtGui.QImage.Format_ARGB32_Premultiplied)
    out = QtGui.QImage(fg.size(), QtGui.QImage.Format_RGB888)
    p = QtGui.QPainter(out)
    g = QtGui.QLinearGradient(0, 0, 0, fg.height())
    g.setColorAt(0.0, top)
    g.setColorAt(1.0, bottom)
    p.fillRect(QtCore.QRect(0, 0, fg.width(), fg.height()), g)
    p.drawImage(0, 0, fg)
    p.end()
    if not out.save(str(dst), 'PNG'):
        raise SystemExit('cannot write ' + str(dst))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--alpha', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--reference')
    ap.add_argument('--top', default='#2b2b2b')
    ap.add_argument('--bottom', default='#3d3d3d')
    ap.add_argument('--straight-alpha', action='store_true', help='source alpha is not premultiplied')
    a = ap.parse_args(argv)
    top, bottom = sample(a.reference) if a.reference else (QtGui.QColor(a.top), QtGui.QColor(a.bottom))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    done = []
    for src in sorted(Path(a.alpha).glob('*_PREVIEW_alpha.png')):
        dst = out / src.name.replace('_PREVIEW_alpha.png', '_PREVIEW.png')
        if dst.exists():
            raise SystemExit('exists, refusing to overwrite: ' + str(dst))
        composite(src, dst, top, bottom, not a.straight_alpha)
        done.append(dst.name)
    print('gradient', top.name(), bottom.name(), 'written', len(done))


if __name__ == '__main__':
    main()
