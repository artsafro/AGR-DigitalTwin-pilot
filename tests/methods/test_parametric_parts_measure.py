"""Probes for the parametric-part FBX measure script (methods catalog, issue #713).

new-case: fail-closed FBX readback for repeatable-part variants.
"""
import array
import importlib.util
import json
import math
import os
import struct
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "methods" / "parametric_parts_measure.py"


def _ascii_fbx(
    vertices,
    polygons,
    unit_scale=None,
    *,
    scene=True,
    scaling=(1.0, 1.0, 1.0),
    translation=(0.0, 0.0, 0.0),
    rotation=(0.0, 0.0, 0.0),
    geometric_translation=None,
    geometric_rotation=None,
    geometric_scaling=None,
    trailing="",
) -> str:
    flat = []
    for x, y, z in vertices:
        flat.extend((x, y, z))
    indices = []
    for poly in polygons:
        for i, vid in enumerate(poly):
            indices.append(~vid if i == len(poly) - 1 else vid)
    unit = ""
    if unit_scale is not None:
        unit = (
            "GlobalSettings:  {\n"
            "  Properties70:  {\n"
            f'    P: "UnitScaleFactor", "double", "Number", "", {unit_scale}\n'
            "  }\n"
            "}\n"
        )
    index_body = ",".join(str(v) for v in indices) + trailing
    scene_text = ""
    if scene:
        sx, sy, sz = scaling
        tx, ty, tz = translation
        rx, ry, rz = rotation
        geometric = ""
        for name, vec in (
            ("GeometricTranslation", geometric_translation),
            ("GeometricRotation", geometric_rotation),
            ("GeometricScaling", geometric_scaling),
        ):
            if vec is None:
                continue
            gx, gy, gz = vec
            geometric += f'      P: "{name}", "{name}", "", "A",{gx},{gy},{gz}\n'
        scene_text = (
            '  Model: 2, "Model::Part", "Mesh" {\n'
            "    Properties70:  {\n"
            f'      P: "Lcl Translation", "Lcl Translation", "", "A",{tx},{ty},{tz}\n'
            f'      P: "Lcl Rotation", "Lcl Rotation", "", "A",{rx},{ry},{rz}\n'
            f'      P: "Lcl Scaling", "Lcl Scaling", "", "A",{sx},{sy},{sz}\n'
            f"{geometric}"
            "    }\n"
            "  }\n"
        )
        connections = (
            "Connections:  {\n"
            '  C: "OO",2,0\n'
            '  C: "OO",1,2\n'
            "}\n"
        )
    else:
        connections = ""
    return (
        "; FBX 7.4.0 project file\n"
        f"{unit}"
        "Objects:  {\n"
        '  Geometry: 1, "Geometry::Part", "Mesh" {\n'
        f"    Vertices: *{len(flat)} {{\n"
        "      a: " + ",".join(str(v) for v in flat) + "\n"
        "    }\n"
        f"    PolygonVertexIndex: *{len(indices)} {{\n"
        "      a: " + index_body + "\n"
        "    }\n"
        "  }\n"
        f"{scene_text}"
        "}\n"
        f"{connections}"
    )


