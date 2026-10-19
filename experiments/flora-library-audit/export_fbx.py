"""New case #189: per-plant FBX 7.4 archive with native readback, no source saves.
Run via dcc_batch.py max only. MAX saveNodes was measured and too slow.
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
from mesh_compare import compare


def xyz(p):
    return [float(p.x), float(p.y), float(p.z)]


def mesh_data(obj):
    mesh = rt.snapshotAsMesh(obj)
    # snapshotAsMesh vertices are already in world space (native bbox probe).
    # Applying node.transform again double-translates/rotates the measurement.
    vertices = [xyz(rt.getVert(mesh, i)) for i in range(1, int(rt.getNumVerts(mesh)) + 1)]
    ntv = int(rt.getNumTVerts(mesh))
    uv = [xyz(rt.getTVert(mesh, i))[:2] for i in range(1, ntv + 1)]
    mat = obj.material
    names = {}
    if mat and rt.isProperty(mat, 'materialIDList'):
        for index, matid in enumerate(mat.materialIDList):
            sub = rt.getSubMtl(mat, index + 1)
            names[int(matid)] = str(sub.name) if sub else None
    triangles = []
    for i in range(1, int(rt.getNumFaces(mesh)) + 1):
        f = rt.getFace(mesh, i)
        tf = rt.getTVFace(mesh, i) if ntv else None
        corners = [vertices[int(k) - 1] + (uv[int(t) - 1] if ntv else []) for k, t in zip((f.x, f.y, f.z), (tf.x, tf.y, tf.z) if tf else (0, 0, 0))]
        finish = names.get(int(rt.getFaceMatID(mesh, i))) if names else (str(mat.name) if mat else None)
        triangles.append({'corners': corners, 'material': finish})
    rt.delete(mesh)
    return {'vertices': len(vertices), 'triangles': triangles, 'uv_vertices': ntv,
            'snapshot_bbox': [[min(v[i] for v in vertices) for i in range(3)], [max(v[i] for v in vertices) for i in range(3)]],
            'bitmap_files': sorted({str(t.filename) for t in rt.getClassInstances(rt.Bitmaptexture, target=mat)}) if mat else [],
            'system_units': str(rt.units.SystemType), 'system_scale': float(rt.units.SystemScale)}


def preview(data, target):
    vertices = [v for tri in data['triangles'] for v in tri['corners']]
    xs, zs = [v[0] for v in vertices], [v[2] for v in vertices]
    xmin, zmin = min(xs), min(zs)
    scale = min(520 / max(max(xs)-xmin, .001), 520 / max(max(zs)-zmin, .001))
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="640" height="640">', '<rect width="640" height="640" fill="white"/>',
           '<text x="20" y="24">Untextured native XZ mesh: audit only</text>', '<g fill="none" stroke="#26734d" stroke-width="0.4">']
    for tri in data['triangles']:
        points = ' '.join(f'{40+(v[0]-xmin)*scale:.3f},{580-(v[2]-zmin)*scale:.3f}' for v in tri['corners'])
        svg.append('<polygon points="' + points + '"/>')
    target.write_text('\n'.join(svg + ['</g>', '</svg>']), encoding='utf-8')


def main():
    if len(rt.objects) or str(rt.maxFileName):
        raise RuntimeError('Expected fresh headless session')
    output = ROOT / 'assets-v002'
    if output.exists():
        raise FileExistsError('Fresh version required')
    output.mkdir()
    catalog = json.loads((HERE / 'catalogue.json').read_text(encoding='utf-8'))
    rt.pluginManager.loadClass(rt.FbxExporter)
    rt.pluginManager.loadClass(rt.FbxImporter)
    rt.execute('fn agrReadPlaintext o = (local s=""; o.GetPlaintextString &s; s)')
    evidence = {'exports': [], 'readbacks': [], 'textplus': [], 'failures': []}
    start = time.perf_counter()
    for scene_index, (name, scene) in enumerate(zip(SCENES, catalog['scenes'])):
        source = ROOT / (name + '.max')
        if hashlib.sha256(source.read_bytes()).hexdigest() != catalog['sources'][scene_index]['copy_sha256']:
            raise RuntimeError('Input hash differs')
        if not rt.loadMaxFile(str(source), quiet=True):
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
        for key, value in [('Animation', False), ('EmbedTextures', False), ('ASCII', False), ('FileVersion', 'FBX201400'), ('UpAxis', 'Z'), ('Cameras', False), ('Lights', False), ('SmoothingGroups', True)]:
            rt.FBXExporterSetParam(key, value)
        for entry in scene['entries']:
            t0 = time.perf_counter()
            obj = rt.getNodeByName(entry['source_name'], exact=True)
            expected = mesh_data(obj)
            target = fresh_path(output, entry['id'] + '.fbx')
            rt.select(rt.Array(obj))
            if not rt.exportFile(str(target), rt.Name('noPrompt'), selectedOnly=True, using=rt.FBXEXP):
                raise RuntimeError('FBX export failed')
            svg = fresh_path(output, entry['id'] + '.svg')
            preview(expected, svg)
            evidence['exports'].append({'id': entry['id'], 'name': entry['source_name'], 'file': str(target), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                                        'preview': str(svg), 'preview_sha256': hashlib.sha256(svg.read_bytes()).hexdigest(), 'expected': expected, 'seconds': time.perf_counter()-t0})
        print('EXPORTED', name, len(scene['entries']))
        (ROOT / 'exports-v002.json').write_text(json.dumps(evidence, ensure_ascii=False), encoding='utf-8')
    for export in evidence['exports']:
        t0 = time.perf_counter()
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
        evidence['readbacks'].append({'id': export['id'], 'node_count': len(nodes), 'equal': same, 'comparison': result,
                                      'vertices': actual['vertices'] if actual else None, 'uv_vertices': actual['uv_vertices'] if actual else None,
                                      'seconds': time.perf_counter()-t0})
        if not same:
            evidence['failures'].append(export['id'])
        if len(evidence['readbacks']) % 10 == 0:
            (ROOT / 'readback-progress-v002.json').write_text(json.dumps(evidence, ensure_ascii=False), encoding='utf-8')
    evidence['seconds_total'] = time.perf_counter()-start
    (ROOT / 'readback-v002.json').write_text(json.dumps(evidence, ensure_ascii=False), encoding='utf-8')
    print('FLORA_AUDIT_COMPLETE', len(evidence['exports']), len(evidence['readbacks']), len(evidence['failures']), evidence['seconds_total'])
    if evidence['failures']:
        raise RuntimeError('Readback mismatch ' + repr(evidence['failures']))
if __name__ == '__main__':
    main()
