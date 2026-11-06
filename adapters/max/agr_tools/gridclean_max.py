"""new-case: AGR Tools 1.0 (#1024) grid cleanup, 3ds Max side. owned by branch H (improve/issue-1024-grid-glass).

runtime.edits_100 calls `model_grid_cleanup(ctx, mode, nodes, preview)` for model.grid_cleanup (plan mode `copy`).
ctx: agr (runtime globals), core (gridclean_core), edit (edit_core), emax (edit_max), options (dict of the preview),
host (host_max.MaxHost: ObjRef, user props, one undo record). pymxs is imported inside functions.

Preview reads every node (a plain Editable Poly directly, anything else through a throwaway copy with undo off) and runs
the core on the data: nothing in the scene changes. Apply makes ONE export copy per node (edit_max.export_copies,
layer AGR_export, one undo record, selection restored), rebuilds the copy's polygons from the core result (vertices,
MatID, smoothing groups, map channel 1) and reads it back. No hidden copies, no MAXScript globals (the dump and the
rebuild are block expressions with locals only), metres through units.SystemScale (host.m_per_unit).

`read_poly` / `rebuild` / `world_tm` are shared with glass_max.py (same owner).
"""
import math

TOOL = 'model.grid_cleanup'
SUFFIX = '_AGR_grid_'
EXPORT_LAYER = 'AGR_export'

# Block expression (no globals): node by handle -> text dump of the Editable Poly base object (object space).
_DUMP = r'''(
local o = maxOps.getNodeByHandle HANDLE
local b = o.baseObject
local ss = stringStream ""
local nv = polyop.getNumVerts b
local nf = polyop.getNumFaces b
local hasUV = (polyop.getNumMaps b) > 1 and (polyop.getMapSupport b 1)
format "% % %\n" nv nf (if hasUV then 1 else 0) to:ss
for i = 1 to nv do (
    local p = polyop.getVert b i
    format "% % %\n" (formattedPrint p.x format:".17g") (formattedPrint p.y format:".17g") (formattedPrint p.z format:".17g") to:ss
)
for f = 1 to nf do (
    format "% %|" (polyop.getFaceMatID b f) (polyop.getFaceSmoothGroup b f) to:ss
    for v in (polyop.getFaceVerts b f) do format "% " v to:ss
    format "|" to:ss
    if hasUV do (
        for m in (polyop.getMapFace b 1 f) do (
            local t = polyop.getMapVert b 1 m
            format "% % " (formattedPrint t.x format:".17g") (formattedPrint t.y format:".17g") to:ss
        )
    )
    format "\n" to:ss
)
for v in ((polyop.getVertSelection b) as array) do format "% " v to:ss
format "\n" to:ss
for v in ((polyop.getHiddenVerts b) as array) do format "% " v to:ss
ss as string
)'''

_REBUILD = r'''(
local o = maxOps.getNodeByHandle %(handle)d
convertToMesh o
local vs = #(%(verts)s)
local fs = #(%(faces)s)
local ms = #(%(mats)s)
local sg = #(%(sgs)s)
local ev = #(%(vis)s)
setMesh o vertices:vs faces:fs
for i = 1 to fs.count do (
    setFaceMatID o i ms[i]
    setFaceSmoothGroup o i sg[i]
    setEdgeVis o i 1 ev[i][1]
    setEdgeVis o i 2 ev[i][2]
    setEdgeVis o i 3 ev[i][3]
)
if %(has_uv)s then (
    local uv = #(%(uvs)s)
    local tf = #(%(uvfaces)s)
    meshop.setMapSupport o 1 true
    setNumTVerts o uv.count
    for i = 1 to uv.count do setTVert o i uv[i]
    buildTVFaces o
    for i = 1 to tf.count do setTVFace o i tf[i]
) else (
    meshop.setMapSupport o 1 false
)
update o
convertTo o Editable_Poly
polyop.getNumFaces o
)'''


def _rt():
    from pymxs import runtime
    return runtime


def node_handle(n):
    return int(_rt().getHandleByAnim(n))


def inode_handle(n):
    return int(n.inode.handle)


