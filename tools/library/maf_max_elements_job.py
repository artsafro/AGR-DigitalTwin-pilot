"""Headless 3ds Max job (pass A of the MAF library audit, issue #183): per-object inventory + mesh elements.

Run on a COPY of the library scene only:
  python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --file tools/library/maf_max_elements_job.py
Config (env or maxOps.mxsCmdLineArgs is not used; edit nothing): AGR_MAF_SCENE (copy .max), AGR_MAF_OUT (json).
Writes {"scene", "units", "unit_to_m", "objects": [{name, handle, class, layer, parent, bbox, tris, mat_ids,
material, elements: [{"bbox": [[x,y,z],[x,y,z]], "tris": n, "first_face": f}]}]} in metres.
Element order = ascending first face index of the collapsed TriMesh (pass B recomputes it the same way).
"""
import json
import os
import time

import pymxs

rt = pymxs.runtime

MXS = r'''
fn agrElements m = (
    local res = #()
    local left = #{1..m.numfaces}
    while not left.isEmpty do (
        local f0 = 0
        for f in left do (f0 = f; exit)
        local el = (meshop.getElementsUsingFace m #{f0}) * left  -- clamp: the call can return faces already taken
        local vs = meshop.getVertsUsingFace m el
        local lo = [1e9,1e9,1e9]; local hi = [-1e9,-1e9,-1e9]
        for v in vs do (local p = getVert m v; lo.x = amin lo.x p.x; lo.y = amin lo.y p.y; lo.z = amin lo.z p.z
                        hi.x = amax hi.x p.x; hi.y = amax hi.y p.y; hi.z = amax hi.z p.z)
        append res #(f0, el.numberSet, lo.x, lo.y, lo.z, hi.x, hi.y, hi.z)
        left = left - el
    )
    res
)
fn agrMatIds m = (
    local ids = #()
    for f in 1 to m.numfaces do appendIfUnique ids (getFaceMatID m f)
    sort ids
)
'''

UNIT = {'millimeters': 0.001, 'centimeters': 0.01, 'meters': 1.0, 'kilometers': 1000.0,
        'inches': 0.0254, 'feet': 0.3048, 'miles': 1609.344}


def main():
    scene = os.environ.get('AGR_MAF_SCENE', 'C:/x/t_3e6ff1b3/src.max')
    out = os.environ.get('AGR_MAF_OUT', 'C:/x/t_3e6ff1b3/elements.json')
    t0 = time.time()
    if not rt.loadMaxFile(scene, quiet=True, useFileUnits=True):
        raise RuntimeError('cannot load ' + scene)
    t_load = time.time() - t0
    rt.execute(MXS)
    su = str(rt.units.SystemType).lower()
    k = UNIT[su] * float(rt.units.SystemScale)
    rows = []
    for n in list(rt.objects):
        r = {'name': str(n.name), 'handle': int(n.inode.handle), 'class': str(rt.classOf(n)),
             'super': str(rt.superClassOf(n)), 'layer': str(n.layer.name),
             'parent': str(n.parent.name) if n.parent else None,
             'material': str(n.material.name) if n.material else None}
        if r['super'] == 'GeometryClass' and r['class'] not in ('TextPlus', 'text') \
                and rt.canConvertTo(n, rt.TriMeshGeometry):
            m = rt.snapshotAsMesh(n)
            try:
                r['tris'] = int(m.numfaces)
                if r['tris']:
                    r['mat_ids'] = [int(i) for i in rt.agrMatIds(m)]
                    els = rt.agrElements(m)
                    r['elements'] = [{'first_face': int(e[0]), 'tris': int(e[1]),
                                      'bbox': [[float(e[2]) * k, float(e[3]) * k, float(e[4]) * k],
                                               [float(e[5]) * k, float(e[6]) * k, float(e[7]) * k]]}
                                     for e in els]
                    lo = [min(e['bbox'][0][i] for e in r['elements']) for i in range(3)]
                    hi = [max(e['bbox'][1][i] for e in r['elements']) for i in range(3)]
                    r['bbox'] = [lo, hi]
            finally:
                rt.delete(m)
        rows.append(r)
    res = {'scene': scene, 'units': su, 'unit_to_m': k, 'load_s': round(t_load, 1), 'count': len(rows),
           'objects': rows, 'total_s': round(time.time() - t0, 1)}
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump(res, fh, ensure_ascii=False)
    print('AGR_ELEMENTS objects=%d seconds=%.1f' % (len(rows), time.time() - t0))


main()
