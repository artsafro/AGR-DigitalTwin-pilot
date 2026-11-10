"""new-case: AGR Tools 1.0 (#1024) Quick Attach by material (Keep split by default) / move apart: To = final gap logic, stdlib only. owned by branch G (improve/issue-1024-body).

Pure logic for `model_attach_by_material` (model.attach_by_material), `model_move_apart` (model.move_apart); no pymxs.
The cores take plain data (ObjRef dicts, metres, face lists), never host objects (contract_core, BRANCH0-U-L12-ADDENDUM).

model.attach_by_material (lab L14, docs/experiments/model.attach_by_material.md, job 20261106-022928-efe08cb9):
  source Turbo Attacher GeoAGR.ms:54814-55618 recoloured faces in the «one object» mode (:55027-55030, :55056-55067:
  the first material of a pair is wrapped into slot 1 of a Multi/Sub, face IDs stay), gave geometry without a material
  its neighbour's material (:55021-55024), attached children silently and ran in `undo off` (:55232). Here:
  * `split` (Keep split, the default, owner answer 06.11.2026): one object per material INSTANCE; material IDs untouched,
    so every face shows the same material as before.
  * `one`: a Multi/Sub of every shown material (slot `No_Material` for faces without one), the face IDs of EVERY source
    remapped through its table «shown material -> slot» (owner: «один объект» only with the full renumbering).
  * names K1 `BODY_<material>_NNN`; two different materials with one name -> warning `same_name_material`;
    children of an attached object are re-parented to the result (or the object is refused, option children=refuse).
  * the check of the lab: area of faces per shown material before == after (1e-6 m2).

model.move_apart (lab L14, docs/experiments/model.move_apart.md, job 20261106-023115-9c734b51): none of Move Verts
:50241 / Move Edges :48952 / Move Faces :49657 gives a usable «gap x range -> gap after» table (Move Faces passes only
d == min, `d >= min and d <= min` :49812; each side moves To, final gap 2*To; ranges in system units; co-directional
pairs move together; `::dist` leaks :50282). Here: pairs of parallel faces overlapping in projection with a gap in
[min, max] metres; back-to-back (or facing) pair: each face along the line between them by (To - g) / 2;
co-directional pair: the front face by (To - g); To = the FINAL gap (owner answer 06.11.2026).
"""
import bisect
import math

ATTACH_MODES = ('split', 'one')
CHILDREN = ('reparent', 'refuse')
ATTACH_OPTIONS = {'mode', 'children', 'name'}
NO_MATERIAL = 'No_Material'
NO_MATERIAL_TOKEN = 'NoMaterial'
AREA_TOL_M2 = 1e-6

MOVE_OPTIONS = {'range', 'min_mm', 'max_mm', 'to_mm', 'angle_deg', 'min_overlap_m2'}
# presets of the source's range buttons (GeoAGR.ms:47135-47172) in mm; `to_mm` is the FINAL gap (owner 06.11.2026)
RANGES = {'main': (0.0, 2.0, 3.0), 'coplanar': (5.0, 20.0, 20.0), 'all': (0.0, 20.0, 20.0)}
DEFAULT_RANGE = 'main'
EPS_M = 1e-7          # inclusive range edges and «same plane» in metres
GAP_TOL_M = 1e-5      # acceptance: gap after = To +- 0.01 mm
_TRANSLIT = dict(zip('абвгдеёжзийклмнопрстуфхцчшщъыьэюя',
                     ['a', 'b', 'v', 'g', 'd', 'e', 'e', 'zh', 'z', 'i', 'y', 'k', 'l', 'm', 'n', 'o', 'p', 'r', 's',
                      't', 'u', 'f', 'h', 'ts', 'ch', 'sh', 'sch', '', 'y', '', 'e', 'yu', 'ya']))


