"""Headless 3ds Max job: resumable per-object MAX/FBX export from the already open scene.

new-case: #224 resumable per-object MAX/FBX export from one headless Max session

Run via dcc_batch.py with AGR_BATCH_EXPORT_REQUEST pointing at a request JSON
(see batch_export_plan.py). Importing this module does not start a request, so
the benchmark can call export_nodes() on a scene it built itself. The loaded
scene is a copy and is never saved.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import batch_export_plan as plan

import pymxs

rt = pymxs.runtime

MXS = r'''
fn agrTris n = (
    if n == undefined do return 0
    if (superClassOf n != GeometryClass) do return 0
    local m = snapshotAsMesh n
    if m == undefined do return 0
    local c = m.numfaces
    delete m
    c
)
fn agrCollectLeaves mat acc = (
    if mat == undefined do return acc
    if classOf mat == Multimaterial then (
        local subs = mat.materialList
        local i
        for i = 1 to subs.count do (
            if subs[i] != undefined do agrCollectLeaves subs[i] acc
        )
    ) else (
        appendIfUnique acc mat
    )
    acc
)
fn agrLeafMats nodes = (
    local acc = #()
    for n in nodes do agrCollectLeaves n.material acc
    acc.count
)
fn agrReadbackMax f = (
    local nodes = #()
    local merged = mergeMAXFile f #autoRenameDups #neverReparent #renameMtlDups #noRedraw quiet:true mergedNodes:&nodes
    if merged == false do return #(false, 0, 0)
    local tris = 0
    local geos = #()
    for n in nodes where (isValidNode n and superClassOf n == GeometryClass) do (
        append geos n
        tris += agrTris n
    )
    local mats = agrLeafMats geos
    for n in nodes do (try (delete n) catch ())
    #(true, tris, mats)
)
fn agrReadbackFbx f = (
    local before = #()
    for o in objects do append before o.handle
    FBXImporterSetParam "Mode" #create
    local imported = importFile f #noPrompt using:FBXIMP
    if imported == false do return #(false, 0, 0)
    local newNodes = #()
    for o in objects do (
        if (findItem before o.handle) == 0 do append newNodes o
    )
    local tris = 0
    local geos = #()
    for n in newNodes where (isValidNode n and superClassOf n == GeometryClass) do (
        append geos n
        tris += agrTris n
    )
    local mats = agrLeafMats geos
    for n in newNodes do (try (delete n) catch ())
    #(true, tris, mats)
)
fn agrSaveNodes n f = (
    saveNodes #(n) f quiet:true
    doesFileExist f
)
fn agrExportFbx n f = (
    select n
    exportFile f #noPrompt selectedOnly:true using:FBXEXP
    clearSelection()
    doesFileExist f
)
'''

_REGISTERED = False
_PRESET = False


def register_helpers() -> None:
    """Install the MAXScript helpers once per session."""
    global _REGISTERED
    if _REGISTERED:
        return
    rt.execute(MXS)
    _REGISTERED = True


def set_fbx_preset() -> None:
    """Geometry-only FBX export. Triangles stay as they are in the mesh."""
    global _PRESET
    if _PRESET:
        return
    rt.FBXExporterSetParam("Animation", False)
    rt.FBXExporterSetParam("Cameras", False)
    rt.FBXExporterSetParam("Lights", False)
    rt.FBXExporterSetParam("EmbedTextures", False)
    rt.FBXExporterSetParam("SmoothingGroups", True)
    rt.FBXExporterSetParam("Triangulate", False)
    rt.FBXExporterSetParam("UpAxis", "Z")
    _PRESET = True


def _truth(value) -> bool:
    return plan.truth(value)


def _as_triple(value):
    """Read #(ok, tris, mats). pymxs Arrays are 0-based Python sequences."""
    return plan.parse_triple(value)


def _missing(node) -> bool:
    if node is None:
        return True
    try:
        if node == rt.undefined:
            return True
    except Exception:
        return True
    return False


def _file_size(path) -> int:
    try:
        return int(os.path.getsize(path))
    except OSError:
        return 0


def _open_scene_path():
    """Path of the scene currently open in Max, when it has a file name."""
    try:
        name = rt.maxFileName
    except Exception:
        return None
    if name is None:
        return None
    text = str(name)
    if text == "" or text == "undefined" or text == "None":
        return None
    try:
        folder = rt.maxFilePath
    except Exception:
        return None
    if folder is None:
        return None
    return str(folder) + text


def _protected_paths(req: dict) -> list:
    protected = []
    scene = req.get("scene")
    if scene:
        protected.append(scene)
    loaded = _open_scene_path()
    if loaded:
        protected.append(loaded)
    extra = req.get("protect", [])
    if isinstance(extra, list):
        protected.extend(extra)
    for key in ("request_path", "result_path"):
        value = req.get(key)
        if value:
            protected.append(value)
    return protected


def _readback(fmt: str, path: str):
    if fmt == "max":
        return _as_triple(rt.agrReadbackMax(path))
    return _as_triple(rt.agrReadbackFbx(path))


def _write_file(fmt: str, node, path: str) -> bool:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    if fmt == "max":
        return _truth(rt.agrSaveNodes(node, path))
    return _truth(rt.agrExportFbx(node, path))


