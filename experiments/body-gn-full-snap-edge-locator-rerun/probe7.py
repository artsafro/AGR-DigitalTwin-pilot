"""t_c2691740 probe7: prototype - band_h as POINT attribute + zero extrude + Set Position(Top, +band_h).

No face->point mean of the offset, so every top vertex of a band should get f32(f32(z0) + f32(h)).
Measures distinct float32 top z per band vs the pinned extrude (snap.top_tree). Scratch only.
"""
import json, sys, time
from collections import defaultdict
from pathlib import Path
import numpy as np

LIB = Path(r"C:/x/t_ad9bc345")
sys.path.insert(0, str(LIB))
src = (LIB / "snap.py").read_text(encoding="utf-8")
ns = {"__file__": str(LIB / "snap.py"), "__name__": "snap_lib"}
exec(compile(src.rstrip()[: -len("main()")], str(LIB / "snap.py"), "exec"), ns)
import bpy  # noqa: E402

OUT = Path(sys.argv[sys.argv.index("--") + 1])
contours = json.loads(ns["CONTOURS"].read_text(encoding="utf-8"))
snapc = json.loads(Path(r"C:/x/t_ad9bc345/snapped_contours.json").read_text(encoding="utf-8"))
bpy.ops.wm.read_factory_settings(use_empty=True)
f32 = np.float32


def add_point_h(me):
    """Copy face band_h to a POINT attribute band_h_pt (each cap vertex belongs to exactly one band)."""
    fh = np.zeros(len(me.polygons), dtype=np.float32)
    me.attributes["band_h"].data.foreach_get("value", fh)
    ph = np.full(len(me.vertices), np.nan, dtype=np.float32)
    conflicts = 0
    for p in me.polygons:
        for v in p.vertices:
            if not np.isnan(ph[v]) and ph[v] != fh[p.index]:
                conflicts += 1
            ph[v] = fh[p.index]
    me.attributes.new("band_h_pt", "FLOAT", "POINT").data.foreach_set("value", ph)
    return conflicts


def proto_tree():
    ng = bpy.data.node_groups.new("TopProto", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    n, L = ng.nodes, ng.links
    gin, gout = n.new("NodeGroupInput"), n.new("NodeGroupOutput")
    ext = n.new("GeometryNodeExtrudeMesh")
    ext.mode = "FACES"
    ext.inputs["Individual"].default_value = False
    ext.inputs["Offset Scale"].default_value = 0.0  # constant: no field mixing
    ext.inputs["Offset"].default_value = (0.0, 0.0, 0.0)
    attr = n.new("GeometryNodeInputNamedAttribute")
    attr.data_type = "FLOAT"
    attr.inputs["Name"].default_value = "band_h_pt"
    comb = n.new("ShaderNodeCombineXYZ")
    sp = n.new("GeometryNodeSetPosition")
    st = n.new("GeometryNodeStoreNamedAttribute")
    st.data_type = "BOOLEAN"
    st.domain = "FACE"
    st.inputs["Name"].default_value = "is_top"
    L.new(gin.outputs[0], ext.inputs["Mesh"])
    L.new(ext.outputs["Mesh"], st.inputs["Geometry"])
    L.new(ext.outputs["Top"], st.inputs["Value"])
    L.new(st.outputs[0], sp.inputs["Geometry"])
    L.new(ext.outputs["Top"], sp.inputs["Selection"])
    L.new(attr.outputs[0], comb.inputs["Z"])
    L.new(comb.outputs[0], sp.inputs["Offset"])
    L.new(sp.outputs[0], gout.inputs[0])
    return ng


def tops(c, co, polys, is_top, band):
    out = {}
    for bi, b in enumerate(c["bands"]):
        zz = defaultdict(int)
        for fi, p in enumerate(polys):
            if is_top[fi] and band[fi] == bi:
                for v in p:
                    zz[co[v, 2].tobytes().hex()] += 1
        if zz:
            exp = f32(f32(b["z0"]) + f32(float(b["z1"]) - float(b["z0"]))).tobytes().hex()
            out[str(bi)] = {"top_z": dict(zz), "expected_hex": exp, "all_expected": list(zz) == [exp]}
    return out


res = {"variants": {}}
for name, c in (("unchanged", contours), ("full_snap", snapc)):
    row = {}
    for tree in ("pinned_extrude", "point_h_setpos"):
        me = ns["build_cap_ids"](c)
        row["point_attr_conflicts"] = add_point_h(me)
        ng = ns["top_tree"]() if tree == "pinned_extrude" else proto_tree()
        t = []
        for _ in range(3):
            t0 = time.perf_counter()
            co, polys, is_top, band = ns["eval_tree"](me, ng)
            t.append(time.perf_counter() - t0)
        bpy.data.node_groups.remove(ng)
        bpy.data.meshes.remove(me)
        tp = tops(c, co, polys, is_top, band)
        row["_geo_" + tree] = (co.astype(np.float64), polys)
        row[tree] = {"faces": len(polys), "median_eval_s": round(sorted(t)[1], 4),
                     "bands_multi_z": [k for k, v in tp.items() if len(v["top_z"]) > 1],
                     "bands_not_expected": [k for k, v in tp.items() if not v["all_expected"]], "tops": tp}
        print(name, tree, "faces", len(polys), "median_s", row[tree]["median_eval_s"], "multi_z", row[tree]["bands_multi_z"],
              "not_expected", row[tree]["bands_not_expected"], "band2", tp["2"]["top_z"], flush=True)
    (ca, pa), (cb, pb) = row.pop("_geo_pinned_extrude"), row.pop("_geo_point_h_setpos")
    row["same_topology"] = pa == pb
    row["max_dev_mm"] = float(np.abs(ca - cb).max() * 1000) if ca.shape == cb.shape else None
    row["n_verts_moved"] = int((np.abs(ca - cb).max(axis=1) > 0).sum()) if ca.shape == cb.shape else None
    print(name, "conflicts", row["point_attr_conflicts"], "same_topology", row["same_topology"], "max_dev_mm", row["max_dev_mm"], "moved", row["n_verts_moved"], flush=True)
    res["variants"][name] = row
OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
print("DONE", flush=True)
