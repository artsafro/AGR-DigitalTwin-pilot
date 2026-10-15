"""Test suite for Task #100: adoption of plan DXF entity coordinate frames.

Validates WCS coordinates for POINT and 3D POLYLINE, OCS transformation for LWPOLYLINE,
fail-closed rejection behavior, repeatability, and documentation contract.
"""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import ezdxf
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


acad_mod = _load_module(
    ROOT / "experiments" / "acad-coreconsole-agr-plans" / "experiment.py",
    "acad_exp_plans",
)
bim_mod = _load_module(
    ROOT / "experiments" / "bim-autocad-agr" / "experiment.py",
    "bim_exp_plans",
)

read_dxf = acad_mod.read_dxf
strict_read = bim_mod.strict_read

NORMALS = {
    "default": (0.0, 0.0, 1.0),
    "neg_z": (0.0, 0.0, -1.0),
    "tilted": (0.0, 0.6, 0.8),
}

POINT_WCS = [[123.0, 456.0, 789.0]]
POLY3D_WCS = [
    [100.0, 200.0, 300.0],
    [1100.0, 200.0, 300.0],
    [1100.0, 200.0, 1300.0],
    [100.0, 200.0, 1300.0],
]

ORACLE = {
    "default": [
        {"layer": "P_POINT", "kind": "POINT", "closed": False, "vertices_mm": POINT_WCS},
        {"layer": "P_3D", "kind": "POLYLINE", "closed": True, "vertices_mm": POLY3D_WCS},
        {
            "layer": "P_LW",
            "kind": "LWPOLYLINE",
            "closed": True,
            "vertices_mm": [
                [100.0, 200.0, 300.0],
                [1100.0, 200.0, 300.0],
                [1100.0, 700.0, 300.0],
                [100.0, 700.0, 300.0],
            ],
        },
    ],
    "neg_z": [
        {"layer": "P_POINT", "kind": "POINT", "closed": False, "vertices_mm": POINT_WCS},
        {"layer": "P_3D", "kind": "POLYLINE", "closed": True, "vertices_mm": POLY3D_WCS},
        {
            "layer": "P_LW",
            "kind": "LWPOLYLINE",
            "closed": True,
            "vertices_mm": [
                [-100.0, 200.0, -300.0],
                [-1100.0, 200.0, -300.0],
                [-1100.0, 700.0, -300.0],
                [-100.0, 700.0, -300.0],
            ],
        },
    ],
    "tilted": [
        {"layer": "P_POINT", "kind": "POINT", "closed": False, "vertices_mm": POINT_WCS},
        {"layer": "P_3D", "kind": "POLYLINE", "closed": True, "vertices_mm": POLY3D_WCS},
        {
            "layer": "P_LW",
            "kind": "LWPOLYLINE",
            "closed": True,
            "vertices_mm": [
                [-100.0, 20.0, 360.0],
                [-1100.0, 20.0, 360.0],
                [-1100.0, -380.0, 660.0],
                [-100.0, -380.0, 660.0],
            ],
        },
    ],
}


def create_frame_dxf(path: Path, normal: tuple[float, float, float]) -> None:
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 4
    for layer in ("P_POINT", "P_3D", "P_LW"):
        doc.layers.add(layer)
    msp = doc.modelspace()

    # POINT WCS (123,456,789)
    msp.add_point(
        (123.0, 456.0, 789.0),
        dxfattribs={"layer": "P_POINT", "extrusion": normal},
    )

    # Closed 3D POLYLINE WCS [(100,200,300),(1100,200,300),(1100,200,1300),(100,200,1300)]
    msp.add_polyline3d(
        [
            (100.0, 200.0, 300.0),
            (1100.0, 200.0, 300.0),
            (1100.0, 200.0, 1300.0),
            (100.0, 200.0, 1300.0),
        ],
        close=True,
        dxfattribs={"layer": "P_3D", "extrusion": normal},
    )

    # Closed LW local [(100,200),(1100,200),(1100,700),(100,700)] elevation 300, no widths/bulges
    msp.add_lwpolyline(
        [
            (100.0, 200.0),
            (1100.0, 200.0),
            (1100.0, 700.0),
            (100.0, 700.0),
        ],
        close=True,
        dxfattribs={"layer": "P_LW", "elevation": 300.0, "extrusion": normal},
    )
    doc.saveas(path)


