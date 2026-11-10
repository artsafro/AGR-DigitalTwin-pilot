"""Real AC08 kernel-operation run: invariants BEFORE and AFTER each op, FBX export and readback parity (#752).

    uv run python jobs/TEC26-OKS/AC08/kernel-ops-v001/run_kernel_ops.py --work C:/x/ev_<card>/v001 \
        [--evidence jobs/TEC26-OKS/AC08/kernel-ops-v001/evidence] [--no-blender]

Input: the tracked, hash-pinned real AC08 Max dump `jobs/TEC26-OKS/AC08/max-dump-008.json` (sha256 pinned in
docs/experiments/hyp-663.md; Max 2026.3 scene "04-09 Geometry Final.max", layer 008). Node "АС.08" is split into
its connected components (body / knob / plate, ordered by face count); the UCX node "Colizii_044" is reported in
the drop list (collision hull, not a render part). Every op runs on a fresh copy of the source scene.

Per state the same metric set is computed on the ACTUAL candidate in memory and, after Blender 5.1 FBX export +
tools/blender/fbx_readback.py, on the readback (per-polygon material ids included); a state is accepted only if every
row is within tol and no UV was lost on export. Payload -> readback fidelity is reported separately. Metrics:
faces/vertices/degrees, open edges, non-manifold edges, zero-area faces, twinqa topology defects,
quad dominance (inv_quads, VPM-OKS), xView (inv_xview, 2/5 mm), texel_ready (VPM-OKS), UV coverage/mirroring.
The kernel visibility invariants (invariants.check_operation) are recorded per op from the op itself.
Native 3ds Max xView (tools/qa/xview_parity.py) is NOT run: this card launches no 3ds Max (Max-lock rule).
Outputs: FBX/readback under --work (outside git), JSON + Markdown under --evidence. Existing outputs are refused.
Pattern: none | new-case: job-local real-AC08 kernel-op evidence driver (#752).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path

import numpy as np

from dt_ai.ops import inv_xview as ix
from dt_ai.ops.attached_decor import move_rigid
from dt_ai.ops.contour import NumpyExtrude, _rebuild as _contour_rebuild, rebuild_by_contour
from dt_ai.ops.inv_quads import PolyMesh, quad_report
from dt_ai.ops.inv_texel import PolyMesh as TexelPolyMesh, texel_report
from dt_ai.ops.invariants import (Context, Mesh, check_operation, no_close_overlap, no_visible_back_faces,
                                  open_borders_hidden)
from dt_ai.ops.operations import (OperationRefused, embed_into_neighbour, keep, primitive_box, run_operation,
                                  to_opacity_plane)
from dt_ai.ops.seams import join_parts, simplify_part
from dt_ai.ops.silhouette import SILHOUETTE_MAX_M
from twinqa.geometry.topology import count_defects

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
SOURCE = ROOT / "jobs" / "TEC26-OKS" / "AC08" / "max-dump-008.json"
SOURCE_SHA256 = "f1fc27dc77d5d194ae25aebe8aeb23e71993ab0890cb08def97279bac3e45225"  # docs/experiments/hyp-663.md
PROFILE = "VPM-OKS"
PART_NAMES = ("AC08_body", "AC08_knob", "AC08_plate")   # connected components by descending face count
ZERO_AREA_M2 = ix.AREA_EPS_M2
UV_AGREE = 1e-5                 # #1144: source corners at one vertex carry one UV only when they agree this close
READBACK_ROUND_M = 1e-6          # fbx_readback rounds world coordinates to 6 decimals
EXPORT = HERE / "export_states_blender.py"
READBACK = ROOT / "tools" / "blender" / "fbx_readback.py"


class InputError(ValueError):
    pass


# ---- source ----------------------------------------------------------------------------------------------------

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_source(path: Path = SOURCE, expected: str = SOURCE_SHA256):
    """(scene state, drop list). state: part -> {"v", "faces", "uv" (per-face corners), "mat"}."""
    got = sha256(path)
    if got != expected:
        raise InputError(f"{path}: sha256 {got} != pinned {expected}")
    dump = json.loads(path.read_text(encoding="utf-8"))
    if dump.get("units") != "meters" or dump.get("unit_scale") != 1.0:
        raise InputError(f"units {dump.get('units')!r} x {dump.get('unit_scale')!r}; expected meters x 1.0")
    nodes = {n["name"]: n for n in dump["nodes"]}
    node = nodes.get("АС.08")
    if node is None:
        raise InputError(f"node 'АС.08' missing; nodes {sorted(nodes)}")
    drops = [{"element": n, "reason": "UCX collision hull, not a render part (UCX lane)"}
             for n in nodes if n != "АС.08"]
    v = np.asarray(node["vertices"], dtype=float)
    faces = [tuple(int(i) for i in f) for f in node["faces"]]
    uvv, uvf = node["uv1"]["verts"], node["uv1"]["faces"]
    mats = list(node["mat_ids"])
    if not (len(faces) == len(uvf) == len(mats)) or any(len(a) != len(b) for a, b in zip(faces, uvf)):
        raise InputError("faces / uv1 faces / mat_ids do not line up")
    parent = list(range(len(v)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for f in faces:
        for a in f[1:]:
            parent[find(a)] = find(f[0])
    groups = defaultdict(list)
    for k, f in enumerate(faces):
        groups[find(f[0])].append(k)
    comps = sorted(groups.values(), key=lambda g: (-len(g), g[0]))
    if len(comps) != len(PART_NAMES):
        raise InputError(f"expected {len(PART_NAMES)} connected components, got {len(comps)}")
    unused = set(range(len(v))) - {i for f in faces for i in f}
    drops += [{"element": f"АС.08 vertex {i}", "reason": "unused by any face"} for i in sorted(unused)]
    scene = {}
    for name, ids in zip(PART_NAMES, comps):
        used = sorted({i for k in ids for i in faces[k]})
        remap = {o: n for n, o in enumerate(used)}
        scene[name] = {"v": v[used].copy(), "faces": tuple(tuple(remap[i] for i in faces[k]) for k in ids),
                       "uv": [[tuple(map(float, uvv[j])) for j in uvf[k]] for k in ids],
                       "mat": [int(mats[k]) for k in ids], "source_faces": list(ids)}
    return scene, drops


# ---- conversions -----------------------------------------------------------------------------------------------

def fan(faces):
    return np.array([(f[0], f[i], f[i + 1]) for f in faces for i in range(1, len(f) - 1)], dtype=int).reshape(-1, 3)


def tri_scene(state):
    return {k: Mesh(p["v"], fan(p["faces"])) for k, p in state.items()}


def poly_scene(state):
    return {k: PolyMesh(p["v"], tuple(p["faces"])) for k, p in state.items()}


def from_tri(mesh: Mesh, mat: int):
    """A triangle-mesh op result: polygons = triangles; the op generates no UV (recorded as lost)."""
    faces = tuple(tuple(int(i) for i in t) for t in mesh.triangles)
    return {"v": np.asarray(mesh.vertices, float).copy(), "faces": faces, "uv": [None] * len(faces),
            "mat": [mat] * len(faces)}


# ---- metrics ---------------------------------------------------------------------------------------------------

def _area(v, f):
    p = v[list(f)]
    return float(np.linalg.norm(np.cross(p, np.roll(p, -1, axis=0)).sum(axis=0)) / 2)


def _uv_area(c):
    c = np.asarray(c, float)
    return float(np.sum(c[:, 0] * np.roll(c[:, 1], -1) - np.roll(c[:, 0], -1) * c[:, 1]) / 2)


def part_metrics(name, p):
    v, faces = p["v"], p["faces"]
    edges = Counter(tuple(sorted(e)) for f in faces for e in zip(f, f[1:] + f[:1]))
    poly = PolyMesh(v, tuple(faces))
    q = quad_report({name: poly}, PROFILE)[name]
    x = ix.xview_report({name: poly}, PROFILE)[name]
    t = texel_report({name: TexelPolyMesh(v, tuple(faces))}, PROFILE)[name]
    topo = count_defects(v, [list(f) for f in faces])
    uv = p["uv"]
    with_uv = [c for c in uv if c is not None]
    lo, hi = v.min(0), v.max(0)
    return {
        "faces": len(faces), "vertices": len(v),
        "degrees": dict(sorted(Counter(str(len(f)) for f in faces).items())),
        "open_edges": sum(1 for c in edges.values() if c == 1),
        "nonmanifold_edges": sum(1 for c in edges.values() if c > 2),
        "zero_area_faces": sum(1 for f in faces if _area(v, f) <= ZERO_AREA_M2),
        "area_m2": float(sum(_area(v, f) for f in faces)),
        "edge_length_m": float(sum(np.linalg.norm(v[a] - v[b]) for a, b in edges)),   # tolerance scale only
        "bounds_m": [np.round(lo, 5).tolist(), np.round(hi, 5).tolist()],
        "topology": {k: topo[k] for k in sorted(topo) if k != "tol_m"},
        "quads": {"triangles": q.triangles, "quads": q.quads, "ngons": q.ngons,
                  "triangle_share": round(q.triangle_share, 6), "needed_share": round(q.needed_share, 6),
                  "share_max": q.share_max, "offenders": len(q.offenders)},
        "xview": {"vertex_pairs": len(x.vertex_pairs), "face_pairs": len(x.face_pairs)},
        "texel_offenders": len(t.offenders),
        "uv": {"faces_with_uv": len(with_uv), "faces_without_uv": len(uv) - len(with_uv),
               "zero_uv_area_faces": sum(1 for c in with_uv if abs(_uv_area(c)) <= 1e-12),
               "mirrored_uv_faces": sum(1 for c in with_uv if _uv_area(c) < -1e-12)},
        "materials": dict(sorted(Counter(str(m) for m in p["mat"]).items())),
    }


def scene_metrics(state, raw_bounds=False):
    """Per-part metrics; `raw_bounds` adds unrounded `bounds_raw_m` (parity only, never written to evidence)."""
    parts = {k: part_metrics(k, p) for k, p in state.items()}
    if raw_bounds:
        for k, p in state.items():
            parts[k]["bounds_raw_m"] = [p["v"].min(0).tolist(), p["v"].max(0).tolist()]
    names = list(state)
    joined = PolyMesh(np.concatenate([state[k]["v"] for k in names]),
                      tuple(tuple(i + off for i in f) for k, off in zip(names, np.cumsum(
                          [0] + [len(state[k]["v"]) for k in names[:-1]])) for f in state[k]["faces"]))
    owner = [k for k in names for _ in state[k]["faces"]]
    cross = [(a, b, kind) for a, b, kind, _ in ix.face_pairs(joined, ix.tolerance_for(PROFILE))
             if owner[a] != owner[b]]
    return {"parts": parts, "cross_part_xview_face_pairs": len(cross)}


def visibility(state, ctx):
    """Kernel visibility invariants on one state (count, passed): back faces, close overlap, hidden borders."""
    s = tri_scene(state)
    out = {r.name: {"passed": r.passed, "count": r.count} for r in
           (no_visible_back_faces(s, ctx), no_close_overlap(s, ctx=ctx))}
    for k in s:
        r = open_borders_hidden(s, k, ctx)
        out[f"{r.name}[{k}]"] = {"passed": r.passed, "count": r.count}
    return out


# ---- operations ------------------------------------------------------------------------------------------------

def copy_state(state):
    return {k: {**p, "v": p["v"].copy(), "uv": list(p["uv"]), "mat": list(p["mat"])} for k, p in state.items()}


def _nearest_face_normal(state, part, host):
    """Outward normal of the host polygon nearest to the part centroid (Newell, Max winding)."""
    c = state[part]["v"].mean(axis=0)
    hv, best = state[host]["v"], None
    for f in state[host]["faces"]:
        p = hv[list(f)]
        n = np.cross(p, np.roll(p, -1, axis=0)).sum(axis=0)
        n = n / np.linalg.norm(n)
        d = abs(float((c - p[0]) @ n)) + float(np.linalg.norm(c - p.mean(axis=0))) * 1e-3
        if best is None or d < best[0]:
            best = (d, n)
    return best[1]


def op_kernel(state, name, part, fn, ctx, params):
    """operations.py op: the kernel verdict from run_operation (it checks and rolls back) plus the CANDIDATE
    after-state from the same deterministic `fn`, so a rolled-back op still has measured AFTER numbers."""
    tri = tri_scene(state)
    res = run_operation(tri, name, part, fn, ctx, params)
    if res.report is None:                     # refused before any geometry changed
        return res, None
    fresh = tri_scene(state)
    candidate = fn(fresh)
    after = copy_state(state)
    if candidate[part] is not fresh[part]:     # the same object back (keep): the polygon state stays as it is
        after[part] = from_tri(candidate[part], state[part]["mat"][0])
    return res, after


def preservation(source, after):
    """[D201] UV/material preservation of a candidate state against the source: faces that had UV and lost it,
    merged material ids (0) and source material ids that vanished. Empty list = preserved."""
    why = []
    lost = sum(1 for p in after.values() for c in p["uv"] if c is None) - \
        sum(1 for p in source.values() for c in p["uv"] if c is None)
    if lost > 0:
        parts = sorted(k for k, p in after.items() if any(c is None for c in p["uv"]))
        why.append(f"UV lost on {lost} faces of {parts}")
    merged = {k: p["mat"].count(0) for k, p in after.items() if 0 in p["mat"]}
    if merged:
        why.append(f"material ids merged on polygons {merged}")
    gone = sorted({m for p in source.values() for m in p["mat"]} - {m for p in after.values() for m in p["mat"]})
    if gone:
        why.append(f"material ids {gone} vanished")
    return why


def run_ops(source, relative=False):
    """The #752 op set. `relative` [D201, #968]: invariants judged against the source (no new violators) and an
    op counts as applied only when it also preserves UV and material ids (`preservation`)."""
    ctx = Context(source=tri_scene(source)) if relative else Context()
    rows = []

    def record(op, part, params, applied, after, report, question, extra=None):
        """after = the candidate state (None when the op refused before changing geometry); `applied` = the
        kernel verdict (False = rolled back or refused)."""
        lost = preservation(source, after) if relative and after is not None else []
        if applied and lost:
            applied, question = False, f"{op} on {part}: invariants pass but not preserved: " + "; ".join(lost)
        rows.append({"op": op, "part": part, "params": params, "applied": bool(applied),
                     "refusal_or_rollback": question, "check_operation": None if report is None else report.to_dict(),
                     **({"preservation": lost} if relative else {}), "after_state": after, **(extra or {})})

    for part in PART_NAMES:
        s = copy_state(source)
        res, after = op_kernel(s, "keep", part, lambda sc, p=part: keep(sc, p), ctx, {})
        record("keep", part, {}, res.applied, after, res.report, res.question)
    for part in ("AC08_knob", "AC08_plate"):
        s = copy_state(source)
        res, after = op_kernel(s, "primitive_box", part, lambda sc, p=part: primitive_box(sc, p), ctx, {})
        record("primitive_box", part, {}, res.applied, after, res.report, res.question)
    for part in ("AC08_knob", "AC08_plate"):
        s = copy_state(source)
        n = _nearest_face_normal(s, part, "AC08_body")
        params = {"neighbour": "AC08_body", "direction": (-n).round(6).tolist(), "depth_m": 0.015,
                  "direction_rule": "minus the outward normal of the nearest body polygon"}
        res, after = op_kernel(s, "embed_into_neighbour", part,
                               lambda sc, p=part, d=-n: embed_into_neighbour(sc, p, "AC08_body", d, 0.015), ctx, params)
        record("embed_into_neighbour", part, params, res.applied, after, res.report, res.question)
    for part in ("AC08_plate", "AC08_knob"):
        s = copy_state(source)
        octx = replace(ctx, opacity_parts=frozenset({part}))
        res, after = op_kernel(s, "to_opacity_plane", part, lambda sc, p=part: to_opacity_plane(sc, p), octx, {})
        record("to_opacity_plane", part, {"opacity_parts": [part]}, res.applied, after, res.report, res.question)
    for part, view in (("AC08_knob", "front"), ("AC08_plate", "front")):
        s = copy_state(source)
        tri = tri_scene(s)
        res = rebuild_by_contour(tri, part, view=view, ctx=ctx)
        after = None
        if res.report is not None:             # candidate: the same private builder rebuild_by_contour wraps
            cand = _contour_rebuild(tri_scene(s), part, view, None, None, None, False, NumpyExtrude(),
                                    SILHOUETTE_MAX_M, {})
            after = copy_state(s)
            after[part] = from_tri(cand[part], s[part]["mat"][0])
        record("rebuild_by_contour", part, {"view": view}, res.applied, after, res.report, res.question,
               {"notes": {k: v for k, v in (res.notes or {}).items() if isinstance(v, (int, float, str))}})
    for pair in (("AC08_body", "AC08_plate"), ("AC08_knob", "AC08_plate"), ("AC08_body", "AC08_knob")):
        seam_op(source, "join_parts", pair, ctx, record)
    for part in PART_NAMES:
        seam_op(source, "simplify_part", (part,), ctx, record)
    for part in ("AC08_knob", "AC08_plate"):
        s = copy_state(source)
        n = _nearest_face_normal(s, part, "AC08_body")
        vec = n * 0.011
        params = {"seeds": [part], "fixed": ["AC08_body"], "vector_m": vec.round(6).tolist(),
                  "vector_rule": "11 mm along the outward normal of the nearest body polygon"}
        try:
            mv = move_rigid(poly_scene(s), [part], vec, fixed=["AC08_body"])
        except ValueError as why:
            record("move_rigid", part, params, False, None, None, f"move_rigid on {part}: {why}")
            continue
        after = copy_state(s)
        for k in mv.moved:
            after[k] = {**after[k], "v": np.asarray(mv.scene[k].vertices, float).copy()}
            if tuple(mv.scene[k].faces) != tuple(after[k]["faces"]):
                raise AssertionError(f"move_rigid changed faces of {k}")
        report = check_operation(tri_scene(s), tri_scene(after), list(mv.moved), ctx)
        record("move_rigid", part, params, report.passed, after, report,
               None if report.passed else "check_operation broke: " + "; ".join(r.name for r in report.broken),
               {"moved": list(mv.moved), "clearance_pairs_10mm": len(mv.clearance)})
    return rows


def _cap_uv(v, ring):
    """Generated planar UV of a cap, normalised to its own bounding box in [0, 1] (recorded as generated)."""
    p = np.asarray(v, float)[list(ring)]
    n = np.cross(p[1] - p[0], p[-1] - p[0])
    for k in range(len(p)):           # first non-collinear corner gives the plane normal
        n = np.cross(p[(k + 1) % len(p)] - p[k], p[k - 1] - p[k])
        if np.linalg.norm(n) > 1e-12:
            break
    n /= np.linalg.norm(n)
    u = p[1] - p[0]
    u /= np.linalg.norm(u)
    w = np.cross(n, u)
    q = np.stack([(p - p[0]) @ u, (p - p[0]) @ w], 1)
    lo, span = q.min(0), np.maximum(q.max(0) - q.min(0), 1e-12)
    return [tuple(float(x) for x in c) for c in (q - lo) / span]


def repair_flip_close(source):
    """`repair.flip_close` (#1144) on every part: flip polygons against their component's winding, cap the open
    border loops whose edges are ALL unhidden violators (open_borders_hidden, absolute). Flipped polygons keep their
    material id and their UV corners (permuted with the winding); a cap takes the one material id of the polygons
    on its loop (two ids on one loop = InputError naming the part and the ids, never a default) and a generated
    planar UV normalised to its bounding box. Returns (repaired state, record). The record holds the absolute
    violators before/after (the new [D201] baseline), the relative check against the source and `applied`:
    no new violators, UV and material ids of every source polygon kept, back-face px AND unhidden borders reduced."""
    from dt_ai.ops.invariants import _unhidden_edges
    from dt_ai.ops.repair import flip_close
    abs_ctx, tri = Context(), tri_scene(source)
    after, flipped, caps, skipped = copy_state(source), {}, {}, {}
    for k, p in source.items():
        unhidden = {tuple(sorted((tuple(np.round(e[0], 9)), tuple(np.round(e[1], 9)))))
                    for e in _unhidden_edges(tri, k, abs_ctx)}
        sel = {frozenset((a, b)) for f in p["faces"] for a, b in zip(f, f[1:] + f[:1])
               if tuple(sorted((tuple(np.round(p["v"][a], 9)), tuple(np.round(p["v"][b], 9))))) in unhidden}
        res = flip_close(PolyMesh(p["v"], tuple(p["faces"])), close=sel)
        flip = set(res.flipped)
        uv, mat = [], []
        for f, src in zip(res.mesh.faces, res.face_sources):
            if src is not None:
                c = p["uv"][src]
                uv.append(c if c is None or src not in flip else [c[0]] + list(c[1:])[::-1])
                mat.append(p["mat"][src])
                continue
            ring = {frozenset((f[j], f[(j + 1) % len(f)])) for j in range(len(f))}
            ids = sorted({p["mat"][i] for i, g in enumerate(p["faces"])
                          if ring & {frozenset((g[j], g[(j + 1) % len(g)])) for j in range(len(g))}})
            if len(ids) != 1:
                raise InputError(f"repair.flip_close {k}: cap loop of {len(f)} points borders material ids {ids}")
            uv.append(_cap_uv(p["v"], f))
            mat.append(ids[0])
        after[k] = {**after[k], "faces": tuple(map(tuple, res.mesh.faces)), "uv": uv, "mat": mat}
        flipped[k] = list(res.flipped)
        caps[k] = [{"points": len(ring), "material": after[k]["mat"][i],
                    "area_m2": float(_area(p["v"], ring))} for i, ring in res.caps]
        skipped[k] = [{"points": len(ring), "reason": why} for ring, why in res.skipped]
    vis_before, vis_after = visibility(source, abs_ctx), visibility(after, abs_ctx)

    def borders(vis):
        return sum(x["count"] for n, x in vis.items() if n.startswith("open_borders_hidden"))
    report = check_operation(tri, tri_scene(after), list(after), Context(source=tri))
    kept = preservation(source, after)
    for k, p in source.items():       # every source polygon: same material, same UV corners (flip-permuted)
        for i, f in enumerate(p["faces"]):
            g, c = after[k]["faces"][i], after[k]["uv"][i]
            if after[k]["mat"][i] != p["mat"][i] or set(g) != set(f) or \
                    (p["uv"][i] is not None and sorted(map(tuple, c)) != sorted(map(tuple, p["uv"][i]))):
                kept.append(f"{k} polygon {i}: material/UV/corners not kept")
    bf = (vis_before["no_visible_back_faces"]["count"], vis_after["no_visible_back_faces"]["count"])
    ob = (borders(vis_before), borders(vis_after))
    why = [] if report.passed else ["check_operation: " + "; ".join(r.name for r in report.broken)]
    why += kept
    if not (bf[1] < bf[0] and ob[1] < ob[0]):
        why.append(f"not reduced: back-face px {bf[0]}->{bf[1]}, unhidden borders {ob[0]}->{ob[1]}")
    record = {"op": "repair.flip_close", "applied": not why, "refusal_or_rollback": "; ".join(why) or None,
              "flipped": flipped, "caps": caps, "skipped": skipped, "back_face_px": list(bf),
              "open_borders_unhidden": list(ob), "visibility_before": vis_before, "visibility_after": vis_after,
              "cap_area_m2": float(sum(c["area_m2"] for cs in caps.values() for c in cs)),
              "check_operation": report.to_dict(), "cap_uv": "generated planar, normalised to the cap bbox"}
    return after, record


def uv_islands(p):
    """Per-face island id (#1144): faces joined across a shared edge only when both end corners carry the same UV
    (within UV_AGREE) in both faces; a face without UV is its own island. Used as a simplify barrier with the
    material id, so a dissolved polygon never spans a UV seam."""
    parent = list(range(len(p["faces"])))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    edge = defaultdict(list)
    for fi, (f, c) in enumerate(zip(p["faces"], p["uv"])):
        if c is None:
            continue
        for k in range(len(f)):
            a, b = f[k], f[(k + 1) % len(f)]
            edge[tuple(sorted((a, b)))].append((fi, {a: c[k], b: c[(k + 1) % len(f)]}))
    for items in edge.values():
        for (fa, ua), (fb, ub) in zip(items, items[1:]):
            if all(max(abs(float(x) - float(y)) for x, y in zip(ua[vi], ub[vi])) <= UV_AGREE for vi in ua):
                parent[find(fb)] = find(fa)
    return [find(i) for i in range(len(parent))]


def seam_op(source, op, parts, ctx, record):
    s = copy_state(source)
    try:
        if op == "join_parts":
            res = join_parts({k: PolyMesh(s[k]["v"], tuple(s[k]["faces"])) for k in parts})
        else:   # every part goes in: simplify conforms the neighbours' seams too; a dissolved polygon keeps one
            p = s[parts[0]]   # material id and one UV island (#1144)
            labels = tuple(zip(p["mat"], uv_islands(p)))
            res = simplify_part(poly_scene(s), parts[0], face_labels={parts[0]: labels})
    except (OperationRefused, ValueError) as why:
        record(op, "+".join(parts), {}, False, None, None, f"{op} on {'+'.join(parts)}: {type(why).__name__}: {why}")
        return
    after, unmapped, merged = carry_seam(s, res, parts if op == "join_parts" else tuple(s), op)
    report = check_operation(tri_scene(s), tri_scene(after), list(after), ctx)
    record(op, "+".join(parts), {}, report.passed, after, report,
           None if report.passed else "check_operation broke: " + "; ".join(r.name for r in report.broken),
           {"max_weld_m": float(res.max_weld_m), "dropped_vertices": len(res.dropped_vertices),
            "uv_corners_unmapped": unmapped, "material_merged_polygons": merged})


def carry_seam(state, res, consumed, op):
    """SeamResult -> state. join: the consumed parts become one part "a+b"; simplify: the result replaces all
    parts as one mesh named "simplified". UV/material carried per corner from the source polygon(s) of the output
    polygon (#1144): a corner takes the source UV of its vertex when EVERY source polygon of the group that has that
    vertex as a corner has UV there and all of them agree within UV_AGREE. A corner with no source corner, a source
    polygon without UV or disagreeing UVs (a UV seam inside a merged group) leaves the whole polygon without UV and
    all its corners are counted as unmapped: reported, never defaulted, never interpolated."""
    vsrc = res.vertex_sources
    unmapped, uv, mats = 0, [], []
    for f, srcs in zip(res.mesh.faces, res.face_sources):
        srcs = tuple(srcs)
        m = {state[p]["mat"][i] for p, i in srcs}
        mats.append(m.pop() if len(m) == 1 else 0)   # 0 = merged ids: reported, never defaulted
        corners = []
        for vi in f:
            origin = set(map(tuple, vsrc[vi]))
            found, missing = [], False
            for part, fi in srcs:
                src_face, src_uv = state[part]["faces"][fi], state[part]["uv"][fi]
                hit = [k for k, sv in enumerate(src_face) if (part, sv) in origin]
                missing |= bool(hit) and src_uv is None
                found += [tuple(map(float, src_uv[k])) for k in hit if src_uv is not None]
            agree = bool(found) and not missing and all(
                max(abs(a - b) for a, b in zip(c, found[0])) <= UV_AGREE for c in found)
            corners.append(found[0] if agree else None)
        if any(c is None for c in corners):
            unmapped += len(f)
            uv.append(None)
        else:
            uv.append(corners)
    name = "+".join(consumed) if op == "join_parts" else "simplified"
    after = {k: p for k, p in copy_state(state).items() if k not in consumed}
    after[name] = {"v": np.asarray(res.mesh.vertices, float).copy(), "faces": tuple(map(tuple, res.mesh.faces)),
                   "uv": uv, "mat": mats}
    return after, unmapped, mats.count(0)


# ---- export / readback -----------------------------------------------------------------------------------------

def export_payload(state):
    """What the FBX writer gets; UV is dropped for an object that lost it on some polygons (stated, not hidden)."""
    objs, notes = [], {}
    for k, p in state.items():
        has = [c is not None for c in p["uv"]]
        uv = p["uv"] if all(has) else [None] * len(has)
        if any(has) and not all(has):
            notes[k] = f"UV dropped for export: {has.count(False)} of {len(has)} polygons have no carried UV"
        objs.append({"name": k.replace("+", "_J_"), "vertices": np.asarray(p["v"]).tolist(),
                     "polygons": [list(f) for f in p["faces"]], "uv": uv, "material_ids": list(p["mat"])})
    return objs, notes


MATERIAL_SLOT = re.compile(r"ID_(\d{2})")


def _strict_number(x, what):
    """A finite JSON number; bool, str, None, containers and NaN/inf are errors naming the element."""
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        raise InputError(f"{what}: {x!r} is not a finite number")
    return float(x)


def _strict_index(x, what):
    """A JSON integer; bool (an int subclass), integral floats, str and None are errors, never int()-coerced."""
    if isinstance(x, bool) or not isinstance(x, int):
        raise InputError(f"{what}: {x!r} is not an integer index")
    return x


def _strict_list(x, what, min_len=0, exact=None):
    if not isinstance(x, list):
        raise InputError(f"{what}: {type(x).__name__} is not a list")
    if (exact is not None and len(x) != exact) or len(x) < min_len:
        raise InputError(f"{what}: {len(x)} entries, need {exact if exact is not None else f'>= {min_len}'}")
    return x


def state_from_readback(report):
    """Readback report -> state with per-polygon material ids; any missing, partial or unmapped field is an error."""
    if report.get("readback_ok") is not True:
        raise InputError(f"readback not ok: {report.get('error') or report.get('readback_ok')!r}")
    meshes = report.get("meshes") or []
    if not meshes:
        raise InputError("readback has no meshes")
    names = [m["name"] for m in meshes]
    dup = sorted(n for n, c in Counter(names).items() if c > 1)
    if dup:
        raise InputError(f"readback mesh names duplicated: {dup}")
    out = {}
    for m in meshes:
        n = m["name"]
        g = m.get("face_geometry")
        if not isinstance(g, dict):
            raise InputError(f"{n}: no face_geometry")
        verts = _strict_list(g.get("vertices"), f"{n}: vertices", min_len=1)
        v = np.array([[_strict_number(x, f"{n}: vertex {k} axis {a}") for a, x in
                       enumerate(_strict_list(p, f"{n}: vertex {k}", exact=3))] for k, p in enumerate(verts)], float)
        polys = tuple(tuple(_strict_index(i, f"{n}: polygon {k} corner {c}") for c, i in
                            enumerate(_strict_list(p, f"{n}: polygon {k}", min_len=3)))
                      for k, p in enumerate(_strict_list(g.get("polygons"), f"{n}: polygons", min_len=1)))
        for k, p in enumerate(polys):
            for c, i in enumerate(p):
                if i < 0 or i >= len(v):
                    raise InputError(f"{n}: polygon {k} corner {c}: vertex index {i} out of range 0..{len(v) - 1}")
        pm = g.get("polygon_material")
        if not isinstance(pm, list) or len(pm) != len(polys):
            raise InputError(f"{n}: per-polygon materials {len(pm) if isinstance(pm, list) else pm!r} "
                             f"for {len(polys)} polygons")
        mats = []
        for i, name in enumerate(pm):
            hit = MATERIAL_SLOT.fullmatch(name) if isinstance(name, str) else None
            if hit is None or int(hit.group(1)) < 1:
                raise InputError(f"{m['name']}: polygon {i} material {name!r} is not an ID_nn slot")
            mats.append(int(hit.group(1)))
        puv = g.get("polygon_uv")
        if puv is not None:
            _strict_list(puv, f"{n}: polygon_uv", exact=len(polys))
            puv = [[tuple(_strict_number(x, f"{n}: polygon {k} uv corner {c} axis {a}") for a, x in
                          enumerate(_strict_list(uv, f"{n}: polygon {k} uv corner {c}", exact=2)))
                    for c, uv in enumerate(_strict_list(cs, f"{n}: polygon {k} uv", exact=len(polys[k])))]
                   for k, cs in enumerate(puv)]
        out[m["name"].replace("_J_", "+")] = {
            "v": v, "faces": polys,
            "uv": [None] * len(polys) if puv is None else puv,
            "mat": mats, "material_slots": len(m["materials"])}
    return out


def rounded(state):
    """In-memory state at the readback precision (6 decimals) so both sides see the same coordinates."""
    return {k: {**p, "v": np.round(p["v"], 6),
                "uv": [None if c is None else [tuple(round(x, 6) for x in uv) for uv in c] for c in p["uv"]]}
            for k, p in state.items()}


COMPARE_KEYS = ("faces", "vertices", "degrees", "open_edges", "nonmanifold_edges", "zero_area_faces", "area_m2",
                "bounds_m", "topology", "quads", "xview", "texel_offenders", "uv", "materials")


VERTEX_TOL_M = 1e-5    # declared: Blender stores float32 coordinates (spacing 3.8e-6 m at 37 m) + 1e-6 rounding
# A vertex moved by <= VERTEX_TOL_M changes a polygon area by <= (its perimeter) x VERTEX_TOL_M, so the part's
# area tolerance is (sum of its edge lengths) x VERTEX_TOL_M.


def parity(mem: dict, back: dict, mem_state=None, rb_state=None):
    """Strict equality per metric; `equal_within_tol` differs only for area_m2 (relative AREA_REL_TOL)."""
    rows = []
    for part in sorted(set(mem["parts"]) | set(back["parts"])):
        a, b = mem["parts"].get(part), back["parts"].get(part)
        for key in COMPARE_KEYS:
            va, vb = (None if a is None else a[key]), (None if b is None else b[key])
            tol = va == vb
            if key == "bounds_m" and va is not None and vb is not None:
                ra, rb = a.get("bounds_raw_m"), b.get("bounds_raw_m")
                if ra is not None and rb is not None:       # unrounded bounds: per coordinate <= VERTEX_TOL_M
                    tol = (np.shape(ra) == np.shape(rb) and bool(np.all(np.isfinite(ra))) and bool(np.all(np.isfinite(rb)))
                           and bool(np.all(np.abs(np.asarray(ra, float) - np.asarray(rb, float)) <= VERTEX_TOL_M)))
                else:                                       # raw bounds missing: strict equality, never a widened tolerance
                    tol = va == vb
            if key == "area_m2" and va is not None and vb is not None:
                tol = abs(va - vb) <= VERTEX_TOL_M * max(a["edge_length_m"], b["edge_length_m"])
            rows.append({"part": part, "metric": key, "in_memory": va, "readback": vb, "equal": va == vb,
                         "equal_within_tol": bool(tol)})
        if mem_state is not None and part in mem_state and part in rb_state:
            ms, rs = mem_state[part], rb_state[part]
            same = ms["faces"] == rs["faces"] and len(ms["v"]) == len(rs["v"])
            dev = float(np.abs(ms["v"] - rs["v"]).max()) if same else None
            uvd = None
            if same and all(c is not None for c in ms["uv"]) and all(c is not None for c in rs["uv"]):
                uvd = max((abs(x - y) for c, d in zip(ms["uv"], rs["uv"]) for p, q in zip(c, d)
                           for x, y in zip(p, q)), default=0.0)
            slots = max(ms["mat"]) if ms["mat"] else 0
            mat_diff = sum(x != y for x, y in zip(ms["mat"], rs["mat"])) if same else None
            mem_uv = any(c is not None for c in ms["uv"])
            uv_ref = 0.0 if mem_uv else None
            for key, va, vb, ok in (("same_polygon_index_lists", True, same, same),
                                    ("vertex_max_abs_dev_m", 0.0, dev, dev is not None and dev <= VERTEX_TOL_M),
                                    ("uv_max_abs_dev", uv_ref, uvd, (uvd is None and not mem_uv)
                                     or (uvd is not None and uvd <= 1e-6)),
                                    ("polygon_material_ids", 0, mat_diff, mat_diff == 0),
                                    ("material_slots", slots, rs["material_slots"], slots == rs["material_slots"])):
                rows.append({"part": part, "metric": key, "in_memory": va, "readback": vb, "equal": va == vb,
                             "equal_within_tol": bool(ok)})
    rows.append({"part": "*", "metric": "cross_part_xview_face_pairs", "in_memory": mem["cross_part_xview_face_pairs"],
                 "readback": back["cross_part_xview_face_pairs"],
                 "equal": mem["cross_part_xview_face_pairs"] == back["cross_part_xview_face_pairs"],
                 "equal_within_tol": mem["cross_part_xview_face_pairs"] == back["cross_part_xview_face_pairs"]})
    return rows


def readback_metrics(rb_state):
    m = scene_metrics(rb_state, raw_bounds=True)
    for k, p in rb_state.items():
        m["parts"][k]["material_slots"] = p["material_slots"]
    return m


def export_state(state):
    """The candidate as the FBX writer receives it (UV of a partially mapped object dropped, see export_payload)."""
    return {k: {**p, "uv": p["uv"] if all(c is not None for c in p["uv"]) else [None] * len(p["uv"])}
            for k, p in state.items()}


def compare_state(candidate, report):
    """Readback vs the ACTUAL candidate (accepted only if every row is within tol and no UV was lost on export),
    plus payload -> readback fidelity (what the writer got vs what came back) kept separate."""
    cand = rounded(candidate)
    exp = rounded(export_state(candidate))
    rb = state_from_readback(report)
    back = readback_metrics(rb)
    cp = parity(scene_metrics(cand, raw_bounds=True), back, cand, rb)
    pp = parity(scene_metrics(exp, raw_bounds=True), back, exp, rb)
    loss = {k: sum(c is not None for c in p["uv"]) for k, p in candidate.items()
            if any(c is not None for c in p["uv"]) and not all(c is not None for c in p["uv"])}
    return {"candidate_parity": cp, "payload_parity": pp, "export_uv_loss": loss, "back": back,
            "accepted": not loss and all(r["equal_within_tol"] for r in cp)}


# ---- main ------------------------------------------------------------------------------------------------------

def _require_new(*paths):
    for p in paths:
        if p.exists():
            raise InputError(f"{p} exists; write a new versioned output")
    resolved = [p.resolve() for p in paths] + [SOURCE.resolve()]
    if len(set(resolved)) != len(resolved):
        raise InputError("output paths alias each other or the input")


def run(work: Path, evidence: Path, blender: bool = True):
    src_before = sha256(SOURCE)
    source, drops = load_source()
    out_json, out_md = evidence / "kernel_ops.json", evidence / "kernel_ops.md"
    _require_new(work, out_json, out_md)
    work.mkdir(parents=True)
    evidence.mkdir(parents=True, exist_ok=True)
    ctx = Context()
    before = scene_metrics(source)
    rows = run_ops(source)
    states = {"S00_source": source}
    for k, r in enumerate(rows, 1):
        state = r.pop("after_state")
        r["label"] = f"S{k:02d}_{r['op']}_{r['part'].replace('+', '_')}"
        r["candidate_measured"] = state is not None
        if state is not None:
            r["after"] = scene_metrics(state)
            r["after_visibility"] = visibility(state, ctx)
            states[r["label"]] = state       # candidate states are exported too (applied or rolled back)
    payload, payload_notes = {}, {}
    not_exported = {}
    for label, st in list(states.items()):
        merged = {k: p["mat"].count(0) for k, p in st.items() if 0 in p["mat"]}
        if merged:
            not_exported[label] = (f"not exported: polygons merge different material ids {merged}; "
                                   "no material id may be defaulted")
            continue
        payload[label], payload_notes[label] = export_payload(st)
    result = {"issue": 752, "source": {"path": SOURCE.relative_to(ROOT).as_posix(), "sha256": src_before},
              "profile": PROFILE, "parts": {k: {"faces": len(p["faces"]), "vertices": len(p["v"]),
                                                "source_faces": p["source_faces"]} for k, p in source.items()},
              "drops": drops, "before": before, "before_visibility": visibility(source, ctx), "ops": rows,
              "native_max_xview_parity": {"status": "not_run",
                                          "reason": "tools/qa/xview_parity.py needs a 3ds Max session; this card "
                                                    "launches no 3ds Max (Max-lock / max_exec rules)"},
              "not_exported": not_exported}
    if blender:
        from dt_ai.core.blender_runner import run_blender
        states_json = work / "states.json"
        states_json.write_text(json.dumps(payload), encoding="utf-8")
        fbx_dir = work / "fbx"
        run_blender(EXPORT, [states_json, fbx_dir], outputs=[fbx_dir / f"{k}.fbx" for k in payload],
                    log_path=work / "export.log", timeout=600)
        result["readback"] = {label: {"status": "not_exported", "reason": why} for label, why in not_exported.items()}
        for label in payload:
            fbx, rep = fbx_dir / f"{label}.fbx", work / "readback" / f"{label}.json"
            rep.parent.mkdir(exist_ok=True)
            report = run_blender(READBACK, [fbx, rep], output_json=rep, log_path=work / f"readback_{label}.log",
                                 timeout=600)
            c = compare_state(states[label], report)
            rows_p, back = c["candidate_parity"], c["back"]
            result["readback"][label] = {
                "fbx": fbx.as_posix(), "fbx_sha256": sha256(fbx), "export_notes": payload_notes[label],
                "readback_ok": report["readback_ok"], "blender": report["blender"],
                "material_slots": {k: v.get("material_slots") for k, v in back["parts"].items()},
                "accepted": c["accepted"], "export_uv_loss": c["export_uv_loss"],
                "parity": rows_p, "all_equal": all(r["equal"] for r in rows_p),
                "all_equal_within_tol": all(r["equal_within_tol"] for r in rows_p),
                "payload_parity": c["payload_parity"],
                "payload_all_equal_within_tol": all(r["equal_within_tol"] for r in c["payload_parity"])}
    if sha256(SOURCE) != src_before:
        raise InputError("the source changed during the run")
    result["source"]["sha256_after"] = sha256(SOURCE)
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    out_md.write_text(markdown(result), encoding="utf-8")
    return result


def _short(p):
    q = p["quads"]
    return (f"{p['faces']}f/{p['vertices']}v open {p['open_edges']} nm {p['nonmanifold_edges']} "
            f"zero {p['zero_area_faces']} tri {q['triangles']}/quad {q['quads']} qoff {q['offenders']} "
            f"xv {p['xview']['vertex_pairs']}/{p['xview']['face_pairs']} tex {p['texel_offenders']} "
            f"uv {p['uv']['faces_with_uv']}/{p['faces']}")


def markdown(r):
    lines = [f"# AC08 kernel ops (#752) - generated by run_kernel_ops.py", "",
             f"Source `{r['source']['path']}` sha256 `{r['source']['sha256']}`; profile {r['profile']}.", "",
             "Cell format: faces/vertices, open edges, non-manifold edges, zero-area faces, triangles/quads, "
             "quad offenders, xView vertex/face pairs, texel offenders, faces with UV/faces.", "",
             "## Before (source)", "", "| part | metrics |", "|---|---|"]
    lines += [f"| {k} | {_short(p)} |" for k, p in r["before"]["parts"].items()]
    lines += ["", f"Cross-part xView face pairs: {r['before']['cross_part_xview_face_pairs']}.", "",
              "## Operations", "", "| # | op | part | applied | check_operation | after (changed parts) | refusal |",
              "|---|---|---|---|---|---|---|"]
    for k, o in enumerate(r["ops"], 1):
        co = o["check_operation"]
        cos = "-" if co is None else ("pass" if co["passed"] else "FAIL ") + ", ".join(
            f"{x['name']}={x['count']}" for x in co["results"] if not x["passed"])
        aft = "-"
        if o.get("after"):
            names = [n for n in o["after"]["parts"] if n not in r["before"]["parts"]
                     or o["after"]["parts"][n] != r["before"]["parts"][n]]
            aft = "<br>".join(f"{n}: {_short(o['after']['parts'][n])}" for n in names) or "unchanged"
        why = (o["refusal_or_rollback"] or "").replace("|", "/")[:160]
        lines.append(f"| {k} | {o['op']} | {o['part']} | {o['applied']} | {cos} | {aft} | {why} |")
    lines += ["", "## Visibility invariants, source -> candidate after-state", "",
              "Kernel check (invariants.py) on the whole scene; ground_z unset (no ground surface in the source).", "",
              "| # | op | part | back-face pixels | close overlaps | open borders not hidden |", "|---|---|---|---|---|---|"]
    bv = r["before_visibility"]
    b_open = sum(x["count"] for k, x in bv.items() if k.startswith("open_borders_hidden"))
    for k, o in enumerate(r["ops"], 1):
        av = o.get("after_visibility")
        if av is None:
            lines.append(f"| {k} | {o['op']} | {o['part']} | not measured: refused before any geometry change | - | - |")
            continue
        a_open = sum(x["count"] for n, x in av.items() if n.startswith("open_borders_hidden"))
        lines.append(f"| {k} | {o['op']} | {o['part']} | {bv['no_visible_back_faces']['count']} -> "
                     f"{av['no_visible_back_faces']['count']} | {bv['no_close_overlap']['count']} -> "
                     f"{av['no_close_overlap']['count']} | {b_open} -> {a_open} |")
    if "readback" in r:
        lines += ["", "## FBX readback parity (in-memory at 1e-6 m vs readback)", "",
                  f"Strict equality; `tol` = within the declared float32 storage tolerance: vertices <= "
                  f"{VERTEX_TOL_M} m, area <= sum(edge lengths) x {VERTEX_TOL_M} m, bounds_m per coordinate <= {VERTEX_TOL_M} m (unrounded), UV <= 1e-6; every other "
                  "metric strictly; per-polygon material ids compared polygon by polygon. Candidate = the op's "
                  "actual after-state; payload = what the FBX writer received (UV of a partially mapped object "
                  "is dropped: the writer has no missing-UV representation, so that state is NOT accepted).", "",
                  "| state | accepted | candidate rows | strictly equal | within tol | failing (not within tol) "
                  "| strictly unequal only | export UV loss (faces) | payload->readback within tol |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for label, rb in r["readback"].items():
            if rb.get("status") == "not_exported":
                lines.append(f"| {label} | FAIL | 0 | 0 | 0 | {rb['reason']} | - | - | - |")
                continue
            neq = [f"{x['part']}.{x['metric']}" for x in rb["parity"] if not x["equal"] and x["equal_within_tol"]]
            bad = [f"{x['part']}.{x['metric']}" for x in rb["parity"] if not x["equal_within_tol"]]
            eq = sum(x["equal"] for x in rb["parity"])
            tol = sum(x["equal_within_tol"] for x in rb["parity"])
            pp = rb["payload_parity"]
            lines.append(f"| {label} | {'yes' if rb['accepted'] else 'FAIL'} | {len(rb['parity'])} | {eq} | {tol} | "
                         f"{', '.join(bad) or '-'} | {', '.join(neq) or '-'} | "
                         f"{', '.join(f'{k}: {n}' for k, n in rb['export_uv_loss'].items()) or '0'} | "
                         f"{sum(x['equal_within_tol'] for x in pp)}/{len(pp)} |")
    lines += ["", f"Native Max xView parity: {r['native_max_xview_parity']['status']} - "
              f"{r['native_max_xview_parity']['reason']}.", ""]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--work", required=True, type=Path)
    ap.add_argument("--evidence", type=Path, default=HERE / "evidence")
    ap.add_argument("--no-blender", action="store_true")
    a = ap.parse_args(argv)
    try:
        r = run(a.work, a.evidence, not a.no_blender)
    except InputError as why:
        print(f"ERROR: {why}", file=sys.stderr)
        return 1
    rb = r.get("readback", {})
    print(json.dumps({"ops": len(r["ops"]), "applied": sum(o["applied"] for o in r["ops"]),
                      "readback_states": len(rb), "not_exported": sum("status" in v for v in rb.values()),
                      "readback_accepted": sum(bool(v.get("accepted")) for v in rb.values()),
                      "readback_all_equal": sum(bool(v.get("all_equal")) for v in rb.values()),
                      "readback_all_equal_within_tol": sum(bool(v.get("all_equal_within_tol")) for v in rb.values())}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
