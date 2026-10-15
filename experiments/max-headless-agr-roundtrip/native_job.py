"""Sandbox geometry-only experiment, run exclusively through dcc_batch.py max."""
import json
import time
import traceback
from pathlib import Path
import pymxs

rt = pymxs.runtime
BASE = Path('C:/Users/artsafro/.hermes/profiles/dt-experimenter-codex/cache/scratch/agr-exp-t_69ee7ca0')
OUT = BASE / 'agr-3dsmax-t_69ee7ca0'
BENCHES = ['bench-b01-box', 'bench-b02-corner-niche']


def dump():
    meshes = []
    for obj in rt.geometry:
        m = rt.snapshotAsMesh(obj)
        verts = [list(rt.getVert(m, i) * obj.objectTransform) for i in range(1, rt.getNumVerts(m) + 1)]
        tris = [[int(x) - 1 for x in rt.getFace(m, i)] for i in range(1, rt.getNumFaces(m) + 1)]
        mids = [int(rt.getFaceMatID(m, i)) for i in range(1, rt.getNumFaces(m) + 1)]
        meshes.append({'name': str(obj.name), 'vertices': verts, 'triangles': tris, 'material_ids': mids,
                       'polygon_sizes': [3] * len(tris), 'transform': [list(r) for r in obj.transform]})
    return {'units': str(rt.units.SystemType), 'meshes': meshes,
            'helpers': [{'name': str(o.name), 'location': list(o.pos)} for o in rt.helpers]}


def clear():
    # Only nodes created/imported by this job in its private initially empty process.
    rt.delete(list(rt.objects))


def create(data):
    for m in data['meshes']:
        obj = rt.mesh(name=m['name'], vertices=[rt.Point3(*v) for v in m['vertices']],
                      faces=[rt.Point3(*(i + 1 for i in f)) for f in m['triangles']])
        for i, mid in enumerate(m['material_ids'], 1):
            rt.setFaceMatID(obj, i, mid)
        rt.update(obj)
    for h in data.get('helpers', []):
        rt.Point(name=h['name'], pos=rt.Point3(*h['location']))


def write(path, value):
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f)


def main():
    inventory = {'version': str(rt.maxVersion()), 'initial_objects': len(rt.objects),
                 'document': str(rt.maxFileName), 'initial_units': str(rt.units.SystemType)}
    print('AGR_INVENTORY', json.dumps(inventory))
    assert not len(rt.objects) and not str(rt.maxFileName)
    rt.units.SystemType = rt.Name('meters')
    rt.units.SystemScale = 1.0
    rt.pluginManager.loadClass(rt.FBXIMP)
    rt.pluginManager.loadClass(rt.FBXEXP)
    rows = []
    try:
        for bench in BENCHES:
            t = time.perf_counter()
            assert rt.importFile(str(BASE / bench / 'etalon.fbx'), rt.Name('noPrompt'), using=rt.FBXIMP)
            write(OUT / (bench + '-etalon-dump.json'), dump())
            rows.append({'bench': bench, 'operation': 'etalon_import_dump', 'seconds': time.perf_counter() - t})
            clear()
        params = {'Animation': False, 'EmbedTextures': False, 'ASCII': False,
                  'FileVersion': 'FBX201400', 'UpAxis': 'Z', 'Cameras': False,
                  'Lights': False, 'Triangulate': True, 'ConvertUnit': 'm'}
        param_results = {}
        for key, value in params.items():
            set_result = rt.FBXExporterSetParam(key, value)
            param_results[key] = {'set': str(set_result), 'readback': str(rt.FBXExporterGetParam(key))}
        for rep in range(3):
            for bench in BENCHES:
                data = json.loads((BASE / bench / 'engine.json').read_text())
                t = time.perf_counter()
                create(data)
                rows.append({'bench': bench, 'rep': rep, 'operation': 'create_mesh', 'seconds': time.perf_counter() - t})
                if rep == 0:
                    write(OUT / (bench + '-created.json'), dump())
                for fmt, exporter, importer in [('fbx', rt.FBXEXP, rt.FBXIMP), ('obj', rt.ObjExp, rt.ObjImp)]:
                    path = OUT / (bench + '-r' + str(rep) + '.' + fmt)
                    assert not path.exists()
                    t = time.perf_counter()
                    assert rt.exportFile(str(path), rt.Name('noPrompt'), selectedOnly=False, using=exporter)
                    rows.append({'bench': bench, 'rep': rep, 'format': fmt, 'operation': 'export', 'seconds': time.perf_counter() - t})
                    clear()
                    t = time.perf_counter()
                    assert rt.importFile(str(path), rt.Name('noPrompt'), using=importer)
                    rows.append({'bench': bench, 'rep': rep, 'format': fmt, 'operation': 'import', 'seconds': time.perf_counter() - t})
                    write(OUT / (path.stem + '-' + fmt + '-readback.json'), dump())
                    clear()
                    if fmt == 'fbx':
                        create(data)
        write(OUT / 'native-results.json', {'inventory': inventory, 'parameters': param_results,
                                           'rows': rows, 'delivery_passed': False})
        print('AGR_EXPERIMENT_COMPLETE', len(rows))
    finally:
        clear()
        print('AGR_CLEANUP_OBJECTS', len(rt.objects))


try:
    main()
except Exception:
    traceback.print_exc()
    raise
