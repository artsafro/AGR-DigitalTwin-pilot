"""Derive observe-only keys from pinned Revit FBX triangle readback, not builder rings.

new-case: tools/qa/form_check/source.py - registered source witnesses for form comparison
"""

import math

import numpy as np

from tools.methods.body.contours import section
from tools.qa.form_check import detector as D


class SourceReadback:
    def __init__(self, path):
        with np.load(path, allow_pickle=False) as src:
            self.tri, self.obj, self.names = (src[name] for name in ("tri", "obj", "names"))
        if (self.tri.ndim != 3 or self.tri.shape[1:] != (3, 3) or
                self.obj.shape != (len(self.tri),) or not np.isfinite(self.tri).all() or
                self.obj.min() < 0 or self.obj.max() >= len(self.names)):
            raise ValueError("invalid Revit FBX triangle readback")
        self.zmin = self.tri[:, :, 2].min(axis=1)
        self.zmax = self.tri[:, :, 2].max(axis=1)

    def cut(self, z, ids=None):
        sel = (self.zmin < z) & (self.zmax > z)
        if ids is not None:
            sel &= np.isin(self.obj, ids)
        v = self.tri[sel].reshape(-1, 3)
        return [tuple(s.coords) for s in section(v, np.arange(len(v)).reshape(-1, 3), z)]

    def point(self, z, object_index, xy):
        """The selector identifies a source object and endpoint; it supplies no output coordinates."""
        points = {p for seg in self.cut(z, [object_index]) for p in seg}
        if not points:
            raise ValueError(f"no cut on source object {object_index} at {z} m")
        best = min(points, key=lambda p: (math.dist(p, xy), p))
        if math.dist(best, xy) > .005:
            raise ValueError(f"no endpoint witness on source object {object_index} at {z} m near {xy}")
        return list(best)

    def named_triangles(self, name):
        ids = np.flatnonzero(self.names == name)
        if len(ids) != 1 or not (self.obj == ids[0]).any():
            raise ValueError(f"source object is missing or ambiguous: {name}")
        return self.tri[self.obj == ids[0]]


def build_key(src, spec):
    """Read a bounded, object-indexed source envelope and project source windows onto their source hosts."""
    ring = [src.point(spec["reference_z"], row[0], row[1:]) for row in spec["vertices"]]
    lines = list(zip(ring, ring[1:]))
    openings = []
    for o in spec["openings"]:
        tri = src.named_triangles(o["source_object"])
        lo, hi = float(tri[:, :, 2].min()), float(tri[:, :, 2].max())
        a, u, _ = D.frame(ring, *o["contour_segment"])
        stations = [D.local(p, a, u)[0] for p in tri.reshape(-1, 3)]
        openings.append({**o, "edge_s_m": [min(stations), max(stations)],
                         "sill_head_z_m": [lo + spec["label_shift_m"], hi + spec["label_shift_m"]]})
    key = {"schema": "form-check-source-key/1", "units": "m", "basis": spec["basis"],
           "source_vertices": [{"object_index": row[0], "object_name": str(src.names[row[0]]), "xy": xy}
                               for row, xy in zip(spec["vertices"], ring)],
           "box_xy_m": spec["box"], "profile": spec["profile"], "openings": openings,
           "contour_vertices_in_box": [{"ring_index": i, "xy": xy} for i, xy in enumerate(ring)]}
    # Reference acquisition is one spandrel trace, compared at repeated typical-storey
    # cuts. It is not a faithful opening-band section or a measured reveal-depth key.
    return key, {z: lines for z in spec["profile"]["contour_z"]}


def corners_from_readback(src, spec):
    """Recover flank lines from source wall sections using approximate stations only for correspondence."""
    anchors = spec["stations"]
    result = {}
    for label, z in spec["levels"].items():
        ids = np.flatnonzero([spec["wall_name_contains"] in name for name in src.names])
        cuts = src.cut(z, ids)
        supports = []
        for a, b in zip(anchors, anchors[1:]):
            mid = tuple((x + y) / 2 for x, y in zip(a, b))
            ray = D._sub(b, a)
            ranked = []
            for p, q in cuts:
                if math.dist(p, q) < .015:
                    continue
                angle = D._angle(ray, D._sub(q, p))
                if min(angle, 180 - angle) > 6:
                    continue
                # Rank by registered station, not by the candidate trace.
                dist = D.seg_d(mid, p, q)
                if dist <= .12:
                    ranked.append((dist, -math.dist(p, q), p, q))
            supports.append(min(ranked)[2:] if ranked else None)
        rows = []
        for i, (left, right) in enumerate(zip(supports, supports[1:]), 1):
            row = {"id": spec["corner_ids"][i - 1], "station_xy": anchors[i], "source_z_m": z}
            if left is None or right is None:
                rows.append({**row, **D.nm("no matching source flank at the registered station")})
                continue
            p, q = left
            r, s = right
            u, v = D._sub(q, p), D._sub(s, r)
            den = D._cross(u, v)
            if abs(den) < 1e-8:
                rows.append({**row, **D.nm("source flanks are parallel")})
                continue
            t = D._cross(D._sub(r, p), v) / den
            apex = (p[0] + u[0] * t, p[1] + u[1] * t)
            if math.dist(apex, anchors[i]) > .15:
                rows.append({**row, **D.nm("source flank intersection outside the registered corner")})
                continue
            legs = [max(edge, key=lambda x: D._dot(D._sub(x, apex), D._sub(anchors[j], anchors[i])))
                    for edge, j in ((left, i - 1), (right, i + 1))]
            # Extend the measured line directions up to the corresponding source
            # station lengths; the direction and intersection are never taken from the station hints.
            triple = []
            for p, j in zip(legs, (i - 1, i + 1)):
                d = math.dist(p, apex)
                scale = math.dist(anchors[j], anchors[i]) / d if d else 0
                triple.append(tuple(o + (x - o) * scale for o, x in zip(apex, p)))
            rows.append({**row, "source": [triple[0], apex, triple[1]], "source_supports_xy_m": [left, right]})
        result[label] = rows
    return result
