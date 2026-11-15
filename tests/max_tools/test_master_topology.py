"""new-case: pre-triangulation master topology contract (#1420), synthetic fixtures."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def core():
    path = ROOT / 'adapters/max/agr_tools/master_topology_core.py'
    assert path.is_file(), 'pre-export master topology core is missing'
    spec = importlib.util.spec_from_file_location('master_topology_test', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_mixed_master():
    report = core().check([{'name': 'synthetic', 'face_degrees': [3, 4, 5]}])
    assert report['status'] == 'fail'
    obj = report['objects'][0]
    assert obj == {'name': 'synthetic', 'status': 'fail', 'faces': 3,
                   'triangles': 1, 'triangle_share': 1 / 3, 'quads': 1,
                   'ngons': 1, 'ngon_face_ids': [3]}
