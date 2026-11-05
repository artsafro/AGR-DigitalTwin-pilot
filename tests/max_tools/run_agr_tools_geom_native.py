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
    # 0.8 acceptance with the 0.8 hull fallback (#979: hull is opt-in, the default reports non-convex pieces)
    pv = agr.edits_080('ucx.triangulate', 'preview', nodes=nodes, options={'nonconvex': 'hull'})
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


# ==== #979 branch E2 ==========================================================================================
geom = agr._load_core('geom_core.py', 'agr_tools_geom_core')
geom_glue = agr._load_core('geom_max.py', 'agr_tools_geom_max')
udim = agr._load_core('udim_core.py', 'agr_tools_udim_core')


def mk_tris(name, pts, polys):
    """Welded closed piece from vertex list + polygons (0-based); each polygon built then welded."""
    node = mkpoly(name, [[P(*pts[i]) for i in poly] for poly in polys])
    rt.polyop.weldVertsByThreshold(node, rt.execute('#all'))
    assert int(rt.polyop.getNumVerts(node)) == len(pts), (name, int(rt.polyop.getNumVerts(node)), len(pts))
    return node


BOX_PTS = [(0, 0, 0), (2, 0, 0), (2, 2, 0), (0, 2, 0), (0, 0, 2), (2, 0, 2), (2, 2, 2), (0, 2, 2)]
BOX_Q = [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]


def valley_piece(name, dz, valley=True, pos=(0, 0, 0)):
    pts = [list(p) for p in BOX_PTS]
    pts[6][2] += dz
    pts = [(p[0] + pos[0], p[1] + pos[1], p[2] + pos[2]) for p in pts]
    tris = []
    for q in BOX_Q[:1] + BOX_Q[2:]:
        a, b, c, d = q
        tris += [[a, b, c], [a, c, d]]
    a, b, c, d = BOX_Q[1]
    tris += [[a, b, d], [b, c, d]] if valley else [[a, b, c], [a, c, d]]
    return mk_tris(name, pts, tris)


def dart_piece(name, pos=(0, 0, 0)):
    """Prism over the plan outline b(0,0) c(2,0) a(2,2) d(2.5,3); lid triangles a-b-c and b-a-d, d lifted."""
    plan = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (2.5, 3.0)]  # b c a d
    top_z = [1.0, 1.0, 1.0, 1.5]
    pts = [(x + pos[0], y + pos[1], pos[2]) for x, y in plan] + \
          [(x + pos[0], y + pos[1], z + pos[2]) for (x, y), z in zip(plan, top_z)]
    b, c, a, d = 4, 5, 6, 7
    polys = [[a, b, c], [b, a, d], [2, 1, 0], [0, 3, 2]]
    for i in range(4):
        j = (i + 1) % 4
        polys.append([i, j, 4 + j, 4 + i])
    return mk_tris(name, pts, polys)


def noisy_piece(name, n=12, noise=0.02, pos=(0, 0, 0)):
    import random
    rnd = random.Random(3)
    m = n + 1
    top = [(i / n * 4.0, j / n * 2.0, 1.0 + rnd.uniform(-noise, noise)) for j in range(m) for i in range(m)]
    pts = top + [(x, y, 0.0) for x, y, _ in top]
    pts = [(x + pos[0], y + pos[1], z + pos[2]) for x, y, z in pts]
    off = len(top)
    polys = []
    for j in range(n):
        for i in range(n):
            a, b, c, d = j * m + i, j * m + i + 1, (j + 1) * m + i + 1, (j + 1) * m + i
            polys += [[a, b, c, d], [off + a, off + d, off + c, off + b]]
    rim = list(range(m)) + [m * k + n for k in range(1, m)] + [n * m + i for i in range(n - 1, -1, -1)] + \
        [m * k for k in range(n - 1, 0, -1)]
    for k in range(len(rim)):
        a, b = rim[k], rim[(k + 1) % len(rim)]
        polys.append([b, a, off + a, off + b])
    return mk_tris(name, pts, polys)


