"""Analytic meshes for the two parametric parts, in metres.

new-case: bench and KPP1 aerator recipes measured for issue #713.

Bench overall box is the catalogue spec row 49 (Скамейка стальная «Андромеда»): 1.8 x 0.5 x 0.72 m.
The aerator overall box is the abutted KPP1 TN_Аэратор stack: flange diameter 0.390 m and height
0.064 m, pipe diameter 0.100 m and length 0.110 m, cap diameter 0.180 m and height 0.150 m.
"""
from __future__ import annotations

import array
import json
import math
import os
import struct
import subprocess
import sys
import tempfile

BENCH_LENGTH_M = 1.8
BENCH_WIDTH_M = 0.5
BENCH_HEIGHT_M = 0.72
BENCH_LENGTH_PARAM_M = 1.9

FLANGE_R_M = 0.195
FLANGE_H_M = 0.064
PIPE_R_M = 0.05
PIPE_LENGTH_M = 0.110
CAP_R_M = 0.09
CAP_H_M = 0.150
AERATOR_SIDES = 16
PIPE_LENGTH_PARAM_M = 0.210


def bench_profile(width: float, height: float):
    """Closed YZ silhouette. The bbox of the profile is exactly width by height."""
    leg = 0.06
    back = 0.04
    seat_top = 0.45
    seat_under = 0.40
    if not (0 < leg < width / 2 and 0 < back < width and 0 < seat_under < seat_top < height):
        raise ValueError("bench profile does not fit the spec box")
    return [
        (0.0, 0.0),
        (leg, 0.0),
        (leg, seat_under),
        (width - leg, seat_under),
        (width - leg, 0.0),
        (width, 0.0),
        (width, height),
        (width - back, height),
        (width - back, seat_top),
        (0.0, seat_top),
    ]


def _ring_fan(origin: int, ring: list[int], reverse: bool):
    """Triangles from a centre vertex to every edge of a closed ring."""
    tris = []
    n = len(ring)
    for i in range(n):
        j = (i + 1) % n
        tris.append((origin, ring[j], ring[i]) if reverse else (origin, ring[i], ring[j]))
    return tris


def _ear_clip(profile):
    """Triangles of a simple polygon (indices into profile). Concave silhouettes stay non-overlapping."""
    n = len(profile)
    area = 0.0
    for i, (y, z) in enumerate(profile):
        y2, z2 = profile[(i + 1) % n]
        area += y * z2 - y2 * z
    order = list(range(n))
    if area < 0:
        order.reverse()

    def inside(p, a, b, c):
        cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        if cross <= 1e-15:
            return False
        w0 = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
        w1 = (c[0] - b[0]) * (p[1] - b[1]) - (c[1] - b[1]) * (p[0] - b[0])
        w2 = (a[0] - c[0]) * (p[1] - c[1]) - (a[1] - c[1]) * (p[0] - c[0])
        return w0 > 1e-15 and w1 > 1e-15 and w2 > 1e-15

    tris = []
    guard = 0
    while len(order) > 3:
        guard += 1
        if guard > n * n:
            raise ValueError("bench profile did not triangulate")
        clipped = False
        for i in range(len(order)):
            i0, i1, i2 = order[(i - 1) % len(order)], order[i], order[(i + 1) % len(order)]
            a, b, c = profile[i0], profile[i1], profile[i2]
            cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if cross <= 1e-15:
                continue
            if any(inside(profile[j], a, b, c) for j in order if j not in (i0, i1, i2)):
                continue
            tris.append((i0, i1, i2))
            del order[i]
            clipped = True
            break
        if not clipped:
            raise ValueError("bench profile has no ear")
    tris.append((order[0], order[1], order[2]))
    return tris


def _quads(a: list[int], b: list[int]):
    tris = []
    n = len(a)
    for i in range(n):
        j = (i + 1) % n
        tris.append((a[i], a[j], b[j]))
        tris.append((a[i], b[j], b[i]))
    return tris


