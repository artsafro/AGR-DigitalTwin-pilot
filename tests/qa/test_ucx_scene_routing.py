"""Public scene routing for six synthetic UCX degeneracy witnesses.

Pattern: n/a | new-case: UCX scene raw-versus-weld routing via public scene_findings.

Characterization of ``scene_findings`` only. The geometry is synthetic and is
not delivery acceptance. Expected penetration and gap come from axis-aligned
bounds (0.5 m overlap, 0.02 m separation), not from private measurement helpers.
"""
import copy
import re

import pytest

from twinqa.geometry.topology import count_defects
from twinqa.scene import scene_findings

_BOX_TRIS = [
    (0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1),
    (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3),
]

# Overlap of unit boxes at x=0 and x=0.5 is 0.5 m. Separation at x=1.02 is 0.02 m.
_PLACEMENT_X = {"overlap": 0.5, "gap": 1.02}
_PENETRATION_MM = 500.0
_GAP_MM = 20.0
_MM_TOL = 0.5

_PROFILE = {
    "geometry": {
        "oks_triangles_per_fbx_max_excluding_collision": 1000000,
        "near_coplanar_spacing_m": {"min": 0.005, "max": 0.02},
        "duplicate_or_self_intersection_count_max": 100,
        "geometric_error_tolerance_m": 0.002,
    },
    "naming": {"max_characters": 254},
}

_DEFECT_KEYS = (
    "duplicate_vertices",
    "duplicate_edges",
    "duplicate_polygons",
    "self_intersections",
    "isolated_vertices",
    "isolated_edges",
    "isolated_polygons",
    "zero_length_edges",
    "duplicates_and_self_intersections",
)

_TOPOLOGY_STATUS = {
    "clean": "pass",
    "tetra": "pass",
    "collinear": "pass",
    "repeated": "fail",
    "weld_only": "fail",
    "split": "fail",
}

_PAIR_MM = re.compile(
    r"\(\s*['\"][^'\"]*['\"]\s*,\s*['\"][^'\"]*['\"]\s*,\s*(-?\d+(?:\.\d+)?)\s*\)"
)


def _unit_box(x=0.0):
    verts = [
        (x + (1 if i & 4 else 0), 1 if i & 2 else 0, 1 if i & 1 else 0)
        for i in range(8)
    ]
    return verts, [tri for tri in _BOX_TRIS]


def _frozen_corpus():
    """The six witnesses, built once. Callers deep-copy before use."""
    verts, tris = _unit_box()
    return {
        "clean": (verts, tris),
        "tetra": (
            [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0.5, 0, 0)],
            [(0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3)],
        ),
        "collinear": (verts + [(0.5, 0, 0)], tris + [(0, 8, 4)]),
        "repeated": (verts, tris + [(0, 0, 1)]),
        "weld_only": (verts + [(1e-6, 0, 0)], tris + [(0, 8, 2)]),
        "split": (
            [verts[i] for tri in tris for i in tri],
            [(3 * k, 3 * k + 1, 3 * k + 2) for k in range(12)],
        ),
    }


_CORPUS = _frozen_corpus()


def _geometry(name):
    verts, tris = _CORPUS[name]
    return copy.deepcopy(verts), copy.deepcopy(tris)


def _mesh(name, geom):
    verts, tris = geom
    return {
        "name": name,
        "hull": {"verts": verts, "tris": tris},
        "triangles": len(tris),
        "polygon_degrees": {"3": len(tris)},
        "rotation_euler_deg": [0, 0, 0],
        "scale": [1, 1, 1],
        "location": [0, 0, 0],
        "uv_channels": 1,
        "mirrored_uv_triangles": 0,
        "udim_tiles": [1001],
        "materials": [],
        "topology": count_defects(verts, tris),
    }


def _readback(witness, placement):
    return {
        "source": "SM_A.fbx",
        "readback_ok": True,
        "meshes": [
            _mesh("UCX_SM_A_Main_001", _geometry(witness)),
            _mesh("UCX_SM_A_Main_002", _unit_box(_PLACEMENT_X[placement])),
        ],
        "other_objects": [],
        "fbx_units": {"unit_scale_factor": 100},
    }


def _flatten(found):
    flat = {}
    for findings in found.values():
        for finding in findings:
            flat[finding.name] = finding
    return flat


def _named_int(observed, key):
    found = re.findall(rf"\b{re.escape(key)}=(\d+)\b", observed)
    assert len(found) == 1, (key, observed)
    return int(found[0])


def _pair_mm(observed):
    return [float(value) for value in _PAIR_MM.findall(observed)]


def _assert_hulls_unchanged(rb, snapshot):
    assert len(rb["meshes"]) == len(snapshot["meshes"])
    for mesh, before in zip(rb["meshes"], snapshot["meshes"]):
        assert mesh["triangles"] == before["triangles"]
        assert len(mesh["hull"]["verts"]) == len(before["hull"]["verts"])
        assert len(mesh["hull"]["tris"]) == len(before["hull"]["tris"])
        assert mesh["hull"]["verts"] == before["hull"]["verts"]
        assert mesh["hull"]["tris"] == before["hull"]["tris"]


def _public(witness, placement):
    rb = _readback(witness, placement)
    snapshot = copy.deepcopy(rb)
    found = _flatten(scene_findings(rb, "vpm", "oks", _PROFILE))
    _assert_hulls_unchanged(rb, snapshot)
    return found


