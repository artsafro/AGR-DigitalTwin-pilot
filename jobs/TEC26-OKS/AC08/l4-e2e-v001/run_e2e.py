"""AC08 (TEC26) L4 end to end through the kernel from a SOURCE FBX (#753).

    uv run python jobs/TEC26-OKS/AC08/l4-e2e-v001/run_e2e.py --source-fbx <AC08_source_geomfinal.fbx> \
        --delivered-fbx <pilot-v010 package-vpm/SM_Nku_1/SM_Nku_1.fbx> --work C:/x/ev_<card>/e2e-v001 \
        [--evidence jobs/TEC26-OKS/AC08/l4-e2e-v001/evidence]

Chain: source FBX (exported by 3dsmaxbatch from a COPY of "04-09 Geometry Final.max", nodes "АС.08" +
"Colizii_044") -> Blender readback -> parity against the hash-pinned Max dump `max-dump-008.json` (same node:
vertex positions per polygon corner, UV, material ids; the FBX material NAME -> Max material id map is derived from
that parity and must be one-to-one) -> the #752 kernel op table (run_kernel_ops.run_ops: invariants before and after
every op) -> FBX export of every candidate state -> readback parity -> kernel output (source + the ops the kernel
accepted) compared with the delivered pilot-v010 VPM FBX: vertex-to-surface distance both ways, area, bounds,
UCX hull and orthographic silhouettes (5 views, IoU) -> gate table.

Gates fail closed: an unknown mesh, an unmapped or ambiguous material, a missing polygon, NaN/inf, an empty mesh or
a tolerance breach is a failure naming the item; never a default. Outputs must be new paths, and no output may alias
an input. Nothing writes or deletes an input. The album (slide 49) and SINTEZ gates are measured by their own job
scripts (compare_facades.py, run_agr_checker.py) and recorded in REPORT.md.
`--invariants relative` (default, [D201], #968): the kernel judges every op against the source baseline (no new
violators) plus UV/material preservation; the source's own violations are the recorded baseline gate, not a failure.
`--invariants absolute` reproduces the #753 run.
Pattern: none | new-case: job-local AC08 L4 source-FBX -> kernel -> delivered-FBX comparison driver (#753).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RKO_PATH = HERE.parent / "kernel-ops-v001" / "run_kernel_ops.py"
_spec = importlib.util.spec_from_file_location("ac08_run_kernel_ops", RKO_PATH)
rko = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = rko
_spec.loader.exec_module(rko)

from dt_ai.ops.invariants import Context, Mesh, distance_to_surface  # noqa: E402

InputError = rko.InputError
BODY_NODE = "АС.08"
UCX_NODE = "Colizii_044"
DELIVERED_BODY = "SM_Nku_1_Main"
DELIVERED_UCX = "UCX_SM_Nku_1_Main_001"
SOURCE_DEV_TOL_M = 1e-5          # FBX float32 storage, as run_kernel_ops.VERTEX_TOL_M
UV_TOL = 1e-5
DELIVERED_DIST_TOL_M = 1e-3      # kernel output vs delivered: surfaces coincide within 1 mm
SILHOUETTE_IOU_MIN = 0.995
SILHOUETTE_PX_PER_M = 100.0
VIEWS = {"north_-y": (0, 2, 1, -1), "south_+y": (0, 2, 1, 1), "west_-x": (1, 2, 0, -1), "east_+x": (1, 2, 0, 1),
         "top_+z": (0, 1, 2, 1)}


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _finite(arr, what):
    a = np.asarray(arr, dtype=float)
    if a.size == 0:
        raise InputError(f"{what}: empty")
    if not np.all(np.isfinite(a)):
        raise InputError(f"{what}: NaN or inf")
    return a


def _meshes(report, expected, what):
    if report.get("readback_ok") is not True:
        raise InputError(f"{what}: readback not ok: {report.get('error')!r}")
    got = {m["name"]: m for m in report.get("meshes") or []}
    if len(got) != len(report.get("meshes") or []):
        raise InputError(f"{what}: duplicated mesh names")
    if set(got) != set(expected):
        raise InputError(f"{what}: meshes {sorted(got)} != expected {sorted(expected)}")
    for n, m in got.items():
        g = m.get("face_geometry")
        if not isinstance(g, dict) or not g.get("polygons"):
            raise InputError(f"{what}: mesh {n!r} has no polygons")
        _finite(g.get("vertices") or [], f"{what}: mesh {n!r} vertices")
    return got


def _dump_node():
    dump = json.loads(rko.SOURCE.read_text(encoding="utf-8"))
    nodes = {n["name"]: n for n in dump["nodes"]}
    return nodes[BODY_NODE], nodes[UCX_NODE]


def source_parity(report):
    """FBX readback of the source vs the pinned Max dump: per polygon corner positions, UV and material ids.

    Returns (rows, material name -> id map). Polygons must come in the dump order; corners may be rotated."""
    if rko.sha256(rko.SOURCE) != rko.SOURCE_SHA256:
        raise InputError(f"{rko.SOURCE}: sha256 differs from the pinned {rko.SOURCE_SHA256}")
    m = _meshes(report, {BODY_NODE, UCX_NODE}, "source FBX")
    node, ucx = _dump_node()
    g = m[BODY_NODE]["face_geometry"]
    fv = _finite(g["vertices"], "source vertices")
    polys = [tuple(int(i) for i in p) for p in g["polygons"]]
    dv = np.asarray(node["vertices"], float)
    dfaces = [tuple(int(i) for i in f) for f in node["faces"]]
    if len(polys) != len(dfaces):
        raise InputError(f"source FBX {BODY_NODE}: {len(polys)} polygons, dump {len(dfaces)}")
    pm, puv = g.get("polygon_material"), g.get("polygon_uv")
    if not isinstance(pm, list) or len(pm) != len(polys):
        raise InputError(f"source FBX {BODY_NODE}: per-polygon materials missing or partial")
    if not isinstance(puv, list) or len(puv) != len(polys):
        raise InputError(f"source FBX {BODY_NODE}: per-polygon UV missing or partial")
    uvv, uvf = node["uv1"]["verts"], node["uv1"]["faces"]
    worst_v, worst_uv, rotated, bad = 0.0, 0.0, 0, []
    name_to_ids = defaultdict(set)
    for k, (p, f) in enumerate(zip(polys, dfaces)):
        if len(p) != len(f):
            bad.append(f"polygon {k}: degree {len(p)} != dump {len(f)}")
            continue
        a, b = fv[list(p)], dv[list(f)]
        best = min(range(len(p)), key=lambda r: float(np.abs(np.roll(a, -r, 0) - b).max()))
        dev = float(np.abs(np.roll(a, -best, 0) - b).max())
        rotated += best != 0
        worst_v = max(worst_v, dev)
        if not dev < SOURCE_DEV_TOL_M:  # at-threshold and NaN fail
            bad.append(f"polygon {k}: corner deviation {dev:.3g} m")
        fu = np.roll(_finite(puv[k], f"source uv polygon {k}"), -best, 0)
        du = np.asarray([uvv[j][:2] for j in uvf[k]], float)
        uvd = float(np.abs(fu - du).max())
        worst_uv = max(worst_uv, uvd)
        if not uvd < UV_TOL:
            bad.append(f"polygon {k}: uv deviation {uvd:.3g}")
        if not isinstance(pm[k], str):
            bad.append(f"polygon {k}: no material")
            continue
        name_to_ids[pm[k]].add(int(node["mat_ids"][k]))
    ambiguous = {n: sorted(i) for n, i in name_to_ids.items() if len(i) != 1}
    mat_map = {n: next(iter(i)) for n, i in name_to_ids.items() if len(i) == 1}
    clash = sorted(i for i in set(mat_map.values()) if list(mat_map.values()).count(i) > 1)
    if ambiguous:
        bad.append(f"material names map to several ids: {ambiguous}")
    if clash:
        bad.append(f"several material names map to one id: {clash}")
    multisub = {e["name"]: int(e["id"]) for e in node.get("multisub") or [] if e.get("name")}
    off_map = {n: (i, multisub.get(n)) for n, i in mat_map.items() if multisub.get(n) != i}
    if off_map:
        bad.append(f"material name -> id differs from the dump multisub: {off_map}")
    uc = m[UCX_NODE]["face_geometry"]
    ucx_dev = _set_dev(_finite(uc["vertices"], "source UCX"), np.asarray(ucx["vertices"], float))
    if not ucx_dev < SOURCE_DEV_TOL_M:  # at-threshold and NaN fail
        bad.append(f"UCX vertex set deviation {ucx_dev:.3g} m")
    rows = {"polygons": len(polys), "dump_polygons": len(dfaces), "vertices": len(fv), "dump_vertices": len(dv),
            "max_corner_dev_m": worst_v, "max_uv_dev": worst_uv, "corner_rotated_polygons": rotated,
            "ucx_vertex_set_dev_m": ucx_dev, "material_map": mat_map, "failures": bad, "passed": not bad}
    if bad:
        raise InputError("source FBX != pinned dump: " + "; ".join(bad[:8]))
    return rows, mat_map


def _set_dev(a, b):
    """Symmetric max nearest-vertex distance between two vertex sets."""
    d = np.linalg.norm(a[:, None, :] - b[None, :, :], axis=2)
    return float(max(d.min(1).max(), d.min(0).max()))


def state_from_source(report, mat_map):
    """Body polygons -> #752 parts (connected components by descending face count), FBX coordinates and UV."""
    g = _meshes(report, {BODY_NODE, UCX_NODE}, "source FBX")[BODY_NODE]["face_geometry"]
    v = np.asarray(g["vertices"], float)
    faces = [tuple(int(i) for i in p) for p in g["polygons"]]
    mats = []
    for k, n in enumerate(g["polygon_material"]):
        if n not in mat_map:
            raise InputError(f"source polygon {k}: material {n!r} unmapped")
        mats.append(mat_map[n])
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
    comps = sorted(groups.values(), key=lambda q: (-len(q), q[0]))
    if len(comps) != len(rko.PART_NAMES):
        raise InputError(f"expected {len(rko.PART_NAMES)} connected components, got {len(comps)}")
    unused = set(range(len(v))) - {i for f in faces for i in f}
    drops = [{"element": UCX_NODE, "reason": "UCX collision hull, not a render part (compared separately)"}]
    drops += [{"element": f"{BODY_NODE} vertex {i}", "reason": "unused by any face"} for i in sorted(unused)]
    state = {}
    for name, ids in zip(rko.PART_NAMES, comps):
        used = sorted({i for k in ids for i in faces[k]})
        remap = {o: n for n, o in enumerate(used)}
        state[name] = {"v": v[used].copy(), "faces": tuple(tuple(remap[i] for i in faces[k]) for k in ids),
                       "uv": [[tuple(map(float, c)) for c in g["polygon_uv"][k]] for k in ids],
                       "mat": [mats[k] for k in ids], "source_faces": list(ids)}
    return state, drops


