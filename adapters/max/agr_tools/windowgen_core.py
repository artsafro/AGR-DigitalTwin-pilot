"""new-case: AGR Tools 1.0 (#1024) window type generator logic, stdlib only; owned by branch J (improve/issue-1024-windows).

Pure logic for `win_generate` (win.generate) and the window meshes win.place instantiates; no pymxs.

Contract K2 (#1024) with the owner answers 06.11.2026 and lab L10 (docs/experiments/win.generate.md):
* [D322] supersedes the seating part of [D204] for every site: use an explicit Revit-type
  frame_profile_m when supplied, otherwise the measured FAMILY profile in standard.json;
* glass/grille panels overlap the light 15..20 mm per edge (default 20) at real frame mid-depth;
  glass is a separate part/object; NPM opaque atlas planes remain unchanged;
* optional interiors are independent set-back boxes around the opening (+44 mm sides, +130 mm head/sill),
  never frame extrusions or frame material; grille openings refuse interiors; existing scenes are not edited;
* the frame follows the fields of the record (`panes_m` glass, `opaque_m` opaque infill [x0, z0, x1, z1] from the
  bottom left of the opening); every field edge is moved onto the standard: an outer edge to the frame face, an
  edge facing a neighbour field to half a mullion from the middle of the gap;
* type quality is automatic (`quality`): not typed, no fields, size outside the role limits, fields outside the
  frame or overlapping, a degenerate glass (< 0.1 m), occurrences 0, or `applicable: false` in the standard
  (WT-02, L10) -> `quarantine` (kept, never offered); the same subdivision -> `duplicate` with `same_as`
  (WT-07 and WT-10 differ: owner 06.11, not merged);
* the face axis is stored per type (standard.json `types` / quality report); generated meshes face -Y.

Mesh frame of a generated type: x 0..W (right as seen from the street), z 0..H (up), y depth: the frame face at
y = 0 looks to -Y, the back at y = depth. Material IDs as Win_Typical.max: 1 face and sides, 4 back of the frame,
5 opaque infill, 10 glass.
"""
import json
import math
import struct
import zlib
from typing import cast

STANDARD_SCHEMA = 'window-standard/1'
REPORT_SCHEMA = 'window-quality/1'
DRAFT_SCHEMA = 'window-type-draft/1'
FACE_AXES = ('-y', '+y')
MAT_FACE, MAT_BACK, MAT_OPAQUE, MAT_GLASS = 1, 4, 5, 10
MAT_GRILLE, MAT_CAPSULE = 11, 12
VERDICTS = ('pass', 'quarantine', 'duplicate')
_FAMILY_KEYS = {'face_m', 'face_top_m', 'face_bottom_m', 'impost_m', 'depth_m', 'glass_from_face_m'}
_EPS = 1e-6
LIBRARY_FILES = ('window_types.json', 'standard.json')


# ---- library files -------------------------------------------------------------------------------------------
def library_dir(option=None, environ=None, here=None):
    """Folder with window_types.json and standard.json: the option, else $AGR_TOOLS_REPO/library/windows, else the
    repository of this module (adapters/max/agr_tools -> library/windows). The installed package has no library:
    an error names the option to give."""
    import os
    environ = os.environ if environ is None else environ
    here = os.path.abspath(here or __file__)
    cands = []
    if option:  # an explicit folder is the only candidate: no silent fallback to another library
        if all(os.path.isfile(os.path.join(option, f)) for f in LIBRARY_FILES):
            return os.path.abspath(option)
        raise ValueError('options.library: no window_types.json + standard.json in ' + str(option))
    if environ.get('AGR_TOOLS_REPO'):
        cands.append(os.path.join(environ['AGR_TOOLS_REPO'], 'library', 'windows'))
    cands.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(here)))),
                              'library', 'windows'))
    for c in cands:
        if all(os.path.isfile(os.path.join(c, f)) for f in LIBRARY_FILES):
            return os.path.abspath(c)
    raise ValueError('window library not found: give options.library (folder of window_types.json and standard.json)')


