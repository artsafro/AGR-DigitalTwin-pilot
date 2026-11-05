"""new-case: AGR Tools 0.7.0 pre-delivery checks (#860), stdlib only, no pymxs.

Twelve read-only checks of plan version 0.7 (docs/plans/agr-tools-suite.json): scene.census, scene.units,
model.perimeter_drop, tex.material_type, ucx.audit, atlas.sets_count, qa.fbx_split, qa.glass, qa.preflight,
qa.scene_hygiene, qa.xform, qa.zero_area. suite_max.py reads the scene into plain rows; this module only
judges them, so every rule runs under plain pytest. Nothing here or in the glue edits the scene (GeoAGR D6).

Base: GeoAGR 13.64 (author Artem, GeoAGR-private@7cd117c, C:/x/geoagr-base/GeoAGR.ms). Adapted lines are
named per function with their changes. Team scripts give an idea and a threshold, not code [D180].
Thresholds are the locked standards (standards/NPM_STANDARD.yaml, VPM_STANDARD.yaml); tests pin them.

Row contract (one dict per scene node, built by suite_max.py; distances in metres):
  key, name, fbx (AGR_EXPORT_PATH or None), superclass ('geometry'|'shape'|'light'|'camera'|'helper'|
  'system'|...), cls, faces, verts, materials [{name, cls, maps, missing, opacity}], parent, children,
  group, animated, modifiers [names], layer, scale (3), rotation (quaternion x,y,z,w), mirror,
  bbox ((x,y,z),(x,y,z)), instances, zero_m (AGR_ZERO_M or None), mesh {'verts', 'tris'} (lazy callable
  allowed), poly_edges (optional).
Scene dict for scene.units: unit_type, unit_scale, file_in_gamma, file_out_gamma, path.
"""
import json
import math
import re

import agr_tools_checks_core as checks  # registered by runtime._load_core / the tests

# --- thresholds (pinned to standards/*.yaml by tests/max_tools/test_agr_tools_suite.py) --------------
PERIMETER_DROP_M = 1.0          # NPM geometry.ground_perimeter_extrude_down_m_min, VPM oks/ground_..._m_min
OKS_FBX_MAX = 20                # NPM archive.fbx_total.max 21 = 1 Ground + 20 OKS
OKS_OPAQUE_OBJECTS_MAX = 20     # NPM geometry.oks_opaque_objects_max
OKS_TRANSPARENT_OBJECTS_MAX = 20  # NPM geometry.oks_transparent_objects_max
GLASS_MATERIALS_MAX = 7         # NPM materials.transparent_materials_max, VPM materials.glass_slots_max
GLASS_OPACITY = 0.5             # NPM materials.transparent_material_opacity
OPACITY_TOL = 1e-3
SETS_MAX = {'oks': 40, 'ground': 20, 'GroundEl': 1, 'Flora': 1}  # plan row atlas.sets_count
ROOF_EXTRA_SETS = 1             # NPM materials.texture_sets_per_oks.with_usable_roof_max - default_max
ALLOWED_MATERIALS = ('Standardmaterial', 'PhysicalMaterial', 'Multimaterial')  # NPM materials.allowed_shaders
XFORM_TOL = 1e-6                # scale/rotation counted as reset within this tolerance
ZERO_EDGE_M = 1e-5              # an edge shorter than 0.01 mm is zero-length (float32 FBX noise level)
ZERO_AREA_M2 = 1e-10            # a triangle below 1e-10 m2 has zero area
SYSTEM_UNIT = 'meters'          # NPM/VPM units.linear
FILE_GAMMA = 1.0                # GeoAGR btn_set_alpha GeoAGR.ms:12554 sets FileIn/FileOutGamma = 1.0

TOOLS = ('census', 'units', 'perimeter_drop', 'material_type', 'ucx_audit', 'sets_count', 'fbx_split',
         'glass', 'preflight', 'scene_hygiene', 'xform', 'zero_area')
PLAN_ROW = {'census': 'scene.census', 'units': 'scene.units', 'perimeter_drop': 'model.perimeter_drop',
            'material_type': 'tex.material_type', 'ucx_audit': 'ucx.audit', 'sets_count': 'atlas.sets_count',
            'fbx_split': 'qa.fbx_split', 'glass': 'qa.glass', 'preflight': 'qa.preflight',
            'scene_hygiene': 'qa.scene_hygiene', 'xform': 'qa.xform', 'zero_area': 'qa.zero_area'}
