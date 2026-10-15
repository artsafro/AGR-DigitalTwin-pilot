"""Synthetic IFC4 intake pilot. Not a Revit importer and not a generic IFC importer.

Supported: straight vertical walls and horizontal polygonal slabs extruded along positive
building Z. Wall binding defaults to the strict synthetic contract W0000..Wnnnn (one per
slab-contour edge, matching origin and X axis). Geometric mode (binding="geometric") is an
opt-in alternative resolving wall-to-edge binding purely from building-local coordinates and
contour frames without relying on wall names. Openings are voids on those walls.
Metre and millimetre IfcSIUnit lengths are accepted.

Unsupported: holes, mapped representations, curves and other non-polyline profiles, nonplanar
points, invalid polygons, nonpositive depth, extrusion that is not positive Z, slabs or walls
tilted off building Z, rounded corners, terrace/roof-parapet semantics (roof=None).
Generated files are synthetic fixtures, not native Revit output.

extract() returns contours, openings and level elevations already in building-local metres.
frame.to_object is the map from raw IFC file coordinates (file length unit) into that frame.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import sys
import time
import types
from pathlib import Path

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.guid
import ifcopenshell.util.placement
import ifcopenshell.util.unit
import numpy as np
import shapely
from dt_ai.spec.compare import _box_diff, _match, _opening_boxes, compare_specs
from dt_ai.spec.model import Spec

CASES = ("bench-b01-box", "bench-b02-corner-niche", "bench-b02t-terrace")
SLAB_T = 0.15
SHIFT_M = (17.0, -11.0, 2.0)
ROT_DEG = 30.0
WALL_DEV_M = 1e-3
IDENT = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
SUPPORTED_SCOPE = (
    "synthetic IFC4",
    "one placed IfcBuilding",
    "storey elevation from the placement chain",
    "horizontal polygonal slabs extruded along positive building Z",
    "straight vertical walls named W0000..Wnnnn whose origin and X axis match the slab contour edge",
    "openings voided from those walls",
    "metre and millimetre IfcSIUnit length",
)
UNSUPPORTED_SCOPE = (
    "native Revit and generic IFC import",
    "wall mapping other than the W0000..Wnnnn contour-edge contract",
    "holes",
    "mapped representations",
    "curves, non-polyline profiles, rounded corners",
    "nonplanar points and invalid polygons",
    "nonpositive depth and extrusion not along positive Z",
    "slabs or walls tilted or rotated off building Z",
    "terrace and roof-parapet semantics (roof is null)",
)


class IntakeError(ValueError):
    pass


def ifc_version_text():
    value = ifcopenshell.version
    if callable(value):
        value = value()
    if isinstance(value, str) and value:
        return value
    text = getattr(value, "__version__", None)
    if isinstance(text, str) and text:
        return text
    return str(value)


def scope_payload(binding="strict"):
    if binding == "geometric":
        supported = [
            s if not s.startswith("straight vertical walls named")
            else "straight vertical walls whose origin and X axis match the slab contour edge"
            for s in SUPPORTED_SCOPE
        ]
        unsupported = [
            u if not u.startswith("wall mapping other than")
            else "wall mapping where origin or X axis does not match the slab contour edge"
            for u in UNSUPPORTED_SCOPE
        ]
        return {"supported": supported, "unsupported": unsupported}
    return {"supported": list(SUPPORTED_SCOPE), "unsupported": list(UNSUPPORTED_SCOPE)}


def gid():
    return ifcopenshell.guid.new()


def axis2(f, origin, xdir=(1.0, 0.0, 0.0), zdir=(0.0, 0.0, 1.0)):
    return f.create_entity(
        "IfcAxis2Placement3D",
        Location=f.create_entity("IfcCartesianPoint", Coordinates=tuple(float(c) for c in origin)),
        Axis=f.create_entity("IfcDirection", DirectionRatios=tuple(float(c) for c in zdir)),
        RefDirection=f.create_entity("IfcDirection", DirectionRatios=tuple(float(c) for c in xdir)),
    )


def placement(f, parent, origin, xdir=(1.0, 0.0, 0.0)):
    return f.create_entity("IfcLocalPlacement", PlacementRelTo=parent, RelativePlacement=axis2(f, origin, xdir))


def new_file(prefix=None):
    f = ifcopenshell.file(schema="IFC4")
    org = f.create_entity("IfcOrganization", Name="synthetic")
    app = f.create_entity("IfcApplication", ApplicationDeveloper=org, Version="0.9.0",
                          ApplicationFullName="ifc-intake-pilot", ApplicationIdentifier="pilot")
    person = f.create_entity("IfcPerson", FamilyName="synthetic")
    user = f.create_entity("IfcPersonAndOrganization", ThePerson=person, TheOrganization=org)
    hist = f.create_entity("IfcOwnerHistory", OwningUser=user, OwningApplication=app,
                           ChangeAction="ADDED", CreationDate=0)
    kw = {"UnitType": "LENGTHUNIT", "Name": "METRE"}
    if prefix:
        kw["Prefix"] = prefix
    units = [f.create_entity("IfcSIUnit", **kw),
             f.create_entity("IfcSIUnit", UnitType="PLANEANGLEUNIT", Name="RADIAN")]
    ctx = f.create_entity("IfcGeometricRepresentationContext", ContextType="Model",
                          CoordinateSpaceDimension=3, Precision=1e-5, WorldCoordinateSystem=axis2(f, (0.0, 0.0, 0.0)))
    body = f.create_entity("IfcGeometricRepresentationSubContext", ContextIdentifier="Body", ContextType="Model",
                           ParentContext=ctx, TargetView="MODEL_VIEW")
    project = f.create_entity("IfcProject", GlobalId=gid(), OwnerHistory=hist, Name="synthetic",
                              RepresentationContexts=[ctx], UnitsInContext=f.create_entity("IfcUnitAssignment", Units=units))
    return f, hist, body, project


def extrude(f, ctx, ring, depth):
    pts = [f.create_entity("IfcCartesianPoint", Coordinates=(float(x), float(y))) for x, y in ring]
    poly = f.create_entity("IfcPolyline", Points=pts + [pts[0]])
    profile = f.create_entity("IfcArbitraryClosedProfileDef", ProfileType="AREA", OuterCurve=poly)
    solid = f.create_entity(
        "IfcExtrudedAreaSolid", SweptArea=profile, Position=axis2(f, (0.0, 0.0, 0.0)),
        ExtrudedDirection=f.create_entity("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0)), Depth=float(depth))
    shape = f.create_entity("IfcShapeRepresentation", ContextOfItems=ctx, RepresentationIdentifier="Body",
                            RepresentationType="SweptSolid", Items=[solid])
    return f.create_entity("IfcProductDefinitionShape", Representations=[shape])


def element(f, cls, hist, name, place, rep):
    return f.create_entity(cls, GlobalId=gid(), OwnerHistory=hist, Name=name, ObjectPlacement=place, Representation=rep)


def rect(length, y0, y1):
    return [(0.0, y0), (length, y0), (length, y1), (0.0, y1)]


def contour_xy(contour):
    out = []
    for p in contour:
        if len(p) != 2 or isinstance(p[0], dict) or isinstance(p[1], dict):
            raise IntakeError("rounded corners and non-polyline contours are unsupported")
        out.append((float(p[0]), float(p[1])))
    poly = shapely.Polygon(out)
    if len(out) < 3 or not poly.is_valid or poly.area <= 0:
        raise IntakeError("slab contour is not a simple polygon")
    return out, bool(poly.exterior.is_ccw)


def edge_frames(pts, ccw):
    side = 1.0 if ccw else -1.0
    frames = []
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        d = np.array(b) - np.array(a)
        length = float(np.linalg.norm(d))
        if length <= 1e-9:
            raise IntakeError("degenerate contour edge")
        u = d / length
        frames.append((a, (float(u[0]), float(u[1]), 0.0), length, side))
    return frames


def generate(spec, prefix, path):
    """Write one synthetic IFC4. Thickness follows the spec opening default (0.2 on these fixtures)."""
    scale = 1000.0 if prefix == "MILLI" else 1.0
    f, hist, ctx, project = new_file(prefix)
    ang = math.radians(ROT_DEG)
    building_pl = placement(f, None, tuple(c * scale for c in SHIFT_M), (math.cos(ang), math.sin(ang), 0.0))
    building = element(f, "IfcBuilding", hist, spec.id, building_pl, None)
    f.create_entity("IfcRelAggregates", GlobalId=gid(), OwnerHistory=hist, RelatingObject=project, RelatedObjects=[building])
    names = [lv.name for lv in spec.levels]
    elev = {lv.name: lv.elev_m for lv in spec.levels}
    storeys = {}
    for lv in spec.levels:
        pl = placement(f, building_pl, (0.0, 0.0, lv.elev_m * scale))
        st = element(f, "IfcBuildingStorey", hist, lv.name, pl, None)
        st.Elevation = float(lv.elev_m * scale)
        storeys[lv.name] = st
    f.create_entity("IfcRelAggregates", GlobalId=gid(), OwnerHistory=hist, RelatingObject=building,
                    RelatedObjects=list(storeys.values()))
    thickness = float(spec.opening_depth_default_m)
    for fl in spec.expanded_floors():
        pts, ccw = contour_xy(fl.contour)
        y0, y1 = (0.0, thickness) if ccw else (-thickness, 0.0)
        hi = names[names.index(fl.level) + 1]
        height = elev[hi] - elev[fl.level]
        if height <= 0:
            raise IntakeError(f"non-positive storey height at {fl.level}")
        st = storeys[fl.level]
        slab = element(f, "IfcSlab", hist, fl.level, placement(f, st.ObjectPlacement, (0.0, 0.0, 0.0)),
                       extrude(f, ctx, [(x * scale, y * scale) for x, y in pts], SLAB_T * scale))
        contained = [slab]
        for i, (a, xdir, length, _side) in enumerate(edge_frames(pts, ccw)):
            wall_pl = placement(f, st.ObjectPlacement, (a[0] * scale, a[1] * scale, 0.0), xdir)
            wall = element(f, "IfcWall", hist, f"W{i:04d}", wall_pl,
                           extrude(f, ctx, rect(length * scale, y0 * scale, y1 * scale), height * scale))
            contained.append(wall)
            for op in fl.openings:
                if op.wall != i:
                    continue
                depth = float(op.depth_m if op.depth_m is not None else spec.opening_depth_default_m)
                oy0, oy1 = (0.0, depth) if ccw else (-depth, 0.0)
                opl = placement(f, wall_pl, (op.x_m * scale, 0.0, op.sill_m * scale))
                opening = element(f, "IfcOpeningElement", hist, f"O{i:04d}", opl,
                                  extrude(f, ctx, rect(op.w_m * scale, oy0 * scale, oy1 * scale), op.h_m * scale))
                f.create_entity("IfcRelVoidsElement", GlobalId=gid(), OwnerHistory=hist,
                                RelatingBuildingElement=wall, RelatedOpeningElement=opening)
        f.create_entity("IfcRelContainedInSpatialStructure", GlobalId=gid(), OwnerHistory=hist,
                        RelatingStructure=st, RelatedElements=contained)
    path.parent.mkdir(parents=True, exist_ok=True)
    f.write(str(path))


def length_scale(f):
    assignments = f.by_type("IfcUnitAssignment")
    if len(assignments) != 1:
        raise IntakeError("missing LENGTHUNIT")
    found = [u for u in assignments[0].Units if u.is_a("IfcSIUnit") and u.UnitType == "LENGTHUNIT"]
    if len(found) != 1 or found[0].Name != "METRE":
        raise IntakeError("missing LENGTHUNIT")
    return float(ifcopenshell.util.unit.calculate_unit_scale(f))


def _unit_direction(direction):
    if direction is None or not direction.is_a("IfcDirection"):
        raise IntakeError("invalid extrusion direction")
    ratios = [float(c) for c in direction.DirectionRatios]
    if len(ratios) != 3 or not all(math.isfinite(c) for c in ratios):
        raise IntakeError("invalid extrusion direction")
    vec = np.array(ratios, dtype=float)
    norm = float(np.linalg.norm(vec))
    if norm <= 1e-12:
        raise IntakeError("invalid extrusion direction")
    return vec / norm


def body_solid(element):
    rep = element.Representation
    if rep is None or not rep.Representations:
        kind = "slab" if element.is_a("IfcSlab") else element.is_a()
        raise IntakeError(f"missing {kind} representation")
    items = []
    for sr in rep.Representations:
        if sr.RepresentationIdentifier not in (None, "Body"):
            continue
        for item in sr.Items:
            if item.is_a("IfcMappedItem"):
                raise IntakeError("mapped representations are unsupported")
            items.append(item)
    if len(items) != 1 or not items[0].is_a("IfcExtrudedAreaSolid"):
        raise IntakeError("unsupported or missing extrusion")
    solid = items[0]
    direction = _unit_direction(solid.ExtrudedDirection)
    if abs(float(direction[0])) > 1e-8 or abs(float(direction[1])) > 1e-8 or float(direction[2]) <= 0.0:
        raise IntakeError("extrusion direction must be positive Z")
    try:
        depth = float(solid.Depth)
    except (TypeError, ValueError):
        raise IntakeError("nonpositive extrusion depth")
    if not math.isfinite(depth) or depth <= 0.0:
        raise IntakeError("nonpositive extrusion depth")
    return solid


def profile_ring(solid):
    area = solid.SweptArea
    if area is None or area.is_a("IfcArbitraryProfileDefWithVoids") or list(getattr(area, "InnerCurves", None) or []):
        raise IntakeError("profiles with holes are unsupported")
    if not area.is_a("IfcArbitraryClosedProfileDef") or area.OuterCurve is None or not area.OuterCurve.is_a("IfcPolyline"):
        raise IntakeError("non-polyline profile")
    pts = []
    for point in area.OuterCurve.Points:
        coords = tuple(float(c) for c in point.Coordinates)
        if len(coords) == 2:
            pts.append((coords[0], coords[1], 0.0))
        elif len(coords) == 3:
            pts.append(coords)
        else:
            raise IntakeError("nonplanar profile points")
    if len(pts) >= 2 and np.allclose(pts[0], pts[-1], atol=1e-6):
        pts = pts[:-1]
    if len(pts) < 3:
        raise IntakeError("profile ring too small")
    arr = np.array(pts, dtype=float)
    if not np.isfinite(arr).all() or float(np.max(np.abs(arr[:, 2]))) > 1e-6:
        raise IntakeError("nonplanar profile points")
    # Three lifted points must stay in the profile plane; a tilted polyline is not a plan contour.
    if len(arr) >= 3:
        normal = np.cross(arr[1] - arr[0], arr[2] - arr[0])
        norm = float(np.linalg.norm(normal))
        if norm <= 1e-12 or abs(float(normal[2])) / norm < 1.0 - 1e-6:
            raise IntakeError("nonplanar profile points")
    poly = shapely.Polygon([(float(p[0]), float(p[1])) for p in arr])
    if not poly.is_valid or poly.area <= 0:
        raise IntakeError("invalid profile polygon")
    return [tuple(float(v) for v in p) for p in arr]


def require_upright(solid, object_placement, building_placement):
    """Extrusion in the building frame must be positive Z. Tilted slabs and walls fail closed."""
    direction = _unit_direction(solid.ExtrudedDirection)
    if solid.Position is None:
        axis = np.eye(4)
    else:
        axis = np.array(ifcopenshell.util.placement.get_axis2placement(solid.Position), dtype=float)
    if object_placement is None or building_placement is None:
        raise IntakeError("tilted extrusion relative to building Z is unsupported")
    obj = np.array(ifcopenshell.util.placement.get_local_placement(object_placement), dtype=float)
    bld = np.array(ifcopenshell.util.placement.get_local_placement(building_placement), dtype=float)
    vec = (np.linalg.inv(bld) @ obj @ axis)[:3, :3] @ direction
    norm = float(np.linalg.norm(vec))
    if norm <= 1e-12:
        raise IntakeError("tilted extrusion relative to building Z is unsupported")
    vec = vec / norm
    if abs(float(vec[0])) > 1e-6 or abs(float(vec[1])) > 1e-6 or float(vec[2]) <= 1.0 - 1e-6:
        raise IntakeError("tilted extrusion relative to building Z is unsupported")


def file_to_building_metres(building_placement, scale):
    """Inverse raw building placement, then scale the first three rows into metres."""
    raw = np.array(ifcopenshell.util.placement.get_local_placement(building_placement), dtype=float)
    matrix = np.linalg.inv(raw)
    matrix[:3, :] *= float(scale)
    return [[float(v) for v in row] for row in matrix]


def bind_walls(walls, ring, storey_z, building_placement, scale):
    """W0000..Wnnnn must be the contour edges of this floor, origin and X axis included.

    This is the synthetic fixture contract, not a generic wall importer.
    """
    pts, ccw = contour_xy([[float(p[0]), float(p[1])] for p in ring])
    frames = edge_frames(pts, ccw)
    if len(walls) != len(frames):
        raise IntakeError("unsupported wall mapping")
    chosen = {}
    for wall in walls:
        name = wall.Name
        if not isinstance(name, str) or len(name) != 5 or not name.startswith("W") or not name[1:].isdigit():
            raise IntakeError("unsupported wall mapping")
        idx = int(name[1:])
        if name != f"W{idx:04d}" or idx in chosen or idx < 0 or idx >= len(frames):
            raise IntakeError("unsupported wall mapping")
        chosen[idx] = wall
    if set(chosen) != set(range(len(frames))):
        raise IntakeError("unsupported wall mapping")
    inv_b = np.linalg.inv(matrix_si(building_placement, scale))
    for i, (origin_xy, xdir, _length, _side) in enumerate(frames):
        wall = chosen[i]
        if wall.ObjectPlacement is None:
            raise IntakeError("unsupported wall mapping")
        local = inv_b @ matrix_si(wall.ObjectPlacement, scale)
        origin = local[:3, 3]
        axis = local[:3, 0]
        norm = float(np.linalg.norm(axis))
        if norm <= 1e-9:
            raise IntakeError("unsupported wall mapping")
        axis = axis / norm
        if max(abs(float(origin[0]) - origin_xy[0]), abs(float(origin[1]) - origin_xy[1]),
               abs(float(origin[2]) - storey_z)) > 1e-4:
            raise IntakeError("unsupported wall mapping")
        if max(abs(float(axis[0]) - xdir[0]), abs(float(axis[1]) - xdir[1]), abs(float(axis[2]))) > 1e-4:
            raise IntakeError("unsupported wall mapping")
    return chosen


def to_building(pts, axis_placement, object_placement, building_placement, scale):
    axis_m = np.array(ifcopenshell.util.placement.get_axis2placement(axis_placement), dtype=float)
    obj_m = np.array(ifcopenshell.util.placement.get_local_placement(object_placement), dtype=float)
    bld_m = np.array(ifcopenshell.util.placement.get_local_placement(building_placement), dtype=float)
    m = np.linalg.inv(bld_m) @ obj_m @ axis_m
    hom = np.c_[np.asarray(pts, dtype=float), np.ones(len(pts))]
    return (m @ hom.T).T[:, :3] * scale


def geom_settings():
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    settings.set("disable-opening-subtractions", True)
    return settings


def world_verts(settings, product):
    shape = ifcopenshell.geom.create_shape(settings, product)
    geom = shape.geometry if hasattr(shape, "geometry") else shape
    verts = np.asarray(geom.verts, dtype=float).reshape(-1, 3)
    if len(verts) == 0:
        raise IntakeError("empty geometry")
    return verts


def apply_inv(verts, inv_m):
    hom = np.c_[verts, np.ones(len(verts))]
    return (inv_m @ hom.T).T[:, :3]


def matrix_si(place, scale):
    m = np.array(ifcopenshell.util.placement.get_local_placement(place), dtype=float)
    m[:3, 3] *= scale
    return m


_wb_spec = importlib.util.spec_from_file_location("wall_binding", Path(__file__).resolve().with_name("wall_binding.py"))
if _wb_spec is None or _wb_spec.loader is None:
    raise ImportError("cannot load wall_binding.py adjacent to pilot.py")
_wb = importlib.util.module_from_spec(_wb_spec)
_wb_spec.loader.exec_module(_wb)

_helpers = types.SimpleNamespace(
    IntakeError=IntakeError,
    contour_xy=contour_xy,
    edge_frames=edge_frames,
    matrix_si=matrix_si,
)
UnresolvedBinding, bind_walls_geometric = _wb.make_geometric_binder(_helpers)


def storey_of(product):
    rels = list(product.ContainedInStructure or [])
    if len(rels) != 1 or not rels[0].RelatingStructure.is_a("IfcBuildingStorey"):
        raise IntakeError(f"element {product.GlobalId} is not in one storey")
    return rels[0].RelatingStructure


def wall_deviation(ring, mesh):
    poly = shapely.Polygon([(float(p[0]), float(p[1])) for p in ring])
    if not poly.is_valid or poly.area <= 0:
        raise IntakeError("wall profile is not a simple polygon")
    cloud = shapely.MultiPoint([(float(x), float(y)) for x, y, _z in mesh])
    d_corner = max(shapely.Point(p[0], p[1]).distance(cloud) for p in ring)
    grown = poly.buffer(1e-6)
    d_vert = 0.0
    for x, y, _z in mesh:
        pt = shapely.Point(float(x), float(y))
        if not grown.covers(pt):
            d_vert = max(d_vert, poly.exterior.distance(pt))
    return float(max(d_corner, d_vert))


def near0(v):
    x = float(v)
    return 0.0 if abs(x) < 1e-9 else x


def extract(path, *, binding="strict"):
    """Recover a spec from IFC only.

    Storey Z comes from the placement chain, not Elevation. Contours, openings and level
    elevations are already in building-local metres. frame.to_object maps a homogeneous raw
    IFC file coordinate (file length unit) into that frame: inverse of the raw building
    placement, with its first three rows multiplied by the length scale (metres per file unit).
    """
    if binding == "strict":
        binder = bind_walls
    elif binding == "geometric":
        binder = bind_walls_geometric
    else:
        raise IntakeError(f"unknown binding mode: {binding!r}")

    f = ifcopenshell.open(str(path))
    scale = length_scale(f)
    buildings = f.by_type("IfcBuilding")
    if len(buildings) != 1 or buildings[0].ObjectPlacement is None:
        raise IntakeError("expected one placed IfcBuilding")
    building = buildings[0]
    if not building.Name:
        raise IntakeError("building has no Name")
    bld_place = building.ObjectPlacement
    inv_b = np.linalg.inv(matrix_si(bld_place, scale))
    settings = geom_settings()
    levels = []
    for st in f.by_type("IfcBuildingStorey"):
        if st.ObjectPlacement is None:
            raise IntakeError("storey has no placement")
        local = np.linalg.inv(np.array(ifcopenshell.util.placement.get_local_placement(bld_place))) @ np.array(
            ifcopenshell.util.placement.get_local_placement(st.ObjectPlacement))
        elev = float(local[2, 3] * scale)
        if st.Name is None:
            raise IntakeError("storey has no Name")
        levels.append({"name": st.Name, "elev_m": elev, "entity": st, "z": elev})
    levels.sort(key=lambda row: row["elev_m"])
    z_of = {row["entity"].GlobalId: row["elev_m"] for row in levels}
    rings = {}
    slab_rows = []
    for slab in f.by_type("IfcSlab"):
        st = storey_of(slab)
        if st.GlobalId in rings:
            raise IntakeError("unsupported wall mapping")
        solid = body_solid(slab)
        require_upright(solid, slab.ObjectPlacement, bld_place)
        ring = to_building(profile_ring(solid), solid.Position, slab.ObjectPlacement, bld_place, scale)
        rings[st.GlobalId] = ring
        slab_rows.append((st, ring))
    walls_by_storey = {}
    devs = []
    for wall in f.by_type("IfcWall"):
        solid = body_solid(wall)
        require_upright(solid, wall.ObjectPlacement, bld_place)
        ring = to_building(profile_ring(solid), solid.Position, wall.ObjectPlacement, bld_place, scale)
        mesh = apply_inv(world_verts(settings, wall), inv_b)
        devs.append(wall_deviation(ring, mesh))
        walls_by_storey.setdefault(storey_of(wall).GlobalId, []).append(wall)
    index_of = {}
    for gid, group in walls_by_storey.items():
        ring = rings.get(gid)
        if ring is None or gid not in z_of:
            raise IntakeError("unsupported wall mapping")
        for i, wall in binder(group, ring, z_of[gid], bld_place, scale).items():
            index_of[wall.GlobalId] = i
    openings_by_storey = {}
    for opening in f.by_type("IfcOpeningElement"):
        rels = [r for r in f.by_type("IfcRelVoidsElement") if r.RelatedOpeningElement == opening]
        if len(rels) != 1 or rels[0].RelatingBuildingElement is None or not rels[0].RelatingBuildingElement.is_a("IfcWall"):
            raise IntakeError("orphan opening host")
        host = rels[0].RelatingBuildingElement
        if host.GlobalId not in index_of:
            raise IntakeError("unsupported wall mapping")
        local = apply_inv(world_verts(settings, opening), np.linalg.inv(matrix_si(host.ObjectPlacement, scale)))
        mn, mx = local.min(axis=0), local.max(axis=0)
        openings_by_storey.setdefault(storey_of(host).GlobalId, []).append({
            "wall": index_of[host.GlobalId], "x_m": near0(mn[0]), "sill_m": near0(mn[2]),
            "w_m": float(mx[0] - mn[0]), "h_m": float(mx[2] - mn[2]), "depth_m": float(mx[1] - mn[1])})
    floors = []
    for st, ring in slab_rows:
        openings = sorted(openings_by_storey.get(st.GlobalId, []), key=lambda o: (o["wall"], o["x_m"]))
        floors.append((z_of[st.GlobalId], {
            "level": st.Name, "contour": [[float(p[0]), float(p[1])] for p in ring], "openings": openings}))
    floors.sort(key=lambda item: item[0])
    spec = Spec.model_validate({
        "id": building.Name, "profile": "npm_min",
        "frame": {"object": building.Name, "source": Path(path).name, "to_object": file_to_building_metres(bld_place, scale)},
        "levels": [{"name": row["name"], "elev_m": row["elev_m"]} for row in levels],
        "floors": [item[1] for item in floors], "roof": None, "opening_depth_default_m": 0.4,
    })
    report = {
        "source_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        "schema": f.schema, "unit_scale": scale,
        "ifcopenshell.version": ifc_version_text(),
        "scope": scope_payload(binding=binding),
        "binding": binding,
        "counts": {"storeys": len(levels), "slabs": len(floors), "walls": len(index_of),
                   "openings": sum(len(v) for v in openings_by_storey.values())},
        "global_ids": {
            "building": building.GlobalId,
            "storeys": [row["entity"].GlobalId for row in levels],
            "slabs": [s.GlobalId for s in f.by_type("IfcSlab")],
            "walls": [w.GlobalId for w in f.by_type("IfcWall")],
            "openings": [o.GlobalId for o in f.by_type("IfcOpeningElement")],
        },
        "wall_profile_vs_geom_m": max(devs) if devs else 0.0,
    }
    return spec, report


def discover(inputs):
    """Read the three bench specs and bench-k01-kpp1/tolerances.json only.

    A later tolerances.json anywhere under inputs is not the benchmark contract.
    """
    root = Path(inputs)
    tol = root / "bench-k01-kpp1" / "tolerances.json"
    specs = {}
    for name in CASES:
        path = root / name / "spec.json"
        if path.is_file():
            specs[name] = path
    missing = [name for name in CASES if name not in specs]
    if missing or not tol.is_file():
        raise IntakeError(f"inputs missing {missing or 'bench-k01-kpp1/tolerances.json'}")
    return specs, tol


def median(xs):
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def timed(fn, repeats=5):
    samples = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - t0)
    return samples


def ring_dev(a, b):
    aa = np.array([(float(p[0]), float(p[1])) for p in a])
    bb = np.array([(float(p[0]), float(p[1])) for p in b])
    if len(aa) != len(bb):
        return float("inf")
    best = min(float(np.max(np.abs(aa - np.roll(bb, k, axis=0)))) for k in range(len(aa)))
    return best


def independent_devs(original, extracted):
    sa, sb = Spec.model_validate(original), Spec.model_validate(extracted)
    ea = {lv.name: lv.elev_m for lv in sa.levels}
    eb = {lv.name: lv.elev_m for lv in sb.levels}
    level = max(abs(ea[name] - eb[name]) for name in ea) if ea.keys() == eb.keys() else float("inf")
    order = {lv.name: i for i, lv in enumerate(sa.levels)}
    fa = sorted(sa.expanded_floors(), key=lambda fl: order.get(fl.level, 999))
    fb = {fl.level: fl for fl in sb.expanded_floors()}
    coord, boxes = 0.0, 0.0
    for fl in fa:
        other = fb.get(fl.level)
        if other is None:
            return level, float("inf"), float("inf")
        coord = max(coord, ring_dev(fl.contour, other.contour))
        ba = _opening_boxes(fl, ea[fl.level], sa.opening_depth_default_m)
        bb = _opening_boxes(other, eb[fl.level], sb.opening_depth_default_m)
        paired = _match(ba, bb, 1e9)
        if len(ba) != len(bb) or len(paired) != len(ba):
            boxes = float("inf")
        else:
            boxes = max([boxes, *(_box_diff(ba[i], bb[j]) for i, j in paired.items())])
    return level, coord, boxes


def expect_counts(spec):
    floors = spec.expanded_floors()
    return {"storeys": len(spec.levels), "slabs": len(floors),
            "walls": sum(len(fl.contour) for fl in floors),
            "openings": sum(len(fl.openings) for fl in floors)}


def dump(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def mini_spec():
    floor = {"contour": [[0.0, 0.0], [10.0, 0.0], [10.0, 8.0], [0.0, 8.0]],
             "openings": [{"wall": 0, "x_m": 1.0, "sill_m": 0.9, "w_m": 1.5, "h_m": 1.5}]}
    return {"id": "bench-mini-ctrl", "profile": "npm_min", "roof": None, "opening_depth_default_m": 0.4,
            "frame": {"object": "bench-mini-ctrl", "source": "control", "to_object": IDENT},
            "levels": [{"name": "L0", "elev_m": 0.0}, {"name": "L1", "elev_m": 3.0}, {"name": "roof", "elev_m": 6.0}],
            "floors": [{"level": "L0", **floor}, {"level": "L1", "contour": floor["contour"], "openings": []}]}


def row_of(result, criterion, level=None):
    for row in result["rows"]:
        if row["criterion"] == criterion and row.get("level") == level:
            return row
    raise IntakeError(f"missing compare row {criterion}")


def negative(out, tolerances):
    """Reject broken IFC, and show the comparator fire just inside and outside its thresholds."""
    neg = out / "negative"
    f, hist, ctx, project = new_file(None)
    project.UnitsInContext = None
    for unit in f.by_type("IfcSIUnit"):
        if unit.UnitType == "LENGTHUNIT":
            f.remove(unit)
    bare = neg / "missing-units.ifc"
    bare.parent.mkdir(parents=True, exist_ok=True)
    f.write(str(bare))
    broken = neg / "missing-slab.ifc"
    generate(Spec.model_validate(mini_spec()), None, broken)
    slab_file = ifcopenshell.open(str(broken))
    slab_file.by_type("IfcSlab")[0].Representation = None
    slab_file.write(str(broken))
    orphan = neg / "orphan-opening.ifc"
    generate(Spec.model_validate(mini_spec()), None, orphan)
    orphan_file = ifcopenshell.open(str(orphan))
    for rel in list(orphan_file.by_type("IfcRelVoidsElement")):
        orphan_file.remove(rel)
    orphan_file.write(str(orphan))
    rejected = {}
    for label, path in (("missing_units", bare), ("missing_slab_representation", broken), ("orphan_opening", orphan)):
        try:
            extract(path)
            rejected[label] = False
        except IntakeError:
            rejected[label] = True
    level_tol = float(tolerances["spec_compare"]["level_elev_m"])
    open_tol = float(tolerances["spec_compare"]["opening_bbox_m"])
    base = mini_spec()

    def shifted(level_delta=0.0, x_delta=0.0, drop_floor=False, drop_opening=False):
        spec = json.loads(json.dumps(base))
        spec["levels"][1]["elev_m"] += level_delta
        spec["floors"][0]["openings"][0]["x_m"] += x_delta
        if drop_floor:
            spec["floors"] = spec["floors"][:1]
        if drop_opening:
            spec["floors"][0]["openings"] = []
        return compare_specs(base, spec, {}, {}, tolerances)

    inside_l = shifted(level_delta=level_tol - 1e-6)
    outside_l = shifted(level_delta=level_tol + 1e-4)
    inside_o = shifted(x_delta=open_tol - 1e-6)
    outside_o = shifted(x_delta=open_tol + 1e-4)
    dropped_f = shifted(drop_floor=True)
    dropped_o = shifted(drop_opening=True)
    checks = {
        **rejected,
        "level_inside": inside_l["failing"] == [] and row_of(inside_l, "level elevation, m", "L1")["within"],
        "level_outside": not row_of(outside_l, "level elevation, m", "L1")["within"],
        "opening_bbox_inside": inside_o["failing"] == [] and row_of(
            inside_o, "opening pairs within bbox tolerance, m (worst pair)", "L0")["within"],
        "opening_bbox_outside": not row_of(outside_o, "opening pairs within bbox tolerance, m (worst pair)", "L0")["within"],
        "dropped_floor": not row_of(dropped_f, "floors")["within"],
        "dropped_opening": not row_of(dropped_o, "opening count", "L0")["within"],
        "level_tol_m": level_tol, "opening_bbox_tol_m": open_tol,
    }
    return checks


def run(inputs, out):
    specs, tol_path = discover(inputs)
    tolerances = json.loads(tol_path.read_text(encoding="utf-8"))
    out = Path(out)
    problems, cases = [], []
    for name in CASES:
        raw_path = specs[name]
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        base_samples = timed(lambda p=raw_path: Spec.model_validate(json.loads(p.read_text(encoding="utf-8"))))
        spec = Spec.model_validate(raw)
        compared = json.loads(json.dumps(raw))
        compared["roof"] = None
        expected = expect_counts(spec)
        for prefix, unit in ((None, "metre"), ("MILLI", "millimetre")):
            ifc_path = out / "ifc" / f"{spec.id}-{unit}.ifc"
            label = f"{spec.id}:{unit}"
            case = {"id": spec.id, "units": unit, "baseline_s": base_samples, "baseline_median_s": median(base_samples)}
            try:
                generate(spec, prefix, ifc_path)
                case["bytes"] = ifc_path.stat().st_size
                parse_s = timed(lambda p=ifc_path: ifcopenshell.open(str(p)))
                extract_s = timed(lambda p=ifc_path: extract(p))
                extracted, report = extract(ifc_path)
                payload = extracted.model_dump(mode="json")
                dump(out / "extracted" / f"{spec.id}-{unit}.json", payload)
                result = compare_specs(compared, payload, {}, {}, tolerances)
                level_m, coord_m, box_m = independent_devs(compared, payload)
                failing = [r for r in result["rows"] if not r["within"]]
                counts_ok = report["counts"] == expected
                wall_m = float(report["wall_profile_vs_geom_m"])
                if failing or not counts_ok or wall_m > WALL_DEV_M:
                    problems.append(label)
                case.update({
                    "parse_s": parse_s, "parse_median_s": median(parse_s),
                    "parse_extract_s": extract_s, "parse_extract_median_s": median(extract_s),
                    "schema": report["schema"], "sha256": report["source_sha256"], "global_ids": report["global_ids"],
                    "counts": report["counts"], "expected_counts": expected, "counts_ok": counts_ok,
                    "comparison_rows": result["rows"], "failing": result["failing"],
                    "max_level_dev_mm": level_m * 1000.0, "max_coord_dev_mm": coord_m * 1000.0,
                    "max_opening_bbox_dev_mm": box_m * 1000.0, "wall_profile_vs_geom_mm": wall_m * 1000.0,
                })
            except Exception as exc:
                problems.append(f"{label}: {exc}")
                case["error"] = str(exc)
            cases.append(case)
    try:
        controls = negative(out, tolerances)
    except Exception as exc:
        controls = {"error": str(exc)}
        problems.append(f"negative: {exc}")
    if any(controls.get(k) is False for k in (
            "missing_units", "missing_slab_representation", "orphan_opening", "level_inside", "level_outside",
            "opening_bbox_inside", "opening_bbox_outside", "dropped_floor", "dropped_opening")):
        problems.append("negative controls")
    results = {
        "ok": not problems, "problems": problems, "cases": cases, "negative": controls,
        "ifcopenshell.version": ifc_version_text(), "scope": scope_payload(),
    }
    dump(out / "results.json", results)
    summary = {"ok": results["ok"], "problems": problems, "negative": {
        k: controls.get(k) for k in ("missing_units", "missing_slab_representation", "orphan_opening",
                                     "level_inside", "level_outside", "opening_bbox_inside", "opening_bbox_outside",
                                     "dropped_floor", "dropped_opening")},
        "cases": [{"id": c["id"], "units": c.get("units"), "bytes": c.get("bytes"), "schema": c.get("schema"),
                   "baseline_median_s": c.get("baseline_median_s"), "parse_median_s": c.get("parse_median_s"),
                   "parse_extract_median_s": c.get("parse_extract_median_s"), "counts_ok": c.get("counts_ok"),
                   "failing": c.get("failing"), "max_level_dev_mm": c.get("max_level_dev_mm"),
                   "max_coord_dev_mm": c.get("max_coord_dev_mm"),
                   "max_opening_bbox_dev_mm": c.get("max_opening_bbox_dev_mm"),
                   "wall_profile_vs_geom_mm": c.get("wall_profile_vs_geom_mm")} for c in cases]}
    print(json.dumps(summary, separators=(",", ":")))
    return 0 if results["ok"] else 1


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    return run(args.inputs, args.out)


if __name__ == "__main__":
    sys.exit(main())
