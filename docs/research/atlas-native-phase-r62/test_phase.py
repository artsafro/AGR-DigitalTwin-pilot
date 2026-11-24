"""Synthetic selection witness; the replay also checks native loop and render parity."""
import pytest

from phase import panel_cell

CELL = {'panel': (0.125, 0.25, 0.125)}


def test_only_entire_panel_is_selected():
    assert panel_cell([(0.126, 0.26), (0.24, 0.26), (0.24, 0.3)], CELL) == 'panel'
    assert panel_cell([(0.3, 0.26), (0.4, 0.26), (0.4, 0.3)], CELL) is None
    with pytest.raises(ValueError, match='partial'):
        panel_cell([(0.19, 0.26), (0.4, 0.26), (0.4, 0.3)], CELL)