# ---- names (K1 BODY_<material>_NNN) ----------------------------------------------------------------------------
def material_token(name):
    """Material name -> the [A-Za-z0-9]+ part of BODY_<material>_NNN (Cyrillic transliterated, the rest dropped)."""
    if name is None:
        return NO_MATERIAL_TOKEN
    out = []
    for ch in str(name):
        low = ch.lower()
        if low in _TRANSLIT:
            t = _TRANSLIT[low]
            out.append(t.capitalize() if ch != low and t else t)
        elif ch.isascii() and ch.isalnum():
            out.append(ch)
    token = ''.join(out)[:48]
    return token or 'Mat'


def next_body_name(token, taken):
    """First free BODY_<token>_NNN (NNN from 001) not in `taken`; adds it to `taken`."""
    for n in range(1, 1000):
        name = 'BODY_{}_{:03d}'.format(token, n)
        if name not in taken:
            taken.add(name)
            return name
    raise ValueError('no free BODY_{}_NNN name (001..999 taken)'.format(token))


# ---- materials ------------------------------------------------------------------------------------------------
def _check_material(mat, where):
    if mat is None:
        return None
    if not isinstance(mat, dict) or mat.get('kind') not in ('single', 'multi'):
        raise ValueError('{}: material must be None or {{kind: single|multi, key, name}}'.format(where))
    if isinstance(mat.get('key'), bool) or not isinstance(mat.get('key'), int):
        raise ValueError('{}: material key must be an integer (instance id)'.format(where))
    if mat['kind'] == 'multi':
        slots = mat.get('slots')
        if not isinstance(slots, list):
            raise ValueError('{}: Multi/Sub needs slots'.format(where))
        for s in slots:
            if not isinstance(s, dict) or isinstance(s.get('id'), bool) or not isinstance(s.get('id'), int):
                raise ValueError('{}: Multi/Sub slot needs an integer id'.format(where))
    return mat


def shown(mat, face_id):
    """(key, name) of the material a face with this material ID shows, None for no material.

    Multi/Sub: the slot whose ID equals the face ID; a face ID outside the ID list wraps by slot index
    ((id - 1) mod n), as 3ds Max renders it; an empty slot shows no material."""
    if mat is None:
        return None
    if mat['kind'] == 'single':
        return (mat['key'], mat.get('name') or '')
    slots = mat['slots']
    if not slots:
        return None
    slot = next((s for s in slots if s['id'] == face_id), None)
    if slot is None:
        slot = slots[(int(face_id) - 1) % len(slots)]
    if slot.get('key') is None:
        return None
    return (slot['key'], slot.get('name') or '')


def material_areas(objects):
    """{shown material key or None: area m2} over all faces of the objects (the lab's before/after measure)."""
    out = {}
    for o in objects:
        mat = o.get('material')
        for fid, area in zip(o['face_ids'], o['face_areas']):
            s = shown(mat, fid)
            key = None if s is None else s[0]
            out[key] = out.get(key, 0.0) + float(area)
    return out


def compare_areas(before, after, tol=AREA_TOL_M2):
    """[(key, before, after)] of shown materials whose face area changed beyond tol (abs, or 1e-9 relative)."""
    bad = []
    for key in sorted(set(before) | set(after), key=lambda k: (k is None, k if k is not None else 0)):
        a, b = before.get(key, 0.0), after.get(key, 0.0)
        if abs(a - b) > max(tol, 1e-9 * max(abs(a), abs(b))):
            bad.append((key, a, b))
    return bad


def _material_names(objects):
    """{key: name} of every material instance seen (singles and Multi/Sub slots)."""
    names = {}
    for o in objects:
        mat = o.get('material')
        if mat is None:
            continue
        names[mat['key']] = mat.get('name') or ''
        for s in mat.get('slots') or ():
            if s.get('key') is not None:
                names.setdefault(s['key'], s.get('name') or '')
    return names


def attach_options(options):
    opts = dict(options or {})
    unknown = set(opts) - ATTACH_OPTIONS
    if unknown:
        raise ValueError('unknown model.attach_by_material options: ' + ', '.join(sorted(unknown)))
    out = {'mode': opts.get('mode', 'split'), 'children': opts.get('children', 'reparent'), 'name': opts.get('name')}
    if out['mode'] not in ATTACH_MODES:
        raise ValueError('options.mode must be split (Keep split, default) or one')
    if out['children'] not in CHILDREN:
        raise ValueError('options.children must be reparent or refuse')
    if out['name'] is not None and (not isinstance(out['name'], str) or material_token(out['name']) != out['name']):
        raise ValueError('options.name must be [A-Za-z0-9]+ (the <material> part of BODY_<material>_NNN)')
    return out


