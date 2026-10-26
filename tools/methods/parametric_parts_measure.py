"""Measure one parametric-part FBX against a spec bbox.

new-case: methods-catalog stand-in for run_variant.py (#706 absent) — build time, triangles, xView 2/5 mm, dimension error, FBX readback.

Field names of one row: part, tool, kind, build_s, triangles, xview_vertices_2mm, xview_faces_5mm,
dimension_error_mm, fbx_readback_ok, topology_valid, spec_extents_mm, measured_extents_mm, status.
xView is dt_ai.ops.inv_xview at 2 mm vertices and 5 mm faces (<= at the threshold).
Dimension error is the max absolute difference of the three bbox extents, in millimetres, after
FBX units are brought to metres (UnitScaleFactor is centimetres, so metres = file_units * factor/100;
no factor means the file is already in metres). Model Lcl Scaling and Lcl Translation are applied
before the unit scale. Non-zero Lcl Rotation, a parent other than the scene root, and a
Geometry used by more than one Model are rejected. A row is written only when readback is
ok. Catalog rows pass --dcc-objects and --dcc-triangles from a fresh DCC import; then
fbx_readback_ok also requires at least one imported object and the same triangle count.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import struct
import sys
import tempfile
import zlib
from pathlib import Path

_MAGIC = b"Kaydara FBX Binary  \x00\x1a\x00"
_AREA_EPS_M2 = 1e-12


class ReadError(Exception):
    """The FBX could not be read as a mesh."""


def _same_file(a, b) -> bool:
    """True when both paths name one file (hard link, or the same path)."""
    try:
        if os.path.samefile(a, b):
            return True
    except OSError:
        pass
    try:
        left = os.stat(a)
        right = os.stat(b)
    except OSError:
        return False
    return left.st_ino != 0 and left.st_dev == right.st_dev and left.st_ino == right.st_ino


def _aliases(a, b) -> bool:
    if os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b)):
        return True
    return _same_file(a, b)


def _unit_scale(text: str):
    for line in text.splitlines():
        if "UnitScaleFactor" not in line:
            continue
        for tok in reversed(line.replace(",", " ").split()):
            try:
                return float(tok)
            except ValueError:
                continue
    return None


def _number_lists(text: str, key: str):
    token = key + ":"
    found = []
    start = 0
    while True:
        i = text.find(token, start)
        if i < 0:
            break
        a = text.find("a:", i)
        end = text.find("}", a if a >= 0 else i)
        if a < 0 or end < 0:
            raise ReadError("unreadable FBX: broken " + key)
        body = text[a + 2:end]
        nums = []
        for part in body.replace("\n", " ").replace("\t", " ").replace(",", " ").split():
            try:
                nums.append(float(part) if key == "Vertices" else int(part, 10))
            except ValueError as exc:
                raise ReadError("unreadable FBX: bad " + key) from exc
        found.append(nums)
        start = end + 1
    return found


def _triangles_from_indices(indices):
    if not indices:
        raise ReadError("malformed polygon: empty PolygonVertexIndex")
    tris = []
    poly = []
    for raw in indices:
        idx = int(raw)
        if idx < 0:
            poly.append(~idx)
            if len(poly) < 3 or len(set(poly)) < 3:
                raise ReadError("malformed polygon")
            for k in range(1, len(poly) - 1):
                tris.append((poly[0], poly[k], poly[k + 1]))
            poly = []
        else:
            poly.append(idx)
    if poly:
        raise ReadError("malformed polygon: unterminated PolygonVertexIndex")
    if not tris:
        raise ReadError("malformed polygon: empty PolygonVertexIndex")
    return tris


def _lcl_from_lines(span: str, key: str, default):
    found = None
    for line in span.splitlines():
        if key not in line:
            continue
        nums = []
        for tok in line.replace(",", " ").split():
            try:
                nums.append(float(tok))
            except ValueError:
                continue
        if len(nums) < 3:
            raise ReadError("malformed FBX: " + key)
        found = nums[-3:]
    return list(default) if found is None else found


def _ascii_scene(text: str):
    marks = []
    for match in re.finditer(r"(?m)^\s*(Geometry|Model):\s*(-?\d+)", text):
        marks.append((match.start(), match.group(1), int(match.group(2))))
    geoms = {}
    models = {}
    for index, (pos, kind, ident) in enumerate(marks):
        end = marks[index + 1][0] if index + 1 < len(marks) else len(text)
        span = text[pos:end]
        if kind == "Geometry":
            v_lists = _number_lists(span, "Vertices")
            i_lists = _number_lists(span, "PolygonVertexIndex")
            if len(v_lists) != 1 or len(i_lists) != 1:
                raise ReadError("malformed FBX: incomplete geometry inventory")
            geoms[ident] = (v_lists[0], i_lists[0])
        else:
            models[ident] = (
                _lcl_from_lines(span, "Lcl Translation", (0.0, 0.0, 0.0)),
                _lcl_from_lines(span, "Lcl Rotation", (0.0, 0.0, 0.0)),
                _lcl_from_lines(span, "Lcl Scaling", (1.0, 1.0, 1.0)),
            )
    links = [(int(m.group(1)), int(m.group(2))) for m in re.finditer(r'C:\s*"OO"\s*,\s*(-?\d+)\s*,\s*(-?\d+)', text)]
    return geoms, models, links


def _transform_vertices(flat, unit_scale, translation, rotation, scaling):
    if any(abs(float(v)) > 1e-8 for v in rotation):
        raise ReadError("unsupported Lcl Rotation")
    tx, ty, tz = (float(v) for v in translation)
    sx, sy, sz = (float(v) for v in scaling)
    if not all(math.isfinite(v) for v in (tx, ty, tz, sx, sy, sz, unit_scale)):
        raise ReadError("non-finite transform")
    if len(flat) % 3 != 0:
        raise ReadError("unreadable FBX: vertex count is not a multiple of 3")
    verts = []
    for i in range(0, len(flat), 3):
        verts.append((
            (float(flat[i]) * sx + tx) * unit_scale,
            (float(flat[i + 1]) * sy + ty) * unit_scale,
            (float(flat[i + 2]) * sz + tz) * unit_scale,
        ))
    return verts


def _assemble(geoms, models, links, unit_scale):
    if not geoms:
        raise ReadError("unreadable FBX")
    geom_parent = {}
    model_parents = {}
    for child, parent in links:
        if child in geoms and parent in models:
            if child in geom_parent:
                raise ReadError("unsupported instance")
            geom_parent[child] = parent
        elif child in models:
            model_parents.setdefault(child, []).append(parent)
    verts = []
    tris = []
    for gid, (flat, indices) in geoms.items():
        if gid not in geom_parent:
            raise ReadError("malformed FBX: Geometry has no Model connection")
        mid = geom_parent[gid]
        parents = model_parents.get(mid, [])
        if len(parents) > 1:
            raise ReadError("unsupported instance")
        if parents and int(parents[0]) != 0:
            raise ReadError("unsupported parent transform")
        translation, rotation, scaling = models[mid]
        local = _transform_vertices(flat, unit_scale, translation, rotation, scaling)
        base = len(verts)
        verts.extend(local)
        for a, b, c in _triangles_from_indices(indices):
            if not (0 <= a < len(local) and 0 <= b < len(local) and 0 <= c < len(local)):
                raise ReadError("malformed polygon: index out of range")
            tris.append((a + base, b + base, c + base))
    return verts, tris


def _read_ascii(text: str):
    if "Vertices:" not in text or "PolygonVertexIndex:" not in text:
        raise ReadError("unreadable FBX")
    factor = _unit_scale(text)
    scale = 1.0 if factor is None else factor / 100.0
    if not math.isfinite(scale) or scale <= 0:
        raise ReadError("unreadable FBX: UnitScaleFactor")
    return _assemble(*_ascii_scene(text), scale)


def _read_prop(data, offset):
    if offset >= len(data):
        raise ReadError("unreadable FBX")
    kind = chr(data[offset])
    offset += 1
    scalars = {"Y": "<h", "C": "<?", "I": "<i", "F": "<f", "D": "<d", "L": "<q"}
    if kind in scalars:
        fmt = scalars[kind]
        size = struct.calcsize(fmt)
        value = struct.unpack_from(fmt, data, offset)[0]
        return value, offset + size
    if kind in ("S", "R"):
        (n,) = struct.unpack_from("<I", data, offset)
        offset += 4
        raw = data[offset:offset + n]
        offset += n
        return (raw.decode("latin1") if kind == "S" else raw), offset
    if kind in "fdiilb":
        count, encoding, clen = struct.unpack_from("<III", data, offset)
        offset += 12
        blob = data[offset:offset + clen]
        offset += clen
        if encoding == 1:
            blob = zlib.decompress(blob)
        elif encoding != 0:
            raise ReadError("unreadable FBX: array encoding")
        fmts = {"f": "<f", "d": "<d", "i": "<i", "l": "<q", "b": "<?"}
        fmt = fmts[kind]
        size = struct.calcsize(fmt)
        if kind == "c":
            values = list(blob[:count])
        else:
            if len(blob) < count * size:
                raise ReadError("unreadable FBX: short array")
            values = list(struct.unpack("<" + fmt[1] * count, blob[:count * size]))
        return values, offset
    raise ReadError("unreadable FBX: property " + kind)


def _read_node(data, offset, version):
    hlen = 13 if version < 7500 else 25
    if offset + hlen > len(data):
        raise ReadError("unreadable FBX")
    if version < 7500:
        end, nprops, _proplen = struct.unpack_from("<III", data, offset)
    else:
        end, nprops, _proplen = struct.unpack_from("<QQQ", data, offset)
    name_len = data[offset + hlen - 1]
    offset += hlen
    if end == 0 and nprops == 0 and name_len == 0:
        return None, offset
    name = data[offset:offset + name_len].decode("latin1", "replace")
    offset += name_len
    props = []
    for _ in range(nprops):
        prop, offset = _read_prop(data, offset)
        props.append(prop)
    children = []
    if offset < end:
        while offset < end:
            child, offset = _read_node(data, offset, version)
            if child is None:
                break
            children.append(child)
        offset = end
    return (name, props, children), offset


def _walk_binary(data):
    if not data.startswith(_MAGIC) or len(data) < 27:
        raise ReadError("unreadable FBX")
    version = struct.unpack_from("<I", data, 23)[0]
    offset = 27
    nodes = []
    while offset < len(data):
        node, offset = _read_node(data, offset, version)
        if node is None:
            break
        nodes.append(node)
    return nodes


def _find_factor(nodes):
    for name, _props, children in nodes:
        if name != "GlobalSettings":
            continue
        for cname, _cprops, kids in children:
            if cname != "Properties70":
                continue
            for pname, pprops, _ in kids:
                if pname == "P" and pprops and pprops[0] == "UnitScaleFactor":
                    for item in reversed(pprops):
                        if isinstance(item, (int, float)) and not isinstance(item, bool):
                            return float(item)
    return None


def _vec_from_props(props, default):
    nums = []
    for item in props:
        if isinstance(item, bool):
            continue
        if isinstance(item, (int, float)):
            nums.append(float(item))
    if len(nums) < 3:
        return list(default)
    return nums[-3:]


def _binary_scene(nodes):
    geoms = {}
    models = {}
    links = []
    for name, _props, children in nodes:
        if name == "Objects":
            for oname, oprops, ochildren in children:
                if oname == "Geometry" and oprops:
                    verts = indices = None
                    for cname, cprops, _ in ochildren:
                        if cname == "Vertices" and cprops and isinstance(cprops[0], list):
                            verts = cprops[0]
                        elif cname == "PolygonVertexIndex" and cprops and isinstance(cprops[0], list):
                            indices = cprops[0]
                    if verts is None and indices is None:
                        continue
                    if verts is None or indices is None:
                        raise ReadError("malformed FBX: incomplete geometry inventory")
                    geoms[int(oprops[0])] = ([float(x) for x in verts], [int(i) for i in indices])
                elif oname == "Model" and oprops:
                    translation = [0.0, 0.0, 0.0]
                    rotation = [0.0, 0.0, 0.0]
                    scaling = [1.0, 1.0, 1.0]
                    for cname, _cprops, kids in ochildren:
                        if cname != "Properties70":
                            continue
                        for pname, pprops, _ in kids:
                            if pname != "P" or not pprops:
                                continue
                            if pprops[0] == "Lcl Translation":
                                translation = _vec_from_props(pprops, translation)
                            elif pprops[0] == "Lcl Rotation":
                                rotation = _vec_from_props(pprops, rotation)
                            elif pprops[0] == "Lcl Scaling":
                                scaling = _vec_from_props(pprops, scaling)
                    models[int(oprops[0])] = (translation, rotation, scaling)
        elif name == "Connections":
            for cname, cprops, _ in children:
                if cname == "C" and len(cprops) >= 3 and cprops[0] == "OO":
                    links.append((int(cprops[1]), int(cprops[2])))
    return geoms, models, links


def _read_binary(data: bytes):
    nodes = _walk_binary(data)
    factor = _find_factor(nodes)
    scale = 1.0 if factor is None else factor / 100.0
    if not math.isfinite(scale) or scale <= 0:
        raise ReadError("unreadable FBX: UnitScaleFactor")
    return _assemble(*_binary_scene(nodes), scale)


def read_mesh(path: Path):
    """Vertices in metres and triangle index triples. Raises ReadError when the file is not a mesh FBX."""
    try:
        blob = path.read_bytes()
    except OSError as exc:
        raise ReadError("unreadable FBX") from exc
    if blob.startswith(_MAGIC):
        return _read_binary(blob)
    try:
        text = blob.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReadError("unreadable FBX") from exc
    return _read_ascii(text)


def _finite(verts) -> bool:
    return all(math.isfinite(c) for v in verts for c in v)


def _bbox_mm(verts):
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    extents = ((max(xs) - min(xs)) * 1000.0, (max(ys) - min(ys)) * 1000.0, (max(zs) - min(zs)) * 1000.0)
    if not all(math.isfinite(v) for v in extents):
        return None
    return extents


def _topology(verts, tris) -> bool:
    if not tris:
        return False
    edges = {}
    limit = (2.0 * _AREA_EPS_M2) ** 2
    n = len(verts)
    for a, b, c in tris:
        if not (0 <= a < n and 0 <= b < n and 0 <= c < n) or len({a, b, c}) < 3:
            return False
        ax, ay, az = verts[a]
        bx, by, bz = verts[b]
        cx, cy, cz = verts[c]
        ux, uy, uz = bx - ax, by - ay, bz - az
        vx, vy, vz = cx - ax, cy - ay, cz - az
        nx = uy * vz - uz * vy
        ny = uz * vx - ux * vz
        nz = ux * vy - uy * vx
        if nx * nx + ny * ny + nz * nz <= limit:
            return False
        for edge in ((a, b), (b, c), (c, a)):
            key = (edge[0], edge[1]) if edge[0] < edge[1] else (edge[1], edge[0])
            edges[key] = edges.get(key, 0) + 1
    return bool(edges) and all(count == 2 for count in edges.values())


def _xview(verts, tris):
    import numpy as np

    from dt_ai.ops.inv_xview import XviewTolerance, part_report
    from dt_ai.ops.invariants import Mesh

    mesh = Mesh(vertices=np.asarray(verts, dtype=float), triangles=np.asarray(tris, dtype=int))
    report = part_report("part", mesh, XviewTolerance())
    return len(report.vertex_pairs), len(report.xview_faces)


def _emit(row) -> None:
    print(json.dumps(row, ensure_ascii=False))


def _base_row(args, status, ok):
    build_s = None if args.build_s is None else args.build_s
    return {
        "part": args.part,
        "tool": args.tool,
        "kind": args.kind,
        "build_s": build_s,
        "triangles": None,
        "xview_vertices_2mm": None,
        "xview_faces_5mm": None,
        "dimension_error_mm": None,
        "fbx_readback_ok": ok,
        "topology_valid": False,
        "spec_extents_mm": [args.spec_mm[0], args.spec_mm[1], args.spec_mm[2]],
        "measured_extents_mm": None,
        "status": status,
    }


def _publish(out: Path, text: str, protected) -> None:
    """Publish text by exclusively creating a temp file, then renaming it onto out.

    A pre-existing sibling such as out + '.partial' is never opened or removed.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    for src in protected:
        if _aliases(out, src):
            raise OSError("output path equals the input")
    fd, name = tempfile.mkstemp(prefix=out.name + ".", suffix=".tmp", dir=str(out.parent))
    tmp = Path(name)
    try:
        for src in list(protected):
            if _same_file(tmp, src):
                raise OSError("temporary file aliases the input")
        if out.exists() and _same_file(tmp, out):
            raise OSError("temporary file aliases the output")
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, out)
    except Exception:
        if tmp.exists():
            os.remove(tmp)
        raise


