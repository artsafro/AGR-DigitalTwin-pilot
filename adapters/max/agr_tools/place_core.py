"""new-case: AGR Tools 0.9 (#979) place block logic, stdlib only; no pymxs. Owned by branch A (improve/issue-979-place).

Pure logic of `place.replace`, `place.schedule`, `place.drop_to_ground`, `place.maf_checks`, `place.flora_repair`.
The pymxs glue (place_max.py) reads the scene, converts system units to metres (units.SystemType/SystemScale, never
the string units.decodeValue), calls these functions and applies the plan. Everything here works in metres, world
space, row-vector transforms of Max (`p_world = p_local * tm`: rows 1-3 are the images of the local axes, row 4 the
pivot).

Sources (#853: ideas only, no team code copied; team files are cited by name + SHA256):
* drop to Ground: `Maf Tools.mcr` Glue (SHA256 df1a3a3e…19fa05), lab L06 `docs/experiments/place.drop_to_ground.md`.
  Taken: ray down, bottom by the vertices. Fixed: offset sign (+ raises), no horizontal plane under the pivot, the
  bottom (not the pivot) touches, no reverse ray (no flipping under a closed Ground), several Ground objects,
  analytic alignment instead of 360 rotated copies, metres.
* MAF checks: `Maf_Fly.ms` (SHA256 ae29be74…f0ef), `Maf Tools.mcr` Maf Check; T05. Fixed: AABB is only a
  pre-filter, rays from the vertices, tolerances in metres, 3D intersections instead of the plan footprint.
* replace: `Zamena_V2.ms` (SHA256 a44ac231…defa3), `H_instancer-1.0.mcr` (SHA256 7c94827f…9eda),
  `place_box001_on_doors.ms` (SHA256 93eb2d12…a928); lab L07 `docs/experiments/place.replace.md` (oriented box).
* schedule: pilot `tools/placement_site.py`, `jobs/VATUTINO-SITE/placement_report.py`; lab L08
  `docs/experiments/place.schedule.md` (report-first, partial placement, obstacles, idempotent re-run).
* Flora repair: pilot `tools/max_flora_transform_repair.py`, `tools/max_flora_tri_repair.py`,
  `tools/max_flora_verify.py`, `experiments/flora-library-audit/mesh_compare.py`; lab L08
  `docs/experiments/place.flora_repair.md` (copies only, no isolation delete, one undo record).
"""
import csv
import fnmatch
import io
import json
import math

ISSUE = '#979'
GROUND_SUFFIX = '_ground'  # NPM role suffix of the relief (case-insensitive)
SCHEDULE_LAYER = 'placement_instances'  # lab L08: the pilot's layer
FLORA_LAYER = 'AGR_flora_repair'
SINK_M = 0.10  # MAF sink into the Ground, NPM [D094/D095]: offset -0.10 m for place.schedule
BURIED_TOL_M = 1e-6
UNITS_M = {'inches': 0.0254, 'feet': 0.3048, 'miles': 1609.344, 'millimeters': 0.001, 'centimeters': 0.01,
           'meters': 1.0, 'kilometers': 1000.0}


# ---- vectors ------------------------------------------------------------------------------------------
def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def length(a):
    return math.sqrt(dot(a, a))


def unit(a):
    n = length(a)
    if not n > 0:
        raise ValueError('zero-length vector')
    return (a[0] / n, a[1] / n, a[2] / n)


def matvec(m, v):
    """3x3 matrix (rows) times a column vector."""
    return (dot(m[0], v), dot(m[1], v), dot(m[2], v))


def rotation_between(a, b):
    """Smallest rotation (3x3, column convention) taking unit direction a to unit direction b (Rodrigues)."""
    a, b = unit(a), unit(b)
    c = max(-1.0, min(1.0, dot(a, b)))
    if c > 1.0 - 1e-15:
        return ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    if c < -1.0 + 1e-15:  # opposite: 180 degrees about any axis perpendicular to a
        k = unit(cross(a, (1.0, 0.0, 0.0) if abs(a[0]) < 0.9 else (0.0, 1.0, 0.0)))
        return axis_angle(k, math.pi)
    return axis_angle(unit(cross(a, b)), math.acos(c))


def axis_angle(k, angle):
    x, y, z = k
    c, s = math.cos(angle), math.sin(angle)
    t = 1.0 - c
    return ((t * x * x + c, t * x * y - s * z, t * x * z + s * y),
            (t * x * y + s * z, t * y * y + c, t * y * z - s * x),
            (t * x * z - s * y, t * y * z + s * x, t * z * z + c))


def rot_z(deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return ((c, -s, 0.0), (s, c, 0.0), (0.0, 0.0, 1.0))


def _finite(*values):
    return all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in values)