def _norm(x):
    if isinstance(x, np.ndarray):
        return ("nd", x.shape, x.tolist())
    if isinstance(x, (list, tuple)):
        return [_norm(i) for i in x]
    if isinstance(x, dict):
        return {k: _norm(v) for k, v in sorted(x.items())}
    return x


def _part_equal(a, b):
    return _norm(a) == _norm(b)


def op_footprint(source, after):
    """Keys an op touched: changed (in both, differ), added (only in after), removed (only in source)."""
    changed = {k for k in source.keys() & after.keys() if not _part_equal(source[k], after[k])}
    return changed, set(after) - set(source), set(source) - set(after)


def kernel_output(source, rows, conflicts: list | None = None):
    """Source + every op the kernel APPLIED. Each op ran on a fresh copy of the source, so its footprint
    (changed, added and removed keys of its after_state vs the source) is applied; overlapping footprints
    of two applied ops are an error naming both. `conflicts` a list [D201 run, #968]: the ops are alternatives on
    one source, so a later applied op whose footprint overlaps an earlier composed one is NOT composed and is
    appended there ({op, conflicts_with, part}) instead of raising; the op order of the #752 table decides."""
    out = rko.copy_state(source)
    applied = [r for r in rows if r.get("applied")]
    owner, composed = {}, []
    for r in applied:
        name = f"{r['op']}:{r['part']}"
        st = r.get("after_state")
        if not isinstance(st, dict):
            raise InputError(f"applied op {name} has no after_state")
        changed, added, removed = op_footprint(source, st)
        keys = sorted(changed | added | removed)
        clash = [k for k in keys if k in owner]
        if clash and conflicts is None:
            raise InputError(f"two applied ops touch part {clash[0]!r}: {owner[clash[0]]} and {name}")
        if clash:
            conflicts.append({"op": name, "conflicts_with": owner[clash[0]], "part": clash[0]})
            continue
        for key in keys:
            owner[key] = name
        for key in removed:
            out.pop(key, None)
        for key in changed | added:
            out[key] = rko.copy_state({key: st[key]})[key]
        composed.append(name)
    return out, composed


