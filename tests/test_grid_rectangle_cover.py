"""Exhaustive coverage-count and label-conservation oracle for grid_patches.rectangles.

Independent of the greedy row-growth algorithm: every test reconstructs a
per-cell coverage-count grid and a label grid by enumerating the half-open
rectangles the extractor emits, then checks the reconstruction against the
source. The exhaustive value is the property (all 512 binary 3x3 masks and all
729 ternary-label 2x3 masks), not extra snapshots.

new-case: exhaustive small-mask coverage + label-conservation oracle
"""

import inspect
import itertools

import numpy as np
import pytest

from dt_ai.geometry import grid_patches


def _rects(mask):
    return list(grid_patches.rectangles(mask))


def _reconstruct(rects, shape):
    """Coverage-count grid and label grid from half-open rectangles, by enumeration."""
    coverage = np.zeros(shape, dtype=int)
    labels = np.zeros(shape, dtype=int)
    for rect in rects:
        i0, i1, j0, j1, value = rect
        coverage[i0:i1, j0:j1] += 1
        labels[i0:i1, j0:j1] = value
    return coverage, labels


def _assert_covers(mask, rects):
    """Independent oracle: rectangles are valid and cover the source exactly once."""
    shape = mask.shape
    nz = mask != 0
    coverage = np.zeros(shape, dtype=int)
    labels = np.zeros(shape, dtype=int)
    total_area = 0
    for rect in rects:
        assert len(rect) == 5, "rectangle is not a 5-tuple"
        i0, i1, j0, j1, value = rect
        assert 0 <= i0 < i1 <= shape[0], "off-by-one row bounds"
        assert 0 <= j0 < j1 <= shape[1], "off-by-one column bounds"
        assert value != 0, "rectangle with a zero label"
        coverage[i0:i1, j0:j1] += 1
        labels[i0:i1, j0:j1] = value
        total_area += (i1 - i0) * (j1 - j0)
    assert (coverage[nz] >= 1).all(), "missing-cell: nonzero source cell uncovered"
    assert (coverage[nz] <= 1).all(), "overlap-count: nonzero source cell covered more than once"
    assert (labels[nz] == mask[nz]).all(), "label-conservation: reconstructed label != source label"
    assert (coverage[~nz] == 0).all(), "zero source cell covered"
    assert (labels[~nz] == 0).all(), "zero source cell labeled"
    assert total_area == int(nz.sum()), "total rectangle area != nonzero source count"


def _verify(mask, extractor=grid_patches.rectangles):
    """Full contract for one mask: coverage, labels, determinism, input unchanged.

    ``extractor`` is injectable so oracle mutations and in-memory production
    mutations exercise the same verification path as the real function. The
    source is snapshotted before the call, and dtype/shape/values are asserted
    against that snapshot after the call (not against the possibly-mutated mask).
    """
    shape_before = mask.shape
    dtype_before = mask.dtype
    source = mask.copy()
    first = list(extractor(mask))
    second = list(extractor(mask))
    _assert_covers(source, first)
    assert first == second, "repeated call changed the decomposition"
    assert mask.shape == shape_before, "input shape changed"
    assert mask.dtype == dtype_before, "input dtype changed"
    np.testing.assert_array_equal(mask, source)
    return first


def _binary_masks_3x3():
    return [np.array(m, dtype=np.uint8).reshape(3, 3)
            for m in itertools.product((0, 1), repeat=9)]


def _ternary_masks_2x3():
    return [np.array(m, dtype=np.int8).reshape(2, 3)
            for m in itertools.product((0, 1, 2), repeat=6)]


_BINARY_IDS = ["".join(map(str, m)) for m in itertools.product((0, 1), repeat=9)]
_TERNARY_IDS = ["".join(map(str, m)) for m in itertools.product((0, 1, 2), repeat=6)]


@pytest.mark.parametrize("mask", _binary_masks_3x3(), ids=_BINARY_IDS)
def test_every_binary_3x3_mask_covers_exactly(mask):
    _verify(mask)


@pytest.mark.parametrize("mask", _ternary_masks_2x3(), ids=_TERNARY_IDS)
def test_every_ternary_2x3_mask_covers_exactly(mask):
    _verify(mask)


def test_acceptance_example():
    mask = np.array([[1, 2], [1, 0]], dtype=np.int8)
    rects = _verify(mask)
    coverage, labels = _reconstruct(rects, mask.shape)
    np.testing.assert_array_equal(coverage, np.array([[1, 1], [1, 0]]))
    np.testing.assert_array_equal(labels, mask)


