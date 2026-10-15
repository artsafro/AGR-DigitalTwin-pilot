"""New case #189: preserve one failed Poly FBX, try a derived Mesh snapshot.

Tree_LP's observed polygon-corner failure only. Four sheared flower variants
require max_flora_transform_repair.py instead (snapshot NODE retains shear).
Headless Max 2026 / dcc_batch.py, on COPY. Never save
source and never overwrite v003/v004 artifacts. Same 0.05mm/UV/finish matcher.
First capture the old native discrepancy; export only if the derived mesh matches
source snapshot before export. New binary/receipt goes to repairs-v006.
"""
import json
import sys
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
HERE = TOOLS.parent / 'experiments/flora-library-audit'
sys.path[:0] = [str(TOOLS), str(HERE)]
from max_flora_verify import checked_mesh
from catalogue import ROOT, fresh_path
from checkpoints import load_valid, save, sha
from mesh_compare import compare
from export_fbx import preview
from pymxs import runtime as rt

ENTRY_ID = 'library-070'
OUTPUT = ROOT / 'out/repairs-v006'


def configure_import():
    rt.resetMaxFile(rt.Name('noPrompt'))
    rt.units.SystemType = rt.Name('meters')
    rt.units.SystemScale = 1
    rt.FBXImporterSetParam('Mode', rt.Name('create'))


def imported(path):
    configure_import()
    if not rt.importFile(str(path), rt.Name('noPrompt'), using=rt.FBXIMP):
        raise RuntimeError('FBX import failed')
    nodes = [o for o in rt.objects if rt.superClassOf(o) == rt.GeometryClass]
    if len(nodes) != 1:
        raise RuntimeError('Expected exactly one geometry node')
    return checked_mesh(nodes[0])


