"""Tests for SPOZU point entity rotation composition under block nesting.

Verifies that model-space and nested INSERT / MINSERT point entities (both planting and MAF)
compose their rotation angles and XY positions correctly through arbitrary nesting depths
under positive uniform scales and +Z extrusion, asserted against an independent sin/cos
affine oracle.
"""

from __future__ import annotations

import math
from typing import NamedTuple

import ezdxf
import pytest

from adapters.cad.spozu import PointItem, SpozuConfig, read_spozu_dxf


# -----------------------------------------------------------------------------
# Independent sin/cos 2D affine oracle (no ezdxf Matrix44 or adapter helpers)
# -----------------------------------------------------------------------------


class Affine2D(NamedTuple):
    """Independent 2D similarity transform oracle.

    Represents p' = R(theta) * scale * p + (tx, ty),
    where R(theta) is standard CCW Cartesian rotation.
    """

    tx: float = 0.0
    ty: float = 0.0
    theta_deg: float = 0.0
    scale: float = 1.0

    def transform_point(self, x: float, y: float) -> tuple[float, float]:
        rad = math.radians(self.theta_deg)
        c = math.cos(rad)
        s = math.sin(rad)
        sx = x * self.scale
        sy = y * self.scale
        return (sx * c - sy * s + self.tx, sx * s + sy * c + self.ty)

    def compose(self, child: Affine2D) -> Affine2D:
        """Compose self (parent) with child: parent(child(p))."""
        ctx, cty = self.transform_point(child.tx, child.ty)
        cscale = self.scale * child.scale
        ctheta = (self.theta_deg + child.theta_deg) % 360.0
        return Affine2D(tx=ctx, ty=cty, theta_deg=ctheta, scale=cscale)

    @classmethod
    def compose_chain(cls, *transforms: Affine2D) -> Affine2D:
        curr = cls()
        for t in transforms:
            curr = curr.compose(t)
        return curr


def direction_vector(angle_deg: float) -> tuple[float, float]:
    """Return 2D unit direction vector (cos, sin) for an angle in degrees."""
    rad = math.radians(angle_deg)
    return (math.cos(rad), math.sin(rad))


def assert_point_matches_oracle(
    point: PointItem,
    *,
    expected_x: float,
    expected_y: float,
    expected_angle_deg: float,
    expected_label: str,
    expected_handle: str,
    expected_container: str | None,
    expected_ref: str,
    pos_tol: float = 1e-4,
    dir_tol: float = 1e-6,
) -> None:
    """Assert XY position, rotation modulo 360 (via direction vectors), label, handle/ref, container."""
    # Assert rotation modulo 360 by comparing unit direction vectors
    act_dx, act_dy = direction_vector(point.rotation)
    exp_dx, exp_dy = direction_vector(expected_angle_deg)
    assert act_dx == pytest.approx(exp_dx, abs=dir_tol), (
        f"Rotation direction X mismatch: actual {point.rotation}° vs expected {expected_angle_deg}°"
    )
    assert act_dy == pytest.approx(exp_dy, abs=dir_tol), (
        f"Rotation direction Y mismatch: actual {point.rotation}° vs expected {expected_angle_deg}°"
    )

    assert point.x == pytest.approx(expected_x, abs=pos_tol)
    assert point.y == pytest.approx(expected_y, abs=pos_tol)

    assert point.label == expected_label
    assert point.handle == expected_handle
    assert point.container == expected_container
    assert point.ref == expected_ref


# -----------------------------------------------------------------------------
# Drawing fixtures & helpers
# -----------------------------------------------------------------------------


def make_config() -> SpozuConfig:
    return SpozuConfig.from_dict({
        "project": "synthetic_rotations",
        "boundary": {"layer": "BOUNDARY"},
        "coverings": [],
        "planting": {"layers": ["PLANT"], "positions": {"Oak": "P1"}},
        "maf": {"layers": ["MAF"], "positions": {"Bench": "M1"}},
        "ignore_layers": ["0", "Defpoints"],
    })