def fmt(v, digits=4):
    return '{:.{}f}'.format(float(v), digits)


# ---- units --------------------------------------------------------------------------------------------
def m_per_unit(system_type, system_scale):
    """Metres per system unit from units.SystemType / units.SystemScale (never the string decodeValue: ru-RU)."""
    key = str(system_type).lstrip('#').lower()
    if key not in UNITS_M:
        raise ValueError('unknown system unit type: ' + repr(system_type))
    scale = float(system_scale)
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError('system scale must be a positive number')
    return UNITS_M[key] * scale


# ---- options ------------------------------------------------------------------------------------------
def _num(options, key, default, lo, hi):
    v = options.get(key, default)
    if not _finite(v) or not lo <= float(v) <= hi:
        raise ValueError('{} must be a number in [{}, {}] (metres)'.format(key, lo, hi))
    return float(v)


def _flag(options, key, default=False):
    v = options.get(key, default)
    if not isinstance(v, bool):
        raise ValueError(key + ' must be true or false')
    return v


def _names(options, key):
    v = options.get(key)
    if v is None:
        return None
    if not isinstance(v, list) or not v or any(not isinstance(n, str) or not n.strip() for n in v):
        raise ValueError(key + ' must be a non-empty list of object names')
    return sorted(set(v))


OPTION_KEYS = {
    'place.drop_to_ground': {'offset_m', 'align', 'lift_buried', 'ground'},
    'place.maf_checks': {'gap_m', 'fly_tol_m', 'sink_tol_m', 'ground', 'intersect', 'contact_tol_m'},
    'place.replace': {'master', 'mask', 'mode', 'stub'},
    'place.schedule': {'rows', 'path', 'offset_m', 'ground', 'obstacles', 'mode'},
    'place.flora_repair': set(),
}


def check_options(tool, options):
    """Validated options of one tool with defaults filled in; unknown keys are refused (no silent typo)."""
    options = dict(options or {})
    stray = sorted(set(options) - OPTION_KEYS[tool])
    if stray:
        raise ValueError('unknown option(s) for {}: {}'.format(tool, stray))
    if tool == 'place.drop_to_ground':
        return {'offset_m': _num(options, 'offset_m', 0.0, -100.0, 100.0), 'align': _flag(options, 'align'),
                'lift_buried': _flag(options, 'lift_buried'), 'ground': _names(options, 'ground')}
    if tool == 'place.maf_checks':
        return {'gap_m': _num(options, 'gap_m', 0.0, -10.0, 10.0),
                'fly_tol_m': _num(options, 'fly_tol_m', 0.001, 0.0, 10.0),
                'sink_tol_m': _num(options, 'sink_tol_m', 0.001, 0.0, 10.0),
                'contact_tol_m': _num(options, 'contact_tol_m', 1e-4, 0.0, 0.1),
                'intersect': _flag(options, 'intersect', True), 'ground': _names(options, 'ground')}
    if tool == 'place.replace':
        stub = _flag(options, 'stub')
        master = options.get('master')
        if stub:
            if master is not None:
                raise ValueError('stub mode replaces by a box: no master')
        elif not isinstance(master, str) or not master.strip():
            raise ValueError('master: the exact name of the reference object is required')
        mask = options.get('mask')
        if mask is not None and (not isinstance(mask, str) or not mask.strip()):
            raise ValueError('mask must be an exact name or a glob (* ? [])')
        mode = options.get('mode', 'instance')
        if mode not in ('instance', 'copy'):
            raise ValueError('mode must be instance or copy')
        return {'master': master, 'mask': mask, 'mode': mode, 'stub': stub}
    if tool == 'place.schedule':
        if ('rows' in options) == ('path' in options):
            raise ValueError('schedule: give exactly one of rows (list) or path (CSV/JSON file)')
        mode = options.get('mode', 'instance')
        if mode not in ('instance', 'copy'):
            raise ValueError('mode must be instance or copy')
        path = options.get('path')
        if path is not None and (not isinstance(path, str) or not path.strip()):
            raise ValueError('path must be a file path')
        return {'rows': options.get('rows'), 'path': path, 'mode': mode,
                'offset_m': _num(options, 'offset_m', -SINK_M, -10.0, 10.0),
                'ground': _names(options, 'ground'), 'obstacles': _names(options, 'obstacles')}
    return {}


def is_ground_name(name):
    return str(name).lower().endswith(GROUND_SUFFIX)


