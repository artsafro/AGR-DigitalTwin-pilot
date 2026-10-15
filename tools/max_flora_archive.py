"""New case #189: resumable native Flora FBX archive on hash-verified COPIES.

Only dcc_batch.py max (2026); no live bridge. Per-row receipts are atomic and
hash checked before skipping work. Existing unreceipted assets are never replaced.
Max is allowed to stop between rows after FLORA_JOB_SECONDS (default 3900).
Resume with exactly the same command. No source scene is ever saved.
"""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1] / 'experiments/flora-library-audit'
sys.path.insert(0, str(HERE))
from checkpoints import load_valid, save, sha
from catalogue import ROOT, SCENES, fresh_path
from export_fbx import mesh_data, preview
from mesh_compare import compare
from pymxs import runtime as rt

OUTPUT = ROOT / 'out/assets-v003'
PROGRESS = ROOT / 'archive-progress-v003.json'


def main():
    if len(rt.objects) or str(rt.maxFileName):
        raise RuntimeError('Expected empty headless Max session')
    OUTPUT.mkdir(parents=True, exist_ok=True)
    catalog = json.loads((HERE / 'catalogue.json').read_text(encoding='utf-8'))
    rt.pluginManager.loadClass(rt.FbxExporter)
    rt.pluginManager.loadClass(rt.FbxImporter)
    start = time.perf_counter()
    limit = float(os.environ.get('FLORA_JOB_SECONDS', '3900'))
    evidence = {'exports': [], 'readbacks': [], 'failures': [], 'textplus': [], 'complete': False}

    def checkpoint(phase, entry_id=None):
        evidence['phase'] = phase
        evidence['current_id'] = entry_id
        evidence['seconds_this_run'] = time.perf_counter() - start
        save(PROGRESS, evidence)
        print('FLORA_PROGRESS', phase, entry_id, len(evidence['exports']), len(evidence['readbacks']), flush=True)

    for scene_index, (name, scene) in enumerate(zip(SCENES, catalog['scenes'])):
        source_hash = catalog['sources'][scene_index]['copy_sha256']
        source = ROOT / (name + '.max')
        if sha(source) != source_hash:
            raise RuntimeError('Input copy hash differs')
        pending = []
        for entry in scene['entries']:
            receipt = OUTPUT / (entry['id'] + '.json')
            row = load_valid(receipt, entry, source_hash)
            if row:
                evidence['exports'].append(row)
            else:
                pending.append(entry)
        if not pending:
            continue
        checkpoint('load', name)
        if not rt.loadMaxFile(str(source), quiet=True):
            raise RuntimeError('Copy load failed')
        for key, value in [('Animation', False), ('EmbedTextures', False), ('ASCII', False), ('FileVersion', 'FBX201400'), ('UpAxis', 'Z'), ('Cameras', False), ('Lights', False), ('SmoothingGroups', True)]:
            rt.FBXExporterSetParam(key, value)
        for entry in pending:
            if time.perf_counter() - start > limit:
                checkpoint('paused_exports', entry['id'])
                return
            t0 = time.perf_counter()
            checkpoint('extract', entry['id'])
            obj = rt.getNodeByName(entry['source_name'], exact=True)
            if obj is None:
                raise RuntimeError('Source node missing')
            expected = mesh_data(obj)
            checkpoint('export', entry['id'])
            target = fresh_path(OUTPUT, entry['id'] + '.fbx')
            svg = fresh_path(OUTPUT, entry['id'] + '.svg')
            rt.select(rt.Array(obj))
            if not rt.exportFile(str(target), rt.Name('noPrompt'), selectedOnly=True, using=rt.FBXEXP):
                raise RuntimeError('FBX export failed')
            preview(expected, svg)
            row = {'id': entry['id'], 'name': entry['source_name'], 'source_sha256': source_hash,
                   'file': str(target), 'sha256': sha(target), 'preview': str(svg), 'preview_sha256': sha(svg),
                   'expected': expected, 'seconds': time.perf_counter() - t0}
            save(OUTPUT / (entry['id'] + '.json'), row)
            evidence['exports'].append(row)
            checkpoint('exported', entry['id'])
    for export in evidence['exports']:
        receipt = OUTPUT / (export['id'] + '-readback.json')
        if receipt.exists():
            rb = json.loads(receipt.read_text(encoding='utf-8'))
            if rb['file_sha256'] != export['sha256']:
                raise RuntimeError('Readback hash mismatch')
        else:
            if time.perf_counter() - start > limit:
                checkpoint('paused_readbacks', export['id'])
                return
            t0 = time.perf_counter()
            checkpoint('readback', export['id'])
            rt.resetMaxFile(rt.Name('noPrompt'))
            rt.units.SystemType = rt.Name('meters')
            rt.units.SystemScale = 1
            rt.FBXImporterSetParam('Mode', rt.Name('create'))
            if not rt.importFile(export['file'], rt.Name('noPrompt'), using=rt.FBXIMP):
                raise RuntimeError('FBX readback failed')
            nodes = [o for o in rt.objects if rt.superClassOf(o) == rt.GeometryClass]
            actual = mesh_data(nodes[0]) if len(nodes) == 1 else None
            result = compare(export['expected']['triangles'], actual['triangles']) if actual else {'equal': False, 'reason': 'node_count'}
            result['bitmap_paths_equal'] = actual is not None and actual['bitmap_files'] == export['expected']['bitmap_files']
            same = result['equal'] and result['bitmap_paths_equal'] and actual['system_units'] == 'meters' and actual['system_scale'] == 1
            rb = {'id': export['id'], 'file_sha256': export['sha256'], 'node_count': len(nodes), 'equal': same,
                  'comparison': result, 'vertices': actual['vertices'] if actual else None,
                  'uv_vertices': actual['uv_vertices'] if actual else None, 'seconds': time.perf_counter() - t0}
            save(receipt, rb)
        evidence['readbacks'].append(rb)
        if not rb['equal']:
            evidence['failures'].append(export['id'])
        checkpoint('readback_done', export['id'])
    evidence['complete'] = True
    evidence['seconds_total'] = sum(e['seconds'] for e in evidence['exports']) + sum(e['seconds'] for e in evidence['readbacks'])
    checkpoint('complete')
    save(ROOT / 'readback-v003.json', evidence)
    print('FLORA_AUDIT_COMPLETE', len(evidence['exports']), len(evidence['readbacks']), len(evidence['failures']), flush=True)


if __name__ == '__main__':
    main()
