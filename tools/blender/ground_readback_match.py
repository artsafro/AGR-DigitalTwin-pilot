"""Pure-Python centre matching for the Ground FBX readback (tools/blender/ground_json_to_fbx.py, issue #1837).

Pattern: n/a | new-case: degree-aware source-face centre keys and transparent match coverage for Ground readback.

No bpy here, so the matching is testable without Blender. A face centre key is the mean of its vertex coordinates
over the face's own degree (triangle /3, quad /4, n-gon /n), rounded to `ndigits` in source (world/MSK-77) metres.
The readback passes one (key, slot, normal_z) per imported polygon, already transformed back to source coordinates
with the placement offset. Coverage is reported explicitly: a zero mismatch count is only `pass` when every source
face and every imported polygon matched exactly once; otherwise the status is `incomplete` (or `fail` on a mismatch).

#1921: also the readback's Ground selection, placement record and opt-in strict UDIM result (all without bpy).
select_ground picks the single Ground surface by the GND-11 / V012 naming owner (src/twinqa/naming.py: is_ucx,
address_from_fbx; mirrored here because Blender's Python cannot import twinqa (it needs yaml); parity is pinned by
tests/test_ground_readback_select_1921.py), independent of import order, and lists every other object with a
reason. load_placement tells a missing or invalid <fbx>.placement.json from a recorded (possibly zero) offset.
strict_udim_result maps only the selection status and udim_assignment.status to measured pass / measured failure /
insufficient evidence; informational fields never become thresholds.
"""
import json
import math
import os
import re

NDIGITS = 3
STRICT_EXIT = {'measured_pass': 0, 'measured_fail': 1, 'insufficient_evidence': 2}


def is_ucx(name):
    """Collision by prefix, case-insensitive (same rule as twinqa.naming.is_ucx)."""
    return name.upper().startswith('UCX_')


def is_generic_ground(name):
    """twinqa.naming.address_from_fbx('vpm', 'ground', name) is not None."""
    return re.fullmatch(r'SM_(?P<a>[A-Za-z0-9_]+?)_Ground', name) is not None


def select_ground(objects, address=None):
    """objects: [(name, type)] in import order; address: export-record address (<Address>_Ground) or None.

    With a recorded address only the exact object SM_<address> is the Ground; without one, any SM_<Address>_Ground.
    Returns status selected / missing / ambiguous; never the first mesh. Every other object is in `excluded`.
    """
    expected = f'SM_{address}' if address else 'SM_<Address>_Ground'
    candidates, excluded = [], []
    for name, kind in objects:
        if kind != 'MESH':
            excluded.append({'name': name, 'reason': f'not a mesh ({kind})'})
        elif is_ucx(name):
            excluded.append({'name': name, 'reason': 'UCX collision mesh'})
        elif name.startswith('SM_') and name.endswith('_GroundGlass'):
            excluded.append({'name': name, 'reason': 'GroundGlass, not the Ground surface'})
        elif (name == expected) if address else is_generic_ground(name):
            candidates.append(name)
        else:
            excluded.append({'name': name, 'reason': f'name is not {expected}'})
    candidates.sort()
    status = 'selected' if len(candidates) == 1 else ('missing' if not candidates else 'ambiguous')
    unexpected = sorted(e['name'] for e in excluded if e['reason'].startswith('name is not'))
    return {'status': status, 'selected': candidates[0] if status == 'selected' else None,
            'expected_name': expected, 'candidates': candidates, 'excluded': excluded,
            'unexpected_surface_meshes': unexpected}


def load_placement(path):
    """The recorded MSK-77 offset of the FBX origin; a missing or invalid record is never replaced by zero."""
    out = {'status': 'invalid', 'path': path, 'offset': None, 'reason': None}
    if not os.path.exists(path):
        return {**out, 'status': 'missing', 'reason': 'no placement record beside the FBX'}
    try:
        with open(path, encoding='utf-8') as stream:
            off = json.load(stream)['origin_msk77_xyz']
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {**out, 'reason': f'unreadable placement record: {type(exc).__name__}: {exc}'}
    if (not isinstance(off, list) or len(off) != 3
            or any(type(c) not in (int, float) or not math.isfinite(c) for c in off)):
        return {**out, 'reason': f'origin_msk77_xyz must be three finite numbers, got {off!r}'}
    return {**out, 'status': 'recorded', 'offset': [float(c) for c in off]}


