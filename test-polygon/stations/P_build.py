"""new-case: polygon fragment builder of branch P (#1024): npm.build (1.0.22), atlas.facade_strip (1.0.23).

Pure generators (no pymxs; loaded by path by tests/max_tools/test_agr_tools_npm.py and the native run) plus
`make(obj, rt) -> node` for build/build_scene.py. Synthetic only (IMPL.md):
* vpm_meshes(): the VPM of the small L09 facade (test-polygon/stations/M_build.py) through vpm_core.build of branch
  M - body (panels id 3 -> UDIM 1001, brick id 7 -> 1002, K6 pieces) and glass (id 31 -> 1001), world metres;
* strip_facade(): a facade of 4 repeating strips (ids 101-104, periods PERIODS, several separate wall pieces per id,
  two of them side by side on one plane) and 2 unique panels (ids 201, 202, own UV 0..1).
Mesh dict: {'key', 'name', 'part', 'verts', 'tris', 'mat_ids', 'uvs', 'uv_tris', 'materials'}.
"""
import importlib.util
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PERIODS = {'101': [1.2, 0.6], '102': [0.6, 1.2], '103': [0.6, 1.2], '104': [1.2, 1.2]}
STRIP_MAPS = {101: 's0.png', 102: 's1.png', 103: 's2.png', 104: 's3.png', 201: 'u1.png', 202: 'u2.png'}


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def vpm_meshes(name='SM_PolygonNpm_Main'):
    mb = _load(os.path.join(HERE, 'M_build.py'), 'agr_polygon_M_build_for_P')
    vpm = _load(os.path.join(HERE, '..', '..', 'adapters', 'max', 'agr_tools', 'vpm_core.py'), 'agr_vpm_core_for_P')
    small = [(0.0, 0.0), (3.6, 0.0), (3.6, 3.6), (0.0, 3.6)]
    tm, _ = mb.triangulate(mb.facade(height=6.0, footprint=small, brick_from=3.0))
    plan = vpm.build([dict(tm, key=1, name=name)], {'glass_ids': [31]})
    out = []
    for p in plan['objects'][0]['parts']:
        g = p['geometry']
        verts = [[sum(w * tm['verts'][v][j] for v, w in ws) for j in range(3)] for ws in g['verts_w']]
        out.append({'key': len(out) + 1, 'name': p['name'], 'part': p['summary']['part'], 'verts': verts,
                    'tris': [list(t) for t in g['tris']], 'mat_ids': list(g['mat_ids']), 'uvs': g['uvs'],
                    'uv_tris': [list(t) for t in g['uv_tris']], 'udim_table': p['summary']['udim_table']})
    return out


class _B:
    def __init__(self):
        self.verts, self.tris, self.ids, self.uvs, self.uv_tris = [], [], [], [], []

    def quad(self, pts, mid, uv=None):
        """A quad with its OWN vertices (separate wall pieces stay separate regions)."""
        base = len(self.verts)
        self.verts.extend([list(p) for p in pts])
        ub = len(self.uvs)
        self.uvs.extend(uv or [[p[0] + p[1], p[2]] for p in pts])
        for a, b, c in ((0, 1, 2), (0, 2, 3)):
            self.tris.append([base + a, base + b, base + c])
            self.uv_tris.append([ub + a, ub + b, ub + c])
            self.ids.append(mid)


def strip_facade(name='SM_PolygonStrip_Main'):
    """9 x 6 m box facade: bands 101 (0-1.2 m), 102 (1.2-3.6), 103 (3.6-4.8), 104 (4.8-6) on the four walls; the
    front wall is cut at x = 4.5 into two pieces of every band; 2 unique panels (201, 202) 0.05 m in front."""
    b = _B()
    W, D = 9.0, 6.0
    bands = [(0.0, 1.2, 101), (1.2, 3.6, 102), (3.6, 4.8, 103), (4.8, 6.0, 104)]
    walls = [((0, 0), (4.5, 0)), ((4.5, 0), (W, 0)), ((W, 0), (W, D)), ((W, D), (0, D)), ((0, D), (0, 0))]
    for (ax, ay), (bx, by) in walls:
        for z0, z1, mid in bands:
            b.quad([(ax, ay, z0), (bx, by, z0), (bx, by, z1), (ax, ay, z1)], mid)
    for x0, mid in ((1.0, 201), (6.0, 202)):
        b.quad([(x0, -0.05, 1.5), (x0 + 1.0, -0.05, 1.5), (x0 + 1.0, -0.05, 2.5), (x0, -0.05, 2.5)], mid,
               uv=[[0, 0], [1, 0], [1, 1], [0, 1]])
    mats = {k: {'name': 'M_Strip_{}'.format(k), 'map': v} for k, v in STRIP_MAPS.items()}
    return {'key': 1, 'name': name, 'part': 'body', 'verts': b.verts, 'tris': b.tris, 'mat_ids': b.ids,
            'uvs': b.uvs, 'uv_tris': b.uv_tris, 'materials': mats}


