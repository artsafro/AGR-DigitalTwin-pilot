"""Headless safety probe for the per-object Max export. Synthetic geometry only.

new-case: #224 resumable per-object MAX/FBX export from one headless Max session

Run via dcc_batch. AGR_SAFETY_OUT is the required output folder. AGR_EXPORT_DIR
selects which tools/export folder to import (default: this file's folder).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

STEP_NAMES = (
    "valid_resume",
    "corrupt_same_size",
    "changed_source",
    "collision_reorder",
    "source_alias",
    "combination",
)


def _load_job():
    os.environ.pop("AGR_BATCH_EXPORT_REQUEST", None)
    folder = os.environ.get("AGR_EXPORT_DIR") or os.path.dirname(os.path.abspath(__file__))
    folder = os.path.abspath(folder)
    while folder in sys.path:
        sys.path.remove(folder)
    sys.path.insert(0, folder)
    for name in ("batch_export_plan", "batch_export_max"):
        sys.modules.pop(name, None)
    import batch_export_max as loaded
    return loaded


def _sha256(path):
    """Own hash helper, so the probe also runs against commits without plan.file_sha256."""
    try:
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except OSError:
        return None


def _slash(path) -> str:
    return os.path.abspath(path).replace("\\", "/")


def _make_box(rt, name, widthsegs=1):
    script = (
        "(\n"
        "local b = Box length:10 width:10 height:10 lengthsegs:1 widthsegs:%d heightsegs:1\n"
        "convertToMesh b\n"
        "b.name = \"%s\"\n"
        "b.material = StandardMaterial name:\"mat_%s\"\n"
        "b.numfaces\n"
        ")"
    ) % (int(widthsegs), name, name)
    return int(rt.execute(script))


def _export(job, nodes, folder, scene=None):
    folder = _slash(folder)
    os.makedirs(folder, exist_ok=True)
    log_path = folder + "/batch.jsonl"
    req = {"nodes": list(nodes), "out_dir": folder, "format": "max"}
    if scene is not None:
        req["scene"] = scene
    rows = job.export_nodes(req, log_path)
    skipped = int(getattr(job.export_nodes, "skipped", 0))
    return rows, skipped, log_path


def _tris(rt, name):
    node = rt.getNodeByName(name, exact=True)
    return int(rt.agrTris(node))


def _record(steps, name, fn):
    try:
        result = fn()
    except Exception as exc:
        steps[name] = {"passed": False, "error": "%s: %s" % (type(exc).__name__, exc)}
        return
    if not isinstance(result, dict):
        steps[name] = {"passed": False, "error": "step returned no dict"}
        return
    result["passed"] = bool(result.get("passed") is True)
    steps[name] = result


def _run(job, out, steps):
    rt = job.rt
    plan = job.plan
    try:
        rt.resetMaxFile(rt.Name("noPrompt"))
        job.register_helpers()
        _make_box(rt, "probe_0")
        _make_box(rt, "probe_1")
        _make_box(rt, "probe_2")
    except Exception as exc:
        error = "%s: %s" % (type(exc).__name__, exc)
        for name in STEP_NAMES:
            steps[name] = {"passed": False, "error": error}
        return

    resume = _slash(os.path.join(out, "resume"))

    def valid_resume():
        rows1, _skipped1, _log = _export(job, ["probe_0"], resume)
        rows2, skipped2, _log = _export(job, ["probe_0"], resume)
        first_ok = len(rows1) == 1 and rows1[0].get("status") == "ok"
        return {
            "passed": first_ok and rows2 == [] and skipped2 == 1,
            "first": len(rows1),
            "second": len(rows2),
            "skipped": skipped2,
        }

    def corrupt_same_size():
        tasks = plan.plan_outputs(["probe_0"], resume, "max")
        path = tasks[0]["output"]
        size = os.path.getsize(path)
        with open(path, "wb") as handle:
            handle.write(b"X" * size)
        rows, _skipped, _log = _export(job, ["probe_0"], resume)
        data = open(path, "rb").read()
        status = rows[0].get("status") if rows else None
        return {
            "passed": len(rows) == 1 and status == "ok" and data != (b"X" * len(data)),
            "rows": len(rows),
            "status": status,
        }

    def changed_source():
        rt.execute("meshop.deleteFaces $probe_0 #{1}")
        rows, _skipped, _log = _export(job, ["probe_0"], resume)
        triangles = rows[0].get("triangles") if rows else None
        status = rows[0].get("status") if rows else None
        return {
            "passed": len(rows) == 1 and status == "ok" and triangles == 11,
            "rows": len(rows),
            "status": status,
            "triangles": triangles,
        }

    def collision_reorder():
        _make_box(rt, "Cx", 1)
        _make_box(rt, "cx", 2)
        folder = _slash(os.path.join(out, "collision"))
        _export(job, ["Cx", "cx"], folder)
        rows, _skipped, _log = _export(job, ["cx", "Cx"], folder)
        matched = len(rows) == 2
        detail = []
        for row in rows:
            current = _tris(rt, row["node"])
            detail.append({
                "node": row.get("node"),
                "status": row.get("status"),
                "readback_triangles": row.get("readback_triangles"),
                "current": current,
            })
            if row.get("status") != "ok" or row.get("readback_triangles") != current:
                matched = False
        for task in plan.plan_outputs(["cx", "Cx"], folder, "max"):
            current = _tris(rt, task["node"])
            ok_flag, got_tris, _mats = job._readback("max", task["output"])
            detail.append({"output": task["output"], "readback": got_tris, "current": current, "ok": bool(ok_flag)})
            if not ok_flag or got_tris != current:
                matched = False
        return {"passed": matched, "detail": detail}

    def source_alias():
        folder = _slash(os.path.join(out, "src"))
        os.makedirs(folder, exist_ok=True)
        kept = int(rt.execute(
            "(\n"
            "local doomed = #()\n"
            "for o in objects where (o.name != \"probe_0\" and o.name != \"probe_1\" and o.name != \"probe_2\") do append doomed o\n"
            "for n in doomed do delete n\n"
            "objects.count\n"
            ")"
        ))
        path = folder + "/probe_1.max"
        saved = bool(rt.saveMaxFile(path, quiet=True))
        before = _sha256(path)
        log_path = folder + "/batch.jsonl"
        raised = False
        message = ""
        try:
            job.export_nodes(
                {"nodes": ["probe_1"], "out_dir": folder, "format": "max", "scene": path},
                log_path,
            )
        except ValueError as exc:
            raised = True
            message = str(exc)
        after = _sha256(path)
        loaded = bool(rt.loadMaxFile(path, quiet=True))
        count = int(rt.execute("objects.count"))
        return {
            "passed": saved and raised and before is not None and before == after and loaded and count == 3 and not os.path.exists(log_path),
            "saved": saved,
            "raised": raised,
            "message": message,
            "kept": kept,
            "count": count,
            "loaded": loaded,
        }

    def combination():
        rt.resetMaxFile(rt.Name("noPrompt"))
        _make_box(rt, "Ka", 1)
        _make_box(rt, "ka", 2)
        folder = _slash(os.path.join(out, "combo"))
        _export(job, ["Ka", "ka"], folder)
        for task in plan.plan_outputs(["Ka", "ka"], folder, "max"):
            size = os.path.getsize(task["output"])
            with open(task["output"], "wb") as handle:
                handle.write(b"X" * size)
        rt.execute("meshop.deleteFaces $Ka #{1}")
        rows, _skipped, _log = _export(job, ["ka", "Ka"], folder)
        detail = []
        matched = len(rows) == 2
        for row in rows:
            current = _tris(rt, row["node"])
            detail.append({
                "node": row.get("node"),
                "status": row.get("status"),
                "triangles": row.get("triangles"),
                "readback_triangles": row.get("readback_triangles"),
                "current": current,
            })
            if row.get("status") != "ok" or row.get("triangles") != current or row.get("readback_triangles") != current:
                matched = False
        return {"passed": matched, "detail": detail}

    _record(steps, "valid_resume", valid_resume)
    _record(steps, "corrupt_same_size", corrupt_same_size)
    _record(steps, "changed_source", changed_source)
    _record(steps, "collision_reorder", collision_reorder)
    _record(steps, "source_alias", source_alias)
    _record(steps, "combination", combination)


def main() -> None:
    out = os.environ.get("AGR_SAFETY_OUT")
    if not out:
        raise SystemExit("AGR_SAFETY_OUT is required")
    out = os.path.abspath(out)
    os.makedirs(out, exist_ok=True)
    steps = {}
    try:
        job = _load_job()
        _run(job, out, steps)
    except Exception as exc:
        if not steps:
            steps["setup"] = {"passed": False, "error": "%s: %s" % (type(exc).__name__, exc)}
    finally:
        text = json.dumps(steps, ensure_ascii=False, indent=2)
        with open(os.path.join(out, "safety.json"), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.write("\n")
        print("AGR_SAFETY_RESULT " + json.dumps(steps, ensure_ascii=False))


if __name__ == "__main__" or os.environ.get("AGR_SAFETY_OUT"):
    main()
