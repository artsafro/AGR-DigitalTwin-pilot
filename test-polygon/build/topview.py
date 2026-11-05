"""new-case: Top-view evidence renders of polygon_all.max (run inside 3ds Max, batch or UI).

Usage (shared DCC lock, opens a COPY of the scene, saves nothing):

    set AGR_TOPVIEW_OUT=C:/x/ev/top_2024      (prefix; writes <prefix>_all.png, <prefix>_<base>.png)
    python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max \
        --scene <out>/polygon_all.max --file test-polygon/build/topview.py --version 2024

3dsmaxbatch has no viewport, so the "top view" is a render through an orthographic
target camera above the scene (Scanline, else Quicksilver, else ART; the default Arnold
renders black without a licence). One overview of the whole polygon plus one image per
base rectangle (`_base_*`), so the 0.35 m station captions are readable. In memory only:
captions get a thin Extrude and a black self-lit material, a light is added. Not saved.
"""
import json
import math
import os
import re

from pymxs import runtime as rt

OUT = os.environ.get('AGR_TOPVIEW_OUT')
WIDTH_ALL = int(os.environ.get('AGR_TOPVIEW_WIDTH', '3200'))
WIDTH_BASE = 2000


def _bbox(nodes):
    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    for node in nodes:
        a, b = node.min, node.max
        for i, (p, q) in enumerate(((a.x, b.x), (a.y, b.y), (a.z, b.z))):
            lo[i] = min(lo[i], p)
            hi[i] = max(hi[i], q)
    if not all(math.isfinite(v) for v in lo + hi):
        raise SystemExit('topview: no bounded nodes')
    return lo, hi


def _renderer():
    for name in ('Default_Scanline_Renderer', 'Quicksilver_Hardware_Renderer', 'ART_Renderer'):
        cls = getattr(rt, name, None)
        if cls is None:
            continue
        try:
            rt.renderers.current = cls()
            return name
        except Exception:  # noqa: BLE001 - try the next renderer
            continue
    raise SystemExit('topview: no Scanline/Quicksilver/ART renderer')


def _render(lo, hi, path, width, pad=0.04):
    cx, cy = (lo[0] + hi[0]) / 2.0, (lo[1] + hi[1]) / 2.0
    span_x = max(hi[0] - lo[0], 1.0) * (1.0 + pad)
    span_y = max(hi[1] - lo[1], 1.0) * (1.0 + pad)
    height = max(1, int(round(width * span_y / span_x)))
    dist = max(span_x, span_y) * 2.0 + 20.0
    cam = rt.Targetcamera(name='_topview_cam', target=rt.Targetobject(name='_topview_target'))
    # A tiny y offset keeps the up vector defined for a camera looking straight down.
    cam.pos = rt.Point3(cx, cy - 0.001, hi[2] + dist)
    cam.target.pos = rt.Point3(cx, cy, hi[2])
    cam.orthoProjection = True
    cam.fov = math.degrees(2.0 * math.atan((span_x / 2.0) / dist))
    rt.render(camera=cam, outputwidth=width, outputheight=height, outputfile=path, vfb=False)
    target = cam.target
    rt.delete(cam)
    if not rt.isDeleted(target):
        rt.delete(target)
    return [width, height]


def main():
    if not OUT:
        raise SystemExit('topview: AGR_TOPVIEW_OUT is not set')
    nodes = list(rt.objects)
    if not nodes:
        raise SystemExit('topview: scene is empty')
    ink = rt.Standardmaterial(name='_topview_ink')
    ink.diffuse = rt.Color(0, 0, 0)
    ink.selfIllumAmount = 100
    texts = 0
    for node in nodes:
        if rt.classOf(node) == rt.Text:
            rt.addModifier(node, rt.Extrude(amount=0.02))
            node.material = ink
            texts += 1
    bounded = [n for n in nodes if rt.superClassOf(n) in (rt.GeometryClass, rt.Shape)]
    lo, hi = _bbox(bounded)
    renderer = _renderer()
    sun = rt.Directionallight(name='_topview_sun')
    sun.pos = rt.Point3((lo[0] + hi[0]) / 2.0, (lo[1] + hi[1]) / 2.0, hi[2] + 1000.0)
    sun.overShoot = True
    sun.multiplier = 1.2
    rt.ambientColor = rt.Color(110, 110, 110)
    shots = {'all': {'file': OUT + '_all.png', 'size': _render(lo, hi, OUT + '_all.png', WIDTH_ALL)}}
    for base in sorted((n for n in nodes if str(n.name).startswith('_base_')), key=lambda n: n.min.x):
        b_lo, b_hi = _bbox([base])
        tag = re.sub(r'[^0-9A-Za-z_.-]+', '_', str(base.name)[len('_base_'):]) or 'base'
        path = '{}_{}.png'.format(OUT, tag)
        shots[tag] = {'file': path, 'size': _render(b_lo, [b_hi[0], b_hi[1], hi[2]], path, WIDTH_BASE, pad=0.12)}
    print('AGR_TOPVIEW ' + json.dumps({
        'max': str(rt.maxVersion()[0]), 'renderer': renderer,
        'file': str(rt.maxFilePath) + str(rt.maxFileName), 'nodes': len(nodes), 'texts': texts,
        'bbox': [lo, hi], 'shots': shots}))


main()
