"""t_c2691740 run8 = run5 + PROTO tree (band_h POINT attr, zero extrude, Set Position Top +band_h_pt); variants unchanged/full_snap.
run5 (copy of frozen t_03a8a042 run4 + full_snap variant + measure_tops): locate the edges that make the TOW02 self-intersected mesh non-PWN.

Variants: unchanged, only_8_10 (same contours as t_ad9bc345 run3).
A) boolean tap output (pinned 24c94691 tree): edges with non-zero orientation sum (Blender is_pwn rule).
B) weld tap output -> new mesh copy -> edit mode -> bpy.ops.mesh.intersect(solver='EXACT', separate_mode='NONE')
   (exact self-intersection, BOOLEAN_NONE path) -> same edge rule.
Each unbalanced edge: endpoints (float64 + float32 hex z), band, incident faces (count, net, normal class).
"""
import copy
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

LIB = Path(r"C:/x/t_ad9bc345")
sys.path.insert(0, str(LIB))
src = (LIB / "snap.py").read_text(encoding="utf-8")
ns = {"__file__": str(LIB / "snap.py"), "__name__": "snap_lib"}
exec(compile(src.rstrip()[: -len("main()")], str(LIB / "snap.py"), "exec"), ns)
import bpy  # noqa: E402

P = ns["P"]
OUT = Path(sys.argv[sys.argv.index("--") + 1])
run1 = json.loads((LIB / "run1.json").read_text(encoding="utf-8"))
contours = json.loads(ns["CONTOURS"].read_text(encoding="utf-8"))
chg = {c["upper_band"]: c["new_z0"] for c in run1["changes"] if c["z0_changed_f32"]}
bpy.ops.wm.read_factory_settings(use_empty=True)

_orig_gn_tree = P._gn_tree


def _proto_gn_tree(tap, hole_tolerant):
    ng = _orig_gn_tree(tap, hole_tolerant)
    n, L = ng.nodes, ng.links
    ext = next(x for x in n if x.bl_idname == "GeometryNodeExtrudeMesh")
    join = next(x for x in n if x.bl_idname == "GeometryNodeJoinGeometry")
    for lk in list(ext.inputs["Offset"].links):
        L.remove(lk)
    ext.inputs["Offset"].default_value = (0.0, 0.0, 0.0)
    ext.inputs["Offset Scale"].default_value = 0.0
    attr = n.new("GeometryNodeInputNamedAttribute")
    attr.data_type = "FLOAT"
    attr.inputs["Name"].default_value = "band_h_pt"
    comb = n.new("ShaderNodeCombineXYZ")
    sp = n.new("GeometryNodeSetPosition")
    L.new(attr.outputs[0], comb.inputs["Z"])
    L.new(comb.outputs[0], sp.inputs["Offset"])
    L.new(ext.outputs["Top"], sp.inputs["Selection"])
    for lk in list(ext.outputs["Mesh"].links):
        to = lk.to_socket
        L.remove(lk)
        L.new(sp.outputs[0], to)
    L.new(ext.outputs["Mesh"], sp.inputs["Geometry"])
    return ng


P._gn_tree = _proto_gn_tree
_orig_build = ns["build_cap_ids"]


def _build_pt(c):
    me = _orig_build(c)
    fh = np.zeros(len(me.polygons), dtype=np.float32)
    me.attributes["band_h"].data.foreach_get("value", fh)
    ph = np.zeros(len(me.vertices), dtype=np.float32)
    for p in me.polygons:
        for v in p.vertices:
            ph[v] = fh[p.index]
    me.attributes.new("band_h_pt", "FLOAT", "POINT").data.foreach_set("value", ph)
    return me


ns["build_cap_ids"] = _build_pt


def f32hex(z):
    return np.float32(z).tobytes().hex()


def band_of(z, bands):
    zf = float(np.float32(z))
    hits = []
    for i, b in enumerate(bands):
        z0, z1 = float(np.float32(b["z0"])), float(np.float32(b["z1"]))
        if abs(zf - z1) < 1e-4:
            hits.append(f"top{i}")
        elif abs(zf - z0) < 1e-4:
            hits.append(f"bot{i}")
        elif z0 < zf < z1:
            hits.append(f"in{i}")
    return "/".join(hits) or "?"


