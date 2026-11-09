"""new-case: AGR Tools 0.9 (#979) finish map by legend logic, stdlib only (branch B).

Pure logic for `tex_finish_map` (tex.finish_map); no pymxs. Assigns a finish to every Multi/Sub material ID from a
colour-scheme legend (legend -> finish -> RAL -> colour/texture), plans horizontal seam rings and checks them back.

Source: pilot `jobs/TEC26-OKS/scripts/finish_map.py` (`validate_legend`, `validate_spec`, finish by ID,
`ring_cut`/`plan_cuts`) and the retro `docs/research/job-retro-tec26-oks-pr574.md` §«Engine candidates» were read for
the idea only (legend first, strict validation: 10 legend mutations -> 10 ValueError); no code is taken over.
Fixed defects of #979 §2 (regression tests in tests/max_tools/test_agr_tools_finish.py):
F1 parameters wired to one job (address, OKS, sheets) -> the legend is an input file (JSON or CSV), mandatory; the
   tool knows no address, no OKS and no sheet;
F2 render before the check against the sheet -> the legend and the IDs are validated before anything is built;
   an ID without a legend row (`finish_id_unmapped`) and a legend ID with no face (`finish_id_absent`) are findings;
F3 the ring cut is planned and checked: a seam outside the object's height (`seam_outside`) refuses the copy
   (fail-closed), the copy is checked back (each seam within +-1 mm, seams counted per facade).

Legend JSON: {"finishes": [{"name", "ral"?, "color"?: "#RRGGBB" | [r, g, b], "texture"?}], "ids": [{"id", "finish"}],
"seams_m"?: [height above the object's lowest point, metres]}. CSV columns: id, finish, ral, color, texture (a row
with an empty id only defines a finish). Unused finishes of the palette are listed, not an error.
"""
import csv
import io
import json
import math
import re

SEAM_TOL_M = 0.001
_RAL = re.compile(r'^RAL ?\d{4}$', re.IGNORECASE)
_HEX = re.compile(r'^#?[0-9A-Fa-f]{6}$')
_NAME = re.compile(r'^[A-Za-z0-9_][A-Za-z0-9_\- .]{0,62}$')
LEGEND_KEYS = {'finishes', 'ids', 'seams_m'}
FINISH_KEYS = {'name', 'ral', 'color', 'texture'}
CODES = ('finish_id_unmapped', 'finish_id_absent', 'seam_outside', 'finish_texture_missing')


