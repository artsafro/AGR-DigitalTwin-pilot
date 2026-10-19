"""Tests for component signed volume evidence follow-up (Task #111).

All test data is SYNTHETIC test data, not a real object.
"""
from __future__ import annotations

import copy
import math
from pathlib import Path
import random
import re

import pytest

from twinqa.geometry.component_volume import component_signed_volumes

ROOT = Path(__file__).resolve().parents[2]

_BASE_BOX_VERTS: list[list[float]] = [
    [0.0, 0.0, 0.0],
    [1.0, 0.0, 0.0],
    [1.0, 1.0, 0.0],
    [0.0, 1.0, 0.0],
    [0.0, 0.0, 1.0],
    [1.0, 0.0, 1.0],
    [1.0, 1.0, 1.0],
    [0.0, 1.0, 1.0],
]

_BASE_BOX_TRIS: list[list[int]] = [
    [0, 3, 2], [0, 2, 1],  # Bottom (-Z)
    [4, 5, 6], [4, 6, 7],  # Top (+Z)
    [0, 1, 5], [0, 5, 4],  # Front (-Y)
    [2, 3, 7], [2, 7, 6],  # Back (+Y)
    [1, 2, 6], [1, 6, 5],  # Right (+X)
    [0, 4, 7], [0, 7, 3],  # Left (-X)
]


class _SyntheticBox:
    """Self-contained synthetic box with randomized scale, rotation, translation, and triangle order."""

    def __init__(self, seed: int):
        self.seed = seed
        rng = random.Random(seed)
        self.lx = rng.uniform(0.2, 20.0)
        self.ly = rng.uniform(0.2, 20.0)
        self.lz = rng.uniform(0.2, 20.0)
        self.theta = rng.uniform(-math.pi, math.pi)
        self.tx = rng.uniform(-1e6, 1e6)
        self.ty = rng.uniform(-1e6, 1e6)
        self.tz = rng.uniform(-1e6, 1e6)

        cos_t = math.cos(self.theta)
        sin_t = math.sin(self.theta)

        self.vertices: list[list[float]] = []
        for x, y, z in _BASE_BOX_VERTS:
            sx, sy, sz = x * self.lx, y * self.ly, z * self.lz
            rx = sx * cos_t - sy * sin_t
            ry = sx * sin_t + sy * cos_t
            rz = sz
            self.vertices.append([rx + self.tx, ry + self.ty, rz + self.tz])

        self.triangles: list[list[int]] = [list(t) for t in _BASE_BOX_TRIS]
        rng.shuffle(self.triangles)
        self.volume: float = self.lx * self.ly * self.lz
        self.drop_idx: int = rng.randrange(len(self.triangles))
        self.reverse_idx: int = rng.randrange(len(self.triangles))


@pytest.fixture
def synthetic_box(seed: int) -> _SyntheticBox:
    """Fixture providing a self-contained randomized synthetic box for a given seed."""
    return _SyntheticBox(seed)


