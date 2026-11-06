"""AGR Tools 1.0 (#1024) placement by the passport logic, stdlib only. Owned by branch T (improve/issue-1024-deliver-small).

Pure logic for `export_place_by_passport` (export.place_by_passport, plan mode `undo`); no pymxs, no host objects.
Idea ported from the team script new-telegram `Import_HP_from_coordinates.ms` (SHA256
ecb001a9b2a5447ee7f7cc696a3af5412aad01348b249f088c0cf590f9778675, read, not copied, #853): import an FBX and put its
origin at [x, y, h_relief] taken from the GeoJSON passport lying next to it.

Defects of the source (lab T06, measured Max 2026) and what is done instead:
  - the GeoJSON text was run line by line through MAXScript `execute` (code from a data file)
        -> `read_passport` is strict stdlib json; every value is DATA, a string never reaches an interpreter;
  - a `Dummy` stayed in the scene after an error -> no helper object is created; on any error the new nodes are
        removed (the glue deletes exactly the nodes it imported), 0 new nodes remain;
  - no schema check -> the passport is checked against the qa.geojson 0.5 shape (FeatureCollection, ONE ObjectFeature,
        Point [x, y], properties.h_relief a number or a numeric string with a comma).
Max positions are single-precision floats: a coordinate like 2 345 678.123 m cannot be stored to 1 mm. `precision_m`
tells the real error; above `PRECISION_TOL_M` the preview is `ambiguous` and apply needs the explicit option
`accept_precision_loss` (nothing is silently rounded).
"""
import json
import math
import os
import re
import struct

TOOL = 'export.place_by_passport'
PRECISION_TOL_M = 0.001
READBACK_TOL_M = 0.001
NUMBER_RE = re.compile(r'^[+-]?\d+(?:[.,]\d+)?$')


