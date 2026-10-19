"""Synthetic regression fixtures; no real-object delivery acceptance."""
import functools
import importlib.util
import json
import random
from pathlib import Path

import numpy as np
import pytest
import technical_library.mesh_audit.core as mesh_audit_core
import twinqa.geometry.checks as geometry_checks
import twinqa.geometry.winding as winding_rule
from technical_library.mesh_audit.core import inspect_mesh
from technical_library.texture_tiles.cli import build, draw, validate
from tools.facades_texture_pattern import raster
from twinqa.geometry.mesh import Soup


def test_mesh_material_interface_and_loose_component():
    result = inspect_mesh([(0,0,0),(1,0,0),(1,1,0),(0,1,0),(3,0,0),(4,0,0)],
                          [(0,1,2),(0,2,3)], [(4,5)], [1,2])
    assert result['boundary_edges'] == 4
    assert result['material_interface_edges'] == 1
    assert result['connected_components'] == 2
    assert result['loose_edges'] == 1
    assert result['vertices_unused_by_faces'] == 2
    assert result['triangles'] == 2
    assert result['delivery_passed'] is False


def test_mesh_duplicates_and_degeneracy_are_separate():
    result = inspect_mesh([(0,0,0),(1,0,0),(2,0,0),(0,0,0)], [(0,1,2),(2,1,0)])
    assert result['duplicate_vertices_rounded'] == 1
    assert result['duplicate_faces_by_vertex_set'] == 1
    assert result['zero_area_faces_fan'] == 2


@pytest.mark.parametrize('vertices,faces,edges,materials', [
    ([(float('nan'),0,0)],[],[],None),
    ([(0,0,0)],[(0,1,2)],[],None),
    ([(0,0,0)],[],[(0,2)],None),
    ([(0,0,0)],[],[],[1]),
])
def test_mesh_invalid_inputs(vertices,faces,edges,materials):
    with pytest.raises(ValueError):
        inspect_mesh(vertices,faces,edges,materials)


def outward_unit_cube():
    # Quads wound so the fan normal from face[0] points outward.
    vertices = [(0,0,0),(1,0,0),(1,1,0),(0,1,0),(0,0,1),(1,0,1),(1,1,1),(0,1,1)]
    faces = [(0,3,2,1),(4,5,6,7),(0,1,5,4),(3,7,6,2),(1,2,6,5),(0,4,7,3)]
    return vertices, faces


def test_mesh_closed_cube_report_counters_are_zero():
    vertices, faces = outward_unit_cube()
    result = inspect_mesh(vertices, faces)
    assert result['inconsistent_winding_edges'] == 0
    assert result['near_duplicate_vertices'] == 0
    assert result['self_intersecting_polygons'] == 0
    assert result['delivery_passed'] is False


def test_mesh_one_reversed_quad_marks_four_winding_edges():
    vertices, faces = outward_unit_cube()
    faces = [faces[0][::-1]]+faces[1:]
    result = inspect_mesh(vertices, faces)
    assert result['inconsistent_winding_edges'] == 4
    assert result['near_duplicate_vertices'] == 0
    assert result['self_intersecting_polygons'] == 0


def test_mesh_near_duplicate_within_default_millimetre():
    vertices, faces = outward_unit_cube()
    vertices = vertices+[(0.0005,0,0)]
    faces = [(8,3,2,1)]+faces[1:]
    result = inspect_mesh(vertices, faces)
    assert result['near_duplicate_vertices'] == 1
    assert result['duplicate_vertices_rounded'] == 0
    tight = inspect_mesh(vertices, faces, near_m=0.0001)
    assert tight['near_duplicate_vertices'] == 0
    assert tight['duplicate_vertices_rounded'] == 0


def test_mesh_bowtie_quad_counts_one_polygon():
    vertices, faces = outward_unit_cube()
    vertices = vertices+[(10,0,0),(11,0,0),(10,0,1),(11,0,1)]
    faces = faces+[(8,9,10,11)]
    result = inspect_mesh(vertices, faces)
    assert result['self_intersecting_polygons'] == 1
    assert result['inconsistent_winding_edges'] == 0


@pytest.mark.parametrize('near_m', [0, -0.001, float('nan')])
def test_mesh_near_m_rejects_non_positive(near_m):
    vertices, faces = outward_unit_cube()
    with pytest.raises(ValueError):
        inspect_mesh(vertices, faces, near_m=near_m)


def tile(**changes):
    return dict(id=1,udim=1001,rgb=[120,150,180],size=[16,16],kind='solid',**changes)


def test_tile_archive_readback_and_no_overwrite(tmp_path):
    config = {'tiles':[tile()]}
    result = build(config,tmp_path/'new')
    assert result['archive_readback_equal']
    assert result['tiles'][0]['solid']
    assert result['delivery_passed'] is False
    with pytest.raises(FileExistsError):
        build(config,tmp_path/'new')


def test_tile_rejects_duplicate_and_non_numeric_filenames():
    with pytest.raises(ValueError):
        validate({'tiles':[tile(),tile()]})
    candidate = tile(); candidate['udim'] = '../input'
    with pytest.raises(ValueError):
        validate({'tiles':[candidate]})