def load_library(folder):
    """{'types': [...], 'by_id': {...}, 'standard': {...}, 'sha256': {file: hex}, 'folder'} of a library folder."""
    import hashlib
    import os
    raw = {}
    for f in LIBRARY_FILES:
        with open(os.path.join(folder, f), 'rb') as fh:
            raw[f] = fh.read()
    types = json.loads(raw['window_types.json'].decode('utf-8'))['types']
    ids = [t['id'] for t in types]
    if len(ids) != len(set(ids)):
        raise ValueError('window_types.json: duplicate ids')
    standard = load_standard(json.loads(raw['standard.json'].decode('utf-8')))
    return {'types': types, 'by_id': {t['id']: t for t in types}, 'standard': standard, 'folder': folder,
            'sha256': {f: hashlib.sha256(b).hexdigest() for f, b in raw.items()}}


# ---- standard ------------------------------------------------------------------------------------------------
def _num(v, what, allow_none=False, positive=True):
    if v is None and allow_none:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or (positive and v <= 0):
        raise ValueError('{} must be a finite number{}: {!r}'.format(what, ' > 0' if positive else '', v))
    return float(v)


def load_standard(doc):
    """Validated standard.json (dict). Unknown family references and bad numbers are errors."""
    if not isinstance(doc, dict) or doc.get('schema') != STANDARD_SCHEMA:
        raise ValueError('standard.json: schema must be ' + STANDARD_SCHEMA)
    fams = doc.get('families')
    if not isinstance(fams, dict) or not fams:
        raise ValueError('standard.json: families missing')
    for name, f in fams.items():
        missing = _FAMILY_KEYS - set(f)
        if missing:
            raise ValueError('standard.json family {}: missing {}'.format(name, sorted(missing)))
        for k in _FAMILY_KEYS:
            _num(f[k], '{}.{}'.format(name, k), allow_none=(k == 'face_bottom_m'))
        if f['glass_from_face_m'] >= f['depth_m'] + 0.05:
            raise ValueError('standard.json family {}: glass behind the frame'.format(name))
    for role, fam in (doc.get('role_family') or {}).items():
        if fam not in fams:
            raise ValueError('role_family {} -> unknown family {}'.format(role, fam))
    for tid, t in (doc.get('types') or {}).items():
        if 'family' in t and t['family'] not in fams:
            raise ValueError('type {} -> unknown family {}'.format(tid, t['family']))
        if t.get('face_axis', '-y') not in FACE_AXES:
            raise ValueError('type {}: face_axis must be one of {}'.format(tid, FACE_AXES))
    if doc.get('face_axis_default', '-y') not in FACE_AXES:
        raise ValueError('face_axis_default must be one of {}'.format(FACE_AXES))
    crit = doc.get('criteria') or {}
    for k in ('min_glass_side_m', 'apply_tol_m', 'same_tol_m', 'neighbour_gap_m'):
        _num(crit.get(k), 'criteria.' + k)
    return doc


def family_of(entry, standard):
    """Family profile with explicit source-type dimensions taking precedence [D322]."""
    t = (standard.get('types') or {}).get(entry.get('id'), {})
    name = t.get('family') or (standard.get('role_family') or {}).get(entry.get('role'))
    if name not in standard['families']:
        raise ValueError('unmapped window role/family: {}'.format(entry.get('role')))
    fam = dict(standard['families'][name])
    if 'frame_profile_m' in entry:
        profile = entry['frame_profile_m']
        allowed = _FAMILY_KEYS - {'glass_from_face_m'}
        if not isinstance(profile, dict) or not {'face_m', 'depth_m', 'impost_m'} <= set(profile):
            raise ValueError('frame_profile_m requires face_m, depth_m and impost_m from the source type')
        if set(profile) - allowed:
            raise ValueError('unknown frame_profile_m keys: {}'.format(sorted(set(profile) - allowed)))
        for k, v in profile.items():
            _num(v, 'frame_profile_m.' + k)
        fam.update(profile)
        fam['face_top_m'] = profile.get('face_top_m', profile['face_m'])
        fam['face_bottom_m'] = profile.get('face_bottom_m', profile['face_m'])
    return name, fam


def face_axis(entry, standard):
    """Face axis of a type mesh as stored in the library ('-y' for every generated type and Win_Typical)."""
    t = (standard.get('types') or {}).get(entry.get('id'), {})
    return t.get('face_axis') or standard.get('face_axis_default') or '-y'


