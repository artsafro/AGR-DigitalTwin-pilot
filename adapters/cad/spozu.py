"""SPOZU DXF/DWG -> typed Ground inputs (boundary, coverings, planting, MAF, elevations).

Pattern: n/a | new-case: config-driven SPOZU reader for the layered-cake Ground procedure (issue #195);
hatches -> closed contours with holes, clipped to the plot, validation findings instead of guesses.

Rules:

* Every layer name comes from a per-project config (``configs/*.yaml``); this module holds none.
* Coordinates are scaled to metres from ``$INSUNITS`` (or the config ``units``); unknown units raise.
* Hatch regions follow ``tools/source/inspect_ground_dxf.py`` (nesting-aware, OCS -> WCS); a loop
  that is open, self-intersecting or degenerate is a finding and the hatch is left out, never repaired.
* Covering polygons are clipped to the boundary; points keep ``inside`` and outside ones are findings.
* The base covering of the layered cake is the covering type with the largest area in the plot.
"""

from __future__ import annotations

import fnmatch
import hashlib
import importlib.util
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from shapely import affinity, union_all
from shapely.geometry import MultiPolygon, Point, Polygon, mapping

ROOT = Path(__file__).resolve().parents[2]
_INSPECT = ROOT / "tools/source/inspect_ground_dxf.py"


def _inspect_module():
    name = "inspect_ground_dxf"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _INSPECT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


INSUNITS_TO_M = {1: 0.0254, 2: 0.3048, 4: 0.001, 5: 0.01, 6: 1.0, 14: 0.1, 7: 1000.0}
UNIT_NAMES = {"in": 0.0254, "ft": 0.3048, "mm": 0.001, "cm": 0.01, "dm": 0.1, "m": 1.0, "km": 1000.0}
CLOSE_TOL_M = 0.001  # m, largest endpoint gap of a hatch edge loop that still counts as closed
GRID = 1e-6  # m, precision grid for unions/overlays
NUMBER = re.compile(r"[-+]?\d+(?:[.,]\d+)?")


class SpozuConfigError(ValueError):
    pass


# ---------------------------------------------------------------- config


@dataclass(frozen=True)
class CoveringSpec:
    type: str
    layers: tuple[str, ...]
    label: str = ""
    sources: tuple[str, ...] = ("hatch",)


@dataclass(frozen=True)
class SpozuConfig:
    project: str
    boundary_layer: str
    boundary_handle: str | None
    coverings: tuple[CoveringSpec, ...]
    planting_layers: tuple[str, ...]
    planting_label: str
    planting_positions: dict
    maf_layers: tuple[str, ...]
    maf_layer_blocks: dict
    maf_label: str
    maf_positions: dict
    elevation_layers: tuple[str, ...]
    elevation_containers: tuple[str, ...]
    elevation_value: str
    ignore_layers: tuple[str, ...]
    units: str | None = None
    overlap_tol_m2: float = 0.01

    @classmethod
    def from_dict(cls, d: dict) -> "SpozuConfig":
        try:
            b = d["boundary"]
            covs = []
            for c in d.get("coverings") or []:
                src = tuple(c.get("sources") or ("hatch",))
                bad = set(src) - {"hatch", "polyline"}
                if bad:
                    raise SpozuConfigError(f"covering {c['type']}: unknown sources {sorted(bad)}")
                covs.append(CoveringSpec(str(c["type"]), tuple(c["layers"]), str(c.get("label") or ""), src))
            pl = d.get("planting") or {}
            maf = d.get("maf") or {}
            el = d.get("elevations") or {}
            cfg = cls(
                project=str(d.get("project") or ""),
                boundary_layer=str(b["layer"]),
                boundary_handle=(str(b["handle"]) if b.get("handle") else None),
                coverings=tuple(covs),
                planting_layers=tuple(pl.get("layers") or ()),
                planting_label=str(pl.get("label") or "block_name"),
                planting_positions=dict(pl.get("positions") or {}),
                maf_layers=tuple(maf.get("layers") or ()),
                maf_layer_blocks={str(k): tuple(v) for k, v in (maf.get("layer_blocks") or {}).items()},
                maf_label=str(maf.get("label") or "block_name"),
                maf_positions=dict(maf.get("positions") or {}),
                elevation_layers=tuple(el.get("layers") or ()),
                elevation_containers=tuple(el.get("containers") or ()),
                elevation_value=str(el.get("value") or "text"),
                ignore_layers=tuple(str(x) for x in d.get("ignore_layers") or ()),
                units=d.get("units"),
                overlap_tol_m2=float(d.get("overlap_tol_m2", 0.01)),
            )
        except KeyError as exc:
            raise SpozuConfigError(f"config: missing key {exc}") from exc
        cfg._check()
        return cfg

    def _check(self) -> None:
        if self.units is not None and self.units not in UNIT_NAMES:
            raise SpozuConfigError(f"units {self.units!r}: use one of {sorted(UNIT_NAMES)}")
        if self.elevation_value not in ("text", "z"):
            raise SpozuConfigError("elevations.value: 'text' or 'z'")
        for lab in (self.planting_label, self.maf_label):
            if lab != "block_name" and not lab.startswith("attrib:"):
                raise SpozuConfigError(f"label {lab!r}: 'block_name' or 'attrib:<TAG>'")
        types = [c.type for c in self.coverings]
        if len(types) != len(set(types)):
            raise SpozuConfigError("covering types must be unique")
        owner: dict[str, str] = {}
        roles = [(f"covering:{c.type}", c.layers) for c in self.coverings]
        roles += [("planting", self.planting_layers), ("maf", self.maf_layers), ("elevations", self.elevation_layers)]
        for role, layers in roles:
            for lay in layers:
                if lay in owner:
                    raise SpozuConfigError(f"layer {lay!r} mapped twice: {owner[lay]} and {role}")
                owner[lay] = role

    def mapped_layers(self) -> set[str]:
        out = {self.boundary_layer, *self.planting_layers, *self.maf_layers, *self.elevation_layers}
        out |= set(self.elevation_containers) | set(self.maf_layer_blocks)
        for c in self.coverings:
            out |= set(c.layers)
        return out

    def ignored(self, layer: str) -> bool:
        return any(fnmatch.fnmatchcase(layer, p) for p in self.ignore_layers)


