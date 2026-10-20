"""Contract tests for dt_ai.spec.mesh._weld (half-shifted grids and wide-cluster fallback).

Pattern: n/a | new-case: extractor weld half-shift grid + wide-cluster fallback contract
characterization (tests only, no kernel change, no checker parity claim).

Acceptance criteria:
1. Inputs and assertions in units of W = WELD_M (0.1 mm).
2. Boundary crossing close-pair controls: for each sign and axis combination,
   points crossing a plain-grid boundary within W/2 on every axis weld to the
   same representative.
3. Isolated duplicate coordinate groups far apart weld into exactly two groups
   whose representatives index unchanged input rows.
4. Wide chain fallback: x = [0.1, 0.5, 0.9, 1.3] * W, y=z=0 forms a transitive
   component wider than W, triggering fallback partition {0, 1, 2} and {3}
   derived independently from plain cell intervals [0, W) and [W, 2W).
   Reversed and all permutations yield the same coordinate-equivalence partition.
5. Dense 3D small lattice spanning multiple W cells falls back to plain-grid cells
   and preserves per-axis representative displacement <= W.
6. Non-wide diagonal cluster with coordinate differences < W/2 but Euclidean distance
   > W/2 documents per-axis (L_inf) guarantee, not Euclidean (L_2) threshold.
7. Distinguishes translation-invariant close-pair guarantees from intentionally
   grid-dependent translations of wide chains under fallback.
8. Task-local in-memory mutations confirm that tests detect missing shifted grids
   and disabled wide fallback.
"""

import itertools
import math
from collections import defaultdict

import numpy as np
import pytest

from dt_ai.spec.mesh import WELD_M, _Sets, _weld


def _partition(rep):
    """Partition of indices 0..n-1 into equivalence classes defined by rep."""
    groups = defaultdict(set)
    for i, r in enumerate(rep):
        groups[int(r)].add(i)
    return {frozenset(s) for s in groups.values()}


def _partition_by_coordinates(rep, perm):
    """Map representative clusters back to original vertex indices after permutation."""
    groups = defaultdict(set)
    for i, r in enumerate(rep):
        groups[int(r)].add(perm[i])
    return {frozenset(s) for s in groups.values()}


# ---------------------------------------------------------------------------
# Requirement 1 & 2: Boundary-crossing close pairs across all sign & axis combinations
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("axis", [0, 1, 2], ids=["X-axis", "Y-axis", "Z-axis"])
@pytest.mark.parametrize("sign", [+1, -1], ids=["positive-bound", "negative-bound"])
def test_close_pair_crossing_plain_grid_boundary_each_sign_and_axis(axis, sign):
    """Two points crossing an integer grid boundary with coordinate difference <= W/2

    must weld to the same representative in dt_ai.spec.mesh._weld, regardless
    of sign or axis. Plain grid alone splits them; the half-shifted grids merge them.
    """
    w = WELD_M
    boundary = sign * w

    # Points separated by 0.4 * W (within W / 2 = 0.5 * W on axis, 0 on other axes)
    p1 = np.zeros(3, dtype=np.float64)
    p2 = np.zeros(3, dtype=np.float64)
    p1[axis] = boundary - 0.2 * w
    p2[axis] = boundary + 0.2 * w

    # Input points span across the plain-grid boundary
    assert math.floor(p1[axis] / w) != math.floor(p2[axis] / w)
    assert abs(p2[axis] - p1[axis]) <= w / 2

    # Both forward and reversed order must resolve to a single representative
    rep_fwd = _weld(np.array([p1, p2]))
    assert rep_fwd[0] == rep_fwd[1]
    assert rep_fwd[0] in (0, 1)

    rep_rev = _weld(np.array([p2, p1]))
    assert rep_rev[0] == rep_rev[1]
    assert rep_rev[0] in (0, 1)


@pytest.mark.parametrize("axis", [0, 1, 2], ids=["X-axis", "Y-axis", "Z-axis"])
def test_close_pair_crossing_zero_boundary(axis):
    """Points crossing 0.0 boundary (negative to positive) within W/2 weld together."""
    w = WELD_M
    p1 = np.zeros(3, dtype=np.float64)
    p2 = np.zeros(3, dtype=np.float64)
    p1[axis] = -0.2 * w
    p2[axis] = +0.2 * w

    assert math.floor(p1[axis] / w) == -1
    assert math.floor(p2[axis] / w) == 0
    assert abs(p2[axis] - p1[axis]) <= w / 2

    rep = _weld(np.array([p1, p2]))
    assert rep[0] == rep[1]


# ---------------------------------------------------------------------------
# Requirement 3: Isolated duplicate-coordinate groups far apart
# ---------------------------------------------------------------------------