PREFLIGHT = ('material_type', 'perimeter_drop', 'ucx_audit', 'sets_count', 'fbx_split', 'glass',
             'scene_hygiene', 'xform', 'zero_area', 'census')

CODES = {
    'census': {'missing_map'},
    'units': set(),
    'perimeter_drop': {'drop_short', 'drop_unmeasurable', 'at_threshold', 'fbx_unmapped', 'kind_unknown'},
    'material_type': {'mat_none', 'mat_class'},
    'ucx_audit': {'ucx_open', 'ucx_concave', 'ucx_material', 'ucx_name', 'ucx_intersect', 'ucx_unmeasurable',
                  'ucx_budget', 'ucx_orphan'},
    'sets_count': {'sets_limit', 'fbx_unmapped'},
    'fbx_split': {'fbx_count', 'fbx_objects', 'fbx_ground_missing', 'fbx_numbering', 'fbx_unmapped'},
    'glass': {'glass_not_separate', 'glass_objects', 'glass_materials', 'glass_maps', 'glass_opacity'},
    'scene_hygiene': {'hyg_non_mesh', 'hyg_animation', 'hyg_hierarchy', 'hyg_group', 'hyg_empty',
                      'hyg_modifier'},
    'xform': {'xform_scale', 'xform_rotation', 'xform_mirror', 'xform_parent', 'xform_unmeasurable'},
    'zero_area': {'zero_area_face', 'zero_length_edge', 'isolated_vertex', 'zero_unmeasurable'},
}
CODES['preflight'] = set().union(*(CODES[t] for t in PREFLIGHT))
SCENE_TOOLS = ('units',)  # report-level: objects [] + plan.findings, as the 0.5.0 GeoJSON report


class Rows:
    """Validated view of the glue rows: a missing field is an error naming it, never a default."""

    def __init__(self, rows):
        if not isinstance(rows, list) or not rows:
            raise ValueError('empty target set')
        seen = set()
        for r in rows:
            if not isinstance(r, dict) or 'key' not in r or 'name' not in r:
                raise ValueError('row without key/name: ' + repr(r)[:80])
            if r['key'] in seen:
                raise ValueError('duplicate target key: ' + repr(r['key']))
            seen.add(r['key'])
        self.rows = rows

    def __iter__(self):
        return iter(self.rows)


def _need(row, field):
    if field not in row:
        raise ValueError('row {} has no field {}'.format(row.get('name'), field))
    return row[field]


def _finite(*values):
    return all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in values)


def _add(found, key, code, detail, ids=()):
    found.setdefault(key, []).append((code, detail, tuple(ids)))


def _geo(row):
    """Mesh rows only: cameras, lights, helpers and shapes are qa.scene_hygiene's findings, not geometry's."""
    return _need(row, 'superclass') == 'geometry'


def _mesh(row):
    m = _need(row, 'mesh')
    if callable(m):
        m = m()
    if not isinstance(m, dict) or 'verts' not in m or 'tris' not in m:
        raise ValueError('row {} has no mesh verts/tris'.format(row.get('name')))
    return m['verts'], m['tris']


def _kind(row):
    """(model, role) of the row's FBX or None (unmapped)."""
    return checks.fbx_kind(row.get('fbx'))


def _materials(row):
    mats = _need(row, 'materials')
    if not isinstance(mats, list):
        raise ValueError('row {} materials is not a list'.format(row.get('name')))
    return mats


def _is_glass_material(m):
    name = str(m.get('name', ''))
    op = m.get('opacity')
    return 'glass' in name.lower() or (_finite(op) and op < 1.0 - OPACITY_TOL)


# --- scene.census -------------------------------------------------------------------------------------
def census(rows):
    """Census of the scene: per class, materials, maps (missing files are findings), bbox, instances.

    New (plan row scene.census, TEC26 census scripts' idea); read-only. Only a missing bitmap file is a
    finding; everything else is the summary of the report.
    """
    rows = Rows(rows)
    found, dropped = {}, []
    by_class, mats, maps, missing = {}, set(), set(), set()
    lo, hi = [math.inf] * 3, [-math.inf] * 3
    instanced = 0
    for r in rows:
        sc = str(_need(r, 'superclass'))
        by_class[sc] = by_class.get(sc, 0) + 1
        for m in _materials(r):
            mats.add(str(m.get('name')))
            for p in m.get('maps') or []:
                maps.add(p)
            for p in m.get('missing') or []:
                missing.add(p)
                _add(found, r['key'], 'missing_map', 'нет файла: ' + str(p))
        box = r.get('bbox')
        if box is not None:
            if not (len(box) == 2 and all(_finite(*c) for c in box)):
                dropped.append({'name': str(r['name']), 'reason': 'bbox not finite'})
            else:
                lo = [min(a, b) for a, b in zip(lo, box[0])]
                hi = [max(a, b) for a, b in zip(hi, box[1])]
        if int(_need(r, 'instances')) > 1:
            instanced += 1
    summary = {'objects': len(rows.rows), 'by_class': dict(sorted(by_class.items())), 'materials': len(mats),
               'maps': len(maps), 'missing_maps': sorted(missing), 'instanced_objects': instanced,
               'bbox_m': [lo, hi] if all(math.isfinite(v) for v in lo + hi) else None}
    return found, dropped, summary


