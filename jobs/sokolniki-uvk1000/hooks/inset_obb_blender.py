"""#1784 step 3 hook (stage `body`, point `after`), Blender side: oriented boxes of the Revit inset families.

Pattern: n/a | new-case: read-only PCA box per Revit FBX object of the families named in insets_config.json
(`families` prefixes) - the only geometry input of inset_build.py. Never saves a .blend, never edits the FBX.

    blender44 -b --factory-startup --python jobs/sokolniki-uvk1000/hooks/inset_obb_blender.py -- \
        SRC.fbx jobs/sokolniki-uvk1000/insets_config.json NEW_OBB.json

Output `revit-obb/1`: {"source", "sha256", "objects": [{"name", "family", "verts", "tris", "center": [x,y,z],
"axes": [[3], [3], [3]] (unit, descending extent), "half": [a, b, c], "zmin", "zmax"}]}. Metres after import.
"""
import hashlib
import json
import os
import sys

import bpy  # noqa: E402
import numpy as np  # noqa: E402


def obb(w):
    c = w.mean(axis=0)
    d = w - c
    _, vecs = np.linalg.eigh(d.T @ d)
    axes = vecs[:, ::-1].T  # descending variance
    p = d @ axes.T
    lo, hi = p.min(axis=0), p.max(axis=0)
    center = c + ((lo + hi) / 2.0) @ axes
    half = (hi - lo) / 2.0
    order = np.argsort(-half)
    return center, axes[order], half[order]


def pane(me, w):
    """Largest flat sheet of an object (canopy glass without its hangers): the polygons parallel to the polygon with
    the largest area; returns its plane box {"center", "axes": [u, v, n], "half": [hu, hv, ht]}."""
    big = max(me.polygons, key=lambda p: p.area)
    m_n = np.array(big.normal, dtype=np.float64)
    par = [p for p in me.polygons if abs(float(np.dot(np.array(p.normal), m_n))) > 0.995]
    # world plane offset of the biggest sheet; keep the parallel polygons within the glass thickness (no hanger faces)
    wn = np.cross(w[big.vertices[1]] - w[big.vertices[0]], w[big.vertices[2]] - w[big.vertices[0]])
    wn /= np.linalg.norm(wn)
    d0 = float(w[list(big.vertices)].mean(axis=0) @ wn)
    sel = [p for p in par if abs(float(w[list(p.vertices)].mean(axis=0) @ wn) - d0) < 0.04]
    idx = sorted({i for p in sel for i in p.vertices})
    c, ax, hf = obb(w[idx])
    return {"center": [round(float(x), 5) for x in c], "axes": [[round(float(x), 6) for x in a] for a in ax],
            "half": [round(float(x), 5) for x in hf], "polygons": len(sel)}


def relief(w):
    """[D384] Pyramid relief of a vertical decor panel ('Панель фасадная 2 Фигурная'): plan normal n (horizontal,
    toward the apex), in-plane horizontal v, the panel rect (v0..v1, z0..z1), the back plane t_back, the rim front
    t_front (max t at the four rect corners), the apex (mean of the vertices within 3 mm of the max t). Coordinates:
    P = origin + v * V + t * N in plan, z absolute."""
    c = w.mean(axis=0)
    d = w - c
    _, vecs = np.linalg.eigh(d.T @ d)
    n = np.array([vecs[0, 0], vecs[1, 0], 0.0])  # smallest-variance axis, flattened (panels are vertical)
    if np.linalg.norm(n) < 0.5:
        raise ValueError("relief panel is not vertical")
    n /= np.linalg.norm(n)
    v = np.array([-n[1], n[0], 0.0])
    t, s, z = d @ n, d @ v, w[:, 2]

    def spread(mask):
        return float(np.ptp(s[mask]) + np.ptp(z[mask])) if mask.any() else 0.0
    if spread(t >= t.max() - 0.003) > spread(t <= t.min() + 0.003):  # the wide flat side is the back
        n, v, t, s = -n, -v, -t, -s
    v0, v1, z0, z1 = float(s.min()), float(s.max()), float(z.min()), float(z.max())
    corner = np.zeros(len(t), dtype=bool)
    for cv in (v0, v1):
        for cz in (z0, z1):
            corner |= (np.abs(s - cv) < 0.02) & (np.abs(z - cz) < 0.02)
    apex = t >= t.max() - 0.003
    r = lambda x: round(float(x), 5)  # noqa: E731
    return {"origin": [r(x) for x in c], "N": [r(x) for x in n], "V": [r(x) for x in v],
            "v": [r(v0), r(v1)], "z": [r(z0), r(z1)], "t_back": r(t.min()), "t_front": r(t[corner].max()),
            "t_apex": r(t.max()), "apex_v": r(s[apex].mean()), "apex_z": r(z[apex].mean())}


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(argv) != 3:
        print("usage: inset_obb_blender.py -- SRC.fbx insets_config.json NEW_OBB.json", file=sys.stderr)
        sys.exit(2)
    src, cfg_path, out = argv
    if os.path.exists(out):
        print("refused: output exists", file=sys.stderr)
        sys.exit(2)
    with open(cfg_path, encoding="utf-8") as fh:
        fams = json.load(fh)["families"]
    h = hashlib.sha256()
    with open(src, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=src)
    objs = []
    for ob in bpy.context.scene.objects:
        if ob.type != "MESH":
            continue
        fam = next((k for k, f in fams.items() if any(ob.name.startswith(p) for p in f["prefixes"])), None)
        if fam is None or not len(ob.data.vertices):
            continue
        me, n = ob.data, len(ob.data.vertices)
        co = np.empty(n * 3, dtype=np.float64)
        me.vertices.foreach_get("co", co)
        m = np.array(ob.matrix_world, dtype=np.float64)
        w = co.reshape(n, 3) @ m[:3, :3].T + m[:3, 3]
        c, ax, hf = obb(w)
        rec = {}
        if fams[fam].get("pane"):
            rec["pane"] = pane(me, w)
        if fams[fam].get("relief"):
            rec["relief"] = relief(w)
        objs.append({**rec, "name": ob.name, "family": fam, "verts": n,
                     "tris": sum(len(p.vertices) - 2 for p in me.polygons),
                     "center": [round(float(x), 5) for x in c], "axes": [[round(float(x), 6) for x in a] for a in ax],
                     "half": [round(float(x), 5) for x in hf],
                     "zmin": round(float(w[:, 2].min()), 4), "zmax": round(float(w[:, 2].max()), 4)})
    doc = {"schema": "revit-obb/1", "source": os.path.realpath(src), "sha256": h.hexdigest(), "objects": objs}
    with open(out, "x", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False)
    print("OBB_OK", len(objs), out)


main()