def make_doc() -> ezdxf.document.Drawing:
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 6  # metres
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (200, 0), (200, 200), (0, 200)], close=True, dxfattribs={"layer": "BOUNDARY"})
    doc.blocks.new("Oak").add_circle((0, 0), 0.5)
    doc.blocks.new("Bench").add_lwpolyline([(0, 0), (2, 0), (2, 1), (0, 1)], close=True)
    return doc


ROLES = [
    ("planting", "PLANT", "Oak"),
    ("maf", "MAF", "Bench"),
]


# -----------------------------------------------------------------------------
# Test Cases
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("role,layer,block_name", ROLES)
def test_case1_model_space_child_30_degrees(role: str, layer: str, block_name: str) -> None:
    """Case 1: model-space child 30 degrees -> 30."""
    doc = make_doc()
    msp = doc.modelspace()
    child_pos = (20.0, 30.0)
    child_rot = 30.0
    ins = msp.add_blockref(block_name, child_pos, dxfattribs={
        "layer": layer,
        "rotation": child_rot,
        "extrusion": (0, 0, 1),
    })

    cfg = make_config()
    res = read_spozu_dxf(doc, cfg)
    assert res.findings == []

    points = res.planting if role == "planting" else res.maf
    assert len(points) == 1
    pt = points[0]

    oracle = Affine2D(tx=child_pos[0], ty=child_pos[1], theta_deg=child_rot)
    exp_x, exp_y = oracle.transform_point(0.0, 0.0)

    assert_point_matches_oracle(
        pt,
        expected_x=exp_x,
        expected_y=exp_y,
        expected_angle_deg=child_rot,
        expected_label=block_name,
        expected_handle=ins.dxf.handle,
        expected_container=None,
        expected_ref=ins.dxf.handle,
    )


@pytest.mark.parametrize("role,layer,block_name", ROLES)
def test_case2_parent_90_plus_child_30_composes_to_120(role: str, layer: str, block_name: str) -> None:
    """Case 2: parent 90 + child 30 -> 120."""
    doc = make_doc()
    parent_block = doc.blocks.new("PARENT_BLOCK")
    child_pos = (5.0, 2.0)
    child_rot = 30.0
    child_ins = parent_block.add_blockref(block_name, child_pos, dxfattribs={
        "layer": layer,
        "rotation": child_rot,
        "extrusion": (0, 0, 1),
    })

    parent_pos = (50.0, 60.0)
    parent_rot = 90.0
    parent_ins = doc.modelspace().add_blockref("PARENT_BLOCK", parent_pos, dxfattribs={
        "layer": "0",
        "rotation": parent_rot,
        "extrusion": (0, 0, 1),
    })

    cfg = make_config()
    res = read_spozu_dxf(doc, cfg)
    assert res.findings == []

    points = res.planting if role == "planting" else res.maf
    assert len(points) == 1
    pt = points[0]

    parent_t = Affine2D(tx=parent_pos[0], ty=parent_pos[1], theta_deg=parent_rot)
    child_t = Affine2D(tx=child_pos[0], ty=child_pos[1], theta_deg=child_rot)
    composed = parent_t.compose(child_t)
    exp_x, exp_y = composed.transform_point(0.0, 0.0)

    assert_point_matches_oracle(
        pt,
        expected_x=exp_x,
        expected_y=exp_y,
        expected_angle_deg=120.0,
        expected_label=block_name,
        expected_handle=child_ins.dxf.handle,
        expected_container=parent_ins.dxf.handle,
        expected_ref=f"{parent_ins.dxf.handle}>{child_ins.dxf.handle}",
    )


