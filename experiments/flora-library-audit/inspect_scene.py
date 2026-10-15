"""Read-only scene inventory; run in Max Python on authorized copies only."""
import json
import time
from pathlib import Path
from pymxs import runtime as rt

ROOT = Path('C:/x/t_366e8d9d')

def xyz(p):
    return [float(p.x), float(p.y), float(p.z)]

def material_info(mat):
    if not mat:
        return None
    maps = []
    for tex in rt.getClassInstances(rt.Bitmaptexture, target=mat):
        filename = str(tex.filename)
        maps.append({'name': str(tex.name), 'filename': filename,
                     'exists': bool(rt.doesFileExist(filename))})
    subs = []
    for i in range(1, int(rt.getNumSubMtls(mat)) + 1):
        sub = rt.getSubMtl(mat, i)
        subs.append({'slot': i, 'name': str(sub.name) if sub else None,
                     'class': str(rt.classOf(sub)) if sub else None})
    return {'name': str(mat.name), 'class': str(rt.classOf(mat)), 'submaterials': subs, 'bitmaps': maps}


def inventory():
    start = time.perf_counter()
    rows = []
    for obj in rt.objects:
        row = {'handle': int(rt.getHandleByAnim(obj)), 'name': str(obj.name),
               'class': str(rt.classOf(obj)), 'superclass': str(rt.superClassOf(obj)),
               'position': xyz(obj.pos), 'hidden': bool(obj.isHidden),
               'parent': str(obj.parent.name) if obj.parent else None,
               'layer': str(obj.layer.name), 'renderable': bool(obj.renderable),
               'transform': str(obj.transform),
               'material': material_info(obj.material) if rt.isProperty(obj, 'material') else None}
        if str(rt.classOf(obj)) == 'TextPlus':
            row['plain_text'] = str(rt.agrReadPlaintext(obj))
            row['properties'] = [str(p) for p in rt.getPropNames(obj)]
            for prop in rt.getPropNames(obj):
                if any(s in str(prop).lower() for s in ['text', 'string']):
                    try:
                        row[str(prop)] = str(rt.getProperty(obj, prop))
                    except Exception as exc:
                        row[str(prop)] = str(exc)
        try:
            bb = rt.nodeGetBoundingBox(obj, rt.matrix3(1))
            row['bbox'] = [xyz(bb[0]), xyz(bb[1])]
        except Exception as exc:
            row['bbox_error'] = str(exc)
        if rt.isProperty(obj, 'text'):
            row['text'] = str(obj.text)
        if rt.superClassOf(obj) == rt.GeometryClass:
            try:
                mesh = rt.snapshotAsMesh(obj)
                row.update(vertices=int(rt.getNumVerts(mesh)), triangles=int(rt.getNumFaces(mesh)),
                           uv_vertices=int(rt.getNumTVerts(mesh)))
                rt.delete(mesh)
            except Exception as exc:
                row['mesh_error'] = str(exc)
        rows.append(row)
    return {'scene': str(rt.maxFilePath) + str(rt.maxFileName),
            'version': str(rt.maxVersion()), 'units': str(rt.units.SystemType),
            'system_scale': float(rt.units.SystemScale),
            'unit_in_m': float(rt.units.decodeValue('1m')),
            'objects': rows, 'inventory_seconds': time.perf_counter() - start}


def main():
    if len(rt.objects) or str(rt.maxFileName):
        raise RuntimeError('Expected empty headless session')
    rt.execute('fn agrReadPlaintext o = (local s=""; o.GetPlaintextString &s; s)')
    manifest = json.loads((ROOT / 'sources-verified.json').read_text(encoding='utf-8'))
    for index, name in enumerate(['FLORA_Union_v1', 'FLORIO_2BT_2022']):
        source = ROOT / (name + '.max')
        import hashlib
        if hashlib.sha256(source.read_bytes()).hexdigest() != manifest[index]['copy_sha256']:
            raise RuntimeError('Copy hash differs')
        if not rt.loadMaxFile(str(source), quiet=True):
            raise RuntimeError('Load failed: ' + str(source))
        results = [inventory() for _ in range(3)]
        result = results[0]
        result['inventory_timings_seconds'] = [r['inventory_seconds'] for r in results]
        (ROOT / (name + '-detailed.json')).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print('INVENTORY', name, len(result['objects']), result['inventory_seconds'])

main()
