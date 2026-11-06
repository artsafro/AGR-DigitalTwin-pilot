"""new-case: AGR Tools 1.0 (#1024) source class A/B/C / small parts of zavod sources logic, stdlib only. Stub of branch 0; owned by branch F (improve/issue-1024-passport).

Pure logic for `scene_source_class` (scene.source_class), `scene_small_parts` (scene.small_parts); no pymxs. Use edit_core.py for reports, preview hashes and new paths, contract_core.py for
roles, markers and ObjRef (the core never takes a host object).

scene.source_class (plan mode `read`, #1024 redaction 1 section 1): a stdlib port of the pilot rule D066
(`src/dt_ai/spec/source_class.py`, constants of `src/dt_ai/spec/mesh.py`: WELD_M 1e-4, PANEL_HINT_SHARE 0.5).
Connected parts after a position weld, the largest part's area share and a closed shell decide:
* a closed shell or one part -> `monolithic` (route `dt spec extract`, the shell engine);
* two or more parts, no shell, largest share strictly below PANEL_HINT_SHARE -> `panelised`
  (route measurement + direct build; TOW02 fed 5 561 parts to the shell engine for ~1.5 h);
* a share within 1e-9 of the threshold -> `ambiguous` (never a class);
* empty input, non-finite coordinates, zero total area, a bad index -> SourceClassError.
The tests keep this port equal to the pilot module on the same meshes (no second rule).

The source level A/B/C of the passport (K1) is not defined in #1024; LEVEL_RULE is the parameter default
(owner questions never block, IMPL.md 8): A = monolithic shell (shell route), B = panelised (measurement + direct
build), C = ambiguous or unclassified (a person or the agent decides).

scene.small_parts (plan mode `undo`, redaction 1 section 16): zavod `analyze_layers_for_optimize.ms`
(SHA256 1a351fba9a1c415e6e4384e20c0d16310120c887129ba5eefeb0d9c4515747a8), `move_fasteners_to_optimize.ms`
(d903f1fbb10e3cd780de43e58d98d9cd594e848fffec7e1100cc6ae04da0d7b9), `move_guess_optimize.ms`
(5e6236a4bc562c4b3a2028869459319143c276fcd944b78d063a1117e4a27f42) are the idea only; not copied (#853).
Measured defect T08: substring keys hit Studio, Minute, Шпиль, М120, Стеклопакет and nodes already in `optimize`
are counted again. Here keys match whole words only (Latin and Cyrillic, separators `_ - .`, space and digits),
size thresholds are in metres and nodes already on the `optimize` layer are skipped.
"""
import math
import re

# ---- scene.source_class: rule D066 ----------------------------------------------------------------------------
WELD_M = 1e-4             # dt_ai.spec.mesh.WELD_M
PANEL_HINT_SHARE = 0.5    # dt_ai.spec.mesh.PANEL_HINT_SHARE [D066]
SHARE_AT = 1e-9           # dt_ai.spec.source_class._SHARE_AT
MONOLITHIC = 'monolithic'
PANELISED = 'panelised'
AMBIGUOUS = 'ambiguous'
ROUTES = {MONOLITHIC: 'dt spec extract', PANELISED: 'measurement+direct-build', AMBIGUOUS: 'person or agent decides'}
LEVEL_RULE = {MONOLITHIC: 'A', PANELISED: 'B', AMBIGUOUS: 'C'}


class SourceClassError(ValueError):
    """The metrics do not decide a class, or the mesh is unusable. Fail closed: no default class."""


class _Sets:
    def __init__(self, n):
        self.parent = list(range(n))

    def find(self, i):
        p = self.parent
        root = i
        while p[root] != root:
            root = p[root]
        while p[i] != root:
            p[i], i = root, p[i]
        return root

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def _weld(verts):
    """Representative index per vertex, the pilot's rule: eight half-shifted grids of WELD_M, a cluster wider than
    WELD_M falls back to the plain grid (dt_ai.spec.mesh._weld). Representatives are the first vertex of a cell."""
    n = len(verts)
    sets = _Sets(n)
    grids = []
    for sx in (0.0, 0.5):
        for sy in (0.0, 0.5):
            for sz in (0.0, 0.5):
                first = {}
                grid = []
                for i, (x, y, z) in enumerate(verts):
                    key = (math.floor(x / WELD_M + sx), math.floor(y / WELD_M + sy), math.floor(z / WELD_M + sz))
                    j = first.setdefault(key, i)
                    grid.append(j)
                    if j != i:
                        sets.union(j, i)
                grids.append(grid)
    rep = [sets.find(i) for i in range(n)]
    lo = {}
    hi = {}
    for i, r in enumerate(rep):
        p = verts[i]
        if r in lo:
            lo[r] = [min(a, b) for a, b in zip(lo[r], p)]
            hi[r] = [max(a, b) for a, b in zip(hi[r], p)]
        else:
            lo[r] = list(p)
            hi[r] = list(p)
    for i, r in enumerate(rep):
        if max(h - l for h, l in zip(hi[r], lo[r])) > WELD_M:
            rep[i] = grids[0][i]
    return rep


