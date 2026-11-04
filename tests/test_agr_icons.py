"""AGR Tools 0.6.0 icon set (#808): SVG sources are well-formed, themed and complete."""

import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[1] / "tools" / "max" / "agr_icons.py"
_spec = importlib.util.spec_from_file_location("agr_icons", _PATH)
agr_icons = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(agr_icons)

ACTIONS = {"xview", "cleanup", "cleanup_apply", "matid", "nudge", "nudge_apply", "atlas", "atlas_apply",
           "ucx", "ucx_apply", "texel", "export", "names", "tris", "textures", "pivot", "geojson"}


def test_every_action_has_an_icon():
    assert ACTIONS <= set(agr_icons.names())
    assert len(agr_icons.names()) == len(set(agr_icons.names()))


@pytest.mark.parametrize("theme,color", list(agr_icons.THEMES.items()))
def test_svg_is_wellformed_and_single_coloured(theme, color):
    for name in agr_icons.names():
        text = agr_icons.svg(name, color)
        root = ET.fromstring(text)
        assert root.get("viewBox") == "0 0 24 24"
        assert "currentColor" not in text
        colours = {v for el in root.iter() for k, v in el.attrib.items() if k in ("fill", "stroke")} - {"none"}
        assert colours == {color}, (theme, name, colours)
        assert agr_icons.label(name)


def test_themes_differ():
    assert agr_icons.THEMES["Dark"] != agr_icons.THEMES["Light"]


def test_unknown_icon_is_an_error_naming_it():
    with pytest.raises(KeyError, match="agr_nope|nope"):
        agr_icons.icon_body("nope")


def test_build_svg_only_layout_and_refuses_existing(tmp_path):
    out = tmp_path / "icons"
    files = agr_icons.build(out, png=False)
    assert len(files) == 2 * len(agr_icons.names())
    for theme in ("Dark", "Light"):
        assert (out / theme / "AgrIcons" / "agr_xview.svg").is_file()
    with pytest.raises(FileExistsError):
        agr_icons.build(out, png=False)
