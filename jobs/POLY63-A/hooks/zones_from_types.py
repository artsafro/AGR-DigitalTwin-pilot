"""Hook `before` stage `body` (#1619 polygon, site 63 tower A): finish zones from the Revit wall TYPES (D344/D341).

Pattern: n/a | new-case: finish-zone IDs from the wall-type names of a Revit FBX crop (no materials, no etalon).

uv run python zones_from_types.py FLOOR.json CROP.npz ZONEMAP.json OUT.json [--min-run 0.6] [--snap 0.15]
    [--max-dist 0.6]

Why: the Revit FBX of site 63 has no Material nodes and site 63 has no etalon texture; Artem's option (b) is to read
the wall materials in the .rvt read-only. When Revit is not available the facade wall TYPE names in the FBX
(`Базовая стена <type>_<hash>`) are the Revit source that is left: one finish = one wall type (the type name
carries the cladding). ZONEMAP = {"zones": {"<type substring>": ["WALL_<ID>", [r, g, b]]}, "skip": [substrings]}.
The contour is sampled every 0.1 m; each sample takes the type of the nearest facade-wall cut segment within
--max-dist (at the contour section height). Runs shorter than --min-run merge into the neighbour (a panel
joint, not a zone); a border within --snap of a jamb/corner takes that vertical, otherwise it adds a full-height cut
(BM-11 / D344). A facade wall type that is not in the map is an error naming it. Refuses OUT equal to an input.
"""
import argparse
import json
import os
import re
import sys

import numpy as np
from shapely.geometry import LineString, Point

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "garibaldi22",
                                "body-training-1619", "hooks"))
from floor_from_dump import section  # noqa: E402


def type_of(name):
    """Revit wall type of an FBX object name: the name without the `_<7 hex>` instance suffix."""
    return re.sub(r"_[0-9a-f]{7}$", "", name)