def extrude_profile(profile, length: float):
    """Extrude a YZ profile along +X from 0 to length. One closed shell."""
    n = len(profile)
    verts = [(0.0, y, z) for y, z in profile] + [(length, y, z) for y, z in profile]
    start = list(range(n))
    end = list(range(n, 2 * n))
    tris = list(_quads(start, end))
    for a, b, c in _ear_clip(profile):
        tris.append((start[a], start[c], start[b]))
        tris.append((end[a], end[b], end[c]))
    return verts, tris


def bench_mesh(length_m: float = BENCH_LENGTH_M, width_m: float = BENCH_WIDTH_M, height_m: float = BENCH_HEIGHT_M):
    return extrude_profile(bench_profile(width_m, height_m), length_m)


def _ring(z: float, radius: float, sides: int):
    return [
        (radius * math.cos(2.0 * math.pi * i / sides), radius * math.sin(2.0 * math.pi * i / sides), z)
        for i in range(sides)
    ]


def aerator_mesh(pipe_length_m: float = PIPE_LENGTH_M, sides: int = AERATOR_SIDES):
    """Stepped revolve. A vertex sits on +X, so the bbox X/Y extents are the flange diameter."""
    z_flange = FLANGE_H_M
    z_pipe = FLANGE_H_M + pipe_length_m
    z_top = z_pipe + CAP_H_M
    rings = [
        _ring(0.0, FLANGE_R_M, sides),
        _ring(z_flange, FLANGE_R_M, sides),
        _ring(z_flange, PIPE_R_M, sides),
        _ring(z_pipe, PIPE_R_M, sides),
        _ring(z_pipe, CAP_R_M, sides),
        _ring(z_top, CAP_R_M, sides),
    ]
    verts = [(-0.0, 0.0, 0.0), (0.0, 0.0, z_top)]
    offsets = []
    for ring in rings:
        offsets.append(list(range(len(verts), len(verts) + sides)))
        verts.extend(ring)
    bottom, top = 0, 1
    outer0, outer1, inner1, inner2, cap0, cap1 = offsets
    tris = []
    tris.extend(_ring_fan(bottom, outer0, reverse=True))
    tris.extend(_quads(outer0, outer1))
    tris.extend(_quads(outer1, inner1))
    tris.extend(_quads(inner1, inner2))
    tris.extend(_quads(inner2, cap0))
    tris.extend(_quads(cap0, cap1))
    tris.extend(_ring_fan(top, cap1, reverse=False))
    return verts, tris


_FBX_MAGIC = b"Kaydara FBX Binary  \x00\x1a\x00"
_FBX_FOOTER_A = bytes.fromhex("fabcab09d0c8d466b176fb831cf7267e")
_FBX_FOOTER_B = bytes.fromhex("f85a8c6adef5d97eece90ce3758f290b")


def _prop_int(value):
    return b"I" + struct.pack("<i", int(value))


def _prop_int64(value):
    return b"L" + struct.pack("<q", int(value))


def _prop_double(value):
    return b"D" + struct.pack("<d", float(value))


def _prop_bool(value):
    return b"C" + struct.pack("<?", bool(value))


def _prop_str(value):
    raw = value.encode("latin1")
    return b"S" + struct.pack("<I", len(raw)) + raw


def _prop_array(kind, typecode, values):
    buf = array.array(typecode, values)
    if sys.byteorder != "little":
        buf.byteswap()
    blob = buf.tobytes()
    return kind + struct.pack("<III", len(buf), 0, len(blob)) + blob


class _FbxNode:
    def __init__(self, name, props, children, force_null=False):
        self.name = name
        self.props = props
        self.children = children
        self.force_null = force_null


def _pack_fbx_node(node, start):
    name = node.name.encode("ascii")
    prop_blob = b"".join(node.props)
    cursor = start + 13 + len(name) + len(prop_blob)
    child_blobs = []
    for child in node.children:
        blob, cursor = _pack_fbx_node(child, cursor)
        child_blobs.append(blob)
    body = prop_blob + b"".join(child_blobs)
    if node.children or node.force_null:
        body += b"\x00" * 13
        cursor += 13
    end = start + 13 + len(name) + len(body)
    header = struct.pack("<III", end, len(node.props), len(prop_blob)) + bytes([len(name)])
    return header + name + body, end


def _p_node(*props):
    return _FbxNode("P", list(props), [])


