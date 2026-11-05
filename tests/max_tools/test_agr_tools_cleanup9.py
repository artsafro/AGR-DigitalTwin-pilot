"""new-case: export.cleanup rework (#979, branch E3), plain pytest, no pymxs.

Source: CA & UDP Cleaner v010 `ClearCustomAttributesAndObjProp_010.ms`
sha256 c1c52e21cf5adf67e6c35a5719669754a7511335573f778128f2a0c26904e53c (T06/clear_ca_udp_010, measured Max 2026; idea
only, no code, #853). Measured defects: by default it deletes vertex channels 0/-1/-2 and every animation key (14 node +
2 material), removes AGR_EXPORT_PATH, works on the originals, Undo does not bring the channels back, writes
`MapChannel:1 = UV` on nodes without channel 1. `cleanup_v010` below models that behaviour (strict xfail, RED);
export_core.cleanup_plan is the 0.9 logic (GREEN). Copies only: the scene side is runtime.cleanup_apply.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'
sys.path.insert(0, str(ROOT / 'src'))
from twinqa.export_hygiene import repair_plan  # noqa: E402

sys.path.pop(0)


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ex = _load(PKG / 'export_core.py', 'agr_tools_export_cleanup9')
V010 = pytest.param('v010', marks=pytest.mark.xfail(strict=True, reason='source behaviour (T06/clear_ca_udp_010)'))
UDP = 'AGR_EXPORT_PATH = C:/x/0101_Polygon_01.fbx\r\nfoo = bar\r\nMapChannel:1 = UV\r\nMapChannel:3 = AO\r\n'


def dump(name='SM_A_001_Main', udp=UDP, channels=(1, 3)):
    """The acceptance copy of #979: CA, UDP (AGR_EXPORT_PATH, foo), vertex colour and 16 keys."""
    return {'name': name, 'custom_attributes': {'base': ['agrData'], 'node': [], 'modifiers': [], 'materials': ['m']},
            'user_props': udp, 'map_channels': list(channels)}


FACT = {'vertex_channels': [0, -1, -2], 'keys': 16}


def cleanup_v010(objects, facts, options=None):
    """CA & UDP Cleaner v010 with its UI defaults (Vertex Channels ON, Animation Keys ON): everything goes."""
    plan = repair_plan(objects)
    for item, fact in zip(plan['objects'], facts):
        item['actions'].append({'action': 'delete_vertex_channels', 'channels': fact['vertex_channels']})
        item['actions'].append({'action': 'delete_animation_keys', 'keys': fact['keys']})
        item['kept_udp'] = []
    return plan


def cleanup_core(objects, facts, options=None):
    return ex.cleanup_plan(repair_plan(objects), facts, options)


def _actions(item):
    return [a['action'] for a in item['actions']]


@pytest.mark.parametrize('impl', [V010, 'core'])
def test_default_keeps_vertex_channels_and_keys(impl):
    (item,) = (cleanup_v010 if impl == 'v010' else cleanup_core)([dump()], [FACT])['objects']
    assert 'delete_vertex_channels' not in _actions(item) and 'delete_animation_keys' not in _actions(item)


@pytest.mark.parametrize('impl', [V010, 'core'])
def test_default_keeps_agr_export_path(impl):
    (item,) = (cleanup_v010 if impl == 'v010' else cleanup_core)([dump()], [FACT])['objects']
    assert 'AGR_EXPORT_PATH = C:/x/0101_Polygon_01.fbx' in item['cleaned']['user_props']
    assert item['kept_udp'] == ['AGR_EXPORT_PATH = C:/x/0101_Polygon_01.fbx']


def test_other_udp_and_extra_map_channels_still_go():
    (item,) = cleanup_core([dump()], [FACT])['objects']
    udp = next(a for a in item['actions'] if a['action'] == 'clear_user_defined_lines')
    assert udp['lines'] == ['foo = bar'] and 'delete_map_channels' in _actions(item)
    assert item['cleaned']['user_props'] == 'MapChannel:1 = UV\r\nAGR_EXPORT_PATH = C:/x/0101_Polygon_01.fbx\r\n'