# ---- fields --------------------------------------------------------------------------------------------------
def fields(entry):
    """[(kind 'glass'|'opaque'|'grille', [x0, z0, x1, z1])] of a record, glass first."""
    out = []
    for kind, key in (('glass', 'panes_m'), ('opaque', 'opaque_m'), ('grille', 'grilles_m')):
        for r in entry.get(key) or ():
            if not isinstance(r, (list, tuple)) or len(r) != 4:
                raise ValueError('{} must contain four-coordinate rectangles'.format(key))
            x0, z0, x1, z1 = (cast(float, _num(c, key, positive=False)) for c in r)
            out.append((kind, [min(x0, x1), min(z0, z1), max(x0, x1), max(z0, z1)]))
    return out


def _overlap(a, b, axis):
    lo, hi = (1, 3) if axis == 'z' else (0, 2)
    return min(a[hi], b[hi]) - max(a[lo], b[lo])


def _area_overlap(a, b):
    return max(0.0, _overlap(a, b, 'x')) * max(0.0, _overlap(a, b, 'z'))


def standardize(entry, family, criteria):
    """Fields moved onto the family standard. Returns {'fields': [(kind, rect)], 'deviation_m': max edge move}."""
    W, H = float(entry['width_m']), float(entry['height_m'])
    src = fields(entry)
    gap = float(criteria['neighbour_gap_m'])
    snap = float(criteria.get('outer_snap_m', 0.15))
    half = family['impost_m'] / 2.0
    new = []
    for i, (kind, r) in enumerate(src):
        others = [q for j, (_, q) in enumerate(src) if j != i]
        left = [q[2] for q in others if q[2] <= r[0] + _EPS and r[0] - q[2] <= gap and _overlap(q, r, 'z') > 0.01]
        right = [q[0] for q in others if q[0] >= r[2] - _EPS and q[0] - r[2] <= gap and _overlap(q, r, 'z') > 0.01]
        below = [q[3] for q in others if q[3] <= r[1] + _EPS and r[1] - q[3] <= gap and _overlap(q, r, 'x') > 0.01]
        above = [q[1] for q in others if q[1] >= r[3] - _EPS and q[1] - r[3] <= gap and _overlap(q, r, 'x') > 0.01]
        # an edge facing a neighbour: half a mullion from the middle of the gap; an edge at the frame (within
        # outer_snap): the frame face; any other edge (a field facing an empty bay) stays where the record has it
        x0 = (r[0] + max(left)) / 2.0 + half if left else (family['face_m'] if r[0] <= snap else r[0])
        x1 = (r[2] + min(right)) / 2.0 - half if right else (W - family['face_m'] if W - r[2] <= snap else r[2])
        if below:
            z0 = (r[1] + max(below)) / 2.0 + half
        elif r[1] <= snap and family['face_bottom_m'] is not None:
            z0 = family['face_bottom_m']
        else:
            z0 = r[1]
        z1 = (r[3] + min(above)) / 2.0 - half if above else (H - family['face_top_m'] if H - r[3] <= snap else r[3])
        new.append([x0, z0, x1, z1])
    # mullions taken from different neighbour pairs can cross at an L junction: the fields of such a pair keep
    # their record edges (the sheet shows it); repeated until no two fields overlap (the record has no overlap)
    for _ in range(len(new) + 1):
        bad = {k for i in range(len(new)) for j in range(i + 1, len(new))
               if _area_overlap(new[i], new[j]) > 1e-9 for k in (i, j)}
        if not bad:
            break
        for k in bad:
            new[k] = list(src[k][1])
    out = [(kind, [round(c, 6) for c in n]) for (kind, _), n in zip(src, new)]
    dev = max([max(abs(a - b) for a, b in zip(n, r)) for n, (_, r) in zip(new, src)] or [0.0])
    return {'fields': out, 'deviation_m': round(dev, 6)}


def _same_rects(pa, pb, tol):
    if len(pa) != len(pb):
        return False
    left = list(pb)
    for p in pa:
        hit = next((q for q in left if all(abs(u - v) <= tol for u, v in zip(p, q))), None)
        if hit is None:
            return False
        left.remove(hit)
    return True


def same_subdivision(a, b, tol=0.002):
    """Same size and the same glass and opaque fields, one to one within tol (metres)."""
    if abs(a['width_m'] - b['width_m']) > tol or abs(a['height_m'] - b['height_m']) > tol:
        return False
    fa, fb = fields(a), fields(b)
    for kind in ('glass', 'opaque', 'grille'):
        if not _same_rects([r for k, r in fa if k == kind], [r for k, r in fb if k == kind], tol):
            return False
    return True