def _binary_fbx(verts, tris) -> bytes:
    """FBX 7400 binary: one Mesh Model, its Geometry, and OO connections to the root.

    Vertices stay in metres. UnitScaleFactor 100 matches the Max control files
    (one file unit is one metre). ASCII FBX is not used: Blender 5.1 rejects it,
    and a Geometry node with no Model imported as zero objects in 3ds Max.
    """
    flat = []
    for x, y, z in verts:
        flat.extend((float(x), float(y), float(z)))
    indices = []
    for a, b, c in tris:
        indices.extend((int(a), int(b), ~int(c)))
    # Low object ids are easy to confuse with the scene root. Max imports the
    # control files, whose ids are large and which carry Definitions.
    geometry_id = 4_000_000_001
    model_id = 4_000_000_002
    document_id = 4_000_000_003
    lcl_t = _p_node(_prop_str("Lcl Translation"), _prop_str("Lcl Translation"), _prop_str(""), _prop_str("A"), _prop_double(0.0), _prop_double(0.0), _prop_double(0.0))
    lcl_r = _p_node(_prop_str("Lcl Rotation"), _prop_str("Lcl Rotation"), _prop_str(""), _prop_str("A"), _prop_double(0.0), _prop_double(0.0), _prop_double(0.0))
    lcl_s = _p_node(_prop_str("Lcl Scaling"), _prop_str("Lcl Scaling"), _prop_str(""), _prop_str("A"), _prop_double(1.0), _prop_double(1.0), _prop_double(1.0))
    roots = [
        _FbxNode("FBXHeaderExtension", [], [
            _FbxNode("FBXHeaderVersion", [_prop_int(1003)], []),
            _FbxNode("FBXVersion", [_prop_int(7400)], []),
            _FbxNode("EncryptionType", [_prop_int(0)], []),
            _FbxNode("Creator", [_prop_str("AGR parametric parts")], []),
        ]),
        _FbxNode("Creator", [_prop_str("AGR parametric parts")], []),
        _FbxNode("GlobalSettings", [], [
            _FbxNode("Version", [_prop_int(1000)], []),
            _FbxNode("Properties70", [], [
                _p_node(_prop_str("UpAxis"), _prop_str("int"), _prop_str("Integer"), _prop_str(""), _prop_int(2)),
                _p_node(_prop_str("UpAxisSign"), _prop_str("int"), _prop_str("Integer"), _prop_str(""), _prop_int(1)),
                _p_node(_prop_str("FrontAxis"), _prop_str("int"), _prop_str("Integer"), _prop_str(""), _prop_int(1)),
                _p_node(_prop_str("FrontAxisSign"), _prop_str("int"), _prop_str("Integer"), _prop_str(""), _prop_int(-1)),
                _p_node(_prop_str("CoordAxis"), _prop_str("int"), _prop_str("Integer"), _prop_str(""), _prop_int(0)),
                _p_node(_prop_str("CoordAxisSign"), _prop_str("int"), _prop_str("Integer"), _prop_str(""), _prop_int(1)),
                _p_node(_prop_str("UnitScaleFactor"), _prop_str("double"), _prop_str("Number"), _prop_str(""), _prop_double(100.0)),
                _p_node(_prop_str("OriginalUnitScaleFactor"), _prop_str("double"), _prop_str("Number"), _prop_str(""), _prop_double(100.0)),
                _p_node(_prop_str("TimeMode"), _prop_str("enum"), _prop_str(""), _prop_str(""), _prop_int(11)),
                _p_node(_prop_str("TimeSpanStart"), _prop_str("KTime"), _prop_str("Time"), _prop_str(""), _prop_int64(0)),
                _p_node(_prop_str("TimeSpanStop"), _prop_str("KTime"), _prop_str("Time"), _prop_str(""), _prop_int64(46186158000)),
            ]),
        ]),
        _FbxNode("Documents", [], [
            _FbxNode("Count", [_prop_int(1)], []),
            _FbxNode("Document", [_prop_int64(document_id), _prop_str("Scene"), _prop_str("Scene")], [
                _FbxNode("Properties70", [], [
                    _p_node(_prop_str("SourceObject"), _prop_str("object"), _prop_str(""), _prop_str("")),
                    _p_node(_prop_str("ActiveAnimStackName"), _prop_str("KString"), _prop_str(""), _prop_str(""), _prop_str("")),
                ]),
                _FbxNode("RootNode", [_prop_int64(0)], []),
            ]),
        ]),
        _FbxNode("References", [], [], force_null=True),
        _FbxNode("Definitions", [], [
            _FbxNode("Version", [_prop_int(100)], []),
            _FbxNode("Count", [_prop_int(3)], []),
            _FbxNode("ObjectType", [_prop_str("GlobalSettings")], [
                _FbxNode("Count", [_prop_int(1)], []),
            ]),
            _FbxNode("ObjectType", [_prop_str("Geometry")], [
                _FbxNode("Count", [_prop_int(1)], []),
            ]),
            _FbxNode("ObjectType", [_prop_str("Model")], [
                _FbxNode("Count", [_prop_int(1)], []),
                _FbxNode("PropertyTemplate", [_prop_str("FbxNode")], [
                    _FbxNode("Properties70", [], [lcl_t, lcl_r, lcl_s]),
                ]),
            ]),
        ]),
        _FbxNode("Objects", [], [
            _FbxNode("Geometry", [_prop_int64(geometry_id), _prop_str("Part\x00\x01Geometry"), _prop_str("Mesh")], [
                _FbxNode("GeometryVersion", [_prop_int(124)], []),
                _FbxNode("Vertices", [_prop_array(b"d", "d", flat)], []),
                _FbxNode("PolygonVertexIndex", [_prop_array(b"i", "i", indices)], []),
            ]),
            _FbxNode("Model", [_prop_int64(model_id), _prop_str("Part\x00\x01Model"), _prop_str("Mesh")], [
                _FbxNode("Version", [_prop_int(232)], []),
                _FbxNode("Properties70", [], [
                    _p_node(_prop_str("InheritType"), _prop_str("enum"), _prop_str(""), _prop_str(""), _prop_int(1)),
                    _p_node(_prop_str("DefaultAttributeIndex"), _prop_str("int"), _prop_str("Integer"), _prop_str(""), _prop_int(0)),
                    lcl_t, lcl_r, lcl_s,
                ]),
                _FbxNode("MultiLayer", [_prop_int(0)], []),
                _FbxNode("MultiTake", [_prop_int(0)], []),
                _FbxNode("Shading", [_prop_bool(True)], []),
                _FbxNode("Culling", [_prop_str("CullingOff")], []),
            ]),
        ]),
        _FbxNode("Connections", [], [
            _FbxNode("C", [_prop_str("OO"), _prop_int64(model_id), _prop_int64(0)], []),
            _FbxNode("C", [_prop_str("OO"), _prop_int64(geometry_id), _prop_int64(model_id)], []),
        ]),
        _FbxNode("Takes", [], [
            _FbxNode("Current", [_prop_str("")], []),
        ]),
    ]
    cursor = 27
    blobs = []
    for node in roots:
        blob, cursor = _pack_fbx_node(node, cursor)
        blobs.append(blob)
    footer = _FBX_FOOTER_A + (b"\x00" * 6) + struct.pack("<I", 7400) + (b"\x00" * 120) + _FBX_FOOTER_B
    return _FBX_MAGIC + struct.pack("<I", 7400) + b"".join(blobs) + (b"\x00" * 13) + footer


