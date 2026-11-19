"""63C exported Revit window names must identify both family and type."""
from pathlib import Path
import runpy

import pytest

HOOK = Path(__file__).resolve().parents[1] / 'jobs/POLY63-C/hooks/stage2_63c.py'
FAMILY = 'Окн_Окн_2 Ств Комфорт'
TYPE = 'Комфорт ОК-17-19'


def test_unresolved_types_list_every_matched_opening():
    names = {19: ' [22038485]', 21: FAMILY + ' [42]', 33: TYPE + ' [43]'}
    with pytest.raises(ValueError) as exc:
        runpy.run_path(str(HOOK))['registry_types'](names)
    for opening, instance in [(19, 22038485), (21, 42), (33, 43)]:
        assert f'opening {opening}, instance {instance}' in str(exc.value)


def test_complete_source_label_is_preserved():
    label = FAMILY + ' ' + TYPE
    assert runpy.run_path(str(HOOK))['registry_types']({19: label + ' [22038485]'}) == {19: label}