def _cube_vertices():
    return [
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (1.0, 1.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
        (1.0, 0.0, 1.0),
        (1.0, 1.0, 1.0),
        (0.0, 1.0, 1.0),
    ]


def _cube_quads():
    return [
        (0, 1, 2, 3),
        (4, 7, 6, 5),
        (0, 4, 5, 1),
        (1, 5, 6, 2),
        (2, 6, 7, 3),
        (3, 7, 4, 0),
    ]


def _run(tmp_path: Path, text: str, out_name="row.json", extra=None, fbx_name="part.fbx"):
    fbx = tmp_path / fbx_name
    fbx.write_text(text, encoding="utf-8")
    out = tmp_path / out_name
    argv = [
        sys.executable,
        str(SCRIPT),
        "--fbx",
        str(fbx),
        "--out",
        str(out),
        "--spec-mm",
        "1000",
        "1000",
        "1000",
        "--part",
        "cube",
        "--tool",
        "fixture",
        "--kind",
        "build",
        "--build-s",
        "0.25",
    ]
    if extra:
        argv.extend(extra)
    proc = subprocess.run(argv, capture_output=True, text=True, cwd=str(ROOT))
    return proc, fbx, out


_FBX_MAGIC = b"Kaydara FBX Binary  \x00\x1a\x00"
_FBX_NULL = b"\x00" * 13


def _prop_int64(value) -> bytes:
    return b"L" + struct.pack("<q", int(value))


def _prop_double(value) -> bytes:
    return b"D" + struct.pack("<d", float(value))


def _prop_str(value) -> bytes:
    raw = str(value).encode("latin1")
    return b"S" + struct.pack("<I", len(raw)) + raw


def _prop_array(kind: bytes, typecode: str, values) -> bytes:
    buf = array.array(typecode, values)
    if sys.byteorder != "little":
        buf.byteswap()
    blob = buf.tobytes()
    return kind + struct.pack("<III", len(buf), 0, len(blob)) + blob


def _pack_fbx_node(name, props, children, start):
    name_b = name.encode("ascii")
    prop_blob = b"".join(props)
    cursor = start + 13 + len(name_b) + len(prop_blob)
    child_blobs = []
    for child in children:
        blob, cursor = _pack_fbx_node(child[0], child[1], child[2], cursor)
        child_blobs.append(blob)
    body = prop_blob + b"".join(child_blobs)
    if children:
        body += _FBX_NULL
        cursor += 13
    end = start + 13 + len(name_b) + len(body)
    header = struct.pack("<III", end, len(props), len(prop_blob)) + bytes([len(name_b)])
    return header + name_b + body, end


def _p_node(name, values):
    props = [
        _prop_str(name),
        _prop_str(name),
        _prop_str(""),
        _prop_str("A"),
        _prop_double(values[0]),
        _prop_double(values[1]),
        _prop_double(values[2]),
    ]
    return ("P", props, [])


def _binary_fbx(
    vertices,
    polygons,
    unit_scale=100.0,
    *,
    scaling=(1.0, 1.0, 1.0),
    translation=(0.0, 0.0, 0.0),
    rotation=(0.0, 0.0, 0.0),
    geometric_translation=None,
    geometric_rotation=None,
    geometric_scaling=None,
) -> bytes:
    flat = []
    for x, y, z in vertices:
        flat.extend((float(x), float(y), float(z)))
    indices = []
    for poly in polygons:
        for i, vid in enumerate(poly):
            indices.append(~vid if i == len(poly) - 1 else vid)
    props = [
        _p_node("Lcl Translation", translation),
        _p_node("Lcl Rotation", rotation),
        _p_node("Lcl Scaling", scaling),
    ]
    if geometric_translation is not None:
        props.append(_p_node("GeometricTranslation", geometric_translation))
    if geometric_rotation is not None:
        props.append(_p_node("GeometricRotation", geometric_rotation))
    if geometric_scaling is not None:
        props.append(_p_node("GeometricScaling", geometric_scaling))
    nodes = [
        ("GlobalSettings", [], [
            ("Properties70", [], [
                ("P", [
                    _prop_str("UnitScaleFactor"),
                    _prop_str("double"),
                    _prop_str("Number"),
                    _prop_str(""),
                    _prop_double(unit_scale),
                ], []),
            ]),
        ]),
        ("Objects", [], [
            ("Geometry", [_prop_int64(1), _prop_str("Geometry::Part"), _prop_str("Mesh")], [
                ("Vertices", [_prop_array(b"d", "d", flat)], []),
                ("PolygonVertexIndex", [_prop_array(b"i", "i", indices)], []),
            ]),
            ("Model", [_prop_int64(2), _prop_str("Model::Part"), _prop_str("Mesh")], [
                ("Properties70", [], props),
            ]),
        ]),
        ("Connections", [], [
            ("C", [_prop_str("OO"), _prop_int64(2), _prop_int64(0)], []),
            ("C", [_prop_str("OO"), _prop_int64(1), _prop_int64(2)], []),
        ]),
    ]
    cursor = 27
    blobs = []
    for node in nodes:
        blob, cursor = _pack_fbx_node(node[0], node[1], node[2], cursor)
        blobs.append(blob)
    return _FBX_MAGIC + struct.pack("<I", 7400) + b"".join(blobs) + _FBX_NULL


def _measure_cube(tmp_path: Path, encoding: str, **kwargs):
    if encoding == "ascii":
        payload = _ascii_fbx(_cube_vertices(), _cube_quads(), unit_scale=100, **kwargs)
        return _run(tmp_path, payload)
    if encoding == "binary":
        payload = _binary_fbx(_cube_vertices(), _cube_quads(), unit_scale=100, **kwargs)
        fbx = tmp_path / "part.fbx"
        fbx.write_bytes(payload)
        out = tmp_path / "row.json"
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--fbx",
                str(fbx),
                "--out",
                str(out),
                "--spec-mm",
                "1000",
                "1000",
                "1000",
                "--part",
                "cube",
                "--tool",
                "fixture",
                "--kind",
                "build",
                "--build-s",
                "0.25",
            ],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        return proc, fbx, out
    raise AssertionError(encoding)