def measure_file(args) -> int:
    fbx = Path(args.fbx)
    out = Path(args.out)
    if _aliases(fbx, out):
        print(f"refusing to write {out}: output path equals the input", file=sys.stderr)
        return 2
    if (args.dcc_objects is None) != (args.dcc_triangles is None):
        print("refusing DCC readback without both object and triangle counts", file=sys.stderr)
        return 2
    try:
        verts, tris = read_mesh(fbx)
    except (ReadError, ValueError, OSError, zlib.error, struct.error) as exc:
        row = _base_row(args, "not measured: " + str(exc).splitlines()[0], False)
        _emit(row)
        return 1
    if not verts or not _finite(verts):
        row = _base_row(args, "not measured: non-finite coordinate", False)
        row["triangles"] = len(tris)
        _emit(row)
        return 1
    if not tris:
        row = _base_row(args, "not measured: empty mesh", False)
        row["triangles"] = 0
        _emit(row)
        return 1
    try:
        xv, xf = _xview(verts, tris)
    except (ValueError, TypeError) as exc:
        row = _base_row(args, "not measured: " + str(exc).splitlines()[0], False)
        row["triangles"] = len(tris)
        _emit(row)
        return 1
    measured = _bbox_mm(verts)
    if measured is None:
        row = _base_row(args, "not measured: non-finite extent", False)
        row["triangles"] = len(tris)
        _emit(row)
        return 1
    error = max(abs(measured[i] - args.spec_mm[i]) for i in range(3))
    if not math.isfinite(error):
        row = _base_row(args, "not measured: non-finite dimension error", False)
        _emit(row)
        return 1
    dcc_ok = True
    if args.dcc_objects is not None:
        dcc_ok = args.dcc_objects >= 1 and args.dcc_triangles == len(tris)
    xview_ok = xv == 0 and xf == 0
    ok = xview_ok and dcc_ok
    if not dcc_ok:
        status = f"not measured: DCC readback objects={args.dcc_objects} triangles={args.dcc_triangles}"
    elif not xview_ok:
        status = "not measured: xview at 2 mm / 5 mm threshold"
    else:
        status = "measured"
    row = _base_row(args, status, ok)
    row["triangles"] = len(tris)
    row["xview_vertices_2mm"] = xv
    row["xview_faces_5mm"] = xf
    row["dimension_error_mm"] = error
    row["topology_valid"] = _topology(verts, tris)
    row["measured_extents_mm"] = [measured[0], measured[1], measured[2]]
    if args.dcc_objects is not None:
        row["dcc_objects"] = args.dcc_objects
        row["dcc_triangles"] = args.dcc_triangles
        row["dcc_tool"] = args.dcc_tool
    _emit(row)
    if not ok:
        return 1
    try:
        _publish(out, json.dumps(row, ensure_ascii=False, indent=2) + "\n", [fbx])
    except OSError as exc:
        print(f"refusing to write {out}: {exc}", file=sys.stderr)
        return 2
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Measure a parametric-part FBX against spec extents")
    parser.add_argument("--fbx", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--spec-mm", nargs=3, type=float, required=True)
    parser.add_argument("--part", default="part")
    parser.add_argument("--tool", default="unknown")
    parser.add_argument("--kind", default="build", choices=("build", "param_change"))
    parser.add_argument("--build-s", type=float, default=None)
    parser.add_argument("--dcc-objects", type=int, default=None)
    parser.add_argument("--dcc-triangles", type=int, default=None)
    parser.add_argument("--dcc-tool", default=None)
    args = parser.parse_args(argv)
    if any(not math.isfinite(v) for v in args.spec_mm):
        print("refusing non-finite spec extents", file=sys.stderr)
        return 2
    return measure_file(args)


if __name__ == "__main__":
    sys.exit(main())