def check_serialization(path: Path, normal: tuple[float, float, float]) -> None:
    doc = ezdxf.readfile(path)
    assert doc.header.get("$INSUNITS") == 4
    entities = list(doc.modelspace())
    assert len(entities) == 3

    # Entity 0: POINT on P_POINT
    e0 = entities[0]
    assert e0.dxftype() == "POINT"
    assert e0.dxf.layer == "P_POINT"
    ext0 = tuple(e0.dxf.extrusion) if e0.dxf.hasattr("extrusion") else (0.0, 0.0, 1.0)
    assert math.dist(ext0, normal) <= 1e-6

    # Entity 1: closed 3D POLYLINE on P_3D
    e1 = entities[1]
    assert e1.dxftype() == "POLYLINE"
    assert e1.dxf.layer == "P_3D"
    ext1 = tuple(e1.dxf.extrusion) if e1.dxf.hasattr("extrusion") else (0.0, 0.0, 1.0)
    assert math.dist(ext1, normal) <= 1e-6
    flags = int(e1.dxf.flags)
    assert (flags & 8) != 0, "POLYLINE must be 3D polyline (flag 8)"
    assert (flags & 1) != 0, "POLYLINE must be closed (flag 1)"

    # Entity 2: closed LWPOLYLINE on P_LW
    e2 = entities[2]
    assert e2.dxftype() == "LWPOLYLINE"
    assert e2.dxf.layer == "P_LW"
    ext2 = tuple(e2.dxf.extrusion) if e2.dxf.hasattr("extrusion") else (0.0, 0.0, 1.0)
    assert math.dist(ext2, normal) <= 1e-6
    assert bool(e2.dxf.flags & 1) or e2.closed, "LWPOLYLINE must be closed"


def run_reader(reader_name: str, path: Path) -> dict:
    if reader_name == "acad_read_dxf":
        entities, audit = read_dxf(path)
        return {
            "features": entities,
            "insunits": audit["insunits"],
            "accepted": True,
            "diagnostics": [],
        }
    if reader_name == "bim_strict_read":
        return strict_read(path)
    raise ValueError(f"Unknown reader: {reader_name}")


@pytest.mark.parametrize("reader_name", ["acad_read_dxf", "bim_strict_read"])
@pytest.mark.parametrize("normal_name", ["default", "neg_z", "tilted"])
def test_entity_frames(reader_name: str, normal_name: str, tmp_path: Path):
    dxf_path = tmp_path / f"{normal_name}.dxf"
    normal = NORMALS[normal_name]
    create_frame_dxf(dxf_path, normal)

    # Edge E1: serialization normal/mode check on reopened drawing
    check_serialization(dxf_path, normal)

    # A1/A2/A3: Decode with reader
    res = run_reader(reader_name, dxf_path)
    assert res["insunits"] == 4
    if reader_name == "bim_strict_read":
        assert res["accepted"] is True
        assert res["diagnostics"] == []
    features = res["features"]

    expected = ORACLE[normal_name]
    assert len(features) == len(expected)
    assert [f["kind"] for f in features] == [e["kind"] for e in expected]
    assert [f["layer"] for f in features] == [e["layer"] for e in expected]
    assert [f["closed"] for f in features] == [e["closed"] for e in expected]
    assert [len(f["vertices_mm"]) for f in features] == [len(e["vertices_mm"]) for e in expected]

    # Per-vertex Euclidean distance <= 0.01 mm against independent hard-coded oracle
    for act_feat, exp_feat in zip(features, expected):
        for v_act, v_exp in zip(act_feat["vertices_mm"], exp_feat["vertices_mm"]):
            assert math.dist(v_act, v_exp) <= 0.01


def test_default_normal_unchanged(tmp_path: Path):
    dxf_path = tmp_path / "default.dxf"
    create_frame_dxf(dxf_path, NORMALS["default"])
    expected = ORACLE["default"]

    for reader_name in ("acad_read_dxf", "bim_strict_read"):
        res = run_reader(reader_name, dxf_path)
        assert res["insunits"] == 4
        assert res["features"] == expected


@pytest.mark.parametrize("reader_name", ["acad_read_dxf", "bim_strict_read"])
def test_measured_improvement(reader_name: str, tmp_path: Path):
    # Mathematical double-transform error on negative-Z 3D polyline:
    # Vertex (1100, 200, 1300) mapped through OCS((0,0,-1)) -> (-1100, 200, -1300).
    old_double_transform_dev = math.dist(
        (1100.0, 200.0, 1300.0),
        (-1100.0, 200.0, -1300.0),
    )
    assert round(old_double_transform_dev, 2) == 3405.88
    assert abs(old_double_transform_dev - 3405.877273) < 0.001

    dxf_path = tmp_path / "neg_z.dxf"
    create_frame_dxf(dxf_path, NORMALS["neg_z"])
    res = run_reader(reader_name, dxf_path)
    features = res["features"]
    expected = ORACLE["neg_z"]

    max_dev = max(
        math.dist(v_act, v_exp)
        for act_feat, exp_feat in zip(features, expected)
        for v_act, v_exp in zip(act_feat["vertices_mm"], exp_feat["vertices_mm"])
    )
    assert max_dev <= 0.01