def _tri(v, polys):
    return np.array([(p[0], p[i], p[i + 1]) for p in polys for i in range(1, len(p) - 1)], int).reshape(-1, 3)


def _area(v, t):
    return float(0.5 * np.linalg.norm(np.cross(v[t[:, 1]] - v[t[:, 0]], v[t[:, 2]] - v[t[:, 0]]), axis=1).sum())


def silhouette(v, t, view, lo, hi):
    from PIL import Image, ImageDraw
    a, b, _, _ = VIEWS[view]
    w = max(1, int(math.ceil((hi[a] - lo[a]) * SILHOUETTE_PX_PER_M)) + 2)
    h = max(1, int(math.ceil((hi[b] - lo[b]) * SILHOUETTE_PX_PER_M)) + 2)
    img = Image.new("1", (w, h), 0)
    d = ImageDraw.Draw(img)
    for tri in t:
        pts = [((v[i, a] - lo[a]) * SILHOUETTE_PX_PER_M + 1, h - 1 - (v[i, b] - lo[b]) * SILHOUETTE_PX_PER_M)
               for i in tri]
        d.polygon(pts, fill=1)
    return np.asarray(img, bool), img


def pivot_offset(meta_path: Path):
    """The delivered package moved the plan centre to the origin (export_vpm.py); its export_meta.json records it
    as `pivot_revit_internal_m` (x, y, 0). offset = -pivot; anything else is an error."""
    meta = json.loads(Path(meta_path).read_text(encoding="utf-8"))
    piv = meta.get("pivot_revit_internal_m")
    if not isinstance(piv, list) or len(piv) != 3:
        raise InputError(f"{meta_path}: pivot_revit_internal_m {piv!r} is not an [x, y, z] list")
    return -_finite(piv, "pivot_revit_internal_m")


