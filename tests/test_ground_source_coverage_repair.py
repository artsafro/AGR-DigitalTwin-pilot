"""Synthetic source-bound residual coverage repair, preserving existing vertices/IDs."""
import importlib.util
from pathlib import Path
import numpy as np
import pytest
from shapely.geometry import Polygon,MultiPolygon
from dt_ai.geometry import ground_cake as g

spec=importlib.util.spec_from_file_location('ground_371_coverage_job',Path(__file__).resolve().parents[1]/'jobs/VATUTINO-SITE/build_ground_v015.py')
job=importlib.util.module_from_spec(spec);spec.loader.exec_module(job)


def fixture(extra):
    p=Polygon([(0,0),(1+extra,0),(1+extra,1),(0,1)])
    plan=g.Plan(MultiPolygon([p]),[],[g.Layer('tile','tile',0,MultiPolygon([p]))],.006)
    v=np.array([[0,0,100],[1,0,100],[1,1,100],[0,1,100]],float)
    f=np.array([[0,1,2],[0,2,3]])
    return g.Mesh(v,f,['TileLight']*2,np.zeros(2,int),v[f,:2]/4,4.),plan


def test_existing_boundary_endpoints_restore_a_thirty_micrometre_residual():
    mesh,plan=fixture(.00223);before=mesh.verts.copy()
    assert g.measure_coverage(mesh,plan,.0022)['uncovered_beyond_tol_m2']>0
    fixed,receipt=job.restore_source_coverage(mesh,plan)
    assert g.measure_coverage(fixed,plan,.0022)['uncovered_beyond_tol_m2']==0
    assert g.measure_coverage(fixed,plan,.0022)['outside_surface_beyond_tol_m2']==0
    assert np.linalg.norm(fixed.verts-before,axis=1).max()<.00005
    assert np.array_equal(fixed.faces,mesh.faces) and fixed.slot==mesh.slot
    assert np.array_equal(mesh.verts,before)
    assert receipt['moved_vertices']


def test_large_residual_is_not_silently_repaired():
    mesh,plan=fixture(.003)
    with pytest.raises(ValueError,match='bound|residual'):
        job.restore_source_coverage(mesh,plan)
