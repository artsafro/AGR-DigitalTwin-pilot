"""new-case: AGR Tools 0.9 (#979) UV tiles (MatID -> UDIM, UDIM tiles and slots) logic, stdlib only (branch B).

Pure logic for `udim_matid_unwrap` (udim.matid_unwrap) and `udim_slots` (udim.slots); no pymxs.

udim.slots (read). Texture names are read by the names_core grammar of E1 (`udim_of`, `texture_stem`, `VPM_MAP`,
`NPM_MAP`, `MAX_SLOTS`): a name is accepted only when names_core builds exactly the same stem back; there is no
own grammar here. Findings: `udim_gap` (tiles of one map of one slot are not 1001..1000+k without holes),
`slot_gap` (slots of one address are not 1..k), `maps_over_100` (> 100 map files in one material slot: the next
maps belong to the next slot), `slot_over_7` (SlotNumber > 7), `name_unparsed` (a map file outside the grammar is
reported, never silently skipped). Source: none measurable (new button); GeoAGR has no such check, the move to
the next slot at > 100 maps is manual there; AGR Tools 0.5.0 `tex.check`/`qa.names` checked single names only.

udim.matid_unwrap (copy). Lab L06 (docs/experiments/udim.matid_unwrap.md, jobs 20261105-125541-261291c9,
20261105-125724-29647441) measured the team script `Maf Tools.mcr` (sha256 df1a3a3e…fa05; read for the idea of
`ID -> tile` only, nothing copied, #853). Its rule ID n -> UDIM 1001 + (n-1) mod 10 + 10*floor((n-1)/10) (= 1000+n)
is kept. Fixed source defects (regression tests in tests/max_tools/test_agr_tools_uvtile.py):
M1 the user stack of a non-Editable_Poly is collapsed silently (`Maf Tools.mcr:192`) -> the source is never
   touched; the evaluated mesh is read and the UVs are written on an export copy (glue); a copy whose stack had to
   be collapsed says so in the report;
M2 every ID is normalised on its own: density differs x2 between IDs -> one px/m for every ID of the run
   (`px_per_m`, through units.SystemScale), +-2 %;
M3 the packer does not read the UVs of the Unwrap_UVW left by step 1 -> islands come from the computed mesh;
M4 the packer lays islands across UDIM borders and loses ID -> tile -> every island inside its own tile, gap
   >= padding (>= 8 px on `map_px`), an overflow is a finding with the calculation (fail-closed: no copy);
M5 the Modify panel and the current modifier are switched -> no UI state is touched (glue).
The UVs are unwrapped per face plane: faces of one ID are grouped into islands of edge-connected faces whose
normals are within `angle` degrees of the island's seed normal and projected on the seed plane (no overlap inside
an island, checked after packing).
"""
import importlib.util
import math
import re
import sys
from pathlib import Path

# ---- shared ----------------------------------------------------------------------------------------------
ID_MIN, ID_MAX = 1, 100
MAP_EXT = ('.png', '.jpg', '.jpeg', '.tga', '.tif', '.tiff', '.exr', '.bmp', '.dds', '.psd', '.tx')
MAPS_PER_SLOT = 100
SLOT_CODES = ('udim_gap', 'slot_gap', 'maps_over_100', 'slot_over_7', 'name_unparsed')


def _sibling(filename, alias):
    mod = sys.modules.get(alias)
    if mod is not None and getattr(mod, '__file__', None):
        return mod
    spec = importlib.util.spec_from_file_location(alias, Path(__file__).with_name(filename))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod


_udimtile = _sibling('udimtile_core.py', 'agr_tools_udimtile_core_uvtile')


def names():
    """names_core of E1 (read only)."""
    return _sibling('names_core.py', 'agr_tools_names_core')