def test_diagnostic_documentation_regression() -> None:
    """Regression test verifying docstring and documentation requirements (Task #111).

    Checks:
    1. twinqa.geometry.component_volume.__doc__ explicitly contains 'new-case'.
    2. docs/qa/component-volume.md contains 'new-case'.
    3. docs/qa/component-volume.md contains a section titled 'Author evidence boundary'.
    4. docs/qa/component-volume.md contains the reproducible probe test path
       ('tests/qa/test_component_volume_evidence.py').
    5. docs/qa/component-volume.md contains an explicit statement that reviewer 800
       checks are not author-session telemetry.

    Expected to fail in Round 1 before documentation and module docstring updates.
    """
    import twinqa.geometry.component_volume as cv_mod

    # 1. Module docstring contains new-case
    assert cv_mod.__doc__ is not None, "component_volume module missing docstring"
    assert "new-case" in cv_mod.__doc__, (
        "twinqa.geometry.component_volume.__doc__ must explicitly contain 'new-case'"
    )

    # Read docs/qa/component-volume.md
    doc_path = ROOT / "docs" / "qa" / "component-volume.md"
    assert doc_path.is_file(), f"Documentation file not found: {doc_path}"
    doc_text = doc_path.read_text(encoding="utf-8")

    # 2. Document contains new-case
    assert "new-case" in doc_text, "docs/qa/component-volume.md must contain 'new-case'"

    # 3. Section titled 'Author evidence boundary'
    assert re.search(r"^#+\s+Author evidence boundary\b", doc_text, re.MULTILINE) is not None, (
        "docs/qa/component-volume.md must contain a section titled 'Author evidence boundary'"
    )

    # 4. Reproducible probe test path
    probe_path = "tests/qa/test_component_volume_evidence.py"
    assert probe_path in doc_text, (
        f"docs/qa/component-volume.md must contain reproducible probe test path '{probe_path}'"
    )

    # 5. Explicit statement that reviewer 800 checks are not author-session telemetry
    lower_text = doc_text.lower()
    assert "reviewer 800" in lower_text, (
        "docs/qa/component-volume.md must reference reviewer 800 checks"
    )
    assert "author-session telemetry" in lower_text or "author session telemetry" in lower_text, (
        "docs/qa/component-volume.md must reference author-session telemetry"
    )
    assert (
        "reviewer 800 checks are not author-session telemetry" in lower_text
        or "reviewer 800 checks are not author session telemetry" in lower_text
        or "not author-session telemetry" in lower_text
        or "not author session telemetry" in lower_text
    ), (
        "docs/qa/component-volume.md must explicitly state that reviewer 800 checks are not author-session telemetry"
    )


@pytest.mark.parametrize("seed", range(100))
def test_synthetic_signed_volume_analytic(seed: int, synthetic_box: _SyntheticBox) -> None:
    """Signed analytic product volume positive and globally reversed negative within rel_tol=1e-6."""
    expected_vol = synthetic_box.volume

    # Forward outward box: positive signed volume
    mesh_forward = {
        "name": f"box_fwd_{seed}",
        "vertices": [list(v) for v in synthetic_box.vertices],
        "triangles": [list(t) for t in synthetic_box.triangles],
    }
    res_fwd = component_signed_volumes([mesh_forward])
    assert len(res_fwd) == 1
    row_fwd = res_fwd[0]
    assert row_fwd["mesh"] == f"box_fwd_{seed}"
    assert row_fwd["n_triangles"] == 12
    assert row_fwd["triangle_ids"] == list(range(12))
    assert row_fwd["eligible"] is True
    assert row_fwd["reasons"] == []
    assert row_fwd["status"] == "measured"
    assert row_fwd["sign"] == 1
    assert row_fwd["signed_volume"] > 0
    assert math.isclose(row_fwd["signed_volume"], expected_vol, rel_tol=1e-6)

    # Globally reversed box: negative signed volume
    tris_rev = [[a, c, b] for a, b, c in synthetic_box.triangles]
    mesh_reversed = {
        "name": f"box_rev_{seed}",
        "vertices": [list(v) for v in synthetic_box.vertices],
        "triangles": tris_rev,
    }
    res_rev = component_signed_volumes([mesh_reversed])
    assert len(res_rev) == 1
    row_rev = res_rev[0]
    assert row_rev["mesh"] == f"box_rev_{seed}"
    assert row_rev["n_triangles"] == 12
    assert row_rev["triangle_ids"] == list(range(12))
    assert row_rev["eligible"] is True
    assert row_rev["reasons"] == []
    assert row_rev["status"] == "measured"
    assert row_rev["sign"] == -1
    assert row_rev["signed_volume"] < 0
    assert math.isclose(row_rev["signed_volume"], -expected_vol, rel_tol=1e-6)