_ROUTING = [
    {"witness": "clean", "placement": "overlap", "inter": "fail", "coverage": "pass", "gap": "pass",
     "unmeasured": 0, "penetration_mm": _PENETRATION_MM},
    {"witness": "clean", "placement": "gap", "inter": "pass", "coverage": "pass", "gap": "review",
     "wide": 1, "gap_mm": _GAP_MM},
    {"witness": "tetra", "placement": "overlap", "inter": "not_run", "coverage": "not_run", "gap": "not_run",
     "unmeasured": 1, "reason": "degenerate"},
    {"witness": "tetra", "placement": "gap", "inter": "pass", "coverage": "pass", "gap": "not_run",
     "unmeasured": 1},
    {"witness": "collinear", "placement": "overlap", "inter": "not_run", "coverage": "not_run", "gap": "not_run",
     "unmeasured": 1, "reason": "open"},
    {"witness": "collinear", "placement": "gap", "inter": "pass", "coverage": "pass", "gap": "not_run",
     "unmeasured": 1},
    {"witness": "repeated", "placement": "overlap", "inter": "fail", "coverage": "pass", "gap": "pass",
     "unmeasured": 0, "penetration_mm": _PENETRATION_MM},
    {"witness": "repeated", "placement": "gap", "inter": "pass", "coverage": "pass", "gap": "review",
     "wide": 1, "gap_mm": _GAP_MM},
    {"witness": "weld_only", "placement": "overlap", "inter": "fail", "coverage": "pass", "gap": "pass",
     "unmeasured": 0, "penetration_mm": _PENETRATION_MM},
    {"witness": "weld_only", "placement": "gap", "inter": "pass", "coverage": "pass", "gap": "review",
     "wide": 1, "gap_mm": _GAP_MM},
    {"witness": "split", "placement": "overlap", "inter": "fail", "coverage": "pass", "gap": "pass",
     "unmeasured": 0, "penetration_mm": _PENETRATION_MM},
    {"witness": "split", "placement": "gap", "inter": "pass", "coverage": "pass", "gap": "review",
     "wide": 1, "gap_mm": _GAP_MM},
]


@pytest.mark.parametrize("case", _ROUTING, ids=lambda case: f"{case['witness']}-{case['placement']}")
def test_public_scene_routing(case):
    found = _public(case["witness"], case["placement"])
    intersections = found["UCX intersections"]
    coverage = found["UCX intersections coverage"]
    gap = found["UCX piece gap (advisory)"]
    assert intersections.status == case["inter"]
    assert coverage.status == case["coverage"]
    assert gap.status == case["gap"]
    if "unmeasured" in case:
        assert _named_int(gap.observed, "unmeasured") == case["unmeasured"]
    if "wide" in case:
        assert _named_int(gap.observed, "wide") == case["wide"]
    if "penetration_mm" in case:
        millimetres = _pair_mm(intersections.observed)
        assert len(millimetres) == 1
        assert abs(millimetres[0] - case["penetration_mm"]) < _MM_TOL
    if "gap_mm" in case:
        millimetres = _pair_mm(gap.observed)
        assert len(millimetres) == 1
        assert abs(millimetres[0] - case["gap_mm"]) < _MM_TOL
    if "reason" in case:
        assert case["reason"] in coverage.observed
    topology = found["topology defects"]
    assert topology.status == _TOPOLOGY_STATUS[case["witness"]]
    if case["witness"] == "repeated":
        assert "zero_length_edges=1" in topology.observed
    if case["witness"] == "split":
        assert topology.status == "fail"


@pytest.mark.parametrize("witness", ["clean", "tetra", "collinear"])
def test_count_defects_all_zero_on_original_triangles(witness):
    counts = count_defects(*_geometry(witness))
    for key in _DEFECT_KEYS:
        assert counts[key] == 0


def test_repeated_index_keeps_zero_length_edge():
    counts = count_defects(*_geometry("repeated"))
    assert counts["zero_length_edges"] == 1


def test_weld_only_and_split_topology_counts():
    weld_only = count_defects(*_geometry("weld_only"))
    assert weld_only["duplicates_and_self_intersections"] == 2
    assert weld_only["zero_length_edges"] == 1
    split = count_defects(*_geometry("split"))
    assert split["duplicates_and_self_intersections"] == 46
    assert split["isolated_polygons"] == 12


@pytest.mark.parametrize("witness", ["tetra", "collinear"])
def test_unsupported_overlap_is_not_pass(witness):
    """Fails if an unsupported overlapping pair is reported as an intersection pass."""
    found = _public(witness, "overlap")
    assert found["UCX intersections"].status == "not_run"
    assert found["UCX intersections coverage"].status == "not_run"
    assert found["UCX piece gap (advisory)"].status == "not_run"


@pytest.mark.parametrize("witness,placement", [
    ("tetra", "overlap"),
    ("tetra", "gap"),
    ("collinear", "overlap"),
    ("collinear", "gap"),
])
def test_unmeasured_count_is_retained(witness, placement):
    """Fails if the unmeasured neighbour count is dropped from the gap finding."""
    found = _public(witness, placement)
    assert _named_int(found["UCX piece gap (advisory)"].observed, "unmeasured") == 1