# --- scene.units --------------------------------------------------------------------------------------
def units(scene):
    """System unit = metres, scale 1; FileIn/FileOut gamma per GeoAGR.

    adapted from GeoAGR 13.64 (author Artem), GeoAGR.ms:12547 btn_set_meters and :12554 btn_set_alpha;
    changes: a check instead of a setter (Set Meters does not rescale geometry, so fixing is a separate,
    confirmed action), every value reported with observed/expected. Fixes GeoAGR D5 at the source
    (texel 100x off in a centimetre scene). Unreadable value -> fail, never pass.
    """
    if not isinstance(scene, dict):
        raise ValueError('scene units not read')
    out = []

    def item(name, ok, observed, expected):
        out.append({'name': name, 'status': 'pass' if ok else 'fail', 'observed': observed, 'expected': expected})

    ut = scene.get('unit_type')
    item('system_unit', ut == SYSTEM_UNIT, str(ut), SYSTEM_UNIT)
    us = scene.get('unit_scale')
    item('system_scale', _finite(us) and abs(us - 1.0) <= 1e-9, repr(us), '1.0')
    for key in ('file_in_gamma', 'file_out_gamma'):
        g = scene.get(key)
        item(key, _finite(g) and abs(g - FILE_GAMMA) <= 1e-6, repr(g), repr(FILE_GAMMA))
    return out


# --- model.perimeter_drop -----------------------------------------------------------------------------
def perimeter_drop(rows):
    """Lowest point of every OKS/Ground mesh is >= 1 m below its ±0.000 (AGR_ZERO_M, metres).

    New (GeoAGR gap #10: no live check). The ±0.000 has no default: a mesh without AGR_ZERO_M is
    `drop_unmeasurable`, never measured against 0. Exactly 1 m is `at_threshold` (review), as 0.5.0.
    Only the perimeter meshes (exact suffix Main / Ground, checks.mesh_kind) are measured: MainGlass,
    GroundEl, Flora etc. stand above ±0.000 by design and are listed in summary `not_applicable`.
    A geometry mesh whose suffix is not one of those known kinds is `kind_unknown` (a finding, never a
    skip): a misnamed perimeter mesh must not disappear into `not_applicable`.
    """
    rows = Rows(rows)
    found, dropped, skipped = {}, [], []
    for r in rows:
        if checks.is_ucx(r['name']) or not _geo(r):
            continue
        mk = checks.mesh_kind(r['name'])
        if mk is None:
            _add(found, r['key'], 'kind_unknown',
                 'суффикс не Main/MainGlass/Ground/GroundGlass/GroundEl/GroundElGlass/Flora: ' + repr(r.get('name')))
            continue
        if mk not in ('Main', 'Ground'):
            skipped.append({'name': r['name'], 'kind': mk})
            continue
        if _kind(r) is None:
            _add(found, r['key'], 'fbx_unmapped', 'AGR_EXPORT_PATH не задан или не по маске: ' + repr(r.get('fbx')))
            continue
        zero = r.get('zero_m')
        verts, _ = _mesh(r)
        zs = [v[2] for v in verts]
        if not _finite(zero) or not zs or not _finite(*zs):
            _add(found, r['key'], 'drop_unmeasurable', 'нет AGR_ZERO_M или геометрии: ' + repr(zero))
            continue
        drop = zero - min(zs)
        if abs(drop - PERIMETER_DROP_M) <= 1e-6:
            _add(found, r['key'], 'at_threshold', 'опуск ровно {:.3f} м'.format(drop))
        elif drop < PERIMETER_DROP_M:
            _add(found, r['key'], 'drop_short', 'опуск {:.3f} м < {:.1f} м'.format(drop, PERIMETER_DROP_M))
    return found, dropped, {'not_applicable': skipped}


