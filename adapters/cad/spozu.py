"""SPOZU DXF/DWG -> typed Ground inputs (boundary, coverings, planting, MAF, elevations).

Pattern: n/a | new-case: config-driven SPOZU reader for the layered-cake Ground procedure (issue #195);
hatches -> closed contours with holes, clipped to the plot, validation findings instead of guesses.

Rules:

* Every layer name comes from a per-project config (``configs/*.yaml``); this module holds none.
* Coordinates are scaled to metres from ``$INSUNITS`` (or the config ``units``); unknown units raise.
* Hatch regions follow ``tools/source/inspect_ground_dxf.py`` (nesting-aware, OCS -> WCS); a loop
  that is open, self-intersecting or degenerate is a finding and the hatch is left out, never repaired.
* Covering polygons are clipped to the boundary; points keep ``inside`` and outside ones are findings.
* Block content is read too: every INSERT that is not itself a point symbol is expanded with its
  composed transform (rotation, scale, mirror, nesting, MINSERT cells); an entity on layer ``0`` takes
  the layer of its insert (AutoCAD rule). ``ref`` is the provenance path ``<insert>>...><entity>``.
  Cycles, nesting deeper than ``MAX_NESTING`` and content that cannot be transformed are findings.
* A label configured as ``attrib:<TAG>`` is that attribute or unresolved (``None`` + finding).
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
MAX_NESTING = 8  # INSERT levels expanded below model space
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
    repair: bool = False  # True: a self-intersecting hatch loop is repaired by make_valid (finding repaired_contour)


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
    contour_layers: tuple[str, ...] = ()  # elevation contour polylines (Z = polyline elevation)
    ground_elements: dict[str, tuple[str, ...]] = field(default_factory=dict)

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
                rep = c.get("repair") or None
                if rep not in (None, "make_valid"):
                    raise SpozuConfigError(f"covering {c['type']}: repair must be 'make_valid' or absent")
                covs.append(CoveringSpec(str(c["type"]), tuple(c["layers"]), str(c.get("label") or ""), src,
                                         rep == "make_valid"))
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
                contour_layers=tuple(el.get("contour_layers") or ()),
                ground_elements={str(k): tuple(v) for k, v in (d.get("ground_elements") or {}).items()},
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
        roles += [("planting", self.planting_layers), ("maf", self.maf_layers), ("elevations", self.elevation_layers),
                  ("elevation_contours", self.contour_layers)]
        roles += [(f"ground_element:{r}", ls) for r, ls in self.ground_elements.items()]
        for role, layers in roles:
            for lay in layers:
                if lay in owner:
                    raise SpozuConfigError(f"layer {lay!r} mapped twice: {owner[lay]} and {role}")
                owner[lay] = role

    def mapped_layers(self) -> set[str]:
        out = {self.boundary_layer, *self.planting_layers, *self.maf_layers, *self.elevation_layers,
               *self.contour_layers}
        out |= set(self.elevation_containers) | set(self.maf_layer_blocks)
        for c in self.coverings:
            out |= set(c.layers)
        for ls in self.ground_elements.values():
            out |= set(ls)
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
    #            elevation_unparsed | label_missing | nested_cycle | nesting_too_deep | nested_unsupported |
    #            repaired_contour (a self-intersecting hatch loop repaired by make_valid; area = after)
    layer: str
    handle: str | None = None  # the source entity (inside the block definition for block content)
    detail: str = ""
    area: float | None = None
    ref: str | None = None  # provenance path insert>...>entity; equals handle for model-space entities

    def __post_init__(self):
        if self.ref is None:
            self.ref = self.handle

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class Covering:
    type: str
    label: str
    layers: tuple[str, ...]
    polygons: list[Polygon] = field(default_factory=list)  # clipped to the plot, holes kept, metres
    sources: list[str] = field(default_factory=list)  # provenance paths (refs) that contributed

    @property
    def area(self) -> float:
        return sum(p.area for p in self.polygons)


@dataclass
class PointItem:
    x: float
    y: float
    z: float
    layer: str  # effective layer
    label: str | None  # None = configured attribute missing/empty (label_missing finding)
    position: str | None
    handle: str  # the source INSERT (inside the block definition for block content)
    inside: bool | None
    rotation: float = 0.0
    container: str | None = None  # provenance path of the enclosing insert, if any
    ref: str = ""  # provenance path of this instance


@dataclass
class ElevationPoint:
    x: float
    y: float
    z: float
    layer: str
    handle: str  # the source entity (inside the block definition for container content)
    inside: bool | None
    container: str | None = None  # provenance path of the enclosing insert, if any
    ref: str = ""
    source: str = "point"  # point (spot height) | contour (a vertex of an elevation contour polyline)


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
    ground_elements: list[dict] = field(default_factory=list)

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
                         "species_inside": len({p.label for p in self.planting if p.inside and p.label is not None}),
                         "unlabeled": sum(p.label is None for p in self.planting)},
            "maf": {"total": len(self.maf), "inside": sum(bool(p.inside) for p in self.maf),
                    "unlabeled": sum(p.label is None for p in self.maf)},
            "elevations": {"total": len(self.elevations), "inside": sum(bool(e.inside) for e in self.elevations),
                           "contour_vertices": sum(e.source == "contour" for e in self.elevations),
                           "contours": len({e.ref for e in self.elevations if e.source == "contour"}),
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
            "ground_elements": self.ground_elements,
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
    from ezdxf.entities.boundary_paths import EdgePath, PolylinePath

    m = _inspect_module()
    problems: list[tuple[str, str]] = []
    for i, bp in enumerate(hatch.paths):
        if isinstance(bp, EdgePath):
            gap = _edge_loop_gap(bp)
            if gap > close_tol:
                problems.append(("open_contour", f"loop {i}: endpoint gap {gap:.6g} drawing units"))
        elif isinstance(bp, PolylinePath) and not bp.is_closed:
            # ezdxf would close it implicitly; only an explicit end == start vertex counts as closed
            v = bp.vertices
            gap = math.dist(v[0][:2], v[-1][:2]) if len(v) >= 2 else math.inf
            if gap > close_tol:
                problems.append(("open_contour", f"loop {i}: polyline path not closed, end gap {gap:.6g} drawing units"))
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


def _repair_hatch(hatch, tol: float):
    """make_valid repair of a hatch whose loops self-intersect: loops combined even-odd.

    Returns (region | None, raw ring area sum in drawing units^2).
    """
    from ezdxf import path as ezpath
    from shapely import make_valid

    region, before = None, 0.0
    for p in ezpath.from_hatch(hatch):
        pts = [(v.x, v.y) for v in p.flattening(tol)]
        if len(pts) < 3:
            continue
        raw = Polygon(pts)
        before += abs(raw.area)
        polys = _polys(make_valid(raw))
        if not polys:
            continue
        fixed = MultiPolygon(polys)
        region = fixed if region is None else region.symmetric_difference(fixed)
    if region is None or region.is_empty:
        return None, before
    return region, before


def _polyline_polygon(e, m, tol: float | None = None) -> tuple[Polygon | None, tuple[str, str] | None]:
    """Closed LWPOLYLINE/2D POLYLINE -> polygon (bulges on the exact arc, chord error <= tol); open -> finding."""
    try:
        return m.polyline_polygon(e, m.BOUNDARY_TOL if tol is None else tol), None
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


def _label(e, mode: str) -> tuple[str | None, str | None]:
    """(label, problem): ``attrib:<TAG>`` is that attribute or unresolved, never the block name."""
    if not mode.startswith("attrib:"):
        return e.dxf.name, None
    tag = mode.split(":", 1)[1]
    found = [a for a in e.attribs if a.dxf.tag == tag]
    for a in found:
        if a.dxf.text.strip():
            return a.dxf.text.strip(), None
    what = "empty" if found else "missing"
    return None, f"block {e.dxf.name!r}: attribute {tag} {what}"


def _text_value(e) -> str:
    if e.dxftype() == "MTEXT":
        return e.plain_text()
    return e.dxf.text


@dataclass
class _Ent:
    e: object  # model-space entity or a WCS copy of block content
    layer: str  # effective layer
    handle: str  # the source entity handle (block definition entity for block content)
    ref: str  # provenance path
    container: str | None  # provenance path of the enclosing insert


def _block_content(insert):
    """(source entity, WCS copy or None, problem, cell suffix) for the block of ``insert`` (ATTDEF skipped).

    A MINSERT inside the block is expanded into its cells in the block's own coordinates first, so
    the parent transform applies to every cell position (row/column spacing included); a transformed
    MINSERT would keep its spacing in the old scale and direction.
    """
    m = insert.matrix44()
    blk = insert.block()
    if blk is None:
        return
    for be in blk:
        if be.dxftype() == "ATTDEF":
            continue
        if be.dxftype() == "INSERT" and be.mcount > 1:
            try:
                cells = list(be.multi_insert())
            except Exception as exc:
                yield be, None, f"{type(exc).__name__}: {exc}", ""
                continue
            parts = [(cell, f"#{k}") for k, cell in enumerate(cells)]
        else:
            parts = [(be, "")]
        for src, suffix in parts:
            try:
                c = src.copy()
                if hasattr(c, "remove_association"):
                    c.remove_association()
                c.transform(m)
            except Exception as exc:  # non-copyable, non-transformable, non-uniform scaling of arcs, shear
                yield be, None, f"{type(exc).__name__}: {exc}", suffix
                continue
            yield be, c, None, suffix


def _walk(msp, atomic, relevant, findings: list, max_depth: int = MAX_NESTING, skipped: list | None = None):
    """Model-space entities plus expanded block content; ``atomic(e, layer)`` INSERTs are not expanded.

    ``relevant(layer)`` decides whether block content that cannot be transformed is a finding
    (an INSERT that cannot be transformed always is: its content is unknown). Non-relevant content
    that cannot be transformed goes to ``skipped`` as (effective layer, handle, ref) so the layer
    check still sees it.
    """

    def visit(e, layer, handle, ref, container, depth, chain):
        if e.dxftype() == "INSERT" and e.mcount > 1:
            for k, cell in enumerate(e.multi_insert()):
                yield from visit(cell, layer, handle, f"{ref}#{k}", container, depth, chain)
            return
        yield _Ent(e, layer, handle, ref, container)
        if e.dxftype() != "INSERT" or atomic(e, layer):
            return
        name = e.dxf.name
        if name in chain:
            findings.append(Finding("nested_cycle", layer, handle, f"block {name!r} inserts itself", ref=ref))
            return
        if depth >= max_depth:
            findings.append(Finding("nesting_too_deep", layer, handle,
                                    f"block {name!r} below {max_depth} insert levels not read", ref=ref))
            return
        for be, c, problem, suffix in _block_content(e):
            lay = layer if be.dxf.layer == "0" else be.dxf.layer
            cref = f"{ref}>{be.dxf.handle}{suffix}"
            if c is None:
                if relevant(lay) or be.dxftype() == "INSERT":
                    findings.append(Finding("nested_unsupported", lay, be.dxf.handle,
                                            f"{be.dxftype()} in block {name!r}: {problem}", ref=cref))
                elif skipped is not None:
                    skipped.append((lay, be.dxf.handle, cref))
                continue
            c.dxf.layer = lay
            yield from visit(c, lay, be.dxf.handle, cref, ref, depth + 1, chain | {name})

    for e in msp:
        yield from visit(e, e.dxf.layer, e.dxf.handle, e.dxf.handle, None, 0, frozenset())


# ---------------------------------------------------------------- reader


def read_spozu_dxf(source, cfg: SpozuConfig, tol: float = 0.001) -> SpozuResult:
    """Read a SPOZU DXF (path or ezdxf document) with ``cfg``; all lengths in metres."""
    import ezdxf

    doc = source if hasattr(source, "modelspace") else ezdxf.readfile(str(source))
    m = _inspect_module()
    s = _unit_scale(doc, cfg)
    msp = doc.modelspace()
    findings: list[Finding] = []
    elev_layers = set(cfg.elevation_layers)
    contour_layers = set(cfg.contour_layers)
    pl_layers, maf_layers = set(cfg.planting_layers), set(cfg.maf_layers)
    layer_type = {lay: c for c in cfg.coverings for lay in c.layers}
    element_roles = {lay: role for role, lays in cfg.ground_elements.items() for lay in lays}

    def is_maf(e, layer):
        return layer in maf_layers or e.dxf.name in cfg.maf_layer_blocks.get(layer, ())

    def atomic(e, layer):  # a point symbol: one point, its block content is not Ground input
        return layer in pl_layers or is_maf(e, layer) or (cfg.elevation_value == "z" and layer in elev_layers)

    def relevant(layer):
        return layer in layer_type or layer in pl_layers or layer in maf_layers or layer in elev_layers \
            or layer in contour_layers or layer in element_roles \
            or layer == cfg.boundary_layer

    skipped: list = []
    ents = list(_walk(msp, atomic, relevant, findings, skipped=skipped))

    # boundary
    boundary = None
    bhandle = None
    cands = [x for x in ents if x.e.dxftype() in ("LWPOLYLINE", "POLYLINE") and x.layer == cfg.boundary_layer]
    if cfg.boundary_handle:
        pick = [x for x in cands if cfg.boundary_handle in (x.ref, x.handle)]
    else:
        pick = [x for x in cands if x.e.is_closed]
        if not pick:
            for x in cands:
                findings.append(Finding("open_contour", cfg.boundary_layer, x.handle, "boundary candidate not closed",
                                        ref=x.ref))
    if len(pick) > 1:
        findings.append(Finding("boundary_ambiguous", cfg.boundary_layer, None,
                                f"{len(pick)} closed candidates: {', '.join(x.ref for x in pick)}"))
    elif len(pick) == 1:
        poly, err = _polyline_polygon(pick[0].e, m)
        if err:
            findings.append(Finding(err[0], cfg.boundary_layer, pick[0].handle, err[1], ref=pick[0].ref))
        else:
            boundary, bhandle = _scale(poly, s), pick[0].ref
    if boundary is None and not any(f.code == "boundary_ambiguous" for f in findings):
        findings.append(Finding("boundary_not_found", cfg.boundary_layer, cfg.boundary_handle, "no valid closed boundary"))

    # coverings
    raw: dict[str, list] = {c.type: [] for c in cfg.coverings}
    srcs: dict[str, list[str]] = {c.type: [] for c in cfg.coverings}
    for x in ents:
        e = x.e
        spec = layer_type.get(x.layer)
        if spec is None:
            continue
        kind = e.dxftype()
        if kind == "HATCH" and "hatch" in spec.sources:
            region, problems = _hatch_polygons(e, tol, CLOSE_TOL_M / s)
            if region is None and spec.repair and problems and \
                    all(c == "self_intersecting_contour" for c, _ in problems):
                region, before = _repair_hatch(e, tol)
                if region is not None:
                    findings.append(Finding("repaired_contour", x.layer, x.handle,
                                            f"make_valid: raw ring area {before * s * s:.3f} m2 -> "
                                            f"{region.area * s * s:.3f} m2 (before boundary clip)",
                                            region.area * s * s, ref=x.ref))
                    problems = []
            for code, detail in problems:
                findings.append(Finding(code, x.layer, x.handle, detail, ref=x.ref))
        elif kind in ("LWPOLYLINE", "POLYLINE") and "polyline" in spec.sources:
            region, err = _polyline_polygon(e, m, tol)
            if err:
                findings.append(Finding(err[0], x.layer, x.handle, err[1], ref=x.ref))
        else:
            continue
        if region is None:
            continue
        region = _scale(region, s)
        if boundary is not None:
            region = region.intersection(boundary)
        if _polys(region):
            raw[spec.type].append(region)
            srcs[spec.type].append(x.ref)
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

    def points(select, label_mode, positions, role):
        out = []
        for it in ents:
            e = it.e
            if e.dxftype() != "INSERT" or not select(e, it.layer):
                continue
            x, y, z = (v * s for v in _insert_xy(e))
            label, problem = _label(e, label_mode)
            if problem:
                findings.append(Finding("label_missing", it.layer, it.handle, f"{role}: {problem}", ref=it.ref))
            ins = inside(x, y)
            out.append(PointItem(x, y, z, it.layer, label, positions.get(e.dxf.name), it.handle, ins,
                                 float(e.dxf.get("rotation", 0.0)), it.container, it.ref))
            if ins is False:
                findings.append(Finding("point_outside_boundary", it.layer, it.handle,
                                        f"{role} {label!r} at {x:.3f},{y:.3f}", ref=it.ref))
        return out

    planting = points(lambda e, lay: lay in pl_layers, cfg.planting_label, cfg.planting_positions, "planting")
    maf = points(is_maf, cfg.maf_label, cfg.maf_positions, "maf")

    # elevations: entities on the elevation layers, in model space or in any expanded block
    elevations: list[ElevationPoint] = []
    for it in ents:
        if it.layer not in elev_layers:
            continue
        e = it.e
        kind = e.dxftype()
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
                findings.append(Finding("elevation_unparsed", it.layer, it.handle,
                                        f"text {txt!r} (container {it.container})", ref=it.ref))
                continue
            z = float(mt.group(0).replace(",", "."))
        else:
            z = p.z * s
        ins = inside(x, y)
        elevations.append(ElevationPoint(x, y, z, it.layer, it.handle, ins, it.container, it.ref))
        if ins is False:
            findings.append(Finding("point_outside_boundary", it.layer, it.handle,
                                    f"elevation {z} at {x:.3f},{y:.3f} (container {it.container})", ref=it.ref))

    # elevation contours: every flattened vertex of a contour polyline, Z = the polyline elevation
    from ezdxf import path as ezpath

    for it in ents:
        if it.layer not in contour_layers or it.e.dxftype() not in ("LWPOLYLINE", "POLYLINE"):
            continue
        e = it.e
        if e.dxftype() == "LWPOLYLINE":
            zs = {float(e.dxf.get("elevation", 0.0))}
        else:
            zs = {round(float(v.dxf.location.z), 6) for v in e.vertices}
        if len(zs) != 1 or not all(math.isfinite(z) for z in zs):
            findings.append(Finding("elevation_unparsed", it.layer, it.handle,
                                    f"contour with Z values {sorted(zs)[:4]} (one constant Z required)", ref=it.ref))
            continue
        z = zs.pop() * s
        seen_xy = set()
        for p in ezpath.make_path(e).flattening(tol):
            key = (round(p.x * s, 6), round(p.y * s, 6))
            if key in seen_xy:
                continue
            seen_xy.add(key)
            elevations.append(ElevationPoint(key[0], key[1], z, it.layer, it.handle, inside(*key), it.container,
                                             it.ref, "contour"))

    # unmapped layers: effective layers of model-space entities and of expanded (non-atomic) block
    # content, neither mapped nor ignored; atomic symbols are not expanded, so their graphics never count
    mapped = cfg.mapped_layers()
    seen: dict[str, dict] = {}
    occ = [(x.layer, x.handle, x.ref, x.container is None) for x in ents]
    occ += [(lay, h, r, False) for lay, h, r in skipped]
    for lay, h, r, top in occ:
        if lay in mapped or cfg.ignored(lay):
            continue
        d = seen.setdefault(lay, {"top": set(), "nested": [], "first": None})
        if top:
            d["top"].add(h)
        else:
            d["nested"].append(r)
            if d["first"] is None:
                d["first"] = (h, r)
    for lay in sorted(seen):
        d = seen[lay]
        top, nested = len(d["top"]), len(d["nested"])
        h, r = d["first"] if d["first"] and not top else (None, None)
        detail = f"{top + nested} entities ({top} model-space, {nested} in blocks)"
        if nested:
            detail += f"; nested e.g. {', '.join(d['nested'][:3])}"
        findings.append(Finding("unmapped_layer", lay, h, detail, ref=r))

    # Keep every configured element, including unsupported primitives and INSERT grouping records.
    # The existing walker supplies WCS transforms and instance provenance; no second DXF reader.
    elements = []
    for it in ents:
        if it.layer not in element_roles:
            continue
        e = it.e
        kind = e.dxftype()
        coords, problem = None, None
        if kind in ("LINE", "LWPOLYLINE", "POLYLINE", "ARC", "SPLINE"):
            try:
                coords = [[float(p.x * s), float(p.y * s), float(p.z * s)]
                          for p in ezpath.make_path(e).flattening(tol / s)]
                if len(coords) < 2 or not all(math.isfinite(v) for p in coords for v in p):
                    raise ValueError("fewer than two finite path points")
            except Exception as exc:
                coords, problem = None, f"{type(exc).__name__}: {exc}"
        elif kind != "INSERT":
            problem = f"unsupported element primitive {kind}"
        elements.append({"role": element_roles[it.layer], "layer": it.layer, "handle": it.handle,
                         "ref": it.ref, "container": it.container, "kind": kind,
                         "label": e.dxf.name if kind == "INSERT" else None,
                         "geometry": {"type": "LineString", "coordinates": coords} if coords else None,
                         "source_width_m": float(e.dxf.get("const_width", 0)) * s if kind == "LWPOLYLINE" else None,
                         "problem": problem})
    return SpozuResult(cfg.project, s, boundary, bhandle, coverings, planting, maf, elevations, findings, elements)


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
