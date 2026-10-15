"""Synthetic IFC4 semantic-loss probe. Not a delivery importer and not a Revit export."""

from __future__ import annotations

import argparse, hashlib, json, math, os, time
from pathlib import Path

import ifcopenshell
import ifcopenshell.api.aggregate, ifcopenshell.api.context, ifcopenshell.api.feature
import ifcopenshell.api.geometry, ifcopenshell.api.root, ifcopenshell.api.spatial
import ifcopenshell.geom, ifcopenshell.util.placement, ifcopenshell.util.unit
import numpy as np, shapely
from dt_ai.spec.model import Spec

try:
    import relation_multimap
except ModuleNotFoundError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import relation_multimap

THICKNESS, SLAB_DEPTH, INSET, PAD = 0.20, 0.20, 0.02, 0.001
ROT_DEG, SHIFT, TOL_M, TOL_V = 23.0, (100.0, -50.0, 7.0), 1e-3, 1e-5
SUPPORTED = {"IfcSite", "IfcBuilding", "IfcBuildingStorey", "IfcSlab", "IfcWall", "IfcWallStandardCase", "IfcOpeningElement", "IfcWindow"}
ARMS = (("no-void", "void"), ("no-fill", "fill"), ("no-contain", "contain"))
UNSUPPORTED = ["full IFC-to-spec contour recovery", "rounded contour corners", "roof interpretation",
               "materials and family identities", "georeferencing", "real Revit export", "production acceptance"]


def _dump(path, obj):
    Path(path).write_text(json.dumps(obj, separators=(",", ":"), sort_keys=True), encoding="utf-8")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _median(values):
    ordered = sorted(values)
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else 0.5 * (ordered[mid - 1] + ordered[mid])


def _maxabs(left, right):
    return max(abs(float(a) - float(b)) for a, b in zip(left, right))


def _flag(settings, key, value):
    try:
        settings.set(key, value)
    except Exception:
        setattr(settings, key.replace("-", "_"), value)


def _rot(x, y, z):
    a = math.radians(ROT_DEG)
    c, s = math.cos(a), math.sin(a)
    return [c * x - s * y + SHIFT[0], s * x + c * y + SHIFT[1], z + SHIFT[2]]


def _building_matrix():
    a = math.radians(ROT_DEG)
    c, s = math.cos(a), math.sin(a)
    m = np.eye(4)
    m[0, 0], m[0, 1], m[1, 0], m[1, 1] = c, -s, s, c
    m[:3, 3] = SHIFT
    return m


def _edge_matrix(start, end):
    d = np.array(end, float) - np.array(start, float)
    x = d / np.linalg.norm(d)
    x3 = np.array([x[0], x[1], 0.0])
    m = np.eye(4)
    m[:3, 0], m[:3, 1], m[:3, 2] = x3, np.cross([0.0, 0.0, 1.0], x3), [0.0, 0.0, 1.0]
    m[:3, 3] = (float(start[0]), float(start[1]), 0.0)
    return m


def _place(model, product, matrix, parent):
    # matrix is local SI metres relative to parent; file coordinates are project length units.
    scale = ifcopenshell.util.unit.calculate_unit_scale(model)
    point = model.create_entity("IfcCartesianPoint", Coordinates=tuple(float(v) / scale for v in matrix[:3, 3]))
    axis = model.create_entity("IfcDirection", DirectionRatios=tuple(float(v) for v in matrix[:3, 2]))
    ref = model.create_entity("IfcDirection", DirectionRatios=tuple(float(v) for v in matrix[:3, 0]))
    axes = model.create_entity("IfcAxis2Placement3D", Location=point, Axis=axis, RefDirection=ref)
    rel = None if parent is None else parent.ObjectPlacement
    product.ObjectPlacement = model.create_entity("IfcLocalPlacement", PlacementRelTo=rel, RelativePlacement=axes)


def _box(model, body, length, height, thickness):
    # offset 0: local Y is [0, thickness]. Lengths passed to the geometry API are metres.
    return ifcopenshell.api.geometry.add_wall_representation(
        model, context=body, length=length, height=height, thickness=thickness, offset=0.0)


def _entity(model, kind, name, text):
    ent = ifcopenshell.api.root.create_entity(model, ifc_class=kind, name=name)
    ent.Description = text
    return ent