def quality(entry, standard):
    """Automatic criteria of K2 -> {'status': 'ok'|'quarantine', 'why': [...], 'notes': [...], 'family',
    'face_axis', 'deviation_mm'}."""
    crit = standard['criteria']
    fam_name, fam = family_of(entry, standard)
    why, notes = [], []
    over = (standard.get('types') or {}).get(entry.get('id'), {})
    if over.get('applicable') is False:
        why.append(over.get('why') or 'стандартный профиль неприменим')
    if not entry.get('typed', True):
        why.append('тип не типизирован (typed: false)')
    src = fields(entry)
    W, H = entry.get('width_m'), entry.get('height_m')
    if not src:
        why.append('нет разбивки: panes_m и opaque_m пусты')
    for index, (kind, rect) in enumerate(src):
        if rect[2] - rect[0] <= _EPS or rect[3] - rect[1] <= _EPS:
            why.append('degenerate {} field {}'.format(kind, index))
    lim = (standard.get('limits_m') or {}).get(entry.get('role'))
    if lim and W and H and not (lim['w'][0] <= W <= lim['w'][1] and lim['h'][0] <= H <= lim['h'][1]):
        why.append('размер {:.3f} x {:.3f} м вне пределов роли {}'.format(W, H, entry.get('role')))
    for k, r in src:
        if r[0] < -0.001 or r[1] < -0.001 or r[2] > W + 0.001 or r[3] > H + 0.001:
            why.append('поле {} выходит за габарит'.format([round(c, 3) for c in r]))
            break
    if any(_area_overlap(a, b) > 1e-6 for i, (_, a) in enumerate(src) for _, b in src[i + 1:]):
        why.append('поля исходника перекрываются')
    occ = (entry.get('source') or {}).get('occurrences')
    if occ is None:
        notes.append('occurrences не посчитаны (библиотечный источник)')
    elif occ < crit.get('occurrences_min', 1):
        why.append('тип не встречается (occurrences {})'.format(occ))
    dev = None
    if src and not why:
        st = standardize(entry, fam, crit)
        dev = round(st['deviation_m'] * 1000, 1)
        sf = st['fields']
        if any(r[2] - r[0] < crit['min_glass_side_m'] or r[3] - r[1] < crit['min_glass_side_m']
               for k, r in sf if k == 'glass'):
            why.append('вырожденное стекло по стандарту (сторона < {} м)'.format(crit['min_glass_side_m']))
        if any(_area_overlap(a, b) > 1e-6 for i, (_, a) in enumerate(sf) for _, b in sf[i + 1:]):
            why.append('поля по стандарту перекрываются')
        if st['deviation_m'] > crit['apply_tol_m']:
            notes.append('поля сдвигаются на {} мм — смотреть на листе «было → стало»'.format(dev))
    return {'status': 'quarantine' if why else 'ok', 'why': why, 'notes': notes, 'family': fam_name,
            'face_axis': face_axis(entry, standard), 'deviation_mm': dev}


def library_report(types, standard):
    """Report of the whole library: one row per type {id, verdict pass|quarantine|duplicate, why, notes, same_as,
    family, face_axis, deviation_mm}. Duplicates: an explicit `same_as`, or the same subdivision as an earlier
    non-quarantined type (same_tol_m). Rows keep the library order."""
    standard = load_standard(standard)
    tol = standard['criteria']['same_tol_m']
    rows, canon = [], []
    by_id = {t['id']: t for t in types}
    for t in types:
        q = quality(t, standard)
        row = {'id': t['id'], 'role': t.get('role'), 'verdict': 'pass', 'why': q['why'], 'notes': q['notes'],
               'same_as': None, 'family': q['family'], 'face_axis': q['face_axis'], 'deviation_mm': q['deviation_mm'],
               'library_status': t.get('status')}
        if q['status'] == 'quarantine':
            row['verdict'] = 'quarantine'
        else:
            first = t.get('same_as') if t.get('same_as') in by_id else None
            if first is None:
                first = next((c['id'] for c in canon if same_subdivision(c, t, tol)), None)
            if first is not None:
                row['verdict'], row['same_as'] = 'duplicate', first
                row['why'] = ['та же разбивка, что у {}'.format(first)]
            else:
                canon.append(t)
        rows.append(row)
    counts = {v: sum(r['verdict'] == v for r in rows) for v in VERDICTS}
    return {'schema': REPORT_SCHEMA, 'standard': standard.get('source', {}).get('sha256'), 'counts': counts,
            'types': rows}