def compare_delivered(out_state, src_report, delivered_report, png_dir: Path | None, offset=None):
    """Kernel output moved by `offset` (the declared pivot rebase) vs the delivered FBX."""
    offset = np.zeros(3) if offset is None else _finite(offset, "offset")
    m = _meshes(delivered_report, {DELIVERED_BODY, DELIVERED_UCX}, "delivered FBX")
    g = m[DELIVERED_BODY]["face_geometry"]
    dv = _finite(g["vertices"], "delivered vertices")
    dt = _tri(dv, g["polygons"])
    kv = np.vstack([p["v"] for p in out_state.values()]) + offset
    off, kts = 0, []
    for p in out_state.values():
        kts.append(_tri(p["v"], p["faces"]) + off)
        off += len(p["v"])
    kt = np.vstack(kts)
    d_kd = distance_to_surface(kv, Mesh(dv, dt))
    d_dk = distance_to_surface(dv, Mesh(kv, kt))
    lo = np.minimum(kv.min(0), dv.min(0))
    hi = np.maximum(kv.max(0), dv.max(0))
    views = {}
    for view in VIEWS:
        ka, kimg = silhouette(kv, kt, view, lo, hi)
        da, dimg = silhouette(dv, dt, view, lo, hi)
        inter, union = int((ka & da).sum()), int((ka | da).sum())
        iou = inter / union if union else float("nan")
        views[view] = {"kernel_px": int(ka.sum()), "delivered_px": int(da.sum()), "iou": iou,
                       "passed": union > 0 and iou > SILHOUETTE_IOU_MIN}
        if png_dir is not None:
            from PIL import Image
            rgb = np.zeros(ka.shape + (3,), np.uint8)
            rgb[ka & da] = (200, 200, 200)
            rgb[ka & ~da] = (220, 40, 40)
            rgb[~ka & da] = (40, 80, 220)
            Image.fromarray(rgb).save(png_dir / f"silhouette_{view}.png")
    su = m[DELIVERED_UCX]["face_geometry"]
    sg = _meshes(src_report, {BODY_NODE, UCX_NODE}, "source FBX")[UCX_NODE]["face_geometry"]
    ucx_dev = _set_dev(np.asarray(sg["vertices"], float) + offset, _finite(su["vertices"], "delivered UCX"))
    res = {"pivot_offset_m": [float(x) for x in offset], "kernel_faces": int(sum(len(p["faces"]) for p in out_state.values())),
           "kernel_triangles": int(len(kt)), "delivered_polygons": len(g["polygons"]), "delivered_triangles": len(dt),
           "kernel_area_m2": _area(kv, kt), "delivered_area_m2": _area(dv, dt),
           "bounds_max_abs_dev_m": float(max(np.abs(kv.min(0) - dv.min(0)).max(), np.abs(kv.max(0) - dv.max(0)).max())),
           "kernel_to_delivered_max_m": float(d_kd.max()), "delivered_to_kernel_max_m": float(d_dk.max()),
           "ucx_vertex_set_dev_m": ucx_dev, "silhouettes": views}
    area_tol = DELIVERED_DIST_TOL_M * 0.01 * res["kernel_area_m2"]
    res["checks"] = {
        "surface_distance": max(res["kernel_to_delivered_max_m"], res["delivered_to_kernel_max_m"]) < DELIVERED_DIST_TOL_M,
        "area": abs(res["kernel_area_m2"] - res["delivered_area_m2"]) < area_tol,
        "bounds": res["bounds_max_abs_dev_m"] < DELIVERED_DIST_TOL_M,
        "ucx": ucx_dev < DELIVERED_DIST_TOL_M,
        "silhouettes": all(x["passed"] for x in views.values())}
    res["passed"] = all(res["checks"].values())
    return res


