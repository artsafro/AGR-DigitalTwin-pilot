"""new-case: polygon fragment builder of branch Q (#1024): npm.to_vpm (1.0.24), udim.udims_to_ids (1.0.25).

Pure generators (no pymxs; loaded by path by tests/max_tools/test_agr_tools_npm_to_vpm.py and the native run) plus
`make(obj, rt) -> node` for build/build_scene.py. Synthetic only (IMPL.md):
* vpm(): the VPM of the small L09 facade through vpm_core.build of branch M (P_build.vpm_meshes): body ids 3 / 7 in
  UDIM 1001 / 1002, glass id 31 in its own mesh at 1001;
* npm(): that VPM through npm_core.plan of branch P (one NPM mesh, body then glass, atlas UV) and its
  correspondence table; window planes on WINDOW_ID are added after the atlas faces;
* window_planes(): lab L11 set - 4 x KPP1-W01, 4 x KPP1-W02, 4 x KPP1-W03 on 5 walls (one at 17 deg; planes of 2, 4
  or 6 triangles), size noise up to 4 mm, + KPP1-W03 turned 90 deg in its plane, + 1.5 x 1.5 m without a type;
* udim_plane(): a plane with faces in UDIM 1001, 1002, 1011 (+ U = -0.5 and U = 10.2 for the FAIL row).
Mesh dict: {'key', 'name', 'verts' (m), 'local' (= verts), 'tris', 'mat_ids', 'uvs', 'uv_tris'}.
"""
import importlib.util
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
WINDOW_ID = 50
NO_ROW_ID = 9
KPP1 = {'KPP1-W01': (1.18, 1.8), 'KPP1-W02': (1.18, 5.45), 'KPP1-W03': (2.0, 1.8)}
COLOURS = {3: (180, 170, 150), 7: (150, 70, 50), 31: (70, 90, 110)}


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _core(name):
    return _load(os.path.join(ROOT, 'adapters', 'max', 'agr_tools', name), 'agr_q_build_' + name[:-3])


def vpm(name='SM_PolygonN2V_Main'):
    pb = _load(os.path.join(HERE, 'P_build.py'), 'agr_polygon_P_build_for_Q')
    return pb.vpm_meshes(name)


def npm(name='SM_PolygonN2V_Main', layout='stack', maps=None):
    """(NPM mesh, table rows, npm_core plan) of the VPM of vpm(): materials are colour plugs unless `maps` gives
    {library id: (path, w, h)} (texture rows, for the native run)."""
    nc = _core('npm_core.py')
    meshes = vpm(name)
    for m in meshes:
        m['materials'] = {}
        for mid in sorted(set(m['mat_ids'])):
            spec = {'name': 'M_lib_{}'.format(mid), 'map': None, 'color': list(COLOURS.get(mid, (128, 128, 128)))}
            if maps and mid in maps:
                spec['map'] = maps[mid][0]
            m['materials'][mid] = spec
    info = {v[0]: {'w': v[1], 'h': v[2]} for v in (maps or {}).values()}
    udim = {}
    for m in meshes:
        udim.update({str(k): v for k, v in m['udim_table'].items()})
    p = nc.plan(meshes, {'layout': layout, 'udim_table': udim, 'glass_ids': [31]}, info)
    if p['findings']:
        raise ValueError('npm.build plan of the polygon VPM failed: {}'.format(p['findings']))
    cm = p['combined']
    mesh = {'key': 1, 'name': name, 'verts': [list(v) for v in cm['verts']], 'tris': [list(t) for t in cm['tris']],
            'mat_ids': list(cm['mat_ids']), 'uvs': [list(u) for u in p['uvs']],
            'uv_tris': [list(t) for t in p['uv_tris']]}
    mesh['local'] = mesh['verts']
    return mesh, p['table'], p


def _rnd(seed):
    """Deterministic noise in [-1, 1] (no `random` state shared with the caller)."""
    x = math.sin(seed * 12.9898 + 78.233) * 43758.5453
    return 2.0 * (x - math.floor(x)) - 1.0


