"""New case #189: v004 world-coordinate probe + corrected all-file verification.

Does NOT re-export or overwrite any FBX. Existing v003 binaries/receipts remain
intact; fresh v004 expected signatures/previews prove snapshot world coordinates
against independent native node bboxes. Only dcc_batch.py max (2026), copies only.
Hash-verified v004 rows/readbacks are resumable. No tolerance is relaxed.
"""
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1] / 'experiments/flora-library-audit'
sys.path.insert(0, str(HERE))
from catalogue import ROOT, SCENES, fresh_path
from checkpoints import load_valid, save, sha
from export_fbx import mesh_data, preview, xyz
from mesh_compare import compare
from pymxs import runtime as rt

OUTPUT = ROOT / 'out/verified-v004'
PROGRESS = ROOT / 'verification-progress-v004.json'


def bbox_error(a, b):
    return max(abs(x-y) for aa, bb in zip(a,b) for x,y in zip(aa,bb))


def checked_mesh(obj):
    data = mesh_data(obj)
    bb = rt.nodeGetBoundingBox(obj, rt.matrix3(1))
    data['independent_node_bbox'] = [xyz(bb[0]), xyz(bb[1])]
    error = bbox_error(data['snapshot_bbox'], data['independent_node_bbox'])
    if error > .00005:
        raise RuntimeError('Snapshot world-space bbox invariant failed: ' + str(error))
    data['bbox_probe_error_mm'] = error * 1000
    return data


def main():
    if len(rt.objects) or str(rt.maxFileName):
        raise RuntimeError('Fresh headless session required')
    OUTPUT.mkdir(parents=True, exist_ok=True)
    catalog = json.loads((HERE / 'catalogue.json').read_text(encoding='utf-8'))
    start = time.perf_counter()
    limit = float(os.environ.get('FLORA_JOB_SECONDS', '1200'))
    evidence = {'exports': [], 'readbacks': [], 'failures': [], 'complete': False,
                'coordinate_convention': 'snapshotAsMesh_world_no_extra_node_transform'}
    def checkpoint(phase, entry_id=None):
        evidence.update(phase=phase, current_id=entry_id, seconds_this_run=time.perf_counter()-start)
        save(PROGRESS, evidence)
        print('FLORA_VERIFY_PROGRESS', phase, entry_id, len(evidence['exports']), len(evidence['readbacks']), flush=True)
    # Independent SYNTHETIC native probe, not a real plant or source modification.
    synthetic = rt.mesh(vertices=rt.Array(rt.Point3(0,0,0),rt.Point3(1,0,0),rt.Point3(0,1,0)), faces=rt.Array(rt.Point3(1,2,3)))
    synthetic.pos = rt.Point3(7,11,13)
    rt.rotate(synthetic, rt.angleAxis(25, rt.Point3(0,0,1)))
    synthetic_data = checked_mesh(synthetic)
    evidence['synthetic_snapshot_world_probe'] = {k:synthetic_data[k] for k in ['snapshot_bbox','independent_node_bbox','bbox_probe_error_mm']}
    rt.resetMaxFile(rt.Name('noPrompt'))
    for index, (name, scene) in enumerate(zip(SCENES, catalog['scenes'])):
        source_hash = catalog['sources'][index]['copy_sha256']
        if sha(ROOT / (name + '.max')) != source_hash:
            raise RuntimeError('Source copy hash mismatch')
        pending = []
        for entry in scene['entries']:
            row = load_valid(OUTPUT / (entry['id']+'.json'), entry, source_hash)
            if row:
                if row.get('coordinate_convention') != evidence['coordinate_convention']:
                    raise RuntimeError('Wrong receipt coordinate convention')
                evidence['exports'].append(row)
            else:
                pending.append(entry)
        if not pending:
            continue
        checkpoint('load_source', name)
        if not rt.loadMaxFile(str(ROOT / (name+'.max')), quiet=True):
            raise RuntimeError('Copy load failed')
        for entry in pending:
            if time.perf_counter()-start > limit:
                checkpoint('paused_expectations', entry['id'])
                return
            t0 = time.perf_counter()
            checkpoint('source_signature', entry['id'])
            old = load_valid(ROOT / 'out/assets-v003' / (entry['id']+'.json'), entry, source_hash)
            if old is None:
                raise RuntimeError('Missing original export receipt')
            obj = rt.getNodeByName(entry['source_name'], exact=True)
            expected = checked_mesh(obj)
            # This independent invariant caught the double-transform baseline bug.
            if bbox_error(expected['snapshot_bbox'], entry['bbox_m']) > .00005:
                raise RuntimeError('Inventory bbox differs from native source snapshot')
            svg = fresh_path(OUTPUT, entry['id']+'.svg')
            preview(expected, svg)
            row = dict(old, expected=expected, preview=str(svg), preview_sha256=sha(svg),
                       coordinate_convention=evidence['coordinate_convention'],
                       corrected_signature_preview_seconds=time.perf_counter()-t0)
            save(OUTPUT / (entry['id']+'.json'), row)
            evidence['exports'].append(row)
            checkpoint('source_signature_done', entry['id'])
    rt.pluginManager.loadClass(rt.FbxImporter)
    for export in evidence['exports']:
        path = OUTPUT / (export['id']+'-readback.json')
        if path.exists():
            row = json.loads(path.read_text(encoding='utf-8'))
            if row['file_sha256'] != export['sha256']:
                raise RuntimeError('Readback hash mismatch')
        else:
            if time.perf_counter()-start > limit:
                checkpoint('paused_readbacks', export['id'])
                return
            t0 = time.perf_counter()
            checkpoint('readback', export['id'])
            rt.resetMaxFile(rt.Name('noPrompt'))
            rt.units.SystemType = rt.Name('meters')
            rt.units.SystemScale = 1
            rt.FBXImporterSetParam('Mode', rt.Name('create'))
            if not rt.importFile(export['file'], rt.Name('noPrompt'), using=rt.FBXIMP):
                raise RuntimeError('FBX import failed')
            nodes = [o for o in rt.objects if rt.superClassOf(o) == rt.GeometryClass]
            actual = checked_mesh(nodes[0]) if len(nodes) == 1 else None
            result = compare(export['expected']['triangles'], actual['triangles']) if actual else {'equal':False,'reason':'node_count'}
            result['bitmap_paths_equal'] = bool(actual and actual['bitmap_files'] == export['expected']['bitmap_files'])
            same = bool(result['equal'] and result['bitmap_paths_equal'] and actual['system_units'] == 'meters' and actual['system_scale'] == 1)
            row = {'id':export['id'], 'file_sha256':export['sha256'], 'node_count':len(nodes),
                   'equal':same, 'comparison':result, 'snapshot_bbox':actual['snapshot_bbox'] if actual else None,
                   'snapshot_bbox_probe_error_mm':actual['bbox_probe_error_mm'] if actual else None,
                   'seconds':time.perf_counter()-t0}
            save(path,row)
        evidence['readbacks'].append(row)
        if not row['equal']:
            evidence['failures'].append(row['id'])
        checkpoint('readback_done', export['id'])
    evidence['complete'] = True
    checkpoint('complete')
    save(ROOT / 'readback-v004.json', evidence)
    print('FLORA_VERIFICATION_COMPLETE',len(evidence['exports']),len(evidence['readbacks']),len(evidence['failures']),flush=True)


if __name__ == '__main__':
    main()
