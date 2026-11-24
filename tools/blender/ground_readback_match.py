"""Pure-Python centre matching for the Ground FBX readback (tools/blender/ground_json_to_fbx.py, issue #1837).

Pattern: n/a | new-case: degree-aware source-face centre keys and transparent match coverage for Ground readback.

No bpy here, so the matching is testable without Blender. A face centre key is the mean of its vertex coordinates
over the face's own degree (triangle /3, quad /4, n-gon /n), rounded to `ndigits` in source (world/MSK-77) metres.
The readback passes one (key, slot, normal_z) per imported polygon, already transformed back to source coordinates
with the placement offset. Coverage is reported explicitly: a zero mismatch count is only `pass` when every source
face and every imported polygon matched exactly once; otherwise the status is `incomplete` (or `fail` on a mismatch).
"""
import math

NDIGITS = 3


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
