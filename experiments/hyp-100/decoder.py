"""Type-specific DXF coordinate decoder for hypothesis 100.

POINT location and 3D POLYLINE vertices are already WCS in DXF. LWPOLYLINE
vertices are OCS and go through ezdxf's public vertices_in_wcs().
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_BIM_PATH = Path(__file__).resolve().parents[1] / "bim-autocad-agr" / "experiment.py"
_spec = importlib.util.spec_from_file_location("bim_autocad_agr", _BIM_PATH)
if _spec is None or _spec.loader is None:
    raise ImportError(_BIM_PATH)
bim = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bim)


def extract_typed(entity):
    """Same schema as bim._extract, without a second OCS pass on WCS geometry."""
    kind = entity.dxftype()
    if kind == "POINT":
        loc = entity.dxf.location
        return {
            "layer": entity.dxf.layer,
            "kind": kind,
            "closed": False,
            "vertices_mm": [[float(loc.x), float(loc.y), float(loc.z)]],
        }
    if kind == "LWPOLYLINE":
        closed = bim.base._closed(entity)
        verts = [list(map(float, vertex)) for vertex in entity.vertices_in_wcs()]
    else:
        closed = bim.base._closed(entity)
        verts = []
        for vertex in entity.vertices:
            loc = vertex.dxf.location
            verts.append([float(loc.x), float(loc.y), float(loc.z)])
    return {
        "layer": entity.dxf.layer,
        "kind": kind,
        "closed": closed,
        "vertices_mm": bim.base._drop_repeated_close(verts, closed),
    }


def candidate_read(path):
    """bim.strict_read with _extract replaced by extract_typed for the call."""
    original = bim._extract
    try:
        bim._extract = extract_typed
        return bim.strict_read(path)
    finally:
        bim._extract = original