def _key(p) -> str:
    """Repo files by repo-relative path (portable across worktrees), outside files by absolute posix path."""
    p = Path(p).resolve()
    return p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else p.as_posix()


def _require_new(inputs, *outs):
    for p in outs:
        if p.exists():
            raise InputError(f"{p} exists; write a new versioned output")
    ins = {Path(p).resolve() for p in inputs}
    res = [p.resolve() for p in outs]
    if len(set(res)) != len(res) or ins & set(res) or any(i.is_relative_to(o) for i in ins for o in res):
        raise InputError("output paths alias each other or an input")


def run(source_fbx: Path, delivered_fbx: Path, work: Path, evidence: Path, blender: bool = True,
        relative: bool = True):
    from dt_ai.core.blender_runner import run_blender
    delivered_meta = Path(delivered_fbx).parent.parent / "export_meta.json"
    inputs = [source_fbx, delivered_fbx, delivered_meta, rko.SOURCE]
    for p in inputs:
        if not Path(p).is_file():
            raise InputError(f"input missing: {p}")
    out_json, out_md = evidence / "e2e.json", evidence / "e2e.md"
    _require_new(inputs, work, out_json, out_md)
    hashes = {_key(p): sha256(p) for p in inputs}
    work.mkdir(parents=True)
    evidence.mkdir(parents=True, exist_ok=True)
    rb = {}
    for key, fbx in (("source", source_fbx), ("delivered", delivered_fbx)):
        rep = work / f"readback_{key}.json"
        rb[key] = run_blender(rko.READBACK, [fbx, rep], output_json=rep, log_path=work / f"readback_{key}.log",
                              timeout=600)
    parity_rows, mat_map = source_parity(rb["source"])
    source, drops = state_from_source(rb["source"], mat_map)
    ctx = Context()
    before = rko.scene_metrics(source)
    rows = rko.run_ops(source, relative=relative)
    states = {"S00_source": source}
    for k, r in enumerate(rows, 1):
        st = r.get("after_state")
        r["label"] = f"S{k:02d}_{r['op']}_{r['part'].replace('+', '_')}"
        r["candidate_measured"] = st is not None
        if st is not None:
            r["after"] = rko.scene_metrics(st)
            r["after_visibility"] = rko.visibility(st, ctx)
            states[r["label"]] = st
    not_composed = [] if relative else None
    out_state, applied = kernel_output(source, rows, not_composed)
    for r in rows:
        r.pop("after_state", None)
    payload, notes, not_exported = {}, {}, {}
    for label, st in states.items():
        merged = {k: p["mat"].count(0) for k, p in st.items() if 0 in p["mat"]}
        if merged:
            not_exported[label] = f"not exported: polygons merge different material ids {merged}"
            continue
        payload[label], notes[label] = rko.export_payload(st)
    result = {"issue": 968 if relative else 753, "invariants": "relative [D201]" if relative else "absolute",
              "inputs": hashes, "source_parity": parity_rows, "drops": drops, "profile": rko.PROFILE,
              "parts": {k: {"faces": len(p["faces"]), "vertices": len(p["v"])} for k, p in source.items()},
              "before": before, "before_visibility": rko.visibility(source, ctx), "ops": rows,
              "kernel_applied_ops": applied, "not_exported": not_exported,
              **({} if not_composed is None else {"applied_not_composed": not_composed}),
              "readback": {lab: {"status": "not_exported", "reason": why} for lab, why in not_exported.items()}}
    if blender:
        sj = work / "states.json"
        sj.write_text(json.dumps(payload), encoding="utf-8")
        fbx_dir = work / "fbx"
        run_blender(rko.EXPORT, [sj, fbx_dir], outputs=[fbx_dir / f"{k}.fbx" for k in payload],
                    log_path=work / "export.log", timeout=600)
        (work / "readback").mkdir()
        for label in payload:
            fbx, rep = fbx_dir / f"{label}.fbx", work / "readback" / f"{label}.json"
            report = run_blender(rko.READBACK, [fbx, rep], output_json=rep, log_path=work / f"rb_{label}.log",
                                 timeout=600)
            c = rko.compare_state(states[label], report)
            result["readback"][label] = {
                "fbx_sha256": sha256(fbx), "accepted": c["accepted"], "export_uv_loss": c["export_uv_loss"],
                "parity": c["candidate_parity"], "payload_parity": c["payload_parity"]}
    png_dir = work / "silhouettes"
    png_dir.mkdir()
    result["delivered_comparison"] = compare_delivered(out_state, rb["source"], rb["delivered"], png_dir,
                                                       pivot_offset(delivered_meta))
    after = {_key(p): sha256(p) for p in inputs}
    if after != hashes:
        raise InputError("an input changed during the run")
    result["gates"] = gates(result)
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    out_md.write_text(markdown(result), encoding="utf-8")
    return result


