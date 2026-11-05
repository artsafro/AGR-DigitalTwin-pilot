"""new-case: #908 branch A native acceptance of model.triangulate, ucx.triangulate, export.pivot_place in locked
batch Max on DISPOSABLE synthetic scenes (docs/experiments/<id>.md, «Minimal acceptance test»).

Run via the lab DCC runner; AGR_TEST_OUTPUT must name a NEW directory. The package is loaded from this checkout
(adapters/max/agr_tools), through runtime.edits_080 exactly as the panel/macros/MCP call it (preview -> apply).
Nothing is saved; the scene is reset between parts. AGR_NO_PROMPT keeps the ±0.000 prompt out of batch Max.
"""
import json
import math
import os
from pathlib import Path
import struct
import sys
import time
import traceback

from pymxs import runtime as rt

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters' / 'max' / 'agr_tools'
OUT = Path(os.environ['AGR_TEST_OUTPUT'])
OUT.mkdir(parents=True, exist_ok=False)
os.environ['LOCALAPPDATA'] = str(OUT / 'localappdata')
os.environ['AGR_NO_PROMPT'] = '1'
sys.path.insert(0, str(PKG))
import runtime as agr  # noqa: E402

summary = {'max_version': list(rt.maxVersion())[:3], 'checks': {}, 'errors': {}}
assert not rt.maxFileName, 'only an empty batch document is allowed'
emax = agr._load_core('edit_max.py', 'agr_tools_edit_max')
ucx = agr._load_core('ucx_core.py', 'agr_tools_ucx_core')

rt.execute(r'''
global agr908t_poly, agr908t_stats, agr908t_world
fn agr908t_poly name pts counts = (
    -- Editable Poly from a flat point3 array cut into polygons by counts (each polygon its own vertices)
    local p = convertToPoly (Plane length:1 width:1 lengthsegs:1 widthsegs:1)
    polyop.deleteFaces p #{1} delIsoVerts:true
    local k = 0
    for c in counts do (
        local ids = for i = 1 to c collect (polyop.createVert p pts[k + i])
        k += c
        polyop.createPolygon p ids
    )
    p.name = name
    p
)
fn agr908t_stats p = (
    -- #(degrees, face areas, matIDs, SG, uv areas of channel 1 (0 when absent)), object level
    local nf = polyop.getNumFaces p
    local hasUV = polyop.getMapSupport p 1
    local deg = #(); local ar = #(); local mid = #(); local sg = #(); local uva = #()
    for f = 1 to nf do (
        append deg (polyop.getFaceDeg p f)
        append ar (polyop.getFaceArea p f)
        append mid (polyop.getFaceMatID p f)
        append sg (polyop.getFaceSmoothGroup p f)
        local a = 0.0
        if hasUV do (
            local mf = polyop.getMapFace p 1 f
            local n = mf.count
            for i = 1 to n do (
                local u0 = polyop.getMapVert p 1 mf[i]
                local u1 = polyop.getMapVert p 1 mf[(mod i n) as integer + 1]
                a += u0.x * u1.y - u1.x * u0.y
            )
        )
        append uva (abs (a / 2.0))
    )
    #(deg, ar, mid, sg, uva)
)
fn agr908t_world n = for i = 1 to (polyop.getNumVerts n) collect (in coordsys world polyop.getVert n i)
''')


def mkpoly(name, polys):
    return rt.agr908t_poly(name, [q for poly in polys for q in poly], [len(poly) for poly in polys])


def check(name, fn):
    t0 = time.perf_counter()
    try:
        summary['checks'][name] = fn()
    except Exception:  # noqa: BLE001 - recorded; the run fails at the end
        summary['errors'][name] = traceback.format_exc()[-3000:]
    summary.setdefault('seconds', {})[name] = round(time.perf_counter() - t0, 3)


def reset():
    rt.resetMaxFile(rt.name('noPrompt'))
    rt.units.SystemType = rt.name('meters')
    rt.units.SystemScale = 1.0


def P(x, y, z):
    return rt.Point3(float(x), float(y), float(z))


def ngon(r, n=8, c=(0.0, 0.0, 0.0)):
    return [P(c[0] + r * math.cos(2 * math.pi * i / n), c[1] + r * math.sin(2 * math.pi * i / n), c[2])
            for i in range(n)]