# ---- Ground surface: vertical rays --------------------------------------------------------------------
class Surface:
    """Triangles of the Ground objects (metres, world). `top(x, y)` is the highest Ground point on the vertical
    line through (x, y) and the upward normal there; None when the line misses every Ground (a «промах»).

    Only downward rays from above are used: an object under a closed Ground is lifted to its top face, never
    glued upside down to its bottom face (lab L06 defect 4). Several Ground objects form one surface (defect 5)."""

    def __init__(self, triangles, cell=None):
        self.tris = []
        for t in triangles:
            a, b, c = (tuple(float(x) for x in p) for p in t)
            if not _finite(*a, *b, *c):
                raise ValueError('non-finite Ground vertex')
            n = cross(sub(b, a), sub(c, a))
            if abs(n[2]) <= 1e-12 * max(1.0, length(n)):  # vertical or degenerate: no vertical hit
                continue
            self.tris.append((a, b, c, unit(n if n[2] > 0 else mul(n, -1.0))))
        if not self.tris:
            raise ValueError('Ground has no faces')
        xs = [p[0] for t in self.tris for p in t[:3]]
        ys = [p[1] for t in self.tris for p in t[:3]]
        zs = [p[2] for t in self.tris for p in t[:3]]
        self.lo, self.hi = (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))
        span = max(self.hi[0] - self.lo[0], self.hi[1] - self.lo[1], 1e-9)
        self.cell = cell or max(span / max(1.0, min(256.0, math.sqrt(len(self.tris)) * 2.0)), 1e-9)
        self.grid = {}
        for i, (a, b, c, _n) in enumerate(self.tris):
            for key in self._cells(min(a[0], b[0], c[0]), min(a[1], b[1], c[1]),
                                   max(a[0], b[0], c[0]), max(a[1], b[1], c[1])):
                self.grid.setdefault(key, []).append(i)

    def _cells(self, x0, y0, x1, y1):
        h = self.cell
        for i in range(int(math.floor((x0 - self.lo[0]) / h)), int(math.floor((x1 - self.lo[0]) / h)) + 1):
            for j in range(int(math.floor((y0 - self.lo[1]) / h)), int(math.floor((y1 - self.lo[1]) / h)) + 1):
                yield i, j

    def top(self, x, y):
        best = None
        h = self.cell
        key = (int(math.floor((x - self.lo[0]) / h)), int(math.floor((y - self.lo[1]) / h)))
        for i in self.grid.get(key, ()):
            a, b, c, n = self.tris[i]
            z = _vertical_hit(a, b, c, x, y)
            if z is not None and (best is None or z > best[0]):
                best = (z, n)
        return best

    def overlaps_xy(self, lo, hi):
        return not (hi[0] < self.lo[0] or lo[0] > self.hi[0] or hi[1] < self.lo[1] or lo[1] > self.hi[1])


