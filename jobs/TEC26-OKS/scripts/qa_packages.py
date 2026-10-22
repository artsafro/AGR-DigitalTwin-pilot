"""new-case: TEC26 package QA from FBX readback dumps (no Blender): names, budget, xView-exact overlaps (fast core),
doubles 2 mm, UV tiles/regions, VPM-vs-NPM colour per face, UCX hull checks, ZIP contents and PNG headers.

Usage: uv run python qa_packages.py <spec.json> <vpm.zip> <vpm.readback.json> <npm.zip> <npm.readback.json>
                                   <npm_atlas.json> <vpm_textures_dir> <npm_textures_dir> <max_dump.json> <new_out.json>
Scope (Artem 2026-10-22): geometry is the source's - `geometry_source_plus_ring_cuts_*` compares every delivered mesh
with the Max dump (all source vertex positions after the plan-centre pivot shift; new vertices only with spec
`ring_cuts` and only ON source edges; every triangle inside one source polygon, areas covering it exactly) and
`cuts_at_joints` puts every new vertex on a panel edge at a joint; geometry findings are reported, never repaired.
Exit 0 only when every check passes; 1 when a check fails (report still written); 2 on bad input (nothing written).
"""
import io
import json
import math
import os
import sys
import zipfile

import numpy as np
from PIL import Image

from dt_ai.ops.inv_xview import mesh_report

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import finish_map  # noqa: E402

TRI_BUDGET = 150_000  # KPP1 limit per OKS (jobs/KPP1/REPORT.md §2)