def stats(n):
    deg, ar, mid, sg, uva = (list(a) for a in rt.agr908t_stats(n))
    return {'deg': [int(d) for d in deg], 'area': [float(a) for a in ar], 'mid': [int(m) for m in mid],
            'sg': [int(s) for s in sg], 'uv': [float(u) for u in uva]}


def by_key(st, key):
    out = {}
    for k, a in zip(st[key], st['area']):
        out[k] = out.get(k, 0.0) + a
    return out


def close(a, b, rel=1e-6, abs_=0.0):
    return abs(a - b) <= max(rel * max(abs(a), abs(b)), abs_)


def f32(x):
    return struct.unpack('<f', struct.pack('<f', x))[0]


def ulp32(x):
    x = abs(f32(x))
    return abs(struct.unpack('<f', struct.pack('<I', struct.unpack('<I', struct.pack('<f', x))[0] + 1))[0] - x)


def names():
    return sorted(str(n.name) for n in rt.objects)


# ---- model.triangulate ------------------------------------------------------------------------------------
def tri_scene():
    reset()
    u = [(0, 0), (6, 0), (6, 6), (4, 6), (4, 2), (2, 2), (2, 6), (0, 6)]
    comb = [(0, 0), (10, 0), (10, 4), (8, 4), (8, 1), (6, 1), (6, 4), (4, 4), (4, 1), (2, 1), (2, 4), (0, 4)]
    # sub-millimetre faces sit near the object origin: at x ~ 3000 float32 spacing is 0.24 mm and Max itself
    # collapses them (measured, job 20261105-011351-26e1965d: reported as degenerate, not hidden)
    mix = [ngon(1000.0, c=(0, 3000, 0)), ngon(1.0, c=(3000, 0, 0)), ngon(1e-3, c=(0.005, 0, 0)),
           ngon(1e-4, c=(0.01, 0, 0)), [P(3030 + x, y, 0) for x, y in u],
           [P(0.02 + x * 1e-4, y * 1e-4, 0) for x, y in u], [P(3050 + x, y, 0) for x, y in comb]]
    a = mkpoly('SM_Tri_Mix', mix)
    a.rotation = rt.EulerAngles(90, 0, 0)
    a.pos = P(12345.678, -6789.012, 150.0)
    hexp = [[P(1.0 * math.cos(i * math.pi / 3) + 0, math.sin(i * math.pi / 3), 0.15 * (-1) ** i) for i in range(6)]]
    mkpoly('SM_Tri_NonPlanar', hexp)
    cyl = rt.Cylinder(name='SM_Tri_Cyl', radius=1.0, height=2.0, sides=24, heightsegs=1, capsegs=1,
                      mapcoords=True, pos=P(0, 20, 0))
    rt.convertTo(cyl, rt.Editable_Poly)
    for f in range(1, int(rt.polyop.getNumFaces(cyl)) + 1):
        rt.polyop.setFaceMatID(cyl, f, 1 + (f % 3))
    hexes = [ngon(1.0, 6, c=(3.0 * x, 3.0 * y, 0)) for x in range(20) for y in range(20)]
    h = mkpoly('SM_Tri_Hex400', hexes)
    h.pos = P(0, 100, 0)
    prim = rt.Box(name='SM_Tri_BoxPrim', length=2, width=3, height=1, pos=P(0, -20, 0))
    rt.addModifier(prim, rt.Bend(angle=0))
    return [a, rt.getNodeByName('SM_Tri_NonPlanar'), cyl, h, prim]