def load_config(path: str | Path) -> SpozuConfig:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return SpozuConfig.from_dict(data)


# ---------------------------------------------------------------- result


@dataclass
class Finding:
    code: str  # open_contour | self_intersecting_contour | degenerate_contour | overlapping_coverings |
    #            point_outside_boundary | unmapped_layer | boundary_not_found | boundary_ambiguous |
    #            elevation_unparsed
    layer: str
    handle: str | None = None
    detail: str = ""
    area: float | None = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class Covering:
    type: str
    label: str
    layers: tuple[str, ...]
    polygons: list[Polygon] = field(default_factory=list)  # clipped to the plot, holes kept, metres
    sources: list[str] = field(default_factory=list)  # handles that contributed

    @property
    def area(self) -> float:
        return sum(p.area for p in self.polygons)


@dataclass
class PointItem:
    x: float
    y: float
    z: float
    layer: str
    label: str
    position: str | None
    handle: str
    inside: bool | None
    rotation: float = 0.0


@dataclass
class ElevationPoint:
    x: float
    y: float
    z: float
    layer: str
    handle: str  # the source entity (inside the block definition for container content)
    inside: bool | None
    container: str | None = None  # handle of the container INSERT, if any


@dataclass
class SpozuResult:
    project: str
    unit_scale: float
    boundary: Polygon | None
    boundary_handle: str | None
    coverings: dict[str, Covering]
    planting: list[PointItem]
    maf: list[PointItem]
    elevations: list[ElevationPoint]
    findings: list[Finding]

    @property
    def base_covering(self) -> str | None:
        cands = [(c.area, t) for t, c in self.coverings.items() if c.area > 0]
        return max(cands)[1] if cands else None

    def summary(self) -> dict:
        from collections import Counter

        return {
            "project": self.project,
            "unit_scale": self.unit_scale,
            "boundary_handle": self.boundary_handle,
            "boundary_area_m2": None if self.boundary is None else round(self.boundary.area, 3),
            "base_covering": self.base_covering,
            "coverings": {
                t: {"polygons": len(c.polygons), "holes": sum(len(p.interiors) for p in c.polygons),
                    "hatches": len(c.sources), "area_m2": round(c.area, 2)}
                for t, c in self.coverings.items()
            },
            "planting": {"total": len(self.planting), "inside": sum(bool(p.inside) for p in self.planting),
                         "species_inside": len({p.label for p in self.planting if p.inside})},
            "maf": {"total": len(self.maf), "inside": sum(bool(p.inside) for p in self.maf)},
            "elevations": {"total": len(self.elevations), "inside": sum(bool(e.inside) for e in self.elevations),
                           "z_min": min((e.z for e in self.elevations if e.inside), default=None),
                           "z_max": max((e.z for e in self.elevations if e.inside), default=None)},
            "findings": dict(Counter(f.code for f in self.findings)),
        }

    def to_dict(self) -> dict:
        return {
            "project": self.project,
            "units": "m",
            "boundary": None if self.boundary is None else mapping(self.boundary),
            "boundary_handle": self.boundary_handle,
            "base_covering": self.base_covering,
            "coverings": {
                t: {"label": c.label, "layers": list(c.layers), "area_m2": c.area, "sources": c.sources,
                    "geometry": mapping(MultiPolygon(c.polygons))}
                for t, c in self.coverings.items()
            },
            "planting": [p.__dict__ for p in self.planting],
            "maf": [p.__dict__ for p in self.maf],
            "elevations": [e.__dict__ for e in self.elevations],
            "findings": [f.to_dict() for f in self.findings],
        }