def gates(r):
    ops = r["ops"]
    rbk = r["readback"]
    ok_rb = [k for k, x in rbk.items() if x.get("accepted")]
    inv = {"passed": bool(r["before_visibility"]) and all(x["passed"] for x in r["before_visibility"].values()),
           "numbers": ", ".join(f"{k}={x['count']}" for k, x in r["before_visibility"].items())}
    if r.get("invariants", "absolute") != "absolute":
        # [D201]: the source's own violations are the baseline every op is judged against, not a failure
        inv_gate = ("source_baseline_recorded", {"passed": bool(r["before_visibility"]),
                                                 "numbers": "baseline (было до нас): " + inv["numbers"]})
    else:
        inv_gate = ("kernel_invariants_on_source", inv)
    return {
        "source_fbx_equals_pinned_dump": {"passed": r["source_parity"]["passed"],
                                          "numbers": f"{r['source_parity']['polygons']} polygons, max corner dev "
                                                     f"{r['source_parity']['max_corner_dev_m']:.2e} m, UV dev "
                                                     f"{r['source_parity']['max_uv_dev']:.2e}"},
        inv_gate[0]: inv_gate[1],
        "kernel_ops_applied": {"passed": bool(r["kernel_applied_ops"]),
                               "numbers": f"{sum(bool(o.get('applied')) for o in ops)}/{len(ops)} applied"},
        "export_readback_parity": {"passed": len(ok_rb) == len(rbk) and bool(rbk),
                                   "numbers": f"{len(ok_rb)}/{len(rbk)} states accepted"},
        "delivered_fbx_comparison": {"passed": r["delivered_comparison"]["passed"],
                                     "numbers": ", ".join(f"{k}={v}" for k, v in
                                                          r["delivered_comparison"]["checks"].items())}}