def _same_file(a, b) -> bool:
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


def publish_bytes(path, data: bytes, protected=()) -> None:
    """Exclusively create a temp file in the destination directory, then rename it onto path.

    Does not open or delete a pre-existing predictable sibling such as path + '.partial'.
    Refuses when path is the same file as a protected path.
    """
    dest = os.path.abspath(path)
    parent = os.path.dirname(dest)
    os.makedirs(parent, exist_ok=True)
    for src in protected:
        if _same_file(dest, src) or os.path.normcase(os.path.abspath(src)) == os.path.normcase(dest):
            raise OSError("refusing to write onto " + str(src))
    fd, name = tempfile.mkstemp(prefix=os.path.basename(dest) + ".", suffix=".tmp", dir=parent)
    try:
        for src in protected:
            if _same_file(name, src):
                raise OSError("temporary file aliases " + str(src))
        with os.fdopen(fd, "wb") as handle:
            fd = -1
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, dest)
    except Exception:
        if fd >= 0:
            os.close(fd)
        if os.path.exists(name):
            os.remove(name)
        raise


_BLENDER = r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe"


def _blender_fbx(path, verts, tris, protected=()) -> None:
    """FBX through Blender 5.1's exporter.

    A hand-built FBX 7400 binary with Model, Geometry and Connections imports in
    Blender and reads back here, but 3ds Max 2026 returns importFile false and
    zero objects. The Max and Blender control files are this exporter's binary
    (Model + Geometry + Connections) and Max imports those.
    """
    dest = os.path.abspath(path)
    parent = os.path.dirname(dest)
    os.makedirs(parent, exist_ok=True)
    for src in protected:
        if _same_file(dest, src) or os.path.normcase(os.path.abspath(src)) == os.path.normcase(dest):
            raise OSError("refusing to write onto " + str(src))
    fd, mesh_name = tempfile.mkstemp(prefix="mesh.", suffix=".json", dir=parent)
    os.close(fd)
    fd, fbx_name = tempfile.mkstemp(prefix=os.path.basename(dest) + ".", suffix=".fbx", dir=parent)
    os.close(fd)
    os.remove(fbx_name)
    fd, script_name = tempfile.mkstemp(prefix="fbx.", suffix=".py", dir=parent)
    os.close(fd)
    script = (
        "import bpy, json, sys\n"
        "argv = sys.argv[sys.argv.index('--') + 1:]\n"
        "mesh_path, fbx_path = argv\n"
        "payload = json.loads(open(mesh_path, encoding='utf-8').read())\n"
        "bpy.ops.wm.read_factory_settings(use_empty=True)\n"
        "mesh = bpy.data.meshes.new('Part')\n"
        "mesh.from_pydata(payload['verts'], [], [tuple(t) for t in payload['tris']])\n"
        "mesh.update()\n"
        "obj = bpy.data.objects.new('Part', mesh)\n"
        "bpy.context.scene.collection.objects.link(obj)\n"
        "bpy.ops.object.select_all(action='DESELECT')\n"
        "obj.select_set(True)\n"
        "bpy.context.view_layer.objects.active = obj\n"
        "bpy.ops.export_scene.fbx(filepath=fbx_path, use_selection=True, apply_unit_scale=True,\n"
        "    bake_space_transform=True, axis_forward='-Y', axis_up='Z', use_mesh_modifiers=False,\n"
        "    mesh_smooth_type='FACE', add_leaf_bones=False, object_types={'MESH'}, path_mode='STRIP')\n"
    )
    try:
        with open(mesh_name, "w", encoding="utf-8") as handle:
            json.dump({"verts": [list(v) for v in verts], "tris": [list(t) for t in tris]}, handle)
        with open(script_name, "w", encoding="utf-8") as handle:
            handle.write(script)
        proc = subprocess.run(
            [_BLENDER, "--background", "--factory-startup", "--python-exit-code", "1", "--python", script_name, "--", mesh_name, fbx_name],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode != 0 or not os.path.isfile(fbx_name):
            raise OSError("Blender FBX export failed: " + (proc.stderr or proc.stdout)[-800:])
        os.replace(fbx_name, dest)
    finally:
        for name in (mesh_name, script_name, fbx_name):
            if name and os.path.exists(name) and not (os.path.exists(dest) and _same_file(name, dest)):
                os.remove(name)


def write_ascii_fbx(path, verts, tris, protected=()) -> None:
    """Write one mesh as FBX. The name is kept for existing callers.

    Blender's exporter is used when Blender 5.1 is installed, because that is the
    binary Max imports. Otherwise the hand-built binary in _binary_fbx is written.
    Publication does not use a predictable .partial sibling.
    """
    if os.path.isfile(_BLENDER):
        _blender_fbx(path, verts, tris, protected)
    else:
        publish_bytes(path, _binary_fbx(verts, tris), protected)