def _unique(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise ValueError('legend: duplicate key ' + repr(k))
        out[k] = v
    return out


def _reject(value):
    raise ValueError('legend: non-finite number ' + value)


def _color(value, where):
    if value is None:
        return None
    if isinstance(value, str):
        if not _HEX.match(value.strip()):
            raise ValueError('{}: colour must be #RRGGBB: {!r}'.format(where, value))
        h = value.strip().lstrip('#')
        return [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    if (isinstance(value, list) and len(value) == 3 and
            all(type(c) is int and 0 <= c <= 255 for c in value)):
        return list(value)
    raise ValueError('{}: colour must be #RRGGBB or [r, g, b] 0..255: {!r}'.format(where, value))


def validate_legend(doc):
    """Normalised legend {'finishes': {name: {ral, color, texture}}, 'ids': {id: name}, 'seams_m': [...]}.
    Any defect is a ValueError naming it; nothing is guessed."""
    if not isinstance(doc, dict):
        raise ValueError('legend must be a JSON object')
    unknown = set(doc) - LEGEND_KEYS
    if unknown:
        raise ValueError('legend: unknown keys {}'.format(sorted(unknown)))
    rows = doc.get('finishes')
    if not isinstance(rows, list) or not rows:
        raise ValueError('legend: finishes must be a non-empty list')
    finishes = {}
    for i, row in enumerate(rows):
        where = 'legend finish {}'.format(i + 1)
        if not isinstance(row, dict) or 'name' not in row or set(row) - FINISH_KEYS:
            raise ValueError('{}: keys name, ral?, color?, texture? only'.format(where))
        name = row['name']
        if not isinstance(name, str) or not _NAME.match(name):
            raise ValueError('{}: name must be Latin letters, digits, _ - . space: {!r}'.format(where, name))
        if name in finishes:
            raise ValueError('legend: duplicate finish ' + repr(name))
        ral = row.get('ral')
        if ral is not None and (not isinstance(ral, str) or not _RAL.match(ral.strip())):
            raise ValueError('{}: RAL must look like "RAL 9010": {!r}'.format(where, ral))
        color = _color(row.get('color'), where)
        tex = row.get('texture')
        if tex is not None and (not isinstance(tex, str) or not tex.strip()):
            raise ValueError('{}: texture must be a file path'.format(where))
        if color is None and tex is None:
            raise ValueError('{}: finish {!r} has neither colour nor texture'.format(where, name))
        finishes[name] = {'ral': None if ral is None else 'RAL ' + ral.strip()[-4:], 'color': color, 'texture': tex}
    ids = {}
    maps = doc.get('ids')
    if not isinstance(maps, list) or not maps:
        raise ValueError('legend: ids must be a non-empty list of {id, finish}')
    for i, row in enumerate(maps):
        where = 'legend id row {}'.format(i + 1)
        if not isinstance(row, dict) or set(row) != {'id', 'finish'}:
            raise ValueError('{}: keys id and finish'.format(where))
        mid = row['id']
        if type(mid) is not int or not 1 <= mid <= 65535:
            raise ValueError('{}: material ID must be an integer 1..65535: {!r}'.format(where, mid))
        if mid in ids:
            raise ValueError('legend: duplicate ID {}'.format(mid))
        if row['finish'] not in finishes:
            raise ValueError('{}: finish {!r} is not in the legend'.format(where, row['finish']))
        ids[mid] = row['finish']
    seams = doc.get('seams_m', [])
    seams = validate_seams(seams)
    return {'finishes': finishes, 'ids': ids, 'seams_m': seams}


def validate_seams(seams):
    if not isinstance(seams, list):
        raise ValueError('legend: seams_m must be a list of heights in metres')
    out = []
    for s in seams:
        if isinstance(s, bool) or not isinstance(s, (int, float)) or not math.isfinite(s) or s <= 0:
            raise ValueError('legend: seam height must be a positive number of metres: {!r}'.format(s))
        out.append(float(s))
    if out != sorted(set(out)):
        raise ValueError('legend: seam heights must be ascending without repeats')
    return out


def parse_legend(text, kind):
    """kind 'json' | 'csv' -> validated legend. CSV: id, finish, ral, color, texture."""
    if kind == 'json':
        return validate_legend(json.loads(text, object_pairs_hook=_unique, parse_constant=_reject))
    if kind != 'csv':
        raise ValueError('legend file must be .json or .csv')
    reader = csv.DictReader(io.StringIO(text))
    cols = set(reader.fieldnames or [])
    if not {'id', 'finish'} <= cols or cols - {'id', 'finish', 'ral', 'color', 'texture'}:
        raise ValueError('legend CSV columns: id, finish, ral, color, texture')
    finishes, order, ids = {}, [], []
    for i, row in enumerate(reader):
        name = (row.get('finish') or '').strip()
        f = {'name': name}
        for k in ('ral', 'color', 'texture'):
            v = (row.get(k) or '').strip()
            if v:
                f[k] = v
        if name in finishes:
            if finishes[name] != f:
                raise ValueError('legend CSV row {}: finish {!r} defined twice differently'.format(i + 2, name))
        else:
            finishes[name] = f
            order.append(name)
        mid = (row.get('id') or '').strip()
        if mid:
            if not mid.isdigit():
                raise ValueError('legend CSV row {}: id must be an integer: {!r}'.format(i + 2, mid))
            ids.append({'id': int(mid), 'finish': name})
    return validate_legend({'finishes': [finishes[n] for n in order], 'ids': ids})


# ---- plan -------------------------------------------------------------------------------------------------
def _normal(pts):
    n = [0.0, 0.0, 0.0]
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        n[0] += a[1] * b[2] - a[2] * b[1]
        n[1] += a[2] * b[0] - a[0] * b[2]
        n[2] += a[0] * b[1] - a[1] * b[0]
    return n


def facade_of(normal):
    """Facade of a face by its horizontal normal: N, E, S, W; None for a roof/floor (|nz| dominates)."""
    nx, ny, nz = normal
    h = math.hypot(nx, ny)
    if h <= abs(nz) or h <= 1e-12:
        return None
    ang = math.degrees(math.atan2(ny, nx)) % 360.0
    return ('E', 'N', 'W', 'S')[int(((ang + 45.0) % 360.0) // 90.0)]


def facades(mesh, unit=1.0):
    """{facade: (zmin, zmax) in metres} of the wall faces."""
    out = {}
    for f in mesh['faces']:
        pts = [mesh['vertices'][i] for i in f]
        fac = facade_of(_normal(pts))
        if fac is None:
            continue
        zs = [p[2] * unit for p in pts]
        lo, hi = out.get(fac, (math.inf, -math.inf))
        out[fac] = (min(lo, min(zs)), max(hi, max(zs)))
    return out


def plan_object(name, mesh, legend, unit=1.0, seams_m=None):
    """One object: findings [(code, faces 1-based, detail)], rows ID -> finish, seam heights (world metres) and
    seams per facade. `ok` False -> no copy (fail-closed)."""
    seams = legend['seams_m'] if seams_m is None else validate_seams(seams_m)
    findings = []
    by_id = {}
    for f, mid in enumerate(mesh['ids']):
        by_id.setdefault(int(mid), []).append(f + 1)
    rows = []
    for mid, faces in sorted(by_id.items()):
        fin = legend['ids'].get(mid)
        if fin is None:
            findings.append(('finish_id_unmapped', faces, 'ID {} ({} faces) has no legend row'.format(mid, len(faces))))
            continue
        spec = legend['finishes'][fin]
        rows.append({'id': mid, 'finish': fin, 'ral': spec['ral'], 'color': spec['color'], 'texture': spec['texture'],
                     'faces': len(faces)})
    zs = [p[2] * unit for p in mesh['vertices']]
    zmin, zmax = min(zs), max(zs)
    cuts = []
    for s in seams:
        z = zmin + s
        if not zmin + SEAM_TOL_M < z < zmax - SEAM_TOL_M:
            findings.append(('seam_outside', [], 'seam at {:.3f} m above the base is outside the object height '
                                                 '{:.3f} m: the ring cannot be cut'.format(s, zmax - zmin)))
            continue
        cuts.append(round(z, 9))
    per_facade = {fac: sum(1 for z in cuts if lo + SEAM_TOL_M < z < hi - SEAM_TOL_M)
                  for fac, (lo, hi) in sorted(facades(mesh, unit).items())}
    return {'object': name, 'findings': findings, 'ids': rows, 'cuts_z_m': cuts, 'base_z_m': round(zmin, 9),
            'seams_per_facade': per_facade}


def plan(objects, legend, unit=1.0, seams_m=None):
    """objects: [(key, name, mesh)] -> per-object plans; a legend ID with no face in the selection is
    `finish_id_absent` on every object (the legend and the model disagree)."""
    if not objects:
        raise ValueError('nothing to paint')
    plans = [dict(plan_object(name, mesh, legend, unit, seams_m), key=key) for key, name, mesh in objects]
    used = {int(m) for _, _, mesh in objects for m in mesh['ids']}
    absent = sorted(set(legend['ids']) - used)
    for p in plans:
        for mid in absent:
            p['findings'].append(('finish_id_absent', [], 'legend ID {} ({}) has no face on the selection'.format(
                mid, legend['ids'][mid])))
    unused = sorted(set(legend['finishes']) - set(legend['ids'].values()))
    return {'plans': plans, 'unused_finishes': unused}


def seam_readback(z_values_m, cuts, tol=SEAM_TOL_M):
    """Per planned cut height: the nearest vertex height and whether it is within tol (+-1 mm)."""
    out = []
    for z in cuts:
        near = min(z_values_m, key=lambda v: abs(v - z)) if z_values_m else None
        out.append({'z_m': z, 'nearest_m': None if near is None else round(near, 9),
                    'ok': near is not None and abs(near - z) <= tol})
    return out
