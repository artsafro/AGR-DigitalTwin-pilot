"""new-case: R3 railing members and quad meshes from a level parapet polyline.

Stdlib only; coordinates and dimensions are metres. Host adapters own publication,
material authoring and mesh storage. Role IDs are not approved library finishes.
"""
from bisect import bisect_right
from math import ceil, dist, hypot, isfinite

TYPES = ('glass_posts', 'posts_handrail', 'posts_handrail_infill')
PROFILES = ('vpm', 'npm')
REPRESENTATIONS = ('geometry', 'opacity')
ROLE_IDS = {'post': 1, 'top_rail': 2, 'glass': 3, 'infill': 4, 'opacity': 5}
MIN_M = 1e-5
MAX_BAYS = 10_000


def _number(value, name, low, high, *, inclusive=False):
    if (type(value) not in (float, int) or not low <= value <= high
            or not isfinite(value) or (not inclusive and value == low)):
        raise ValueError(f'{name}: expected a finite number in {"[" if inclusive else "("}{low}, {high}]')
    return float(value)


def _keys(doc, required, optional=()):
    if not isinstance(doc, dict) or set(doc) - set(required) - set(optional) or set(required) - set(doc):
        raise ValueError(f'expected keys {sorted(required)}, optional {sorted(optional)}; got {list(doc) if isinstance(doc, dict) else type(doc).__name__}')


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _normal(u):
    return -u[1], u[0]


def _unit(a, b):
    length = dist(a, b)
    if length <= MIN_M:
        raise ValueError('spline has an edge at or below 0.01 mm')
    return (b[0] - a[0]) / length, (b[1] - a[1]) / length


def _join(u, v):
    d = 1 + _dot(u, v)
    if d < .125:  # <= four half-widths of miter extension
        raise ValueError('spline has a reversal or an acute miter')
    return (-(u[1] + v[1]) / d, (u[0] + v[0]) / d)


def _crossing(a, b, c, d):
    if any(max(a[i], b[i]) < min(c[i], d[i]) or max(c[i], d[i]) < min(a[i], b[i]) for i in (0, 1)):
        return False

    def side(p, q, r):
        return _cross((q[0] - p[0], q[1] - p[1]), (r[0] - p[0], r[1] - p[1]))

    return side(a, b, c) * side(a, b, d) <= 0 and side(c, d, a) * side(c, d, b) <= 0


class _Path:
    def __init__(self, points, closed, corners):
        if not isinstance(points, (list, tuple)) or not (3 if closed else 2) <= len(points) <= 2048:
            raise ValueError('spline requires 2–2048 points (at least 3 if closed)')
        if any(not isinstance(p, (list, tuple)) or len(p) != 3 for p in points):
            raise ValueError('points must be xyz triples in metres')
        pts = [tuple(_number(x, 'coordinate', -100_000, 100_000, inclusive=True) for x in p) for p in points]
        if len(set(pts)) != len(pts):
            raise ValueError('duplicate spline points; do not repeat the closing point')
        if any(p[2] != pts[0][2] for p in pts):
            raise ValueError('only level splines are supported; split changes of datum into separate inputs')
        self.pts = pts + [pts[0]] if closed else pts
        self.station = [0.]
        edges = list(zip(self.pts, self.pts[1:]))
        self.tangents = [_unit(a, b) for a, b in edges]
        for i, (a, b) in enumerate(edges):
            self.station.append(self.station[-1] + dist(a, b))
            for j in range(i - 1):
                if closed and j == 0 and i == len(edges) - 1:
                    continue
                if _crossing(a, b, *edges[j]):
                    raise ValueError(f'spline self-intersects at edges {j} and {i}')
        tangents = self.tangents
        self.joins = [_join(tangents[i-1], tangents[i]) for i in range(1, len(edges))]
        self.joins.insert(0, _join(tangents[-1], tangents[0]) if closed else _normal(tangents[0]))
        self.joins.append(self.joins[0] if closed else _normal(tangents[-1]))
        if corners is None:
            corners = [i for i in range(0 if closed else 1, len(edges))
                       if abs(_cross(tangents[i-1], tangents[i])) > 1e-8]
        elif (not isinstance(corners, list) or any(type(i) is not int or not 0 <= i < len(pts) for i in corners)
              or len(set(corners)) != len(corners)):
            raise ValueError('corners must contain distinct point indices')
        self.anchors = sorted({0, len(edges), *corners})

    def section(self, s, *, miter=False):
        if s == self.station[-1]:
            i = len(self.tangents) - 1
            return self.pts[-1], self.joins[-1] if miter else _normal(self.tangents[i])
        i = bisect_right(self.station, s) - 1
        p, t = self.pts[i], self.tangents[i]
        d = s - self.station[i]
        if d == 0:
            return p, self.joins[i]
        return (p[0] + d * t[0], p[1] + d * t[1], p[2]), _normal(t)

    def stations(self, a, b):
        return [a, *(s for s in self.station if a < s < b), b]