def tile_of_id(mid):
    """UDIM of material ID 1..100 (1001 + (n-1) mod 10 + 10*floor((n-1)/10) = 1000 + n), else ValueError."""
    if type(mid) is not int or not ID_MIN <= mid <= ID_MAX:
        raise ValueError('material ID outside 1..100 has no UDIM tile: ' + repr(mid))
    return _udimtile.udim_of_cell((mid - 1) % 10, (mid - 1) // 10)


def tile_origin(tile):
    return _udimtile.tile_origin(tile)


# ---- udim.slots --------------------------------------------------------------------------------------------
def _basename(path):
    return str(path).replace('\\', '/').rsplit('/', 1)[-1]


def parse_texture(path):
    """{'model', 'address', 'oks', 'type', 'ground', 'map', 'role', 'slot', 'udim', 'stem'} or a reason string.

    The candidate is read from the right (slot, map token, optional Ground / OKS + type) and accepted only when
    names_core.texture_stem builds the same stem back (slot > 7 is checked with slot 1 and flagged later)."""
    nc = names()
    base = _basename(path)
    low = base.lower()
    ext = next((e for e in MAP_EXT if low.endswith(e)), None)
    stem = base[:-len(ext)] if ext else base
    udim = nc.udim_of(base)
    body = stem
    if udim is not None:
        body = stem[:-5]
    tokens = body.split('_')
    if len(tokens) < 4 or tokens[0] != 'T' or not tokens[-1].isdigit():
        return 'not T_<Address>_<Map>_<Slot>[.<UDIM>]: ' + base
    slot = int(tokens[-1])
    if slot < 1:
        return 'SlotNumber must be >= 1: ' + base
    rev_vpm = {v: k for k, v in nc.VPM_MAP.items() if v and k in ('diffuse', 'normal', 'metalness')}
    rev_npm = {v: k for k, v in nc.NPM_MAP.items() if v}
    mp = tokens[-2]
    cand = []
    if mp in rev_vpm:
        rest = tokens[1:-2]
        ground = len(rest) >= 2 and rest[-1] == 'Ground'
        addr = rest[:-1] if ground else rest
        if addr:
            obj = {'address': '_'.join(addr), 'oks': None, 'type': 'Ground' if ground else 'Main'}
            cand.append(('vpm', obj, rev_vpm[mp], ground))
    if mp in rev_npm and len(tokens) >= 5:
        kind = tokens[-3]
        rest = tokens[1:-3]
        oks = None
        if kind in ('Main', 'MainGlass') and rest and rest[-1].isdigit():
            oks, rest = rest[-1], rest[:-1]
        if rest and kind in nc.TYPES:
            obj = {'address': '_'.join(rest), 'oks': oks, 'type': kind}
            cand.append(('npm', obj, rev_npm[mp], kind.startswith('Ground')))
    for model, obj, role, ground in cand:
        probe = min(slot, nc.MAX_SLOTS)
        try:
            built = nc.texture_stem(obj, model, role, probe, udim if model == 'vpm' else None)
        except ValueError:
            continue
        want = '_'.join(tokens[:-1] + [str(probe)]) + ('.' + str(udim) if model == 'vpm' else '')
        if model == 'vpm' and udim is None:
            continue
        if model == 'npm' and udim is not None:
            continue
        if built == want:
            return {'model': model, 'address': obj['address'], 'oks': obj['oks'], 'type': obj['type'],
                    'ground': ground, 'map': mp, 'role': role, 'slot': slot, 'udim': udim, 'stem': stem}
    if mp in rev_vpm and udim is None:
        return 'VPM map without a UDIM tile (.1001..1100): ' + base
    return 'outside the names_core texture grammar (T_<Address>[_Ground]_<Diffuse|ERM|Normal>_<Slot>.<UDIM> or ' \
           'NPM T_<Address>[_NNN]_<Type>_<d|n|o|m|r>_<Slot>): ' + base


def _owner(p):
    """Material key of a parsed name: one material per address (+ OKS/type for NPM, + Ground for VPM)."""
    if p['model'] == 'vpm':
        return 'T_{}{}'.format(p['address'], '_Ground' if p['ground'] else '')
    return 'T_{}{}_{}'.format(p['address'], '_' + p['oks'] if p['oks'] else '', p['type'])


def slots_plan(objects):
    """objects: [{'key', 'name', 'files': [path]}] -> {'entries': [(key, name, [(code, detail)])], 'groups', ...}.

    No map file in the whole input is an error."""
    if not any(o['files'] for o in objects):
        raise ValueError('no map file on the selected objects')
    parsed, per_object = {}, {}
    for o in objects:
        mine = per_object.setdefault(o['key'], set())
        for f in o['files']:
            base = _basename(f)
            parsed.setdefault(base.lower(), (base, parse_texture(f)))
            mine.add(base.lower())
    group_findings = {}   # finding key -> (code, detail, set of file keys)

    def add(code, detail, files):
        group_findings.setdefault((code, detail), set()).update(files)

    owners = {}
    for key, (base, p) in parsed.items():
        if isinstance(p, str):
            add('name_unparsed', p, {key})
            continue
        owners.setdefault(_owner(p), []).append((key, p))
    groups = []
    for owner, items in sorted(owners.items()):
        slots = sorted({p['slot'] for _, p in items})
        for s in slots:
            files = [k for k, p in items if p['slot'] == s]
            row = {'material': owner, 'slot': s, 'maps': len(files), 'tiles': {}}
            if s > names().MAX_SLOTS:
                add('slot_over_7', '{}: SlotNumber {} > {}'.format(owner, s, names().MAX_SLOTS), files)
            if len(files) > MAPS_PER_SLOT:
                add('maps_over_100', '{} slot {}: {} maps > {}; the next maps go to slot {}'.format(
                    owner, s, len(files), MAPS_PER_SLOT, s + 1), files)
            for mp in sorted({p['map'] for k, p in items if p['slot'] == s}):
                keys = [(k, p['udim']) for k, p in items if p['slot'] == s and p['map'] == mp]
                tiles = sorted({u for _, u in keys if u is not None})
                row['tiles'][mp] = tiles
                if tiles:
                    want = list(range(1001, 1001 + len(tiles)))
                    if tiles != want:
                        missing = sorted(set(range(1001, max(tiles) + 1)) - set(tiles))
                        add('udim_gap', '{} {} slot {}: tiles {} miss {}'.format(
                            owner, mp, s, _ranges(tiles), _ranges(missing)), [k for k, _ in keys])
            groups.append(row)
        want = list(range(1, len(slots) + 1))
        if slots != want:
            missing = sorted(set(range(1, max(slots) + 1)) - set(slots))
            add('slot_gap', '{}: slots {} miss {}'.format(owner, slots, missing), [k for k, _ in items])
    entries = []
    for o in objects:
        mine = per_object[o['key']]
        found = []
        for (code, detail), files in sorted(group_findings.items()):
            if files & mine:
                found.append((code, detail))
        entries.append((o['key'], o['name'], found))
    names_out = [{'file': base, 'parsed': None if isinstance(p, str) else
                  {k: p[k] for k in ('model', 'address', 'map', 'slot', 'udim')}} for base, p in
                 sorted(parsed.values())]
    return {'entries': entries, 'groups': groups, 'files': names_out}


def _ranges(nums):
    nums = sorted(nums)
    if not nums:
        return '-'
    out, start, prev = [], nums[0], nums[0]
    for n in nums[1:] + [None]:
        if n is not None and n == prev + 1:
            prev = n
            continue
        out.append(str(start) if start == prev else '{}-{}'.format(start, prev))
        if n is not None:
            start = prev = n
    return ','.join(out)


# ---- udim.matid_unwrap ----------------------------------------------------------------------------------
DEFAULT_MAP_PX = 1024
PAD_MIN_PX = 8
DEFAULT_ANGLE = 10.0
DENSITY_TOL = 0.02
UNWRAP_CODES = ('id_out_of_range', 'tile_overflow', 'uv_overlap', 'degenerate_faces')


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a):
    return math.sqrt(_dot(a, a))