def test_metric_tile_reuses_canonical_raster():
    candidate = tile(); candidate.update(kind='metric_pattern',pattern_id=102,extent_m=[1.2,1.6])
    expected = raster(102,16,16,[1.2,1.6],np.array(candidate['rgb'])/255)
    expected = np.rint(np.clip(expected,0,1)*255).astype(np.uint8)
    assert np.array_equal(np.asarray(draw(candidate)),expected)
    candidate['extent_m'] = [0,1]
    with pytest.raises(ValueError):
        validate({'tiles':[candidate]})


_ZERO_DEFECTS = (
    'inconsistent_winding_edges',
    'near_duplicate_vertices',
    'self_intersecting_polygons',
    'duplicate_vertices_rounded',
    'zero_area_faces_fan',
)


def test_mesh_deleted_face_shows_only_as_boundary_delta():
    vertices, faces = outward_unit_cube()
    clean = inspect_mesh(vertices, faces)
    cut = inspect_mesh(vertices, faces[1:])
    assert clean['boundary_edges'] == 0
    assert cut['boundary_edges'] == 4
    for key in _ZERO_DEFECTS:
        assert clean[key] == 0
        assert cut[key] == 0


_ETALON_BASE = {
    'bench-b01-box': 28,
    'bench-b02-corner-niche': 52,
    'bench-b02t-terrace': 90,
}
# winding, near duplicates, bowtie polygons, boundary delta from the clean body
_ETALON_DEFECT = {
    'clean': (0, 0, 0, 0),
    'flip1': (4, 0, 0, 0),
    'del1': (0, 0, 0, 4),
    'dup05': (0, 1, 0, 4),
    'bowtie': (0, 0, 1, 4),
}


@functools.lru_cache(maxsize=None)
def _offline_variants():
    path = Path(__file__).resolve().parents[1] / 'experiments' / 'blender-mesh-audit-live' / 'offline.py'
    spec = importlib.util.spec_from_file_location('mesh_audit_live_offline', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.variants


@functools.lru_cache(maxsize=None)
def _bench_bodies(bench):
    from dt_ai.geometry.from_spec import BuildInputs, build as build_body
    from dt_ai.spec.model import Spec

    root = Path(__file__).resolve().parents[1]
    folder = root / 'benchmark' / bench
    spec = Spec.model_validate(json.loads((folder / 'spec.json').read_text(encoding='utf-8')))
    obj = json.loads((folder / 'object.json').read_text(encoding='utf-8'))
    body = build_body(spec, BuildInputs.from_object(obj))['meshes'][0]
    made = _offline_variants()(body['vertices'], body['polygons'])
    return {
        name: (tuple(tuple(float(c) for c in point) for point in verts),
               tuple(tuple(int(i) for i in poly) for poly in polys))
        for name, (verts, polys) in made.items()
    }


@pytest.mark.parametrize('bench,base', list(_ETALON_BASE.items()))
@pytest.mark.parametrize('variant,expected', list(_ETALON_DEFECT.items()))
def test_engine_body_etalon_defects(bench, base, variant, expected):
    winding, near, bowtie, extra = expected
    vertices, polygons = _bench_bodies(bench)[variant]
    result = inspect_mesh(vertices, polygons)
    assert result['inconsistent_winding_edges'] == winding
    assert result['near_duplicate_vertices'] == near
    assert result['self_intersecting_polygons'] == bowtie
    assert result['boundary_edges'] == base + extra
    assert result['delivery_passed'] is False


def test_winding_rule_is_shared():
    assert mesh_audit_core.same_direction_edges is winding_rule.same_direction_edges
    assert geometry_checks.same_direction_edges is winding_rule.same_direction_edges


def _brute_same_direction(loops, count):
    bad = 0
    for u in range(count):
        for v in range(u + 1, count):
            starts = []
            for loop in loops:
                n = len(loop)
                for i in range(n):
                    a = loop[i]
                    b = loop[(i + 1) % n]
                    if a == b or {a, b} != {u, v}:
                        continue
                    starts.append(a)
            if len(starts) == 2 and starts[0] == starts[1]:
                bad += 1
    return bad


def test_same_direction_edges_matches_brute_force():
    rng = random.Random(145)
    for _ in range(300):
        count = rng.randint(4, 8)
        loops = [[rng.randrange(count) for _ in range(rng.randint(3, 5))]
                 for _ in range(rng.randint(1, 8))]
        assert winding_rule.same_direction_edges(loops) == _brute_same_direction(loops, count)


def _fan_triangles(faces):
    tris = []
    for face in faces:
        for i in range(1, len(face) - 1):
            tris.append((int(face[0]), int(face[i]), int(face[i + 1])))
    return tris


def test_core_and_twinqa_winding_agree_on_fan_triangulated_meshes():
    rng = random.Random(145)
    for _ in range(200):
        vertices, base = outward_unit_cube()
        faces = [face[::-1] if rng.randrange(2) else face for face in base]
        if rng.randrange(2):
            del faces[rng.randrange(len(faces))]
        reported = inspect_mesh(vertices, faces)['inconsistent_winding_edges']
        tris = _fan_triangles(faces)
        soup = Soup(np.asarray(vertices, dtype=float), np.asarray(tris, dtype=np.int64),
                    np.zeros(len(tris), dtype=int), None, {})
        judged = int(geometry_checks.winding_bad_edges(soup, 1e-6)[0])
        assert reported == judged