def offerable(report, statuses=('confirmed', 'unconfirmed')):
    """Ids a placement or an agent may offer: verdict pass (never quarantine or a duplicate) and a library status
    among `statuses`."""
    return [r['id'] for r in report['types'] if r['verdict'] == 'pass' and r.get('library_status') in statuses]


# ---- mesh ----------------------------------------------------------------------------------------------------
class _Builder:
    def __init__(self):
        self.verts, self.key, self.faces, self.mat_ids = [], {}, [], []

    def v(self, p):
        k = tuple(round(c, 7) for c in p)
        if k not in self.key:
            self.key[k] = len(self.verts)
            self.verts.append([k[0], k[1], k[2]])
        return self.key[k]

    def quad(self, pts, mat, want):
        ids = [self.v(p) for p in pts]
        a, b, c = (self.verts[i] for i in ids[:3])
        n = ((b[1] - a[1]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[1] - a[1]),
             (b[2] - a[2]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[2] - a[2]),
             (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))
        if n[0] * want[0] + n[1] * want[1] + n[2] * want[2] < 0:
            ids.reverse()
        self.faces.append(ids)
        self.mat_ids.append(mat)
        return len(self.faces) - 1


def build_type(entry, standard, options=None):
    """One window type mesh by the library standard (K2).

    entry: a record of library/windows/window_types.json (id, role, width_m, height_m, panes_m, opaque_m, ...);
    standard: library/windows/standard.json (load_standard); options: variant ('vpm'|'npm'),
    infill_overlap_m (15..20 mm), interior (explicit setback_m > frame depth and depth_m > 20 mm).
    Source frame_profile_m: required face_m/depth_m/impost_m, optional face_top_m/face_bottom_m.
    Interiors require glass-only openings; split mixed grille/glass openings before requesting interiors.
    Returns {'verts': [[x, y, z]...] metres in the type frame, 'faces': [[i...]...] (quads), 'mat_ids': [...],
    'parts': {'frame': [face idx], 'glass': [face idx]}, 'face_axis_m': y of the frame face (0.0),
    'face_axis': '-y', 'depth_m', 'frame_mid_m', 'glass_y_m', 'size_m': [W, depth, H], 'family', 'fields',
    'status': 'ok'|'quarantine', 'why': [str]}."""
    standard = load_standard(standard)
    opts = dict(options or {})
    variant = opts.pop('variant', 'vpm')
    overlap = _num(opts.pop('infill_overlap_m', 0.020), 'infill_overlap_m')
    if overlap is None or not 0.015 <= overlap <= 0.020:
        raise ValueError('infill_overlap_m must be within 15..20 mm')
    interior = opts.pop('interior', None)
    if opts or variant not in ('vpm', 'npm'):
        raise ValueError('build_type options: {variant: vpm|npm}')
    W, H = _num(entry.get('width_m'), 'width_m'), _num(entry.get('height_m'), 'height_m')
    fam_name, fam = family_of(entry, standard)
    q = quality(entry, standard)
    b = _Builder()
    parts = {'frame': [], 'glass': [], 'grille': [], 'capsule': []}
    dropped_fields = []
    depth = fam['depth_m']
    gy = depth / 2.0  # [D322]: general standard, supersedes the D204 glass offset
    st = standardize(entry, fam, standard['criteria']) if fields(entry) else {'fields': [], 'deviation_m': 0.0}
    seat = room = 0.0
    if interior is not None:
        if variant != 'vpm' or not any(k == 'glass' for k, _ in st['fields']) or any(k == 'grille' for k, _ in st['fields']):
            raise ValueError('interior requires a glazed VPM opening; no capsule behind a grille (split mixed openings)')
        if not isinstance(interior, dict) or set(interior) != {'setback_m', 'depth_m'}:
            raise ValueError('interior requires explicit setback_m and depth_m')
        seat = cast(float, _num(interior['setback_m'], 'interior.setback_m'))
        room = cast(float, _num(interior['depth_m'], 'interior.depth_m'))
        if seat <= depth or room <= 0.020:
            raise ValueError('interior must start behind the frame and have depth > 20 mm')
    if variant == 'npm':
        parts['frame'].append(b.quad([(0, 0, 0), (W, 0, 0), (W, 0, H), (0, 0, H)], MAT_FACE, (0, -1, 0)))
    else:
        holes = [r for _, r in st['fields']]
        xs = sorted({0.0, W} | {round(min(max(c, 0.0), W), 7) for r in holes for c in (r[0], r[2])})
        zs = sorted({0.0, H} | {round(min(max(c, 0.0), H), 7) for r in holes for c in (r[1], r[3])})

        def solid(i, j):
            if i < 0 or j < 0 or i >= len(xs) - 1 or j >= len(zs) - 1:
                return False
            cx, cz = (xs[i] + xs[i + 1]) / 2, (zs[j] + zs[j + 1]) / 2
            return not any(r[0] < cx < r[2] and r[1] < cz < r[3] for r in holes)

        for i in range(len(xs) - 1):
            for j in range(len(zs) - 1):
                if not solid(i, j):
                    continue
                x0, x1, z0, z1 = xs[i], xs[i + 1], zs[j], zs[j + 1]
                parts['frame'].append(b.quad([(x0, 0, z0), (x1, 0, z0), (x1, 0, z1), (x0, 0, z1)], MAT_FACE, (0, -1, 0)))
                parts['frame'].append(b.quad([(x0, depth, z0), (x1, depth, z0), (x1, depth, z1), (x0, depth, z1)],
                                             MAT_BACK, (0, 1, 0)))
                for (di, dj), pts, want in (
                        ((-1, 0), [(x0, 0, z0), (x0, depth, z0), (x0, depth, z1), (x0, 0, z1)], (-1, 0, 0)),
                        ((1, 0), [(x1, 0, z0), (x1, depth, z0), (x1, depth, z1), (x1, 0, z1)], (1, 0, 0)),
                        ((0, -1), [(x0, 0, z0), (x1, 0, z0), (x1, depth, z0), (x0, depth, z0)], (0, 0, -1)),
                        ((0, 1), [(x0, 0, z1), (x1, 0, z1), (x1, depth, z1), (x0, depth, z1)], (0, 0, 1))):
                    if not solid(i + di, j + dj):
                        parts['frame'].append(b.quad(pts, MAT_FACE, want))
        for field_index, (kind, r) in enumerate(st['fields']):
            x0, z0, x1, z1 = r
            if x1 - x0 <= _EPS or z1 - z0 <= _EPS:
                if kind == 'opaque':  # preserve legacy family normalization, but never silently drop it
                    dropped_fields.append({'index': field_index, 'kind': kind, 'rect': r,
                                           'reason': 'degenerate after family standardization'})
                    continue
                raise ValueError('degenerate {} field {}'.format(kind, r))
            cover = overlap if kind in ('glass', 'grille') else 0.0
            quad = [(x0-cover, gy, z0-cover), (x1+cover, gy, z0-cover),
                    (x1+cover, gy, z1+cover), (x0-cover, gy, z1+cover)]
            if kind == 'glass':
                parts['glass'].append(b.quad(quad, MAT_GLASS, (0, -1, 0)))
            elif kind == 'grille':
                parts['grille'].append(b.quad(quad, MAT_GRILLE, (0, -1, 0)))
            else:
                parts['frame'].append(b.quad(quad, MAT_OPAQUE, (0, -1, 0)))
        if interior is not None:
            # Independent open-front box around the OPENING, never an extrusion of frame edges [D322].
            x0, x1, z0, z1, y0, y1 = -0.044, W+0.044, -0.130, H+0.130, seat, seat+room
            for pts, normal in (
                    ([(x0,y0,z0),(x0,y1,z0),(x0,y1,z1),(x0,y0,z1)], (1,0,0)),
                    ([(x1,y0,z0),(x1,y1,z0),(x1,y1,z1),(x1,y0,z1)], (-1,0,0)),
                    ([(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0)], (0,0,1)),
                    ([(x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)], (0,0,-1)),
                    ([(x0,y1,z0),(x1,y1,z0),(x1,y1,z1),(x0,y1,z1)], (0,-1,0))):
                parts['capsule'].append(b.quad(pts, MAT_CAPSULE, normal))
    return {'verts': b.verts, 'faces': b.faces, 'mat_ids': b.mat_ids, 'parts': parts, 'face_axis_m': 0.0,
            'face_axis': '-y', 'depth_m': depth, 'frame_mid_m': depth / 2.0, 'glass_y_m': gy,
            'size_m': [W, depth, H], 'family': fam_name, 'fields': st['fields'], 'variant': variant,
            'status': q['status'], 'why': q['why'], 'dropped_fields': dropped_fields}