def _unit(a):
    n = _norm(a)
    return None if n <= 1e-15 else (a[0] / n, a[1] / n, a[2] / n)


def face_normal(pts):
    n = (0.0, 0.0, 0.0)
    for i in range(len(pts)):
        c = _cross(pts[i], pts[(i + 1) % len(pts)])
        n = (n[0] + c[0], n[1] + c[1], n[2] + c[2])
    return n


def face_area(pts):
    return 0.5 * _norm(face_normal(pts))


def _basis(n):
    """Orthonormal (x, y) on the plane of unit normal n, stable for the axis planes."""
    ax = min(range(3), key=lambda k: abs(n[k]))
    e = [0.0, 0.0, 0.0]
    e[ax] = 1.0
    x = _unit(_cross(e, n))
    y = _cross(n, x)
    return x, y


def islands(mesh, faces, angle=DEFAULT_ANGLE):
    """Edge-connected groups of `faces` whose normals are within `angle` of the group's seed normal.
    Returns [(seed unit normal, [face])]; degenerate faces (zero area) come back as [(None, [face])]."""
    cos_lim = math.cos(math.radians(angle))
    verts = mesh['vertices']
    normals = {}
    for f in faces:
        normals[f] = _unit(face_normal([verts[i] for i in mesh['faces'][f]]))
    edge_faces = {}
    for f in faces:
        idx = mesh['faces'][f]
        for k in range(len(idx)):
            e = tuple(sorted((idx[k], idx[(k + 1) % len(idx)])))
            edge_faces.setdefault(e, []).append(f)
    seen, out = set(), []
    for f in faces:
        if f in seen:
            continue
        if normals[f] is None:
            seen.add(f)
            out.append((None, [f]))
            continue
        seed = normals[f]
        group, stack = [], [f]
        seen.add(f)
        while stack:
            g = stack.pop()
            group.append(g)
            idx = mesh['faces'][g]
            for k in range(len(idx)):
                e = tuple(sorted((idx[k], idx[(k + 1) % len(idx)])))
                for h in edge_faces[e]:
                    if h in seen or normals[h] is None:
                        continue
                    if _dot(normals[h], seed) >= cos_lim:
                        seen.add(h)
                        stack.append(h)
        out.append((seed, sorted(group)))
    return out


