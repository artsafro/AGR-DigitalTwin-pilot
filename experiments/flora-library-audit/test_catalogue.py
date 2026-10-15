"""Synthetic regression probes for the standalone Flora audit, not production QA."""
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location('flora_catalogue', Path(__file__).with_name('catalogue.py'))
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def node(handle, x, y, z):
    return {'handle': handle, 'position': [x, y, z]}


def test_front_labels_use_xz_not_xy():
    meshes = [node(1, 10, 10, 0), node(2, 10, 10, -3)]
    assert mod.pair(node(3, 10, 8.75, -3.4), meshes, 'xz') == [2]
    assert mod.pair(node(3, 10, 8.75, -3.4), meshes, 'xy') == [1, 2]


def test_ties_report_all_candidates_not_first():
    assert mod.pair(node(3, 0, 0, 0), [node(2, 1, 0, 0), node(1, -1, 0, 0)], 'xz') == [1, 2]


def test_empty_and_far_unpaired():
    assert mod.pair(node(3, 0, 0, 0), [], 'xz') == []
    assert mod.pair(node(3, 0, 0, 0), [node(1, 500, 0, 0)], 'xz', max_distance=5) == []


def test_generated_order_invariance():
    for x in range(-20, 21):
        meshes = [node(1, x, 10, 0), node(2, x, 10, -3)]
        label = node(3, x, 8, -3.4)
        assert mod.pair(label, meshes, 'xz') == mod.pair(label, meshes[::-1], 'xz') == [2]


def test_dimensions_are_world_bbox_meters():
    assert mod.dimensions({'bbox': [[-1, -2, -0.1], [1, 2, 3.9]]}, 1) == [2, 4, 4]
    assert mod.dimensions({'bbox': [[0, 0, 0], [100, 200, 300]]}, 100) == [1, 2, 3]


def test_profile_preserves_uncertain_and_raw_tokens():
    assert mod.profiles('LP -> HP') == ['NPM', 'VPM']
    assert mod.profiles('HP') == ['VPM']
    assert mod.profiles('LP') == ['NPM']
    assert mod.profiles('unknown') == []


def test_fresh_outputs_cannot_escape_or_overwrite(tmp_path):
    assert mod.fresh_path(tmp_path, 'item.max') == tmp_path / 'item.max'
    (tmp_path / 'item.max').touch()
    with pytest.raises(FileExistsError):
        mod.fresh_path(tmp_path, 'item.max')
    for name in ['../source.max', 'C:/source.max', '/source.max', 'nested/item.max', '..\\source.max']:
        with pytest.raises(ValueError):
            mod.fresh_path(tmp_path, name)