def attach_plan(objects, options=None, taken=()):
    """Plan of model.attach_by_material.

    objects: [{handle, name, geometry: bool, material: None | {kind: single, key, name} |
               {kind: multi, key, name, slots: [{id, key|None, name}]}, face_ids: [...], face_areas: [m2...],
               parent: handle|None, children: [handle...]}] in selection order.
    taken: object names already in the scene (the new BODY_ names avoid them).
    Returns {mode, groups: [{name, kind: material|multi|none|one, key, members: [handle], id_maps: {handle: {old: new}},
    slots: [{id, key|None, name}] (mode one), reparent: [[child, member]]}], skipped: [(handle, name, reason)],
    findings: {handle: [(code, detail)]}, areas: {key: m2}, names: {key: name}, warnings: [text]}."""
    opts = attach_options(options)
    if not objects:
        raise ValueError('model.attach_by_material: empty selection')
    selected = {o['handle'] for o in objects}
    findings, skipped, work = {}, [], []
    for o in objects:
        _check_material(o.get('material'), o.get('name'))
        if not o.get('geometry'):
            skipped.append((o['handle'], o['name'], 'not geometry ({})'.format(o.get('cls') or 'helper')))
            continue
        if not o['face_ids']:
            skipped.append((o['handle'], o['name'], 'no faces'))
            continue
        if len(o['face_ids']) != len(o['face_areas']):
            raise ValueError(o['name'] + ': face_ids and face_areas differ in length')
        outside = [c for c in o.get('children') or () if c not in selected]
        if outside and opts['children'] == 'refuse':
            skipped.append((o['handle'], o['name'], '{} child object(s) not selected; options.children=refuse'.format(
                len(outside))))
            continue
        work.append(o)
    if not work:
        raise ValueError('model.attach_by_material: nothing to attach ({} skipped)'.format(len(skipped)))
    names = _material_names(work)
    by_name = {}
    for key, nm in names.items():
        by_name.setdefault(nm, set()).add(key)
    clash = {nm for nm, keys in by_name.items() if len(keys) > 1}
    warnings = ['material name {!r} is used by {} different materials; kept apart (by instance)'.format(
        nm, len(by_name[nm])) for nm in sorted(clash)]
    for o in work:
        mat = o.get('material')
        keys = {s[0] for s in (shown(mat, f) for f in set(o['face_ids'])) if s is not None}
        if any(names.get(k) in clash for k in keys):
            findings.setdefault(o['handle'], []).append(
                ('same_name_material', 'another material has the same name; kept apart (by instance)'))
        if any(shown(mat, f) is None for f in set(o['face_ids'])):
            findings.setdefault(o['handle'], []).append(
                ('no_material', 'faces without a material -> ' + (NO_MATERIAL + ' slot' if opts['mode'] == 'one'
                                                                  else 'object BODY_NoMaterial_NNN')))
    taken = set(taken)
    groups = []
    if opts['mode'] == 'split':
        order, members = [], {}
        for o in work:
            mat = o.get('material')
            gk = None if mat is None else (mat['kind'], mat['key'])
            if gk not in members:
                order.append(gk)
                members[gk] = []
            members[gk].append(o)
        for gk in order:
            if gk is None:
                kind, key, token = 'none', None, NO_MATERIAL_TOKEN
            else:
                mat = members[gk][0]['material']
                kind, key, token = ('material' if gk[0] == 'single' else 'multi'), gk[1], material_token(mat.get('name'))
            groups.append({'name': next_body_name(token, taken), 'kind': kind, 'key': key,
                           'members': [o['handle'] for o in members[gk]], 'id_maps': {}, 'slots': []})
    else:
        slots, slot_of = [], {}
        for o in work:
            mat = o.get('material')
            for f in o['face_ids']:
                s = shown(mat, f)
                k = None if s is None else s[0]
                if k not in slot_of:
                    slot_of[k] = len(slots) + 1
                    slots.append({'id': slot_of[k], 'key': k, 'name': NO_MATERIAL if k is None else names.get(k, '')})
        id_maps = {}
        for o in work:
            mat = o.get('material')
            m = {}
            for f in sorted(set(o['face_ids'])):
                s = shown(mat, f)
                m[f] = slot_of[None if s is None else s[0]]
            id_maps[o['handle']] = m
        token = opts['name'] or 'Attached'
        groups.append({'name': next_body_name(token, taken), 'kind': 'one', 'key': None,
                       'members': [o['handle'] for o in work], 'id_maps': id_maps, 'slots': slots})
    group_of = {h: g['name'] for g in groups for h in g['members']}
    for g in groups:
        g['reparent'] = [[c, h] for h in g['members'] for o in work if o['handle'] == h
                         for c in o.get('children') or () if c not in group_of]
    return {'mode': opts['mode'], 'groups': groups, 'skipped': skipped, 'findings': findings,
            'areas': material_areas(work), 'names': names, 'warnings': warnings, 'options': opts}


