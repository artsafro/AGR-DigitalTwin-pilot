"""new-case: native finalizer refuses shading/attributes it cannot preserve."""
import pytest
from tools.blender.course_grid_finalize import check_native_metadata


def test_supported_native_metadata_matches_actual_pilot_contract():
    check_native_metadata(dict(custom_normals=False,uv_channels=1,uv_names=['UVMap'],edge_seams=0,
      attributes=[dict(name='UVMap',domain='CORNER',type='FLOAT2'),
       dict(name='sharp_face',domain='FACE',type='BOOLEAN'),
       dict(name='agr_source_face',domain='FACE',type='INT')]))


@pytest.mark.parametrize('override', [dict(custom_normals=True),dict(uv_channels=2),
 dict(edge_seams=1),dict(attributes=[dict(name='crease_edge',domain='EDGE',type='FLOAT')]),
 dict(attributes=[dict(name='not_a_uv_layer',domain='CORNER',type='FLOAT2')])])
def test_unsupported_native_metadata_fails_before_mutation(override):
    meta=dict(custom_normals=False,uv_channels=1,uv_names=['UVMap'],edge_seams=0,
      attributes=[dict(name='UVMap',domain='CORNER',type='FLOAT2')]);meta.update(override)
    with pytest.raises(ValueError):check_native_metadata(meta)