class PassportError(ValueError):
    """A user-facing passport/FBX problem (Russian message). `code` is machine-readable."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def _pairs(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise ValueError('повторяющийся ключ ' + repr(k))
        out[k] = v
    return out


def _reject(token):
    raise ValueError('значение ' + token + ' не число')


def _num(value, label):
    if isinstance(value, bool):
        raise PassportError('schema', 'Паспорт: {} не число.'.format(label))
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise PassportError('schema', 'Паспорт: {} не конечное число.'.format(label))
        return float(value)
    if isinstance(value, str) and NUMBER_RE.match(value.strip()):
        return float(value.strip().replace(',', '.'))
    raise PassportError('schema', 'Паспорт: {} = {!r} — не число (ожидается число или «152,3»).'.format(label, value if len(str(value)) < 60 else str(value)[:60] + '…'))


def read_passport(data):
    """GeoJSON passport bytes -> {'x', 'y', 'h'} in metres. Any problem is a PassportError, nothing is executed."""
    if not isinstance(data, (bytes, bytearray)):
        raise PassportError('json', 'Паспорт: ожидались байты файла.')
    try:
        text = bytes(data).decode('utf-8-sig')
    except UnicodeDecodeError:
        raise PassportError('encoding', 'Паспорт не в UTF-8.') from None
    try:
        doc = json.loads(text, object_pairs_hook=_pairs, parse_constant=_reject)
    except ValueError as exc:
        raise PassportError('json', 'Паспорт — не корректный JSON: {}'.format(str(exc)[:120])) from None
    if not isinstance(doc, dict) or doc.get('type') != 'FeatureCollection':
        raise PassportError('schema', 'Паспорт: верхний уровень должен быть FeatureCollection.')
    feats = doc.get('features')
    if not isinstance(feats, list) or len(feats) != 1 or not isinstance(feats[0], dict):
        raise PassportError('schema', 'Паспорт: должен быть ровно один объект (feature).')
    feat = feats[0]
    if feat.get('type') != 'ObjectFeature':
        raise PassportError('schema', 'Паспорт: тип объекта должен быть ObjectFeature.')
    geom = feat.get('geometry')
    if not isinstance(geom, dict) or geom.get('type') != 'Point':
        raise PassportError('schema', 'Паспорт: geometry должна быть Point.')
    coords = geom.get('coordinates')
    if not isinstance(coords, list) or len(coords) != 2:
        raise PassportError('schema', 'Паспорт: coordinates должны быть [x, y].')
    props = feat.get('properties')
    if not isinstance(props, dict) or 'h_relief' not in props:
        raise PassportError('schema', 'Паспорт: в properties нет h_relief.')
    return {'x': _num(coords[0], 'x'), 'y': _num(coords[1], 'y'), 'h': _num(props['h_relief'], 'h_relief')}


def find_passport(folder, listing):
    """The one `*.geojson` next to the FBX. listing: file names in that folder. None -> 0, many -> ambiguous."""
    found = sorted(n for n in listing if n.lower().endswith('.geojson'))
    if not found:
        raise PassportError('passport_missing', 'Рядом с FBX нет паспорта *.geojson: {}'.format(folder))
    if len(found) > 1:
        raise PassportError('passport_many', 'Рядом с FBX несколько паспортов ({}): укажите один параметром passport.'.format(', '.join(found)))
    return os.path.join(folder, found[0])


FBX_MAGIC = (b'Kaydara FBX Binary', b'; FBX')


def check_fbx_header(head):
    """A file that is not an FBX is refused before the importer (and before anything is created)."""
    if not bytes(head).startswith(FBX_MAGIC):
        raise PassportError('fbx_invalid', 'Файл не похож на FBX (нет заголовка FBX).')


def place_options(options):
    o = dict(options or {})
    unknown = set(o) - {'fbx', 'passport', 'accept_precision_loss'}
    if unknown:
        raise ValueError('unknown export.place_by_passport options: ' + ', '.join(sorted(unknown)))
    fbx = o.get('fbx')
    if not isinstance(fbx, str) or not fbx.strip():
        raise PassportError('fbx_path', 'Не задан путь к FBX (параметр fbx).')
    if not fbx.lower().endswith('.fbx'):
        raise PassportError('fbx_path', 'Файл должен быть .fbx: {}'.format(fbx))
    passport = o.get('passport')
    if passport is not None and (not isinstance(passport, str) or not passport.strip()):
        raise PassportError('passport_path', 'Параметр passport должен быть путём к *.geojson.')
    return {'fbx': fbx.strip(), 'passport': passport.strip() if passport else None,
            'accept_precision_loss': bool(o.get('accept_precision_loss', False))}


def float32(v):
    return struct.unpack('f', struct.pack('f', v))[0]


def plan_target(values, m_per_unit):
    """Target in system units + the float32 error in metres per axis (what Max can actually store)."""
    if not (m_per_unit > 0 and math.isfinite(m_per_unit)):
        raise ValueError('bad unit scale')
    target = [values['x'] / m_per_unit, values['y'] / m_per_unit, values['h'] / m_per_unit]
    err = [abs(float32(t) - t) * m_per_unit for t in target]
    return {'target_units': target, 'stored_units': [float32(t) for t in target], 'precision_m': max(err)}


def readback_ok(target_units, actual_units, m_per_unit, tol_m=READBACK_TOL_M):
    """Pivot within `tol_m` of the target, judged against what float32 can hold (the error floor is reported
    separately as precision_m, so a stored-nearest value is a pass)."""
    worst = max(abs(a - float32(t)) * m_per_unit for a, t in zip(actual_units, target_units))
    return worst <= tol_m, worst


def report(edit, mode, opts, values, plan, nodes, state_hash, problems=(), readback=None):
    """Preview / apply report. nodes: [{'handle', 'name'}] imported roots (apply) — none in a preview."""
    objects = [edit.entry(n['handle'], n['name']) for n in nodes]
    ambiguous = [dict(p) for p in problems]
    done = []
    if values is not None and plan is not None:
        if plan['precision_m'] > PRECISION_TOL_M and not opts['accept_precision_loss']:
            ambiguous.append({'code': 'precision', 'message': 'Max хранит координаты одинарной точностью: ошибка {:.3f} м > 1 мм. '
                                                              'Поставить всё равно — параметр accept_precision_loss.'.format(plan['precision_m'])})
        done.append({'item': 'позиция', 'x': values['x'], 'y': values['y'], 'h': values['h']})
    findings = [{'name': a['code'], 'status': 'fail'} for a in ambiguous] or [{'name': 'passport', 'status': 'pass'}]
    extra = {'findings': findings, 'fbx': opts['fbx'], 'passport': opts['passport'], 'accept_precision_loss': opts['accept_precision_loss'],
             'values': values,
             'target_units': plan['target_units'] if plan else None, 'precision_m': plan['precision_m'] if plan else None,
             'readback_m': readback}
    return edit.report(TOOL, mode, objects=objects, done=done, ambiguous=ambiguous, state_hash=state_hash if mode == 'preview' else None,
                       extra=extra)