# --- tex.material_type --------------------------------------------------------------------------------
def material_type(rows):
    """Only Standard / Physical (and Multi/Sub holding them); Corona, VRay and others name the material.

    adapted from GeoAGR 13.64 (author Artem), GeoAGR.ms:65278 Prepare LowPoly (material class branch);
    changes: read-only, no collapse or conversion (D6); every sub-material is checked, not only the top.
    """
    rows = Rows(rows)
    found = {}
    for r in rows:
        if checks.is_ucx(r['name']) or not _geo(r):
            continue
        mats = _materials(r)
        if not mats:
            _add(found, r['key'], 'mat_none', 'нет материала')
        for m in mats:
            cls = str(m.get('cls'))
            if cls not in ALLOWED_MATERIALS:
                _add(found, r['key'], 'mat_class', '{}: {}'.format(m.get('name'), cls))
    return found, [], {}


# --- ucx.audit ----------------------------------------------------------------------------------------
def ucx_audit(rows, audit):
    """Existing UCX_ hulls: closed, convex, no material, name mask, SAT intersections, budget.

    audit = the shipped twinqa ucx_audit slice (ucx_audit_core.py). Merges GeoAGR Check Convex
    GeoAGR.ms:60910 and ucx_check.exe :60449 (misses containment, cuts names at a space): SAT pairs
    with containment instead; the full name is kept. Budget = checks_core.vpm_ucx_limit of the FBX.
    """
    rows = Rows(rows)
    found, dropped = {}, []
    ucx = [r for r in rows if checks.is_ucx(r['name'])]
    mains = {}
    for r in rows:
        if not checks.is_ucx(r['name']) and checks.mesh_kind(r['name']) in ('Main', 'Ground'):
            mains.setdefault(r.get('fbx'), []).append(r)
    hulls, tri_by_fbx, render_by_fbx = [], {}, {}
    for r in rows:
        if not checks.is_ucx(r['name']) and _geo(r):
            render_by_fbx[r.get('fbx')] = render_by_fbx.get(r.get('fbx'), 0) + int(_need(r, 'faces'))
    for r in ucx:
        verts, tris = _mesh(r)
        v = audit.classify([tuple(map(float, p)) for p in verts], [tuple(map(int, t)) for t in tris])
        if v.get('status') == 'review' or v.get('closed') is None:
            _add(found, r['key'], 'ucx_unmeasurable', str(v.get('reason') or v))
        else:
            if v.get('closed') is not True:
                _add(found, r['key'], 'ucx_open', 'оболочка не замкнута')
            if v.get('convex') is not True:
                _add(found, r['key'], 'ucx_concave', 'оболочка не выпуклая')
        if _materials(r):
            _add(found, r['key'], 'ucx_material', ', '.join(str(m.get('name')) for m in r['materials']))
        owner = mains.get(r.get('fbx')) or []
        main_name = owner[0]['name'] if len(owner) == 1 else ''
        if not owner:
            _add(found, r['key'], 'ucx_orphan', 'нет Main/Ground в том же FBX: ' + repr(r.get('fbx')))
        rep = audit.name_report([r['name']], main_name)
        if rep['mask_bad_count']:
            _add(found, r['key'], 'ucx_name', 'имя не по маске UCX_SM_{Address}_{Main|Ground}_NNN')
        hulls.append({'name': r['name'], 'verts': [tuple(map(float, p)) for p in verts],
                      'tris': [tuple(map(int, t)) for t in tris], 'key': r['key']})
        tri_by_fbx[r.get('fbx')] = tri_by_fbx.get(r.get('fbx'), 0) + len(tris)
    by_name = {h['name']: h['key'] for h in hulls}
    for item in audit.collision_findings([{k: h[k] for k in ('name', 'verts', 'tris')} for h in hulls]):
        if item.get('type') == 'not_run':
            continue  # per-hull problems are already reported above by classify
        for side in ('a', 'b'):
            key = by_name.get(item.get(side))
            if key is not None:
                _add(found, key, 'ucx_intersect', '{}: {} / {}'.format(item.get('type'), item.get('a'), item.get('b')))
    for fbx, n in tri_by_fbx.items():
        kind = checks.fbx_kind(fbx)
        if kind is None or kind[0] != 'vpm':
            continue
        limit = checks.vpm_ucx_limit(render_by_fbx.get(fbx, 0))
        if limit is not None and n > limit:
            for r in ucx:
                if r.get('fbx') == fbx:
                    _add(found, r['key'], 'ucx_budget', '{} треуг. UCX > {} в {}'.format(n, limit, fbx))
    return found, dropped, {'ucx_objects': len(ucx)}