def remap_ids(face_ids, id_map):
    """Face IDs after the remap of the «one object» mode (every ID of the source must be in its map)."""
    missing = sorted(set(face_ids) - set(id_map))
    if missing:
        raise ValueError('face IDs without a slot: {}'.format(missing[:10]))
    return [id_map[f] for f in face_ids]


def merged_object(plan, group, objects):
    """The result object of a group as the core sees it (material + face IDs), for the area check without a host."""
    by = {o['handle']: o for o in objects}
    face_ids, face_areas = [], []
    for h in group['members']:
        o = by[h]
        ids = remap_ids(o['face_ids'], {int(k): v for k, v in group['id_maps'][h].items()}) \
            if group['kind'] == 'one' else list(o['face_ids'])
        face_ids += ids
        face_areas += list(o['face_areas'])
    if group['kind'] == 'one':
        mat = {'kind': 'multi', 'key': -1, 'name': group['name'],
               'slots': [{'id': s['id'], 'key': s['key'], 'name': s['name']} for s in group['slots']]}
    elif group['kind'] == 'none':
        mat = None
    else:
        mat = by[group['members'][0]]['material']
    return {'handle': -1, 'name': group['name'], 'geometry': True, 'material': mat, 'face_ids': face_ids,
            'face_areas': face_areas}


# ---- geometry (move apart) -------------------------------------------------------------------------------------
def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a):
    return math.sqrt(_dot(a, a))


def face_frame(pts):
    """(unit normal (Newell), centroid, area m2) of a planar polygon; None for a degenerate one."""
    nx = ny = nz = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1, z1 = pts[i]
        x2, y2, z2 = pts[(i + 1) % n]
        nx += (y1 - y2) * (z1 + z2)
        ny += (z1 - z2) * (x1 + x2)
        nz += (x1 - x2) * (y1 + y2)
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length < 1e-12:
        return None
    c = (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n, sum(p[2] for p in pts) / n)
    return (nx / length, ny / length, nz / length), c, length / 2.0


def _basis(n):
    a = (1.0, 0.0, 0.0) if abs(n[0]) < 0.9 else (0.0, 1.0, 0.0)
    u = _cross(n, a)
    u = _mul(u, 1.0 / _norm(u))
    return u, _cross(n, u)


def _clip(subject, a, b):
    """Sutherland-Hodgman: keep the part of `subject` left of the directed edge a->b (2D)."""
    out = []
    if not subject:
        return out

    def side(p):
        return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
    prev = subject[-1]
    for cur in subject:
        sc, sp = side(cur), side(prev)
        if sc >= 0:
            if sp < 0:
                out.append(_cut(prev, cur, sp, sc))
            out.append(cur)
        elif sp >= 0:
            out.append(_cut(prev, cur, sp, sc))
        prev = cur
    return out