def test_isolated_duplicate_groups_far_apart():
    """Two isolated duplicate groups far apart produce exactly two groups

    with representatives indexing unchanged input rows.
    """
    w = WELD_M
    # Group A at origin, Group B shifted by 10 * W on all axes (far apart, > 10 * W)
    grp_a = np.array([
        [0.0, 0.0, 0.0],
        [0.0, 0.0, 0.0],
        [0.1 * w, 0.1 * w, 0.1 * w],
    ], dtype=np.float64)
    grp_b = np.array([
        [10.0 * w, 10.0 * w, 10.0 * w],
        [10.0 * w, 10.0 * w, 10.0 * w],
        [10.1 * w, 10.1 * w, 10.1 * w],
    ], dtype=np.float64)

    pts = np.vstack([grp_a, grp_b])
    rep = _weld(pts)

    unique_reps = sorted(set(rep.tolist()))
    assert len(unique_reps) == 2, f"Expected 2 groups, got {unique_reps}"

    # Group A points point to unique_reps[0], Group B points point to unique_reps[1]
    assert set(rep[:3]) == {unique_reps[0]}
    assert set(rep[3:]) == {unique_reps[1]}
    assert unique_reps[0] in {0, 1, 2}
    assert unique_reps[1] in {3, 4, 5}

    # Representatives index unchanged input row
    for r in unique_reps:
        assert np.array_equal(pts[r], pts[rep[r]])


# ---------------------------------------------------------------------------
# Requirement 4: Wide chain fallback and permutation invariance
# ---------------------------------------------------------------------------


def test_wide_chain_shifted_grid_component_and_fallback_partition():
    """x = [0.1, 0.5, 0.9, 1.3] * W, y=z=0 forms a transitive shifted-grid component

    wider than W, which falls back to plain-grid cell intervals [0, W) and [W, 2W).
    Plain cell interval arithmetic independently derives partition {0, 1, 2} and {3}.
    """
    w = WELD_M
    chain = np.array([
        [0.1, 0.0, 0.0],
        [0.5, 0.0, 0.0],
        [0.9, 0.0, 0.0],
        [1.3, 0.0, 0.0],
    ], dtype=np.float64) * w

    # Step 1: Independent interval arithmetic derivation:
    # Cell 0: [0, W) -> points at 0.1*W, 0.5*W, 0.9*W have math.floor(x/W) == 0
    # Cell 1: [W, 2W) -> point at 1.3*W has math.floor(x/W) == 1
    expected_cells = [math.floor(p[0] / w) for p in chain]
    assert expected_cells == [0, 0, 0, 1]
    expected_partition = {frozenset({0, 1, 2}), frozenset({3})}

    # Step 2: Total span is 1.3 * W - 0.1 * W = 1.2 * W > W (triggers wide fallback)
    span = chain[:, 0].max() - chain[:, 0].min()
    assert span > w

    rep = _weld(chain)
    actual_partition = _partition(rep)
    assert actual_partition == expected_partition
    assert rep[0] == rep[1] == rep[2] == 0
    assert rep[3] == 3


def test_wide_chain_permutations_preserve_coordinate_partition():
    """Permuting the wide chain preserves the coordinate-equivalence partition

    {0, 1, 2} and {3} after undoing the permutation, though representatives may differ.
    """
    w = WELD_M
    chain = np.array([
        [0.1, 0.0, 0.0],
        [0.5, 0.0, 0.0],
        [0.9, 0.0, 0.0],
        [1.3, 0.0, 0.0],
    ], dtype=np.float64) * w

    expected_partition = {frozenset({0, 1, 2}), frozenset({3})}

    # Check reversed chain specifically:
    # in reversed chain, points are [1.3, 0.9, 0.5, 0.1] * W
    # plain grid assigns rep to first occurrence in cell:
    # point 1.3*W is at index 0 (rep 0); points 0.9*W, 0.5*W, 0.1*W are at indices 1, 2, 3 (rep 1).
    rep_rev = _weld(chain[::-1])
    assert rep_rev.tolist() == [0, 1, 1, 1]
    # In forward chain representative of {0, 1, 2} was index 0 (coord 0.1*W);
    # In reversed chain representative is index 1 (coord 0.9*W): representatives differ!
    assert not np.allclose(chain[0], chain[::-1][rep_rev[1]])

    # All 24 permutations must preserve the coordinate partition {0, 1, 2} and {3}
    for perm in itertools.permutations(range(4)):
        perm = list(perm)
        permuted_chain = chain[perm]
        rep = _weld(permuted_chain)
        partition = _partition_by_coordinates(rep, perm)
        assert partition == expected_partition, f"Failed for permutation {perm}: {partition}"