_ASYMMETRIC_MASKS = {
    # Off-center hole plus a missing corner: asymmetric under transpose/rotate.
    "ring-hole": np.array([[1, 1, 1], [1, 0, 1], [0, 1, 1]], dtype=np.int8),
    # Asymmetric checkerboard (last cell empty instead of filled).
    "checkerboard": np.array([[1, 0, 1], [0, 1, 0], [1, 0, 0]], dtype=np.int8),
    # Adjacent unequal labels touching along several edges.
    "adjacent-labels": np.array([[1, 2, 0], [0, 1, 2], [2, 0, 1]], dtype=np.int8),
}

_TRANSFORMS = [
    ("transpose", lambda m: m.T.copy()),
    ("rot90", lambda m: np.rot90(m, 1)),
    ("rot180", lambda m: np.rot90(m, 2)),
    ("rot270", lambda m: np.rot90(m, 3)),
]


@pytest.mark.parametrize("mask_name", sorted(_ASYMMETRIC_MASKS))
def test_transpose_and_rotate_asymmetric_masks(mask_name):
    source = _ASYMMETRIC_MASKS[mask_name]
    for transform_name, fn in _TRANSFORMS:
        transformed = fn(source)
        rects = _rects(transformed)
        coverage, labels = _reconstruct(rects, transformed.shape)
        _assert_covers(transformed, rects)
        np.testing.assert_array_equal(coverage, (transformed != 0).astype(int))
        np.testing.assert_array_equal(labels, transformed)


def test_oracle_rejects_dropped_last_rectangle():
    mask = np.array([[1, 2], [1, 0]], dtype=np.int8)
    rects = _rects(mask)
    assert len(rects) >= 2
    with pytest.raises(AssertionError, match="missing-cell"):
        _assert_covers(mask, rects[:-1])


def test_oracle_rejects_duplicated_rectangle():
    mask = np.array([[1, 2], [1, 0]], dtype=np.int8)
    rects = _rects(mask)
    with pytest.raises(AssertionError, match="overlap-count"):
        _assert_covers(mask, rects + [rects[-1]])


def test_oracle_rejects_changed_label():
    mask = np.array([[1, 2], [1, 0]], dtype=np.int8)
    rects = _rects(mask)
    i0, i1, j0, j1, _ = rects[-1]
    relabeled = list(rects)
    relabeled[-1] = (i0, i1, j0, j1, 3)
    with pytest.raises(AssertionError, match="label-conservation"):
        _assert_covers(mask, relabeled)


@pytest.mark.filterwarnings("ignore:Setting the dtype on a NumPy array has been deprecated:DeprecationWarning")
def test_verify_rejects_input_dtype_mutation():
    mask = np.array([[1, 2], [1, 0]], dtype=np.int8)

    def mutate_dtype(m):
        m.dtype = np.uint8  # in-place reinterpretation changes the input dtype
        yield from grid_patches.rectangles(m)

    with pytest.raises(AssertionError, match="dtype"):
        _verify(mask, extractor=mutate_dtype)


_GROW_PREDICATE = "remaining[i, j1] == value"


def _mutated_rectangles_grow_across_label():
    """In-memory mutation of the production ``rectangles`` predicate: the
    horizontal run grows across any nonzero cell instead of only equal-valued
    cells, so adjacent unequal labels are mixed into one rectangle. The mutant
    is built from the production source at runtime (single token swap) and is
    never committed; the test restores the real function after the assertion.
    """
    source = inspect.getsource(grid_patches.rectangles)
    assert _GROW_PREDICATE in source, "production grow predicate token changed"
    mutated = source.replace(_GROW_PREDICATE, "remaining[i, j1] != 0")
    namespace = {}
    exec(mutated, namespace)
    return namespace["rectangles"]


def test_oracle_rejects_in_memory_production_predicate_mutation(monkeypatch):
    mask = np.array([[1, 2], [1, 0]], dtype=np.int8)
    baseline = _verify(mask)  # baseline GREEN before the mutation
    monkeypatch.setattr(grid_patches, "rectangles", _mutated_rectangles_grow_across_label())
    with pytest.raises(AssertionError, match="label-conservation"):
        _assert_covers(mask, list(grid_patches.rectangles(mask)))
    monkeypatch.undo()
    assert _verify(mask) == baseline  # baseline restored GREEN
