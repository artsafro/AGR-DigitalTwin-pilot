"""Probes for the parametric-part FBX measure script (methods catalog, issue #713).

new-case: fail-closed FBX readback for repeatable-part variants.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "methods" / "parametric_parts_measure.py"


def _ascii_fbx(vertices, polygons, unit_scale=None) -> str:
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
    return (
        "; FBX 7.4.0 project file\n"
        f"{unit}"
        "Objects:  {\n"
        '  Geometry: 0, "Geometry::Part", "Mesh" {\n'
        f"    Vertices: *{len(flat)} {{\n"
        "      a: " + ",".join(str(v) for v in flat) + "\n"
        "    }\n"
        f"    PolygonVertexIndex: *{len(indices)} {{\n"
        "      a: " + ",".join(str(v) for v in indices) + "\n"
        "    }\n"
        "  }\n"
        "}\n"
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