def write_ifc(spec, path, milli):
    model = ifcopenshell.file(schema="IFC4")
    project = _entity(model, "IfcProject", "SYNTHETIC", "SYNTHETIC offline semantic transport. Not a survey and not a Revit export.")
    unit = model.create_entity("IfcSIUnit", None, "LENGTHUNIT", "MILLI" if milli else None, "METRE")
    project.UnitsInContext = model.create_entity("IfcUnitAssignment", Units=(unit,))
    ctx = ifcopenshell.api.context.add_context(model, context_type="Model")
    body = ifcopenshell.api.context.add_context(model, context_type="Model", context_identifier="Body", target_view="MODEL_VIEW", parent=ctx)
    site = _entity(model, "IfcSite", "SYNTHETIC-SITE", "SYNTHETIC site")
    building = _entity(model, "IfcBuilding", "SYNTHETIC-BUILDING", "SYNTHETIC nested placement. Not a measured building.")
    ifcopenshell.api.aggregate.assign_object(model, products=[site], relating_object=project)
    ifcopenshell.api.aggregate.assign_object(model, products=[building], relating_object=site)
    _place(model, site, np.eye(4), None)
    _place(model, building, _building_matrix(), site)
    names = [lv.name for lv in spec.levels]
    elev = {lv.name: float(lv.elev_m) for lv in spec.levels}
    storeys = {}
    for lv in spec.levels:
        st = _entity(model, "IfcBuildingStorey", lv.name, "SYNTHETIC storey")
        st.Elevation = float(lv.elev_m) * (1000.0 if milli else 1.0)
        ifcopenshell.api.aggregate.assign_object(model, products=[st], relating_object=building)
        local = np.eye(4)
        local[2, 3] = float(lv.elev_m)
        _place(model, st, local, building)
        storeys[lv.name] = st
    for fl in spec.expanded_floors():
        pts = [(float(p[0]), float(p[1])) for p in fl.contour]
        z0, z1 = elev[fl.level], elev[names[names.index(fl.level) + 1]]
        st = storeys[fl.level]
        slab = _entity(model, "IfcSlab", f"slab:{fl.level}", "SYNTHETIC structural slab, not an AGR plate")
        ifcopenshell.api.geometry.assign_representation(model, product=slab, representation=ifcopenshell.api.geometry.add_slab_representation(model, context=body, polyline=pts, depth=SLAB_DEPTH))
        ifcopenshell.api.spatial.assign_container(model, products=[slab], relating_structure=st)
        slab_at = np.eye(4)
        slab_at[2, 3] = -SLAB_DEPTH
        _place(model, slab, slab_at, st)
        hosts = []
        for i, a in enumerate(pts):
            b = pts[(i + 1) % len(pts)]
            wall = _entity(model, "IfcWall", f"wall:{fl.level}:{i}", "SYNTHETIC wall")
            ifcopenshell.api.geometry.assign_representation(model, product=wall, representation=_box(model, body, float(np.linalg.norm(np.subtract(b, a))), z1 - z0, THICKNESS))
            ifcopenshell.api.spatial.assign_container(model, products=[wall], relating_structure=st)
            _place(model, wall, _edge_matrix(a, b), st)
            hosts.append(wall)
        for j, op in enumerate(fl.openings):
            void = _entity(model, "IfcOpeningElement", f"opening:{fl.level}:{j}", "SYNTHETIC rough opening")
            if hasattr(void, "PredefinedType"):
                void.PredefinedType = "OPENING"
            win = _entity(model, "IfcWindow", f"window:{fl.level}:{j}", "SYNTHETIC fill inset from the rough opening")
            ifcopenshell.api.geometry.assign_representation(model, product=void, representation=_box(model, body, op.w_m, op.h_m, THICKNESS + 2 * PAD))
            ifcopenshell.api.geometry.assign_representation(model, product=win, representation=_box(model, body, op.w_m - 2 * INSET, op.h_m - 2 * INSET, THICKNESS - 2 * INSET))
            ifcopenshell.api.feature.add_feature(model, feature=void, element=hosts[op.wall])
            ifcopenshell.api.feature.add_filling(model, opening=void, element=win)
            ifcopenshell.api.spatial.assign_container(model, products=[win], relating_structure=st)
            ov, wv = np.eye(4), np.eye(4)
            ov[:3, 3] = (op.x_m, -PAD, op.sill_m)
            wv[:3, 3] = (op.x_m + INSET, INSET, op.sill_m + INSET)
            _place(model, void, ov, hosts[op.wall])
            _place(model, win, wv, hosts[op.wall])
    model.write(str(path))