def _check_mesh(verts, tris):
    if not isinstance(verts, (list, tuple)) or not isinstance(tris, (list, tuple)):
        raise SourceClassError('unsupported mesh: vertices (N, 3) and triangles (M, 3) are required')
    if not verts or not tris:
        raise SourceClassError('empty part list')
    vs = []
    for p in verts:
        if not isinstance(p, (list, tuple)) or len(p) != 3:
            raise SourceClassError('unsupported mesh: vertices (N, 3) and triangles (M, 3) are required')
        q = []
        for c in p:
            if isinstance(c, bool) or not isinstance(c, (int, float)):
                raise SourceClassError('unsupported vertices: ' + repr(c)[:40])
            if not math.isfinite(c):
                raise SourceClassError('non-finite vertex coordinate')
            q.append(float(c))
        vs.append(q)
    ts = []
    for t in tris:
        if not isinstance(t, (list, tuple)) or len(t) != 3:
            raise SourceClassError('unsupported mesh: vertices (N, 3) and triangles (M, 3) are required')
        row = []
        for i in t:
            if isinstance(i, bool) or not isinstance(i, (int, float)):
                raise SourceClassError('unsupported triangle index type')
            if isinstance(i, float) and (not math.isfinite(i) or i != int(i)):
                raise SourceClassError('fractional or non-finite triangle index')
            i = int(i)
            if i < 0 or i >= len(vs):
                raise SourceClassError('triangle index out of range')
            row.append(i)
        ts.append(row)
    return vs, ts


def _area(a, b, c):
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    return math.sqrt((uy * vz - uz * vy) ** 2 + (uz * vx - ux * vz) ** 2 + (ux * vy - uy * vx) ** 2) / 2.0


def _closed_shell(tris):
    """Every undirected edge used by exactly two triangles (winding ignored, as the pilot)."""
    if len(tris) < 4:
        return False
    counts = {}
    for a, b, c in tris:
        if len({a, b, c}) < 3:
            return False
        for i, j in ((a, b), (b, c), (c, a)):
            e = (i, j) if i < j else (j, i)
            counts[e] = counts.get(e, 0) + 1
    return bool(counts) and all(n == 2 for n in counts.values())


def source_facts(verts, tris):
    """{'parts', 'largest_share', 'shell', 'class', 'route', 'level', 'area_m2', 'triangles'} of one mesh in metres.

    `class` is monolithic | panelised | ambiguous (share within SHARE_AT of PANEL_HINT_SHARE, no shell, > 1 part).
    Raises SourceClassError for an unusable mesh."""
    vs, ts = _check_mesh(verts, tris)
    rep = _weld(vs)
    tris_w = [[rep[i] for i in t] for t in ts]
    areas = [_area(vs[a], vs[b], vs[c]) for a, b, c in tris_w]
    if not all(math.isfinite(x) for x in areas):
        raise SourceClassError('non-finite triangle area')
    total = math.fsum(areas)
    if not math.isfinite(total) or total <= 0.0:
        raise SourceClassError('total area is not a positive finite number')
    sets = _Sets(len(vs))
    for a, b, c in tris_w:
        sets.union(a, b)
        sets.union(a, c)
    groups = {}
    for k, t in enumerate(tris_w):
        groups.setdefault(sets.find(t[0]), []).append(k)
    parts = sorted(groups.values(), key=lambda g: math.fsum(areas[k] for k in g), reverse=True)
    shares = [math.fsum(areas[k] for k in g) / total for g in parts]
    if any(not math.isfinite(s) for s in shares):
        raise SourceClassError('non-finite area share')
    largest = shares[0]
    shell = any(_closed_shell([tris_w[k] for k in g]) for g in parts)
    cls = decide(len(parts), largest, shell)
    return {'parts': len(parts), 'largest_share': largest, 'shell': shell, 'class': cls, 'route': ROUTES[cls],
            'level': LEVEL_RULE[cls], 'area_m2': total, 'triangles': len(ts)}


def decide(n_parts, largest, shell):
    """Rule D066 (dt_ai.spec.source_class._decide) with `ambiguous` instead of an exception at the threshold."""
    if shell or n_parts == 1:
        return MONOLITHIC
    if abs(largest - PANEL_HINT_SHARE) <= SHARE_AT:
        return AMBIGUOUS
    return PANELISED if largest < PANEL_HINT_SHARE else MONOLITHIC


def merge_meshes(meshes):
    """[{'verts', 'faces'}] (HostAdapter.mesh, metres, world space) -> one (verts, tris) of the whole source."""
    verts, tris = [], []
    for m in meshes:
        base = len(verts)
        verts.extend(m['verts'])
        tris.extend([[base + i for i in f] for f in m['faces']])
    return verts, tris