def window_planes(noise=0.004, rotated=True, untyped=True):
    """[{'type', 'rotated', 'w', 'h', 'centre', 'normal', 'quad': [4 points], 'split': 1|2|3}] (metres)."""
    walls = [((0.0, -1.0, 0.0), (1.0, 0.0, 0.0)), ((20.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
             ((20.0, 12.0, 0.0), (-1.0, 0.0, 0.0)), ((0.0, 12.0, 0.0), (0.0, -1.0, 0.0))]
    a = math.radians(17.0)
    walls.append(((-1.0, 6.0, 0.0), (math.sin(a), -math.cos(a), 0.0)))  # wall turned 17 deg, normal (-cos, -sin)
    order = ['KPP1-W01'] * 4 + ['KPP1-W02'] * 4 + ['KPP1-W03'] * 4
    out = []
    for i, tid in enumerate(order):
        W, H = KPP1[tid]
        out.append({'type': tid, 'rotated': False, 'w': W + noise * _rnd(i * 2 + 1), 'h': H + noise * _rnd(i * 2 + 2),
                    'wall': i % 5, 'along': 1.5 + 3.2 * (i // 5), 'z': 1.0 + 0.4 * (i % 3), 'split': 1 + i % 3})
    if rotated:
        W, H = KPP1['KPP1-W03']
        out.append({'type': 'KPP1-W03', 'rotated': True, 'w': H + noise * _rnd(91), 'h': W + noise * _rnd(92),
                    'wall': 1, 'along': 11.0, 'z': 1.0, 'split': 2})
    if untyped:
        out.append({'type': None, 'rotated': False, 'w': 1.5, 'h': 1.5, 'wall': 3, 'along': 11.0, 'z': 1.0,
                    'split': 1})
    for p in out:
        (ox, oy, oz), (dx, dy, dz) = walls[p['wall']]
        normal = (dy, -dx, 0.0)  # the street side: right-handed with the wall direction and up
        x0 = [ox + dx * p['along'], oy + dy * p['along'], p['z']]
        q = [[x0[0], x0[1], x0[2]], [x0[0] + dx * p['w'], x0[1] + dy * p['w'], x0[2]],
             [x0[0] + dx * p['w'], x0[1] + dy * p['w'], x0[2] + p['h']], [x0[0], x0[1], x0[2] + p['h']]]
        p['quad'] = q
        p['normal'] = list(normal)
        p['centre'] = [x0[0] + dx * p['w'] / 2.0, x0[1] + dy * p['w'] / 2.0, x0[2] + p['h'] / 2.0]
    return out


def add_planes(mesh, planes, mid=WINDOW_ID):
    """Window planes appended to a mesh (own vertices; split into `split` strips of 2 triangles; atlas UV 0)."""
    for p in planes:
        a, b, c, d = p['quad']
        n = p['split']
        cols = []
        for k in range(n + 1):
            t = k / float(n)
            cols.append(([a[j] + (b[j] - a[j]) * t for j in range(3)], [d[j] + (c[j] - d[j]) * t for j in range(3)]))
        for k in range(n):
            (p0, p3), (p1, p2) = cols[k], cols[k + 1]
            base = len(mesh['verts'])
            mesh['verts'].extend([list(p0), list(p1), list(p2), list(p3)])
            ub = len(mesh['uvs'])
            mesh['uvs'].extend([[0.001, 0.001], [0.002, 0.001], [0.002, 0.002], [0.001, 0.002]])
            for t in ((0, 1, 2), (0, 2, 3)):
                mesh['tris'].append([base + t[0], base + t[1], base + t[2]])
                mesh['uv_tris'].append([ub + t[0], ub + t[1], ub + t[2]])
                mesh['mat_ids'].append(mid)
    mesh['local'] = mesh['verts']
    return mesh


def add_no_row_quad(mesh, mid=NO_ROW_ID):
    base = len(mesh['verts'])
    mesh['verts'].extend([[0, -0.5, 0], [1, -0.5, 0], [1, -0.5, 1], [0, -0.5, 1]])
    ub = len(mesh['uvs'])
    mesh['uvs'].extend([[0.9, 0.9], [0.95, 0.9], [0.95, 0.95], [0.9, 0.95]])
    for t in ((0, 1, 2), (0, 2, 3)):
        mesh['tris'].append([base + t[0], base + t[1], base + t[2]])
        mesh['uv_tris'].append([ub + t[0], ub + t[1], ub + t[2]])
        mesh['mat_ids'].append(mid)
    mesh['local'] = mesh['verts']
    return mesh


def station_npm(name, kind):
    """NPM of a station row: `ok` (12 KPP1 planes + the 90 deg one) | `fail` (+ the untyped plane + id 9 without a
    row)."""
    mesh, _rows, _p = npm(name)
    planes = window_planes(rotated=True, untyped=(kind == 'fail'))
    add_planes(mesh, planes)
    if kind == 'fail':
        add_no_row_quad(mesh)
    return mesh


def station_options():
    """Options of the npm.to_vpm station (written into Q.json; a unit test keeps them equal)."""
    _mesh, rows, _p = npm('SM_PolygonN2V_Main')
    return {'table': {'table': rows}, 'window_ids': [WINDOW_ID], 'window_types': sorted(KPP1)}


ATLAS_CELLS = {2: (0.02, 0.05, 0.31, 0.22), 5: (1.35, 0.30, 1.60, 0.71), 9: (0.62, 0.40, 0.70, 0.90),
               12: (0.80, 0.0, 1.0, 0.16)}


def atlas_npm(name='SM_PolygonUnatlas_Main'):
    """NPM without a table (lab L11 case B): ids 2, 5, 9, 12 in atlas cells, two overlapping islands per id (a
    stack); id 12 at the atlas edge; id 5 in the atlas tile (1, 0) - outside the first UDIM."""
    m = {'key': 1, 'name': name, 'verts': [], 'tris': [], 'mat_ids': [], 'uvs': [], 'uv_tris': []}
    for mid, (u0, v0, u1, v1) in sorted(ATLAS_CELLS.items()):
        for k, (a, b) in enumerate(((0.0, 1.0), (0.2, 0.9))):
            base = len(m['verts'])
            m['verts'].extend([[mid, k, 0], [mid + 1, k, 0], [mid + 1, k, 1], [mid, k, 1]])
            uu0, uu1 = u0 + (u1 - u0) * a, u0 + (u1 - u0) * b
            m['uvs'].extend([[uu0, v0], [uu1, v0], [uu1, v1], [uu0, v1]])
            for t in ((0, 1, 2), (0, 2, 3)):
                m['tris'].append([base + t[0], base + t[1], base + t[2]])
                m['uv_tris'].append([base + t[0], base + t[1], base + t[2]])
                m['mat_ids'].append(mid)
    m['local'] = m['verts']
    return m


def coord16_png(w, h):
    """16-bit RGB PNG: R = 32 * x + 16, G = 32 * y + 16 (the pixel tells its atlas coordinate), B = 0."""
    import struct
    import zlib
    rows = []
    for y in range(h):
        g = 32 * y + 16
        rows.append(b'\x00' + b''.join(struct.pack('>HHH', 32 * x + 16, g, 0) for x in range(w)))

    def ck(k, b):
        return struct.pack('>I', len(b)) + k + b + struct.pack('>I', zlib.crc32(k + b) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + ck(b'IHDR', struct.pack('>IIBBBBB', w, h, 16, 2, 0, 0, 0)) +
            ck(b'IDAT', zlib.compress(b''.join(rows), 6)) + ck(b'IEND', b''))


def udim_plane(name='SM_UdimView', bad=False):
    """Unit quads at x = 0..n with UV centred in 1001, 1002, 1011 (ids now 1), + U = -0.5 / U = 10.2 when bad."""
    centres = [(0.5, 0.5), (1.5, 0.5), (0.5, 1.5)] + ([(-0.5, 0.5), (10.2, 0.5)] if bad else [])
    m = {'key': 1, 'name': name, 'verts': [], 'tris': [], 'mat_ids': [], 'uvs': [], 'uv_tris': []}
    for i, (cu, cv) in enumerate(centres):
        base = len(m['verts'])
        m['verts'].extend([[i, 0, 0], [i + 1, 0, 0], [i + 1, 0, 1], [i, 0, 1]])
        m['uvs'].extend([[cu - 0.4, cv - 0.4], [cu + 0.4, cv - 0.4], [cu + 0.4, cv + 0.4], [cu - 0.4, cv + 0.4]])
        for t in ((0, 1, 2), (0, 2, 3)):
            m['tris'].append([base + t[0], base + t[1], base + t[2]])
            m['uv_tris'].append([base + t[0], base + t[1], base + t[2]])
            m['mat_ids'].append(1)
    m['local'] = m['verts']
    return m


# ---- polygon stations (3ds Max) --------------------------------------------------------------------------------
def make(obj, rt):
    """Editable_Mesh node of a station object: extra.kind n2v_ok | n2v_fail (NPM with window planes) | udim_ok |
    udim_bad. Metres written in system units (units.SystemScale); `pos` of the polygon layout moves the node."""
    kind = (obj.get('extra') or {}).get('kind', 'n2v_ok')
    if kind.startswith('n2v'):
        mesh = station_npm(obj['name'], 'fail' if kind == 'n2v_fail' else 'ok')
    else:
        mesh = udim_plane(obj['name'], bad=(kind == 'udim_bad'))
    node = build_node(rt, mesh, obj['name'])
    if obj.get('pos'):
        k = 1.0 / _m_per_unit(rt)
        node.position = rt.point3(*[float(c) * k for c in obj['pos']])
    return node


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
