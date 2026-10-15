"""E1 native script. Bootstrap supplies CONFIG; only run via dcc_batch.py max.

Standard shaders below are synthetic diagnostic materials, not approved finishes.
"""
import hashlib
import json
import sys
import time
from pathlib import Path
import pymxs

rt = pymxs.runtime
BENCHES = ['bench-b01-box', 'bench-b02-corner-niche']


def write(path, data):
    with path.open('x', encoding='utf-8') as f:
        json.dump(data, f)


def clear():
    rt.delete(list(rt.objects))  # Exclusively owned, initially empty batch process.


def dump():
    meshes = []
    for obj in rt.geometry:
        mesh = rt.snapshotAsMesh(obj)
        mat = obj.material
        table = {}
        if mat:
            if rt.classOf(mat) == rt.MultiMaterial:
                for i in range(len(mat.materialIDList)):
                    sub = mat.materialList[i]
                    table[str(int(mat.materialIDList[i]))] = str(sub.name) if sub else None
            else:
                table['1'] = str(mat.name)
        faces = [[int(x)-1 for x in rt.getFace(mesh, i)] for i in range(1, rt.getNumFaces(mesh)+1)]
        meshes.append({'name': str(obj.name),
                       'vertices': [list(rt.getVert(mesh, i)*obj.objectTransform) for i in range(1, rt.getNumVerts(mesh)+1)],
                       'triangles': faces, 'polygon_sizes': [3]*len(faces),
                       'material_ids': [int(rt.getFaceMatID(mesh, i)) for i in range(1, len(faces)+1)],
                       'material_table': table, 'transform': [list(r) for r in obj.transform]})
    return {'units': str(rt.units.SystemType), 'meshes': meshes,
            'helpers': [{'name': str(o.name), 'location': list(o.pos)} for o in rt.helpers]}


def create(data, explicit):
    for m in data['meshes']:
        obj = rt.mesh(name=m['name'], vertices=[rt.Point3(*v) for v in m['vertices']],
                      faces=[rt.Point3(*(i+1 for i in f)) for f in m['triangles']])
        for i, mid in enumerate(m['material_ids'], 1):
            rt.setFaceMatID(obj, i, mid)
        if explicit:
            ids = sorted(set(m['material_ids']))
            material = rt.MultiMaterial(numsubs=len(ids), name=m['name']+'_finish_table')
            material.materialIDList = rt.Array(*ids)
            for i, mid in enumerate(ids):
                material.materialList[i] = rt.StandardMaterial(name='MAT_'+str(mid).zfill(3))
            obj.material = material
        rt.update(obj)
    for h in data.get('helpers', []):
        rt.Point(name=h['name'], pos=rt.Point3(*h['location']))


def main(config):
    base = Path(config['run'])
    mode = config['mode']
    out = base / mode
    out.mkdir(exist_ok=False)
    inventory = {'version': list(rt.maxVersion()), 'python': sys.version,
                 'initial_objects': len(rt.objects), 'document': str(rt.maxFileName),
                 'initial_units': str(rt.units.SystemType)}
    assert inventory['initial_objects'] == 0 and not inventory['document']
    print('AGR_E1_INVENTORY', json.dumps(inventory))
    rt.units.SystemType = rt.Name('meters')
    rt.units.SystemScale = 1.0
    rt.pluginManager.loadClass(rt.FBXIMP)
    rt.pluginManager.loadClass(rt.FBXEXP)
    params = {'Animation': False, 'EmbedTextures': False, 'ASCII': False,
              'FileVersion': 'FBX201400', 'UpAxis': 'Z', 'Cameras': False,
              'Lights': False, 'Triangulate': True, 'ConvertUnit': 'm'}
    getters, rows = {}, []
    try:
        for key, value in params.items():
            getters[key] = {'set': str(rt.FBXExporterSetParam(key, value)),
                            'get': str(rt.FBXExporterGetParam(key))}
        if mode in ['baseline', 'prototype']:
            for bench in BENCHES:
                data = json.loads((base / bench / 'engine.json').read_text())
                for rep in range(3):
                    start = time.perf_counter()
                    create(data, mode == 'prototype')
                    create_seconds = time.perf_counter()-start
                    stem = bench+'-r'+str(rep)
                    if rep == 0:
                        write(out / (stem+'-created.json'), dump())
                    target = out / (stem+'.fbx')
                    assert not target.exists()
                    start = time.perf_counter()
                    assert rt.exportFile(str(target), rt.Name('noPrompt'), using=rt.FBXEXP)
                    rows.append({'bench': bench, 'rep': rep, 'create_seconds': create_seconds,
                                 'export_seconds': time.perf_counter()-start,
                                 'file': str(target), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
                    clear()
        elif mode == 'readback':
            for bench in BENCHES:
                targets = [('etalon', base / bench / 'etalon.fbx')]
                targets += [(arm+'-r'+str(rep), base / arm / (bench+'-r'+str(rep)+'.fbx'))
                            for arm in ['baseline', 'prototype'] for rep in range(3)]
                for label, target in targets:
                    start = time.perf_counter()
                    assert rt.importFile(str(target), rt.Name('noPrompt'), using=rt.FBXIMP)
                    data = dump()
                    rows.append({'bench': bench, 'label': label, 'import_dump_seconds': time.perf_counter()-start})
                    write(out / (bench+'-'+label+'.json'), data)
                    clear()
        else:
            raise ValueError(mode)
        write(out / 'results.json', {'inventory': inventory, 'parameters': getters, 'rows': rows,
                                     'delivery_passed': False})
        print('AGR_E1_COMPLETE', mode, len(rows))
    finally:
        clear()
        print('AGR_E1_CLEANUP', len(rt.objects))


main(CONFIG)
