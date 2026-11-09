"""new-case: AGR Tools 1.0.x (#1024, branch BH) Max <-> Blender handoff with materials, logic, stdlib only.

Pure logic of `handoff.export`, `handoff.import`, `handoff.verify`, `handoff.restore_materials` (glue: handoff_max.py;
Blender side: tools/blender/handoff_blender.py, which loads THIS file by path). No pymxs, no bpy: hosts hand in plain
facts. Contract of the bundle `handoff/<job>/<seq>/` (mcp-review REPORT.md 3.12, schemas/Handoff.schema.json):

* `model.fbx`        working FBX, NOT triangulated (quads and n-gons as built), metres, Z up, instances preserved;
* `manifest.json`    schema, source host/document, units, axis, system_scale, objects (name, agr_role, layer, parent,
                     world matrix, instance_of, geometry hash, slot table slot_index <-> matID <-> library_id <-> UDIM,
                     UV channels and their tiles), the sha256 of the FBX and of materials.json;
* `sidecar.json`     what FBX loses: user properties (agr_role, agr_window_type, agr_opening, ...), hard edges /
                     smoothing summary, OPEN_* / LEVEL_* markers (helpers are not exported), the passport reference;
* `materials.json`   (owner answer 06.11.2026, critical) per object the assigned material; every material/map node with
                     class (Standardmaterial = Standard Legacy, Multimaterial = Multi/Sub with its IDs, Bitmaptexture
                     with its file path, ...), node name and ALL its parameters, so «Восстановить материалы» rebuilds or
                     reconnects them after the return from Blender (match by name and role; the unmatched go to the
                     report);
* `readback_max.json` host-neutral facts of every exported object (the reference of handoff.verify).

Facts (one dict per mesh object, the same shape on both hosts; metres, world space):
  name, role, parent, world [[x,y,z] row1..row4], scale, verts, faces, edges, degrees {deg: n}, mat_hist {id: n},
  face_keys [[cx,cy,cz,mat_id,deg]...] sorted, uv {channel: {tiles, corners [[u,v]...] sorted}}, hard [[mx,my,mz]...]
  sorted (interior edges whose two faces share no smoothing group / are marked sharp), bbox [[min],[max]],
  instance_group (leader name or None).

What must survive the round trip (REPORT 3.12) is ROWS with the tolerances of TOL; `compare` names every discrepancy.

Defects of the plain FBX round trip this fixes (tests/max_tools/test_agr_tools_handoff.py, RED on the naive model):
  * Blender renames a clashing name `X` to `X.001` and cuts names to 63 UTF-8 bytes -> `restore_name`;
  * matIDs come back as slot order 1..n (a Multi/Sub with IDs 3, 9, 12 returns 1, 2, 3) -> `matid_remap` by the
    sub-material names of the slot table;
  * user properties / roles / markers are not in the FBX -> sidecar;
  * materials come back as FBX (Physical / Principled) copies without the Standard Legacy settings and map nodes ->
    materials.json + `restore_plan` + `diff_nodes`.
"""
import hashlib
import json
import math
import re

TOOL_EXPORT = 'handoff.export'
TOOL_IMPORT = 'handoff.import'
TOOL_VERIFY = 'handoff.verify'
TOOL_RESTORE = 'handoff.restore_materials'
TOOLS = (TOOL_EXPORT, TOOL_IMPORT, TOOL_VERIFY, TOOL_RESTORE)
SCHEMA = 1
KINDS = ('agr.handoff.manifest', 'agr.handoff.sidecar', 'agr.handoff.materials', 'agr.handoff.readback')
BUNDLE_FILES = ('model.fbx', 'manifest.json', 'sidecar.json', 'materials.json', 'readback_max.json')
ROWS = ('names_roles', 'matid_slots', 'uv_udim', 'normals', 'units', 'transform', 'topology', 'instances')
ROW_TITLES = {'names_roles': 'Имена объектов и роли', 'matid_slots': 'matID ↔ слоты', 'uv_udim': 'UV/UDIM',
              'normals': 'Нормали и сглаживание', 'units': 'Единицы, ось, масштаб',
              'transform': 'Пивоты и трансформы', 'topology': 'Топология', 'instances': 'Инстансы'}
TOL = {'uv': 1e-6, 'bbox_m': 1e-4, 'matrix': 1e-5, 'pos_m': 1e-4, 'scale': 1e-5, 'float': 1e-6}
# FBX export of the bundle (FBXExporterSetParam): working model, no triangulation, metres, Z up. Measured (lab job
# 20261106-134044-fbdf80ba): the Max 2024 exporter writes TRIANGLES for Editable_Mesh nodes and for instanced
# Editable_Poly nodes when Preserveinstances is on; so the glue exports temporary Editable_Poly copies with
# Preserveinstances off, and the instances are linked again from manifest.instance_of (Blender side and import).
FBX_EXPORT_PARAMS = (('Animation', False), ('Cameras', False), ('Lights', False), ('ASCII', False),
                     ('FileVersion', 'FBX201400'), ('EmbedTextures', False), ('Triangulate', False),
                     ('SmoothingGroups', True), ('SmoothMeshExport', False), ('ConvertUnit', 'm'), ('UpAxis', 'Z'),
                     ('ScaleFactor', 1.0), ('Preserveinstances', False), ('GeomAsBone', False))