def targets(nodes):
    """Unique valid nodes in handle order; an empty input is an error (no whole-scene fallback)."""
    rt = _rt()
    if nodes is None:
        nodes = list(rt.selection)
    nodes = list(nodes)
    if not nodes:
        raise ValueError('nothing selected: select the objects to clean (the tool never runs on the whole scene)')
    seen, out = set(), []
    for n in nodes:
        if not rt.isValidNode(n):
            raise ValueError('invalid node')
        h = node_handle(n)
        if h not in seen:
            seen.add(h)
            out.append(n)
    return sorted(out, key=node_handle)


def from_preview(preview):
    rt = _rt()
    nodes = []
    for h in preview['plan']['handles']:
        n = rt.getAnimByHandle(int(h))
        if n is None or not rt.isValidNode(n):
            raise ValueError('a node of the preview is gone; run preview again')
        nodes.append(n)
    return nodes


# ---- transforms (row-vector Max convention: p_world = p_obj * R + t) ----------------------------------------------
def world_tm(n):
    tm = n.objectTransform
    return [[float(r.x), float(r.y), float(r.z)] for r in (tm.row1, tm.row2, tm.row3, tm.row4)]


def to_world(p, tm, k):
    return [(p[0] * tm[0][c] + p[1] * tm[1][c] + p[2] * tm[2][c] + tm[3][c]) * k for c in range(3)]


