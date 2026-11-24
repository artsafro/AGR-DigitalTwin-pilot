"""#1784 step 3 v007 hook (stage `body`, point `after`): completeness census of the Revit FBX [D378].

Pattern: n/a | new-case: the denominator of the decor table. Every mesh object of the Revit dump
(`tools/methods/body/revit_fbx_dump_blender.py`, hull XY + z per object) is grouped by family (name without the
Revit id suffix) and placed against the accepted body v005 (volume rings + roof): `inside` (centre inside a ring,
under its top), `face` (within FACE_M of a ring edge), `roof` (over a ring, above the roof), `out` (none of these).
Pure Python, read-only.

    uv run python jobs/sokolniki-uvk1000/hooks/inset_census.py SOK_DUMP.json VOLUME_LINES.json NEW_CENSUS.json

Output `revit-census/1`: {"families": [{"family", "count", "tris", "bbox": [x0, y0, z0, x1, y1, z1],
"place": {"inside": n, "face": n, "roof": n, "out": n}, "height": [min, max]}], "objects": [{"name", "family",
"place", "bbox"}]}.
"""
import json
import math
import os
import re
import sys

FACE_M = 0.8
_ID = re.compile(r"(_[0-9a-f]{7}| \[\d+\]|\.\d{3})$")


def family(name):
    """Revit family/type of an FBX object: the name without the Revit id suffix (`_<hex7>`, ` [<id>]`, `.001`)."""
    prev = None
    while prev != name:
        prev, name = name, _ID.sub("", name).strip()
    return name


def _inside(p, ring):
    x, y = p
    n, c = len(ring), False
    for i in range(n):
        (x0, y0), (x1, y1) = ring[i], ring[(i + 1) % n]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            c = not c
    return c


def _dist(p, ring):
    best = math.inf
    for i in range(len(ring)):
        (x0, y0), (x1, y1) = ring[i], ring[(i + 1) % len(ring)]
        dx, dy = x1 - x0, y1 - y0
        L = dx * dx + dy * dy
        t = 0.0 if L == 0 else max(0.0, min(1.0, ((p[0] - x0) * dx + (p[1] - y0) * dy) / L))
        best = min(best, math.hypot(p[0] - x0 - t * dx, p[1] - y0 - t * dy))
    return best


def place(obj, volumes):
    hull = obj["hull"]
    c = (sum(x for x, _ in hull) / len(hull), sum(y for _, y in hull) / len(hull))
    z0, z1 = obj["z"]
    zc = (z0 + z1) / 2.0
    for v in volumes.values():
        ring, base = v["ring"], v["levels"][0]
        if _dist(c, ring) < FACE_M and base - 0.5 <= zc <= v["top"] + 0.5:
            return "face"
    for v in volumes.values():
        ring, base = v["ring"], v["levels"][0]
        if _inside(c, ring):
            if zc > v["roof"] + 0.05 and z0 >= v["roof"] - 0.5:
                return "roof"
            if base - 0.5 <= zc <= v["top"] + 0.5:
                return "inside"
    return "out"


def census(dump, lines):
    vols = lines["volumes"]
    fams, objs = {}, []
    for o in dump["objects"]:
        if not o.get("hull"):
            continue
        f = family(o["name"])
        xs = [x for x, _ in o["hull"]]
        ys = [y for _, y in o["hull"]]
        bb = [min(xs), min(ys), o["z"][0], max(xs), max(ys), o["z"][1]]
        pl = place(o, vols)
        objs.append({"name": o["name"], "family": f, "place": pl, "bbox": [round(b, 3) for b in bb]})
        r = fams.setdefault(f, {"family": f, "count": 0, "tris": 0, "bbox": list(bb),
                                "place": {"inside": 0, "face": 0, "roof": 0, "out": 0}, "height": [math.inf, 0.0]})
        r["count"] += 1
        r["tris"] += o.get("tris", 0)
        r["place"][pl] += 1
        r["bbox"] = [min(r["bbox"][i], bb[i]) for i in range(3)] + [max(r["bbox"][i], bb[i]) for i in range(3, 6)]
        h = bb[5] - bb[2]
        r["height"] = [min(r["height"][0], h), max(r["height"][1], h)]
    out = sorted(fams.values(), key=lambda r: -r["count"])
    for r in out:
        r["bbox"] = [round(b, 2) for b in r["bbox"]]
        r["height"] = [round(h, 2) for h in r["height"]]
    return {"schema": "revit-census/1", "source_sha256": dump.get("sha256"), "families": out, "objects": objs}


def main(argv):
    if len(argv) != 3:
        print("usage: inset_census.py SOK_DUMP.json VOLUME_LINES.json NEW_CENSUS.json", file=sys.stderr)
        return 2
    if os.path.exists(argv[2]):
        print("refused: output exists", file=sys.stderr)
        return 2
    with open(argv[0], encoding="utf-8") as fh:
        dump = json.load(fh)
    with open(argv[1], encoding="utf-8") as fh:
        lines = json.load(fh)
    doc = census(dump, lines)
    with open(argv[2], "x", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
    print("CENSUS_OK", len(doc["families"]), "families", len(doc["objects"]), "objects")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