UNIT_CODES = {'millimeters': 'mm', 'centimeters': 'cm', 'meters': 'm', 'kilometers': 'km', 'inches': 'in',
              'feet': 'ft', 'miles': 'mi'}
BLENDER_NAME_BYTES = 63
SUFFIX_RE = re.compile(r'^(?P<base>.+)\.(?P<n>\d{3,})$')
SEQ_RE = re.compile(r'^\d{3}$')
SHA_RE = re.compile(r'^[0-9a-f]{64}$')
PROP_LINE_RE = re.compile(r'^\s*([^=\s][^=]*?)\s*=\s*(.*?)\s*$')
TAGS = ('color', 'point2', 'point3', 'point4', 'name', 'array', 'ref', 'sub', 'skip')
MULTI_CLASSES = ('multimaterial',)


# ---- small helpers -------------------------------------------------------------------------------------------------
def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def next_seq(existing):
    """'001', '002', ... the first free bundle number among the folder names of handoff/."""
    taken = {e for e in existing if SEQ_RE.match(str(e))}
    for n in range(1, 1000):
        s = '{:03d}'.format(n)
        if s not in taken:
            return s
    raise ValueError('no free handoff sequence under 001..999')


def udim(u, v):
    """UDIM tile of a UV point (1001 + floor(u) + 10 floor(v)); None outside the 10-column grid."""
    if not (math.isfinite(u) and math.isfinite(v)):
        return None
    fu, fv = math.floor(u), math.floor(v)
    return 1001 + int(fu) + 10 * int(fv) if 0 <= fu < 10 and fv >= 0 else None


