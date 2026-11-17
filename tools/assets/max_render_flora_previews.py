"""new-case: previews for Flora library species without one (#1024), in the style of the A101 PreviewFlora images
(owner 06.11.2026: "viewport screenshot, same type"). Batch Max has no viewport, so: Scanline render of the _high
object alone, default lights, two-sided materials (the viewport lights back faces), unfiltered bitmaps (crisp alpha), camera 30 degrees off the front axis and 20 degrees
above, 40 degree FOV, object filling ~85 % of 1024 px; alpha PNG. The grey gradient of the A101 previews is laid
under it outside Max (tools/assets/composite_previews.py).

Run through the AGR Lab runner on a COPY of the library .max (nothing is saved):
  AGR_FLORA_MAX  copy of the library .max;  AGR_FLORA_TEX  folder with the textures (read only, by basename)
  AGR_BASES      comma list of species bases;  AGR_OUT  output folder (<base>_PREVIEW_alpha.png + previews.json)
"""
import json
import math
import os
from pathlib import Path

from pymxs import runtime as rt

OUT = Path(os.environ['AGR_OUT'])
OUT.mkdir(parents=True, exist_ok=True)
TEX = os.environ['AGR_FLORA_TEX']
SIZE, FOV, ELEV, AZIM, FILL = 1024, 40.0, 20.0, 30.0, 0.85


def repath(texdir):
    names = {f.lower(): os.path.join(texdir, f) for f in os.listdir(texdir)}
    n = 0
    for b in rt.getClassInstances(rt.Bitmaptexture):
        f = str(b.filename or '')
        hit = names.get(f.replace('\\', '/').rsplit('/', 1)[-1].lower())
        if hit and hit != f:
            b.filename = hit
            n += 1
    return n


def frame(node):
    bb = rt.nodeGetBoundingBox(node, rt.Matrix3(1))
    lo, hi = bb[0], bb[1]
    c = rt.Point3((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, (lo.z + hi.z) / 2)
    w = math.hypot(hi.x - lo.x, hi.y - lo.y) * 0.8  # seen 30 degrees off the axes
    h = hi.z - lo.z
    span = max(h, w) / FILL
    d = (span / 2) / math.tan(math.radians(FOV / 2))
    e = math.radians(ELEV)
    cam = rt.Targetcamera(fov=FOV, target=rt.Targetobject(pos=c))
    a = math.radians(AZIM)  # off-axis: crossed axis-aligned cards are never seen edge-on (black streaks)
    cam.pos = rt.Point3(c.x + d * math.cos(e) * math.sin(a), c.y - d * math.cos(e) * math.cos(a), c.z + d * math.sin(e))
    return cam


rt.loadMaxFile(os.environ['AGR_FLORA_MAX'], quiet=True, useFileUnits=True)
res = {'repathed': repath(TEX), 'previews': {}, 'missing': []}
for m in rt.getClassInstances(rt.StandardMaterial):  # lit back faces, like the viewport (copy, never saved)
    m.twoSided = True
for b in rt.getClassInstances(rt.Bitmaptexture):  # no pyramidal blur of the cut-out alpha at grazing angles
    b.filtering = 2  # none: black RGB under transparent texels otherwise smears into the leaves
rt.pngio.setType(rt.Name('true24'))
rt.pngio.setAlpha(True)
for base in [b.strip() for b in os.environ['AGR_BASES'].split(',') if b.strip()]:
    node = rt.getNodeByName(base + '_high')
    if node is None:
        res['missing'].append(base)
        continue
    keep = int(rt.getHandleByAnim(node))
    for o in rt.objects:
        o.isHidden = int(rt.getHandleByAnim(o)) != keep
    cam = frame(node)
    bm = rt.render(camera=cam, outputwidth=SIZE, outputheight=SIZE, vfb=False)
    path = str(OUT / (base + '_PREVIEW_alpha.png'))
    bm.filename = path
    rt.save(bm)
    rt.close(bm)
    rt.delete(cam)  # a target camera takes its target with it
    res['previews'][base] = {'file': Path(path).name, 'bytes': Path(path).stat().st_size}
(OUT / 'previews.json').write_text(json.dumps(res, indent=1), encoding='utf-8')
if res['missing']:
    raise RuntimeError('no _high object for: ' + ', '.join(res['missing']))
