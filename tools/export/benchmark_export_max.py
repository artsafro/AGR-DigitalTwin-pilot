"""Synthetic headless 3ds Max export benchmark. All geometry and maps are synthetic.

Env: AGR_BENCH_OUT (fresh directory, required, outside the repo), AGR_BENCH_SIZES
(default 50,200), AGR_BENCH_ROUTE_BUDGET_S (default 240), AGR_BENCH_ROUTES
(optional comma filter). Prints AGR_BENCH_DONE <path>.
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import batch_export_max as job
import batch_export_plan as plan

rt = job.rt

ALL_ROUTES = (
    "a_savenodes",
    "b_fbx",
    "c_one_pass",
    "c_one_pass_fbx",
    "d_hold_fetch",
    "d_pymxs_fingerprint",
    "d_gc",
    "d_scene_size",
)
_EXPORT_ROUTES = ("a_savenodes", "b_fbx", "c_one_pass", "c_one_pass_fbx")

FINGERPRINT_MXS = r'''
fn agrBenchFingerprint m = (
    local s = 0.0
    local nv = getNumVerts m
    local nf = getNumFaces m
    local i
    for i = 1 to nv do (
        local v = getVert m i
        s += v.x + v.y + v.z
    )
    for i = 1 to nf do (
        local f = getFace m i
        s += f.x + f.y + f.z
    )
    s
)
'''


def _slash(path: str) -> str:
    return os.path.abspath(path).replace("\\", "/")


def _repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


def _inside_repo(path: str) -> bool:
    repo = _repo_root()
    try:
        common = os.path.commonpath([repo, os.path.abspath(path)])
    except ValueError:
        return False
    return common.casefold() == repo.casefold()


def _names(n: int) -> list[str]:
    return ["syn_%03d" % index for index in range(n)]


def generate_scene(n: int, root: str) -> str:
    """Build n synthetic planes (even index 2000 tris, odd index 20000) and save a new scene."""
    root = _slash(root)
    maps = root + "/maps"
    os.makedirs(maps, exist_ok=True)
    rt.resetMaxFile(rt.Name("noPrompt"))
    cols = max(1, int(n ** 0.5 + 0.999))
    for index in range(n):
        name = "syn_%03d" % index
        png = maps + "/" + name + ".png"
        if index % 2 == 0:
            lengthsegs, widthsegs, expect = 10, 100, 2000
        else:
            lengthsegs, widthsegs, expect = 100, 100, 20000
        red = (index * 37) % 256
        green = (index * 17) % 256
        blue = (index * 91) % 256
        column = index % cols
        row = index // cols
        script = (
            '(\n'
            'local png = "%s"\n'
            'local b = bitmap 8 8 color:(color %d %d %d)\n'
            'b.filename = png\n'
            'save b\n'
            'close b\n'
            'local p = Plane length:100 width:100 lengthsegs:%d widthsegs:%d\n'
            'convertToMesh p\n'
            'p.name = "%s"\n'
            'local mat = StandardMaterial name:"mat_%d"\n'
            'local tex = Bitmaptexture filename:png\n'
            'mat.diffuseMap = tex\n'
            'p.material = mat\n'
            'p.pos = [%d, %d, 0]\n'
            'if p.numfaces != %d do throw ("face count " + (p.numfaces as string) + " != %d")\n'
            'p.numfaces\n'
            ')'
        ) % (png, red, green, blue, lengthsegs, widthsegs, name, index, column * 150, row * 150, expect, expect)
        got = int(rt.execute(script))
        if got != expect:
            raise RuntimeError("synthetic %s has %s faces, expected %s" % (name, got, expect))
    scene = root + "/scene_n%d.max" % n
    if not rt.saveMaxFile(scene, quiet=True):
        raise RuntimeError("saveMaxFile failed: " + scene)
    print(
        "GENERATOR synthetic=true n=%d even=Plane length:100 width:100 lengthsegs:10 widthsegs:100 tris=2000 "
        "odd=lengthsegs:100 widthsegs:100 tris=20000 map=8x8 StandardMaterial scene=%s"
        % (n, scene)
    )
    return scene


def _reload(scene: str) -> None:
    if not rt.loadMaxFile(scene, quiet=True, useFileUnits=True):
        raise RuntimeError("reload failed: " + scene)


def _budget_hit(started: float, budget: float) -> bool:
    return (time.perf_counter() - started) >= budget


def _record(route: str, n: int, node: str, tris, seconds, export_s, readback_s, ok: bool) -> dict:
    return {
        "route": route,
        "n": n,
        "node": node,
        "tris": tris,
        "seconds": round(float(seconds), 6),
        "export_s": round(float(export_s), 6),
        "readback_s": round(float(readback_s), 6),
        "ok": bool(ok),
    }


def _verdict_ok(expected_tris, got_tris, expected_mats, got_mats, path, ok_flag) -> bool:
    exists = os.path.exists(path) and ok_flag
    error = None if ok_flag else "readback failed"
    status, _reason = plan.readback_verdict(expected_tris, got_tris, expected_mats, got_mats, exists, error)
    return status == "ok"


def run_a_savenodes(n: int, folder: str, budget: float) -> list[dict]:
    """Today's route: saveNodes per object, then agrReadbackMax."""
    rows = []
    started = time.perf_counter()
    for name in _names(n):
        if _budget_hit(started, budget):
            break
        node = rt.getNodeByName(name, exact=True)
        if job._missing(node):
            raise RuntimeError("node not found: " + name)
        path = folder + "/" + name + ".max"
        expected_tris = int(rt.agrTris(node))
        expected_mats = int(rt.agrLeafMats(rt.Array(node)))
        whole = time.perf_counter()
        export_started = time.perf_counter()
        rt.saveNodes(rt.Array(node), path, quiet=True)
        export_s = time.perf_counter() - export_started
        read_started = time.perf_counter()
        ok_flag, got_tris, got_mats = job._as_triple(rt.agrReadbackMax(path))
        readback_s = time.perf_counter() - read_started
        seconds = time.perf_counter() - whole
        rows.append(_record(
            "a_savenodes", n, name, expected_tris, seconds, export_s, readback_s,
            _verdict_ok(expected_tris, got_tris, expected_mats, got_mats, path, ok_flag),
        ))
    return rows