@pytest.mark.parametrize("seed", range(100))
def test_synthetic_coincident_and_separate(seed: int, synthetic_box: _SyntheticBox) -> None:
    """Coincident index-disjoint boxes in one mesh AND separate meshes remain separate with exact local IDs."""
    expected_vol = synthetic_box.volume
    n_v = len(synthetic_box.vertices)

    # Part 1: Coincident index-disjoint boxes packed in a single mesh
    v_combined = [list(v) for v in synthetic_box.vertices] + [list(v) for v in synthetic_box.vertices]
    t_combined = [list(t) for t in synthetic_box.triangles] + [
        [a + n_v, b + n_v, c + n_v] for a, b, c in synthetic_box.triangles
    ]
    mesh_one = {
        "name": f"coincident_one_{seed}",
        "vertices": v_combined,
        "triangles": t_combined,
    }
    res_one = component_signed_volumes([mesh_one])
    assert len(res_one) == 2
    r1, r2 = res_one[0], res_one[1]
    assert r1["mesh"] == f"coincident_one_{seed}"
    assert r2["mesh"] == f"coincident_one_{seed}"
    assert r1["n_triangles"] == 12
    assert r2["n_triangles"] == 12
    assert r1["triangle_ids"] == list(range(12))
    assert r2["triangle_ids"] == list(range(12, 24))
    assert r1["eligible"] is True and r1["status"] == "measured" and r1["sign"] == 1 and r1["reasons"] == []
    assert r2["eligible"] is True and r2["status"] == "measured" and r2["sign"] == 1 and r2["reasons"] == []
    assert math.isclose(r1["signed_volume"], expected_vol, rel_tol=1e-6)
    assert math.isclose(r2["signed_volume"], expected_vol, rel_tol=1e-6)

    # Part 2: Separate meshes remain separate with exact local IDs
    mesh_a = {
        "name": f"sep_a_{seed}",
        "vertices": [list(v) for v in synthetic_box.vertices],
        "triangles": [list(t) for t in synthetic_box.triangles],
    }
    mesh_b = {
        "name": f"sep_b_{seed}",
        "vertices": [list(v) for v in synthetic_box.vertices],
        "triangles": [list(t) for t in synthetic_box.triangles],
    }
    res_sep = component_signed_volumes([mesh_a, mesh_b])
    assert len(res_sep) == 2
    ra, rb = res_sep[0], res_sep[1]
    assert ra["mesh"] == f"sep_a_{seed}"
    assert rb["mesh"] == f"sep_b_{seed}"
    assert ra["triangle_ids"] == list(range(12))
    assert rb["triangle_ids"] == list(range(12))
    assert ra["n_triangles"] == 12
    assert rb["n_triangles"] == 12
    assert ra["eligible"] is True and ra["status"] == "measured" and ra["sign"] == 1 and ra["reasons"] == []
    assert rb["eligible"] is True and rb["status"] == "measured" and rb["sign"] == 1 and rb["reasons"] == []
    assert math.isclose(ra["signed_volume"], expected_vol, rel_tol=1e-6)
    assert math.isclose(rb["signed_volume"], expected_vol, rel_tol=1e-6)