# --- atlas.sets_count ---------------------------------------------------------------------------------
def sets_count(rows):
    """Opaque texture sets per FBX: OKS <= 40 (+1 usable roof), Ground <= 20, GroundEl 1, Flora 1.

    New (GeoAGR: NPM-2.1-5.b unreachable, NPM-2.1-4.c manual). A set = one opaque material (glass is
    not a set). Roof extra only when an object of the FBX has AGR_ROOF_SET = 1 (no implicit roof).
    """
    rows = Rows(rows)
    found = {}
    groups = {}
    for r in rows:
        if checks.is_ucx(r['name']) or not _geo(r):
            continue
        kind = _kind(r)
        if kind is None:
            _add(found, r['key'], 'fbx_unmapped', 'AGR_EXPORT_PATH не задан или не по маске: ' + repr(r.get('fbx')))
            continue
        mk = checks.mesh_kind(r['name'])
        bucket = mk if mk in ('GroundEl', 'Flora') else kind[1]
        g = groups.setdefault((r['fbx'], bucket), {'rows': [], 'sets': set(), 'roof': False})
        g['rows'].append(r)
        g['roof'] = g['roof'] or bool(r.get('roof_set'))
        for m in _materials(r):
            if str(m.get('cls')) != 'Multimaterial' and not _is_glass_material(m):
                g['sets'].add(str(m.get('name')))
    table = []
    for (fbx, bucket), g in sorted(groups.items()):
        limit = SETS_MAX[bucket] + (ROOF_EXTRA_SETS if bucket == 'oks' and g['roof'] else 0)
        n = len(g['sets'])
        table.append({'fbx': fbx, 'bucket': bucket, 'sets': n, 'limit': limit})
        if n > limit:
            for r in g['rows']:
                _add(found, r['key'], 'sets_limit', '{}: {} наборов > {} ({})'.format(fbx, n, limit, bucket))
    return found, [], {'sets': table}


# --- qa.fbx_split -------------------------------------------------------------------------------------
_PART = re.compile(r'_(\d{2})\.fbx$', re.IGNORECASE)


def fbx_split(rows):
    """FBX split: OKS FBX <= 20, opaque/transparent objects per OKS FBX <= 20 each, Ground FBX present,
    OKS parts numbered 01..N without gaps. New (GeoAGR gap #11: no check)."""
    rows = Rows(rows)
    found = {}
    files = {}
    for r in rows:
        kind = _kind(r)
        if kind is None:
            _add(found, r['key'], 'fbx_unmapped', 'AGR_EXPORT_PATH не задан или не по маске: ' + repr(r.get('fbx')))
            continue
        files.setdefault(r['fbx'], {'kind': kind, 'rows': []})['rows'].append(r)
    models = sorted({f['kind'][0] for f in files.values()})
    table = []
    for model in models:
        mine = {p: f for p, f in files.items() if f['kind'][0] == model}
        oks = sorted(p for p, f in mine.items() if f['kind'][1] == 'oks')
        grounds = [p for p, f in mine.items() if f['kind'][1] == 'ground']
        every = [r for f in mine.values() for r in f['rows']]
        if not grounds:
            for r in every:
                _add(found, r['key'], 'fbx_ground_missing', '{}: нет Ground FBX'.format(model.upper()))
        if len(oks) > OKS_FBX_MAX:
            for p in oks:
                for r in mine[p]['rows']:
                    _add(found, r['key'], 'fbx_count', '{} ОКС FBX > {}'.format(len(oks), OKS_FBX_MAX))
        if model == 'npm':
            parts = sorted(int(_PART.search(p).group(1)) for p in oks if _PART.search(p))
            if parts != list(range(1, len(parts) + 1)):
                for p in oks:
                    for r in mine[p]['rows']:
                        _add(found, r['key'], 'fbx_numbering', 'номера частей {} не 01..{:02d}'.format(
                            parts, len(parts)))
        for p in sorted(mine):
            f = mine[p]
            meshes = [r for r in f['rows'] if not checks.is_ucx(r['name']) and _geo(r)]
            glass = [r for r in meshes if str(checks.mesh_kind(r['name']) or '').endswith('Glass')]
            opaque = len(meshes) - len(glass)
            table.append({'fbx': p, 'model': model, 'role': f['kind'][1], 'opaque': opaque, 'transparent': len(glass)})
            if model == 'npm' and f['kind'][1] == 'oks':
                for n, cap, what in ((opaque, OKS_OPAQUE_OBJECTS_MAX, 'непрозрачных'),
                                     (len(glass), OKS_TRANSPARENT_OBJECTS_MAX, 'прозрачных')):
                    if n > cap:
                        for r in meshes:
                            _add(found, r['key'], 'fbx_objects', '{}: {} {} объектов > {}'.format(p, n, what, cap))
    return found, [], {'fbx': table}