def model_triangulate():
    nodes = tri_scene()
    before = emax.snapshot(nodes)
    st_before = {str(n.name): stats(n) for n in nodes if str(rt.classOf(n.baseObject)) == 'Editable_Poly'}
    rt.select(nodes[0])
    keep_sel = [str(n.name) for n in rt.selection]
    t0 = time.perf_counter()
    pv = agr.edits_080('model.triangulate', 'preview', nodes=nodes)
    t_prev = time.perf_counter() - t0
    assert pv['status'] == 'pass', pv['plan']['ambiguous']
    rows = {r['name']: r for r in pv['plan']['rows']}
    assert rows['SM_Tri_Mix']['ngons'] == 7 and rows['SM_Tri_Hex400']['diagonals'] == 1200, rows
    assert rows['SM_Tri_BoxPrim']['convert'], rows['SM_Tri_BoxPrim']
    assert agr.parse_report(json.dumps(pv)) == pv
    t0 = time.perf_counter()
    ap = agr.edits_080('model.triangulate', 'apply', pv)
    t_apply = time.perf_counter() - t0
    assert ap['status'] == 'pass', [o for o in ap['objects'] if o['findings']]
    after = emax.snapshot(nodes)
    assert after == before, 'working objects changed'
    assert [str(n.name) for n in rt.selection] == keep_sel, 'selection not restored'
    out = {'preview_s': round(t_prev, 3), 'apply_s': round(t_apply, 3), 'copies': {}}
    for c in ap['plan']['copies']:
        node = rt.getNodeByName(c['copy'])
        assert node is not None and str(node.layer.name) == 'AGR_export', c
        st = stats(node)
        left = [i + 1 for i, d in enumerate(st['deg']) if d > 3]
        assert not left and c['leftovers'] == [], (c['copy'], left[:10])
        assert c['verts_after'] == c['verts_before'], c
        src = st_before.get(c['source'])
        res = {'faces': len(st['deg']), 'diagonals': c['diagonals'], 'failed': len(c['failed'])}
        assert not c['failed'], c
        if src is not None and c['source'] != 'SM_Tri_NonPlanar':
            assert close(sum(st['area']), sum(src['area']), 1e-6), (c['source'], sum(st['area']), sum(src['area']))
            # every original face tiled exactly: per-face area sums by matID / SG unchanged
            for key in ('mid', 'sg'):
                a, b = by_key(st, key), by_key(src, key)
                assert set(a) == set(b) and all(close(a[k], b[k], 1e-6) for k in a), (c['source'], key)
            if c['source'] == 'SM_Tri_Cyl':
                assert close(sum(st['uv']), sum(src['uv']), 1e-6) and sum(src['uv']) > 0, 'UV area changed'
                res['uv_area'] = [sum(src['uv']), sum(st['uv'])]
            res['area_rel'] = abs(sum(st['area']) - sum(src['area'])) / sum(src['area'])
        out['copies'][c['source']] = res
    # timing: 400 hexagons alone, preview + apply
    hexnode = rt.getNodeByName('SM_Tri_Hex400')
    t0 = time.perf_counter()
    p2 = agr.edits_080('model.triangulate', 'preview', nodes=[hexnode])
    agr.edits_080('model.triangulate', 'apply', p2)
    out['hex400_s'] = round(time.perf_counter() - t0, 3)
    assert out['hex400_s'] < 2.0, out['hex400_s']
    # stale preview: the scene changed -> refused, no copy
    p3 = agr.edits_080('model.triangulate', 'preview', nodes=[hexnode])
    rt.move(hexnode, P(0.001, 0, 0))
    count = len(rt.objects)
    try:
        agr.edits_080('model.triangulate', 'apply', p3)
    except ValueError as exc:
        out['stale'] = str(exc)[:80]
    else:
        raise AssertionError('stale preview applied')
    assert len(rt.objects) == count
    return out


# ---- ucx.triangulate --------------------------------------------------------------------------------------
def prism(name, ring, h):
    """Closed welded prism over a CCW outline (outward winding)."""
    n = len(ring)
    polys = [[P(x, y, 0) for x, y in reversed(ring)], [P(x, y, h) for x, y in ring]]
    polys += [[P(*ring[i], 0), P(*ring[(i + 1) % n], 0), P(*ring[(i + 1) % n], h), P(*ring[i], h)] for i in range(n)]
    node = mkpoly(name, polys)
    node.weldThreshold = 1e-3
    rt.polyop.weldVertsByThreshold(node, rt.execute('#all'))
    assert int(rt.polyop.getNumVerts(node)) == 2 * n, (name, int(rt.polyop.getNumVerts(node)))
    return node


