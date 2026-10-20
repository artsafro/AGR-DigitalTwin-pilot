"""Synthetic topology witnesses, not botanical ground truth."""
import importlib.util
from pathlib import Path


def load():
    path=Path(__file__).parents[1]/'tools/flora/geometry_parts.py'
    assert path.exists(), 'geometry-only decomposition module is missing'
    spec=importlib.util.spec_from_file_location('geometry_parts',path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod


def test_duplicate_uv_indices_join_only_across_same_geometry_edge():
    mod=load()
    record={'vertices':[[0,0,0],[1,0,0],[1,0,1],[0,0,1]],
            'faces':[[0,1,2],[0,2,3]],
            'uv':[[0,0],[1,0],[1,1],[0,0],[1,1],[0,1]],
            'uvfaces':[[0,1,2],[3,4,5]], 'face_material_ids':[1,1]}
    assert mod.uv_charts(record)==[[0,1]]
    record['uv'][3]=[.1,0]
    assert mod.uv_charts(record)==[[0],[1]]