# ---- polygon stations (3ds Max) --------------------------------------------------------------------------------
def make(obj, rt):
    """Editable_Mesh node of a station object: extra.kind npm_vpm (VPM body, colour plugs) | npm_vpm_nomap (brick
    map file missing) | strip (strip facade, colour plugs) | strip_nomap (one strip map missing). Metres written in
    system units (units.SystemScale); `pos` of the polygon layout moves the node."""
    extra = obj.get('extra') or {}
    kind = extra.get('kind', 'npm_vpm')
    if kind.startswith('npm_vpm'):
        mesh = vpm_meshes(obj['name'])[0]
        mats = {3: ('M_Panel', (180, 170, 150), None), 7: ('M_Brick', (150, 70, 50), None)}
    else:
        mesh = strip_facade(obj['name'])
        mats = {k: ('M_Strip_{}'.format(k), (60 + k % 100 * 30, 90, 120), None) for k in STRIP_MAPS}
    if kind.endswith('_nomap'):
        key = 7 if kind.startswith('npm_vpm') else 103
        mats[key] = (mats[key][0], mats[key][1], os.path.join(HERE, '_missing_P_station_map.png'))
    node = build_node(rt, mesh, obj['name'])
    node.material = material(rt, obj['name'], mats)
    if obj.get('pos'):
        k = 1.0 / _m_per_unit(rt)
        node.position = rt.point3(*[float(c) * k for c in obj['pos']])
    return node


def material(rt, name, mats):
    """Multi/Sub by library id: Standard materials with a diffuse colour or a Bitmaptexture file."""
    ids = sorted(mats)
    mm = rt.MultiMaterial(numsubs=len(ids))
    mm.name = 'M_' + name
    for i, mid in enumerate(ids):
        label, colour, path = mats[mid]
        sub = rt.StandardMaterial(name=label)
        sub.diffuse = rt.color(*colour)
        if path:
            sub.diffuseMap = rt.Bitmaptexture(filename=path)
        mm.materialList[i] = sub
        mm.materialIDList[i] = mid
    return mm


def build_node(rt, mesh, name):
    k = 1.0 / _m_per_unit(rt)
    node = rt.mesh(numverts=len(mesh['verts']), numfaces=len(mesh['tris']))
    for i, p in enumerate(mesh['verts'], 1):
        rt.setVert(node, i, rt.point3(p[0] * k, p[1] * k, p[2] * k))
    for f, (t, mid) in enumerate(zip(mesh['tris'], mesh['mat_ids']), 1):
        rt.setFace(node, f, t[0] + 1, t[1] + 1, t[2] + 1)
        rt.setFaceMatID(node, f, mid)
    rt.meshop.setMapSupport(node, 1, True)
    rt.meshop.setNumMapVerts(node, 1, len(mesh['uvs']))
    for i, (u, v) in enumerate(mesh['uvs'], 1):
        rt.meshop.setMapVert(node, 1, i, rt.point3(float(u), float(v), 0.0))
    for f, t in enumerate(mesh['uv_tris'], 1):
        rt.meshop.setMapFace(node, 1, f, rt.point3(t[0] + 1, t[1] + 1, t[2] + 1))
    rt.update(node)
    node.name = name
    return node


def _m_per_unit(rt):
    per = {'millimeters': 0.001, 'centimeters': 0.01, 'meters': 1.0, 'kilometers': 1000.0, 'inches': 0.0254,
           'feet': 0.3048, 'miles': 1609.344}
    return per[str(rt.units.SystemType).lower().lstrip('#')] * float(rt.units.SystemScale)