@pytest.mark.parametrize("role,layer,block_name", ROLES)
def test_case3_parent_minus_45_inner_90_child_30_composes_to_75(role: str, layer: str, block_name: str) -> None:
    """Case 3: parent -45 + inner 90 + child 30 -> 75."""
    doc = make_doc()

    inner_block = doc.blocks.new("INNER_BLOCK")
    child_pos = (4.0, 1.0)
    child_rot = 30.0
    child_ins = inner_block.add_blockref(block_name, child_pos, dxfattribs={
        "layer": layer,
        "rotation": child_rot,
        "extrusion": (0, 0, 1),
    })

    outer_block = doc.blocks.new("OUTER_BLOCK")
    inner_pos = (3.0, 7.0)
    inner_rot = 90.0
    inner_ins = outer_block.add_blockref("INNER_BLOCK", inner_pos, dxfattribs={
        "layer": "0",
        "rotation": inner_rot,
        "extrusion": (0, 0, 1),
    })

    parent_pos = (70.0, 80.0)
    parent_rot = -45.0
    parent_ins = doc.modelspace().add_blockref("OUTER_BLOCK", parent_pos, dxfattribs={
        "layer": "0",
        "rotation": parent_rot,
        "extrusion": (0, 0, 1),
    })

    cfg = make_config()
    res = read_spozu_dxf(doc, cfg)
    assert res.findings == []

    points = res.planting if role == "planting" else res.maf
    assert len(points) == 1
    pt = points[0]

    parent_t = Affine2D(tx=parent_pos[0], ty=parent_pos[1], theta_deg=parent_rot)
    inner_t = Affine2D(tx=inner_pos[0], ty=inner_pos[1], theta_deg=inner_rot)
    child_t = Affine2D(tx=child_pos[0], ty=child_pos[1], theta_deg=child_rot)
    composed = Affine2D.compose_chain(parent_t, inner_t, child_t)
    exp_x, exp_y = composed.transform_point(0.0, 0.0)

    assert_point_matches_oracle(
        pt,
        expected_x=exp_x,
        expected_y=exp_y,
        expected_angle_deg=75.0,
        expected_label=block_name,
        expected_handle=child_ins.dxf.handle,
        expected_container=f"{parent_ins.dxf.handle}>{inner_ins.dxf.handle}",
        expected_ref=f"{parent_ins.dxf.handle}>{inner_ins.dxf.handle}>{child_ins.dxf.handle}",
    )


@pytest.mark.parametrize("role,layer,block_name", ROLES)
def test_case4_two_instances_different_parent_angles(role: str, layer: str, block_name: str) -> None:
    """Case 4: two instances of one block under different parent angles -> distinct correct directions and refs."""
    doc = make_doc()
    container_block = doc.blocks.new("SHARED_CONTAINER")
    child_pos = (2.0, 1.0)
    child_rot = 25.0
    child_ins = container_block.add_blockref(block_name, child_pos, dxfattribs={
        "layer": layer,
        "rotation": child_rot,
        "extrusion": (0, 0, 1),
    })

    msp = doc.modelspace()
    # Instance A: parent angle 40 deg
    pos_a = (30.0, 40.0)
    rot_a = 40.0
    ins_a = msp.add_blockref("SHARED_CONTAINER", pos_a, dxfattribs={
        "layer": "0",
        "rotation": rot_a,
        "extrusion": (0, 0, 1),
    })

    # Instance B: parent angle 160 deg
    pos_b = (90.0, 110.0)
    rot_b = 160.0
    ins_b = msp.add_blockref("SHARED_CONTAINER", pos_b, dxfattribs={
        "layer": "0",
        "rotation": rot_b,
        "extrusion": (0, 0, 1),
    })

    cfg = make_config()
    res = read_spozu_dxf(doc, cfg)
    assert res.findings == []

    points = res.planting if role == "planting" else res.maf
    assert len(points) == 2

    points_by_container = {p.container: p for p in points}
    assert ins_a.dxf.handle in points_by_container
    assert ins_b.dxf.handle in points_by_container

    pt_a = points_by_container[ins_a.dxf.handle]
    pt_b = points_by_container[ins_b.dxf.handle]

    # Instance A assertions
    t_a = Affine2D(tx=pos_a[0], ty=pos_a[1], theta_deg=rot_a).compose(
        Affine2D(tx=child_pos[0], ty=child_pos[1], theta_deg=child_rot)
    )
    exp_xa, exp_ya = t_a.transform_point(0.0, 0.0)
    assert_point_matches_oracle(
        pt_a,
        expected_x=exp_xa,
        expected_y=exp_ya,
        expected_angle_deg=rot_a + child_rot,
        expected_label=block_name,
        expected_handle=child_ins.dxf.handle,
        expected_container=ins_a.dxf.handle,
        expected_ref=f"{ins_a.dxf.handle}>{child_ins.dxf.handle}",
    )

    # Instance B assertions
    t_b = Affine2D(tx=pos_b[0], ty=pos_b[1], theta_deg=rot_b).compose(
        Affine2D(tx=child_pos[0], ty=child_pos[1], theta_deg=child_rot)
    )
    exp_xb, exp_yb = t_b.transform_point(0.0, 0.0)
    assert_point_matches_oracle(
        pt_b,
        expected_x=exp_xb,
        expected_y=exp_yb,
        expected_angle_deg=rot_b + child_rot,
        expected_label=block_name,
        expected_handle=child_ins.dxf.handle,
        expected_container=ins_b.dxf.handle,
        expected_ref=f"{ins_b.dxf.handle}>{child_ins.dxf.handle}",
    )

    # Verify distinct directions and distinct refs
    dir_a = direction_vector(pt_a.rotation)
    dir_b = direction_vector(pt_b.rotation)
    assert (abs(dir_a[0] - dir_b[0]) > 1e-3) or (abs(dir_a[1] - dir_b[1]) > 1e-3)
    assert pt_a.ref != pt_b.ref


