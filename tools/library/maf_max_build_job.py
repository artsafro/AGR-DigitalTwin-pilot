"""Headless 3ds Max job (pass B of the MAF library audit, issue #183): one .max + FBX + preview per MAF.

Reads the plan written by `maf_catalogue.py plan` and builds, for every entry, a library copy of its geometry:
split objects (several MAF attached into one mesh) are copied, collapsed to Editable Mesh and reduced to the faces of
the entry's elements; single-MAF objects are plain copies. Each copy is saved alone with `saveNodes` (new file),
exported to FBX (selected only) and rendered to a PNG preview (Scanline, default lights, only that node renderable).
The loaded scene is a COPY and is never saved. Results are appended to a JSONL file (one row per entry), so a
second run skips entries already built ok.

Env: AGR_MAF_SCENE (copy .max), AGR_MAF_PLAN (plan json), AGR_MAF_LIB (library dir, outside the repo),
AGR_MAF_BUILT (jsonl), AGR_MAF_LIMIT (optional int), AGR_MAF_PREVIEW_PX (default 256).
"""
import json
import math
import os
import time

import pymxs

rt = pymxs.runtime

MXS = r'''
fn agrKeepElements c firstFaces = (
    -- same partition as agrElements in maf_max_elements_job.py (seed = lowest free face, clamp to free faces)
    local m = c.mesh
    local want = firstFaces as bitArray
    local keep = #{}
    local left = #{1..m.numfaces}
    while not left.isEmpty do (
        local f0 = 0
        for f in left do (f0 = f; exit)
        local el = (meshop.getElementsUsingFace m #{f0}) * left
        if want[f0] do keep += el
        left = left - el
    )
    local drop = #{1..m.numfaces} - keep
    if not drop.isEmpty do meshop.deleteFaces c drop delIsoVerts:true
    update c
    c.mesh.numfaces
)
fn agrMatIds c = (
    local m = snapshotAsMesh c
    local ids = #()
    for f in 1 to m.numfaces do appendIfUnique ids (getFaceMatID m f)
    delete m
    sort ids
)
fn agrRender c pngPath px = (
    local bb = nodeGetBoundingBox c (matrix3 1)
    local ctr = (bb[1] + bb[2]) / 2.0
    local r = (length (bb[2] - bb[1])) / 2.0
    if r < 0.001 do r = 0.001
    local dir = normalize [1, -1.2, 0.8]
    local fov = 40.0
    local d = r / (sin (fov / 2.0)) * 1.05
    local cam = Freecamera fov:fov
    cam.transform = (matrixFromNormal dir)
    cam.pos = ctr + dir * d
    cam.dir = dir
    cam.nearclip = 0.0; cam.clipManually = false
    c.renderable = true
    local bmp = render camera:cam outputSize:[px, px] vfb:false quiet:true outputfile:pngPath
    c.renderable = false
    delete cam
    if bmp != undefined do close bmp
    doesFileExist pngPath
)
'''


def load_done(path):
    done = set()
    if os.path.exists(path):
        with open(path, encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if line:
                    row = json.loads(line)
                    if row.get('ok'):
                        done.add(row['id'])
    return done


def main():
    scene = os.environ.get('AGR_MAF_SCENE', 'C:/x/t_3e6ff1b3/src.max')
    plan = json.load(open(os.environ.get('AGR_MAF_PLAN', 'C:/x/t_3e6ff1b3/plan.json'), encoding='utf-8'))
    lib = os.environ.get('AGR_MAF_LIB', 'C:/x/t_3e6ff1b3/library')
    built = os.environ.get('AGR_MAF_BUILT', os.path.join(lib, 'built.jsonl'))
    limit = int(os.environ.get('AGR_MAF_LIMIT', '0') or 0)
    px = int(os.environ.get('AGR_MAF_PREVIEW_PX', '256'))
    for sub in ('max', 'fbx', 'preview'):
        os.makedirs(os.path.join(lib, sub), exist_ok=True)
    t0 = time.time()
    if not rt.loadMaxFile(scene, quiet=True, useFileUnits=True):
        raise RuntimeError('cannot load ' + scene)
    rt.execute(MXS)
    rt.renderers.current = rt.Default_Scanline_Renderer()
    rt.backgroundColor = rt.color(205, 205, 205)  # light grey: dark materials stay visible
    for n in list(rt.objects):
        try:
            n.renderable = False
        except Exception:
            pass
    rt.FBXExporterSetParam('Animation', False)
    rt.FBXExporterSetParam('EmbedTextures', False)
    rt.FBXExporterSetParam('Cameras', False)
    rt.FBXExporterSetParam('Lights', False)
    by_handle = {int(n.inode.handle): n for n in rt.objects}
    done = load_done(built)
    todo = [e for e in plan['entries'] if e['id'] not in done]
    if limit:
        todo = todo[:limit]
    n_ok = 0
    with open(built, 'a', encoding='utf-8') as out:
        for e in todo:
            t1 = time.time()
            row = {'id': e['id'], 'ok': False}
            c = None
            try:
                src = by_handle.get(int(e['source_handle']))
                if src is None:
                    raise RuntimeError('source handle not found')
                c = rt.copy(src)
                c.parent = rt.undefined
                c.name = e['slug']
                if e.get('split'):
                    rt.convertToMesh(c)
                    row['tris_built'] = int(rt.agrKeepElements(c, [int(f) for f in e['element_first_faces']]))
                else:
                    m = rt.snapshotAsMesh(c)
                    row['tris_built'] = int(m.numfaces)
                    rt.delete(m)
                row['mat_ids'] = [int(i) for i in rt.agrMatIds(c)]
                mp = os.path.join(lib, 'max', e['slug'] + '.max').replace('\\', '/')
                fp = os.path.join(lib, 'fbx', e['slug'] + '.fbx').replace('\\', '/')
                pp = os.path.join(lib, 'preview', e['slug'] + '.png').replace('\\', '/')
                rt.saveNodes(c, mp, quiet=True)
                rt.select(c)
                rt.exportFile(fp, rt.Name('noPrompt'), selectedOnly=True, using=rt.FBXEXP)
                rt.clearSelection()
                rendered = bool(rt.agrRender(c, pp, px))
                row.update({'max_path': mp, 'fbx_path': fp, 'preview_path': pp if rendered else None,
                            'max_ok': os.path.exists(mp), 'fbx_ok': os.path.exists(fp), 'preview_ok': rendered})
                row['ok'] = row['max_ok'] and row['fbx_ok'] and rendered and row['tris_built'] == e['tris']
                if row['tris_built'] != e['tris']:
                    row['error'] = 'tris mismatch %d != %d' % (row['tris_built'], e['tris'])
            except Exception as exc:
                row['error'] = str(exc)[:300]
            finally:
                if c is not None:
                    try:
                        rt.delete(c)
                    except Exception:
                        pass
            row['seconds'] = round(time.time() - t1, 2)
            n_ok += int(row['ok'])
            out.write(json.dumps(row, ensure_ascii=False) + '\n')
            out.flush()
    print('AGR_BUILD todo=%d ok=%d seconds=%.1f' % (len(todo), n_ok, time.time() - t0))


main()