def part_mesh(mesh, part):
    """Compact part mesh; body is every non-glass part, retaining grilles/capsules in host placement."""
    idx = ([fi for name, faces in mesh['parts'].items() if name != 'glass' for fi in faces]
           if part == 'body' else mesh['parts'][part])
    remap, verts, faces, ids = {}, [], [], []
    for fi in idx:
        f = []
        for i in mesh['faces'][fi]:
            if i not in remap:
                remap[i] = len(verts)
                verts.append(list(mesh['verts'][i]))
            f.append(remap[i])
        faces.append(f)
        ids.append(mesh['mat_ids'][fi])
    return {'verts': verts, 'faces': faces, 'mat_ids': ids}


def to_obj(mesh, name):
    """Wavefront OBJ text of a type mesh (metres, Max/Blender import), parts as groups."""
    lines = ['# AGR Tools win.generate (#1024): {} family {} face {}'.format(name, mesh.get('family'),
                                                                          mesh.get('face_axis')),
             'o ' + name]
    lines += ['v {:.6f} {:.6f} {:.6f}'.format(*v) for v in mesh['verts']]
    owner = {}
    for part, idx in mesh['parts'].items():
        for fi in idx:
            owner[fi] = part
    for part in mesh['parts']:
        lines.append('o {}_{}'.format(name, part))
        lines.append('g {}_{}'.format(name, part))
        last = None
        for fi, f in enumerate(mesh['faces']):
            if owner.get(fi) != part:
                continue
            if mesh['mat_ids'][fi] != last:
                last = mesh['mat_ids'][fi]
                lines.append('usemtl matid_{}'.format(last))
            lines.append('f ' + ' '.join(str(i + 1) for i in f))
    return '\n'.join(lines) + '\n'


