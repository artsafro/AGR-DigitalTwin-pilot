"""new-case: conservative source pixel-cell coverage survives rotated subpixel traces."""
import numpy as np
import pytest
from shapely.geometry import Polygon,box
from tools.materials import course_grid_native as native


def test_thin_source_cell_is_not_lost_between_target_pixel_centres():
    mask=np.zeros((5,5),dtype=bool);mask[2,2]=True
    centres=[[1.99,2.5],[3.01,2.5],[.5,.5]]
    result=native.raster_cell_intersections(mask,centres,[[1.1,0],[0,1.1]])
    assert result.tolist()==[True,True,False]


def test_touching_only_does_not_paint_a_neighbour():
    mask=np.zeros((3,3),dtype=bool);mask[1,1]=True
    assert native.raster_cell_intersections(mask,[[.5,1.5]],[[1,0],[0,1]]).tolist()==[False]


def test_generated_rotated_cells_match_independent_polygon_overlap():
    rng=np.random.default_rng(1326);mask=rng.random((9,9))<.12
    dark=[box(x,y,x+1,y+1) for y,x in zip(*np.where(mask))]
    for _ in range(20):
        angle=rng.uniform(-np.pi,np.pi);c,s=np.cos(angle),np.sin(angle)
        axes=np.array([[c,s],[-s,c]])*rng.uniform(.5,1.5)
        centres=rng.uniform(.5,8.5,(30,2))
        actual=native.raster_cell_intersections(mask,centres.tolist(),axes.tolist())
        expected=[]
        for point in centres:
            poly=Polygon([point+a*axes[0]/2+b*axes[1]/2 for a,b in [(1,1),(-1,1),(-1,-1),(1,-1)]])
            expected.append(any(poly.intersection(cell).area>1e-12 for cell in dark))
        assert actual.tolist()==expected


@pytest.mark.parametrize('centres,axes', [([],[[1,0],[0,1]]),([[float('nan'),1]],[[1,0],[0,1]]),
    ([[1,1]],[[1,0],[1,0]]),([[1,1]],[[float('inf'),0],[0,1]]),([[1,1]],[[50,0],[0,50]])])
def test_raster_coverage_refuses_invalid_or_unbounded_sampling(centres,axes):
    with pytest.raises(ValueError):
        native.raster_cell_intersections(np.zeros((3,3),bool),centres,axes)