def _mesh(shape):
    geo = getattr(shape, "geometry", shape)
    v = np.array(geo.verts, float).reshape(-1, 3)
    tri = v[np.array(geo.faces, int).reshape(-1, 3)]
    vol = abs(float(np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum() / 6.0))
    return [float(x) for x in v.min(0)], [float(x) for x in v.max(0)], vol


def _geom(settings, product):
    try:
        low, high, vol = _mesh(ifcopenshell.geom.create_shape(settings, product))
    except Exception as exc:
        return exc
    return (low, high, vol) if low else None


def _geom_settings(subtract):
    s = ifcopenshell.geom.settings()
    _flag(s, "use-world-coords", True)
    _flag(s, "disable-opening-subtractions", not subtract)
    return s


def read_ledger(path):
    """Open one IFC from disk. Does not take a spec, expected numbers, or name/bbox hints."""
    path = Path(path)
    ifc = ifcopenshell.open(str(path))
    scale = float(ifcopenshell.util.unit.calculate_unit_scale(ifc))
    project = ifc.by_type("IfcProject")

    census = relation_multimap.census(ifc)
    voids = relation_multimap.singletons(census["maps"], "void")
    fills = relation_multimap.singletons(census["maps"], "fill")
    contained = relation_multimap.singletons(census["maps"], "contain")
    conflicting_containment = {d["source_id"] for d in census["diagnostics"] if d["family"] == "contain"}

    cut, plain = _geom_settings(True), _geom_settings(False)
    supported, unsupported, issues = {}, {}, []
    slabs, walls, openings, windows, storeys = [], [], [], [], []

    def solid(settings, product, gid):
        got = _geom(settings, product)
        if isinstance(got, Exception):
            issues.append(f"geometry failed {gid} {got}")
            return None
        if got is None:
            issues.append(f"geometry failed {gid} empty mesh")
            return None
        return got

    for prod in ifc.by_type("IfcProduct"):
        kind, gid, name = prod.is_a(), prod.GlobalId, prod.Name or ""
        (supported if kind in SUPPORTED else unsupported)[kind] = (supported if kind in SUPPORTED else unsupported).get(kind, 0) + 1
        if kind not in SUPPORTED:
            issues.append(f"unsupported product {kind} {gid}")
        elif kind == "IfcBuildingStorey":
            m = np.array(ifcopenshell.util.placement.get_local_placement(prod.ObjectPlacement))
            raw = None if prod.Elevation is None else float(prod.Elevation)
            storeys.append({"name": name, "global_id": gid, "world_m": [float(v) * scale for v in m[:3, 3]],
                            "elevation_raw": raw, "elevation_m": None if raw is None else raw * scale})
        elif kind in ("IfcSlab", "IfcWall", "IfcWallStandardCase", "IfcWindow"):
            body = None if prod.Representation is None else solid(cut, prod, gid)
            if prod.Representation is None:
                issues.append(f"geometry failed {gid} no representation")
            sid = contained.get(gid)
            if sid is None and gid not in conflicting_containment:
                issues.append(f"missing containment {gid}")
            row = {"name": name, "global_id": gid, "storey_id": sid}
            if kind == "IfcWindow":
                if body:
                    row["bbox_min"], row["bbox_max"] = body[0], body[1]
                windows.append(row)
            elif kind == "IfcSlab":
                if body:
                    row["bbox_min"], row["bbox_max"], row["volume_m3"] = body
                slabs.append(row)
            else:
                bare = None if prod.Representation is None else solid(plain, prod, gid)
                if body:
                    row["volume_cut_m3"] = body[2]
                if bare:
                    row["volume_uncut_m3"] = bare[2]
                walls.append(row)
        elif kind == "IfcOpeningElement":
            body = None if prod.Representation is None else solid(cut, prod, gid)
            if prod.Representation is None:
                issues.append(f"geometry failed {gid} no representation")
            if gid not in voids:
                issues.append(f"missing host {gid}")
            if gid not in fills:
                issues.append(f"missing fill {gid}")
            row = {"name": name, "global_id": gid, "host_id": voids.get(gid), "fill_id": fills.get(gid)}
            if body:
                row["bbox_min"], row["bbox_max"] = body[0], body[1]
            openings.append(row)
    for d in census["diagnostics"]:
        issues.append(f"cardinality {d['family']} {d['source_id']} unresolved")
    return {"sha256": _sha(path), "schema": ifc.schema, "unit_scale_m": scale,
            "synthetic_root": bool(project and project[0].Name and "SYNTHETIC" in project[0].Name),
            "volume_meaning": {"cut": "opening subtractions at engine default", "uncut": "opening subtractions disabled"},
            "counts": {"supported": supported, "unsupported": unsupported, "products": sum(supported.values()) + sum(unsupported.values())},
            "storeys": storeys, "slabs": slabs, "walls": walls, "openings": openings, "windows": windows, "issues": issues,
            "relation_census": census}