def parse_user_props(buffer):
    """Max user property buffer (`key = value` lines) -> {key: value} (the last one wins, as getUserProp does)."""
    out = {}
    for line in str(buffer or '').replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        m = PROP_LINE_RE.match(line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def rows_from_columns(m):
    """Blender matrix_world (4x4, axes in columns) -> Max-style rows [row1, row2, row3, row4=translation]."""
    return [[float(m[r][c]) for r in range(3)] for c in range(4)]


# ---- names ---------------------------------------------------------------------------------------------------------
def blender_name(name):
    """The name Blender keeps: at most 63 UTF-8 bytes, never a broken character."""
    data = str(name).encode('utf-8')
    if len(data) <= BLENDER_NAME_BYTES:
        return str(name)
    return data[:BLENDER_NAME_BYTES].decode('utf-8', errors='ignore')


def name_collisions(names):
    """[(blender_name, [names])] of names that Blender would cut to the same 63 bytes (the round trip is ambiguous)."""
    by = {}
    for n in names:
        by.setdefault(blender_name(n), []).append(n)
    return sorted((k, sorted(v)) for k, v in by.items() if len(v) > 1)


def restore_name(name, known, taken=()):
    """The original name of an object or material that came back from Blender, or None.

    known: the names of the manifest; taken: names already given back in this import. `X` stays `X`; `X.001` (Blender's
    clash suffix) -> `X`; a name cut to 63 bytes -> the one known name it is the cut of."""
    name = str(name)
    known = list(known)
    taken = set(taken)
    if name in known and name not in taken:
        return name
    m = SUFFIX_RE.match(name)
    if m and m.group('base') in known and m.group('base') not in taken:
        return m.group('base')
    for cand in (name, m.group('base') if m else None):
        if cand is None:
            continue
        hits = [k for k in known if k not in taken and blender_name(k) == cand and k != cand]
        if len(hits) == 1:
            return hits[0]
    return None


def restore_names(got, known):
    """{got name: original name or None} for a list of returned names; first come, first served for duplicates."""
    out, taken = {}, set()
    for g in got:
        r = restore_name(g, known, taken)
        out[g] = r
        if r is not None:
            taken.add(r)
    return out


# ---- slot table / matID --------------------------------------------------------------------------------------------
def slot_table(face_ids, sub_names, tiles_by_id=None):
    """Slot table of one object: [{slot_index, mat_id, material, library_id, udim}] in ascending matID.

    face_ids: matID of every face; sub_names: {mat_id: sub-material name} (Multi/Sub) or {'*': name} (one material);
    tiles_by_id: {mat_id: [UDIM tiles of channel 1]}. Library ids are the mid-poly face ids (< 1001, mat.table K3);
    a delivery id >= 1001 is the UDIM itself."""
    out = []
    for i, mid in enumerate(sorted(set(int(x) for x in face_ids))):
        name = sub_names.get(mid, sub_names.get('*')) if sub_names else None
        tiles = sorted(set((tiles_by_id or {}).get(mid, [])))
        out.append({'slot_index': i, 'mat_id': mid, 'material': name,
                    'library_id': mid if mid < 1001 else None, 'udim': tiles or ([mid] if mid >= 1001 else [])})
    return out


def matid_of_material(slots, material_name):
    """matID of a returned slot material (Blender material / imported sub-material name), or None."""
    names = [s['material'] for s in slots if s['material'] is not None]
    orig = restore_name(material_name, names)
    hits = sorted({s['mat_id'] for s in slots if s['material'] == orig}) if orig is not None else []
    return hits[0] if len(hits) == 1 else None


def matid_remap(slots, imported):
    """({imported id: original id}, [ambiguous]) of one returned object.

    imported: {imported matID: sub-material name} of the material the FBX import made. Two original IDs with the
    same sub-material cannot be told apart after FBX (one FBX material): reported as ambiguous, ID left as is."""
    mapping, ambiguous = {}, []
    names = [s['material'] for s in slots if s['material'] is not None]
    for iid, mname in sorted(imported.items()):
        orig = restore_name(mname, names) if mname is not None else None
        ids = sorted({s['mat_id'] for s in slots if s['material'] == orig}) if orig is not None else []
        if len(ids) == 1:
            mapping[int(iid)] = ids[0]
        else:
            ambiguous.append('imported matID {} ({}) -> {}'.format(iid, mname, ids or 'no slot'))
    return mapping, ambiguous


# ---- facts ---------------------------------------------------------------------------------------------------------
def _r(x, nd=6):
    v = round(float(x), nd)
    return 0.0 if v == 0 else v


def diagonals(ngon_ref, edges, tol=TOL['pos_m']):
    """Edges to dissolve so a triangulated n-gon mesh gets its polygons back.

    The Max 2024 FBX exporter writes TRIANGLES for a mesh with n-gons (> 4 sides) next to other faces (lab job
    20261106-134859-6511047e: an 8-gon prism and a converted cylinder come out as triangles, one pentagon alone does
    not). ngon_ref: {'edges': [midpoints], 'verts': [positions]} of the original mesh (world metres); edges:
    [(edge id, midpoint, [p1, p2])] of the interior edges (two faces) of the returned mesh. An edge is a
    triangulation diagonal when it is not an original edge but both its ends are original vertices."""
    if not ngon_ref:
        return []
    eidx = PointIndex(ngon_ref['edges'])
    vidx = PointIndex(ngon_ref['verts'])
    out = []
    for eid, mid, ends in edges:
        if eidx.find(mid, tol) is None and all(vidx.find(p, tol) is not None for p in ends):
            out.append(eid)
    return out


def finish_facts(name, world, verts_world, faces, mat_ids, edges, hard_mids, uv_corners, role=None, parent=None,
                 scale=None, instance_group=None, edge_mids=None):
    """Host-neutral facts of one mesh object from raw host data.

    world: rows [row1..row4] (metres); verts_world: [[x,y,z]] metres; faces: [[vertex index...]]; mat_ids: per face;
    edges: edge count; hard_mids: [[x,y,z]] midpoints of hard interior edges; uv_corners: {channel: [[[u,v]...] per
    face corner, per face]} (faces in the same order as `faces`)."""
    if len(faces) != len(mat_ids):
        raise ValueError('faces and mat_ids differ in length: ' + name)
    degrees, mat_hist, keys = {}, {}, []
    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    for p in verts_world:
        for i in range(3):
            if not math.isfinite(p[i]):
                raise ValueError('non-finite vertex in ' + name)
            lo[i], hi[i] = min(lo[i], p[i]), max(hi[i], p[i])
    for f, mid in zip(faces, mat_ids):
        d = len(f)
        degrees[str(d)] = degrees.get(str(d), 0) + 1
        mat_hist[str(int(mid))] = mat_hist.get(str(int(mid)), 0) + 1
        c = [sum(verts_world[i][k] for i in f) / d for k in range(3)]
        keys.append([_r(c[0]), _r(c[1]), _r(c[2]), int(mid), d])
    uv = {}
    for ch, per_face in sorted((uv_corners or {}).items(), key=lambda kv: int(kv[0])):
        corners, tiles = [], set()
        for fc in per_face:
            if not fc:
                continue
            cu = sum(p[0] for p in fc) / len(fc)
            cv = sum(p[1] for p in fc) / len(fc)
            tiles.add(udim(cu, cv))
            corners.extend([_r(p[0]), _r(p[1])] for p in fc)
        uv[str(int(ch))] = {'tiles': sorted(t for t in tiles if t is not None), 'outside': None in tiles,
                            'corners': sorted(corners)}
    return {'name': str(name), 'role': role, 'parent': parent,
            'world': [[_r(x) for x in row] for row in world], 'scale': [_r(s) for s in (scale or [1.0, 1.0, 1.0])],
            'verts': len(verts_world), 'faces': len(faces), 'edges': int(edges),
            'degrees': dict(sorted(degrees.items(), key=lambda kv: int(kv[0]))),
            'mat_hist': dict(sorted(mat_hist.items(), key=lambda kv: int(kv[0]))),
            'face_keys': sorted(keys), 'uv': uv, 'hard': sorted([_r(x) for x in p] for p in hard_mids),
            'bbox': [[_r(x) for x in lo], [_r(x) for x in hi]] if verts_world else None,
            'instance_group': instance_group,
            # n-gon meshes only: the original edges and vertices, to undo the exporter's triangulation (diagonals)
            'ngon_ref': {'edges': sorted([_r(x) for x in p] for p in edge_mids),
                         'verts': sorted([_r(x) for x in p] for p in verts_world)}
            if edge_mids is not None and any(len(f) > 4 for f in faces) else None}


class PointIndex:
    """Nearest stored point within a tolerance (grid of `cell` metres): face centres -> matID, edge midpoints -> hard."""

    def __init__(self, points, values=None, cell=1e-3):
        self.cell = cell
        self.grid = {}
        for i, p in enumerate(points):
            self.grid.setdefault(self._key(p), []).append((p, values[i] if values is not None else i))

    def _key(self, p):
        return tuple(int(math.floor(float(c) / self.cell)) for c in p[:3])

    def find(self, p, tol):
        k = self._key(p)
        best, bd = None, tol
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for q, v in self.grid.get((k[0] + dx, k[1] + dy, k[2] + dz), ()):
                        d = max(abs(float(p[i]) - float(q[i])) for i in range(3))
                        if d <= bd:
                            best, bd = v, d
        return best


def ids_by_centre(ref_face_keys, centres, tol=TOL['pos_m']):
    """Original matID of every returned face by its centre (world metres), None where no reference face is there.

    FBX keeps per-face IDs only as material slots: a single (non Multi/Sub) material loses them, and two IDs of one
    sub-material collapse. The reference face keys of readback_max carry them back (an edited face stays None)."""
    idx = PointIndex([k[:3] for k in ref_face_keys], [k[3] for k in ref_face_keys])
    return [idx.find(c, tol) for c in centres]


def hard_index(ref_hard):
    return PointIndex(ref_hard)


SHARP_COS = math.cos(math.radians(0.5))


def sharp_edges(faces, corner_normals, cos_limit=SHARP_COS):
    """Edges (sorted vertex pairs) whose two faces have different corner normals at a shared vertex.

    faces: [[vertex...]]; corner_normals: per face, one unit normal per corner. The Blender FBX importer turns Max
    smoothing groups into custom normals only (no sharp edges); these are the edges to mark sharp again."""
    at = {}
    owners = {}
    for fi, (f, ns) in enumerate(zip(faces, corner_normals)):
        for k, v in enumerate(f):
            at[(fi, v)] = ns[k]
            e = tuple(sorted((v, f[(k + 1) % len(f)])))
            owners.setdefault(e, []).append(fi)
    out = set()
    for e, fs in owners.items():
        if len(fs) != 2:
            continue
        for v in e:
            a, b = at[(fs[0], v)], at[(fs[1], v)]
            if a[0] * b[0] + a[1] * b[1] + a[2] * b[2] < cos_limit:
                out.add(e)
                break
    return out


def geometry_hash(facts):
    """sha256 of the topology + rounded face keys + UV corners (0.1 mm / 1e-5): a label, the verdict is `compare`."""
    body = {'verts': facts['verts'], 'faces': facts['faces'], 'edges': facts['edges'], 'degrees': facts['degrees'],
            'mat_hist': facts['mat_hist'],
            'face_keys': [[round(k[0], 4), round(k[1], 4), round(k[2], 4), k[3], k[4]] for k in facts['face_keys']],
            'uv': {ch: [[round(u, 5), round(v, 5)] for u, v in d['corners']] for ch, d in facts['uv'].items()}}
    return sha256_bytes(canonical(body).encode('utf-8'))


def instance_groups(leaders):
    """{name: leader} -> [[names...]] of groups with more than one member (sorted)."""
    by = {}
    for name, lead in leaders.items():
        if lead is not None:
            by.setdefault(lead, []).append(name)
    return sorted(sorted(v) for v in by.values() if len(v) > 1)


def _close_lists(a, b, tol):
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if isinstance(x, list):
            if not _close_lists(x, y, tol):
                return False
        elif isinstance(x, (int, float)) and isinstance(y, (int, float)):
            if abs(float(x) - float(y)) > tol:
                return False
        elif x != y:
            return False
    return True


def _max_dev(a, b):
    dev = 0.0
    for x, y in zip(a, b):
        if isinstance(x, list):
            dev = max(dev, _max_dev(x, y))
        else:
            dev = max(dev, abs(float(x) - float(y)))
    return dev


def multiset_close(a, b, tol, dims=3):
    """Two point multisets equal: every point of `a` pairs with its own point of `b` within tol in the first `dims`
    coordinates and exactly in the rest (matID, degree). Order-free (a sorted-list compare fails when 13.83 and
    13.829999 swap places; measured on KPP1_Parapet, job 20261106-134538-40e13b6f)."""
    if len(a) != len(b):
        return False
    cell = max(tol * 2.0, 1e-9)
    grid = {}

    def key(p):
        return tuple(int(math.floor(float(p[d]) / cell)) for d in range(dims))
    for i, p in enumerate(b):
        grid.setdefault(key(p), []).append(i)
    used = set()
    offsets = [()]
    for _ in range(dims):
        offsets = [o + (d,) for o in offsets for d in (-1, 0, 1)]
    for p in a:
        k = key(p)
        found = None
        for o in offsets:
            for i in grid.get(tuple(k[d] + o[d] for d in range(dims)), ()):
                q = b[i]
                if i not in used and list(p[dims:]) == list(q[dims:]) and \
                        all(abs(float(p[d]) - float(q[d])) <= tol for d in range(dims)):
                    found = i
                    break
            if found is not None:
                break
        if found is None:
            return False
        used.add(found)
    return True


def _keys_close(a, b, tol):
    """Face keys [[cx,cy,cz,id,deg]] equal as multisets: position within tol, id/degree exactly."""
    return multiset_close(a, b, tol, 3)


def compare(ref, got, rows=ROWS, check_roles=True):
    """{row: [(object name, detail)]} of the discrepancies between two fact lists (reference -> returned).

    Objects are paired by name (the caller restores the names first). An empty list per row = 0 discrepancies."""
    out = {r: [] for r in rows}
    rb = {f['name']: f for f in ref}
    gb = {f['name']: f for f in got}
    if 'names_roles' in out:
        for n in sorted(set(rb) - set(gb)):
            out['names_roles'].append((n, 'missing after the round trip'))
        for n in sorted(set(gb) - set(rb)):
            out['names_roles'].append((n, 'new object (not in the reference)'))
    for n in sorted(set(rb) & set(gb)):
        a, b = rb[n], gb[n]
        if 'names_roles' in out:
            if check_roles and a.get('role') != b.get('role'):
                out['names_roles'].append((n, 'role {} -> {}'.format(a.get('role'), b.get('role'))))
            if a.get('parent') != b.get('parent'):
                out['names_roles'].append((n, 'parent {} -> {}'.format(a.get('parent'), b.get('parent'))))
        if 'topology' in out:
            for k in ('verts', 'faces', 'edges', 'degrees'):
                if a[k] != b[k]:
                    out['topology'].append((n, '{} {} -> {}'.format(k, a[k], b[k])))
        if 'matid_slots' in out:
            if a['mat_hist'] != b['mat_hist']:
                out['matid_slots'].append((n, 'matID histogram {} -> {}'.format(a['mat_hist'], b['mat_hist'])))
            elif not _keys_close(a['face_keys'], b['face_keys'], TOL['pos_m']):
                out['matid_slots'].append((n, 'matID per face differs (face centres / ids)'))
        if 'uv_udim' in out:
            if sorted(a['uv']) != sorted(b['uv']):
                out['uv_udim'].append((n, 'UV channels {} -> {}'.format(sorted(a['uv']), sorted(b['uv']))))
            for ch in sorted(set(a['uv']) & set(b['uv'])):
                ua, ub = a['uv'][ch], b['uv'][ch]
                if ua['tiles'] != ub['tiles']:
                    out['uv_udim'].append((n, 'channel {} UDIM {} -> {}'.format(ch, ua['tiles'], ub['tiles'])))
                if len(ua['corners']) != len(ub['corners']):
                    out['uv_udim'].append((n, 'channel {} corners {} -> {}'.format(
                        ch, len(ua['corners']), len(ub['corners']))))
                elif not multiset_close(ua['corners'], ub['corners'], TOL['uv'], 2):
                    out['uv_udim'].append((n, 'channel {} UV differs (sorted max {:.2e} > {:.0e})'.format(
                        ch, _max_dev(ua['corners'], ub['corners']), TOL['uv'])))
        if 'normals' in out:
            if len(a['hard']) != len(b['hard']):
                out['normals'].append((n, 'hard edges {} -> {}'.format(len(a['hard']), len(b['hard']))))
            elif not multiset_close(a['hard'], b['hard'], TOL['pos_m'], 3):
                out['normals'].append((n, 'hard edges moved'))
        if 'units' in out:
            if (a['bbox'] is None) != (b['bbox'] is None) or (
                    a['bbox'] is not None and not _close_lists(a['bbox'], b['bbox'], TOL['bbox_m'])):
                out['units'].append((n, 'bbox {} -> {}'.format(a['bbox'], b['bbox'])))
            if not _close_lists(a.get('scale') or [1, 1, 1], b.get('scale') or [1, 1, 1], TOL['scale']):
                out['units'].append((n, 'scale {} -> {}'.format(a.get('scale'), b.get('scale'))))
        if 'transform' in out and not _close_lists(a['world'], b['world'], TOL['matrix']):
            out['transform'].append((n, 'world matrix differs by {:.2e} (> {:.0e})'.format(
                _max_dev(a['world'], b['world']), TOL['matrix'])))
    if 'instances' in out:
        ga = instance_groups({f['name']: f.get('instance_group') for f in ref})
        gb_ = instance_groups({f['name']: f.get('instance_group') for f in got})
        for g in ga:
            if g not in gb_:
                out['instances'].append((g[0], 'instance group {} lost'.format(g)))
        for g in gb_:
            if g not in ga:
                out['instances'].append((g[0], 'new instance group {}'.format(g)))
    return out


def discrepancy_count(result):
    return sum(len(v) for v in result.values())


def summary_table(result):
    """[[row, title, count, first detail]] for reports and the PR table."""
    return [[r, ROW_TITLES[r], len(result[r]), '; '.join('{}: {}'.format(n, d) for n, d in result[r][:3])]
            for r in result]


# ---- manifest / sidecar / readback ---------------------------------------------------------------------------------
def build_manifest(source, units, fbx, materials, objects):
    """source {host, doc, app}; units {system, m_per_unit, system_scale}; fbx/materials {file, sha256};
    objects [{name, agr_role, layer, parent, world, instance_of, geometry_hash, handle, slots, uv_channels}]."""
    doc = {'schema': SCHEMA, 'kind': 'agr.handoff.manifest', 'source': source,
           'units': dict(units, export='m', axis='Z-up'), 'fbx': dict(fbx, triangulated=False, ucx=False),
           'materials': materials, 'objects': objects}
    return validate_manifest(doc)


def _req(d, keys, what):
    if not isinstance(d, dict):
        raise ValueError(what + ' must be an object')
    missing = [k for k in keys if k not in d]
    if missing:
        raise ValueError('{} misses {}'.format(what, ', '.join(missing)))


def _file_ref(d, what):
    _req(d, ('file', 'sha256'), what)
    if not isinstance(d['file'], str) or not d['file'] or not SHA_RE.match(str(d['sha256'])):
        raise ValueError(what + ' must be {file, sha256}')


def validate_manifest(doc):
    """Mirror of schemas/Handoff.schema.json $defs/manifest (a pytest pins the equivalence). Returns doc."""
    _req(doc, ('schema', 'kind', 'source', 'units', 'fbx', 'materials', 'objects'), 'manifest')
    if doc['schema'] != SCHEMA or doc['kind'] != 'agr.handoff.manifest':
        raise ValueError('manifest: schema 1, kind agr.handoff.manifest')
    _req(doc['source'], ('host', 'doc', 'app'), 'manifest.source')
    if doc['source']['host'] not in ('max', 'blender'):
        raise ValueError('manifest.source.host must be max or blender')
    _req(doc['units'], ('system', 'm_per_unit', 'system_scale', 'export', 'axis'), 'manifest.units')
    if not isinstance(doc['units']['m_per_unit'], (int, float)) or doc['units']['m_per_unit'] <= 0:
        raise ValueError('manifest.units.m_per_unit must be > 0')
    _file_ref(doc['fbx'], 'manifest.fbx')
    if doc['fbx'].get('triangulated') is not False:
        raise ValueError('manifest.fbx: the working model is never triangulated')
    _file_ref(doc['materials'], 'manifest.materials')
    if not isinstance(doc['objects'], list) or not doc['objects']:
        raise ValueError('manifest.objects must be a non-empty list')
    names = set()
    for o in doc['objects']:
        _req(o, ('name', 'agr_role', 'layer', 'parent', 'world', 'instance_of', 'geometry_hash', 'handle', 'slots',
                 'uv_channels'), 'manifest object')
        if o['name'] in names:
            raise ValueError('manifest: duplicate object name ' + repr(o['name']))
        names.add(o['name'])
        if not isinstance(o['world'], list) or len(o['world']) != 4 or any(len(r) != 3 for r in o['world']):
            raise ValueError('manifest object world must be 4 rows of 3 numbers: ' + o['name'])
        for s in o['slots']:
            _req(s, ('slot_index', 'mat_id', 'material', 'library_id', 'udim'), 'manifest slot')
        for u in o['uv_channels']:
            _req(u, ('channel', 'purpose', 'tiles'), 'manifest uv channel')
    for o in doc['objects']:
        if o['instance_of'] is not None and o['instance_of'] not in names:
            raise ValueError('manifest: instance_of names no exported object: ' + repr(o['instance_of']))
    return doc


def build_sidecar(source, objects, markers, passport):
    doc = {'schema': SCHEMA, 'kind': 'agr.handoff.sidecar', 'source': source, 'objects': objects,
           'markers': markers, 'passport': passport}
    return validate_sidecar(doc)


def validate_sidecar(doc):
    _req(doc, ('schema', 'kind', 'source', 'objects', 'markers', 'passport'), 'sidecar')
    if doc['schema'] != SCHEMA or doc['kind'] != 'agr.handoff.sidecar':
        raise ValueError('sidecar: schema 1, kind agr.handoff.sidecar')
    if not isinstance(doc['objects'], dict):
        raise ValueError('sidecar.objects must be {name: {...}}')
    for name, o in doc['objects'].items():
        _req(o, ('user_props', 'props', 'hard_edges', 'smoothing'), 'sidecar object ' + name)
    for m in doc['markers']:
        _req(m, ('name', 'kind', 'world', 'props'), 'sidecar marker')
        if m['kind'] not in ('opening', 'level'):
            raise ValueError('sidecar marker kind opening|level: ' + repr(m['kind']))
    return doc


def build_readback(host, app, facts):
    return {'schema': SCHEMA, 'kind': 'agr.handoff.readback', 'host': host, 'app': app, 'objects': list(facts)}


def manifest_object(facts, handle, layer, slots, instance_of, uv_purpose=None):
    return {'name': facts['name'], 'agr_role': facts.get('role'), 'layer': layer, 'parent': facts.get('parent'),
            'world': facts['world'], 'instance_of': instance_of, 'geometry_hash': geometry_hash(facts),
            'handle': int(handle), 'slots': slots,
            'uv_channels': [{'channel': int(ch), 'purpose': (uv_purpose or {}).get(int(ch), _purpose(int(ch))),
                             'tiles': d['tiles']} for ch, d in sorted(facts['uv'].items(), key=lambda kv: int(kv[0]))]}


def _purpose(ch):
    return {1: 'delivery UDIM (texture)', 2: 'second channel (lightmap / tiling)'}.get(ch, 'channel {}'.format(ch))


# ---- materials.json ------------------------------------------------------------------------------------------------
def build_materials(source, objects, nodes):
    """objects [{name, role, handle, material: key|None, mat_ids: [...]}]; nodes {key: node} (see encode rules)."""
    doc = {'schema': SCHEMA, 'kind': 'agr.handoff.materials', 'source': source, 'objects': objects, 'nodes': nodes,
           'maps': map_list(nodes)}
    return validate_materials(doc)


def validate_materials(doc):
    _req(doc, ('schema', 'kind', 'source', 'objects', 'nodes', 'maps'), 'materials.json')
    if doc['schema'] != SCHEMA or doc['kind'] != 'agr.handoff.materials':
        raise ValueError('materials.json: schema 1, kind agr.handoff.materials')
    nodes = doc['nodes']
    if not isinstance(nodes, dict):
        raise ValueError('materials.json nodes must be {key: node}')
    for key, n in nodes.items():
        _req(n, ('name', 'class', 'superclass', 'props'), 'material node ' + key)
        for v in n['props'].values():
            _check_value(v, nodes, key)
    for o in doc['objects']:
        _req(o, ('name', 'role', 'handle', 'material', 'mat_ids'), 'materials.json object')
        if o['material'] is not None and o['material'] not in nodes:
            raise ValueError('materials.json: object {} names unknown node {}'.format(o['name'], o['material']))
    return doc


def _check_value(v, nodes, where):
    if v is None or isinstance(v, (bool, int, float, str)):
        if isinstance(v, float) and not math.isfinite(v):
            raise ValueError('non-finite value in ' + where)
        return
    if isinstance(v, dict) and v.get('$') in TAGS:
        tag = v['$']
        if tag == 'ref' and v.get('v') not in nodes:
            raise ValueError('ref to unknown node {} in {}'.format(v.get('v'), where))
        if tag == 'array':
            for x in v['v']:
                _check_value(x, nodes, where)
        if tag == 'sub':
            for x in v['props'].values():
                _check_value(x, nodes, where)
        return
    raise ValueError('unknown encoded value in {}: {!r}'.format(where, v)[:200])


def is_multi(node):
    return str(node.get('class', '')).lower() in MULTI_CLASSES


def map_list(nodes):
    """[{node, class, path, used_by: [material/map names]}] of every node with a file path (Bitmaptexture etc.)."""
    users = {}
    for key, n in nodes.items():
        for ref in _refs_in(n['props']):
            users.setdefault(ref, set()).add(n['name'])
    out = []
    for key, n in sorted(nodes.items()):
        path = n['props'].get('filename') if isinstance(n['props'].get('filename'), str) else \
            n['props'].get('fileName') if isinstance(n['props'].get('fileName'), str) else None
        if path is not None:
            out.append({'node': n['name'], 'key': key, 'class': n['class'], 'path': path,
                        'used_by': sorted(users.get(key, ()))})
    return out


def _refs_in(props):
    for v in props.values():
        yield from _refs_value(v)


def _refs_value(v):
    if isinstance(v, dict):
        if v.get('$') == 'ref':
            yield v['v']
        elif v.get('$') == 'array':
            for x in v['v']:
                yield from _refs_value(x)
        elif v.get('$') == 'sub':
            yield from _refs_in(v['props'])


def multi_ids(node):
    """{mat_id: sub-material ref key or None} of a Multi/Sub node (materialIDList x materialList)."""
    ids = node['props'].get('materialIDList', {}).get('v', [])
    subs = node['props'].get('materialList', {}).get('v', [])
    out = {}
    for i, mid in enumerate(ids):
        ref = subs[i] if i < len(subs) else None
        out[int(mid)] = ref['v'] if isinstance(ref, dict) and ref.get('$') == 'ref' else None
    return out


def sub_names(doc, key, used_ids=None):
    """{mat_id: sub-material name} of the object's material (Multi/Sub), or {'*': name} for one material."""
    if key is None:
        return {}
    node = doc['nodes'][key]
    if not is_multi(node):
        return {'*': node['name']}
    out = {}
    ids = multi_ids(node)
    for mid, ref in ids.items():
        if used_ids is None or mid in used_ids:
            out[mid] = doc['nodes'][ref]['name'] if ref else None
    return out


def diff_nodes(nodes_a, key_a, nodes_b, key_b, path='', seen=None, tol=TOL['float']):
    """[path: what differs] between node `key_a` of one materials document and `key_b` of another (refs followed,
    skipped values ignored). Empty = the same material graph (names, classes, every encoded parameter, map paths)."""
    seen = set() if seen is None else seen
    if (key_a, key_b) in seen:
        return []
    seen.add((key_a, key_b))
    a, b = nodes_a[key_a], nodes_b[key_b]
    here = path or a['name']
    out = []
    if a['class'] != b['class']:
        return ['{}: class {} -> {}'.format(here, a['class'], b['class'])]
    if a['name'] != b['name']:
        out.append('{}: name {} -> {}'.format(here, a['name'], b['name']))
    for prop in sorted(set(a['props']) | set(b['props'])):
        va, vb = a['props'].get(prop, {'$': 'skip'}), b['props'].get(prop, {'$': 'skip'})
        out.extend(_diff_value(nodes_a, va, nodes_b, vb, '{}.{}'.format(here, prop), seen, tol))
    return out


def _diff_value(na, va, nb, vb, path, seen, tol):
    if _skip(va) or _skip(vb):
        return []
    if isinstance(va, dict) and isinstance(vb, dict) and va.get('$') == vb.get('$'):
        tag = va['$']
        if tag == 'ref':
            return diff_nodes(na, va['v'], nb, vb['v'], path + '>' + nb[vb['v']]['name'], seen, tol)
        if tag == 'array':
            if len(va['v']) != len(vb['v']):
                return ['{}: {} items -> {}'.format(path, len(va['v']), len(vb['v']))]
            out = []
            for i, (x, y) in enumerate(zip(va['v'], vb['v'])):
                out.extend(_diff_value(na, x, nb, y, '{}[{}]'.format(path, i + 1), seen, tol))
            return out
        if tag == 'sub':
            out = []
            for p in sorted(set(va['props']) | set(vb['props'])):
                out.extend(_diff_value(na, va['props'].get(p, {'$': 'skip'}), nb, vb['props'].get(p, {'$': 'skip'}),
                                       '{}.{}'.format(path, p), seen, tol))
            return out
        if tag in ('color', 'point2', 'point3', 'point4'):
            return [] if _close_lists(va['v'], vb['v'], tol) else ['{}: {} -> {}'.format(path, va['v'], vb['v'])]
        return [] if va == vb else ['{}: {} -> {}'.format(path, va, vb)]
    if isinstance(va, bool) or isinstance(vb, bool):
        return [] if va is vb else ['{}: {} -> {}'.format(path, va, vb)]
    if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
        return [] if abs(float(va) - float(vb)) <= tol * max(1.0, abs(float(va))) else \
            ['{}: {} -> {}'.format(path, va, vb)]
    if isinstance(va, str) and isinstance(vb, str) and path.lower().endswith(('.filename', '.filename]')):
        return [] if va.replace('/', '\\').lower() == vb.replace('/', '\\').lower() else \
            ['{}: {} -> {}'.format(path, va, vb)]
    return [] if va == vb else ['{}: {!r} -> {!r}'.format(path, va, vb)[:300]]


def _skip(v):
    return isinstance(v, dict) and v.get('$') == 'skip'


def restore_plan(entries, targets):
    """Pair materials.json objects with scene objects by name and role.

    entries: materials.json `objects`; targets: [{'handle', 'name', 'role'}] (the returned objects).
    Returns (pairs [(handle, entry)], unmatched_json [(name, why)], unmatched_scene [(handle, name, why)],
    ambiguous [(name, why)]). Names go through restore_name (Blender `.001` and 63-byte cuts); a role on both sides
    must be equal."""
    known = [e['name'] for e in entries]
    by_entry = {e['name']: e for e in entries}
    cands = {}
    unmatched_scene = []
    for t in targets:
        orig = restore_name(t['name'], known)
        if orig is None:
            unmatched_scene.append((t['handle'], t['name'], 'no object of materials.json has this name'))
            continue
        e = by_entry[orig]
        if e['role'] not in (None, '') and t.get('role') not in (None, '') and e['role'] != t['role']:
            unmatched_scene.append((t['handle'], t['name'], 'role {} != {} of materials.json'.format(
                t.get('role'), e['role'])))
            continue
        cands.setdefault(orig, []).append(t)
    pairs, ambiguous, unmatched_json = [], [], []
    for e in entries:
        got = cands.get(e['name'], [])
        if not got:
            unmatched_json.append((e['name'], 'no returned object with this name and role'))
        elif len(got) > 1:
            exact = [t for t in got if t['name'] == e['name']]
            if len(exact) == 1:
                pairs.append((exact[0]['handle'], e))
                for t in got:
                    if t is not exact[0]:
                        unmatched_scene.append((t['handle'], t['name'], 'second candidate for ' + e['name']))
            else:
                ambiguous.append((e['name'], '{} returned objects: {}'.format(
                    len(got), ', '.join(t['name'] for t in got))))
        else:
            pairs.append((got[0]['handle'], e))
    return pairs, unmatched_json, unmatched_scene, ambiguous


# ---- options -------------------------------------------------------------------------------------------------------
EXPORT_OPTIONS = ('job_dir', 'seq', 'materials_next_to_scene')
IMPORT_OPTIONS = ('bundle', 'fbx', 'request_id', 'agent_dir', 'project_id')
VERIFY_OPTIONS = ('bundle', 'layer', 'blender_readback')
RESTORE_OPTIONS = ('materials', 'bundle', 'layer', 'reuse')


def check_options(tool, opts, allowed):
    unknown = set(opts or {}) - set(allowed)
    if unknown:
        raise ValueError('unknown {} options: {}'.format(tool, ', '.join(sorted(unknown))))
    return dict(opts or {})


def request_id_of(bundle_dir, seq=None):
    """Default agent request id of an import: `bh<seq>` (layer AGENT_bh001)."""
    import os
    s = seq or os.path.basename(os.path.normpath(bundle_dir))
    s = re.sub(r'[^A-Za-z0-9-]', '', str(s)) or '000'
    return 'bh' + s[-16:]
