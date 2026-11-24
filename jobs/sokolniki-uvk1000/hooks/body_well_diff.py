"""#1784 v007 hook (stage `body`, point `after`): proof that the [D384] roof wells changed nothing outside the wells.

Pattern: n/a | new-case: face-set diff of two volume_body.py builds (accepted v005 vs v007, both `meshes.json`).
A face is its rounded vertex positions (1 mm) + material, so the proof does not depend on vertex numbering.

Pass rules per volume:
- a volume with a well: v005 minus v007 = exactly its flat top cap; every added face lies on the top (parapet band)
  or inside the parapet (all vertices >= parapet - 1 mm from the outer ring in plan) between deck and top;
- a re-based volume (`base_by_volume`, H on the D deck): every changed vertex keeps its plan position, moves only
  from the old base to the new one, and lies inside the well of the volume it stands on;
- any other volume: no change at all.
So facade, parapet and opening faces (outer walls, reveals, window planes) are identical: `outside_diff` = 0.

    uv run python jobs/sokolniki-uvk1000/hooks/body_well_diff.py V005/meshes.json V007/meshes.json \
        jobs/sokolniki-uvk1000/body_config_v007.json VOLUME_LINES.json NEW_REPORT.json

Exit 0 pass, 1 a change outside the wells (listed), 2 bad input / output exists.
"""
import json
import math
import os
import sys

TOL = 1e-3


def _key(p):
    return tuple(round(c, 3) for c in p)


def faces(mesh):
    vv = mesh["verts"]
    return {(tuple(_key(vv[i]) for i in f["v"]), f["mat"]) for f in mesh["faces"]}


def _canon(face):
    """Rotation-invariant face key (same winding)."""
    pts, mat = face
    k = min(range(len(pts)), key=lambda i: pts[i])
    return (pts[k:] + pts[:k], mat)


def _seg_dist(p, a, b):
    ax, ay = b[0] - a[0], b[1] - a[1]
    L2 = ax * ax + ay * ay
    if L2 < 1e-12:
        return math.dist(p[:2], a[:2])
    t = max(0.0, min(1.0, ((p[0] - a[0]) * ax + (p[1] - a[1]) * ay) / L2))
    return math.hypot(p[0] - a[0] - t * ax, p[1] - a[1] - t * ay)


def _inside(p, ring):
    x, y, c = p[0], p[1], False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            c = not c
    return c


def ring_of(vl, vn):
    r = [tuple(p) for p in vl["volumes"][vn]["ring"]]
    return r[:-1] if r[0] == r[-1] else r


def ring_dist(p, ring):
    return min(_seg_dist(p, a, b) for a, b in zip(ring, ring[1:] + ring[:1]))


def check(m5, m7, cfg, vl):
    wells, rebased = cfg.get("roof_wells", {}), cfg.get("base_by_volume", {})
    rep = {"volumes": {}, "outside_diff": 0, "problems": []}
    for vn in sorted(set(m5) | set(m7)):
        f5 = {_canon(f) for f in faces(m5[vn]["body"])}
        f7 = {_canon(f) for f in faces(m7[vn]["body"])}
        gone, new = f5 - f7, f7 - f5
        ring = ring_of(vl, vn)
        top = max(z for z in vl["volumes"][vn]["levels"])
        bad = []
        if vn in wells:
            w = wells[vn]
            caps = [f for f in gone if len(f[0]) > 4 and all(abs(p[2] - top) < TOL for p in f[0])]
            bad += [("removed", f) for f in gone if f not in caps]
            if len(caps) != 1:
                bad.append(("top_caps_removed", len(caps)))
            dmin = min([w["parapet_m"]] + list(w.get("parapet_m_by_edge", {}).values()))
            for f in new:
                pts = f[0]
                on_top = all(abs(p[2] - top) < TOL for p in pts)
                in_well = all(w["deck_z"] - TOL <= p[2] <= top + TOL and _inside(p, ring)
                              and ring_dist(p, ring) >= dmin - TOL for p in pts)
                if not (on_top and all(_inside(p, ring) or ring_dist(p, ring) < TOL for p in pts)) and not in_well:
                    bad.append(("added_outside_well", f))
            rep["volumes"][vn] = {"kind": "well", "faces_v005": len(f5), "faces_v007": len(f7),
                                  "removed": len(gone), "added": len(new), "deck_z": w["deck_z"], "top_z": top,
                                  "unchanged_v005_faces": len(f5 & f7)}
        elif vn in rebased:
            z_new = float(rebased[vn])
            z_old = float(vl["volumes"][vn]["levels"][0])
            host = next((h for h in wells if _inside(ring[0], ring_of(vl, h))), None)
            if host is None:
                bad.append(("rebased_without_host_well", vn))
            else:
                hw, hring = wells[host], ring_of(vl, host)
                old = {p for f in gone for p in f[0]} - {p for f in new for p in f[0]}
                nw = {p for f in new for p in f[0]} - {p for f in gone for p in f[0]}
                moved = {(p[0], p[1]) for p in old}
                if moved != {(p[0], p[1]) for p in nw}:
                    bad.append(("rebased_plan_moved", vn))
                bad += [("rebased_vertex_not_base", p) for p in old if abs(p[2] - z_old) > TOL]
                bad += [("rebased_vertex_not_new_base", p) for p in nw if abs(p[2] - z_new) > TOL]
                bad += [("rebased_outside_host_well", p) for p in nw
                        if not (_inside(p, hring) and ring_dist(p, hring) >= hw["parapet_m"] - TOL)]
                if abs(z_new - hw["deck_z"]) > TOL:
                    bad.append(("rebased_not_on_host_deck", z_new))
            rep["volumes"][vn] = {"kind": "rebased", "host": host, "base_from": z_old, "base_to": z_new,
                                  "faces_changed": len(gone), "faces_v005": len(f5), "faces_v007": len(f7)}
        else:
            bad += [("removed", f) for f in gone] + [("added", f) for f in new]
            rep["volumes"][vn] = {"kind": "unchanged", "faces": len(f5)}
        rep["volumes"][vn]["outside_diff"] = len(bad)
        rep["outside_diff"] += len(bad)
        rep["problems"] += [[vn, str(b)[:200]] for b in bad[:10]]
    rep["pass"] = rep["outside_diff"] == 0
    return rep


def main(argv):
    if len(argv) != 5:
        print(__doc__, file=sys.stderr)
        return 2
    if os.path.exists(argv[4]):
        print("refused: output exists", file=sys.stderr)
        return 2
    docs = []
    for p in argv[:4]:
        with open(p, encoding="utf-8") as fh:
            docs.append(json.load(fh))
    rep = check(*docs)
    rep["inputs"] = [os.path.realpath(p) for p in argv[:4]]
    with open(argv[4], "x", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
    print(json.dumps({vn: v for vn, v in rep["volumes"].items()}, ensure_ascii=False))
    print("outside_diff", rep["outside_diff"], "PASS" if rep["pass"] else "FAIL")
    return 0 if rep["pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