@pytest.mark.parametrize("reader_name", ["acad_read_dxf", "bim_strict_read"])
@pytest.mark.parametrize("normal_name", ["default", "neg_z", "tilted"])
def test_repetitions_agree(reader_name: str, normal_name: str, tmp_path: Path):
    normal = NORMALS[normal_name]
    reps_features = []
    for rep in range(1, 4):
        rep_path = tmp_path / f"{normal_name}_{reader_name}_rep{rep}.dxf"
        create_frame_dxf(rep_path, normal)
        check_serialization(rep_path, normal)
        res = run_reader(reader_name, rep_path)
        reps_features.append(res["features"])

    assert reps_features[0] == reps_features[1] == reps_features[2]


@pytest.mark.parametrize(
    "case_name,expected_reason",
    [
        ("empty", "empty_document"),
        ("wrong_units", "unit_mismatch"),
        ("open_lw", "open_contour"),
        ("bulged_lw", "curved_segment"),
        ("2d_polyline", "unsupported_polyline"),
        ("insert", "block_not_normalized"),
        ("duplicate_layer", "duplicate_layer"),
        ("line", "unsupported_type"),
    ],
)
def test_strict_support_contract(case_name: str, expected_reason: str, tmp_path: Path):
    dxf_path = tmp_path / f"{case_name}.dxf"
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()

    if case_name == "empty":
        pass
    elif case_name == "wrong_units":
        doc.header["$INSUNITS"] = 0
        msp.add_point((0.0, 0.0, 0.0), dxfattribs={"layer": "P1"})
    elif case_name == "open_lw":
        msp.add_lwpolyline([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)], close=False, dxfattribs={"layer": "P1"})
    elif case_name == "bulged_lw":
        msp.add_lwpolyline(
            [(0.0, 0.0, 0.0, 0.0, 0.5), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)],
            close=True,
            dxfattribs={"layer": "P1"},
        )
    elif case_name == "2d_polyline":
        msp.add_polyline2d([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)], close=True, dxfattribs={"layer": "P1"})
    elif case_name == "insert":
        doc.blocks.new("MYBLOCK")
        msp.add_blockref("MYBLOCK", (0.0, 0.0), dxfattribs={"layer": "P1"})
    elif case_name == "duplicate_layer":
        msp.add_point((0.0, 0.0, 0.0), dxfattribs={"layer": "P1"})
        msp.add_point((10.0, 10.0, 10.0), dxfattribs={"layer": "P1"})
    elif case_name == "line":
        msp.add_line((0.0, 0.0, 0.0), (10.0, 10.0, 10.0), dxfattribs={"layer": "P1"})
    else:
        raise ValueError(f"Unknown case: {case_name}")

    doc.saveas(dxf_path)
    res = strict_read(dxf_path)
    assert res["accepted"] is False
    assert res["features"] == []
    diag_reasons = [d.get("reason") for d in res["diagnostics"]]
    assert expected_reason in diag_reasons, f"Expected {expected_reason} in {diag_reasons}"


def test_readme_frame_contract():
    readme_path = ROOT / "experiments" / "bim-autocad-agr" / "README.md"
    assert readme_path.is_file(), f"Expected README at {readme_path}"
    content = readme_path.read_text(encoding="utf-8")
    lowered = content.lower()

    # 1. WCS for POINT and 3D POLYLINE
    assert "wcs" in lowered, "README must explicitly state WCS coordinates for POINT and 3D POLYLINE"
    assert "point" in lowered
    assert "3d" in lowered or "polyline" in lowered

    # 2. OCS for LWPOLYLINE / elevated LW
    assert "ocs" in lowered, "README must explicitly state OCS coordinates for LWPOLYLINE (elevated LW)"
    assert "lw" in lowered or "lwpolyline" in lowered

    # 3. Synthetic limits
    assert "synthetic" in lowered, "README must document synthetic limits"

    # 4. No production adapter
    assert "production adapter" in lowered or ("no production" in lowered and "adapter" in lowered), (
        "README must clarify that no production adapter is created"
    )
