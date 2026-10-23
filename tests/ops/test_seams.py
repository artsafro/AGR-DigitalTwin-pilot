"""new-case: join and atomic seam simplification regression controls (#530)."""
import numpy as np
import pytest

from dt_ai.ops.inv_quads import PolyMesh
from dt_ai.ops.inv_xview import XviewTolerance, face_pairs


def band(cols=30, sag=0.002):
    v = [(0, 0, 0), (10, 0, 0), (10, 0, 3.5), (0, 0, 3.5)]
    xs = np.linspace(0, 10, cols + 1)
    bottom = [3] + list(range(4, 4 + cols - 1)) + [2]
    v += [(x, sag * np.sin(np.pi * x / 10), 3.5) for x in xs[1:-1]]
    top = list(range(len(v), len(v) + cols + 1))
    v += [(x, sag * np.sin(np.pi * x / 10), 4.05) for x in xs]
    return PolyMesh(v, ((0, 1, 2, 3),)), PolyMesh(v, tuple(
        (bottom[i], bottom[i+1], top[i+1], top[i]) for i in range(cols)))


def contacts(mesh):
    return [p for p in face_pairs(mesh, XviewTolerance()) if 'contact' in p[2]]


def test_join_conforms_sagged_band_to_glass_boundary_without_separating():
    from dt_ai.ops.seams import join_parts
    glass, strip = band()
    before = PolyMesh(glass.vertices, glass.faces + strip.faces)
    assert len(contacts(before)) == 30
    result = join_parts({'glass': glass, 'band': strip})
    assert contacts(result.mesh) == []
    assert len(result.mesh.faces) == 31
    assert len(result.face_sources) == 31
    assert result.max_weld_m <= 0.002000001
    assert result.displacements == {}
    assert len(result.mesh.faces[0]) == 33
    assert np.array_equal(glass.vertices, strip.vertices)


def test_simplification_updates_other_side_in_same_operation():
    from dt_ai.ops.seams import simplify_part
    glass, strip = band(cols=6, sag=0)
    # Split the glass into six panels with exactly the band's shared top row.
    v = strip.vertices.tolist()
    top = [3] + list(range(4, 9)) + [2]
    bottom = list(range(len(v), len(v) + 7))
    v += [(x, 0, 0) for x in np.linspace(0, 10, 7)]
    panels = tuple((bottom[i], bottom[i+1], top[i+1], top[i]) for i in range(6))
    source = PolyMesh(v, panels)
    result = simplify_part({'glass': source, 'band': strip}, 'glass')
    assert len(result.mesh.faces) == 7
    assert contacts(result.mesh) == []
    assert len(result.mesh.faces[0]) == 9  # 4 corners + 5 boundary seam vertices
    assert result.face_sources[0] == tuple(('glass', i) for i in range(6))
    assert source.faces == panels


@pytest.mark.parametrize('shift', [(-0.003, 0, 0), (0, 0.003, 0), (0, 0.006, 0)])
def test_original_unit_cases_bowtie_corner(shift):
    from dt_ai.ops.seams import join_parts
    glass, strip = band(1, sag=0)
    v = glass.vertices.tolist() + [(10 + shift[0], shift[1], 3.5 + shift[2])]
    glass = PolyMesh(v, ((0, 1, len(v)-1, 3),))
    result = join_parts({'glass': glass, 'band': strip})
    assert contacts(result.mesh) == []
    if shift[1] < 0.006:
        assert len(set(result.mesh.faces[0]) & set(result.mesh.faces[1])) == 2


@pytest.mark.parametrize('dz, expected', [(0, 1), (.003, 1), (.005, 1), (.006, 0), (.032, 0)])
def test_original_unit_cases_rail_soffit_separations(dz, expected):
    from dt_ai.ops.seams import join_parts
    soffit = PolyMesh([(0,0,0),(0,2,0),(2,2,0),(2,0,0)], ((0,1,2,3),))
    rail = PolyMesh([(-3.358,.5,dz),(-3.358,.565,dz),(.012,.565,dz),(.012,.5,dz)], ((0,1,2,3),))
    v = np.concatenate([soffit.vertices, rail.vertices])
    assert len(contacts(PolyMesh(v, ((0,1,2,3),(4,5,6,7))))) == expected
    if expected:
        from dt_ai.ops.operations import OperationRefused
        with pytest.raises(OperationRefused, match='pairs'):
            join_parts({'soffit': soffit, 'rail': rail})
        result = join_parts({'soffit': soffit, 'rail': rail}, displacements={'rail': (0,0,.006)})
    else:
        result = join_parts({'soffit': soffit, 'rail': rail})
    assert contacts(result.mesh) == []


