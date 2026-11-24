"""Form check v1 - Artem's rules the detector must know, else it flags correct models (OBSERVE only).

A rule never turns a measurement into `pass`: it relabels a `fail` as `expected` and keeps the measured basis plus
the citation, so the report still shows the number.

* NARROW - an opening narrower than the Revit window (key edges) is expected: windows are cut/trimmed into the
  accepted opening (Artem 2026-11-20, 63B stage 2). Wider or shifted openings still fail.
* ACCEPTED - deviations Artem accepted on a named model, given per pair with their citation (e.g. the D341
  step-corner clip of 63B v007, #57: the narrowing is real, it originates in floor_A.json, and v007 is accepted).
  Matched by item name, location (`near_xy` within `radius_m`) and size (`dev_m` <= `max_dev_m`).

new-case: tools/qa/form_check/rules.py - form check v1 Artem rules
"""
from __future__ import annotations

import math

EDGE_TOL_M = 0.03  # frozen opening edge tolerance (t_563a40f7)
NARROW_BASIS = ("opening narrower than the Revit window: the window is cut/trimmed into the accepted opening "
                "(Artem 2026-11-20, 63B stage 2; jobs/POLY63-B/stage2/hooks/stage2_63b.py 'fitted'; no D-row yet)")


def narrower_than_key(item):
    """Every observed edge lies inside the key (Revit window) edges, within the edge tolerance; at least one edge is
    really inside. A wider or shifted opening is not covered."""
    key = item.get("key")
    obs = item.get("observed") or []
    if not key or not obs:
        return False
    e0, e1 = key
    inside = all(o[0] >= e0 - EDGE_TOL_M and o[1] <= e1 + EDGE_TOL_M for o in obs)
    return inside and any(o[0] > e0 + EDGE_TOL_M or o[1] < e1 - EDGE_TOL_M for o in obs)


def _accepted(name, item, accepted):
    for a in accepted:
        if a.get("item") is not None and a["item"] != name:
            continue
        if a.get("item_prefix") is not None and not name.startswith(a["item_prefix"]):
            continue
        if a.get("item") is None and a.get("item_prefix") is None:
            continue
        if "near_xy" in a:
            at = item.get("at")
            if at is None or math.dist(at, a["near_xy"]) > a.get("radius_m", 0.2):
                continue
        if "max_dev_m" in a and (item.get("dev_m") is None or item["dev_m"] > a["max_dev_m"]):
            continue
        return a
    return None


def apply(items, accepted):
    """Return a new items dict with Artem's rules applied to `fail` items."""
    out = {}
    for name, item in items.items():
        new = dict(item)
        if item.get("status") == "fail":
            a = _accepted(name, item, accepted or [])
            if a is None and name.endswith(":edges") and narrower_than_key(item):
                new.update(status="expected", rule="NARROW",
                           basis=f"{item.get('basis', '')} | expected: {NARROW_BASIS}")
            elif a:
                new.update(status="expected", rule=a.get("rule", "accepted"),
                           basis=f"{item.get('basis', '')} | expected: {a['basis']}")
        out[name] = new
    return out
