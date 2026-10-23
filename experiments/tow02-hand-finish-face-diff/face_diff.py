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