@pytest.mark.parametrize("role,layer,block_name", ROLES)
def test_case5_nested_minsert_2x2_four_positions_same_composed_direction(
    role: str, layer: str, block_name: str
) -> None:
    """Case 5: nested MINSERT 2x2 -> four correct positions with the same composed direction."""
    doc = make_doc()
    container_block = doc.blocks.new("MINSERT_CONTAINER")

    base_pos = (1.0, 2.0)
    mi_rot = 30.0
    row_count = 2
    col_count = 2
    row_spacing = 4.0
    col_spacing = 6.0

    mi = container_block.add_blockref(block_name, base_pos, dxfattribs={
        "layer": layer,
        "rotation": mi_rot,
        "row_count": row_count,
        "column_count": col_count,
        "row_spacing": row_spacing,
        "column_spacing": col_spacing,
        "extrusion": (0, 0, 1),
    })

    parent_pos = (40.0, 50.0)
    parent_rot = 90.0
    parent_ins = doc.modelspace().add_blockref("MINSERT_CONTAINER", parent_pos, dxfattribs={
        "layer": "0",
        "rotation": parent_rot,
        "extrusion": (0, 0, 1),
    })

    cfg = make_config()
    res = read_spozu_dxf(doc, cfg)
    assert res.findings == []

    points = res.planting if role == "planting" else res.maf
    assert len(points) == 4

    parent_t = Affine2D(tx=parent_pos[0], ty=parent_pos[1], theta_deg=parent_rot)
    base_cell_t = Affine2D(tx=base_pos[0], ty=base_pos[1], theta_deg=mi_rot)
    expected_composed_angle = (parent_rot + mi_rot) % 360.0

    for row in range(row_count):
        for col in range(col_count):
            k = row * col_count + col
            # Displacement along col (local X) and row (local Y) in cell coordinates:
            dx = col * col_spacing
            dy = row * row_spacing
            # Cell insert point in block definition coordinates:
            cell_x_in_block, cell_y_in_block = base_cell_t.transform_point(dx, dy)
            cell_t = Affine2D(tx=cell_x_in_block, ty=cell_y_in_block, theta_deg=mi_rot)

            # Transformed to WCS by parent:
            wcs_t = parent_t.compose(cell_t)
            exp_x, exp_y = wcs_t.transform_point(0.0, 0.0)

            exp_ref = f"{parent_ins.dxf.handle}>{mi.dxf.handle}#{k}"
            matching = [p for p in points if p.ref == exp_ref]
            assert len(matching) == 1, f"Missing point for ref {exp_ref}"
            pt = matching[0]

            assert_point_matches_oracle(
                pt,
                expected_x=exp_x,
                expected_y=exp_y,
                expected_angle_deg=expected_composed_angle,
                expected_label=block_name,
                expected_handle=mi.dxf.handle,
                expected_container=parent_ins.dxf.handle,
                expected_ref=exp_ref,
            )