def test_only_pipeline_udp_means_no_udp_action():
    (item,) = cleanup_core([dump(udp='AGR_EXPORT_PATH = a.fbx\r\nMapChannel:1 = UV\r\n', channels=(1,))],
                           [{'vertex_channels': [], 'keys': 0}])['objects']
    assert 'clear_user_defined_lines' not in _actions(item) and item['kept_udp'] == ['AGR_EXPORT_PATH = a.fbx']


def test_opt_in_channels_and_keys_are_planned_only_when_asked():
    (item,) = cleanup_core([dump()], [FACT], {'channels': True})['objects']
    assert {'action': 'delete_vertex_channels', 'channels': [0, -1, -2]} in item['actions']
    assert 'delete_animation_keys' not in _actions(item)
    (item,) = cleanup_core([dump()], [FACT], {'keys': True})['objects']
    assert {'action': 'delete_animation_keys', 'keys': 16} in item['actions']
    assert 'delete_vertex_channels' not in _actions(item)
    (item,) = cleanup_core([dump()], [{'vertex_channels': [], 'keys': 0}], {'channels': True, 'keys': True})['objects']
    assert 'delete_vertex_channels' not in _actions(item) and 'delete_animation_keys' not in _actions(item)


def test_scene_ops_follow_the_options_of_the_preview():
    (item,) = cleanup_core([dump()], [FACT], {'channels': True, 'keys': True})['objects']
    assert ex.cleanup_scene_ops(item, {'channels': True, 'keys': True}) == [
        ('vertex_channel', 0), ('vertex_channel', -1), ('vertex_channel', -2), ('keys',)]
    with pytest.raises(ValueError, match='opt-in option channels'):
        ex.cleanup_scene_ops(item, {'keys': True})  # an action without its option: an edited preview
    (plain,) = cleanup_core([dump()], [FACT])['objects']
    assert ex.cleanup_scene_ops(plain) == []


def test_channels_list_names_vertex_channels_only_with_the_option():
    (item,) = cleanup_core([dump()], [FACT], {'channels': True})['objects']
    assert ex._cleanup_channels(item['actions'], {'channels': True}) == [3, 0, -1, -2]
    (plain,) = cleanup_core([dump()], [FACT])['objects']
    assert ex._cleanup_channels(plain['actions']) == [3]


def test_plan_input_is_never_modified_and_facts_are_strict():
    plan = repair_plan([dump()])
    before = repr(plan)
    ex.cleanup_plan(plan, [FACT], {'channels': True, 'keys': True})
    assert repr(plan) == before
    for bad in ({'vertex_channels': [1], 'keys': 0}, {'vertex_channels': [], 'keys': -1}, {'keys': 0},
                {'vertex_channels': [0, 0], 'keys': 0}, {'vertex_channels': [], 'keys': True}):
        with pytest.raises(ValueError):
            ex.cleanup_plan(repair_plan([dump()]), [bad])
    with pytest.raises(ValueError, match='one cleanup fact'):
        ex.cleanup_plan(repair_plan([dump()]), [])
    with pytest.raises(ValueError, match='unknown cleanup option'):
        ex.cleanup_plan(repair_plan([dump()]), [FACT], {'everything': True})


def test_node_without_channel_1_is_refused_not_given_a_uv_name():
    """v010 wrote `MapChannel:1 = UV` on nodes without channel 1 (measured); here it stays unrepairable."""
    (item,) = cleanup_core([dump(udp='', channels=())], [{'vertex_channels': [], 'keys': 0}])['objects']
    assert item['unrepairable'] and 'MapChannel:1' not in item['cleaned']['user_props']


def test_pipeline_keys_match_the_runtime_held_off_set():
    src = (PKG / 'runtime.py').read_text(encoding='utf-8')
    start = src.index('_HELD_OFF = {')
    held = set(eval(src[start + len('_HELD_OFF = '):src.index('}', start) + 1]))  # noqa: S307 - our own literal
    assert held == set(ex.PIPELINE_UDP)