def ucx_979():
    reset()
    valley = valley_piece('UCX_E2_Valley', 0.6)
    ridge = valley_piece('UCX_E2_Ridge', 0.6, valley=False, pos=(5, 0, 0))
    fold = valley_piece('UCX_E2_Fold', 1e-6, pos=(10, 0, 0))
    dart = dart_piece('UCX_E2_Dart', pos=(15, 0, 0))
    noisy = noisy_piece('UCX_E2_Noisy', pos=(20, 0, 0))
    stack = valley_piece('UCX_E2_Stack', 0.6, pos=(30, 0, 0))
    rt.addModifier(stack, rt.Edit_Poly())
    nodes = [valley, ridge, fold, dart, noisy, stack]
    before = emax.snapshot(nodes)
    mods_before = int(stack.modifiers.count)
    pv = agr.edits_080('ucx.triangulate', 'preview', nodes=nodes)
    rows = {r['name']: r for r in pv['plan']['rows']}
    codes = {o['name']: sorted(f['code'] for f in o['findings']) for o in pv['objects']}
    assert emax.snapshot(nodes) == before, 'preview changed the scene'
    assert rows['UCX_E2_Valley']['flips'] == 1 and rows['UCX_E2_Valley']['convex'], rows['UCX_E2_Valley']
    assert rows['UCX_E2_Ridge']['action'] == 'none' and rows['UCX_E2_Ridge']['flips'] == 0
    assert rows['UCX_E2_Fold']['action'] == 'none' and rows['UCX_E2_Fold']['flips'] == 0, rows['UCX_E2_Fold']
    assert rows['UCX_E2_Dart']['flips'] == 0 and not rows['UCX_E2_Dart']['convex']
    assert 'dart' in {r['reason'] for r in rows['UCX_E2_Dart']['refused']}, rows['UCX_E2_Dart']['refused']
    assert any('UCX_E2_Dart' in a for a in pv['plan']['ambiguous'])
    assert codes['UCX_E2_Valley'] == ['reflex_edge'] and codes['UCX_E2_Dart'] == ['not_convex'], codes
    assert codes['UCX_E2_Ridge'] == [] and codes['UCX_E2_Fold'] == [], codes
    ap = agr.edits_080('ucx.triangulate', 'apply', pv)
    assert emax.snapshot(nodes) == before, 'working UCX changed'
    assert int(stack.modifiers.count) == mods_before, 'source stack collapsed'
    out = {'preview_codes': codes, 'pieces': {}}
    for c in ap['plan']['copies']:
        node = rt.getNodeByName(c['copy'])
        st = stats(node)
        quads = sum(1 for d in st['deg'] if d > 3)
        assert quads == 0, (c['copy'], quads)
        assert c['verts_after'] == c['verts_before'], c
        out['pieces'][c['source']] = {'action': c['action'], 'flips': c['flips'], 'rebuilt': c['rebuilt'],
                                      'convex': c['check'] and c['check']['convex'], 'quads': quads,
                                      'refused': len(c['refused']), 'faces': len(st['deg'])}
    p = out['pieces']
    assert p['UCX_E2_Valley']['convex'] and p['UCX_E2_Valley']['flips'] == 1
    assert p['UCX_E2_Stack']['convex'] and p['UCX_E2_Stack']['flips'] == 1
    assert p['UCX_E2_Fold']['flips'] == 0 and p['UCX_E2_Ridge']['convex']
    assert p['UCX_E2_Dart']['flips'] == 0 and not p['UCX_E2_Dart']['convex']
    assert p['UCX_E2_Noisy']['quads'] == 0 and p['UCX_E2_Noisy']['flips'] > 0
    # the copy of the fold keeps exactly the source triangles
    fold_copy = rt.getNodeByName([c['copy'] for c in ap['plan']['copies'] if c['source'] == 'UCX_E2_Fold'][0])
    assert geom_glue.poly_data(fold_copy.baseObject)[1] == geom_glue.poly_data(fold.baseObject)[1]
    return out


# ---- export.pivot_place: axes (L07 acceptance) -----------------------------------------------------------
SCENES = {'m_zero': ('meters', 1.0, (0.0, 0.0)), 'cm': ('centimeters', 100.0, (234567800.0, 123456700.0)),
          'm_far': ('meters', 1.0, (2345678.0, 1234567.0))}


def reset_units(system):
    rt.resetMaxFile(rt.name('noPrompt'))
    rt.units.SystemType = rt.name(system)
    rt.units.SystemScale = 1.0


