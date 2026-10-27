"""Opening schedule of a building-body contour input (#727 review 1): validation shared by the Blender opening cut.

Pattern: new-case: fail-closed opening-schedule reader for the building-body methods class (stdlib only, so it
loads inside Blender's Python too).

contours.json may carry `"openings": [{"id": str, "min": [x, y, z], "max": [x, y, z]}, ...]`: one axis-aligned
cutter box per opening (an opening schedule from drawings gives position, width, sill and head heights; the
wall depth is crossed by the box). Fail closed: an unknown key, a missing/duplicate id, a non-finite coordinate,
min >= max on any axis or a non-list value is a ValueError naming the opening; nothing is dropped silently.
The Blender side then cuts every box and refuses an opening that removes no volume (misses the body).
"""
from __future__ import annotations

import math

KEYS = {"id", "min", "max"}


def schedule(data: dict) -> list[dict]:
    """Validated opening list (possibly empty) of a contours.json dict."""
    raw = data.get("openings", [])
    if not isinstance(raw, list):
        raise ValueError(f"openings must be a list, got {type(raw).__name__}")
    out, seen = [], set()
    for i, o in enumerate(raw):
        if not isinstance(o, dict):
            raise ValueError(f"opening #{i} is not an object")
        oid = o.get("id")
        if not isinstance(oid, str) or not oid:
            raise ValueError(f"opening #{i} has no id")
        unknown = sorted(set(o) - KEYS)
        if unknown:
            raise ValueError(f"opening {oid!r}: unknown key(s) {unknown}")
        if oid in seen:
            raise ValueError(f"opening {oid!r}: duplicate id")
        seen.add(oid)
        box = []
        for k in ("min", "max"):
            p = o.get(k)
            if not isinstance(p, list) or len(p) != 3:
                raise ValueError(f"opening {oid!r}: {k} must be [x, y, z]")
            try:
                p = [float(x) for x in p]
            except (TypeError, ValueError):
                raise ValueError(f"opening {oid!r}: {k} is not numeric") from None
            if not all(math.isfinite(x) for x in p):
                raise ValueError(f"opening {oid!r}: non-finite {k}")
            box.append(p)
        if not all(a < b for a, b in zip(*box)):
            raise ValueError(f"opening {oid!r}: min must be < max on every axis")
        out.append({"id": oid, "min": box[0], "max": box[1]})
    return out