def ucx_scene():
    reset()
    nodes = []

    def box(name, pos):
        b = rt.Box(name=name, length=2, width=2, height=2, pos=pos)
        rt.convertTo(b, rt.Editable_Poly)
        return b
    nodes.append(box('UCX_Box', P(0, 0, 0)))
    for i, corner in enumerate(('raise_a', 'raise_b')):
        b = box('UCX_Raise_' + corner[-1], P(10 + 5 * i, 0, 0))
        tops = [v for v in range(1, 9) if float(rt.polyop.getVert(b, v).z) > 1.0]
        tops.sort(key=lambda v: (float(rt.polyop.getVert(b, v).x), float(rt.polyop.getVert(b, v).y)))
        v = tops[0] if i == 0 else tops[1]
        rt.polyop.moveVert(b, v, P(0, 0, 0.6))
        nodes.append(b)
    for name, sides, pos in (('UCX_Oct', 8, P(0, 10, 0)), ('UCX_P64', 64, P(0, 20, 0))):
        c = rt.Cylinder(name=name, radius=1, height=2, sides=sides, heightsegs=1, capsegs=1, pos=pos)
        rt.convertTo(c, rt.Editable_Poly)
        nodes.append(c)
    ring = [(1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1)]
    nodes.append(prism('UCX_MidEdge', ring, 2.0))
    prim = rt.Box(name='UCX_BoxPrim', length=2, width=2, height=2, pos=P(30, 0, 0))
    nodes.append(prim)
    mesh = rt.Box(name='UCX_Mesh', length=2, width=2, height=2, pos=P(35, 0, 0))
    rt.convertToMesh(mesh)
    nodes.append(mesh)
    mod = box('UCX_Mod', P(40, 0, 0))
    rt.addModifier(mod, rt.Edit_Poly())
    nodes.append(mod)
    hid = box('UCX_Hidden', P(45, 0, 0))
    rt.polyop.setHiddenFaces(hid, rt.execute('#{1, 2}'))
    nodes.append(hid)
    lpts = [(0, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2)]
    lp = prism('UCX_L', lpts, 1.0)
    lp.pos = P(50, 0, 0)
    nodes.append(lp)
    nodes.append(rt.Point(name='UCX_Helper'))
    return nodes


def ucx_triangulate():
    nodes = ucx_scene()
    geo = [n for n in nodes if str(n.name) != 'UCX_Helper']
    before = emax.snapshot(geo)
    hid_src = rt.getNodeByName('UCX_Hidden')
    hidden_before = list(rt.polyop.getHiddenFaces(hid_src))
    pv = agr.edits_080('ucx.triangulate', 'preview', nodes=nodes)
    skipped = {s['item']: s['reason'] for s in pv['plan']['skipped']}
    assert 'UCX_Helper' in skipped, skipped
    rows = {r['name']: r for r in pv['plan']['rows']}
    for n in ('UCX_BoxPrim', 'UCX_Mesh', 'UCX_Mod'):
        assert rows[n]['convert'], (n, rows[n])
    assert rows['UCX_L']['action'] == 'hull', rows['UCX_L']
    ap = agr.edits_080('ucx.triangulate', 'apply', pv)
    bad = [o for o in ap['objects'] if o['findings']]
    assert ap['status'] == 'pass', bad
    assert emax.snapshot(geo) == before, 'working UCX changed'
    assert list(rt.polyop.getHiddenFaces(hid_src)) == hidden_before, 'source hidden state changed'
    out = {'skipped': skipped, 'pieces': {}}
    for c in ap['plan']['copies']:
        node = rt.getNodeByName(c['copy'])
        st = stats(node)
        assert all(d == 3 for d in st['deg']), c['copy']
        assert c['check']['ok'] and c['check']['convex'] and c['check']['closed'], c
        assert min(st['area']) > 1e-9, (c['copy'], min(st['area']))
        if c['action'] != 'hull':
            assert c['verts_after'] == c['verts_before'], c
        out['pieces'][c['source']] = {'action': c['action'], 'diagonals': c['diagonals'],
                                      'worst': c['check']['worst'], 'convert': c['convert'],
                                      'hidden': [c['hidden_faces_before'], c['hidden_faces_after']]}
    hid = out['pieces']['UCX_Hidden']['hidden']
    assert hid == [2, 4], hid  # two hidden quads -> four hidden triangles on the copy
    return out


# ---- export.pivot_place -----------------------------------------------------------------------------------
def pivot_scene(xy, annex=True):
    reset()
    slab = rt.Box(name='SM_Building', length=12, width=22, height=0.6, pos=P(0, 0, 149.4))
    block = rt.Box(name='Block', length=10, width=20, height=9, pos=P(0, 0, 150.0))
    rt.convertTo(slab, rt.Editable_Poly)
    rt.polyop.attach(slab, block)
    rt.rotate(slab, rt.EulerAngles(0, 0, 30))
    slab.pos = P(xy[0], xy[1], 149.4)
    nodes = [slab]
    if annex:
        an = rt.Box(name='SM_Annex', length=4, width=4, height=3, pos=P(xy[0] + 30, xy[1], 150.0))
        rt.convertTo(an, rt.Editable_Poly)
        rt.rotate(an, rt.EulerAngles(0, 0, 30))
        nodes.append(an)
    return nodes