def run_b_fbx(n: int, folder: str, budget: float) -> list[dict]:
    """FBX preset once, then selectedOnly export and agrReadbackFbx per object."""
    job.set_fbx_preset()
    rows = []
    started = time.perf_counter()
    for name in _names(n):
        if _budget_hit(started, budget):
            break
        node = rt.getNodeByName(name, exact=True)
        if job._missing(node):
            raise RuntimeError("node not found: " + name)
        path = folder + "/" + name + ".fbx"
        expected_tris = int(rt.agrTris(node))
        expected_mats = int(rt.agrLeafMats(rt.Array(node)))
        whole = time.perf_counter()
        export_started = time.perf_counter()
        rt.select(node)
        rt.exportFile(path, rt.Name("noPrompt"), selectedOnly=True, using=rt.FBXEXP)
        rt.clearSelection()
        export_s = time.perf_counter() - export_started
        read_started = time.perf_counter()
        ok_flag, got_tris, got_mats = job._as_triple(rt.agrReadbackFbx(path))
        readback_s = time.perf_counter() - read_started
        seconds = time.perf_counter() - whole
        rows.append(_record(
            "b_fbx", n, name, expected_tris, seconds, export_s, readback_s,
            _verdict_ok(expected_tris, got_tris, expected_mats, got_mats, path, ok_flag),
        ))
    return rows


def _rows_from_log(route: str, n: int, names: list[str], log_path: str) -> list[dict]:
    found = plan.read_log(log_path)
    by_node = {row.get("node"): row for row in found.values()}
    rows = []
    for name in names:
        row = by_node.get(name)
        if row is None:
            continue
        timings = row.get("timings") if isinstance(row.get("timings"), dict) else {}
        rows.append(_record(
            route, n, name, row.get("triangles"),
            float(row.get("seconds") or 0.0),
            float(timings.get("export") or 0.0),
            float(timings.get("readback") or 0.0),
            row.get("status") == "ok",
        ))
    return rows