# ---- drafts --------------------------------------------------------------------------------------------------
def draft_entry(opening, standard, role='window', name=None):
    """A draft library record for an opening without a type (D116: the agent only proposes a draft; it reaches the
    library only through the preview sheet). One glass field inside the F100 frame face."""
    standard = load_standard(standard)
    w, h = opening.get('w'), opening.get('h')
    if not w or not h:
        raise ValueError('a draft needs the opening width and height')
    fam_name = (standard.get('role_family') or {}).get(role, 'F100')
    f = standard['families'][fam_name]['face_m']
    return {'schema': DRAFT_SCHEMA, 'status': 'draft', 'id': None, 'name': name, 'role': role,
            'width_m': round(w, 4), 'height_m': round(h, 4), 'sections': 1, 'transoms': 0,
            'panes_m': [[f, f, round(w - f, 4), round(h - f, 4)]], 'opaque_m': None, 'family': fam_name,
            'source': {'opening': opening.get('marker'), 'wall': opening.get('wall'), 'kind': opening.get('kind'),
                       'why': list(opening.get('why') or [])}}


# ---- preview sheet (PNG, stdlib) -----------------------------------------------------------------------------
_FONT = {  # 3x5 glyphs, rows top..bottom, bits left..right
    '0': '111101101101111', '1': '010110010010111', '2': '111001111100111', '3': '111001111001111',
    '4': '101101111001001', '5': '111100111001111', '6': '111100111101111', '7': '111001010010010',
    '8': '111101111101111', '9': '111101111001111', 'A': '010101111101101', 'B': '110101110101110',
    'C': '011100100100011', 'D': '110101101101110', 'E': '111100110100111', 'F': '111100110100100',
    'G': '011100101101011', 'H': '101101111101101', 'I': '111010010010111', 'J': '001001001101010',
    'K': '101101110101101', 'L': '100100100100111', 'M': '101111111101101', 'N': '110101101101101',
    'O': '010101101101010', 'P': '110101110100100', 'Q': '010101101110011', 'R': '110101110101101',
    'S': '011100010001110', 'T': '111010010010010', 'U': '101101101101111', 'V': '101101101101010',
    'W': '101101101111101', 'X': '101101010101101', 'Y': '101101010010010', 'Z': '111001010100111',
    '-': '000000111000000', '_': '000000000000111', ' ': '000000000000000', '>': '100010001010100',
    '.': '000000000000010', ':': '000010000010000',
}
_COL = {'bg': (250, 250, 250), 'frame': (70, 70, 75), 'glass': (150, 200, 235), 'opaque': (175, 165, 150),
        'line': (30, 30, 30), 'pass': (60, 160, 80), 'quarantine': (200, 50, 50), 'duplicate': (230, 150, 30),
        'src': (210, 225, 240), 'text': (20, 20, 20)}