def floor_faces(n):
    out = []
    for f in range(1, int(rt.polyop.getNumFaces(n)) + 1):
        nz = float(rt.polyop.getFaceNormal(n, f).z)
        cz = float(rt.polyop.getFaceCenter(n, f).z)
        if nz > 0.99 and abs(cz - 150.0) < 1e-3:
            out.append(f)
    return out


def world(n):
    return [(float(p.x), float(p.y), float(p.z)) for p in rt.agr908t_world(n)]


def pivot_case(xy, mode):
    nodes = pivot_scene(xy)
    b = nodes[0]
    faces = floor_faces(b)
    assert len(faces) == 1, faces
    options = None
    if mode == 'faces':
        rt.polyop.setFaceSelection(b, rt.execute('#{%d}' % faces[0]))
    elif mode == 'verts':
        rt.polyop.setFaceSelection(b, rt.execute('#{}'))
        vs = list(rt.polyop.getFaceVerts(b, faces[0]))
        rt.polyop.setVertSelection(b, rt.execute('#{%s}' % ','.join(str(int(v)) for v in vs)))
    elif mode == 'explicit':
        options = {'floor_z': '150,000', 'target': 'both'}
    before = emax.snapshot(nodes)
    pivots_before = [[float(n.pivot.x), float(n.pivot.y), float(n.pivot.z)] for n in nodes]
    src_world = [world(n) for n in nodes]
    ctrl_z = float(rt.execute("$'SM_Building'.rotation.controller.Z_Rotation"))
    pv = agr.edits_080('export.pivot_place', 'preview', nodes=nodes, options=options)
    fl = pv['plan']['floor']
    assert abs(fl['value'] - 150.0) < 1e-3, fl
    assert [r['rotation_ui'][2] for r in pv['plan']['nodes']] == ['30.000', '30.000'], pv['plan']['nodes']
    assert abs(ctrl_z - 30.0) < 1e-4, ctrl_z  # what the UI shows == what we report
    assert all('e' not in t for t in pv['plan']['pivot']), pv['plan']['pivot']
    ap = agr.edits_080('export.pivot_place', 'apply', pv)
    assert ap['status'] == 'pass'
    assert emax.snapshot(nodes) == before, 'working objects changed'
    assert [[float(n.pivot.x), float(n.pivot.y), float(n.pivot.z)] for n in nodes] == pivots_before
    pv_val = pv['plan']['pivot_value']
    res = {'floor': fl, 'pivot': pv['plan']['pivot'], 'ctrl_z': ctrl_z}
    by = {}
    for c in ap['plan']['copies']:
        node = [n for n in rt.objects if int(rt.getHandleByAnim(n)) == c['handle']][0]
        by[(c['source'], c['target'])] = node
    tol_xy = 1e-3 + ulp32(max(abs(xy[0]), abs(xy[1])))
    worst_npm = 0.0
    for i, n in enumerate(nodes):
        npm = by[(str(n.name), 'npm')]
        w = world(npm)
        worst = max(math.dist(a, b2) for a, b2 in zip(w, src_world[i]))
        worst_npm = max(worst_npm, worst)
        assert worst <= max(1e-4, 2 * ulp32(max(abs(xy[0]), abs(xy[1])))), (str(n.name), worst)
        piv = (float(npm.pivot.x), float(npm.pivot.y), float(npm.pivot.z))
        assert abs(piv[0] - pv_val[0]) <= tol_xy and abs(piv[1] - pv_val[1]) <= tol_xy, (piv, pv_val)
        assert abs(piv[2] - 150.0) <= 1e-3, piv
    res['npm_worst_vertex_shift_m'] = worst_npm
    res['npm_pivot_tol_m'] = tol_xy
    vb = by[('SM_Building', 'vpm')]
    va = by[('SM_Annex', 'vpm')]
    assert math.dist((float(vb.pivot.x), float(vb.pivot.y), float(vb.pivot.z)), (0, 0, 0)) <= 1e-3
    floor_z = min(float(rt.polyop.getVert(vb, v).z) for v in rt.polyop.getFaceVerts(vb, faces[0]))
    assert abs(floor_z) <= 1e-3, floor_z
    # the offset between the two models is kept (lab: Combine near zero lost it)
    off_src = [float(getattr(nodes[1].center, a)) - float(getattr(nodes[0].center, a)) for a in 'xyz']
    off_vpm = [float(getattr(va.center, a)) - float(getattr(vb.center, a)) for a in 'xyz']
    assert all(abs(a - b2) <= 1e-3 + ulp32(max(abs(xy[0]), abs(xy[1]))) for a, b2 in zip(off_src, off_vpm)), \
        (off_src, off_vpm)
    assert abs(float(rt.execute("$'%s'.rotation.controller.Z_Rotation" % str(vb.name))) - 30.0) < 1e-3
    res.update(vpm_floor_z=floor_z, offset_src=off_src, offset_vpm=off_vpm,
               copies=sorted(str(n.name) for n in by.values()))
    return res, by