def cell_node(name, angle, unit, xy, size=(4.0, 1.0, 0.5), segs=(8, 2, 1)):
    """L07 cell: box 4 x 1 x 0.5 m (x unit), rotation baked into the mesh, node at the far X/Y, no node rotation."""
    b = rt.Box(name=name, width=size[0] * unit, length=size[1] * unit, height=size[2] * unit,
               widthsegs=segs[0], lengthsegs=segs[1], heightsegs=segs[2])
    rt.convertTo(b, rt.Editable_Poly)
    a = math.radians(angle)
    for v in range(1, int(rt.polyop.getNumVerts(b)) + 1):
        p = rt.polyop.getVert(b.baseObject, v)
        x, y = float(p.x), float(p.y)
        rt.polyop.setVert(b.baseObject, v, P(x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a),
                                             float(p.z)))
    b.pos = P(xy[0], xy[1], 0.0)
    return b


def world_double(n):
    node_rows, off_rows, pts = geom_glue.read_frame(n)
    return geom.world_points(pts, off_rows, node_rows)


def x_angle(n):
    r = n.transform.row1
    return math.degrees(math.atan2(float(r.y), float(r.x)))


PIVOT_OPTS = {'orient': 'long_side', 'pivot_at': 'bottom_centre', 'target': 'npm'}


def pivot_cells():
    import pymxs
    out = {}
    for scene, (system, unit, xy) in SCENES.items():
        reset_units(system)
        with pymxs.undo(False):
            nodes = [cell_node('SM_Cell_%d' % a, a, unit, (xy[0] + 10 * unit * i, xy[1])) for i, a in
                     enumerate((17, 45, 89, 135))]
        rt.clearUndoBuffer()
        before = emax.snapshot(nodes)
        world_before = {str(n.name): world_double(n) for n in nodes}
        hash_before = {str(n.name): emax.mesh_hash(n) for n in nodes}
        pv = agr.edits_080('export.pivot_place', 'preview', nodes=nodes, options=PIVOT_OPTS)
        assert pv['status'] == 'pass', pv['objects']
        assert emax.snapshot(nodes) == before, 'dry-run (preview) changed the scene'
        ap = agr.edits_080('export.pivot_place', 'apply', pv)
        assert ap['status'] == 'pass', ap['objects']
        assert emax.snapshot(nodes) == before, 'working objects changed'
        res = {}
        for c in ap['plan']['copies']:
            node = [n for n in rt.objects if int(rt.getHandleByAnim(n)) == c['handle']][0]
            ang = int(c['source'].split('_')[-1])
            err = abs(geom.canonical_angle(x_angle(node)) - ang)
            err = min(err, 180 - err)
            drift = max(math.dist(a, b) for a, b in zip(world_double(node), world_before[c['source']]))
            z = node.transform.row3
            same_hash = emax.mesh_hash(node) == hash_before[c['source']]
            res[ang] = {'axis_err_deg': err, 'drift': drift, 'z_up': [float(z.x), float(z.y), float(z.z)],
                        'world_hash_same': same_hash, 'pivot': c['pivot']}
            assert err <= 0.01, (scene, ang, err)
            assert drift <= 1e-4, (scene, ang, drift)  # system units (m or cm)
            assert abs(float(z.z) - 1.0) < 1e-6, (scene, ang, res[ang]['z_up'])
        # one undo record returns every transform: the copies disappear, the working nodes are as before
        count = len(rt.objects)
        rt.execute('max undo')
        res['undo'] = {'objects_before': count, 'objects_after': len(rt.objects)}
        assert len(rt.objects) == count - 4, res['undo']
        assert emax.snapshot(nodes) == before
        out[scene] = res
    return out


