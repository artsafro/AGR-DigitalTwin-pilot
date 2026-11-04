"""AGR Tools 0.6.0 icon set: own monochrome SVG sources, Dark/Light, PNG 24/30/36/48.

Pattern: new-case: generated monochrome icon set for the 3ds Max plugin package (#808).

Every icon is drawn here from primitives on a 24x24 grid (no third-party icon
fonts or files). One colour per theme: the Dark theme gets a light stroke, the
Light theme a dark stroke. Output layout matches the package spec of the
handoff: ``<out>/Dark/AgrIcons/agr_<name>.svg`` and ``agr_<name>_<NN>.png``.

    python tools/max/agr_icons.py <new-output-dir> [--sheet <new-sheet.png>]

PNG rendering needs PySide6 (QtSvg); SVG generation is stdlib only.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SIZES = (24, 30, 36, 48)
THEMES = {"Dark": "#dcdcdc", "Light": "#383838"}

_S = 'fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"'
_F = 'fill="currentColor" stroke="none"'

# name -> (Russian label, SVG body on a 24x24 grid using currentColor)
BASE: dict[str, tuple[str, str]] = {
    "tools": ("Панель AGR Tools",
              f'<path {_S} d="M4 21V9l6-4v16M10 21V3l10 4v14M2 21h20"/>'
              f'<path {_S} d="M13 9h4M13 13h4M13 17h4M6 12h2M6 16h2"/>'),
    "xview": ("xView: перекрытия",
              f'<rect {_S} x="3" y="3" width="12" height="12" rx="1"/>'
              f'<rect {_S} x="9" y="9" width="12" height="12" rx="1"/>'
              f'<rect {_F} x="9" y="9" width="6" height="6" opacity="0.55"/>'),
    "matid": ("MatID",
              f'<rect {_S} x="3" y="3" width="8" height="8" rx="1"/>'
              f'<rect {_S} x="13" y="3" width="8" height="8" rx="1"/>'
              f'<rect {_S} x="3" y="13" width="8" height="8" rx="1"/>'
              f'<rect {_F} x="13" y="13" width="8" height="8" rx="1"/>'),
    "names": ("Имена NPM/VPM",
              f'<path {_S} d="M3 6.5V4h11l7 8-7 8H3v-2.5"/>'
              f'<path {_S} d="M6 9h6M6 12h8M6 15h5"/>'),
    "tris": ("Лимиты треугольников",
             f'<path {_S} d="M12 3L21.5 20H2.5Z"/>'
             f'<path {_S} d="M7.25 11.5h9.5L12 20Z"/>'),
    "textures": ("Текстуры",
                 f'<rect {_S} x="3" y="3" width="18" height="18" rx="1.5"/>'
                 f'<path {_F} d="M3.8 3.8h5.4v5.4H3.8ZM14.8 3.8h5.4v5.4h-5.4ZM9.2 9.2h5.6v5.6H9.2Z'
                 f'M3.8 14.8h5.4v5.4H3.8ZM14.8 14.8h5.4v5.4h-5.4Z"/>'),
    "pivot": ("Пивот",
              f'<circle {_S} cx="12" cy="12" r="6.5"/>'
              f'<path {_S} d="M12 2v5M12 17v5M2 12h5M17 12h5"/>'
              f'<circle {_F} cx="12" cy="12" r="2"/>'),
    "cleanup": ("Очистка перед экспортом",
                f'<path {_S} d="M14.5 3.5l-4 7"/>'
                f'<path {_S} d="M7 10.5h7.5l2 3.5H5Z"/>'
                f'<path {_S} d="M5.5 14L4 21M9 14l-1 7M12.5 14l.5 7M16 14l1.5 7"/>'
                f'<path {_S} d="M19 3v3M17.5 4.5h3"/>'),
    "nudge": ("UV: сдвиг на целый тайл",
              f'<path {_S} d="M3 3v18h18" opacity="0.6"/>'
              f'<rect {_S} x="5" y="11" width="6" height="6" rx="0.5" stroke-dasharray="2 1.6"/>'
              f'<rect {_S} x="14" y="4" width="6" height="6" rx="0.5"/>'
              f'<path {_S} d="M10 12l4-3.5M14 8.5h-2.6M14 8.5v2.4"/>'),
    "atlas": ("UDIM -> атлас NPM",
              f'<rect {_S} x="3" y="3" width="18" height="18" rx="1"/>'
              f'<path {_S} d="M3 13h10M13 3v18M13 9h8M17 9v12"/>'),
    "texel": ("Плотность текселя",
              f'<path {_S} d="M3 16L16 3l5 5L8 21Z"/>'
              f'<path {_S} d="M7 12l2 2M10 9l1.5 1.5M13 6l2 2M5.5 13.5l1 1M11.5 7.5l1 1"/>'),
    "ucx": ("Коллизия UCX",
            f'<path {_S} d="M12 2.5l8.5 4.75v9.5L12 21.5l-8.5-4.75v-9.5Z" stroke-dasharray="2.4 1.8"/>'
            f'<path {_S} d="M12 7l4.5 2.5v5L12 17l-4.5-2.5v-5Z"/>'
            f'<path {_S} d="M7.5 9.5L12 12l4.5-2.5M12 12v5"/>'),
    "export": ("Экспорт с проверкой",
               f'<path {_S} d="M4 13v7h16v-7"/>'
               f'<path {_S} d="M12 15V3M7.5 7.5L12 3l4.5 4.5"/>'),
    "geojson": ("Проверка GeoJSON",
                f'<path {_S} d="M3 19l5-2 8 3 5-2V6l-5 2-8-3-5 2Z" opacity="0.6"/>'
                f'<path {_S} d="M12 15.5s-4-3.6-4-6.5a4 4 0 0 1 8 0c0 2.9-4 6.5-4 6.5Z"/>'
                f'<circle {_F} cx="12" cy="9" r="1.4"/>'),
    # status / control icons for the result table and the progress row
    "ok": ("Статус: ок",
           f'<circle {_S} cx="12" cy="12" r="9"/><path {_S} d="M7.5 12.5l3 3 6-6.5"/>'),
    "error": ("Статус: ошибка",
              f'<circle {_S} cx="12" cy="12" r="9"/><path {_S} d="M8.5 8.5l7 7M15.5 8.5l-7 7"/>'),
    "warn": ("Статус: предупреждение",
             f'<path {_S} d="M12 3l9.5 17h-19Z"/><path {_S} d="M12 9.5v5"/>'
             f'<circle {_F} cx="12" cy="17.3" r="1.1"/>'),
    "cancel": ("Отмена",
               f'<circle {_S} cx="12" cy="12" r="9"/><rect {_F} x="8.5" y="8.5" width="7" height="7" rx="1"/>'),
    "select": ("Выделить в сцене",
               f'<path {_S} d="M5 3l13 7.5-5.5 1.5-2.5 5.5Z"/><path {_S} d="M13 12.5l5 6.5"/>'),
}

# "apply to new export copy" variants = base icon (scaled) + copy badge
APPLY: dict[str, tuple[str, str]] = {
    "cleanup_apply": ("cleanup", "Очистка: применить к копиям"),
    "nudge_apply": ("nudge", "UV-сдвиг: применить к копиям"),
    "atlas_apply": ("atlas", "Атлас: применить к копиям"),
    "ucx_apply": ("ucx", "UCX: применить к копиям"),
}

_BADGE = (f'<rect fill="none" stroke="currentColor" stroke-width="1.5" x="13.5" y="13.5" width="9" height="9" rx="1.5"/>'
          f'<path fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" d="M18 15.6v4.8M15.6 18h4.8"/>')


def icon_body(name: str) -> str:
    if name in BASE:
        return BASE[name][1]
    if name in APPLY:
        base = BASE[APPLY[name][0]][1]
        return f'<g transform="scale(0.68)">{base}</g>{_BADGE}'
    raise KeyError(f"unknown AGR icon: {name}")


def names() -> list[str]:
    return list(BASE) + list(APPLY)


def label(name: str) -> str:
    return BASE[name][0] if name in BASE else APPLY[name][1]


def svg(name: str, color: str) -> str:
    body = icon_body(name).replace("currentColor", color)
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">'
            f'{body}</svg>\n')


def _render_png(svg_text: str, size: int, path: Path) -> None:
    from PySide6 import QtCore, QtGui, QtSvg

    renderer = QtSvg.QSvgRenderer(QtCore.QByteArray(svg_text.encode("utf-8")))
    if not renderer.isValid():
        raise ValueError(f"invalid SVG for {path.name}")
    image = QtGui.QImage(size, size, QtGui.QImage.Format_ARGB32)
    image.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    renderer.render(painter)
    painter.end()
    if not image.save(str(path), "PNG"):
        raise OSError(f"cannot write {path}")


def build(out: Path, png: bool = True) -> list[Path]:
    if out.exists():
        raise FileExistsError(f"output exists, refusing to overwrite: {out}")
    written: list[Path] = []
    if png:
        from PySide6 import QtGui
        _app = QtGui.QGuiApplication.instance() or QtGui.QGuiApplication([])  # noqa: F841
    for theme, color in THEMES.items():
        folder = out / theme / "AgrIcons"
        folder.mkdir(parents=True)
        for name in names():
            text = svg(name, color)
            path = folder / f"agr_{name}.svg"
            path.write_text(text, encoding="utf-8", newline="\n")
            written.append(path)
            if png:
                for size in SIZES:
                    p = folder / f"agr_{name}_{size}.png"
                    _render_png(text, size, p)
                    written.append(p)
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out", type=Path)
    ap.add_argument("--svg-only", action="store_true")
    args = ap.parse_args(argv)
    files = build(args.out, png=not args.svg_only)
    print(f"{len(files)} files -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
