"""new-case: reproduce Blender library-loader mutation of borrowed catalogue object-name lists."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest


class StopProbe(Exception):
    pass


class Rotation:
    def __init__(self, *args):
        pass

    def to_track_quat(self, *args):
        return self

    def to_matrix(self):
        return self

    def transposed(self):
        return self


def test_showcase_does_not_lend_catalogue_list_to_blender(monkeypatch, tmp_path):
    class Loader:
        def __enter__(self):
            self.destination = SimpleNamespace(objects=[])
            return None, self.destination

        def __exit__(self, *args):
            # Actual bpy.data.libraries.load replaces names with loaded Object
            # instances in the same assigned list on context-manager exit.
            self.destination.objects[:] = [SimpleNamespace(name='R01_vpm_body')]

    def stop_after_load(obj):
        raise StopProbe

    scene = SimpleNamespace(unit_settings=SimpleNamespace(),
                            collection=SimpleNamespace(objects=SimpleNamespace(link=stop_after_load)))
    bpy = SimpleNamespace(ops=SimpleNamespace(wm=SimpleNamespace(read_factory_settings=lambda **kw: None)),
                          context=SimpleNamespace(scene=scene),
                          data=SimpleNamespace(libraries=SimpleNamespace(load=lambda *a, **kw: Loader())))
    monkeypatch.setitem(sys.modules, 'bpy', bpy)
    monkeypatch.setitem(sys.modules, 'mathutils', SimpleNamespace(Matrix=Rotation, Vector=Rotation))
    path = Path(__file__).resolve().parents[2]/'tools/library/build_roof_blender.py'
    spec = importlib.util.spec_from_file_location('roof_showcase_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assets = [{'variants': {'vpm': {'path': 'assets/R01/vpm.blend', 'objects': ['R01_vpm_body']}}}]
    before = json.dumps(assets)
    with pytest.raises(StopProbe):
        module.showcase(assets, tmp_path)
    assert json.dumps(assets) == before
