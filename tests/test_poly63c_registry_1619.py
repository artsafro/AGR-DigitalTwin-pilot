"""63C exported Revit window names must identify both family and type."""
import importlib.util
from pathlib import Path
import runpy

import numpy as np

import pytest

HOOK = Path(__file__).resolve().parents[1] / 'jobs/POLY63-C/hooks/stage2_63c.py'
FAMILY = 'Окн_Окн_2 Ств Комфорт'
TYPE = 'Комфорт ОК-17-19'


def _stage2_plan():
    spec = importlib.util.spec_from_file_location('stage2_plan_63c_reg', HOOK.parents[2] / 'POLY63-A/stage2-1619/hooks/stage2_plan.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_unresolved_types_list_every_matched_opening():
    """#1714: the 63C name check runs inside the shared matcher and lists every claimed opening before STOP."""
    hook = runpy.run_path(str(HOOK))
    names = [' [22038485]', FAMILY + ' [42]', TYPE + ' [43]']
    ops = [{'id': k, 'status': 'ok', 'why': [], 'w': 1.0, 'h': 2.0,
            'border': [[3.0 * k, 0, 0.6], [3.0 * k + 1, 0, 0.6], [3.0 * k + 1, 0, 2.6], [3.0 * k, 0, 2.6]]}
           for k in (19, 21, 33)]
    modules = [{'centre': np.array([3.0 * k + 0.5, 0.0, 1.6]), 'W': 1.0, 'H': 2.0} for k in (19, 21, 33)]
    reg = [{'sill_m': '0.6', 'module_opening_1based': str(n + 1), 'fbx_model': name,
            'ref_centroid_x': str(modules[n]['centre'][0]), 'ref_centroid_y': '0.0'} for n, name in enumerate(names)]
    with pytest.raises(SystemExit) as exc:
        hook['match_registry'](_stage2_plan(), ops, reg, modules)
    for opening, instance in [(19, 22038485), (21, 42), (33, 43)]:
        assert f'opening {opening} (body detection ID)' in str(exc.value)
        assert f'instance {instance}' in str(exc.value)
    assert str(exc.value).count('Unresolved Revit family/type') == 3


def test_complete_source_label_is_preserved():
    label = FAMILY + ' ' + TYPE
    revit_type = runpy.run_path(str(HOOK))['revit_type']
    assert revit_type(label + ' [22038485]') == label
    assert [revit_type(n) for n in (' [22038485]', FAMILY + ' [42]', TYPE + ' [43]', label, label + ' [x]', None)]         == [None] * 6


def test_plan_requires_a_new_output_path(tmp_path):
    write_plan = runpy.run_path(str(HOOK))['write_plan']
    floor = tmp_path / 'floor.json'
    original = b'{"opening_sources": []}\r\n'
    floor.write_bytes(original)
    with pytest.raises(FileExistsError):
        write_plan(floor, {}, [])
    assert floor.read_bytes() == original

    output = tmp_path / 'plan.json'
    write_plan(output, {'type': TYPE}, [])
    assert output.read_bytes() == ('{"report": {"type": "' + TYPE + '"}, "elements": []}').encode('utf8')