@pytest.mark.parametrize("role,layer,block_name", ROLES)
@pytest.mark.parametrize("scale", [0.5, 1.0, 2.5, 5.0])
def test_case6_parent_translation_and_positive_uniform_scale_direction_unchanged(
    role: str, layer: str, block_name: str, scale: float
) -> None:
    """Case 6: parent translation and positive uniform scale -> unchanged direction."""
    doc = make_doc()
    container_block = doc.blocks.new("CONTAINER_SCALE")
    child_pos = (3.0, 4.0)
    child_rot = 35.0
    child_ins = container_block.add_blockref(block_name, child_pos, dxfattribs={
        "layer": layer,
        "rotation": child_rot,
        "extrusion": (0, 0, 1),
    })

    parent_pos = (50.0, 60.0)
    parent_ins = doc.modelspace().add_blockref("CONTAINER_SCALE", parent_pos, dxfattribs={
        "layer": "0",
        "rotation": 0.0,
        "xscale": scale,
        "yscale": scale,
        "zscale": scale,
        "extrusion": (0, 0, 1),
    })

    cfg = make_config()
    res = read_spozu_dxf(doc, cfg)
    assert res.findings == []

    points = res.planting if role == "planting" else res.maf
    assert len(points) == 1
    pt = points[0]

    parent_t = Affine2D(tx=parent_pos[0], ty=parent_pos[1], theta_deg=0.0, scale=scale)
    child_t = Affine2D(tx=child_pos[0], ty=child_pos[1], theta_deg=child_rot, scale=1.0)
    composed = parent_t.compose(child_t)
    exp_x, exp_y = composed.transform_point(0.0, 0.0)

    assert_point_matches_oracle(
        pt,
        expected_x=exp_x,
        expected_y=exp_y,
        expected_angle_deg=child_rot,
        expected_label=block_name,
        expected_handle=child_ins.dxf.handle,
        expected_container=parent_ins.dxf.handle,
        expected_ref=f"{parent_ins.dxf.handle}>{child_ins.dxf.handle}",
    )


def test_nested_container_with_both_planting_and_maf_rotations() -> None:
    """Verify concurrent planting and MAF in the same rotated container block."""
    doc = make_doc()
    container = doc.blocks.new("SHARED_BOTH")

    plant_ins = container.add_blockref("Oak", (2.0, 3.0), dxfattribs={
        "layer": "PLANT",
        "rotation": 30.0,
        "extrusion": (0, 0, 1),
    })
    maf_ins = container.add_blockref("Bench", (4.0, 5.0), dxfattribs={
        "layer": "MAF",
        "rotation": 60.0,
        "extrusion": (0, 0, 1),
    })

    parent_pos = (25.0, 35.0)
    parent_rot = 45.0
    parent_ins = doc.modelspace().add_blockref("SHARED_BOTH", parent_pos, dxfattribs={
        "layer": "0",
        "rotation": parent_rot,
        "extrusion": (0, 0, 1),
    })

    cfg = make_config()
    res = read_spozu_dxf(doc, cfg)
    assert res.findings == []
    assert len(res.planting) == 1
    assert len(res.maf) == 1

    parent_t = Affine2D(tx=parent_pos[0], ty=parent_pos[1], theta_deg=parent_rot)

    # Oak: 45 + 30 = 75
    oak_t = parent_t.compose(Affine2D(tx=2.0, ty=3.0, theta_deg=30.0))
    oak_x, oak_y = oak_t.transform_point(0.0, 0.0)
    assert_point_matches_oracle(
        res.planting[0],
        expected_x=oak_x,
        expected_y=oak_y,
        expected_angle_deg=75.0,
        expected_label="Oak",
        expected_handle=plant_ins.dxf.handle,
        expected_container=parent_ins.dxf.handle,
        expected_ref=f"{parent_ins.dxf.handle}>{plant_ins.dxf.handle}",
    )

    # Bench: 45 + 60 = 105
    bench_t = parent_t.compose(Affine2D(tx=4.0, ty=5.0, theta_deg=60.0))
    bench_x, bench_y = bench_t.transform_point(0.0, 0.0)
    assert_point_matches_oracle(
        res.maf[0],
        expected_x=bench_x,
        expected_y=bench_y,
        expected_angle_deg=105.0,
        expected_label="Bench",
        expected_handle=maf_ins.dxf.handle,
        expected_container=parent_ins.dxf.handle,
        expected_ref=f"{parent_ins.dxf.handle}>{maf_ins.dxf.handle}",
    )