def expect(spec):
    """SI expectation from the spec only: shapely area and the probe placement, not an IFC file."""
    floors, names = spec.expanded_floors(), [lv.name for lv in spec.levels]
    elev = {lv.name: float(lv.elev_m) for lv in spec.levels}
    slabs, walls, openings = {}, {}, {}
    for fl in floors:
        pts = [(float(p[0]), float(p[1])) for p in fl.contour]
        z0, z1 = elev[fl.level], elev[names[names.index(fl.level) + 1]]
        corners = np.array([_rot(x, y, z) for x, y in pts for z in (z0 - SLAB_DEPTH, z0)])
        slabs[f"slab:{fl.level}"] = {"volume": float(shapely.Polygon(pts).area) * SLAB_DEPTH,
                                     "bbox_min": [float(v) for v in corners.min(0)], "bbox_max": [float(v) for v in corners.max(0)]}
        for i, a in enumerate(pts):
            b = pts[(i + 1) % len(pts)]
            vec = np.subtract(b, a)
            removed = sum(op.w_m * op.h_m for op in fl.openings if op.wall == i)
            walls[f"wall:{fl.level}:{i}"] = {"volume": THICKNESS * (float(np.linalg.norm(vec)) * (z1 - z0) - removed)}
        for j, op in enumerate(fl.openings):
            a, b = np.array(pts[op.wall], float), np.array(pts[(op.wall + 1) % len(pts)], float)
            axis = (b - a) / np.linalg.norm(b - a)
            left = np.array([-axis[1], axis[0]])
            box = []
            for along in (op.x_m, op.x_m + op.w_m):
                for across in (-PAD, THICKNESS + PAD):
                    for h in (z0 + op.sill_m, z0 + op.sill_m + op.h_m):
                        p = a + axis * along + left * across
                        box.append(_rot(float(p[0]), float(p[1]), h))
            arr = np.array(box)
            openings[f"opening:{fl.level}:{j}"] = {"bbox_min": [float(v) for v in arr.min(0)], "bbox_max": [float(v) for v in arr.max(0)],
                                                    "host": f"wall:{fl.level}:{op.wall}", "fill": f"window:{fl.level}:{j}"}
    return {"storeys": {lv.name: _rot(0.0, 0.0, float(lv.elev_m)) for lv in spec.levels}, "elev": elev,
            "slabs": slabs, "walls": walls, "openings": openings, "n_storeys": len(spec.levels)}


def _named(rows):
    return {row["name"]: row for row in rows}


