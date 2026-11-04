"""t_c2691740 probe6: does band 2's 13.7 m top split follow vertex valence (face->point mean of band_h)?

For each variant: extrude exactly as the pinned tree (snap.top_tree), then for every band-2 top vertex count
the band-2 top faces around it (= cap faces sharing the vertex) and record its float32 z.
Prediction (numpy float32): z = f32(z0) + mean_n(h32), mean_n = f32(sum of n copies of h32) * f32(1/n)
(and the alternative f32(sum)/n). Scratch only; reads contours, writes nothing but the JSON given after --.
"""
import copy, json, sys
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


def pred(z0, z1, n, mode):
    h = f32(float(z1) - float(z0))
    s = f32(0.0)
    for _ in range(n):
        s = f32(s + h)
    m = f32(s * f32(1.0 / n)) if mode == "mul_inv" else f32(s / f32(n))
    return f32(f32(z0) + m).tobytes().hex()


res = {"variants": {}}
for name, c in (("unchanged", contours), ("full_snap", snapc)):
    me = ns["build_cap_ids"](c)
    ng = ns["top_tree"]()
    co, polys, is_top, band = ns["eval_tree"](me, ng)
    bpy.data.node_groups.remove(ng)
    bpy.data.meshes.remove(me)
    per_band = {}
    for bi in range(len(c["bands"])):
        val = defaultdict(int)
        for fi, p in enumerate(polys):
            if is_top[fi] and band[fi] == bi:
                for v in p:
                    val[v] += 1
        if not val:
            continue
        tab = defaultdict(lambda: defaultdict(int))
        for v, n in val.items():
            tab[n][co[v, 2].tobytes().hex()] += 1
        z0, z1 = c["bands"][bi]["z0"], c["bands"][bi]["z1"]
        rows, hits = [], {"mul_inv": 0, "div": 0}
        for n in sorted(tab):
            obs = dict(tab[n])
            p_mul, p_div = pred(z0, z1, n, "mul_inv"), pred(z0, z1, n, "div")
            hits["mul_inv"] += obs.get(p_mul, 0)
            hits["div"] += obs.get(p_div, 0)
            rows.append({"valence": n, "observed": obs, "pred_mul_inv": p_mul, "pred_div": p_div})
        nv = len(val)
        per_band[str(bi)] = {"top_verts": nv, "n_top_z": len({co[v, 2].tobytes() for v in val}),
                             "pred_hit": {k: f"{x}/{nv}" for k, x in hits.items()}, "rows": rows}
    res["variants"][name] = per_band
    b2 = per_band["2"]
    print(name, "band2", b2["n_top_z"], b2["pred_hit"], [(r["valence"], r["observed"]) for r in b2["rows"]], flush=True)
    print(name, "bands with >1 top z:", [k for k, v in per_band.items() if v["n_top_z"] > 1],
          "pred_hit all bands:", {k: v["pred_hit"] for k, v in per_band.items()}, flush=True)
OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
print("DONE", flush=True)
