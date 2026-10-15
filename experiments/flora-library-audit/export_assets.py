"""New case #189: isolated per-node MAX copies + native mesh readback.

Execute only via dcc_batch.py max, in a fresh headless session. Sources must be
copies under the card root; outputs are fresh assets-v001 files. No source save,
texture resolution changes, live bridge, renderer, or global defaults are used.
"""
import hashlib
import json
import sys
import time
from pathlib import Path

from pymxs import runtime as rt

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from catalogue import ROOT, SCENES, fresh_path


def xyz(p):
    return [float(p.x), float(p.y), float(p.z)]


def fingerprint(obj):
    mesh = rt.snapshotAsMesh(obj)
    vertices = [xyz(rt.getVert(mesh, i)) for i in range(1, int(rt.getNumVerts(mesh)) + 1)]
    faces = [xyz(rt.getFace(mesh, i)) for i in range(1, int(rt.getNumFaces(mesh)) + 1)]
    matids = [int(rt.getFaceMatID(mesh, i)) for i in range(1, len(faces) + 1)]
    ntv = int(rt.getNumTVerts(mesh))
    uv = [xyz(rt.getTVert(mesh, i)) for i in range(1, ntv + 1)]
    uvfaces = [xyz(rt.getTVFace(mesh, i)) for i in range(1, len(faces) + 1)] if ntv else []
    bb = rt.nodeGetBoundingBox(obj, rt.matrix3(1))
    maps = sorted((str(t.name), str(t.filename)) for t in rt.getClassInstances(rt.Bitmaptexture, target=obj.material)) if obj.material else []
    result = {'vertices': len(vertices), 'triangles': len(faces), 'uv_vertices': ntv,
              'mesh_sha256': hashlib.sha256(json.dumps([vertices, faces, matids, uv, uvfaces]).encode()).hexdigest(),
              'bbox': [xyz(bb[0]), xyz(bb[1])], 'transform': str(obj.transform),
              'material': str(obj.material.name) if obj.material else None, 'bitmaps': maps,
              'system_units': str(rt.units.SystemType), 'system_scale': float(rt.units.SystemScale),
              'units_per_meter': float(rt.units.decodeValue('1m'))}
    rt.delete(mesh)
    return result


def preview(obj, target):
    """Geometry-only XZ projection, not an atlas/opacity or rendered appearance."""
    mesh = rt.snapshotAsMesh(obj)
    vertices = [rt.getVert(mesh, i) * obj.transform for i in range(1, int(rt.getNumVerts(mesh)) + 1)]
    xs, zs = [float(v.x) for v in vertices], [float(v.z) for v in vertices]
    scale = min(520 / max(max(xs) - min(xs), .001), 520 / max(max(zs) - min(zs), .001))
    points = [(40 + (x - min(xs)) * scale, 580 - (z - min(zs)) * scale) for x, z in zip(xs, zs)]
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="640" height="640" viewBox="0 0 640 640">',
           '<rect width="640" height="640" fill="white"/>',
           '<text x="20" y="24" font-size="14">Untextured XZ mesh projection (audit only)</text>',
           '<g fill="none" stroke="#26734d" stroke-width="0.4" opacity="0.55">']
    for i in range(1, int(rt.getNumFaces(mesh)) + 1):
        face = rt.getFace(mesh, i)
        coords = [points[int(k) - 1] for k in (face.x, face.y, face.z)]
        svg.append('<polygon points="' + ' '.join(f'{x:.3f},{y:.3f}' for x, y in coords) + '"/>')
    svg.extend(['</g>', '</svg>'])
    target.write_text('\n'.join(svg), encoding='utf-8')
    rt.delete(mesh)


def main():
    if len(rt.objects) or str(rt.maxFileName):
        raise RuntimeError('Expected fresh headless session')
    output = ROOT / 'assets-v001'
    if output.exists():
        raise FileExistsError('Fresh version directory required: ' + str(output))
    output.mkdir()
    catalog = json.loads((HERE / 'catalogue.json').read_text(encoding='utf-8'))
    rt.execute('fn agrReadPlaintext o = (local s=""; o.GetPlaintextString &s; s)')
    evidence = {'exports': [], 'readbacks': [], 'textplus': [], 'failures': []}
    start = time.perf_counter()
    for name, scene in zip(SCENES, catalog['scenes']):
        source = ROOT / (name + '.max')
        expected_source_hash = catalog['sources'][SCENES.index(name)]['copy_sha256']
        if hashlib.sha256(source.read_bytes()).hexdigest() != expected_source_hash:
            raise RuntimeError('Input copy hash differs from manifest: ' + str(source))
        if source.parent != ROOT or not rt.loadMaxFile(str(source), quiet=True):
            raise RuntimeError('Copy load failed')
        detailed_path = ROOT / (name + '-detailed.json')
        detailed = json.loads(detailed_path.read_text(encoding='utf-8'))
        for obj in rt.objects:
            if str(rt.classOf(obj)) == 'TextPlus':
                text = str(rt.agrReadPlaintext(obj))
                evidence['textplus'].append({'name': str(obj.name), 'text': text})
                for row in detailed['objects']:
                    if row['name'] == str(obj.name):
                        row['plain_text'] = text
        detailed_path.write_text(json.dumps(detailed, ensure_ascii=False, indent=2), encoding='utf-8')
        for entry in scene['entries']:
            t0 = time.perf_counter()
            obj = rt.getNodeByName(entry['source_name'], exact=True)
            if obj is None:
                raise RuntimeError('Missing named node ' + entry['source_name'])
            expected = fingerprint(obj)
            target = fresh_path(output, entry['id'] + '.max')
            if not rt.saveNodes(rt.Array(obj), str(target), quiet=True):
                raise RuntimeError('saveNodes failed: ' + str(target))
            svg = fresh_path(output, entry['id'] + '.svg')
            preview(obj, svg)
            evidence['exports'].append({'id': entry['id'], 'name': entry['source_name'], 'file': str(target),
                                        'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                                        'preview': str(svg), 'preview_sha256': hashlib.sha256(svg.read_bytes()).hexdigest(),
                                        'expected': expected, 'seconds': time.perf_counter() - t0})
        print('EXPORTED', name, len(scene['entries']))
    (ROOT / 'exports-v001.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    # Reload each standalone output; source copies are never saved.
    for export in evidence['exports']:
        t0 = time.perf_counter()
        if not rt.loadMaxFile(export['file'], quiet=True):
            raise RuntimeError('Readback failed: ' + export['file'])
        nodes = list(rt.objects)
        actual = fingerprint(nodes[0]) if len(nodes) == 1 else None
        # JSON roundtrip converts tuples (bitmap pairs) to arrays: compare via JSON.
        same = actual is not None and json.dumps(actual, sort_keys=True) == json.dumps(export['expected'], sort_keys=True)
        same = same and str(nodes[0].name) == export['name']
        evidence['readbacks'].append({'id': export['id'], 'node_count': len(nodes), 'equal': same,
                                      'actual': actual, 'seconds': time.perf_counter() - t0})
        if not same:
            evidence['failures'].append(export['id'])
    evidence['seconds_total'] = time.perf_counter() - start
    (ROOT / 'readback-v001.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    print('FLORA_AUDIT_COMPLETE', len(evidence['exports']), len(evidence['readbacks']), len(evidence['failures']), evidence['seconds_total'])
    if evidence['failures']:
        raise RuntimeError('Readback mismatch: ' + repr(evidence['failures']))


main()