# ---------------------------------------------------------------------------
# Requirement 5: Dense 3D small lattice spanning multiple W cells
# ---------------------------------------------------------------------------


def test_dense_3d_lattice_fallback_partition_and_displacement_bound():
    """Dense 3D small lattice spanning multiple W cells:

    - Adjacent points are spaced <= W/2, chaining into a wide component > W across axes.
    - Fallback partition equals plain-grid cell partition (independent interval math).
    - Per-axis representative displacement is strictly <= W.
    """
    w = WELD_M
    # Coordinates along each axis: steps within W / 2 (0.4 * W, 0.5 * W, 0.4 * W)
    # Span is 1.6 * W - 0.3 * W = 1.3 * W > W
    axis_coords = [0.3 * w, 0.7 * w, 1.2 * w, 1.6 * w]
    pts = np.array(list(itertools.product(axis_coords, axis_coords, axis_coords)), dtype=np.float64)
    assert len(pts) == 64

    # Independent plain-grid cell grouping:
    expected_cell_groups = defaultdict(list)
    for idx, p in enumerate(pts):
        cell_key = (
            math.floor(p[0] / w),
            math.floor(p[1] / w),
            math.floor(p[2] / w),
        )
        expected_cell_groups[cell_key].append(idx)
    expected_partition = {frozenset(indices) for indices in expected_cell_groups.values()}
    # 2 intervals on X * 2 on Y * 2 on Z = 8 cells
    assert len(expected_partition) == 8

    rep = _weld(pts)
    actual_partition = _partition(rep)
    assert actual_partition == expected_partition

    # Per-axis displacement bound: |v[i] - v[rep[i]]| <= W for all axes
    disp = np.abs(pts - pts[rep])
    max_disp_per_axis = disp.max(axis=0)
    assert (max_disp_per_axis <= w).all(), f"Displacement exceeded W: {max_disp_per_axis / w}"


# ---------------------------------------------------------------------------
# Requirement 6: Non-wide diagonal cluster (L_inf guarantee vs Euclidean distance)
# ---------------------------------------------------------------------------


def test_non_wide_diagonal_cluster_per_axis_guarantee_not_euclidean():
    """A diagonal pair with per-axis differences < W/2 but Euclidean distance > W/2

    welds to the same representative in _weld, demonstrating a per-axis (Chebyshev)
    guarantee rather than a Euclidean distance threshold.
    """
    w = WELD_M
    p0 = np.array([0.0, 0.0, 0.0], dtype=np.float64)
    p1 = np.array([0.4 * w, 0.4 * w, 0.4 * w], dtype=np.float64)
    pts = np.array([p0, p1])

    # Per-axis difference is 0.4 * W < W / 2 = 0.5 * W
    diffs = np.abs(p1 - p0)
    assert (diffs < w / 2).all()

    # Euclidean distance is sqrt(0.4^2 + 0.4^2 + 0.4^2) * W = sqrt(0.48) * W ≈ 0.693 * W > W / 2
    euclidean_dist = math.dist(p0, p1)
    assert euclidean_dist > w / 2

    # Cluster span is 0.4 * W <= W, so it is not wide (no fallback)
    assert diffs.max() <= w

    rep = _weld(pts)
    assert rep[0] == rep[1]


# ---------------------------------------------------------------------------
# Requirement 7: Distinguish translation-invariant close pairs from grid-dependent wide chain
# ---------------------------------------------------------------------------


def test_distinguish_grid_dependent_translations_from_close_pair_controls():
    """Distinguish close-pair controls (guaranteed welding invariant to translation)

    from wide chain fallback (intentionally grid-dependent partition under translation).
    """
    w = WELD_M

    # 1. Guaranteed close-pair control:
    # Points within W/2 on every axis must weld regardless of translation offset.
    pair = np.array([[0.0, 0.0, 0.0], [0.35 * w, 0.35 * w, 0.0]], dtype=np.float64)
    translations = [-2.5, -1.0, -0.25, 0.0, 0.33, 0.5, 0.7, 1.0, 1.25, 4.0]
    for offset in translations:
        shifted_pair = pair + offset * w
        rep = _weld(shifted_pair)
        assert rep[0] == rep[1], f"Close pair failed to weld at translation {offset} * W"

    # 2. Intentionally grid-dependent wide chain translations:
    # For a wide chain, the plain grid cells define the fallback partition boundaries.
    chain = np.array([
        [0.1, 0.0, 0.0],
        [0.5, 0.0, 0.0],
        [0.9, 0.0, 0.0],
        [1.3, 0.0, 0.0],
    ], dtype=np.float64) * w

    # Offset 0.0: points in [0, W) are {0, 1, 2}; point in [W, 2W) is {3}
    part_0 = _partition(_weld(chain))
    assert part_0 == {frozenset({0, 1, 2}), frozenset({3})}

    # Offset +0.25 * W: points become [0.35, 0.75, 1.15, 1.55] * W
    # Points in [0, W) are {0, 1}; points in [W, 2W) are {2, 3}
    part_25 = _partition(_weld(chain + np.array([0.25 * w, 0.0, 0.0])))
    assert part_25 == {frozenset({0, 1}), frozenset({2, 3})}

    # Offset +0.60 * W: points become [0.70, 1.10, 1.50, 1.90] * W
    # Point in [0, W) is {0}; points in [W, 2W) are {1, 2, 3}
    part_60 = _partition(_weld(chain + np.array([0.60 * w, 0.0, 0.0])))
    assert part_60 == {frozenset({0}), frozenset({1, 2, 3})}