def run_c_one_pass(n: int, folder: str, budget: float, fmt: str, route: str) -> tuple[list[dict], dict]:
    """holdMaxFile, shared export_nodes, fetchMaxFile. Per-object seconds come from the JSONL log."""
    names = _names(n)
    hold_started = time.perf_counter()
    rt.holdMaxFile()
    hold_s = time.perf_counter() - hold_started
    log_path = folder + "/export.jsonl"
    req = {
        "scene": None,
        "nodes": names,
        "out_dir": folder,
        "format": fmt,
        "log_path": log_path,
        "deadline": time.perf_counter() + budget,
    }
    job.export_nodes(req, log_path)
    fetch_started = time.perf_counter()
    rt.fetchMaxFile(quiet=True)
    fetch_s = time.perf_counter() - fetch_started
    extra = {"hold_s": round(hold_s, 6), "fetch_s": round(fetch_s, 6), "format": fmt}
    return _rows_from_log(route, n, names, log_path), extra


def run_d_hold_fetch() -> dict:
    hold_s = []
    fetch_s = []
    for _repeat in range(3):
        started = time.perf_counter()
        rt.holdMaxFile()
        hold_s.append(round(time.perf_counter() - started, 6))
        started = time.perf_counter()
        rt.fetchMaxFile(quiet=True)
        fetch_s.append(round(time.perf_counter() - started, 6))
    return {"repeats": 3, "hold_s": hold_s, "fetch_s": fetch_s}


def run_d_pymxs_fingerprint() -> dict:
    """Python per-vertex/face loop versus one MAXScript call, on one 20k snapshot."""
    node = rt.getNodeByName("syn_001", exact=True)
    if job._missing(node):
        node = rt.getNodeByName("syn_000", exact=True)
    mesh = rt.snapshotAsMesh(node)
    try:
        verts = int(rt.getNumVerts(mesh))
        faces = int(rt.getNumFaces(mesh))
        started = time.perf_counter()
        total = 0.0
        for index in range(1, verts + 1):
            point = rt.getVert(mesh, index)
            total += float(point.x)
        for index in range(1, faces + 1):
            face = rt.getFace(mesh, index)
            total += float(face.x)
        python_s = time.perf_counter() - started
        rt.execute(FINGERPRINT_MXS)
        started = time.perf_counter()
        scripted = rt.agrBenchFingerprint(mesh)
        maxscript_s = time.perf_counter() - started
    finally:
        rt.delete(mesh)
    return {
        "node": str(node.name),
        "verts": verts,
        "faces": faces,
        "python_s": round(python_s, 6),
        "maxscript_s": round(maxscript_s, 6),
        "python_acc": total,
        "maxscript_acc": float(scripted),
    }


def run_d_gc() -> dict:
    started = time.perf_counter()
    rt.gc(light=True)
    light_s = time.perf_counter() - started
    started = time.perf_counter()
    rt.gc()
    full_s = time.perf_counter() - started
    return {"light_s": round(light_s, 6), "full_s": round(full_s, 6)}


def run_d_scene_size(n: int, folder: str) -> dict:
    """saveNodes of one 20k node in the full scene, then again after every other node is deleted."""
    name = "syn_001" if n > 1 else "syn_000"
    node = rt.getNodeByName(name, exact=True)
    if job._missing(node):
        raise RuntimeError("node not found: " + name)
    tris = int(rt.agrTris(node))
    full_path = folder + "/full.max"
    started = time.perf_counter()
    rt.saveNodes(rt.Array(node), full_path, quiet=True)
    full_s = time.perf_counter() - started
    others = [item for item in list(rt.objects) if str(item.name) != name]
    for item in others:
        rt.delete(item)
    alone_path = folder + "/alone.max"
    node = rt.getNodeByName(name, exact=True)
    started = time.perf_counter()
    rt.saveNodes(rt.Array(node), alone_path, quiet=True)
    alone_s = time.perf_counter() - started
    return {
        "n": n,
        "node": name,
        "tris": tris,
        "full_scene_s": round(full_s, 6),
        "alone_s": round(alone_s, 6),
        "others_deleted": len(others),
    }