@pytest.mark.parametrize("seed", range(100))
def test_synthetic_abstain_defects(seed: int, synthetic_box: _SyntheticBox) -> None:
    """Open box obtained by removing a triangle AND inconsistent winding obtained by reversing one triangle both abstain."""
    # Part 1: Open box (remove one triangle at drop_idx)
    tris_open = [list(t) for i, t in enumerate(synthetic_box.triangles) if i != synthetic_box.drop_idx]
    mesh_open = {
        "name": f"open_{seed}",
        "vertices": [list(v) for v in synthetic_box.vertices],
        "triangles": tris_open,
    }
    res_open = component_signed_volumes([mesh_open])
    assert len(res_open) == 1
    row_open = res_open[0]
    assert row_open["mesh"] == f"open_{seed}"
    assert row_open["n_triangles"] == 11
    assert row_open["triangle_ids"] == list(range(11))
    assert row_open["eligible"] is False
    assert row_open["status"] == "not_measured"
    assert row_open["signed_volume"] is None
    assert row_open["sign"] is None
    assert "open_or_nonmanifold_edge" in row_open["reasons"]

    # Part 2: Inconsistent winding (reverse orientation of one triangle at reverse_idx)
    tris_incon = [list(t) for t in synthetic_box.triangles]
    tris_incon[synthetic_box.reverse_idx] = [
        tris_incon[synthetic_box.reverse_idx][0],
        tris_incon[synthetic_box.reverse_idx][2],
        tris_incon[synthetic_box.reverse_idx][1],
    ]
    mesh_incon = {
        "name": f"inconsistent_{seed}",
        "vertices": [list(v) for v in synthetic_box.vertices],
        "triangles": tris_incon,
    }
    res_incon = component_signed_volumes([mesh_incon])
    assert len(res_incon) == 1
    row_incon = res_incon[0]
    assert row_incon["mesh"] == f"inconsistent_{seed}"
    assert row_incon["n_triangles"] == 12
    assert row_incon["triangle_ids"] == list(range(12))
    assert row_incon["eligible"] is False
    assert row_incon["status"] == "not_measured"
    assert row_incon["signed_volume"] is None
    assert row_incon["sign"] is None
    assert "inconsistent_winding" in row_incon["reasons"]


@pytest.mark.parametrize("seed", range(100))
def test_synthetic_determinism_and_immutability(seed: int, synthetic_box: _SyntheticBox) -> None:
    """Inputs unchanged, repeated reports identical, mesh order and sorted IDs deterministic, and empty input returns []."""
    # Empty input returns []
    assert component_signed_volumes([]) == []
    assert component_signed_volumes([{"name": "empty", "vertices": [], "triangles": []}]) == []
    assert component_signed_volumes([{"name": "no_tris", "vertices": synthetic_box.vertices, "triangles": []}]) == []

    # Inputs unchanged (immutability)
    m1 = {
        "name": f"mesh1_{seed}",
        "vertices": [list(v) for v in synthetic_box.vertices],
        "triangles": [list(t) for t in synthetic_box.triangles],
    }
    m2 = {
        "name": f"mesh2_{seed}",
        "vertices": [list(v) for v in synthetic_box.vertices],
        "triangles": [list(t) for t in synthetic_box.triangles],
    }
    meshes = [m1, m2]
    input_copy = copy.deepcopy(meshes)
    rep1 = component_signed_volumes(meshes)
    assert meshes == input_copy, "component_signed_volumes mutated its input!"

    # Repeated reports identical (idempotence)
    rep2 = component_signed_volumes(meshes)
    rep3 = component_signed_volumes(meshes)
    assert rep1 == rep2 == rep3

    # Mesh order deterministic
    assert [r["mesh"] for r in rep1] == [f"mesh1_{seed}", f"mesh2_{seed}"]
    meshes_rev = [copy.deepcopy(m2), copy.deepcopy(m1)]
    rep_rev = component_signed_volumes(meshes_rev)
    assert [r["mesh"] for r in rep_rev] == [f"mesh2_{seed}", f"mesh1_{seed}"]

    # Sorted IDs deterministic
    for row in rep1:
        assert row["triangle_ids"] == sorted(row["triangle_ids"])

    # Permuted triangle order in combined mesh preserves sorted triangle_ids
    n_v = len(synthetic_box.vertices)
    v_comb = [list(v) for v in synthetic_box.vertices] + [list(v) for v in synthetic_box.vertices]
    t_comb = [list(t) for t in synthetic_box.triangles] + [
        [a + n_v, b + n_v, c + n_v] for a, b, c in synthetic_box.triangles
    ]
    rng_perm = random.Random(seed + 9999)
    rng_perm.shuffle(t_comb)
    m_comb = {"name": f"permuted_{seed}", "vertices": v_comb, "triangles": t_comb}
    rep_comb = component_signed_volumes([m_comb])
    assert len(rep_comb) == 2
    for row in rep_comb:
        assert row["triangle_ids"] == sorted(row["triangle_ids"])
