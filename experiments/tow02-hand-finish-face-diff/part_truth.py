"""M2: how good is the research's UV-swatch + z part label? Ground truth = the 37 TOW02_* source objects of
build-v030 tow02_tex.blend (dumped by bl_dump.py blend), matched to export-v005 faces by world centroid + normal.
Usage: python part_truth.py <tmpdir>   (needs bl_parts.json, v005.fbx, out_raw/faces_v005.tsv, out_raw/added_user_tris.tsv)
"""
import collections, json, math, sys
import face_diff as fd

T = sys.argv[1]
src = {k: v for k, v in json.load(open(T + "/bl_parts.json")).items() if k.startswith("TOW02_")}


def group(obj):
    if obj.startswith("TOW02_fin_"): return "fins"
    return {"TOW02_top": "TOW02_top", "TOW02_top_glass": "top_glass", "TOW02_ac_railing_glass": "ac_railing_glass",
            "TOW02_railing_glass": "ac_railing_glass", "TOW02_ac_baskets": "ac_basket", "TOW02_ac_coping": "ac_basket"
            }.get(obj, "body")   # body, body_glass, soffit, louvre, coping


V, P, _, _ = fd.mesh(T + "/v005.fbx", fd.OBJ)
items = [((r[0], r[1], r[2]), (r[3], r[4], r[5]), o) for o, rows in src.items() for r in rows]
g = fd.Grid([(c, None, None) for c, _, _ in items], 0.05)
used = set(); truth = []; dists = []
for p in P:
    c = tuple(sum(V[i][a] for i in p) / len(p) for a in range(3))
    n = fd.tri(V, p[:3])[1]
    best, bd = None, 0.005
    for j in g.near(c, 0.005):
        if j in used: continue
        d = math.dist(c, items[j][0])
        if d <= bd and fd.dot(n, items[j][1]) >= 0.99: best, bd = j, d
    if best is None:
        truth.append(None)
    else:
        used.add(best); truth.append(items[best][2]); dists.append(bd)
print("MATCH v005_faces=%d source_faces=%d matched=%d max_d_mm=%.3f" % (len(P), len(items), sum(t is not None for t in truth), 1000 * max(dists)))

rows = [l.rstrip("\r\n").split("\t") for l in open(T + "/out_raw/faces_v005.tsv")][1:]
conf = collections.Counter((r[1], group(t) if t else "?") for r, t in zip(rows, truth))
print("CONFUSION (research label -> true group): " + json.dumps({"%s->%s" % k: v for k, v in sorted(conf.items())}))
acc = sum(v for (a, b), v in conf.items() if a == b) / len(rows)
print("LABEL_ACCURACY %.4f" % acc)

# H2 share with research labels vs true labels
HOT = {"TOW02_top", "top_glass", "ac_railing_glass"}
cent = [(float(r[4]), float(r[5]), float(r[6])) for r in rows]
ga = fd.Grid([(c, None, None) for c in cent], 0.5)
added = [l.rstrip("\r\n").split("\t") for l in open(T + "/out_raw/added_user_tris.tsv")][1:]


def share(label_of):
    hot = tot = 0
    by = collections.Counter()
    for i, r in enumerate(rows):
        if r[2] == "unchanged": continue
        k = len(P[i]) - 2; lab = label_of(i); tot += k; by[lab] += k
        if lab in HOT or cent[i][2] >= fd.Z_TOP: hot += k
    for a in added:
        c = (float(a[3]), float(a[4]), float(a[5]))
        best, bd = None, 2.0
        for i in ga.near(c, 2.0):
            d = math.dist(c, cent[i])
            if d < bd: best, bd = i, d
        lab = label_of(best) if best is not None else ("TOW02_top" if c[2] >= fd.Z_TOP else "body")
        tot += 1; by[lab] += 1
        if lab in HOT or c[2] >= fd.Z_TOP: hot += 1
    return dict(changed_tris=tot, hot_tris=hot, h2_share=round(hot / tot, 4),
                h2_share_with_baskets=round((hot + sum(v for k, v in by.items() if k == "ac_basket")) / tot, 4) if tot else None,
                by_part=dict(by))


print("H2_RESEARCH " + json.dumps(share(lambda i: rows[i][1])))
print("H2_TRUE " + json.dumps(share(lambda i: group(truth[i]) if truth[i] else rows[i][1])))
objc = collections.Counter()
for i, r in enumerate(rows):
    if r[2] != "unchanged": objc[(truth[i] or "?") if not (truth[i] or "").startswith("TOW02_fin_") else "TOW02_fin_*"] += len(P[i]) - 2
print("CHANGED_V005_TRIS_BY_TRUE_OBJECT " + json.dumps(dict(objc.most_common())))