def pivot_doors_and_limits():
    reset_units('meters')
    far = (2345678.912, 1234567.891)
    door = rt.Box(name='SM_Door', width=0.9, length=0.05, height=2.1)
    rt.convertTo(door, rt.Editable_Poly)
    rt.rotate(door, rt.EulerAngles(0, 0, 30))
    door.pos = P(far[0], far[1], 150.0)
    parent = rt.Dummy(name='Frame_Parent', pos=P(far[0] + 5, far[1], 150.0))
    rt.rotate(parent, rt.EulerAngles(0, 0, 15))
    kid = rt.Box(name='SM_Door_Child', width=0.9, length=0.05, height=2.1)
    rt.convertTo(kid, rt.Editable_Poly)
    kid.parent = parent
    kid.transform = rt.Matrix3(1) * rt.rotateZMatrix(45) * rt.transMatrix(P(far[0] + 5, far[1] + 1, 150.0))
    mesh = rt.Box(name='SM_Door_Mesh', width=0.9, length=0.05, height=2.1)
    rt.convertToMesh(mesh)
    rt.rotate(mesh, rt.EulerAngles(0, 0, 60))
    mesh.pos = P(far[0] + 10, far[1], 150.0)
    big = cell_node('SM_Cell_5000', 17, 1.0, (far[0] + 20, far[1]), segs=(80, 20, 9))
    nodes = [door, kid, mesh, big]
    nverts = int(rt.polyop.getNumVerts(big))
    t0 = time.perf_counter()
    node_rows, off_rows, pts = geom_glue.read_frame(big)
    t_read = time.perf_counter() - t0
    t0 = time.perf_counter()
    geom.axes_long_side(pts, geom.mat3_mul(off_rows[:3], node_rows[:3]))
    t_axes = time.perf_counter() - t0
    t0 = time.perf_counter()
    emax.snapshot([big])
    t_snap = time.perf_counter() - t0
    t0 = time.perf_counter()
    pv_big = agr.edits_080('export.pivot_place', 'preview', nodes=[big], options=PIVOT_OPTS)
    t_big = time.perf_counter() - t0
    timing = {'read_frame_s': round(t_read, 3), 'axes_s': round(t_axes, 3), 'snapshot_s': round(t_snap, 3),
              'preview_s': round(t_big, 3), 'vertices': nverts}
    import glob
    import tempfile
    timing['temp_left'] = len(glob.glob(os.path.join(tempfile.gettempdir(), 'agr979_*.bin')))
    summary.setdefault('timing_5000', timing)
    assert timing['temp_left'] == 0, timing
    assert pv_big['status'] == 'pass' and nverts >= 5000 and t_big < 2.0, timing
    t_prev = t_big
    before = emax.snapshot(nodes)
    parent_tm = emax.snapshot([parent])
    world_before = {str(n.name): world_double(n) for n in nodes}
    expect = {str(n.name): geom.canonical_angle(x_angle(n)) for n in (door, kid, mesh)}
    expect['SM_Cell_5000'] = 17.0
    pv = agr.edits_080('export.pivot_place', 'preview', nodes=nodes, options=PIVOT_OPTS)
    assert pv['status'] == 'pass', (pv['objects'], pv['plan']['skipped'])
    ap = agr.edits_080('export.pivot_place', 'apply', pv)
    assert ap['status'] == 'pass', ap['objects']
    assert emax.snapshot(nodes) == before and emax.snapshot([parent]) == parent_tm
    out = {'preview_s_5000': round(t_prev, 3), 'vertices_big': nverts, 'copies': {}, 'expect': expect}
    for c in ap['plan']['copies']:
        node = [n for n in rt.objects if int(rt.getHandleByAnim(n)) == c['handle']][0]
        err = abs(geom.canonical_angle(x_angle(node)) - expect[c['source']])
        err = min(err, 180 - err)
        drift = max(math.dist(a, b) for a, b in zip(world_double(node), world_before[c['source']]))
        zmin = min(p[2] for p in world_before[c['source']])
        piv_z = float(node.transform.row4.z)
        out['copies'][c['source']] = {'axis_err_deg': err, 'drift': drift, 'pivot_z': piv_z, 'bottom_z': zmin,
                                      'class': str(rt.classOf(node.baseObject)),
                                      'parent': str(node.parent.name) if node.parent else None}
        assert err <= 0.01 and drift <= 1e-4, (c['source'], err, drift)
        assert abs(piv_z - zmin) <= 1e-3 + ulp32(150.0), (c['source'], piv_z, zmin)
    # refusals: square cell and a scaled node -> listed with the exact reason, transform untouched
    sq = cell_node('SM_Square', 30, 1.0, (far[0] + 40, far[1]), size=(1.0, 1.0, 0.5))
    sc = cell_node('SM_Scaled', 30, 1.0, (far[0] + 50, far[1]))
    sc.scale = P(2, 1, 1)
    ref_before = emax.snapshot([sq, sc])
    count = len(rt.objects)
    pv2 = agr.edits_080('export.pivot_place', 'preview', nodes=[sq, sc, door], options=PIVOT_OPTS)
    reasons = {s['item']: s['reason'] for s in pv2['plan']['skipped']}
    codes = {o['name']: [f['code'] for f in o['findings']] for o in pv2['objects']}
    assert 'square or degenerate footprint' in reasons['SM_Square'], reasons
    assert 'node scale' in reasons['SM_Scaled'], reasons
    assert codes['SM_Square'] == ['pivot_axis_undefined'] and codes['SM_Scaled'] == ['pivot_node_scale'], codes
    agr.edits_080('export.pivot_place', 'apply', pv2)
    assert emax.snapshot([sq, sc]) == ref_before and len(rt.objects) == count + 1
    out['refusals'] = reasons
    return out