def _summarize(rows: list[dict], sizes: list[int]) -> dict:
    grouped: dict[tuple, list] = {}
    for row in rows:
        grouped.setdefault((row["route"], int(row["n"])), []).append(row)
    summary: dict = {}
    for (route, n), items in grouped.items():
        summary.setdefault(route, {})
        ok = sum(1 for item in items if item["ok"])
        summary[route][str(n)] = {
            "seconds": plan.stats([float(item["seconds"]) for item in items]),
            "export_s": plan.stats([float(item["export_s"]) for item in items]),
            "ok": ok,
            "failed": len(items) - ok,
            "budget_hit": len(items) < n,
        }
    return summary


def _ordered(selected: list[str]) -> list[str]:
    rank = {name: index for index, name in enumerate(ALL_ROUTES)}
    unknown = [name for name in selected if name not in rank]
    known = [name for name in selected if name in rank]
    known.sort(key=lambda name: rank[name])
    return known + unknown


def main() -> None:
    root = os.environ.get("AGR_BENCH_OUT")
    if not root:
        raise SystemExit("AGR_BENCH_OUT is required")
    root = _slash(root)
    if _inside_repo(root):
        raise SystemExit("AGR_BENCH_OUT must be outside the repository")
    if os.path.exists(root):
        raise SystemExit("AGR_BENCH_OUT already exists: " + root)
    os.makedirs(root)
    sizes = [int(part) for part in os.environ.get("AGR_BENCH_SIZES", "50,200").split(",") if part.strip()]
    budget = float(os.environ.get("AGR_BENCH_ROUTE_BUDGET_S", "240"))
    raw_routes = os.environ.get("AGR_BENCH_ROUTES", "").strip()
    selected = _ordered([part.strip() for part in raw_routes.split(",") if part.strip()] if raw_routes else list(ALL_ROUTES))
    job.register_helpers()
    version = "unknown"
    try:
        version = str(list(rt.maxVersion()))
    except Exception:
        version = str(rt.maxVersion())
    rows: list[dict] = []
    extras: dict = {}
    for n in sizes:
        scene = generate_scene(n, root)
        for route in selected:
            folder = "%s/n%d/%s" % (root, n, route)
            os.makedirs(folder, exist_ok=True)
            try:
                _reload(scene)
                if route == "a_savenodes":
                    rows.extend(run_a_savenodes(n, folder, budget))
                elif route == "b_fbx":
                    rows.extend(run_b_fbx(n, folder, budget))
                elif route == "c_one_pass":
                    made, extra = run_c_one_pass(n, folder, budget, "max", route)
                    rows.extend(made)
                    extras.setdefault("c_one_pass_hold_fetch", {})[str(n)] = extra
                elif route == "c_one_pass_fbx":
                    made, extra = run_c_one_pass(n, folder, budget, "fbx", route)
                    rows.extend(made)
                    extras.setdefault("c_one_pass_fbx_hold_fetch", {})[str(n)] = extra
                elif route == "d_hold_fetch":
                    extras.setdefault("d_hold_fetch", {})[str(n)] = run_d_hold_fetch()
                elif route == "d_pymxs_fingerprint":
                    extras.setdefault("d_pymxs_fingerprint", {})[str(n)] = run_d_pymxs_fingerprint()
                elif route == "d_gc":
                    extras.setdefault("d_gc", {})[str(n)] = run_d_gc()
                elif route == "d_scene_size":
                    extras.setdefault("d_scene_size", {})[str(n)] = run_d_scene_size(n, folder)
                else:
                    raise RuntimeError("unknown route: " + route)
            except Exception as exc:
                extras.setdefault("errors", {})["%s/n%d" % (route, n)] = str(exc)[:300]
                print("ROUTE_FAIL", route, n, str(exc)[:300])
    payload = {
        "max_version": version,
        "generator": {
            "synthetic": True,
            "object_name": "syn_000",
            "even_index_tris": 2000,
            "odd_index_tris": 20000,
            "even_lengthsegs": 10,
            "even_widthsegs": 100,
            "odd_lengthsegs": 100,
            "odd_widthsegs": 100,
            "plane_length": 100,
            "plane_width": 100,
            "map_px": 8,
            "material": "StandardMaterial",
        },
        "sizes": sizes,
        "rows": rows,
        "extras": extras,
        "summary": _summarize(rows, sizes),
    }
    target = root + "/benchmark.json"
    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print("AGR_BENCH_DONE " + target)


if __name__ == "__main__" or os.environ.get("AGR_BENCH_OUT"):
    main()