# ---------------------------------------------------------------------------
# Requirement 8: Task-local in-memory mutation sensitivity tests
# ---------------------------------------------------------------------------


def test_in_memory_mutation_removing_shifted_grids_is_detected():
    """Verify that removing the 7 shifted grids (using plain grid alone)

    fails the boundary-crossing close-pair contract.
    """
    w = WELD_M

    def _weld_mutation_no_shifted_grids(v):
        """Mutated weld: only plain grid shift=(0, 0, 0), missing 7 half-shifted grids."""
        sets = _Sets(len(v))
        keys = np.floor(v / w).astype(np.int64)
        _, first, inverse = np.unique(keys, axis=0, return_index=True, return_inverse=True)
        grid0 = first[inverse.ravel()]
        for i, j in enumerate(grid0):
            if i != j:
                sets.union(int(j), i)
        return np.array([sets.find(i) for i in range(len(v))])

    # Points crossing boundary 1.0 * W with difference 0.2 * W <= W/2
    p1 = np.array([0.9 * w, 0.0, 0.0])
    p2 = np.array([1.1 * w, 0.0, 0.0])
    pts = np.array([p1, p2])

    # Baseline production weld passes:
    rep_prod = _weld(pts)
    assert rep_prod[0] == rep_prod[1]

    # Mutated weld fails: plain grid splits them into separate representatives
    rep_mut = _weld_mutation_no_shifted_grids(pts)
    assert rep_mut[0] != rep_mut[1], "Mutation without shifted grids was not detected!"


def test_in_memory_mutation_disabling_wide_fallback_is_detected():
    """Verify that disabling the wide-component fallback fails both

    the wide-chain partition contract and the bounded displacement contract.
    """
    w = WELD_M

    def _weld_mutation_no_wide_fallback(v):
        """Mutated weld: 8 shifted grids but wide fallback is disabled."""
        sets = _Sets(len(v))
        grids = []
        for shift in itertools.product((0.0, 0.5), repeat=3):
            keys = np.floor(v / w + np.asarray(shift)).astype(np.int64)
            _, first, inverse = np.unique(keys, axis=0, return_index=True, return_inverse=True)
            grids.append(first[inverse.ravel()])
            for i, j in enumerate(grids[-1]):
                if i != j:
                    sets.union(int(j), i)
        # Omit: wide fallback logic (rep[wide] = grids[0][wide])
        return np.array([sets.find(i) for i in range(len(v))])

    # Case 1: Wide chain partition failure
    chain = np.array([
        [0.1, 0.0, 0.0],
        [0.5, 0.0, 0.0],
        [0.9, 0.0, 0.0],
        [1.3, 0.0, 0.0],
    ], dtype=np.float64) * w

    rep_mut_chain = _weld_mutation_no_wide_fallback(chain)
    part_mut_chain = _partition(rep_mut_chain)
    # Production gives {0, 1, 2} and {3}; mutation incorrectly collapses all into {0, 1, 2, 3}
    assert part_mut_chain != {frozenset({0, 1, 2}), frozenset({3})}
    assert part_mut_chain == {frozenset({0, 1, 2, 3})}

    # Case 2: 3D lattice displacement violation (> W)
    axis_coords = [0.3 * w, 0.7 * w, 1.2 * w, 1.6 * w]
    lattice = np.array(list(itertools.product(axis_coords, axis_coords, axis_coords)), dtype=np.float64)
    rep_mut_lattice = _weld_mutation_no_wide_fallback(lattice)
    max_disp = np.abs(lattice - lattice[rep_mut_lattice]).max(axis=0)
    # Mutation causes vertices to move by up to 1.3 * W (> W)
    assert (max_disp > w).any(), "Mutation without wide fallback was not detected by displacement!"