# ---- udim.ids_to_udims (keep layout, stacks, 5000 faces) ---------------------------------------------------
def udim_979():
    import random
    reset()
    plane = rt.Plane(name='SM_Udim5000', length=50, width=50, lengthsegs=50, widthsegs=50, mapcoords=True)
    rt.convertToMesh(plane)
    rnd = random.Random(7)
    nf = int(plane.numfaces)
    for f in range(1, nf + 1, 2):
        mid = rnd.randint(1, 100)
        rt.setFaceMatID(plane, f, mid)
        rt.setFaceMatID(plane, f + 1, mid)
    rt.update(plane)
    stack = rt.Plane(name='SM_UdimStack', length=4, width=4, lengthsegs=4, widthsegs=4, mapcoords=True,
                     pos=P(60, 0, 0))
    rt.convertTo(stack, rt.Editable_Poly)
    for f in range(1, 17):
        rt.polyop.setFaceMatID(stack, f, 1 + (f - 1) % 4 if f != 16 else 101)
    rt.addModifier(stack, rt.Unwrap_UVW())
    rt.addModifier(stack, rt.UVW_Xform(U_Offset=-1.5, V_Offset=-0.25))
    nodes = [plane, stack]
    before = emax.snapshot(nodes)
    umax = agr._load_core('udim_max.py', 'agr_tools_udim_max')

    class Ctx:
        pass
    ctx = Ctx()
    ctx.agr = agr
    eval_before = {str(n.name): umax._read_eval(ctx, n) for n in nodes}
    pv = agr.edits_080('udim.ids_to_udims', 'preview', nodes=nodes, options={'mode': 'keep'})
    codes = {o['name']: sorted({f['code'] for f in o['findings']}) for o in pv['objects']}
    assert codes == {'SM_Udim5000': [], 'SM_UdimStack': ['udim_id_out_of_range']}, codes
    rt.select(nodes)  # apply re-reads the selection, as the panel does
    ap = agr.edits_080('udim.ids_to_udims', 'apply', pv)
    assert emax.snapshot(nodes) == before and int(stack.modifiers.count) == 2, 'working objects changed'
    out = {'nf_plane': nf}
    for name in ap['plan']['copies']:
        c = rt.getNodeByName(name)
        back = agr._read_channel(c)
        src = eval_before[name.split('_AGR_export_')[0]]
        ids = udim.ids_from_tiles(back['uvs'], back['face_uvs'])
        ok = sum(1 for a, b in zip(ids, back['ids']) if a == b)
        placed = [i for i, m in enumerate(back['ids']) if 1 <= m <= 100]
        kept = True
        for f in range(len(back['ids'])):  # every face moved by whole tiles from the EVALUATED source UVs
            d = {(round(float(back['uvs'][j][0]) - float(src['uvs'][k][0]), 5),
                  round(float(back['uvs'][j][1]) - float(src['uvs'][k][1]), 5))
                 for j, k in zip(back['face_uvs'][f], src['face_uvs'][f])}
            if len(d) != 1 or any(abs(x - round(x)) > 1e-5 for x in next(iter(d))):
                kept = False
        out[name] = {'faces': len(back['ids']), 'round_trip_ok': ok, 'placed': len(placed), 'layout_kept': kept,
                     'modifiers_on_copy': int(c.modifiers.count)}
        assert ok == len(placed) and kept, out[name]
    assert any(v['faces'] == 5000 and v['round_trip_ok'] == 5000 for k, v in out.items() if isinstance(v, dict))
    return out


for name, fn in (('model_triangulate', model_triangulate), ('ucx_triangulate', ucx_triangulate),
                 ('pivot_place', pivot_place), ('pivot_refusals', pivot_refusals),
                 ('e2_ucx', ucx_979), ('e2_pivot_cells', pivot_cells), ('e2_pivot_doors', pivot_doors_and_limits),
                 ('e2_udim', udim_979)):
    if os.environ.get('AGR_E2_ONLY') and not name.startswith('e2_'):
        continue
    check(name, fn)
summary['scene_saved'] = bool(str(rt.maxFileName))
(OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding='utf-8')
print('AGR_908A_SUMMARY ' + json.dumps(summary, ensure_ascii=True)[:3000])
assert not summary['errors'] and not summary['scene_saved'], sorted(summary['errors'])
