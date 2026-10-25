"""Pure collection of source diffuse/opacity pairs for atlas review sheets (#369)."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/flora'))
from review_atlas_regions import sheet_slices, source_bound_pairs


def _standard(name, diffuse, opacity, bound=True, mode=0):
    return {'class':'Standardmaterial','name':name,'bindings':{'opacityMapEnable':bound},
            'slot_paths':{'diffuseMap':diffuse,'opacityMap':opacity},
            'slot_settings':{'opacityMap':{'monoOutput':mode}}}


def test_source_pairs_traverse_standard_and_multimaterial_once(tmp_path):
    maps=tmp_path/'maps';maps.mkdir()
    for name in ('a.png','b.png','c.png','d.png'):(maps/name).write_bytes(b'x')
    assert 'pymxs' not in Path(source_bound_pairs.__code__.co_filename).read_text(encoding='utf-8')
    nested={'class':'Multimaterial','submaterials':[
        _standard('leaf','A.PNG','B.PNG',mode=1),
        {'class':'Multimaterial','submaterials':[
            _standard('bark','c.png','d.png',mode=0),
            _standard('unbound','a.png','b.png',bound=False)]}]}
    inventory={'failures':[],'scenes':{
        'original':{'records':{'One':{'material':nested},'Two':{'material':_standard('again','a.png','b.png',mode=1)}}},
        'florio':{'records':{'Three':{'material':_standard('copy','a.png','b.png',mode=1)}}}}}
    job={'scenes':[{'tag':'original','maps':str(maps)},{'tag':'florio','maps':str(maps)}]}
    pairs=source_bound_pairs(inventory,job)
    assert [(Path(p['diffuse']).name,Path(p['opacity']).name,p['alpha_mode'],p['tag']) for p in pairs]==[
        ('a.png','b.png',True,'original'),('c.png','d.png',False,'original')]
    assert all(p['diffuse_key']==p['diffuse'].replace('\\','/').lower() for p in pairs)
    assert sheet_slices(0)==[] and sheet_slices(8)==[(0,8)] and sheet_slices(9)==[(0,8),(8,9)]