def _cut(p, q, sp, sq):
    t = sp / (sp - sq)
    return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)


def _area2(poly):
    s = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        s += x1 * y2 - x2 * y1
    return s / 2.0


def _ccw(tri):
    return tri if _area2(tri) >= 0 else tri[::-1]


def _fan(poly):
    return [_ccw([poly[0], poly[i], poly[i + 1]]) for i in range(1, len(poly) - 1)]


def overlap_area(pa, pb, n):
    """Area (m2) of the overlap of two parallel polygons projected on the plane with normal n (fan triangles)."""
    u, v = _basis(n)
    a2 = [(_dot(p, u), _dot(p, v)) for p in pa]
    b2 = [(_dot(p, u), _dot(p, v)) for p in pb]
    total = 0.0
    for ta in _fan(a2):
        for tb in _fan(b2):
            piece = list(tb)
            for i in range(3):
                piece = _clip(piece, ta[i], ta[(i + 1) % 3])
                if not piece:
                    break
            if len(piece) >= 3:
                total += abs(_area2(piece))
    return total


def move_options(options):
    """{min_m, max_m, to_m, angle_deg, min_overlap_m2, range} from the options (mm in, metres out)."""
    opts = dict(options or {})
    unknown = set(opts) - MOVE_OPTIONS
    if unknown:
        raise ValueError('unknown model.move_apart options: ' + ', '.join(sorted(unknown)))
    preset = opts.get('range', DEFAULT_RANGE)
    if preset not in RANGES:
        raise ValueError('options.range must be one of ' + ', '.join(sorted(RANGES)))
    lo, hi, to = RANGES[preset]
    vals = {}
    for key, default in (('min_mm', lo), ('max_mm', hi), ('to_mm', to), ('angle_deg', 1.0),
                         ('min_overlap_m2', 1e-6)):
        v = opts.get(key, default)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
            raise ValueError('options.{} must be a finite number >= 0: {!r}'.format(key, v))
        vals[key] = float(v)
    if vals['min_mm'] > vals['max_mm']:
        raise ValueError('options.min_mm > options.max_mm')
    if vals['to_mm'] <= 0:
        raise ValueError('options.to_mm (the final gap) must be > 0')
    if not 0 <= vals['angle_deg'] < 45:
        raise ValueError('options.angle_deg must be in [0, 45)')
    return {'range': preset, 'min_m': vals['min_mm'] / 1000.0, 'max_m': vals['max_mm'] / 1000.0,
            'to_m': vals['to_mm'] / 1000.0, 'angle_deg': vals['angle_deg'], 'min_overlap_m2': vals['min_overlap_m2']}


def _faces(objects):
    """Faces with normal, centroid, canonical normal `cn` and plane offset `d` about the selection centre (so a
    far-from-zero scene does not widen the offset window), plus `r`: the largest centroid radius."""
    out = []
    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    for o in objects:
        for p in o['verts']:
            for k in range(3):
                lo[k] = min(lo[k], float(p[k]))
                hi[k] = max(hi[k], float(p[k]))
    centre = tuple((lo[k] + hi[k]) / 2.0 for k in range(3)) if objects and math.isfinite(lo[0]) else (0.0, 0.0, 0.0)
    for oi, o in enumerate(objects):
        verts = o['verts']
        for fi, poly in enumerate(o['faces']):
            pts = [tuple(float(c) for c in verts[i]) for i in poly]
            if not all(math.isfinite(c) for p in pts for c in p):
                raise ValueError('non-finite vertex in object {} face {}'.format(oi, fi + 1))
            fr = face_frame(pts)
            if fr is None:
                continue
            n, c, area = fr
            # canonical direction: the normal or its opposite, the largest component positive
            big = max(range(3), key=lambda k: abs(n[k]))
            cn = n if n[big] > 0 else _mul(n, -1.0)
            rc = _sub(c, centre)
            out.append({'obj': oi, 'face': fi, 'pts': pts, 'n': n, 'c': c, 'area': area,
                        'cn': cn, 'd': _dot(cn, rc), 'r': _norm(rc), 'verts': list(poly)})
    return out


