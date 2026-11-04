# Research: TOW02 — where did the user's hand finish change faces (export-v005 vs the user's final FBX)?

Card t_87c6a6f9 (research, no GitHub issue). Answers retro hypothesis H2 of
`docs/research/job-retro-vyatskaya-tow02-pr515.md` ("the 5 h hand finish fixed the top floors and the railings")
and feeds the open review issue #514.

## Summary

- Compared export-v005 (`SM_Vyatskaya_Vl_47_49_013_Main.fbx`, 35 407 faces, quads) with the user's
  `for_placement/0213_Vyatskaya_Vl_47_49_05.fbx`, object `SM_..._013_Main` (73 594 triangles: 3ds Max exported it fully
  triangulated). Same coordinates: the user only moved the pivot (`GeometricTranslation` = -bbox centre).
- 33 256 of 35 407 v005 faces (93.9 %) are unchanged at 1 mm; 1 292 moved (4.7-21 mm, median 7.7 mm); 859 deleted;
  4 634 user triangles are new. Changed geometry = 8 936 triangles (12 % of the user mesh), new area 929 m2.
- **H2 is rejected as stated**: only 28.4 % of the changed triangles are in TOW02_top / top_glass / ac_railing_glass
  or at z >= 64.7. Counting the AC baskets that carry the balcony railing glass as "railings" gives 71.5 % — still < 80 %.
- Where the hand finish went: (1) AC baskets + their railing glass on every floor z 10-60 (620 + 666 faces moved
  4.7-21 mm, 2 709 + 291 triangles added) = 5 632 tris, 63 %; (2) the fin bottoms at z 0-5 (433 deleted,
  612 added) and new fin geometry below z = 0 down to -0.81 m (254 tris); (3) the top floors z >= 64.7
  (279 deleted, 362 added, 40 moved) — the part the user named.