@pytest.mark.parametrize('seed', range(12))
def test_generated_transformed_seams_and_face_vertex_conservation(seed):
    from dt_ai.ops.seams import join_parts
    rng = np.random.default_rng(seed)
    matrix, _ = np.linalg.qr(rng.normal(size=(3,3)))
    offset = rng.uniform(-100,100,3)
    g, b = band(cols=seed+2, sag=(-1)**seed * .002)
    parts = {name: PolyMesh(m.vertices @ matrix + offset, m.faces) for name,m in [('glass',g),('band',b)]}
    snapshots = {name: m.vertices.copy() for name,m in parts.items()}
    result = join_parts(parts)
    assert face_pairs(result.mesh, XviewTolerance()) == []
    expected_faces = {(name, i) for name,m in parts.items() for i in range(len(m.faces))}
    assert {x for s in result.face_sources for x in s} == expected_faces
    all_vertices = {(name,i) for name,m in parts.items() for i in range(len(m.vertices))}
    actual = [x for s in result.vertex_sources for x in s]
    actual += [(name,i) for name,i,why in result.dropped_vertices]
    assert len(actual) == len(set(actual))
    assert set(actual) == all_vertices
    for name,m in parts.items():
        np.testing.assert_array_equal(m.vertices, snapshots[name])


@pytest.mark.parametrize('d', [0, .003, .005, np.nextafter(.006, 0), float('nan'), float('inf')])
def test_sub_clearance_or_nonfinite_separation_refused(d):
    from dt_ai.ops.seams import join_parts
    g,b = band(1,0)
    with pytest.raises(ValueError):
        join_parts({'glass': g, 'band': b}, displacements={'glass': (0,d,0)})


@pytest.mark.parametrize('bad', [{}, {'empty': PolyMesh(np.empty((0,3)), ())}, {'raw': object()}])
def test_empty_partial_unsupported_refused(bad):
    from dt_ai.ops.seams import join_parts
    with pytest.raises(ValueError):
        join_parts(bad)


def test_unknown_duplicate_and_failed_postcondition_are_atomic():
    from dt_ai.ops.seams import join_parts
    from dt_ai.ops.operations import OperationRefused
    g,b = band(1,0)
    saved = g.vertices.copy()
    with pytest.raises(ValueError, match='duplicated'):
        join_parts({'a':g, 'b':g})
    with pytest.raises(ValueError, match='missing'):
        join_parts({'a':g}, displacements={'missing':(0,.006,0)})
    with pytest.raises(OperationRefused, match='pairs'):
        join_parts({'a':g, 'b':PolyMesh(g.vertices.copy(),g.faces)})
    np.testing.assert_array_equal(g.vertices,saved)


@pytest.mark.parametrize('sag', [0, .002, -.002, .005])
@pytest.mark.parametrize('cols', [1, 2, 7, 30])
def test_generated_column_and_face_threshold_bounds(cols, sag):
    from dt_ai.ops.seams import join_parts
    from dt_ai.ops.operations import OperationRefused
    g,b = band(cols,sag)
    try:
        result = join_parts({'glass':g,'band':b})
    except OperationRefused:
        # At the closed tolerance boundary roundoff may refuse, never return dirty.
        assert abs(sag) == .005
    else:
        assert face_pairs(result.mesh,XviewTolerance()) == []
        assert result.max_weld_m <= .005


def test_all_neighbours_conform_and_outputs_do_not_alias_inputs():
    from dt_ai.ops.seams import join_parts, simplify_part
    g,b = band(8,0)
    left = PolyMesh(b.vertices.copy(),b.faces[:4])
    right = PolyMesh(b.vertices.copy(),b.faces[4:])
    parts = {'glass':g,'left':left,'right':right}
    result = simplify_part(parts,'glass')
    assert face_pairs(result.mesh,XviewTolerance()) == []
    assert len(result.mesh.faces[0]) == 11
    assert {name for labels in result.face_sources for name,i in labels} == set(parts)
    result.mesh.vertices[:] += 100
    np.testing.assert_array_equal(g.vertices,b.vertices)
    assert join_parts(parts).mesh.vertices.max() < 11


@pytest.mark.parametrize('line_m', [-1, .003, np.nan, np.inf, True])
def test_simplification_rejects_invalid_threshold(line_m):
    from dt_ai.ops.seams import simplify_part
    g,b = band(1,0)
    with pytest.raises(ValueError):
        simplify_part({'glass':g,'band':b},'glass',line_m=line_m)


def test_mesh_adapter_and_fresh_process_import():
    import subprocess
    import sys
    from dt_ai.ops.invariants import Mesh
    from dt_ai.ops.seams import join_parts
    g,b = band(1,0)
    triangles = Mesh(g.vertices, np.array([[0,1,2],[0,2,3]]))
    assert face_pairs(join_parts({'glass':triangles,'band':b}).mesh,XviewTolerance()) == []
    run = subprocess.run([sys.executable,'-c',
        'from dt_ai.ops.seams import join_parts, simplify_part; '
        'from dt_ai.ops.operations import OperationRefused; print("IMPORT_OK")'],
        capture_output=True,text=True,check=True)
    assert run.stdout.strip() == 'IMPORT_OK'


def test_report_includes_coincident_weld_motion_not_only_boundary_snaps():
    from dt_ai.ops.seams import join_parts
    mesh = PolyMesh([(0,0,0),(1,0,0),(0,1,0),
                     (0,0,5e-9),(0,0,1),(1,0,1)], ((0,1,2),(3,4,5)))
    result = join_parts({'part':mesh})
    assert result.max_weld_m == pytest.approx(5e-9, abs=1e-15)