def _assert_rejected(proc, fbx, out, *needles):
    assert proc.returncode != 0, proc.stdout
    row = _row_from_stdout(proc)
    assert row["fbx_readback_ok"] is False
    for needle in needles:
        assert needle in row["status"], row["status"]
    assert row["status"] != "measured"
    assert not out.exists()
    assert not Path(str(out) + ".partial").exists()
    assert fbx.is_file() and fbx.stat().st_size > 0


def test_clean_cube_writes_measured_row(tmp_path):
    proc, fbx, out = _run(tmp_path, _ascii_fbx(_cube_vertices(), _cube_quads(), unit_scale=100))
    assert proc.returncode == 0, proc.stderr
    assert out.is_file()
    assert not Path(str(out) + ".partial").exists()
    row = json.loads(out.read_text(encoding="utf-8"))
    assert row["part"] == "cube"
    assert row["tool"] == "fixture"
    assert row["kind"] == "build"
    assert row["build_s"] == 0.25
    assert row["triangles"] == 12
    assert row["xview_vertices_2mm"] == 0
    assert row["xview_faces_5mm"] == 0
    assert row["dimension_error_mm"] == 0
    assert row["fbx_readback_ok"] is True
    assert row["topology_valid"] is True
    assert row["status"] == "measured"
    assert fbx.read_text(encoding="utf-8").startswith("; FBX")


def _row_from_stdout(proc):
    assert "can't open file" not in proc.stderr
    line = proc.stdout.strip().splitlines()[-1]
    return json.loads(line)


@pytest.mark.parametrize("mutate", ["nan", "inf", "empty"])
def test_bad_mesh_nonzero_and_nothing_written(tmp_path, mutate):
    verts = _cube_vertices()
    polys = _cube_quads()
    if mutate == "nan":
        verts[0] = (float("nan"), 0.0, 0.0)
    elif mutate == "inf":
        verts[1] = (float("inf"), 0.0, 0.0)
    else:
        polys = []
    proc, fbx, out = _run(tmp_path, _ascii_fbx(verts, polys))
    assert proc.returncode == 1
    row = _row_from_stdout(proc)
    assert row["fbx_readback_ok"] is False
    assert row["status"].startswith("not measured:")
    assert not out.exists()
    assert not Path(str(out) + ".partial").exists()
    assert fbx.is_file() and fbx.stat().st_size > 0