def find_pairs(objects, opts):
    """Candidate pairs of parallel faces with an overlap in projection and a gap in [min_m, max_m] (metres).

    objects: [{'verts': [[x, y, z] m world], 'faces': [[i...]...]}]. Returns pairs sorted by gap, each
    {a, b: (obj, face), kind: bi|co, gap_m, s_m (signed: b's plane from a along a's normal), overlap_m2}."""
    faces = _faces(objects)
    if not faces:
        return []
    cos_tol = math.cos(math.radians(opts['angle_deg'])) - 1e-12
    q = max(math.sin(math.radians(max(opts['angle_deg'], 0.05))), 1e-3) * 2.0
    hi = opts['max_m'] + EPS_M
    # the plane offsets of two near-parallel faces differ by the gap plus the tilt over the centroid radius
    margin = hi + 2.0 * math.sin(math.radians(opts['angle_deg']) / 2.0 + 1e-12) * max(f['r'] for f in faces) * 2.0 \
        + 1e-6

    def qkey(n):
        return tuple(int(math.floor(c / q)) for c in n)
    buckets = {}
    for j, f in enumerate(faces):
        buckets.setdefault(qkey(f['cn']), []).append((f['d'], j))
    for lst in buckets.values():
        lst.sort()
    pairs, seen = [], set()
    for i, fa in enumerate(faces):
        for sgn in (1.0, -1.0):  # the canonical sign may flip between two near-parallel normals: look both ways
            key = qkey(_mul(fa['cn'], sgn))
            d0 = sgn * fa['d']
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        lst = buckets.get((key[0] + dx, key[1] + dy, key[2] + dz))
                        if not lst:
                            continue
                        k = bisect.bisect_left(lst, (d0 - margin, -1))
                        for d, j in lst[k:]:
                            if d > d0 + margin:
                                break
                            if j <= i or (i, j) in seen:
                                continue
                            seen.add((i, j))
                            _pair(fa, faces[j], opts, cos_tol, hi, pairs)
    pairs.sort(key=lambda p: (p['gap_m'], p['a'], p['b']))
    return pairs


def _pair(fa, fb, opts, cos_tol, hi, pairs):
    cosang = _dot(fa['n'], fb['n'])
    if abs(cosang) < cos_tol:
        return
    s = _dot(_sub(fb['c'], fa['c']), fa['n'])
    gap = abs(s)
    if gap < opts['min_m'] - EPS_M or gap > hi:
        return
    if not _bbox_near(fa['pts'], fb['pts'], hi):
        return
    ov = overlap_area(fa['pts'], fb['pts'], fa['n'])
    if ov <= opts['min_overlap_m2']:
        return
    pairs.append({'a': (fa['obj'], fa['face']), 'b': (fb['obj'], fb['face']),
                  'kind': 'co' if cosang > 0 else 'bi', 'gap_m': gap, 's_m': s, 'overlap_m2': ov,
                  '_fa': fa, '_fb': fb})


def _bbox_near(pa, pb, pad):
    for k in range(3):
        if min(p[k] for p in pa) > max(p[k] for p in pb) + pad or min(p[k] for p in pb) > max(p[k] for p in pa) + pad:
            return False
    return True


def _shifts(pair, to_m):
    """{(obj, face): world shift vector m} that sets the gap of the pair to to_m."""
    fa, fb = pair['_fa'], pair['_fb']
    s, g, delta = pair['s_m'], pair['gap_m'], to_m - pair['gap_m']
    n = fa['n']
    if pair['kind'] == 'bi':
        if g > EPS_M:
            da, db = _mul(n, -math.copysign(1.0, s)), _mul(n, math.copysign(1.0, s))
        else:  # one double plane: back to back, each face along its own normal
            da, db = fa['n'], fb['n']
        return {pair['a']: _mul(da, delta / 2.0), pair['b']: _mul(db, delta / 2.0)}
    # co-directional: one side moves; the front face (b in front of a), at g == 0 the later face (b)
    if g > EPS_M and s < 0:
        return {pair['a']: _mul(n, delta)}
    return {pair['b']: _mul(n, delta)}