def _project(mesh, seed, faces, unit):
    """Corner UV (metres on the seed plane) of every face corner: {(face, corner): (x, y)}."""
    x, y = _basis(seed)
    verts = mesh['vertices']
    out = {}
    for f in faces:
        for c, vi in enumerate(mesh['faces'][f]):
            p = verts[vi]
            out[(f, c)] = (_dot(p, x) * unit, _dot(p, y) * unit)
    return out


def _min_box(pts):
    """Rotation (cos, sin) giving the smallest axis box of the points among their hull edge directions."""
    hull = _hull(list(set(pts)))
    best = (None, 1.0, 0.0)
    cands = [(1.0, 0.0)]
    for i in range(len(hull)):
        a, b = hull[i], hull[(i + 1) % len(hull)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy)
        if ln > 1e-12:
            cands.append((dx / ln, dy / ln))
    for c, s in cands:
        xs = [p[0] * c + p[1] * s for p in hull]
        ys = [-p[0] * s + p[1] * c for p in hull]
        area = (max(xs) - min(xs)) * (max(ys) - min(ys))
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        if h > w:  # lie flat: the longer side along U
            c, s = -s, c
            area = w * h
        if best[0] is None or area < best[0] - 1e-12:
            best = (area, c, s)
    return best[1], best[2]


def _hull(pts):
    pts = sorted(pts)
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _shelf(rects, side, gap):
    """Shelf-pack rects [(w, h, key)] into a side x side square, gap between and around. {key: (x, y)} or None."""
    placed, x, y, shelf = {}, gap, gap, 0.0
    for w, h, key in sorted(rects, key=lambda r: (-r[1], -r[0], r[2])):
        if w + 2 * gap > side + 1e-12 or h + 2 * gap > side + 1e-12:
            return None
        if x + w + gap > side + 1e-12:
            x, y, shelf = gap, y + shelf + gap, 0.0
        if y + h + gap > side + 1e-12:
            return None
        placed[key] = (x, y)
        x += w + gap
        shelf = max(shelf, h)
    return placed