def compare(spec, ledger):
    exp, dev, missing = expect(spec), {}, []
    for key in ("storey_m", "elevation_m", "slab_bbox_m", "slab_volume_m3", "opening_bbox_m", "wall_volume_m3"):
        dev[key] = 0.0
    storeys, slabs, walls, openings = _named(ledger["storeys"]), _named(ledger["slabs"]), _named(ledger["walls"]), _named(ledger["openings"])
    windows = _named(ledger["windows"])
    for name, xyz in exp["storeys"].items():
        row = storeys.get(name)
        if row is None or row["elevation_m"] is None:
            missing.append(name)
        else:
            dev["storey_m"] = max(dev["storey_m"], _maxabs(row["world_m"], xyz))
            dev["elevation_m"] = max(dev["elevation_m"], abs(row["elevation_m"] - exp["elev"][name]))
    for name, row in exp["slabs"].items():
        got = slabs.get(name)
        if not got or "bbox_min" not in got:
            missing.append(name)
        else:
            dev["slab_bbox_m"] = max(dev["slab_bbox_m"], _maxabs(got["bbox_min"] + got["bbox_max"], row["bbox_min"] + row["bbox_max"]))
            dev["slab_volume_m3"] = max(dev["slab_volume_m3"], abs(got["volume_m3"] - row["volume"]))
    for name, row in exp["walls"].items():
        got = walls.get(name)
        if not got or "volume_cut_m3" not in got:
            missing.append(name)
        else:
            dev["wall_volume_m3"] = max(dev["wall_volume_m3"], abs(got["volume_cut_m3"] - row["volume"]))
    for name, row in exp["openings"].items():
        got = openings.get(name)
        if not got or "bbox_min" not in got:
            missing.append(name)
        else:
            dev["opening_bbox_m"] = max(dev["opening_bbox_m"], _maxabs(got["bbox_min"] + got["bbox_max"], row["bbox_min"] + row["bbox_max"]))
    storey_id = {r["name"]: r["global_id"] for r in ledger["storeys"]}
    wall_id = {r["name"]: r["global_id"] for r in ledger["walls"]}
    window_id = {r["name"]: r["global_id"] for r in ledger["windows"]}
    linked = all(openings.get(name, {}).get("host_id") == wall_id.get(row["host"]) and openings.get(name, {}).get("fill_id") == window_id.get(row["fill"]) for name, row in exp["openings"].items())
    contained = all((slabs.get(name) or {}).get("storey_id") == storey_id.get(name.split(":")[1]) for name in exp["slabs"]) and all((walls.get(name) or {}).get("storey_id") == storey_id.get(name.split(":")[1]) for name in exp["walls"]) and all((windows.get(name.replace("opening", "window", 1)) or {}).get("storey_id") == storey_id.get(name.split(":")[1]) for name in exp["openings"])
    named = (set(slabs) == set(exp["slabs"]) and set(walls) == set(exp["walls"]) and set(openings) == set(exp["openings"])
             and {r["name"] for r in ledger["windows"]} == {n.replace("opening", "window", 1) for n in exp["openings"]}
             and len(ledger["storeys"]) == exp["n_storeys"])
    counts_ok = not missing and not ledger["issues"] and not ledger["counts"]["unsupported"] and linked and contained and named
    coord, volume = max(dev["storey_m"], dev["elevation_m"], dev["slab_bbox_m"], dev["opening_bbox_m"]), max(dev["slab_volume_m3"], dev["wall_volume_m3"])
    return {"within_tolerance": bool(counts_ok and coord <= TOL_M and volume <= TOL_V), "counts_ok": bool(counts_ok),
            "deviation": dev, "missing": missing,
            "evidence": {"expected_slab_volumes_m3": {n: r["volume"] for n, r in exp["slabs"].items()},
                         "measured_slab_volumes_m3": {n: r.get("volume_m3") for n, r in slabs.items()},
                         "expected_wall_volumes_m3": {n: r["volume"] for n, r in exp["walls"].items()},
                         "measured_wall_volumes_cut_m3": {n: r.get("volume_cut_m3") for n, r in walls.items()},
                         "measured_wall_volumes_uncut_m3": {n: r.get("volume_uncut_m3") for n, r in walls.items()}}}


def _gids(ledger):
    return sorted(r["global_id"] for r in ledger["slabs"] + ledger["walls"] + ledger["openings"] + ledger["windows"])


def _assoc(ledger):
    return {"hosts": sum(r["host_id"] is not None for r in ledger["openings"]),
            "fills": sum(r["fill_id"] is not None for r in ledger["openings"]),
            "contained": sum(bool(r.get("storey_id")) for r in ledger["slabs"] + ledger["walls"] + ledger["windows"])}


def _punch(src, dest, kind):
    ifc = ifcopenshell.open(str(src))
    if kind == "void":
        ifc.remove(ifc.by_type("IfcRelVoidsElement")[0])
    elif kind == "fill":
        ifc.remove(ifc.by_type("IfcRelFillsElement")[0])
    else:
        rel = max(ifc.by_type("IfcRelContainedInSpatialStructure"), key=lambda item: len(item.RelatedElements or []))
        elems = list(rel.RelatedElements or [])
        if len(elems) > 1:
            rel.RelatedElements = elems[1:]
        else:
            ifc.remove(rel)
    ifc.write(str(dest))


def _samples(ledger):
    return {"schema": ledger["schema"], "unit_scale_m": ledger["unit_scale_m"], "sha256": ledger["sha256"], "storeys": ledger["storeys"],
            "opening_bboxes": [[r["name"], r.get("bbox_min"), r.get("bbox_max")] for r in ledger["openings"]],
            "window_bboxes": [[r["name"], r.get("bbox_min"), r.get("bbox_max")] for r in ledger["windows"]],
            "issues": ledger["issues"], "counts": ledger["counts"], "associations": _assoc(ledger)}