def test_exactly_at_2mm_vertex_threshold_nonzero_and_nothing_written(tmp_path):
    verts = _cube_vertices() + [(0.002, 0.0, 0.0)]
    proc, fbx, out = _run(tmp_path, _ascii_fbx(verts, _cube_quads()))
    assert proc.returncode == 1
    row = _row_from_stdout(proc)
    assert row["xview_vertices_2mm"] >= 1
    assert row["fbx_readback_ok"] is False
    assert not out.exists()
    assert not Path(str(out) + ".partial").exists()
    assert fbx.is_file()


def test_same_input_output_path_nonzero_and_input_unchanged(tmp_path):
    fbx = tmp_path / "part.fbx"
    payload = _ascii_fbx(_cube_vertices(), _cube_quads())
    fbx.write_text(payload, encoding="utf-8")
    before = fbx.read_bytes()
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--fbx",
            str(fbx),
            "--out",
            str(fbx),
            "--spec-mm",
            "1000",
            "1000",
            "1000",
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert proc.returncode == 2
    assert "refusing" in proc.stderr
    assert proc.stdout.strip() == ""
    assert fbx.read_bytes() == before
    assert not Path(str(fbx) + ".partial").exists()
    assert list(tmp_path.iterdir()) == [fbx]


def _load_measure():
    spec = importlib.util.spec_from_file_location("parametric_parts_measure", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_recipe():
    path = ROOT / "tools" / "methods" / "parametric_parts" / "mesh_recipe.py"
    spec = importlib.util.spec_from_file_location("mesh_recipe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_solidcraft():
    folder = str(ROOT / "tools" / "methods" / "parametric_parts")
    if folder not in sys.path:
        sys.path.insert(0, folder)
    path = ROOT / "tools" / "methods" / "parametric_parts" / "solidcraft_build.py"
    spec = importlib.util.spec_from_file_location("solidcraft_build", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_geometry_without_model_connection_nonzero_and_nothing_written(tmp_path):
    text = _ascii_fbx(_cube_vertices(), _cube_quads(), unit_scale=100, scene=False)
    proc, fbx, out = _run(tmp_path, text)
    assert proc.returncode != 0
    row = _row_from_stdout(proc)
    assert row["fbx_readback_ok"] is False
    assert "Model" in row["status"]
    assert not out.exists()
    assert not Path(str(out) + ".partial").exists()
    assert fbx.read_text(encoding="utf-8").startswith("; FBX")


def test_unterminated_polygon_nonzero_and_nothing_written(tmp_path):
    text = _ascii_fbx(_cube_vertices(), _cube_quads(), unit_scale=100, trailing=",0,1")
    proc, fbx, out = _run(tmp_path, text)
    assert proc.returncode != 0
    row = _row_from_stdout(proc)
    assert row["fbx_readback_ok"] is False
    assert "malformed polygon" in row["status"]
    assert not out.exists()
    assert not Path(str(out) + ".partial").exists()
    assert fbx.is_file() and fbx.stat().st_size > 0


def test_lcl_scaling_changes_world_extents(tmp_path):
    text = _ascii_fbx(_cube_vertices(), _cube_quads(), unit_scale=100, scaling=(2.0, 1.0, 1.0))
    proc, _fbx, out = _run(tmp_path, text)
    assert proc.returncode == 0, proc.stderr
    row = json.loads(out.read_text(encoding="utf-8"))
    assert row["measured_extents_mm"] == [2000.0, 1000.0, 1000.0]
    assert row["dimension_error_mm"] == 1000.0
    assert row["triangles"] == 12
    assert row["fbx_readback_ok"] is True


def test_lcl_translation_moves_vertices_and_keeps_extents(tmp_path):
    text = _ascii_fbx(_cube_vertices(), _cube_quads(), unit_scale=100, translation=(1.0, 0.0, 0.0))
    fbx = tmp_path / "part.fbx"
    fbx.write_text(text, encoding="utf-8")
    verts, tris = _load_measure().read_mesh(fbx)
    assert len(tris) == 12
    assert min(v[0] for v in verts) == pytest.approx(1.0)
    assert max(v[0] for v in verts) - min(v[0] for v in verts) == pytest.approx(1.0)


def test_lcl_rotation_rejected(tmp_path):
    text = _ascii_fbx(_cube_vertices(), _cube_quads(), unit_scale=100, rotation=(90.0, 0.0, 0.0))
    proc, fbx, out = _run(tmp_path, text)
    assert proc.returncode != 0
    row = _row_from_stdout(proc)
    assert row["fbx_readback_ok"] is False
    assert "unsupported Lcl Rotation" in row["status"]
    assert not out.exists()
    assert fbx.is_file()


@pytest.mark.parametrize("encoding", ["ascii", "binary"])
def test_nan_lcl_rotation_invalid_and_nothing_written(tmp_path, encoding):
    proc, fbx, out = _measure_cube(tmp_path, encoding, rotation=(float("nan"), 0.0, 0.0))
    _assert_rejected(proc, fbx, out, "invalid transform", "Lcl Rotation")


@pytest.mark.parametrize("encoding", ["ascii", "binary"])
def test_inf_lcl_rotation_invalid_and_nothing_written(tmp_path, encoding):
    proc, fbx, out = _measure_cube(tmp_path, encoding, rotation=(float("inf"), 0.0, 0.0))
    _assert_rejected(proc, fbx, out, "invalid transform", "Lcl Rotation")


@pytest.mark.parametrize("encoding", ["ascii", "binary"])
def test_geometric_scaling_rejected_and_nothing_written(tmp_path, encoding):
    proc, fbx, out = _measure_cube(tmp_path, encoding, geometric_scaling=(2.0, 1.0, 1.0))
    _assert_rejected(proc, fbx, out, "GeometricScaling")


@pytest.mark.parametrize("encoding", ["ascii", "binary"])
def test_nan_geometric_scaling_invalid_and_nothing_written(tmp_path, encoding):
    proc, fbx, out = _measure_cube(
        tmp_path, encoding, geometric_scaling=(float("nan"), 1.0, 1.0)
    )
    _assert_rejected(proc, fbx, out, "invalid transform", "GeometricScaling")


@pytest.mark.parametrize("encoding", ["ascii", "binary"])
def test_identity_geometric_transform_writes_measured_row(tmp_path, encoding):
    proc, fbx, out = _measure_cube(
        tmp_path,
        encoding,
        geometric_translation=(0.0, 0.0, 0.0),
        geometric_rotation=(0.0, 0.0, 0.0),
        geometric_scaling=(1.0, 1.0, 1.0),
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    row = json.loads(out.read_text(encoding="utf-8"))
    assert row["status"] == "measured"
    assert row["triangles"] == 12
    assert row["measured_extents_mm"] == [1000.0, 1000.0, 1000.0]
    assert row["dimension_error_mm"] == 0
    assert row["fbx_readback_ok"] is True
    assert fbx.is_file() and fbx.stat().st_size > 0


def test_nonfinite_transform_components_rejected(tmp_path):
    """Every component of every local and geometric vector, nan/inf/-inf, both readers."""
    properties = {
        "Lcl Translation": ("translation", (0.0, 0.0, 0.0)),
        "Lcl Rotation": ("rotation", (0.0, 0.0, 0.0)),
        "Lcl Scaling": ("scaling", (1.0, 1.0, 1.0)),
        "GeometricTranslation": ("geometric_translation", (0.0, 0.0, 0.0)),
        "GeometricRotation": ("geometric_rotation", (0.0, 0.0, 0.0)),
        "GeometricScaling": ("geometric_scaling", (1.0, 1.0, 1.0)),
    }
    bad = {
        "nan": float("nan"),
        "inf": float("inf"),
        "-inf": float("-inf"),
    }
    missed = []
    total = 0
    for encoding in ("ascii", "binary"):
        for label, (kw, identity) in properties.items():
            for axis in range(3):
                for token, value in bad.items():
                    total += 1
                    vec = list(identity)
                    vec[axis] = value
                    case = tmp_path / f"{encoding}_{kw}_{axis}_{token.replace('-', 'm')}"
                    case.mkdir()
                    proc, fbx, out = _measure_cube(case, encoding, **{kw: tuple(vec)})
                    status = ""
                    if proc.stdout.strip():
                        try:
                            status = _row_from_stdout(proc)["status"]
                        except (AssertionError, json.JSONDecodeError):
                            status = proc.stdout
                    if not (
                        proc.returncode != 0
                        and not out.exists()
                        and "invalid transform" in status
                        and label in status
                        and fbx.is_file()
                    ):
                        missed.append(f"{encoding} {label}[{axis}]={token} rc={proc.returncode} {status}")
    assert not missed, f"{total - len(missed)}/{total} rejected; first: {missed[:5]}"


def test_nonidentity_geometric_transforms_rejected(tmp_path):
    """Each geometric component off identity, both readers, names the property."""
    cases = {
        "GeometricTranslation": ("geometric_translation", (0.0, 0.0, 0.0), 5.0),
        "GeometricRotation": ("geometric_rotation", (0.0, 0.0, 0.0), 90.0),
        "GeometricScaling": ("geometric_scaling", (1.0, 1.0, 1.0), 2.0),
    }
    missed = []
    total = 0
    for encoding in ("ascii", "binary"):
        for label, (kw, identity, value) in cases.items():
            for axis in range(3):
                total += 1
                vec = list(identity)
                vec[axis] = value
                case = tmp_path / f"{encoding}_{kw}_{axis}"
                case.mkdir()
                proc, fbx, out = _measure_cube(case, encoding, **{kw: tuple(vec)})
                status = ""
                if proc.stdout.strip():
                    try:
                        status = _row_from_stdout(proc)["status"]
                    except (AssertionError, json.JSONDecodeError):
                        status = proc.stdout
                if not (
                    proc.returncode != 0
                    and not out.exists()
                    and label in status
                    and fbx.is_file()
                ):
                    missed.append(f"{encoding} {label}[{axis}] rc={proc.returncode} {status}")
    assert not missed, f"{total - len(missed)}/{total} rejected; first: {missed[:5]}"


def test_preexisting_partial_sentinel_is_not_overwritten(tmp_path):
    text = _ascii_fbx(_cube_vertices(), _cube_quads(), unit_scale=100)
    fbx = tmp_path / "part.fbx"
    fbx.write_text(text, encoding="utf-8")
    out = tmp_path / "row.json"
    sentinel = Path(str(out) + ".partial")
    sentinel.write_text("SENTINEL", encoding="utf-8")
    before = sentinel.read_bytes()
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--fbx",
            str(fbx),
            "--out",
            str(out),
            "--spec-mm",
            "1000",
            "1000",
            "1000",
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert proc.returncode == 0, proc.stderr
    assert sentinel.read_bytes() == before
    assert out.is_file()
    assert json.loads(out.read_text(encoding="utf-8"))["triangles"] == 12


def test_output_hardlink_of_input_is_refused(tmp_path):
    fbx = tmp_path / "part.fbx"
    payload = _ascii_fbx(_cube_vertices(), _cube_quads(), unit_scale=100)
    fbx.write_text(payload, encoding="utf-8")
    alias = tmp_path / "row.json"
    os.link(fbx, alias)
    before = fbx.read_bytes()
    inode = fbx.stat().st_ino
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--fbx",
            str(fbx),
            "--out",
            str(alias),
            "--spec-mm",
            "1000",
            "1000",
            "1000",
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert proc.returncode == 2
    assert "refusing" in proc.stderr
    assert proc.stdout.strip() == ""
    assert fbx.read_bytes() == before
    assert alias.stat().st_ino == inode
    assert os.path.samefile(fbx, alias)


def test_fbx_writer_sentinel_and_model_connection(tmp_path):
    recipe = _load_recipe()
    dest = tmp_path / "part.fbx"
    sentinel = Path(str(dest) + ".partial")
    sentinel.write_bytes(b"SENTINEL")
    recipe.write_ascii_fbx(dest, _cube_vertices(), [(a, b, c) for poly in _cube_quads() for a, b, c in ((poly[0], poly[1], poly[2]), (poly[0], poly[2], poly[3]))])
    assert sentinel.read_bytes() == b"SENTINEL"
    verts, tris = _load_measure().read_mesh(dest)
    assert len(tris) == 12
    assert max(v[0] for v in verts) - min(v[0] for v in verts) == pytest.approx(1.0)


def test_obj_and_fbx_hardlink_is_refused(tmp_path):
    solidcraft = _load_solidcraft()
    obj = tmp_path / "part.obj"
    obj.write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n", encoding="utf-8")
    alias = tmp_path / "part.fbx"
    os.link(obj, alias)
    before = obj.read_bytes()
    with pytest.raises(solidcraft.McpError, match="refusing"):
        solidcraft._obj_to_fbx(obj, alias)
    assert obj.read_bytes() == before
    assert os.path.samefile(obj, alias)


def test_catalog_aerator_is_stepped_flange_pipe_cap():
    path = Path(r"C:\x\methods\parametric-parts\aerator-solidcraft.fbx")
    assert path.is_file()
    verts, tris = _load_measure().read_mesh(path)
    assert len(tris) != 12
    radii = [math.hypot(x, y) for x, y, z in verts]
    assert max(radii) == pytest.approx(0.195, abs=1e-3)
    assert any(abs(radius - 0.05) < 1e-3 for radius in radii)
    assert any(z < 0.02 and abs(math.hypot(x, y) - 0.195) < 1e-3 for x, y, z in verts)
    assert any(z > 0.30 and abs(math.hypot(x, y) - 0.09) < 1e-3 for x, y, z in verts)
    extents = _load_measure()._bbox_mm(verts)
    assert extents[0] == pytest.approx(390.0, abs=0.05)
    assert extents[1] == pytest.approx(390.0, abs=0.05)
    assert extents[2] == pytest.approx(324.0, abs=0.05)


def test_timing_boundary_is_documented():
    when = (ROOT / "docs" / "methods" / "parametric-parts" / "WHEN.md").read_text(encoding="utf-8")
    variants = (ROOT / "docs" / "methods" / "parametric-parts" / "VARIANTS.md").read_text(encoding="utf-8")
    assert "build + FBX export" in when
    assert "OBJ" in variants and "FBX" in variants
    assert "Adoption:" in when


def _source_triangles(path: Path) -> int:
    _verts, tris = _load_measure().read_mesh(path)
    return len(tris)


def _max_inventory(paths, work: Path):
    script = work / "dcc_readback.py"
    listing = json.dumps([str(path) for path in paths])
    script.write_text(
        "import json\n"
        "import pymxs\n"
        "rt = pymxs.runtime\n"
        "rt.pluginManager.loadClass(rt.FBXIMP)\n"
        f"paths = {listing}\n"
        "rows = []\n"
        "for path in paths:\n"
        "    rt.resetMaxFile(rt.Name('noPrompt'))\n"
        "    imported = rt.importFile(path, rt.Name('noPrompt'), using=rt.FBXIMP)\n"
        "    objects = list(rt.objects)\n"
        "    triangles = 0\n"
        "    for obj in objects:\n"
        "        try:\n"
        "            triangles += int(rt.getNumFaces(obj))\n"
        "        except Exception:\n"
        "            pass\n"
        "    rows.append({'path': path, 'importFile': bool(imported), 'objects': len(objects), 'triangles': triangles})\n"
        "print('DCC_READBACK ' + json.dumps(rows))\n"
        "rt.resetMaxFile(rt.Name('noPrompt'))\n",
        encoding="utf-8",
    )
    out = work / "dcc-readback.json"
    proc = subprocess.run(
        [
            sys.executable,
            r"C:\Users\artsafro\hermes_kanban\scripts\dcc_batch.py",
            "max",
            "--file",
            str(script),
            "--version",
            "2026",
            "--card",
            "t_5fcef264",
            "--timeout",
            "180",
            "--wait",
            "180",
            "--max-chars",
            "200000",
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    wrapper_text = out.read_text(encoding="utf-8") if out.is_file() else proc.stdout
    wrapper = json.loads(wrapper_text)
    raw = wrapper.get("log") or ""
    marker = "DCC_READBACK "
    assert marker in raw, (wrapper.get("status"), str(raw)[-1500:])
    payload = raw.split(marker, 1)[1].splitlines()[0].strip()
    return json.loads(payload), "3ds Max 2026.3 / dcc_batch"


def _blender_inventory(paths, work: Path):
    script = work / "blender_readback.py"
    listing = json.dumps([str(path) for path in paths])
    script.write_text(
        "import bpy, json\n"
        f"paths = {listing}\n"
        "rows = []\n"
        "for path in paths:\n"
        "    bpy.ops.wm.read_factory_settings(use_empty=True)\n"
        "    result = bpy.ops.import_scene.fbx(filepath=path)\n"
        "    triangles = 0\n"
        "    meshes = [obj for obj in bpy.data.objects if obj.type == 'MESH']\n"
        "    for obj in meshes:\n"
        "        obj.data.calc_loop_triangles()\n"
        "        triangles += len(obj.data.loop_triangles)\n"
        "    rows.append({'path': path, 'importFile': result == {'FINISHED'}, 'objects': len(meshes), 'triangles': triangles})\n"
        "print('DCC_READBACK ' + json.dumps(rows))\n",
        encoding="utf-8",
    )
    blender = Path(r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe")
    proc = subprocess.run(
        [str(blender), "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(script)],
        capture_output=True,
        text=True,
    )
    raw = proc.stdout + proc.stderr
    marker = "DCC_READBACK "
    assert marker in raw, raw[-1500:]
    payload = raw.split(marker, 1)[1].splitlines()[0]
    return json.loads(payload), "Blender 5.1.2 bpy import_scene.fbx"


@pytest.mark.max
def test_dcc_readback_imports_mesh_and_solidcraft_files(tmp_path):
    max_batch = Path(r"C:\Program Files\Autodesk\3ds Max 2026\3dsmaxbatch.exe")
    blender = Path(r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe")
    if not max_batch.is_file() and not blender.is_file():
        pytest.skip("DCC readback unavailable: 3ds Max 2026 and Blender 5.1 are not installed")
    recipe = _load_recipe()
    cube = tmp_path / "cube.fbx"
    tris = []
    for poly in _cube_quads():
        tris.append((poly[0], poly[1], poly[2]))
        tris.append((poly[0], poly[2], poly[3]))
    recipe.write_ascii_fbx(cube, _cube_vertices(), tris)
    catalog = Path(r"C:\x\methods\parametric-parts")
    paths = [cube, catalog / "bench-solidcraft.fbx", catalog / "aerator-solidcraft.fbx"]
    for path in paths:
        assert path.is_file(), path
    if max_batch.is_file():
        rows, tool = _max_inventory(paths, tmp_path)
    else:
        rows, tool = _blender_inventory(paths, tmp_path)
    assert tool
    by_path = {str(Path(row["path"])): row for row in rows}
    for path in paths:
        row = by_path[str(path)]
        assert row["objects"] >= 1, row
        assert row["triangles"] == _source_triangles(path), row