def inverse_rows(tm):
    """Inverse of the 3x3 part (rows) for world -> object."""
    (a, b, c), (d, e, f), (g, h, i) = tm[0], tm[1], tm[2]
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    if abs(det) < 1e-18:
        raise ValueError('degenerate object transform (zero scale)')
    return [[(e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det],
            [(f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det],
            [(d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det]]


def to_object(p, tm, inv, k):
    q = [p[0] / k - tm[3][0], p[1] / k - tm[3][1], p[2] / k - tm[3][2]]
    return [q[0] * inv[0][c] + q[1] * inv[1][c] + q[2] * inv[2][c] for c in range(3)]


# ---- read ---------------------------------------------------------------------------------------------------------
def parse_dump(text):
    lines = text.split('\n')
    nv, nf, has_uv = (int(x) for x in lines[0].split())
    verts = [[float(c) for c in lines[1 + i].split()] for i in range(nv)]
    faces = []
    for k in range(nf):
        head, vs, uvs = lines[1 + nv + k].split('|')
        mat, sg = (int(x) for x in head.split())
        ring = [int(v) - 1 for v in vs.split()]
        uv = None
        if has_uv:
            nums = [float(x) for x in uvs.split()]
            uv = [[nums[2 * j], nums[2 * j + 1]] for j in range(len(nums) // 2)]
            if len(uv) != len(ring):
                uv = None
        faces.append({'v': ring, 'uv': uv, 'mat': mat, 'sg': sg})
    sel = [int(v) - 1 for v in lines[1 + nv + nf].split()] if len(lines) > 1 + nv + nf else []
    hidden = [int(v) - 1 for v in lines[2 + nv + nf].split()] if len(lines) > 2 + nv + nf else []
    if has_uv and any(f['uv'] is None for f in faces):
        has_uv = 0
        for f in faces:
            f['uv'] = None
    return {'verts': verts, 'faces': faces, 'uv': bool(has_uv)}, sel, hidden


def _plain_poly(n):
    rt = _rt()
    return str(rt.classOf(n.baseObject)) == 'Editable_Poly' and len(n.modifiers) == 0


def read_poly(n, k):
    """(mesh in world metres, vertex selection, hidden verts) of a node; the scene is left as it was."""
    import pymxs
    rt = _rt()
    if _plain_poly(n):
        text = str(rt.execute(_DUMP.replace('HANDLE', str(inode_handle(n)))))
        tm = world_tm(n)
    else:
        with pymxs.undo(False):
            tmp = rt.copy(n)
            try:
                rt.convertTo(tmp, rt.Editable_Poly)
                text = str(rt.execute(_DUMP.replace('HANDLE', str(inode_handle(tmp)))))
                tm = world_tm(tmp)
            finally:
                rt.delete(tmp)
    mesh, sel, hidden = parse_dump(text)
    mesh['verts'] = [to_world(p, tm, k) for p in mesh['verts']]
    return mesh, sel, hidden


def convertible(n):
    rt = _rt()
    return str(rt.superClassOf(n)) == 'GeometryClass' and bool(rt.canConvertTo(n, rt.Editable_Poly))


# ---- rebuild ------------------------------------------------------------------------------------------------------
def _g(x):
    return repr(float(x))


def fan(n):
    """Fan triangles of an n-gon (corner indices) and edge visibility: only the polygon border is visible, so
    convertTo Editable_Poly gives the polygon back (the route of geom_max agr908_setMesh, measured in Max 2024)."""
    out = []
    for i in range(1, n - 1):
        out.append(((0, i, i + 1), (i == 1, True, i == n - 2)))
    return out


def _tri_area(a, b, c):
    u = [b[i] - a[i] for i in range(3)]
    v = [c[i] - a[i] for i in range(3)]
    x = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
    return math.sqrt(sum(t * t for t in x)) / 2.0


def best_start(verts, ring):
    """Fan start corner with the largest smallest triangle: a collinear (T) point of a polygon gives no
    zero-area triangle when the fan starts at it."""
    if len(ring) <= 3:
        return 0
    best, at = -1.0, 0
    for s in range(len(ring)):
        r = ring[s:] + ring[:s]
        m = min(_tri_area(verts[r[0]], verts[r[i]], verts[r[i + 1]]) for i in range(1, len(r) - 1))
        if m > best * (1 + 1e-9):
            best, at = m, s
    return at


def mesh_script(handle, verts_obj, mesh):
    """MAXScript block (locals only) that replaces the geometry of node `handle` (object-space vertices)."""
    tris, mats, sgs, vis, uvfaces = [], [], [], [], []
    uvs, keys = [], {}
    for f in mesh['faces']:
        row = None
        if mesh['uv']:
            row = []
            for t in f['uv']:
                key = (round(float(t[0]), 12), round(float(t[1]), 12))
                if key not in keys:
                    keys[key] = len(uvs) + 1
                    uvs.append(key)
                row.append(keys[key])
        s = best_start(verts_obj, f['v'])
        ring = f['v'][s:] + f['v'][:s]
        if row is not None:
            row = row[s:] + row[:s]
        for corners, ev in fan(len(ring)):
            tris.append([ring[c] + 1 for c in corners])
            mats.append(int(f['mat']))
            sgs.append(int(f['sg']))
            vis.append(ev)
            if row is not None:
                uvfaces.append([row[c] for c in corners])
    b = lambda x: 'true' if x else 'false'  # noqa: E731
    return _REBUILD % {
        'handle': handle,
        'verts': ', '.join('[{}, {}, {}]'.format(_g(p[0]), _g(p[1]), _g(p[2])) for p in verts_obj),
        'faces': ', '.join('[{}, {}, {}]'.format(*t) for t in tris),
        'mats': ', '.join(str(m) for m in mats),
        'sgs': ', '.join(str(s) for s in sgs),
        'vis': ', '.join('#({}, {}, {})'.format(*(b(x) for x in e)) for e in vis),
        'has_uv': b(mesh['uv']),
        'uvs': ', '.join('[{}, {}, 0]'.format(_g(u), _g(v)) for u, v in uvs),
        'uvfaces': ', '.join('[{}, {}, {}]'.format(*t) for t in uvfaces)}


def rebuild(c, mesh, k):
    """Replace the polygons of the COPY c by mesh (world metres). Returns the number of polygons missing after
    the conversion back to Editable Poly (0 = every polygon came back)."""
    rt = _rt()
    tm = world_tm(c)
    inv = inverse_rows(tm)
    verts = [to_object(p, tm, inv, k) for p in mesh['verts']]
    got = int(rt.execute(mesh_script(inode_handle(c), verts, mesh)))
    return max(0, len(mesh['faces']) - got)


def state(emax, nodes, opts):
    return {'nodes': emax.snapshot(nodes), 'options': opts}


# ---- the row ------------------------------------------------------------------------------------------------------
def _weld_selection(opts, sel):
    return sel if opts['t_mode'] == 'weld' and 'tjunctions' in opts['modes'] else None


def model_grid_cleanup(ctx, mode, nodes, preview):
    """Facade grid cleanup on export copies: T-junctions, detriangulation, loops; metres; preview -> apply."""
    edit, emax, core = ctx.edit, ctx.emax, ctx.core
    k = float(ctx.host.m_per_unit())
    if mode == 'preview':
        opts = core.options(ctx.options)
        nodes = targets(nodes)
        rows, objects, done, skipped, ambiguous, work = [], [], [], [], [], []
        for n in nodes:
            name = str(n.name)
            if not convertible(n):
                skipped.append(edit.skipped(name, 'not a geometry object that converts to Editable Poly'))
                continue
            mesh, sel, _ = read_poly(n, k)
            res = core.clean(mesh, opts, _weld_selection(opts, sel))
            if res['skipped']:
                skipped.append(edit.skipped(name, res['skipped']))
                continue
            work.append(n)
            findings = [edit.finding(code, (), detail) for code, detail in core.preview_findings(res['before'], opts)]
            for code, detail in res['findings']:
                ambiguous.append('{}: {} {}'.format(name, code, detail))
            objects.append(edit.entry(node_handle(n), name, findings))
            rows.append({'handle': node_handle(n), 'name': name, 'counts': res['counts'],
                         'faces': [res['before']['faces'], res['after']['faces']],
                         'tris': [res['before']['tris'], res['after']['tris']],
                         't_vertices': [res['before']['t_vertices'], res['after']['t_vertices']]})
            done.append('{}: {}'.format(name, core.plan_counts(res)))
        st = state(emax, work, opts)
        return edit.report(TOOL, 'preview', objects=objects, done=done, skipped_=skipped, ambiguous=ambiguous,
                           state_hash=edit.fingerprint(st),
                           extra={'handles': [r['handle'] for r in rows], 'rows': rows, 'options': opts,
                                  'layer': EXPORT_LAYER, 'm_per_unit': k})
    opts = preview['plan']['options']
    nodes = from_preview(preview)
    edit.require_current(preview, state(emax, nodes, opts))
    rt = _rt()
    objects, done, copies = [], [], []
    ambiguous = list(preview['plan']['ambiguous'])
    with emax.session(TOOL):
        pairs = emax.export_copies(nodes, suffix=SUFFIX, layer=EXPORT_LAYER)
        for (n, c), row in zip(pairs, preview['plan']['rows']):
            rt.convertTo(c, rt.Editable_Poly)
            mesh, sel, _ = read_poly(c, k)
            res = core.clean(mesh, opts, _weld_selection(opts, sel))
            findings = []
            if res['skipped']:
                findings.append(edit.finding('skipped_on_copy', (), res['skipped']))
            else:
                bad = rebuild(c, res['mesh'], k)
                if bad:
                    findings.append(edit.finding('rebuild_failed', (), '{} polygon(s) not created'.format(bad)))
                back, _, _ = read_poly(c, k)
                after = core.stats(back)
                for code, detail in core.verify(res['before'], after, back, _remap_corners(res, back), opts):
                    findings.append(edit.finding(code, (), detail))
                if (after['faces'], after['tris']) != (res['after']['faces'], res['after']['tris']):
                    findings.append(edit.finding('readback', (), 'faces/tris {} / {} expected {} / {}'.format(
                        after['faces'], after['tris'], res['after']['faces'], res['after']['tris'])))
            objects.append(edit.entry(node_handle(c), str(c.name), findings))
            done.append('{} -> {}: {}'.format(row['name'], str(c.name), core.plan_counts(res)) if not findings
                        else '{} -> {}: see findings'.format(row['name'], str(c.name)))
            copies.append({'source': row['name'], 'copy': str(c.name), 'handle': node_handle(c),
                           'counts': res['counts']})
    return edit.report(TOOL, 'apply', objects=objects, done=done, skipped_=preview['plan']['skipped'],
                       ambiguous=ambiguous, extra={'copies': copies, 'layer': EXPORT_LAYER, 'options': opts})


def _remap_corners(res, back):
    """Protected corners of the core result re-indexed on the read-back copy (by position, the rebuild compacts)."""
    out = {}
    pts = back['verts']
    for _, p in res['protected'].items():
        best = min(range(len(pts)), key=lambda i: sum((pts[i][c] - p[c]) ** 2 for c in range(3))) if pts else None
        if best is not None:
            out[best] = p
    return out


def dist(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))