- Of the 81 independent-checker overlap pairs (proxy for xView's 185 faces, whose list was never exported):
  soffit z 6.9 — 16 of 32 faces deleted (one of each coplanar pair); top 69.52/76.32 and railing glass 70.1/76.9 —
  4 of 6 deleted; basket glass 14.99/18.39 moved; the 58 tiny contact slivers at 69.175/75.975 all deleted on the
  TOW02_top side and on top_glass 73.95, kept on top_glass 67.15.

## Findings

All numbers below were produced by me with the script at the end (`python face_diff.py`, 3.4 s, pure Python, no
Blender run — the card forbids running DCC). Inputs read-only, SHA-256 prefixes verified:
export-v005 `ff8994dc4b7c…` (1 391 596 B), user FBX `2fd800812c53…` (6 302 640 B, matches STATE.md `2fd80081…`).

### Method (verified by running)

1. Own binary FBX 7.4 reader (zlib arrays) reads `Vertices`, `PolygonVertexIndex`, UV of the model named
   `SM_Vyatskaya_Vl_47_49_013_Main` in both files. The user file holds 4 models (012/013/014/015; 014 is a mirrored
   instance of 013, 015 of 012); only 013 is compared. Raw vertices of both files share one frame: 41 879 of 44 000 v005
   vertices exist in the user mesh on a 1 mm grid; bboxes equal in x/y to 1 mm; user z goes down to -0.808 (v005: 0.0).
2. v005 quads are split with both diagonals; a face is **unchanged** when all triangles of one diagonal have a user
   triangle with centroid <= 1 mm and normal dot >= 0.9995 (each user triangle used once); **moved** when they are
   found within 25 mm, dot >= 0.996; else **deleted**. User triangles left over are **added** and get the part of the
   nearest v005 face centroid (<= 2 m). Re-run at 2 mm / dot 0.999 gave identical counts (stable).
3. Part labels (the joined FBX has no part attribute: `join_export_blender.py` removes `tow02_src_part` after the
   weld): UV centroid -> rect in `build-v030/atlas_layout.json` (v flipped). Window strips -> top_glass if z >= 64.7
   else body (body_glass; gives exactly 86 top_glass faces = `build-v029/run.log` CLEAN_DONE); `glass_solid` ->
   ac_railing_glass (732 faces, z 11.6-76.9); `fin_*` -> fins; `ac_coping/ac_perforated/ac_floor` -> ac_basket;
   other swatches (wall, roof, soffit, reveal, louvre, coping, ledge) -> TOW02_top if z >= 64.7 else body.
   This is an approximation of the 37 Blender objects (inferred, not read from the .blend).

### Per part (v005 faces; added in user triangles; changed = moved + deleted + added, in triangles)

| part | unchanged | moved <= 25 mm | deleted | added (user tris) | changed (tris) |
|---|---:|---:|---:|---:|---:|
| TOW02_top | 3188 | 6 | 227 | 208 | 674 |
| ac_basket | 1663 | 620 | 0 | 2709 | 3949 |
| ac_railing_glass | 36 | 666 | 30 | 291 | 1683 |
| body | 20300 | 0 | 127 | 450 | 704 |
| fins | 8005 | 0 | 453 | 938 | 1844 |
| top_glass | 64 | 0 | 22 | 38 | 82 |

### Per z-band (5 m bands by face centroid; z >= 64.7 is its own band)

| z band | unchanged | moved <= 25 mm | deleted | added (user tris) | changed (tris) |
|---|---:|---:|---:|---:|---:|
| -5-00 | 0 | 0 | 0 | 254 | 254 |
| 00-05 | 306 | 0 | 433 | 612 | 1478 |
| 05-10 | 3058 | 0 | 103 | 206 | 412 |
| 10-15 | 2710 | 136 | 0 | 272 | 544 |
| 15-20 | 2295 | 136 | 0 | 432 | 704 |
| 20-25 | 2862 | 68 | 0 | 272 | 408 |
| 25-30 | 2489 | 136 | 0 | 256 | 528 |
| 30-35 | 2940 | 136 | 0 | 440 | 712 |
| 35-40 | 2387 | 204 | 0 | 440 | 848 |
| 40-45 | 2151 | 0 | 0 | 176 | 176 |
| 45-50 | 2329 | 272 | 0 | 528 | 1072 |
| 50-55 | 2193 | 0 | 26 | 18 | 70 |
| 55-60 | 1991 | 164 | 18 | 366 | 730 |
| 60-65 | 1776 | 0 | 0 | 0 | 0 |
| z>=64.7 | 3769 | 40 | 279 | 362 | 1000 |

### Overlap faces (proxy for xView 185)

`outputs/xview-v005/xview_tol_faces.txt` does not exist; `xview_tol_report.jsonl` has only the count (185). Used the
independent checker's `outputs/xview-v005/ovl_pairs.json` (81 pairs = 162 faces: 23 "OVL23" + 58 "TINY"):

| group | part, z | faces: deleted / moved / unchanged |
|---|---|---|
| OVL23 | body soffit z 6.9 (16 coplanar pairs) | 16 / 0 / 16 — one face of each pair removed |
| OVL23 | TOW02_top z 69.52 / 76.32 | 1 / 0 / 2 |
| OVL23 | ac_railing_glass z 70.13 / 76.93 | 3 / 0 / 0 |
| OVL23 | basket glass vs basket z 14.2-18.4 (gap 4.1 mm) | 0 / 4 / 4 — glass moved, basket kept |
| TINY | TOW02_top z 69.175 / 75.975 | 58 / 0 / 0 |
| TINY | top_glass z 73.95 / 67.15 | 26 / 0 / 32 |

So the user removed the overlap at the soffit and the top floor by deleting faces, and cured the basket glass by
moving it (4.7-21 mm, consistent with "rebuilt so they do not overlap").

### Outputs (not committed; `C:/x/tow02-hand-finish-face-diff/`)

`face_diff.py`, `summary.json`, `faces_v005.tsv` (status per v005 face), `added_user_tris.tsv`, `ovl_pairs_status.json`,
`sens_2mm/` (tolerance re-run).

## How it applies to this repository

- `jobs/vyatskaya-tow02/STATE.md` ("User finish 2026-10-21"): the user's description (top floors + balcony glass)
  is right about *what*, but 63 % of the changed triangles are in the AC baskets / railing glass on all floors, and
  the fin bottoms at z 0-5 were rebuilt and extended 0.81 m below the v005 ground (z = 0) — not mentioned anywhere.
- `jobs/vyatskaya-tow02/scripts/build_decor_blender.py` (AC baskets, railing glass) and `build_fins.py` (fin bases)
  are the generators to fix first; `build_top_blender.py` / `fix_overlaps_blender.py` for the 279 deleted top faces.
- `jobs/vyatskaya-tow02/scripts/join_export_blender.py` drops `tow02_src_part`; keeping a part id per face (e.g. a
  face attribute exported as a separate UV/colour set or a side-car JSON) would make this diff exact.
- xView parity (`docs/domain/` validation rules; retro finding "own Overlapping Faces is not xView"): the soffit
  coplanar duplicates and the TINY slivers are real overlaps the user removed; the 4.1 mm basket gaps were moved
  apart rather than deleted.

## Proposed next tasks

1. **TOW02 AC basket + railing glass generator: no glass within 5 mm of the basket** — in
   `build_decor_blender.py` offset the railing glass >= 25 mm from basket faces (the user moved the glass 7.7-21.1 mm),
   add a 5 mm parallel-face check per basket, re-run on build-v030 and compare against the user's mesh with
   `face_diff.py` (target: ac_basket+glass changed tris 5 632 -> < 500). Value high / effort M. Advances #514.
2. **TOW02 fin bases: what did the user build at z -0.81..5?** — export the 433 deleted + 866 added fin triangles
   (`faces_v005.tsv`, `added_user_tris.tsv`) as a marker FBX and ask the user whether the fins must reach the
   ground/terrain line below z = 0 (a plinth rule for Ground/OKS contact). Value medium / effort S. Advances #514.
3. **Keep a per-face part id through join/export** — write `tow02_src_part` per face into a side-car JSON next to
   the FBX in `join_export_blender.py` (generic: `src/dt_ai` export step) so later diffs/QA can report per part exactly
   instead of by UV swatch + z. Value medium / effort S. Advances #149.
4. **Reusable `fbx_face_diff` tool** — promote the pure-Python reader + triangle matcher to `tools/qa/` with a test on
   two tiny synthetic FBX files; use it for every "our export vs the user's fix" review. Value medium / effort M.
   Advances #149.

## Open questions for the user

1. Fins below z = 0 (down to -0.81 m) at the base: intended (the building stands on a lower terrain line), or a side
   effect of the hand edit? Should our generator do the same?
2. AC baskets: 620 basket faces moved 4.7-19 mm and 2 709 triangles added on floors z 10-60 — was the basket shape
   changed on purpose (more detail), or only to clear the railing glass?
3. Is `SM_..._014_Main` (mirrored instance of 013) part of the TOW02 delivery or a second tower?

<details><summary>Script: face_diff.py (verbatim, also at C:/x/tow02-hand-finish-face-diff/face_diff.py)</summary>

```python
"""TOW02 hand-finish face diff: export-v005 (Blender, quads) vs the user's final FBX (3ds Max, triangles).

Pure Python (no Blender, no numpy): reads both binary FBX files, triangulates the v005 quads with both diagonals and
matches triangles by centroid (1 mm) + normal. Usage: python face_diff.py [out_dir]
Research card t_87c6a6f9; read-only on both inputs.
"""
import collections, json, math, struct, sys, zlib

V5 = "C:/Users/artsafro/.AGR-DigitalTwin_pilot/jobs/vyatskaya-tow02/outputs/export-v005/SM_Vyatskaya_Vl_47_49_013_Main.fbx"
USER = ("C:/Users/artsafro/Desktop/!3D viz/NTR/26_Vyatskoe/001 - Моделирование НПМ с нуля/"
        "001 - Моделирование НПМ с нуля/for_placement/0213_Vyatskaya_Vl_47_49_05.fbx")
ATLAS = "C:/Users/artsafro/.AGR-DigitalTwin_pilot/jobs/vyatskaya-tow02/outputs/build-v030/atlas_layout.json"
OVL = "C:/Users/artsafro/.AGR-DigitalTwin_pilot/jobs/vyatskaya-tow02/outputs/xview-v005/ovl_pairs.json"
OBJ = "SM_Vyatskaya_Vl_47_49_013_Main"
TOL_SAME, TOL_MOVE, DOT_SAME, DOT_MOVE, Z_TOP = 0.001, 0.025, 0.9995, 0.996, 64.7


def read_fbx(path):
    data = open(path, "rb").read()
    assert data[:20] == b"Kaydara FBX Binary  "
    big = struct.unpack_from("<I", data, 23)[0] >= 7500

    def prop(o):
        t = chr(data[o]); o += 1
        if t in "YCILFD":
            f = {"Y": "<h", "C": "<?", "I": "<i", "L": "<q", "F": "<f", "D": "<d"}[t]
            return struct.unpack_from(f, data, o)[0], o + struct.calcsize(f)
        if t in "fdlib":
            n, enc, cl = struct.unpack_from("<III", data, o); o += 12
            raw = data[o:o + cl]; raw = zlib.decompress(raw) if enc else raw
            return list(struct.unpack("<%d%s" % (n, {"f": "f", "d": "d", "l": "q", "i": "i", "b": "?"}[t]), raw)), o + cl
        n = struct.unpack_from("<I", data, o)[0]; o += 4
        return (data[o:o + n].decode("utf-8", "replace") if t == "S" else data[o:o + n]), o + n

    def node(o):
        end, np_, _ = struct.unpack_from("<QQQ" if big else "<III", data, o); o += 24 if big else 12
        nl = data[o]; o += 1
        if end == 0:
            return None, o
        name = data[o:o + nl].decode(); o += nl
        props = []
        for _ in range(np_):
            v, o = prop(o); props.append(v)
        kids = []
        while o < end:
            k, o = node(o)
            if k is None:
                break
            kids.append(k)
        return (name, props, kids), end

    o, top = 27, []
    while o < len(data) - 200:
        n, o = node(o)
        if n is None:
            break
        top.append(n)
    return top


def kid(n, name):
    return [k for k in n[2] if k[0] == name]


def mesh(path, want):
    """Raw local vertices of the model named want* (GeometricTranslation ignored: it only moves the pivot)."""
    top = read_fbx(path)
    objs = next(n for n in top if n[0] == "Objects"); conns = next(n for n in top if n[0] == "Connections")
    geo = {k[1][0]: k for k in objs[2] if k[0] == "Geometry"}; mod = {k[1][0]: k for k in objs[2] if k[0] == "Model"}
    gid = next(c[1][1] for c in conns[2] if c[1][0] == "OO" and c[1][1] in geo and c[1][2] in mod
               and mod[c[1][2]][1][1].startswith(want))
    g = geo[gid]
    v = kid(g, "Vertices")[0][1][0]
    verts = [(v[i], v[i + 1], v[i + 2]) for i in range(0, len(v), 3)]
    polys, cur = [], []
    for i in kid(g, "PolygonVertexIndex")[0][1][0]:
        cur.append(~i if i < 0 else i)
        if i < 0:
            polys.append(cur); cur = []
    uvl = kid(g, "LayerElementUV")[0]
    return verts, polys, kid(uvl, "UV")[0][1][0], kid(uvl, "UVIndex")[0][1][0]


def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def tri(V, ids):
    a, b, c = (V[i] for i in ids)
    n = cross(sub(b, a), sub(c, a)); ln = math.sqrt(dot(n, n))
    cen = tuple((a[k] + b[k] + c[k]) / 3 for k in range(3))
    return cen, (tuple(x / ln for x in n) if ln > 1e-12 else (0, 0, 0)), ln / 2


class Grid:
    def __init__(self, items, cell):
        self.cell, self.items, self.h = cell, items, collections.defaultdict(list)
        for i, (c, _n, _a) in enumerate(items):
            self.h[self.key(c)].append(i)

    def key(self, c): return tuple(int(math.floor(x / self.cell)) for x in c)

    def near(self, c, r):
        k, s = self.key(c), int(math.ceil(r / self.cell))
        for dx in range(-s, s + 1):
            for dy in range(-s, s + 1):
                for dz in range(-s, s + 1):
                    yield from self.h.get((k[0] + dx, k[1] + dy, k[2] + dz), ())


def classify(fuv, z, atlas):
    S, x, y = atlas["size"], fuv[0] * atlas["size"], (1 - fuv[1]) * atlas["size"]
    hit = None
    for n, s in atlas["swatches"].items():
        rx, ry, rw, rh = s["rect"]
        if rx - 1 <= x <= rx + rw + 1 and ry - 1 <= y <= ry + rh + 1:
            hit = n; break
    if hit is None:
        for s in atlas["strips"]:
            for pc in s["pieces"]:
                rx, ry, rw, rh = pc["rect"]
                if rx - 1 <= x <= rx + rw + 1 and ry - 1 <= y <= ry + rh + 1:
                    hit = "window"
    if hit == "window":
        return "top_glass" if z >= Z_TOP else "body"      # body_glass is reported inside body
    if hit == "glass_solid":
        return "ac_railing_glass"
    if hit and hit.startswith("fin_"):
        return "fins"
    if hit in ("ac_coping", "ac_perforated", "ac_floor"):
        return "ac_basket"
    return "TOW02_top" if z >= Z_TOP else "body"           # wall/roof/soffit/reveal/louvre/coping/ledge by z


def main(out_dir):
    atlas = json.load(open(ATLAS, encoding="utf-8"))
    AV, AP, AUV, AUI = mesh(V5, OBJ)
    BV, BP, _, _ = mesh(USER, OBJ)
    B = [tri(BV, p) for p in BP]
    assert all(len(p) == 3 for p in BP), "user mesh expected fully triangulated"
    gB = Grid(B, 0.05)
    used = [False] * len(B)

    def find(t, r, dmin, taken):
        best, bd = None, r
        for j in gB.near(t[0], r):
            if used[j] or j in taken:
                continue
            d = math.dist(t[0], B[j][0])
            if d <= bd and dot(t[1], B[j][1]) >= dmin:
                best, bd = j, d
        return best, bd

    faces, k = [], 0
    for fi, p in enumerate(AP):
        uvc = (sum(AUV[2 * AUI[k + i]] for i in range(len(p))) / len(p),
               sum(AUV[2 * AUI[k + i] + 1] for i in range(len(p))) / len(p)); k += len(p)
        cen = tuple(sum(AV[i][a] for i in p) / len(p) for a in range(3))
        diags = [[(p[0], p[1], p[2])]] if len(p) == 3 else \
            [[(p[0], p[1], p[2]), (p[0], p[2], p[3])], [(p[1], p[2], p[3]), (p[1], p[3], p[0])]]
        faces.append(dict(i=fi, c=cen, part=classify(uvc, cen[2], atlas), diags=[[tri(AV, t) for t in d] for d in diags]))
    # pass 1: unchanged (every triangle of one diagonal found within 1 mm, same normal)
    for f in faces:
        f["st"] = None
        for d in f["diags"]:
            got = []
            for t in d:
                j, _ = find(t, TOL_SAME, DOT_SAME, got)
                if j is None or t[2] < 1e-9:
                    break
                got.append(j)
            if len(got) == len(d):
                for j in got: used[j] = True
                f["st"], f["d"] = "unchanged", 0.0; break
    # pass 2: moved (<= 25 mm, normal within ~5 deg); else deleted
    for f in faces:
        if f["st"]:
            continue
        for d in f["diags"]:
            got, dm = [], 0.0
            for t in d:
                j, dd = find(t, TOL_MOVE, DOT_MOVE, got)
                if j is None:
                    break
                got.append(j); dm = max(dm, dd)
            if len(got) == len(d):
                for j in got: used[j] = True
                f["st"], f["d"] = "moved", dm; break
        if not f["st"]:
            f["st"], f["d"] = "deleted", None
    # added user triangles: part of the nearest v005 face centroid (<= 2 m), else by z
    gA = Grid([(f["c"], None, None) for f in faces], 0.5)
    added = []
    for j, t in enumerate(B):
        if used[j]:
            continue
        best, bd = None, 2.0
        for i in gA.near(t[0], 2.0):
            d = math.dist(t[0], faces[i]["c"])
            if d < bd: best, bd = i, d
        part = faces[best]["part"] if best is not None else ("TOW02_top" if t[0][2] >= Z_TOP else "body")
        added.append(dict(j=j, c=t[0], part=part, a=t[2]))

    def band(z): return "z>=64.7" if z >= Z_TOP else "%02d-%02d" % (int(z // 5) * 5, int(z // 5) * 5 + 5)
    tab = collections.defaultdict(lambda: collections.Counter())
    for f in faces:
        ntri = len(f["diags"][0])
        for key in (("part", f["part"]), ("band", band(f["c"][2])), ("all", "all")):
            tab[key][f["st"]] += 1; tab[key][f["st"] + "_tri"] += ntri
    for a in added:
        for key in (("part", a["part"]), ("band", band(a["c"][2])), ("all", "all")):
            tab[key]["added_tri"] += 1
    ovl = json.load(open(OVL, encoding="utf-8"))
    ovl_res = collections.Counter(); ovl_rows = []
    for pr in ovl["pairs"]:
        for side in ("a", "b"):
            f = faces[pr[side]]
            ovl_res[(pr.get("group", "?"), f["st"])] += 1
            ovl_rows.append(dict(face=pr[side], group=pr.get("group"), status=f["st"], part=f["part"], z=round(f["c"][2], 3)))
    out = dict(inputs=dict(v005=V5, user=USER), v005_faces=len(AP), user_tris=len(BP),
               table={"%s:%s" % k: dict(v) for k, v in sorted(tab.items())},
               ovl_pairs_faces={"%s:%s" % k: v for k, v in sorted(ovl_res.items())})
    json.dump(out, open(out_dir + "/summary.json", "w"), indent=1)
    json.dump(ovl_rows, open(out_dir + "/ovl_pairs_status.json", "w"), indent=1)
    with open(out_dir + "/faces_v005.tsv", "w") as fh:
        fh.write("face\tpart\tstatus\tmax_move_m\tx\ty\tz\n")
        for f in faces:
            fh.write("%d\t%s\t%s\t%s\t%.4f\t%.4f\t%.4f\n" % (f["i"], f["part"], f["st"], "" if f["d"] is None else "%.4f" % f["d"], *f["c"]))
    with open(out_dir + "/added_user_tris.tsv", "w") as fh:
        fh.write("tri\tpart\tarea_m2\tx\ty\tz\n")
        for a in added:
            fh.write("%d\t%s\t%.6f\t%.4f\t%.4f\t%.4f\n" % (a["j"], a["part"], a["a"], *a["c"]))
    print(json.dumps(out["table"]["all:all"]))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "C:/x/tow02-hand-finish-face-diff")
```

</details>
