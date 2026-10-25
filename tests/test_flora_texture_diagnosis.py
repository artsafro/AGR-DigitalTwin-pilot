"""Pure-Python diagnosis guards and measurement regression probes (#369)."""
import importlib.util
import math
from pathlib import Path
import pytest

SPEC = importlib.util.spec_from_file_location('flora_diag', Path(__file__).parents[1]/'tools/flora/diagnose_texture.py')
diag = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diag)


@pytest.mark.parametrize('u,v,expected', [(0,0,(0,99)),(1,1,(99,0)),(.25,.75,(25,25))])
def test_uv_image_origin(u,v,expected):
    assert diag.uv_pixel((u,v),100)==expected


@pytest.mark.parametrize('uv', [(),(0,), (math.nan,0),(0,math.inf),(-.01,0),(1.01,0)])
def test_uv_invalid_fail_closed(uv):
    with pytest.raises(ValueError): diag.uv_pixel(uv,100)


def test_bitmap_basename_not_map_name(tmp_path):
    image=tmp_path/'Maps_Bereza_01.png'; image.write_bytes(b'original')
    assert diag.resolve_bitmap(r'G:\old\Maps_Bereza_01.png',tmp_path)==image
    with pytest.raises(ValueError,match='absent'):diag.resolve_bitmap('absent.png',tmp_path)


def test_no_input_output_aliases(tmp_path):
    source=tmp_path/'source';source.write_bytes(b'original')
    alias=tmp_path/'alias';alias.hardlink_to(source)
    with pytest.raises(ValueError):diag.guard_outputs([source],[alias])
    assert source.read_bytes()==b'original'
    with pytest.raises(ValueError):diag.guard_outputs([source],[source])
    with pytest.raises(ValueError):diag.guard_outputs([source],[tmp_path/'new',tmp_path/'new'])
    diag.guard_outputs([source],[tmp_path/'fresh'])


def test_measure_requires_complete_mapping():
    source={'oak':{'uv_sha256':'abc','triangles':10}}
    ours={'oak':{'uv_sha256':'abc','triangles':10}}
    assert diag.compare_inventory(source,ours)=={'total':1,'uv_identical':['oak'],'uv_changed':[]}
    with pytest.raises(ValueError,match='oak'):diag.compare_inventory({},ours)
    with pytest.raises(ValueError):diag.compare_inventory({}, {})


def test_generated_accounting():
    source={str(i):{'uv_sha256':str(i),'triangles':i+1} for i in range(99)}
    ours={k:dict(v) for k,v in source.items()}
    for i in range(0,99,3):ours[str(i)]['uv_sha256']='changed'
    result=diag.compare_inventory(source,ours)
    assert len(result['uv_identical'])==66
    assert len(result['uv_changed'])==33
    assert set(result['uv_identical']+result['uv_changed'])==set(source)


@pytest.mark.parametrize('count',[0,-1,float('nan'),float('inf'),True,'10'])
def test_invalid_mesh_counts(count):
    record={'uv_sha256':'a','triangles':count}
    with pytest.raises(ValueError):diag.compare_inventory({'oak':record},{'oak':record})


def test_slot_paths_survive_duplicate_display_names():
    record={'name':'oak','material':{'slot_paths':{'diffuseMap':r'G:\old\diffuse.png'},
                                  'textures':[{'name':'Bitmaptexture'},{'name':'Bitmaptexture'}]}}
    receipt={'resolved_bitmaps':[{'source_copy':'scratch/opacity.png'},{'source_copy':'scratch/diffuse.png'}]}
    assert diag.bound_diffuse(record,receipt)=='scratch/diffuse.png'
    record['material']['slot_paths']['diffuseMap']='missing.png'
    with pytest.raises(ValueError,match='missing.png'):diag.bound_diffuse(record,receipt)


@pytest.mark.parametrize('a,b',[([],[]),([[0,0,0]],[]),([[float('nan'),0,0]],[[0,0,0]]),([[1,2]],[[1,2]])])
def test_bad_geometry_rejected(a,b):
    with pytest.raises(ValueError):diag.centered_deviation_mm(a,b)


def test_centered_measure_is_translation_invariant():
    assert diag.centered_deviation_mm([[0,0,0],[1,2,3]],[[10,20,30],[11,22,33]])==0
    assert diag.centered_deviation_mm([[0,0,0],[1,0,0]],[[0,0,0],[1.002,0,0]])==pytest.approx(1)


def test_native_scripts_never_save_a_scene():
    import ast
    for name in ('diagnose_texture_max.py','render_texture_diagnosis_max.py','probe_texture_diagnosis_max.py'):
        tree=ast.parse((Path(__file__).parents[1]/'tools/flora'/name).read_text())
        calls={n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
        assert not calls.intersection({'saveMaxFile','saveNodes','exportFile','saveplus','SaveSystemDefaults'})


def test_overlay_invalid_topology_writes_nothing(tmp_path):
    from PIL import Image
    image=tmp_path/'source.png';Image.new('RGB',(8,8),'white').save(image)
    output=tmp_path/'overlay.png'
    for record in [{'uv':[],'uvfaces':[]},{'uv':[[0,0]],'uvfaces':[[0,0,3]]}]:
        with pytest.raises(ValueError):diag.overlay(record,image,output)
        assert not output.exists()
    with pytest.raises(ValueError):diag.overlay({'uv':[[0,0]],'uvfaces':[[0,0,0]]},image,image)
    assert Image.open(image).getpixel((0,0))==(255,255,255)


def test_replacement_accounting_and_unmapped_error():
    row={'name':'oak','triangles':1,'uv_sha256':'abc','material':{'class':'Standardmaterial','textures':[{'filename':'old.png'}]}}
    other={**row,'material':{'class':'Standardmaterial','textures':[{'filename':'new.png'}]}}
    assert diag.replacement_evidence({'oak':row},{'oak':other})[0]['maps_replaced']
    other['material']['textures']=[]
    with pytest.raises(ValueError,match='oak'):diag.replacement_evidence({'oak':row},{'oak':other})