def repair_one():
    if len(rt.objects) or str(rt.maxFileName):
        raise RuntimeError('Fresh headless session required')
    OUTPUT.mkdir(parents=True, exist_ok=True)
    catalog = json.loads((HERE/'catalogue.json').read_text(encoding='utf-8'))
    entry = next(e for s in catalog['scenes'] for e in s['entries'] if e['id'] == ENTRY_ID)
    source_hash = catalog['sources'][0]['copy_sha256']
    if sha(ROOT/'FLORA_Union_v1.max') != source_hash:
        raise RuntimeError('Source copy hash mismatch')
    old = load_valid(ROOT/'out/verified-v004'/ (ENTRY_ID+'.json'),entry,source_hash)
    existing = load_valid(OUTPUT/(ENTRY_ID+'.json'),entry,source_hash)
    if existing and (OUTPUT/(ENTRY_ID+'-readback.json')).exists():
        print('FLORA_TRI_REPAIR_SKIPPED_HASH_VERIFIED',ENTRY_ID,flush=True)
        return
    rt.pluginManager.loadClass(rt.FbxImporter)
    rt.pluginManager.loadClass(rt.FbxExporter)
    start = time.perf_counter()
    actual_old = imported(old['file'])
    baseline = compare(old['expected']['triangles'],actual_old['triangles'])
    geometry_only_expected = [{'corners':[c[:3] for c in t['corners']], 'material':None} for t in old['expected']['triangles']]
    geometry_only_actual = [{'corners':[c[:3] for c in t['corners']], 'material':None} for t in actual_old['triangles']]
    diagnostic = {'id':ENTRY_ID,'old_file_sha256':old['sha256'], 'old_comparison':baseline,
        'geometry_only_comparison':compare(geometry_only_expected,geometry_only_actual),
        'source_triangles':len(old['expected']['triangles']), 'imported_triangles':len(actual_old['triangles']),
        'actual_old':actual_old}
    save(OUTPUT/(ENTRY_ID+'-old-poly-diagnostic.json'),diagnostic)
    print('FLORA_OLD_POLY_DIAGNOSTIC',baseline,flush=True)
    if baseline['equal']:
        raise RuntimeError('Failure not reproduced: do not export an unnecessary repair')
    if not rt.loadMaxFile(str(ROOT/'FLORA_Union_v1.max'),quiet=True):
        raise RuntimeError('Copy load failed')
    source = rt.getNodeByName(entry['source_name'],exact=True)
    expected = checked_mesh(source)
    derived = rt.snapshot(source)
    derived.material = source.material
    derived.name = entry['source_name'] + '_AuditTri'
    before = compare(expected['triangles'],checked_mesh(derived)['triangles'])
    if not before['equal']:
        raise RuntimeError('Derived snapshot does not preserve source corners/UV/finish')
    diagnostic.update(source_class=str(rt.classOf(source)), derived_class=str(rt.classOf(derived)), derived_before_export=before)
    save(OUTPUT/(ENTRY_ID+'-old-poly-diagnostic.json'),diagnostic)
    print('FLORA_DERIVED_MATCHES_SOURCE',diagnostic['source_class'],diagnostic['derived_class'],flush=True)
    print('FLORA_TRI_CLEAN_SCENE_BEGIN', ENTRY_ID, len(rt.objects), flush=True)
    rt.delete(rt.Array(*[o for o in list(rt.objects) if o != derived]))
    after_cleanup = compare(expected['triangles'], checked_mesh(derived)['triangles'])
    if len(rt.objects) != 1 or not after_cleanup['equal']:
        raise RuntimeError('Isolated snapshot differs from source')
    print('FLORA_TRI_CLEAN_SCENE_END', ENTRY_ID, len(rt.objects), flush=True)
    for key,value in [('Animation',False),('EmbedTextures',False),('ASCII',False),('FileVersion','FBX201400'),('UpAxis','Z'),('Cameras',False),('Lights',False),('SmoothingGroups',True)]:
        rt.FBXExporterSetParam(key,value)
    target = fresh_path(OUTPUT,ENTRY_ID+'.fbx')
    print('FLORA_TRI_SELECT_BEGIN', ENTRY_ID, flush=True)
    rt.select(rt.Array(derived))
    print('FLORA_TRI_EXPORT_BEGIN', ENTRY_ID, flush=True)
    export_start = time.perf_counter()
    if not rt.exportFile(str(target),rt.Name('noPrompt'),selectedOnly=True,using=rt.FBXEXP):
        raise RuntimeError('Derived FBX export failed')
    svg = fresh_path(OUTPUT,ENTRY_ID+'.svg')
    preview(expected,svg)
    row = dict(old,file=str(target),sha256=sha(target),expected=expected,
        preview=str(svg),preview_sha256=sha(svg),seconds=time.perf_counter()-export_start,
        corrected_signature_preview_seconds=old['corrected_signature_preview_seconds'],
        repair_basis='derived_world_state_Editable_Mesh_snapshot',
        original_unmodified_fbx=old['file'],original_unmodified_fbx_sha256=old['sha256'])
    save(OUTPUT/(ENTRY_ID+'.json'),row)
    readback_start = time.perf_counter()
    actual = imported(target)
    result = compare(expected['triangles'],actual['triangles'])
    result['bitmap_paths_equal'] = actual['bitmap_files'] == expected['bitmap_files']
    equal = result['equal'] and result['bitmap_paths_equal'] and actual['system_units']=='meters' and actual['system_scale']==1
    rb = {'id':ENTRY_ID,'file_sha256':row['sha256'],'node_count':1,'equal':equal,'comparison':result,
        'snapshot_bbox':actual['snapshot_bbox'],'snapshot_bbox_probe_error_mm':actual['bbox_probe_error_mm'],
        'seconds':time.perf_counter()-readback_start}
    save(OUTPUT/(ENTRY_ID+'-readback.json'),rb)
    save(ROOT/('tri-repair-v006-'+ENTRY_ID+'.json'),{'id':ENTRY_ID,'old_comparison':baseline,'new_comparison':rb,'seconds_total':time.perf_counter()-start,
        'derived_before_export':before,'source_class':diagnostic['source_class'],'derived_class':diagnostic['derived_class']})
    if sha(old['file']) != old['sha256']:
        raise RuntimeError('Original FBX unexpectedly changed')
    print('FLORA_TRI_REPAIR_COMPLETE',ENTRY_ID,equal,result,flush=True)
    if not equal:
        raise RuntimeError('Derived snapshot FBX still differs')


def main():
    global ENTRY_ID
    if len(rt.objects) or str(rt.maxFileName):
        raise RuntimeError('Fresh headless session required before any reset')
    start = time.perf_counter()
    cases = []
    for entry_id in ['library-070']:
        ENTRY_ID = entry_id
        rt.resetMaxFile(rt.Name('noPrompt'))
        repair_one()
        case = json.loads((ROOT / ('tri-repair-v006-' + entry_id + '.json')).read_text(encoding='utf-8'))
        cases.append(case)
    save(ROOT / 'tri-repair-v006.json', {'cases': cases, 'seconds_total': time.perf_counter()-start,
                                       'failures': [c['id'] for c in cases if not c['new_comparison']['equal']]})
    if not all(c['new_comparison']['equal'] for c in cases):
        raise RuntimeError('A resumed repair receipt is not equal')
    print('FLORA_TRI_REPAIR_BATCH_COMPLETE', len(cases), flush=True)


if __name__=='__main__':
    main()