def _mesh(role, vertices, faces, **details):
    return dict(role=role, material_id=ROLE_IDS[role], vertices=vertices, faces=faces, **details)


def _rings(role, rings, closed=False):
    vertices = [p for ring in rings for p in ring]
    faces = []
    for i in range(len(rings) if closed else len(rings) - 1):
        a, b = 4*i, 4*((i+1) % len(rings))
        faces.extend((a+j, a+(j+1)%4, b+(j+1)%4, b+j) for j in range(4))
    if not closed:
        faces += [(3, 2, 1, 0), tuple(range(len(vertices)-4, len(vertices)))]
    return _mesh(role, vertices, faces)


def _post(p, n, width, depth, bottom, top):
    mag = hypot(*n)
    nx, ny = n[0] / mag, n[1] / mag
    rings = [[(p[0]+ny*x+nx*y, p[1]-nx*x+ny*y, p[2]+z)
              for x, y in ((-width/2, depth/2), (-width/2, -depth/2),
                           (width/2, -depth/2), (width/2, depth/2))] for z in (bottom, top)]
    return _rings('post', rings)


def _sweep(path, stations, role, width, bottom, top, closed=False):
    rings = []
    for s in stations:
        p, n = path.section(s, miter=True)
        rings.append([(p[0]+n[0]*x, p[1]+n[1]*x, p[2]+z)
                      for x, z in ((-width/2, bottom), (width/2, bottom), (width/2, top), (-width/2, top))])
    for i, (a, b) in enumerate(zip(rings, rings[1:] + rings[:1] if closed else rings[1:])):
        pa, pb = path.section(stations[i])[0], path.section(stations[(i+1) % len(stations)])[0]
        u = _unit(pa, pb)
        if any(_dot((b[j][0]-a[j][0], b[j][1]-a[j][1]), u) <= MIN_M for j in (0, 1)):
            raise ValueError(f'{role}: section folds at a short miter')
    return _rings(role, rings, closed)


def _opacity(path, a, b, d, rail, panel, post_top, trim):
    bottom = min(0., d['post_bottom'])
    height = d['height'] - bottom
    bay = b - a
    half = d['post_width'] / 2 / bay
    rectangles = [(0., half, (d['post_bottom']-bottom)/height, (post_top-bottom)/height, 'post'),
                  (1-half, 1., (d['post_bottom']-bottom)/height, (post_top-bottom)/height, 'post')]
    if rail:
        rectangles.append((0., 1., (height-d['rail_height'])/height, 1., 'top_rail'))
    if panel:
        rectangles.append((trim/bay, 1-trim/bay, (d['panel_bottom']-bottom)/height,
                           (d['panel_top']-bottom)/height, 'glass' if not rail else 'infill'))
    stations = path.stations(a, b)
    result = []
    for x, y in zip(stations, stations[1:]):
        p, q = path.section(x)[0], path.section(y)[0]
        verts = [(v[0], v[1], v[2]+z) for v, z in ((p, bottom), (q, bottom), (q, d['height']), (p, d['height']))]
        result.append(_mesh('opacity', verts, [(0, 1, 2, 3)], mask_rects=rectangles,
                            u_limits=((x-a)/bay, (y-a)/bay)))
    return result