def pivot_refusals():
    nodes = pivot_scene((12345.678, -6789.012))
    out = {}
    for name, options, word in (('no_selection', None, 'bbox bottom is never used'),
                                ('empty_field', {'floor_z': ''}, 'empty'),
                                ('exponent', {'floor_z': '1.5e2'}, 'plain decimal'),
                                ('bad_target', {'target': 'msk', 'floor_z': '150'}, 'target')):
        count = len(rt.objects)
        try:
            agr.edits_080('export.pivot_place', 'preview', nodes=nodes, options=options)
        except ValueError as exc:
            assert word in str(exc), (name, exc)
            out[name] = str(exc)[:90]
        else:
            raise AssertionError('accepted ' + name)
        assert len(rt.objects) == count
    return out


def pivot_fbx_readback(by):
    """Export NPM and VPM copies to FBX, read back in a fresh scene and repeat the pivot checks in metres."""
    res = {}
    targets = {}
    for (src, t), node in by.items():
        if src != 'SM_Building':
            continue
        path = OUT / 'pivot_{}.fbx'.format(t)
        rt.select(node)
        rt.FBXExporterSetParam('ConvertUnit', 'm')
        rt.FBXExporterSetParam('UpAxis', 'Z')
        rt.FBXExporterSetParam('ASCII', False)
        ok = rt.exportFile(str(path), rt.name('noPrompt'), selectedOnly=True, using=rt.FBXEXP)
        assert ok and path.is_file(), path
        targets[t] = (path, [float(node.pivot.x), float(node.pivot.y), float(node.pivot.z)])
    for t, (path, piv) in targets.items():
        reset()
        rt.FBXImporterSetParam('ConvertUnit', 'm')
        rt.FBXImporterSetParam('UpAxis', 'Z')
        assert rt.importFile(str(path), rt.name('noPrompt'), using=rt.FBXIMP)
        geo = [n for n in rt.geometry]
        assert len(geo) == 1, names()
        n = geo[0]
        got = [float(n.pivot.x), float(n.pivot.y), float(n.pivot.z)]
        assert all(abs(a - b) <= 1e-3 + ulp32(max(abs(v) for v in piv)) for a, b in zip(got, piv)), (t, got, piv)
        rt.convertTo(n, rt.Editable_Poly)
        zmin = min(float(p.z) for p in rt.agr908t_world(n))
        res[t] = {'pivot': got, 'min_z': zmin}
        if t == 'vpm':
            assert abs(zmin + 0.6) <= 1e-3, zmin  # slab bottom 0.6 m under the clean floor at 0
    return res


def pivot_place():
    out = {}
    out['faces_1e4'], _ = pivot_case((12345.678, -6789.012), 'faces')
    out['verts_1e4'], _ = pivot_case((12345.678, -6789.012), 'verts')
    out['explicit_1e6'], by = pivot_case((2345678.912, 1234567.891), 'explicit')
    out['faces_1e6'], by = pivot_case((2345678.912, 1234567.891), 'faces')
    out['fbx_readback_1e6'] = pivot_fbx_readback(by)
    return out


for name, fn in (('model_triangulate', model_triangulate), ('ucx_triangulate', ucx_triangulate),
                 ('pivot_place', pivot_place), ('pivot_refusals', pivot_refusals)):
    check(name, fn)
summary['scene_saved'] = bool(str(rt.maxFileName))
(OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding='utf-8')
print('AGR_908A_SUMMARY ' + json.dumps(summary, ensure_ascii=True)[:3000])
assert not summary['errors'] and not summary['scene_saved'], sorted(summary['errors'])
