"""Contract tests for the engine's 1D plan-axis weld (`dt_ai.geometry.from_spec._Weld`).

new-case: engine 1D axis weld — fixed-anchor priority and non-transitive free groups

The engine welds one plan axis at a time (spec `weld_m`, user 2026-10-13 "how the user welds by
hand"): a value within the weld (inclusive) of a fixed anchor becomes that anchor; other values
within the weld of a group's smallest value join that group at the smallest; a value off every
group stays where it is; fixed values (an earlier weld's results) never move. This file pins that
existing behaviour with finite literal coordinates and independently hand-calculated expectations,
so a refactor cannot silently change the contract. Synthetic data; not a real object.
"""

import pytest

from dt_ai.geometry.from_spec import _Weld


def mapped(weld, queries):
    """Coordinate -> welded coordinate for an ordered list of queries (keeps duplicates)."""
    return [weld(v) for v in queries]


def test_free_values_weld_non_transitively():
    # 0.004 is 4 mm from 0, past the 3 mm weld: it must not collapse through the 0.002 bridge.
    weld = _Weld([0.0, 0.002, 0.004], w=0.003)
    assert mapped(weld, [0.0, 0.002, 0.004]) == [0.0, 0.0, 0.004]
    # free groups are [0.0 .. 0.002] and [0.004 .. 0.004]
    assert weld.values() == [0.0, 0.004]


def test_duplicates_and_permutations_give_the_same_mapping():
    base = [0.0, 0.002, 0.004]
    permuted = [0.004, 0.0, 0.002]
    duplicated = [0.0, 0.0, 0.002, 0.004, 0.002]
    weld_base = _Weld(base, w=0.003)
    weld_perm = _Weld(permuted, w=0.003)
    weld_dup = _Weld(duplicated, w=0.003)
    for v in [0.0, 0.002, 0.004]:
        assert weld_base(v) == weld_perm(v) == weld_dup(v)
    assert weld_base.values() == weld_perm.values() == weld_dup.values()


def test_fixed_anchors_win_and_use_the_sorted_stable_nearest_rule():
    weld = _Weld([0.001, 0.003], w=0.003, fixed=[0.0, 0.004])
    assert weld(0.001) == 0.0     # 1 mm from 0, 3 mm from 0.004
    assert weld(0.003) == 0.004   # 1 mm from 0.004, 3 mm from 0
    # exact midpoint 0.002: both anchors are 2 mm away -> the lower fixed wins (sorted/stable)
    assert weld(0.002) == 0.0


def test_fixed_anchors_are_unchanged_even_when_closer_than_the_weld():
    weld = _Weld([0.001, 0.003], w=0.003, fixed=[0.0, 0.004])
    assert weld(0.0) == 0.0
    assert weld(0.004) == 0.004
    # fixed entries come first in values(), unchanged
    assert weld.values()[:2] == [0.0, 0.004]


def test_free_group_retains_its_smallest_coordinate():
    weld = _Weld([0.020, 0.022], w=0.003)
    assert weld(0.020) == 0.020
    assert weld(0.022) == 0.020
    assert weld.values() == [0.020]


def test_query_outside_every_fixed_and_group_span_is_unchanged():
    weld = _Weld([0.020, 0.022], w=0.003, fixed=[0.0, 0.004])
    for v in [-0.010, 0.010, 0.050, 1.0]:
        assert weld(v) == v


def test_values_returns_fixed_entries_then_free_group_minima():
    weld = _Weld([0.001, 0.003, 0.020, 0.022], w=0.003, fixed=[0.0, 0.004])
    # 0.001 snaps to 0 and 0.003 to 0.004, so the only free group is [0.020 .. 0.022]
    assert weld.values() == [0.0, 0.004, 0.020]


def test_caller_owned_input_lists_are_unchanged():
    values = [0.004, 0.0, 0.002]
    fixed = [0.004, 0.0]
    snapshot_values = list(values)
    snapshot_fixed = list(fixed)
    _Weld(values, w=0.003, fixed=fixed)
    assert values == snapshot_values
    assert fixed == snapshot_fixed
