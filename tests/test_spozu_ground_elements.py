"""Synthetic DXF element paths: typed adapter output, not a second parser (#295)."""
import ezdxf
import pytest
from adapters.cad.spozu import SpozuConfig, SpozuConfigError, read_spozu_dxf


def config(**kw):
    return SpozuConfig.from_dict({'boundary': {'layer': 'B'}, 'ground_elements': {
        'curb_garden': ['CURB'], 'stairs': ['STAIR']}, **kw})


def test_element_paths_nested_world_metres_and_provenance():
    d = ezdxf.new(); d.header['$INSUNITS'] = 4
    m = d.modelspace(); m.add_lwpolyline([(0,0),(10000,0),(10000,10000),(0,10000)], close=True, dxfattribs={'layer':'B'})
    b = d.blocks.new('treads'); line = b.add_line((0,0), (1000,0), dxfattribs={'layer':'0'})
    ins = m.add_blockref('treads',(2000,3000),dxfattribs={'layer':'STAIR','rotation':90})
    curb = m.add_lwpolyline([(1000,1000),(9000,1000)],dxfattribs={'layer':'CURB','const_width':80})
    r = read_spozu_dxf(d,config()); es = r.to_dict().get('ground_elements',[])
    assert len(es) == 3
    c = next(x for x in es if x['handle']==curb.dxf.handle)
    assert c['role']=='curb_garden' and c['geometry']['coordinates']==[[1.,1.,0.],[9.,1.,0.]]
    assert c['source_width_m'] == pytest.approx(.08)
    t = next(x for x in es if x['ref']==f'{ins.dxf.handle}>{line.dxf.handle}')
    assert t['geometry']['coordinates'][0] == pytest.approx([2,3,0])
    assert t['geometry']['coordinates'][1] == pytest.approx([2,4,0])
    assert t['container']==ins.dxf.handle
    assert not any(f.code=='unmapped_layer' for f in r.findings)


def test_unsupported_element_retained_with_reason_not_silently_lost():
    d=ezdxf.new(); d.header['$INSUNITS']=6
    d.modelspace().add_circle((1,1),1,dxfattribs={'layer':'CURB'})
    es=read_spozu_dxf(d,config()).to_dict().get('ground_elements',[])
    assert len(es)==1 and es[0]['geometry'] is None and es[0]['problem']


def test_element_layer_double_mapping_rejected():
    with pytest.raises(SpozuConfigError, match='mapped twice'):
        config(coverings=[{'type':'x','layers':['CURB']}])