# --- qa.glass -----------------------------------------------------------------------------------------
def glass(rows):
    """Glass: on a separate *Glass mesh, <= 20 translucent objects per FBX, <= 7 glass materials per FBX,
    no texture maps, NPM opacity 0.5.

    adapted from GeoAGR 13.64 (author Artem), GeoAGR.ms:65330-65375 Prepare LowPoly MainGlass branch;
    changes: D2 - the branch is reached by the exact suffix token (checks.mesh_kind), not a substring
    `case` that matched Main first; D3 - "no textures" counts the usedMaps ARRAY (an empty list is no
    maps), the old test against undefined fired on every material.
    """
    rows = Rows(rows)
    found = {}
    per_fbx = {}
    for r in rows:
        if checks.is_ucx(r['name']) or not _geo(r):
            continue
        is_glass_mesh = str(checks.mesh_kind(r['name']) or '').endswith('Glass')
        mats = _materials(r)
        gm = [m for m in mats if str(m.get('cls')) != 'Multimaterial' and _is_glass_material(m)]
        if gm and not is_glass_mesh:
            _add(found, r['key'], 'glass_not_separate', 'стекло на непрозрачном объекте: ' +
                 ', '.join(str(m.get('name')) for m in gm))
        if not is_glass_mesh:
            continue
        slot = per_fbx.setdefault(r.get('fbx'), {'rows': [], 'materials': set()})
        slot['rows'].append(r)
        for m in gm or [m for m in mats if str(m.get('cls')) != 'Multimaterial']:
            slot['materials'].add(str(m.get('name')))
            maps = m.get('maps')
            if not isinstance(maps, list):
                raise ValueError('material {} maps is not a list'.format(m.get('name')))
            if maps:
                _add(found, r['key'], 'glass_maps', '{}: {} карт'.format(m.get('name'), len(maps)))
            kind = _kind(r)
            if kind is not None and kind[0] == 'npm':
                op = m.get('opacity')
                if not _finite(op) or abs(op - GLASS_OPACITY) > OPACITY_TOL:
                    _add(found, r['key'], 'glass_opacity', '{}: {} != {}'.format(m.get('name'), op, GLASS_OPACITY))
    table = []
    for fbx, slot in sorted(per_fbx.items(), key=lambda kv: str(kv[0])):
        table.append({'fbx': fbx, 'objects': len(slot['rows']), 'materials': len(slot['materials'])})
        if len(slot['rows']) > OKS_TRANSPARENT_OBJECTS_MAX:
            for r in slot['rows']:
                _add(found, r['key'], 'glass_objects', '{}: {} > {}'.format(fbx, len(slot['rows']),
                                                                           OKS_TRANSPARENT_OBJECTS_MAX))
        if len(slot['materials']) > GLASS_MATERIALS_MAX:
            for r in slot['rows']:
                _add(found, r['key'], 'glass_materials', '{}: {} > {}'.format(fbx, len(slot['materials']),
                                                                             GLASS_MATERIALS_MAX))
    return found, [], {'glass': table}


# --- qa.scene_hygiene ---------------------------------------------------------------------------------
def scene_hygiene(rows):
    """Cameras/lights/bones/helpers/shapes, animation, hierarchy, groups, empty meshes, modifiers.

    adapted from GeoAGR 13.64 (author Artem), GeoAGR.ms:9136 RulesCheck_lowpoly checkboxes (dead UI, D7);
    changes: the rules are the current standards (NPM no_hierarchy_or_groups; VPM
    no_empty_unrelated_animation_or_modifier_objects, conflict #14: any non-mesh object fails), and
    every rule is always on.
    """
    rows = Rows(rows)
    found = {}
    for r in rows:
        sc = str(_need(r, 'superclass'))
        if sc != 'geometry':
            _add(found, r['key'], 'hyg_non_mesh', '{} ({})'.format(sc, r.get('cls')))
        if _need(r, 'animated'):
            _add(found, r['key'], 'hyg_animation', 'есть ключи анимации')
        if r.get('parent') or int(_need(r, 'children')):
            _add(found, r['key'], 'hyg_hierarchy', 'родитель {} / детей {}'.format(r.get('parent'), r['children']))
        if _need(r, 'group'):
            _add(found, r['key'], 'hyg_group', 'объект в группе')
        if sc == 'geometry' and int(_need(r, 'faces')) == 0:
            _add(found, r['key'], 'hyg_empty', '0 граней')
        mods = _need(r, 'modifiers')
        if mods:
            _add(found, r['key'], 'hyg_modifier', ', '.join(map(str, mods)))
    return found, [], {}