def load(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def ucx_hull(o):
    v = np.asarray(o["vertices"], float)
    edges = {}
    ok_convex = True
    c = v.mean(0)
    outward = True
    for f in o["faces"]:
        p = v[f]
        n = np.cross(p[1] - p[0], p[2] - p[0])
        n /= np.linalg.norm(n)
        outward &= bool(np.dot(p.mean(0) - c, n) > 0)
        ok_convex &= bool(((v - p[0]) @ n <= 1e-5).all())
        for k in range(len(f)):
            e = tuple(sorted((f[k], f[(k + 1) % len(f)])))
            edges[e] = edges.get(e, 0) + 1
    return {"closed": all(x == 2 for x in edges.values()), "convex": ok_convex, "outward": outward,
            "tris": sum(len(f) - 2 for f in o["faces"]), "uv_layers": len(o["uv_layers"]),
            "materials": len([m for m in o["materials"] if m["name"]])}


def _poly_geo(src_v, src_faces):
    out = []
    for f in src_faces:
        p = np.asarray([src_v[k] for k in f], float)
        n = np.zeros(3)
        for i in range(len(p)):
            a, b = p[i], p[(i + 1) % len(p)]
            n += [(a[1] - b[1]) * (a[2] + b[2]), (a[2] - b[2]) * (a[0] + b[0]), (a[0] - b[0]) * (a[1] + b[1])]
        ln = np.linalg.norm(n)
        if ln <= 0:
            out.append(None)
            continue
        n /= ln
        keep = [a for a in range(3) if a != int(np.argmax(np.abs(n)))]
        out.append({"n": n, "d": float(n @ p[0]), "p2": p[:, keep], "keep": keep, "lo": p.min(0), "hi": p.max(0),
                    "area": ln / 2})
    return out


def _inside2d(q, poly, tol):
    """Point in polygon (2-D, ray casting); with tol >= 0 a point within tol of an edge counts as inside."""
    x, y = q
    inside = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
        if tol >= 0:
            e = np.array([x2 - x1, y2 - y1])
            t = np.clip(((x - x1) * e[0] + (y - y1) * e[1]) / max(e @ e, 1e-30), 0, 1)
            if np.hypot(x - x1 - t * e[0], y - y1 - t * e[1]) <= tol:
                return True
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def match_source_faces(src_v, src_faces, out_v, out_faces, shift, tol=2e-4):
    """Source polygon of every delivered triangle, by containment (export triangulation, vertex splitting and the
    allowed ring cuts tolerant): a triangle belongs to the source polygon whose plane holds its three corners (within
    `tol`, after undoing the pivot shift), whose outline contains them (edges within `tol` count) and contains the
    triangle centroid strictly. Returns owners per triangle: sorted tuple of source polygon indices, possibly empty."""
    geo = _poly_geo(src_v, src_faces)
    ov = np.asarray(out_v, float) + np.asarray(shift, float)
    owners = []
    for f in out_faces:
        q = ov[list(f)]
        c = q.mean(0)
        qlo, qhi = q.min(0), q.max(0)
        hits = []
        for pi, g in enumerate(geo):
            if g is None or (qlo < g["lo"] - tol).any() or (qhi > g["hi"] + tol).any():
                continue
            if np.abs(q @ g["n"] - g["d"]).max() > tol:
                continue
            if all(_inside2d(x[g["keep"]], g["p2"], tol) for x in q) and _inside2d(c[g["keep"]], g["p2"], -1):
                hits.append(pi)
        owners.append(tuple(hits))
    return owners


def tri_areas(out_v, out_faces):
    v = np.asarray(out_v, float)
    return [float(np.linalg.norm(np.cross(v[f[1]] - v[f[0]], v[f[2]] - v[f[0]])) / 2) for f in out_faces]


def poly_areas(src_v, src_faces):
    return [g["area"] if g else 0.0 for g in _poly_geo(src_v, src_faces)]


def source_finish_report(expected, src_faces, owners, delivered, t_areas=None, p_areas=None):
    """Delivered finish per triangle vs the approved source-ID mapping (finish_map.assign_finishes incl. the ID1
    below-zero split). Fail-closed: an unmatched triangle, a triangle whose candidate source polygons disagree, a
    wrong finish, and a source polygon not covered (by exactly len(f)-2 triangles, or - with areas given, as after
    ring cuts - by triangles whose areas sum to the polygon area within 1e-6 m2 + 1e-5) are all counted as errors."""
    wrong, unmatched, ambiguous, examples = 0, 0, 0, []
    per_poly = [0] * len(src_faces)
    per_area = [0.0] * len(src_faces)
    for t, (own, got) in enumerate(zip(owners, delivered)):
        if not own:
            unmatched += 1
            continue
        want = {expected[i] for i in own}
        if len(own) == 1:
            per_poly[own[0]] += 1
            if t_areas is not None:
                per_area[own[0]] += t_areas[t]
        if len(want) != 1:
            ambiguous += 1
            continue
        w = next(iter(want))
        if got != w:
            wrong += 1
            if len(examples) < 5:
                examples.append({"tri": t, "source_polygon": own[0], "expected": w, "delivered": got})
    if t_areas is not None and p_areas is not None:
        uncovered = [i for i in range(len(src_faces)) if abs(per_area[i] - p_areas[i]) > 1e-6 + 1e-5 * p_areas[i]]
    else:
        uncovered = [i for i, f in enumerate(src_faces) if per_poly[i] != len(f) - 2]
    return {"ok": not (wrong or unmatched or ambiguous or uncovered) and len(owners) > 0, "tris": len(owners),
            "wrong_finish": wrong, "unmatched": unmatched, "ambiguous": ambiguous,
            "source_polygons_not_covered": len(uncovered), "uncovered_examples": uncovered[:5], "examples": examples}


def _new_vertices(src_v, out_v, shift, tol=2e-4):
    sv = np.asarray(src_v, float)
    ov = np.unique(np.round(np.asarray(out_v, float) + np.asarray(shift, float), 5), axis=0)
    d = np.abs(ov[:, None, :] - sv[None, :, :]).max(2)
    missing = int((d.min(0) > tol).sum())          # source vertices absent from the delivery
    return ov[d.min(1) > tol], missing


def _on_edge(q, a, b, tol):
    e = b - a
    t = float((q - a) @ e / max(e @ e, 1e-30))
    return 1e-6 < t < 1 - 1e-6 and np.linalg.norm(a + t * e - q) <= tol


def geometry_report(src_v, src_faces, out_v, shift, cuts_allowed, tol=2e-4):
    """Delivered vertices = all source vertices + (only with spec ring_cuts) new points ON source edges."""
    new, missing = _new_vertices(src_v, out_v, shift, tol)
    sv = np.asarray(src_v, float)
    edges = {tuple(sorted((f[k], f[(k + 1) % len(f)]))) for f in src_faces for k in range(len(f))}
    off = [q.round(4).tolist() for q in new if not any(_on_edge(q, sv[a], sv[b], tol) for a, b in edges)]
    ok = missing == 0 and not off and (cuts_allowed or len(new) == 0)
    return {"ok": ok, "missing_source_vertices": missing, "new_vertices": len(new), "cuts_allowed": bool(cuts_allowed),
            "new_off_source_edges": len(off), "off_examples": off[:5]}


def cut_joint_report(src_v, src_faces, expected, spec, out_v, shift, tol=2e-4):
    """Every new vertex on an edge of a patterned (facade_uv) source polygon sits on a joint of that polygon's joint
    frame (|u' - n P| <= half joint width). Vacuous when no new vertex exists (no cut needed)."""
    new, _ = _new_vertices(src_v, out_v, shift, tol)
    sv = np.asarray(src_v, float)
    lo, hi = finish_map.body_plan_bbox(src_v, spec["zero_m"])
    pat = set(spec.get("facade_uv", {}))
    checked, off = 0, []
    for q in new:
        for pi, f in enumerate(src_faces):
            if expected[pi] not in pat or not any(_on_edge(q, sv[f[k]], sv[f[(k + 1) % len(f)]], tol)
                                                  for k in range(len(f))):
                continue
            t = spec["finishes"][expected[pi]]
            axis, sign, origin = finish_map.joint_origin(src_v, f, lo, hi)
            u = sign * (q[axis] - origin)
            r = u % t["P"][0]
            dist = min(r, t["P"][0] - r)
            checked += 1
            if dist > t.get("joint_half_mm", 4) / 1000:
                off.append({"source_polygon": pi, "u_m": round(float(u), 4), "off_joint_m": round(float(dist), 4)})
    return {"ok": not off, "new_vertices": len(new), "checked_on_patterned_edges": checked, "off_joint": off[:10],
            "off_joint_count": len(off)}


def sample(img, uv):
    h, w = img.shape[:2]
    x = min(w - 1, max(0, int(uv[0] * w)))
    y = min(h - 1, max(0, int((1 - uv[1]) * h)))
    return img[y, x, :3].tolist()


def write(out, obj):
    """Atomic: a crash mid-dump leaves only <out>.partial, never a half report under the final name."""
    tmp = out + ".partial"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, out)


