"""new-case: Endpoint-midpoint and bounded dyadic cluster conservation contracts.

Synthetic finite inputs only; no tolerance, nonfinite or performance policy.
The oracle checks the returned partition, rather than implementing clustering.
"""

from itertools import combinations

import pytest

from dt_ai.geometry.grid_patches import clustered


LATTICE = tuple(n / 16 for n in (-4, -3, -1, 0, 1, 4, 6))
SPANS = (1 / 16, 1 / 8, 1 / 4, 1 / 2)


@pytest.mark.parametrize("values, expected", [
    ([0, 1 / 16, 1 / 4], {0: 1 / 8, 1 / 16: 1 / 8, 1 / 4: 1 / 8}),
    ([-1 / 4, -3 / 16, 0], {-1 / 4: -1 / 8, -3 / 16: -1 / 8, 0: -1 / 8}),
    ([0, 1 / 16, 1 / 4, 3 / 8],
     {0: 1 / 8, 1 / 16: 1 / 8, 1 / 4: 1 / 8, 3 / 8: 3 / 8}),
], ids=["positive-skew", "negative-skew", "maximal-skew-with-singleton"])
def test_skewed_clusters_use_extreme_midpoint_not_mean_or_first(values, expected):
    before = values.copy()
    assert clustered(values, span=1 / 4) == expected
    assert values == before


def assert_partition_contract(values, span, mapping):
    """Inspect inverse images; do not predict groups with a greedy scan."""
    keys = sorted(set(values))
    assert set(mapping) == set(keys), "every distinct coordinate must survive"
    assert list(mapping) == keys, "mapping keys must be sorted"

    groups = [
        [value for value in keys if mapping[value] == representative]
        for representative in sorted(set(mapping.values()))
    ]
    assert [value for group in groups for value in group] == keys, (
        "groups must be ordered contiguous blocks of input coordinates"
    )
    for group in groups:
        low, high = min(group), max(group)
        representative = mapping[low]
        assert representative == (low + high) / 2, "endpoint midpoint required"
        assert high - low <= span, "full span must be bounded"
        assert all(abs(value - representative) <= span / 2 for value in group)

    for earlier, later in combinations(groups, 2):
        assert min(later) > min(earlier) + span, "earlier group must be maximal"


@pytest.mark.parametrize("mask", range(1 << len(LATTICE)))
@pytest.mark.parametrize("span", SPANS)
def test_all_dyadic_subsets_conserve_partition_and_affine_mapping(mask, span):
    # All 128 subsets of seven fixed locations, including the empty subset.
    coordinates = [value for i, value in enumerate(LATTICE) if mask & (1 << i)]
    before = coordinates.copy()
    mapping = clustered(coordinates, span=span)
    assert coordinates == before
    assert_partition_contract(coordinates, span, mapping)

    # Unequal multiplicities distinguish endpoint choice from weighted averaging.
    repeated = [value for i, value in enumerate(coordinates) for _ in range(i % 3 + 1)]
    variants = (
        repeated,
        repeated[::-1],
        repeated[1:] + repeated[:1],
        repeated[::2] + repeated[1::2],
    )
    for values in variants:
        snapshot = values.copy()
        actual = clustered(values, span=span)
        assert values == snapshot
        assert actual == mapping, "permutation and multiplicity must not change clusters"
        assert_partition_contract(values, span, actual)

    # Exact dyadic arithmetic: translation, contraction, expansion and their composition.
    for scale, shift in ((1, -1 / 2), (1 / 2, 0), (4, 0), (2, 1 / 4)):
        transformed = [scale * value + shift for value in repeated[::-1]]
        snapshot = transformed.copy()
        actual = clustered(transformed, span=scale * span)
        expected = {
            scale * value + shift: scale * representative + shift
            for value, representative in mapping.items()
        }
        assert actual == expected
        assert transformed == snapshot
        assert_partition_contract(transformed, scale * span, actual)