def build_railing(document, kind, profile='vpm', representation='geometry'):
    """Build independent inset meshes plus a station/readback ledger; no DCC imports."""
    for field, value, allowed in (('type', kind, TYPES), ('profile', profile, PROFILES),
                                  ('representation', representation, REPRESENTATIONS)):
        if value not in allowed:
            raise ValueError(f'unsupported {field}: {value!r}')
    if representation == 'opacity' and profile != 'npm':
        raise ValueError('opacity representation is NPM-only')
    _keys(document, ('points', 'closed', 'dimensions'), ('corners',))
    closed = document['closed']
    if type(closed) is not bool:
        raise ValueError('closed must be a boolean')
    path = _Path(document['points'], closed, document.get('corners'))
    rail, panel = kind != 'glass_posts', kind != 'posts_handrail'
    needed = ['height', 'max_step', 'post_width', 'post_depth']
    if rail:
        needed += ['rail_width', 'rail_height']
    if panel:
        needed += ['panel_bottom', 'panel_top', 'panel_depth', 'clearance']
    input_dims = document['dimensions']
    _keys(input_dims, needed, ('post_bottom',) if rail else ('post_bottom', 'post_top'))
    d = {k: _number(input_dims[k], k, 0 if k == 'panel_bottom' else MIN_M, 100,
                    inclusive=k == 'panel_bottom') for k in needed}
    post_top = d['height'] - d['rail_height'] if rail else _number(input_dims.get('post_top', d['height']), 'post_top', MIN_M, d['height'], inclusive=True)
    d['post_bottom'] = _number(input_dims.get('post_bottom', 0.), 'post_bottom', -10, 0, inclusive=True)
    if post_top <= MIN_M or (panel and not d['panel_bottom']+MIN_M < d['panel_top'] <= (post_top if rail else d['height'])):
        raise ValueError('invalid member heights')
    trim = hypot(d['post_width'], d['post_depth'])/2 + d.get('clearance', 0.)
    s = path.station
    stations, steps = [0.], []
    for i, j in zip(path.anchors, path.anchors[1:]):
        length = s[j] - s[i]
        count = ceil(length / d['max_step'])
        if len(stations) + count - 1 > MAX_BAYS:
            raise ValueError(f'spline exceeds {MAX_BAYS} bays')
        step = length / count
        if step <= 2*trim + MIN_M:
            raise ValueError('bay too short to clear the post profiles')
        steps.append(step)
        stations.extend(s[i]+step*k for k in range(1, count))
        stations.append(s[j])
    post_sections = [path.section(x) for x in (stations[:-1] if closed else stations)]
    if representation == 'geometry':
        meshes = [_post(p, n, d['post_width'], d['post_depth'], d['post_bottom'], post_top) for p, n in post_sections]
        if rail:
            meshes.append(_sweep(path, s[:-1] if closed else s, 'top_rail', d['rail_width'], post_top, d['height'], closed))
        if panel:
            meshes.extend(_sweep(path, path.stations(a+trim, b-trim), 'infill' if rail else 'glass',
                                 d['panel_depth'], d['panel_bottom'], d['panel_top'])
                          for a, b in zip(stations, stations[1:]))
    else:
        meshes = [m for a, b in zip(stations, stations[1:]) for m in _opacity(path, a, b, d, rail, panel, post_top, trim)]
    return dict(type=kind, profile=profile, representation=representation,
                posts=[p for p, _ in post_sections], bay_stations_m=stations, run_steps_m=steps,
                triangle_count=sum(2*len(m['faces']) for m in meshes),
                materials={m['material_id']: m['role'] for m in meshes}, meshes=meshes)
