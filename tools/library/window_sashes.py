"""Sash candidates from a 3ds Max window-library mesh dump (issue #4).

    uv run python tools/library/window_sashes.py read --dump <dump.json> --output <sash-source.json>
    uv run python tools/library/window_sashes.py apply --types library/windows/window_types.json --sashes <sash-source.json>

Pattern: none — library tooling, not a building node (REVIEW_CHECKLIST Q1: new-case).

Front faces of the frame (material ID 1, normal -Y) are grouped by depth. The level that
covers the frame extent's boundary is the outer frame; a closed inner frame on any other
level is an opening-sash candidate. `sashes` and `handing` on the type list stay null until
the user confirms them — readings are written under `unconfirmed`.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

HOLE_M2 = 0.01
FRONT_Y = -0.99          # unit normal y below this is a front face (the window faces -Y)
_REASONS = {
    "rings": "read from the Max scene: an inner frame on its own depth level inside a field is taken as an "
             "opening sash; not confirmed by the user",
    "rings_overlap": "two sash depth levels overlap at the meeting stile (sliding or not is unknown); "
                     "not confirmed by the user",
    "no_ring": "no inner frame on another depth level: read as fixed glazing (0 sashes); not confirmed by the user",
}
_HAND_MAX = "the Max scene has no handle, hinge or opening-direction geometry"
_HAND_NONE = "the source has no handing data"
_SASH_NONE = "the source has no sash data"
_NOTE = ("Unconfirmed sash and handing readings with their reasons are in each entry's `unconfirmed` field "
         "(tools/library/window_sashes.py).")
_METHOD = (
    "Frame extent is the X/Z bbox of every material ID 1 face (sills 2/3 are not in it); local x/z start at "
    "its minimum and sizes are rounded to 1 mm. Front faces are the ID 1 triangles whose unit normal has "
    "y < -0.99, grouped by depth Y rounded to 1 mm. A level is dropped when its triangles lie outside that "
    "extent or behind the frame back (Y greater than the maximum Y of material ID 4). Each kept level is "
    "rasterised on a 2 mm grid over the extent (a cell is in when its centre lies in a triangle). The outer "
    "frame is the level that covers the most boundary cells. On every other level a 4-connected component is "
    "a sash ring when the complement inside its bbox has a 4-connected region of at least 0.01 m2 that does "
    "not touch the bbox border (a closed frame; that count is the hole count) or, failing that, a region of "
    "that area that touches only one side of the border (a leaf open at the meeting stile, which is modelled "
    "on the other leaf). Other components are ignored. Overlap is true when rings on two different levels "
    "overlap by more than one grid cell in X and in Z, or meet within one grid cell on one axis while "
    "overlapping by more than one cell on the other (the meeting stile of two sliding leaves). The scene has "
    "no handle, hinge or opening-direction geometry, so handing is not read."
)


def _label4(mask):
    """4-connected labels of a boolean mask. Returns (labels int32, count); background is 0."""
    h, w = mask.shape
    labels = np.zeros((h, w), np.int32)
    parent = [0]
    rank = [0]

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        if rank[ra] < rank[rb]:
            parent[ra] = rb
        elif rank[ra] > rank[rb]:
            parent[rb] = ra
        else:
            parent[rb] = ra
            rank[ra] += 1

    prev = []          # runs of the row above: (c0, c1, label), c1 exclusive
    next_id = 0
    for y in range(h):
        xs = np.flatnonzero(mask[y])
        runs = []
        if len(xs):
            breaks = np.flatnonzero(np.diff(xs) > 1)
            starts = np.concatenate(([xs[0]], xs[breaks + 1]))
            ends = np.concatenate((xs[breaks] + 1, [xs[-1] + 1]))
            pi = 0
            for c0, c1 in zip(starts.tolist(), ends.tolist()):
                while pi < len(prev) and prev[pi][1] <= c0:
                    pi += 1
                overlaps, pj = [], pi
                while pj < len(prev) and prev[pj][0] < c1:
                    overlaps.append(prev[pj][2])
                    pj += 1
                if not overlaps:
                    next_id += 1
                    parent.append(next_id)
                    rank.append(0)
                    lab = next_id
                else:
                    lab = overlaps[0]
                    for other in overlaps[1:]:
                        union(lab, other)
                labels[y, c0:c1] = lab
                runs.append((c0, c1, lab))
        prev = runs
    remap = np.zeros(next_id + 1, np.int32)
    root_of, n = {}, 0
    for i in range(1, next_id + 1):
        root = find(i)
        if root not in root_of:
            n += 1
            root_of[root] = n
        remap[i] = root_of[root]
    return remap[labels], n


def _raster(tris, nx, nz, grid):
    """Cells whose centres lie in any triangle. `tris` is (N, 3, 2) in local metres, rows are Z."""
    mask = np.zeros((nz, nx), dtype=bool)
    for tri in tris:
        minx, minz = tri.min(axis=0)
        maxx, maxz = tri.max(axis=0)
        c0 = max(0, int(np.floor(minx / grid - 0.5)))
        c1 = min(nx, int(np.floor(maxx / grid - 0.5)) + 1)
        r0 = max(0, int(np.floor(minz / grid - 0.5)))
        r1 = min(nz, int(np.floor(maxz / grid - 0.5)) + 1)
        if c0 >= c1 or r0 >= r1:
            continue
        xs = (np.arange(c0, c1) + 0.5) * grid
        zs = (np.arange(r0, r1) + 0.5) * grid
        gx, gz = np.meshgrid(xs, zs)
        x0, z0 = tri[0]
        x1, z1 = tri[1]
        x2, z2 = tri[2]
        den = (z1 - z2) * (x0 - x2) + (x2 - x1) * (z0 - z2)
        if abs(den) < 1e-14:
            continue
        a = ((z1 - z2) * (gx - x2) + (x2 - x1) * (gz - z2)) / den
        b = ((z2 - z0) * (gx - x2) + (x0 - x2) * (gz - z2)) / den
        mask[r0:r1, c0:c1] |= (a >= -1e-8) & (b >= -1e-8) & (1 - a - b >= -1e-8)
    return mask


def _rings(mask, grid, depth):
    """Ring components of one level: closed frames with an interior hole of at least 0.01 m2."""
    labels, n = _label4(mask)
    found = []
    for k in range(1, n + 1):
        ys, xs = np.nonzero(labels == k)
        y0, y1 = int(ys.min()), int(ys.max())
        x0, x1 = int(xs.min()), int(xs.max())
        comp = labels[y0:y1 + 1, x0:x1 + 1] == k
        hlab, hn = _label4(~comp)
        sealed = opened = 0
        cell = grid * grid
        for h in range(1, hn + 1):
            region = hlab == h
            if int(region.sum()) * cell < HOLE_M2:
                continue
            # a sliding leaf is drawn open on the meeting stile, so its opening reaches one border
            sides = (int(region[0].any()) + int(region[-1].any())
                     + int(region[:, 0].any()) + int(region[:, -1].any()))
            if sides == 0:
                sealed += 1
            elif sides == 1:
                opened += 1
        holes = sealed or opened
        if holes < 1:
            continue
        rect = (x0 * grid, y0 * grid, (x1 + 1) * grid, (y1 + 1) * grid)
        found.append({"rect": rect, "depth_m": depth, "holes": holes})
    return found


def _object(obj, grid):
    verts = np.asarray(obj["verts"], float)
    faces = np.asarray(obj["faces"], int)
    empty = {"object": obj["name"], "width_m": 0.0, "height_m": 0.0, "outer_depth_m": None,
             "levels": [], "rings": [], "overlap": False, "reading": "no_ring"}
    id1 = faces[:, 3] == 1
    if not id1.any():
        return empty
    pts = verts[faces[id1][:, :3].reshape(-1)]
    minx, maxx = float(pts[:, 0].min()), float(pts[:, 0].max())
    minz, maxz = float(pts[:, 2].min()), float(pts[:, 2].max())
    width, height = maxx - minx, maxz - minz
    id4 = faces[:, 3] == 4
    back_y = float(verts[faces[id4][:, :3].reshape(-1), 1].max()) if id4.any() else None

    tri = faces[id1][:, :3]
    a, b, c = verts[tri[:, 0]], verts[tri[:, 1]], verts[tri[:, 2]]
    normal = np.cross(b - a, c - a)
    length = np.linalg.norm(normal, axis=1)
    front = (length > 0) & (normal[:, 1] / np.maximum(length, 1e-15) < FRONT_Y)
    ymean = (a[:, 1] + b[:, 1] + c[:, 1]) / 3
    if back_y is not None:
        front &= ymean <= back_y
    # a triangle outside the frame extent (X/Z) cannot be part of the front frame
    outside = ((np.maximum(np.maximum(a[:, 0], b[:, 0]), c[:, 0]) < minx - 1e-6)
               | (np.minimum(np.minimum(a[:, 0], b[:, 0]), c[:, 0]) > maxx + 1e-6)
               | (np.maximum(np.maximum(a[:, 2], b[:, 2]), c[:, 2]) < minz - 1e-6)
               | (np.minimum(np.minimum(a[:, 2], b[:, 2]), c[:, 2]) > maxz + 1e-6))
    front &= ~outside
    groups = defaultdict(list)
    for i in np.flatnonzero(front):
        groups[round(float(ymean[i]), 3)].append(
            np.stack(((a[i, 0] - minx, a[i, 2] - minz), (b[i, 0] - minx, b[i, 2] - minz),
                      (c[i, 0] - minx, c[i, 2] - minz))))
    nx = max(1, int(np.floor(width / grid - 0.5 + 1e-9)) + 1)
    nz = max(1, int(np.floor(height / grid - 0.5 + 1e-9)) + 1)
    levels = []
    for depth in sorted(groups):
        mask = _raster(np.asarray(groups[depth]), nx, nz, grid)
        if not mask.any():
            continue
        levels.append({"depth_m": depth, "area_m2": round(float(mask.sum()) * grid * grid, 4), "mask": mask})
    if not levels:
        empty["width_m"], empty["height_m"] = round(width, 3), round(height, 3)
        return empty
    boundary = np.zeros((nz, nx), dtype=bool)
    boundary[0, :] = boundary[-1, :] = boundary[:, 0] = boundary[:, -1] = True
    outer = max(levels, key=lambda lv: (int((lv["mask"] & boundary).sum()), lv["area_m2"]))
    rings = []
    for lv in levels:
        if lv is outer:
            continue
        rings.extend(_rings(lv["mask"], grid, lv["depth_m"]))
    overlap = any(ra["depth_m"] != rb["depth_m"] and _overlap(ra["rect"], rb["rect"], grid)
                  for i, ra in enumerate(rings) for rb in rings[i + 1:])
    rings.sort(key=lambda r: (r["rect"][0], r["rect"][1]))
    reading = "rings_overlap" if overlap else "rings" if rings else "no_ring"
    return {"object": obj["name"], "width_m": round(width, 3), "height_m": round(height, 3),
            "outer_depth_m": outer["depth_m"],
            "levels": [{"depth_m": lv["depth_m"], "area_m2": lv["area_m2"]} for lv in levels],
            "rings": [{"rect_m": [round(v, 3) for v in r["rect"]], "depth_m": r["depth_m"], "holes": r["holes"]}
                      for r in rings],
            "overlap": overlap, "reading": reading}


def _overlap(a, b, grid):
    """Rings on two levels that cross, or that meet along a stile.

    A crossing overlaps by more than one grid cell in both X and Z. A meeting stile
    overlaps by more than one cell on one axis and touches within one cell on the other
    (one leaf carries the stile, so the two rectangles abut)."""
    ox = min(a[2], b[2]) - max(a[0], b[0])
    oz = min(a[3], b[3]) - max(a[1], b[1])
    deep_x, deep_z = ox > grid, oz > grid
    meet_x, meet_z = ox >= -grid, oz >= -grid
    return (deep_x and meet_z) or (deep_z and meet_x)


def read_sashes(dump, *, grid_m=0.002):
    """Sash-source document for one mesh dump. One object per dump object, in dump order."""
    return {"schema": "window-sash-source-max/1",
            "source": {"file": Path(dump["file"]).name, "method": _METHOD},
            "objects": [_object(obj, grid_m) for obj in dump["objects"]]}


def apply_sashes(types_doc, sources):
    """Write unconfirmed sash and handing candidates onto every type. `sashes` and `handing` stay null.

    `sources` is a list of (repo-relative posix path, sash-source doc). An entry whose Max object is
    missing from every source is an error. Replacing `unconfirmed` makes a second call a no-op.
    """
    by_name = {}
    for path, doc in sources:
        for obj in doc["objects"]:
            by_name[obj["object"]] = (path, obj)
    missing = [t["source"]["max_object"] for t in types_doc["types"]
               if t.get("source", {}).get("max_object") and t["source"]["max_object"] not in by_name]
    if missing:
        raise SystemExit(f"sash source has no object {missing[0]}")
    for t in types_doc["types"]:
        name = t.get("source", {}).get("max_object")
        if name:
            path, obj = by_name[name]
            sashes = {"candidate": len(obj["rings"]), "rects_m": [r["rect_m"] for r in obj["rings"]],
                      "reason": _REASONS[obj["reading"]], "source": path}
            handing = {"candidate": None, "reason": _HAND_MAX}
        else:
            sashes = {"candidate": None, "reason": _SASH_NONE}
            handing = {"candidate": None, "reason": _HAND_NONE}
        t["unconfirmed"] = {"sashes": sashes, "handing": handing}
    note = types_doc.get("note") or ""
    if _NOTE not in note:
        types_doc["note"] = f"{note} {_NOTE}".strip()
    return types_doc


def _write(path, doc):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _repo_path(path):
    path = Path(path).resolve()
    root = Path(__file__).resolve().parents[2]
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    rd = sub.add_parser("read")
    rd.add_argument("--dump", type=Path, required=True)
    rd.add_argument("--output", type=Path, required=True)
    apy = sub.add_parser("apply")
    apy.add_argument("--types", type=Path, required=True)
    apy.add_argument("--sashes", type=Path, action="append", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "read":
        doc = read_sashes(json.loads(args.dump.read_text(encoding="utf-8")))
        _write(args.output, doc)
        counts = {k: sum(o["reading"] == k for o in doc["objects"]) for k in ("no_ring", "rings", "rings_overlap")}
        print(f"sashes: {len(doc['objects'])} objects "
              f"(no_ring {counts['no_ring']}, rings {counts['rings']}, rings_overlap {counts['rings_overlap']}) "
              f"-> {args.output}")
        return
    types_doc = json.loads(args.types.read_text(encoding="utf-8"))
    sources = [(_repo_path(p), json.loads(Path(p).read_text(encoding="utf-8"))) for p in args.sashes]
    apply_sashes(types_doc, sources)
    _write(args.types, types_doc)
    n = sum(t["unconfirmed"]["sashes"]["candidate"] is not None for t in types_doc["types"])
    print(f"window types: {len(types_doc['types'])} entries, unconfirmed sashes on {n} -> {args.types}")


if __name__ == "__main__":
    main()