# ---------------------------------------------------------------- helpers


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _polys(g) -> list[Polygon]:
    if g is None or g.is_empty:
        return []
    if g.geom_type == "Polygon":
        return [g]
    out: list[Polygon] = []
    for p in getattr(g, "geoms", []):
        out.extend(_polys(p))
    return out


def _scale(g, s: float):
    return g if s == 1.0 else affinity.scale(g, s, s, origin=(0, 0))


def _classify(err: str) -> str:
    if "elf-intersection" in err or "Self" in err:
        return "self_intersecting_contour"
    return "degenerate_contour"


def _unit_scale(doc, cfg: SpozuConfig) -> float:
    if cfg.units:
        return UNIT_NAMES[cfg.units]
    code = int(doc.header.get("$INSUNITS", 0))
    if code not in INSUNITS_TO_M:
        raise SpozuConfigError(f"$INSUNITS={code} is not a known length unit; set `units` in the config")
    return INSUNITS_TO_M[code]


def _edge_loop_gap(path) -> float:
    """Largest distance from an edge endpoint to the nearest endpoint of another edge (0 = closed).

    Edge direction is ignored (drawings store reversed edges); a single closed edge (full circle or
    ellipse) closes on itself.
    """
    ends = []
    for i, edge in enumerate(path.edges):
        a, b = edge.start_point, edge.end_point
        ends.append((i, (float(a[0]), float(a[1]))))
        ends.append((i, (float(b[0]), float(b[1]))))
    if not ends:
        return math.inf
    if len(path.edges) == 1:
        (_, a), (_, b) = ends
        return math.dist(a, b)
    worst = 0.0
    for k, (i, p) in enumerate(ends):
        near = min(math.dist(p, q) for kk, (j, q) in enumerate(ends) if kk != k and j != i)
        worst = max(worst, near)
    return worst


def _hatch_polygons(hatch, tol: float, close_tol: float) -> tuple[object | None, list[tuple[str, str]]]:
    """Filled region of a hatch or (None, [(code, detail)]) when a loop is open or invalid.

    ``close_tol`` (drawing units) is the largest endpoint gap of an edge loop that still counts as closed.
    """
    from ezdxf import path as ezpath
    from ezdxf.entities.boundary_paths import EdgePath

    m = _inspect_module()
    problems: list[tuple[str, str]] = []
    for i, bp in enumerate(hatch.paths):
        if isinstance(bp, EdgePath):
            gap = _edge_loop_gap(bp)
            if gap > close_tol:
                problems.append(("open_contour", f"loop {i}: endpoint gap {gap:.6g} drawing units"))
    if problems:
        return None, problems
    for i, p in enumerate(ezpath.from_hatch(hatch)):
        _, err = m._ring(list(p.flattening(tol)))
        if err:
            problems.append((_classify(err), f"loop {i}: {err}"))
    if problems:
        return None, problems
    region, issues = m.hatch_region(hatch, tol)
    if region is None:
        return None, [(_classify(x), x) for x in issues] or [("degenerate_contour", "no loops")]
    return region, []


def _polyline_polygon(e, m, tol: float | None = None) -> tuple[Polygon | None, tuple[str, str] | None]:
    """Closed LWPOLYLINE/2D POLYLINE -> polygon (bulges on the exact arc, chord error <= tol); open -> finding."""
    try:
        return m.boundary_polygon(e.doc, e.dxf.handle, m.BOUNDARY_TOL if tol is None else tol), None
    except ValueError as exc:
        msg = str(exc)
        if "not closed" in msg:
            return None, ("open_contour", msg)
        if "unsupported" in msg:
            return None, ("degenerate_contour", msg)
        return None, (_classify(msg), msg)


def _insert_xy(e):
    p = e.ocs().to_wcs(e.dxf.insert)
    return p.x, p.y, p.z


