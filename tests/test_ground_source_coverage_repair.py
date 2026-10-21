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


@pytest.mark.parametrize('offset',[(-7548.1575,-15354.741),(-7600.,-15400.)])
def test_world_coordinate_coverage_repair_does_not_accept_or_stall_on_roundoff_slivers(offset):
    from shapely.affinity import translate
    mesh,plan=fixture(.00223)
    mesh.verts[:,:2]+=offset
    plan.surface=translate(plan.surface,xoff=offset[0],yoff=offset[1])
    fixed,receipt=job.restore_source_coverage(mesh,plan)
    report=g.measure_coverage(fixed,plan,.0022)
    assert report['uncovered_beyond_tol_m2']==0 and report['outside_surface_beyond_tol_m2']==0


@pytest.mark.parametrize('kind',['empty_plan','partial_levels','nan','inf','empty_faces','exact_bound'])
def test_coverage_restoration_fails_closed_on_unmeasurable_or_at_bound_inputs(kind):
    mesh,plan=fixture(.00225 if kind=='exact_bound' else 0)
    if kind=='empty_plan':plan.surface=MultiPolygon([])
    if kind=='partial_levels':mesh.level=np.array([],int)
    if kind in ('nan','inf'):mesh.verts[0,0]=float(kind)
    if kind=='empty_faces':mesh.faces=np.empty((0,3),int);mesh.level=np.array([],int);mesh.slot=[];mesh.uv=np.empty((0,3,2))
    with pytest.raises(ValueError):job.restore_source_coverage(mesh,plan)


def test_real_derived_root_roundoff_residual_is_repaired_not_waived():
    import json
    from shapely.geometry import shape
    data=json.loads((Path(__file__).parent/'data/ground-v015-tongue-root.json').read_text())
    v=np.array(data['verts']);f=np.array(data['faces'])
    mesh=g.Mesh(v,f,['TileLight']*len(f),np.zeros(len(f),int),v[f,:2]/4,4.)
    outline=shape(data['source'])
    plan=g.Plan(MultiPolygon([outline]),[],[g.Layer('tile','tile',0,MultiPolygon([outline]))],.006)
    fixed,receipt=job.restore_source_coverage(mesh,plan)
    report=g.measure_coverage(fixed,plan,.0022)
    assert report['uncovered_beyond_tol_m2']==0 and report['outside_surface_beyond_tol_m2']==0


def test_large_residual_is_not_silently_repaired():
    mesh,plan=fixture(.003)
    with pytest.raises(ValueError,match='bound|residual'):
        job.restore_source_coverage(mesh,plan)