# ---- scene.small_parts ----------------------------------------------------------------------------------------
OPTIMIZE_LAYER = 'optimize'
SOURCE_LAYER_PROP = 'agr_source_layer'
# whole words (case-insensitive, after the separators split); own list of fastener / angle / flashing words,
# Latin and Russian, singular and plural. `stud` is a key: Studio does not match it any more (T08).
KEYWORDS = frozenset((
    'bolt', 'bolts', 'screw', 'screws', 'nut', 'nuts', 'washer', 'washers', 'rivet', 'rivets', 'anchor', 'anchors',
    'stud', 'studs', 'fastener', 'fasteners', 'fixing', 'fixings', 'bracket', 'brackets', 'clamp', 'clamps',
    'hinge', 'hinges', 'flashing', 'flashings', 'angle', 'angles', 'hardware',
    'болт', 'болты', 'винт', 'винты', 'гайка', 'гайки', 'шайба', 'шайбы', 'саморез', 'саморезы', 'заклепка',
    'заклёпка', 'заклепки', 'заклёпки', 'анкер', 'анкеры', 'шпилька', 'шпильки', 'крепеж', 'крепёж', 'метиз',
    'метизы', 'кронштейн', 'кронштейны', 'хомут', 'хомуты', 'уголок', 'уголки', 'отлив', 'отливы', 'петля',
    'петли',
))
WORD_SPLIT = re.compile(r'[\s_.\-0-9]+')
DEFAULTS = {'max_extent_m': 0.15, 'max_faces': None, 'keywords': None, 'layer': OPTIMIZE_LAYER}


def words(name):
    """Whole words of a node name: split on `_ - .`, whitespace and digits; lower case; empty pieces dropped."""
    return [w for w in WORD_SPLIT.split(str(name).lower()) if w]


def small_options(options):
    out = dict(DEFAULTS)
    for k, v in (options or {}).items():
        if k not in DEFAULTS:
            raise ValueError('scene.small_parts: unknown option {!r}; known {}'.format(k, sorted(DEFAULTS)))
        out[k] = v
    ext = out['max_extent_m']
    if ext is not None and (isinstance(ext, bool) or not isinstance(ext, (int, float)) or not math.isfinite(ext)
                            or ext <= 0):
        raise ValueError('scene.small_parts: max_extent_m must be metres > 0 or null')
    mf = out['max_faces']
    if mf is not None and (isinstance(mf, bool) or not isinstance(mf, int) or mf < 1):
        raise ValueError('scene.small_parts: max_faces must be an integer >= 1 or null')
    kw = out['keywords']
    if kw is not None:
        if not isinstance(kw, list) or not kw or not all(isinstance(w, str) and words(w) == [w.lower()] for w in kw):
            raise ValueError('scene.small_parts: keywords must be a non-empty list of single words')
    if not isinstance(out['layer'], str) or not out['layer'].strip():
        raise ValueError('scene.small_parts: layer must name a layer')
    return out


def small_part_reasons(name, extent_m, faces, opts):
    """[(code, detail)] why a node is a small part: `keyword` (a whole word), `small_size` (largest bbox extent in
    metres <= max_extent_m and, when max_faces is set, faces <= max_faces). Empty: not a small part."""
    keys = frozenset(w.lower() for w in opts['keywords']) if opts['keywords'] else KEYWORDS
    out = []
    hit = sorted(set(w for w in words(name) if w in keys))
    if hit:
        out.append(('keyword', 'whole word ' + ', '.join(hit)))
    lim = opts['max_extent_m']
    if lim is not None and extent_m is not None and math.isfinite(extent_m) and extent_m <= lim:
        if opts['max_faces'] is None or (faces is not None and faces <= opts['max_faces']):
            out.append(('small_size', 'largest extent {:.4f} m <= {} m'.format(extent_m, lim)))
    return out


def small_parts_plan(items, opts):
    """items: [{'ref', 'name', 'layer', 'extent_m', 'faces'}] -> (findings by name, done names, skipped).

    Nodes already on the target layer are skipped (never counted again, T08)."""
    findings, done, skipped = {}, [], []
    for it in items:
        if it['layer'] == opts['layer']:
            skipped.append((it['name'], 'already on layer ' + opts['layer']))
            findings[it['name']] = []
            continue
        if it.get('group_member'):  # T08: a member left its group head's layer
            skipped.append((it['name'], 'group member: moving one member takes it out of its group layer (T08); '
                                       'ungroup first'))
            findings[it['name']] = []
            continue
        reasons = small_part_reasons(it['name'], it['extent_m'], it['faces'], opts)
        findings[it['name']] = reasons
        if reasons:
            done.append(it['name'])
    return findings, done, skipped