def unwrap_groups(mesh, unit=1.0, angle=DEFAULT_ANGLE):
    """Per ID: islands with their corner coordinates in metres, rotated to their smallest box.

    Returns ({id: [{'faces', 'corners': {(f, c): (x, y)}, 'w', 'h', 'area3'}]}, {id: [degenerate faces]})."""
    by_id = {}
    for f, mid in enumerate(mesh['ids']):
        by_id.setdefault(int(mid), []).append(f)
    out, degenerate = {}, {}
    for mid, faces in sorted(by_id.items()):
        isl = []
        for seed, group in islands(mesh, faces, angle):
            if seed is None:
                degenerate.setdefault(mid, []).extend(group)
                continue
            corners = _project(mesh, seed, group, unit)
            c, s = _min_box(list(corners.values()))
            rot = {k: (p[0] * c + p[1] * s, -p[0] * s + p[1] * c) for k, p in corners.items()}
            xs = [p[0] for p in rot.values()]
            ys = [p[1] for p in rot.values()]
            x0, y0 = min(xs), min(ys)
            rot = {k: (p[0] - x0, p[1] - y0) for k, p in rot.items()}
            area3 = sum(face_area([[v * unit for v in mesh['vertices'][i]] for i in mesh['faces'][f]]) for f in group)
            isl.append({'faces': group, 'corners': rot, 'w': max(xs) - x0, 'h': max(ys) - y0, 'area3': area3})
        out[mid] = isl
    return out, degenerate


def _fits(isl, px_per_m, map_px, pad_px):
    s = px_per_m / float(map_px)   # UV per metre
    gap = pad_px / float(map_px)
    rects = [(i['w'] * s, i['h'] * s, k) for k, i in enumerate(isl)]
    return _shelf(rects, 1.0, gap)


def max_density(isl, map_px, pad_px, hi=1e6):
    """Largest px/m (to 1e-4 relative) at which the islands of one ID fit their tile, or 0."""
    lo = 0.0
    if not isl:
        return hi
    hi = min(hi, (map_px - 2 * pad_px) / max(max(i['w'], i['h']) for i in isl))
    if hi <= 0:
        return 0.0
    if _fits(isl, hi, map_px, pad_px) is not None:
        return hi
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if _fits(isl, mid, map_px, pad_px) is not None:
            lo = mid
        else:
            hi = mid
        if hi - lo <= 1e-4 * hi:
            break
    return lo