def runs_of(cls, step, min_run):
    """Sample classes -> [[i0, i1, cls]] with runs shorter than min_run merged into the shorter-loss neighbour."""
    runs = []
    for i, c in enumerate(cls):
        if runs and runs[-1][2] == c:
            runs[-1][1] = i + 1
        else:
            runs.append([i, i + 1, c])
    while len(runs) > 1:
        k = min(range(len(runs)), key=lambda j: runs[j][1] - runs[j][0])
        if (runs[k][1] - runs[k][0]) * step >= min_run:
            break
        if k > 0:
            runs[k - 1][1] = runs[k][1]
        else:
            runs[k + 1][0] = runs[k][0]
        del runs[k]
        merged = []
        for r in runs:
            if merged and merged[-1][2] == r[2]:
                merged[-1][1] = r[1]
            else:
                merged.append(r)
        runs = merged
    # the ring is closed: a first and last run of the same class are one zone, split only at s=0
    return runs


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("floor")
    ap.add_argument("crop")
    ap.add_argument("zonemap")
    ap.add_argument("out")
    ap.add_argument("--min-run", type=float, default=0.6)
    ap.add_argument("--snap", type=float, default=0.15)
    ap.add_argument("--max-dist", type=float, default=0.6)
    a = ap.parse_args(argv)
    if os.path.realpath(a.out) in {os.path.realpath(p) for p in (a.floor, a.crop, a.zonemap)} or not a.out.endswith(".json"):
        sys.exit("refused: output must be a new .json, not an input")
    spec = json.load(open(a.floor, encoding="utf-8"))
    zm = json.load(open(a.zonemap, encoding="utf-8"))
    d = np.load(a.crop)
    names = [str(n) for n in d["names"]]
    tri, obj = d["tri"], d["obj"]
    zc = float(spec["contour_section_z"])
    m = (tri[:, :, 2].min(1) <= zc) & (tri[:, :, 2].max(1) >= zc)
    tri, obj = tri[m], obj[m]
    segs, seg_type = [], []
    unknown = {}
    for o in np.unique(obj):
        n = names[o]
        if not n.startswith("Базовая стена") or any(s in n for s in zm.get("skip", [])):
            continue
        key = next((k for k in zm["zones"] if k in n), None)
        ss = section(tri[obj == o], zc)
        if key is None:
            unknown[type_of(n)] = unknown.get(type_of(n), 0) + len(ss)
            continue
        segs += ss
        seg_type += [zm["zones"][key][0]] * len(ss)
    ring = spec["rings"][0]
    xy = np.array(ring["xy"], float)
    ext = LineString(list(map(tuple, xy)) + [tuple(xy[0])])
    perim = ext.length
    step = 0.1
    ss_ = np.arange(step / 2, perim, step)
    pts = np.array([ext.interpolate(s).coords[0] for s in ss_])
    A = np.array([s[0] for s in segs])[None]
    B = np.array([s[1] for s in segs])[None]
    AB = B - A
    tt = np.clip((((pts[:, None, :] - A) * AB).sum(-1)) / np.maximum((AB ** 2).sum(-1), 1e-12), 0, 1)
    dd = np.sqrt(((pts[:, None, :] - (A + tt[..., None] * AB)) ** 2).sum(-1))
    near = dd.argmin(1)
    ok = dd.min(1) <= a.max_dist
    if unknown:
        sys.exit("refused: wall types on the cut are neither mapped nor skipped: %s" % sorted(unknown))
    cls = np.array([seg_type[j] if o_ else "" for j, o_ in zip(near, ok)], dtype=object)
    known = np.nonzero(cls != "")[0]
    if not len(known):
        sys.exit("refused: no contour sample within %.2f m of a mapped facade wall" % a.max_dist)
    unknown_m = float((cls == "").sum() * step)
    for i in np.nonzero(cls == "")[0]:
        cls[i] = cls[known[np.abs(known - i).argmin()]]
    raw_m = {}
    for c in cls:
        raw_m[c] = raw_m.get(c, 0) + step
    runs = runs_of(list(cls), step, a.min_run)
    cuts = list(ring.get("cuts", []))
    corner_s = [ext.project(Point(c)) for c in xy]
    bounds = [0.0] + [r[0] * step for r in runs[1:]] + [perim]
    zones = [[round(bounds[k], 4), round(bounds[k + 1], 4), r[2]] for k, r in enumerate(runs)]
    snapped = new_cuts = 0
    wins = [(w[1], w[2]) for w in spec.get("windows", []) if w[0] == 0]
    for k in range(1, len(bounds) - 1):
        b = bounds[k]
        cand = [c for c in cuts + corner_s if abs(c - b) <= a.snap]
        if cand:
            nb = min(cand, key=lambda c: abs(c - b))
            snapped += 1
        else:
            nb = round(b, 4)
            inside = [w for w in wins if w[0] + 1e-3 < nb < w[1] - 1e-3]
            if inside:  # a zone border never splits an opening: take the nearer jamb
                w = inside[0]
                nb = w[0] if nb - w[0] < w[1] - nb else w[1]
                snapped += 1
            else:
                cuts.append(nb)
                new_cuts += 1
        zones[k - 1][1] = zones[k][0] = round(nb, 4)
    ring["cuts"] = sorted(set(round(c, 4) for c in cuts))
    ring["zones"] = zones
    mats = {k: v for k, v in spec["materials"].items() if k != "WALL_A"}
    for key, (zname, rgb) in zm["zones"].items():
        if any(z[2] == zname for z in zones):
            mats[zname] = rgb
    spec["materials"] = mats
    spec["zones_report"] = {
        "source": "Revit wall TYPE names in the FBX crop (FBX has no materials; Revit 2025 not available for the "
                  "read-only .rvt material list)",
        "section_z": zc, "segments": len(segs), "unmapped_types_on_cut": unknown,
        "unknown_m_filled": round(unknown_m, 1), "raw_m": {k: round(v, 1) for k, v in raw_m.items()},
        "zones": len(zones), "zone_m": {z: round(sum(q[1] - q[0] for q in zones if q[2] == z), 1) for z in mats
                                        if z.startswith("WALL_")},
        "borders_snapped": snapped, "borders_new_cut": new_cuts,
    }
    with open(a.out, "x", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=1)
    print(json.dumps(spec["zones_report"], ensure_ascii=False))


if __name__ == "__main__":
    main()