def _fault(clean, ledger, kind):
    prefix = {"void": "missing host", "fill": "missing fill", "contain": "missing containment"}[kind]
    flagged = [i for i in ledger["issues"] if i.startswith(prefix)]
    before, after = _assoc(clean), _assoc(ledger)
    delta = {"void": "hosts", "fill": "fills", "contain": "contained"}[kind]
    others = {"hosts", "fills", "contained"} - {delta}
    ok = len(flagged) == 1 and _gids(clean) == _gids(ledger) and before[delta] - after[delta] == 1 and all(before[k] == after[k] for k in others)
    return {"fault_ok": bool(ok), "flagged": flagged, "associations": after, "clean_associations": before}


def _time_specs(texts, repeats):
    out = {}
    for name, raw in texts.items():
        samples = []
        for _ in range(repeats):
            t0 = time.perf_counter()
            Spec.model_validate_json(raw).expanded_floors()
            samples.append(time.perf_counter() - t0)
        out[name] = {"samples": samples, "median": _median(samples)}
    return out


def run(inputs, out, repeats=3):
    if repeats < 3:
        raise ValueError("repeats must be >= 3")
    inputs, out = Path(inputs), Path(out)
    os.mkdir(out)
    (out / "ifc").mkdir()
    (out / "ledgers").mkdir()
    found = sorted(inputs.glob("*/spec.json"))
    if not found:
        raise FileNotFoundError(f"no */spec.json under {inputs}")
    texts = {p.parent.name: p.read_bytes() for p in found}
    specs = {name: Spec.model_validate_json(raw) for name, raw in texts.items()}
    cases = []
    for name, spec in specs.items():
        for milli, units in ((False, "m"), (True, "mm")):
            ifc_path = out / "ifc" / f"{name}-{units}.ifc"
            write_ifc(spec, ifc_path, milli)
            samples, ledger = [], None
            for _ in range(repeats):
                t0 = time.perf_counter()
                ledger = read_ledger(ifc_path)
                samples.append(time.perf_counter() - t0)
            _dump(out / "ledgers" / f"{name}-{units}.json", ledger)
            cases.append({"id": name, "units": units, "arm": "clean", "ifc": ifc_path.relative_to(out).as_posix(),
                          "ledger": f"ledgers/{name}-{units}.json", "intake_s": samples, "intake_median_s": _median(samples),
                          "samples": _samples(ledger), **compare(spec, ledger)})
            for arm, kind in ARMS:
                neg = out / "ifc" / f"{name}-{units}-{arm}.ifc"
                _punch(ifc_path, neg, kind)
                t0 = time.perf_counter()
                led = read_ledger(neg)
                elapsed = time.perf_counter() - t0
                _dump(out / "ledgers" / f"{name}-{units}-{arm}.json", led)
                cases.append({"id": name, "units": units, "arm": arm, "ifc": neg.relative_to(out).as_posix(),
                              "ledger": f"ledgers/{name}-{units}-{arm}.json", "intake_s": [elapsed], "intake_median_s": elapsed,
                              "samples": _samples(led), "global_ids_kept": _gids(ledger) == _gids(led), **_fault(ledger, led, kind)})
    base, bp = None, inputs / "baseline.json"
    if bp.exists():
        base = {"present": True, "sha256": _sha(bp)}
        if bp.stat().st_size <= 20000:
            base["body"] = json.loads(bp.read_text(encoding="utf-8"))
    results = {"delivery_passed": False, "synthetic": True, "speedup_claimed": False, "unsupported": UNSUPPORTED,
               "tolerances": {"coord_m": TOL_M, "volume_m3": TOL_V},
               "spec_sha256": {name: hashlib.sha256(raw).hexdigest() for name, raw in texts.items()},
               "spec_validate_s": _time_specs(texts, repeats), "baseline": base, "cases": cases}
    _dump(out / "results.json", results)
    return results


def main(argv=None):
    p = argparse.ArgumentParser(description="Synthetic IFC4 semantic-loss probe")
    p.add_argument("--inputs", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--repeats", type=int, default=3)
    args = p.parse_args(argv)
    run(args.inputs, args.out, args.repeats)
    print(Path(args.out) / "results.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
