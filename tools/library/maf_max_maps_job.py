"""Headless 3ds Max job: dump every material and texture map of the MAF library scene (issue #524).

Pattern: verify actual artifacts, not exporter return codes (docs/domain/patterns/INDEX.md).
new-case: library-scene map readback for the atlas-cell material ID list (#524); FBX export
drops the file name of non-Bitmap maps (`Map #N` with an empty path), the scene keeps it.

Run on a COPY of the library scene only (read-only, never saves):
  AGR_MAF_SCENE=C:/x/t_3e6ff1b3/src.max AGR_MAF_MAPS_OUT=<NEW json> \
  python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --file tools/library/maf_max_maps_job.py
Writes {"scene", "materials": [{"name", "class", "maps": [{"name", "class", "file", "path"}]}],
"objects": {object name: material name}}; `file` is null when the map has no file property.
"""
import json
import os

import pymxs

rt = pymxs.runtime

MXS = r'''
fn agrFile t = (
    local f = undefined
    for p in #(#filename, #fileName, #HDRIMapName, #bitmapFile) while f == undefined do
        if isProperty t p then (local v = getProperty t p; if classOf v == String then f = v)
    if f == undefined then "" else f
)
fn agrMaps t path acc = (
    if t == undefined then return acc
    append acc #(t.name, (classOf t) as string, agrFile t, path)
    for i in 1 to (getNumSubTexmaps t) do agrMaps (getSubTexmap t i) (path + "/" + (i as string)) acc
    acc
)
fn agrMtl m path acc = (
    if m == undefined then return acc
    local maps = #()
    for i in 1 to (getNumSubTexmaps m) do agrMaps (getSubTexmap m i) ((getSubTexmapSlotName m i) as string) maps
    append acc #(m.name, (classOf m) as string, maps, path)
    if isKindOf m Material then
        for i in 1 to (getNumSubMtls m) do agrMtl (getSubMtl m i) (path + "/" + (i as string)) acc
    acc
)
fn agrAll = (
    local acc = #()
    for m in sceneMaterials do agrMtl m "" acc
    acc
)
'''


def main():
    scene = os.environ.get('AGR_MAF_SCENE', 'C:/x/t_3e6ff1b3/src.max')
    out = os.environ['AGR_MAF_MAPS_OUT']
    if os.path.exists(out):
        raise RuntimeError('refusing to overwrite ' + out)
    if not rt.loadMaxFile(scene, quiet=True, useFileUnits=True):
        raise RuntimeError('cannot load ' + scene)
    rt.execute(MXS)
    mats = []
    for m in rt.agrAll():
        maps = [{'name': str(x[0]), 'class': str(x[1]), 'file': str(x[2]) or None, 'path': str(x[3])}
                for x in m[2]]
        mats.append({'name': str(m[0]), 'class': str(m[1]), 'maps': maps, 'parent_path': str(m[3])})
    objects = {str(n.name): (str(n.material.name) if n.material else None) for n in list(rt.objects)}
    with open(out, 'x', encoding='utf-8') as f:
        json.dump({'scene': scene, 'materials': mats, 'objects': objects}, f, ensure_ascii=False)
    print('AGR_MAF_MAPS', len(mats), len(objects), out)


main()