def unwrap_plan(mesh, unit=1.0, px_per_m=None, map_px=DEFAULT_MAP_PX, pad_px=PAD_MIN_PX, angle=DEFAULT_ANGLE):
    """Plan of one object. px_per_m None: the largest common density at which every ID fits (one value for all
    IDs, M2). A given px_per_m that does not fit an ID is `tile_overflow` with the calculation (M4).

    Returns {'rows': per-ID rows, 'findings': [(code, faces 1-based, detail)], 'uvs', 'face_uvs', 'px_per_m',
    'ok': bool}. uvs/face_uvs are None when the plan is not ok (fail-closed: the copy is not written)."""
    if type(map_px) is not int or map_px < 64:
        raise ValueError('map_px must be an integer >= 64: ' + repr(map_px))
    if type(pad_px) is not int or pad_px < PAD_MIN_PX:
        raise ValueError('padding must be an integer >= {} px: {!r}'.format(PAD_MIN_PX, pad_px))
    if not 0.0 < float(angle) < 90.0:
        raise ValueError('angle must be in (0, 90) degrees')
    if not mesh['faces']:
        raise ValueError('mesh has no faces')
    if len(mesh['ids']) != len(mesh['faces']):
        raise ValueError('faces and material IDs differ in count')
    groups, degenerate = unwrap_groups(mesh, unit, angle)
    findings = []
    bad_ids = sorted(m for m in groups if not ID_MIN <= m <= ID_MAX)
    for m in bad_ids:
        faces = [f + 1 for f in range(len(mesh['ids'])) if int(mesh['ids'][f]) == m]
        findings.append(('id_out_of_range', faces, 'material ID {} outside 1..100 has no UDIM tile'.format(m)))
    for m, faces in sorted(degenerate.items()):
        findings.append(('degenerate_faces', [f + 1 for f in faces],
                         'ID {}: {} face(s) of zero area get no UV island'.format(m, len(faces))))
    good = {m: isl for m, isl in groups.items() if ID_MIN <= m <= ID_MAX and isl}
    caps = {m: max_density(isl, map_px, pad_px) for m, isl in good.items()}
    if px_per_m is None:
        density = min(caps.values()) if caps else 0.0
        density = math.floor(density * 1000.0) / 1000.0
    else:
        density = float(px_per_m)
        if not math.isfinite(density) or density <= 0:
            raise ValueError('px_per_m must be a positive number: ' + repr(px_per_m))
    rows = []
    for m, isl in sorted(good.items()):
        area3 = sum(i['area3'] for i in isl)
        need = sum((i['w'] * density + 2 * pad_px) * (i['h'] * density + 2 * pad_px) for i in isl)
        row = {'id': m, 'tile': tile_of_id(m), 'faces': sum(len(i['faces']) for i in isl), 'islands': len(isl),
               'area_m2': round(area3, 9), 'max_px_per_m': round(caps[m], 4)}
        if _fits(isl, density, map_px, pad_px) is None:
            findings.append(('tile_overflow', [f + 1 for i in isl for f in i['faces']],
                             'ID {} -> {}: {} island(s) of {:.4g} m2 need about {:.0f} px2 at {:.4g} px/m with '
                             '{} px padding; the {} px tile holds {} px2; it fits up to {:.4g} px/m'.format(
                                 m, tile_of_id(m), len(isl), area3, need, density, pad_px, map_px, map_px * map_px,
                                 caps[m])))
            row['fits'] = False
        else:
            row['fits'] = True
        rows.append(row)
    ok = not any(c in ('tile_overflow', 'id_out_of_range', 'degenerate_faces') for c, _, _ in findings) and bool(good)
    result = {'rows': rows, 'findings': findings, 'px_per_m': round(density, 6), 'map_px': map_px,
              'pad_px': pad_px, 'ok': ok, 'uvs': None, 'face_uvs': None}
    if not ok:
        return result
    s = density / float(map_px)
    uvs, face_uvs = [], [None] * len(mesh['faces'])
    for m, isl in sorted(good.items()):
        u0, v0 = tile_origin(tile_of_id(m))
        placed = _fits(isl, density, map_px, pad_px)
        for k, i in enumerate(isl):
            ox, oy = placed[k]
            for f in i['faces']:
                row = []
                for c in range(len(mesh['faces'][f])):
                    x, y = i['corners'][(f, c)]
                    uvs.append((u0 + ox + x * s, v0 + oy + y * s))
                    row.append(len(uvs) - 1)
                face_uvs[f] = row
    result['uvs'], result['face_uvs'] = uvs, face_uvs
    measured = measure_layout(mesh, uvs, face_uvs, unit, map_px)
    for r in rows:
        r.update(measured['ids'][r['id']])
    if measured['overlaps']:
        result['findings'].append(('uv_overlap', sorted({f for pair in measured['overlaps'] for f in pair}),
                                   '{} overlapping face pair(s) after packing'.format(len(measured['overlaps']))))
        result['ok'] = False
        result['uvs'] = result['face_uvs'] = None
    return result


def _tri(poly):
    return [(poly[0], poly[i], poly[i + 1]) for i in range(1, len(poly) - 1)]


def _area2(a, b, c):
    return 0.5 * ((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1]))


def _seg_cross(p1, p2, q1, q2):
    def o(a, b, c):
        v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        return 0 if abs(v) < 1e-14 else (1 if v > 0 else -1)
    return o(p1, p2, q1) * o(p1, p2, q2) < 0 and o(q1, q2, p1) * o(q1, q2, p2) < 0


def _inside(p, t):
    d1, d2, d3 = _area2(t[0], t[1], p), _area2(t[1], t[2], p), _area2(t[2], t[0], p)
    eps = 1e-14
    return (d1 > eps and d2 > eps and d3 > eps) or (d1 < -eps and d2 < -eps and d3 < -eps)