def _label(e, mode: str) -> str:
    if mode.startswith("attrib:"):
        tag = mode.split(":", 1)[1]
        for a in e.attribs:
            if a.dxf.tag == tag and a.dxf.text.strip():
                return a.dxf.text.strip()
    return e.dxf.name


def _text_value(e) -> str:
    if e.dxftype() == "MTEXT":
        return e.plain_text()
    return e.dxf.text


def _walk_container(insert, layers: set[str], depth: int = 0):
    """Entities on ``layers`` inside an INSERT (virtual WCS copies), recursing into nested inserts."""
    if depth > 4:
        return
    for v in insert.virtual_entities():
        if v.dxftype() == "INSERT":
            if v.dxf.layer in layers:
                yield v, insert
            yield from _walk_container(v, layers, depth + 1)
        elif v.dxf.layer in layers:
            yield v, insert


# ---------------------------------------------------------------- reader


def read_spozu_dxf(source, cfg: SpozuConfig, tol: float = 0.001) -> SpozuResult:
    """Read a SPOZU DXF (path or ezdxf document) with ``cfg``; all lengths in metres."""
    import ezdxf

    doc = source if hasattr(source, "modelspace") else ezdxf.readfile(str(source))
    m = _inspect_module()
    s = _unit_scale(doc, cfg)
    msp = doc.modelspace()
    findings: list[Finding] = []

    # boundary
    boundary = None
    bhandle = None
    cands = [e for e in msp.query("LWPOLYLINE POLYLINE") if e.dxf.layer == cfg.boundary_layer]
    if cfg.boundary_handle:
        cands = [e for e in cands if e.dxf.handle == cfg.boundary_handle]
        pick = cands
    else:
        closed = [e for e in cands if e.is_closed]
        pick = closed
        if not closed:
            for e in cands:
                findings.append(Finding("open_contour", cfg.boundary_layer, e.dxf.handle, "boundary candidate not closed"))
    if len(pick) > 1:
        findings.append(Finding("boundary_ambiguous", cfg.boundary_layer, None,
                                f"{len(pick)} closed candidates: {', '.join(e.dxf.handle for e in pick)}"))
    elif len(pick) == 1:
        poly, err = _polyline_polygon(pick[0], m)
        if err:
            findings.append(Finding(err[0], cfg.boundary_layer, pick[0].dxf.handle, err[1]))
        else:
            boundary, bhandle = _scale(poly, s), pick[0].dxf.handle
    if boundary is None and not any(f.code == "boundary_ambiguous" for f in findings):
        findings.append(Finding("boundary_not_found", cfg.boundary_layer, cfg.boundary_handle, "no valid closed boundary"))

    # coverings
    layer_type = {lay: c for c in cfg.coverings for lay in c.layers}
    raw: dict[str, list] = {c.type: [] for c in cfg.coverings}
    srcs: dict[str, list[str]] = {c.type: [] for c in cfg.coverings}
    for e in msp:
        spec = layer_type.get(e.dxf.layer)
        if spec is None:
            continue
        kind = e.dxftype()
        if kind == "HATCH" and "hatch" in spec.sources:
            region, problems = _hatch_polygons(e, tol, CLOSE_TOL_M / s)
            for code, detail in problems:
                findings.append(Finding(code, e.dxf.layer, e.dxf.handle, detail))
        elif kind in ("LWPOLYLINE", "POLYLINE") and "polyline" in spec.sources:
            region, err = _polyline_polygon(e, m, tol)
            if err:
                findings.append(Finding(err[0], e.dxf.layer, e.dxf.handle, err[1]))
        else:
            continue
        if region is None:
            continue
        region = _scale(region, s)
        if boundary is not None:
            region = region.intersection(boundary)
        if _polys(region):
            raw[spec.type].append(region)
            srcs[spec.type].append(e.dxf.handle)
    coverings: dict[str, Covering] = {}
    unions = {}
    for c in cfg.coverings:
        u = union_all(raw[c.type], grid_size=GRID) if raw[c.type] else None
        polys = [p for p in _polys(u) if p.area > 0]
        unions[c.type] = MultiPolygon(polys) if polys else None
        coverings[c.type] = Covering(c.type, c.label, c.layers, polys, srcs[c.type])
    types = [c.type for c in cfg.coverings]
    for i, a in enumerate(types):
        for b in types[i + 1:]:
            if unions[a] is None or unions[b] is None:
                continue
            ar = sum(p.area for p in _polys(unions[a].intersection(unions[b], grid_size=GRID)))
            if ar > cfg.overlap_tol_m2:
                findings.append(Finding("overlapping_coverings", f"{a} / {b}", None, f"{ar:.4f} m2", ar))

    def inside(x, y):
        return None if boundary is None else bool(boundary.covers(Point(x, y)))

    def points(layers, layer_blocks, label_mode, positions, role):
        out = []
        lays = set(layers)
        for e in msp.query("INSERT"):
            lay = e.dxf.layer
            if lay not in lays and e.dxf.name not in layer_blocks.get(lay, ()):
                continue
            x, y, z = (v * s for v in _insert_xy(e))
            label = _label(e, label_mode)
            ins = inside(x, y)
            out.append(PointItem(x, y, z, lay, label, positions.get(e.dxf.name), e.dxf.handle, ins,
                                 float(e.dxf.get("rotation", 0.0))))
            if ins is False:
                findings.append(Finding("point_outside_boundary", lay, e.dxf.handle, f"{role} {label!r} at {x:.3f},{y:.3f}"))
        return out

    planting = points(cfg.planting_layers, {}, cfg.planting_label, cfg.planting_positions, "planting")
    maf = points(cfg.maf_layers, cfg.maf_layer_blocks, cfg.maf_label, cfg.maf_positions, "maf")

    # elevations: top-level entities on the layers plus those inside container inserts
    elev_layers = set(cfg.elevation_layers)
    ents = [(e, None) for e in msp if e.dxf.layer in elev_layers]
    for ins in msp.query("INSERT"):
        if ins.dxf.layer in cfg.elevation_containers:
            ents.extend(_walk_container(ins, elev_layers))
    elevations: list[ElevationPoint] = []
    for e, parent in ents:
        kind = e.dxftype()
        src = getattr(e, "source_of_copy", None) if parent is not None else None
        handle = e.dxf.handle or (src.dxf.handle if src is not None else "") or ""
        container = parent.dxf.handle if parent is not None else None
        if kind in ("TEXT", "MTEXT"):
            p = e.dxf.insert
            p = e.ocs().to_wcs(p) if kind == "TEXT" else p
        elif kind == "INSERT":
            p = e.ocs().to_wcs(e.dxf.insert)
        elif kind == "POINT":
            p = e.dxf.location
        else:
            continue
        x, y = p.x * s, p.y * s
        if cfg.elevation_value == "text":
            if kind not in ("TEXT", "MTEXT"):
                continue
            txt = _text_value(e)
            mt = NUMBER.search(txt or "")
            if not mt:
                findings.append(Finding("elevation_unparsed", e.dxf.layer, handle, f"text {txt!r} (container {container})"))
                continue
            z = float(mt.group(0).replace(",", "."))
        else:
            z = p.z * s
        ins = inside(x, y)
        elevations.append(ElevationPoint(x, y, z, e.dxf.layer, handle, ins, container))
        if ins is False:
            findings.append(Finding("point_outside_boundary", e.dxf.layer, handle,
                                    f"elevation {z} at {x:.3f},{y:.3f} (container {container})"))

    # unmapped layers: model-space layers with entities, neither mapped nor ignored
    mapped = cfg.mapped_layers()
    used = sorted({e.dxf.layer for e in msp})
    for lay in used:
        if lay not in mapped and not cfg.ignored(lay):
            n = sum(1 for e in msp if e.dxf.layer == lay)
            findings.append(Finding("unmapped_layer", lay, None, f"{n} model-space entities"))

    return SpozuResult(cfg.project, s, boundary, bhandle, coverings, planting, maf, elevations, findings)


def read_spozu(path: str | Path, cfg: SpozuConfig, workdir: str | Path | None = None) -> SpozuResult:
    """DWG (converted on a copy through the core console) or DXF -> SpozuResult."""
    path = Path(path)
    if path.suffix.lower() == ".dwg":
        from adapters.cad.dwg import dwg_to_dxf

        if workdir is None:
            raise SpozuConfigError("a DWG needs a workdir for the converted copy")
        path = dwg_to_dxf(path, workdir).dxf
    return read_spozu_dxf(path, cfg)


def main(argv=None) -> int:
    import argparse
    import json

    ap = argparse.ArgumentParser(description="SPOZU DWG/DXF -> Ground inputs (JSON)")
    ap.add_argument("source", help=".dwg (a COPY is converted) or .dxf")
    ap.add_argument("--config", required=True)
    ap.add_argument("--workdir", help="where the DWG copy and DXF go")
    ap.add_argument("--json", help="full result (GeoJSON geometries) path")
    a = ap.parse_args(argv)
    res = read_spozu(a.source, load_config(a.config), a.workdir)
    if a.json:
        Path(a.json).write_text(json.dumps(res.to_dict(), ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res.summary(), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