def _compatible(existing, vec):
    """A vertex may take several shifts only if they are equal or mutually orthogonal (a box corner)."""
    for e in existing:
        if _norm(_sub(e, vec)) <= 1e-9:
            return True, False
        ne, nv = _norm(e), _norm(vec)
        if ne > 0 and nv > 0 and abs(_dot(e, vec)) / (ne * nv) > 0.01:
            return False, False
    return True, True


def move_plan(objects, options=None):
    """Plan of model.move_apart: pairs found, the per-vertex shifts (metres world) and the skipped pairs.

    Each face is in at most one pair (the smallest gap first). Returns {opts, pairs: [...], moves: {obj: {vert:
    [dx, dy, dz]}}, skipped: [(pair, reason)], faces: {obj: [face...]} (1-based face numbers of pairs)}."""
    opts = move_options(options)
    if not objects:
        raise ValueError('model.move_apart: empty selection')
    cands = find_pairs(objects, opts)
    used, taken, skipped = set(), [], []
    vshift = {}
    for p in cands:
        if p['a'] in used or p['b'] in used:
            continue
        shifts = _shifts(p, opts['to_m'])
        plan_v, ok = {}, True
        for (oi, fi), vec in shifts.items():
            face = p['_fa'] if (oi, fi) == p['a'] else p['_fb']
            for v in face['verts']:
                key = (oi, v)
                have = vshift.get(key, []) + plan_v.get(key, [])
                fine, add = _compatible(have, vec)
                if not fine:
                    ok = False
                    break
                if add:
                    plan_v.setdefault(key, []).append(vec)
            if not ok:
                break
        if not ok:
            skipped.append((p, 'vertex shared with another moved pair in another direction'))
            continue
        for key, vecs in plan_v.items():
            vshift.setdefault(key, []).extend(vecs)
        used.update((p['a'], p['b']))
        p['shift_m'] = {'{}:{}'.format(*k): [round(c, 12) for c in v] for k, v in shifts.items()}
        taken.append(p)
    moves = {}
    for (oi, v), vecs in vshift.items():
        tot = (0.0, 0.0, 0.0)
        for vec in vecs:
            tot = _add(tot, vec)
        moves.setdefault(oi, {})[v] = list(tot)
    faces = {}
    for p in taken:
        for oi, fi in (p['a'], p['b']):
            faces.setdefault(oi, set()).add(fi + 1)
    return {'opts': opts, 'pairs': taken, 'moves': moves, 'skipped': skipped,
            'faces': {k: sorted(v) for k, v in faces.items()}}


def apply_moves(objects, moves):
    """New world vertex lists (metres) after the plan's shifts; the inputs are not changed."""
    out = []
    for oi, o in enumerate(objects):
        m = moves.get(oi, {})
        out.append({'verts': [list(_add(tuple(p), tuple(m[i]))) if i in m else list(p)
                              for i, p in enumerate(o['verts'])], 'faces': o['faces']})
    return out


def gap_after(objects_after, pair):
    """Gap (m) and the largest lateral shift of the pair's faces after the move (acceptance: To +- 0.01 mm)."""
    fa = face_frame([tuple(objects_after[pair['a'][0]]['verts'][i]) for i in objects_after[pair['a'][0]]['faces'][pair['a'][1]]])
    fb = face_frame([tuple(objects_after[pair['b'][0]]['verts'][i]) for i in objects_after[pair['b'][0]]['faces'][pair['b'][1]]])
    return abs(_dot(_sub(fb[1], fa[1]), fa[0]))


def pair_row(p, names):
    """JSON row of a pair for the report (names: object names by index)."""
    return {'a': [names[p['a'][0]], p['a'][1] + 1], 'b': [names[p['b'][0]], p['b'][1] + 1], 'kind': p['kind'],
            'gap_mm': round(p['gap_m'] * 1000.0, 6), 'overlap_m2': round(p['overlap_m2'], 9)}