def _tris_overlap(a, b):
    for i in range(3):
        for j in range(3):
            if _seg_cross(a[i], a[(i + 1) % 3], b[j], b[(j + 1) % 3]):
                return True
    ca = ((a[0][0] + a[1][0] + a[2][0]) / 3, (a[0][1] + a[1][1] + a[2][1]) / 3)
    cb = ((b[0][0] + b[1][0] + b[2][0]) / 3, (b[0][1] + b[1][1] + b[2][1]) / 3)
    return _inside(ca, b) or _inside(cb, a)


def overlaps(uvs, face_uvs, faces=None):
    """Pairs (f1, f2) of 1-based faces whose UV interiors overlap (grid-bucketed)."""
    faces = range(len(face_uvs)) if faces is None else faces
    tris, boxes = [], {}
    for f in faces:
        poly = [uvs[i] for i in face_uvs[f]]
        for t in _tri(poly):
            if abs(_area2(*t)) < 1e-16:
                continue
            tris.append((f, t))
    if not tris:
        return []
    cell = max(1e-6, math.sqrt(sum(abs(_area2(*t)) for _, t in tris) / len(tris)) * 2)
    grid = {}
    for k, (f, t) in enumerate(tris):
        xs, ys = [p[0] for p in t], [p[1] for p in t]
        for gx in range(int(math.floor(min(xs) / cell)), int(math.floor(max(xs) / cell)) + 1):
            for gy in range(int(math.floor(min(ys) / cell)), int(math.floor(max(ys) / cell)) + 1):
                grid.setdefault((gx, gy), []).append(k)
    found = set()
    for bucket in grid.values():
        for i in range(len(bucket)):
            for j in range(i + 1, len(bucket)):
                fa, ta = tris[bucket[i]]
                fb, tb = tris[bucket[j]]
                if fa == fb or (min(fa, fb) + 1, max(fa, fb) + 1) in found:
                    continue
                if _tris_overlap(ta, tb):
                    found.add((min(fa, fb) + 1, max(fa, fb) + 1))
    return sorted(found)


def measure_layout(mesh, uvs, face_uvs, unit=1.0, map_px=DEFAULT_MAP_PX):
    """Readback of a layout: per ID tiles of its faces, px/m (sqrt of pixel area / metric area), islands outside
    their tile, overlaps. {'ids': {id: {...}}, 'overlaps': [(f1, f2)]}."""
    per = {}
    for f, mid in enumerate(mesh['ids']):
        mid = int(mid)
        g = per.setdefault(mid, {'uv_area': 0.0, 'area': 0.0, 'outside': [], 'tiles': set()})
        poly2 = [uvs[i] for i in face_uvs[f]]
        poly3 = [[v * unit for v in mesh['vertices'][i]] for i in mesh['faces'][f]]
        g['uv_area'] += abs(sum(_area2(*t) for t in _tri(poly2)))
        g['area'] += face_area(poly3)
        cu = sum(p[0] for p in poly2) / len(poly2)
        cv = sum(p[1] for p in poly2) / len(poly2)
        fu, fv = math.floor(cu), math.floor(cv)
        tile = 1001 + fu + 10 * fv if 0 <= fu <= 9 and fv >= 0 else None
        g['tiles'].add(tile)
        if tile is not None:
            for u, v in poly2:
                if not (fu - 1e-9 <= u <= fu + 1 + 1e-9 and fv - 1e-9 <= v <= fv + 1 + 1e-9):
                    g['outside'].append(f + 1)
                    break
        if ID_MIN <= mid <= ID_MAX and tile != tile_of_id(mid):
            g['outside'].append(f + 1)
    ids = {}
    for mid, g in per.items():
        dens = math.sqrt(g['uv_area'] / g['area']) * map_px if g['area'] > 0 else None
        ids[mid] = {'px_per_m_after': None if dens is None else round(dens, 4),
                    'tiles_after': sorted(t for t in g['tiles'] if t is not None),
                    'outside_tile': sorted(set(g['outside']))}
    by_tile = {}
    for f, mid in enumerate(mesh['ids']):
        by_tile.setdefault(int(mid), []).append(f)
    pairs = []
    for mid, faces in by_tile.items():
        pairs.extend(overlaps(uvs, face_uvs, faces))
    return {'ids': ids, 'overlaps': sorted(set(pairs))}