class _Canvas:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.px = bytearray(bytes(bg) * (w * h))

    def rect(self, x0, y0, x1, y1, col):
        x0, x1 = max(0, int(round(min(x0, x1)))), min(self.w, int(round(max(x0, x1))))
        y0, y1 = max(0, int(round(min(y0, y1)))), min(self.h, int(round(max(y0, y1))))
        row = bytes(col) * max(0, x1 - x0)
        for y in range(y0, y1):
            i = (y * self.w + x0) * 3
            self.px[i:i + len(row)] = row

    def outline(self, x0, y0, x1, y1, col):
        self.rect(x0, y0, x1, y0 + 1, col)
        self.rect(x0, y1 - 1, x1, y1, col)
        self.rect(x0, y0, x0 + 1, y1, col)
        self.rect(x1 - 1, y0, x1, y1, col)

    def text(self, x, y, s, col, k=2):
        for ch in s.upper():
            g = _FONT.get(ch, _FONT[' '])
            for r in range(5):
                for c in range(3):
                    if g[r * 3 + c] == '1':
                        self.rect(x + c * k, y + r * k, x + (c + 1) * k, y + (r + 1) * k, col)
            x += 4 * k

    def png(self):
        def chunk(kind, data):
            return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
        raw = b''.join(b'\x00' + bytes(self.px[y * self.w * 3:(y + 1) * self.w * 3]) for y in range(self.h))
        return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', self.w, self.h, 8, 2, 0, 0, 0))
                + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def _draw_window(cv, ox, oy, size, W, H, rects, frame):
    s = min(size / W, size / H)
    w, h = W * s, H * s
    x0, y0 = ox + (size - w) / 2, oy + (size - h) / 2
    cv.rect(x0, y0, x0 + w, y0 + h, _COL['frame'] if frame else _COL['src'])
    for kind, r in rects:
        cv.rect(x0 + r[0] * s, y0 + h - r[3] * s, x0 + r[2] * s, y0 + h - r[1] * s, _COL[kind])
    cv.outline(x0, y0, x0 + w, y0 + h, _COL['line'])


def sheet_png(types, standard, report, cols=6, cell=110):
    """Preview sheet «было -> стало»: per type the raw record fields (left) and the standard mesh fields (right),
    the id and a verdict bar (green pass, red quarantine, orange duplicate). PNG bytes."""
    rows_by = {r['id']: r for r in report['types']}
    n = len(types)
    nrows = max(1, (n + cols - 1) // cols)
    cw, ch = cell * 2 + 30, cell + 40
    cv = _Canvas(cols * cw + 20, nrows * ch + 50, _COL['bg'])
    cv.text(10, 10, 'WIN.GENERATE  {} TYPES  PASS {}  QUARANTINE {}  DUPLICATE {}'.format(
        n, report['counts']['pass'], report['counts']['quarantine'], report['counts']['duplicate']), _COL['text'])
    for k, t in enumerate(types):
        gx, gy = 10 + (k % cols) * cw, 40 + (k // cols) * ch
        row = rows_by[t['id']]
        cv.rect(gx, gy, gx + cw - 10, gy + 4, _COL[row['verdict']])
        cv.text(gx, gy + 8, t['id'][:16], _COL['text'])
        W, H = t.get('width_m'), t.get('height_m')
        if not W or not H:
            continue
        _draw_window(cv, gx, gy + 24, cell, W, H, fields(t), False)
        cv.text(gx + cell + 4, gy + 24 + cell // 2 - 5, '>', _COL['text'])
        if row['verdict'] != 'quarantine' or fields(t):
            try:
                fam = family_of(t, standard)[1]
                std = standardize(t, fam, standard['criteria'])['fields'] if fields(t) else []
            except (ValueError, KeyError):
                std = []
            _draw_window(cv, gx + cell + 18, gy + 24, cell, W, H, std, True)
    return cv.png()


def report_json(report):
    return json.dumps(report, ensure_ascii=False, indent=1, sort_keys=False) + '\n'