def markdown(r):
    dc = r["delivered_comparison"]
    head = ("# AC08 L4 end to end (#753) - generated by run_e2e.py" if "invariants" not in r else
            f"# AC08 L4 end to end (#{r['issue']}, invariants {r['invariants']}) - generated by run_e2e.py")
    lines = [head, "",
             "Inputs (sha256): " + "; ".join(f"`{Path(k).name}` `{v[:12]}`" for k, v in r["inputs"].items()), "",
             "## Gates", "", "| gate | result | numbers |", "|---|---|---|"]
    lines += [f"| {k} | {'pass' if g['passed'] else 'FAIL'} | {g['numbers']} |" for k, g in r["gates"].items()]
    lines += ["", "## Before (source FBX)", "", "| part | metrics |", "|---|---|"]
    lines += [f"| {k} | {rko._short(p)} |" for k, p in r["before"]["parts"].items()]
    lines += ["", "## Operations (same set as #752)", "", "| # | op | part | applied | check_operation | refusal |",
              "|---|---|---|---|---|---|"]
    for k, o in enumerate(r["ops"], 1):
        co = o["check_operation"]
        cos = "-" if co is None else (("pass" if co["passed"] else "FAIL ") + ", ".join(
            f"{x['name']}={x['count']}" for x in co["results"] if not x["passed"])
            + "".join(f" {x['name']} {x['baseline']}/{x['after']}/+{x['new']}" for x in co["results"]
                      if "baseline" in x))
        why = (o["refusal_or_rollback"] or "").replace("|", "/")[:120]
        lines.append(f"| {k} | {o['op']} | {o['part']} | {o['applied']} | {cos} | {why} |")
    lines += ["", "## Export readback", "", "| state | accepted | rows within tol | UV loss |", "|---|---|---|---|"]
    for lab, x in r["readback"].items():
        if x.get("status") == "not_exported":
            lines.append(f"| {lab} | FAIL | - | {x['reason']} |")
            continue
        lines.append(f"| {lab} | {'yes' if x['accepted'] else 'FAIL'} | "
                     f"{sum(p['equal_within_tol'] for p in x['parity'])}/{len(x['parity'])} | "
                     f"{sum(x['export_uv_loss'].values()) if x['export_uv_loss'] else 0} |")
    lines += ["", "## Kernel output vs delivered pilot-v010 VPM FBX", "",
              f"Pivot rebase applied to the kernel output: {dc['pivot_offset_m']} m (delivered export_meta.json "
              "pivot_revit_internal_m -> origin).",
              f"Kernel output = source + applied ops {r['kernel_applied_ops'] or '(none)'}: {dc['kernel_faces']} "
              f"polygons / {dc['kernel_triangles']} triangles; delivered {dc['delivered_polygons']} triangles.",
              *([f"Applied but not composed (footprint overlaps an earlier composed op): "
                 + "; ".join(f"{x['op']} (part {x['part']} owned by {x['conflicts_with']})"
                             for x in r["applied_not_composed"])] if r.get("applied_not_composed") else []), "",
              f"- surface distance kernel->delivered {dc['kernel_to_delivered_max_m']:.2e} m, delivered->kernel "
              f"{dc['delivered_to_kernel_max_m']:.2e} m (tol {DELIVERED_DIST_TOL_M} m)",
              f"- area {dc['kernel_area_m2']:.4f} vs {dc['delivered_area_m2']:.4f} m2; bounds dev "
              f"{dc['bounds_max_abs_dev_m']:.2e} m; UCX vertex-set dev {dc['ucx_vertex_set_dev_m']:.2e} m", "",
              "| view | kernel px | delivered px | IoU |", "|---|---|---|---|"]
    lines += [f"| {k} | {v['kernel_px']} | {v['delivered_px']} | {v['iou']:.5f} |" for k, v in dc["silhouettes"].items()]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source-fbx", required=True, type=Path)
    ap.add_argument("--delivered-fbx", required=True, type=Path)
    ap.add_argument("--work", required=True, type=Path)
    ap.add_argument("--evidence", type=Path, default=HERE / "evidence")
    ap.add_argument("--invariants", choices=("relative", "absolute"), default="relative",
                    help="relative = judged against the source baseline [D201]; absolute = the #753 run")
    a = ap.parse_args(argv)
    try:
        r = run(a.source_fbx, a.delivered_fbx, a.work, a.evidence, relative=a.invariants == "relative")
    except InputError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    for k, g in r["gates"].items():
        print(f"GATE {k}: {'pass' if g['passed'] else 'FAIL'} ({g['numbers']})")
    return 0 if all(g["passed"] for g in r["gates"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