def unbalanced(coords, polys, bands, cap=60):
    tot = defaultdict(int)
    inc = defaultdict(list)
    for fi, p in enumerate(polys):
        for i in range(len(p)):
            a, b = p[i], p[(i + 1) % len(p)]
            k = (a, b) if a < b else (b, a)
            tot[k] += 1 if a < b else -1
            inc[k].append(fi)
    bad = sorted((k for k, v in tot.items() if v != 0), key=lambda k: (coords[k[0]][2], coords[k[0]][0]))
    C = np.asarray(coords, dtype=np.float64)

    def fclass(fi):
        p = polys[fi]
        v = C[p]
        n = np.zeros(3)
        for i in range(len(p)):
            n += np.cross(v[i], v[(i + 1) % len(p)])
        n /= (np.linalg.norm(n) or 1.0)
        cls = "up" if n[2] > 0.99 else "down" if n[2] < -0.99 else "vert" if abs(n[2]) < 0.01 else "slope"
        return {"f": fi, "cls": cls, "nverts": len(p), "zmin": round(float(v[:, 2].min()), 6), "zmax": round(float(v[:, 2].max()), 6)}

    rows = []
    for k in bad[:cap]:
        a, b = C[k[0]], C[k[1]]
        rows.append({
            "v": list(k), "net": tot[k], "nfaces": len(inc[k]),
            "a": [round(float(x), 6) for x in a], "b": [round(float(x), 6) for x in b],
            "za_f32": f32hex(a[2]), "zb_f32": f32hex(b[2]),
            "band_a": band_of(a[2], bands), "band_b": band_of(b[2], bands),
            "len": round(float(np.linalg.norm(a - b)), 6),
            "faces": [fclass(f) for f in inc[k]],
        })
    hist = defaultdict(int)
    for k in bad:
        hist[f"{f32hex(C[k[0]][2])}|{f32hex(C[k[1]][2])}"] += 1
    return {"edges": len(tot), "unbalanced_edges": len(bad), "polys": len(polys), "verts": len(coords),
            "z_hist": dict(hist), "rows": rows}


def self_intersect(w):
    me = bpy.data.meshes.new("weld_copy")
    me.from_pydata([tuple(c) for c in w["coords"]], [], w["polys"])
    o = bpy.data.objects.new("weld_copy", me)
    bpy.context.scene.collection.objects.link(o)
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    r = bpy.ops.mesh.intersect(mode="SELECT", separate_mode="NONE", solver="EXACT")
    bpy.ops.object.mode_set(mode="OBJECT")
    coords, polys, _, _ = P.read_mesh(o.data)
    bpy.data.objects.remove(o)
    bpy.data.meshes.remove(me)
    return coords, polys, list(r)


def variants():
    out = {"unchanged": contours}
    c = copy.deepcopy(contours)
    for b in (8, 10):
        c["bands"][b]["z0"] = chg[b]
    out["full_snap"] = json.loads(Path(r"C:/x/t_ad9bc345/snapped_contours.json").read_text(encoding="utf-8"))
    return out


import time
st = {"run4_py_sha256": ns["sha"](__file__), "chg": chg, "variants": {}}
for name, c in variants().items():
    t0 = time.perf_counter()
    me = ns["build_cap_ids"](c)
    tops = ns["measure_tops"](c, me)["bands"]
    top_summary = {k: {"n_top_z": v["n_top_z"], "top_z": [(t["hex"], t["vert_refs"]) for t in v["top_z"]]} for k, v in tops.items()}
    b = P.tap_eval(me, "boolean", False)
    cen = P.census_pack(b["coords"], b["polys"])["brief"]
    A = unbalanced(b["coords"], b["polys"], c["bands"])
    w = P.tap_eval(me, "weld", False)
    Wb = unbalanced(w["coords"], w["polys"], c["bands"], cap=0)
    sc, sp, r = self_intersect(w)
    B = unbalanced(sc, sp, c["bands"])
    B["op_result"] = r
    st["variants"][name] = {"boolean_census": cen, "boolean": A, "weld_unbalanced": Wb["unbalanced_edges"], "self_intersect": B, "tops": top_summary, "variant_s": round(time.perf_counter() - t0, 1)}
    bpy.data.meshes.remove(me)
    print(name, "census", cen, "bool_unbal", A["unbalanced_edges"], "weld_unbal", Wb["unbalanced_edges"],
          "si_unbal", B["unbalanced_edges"], "si_polys", B["polys"], flush=True)
st["contours_sha256_after"] = ns["sha"](ns["CONTOURS"])
OUT.write_text(json.dumps(P.conv(st), indent=1), encoding="utf-8")
print("DONE", flush=True)