def main(argv):
    spec_p, vzip, vrb, nzip, nrb, atlas_p, vtex, ntex, dump_p, out = argv
    ins = [spec_p, vzip, vrb, nzip, nrb, atlas_p, dump_p]
    if os.path.lexists(out) or os.path.lexists(out + ".partial") or any(os.path.realpath(out) == os.path.realpath(p) for p in ins):
        print(f"refusing to write {out}", file=sys.stderr)
        return 2
    spec, vr, nr, atlas = load(spec_p), load(vrb), load(nrb), load(atlas_p)
    A = spec["address"]
    fin = spec["finishes"]
    rep, fails = {}, []

    def _rep(r):
        return {"ok": r["ok"], "detail": r}

    def check(name, ok, detail):
        rep[name] = {"ok": bool(ok), "detail": detail}
        if not ok:
            fails.append(name)

    vobj = {o["name"]: o for o in vr["objects"]}
    nobj = {o["name"]: o for o in nr["objects"]}
    vmain, nmain = vobj.get(f"SM_{A}_Main"), nobj.get(f"SM_{A}_001_Main")
    ucx = [o for n, o in vobj.items() if n.startswith(f"UCX_SM_{A}_Main_")]
    check("names_vpm", vmain is not None and len(ucx) >= 1 and set(vobj) == {f"SM_{A}_Main"} | {o["name"] for o in ucx},
          sorted(vobj))
    check("names_npm", set(nobj) == {f"SM_{A}_001_Main"}, sorted(nobj))
    if vmain is None or nmain is None:
        write(out, {"checks": rep, "failed": fails})
        return 1
    for tag, o in (("vpm", vmain), ("npm", nmain)):
        tris = sum(len(f) - 2 for f in o["faces"])
        check(f"triangulated_{tag}", all(len(f) == 3 for f in o["faces"]), {"faces": len(o["faces"])})
        check(f"budget_{tag}", 0 < tris <= TRI_BUDGET, {"tris": tris, "budget": TRI_BUDGET})
        check(f"one_uv_{tag}", o["uv_layers"] == ["UVMap"], o["uv_layers"])
        check(f"transforms_{tag}", o["scale"] == [1.0, 1.0, 1.0] and max(map(abs, o["rotation"])) < 1e-6 and
              max(map(abs, o["location"])) < 1e-6, {"loc": o["location"], "rot": o["rotation"], "scale": o["scale"]})
        x = mesh_report(o["vertices"], o["faces"], profile=tag.upper())
        check(f"xview_{tag}", x["passed"], {k: x[k] for k in ("vertex_pairs", "face_pairs", "face_pairs_by_kind",
                                                              "thresholds", "offenders")})
    for o in ucx:
        h = ucx_hull(o)
        check(f"ucx_{o['name']}", h["closed"] and h["convex"] and h["outward"] and h["uv_layers"] == 0
              and h["materials"] == 0, h)
        x = mesh_report(o["vertices"], o["faces"], profile="VPM")
        check(f"xview_{o['name']}", x["passed"], {k: x[k] for k in ("vertex_pairs", "face_pairs")})
    dump = load(dump_p)
    body = next(n for n in dump["nodes"] if n["multisub"])
    hulls = sorted((n for n in dump["nodes"] if not n["multisub"]), key=lambda n: n["name"])
    sv = np.asarray(body["vertices"], float)
    shift = np.array([(sv[:, 0].min() + sv[:, 0].max()) / 2, (sv[:, 1].min() + sv[:, 1].max()) / 2, 0.0])
    src_tris = sum(len(f) - 2 for f in body["faces"])

    def same_points(a, b):
        a = np.unique(np.round(np.asarray(a, float), 4), axis=0)
        b = np.unique(np.round(np.asarray(b, float), 4), axis=0)
        return a.shape == b.shape and bool(np.allclose(a, b, atol=2e-4))

    for tag, o in (("vpm", vmain), ("npm", nmain)):
        tris = sum(len(f) - 2 for f in o["faces"])
        g = geometry_report(body["vertices"], body["faces"], o["vertices"], shift, bool(spec.get("ring_cuts")))
        check(f"geometry_source_plus_ring_cuts_{tag}", g["ok"] and tris >= src_tris,
              dict(g, tris=tris, source_tris=src_tris, pivot_shift=shift.round(4).tolist()))
    check("ucx_count_eq_source", len(ucx) == len(hulls), {"ucx": len(ucx), "source_hulls": [h["name"] for h in hulls]})
    for o, h in zip(sorted(ucx, key=lambda o: o["name"]), hulls):
        check(f"geometry_unchanged_{o['name']}", same_points(o["vertices"], np.asarray(h["vertices"]) - shift) and
              sorted(len(f) for f in o["faces"]) == sorted(len(f) for f in h["faces"]),
              {"source": h["name"], "faces": len(o["faces"]), "source_faces": len(h["faces"])})
    vb = np.asarray(vmain["vertices"]); nb = np.asarray(nmain["vertices"])
    check("bbox_vpm_eq_npm", np.allclose(vb.min(0), nb.min(0), atol=1e-4) and np.allclose(vb.max(0), nb.max(0), atol=1e-4),
          {"vpm": [vb.min(0).round(4).tolist(), vb.max(0).round(4).tolist()], "npm": [nb.min(0).round(4).tolist(),
                                                                                    nb.max(0).round(4).tolist()]})
    check("perimeter_drop_min_z", vb[:, 2].min() <= -1.0 and nb[:, 2].min() <= -1.0,
          {"vpm_min_z": round(float(vb[:, 2].min()), 4), "npm_min_z": round(float(nb[:, 2].min()), 4)})
    # VPM UV: every face inside one finish tile, finish tiles only
    udims = {t["udim"] for t in fin.values()}
    bad_tile, tiles = 0, {}
    for uvs in vmain["face_uvs"]:
        u = np.asarray(uvs)
        tu, tv = np.floor(u.mean(0)).astype(int)
        ud = int(1001 + tu + 10 * tv)
        tiles[ud] = tiles.get(ud, 0) + 1
        loc = u - [tu, tv]
        if ud not in udims or loc.min() < 0 or loc.max() > 1:
            bad_tile += 1
    check("vpm_uv_tiles", bad_tile == 0 and set(tiles) <= udims, {"faces_per_udim": tiles, "bad": bad_tile})
    # NPM UV: every face inside one atlas region
    regions = list(atlas["finishes"].values())
    bad_reg = 0
    for uvs in nmain["face_uvs"]:
        u = np.asarray(uvs)
        if not any((u[:, 0] >= r["u0"] - 1e-6).all() and (u[:, 0] <= r["u0"] + r["size"] + 1e-6).all() and
                   (u[:, 1] >= r["v0"] - 1e-6).all() and (u[:, 1] <= r["v0"] + r["size"] + 1e-6).all() for r in regions):
            bad_reg += 1
    check("npm_uv_regions", bad_reg == 0, {"faces": len(nmain["face_uvs"]), "outside_any_region": bad_reg})
    # colour: every face shows the same finish in VPM (its UDIM tile) and NPM (its atlas region); per finish the median
    # colour of the VPM tile equals the median of the NPM region and the spec/KPP RGB (joints/noise excluded by median)
    by_udim = {t["udim"]: n for n, t in fin.items()}
    by_region = {}
    for n, r in atlas["finishes"].items():
        by_region[n] = r
    tiles_img = {t["udim"]: np.asarray(Image.open(os.path.join(vtex, f"T_{A}_Diffuse_1.{t['udim']}.png")).convert("RGB"))
                 for t in fin.values()}
    atlas_img = np.asarray(Image.open(os.path.join(ntex, f"T_{A}_001_Main_d_1.png")).convert("RGB"))

    def npm_finish(uvs):
        u = np.asarray(uvs).mean(0)
        hits = [n for n, r in by_region.items() if r["u0"] <= u[0] <= r["u0"] + r["size"] and
                r["v0"] <= u[1] <= r["v0"] + r["size"]]
        return hits[0] if len(hits) == 1 else None

    vkey = [tuple(np.round(np.asarray(vmain["vertices"])[f].mean(0), 4)) for f in vmain["faces"]]
    nkey = {tuple(np.round(np.asarray(nmain["vertices"])[f].mean(0), 4)): i for i, f in enumerate(nmain["faces"])}
    mism, unmatched, per_finish = 0, 0, {}
    for i, k in enumerate(vkey):
        j = nkey.get(k)
        if j is None:
            unmatched += 1
            continue
        c = np.asarray(vmain["face_uvs"][i]).mean(0)
        vf = by_udim.get(int(1001 + np.floor(c[0]) + 10 * np.floor(c[1])))
        nf = npm_finish(nmain["face_uvs"][j])
        per_finish[str(vf)] = per_finish.get(str(vf), 0) + 1
        mism += vf is None or vf != nf
    med = {}
    for n, t in fin.items():
        r = by_region[n]
        x0, y1, sz = round(r["u0"] * 2048), round((1 - r["v0"]) * 2048), round(r["size"] * 2048)
        vm = np.median(tiles_img[t["udim"]].reshape(-1, 3), 0)
        nm = np.median(atlas_img[y1 - sz:y1, x0:x0 + sz].reshape(-1, 3), 0)
        med[n] = {"vpm": vm.tolist(), "npm": nm.tolist(), "spec": t["rgb"],
                  "ok": bool(np.abs(vm - nm).max() <= 3 and np.abs(vm - t["rgb"]).max() <= 3)}
    check("colour_vpm_eq_npm_per_face", mism == 0 and unmatched == 0,
          {"faces": len(vkey), "finish_mismatch": int(mism), "unmatched": unmatched, "faces_per_finish": per_finish})
    check("colour_median_vpm_eq_npm_eq_spec", all(m["ok"] for m in med.values()), med)
    # delivered finish per triangle vs the approved source face/ID mapping (incl. the ID1 below-zero split): VPM=NPM
    # alone cannot prove either is right (review #574: all cassette faces remapped to plain blue in both passed)
    try:
        finish_map.validate_spec(spec, finish_map.load_kpp())
        contract_err = None
    except ValueError as e:
        contract_err = str(e)
    check("spec_contract_kpp", contract_err is None, {"error": contract_err})
    expected = finish_map.assign_finishes(body["vertices"], body["faces"], body["mat_ids"], spec)
    vown = match_source_faces(body["vertices"], body["faces"], vmain["vertices"], vmain["faces"], shift)
    nown = match_source_faces(body["vertices"], body["faces"], nmain["vertices"], nmain["faces"], shift)
    vfin = [by_udim.get(int(1001 + np.floor(np.asarray(u).mean(0)[0]) + 10 * np.floor(np.asarray(u).mean(0)[1])))
            for u in vmain["face_uvs"]]
    nfin = [npm_finish(u) for u in nmain["face_uvs"]]
    pa = poly_areas(body["vertices"], body["faces"])
    check("source_finish_vpm", **_rep(source_finish_report(expected, body["faces"], vown, vfin,
                                                           tri_areas(vmain["vertices"], vmain["faces"]), pa)))
    check("source_finish_npm", **_rep(source_finish_report(expected, body["faces"], nown, nfin,
                                                           tri_areas(nmain["vertices"], nmain["faces"]), pa)))
    for tag, o in (("vpm", vmain), ("npm", nmain)):
        check(f"cuts_at_joints_{tag}", **_rep(cut_joint_report(body["vertices"], body["faces"], expected, spec,
                                                               o["vertices"], shift)))
    # texel density of full (patterned) finishes: EVERY triangle the source mapping makes patterned must be measured
    # (no vacuous all([]) pass) and deliver the contract density (KPP twin, or an approved exception) +-1 %; band
    # reg p.32 §6.2 512..1706 px/m
    V = np.asarray(vmain["vertices"], float)
    dens, need, measured, off, degenerate = {}, 0, 0, [], 0
    for t, (o_uvs, f) in enumerate(zip(vmain["face_uvs"], vmain["faces"])):
        own = vown[t]
        want = expected[own[0]] if len(own) == 1 else None
        if want is None or fin[want]["kind"] != "full":
            continue
        need += 1
        p3 = V[f]
        u = np.asarray(o_uvs)
        a3 = np.linalg.norm(np.cross(p3[1] - p3[0], p3[2] - p3[0])) / 2
        if a3 <= 1e-4:
            degenerate += 1
            continue
        if vfin[t] != want:
            continue
        e1, e2 = u[1] - u[0], u[2] - u[0]
        d = math.sqrt(abs(e1[0] * e2[1] - e1[1] * e2[0]) / 2 * spec["size_full"] ** 2 / a3)
        measured += 1
        lo_, hi_ = dens.get(want, (1e9, 0))
        dens[want] = (min(lo_, d), max(hi_, d))
        try:
            c = finish_map.contract_density(want, spec, finish_map.load_kpp())
        except (ValueError, KeyError) as e:
            c = None
        if c is None or abs(d - c) > 0.01 * c or not 512 <= d <= 1706:
            off.append({"tri": t, "finish": want, "px_per_m": round(d, 1), "contract": c})
    check("vpm_texel_contract", need > 0 and measured == need - degenerate and not off,
          {"patterned_tris_expected": need, "measured": measured, "degenerate": degenerate,
           "off_contract": len(off), "examples": off[:5],
           "range_px_per_m": {k: [round(a, 1), round(b, 1)] for k, (a, b) in dens.items()}})
    # ZIP contents and PNG headers
    with zipfile.ZipFile(vzip) as z:
        names = sorted(z.namelist())
        want = sorted([f"SM_{A}.fbx"] + [f"T_{A}_{k}_1.{t['udim']}.png" for t in fin.values()
                                          for k in ("Diffuse", "ERM", "Normal")])
        pngs = {n: Image.open(io.BytesIO(z.read(n))) for n in names if n.endswith(".png")}
        check("vpm_zip_contents", names == want, {"names": names})
        def size_ok(n, im):
            t = next(t for t in fin.values() if n.endswith(f".{t['udim']}.png"))
            if t["kind"] == "placeholder":
                return im.size == (spec["size_placeholder"],) * 2
            full = (spec["size_full"],) * 2
            return im.size == full or ("_ERM_" in n and im.size == (spec["size_placeholder"],) * 2)

        check("vpm_png_rgb", all(im.mode == "RGB" and size_ok(n, im) for n, im in pngs.items()),
              {n: [im.mode, list(im.size)] for n, im in pngs.items()})
    with zipfile.ZipFile(nzip) as z:
        names = sorted(z.namelist())
        check("npm_zip_contents", names == [f"0000_{A}_01.fbx"], {"names": names})
        blob = z.read(names[0])
    emb = [n for n in (f"T_{A}_001_Main_d_1.png", f"T_{A}_001_Main_o_1.png") if n.encode() in blob]
    check("npm_embedded_png", len(emb) == 2 and blob.count(b"\x89PNG") >= 2, {"names_in_fbx": emb,
                                                                               "png_signatures": blob.count(b"\x89PNG")})
    imgs = {i["name"]: i for m in nmain["materials"] for i in m["images"]}
    check("npm_material", [m["name"] for m in nmain["materials"]] == [f"M_{A}_001_Main_1"] and
          {f"T_{A}_001_Main_d_1", f"T_{A}_001_Main_o_1"} <= {os.path.splitext(k)[0] for k in imgs}, imgs)
    for n in ("d", "o"):
        im = Image.open(os.path.join(ntex, f"T_{A}_001_Main_{n}_1.png"))
        check(f"npm_png_{n}_rgb_2048", im.mode == "RGB" and im.size == (2048, 2048), [im.mode, list(im.size)])
    check("vpm_material", [m["name"] for m in vmain["materials"]] == [f"M_{A}_Main_1"] and
          all(not m["images"] for m in vmain["materials"]), [m["name"] for m in vmain["materials"]])
    write(out, {"checks": rep, "failed": fails})
    print("QA-PACKAGES", "PASS" if not fails else "FAIL", len(rep) - len(fails), "/", len(rep), fails)
    return 0 if not fails else 1


if __name__ == "__main__":
    if len(sys.argv) != 11:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1:]))