def _vertical_hit(a, b, c, x, y, eps=1e-12):
    """z of the triangle on the vertical line (x, y), edges included; None outside."""
    d = (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])
    if d == 0:
        return None
    u = ((x - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (y - a[1])) / d
    v = ((b[0] - a[0]) * (y - a[1]) - (x - a[0]) * (b[1] - a[1])) / d
    if u < -eps or v < -eps or u + v > 1 + eps:
        return None
    return a[2] + u * (b[2] - a[2]) + v * (c[2] - a[2])


def vertical_gaps(verts, surface):
    """[(vertex index, gap)] for the vertices with Ground below/above them: gap = z - Ground z (m)."""
    out = []
    for i, v in enumerate(verts):
        hit = surface.top(v[0], v[1])
        if hit is not None:
            out.append((i, v[2] - hit[0]))
    return out


def bbox(verts):
    return (tuple(min(v[i] for v in verts) for i in range(3)), tuple(max(v[i] for v in verts) for i in range(3)))


# ---- place.drop_to_ground -----------------------------------------------------------------------------
def drop(verts, rows, surface, offset=0.0, align=False, lift_buried=False):
    """Plan of one object: vertical move (and optional alignment to the Ground normal) so that the smallest
    vertical gap between its vertices and the Ground equals `offset` (+ raises, - sinks; metres).

    verts: world vertices (m); rows: the node transform [row1, row2, row3, row4] (axes, pivot in m).
    Returns {'status': 'ok'|'miss'|'buried', ...}; 'ok' carries the new transform rows."""
    if not verts:
        return {'status': 'empty', 'reason': 'object has no vertices'}
    pivot = tuple(rows[3])
    axes = [tuple(r) for r in rows[:3]]
    rot = None
    normal = None
    if align:
        probe = surface.top(pivot[0], pivot[1])
        if probe is None:
            lo, hi = bbox(verts)
            probe = surface.top((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2)
        if probe is None:
            return {'status': 'miss', 'reason': 'no Ground under the pivot or the bounding-box centre'}
        normal = probe[1]
        rot = rotation_between(axes[2], normal)
        verts = [add(pivot, matvec(rot, sub(v, pivot))) for v in verts]
        axes = [matvec(rot, a) for a in axes]
    gaps = vertical_gaps(verts, surface)
    if not gaps:
        return {'status': 'miss', 'reason': 'no Ground under any vertex'}
    low = min(g for _, g in gaps)
    high = max(g for _, g in gaps)
    if high < -BURIED_TOL_M and not lift_buried:
        return {'status': 'buried', 'reason': 'the whole object is under the Ground (lift_buried is off)',
                'gap_m': low}
    dz = offset - low
    new_pivot = (pivot[0], pivot[1], pivot[2] + dz)
    out = {'status': 'ok', 'dz_m': dz, 'gap_before_m': low, 'gap_after_m': offset,
           'rows': [list(a) for a in axes] + [list(new_pivot)], 'vertices_on_ground': len(gaps),
           'vertices_off_ground': len(verts) - len(gaps), 'buried': high < -BURIED_TOL_M}
    if align:
        out['normal'] = list(normal)
        out['tilt_deg'] = math.degrees(math.acos(max(-1.0, min(1.0, normal[2]))))
        out['z_dot_n'] = dot(unit(axes[2]), normal)
    return out


# ---- place.maf_checks ---------------------------------------------------------------------------------
def maf_gap(verts, surface):
    """(min gap, vertices with Ground) after the AABB pre-filter; (None, 0) when there is no Ground below."""
    lo, hi = bbox(verts)
    if not surface.overlaps_xy(lo, hi):
        return None, 0
    gaps = vertical_gaps(verts, surface)
    if not gaps:
        return None, 0
    return min(g for _, g in gaps), len(gaps)


def maf_verdict(gap, gap_m=0.0, fly_tol_m=0.001, sink_tol_m=0.001):
    """'ok' | 'maf_flying' | 'maf_sunk' for the smallest vertical gap (m) against the target gap ± tolerances."""
    if gap > gap_m + fly_tol_m:
        return 'maf_flying'
    if gap < gap_m - sink_tol_m:
        return 'maf_sunk'
    return 'ok'


def _plane_side(tri, pts, eps):
    n = cross(sub(tri[1], tri[0]), sub(tri[2], tri[0]))
    ln = length(n)
    if ln == 0:
        return None, None
    n = mul(n, 1.0 / ln)
    d = [dot(n, sub(p, tri[0])) for p in pts]
    return n, [0.0 if abs(x) <= eps else x for x in d]


def _interval(tri, d, direction):
    pts = [tri[i] for i in range(3) if d[i] == 0.0]
    for i, j in ((0, 1), (1, 2), (2, 0)):
        if d[i] * d[j] < 0:
            pts.append(add(tri[i], mul(sub(tri[j], tri[i]), d[i] / (d[i] - d[j]))))
    ts = [dot(direction, p) for p in pts]
    return (min(ts), max(ts)) if ts else None


def triangles_cross(t1, t2, eps=1e-4):
    """True when two triangles really cross (penetrate) in 3D. Touching within `eps` and coplanar contact are
    not crossings (two MAF standing side by side are not an intersection)."""
    n2, d1 = _plane_side(t2, t1, eps)
    if n2 is None or all(x >= 0 for x in d1) or all(x <= 0 for x in d1):
        return False
    n1, d2 = _plane_side(t1, t2, eps)
    if n1 is None or all(x >= 0 for x in d2) or all(x <= 0 for x in d2):
        return False
    direction = cross(n1, n2)
    if length(direction) < 1e-12:
        return False
    direction = unit(direction)
    a, b = _interval(t1, d1, direction), _interval(t2, d2, direction)
    if a is None or b is None:
        return False
    return min(a[1], b[1]) - max(a[0], b[0]) > eps


def _tri_box(t):
    return (tuple(min(p[i] for p in t) for i in range(3)), tuple(max(p[i] for p in t) for i in range(3)))


def _boxes_overlap(a, b, pad=0.0):
    return all(a[0][i] - pad <= b[1][i] and b[0][i] - pad <= a[1][i] for i in range(3))


def mesh_intersections(tris_a, tris_b, eps=1e-4, limit=100):
    """Face pairs (1-based) where mesh A really crosses mesh B, at most `limit`."""
    box_a, box_b = bbox([p for t in tris_a for p in t]), bbox([p for t in tris_b for p in t])
    if not _boxes_overlap(box_a, box_b):
        return []
    common = (tuple(max(box_a[0][i], box_b[0][i]) for i in range(3)),
              tuple(min(box_a[1][i], box_b[1][i]) for i in range(3)))
    near_a = [(i, t, _tri_box(t)) for i, t in enumerate(tris_a) if _boxes_overlap(_tri_box(t), common, eps)]
    near_b = [(j, t, _tri_box(t)) for j, t in enumerate(tris_b) if _boxes_overlap(_tri_box(t), common, eps)]
    out = []
    for i, ta, ba in near_a:
        for j, tb, bb in near_b:
            if _boxes_overlap(ba, bb) and triangles_cross(ta, tb, eps):
                out.append((i + 1, j + 1))
                if len(out) >= limit:
                    return out
    return out


def maf_checks(objects, surface, opts):
    """objects: [{handle, name, verts, tris (vertex triples, 0-based), hidden, frozen}] (metres, world).
    Returns {handle: [(code, ids, detail)]}, rows [{name, gap_m, verdict}], no_ground [names], pairs."""
    findings = {o['handle']: [] for o in objects}
    rows, no_ground, pairs = [], [], []
    for o in objects:
        flag = ' (скрыт)' if o.get('hidden') else ' (заморожен)' if o.get('frozen') else ''
        gap, hits = maf_gap(o['verts'], surface) if o['verts'] else (None, 0)
        if gap is None:
            no_ground.append(o['name'])
            rows.append({'name': o['name'], 'gap_m': None, 'verdict': 'no_ground', 'hidden': bool(o.get('hidden')),
                         'frozen': bool(o.get('frozen'))})
            continue
        verdict = maf_verdict(gap, opts['gap_m'], opts['fly_tol_m'], opts['sink_tol_m'])
        rows.append({'name': o['name'], 'gap_m': gap, 'verdict': verdict, 'vertices_on_ground': hits,
                     'hidden': bool(o.get('hidden')), 'frozen': bool(o.get('frozen'))})
        if verdict == 'maf_flying':
            findings[o['handle']].append(('maf_flying', (), 'зазор {} м{}'.format(fmt(gap - opts['gap_m']), flag)))
        elif verdict == 'maf_sunk':
            findings[o['handle']].append(('maf_sunk', (), 'глубина {} м{}'.format(fmt(opts['gap_m'] - gap), flag)))
    if opts['intersect']:
        meshes = [(o, [tuple(o['verts'][k] for k in t) for t in o['tris']]) for o in objects if o['tris']]
        for x in range(len(meshes)):
            for y in range(x + 1, len(meshes)):
                (oa, ta), (ob, tb) = meshes[x], meshes[y]
                hit = mesh_intersections(ta, tb, opts['contact_tol_m'])
                if not hit:
                    continue
                pairs.append({'a': oa['name'], 'b': ob['name'], 'faces': len(hit)})
                findings[oa['handle']].append(('maf_intersect', sorted({i for i, _ in hit}),
                                               'пересекает {}'.format(ob['name'])))
                findings[ob['handle']].append(('maf_intersect', sorted({j for _, j in hit}),
                                               'пересекает {}'.format(oa['name'])))
    return {'findings': findings, 'rows': rows, 'no_ground': no_ground, 'pairs': pairs}


# ---- place.replace ------------------------------------------------------------------------------------
def mask_match(name, mask):
    """Exact name by default; an explicit glob only when the mask has * ? or [ ] (never a substring)."""
    if mask is None:
        return True
    if any(ch in mask for ch in '*?['):
        return fnmatch.fnmatchcase(str(name), mask)
    return str(name) == mask


def replace_targets(candidates, opts):
    """candidates: [{handle, name, selected, hidden, frozen, is_master, master_instance, master_copy, geometry}].

    Targets: with a mask, every scene object matching it (selected objects that do not match are listed as
    unmatched); without a mask, the selection. The master, its instances and
    its geometric copies (earlier replacements included) are never targets (by handle, not by name), so a re-run
    changes nothing. Returns (targets, skipped [(name, reason)], findings {handle: [(code, detail)]},
    unmatched [names])."""
    picked = list(candidates) if opts['mask'] else [c for c in candidates if c['selected']]
    if not picked:
        raise ValueError('nothing selected and no mask: select the targets or give a mask')
    targets, skipped, findings, unmatched = [], [], {}, []
    matched = 0
    for c in picked:
        if not mask_match(c['name'], opts['mask']):
            if c['selected']:
                unmatched.append(c['name'])
                skipped.append((c['name'], 'does not match the mask ' + repr(opts['mask'])))
            continue
        matched += 1
        why = None
        if c.get('is_master'):
            why = ('is_master', 'the master itself is never replaced')
        elif c.get('master_instance'):
            why = ('master_instance', 'an instance of the master (already replaced)')
        elif c.get('master_copy'):
            why = ('master_copy', 'a copy of the master (same geometry and class)')
        elif not c.get('geometry', True):
            why = ('not_geometry', 'not a geometry object')
        elif c.get('hidden') or c.get('frozen'):
            why = ('hidden' if c.get('hidden') else 'frozen', 'hidden or frozen objects are reported, not replaced')
        if why:
            skipped.append((c['name'], why[1]))
            if c['selected']:
                findings[c['handle']] = [why]
            continue
        targets.append(c)
    if not matched:
        raise ValueError('the mask {!r} matched no object'.format(opts['mask']))
    return targets, skipped, findings, unmatched


def oriented_box(verts, ot):
    """Box stub over the world vertices of a node in the axes of its objectTransform `ot` (lab L07 formula):
    e1 = |ot.row1|, e2 = row2 orthogonalised, e3 = e1 x e2; width along e1 (X), length along e2 (Y), height
    along e3; the Box pivot is the centre of its base. The node scale is in the vertices, applied once."""
    e1 = unit(ot[0])
    r2 = tuple(ot[1])
    e2 = unit(sub(r2, mul(e1, dot(r2, e1))))
    e3 = cross(e1, e2)
    o = tuple(ot[3])
    q = [(dot(sub(p, o), e1), dot(sub(p, o), e2), dot(sub(p, o), e3)) for p in verts]
    lo = tuple(min(v[i] for v in q) for i in range(3))
    hi = tuple(max(v[i] for v in q) for i in range(3))
    base = add(add(add(o, mul(e1, (lo[0] + hi[0]) / 2)), mul(e2, (lo[1] + hi[1]) / 2)), mul(e3, lo[2]))
    return {'width': hi[0] - lo[0], 'length': hi[1] - lo[1], 'height': hi[2] - lo[2],
            'rows': [list(e1), list(e2), list(e3), list(base)]}


def box_vertices(box):
    """World corners of an oriented box stub (for checks)."""
    e1, e2, e3, base = (tuple(r) for r in box['rows'])
    out = []
    for sx in (-0.5, 0.5):
        for sy in (-0.5, 0.5):
            for sz in (0.0, 1.0):
                out.append(add(add(add(base, mul(e1, sx * box['width'])), mul(e2, sy * box['length'])),
                               mul(e3, sz * box['height'])))
    return out


def to_local(verts, rows):
    """World points -> the space of a transform given as rows (row-vector convention: p_world = p_local*A + t)."""
    a = [tuple(r) for r in rows[:3]]
    t = tuple(rows[3])
    det = dot(a[0], cross(a[1], a[2]))
    if abs(det) < 1e-300:
        raise ValueError('singular transform')
    # inverse of the row matrix A: columns of A^-1 are the cross products / det
    c0, c1, c2 = cross(a[1], a[2]), cross(a[2], a[0]), cross(a[0], a[1])
    out = []
    for p in verts:
        d = sub(p, t)
        out.append((dot(d, c0) / det, dot(d, c1) / det, dot(d, c2) / det))
    return out


def inside_box(p, box, tol=1e-4):
    e1, e2, e3, base = (tuple(r) for r in box['rows'])
    d = sub(p, base)
    return (abs(dot(d, e1)) <= box['width'] / 2 + tol and abs(dot(d, e2)) <= box['length'] / 2 + tol
            and -tol <= dot(d, e3) <= box['height'] + tol)


# ---- place.schedule -----------------------------------------------------------------------------------
SCHEDULE_COLUMNS = ('id', 'model', 'x', 'y', 'rotation_deg')


def _number(text):
    if isinstance(text, (int, float)) and not isinstance(text, bool):
        v = float(text)
    else:
        v = float(str(text).strip().replace(',', '.'))
    if not math.isfinite(v):
        raise ValueError('non-finite number in the schedule')
    return v


def parse_schedule(rows=None, text=None, suffix='.csv'):
    """Schedule rows [{id, model, x, y, rotation_deg}] from a list (MCP / polygon) or a CSV / JSON text.
    CSV: header id;model;x;y;rotation_deg (`;` or `,`; decimal comma allowed with `;`). Coordinates in metres,
    world; rotation about Z in degrees. Duplicate or empty ids and non-finite numbers are errors."""
    if rows is None:
        if text is None:
            raise ValueError('schedule: no rows')
        if suffix.lower() == '.json':
            doc = json.loads(text)
            rows = doc['rows'] if isinstance(doc, dict) else doc
        else:
            text = text.lstrip('﻿')
            first = text.splitlines()[0] if text.strip() else ''
            delim = ';' if first.count(';') >= first.count(',') else ','
            rows = list(csv.DictReader(io.StringIO(text), delimiter=delim))
    if not isinstance(rows, list) or not rows:
        raise ValueError('schedule: empty (an empty input is an error, not a pass)')
    out, seen = [], set()
    for i, r in enumerate(rows, 1):
        if not isinstance(r, dict):
            raise ValueError('schedule row {} is not an object'.format(i))
        r = {str(k).strip().lower(): v for k, v in r.items() if k is not None}
        missing = [c for c in SCHEDULE_COLUMNS if c not in r and not (c == 'rotation_deg' and 'rotation' in r)]
        if missing:
            raise ValueError('schedule row {}: missing {}'.format(i, missing))
        rid, model = str(r['id']).strip(), str(r['model']).strip()
        if not rid or not model:
            raise ValueError('schedule row {}: empty id or model'.format(i))
        if rid in seen:
            raise ValueError('schedule: duplicate id ' + rid)
        seen.add(rid)
        out.append({'id': rid, 'model': model, 'x': _number(r['x']), 'y': _number(r['y']),
                    'rotation_deg': _number(r.get('rotation_deg', r.get('rotation')))})
    return out


def convex_hull_xy(points):
    pts = sorted(set((round(p[0], 9), round(p[1], 9)) for p in points))
    if len(pts) <= 2:
        return pts

    def turn(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and turn(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and turn(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def hulls_overlap(a, b, tol=1e-6):
    """Separating-axis test of two convex XY polygons: True when they overlap by more than `tol` (touching
    edges are not a conflict)."""
    if len(a) < 3 or len(b) < 3:
        return False
    for poly in (a, b):
        for i in range(len(poly)):
            p, q = poly[i], poly[(i + 1) % len(poly)]
            nx, ny = q[1] - p[1], p[0] - q[0]
            ln = math.hypot(nx, ny)
            if ln == 0:
                continue
            nx, ny = nx / ln, ny / ln
            pa = [nx * x + ny * y for x, y in a]
            pb = [nx * x + ny * y for x, y in b]
            if min(max(pa), max(pb)) - max(min(pa), min(pb)) <= tol:
                return False
    return True


def obstacle(name, verts):
    lo, hi = bbox(verts)
    return {'name': name, 'hull': convex_hull_xy(verts), 'zmin': lo[2], 'zmax': hi[2]}


def schedule_plan(rows, library, surface, obstacles, offset=-SINK_M, existing=()):
    """Report-first plan of a schedule (lab L08): one result per row, never a whole-run stop on one point.

    library: {model name: {'verts': world vertices (m), 'rows': world transform rows (m)}}; a missing model is
    `no_library_model`. Each row: the instance keeps the library node's axes rotated about Z by rotation_deg,
    its pivot goes to (x, y) and it is dropped onto the Ground with the same vertical rays as
    place.drop_to_ground (`offset`, default -0.10 m = the NPM 10 cm sink). Pivot outside the Ground:
    `outside_ground`; footprint over an obstacle (building) or an already planned instance with overlapping
    heights: `blocked_by_obstacle`; `existing` row ids (placed by an earlier run, by handle): `already_placed`."""
    results = []
    placed = []
    existing = set(existing)
    for r in rows:
        res = {'id': r['id'], 'model': r['model'], 'x': r['x'], 'y': r['y'], 'rotation_deg': r['rotation_deg']}
        results.append(res)
        if r['id'] in existing:
            res.update(status='already_placed', reason='placed by an earlier run (same row id, model)')
            continue
        lib = library.get(r['model'])
        if lib is None:
            res.update(status='no_library_model', reason='no reference object named ' + repr(r['model']))
            continue
        if surface.top(r['x'], r['y']) is None:
            res.update(status='outside_ground', reason='no Ground under ({}, {})'.format(fmt(r['x'], 3),
                                                                                          fmt(r['y'], 3)))
            continue
        rz = rot_z(r['rotation_deg'])
        pivot = tuple(lib['rows'][3])
        target = (r['x'], r['y'], 0.0)
        verts = [add(target, matvec(rz, sub(v, pivot))) for v in lib['verts']]
        axes = [list(matvec(rz, a)) for a in lib['rows'][:3]]
        d = drop(verts, axes + [list(target)], surface, offset, align=False, lift_buried=True)
        if d['status'] != 'ok':
            res.update(status='outside_ground', reason=d['reason'])
            continue
        dz = d['dz_m']
        verts = [(v[0], v[1], v[2] + dz) for v in verts]
        mine = obstacle(r['id'], verts)
        hit = None
        for ob in list(obstacles) + placed:
            if ob['zmin'] < mine['zmax'] and mine['zmin'] < ob['zmax'] and hulls_overlap(mine['hull'], ob['hull']):
                hit = ob['name']
                break
        if hit is not None:
            res.update(status='blocked_by_obstacle', reason='footprint crosses ' + hit)
            continue
        placed.append(dict(mine, name='{} ({})'.format(r['id'], r['model'])))
        res.update(status='placed', rows=d['rows'], gap_m=d['gap_after_m'],
                   vertices_off_ground=d['vertices_off_ground'])
    return results


def schedule_summary(results):
    count = {}
    for r in results:
        count[r['status']] = count.get(r['status'], 0) + 1
    return {'placed': count.get('placed', 0), 'no_library_model': count.get('no_library_model', 0),
            'no_place': count.get('outside_ground', 0) + count.get('blocked_by_obstacle', 0),
            'already_placed': count.get('already_placed', 0), 'by_status': count}


# ---- place.flora_repair -------------------------------------------------------------------------------
def transform_codes(rows, tol=1e-6):
    """Codes of a node transform (rows 1-3): negative_scale (det < 0), shear (axes not orthogonal),
    rotated (the normalised axes are not ±identity, or a 180-degree turn)."""
    axes = [tuple(r) for r in rows[:3]]
    det = dot(axes[0], cross(axes[1], axes[2]))
    codes = []
    if det < 0:
        codes.append('negative_scale')
    u = [unit(a) for a in axes]
    if any(abs(dot(u[i], u[j])) > tol for i, j in ((0, 1), (0, 2), (1, 2))):
        codes.append('shear')
    diagonal = all(abs(u[i][j]) <= tol for i in range(3) for j in range(3) if i != j)
    negatives = sum(1 for i in range(3) if u[i][i] < 0)
    # a diagonal mirror (det < 0: one or three negative axes; Max stores scale [-1,1,1] as -I) is not a rotation
    if not diagonal or (det > 0 and negatives == 2):
        codes.append('rotated')
    return codes


def flora_plan(info):
    """info: {name, geometry, faces, uv, degrees (poly face corner counts or []), rows}.
    Returns {'action': 'skip', 'reason'} for a broken object, else {'action': 'bake'|'snapshot', 'codes'}:
    shear -> world-baked identity mesh (transform repair basis, the only case whose source FBX differs, lab L08);
    any other -> triangulated snapshot keeping the transform (tri repair basis)."""
    if not info.get('geometry'):
        return {'action': 'skip', 'reason': 'not geometry', 'code': 'not_geometry'}
    if not info.get('faces'):
        return {'action': 'skip', 'reason': 'empty mesh (0 faces)', 'code': 'empty_mesh'}
    if not info.get('uv'):
        return {'action': 'skip', 'reason': 'no UV channel 1: the Flora card cannot be verified', 'code': 'no_uv'}
    codes = transform_codes(info['rows'])
    ngons = [i + 1 for i, d in enumerate(info.get('degrees') or []) if d > 3]
    return {'action': 'bake' if 'shear' in codes else 'snapshot', 'codes': codes, 'ngons': ngons}


def compare_meshes(expected, actual, position_tolerance=0.00005, uv_tolerance=0.00002):
    """Bijective triangle/corner matching in metres (idea of the pilot experiments/flora-library-audit/
    mesh_compare.py): every triangle of `actual` matches one of `expected` with the same material, corners in
    the same cyclic order (winding) within 0.05 mm and UV within 2e-5. Triangles: {'corners': [[x,y,z,u,v]...],
    'material': name}."""
    if len(expected) != len(actual):
        return {'equal': False, 'reason': 'triangle_count', 'expected': len(expected), 'actual': len(actual)}
    buckets = {}

    def key(tri):
        return tuple(math.floor(sum(c[i] for c in tri['corners']) / 3 / position_tolerance) for i in range(3))
    for index, tri in enumerate(expected):
        buckets.setdefault(key(tri), []).append(index)
    used = set()
    max_pos = max_uv = 0.0
    offsets = [(a, b, c) for a in (-1, 0, 1) for b in (-1, 0, 1) for c in (-1, 0, 1)]
    for tri in actual:
        cell = key(tri)
        best = None
        for off in offsets:
            for index in buckets.get((cell[0] + off[0], cell[1] + off[1], cell[2] + off[2]), ()):
                if index in used or expected[index]['material'] != tri['material']:
                    continue
                ref = expected[index]['corners']
                for shift in range(3):
                    seq = tri['corners'][shift:] + tri['corners'][:shift]
                    if any(len(a) != len(b) for a, b in zip(ref, seq)):
                        continue
                    pd = max(math.dist(a[:3], b[:3]) for a, b in zip(ref, seq))
                    ud = max((math.dist(a[3:], b[3:]) for a, b in zip(ref, seq)), default=0.0)
                    if pd <= position_tolerance and ud <= uv_tolerance and (best is None or (pd, ud) < best[:2]):
                        best = (pd, ud, index)
        if best is None:
            return {'equal': False, 'reason': 'unmatched_geometry_uv_winding_or_material', 'matched': len(used)}
        used.add(best[2])
        max_pos, max_uv = max(max_pos, best[0]), max(max_uv, best[1])
    return {'equal': len(used) == len(expected), 'matched': len(used), 'max_deviation_mm': max_pos * 1000,
            'max_uv_deviation': max_uv}