# --- qa.xform -----------------------------------------------------------------------------------------
def xform(rows):
    """Unreset scale / rotation / mirror and parents; the reset itself happens on export copies.

    adapted from GeoAGR 13.64 (author Artem), GeoAGR.ms:65536 Prepare LowPoly ResetXForm (destructive);
    changes: D6 - a check only, nothing is reset or collapsed here.
    """
    rows = Rows(rows)
    found = {}
    for r in rows:
        s, q = r.get('scale'), r.get('rotation')
        if not (isinstance(s, (list, tuple)) and len(s) == 3 and _finite(*s)
                and isinstance(q, (list, tuple)) and len(q) == 4 and _finite(*q)):
            _add(found, r['key'], 'xform_unmeasurable', 'scale/rotation не прочитаны')
            continue
        if any(abs(abs(v) - 1.0) > XFORM_TOL for v in s):
            _add(found, r['key'], 'xform_scale', 'масштаб {}'.format([round(v, 6) for v in s]))
        if bool(_need(r, 'mirror')) or any(v < 0 for v in s):
            _add(found, r['key'], 'xform_mirror', 'зеркальная матрица')
        w = abs(q[3]) / (math.sqrt(sum(v * v for v in q)) or 1.0)
        if 1.0 - w > XFORM_TOL:
            _add(found, r['key'], 'xform_rotation', 'поворот {:.4f}°'.format(math.degrees(2 * math.acos(min(1.0, w)))))
        if r.get('parent'):
            _add(found, r['key'], 'xform_parent', 'родитель ' + str(r['parent']))
    return found, [], {}


# --- qa.zero_area -------------------------------------------------------------------------------------
def _area(a, b, c):
    u = [b[i] - a[i] for i in range(3)]
    v = [c[i] - a[i] for i in range(3)]
    x = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    return 0.5 * math.sqrt(sum(t * t for t in x))


def zero_area(rows):
    """Zero-area faces, zero-length edges, isolated vertices (ids are 1-based snapshot ids).

    adapted from GeoAGR 13.64 (author Artem), GeoAGR.ms:36036 Areas Poly ro_count_area (the finder is kept);
    changes: metres (VertexCleaner's weight is not metres), no removal (Remove Overlayed has probable
    errors). Non-finite coordinates -> zero_unmeasurable, never pass.
    """
    rows = Rows(rows)
    found = {}
    for r in rows:
        if _need(r, 'superclass') != 'geometry':
            continue
        verts, tris = _mesh(r)
        if not all(len(v) == 3 and _finite(*v) for v in verts):
            _add(found, r['key'], 'zero_unmeasurable', 'координаты не конечны')
            continue
        broken = [i + 1 for i, t in enumerate(tris) if len(t) != 3 or any(not 0 <= k < len(verts) for k in t)]
        if broken:
            _add(found, r['key'], 'zero_unmeasurable', 'грани ссылаются вне вершин: {}'.format(broken[:5]))
            continue
        used, bad_f, bad_e = set(), [], 0
        seen_e = set()
        for i, t in enumerate(tris):
            used.update(t)
            a, b, c = (verts[k] for k in t)
            if _area(a, b, c) < ZERO_AREA_M2:
                bad_f.append(i + 1)
            for p, q in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                e = (min(p, q), max(p, q))
                if e in seen_e:
                    continue
                seen_e.add(e)
                if math.dist(verts[p], verts[q]) < ZERO_EDGE_M:
                    bad_e += 1
        if bad_f:
            _add(found, r['key'], 'zero_area_face', '{} граней'.format(len(bad_f)), bad_f)
        if bad_e:
            _add(found, r['key'], 'zero_length_edge', '{} рёбер'.format(bad_e))
        iso = [k + 1 for k in range(len(verts)) if k not in used]
        if iso:
            _add(found, r['key'], 'isolated_vertex', '{} вершин'.format(len(iso)))
    return found, [], {}