def _export_one(task: dict, log: dict, fmt: str):
    """Returns (row or None, log_this_row). Skip logs nothing."""
    started = time.perf_counter()
    timings: dict = {}
    try:
        node = rt.getNodeByName(task["node"], exact=True)
        if _missing(node):
            seconds = round(time.perf_counter() - started, 4)
            row = plan.make_row(
                task, "failed", seconds, None, None, None, None, 0,
                error="node not found", timings=timings,
            )
            return row, True
        expected_tris = int(rt.agrTris(node))
        expected_mats = int(rt.agrLeafMats(rt.Array(node)))
        action = plan.decide(task, log, expected_tris, expected_mats)

        def readback():
            stamp = time.perf_counter()
            try:
                return _readback(fmt, task["output"])
            finally:
                timings["readback"] = round(time.perf_counter() - stamp, 4)

        def write():
            stamp = time.perf_counter()
            try:
                return _write_file(fmt, node, task["output"])
            finally:
                timings["export"] = round(time.perf_counter() - stamp, 4)

        if action == "verify":
            try:
                ok_flag, got_tris, got_mats = readback()
                exists = os.path.exists(task["output"])
                error = None if ok_flag else "readback failed"
                status, _reason = plan.readback_verdict(
                    expected_tris, got_tris, expected_mats, got_mats, exists, error,
                )
            except Exception:
                status = "failed"
            if status == "ok":
                return None, False
            timings.pop("readback", None)

        wrote = write()
        exists = os.path.exists(task["output"])
        got_tris = None
        got_mats = None
        error = None if wrote else "export failed"
        ok_flag = False
        if exists:
            ok_flag, got_tris, got_mats = readback()
            if not ok_flag:
                error = error or "readback failed"
        else:
            error = error or "export failed"
        status, reason = plan.readback_verdict(
            expected_tris, got_tris, expected_mats, got_mats, exists, error,
        )
        seconds = round(time.perf_counter() - started, 4)
        sha = plan.file_sha256(task["output"]) if status == "ok" else None
        row = plan.make_row(
            task, status, seconds, expected_tris, expected_mats, got_tris, got_mats,
            _file_size(task["output"]), error=reason, resumed=False, timings=dict(timings),
            sha256=sha,
        )
        return row, True
    except Exception as exc:
        seconds = round(time.perf_counter() - started, 4)
        row = plan.make_row(
            task, "failed", seconds, None, None, None, None, _file_size(task.get("output", "")),
            error=str(exc)[:300], timings=timings,
        )
        return row, True


def export_nodes(req: dict, log_path) -> list[dict]:
    """Export each planned node. One log row per object except confirmed skips."""
    register_helpers()
    fmt = req["format"]
    if fmt == "fbx":
        set_fbx_preset()
    tasks = plan.plan_outputs(list(req["nodes"]), req["out_dir"], fmt)
    plan.preflight(tasks, _protected_paths(req), "" if log_path is None else str(log_path))
    found = plan.read_log(log_path)
    parent = req["out_dir"]
    if parent:
        os.makedirs(parent, exist_ok=True)
    deadline = req.get("deadline")
    rows: list[dict] = []
    skipped = 0
    rt.disableSceneRedraw()
    try:
        with pymxs.undo(False), pymxs.redraw(False):
            for index, task in enumerate(tasks, start=1):
                if deadline is not None and time.perf_counter() >= float(deadline):
                    break
                row, log_it = _export_one(task, found, fmt)
                if index % 25 == 0:
                    stamp = time.perf_counter()
                    rt.gc(light=True)
                    if row is not None:
                        timings = row.get("timings")
                        if not isinstance(timings, dict):
                            timings = {}
                            row["timings"] = timings
                        timings["gc"] = round(time.perf_counter() - stamp, 4)
                        if isinstance(row.get("seconds"), (int, float)) and not isinstance(row.get("seconds"), bool):
                            row["seconds"] = round(float(row["seconds"]) + timings["gc"], 4)
                if log_it and row is not None:
                    plan.append_log(log_path, row)
                    found[plan.path_key(row["output"])] = row
                    rows.append(row)
                else:
                    skipped += 1
    finally:
        rt.enableSceneRedraw()
    export_nodes.skipped = skipped
    return rows


def _run_request() -> None:
    path = os.environ.get("AGR_BATCH_EXPORT_REQUEST")
    if not path:
        return
    req = plan.load_request(path)
    scene = req.get("scene")
    if scene:
        if not rt.loadMaxFile(scene, quiet=True, useFileUnits=True):
            raise RuntimeError("cannot load scene")
    rows = export_nodes(req, req["log_path"])
    skipped = int(getattr(export_nodes, "skipped", 0))
    ok = sum(1 for row in rows if row.get("status") == "ok")
    failed = sum(1 for row in rows if row.get("status") == "failed")
    done = ok + failed + skipped
    median = plan.stats([float(row["seconds"]) for row in rows if row.get("status") == "ok" and row.get("seconds") is not None])["median"]
    median_s = "none" if median is None else ("%.4f" % median)
    print("AGR_BATCH_EXPORT done=%d ok=%d failed=%d skipped=%d median_s=%s" % (done, ok, failed, skipped, median_s))


if __name__ == "__main__" or os.environ.get("AGR_BATCH_EXPORT_REQUEST"):
    # An import from the benchmark has neither __main__ nor this variable set.
    _run_request()
