"""new-case: AGR Tools 1.0 (#1024) UDIM -> ID view logic, stdlib only; owned by branch Q (improve/issue-1024-npm-to-vpm).

Pure logic for `udim_udims_to_ids` (udim.udims_to_ids, plan mode `read`, station 1.0.25); no pymxs, the core never
takes a host object. Shows which UDIM tile gives which material ID; writes nothing (owner default Q08).

Rule `face_tile` (Telegram `UDIM Viewer_V1.2.ms` sha256 1f284bbd1b1bb438a603e4f3838b6c9bb68580cea94ab5ce66dcc128b62c2f95,
read for the rule only, nothing copied, #853; measured T02/udim_viewer_v12): the tile of a face is the tile of its
UV centroid, floor per axis, ID = UDIM - 1000. A centroid with U < 0, U >= 10 or V < 0, or a tile above 1100 (ID >
100) has no UDIM ID: the face is `ambiguous`, never clamped.

Defects of GeoAGR «UDIMs -> IDs» `btn_ids_as_udims` (GeoAGR.ms:41355-41560) not repeated (regression tests in
tests/max_tools/test_agr_tools_npm_to_vpm.py):
* U1 Editable_Mesh path: the tile of the FIRST UV vertex of the face, not of the face (:41484-41494);
* U2 a negative tile is clamped to ID 1 (:41498) and U >= 10 runs into the next row (u 10.2 -> ID 11 = UDIM 1011);
* U3 Unwrap path: `abs(poi.x as integer)` truncates toward zero and mirrors negatives (:41452: u -0.5 -> ID 1);
* U4 it WRITES the material IDs (setFaceMatID :41500, setSelectMatID :41454) and switches the Modify panel / adds an
  Unwrap_UVW (:41372-41377) -> here a read-only report, the stack and the IDs never change.
"""
import importlib.util
import math
from pathlib import Path


def _sibling(name, alias):
    spec = importlib.util.spec_from_file_location(alias, Path(__file__).with_name(name))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_udimtile = _sibling('udimtile_core.py', 'agr_tools_udimtile_core_view')

TOOL = 'udim.udims_to_ids'
OPTION_KEYS = {'faces'}
FIRST, LAST = 1001, 1100


def options(opts):
    opts = dict(opts or {})
    unknown = set(opts) - OPTION_KEYS
    if unknown:
        raise ValueError('unknown udim.udims_to_ids options: ' + ', '.join(sorted(unknown)))
    faces = opts.get('faces')
    if faces is not None and (not isinstance(faces, list) or not faces or
                              any(type(f) is not int or f <= 0 for f in faces)):
        raise ValueError('options.faces must be a non-empty list of 1-based faces or null')
    return {'faces': sorted(set(faces)) if faces else None}


def face_tile(pts):
    """(UDIM, None) of a face by the V1.2 rule (centroid, floor), or (None, reason) when it has no UDIM ID."""
    cu = sum(p[0] for p in pts) / len(pts)
    cv = sum(p[1] for p in pts) / len(pts)
    if not (math.isfinite(cu) and math.isfinite(cv)):
        return None, 'non-finite UV'
    fu, fv = math.floor(cu), math.floor(cv)
    if fu < 0 or fv < 0:
        return None, 'negative UV (centre {:.3f}, {:.3f})'.format(cu, cv)
    if fu > 9:
        return None, 'U >= 10 (centre {:.3f}, {:.3f}): outside the 10 UDIM columns'.format(cu, cv)
    tile = _udimtile.udim_tile(cu, cv)
    if tile > LAST:
        return None, 'tile {} > {}: ID > 100'.format(tile, LAST)
    return tile, None


def view(mesh, faces=None):
    """{'tiles': {UDIM: {'id', 'faces', 'mat_ids_now': {id: count}}}, 'ambiguous': [(face 0-based, reason)],
    'mismatch': [faces whose ID now differs from UDIM - 1000], 'faces': n}. Nothing is changed."""
    if mesh.get('uv_tris') is None:
        raise ValueError('no UV channel 1')
    scope = range(len(mesh['tris'])) if faces is None else [f - 1 for f in faces if 1 <= f <= len(mesh['tris'])]
    tiles, amb, mismatch = {}, [], []
    for f in scope:
        tile, why = face_tile([mesh['uvs'][i] for i in mesh['uv_tris'][f]])
        if tile is None:
            amb.append((f, why))
            continue
        row = tiles.setdefault(tile, {'id': tile - 1000, 'faces': 0, 'mat_ids_now': {}})
        row['faces'] += 1
        now = int(mesh['mat_ids'][f])
        row['mat_ids_now'][now] = row['mat_ids_now'].get(now, 0) + 1
        if now != tile - 1000:
            mismatch.append(f)
    return {'tiles': {k: tiles[k] for k in sorted(tiles)}, 'ambiguous': amb, 'mismatch': mismatch,
            'faces': len(list(scope))}


def findings_of(v):
    """[(code, faces 1-based, detail)]: faces without a UDIM ID are `udim_ambiguous` (the report fails)."""
    if not v['ambiguous']:
        return []
    reasons = sorted({w for _, w in v['ambiguous']})
    return [('udim_ambiguous', [f + 1 for f, _ in v['ambiguous']], '{} face(s) without a UDIM ID: {}'.format(
        len(v['ambiguous']), '; '.join(reasons[:4])))]


def rows_of(v):
    """Report rows: UDIM -> ID, faces, the IDs the faces have now."""
    return [{'udim': t, 'id': r['id'], 'faces': r['faces'],
             'mat_ids_now': {str(k): c for k, c in sorted(r['mat_ids_now'].items())}} for t, r in v['tiles'].items()]