# --- qa.preflight -------------------------------------------------------------------------------------
def preflight(rows, audit):
    """All object checks of 0.7 in one pass, one table; nothing changes the scene.

    Replaces GeoAGR Prepare LowPoly GeoAGR.ms:65278 / Prepare HighPoly :65653 (destructive: D6 ResetXForm +
    collapse, D1, D2, D7, D8) with the read-only checks above. Each finding detail starts with its check.
    """
    found, dropped, status = {}, [], {}
    for tool in PREFLIGHT:
        f, d, _ = run(tool, rows, audit)
        status[tool] = 'fail' if any(f.values()) else 'pass'
        for key, items in f.items():
            for code, detail, ids in items:
                _add(found, key, code, '{}: {}'.format(PLAN_ROW[tool], detail), ids)
        dropped += [{'name': x['name'], 'reason': tool + ': ' + x['reason']} for x in d]
    return found, dropped, {'checks': status}


def run(tool, rows, audit=None):
    fn = {'census': census, 'perimeter_drop': perimeter_drop, 'material_type': material_type,
          'sets_count': sets_count, 'fbx_split': fbx_split, 'glass': glass, 'scene_hygiene': scene_hygiene,
          'xform': xform, 'zero_area': zero_area}
    if tool == 'ucx_audit':
        return ucx_audit(rows, audit)
    if tool == 'preflight':
        return preflight(rows, audit)
    if tool not in fn:
        raise KeyError('unknown 0.7 check: ' + repr(tool))
    return fn[tool](rows)


# --- report contract (0.5.0 shape: schema/tool/status/objects/plan) ----------------------------------
def report(tool, rows, found, dropped, summary):
    """Report of an object check. Every input row ends in objects; status derived from findings."""
    objects = []
    for r in rows:
        fs = [{'code': c, 'ids': sorted(set(int(i) for i in ids)), 'detail': d} for c, d, ids in found.get(r['key'], [])]
        objects.append({'handle': int(r['key']), 'name': str(r['name']), 'findings': fs})
    out = {'schema': 1, 'tool': tool, 'status': 'fail' if any(o['findings'] for o in objects) else 'pass',
           'objects': objects, 'plan': {'dropped': list(dropped), 'summary': summary}}
    return validate_report(json.loads(json.dumps(out, allow_nan=False)))


def scene_report(tool, path, findings):
    out = {'schema': 1, 'tool': tool, 'status': 'pass' if all(f['status'] == 'pass' for f in findings) else 'fail',
           'objects': [], 'plan': {'path': str(path), 'findings': findings}}
    return validate_report(json.loads(json.dumps(out, allow_nan=False)))


def validate_report(r):
    """Strict 0.7 report: unknown tool, unmapped code, partial object or claimed pass with findings fail."""
    if not isinstance(r, dict) or set(r) != {'schema', 'tool', 'status', 'objects', 'plan'}:
        raise ValueError('incomplete report')
    if r['schema'] != 1 or r['tool'] not in CODES or r['status'] not in ('pass', 'fail'):
        raise ValueError('unsupported schema/tool')
    plan = r['plan']
    if r['tool'] in SCENE_TOOLS:
        if r['objects'] != [] or not isinstance(plan, dict) or set(plan) != {'path', 'findings'}:
            raise ValueError('incomplete plan')
        if not plan['findings']:
            raise ValueError('empty findings')
        for f in plan['findings']:
            if not isinstance(f, dict) or set(f) != {'name', 'status', 'observed', 'expected'} \
                    or f['status'] not in ('pass', 'fail'):
                raise ValueError('incomplete finding')
        expected = 'pass' if all(f['status'] == 'pass' for f in plan['findings']) else 'fail'
    else:
        if not isinstance(plan, dict) or set(plan) != {'dropped', 'summary'} or not isinstance(plan['dropped'], list):
            raise ValueError('incomplete plan')
        for d in plan['dropped']:
            if not isinstance(d, dict) or set(d) != {'name', 'reason'} or not d['reason']:
                raise ValueError('drop without a reason')
        if not isinstance(r['objects'], list) or not r['objects']:
            raise ValueError('empty objects')
        seen = set()
        for o in r['objects']:
            if not isinstance(o, dict) or set(o) != {'handle', 'name', 'findings'}:
                raise ValueError('incomplete object')
            if type(o['handle']) is not int or o['handle'] <= 0 or o['handle'] in seen:
                raise ValueError('invalid/duplicate handle')
            seen.add(o['handle'])
            for f in o['findings']:
                if not isinstance(f, dict) or set(f) != {'code', 'ids', 'detail'} or f['code'] not in CODES[r['tool']]:
                    raise ValueError('unmapped finding: ' + repr(f.get('code') if isinstance(f, dict) else f))
        expected = 'fail' if any(o['findings'] for o in r['objects']) else 'pass'
    if r['status'] != expected:
        raise ValueError('inconsistent status')
    return r