def strict_udim_result(report):
    """Opt-in strict verdict of the VPM UDIM readback: measured_pass (0), measured_fail (1),
    insufficient_evidence (2). Only the Ground selection and udim_assignment.status are read."""
    selection = (report.get('ground_selection') or {}).get('status')
    assignment = (report.get('uv_tiles') or {}).get('udim_assignment')
    status = assignment.get('status') if isinstance(assignment, dict) else None
    if selection != 'selected':
        result, reason = 'insufficient_evidence', f'Ground selection is {selection!r}'
    elif not isinstance(assignment, dict):
        result, reason = 'insufficient_evidence', 'no VPM UDIM assignment in the report'
    elif status == 'pass':
        result, reason = 'measured_pass', 'udim_assignment pass'
    elif status == 'fail':
        result, reason = 'measured_fail', f"udim_assignment fail: {assignment.get('reason') or 'differences'}"
    elif status == 'not_measured':
        result, reason = 'insufficient_evidence', f"udim_assignment not_measured: {assignment.get('reason')}"
    else:
        result, reason = 'insufficient_evidence', f'unknown udim_assignment status {status!r}'
    return {'result': result, 'exit': STRICT_EXIT[result], 'reason': reason}


def face_centre_key(verts, face, ndigits=NDIGITS):
    """Rounded mean of the face's vertices, divided by the actual face degree."""
    if len(face) < 3:
        raise ValueError(f"face {list(face)!r} has {len(face)} vertices; a polygon needs at least 3")
    return tuple(round(sum(verts[i][k] for i in face) / len(face), ndigits) for k in range(3))


def _finite(key):
    return all(math.isfinite(c) for c in key)


def match_by_centre(src, imported, ndigits=NDIGITS):
    """Match imported polygons to source faces by centre key; return counts, coverage and check statuses.

    src: the Ground mesh JSON dict (verts, faces, mat, slots, level).
    imported: list of (key, slot, normal_z) per imported polygon, key in source coordinates.
    """
    faces, mats, levels, slots = src["faces"], src["mat"], src["level"], src["slots"]
    if not (len(faces) == len(mats) == len(levels)):
        raise ValueError(f"faces/mat/level lengths differ: {len(faces)}/{len(mats)}/{len(levels)}")
    want = {}
    nonfinite = []
    for fi, (f, mi) in enumerate(zip(faces, mats)):
        if not 0 <= mi < len(slots):
            raise ValueError(f"face {fi}: material index {mi} has no slot (slots={slots!r})")
        key = face_centre_key(src["verts"], f, ndigits)
        if not _finite(key):
            nonfinite.append(fi)
            continue
        want.setdefault(key, []).append(fi)
    ambiguous = sorted(fi for ids in want.values() if len(ids) > 1 for fi in ids)
    matched = {}
    unmatched_imported, ambiguous_imported, duplicate_imported = [], [], []
    mism = down = surface_checked = 0
    for pi, (key, slot, nz) in enumerate(imported):
        ids = want.get(tuple(key)) if _finite(key) else None
        if not ids:
            unmatched_imported.append(pi)
            continue
        if len(ids) > 1:
            ambiguous_imported.append(pi)
            continue
        fi = ids[0]
        if fi in matched:
            duplicate_imported.append(pi)
            continue
        matched[fi] = pi
        if slots[mats[fi]] != slot:
            mism += 1
        if levels[fi] >= 0:
            surface_checked += 1
            if not nz > 0:  # NaN normal counts as down
                down += 1
    unmatched_source = [fi for fi in range(len(faces)) if fi not in matched]
    complete = (not unmatched_source and not unmatched_imported and not ambiguous_imported
                and not duplicate_imported and len(imported) == len(faces))

    def status(bad):
        return "fail" if bad else ("pass" if complete else "incomplete")

    return {
        "centre_match": {"ndigits": ndigits, "expected": len(faces), "imported": len(imported),
                         "matched": len(matched), "unmatched_source_faces": unmatched_source,
                         "unmatched_imported_faces": unmatched_imported,
                         "ambiguous_source_faces": ambiguous, "ambiguous_imported_faces": ambiguous_imported,
                         "duplicate_imported_faces": duplicate_imported, "nonfinite_source_faces": nonfinite,
                         "complete": complete},
        "faces_matched_by_centre": len(matched),
        "material_mismatch": mism,
        "material_by_centre": status(mism),
        "surface_faces_checked_by_centre": surface_checked,
        "surface_faces_normal_down": down,
        "surface_normals_by_centre": status(down),
    }
