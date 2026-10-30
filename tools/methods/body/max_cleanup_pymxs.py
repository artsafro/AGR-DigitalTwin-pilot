"""3ds Max pymxs edit-poly clean-up of a supplied body FBX (#727); runs INSIDE 3dsmaxbatch through dcc_batch.py.

Pattern: new-case: headless pymxs weld / isolated-vertex / cap-holes clean-up for the building-body methods class.

The batch driver writes a job file `CONFIG = {...}` + `exec(<this file>)`; CONFIG = {"src": <copy of the source
FBX>, "out": <new FBX>, "report": <out>.variant.json}. Steps on every non-UCX geometry object: Editable Poly,
weld vertices within 1 mm (system units from units.decodeValue), delete isolated vertices, Cap Holes modifier,
collapse; UCX pieces are left as imported. FBX export of the whole scene. The report carries ok, wall_time_s
(after import up to the end of the export), the Max version and per-object vertex / face counts before and after.
Our own logic: no team-script text (docs/research/team-scripts-audit.md describes theirs).
Before Max is touched: src, out and report must be three different files (resolved path, hard link, symlink);
otherwise RuntimeError, nothing is written (not even the report), the driver sees a failed job.
"""
import json
import os
import time

from pymxs import runtime as rt

cfg = CONFIG  # noqa: F821 - set by the job file


def _same(a, b):
    if os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b)):
        return True
    try:
        return os.path.exists(a) and os.path.exists(b) and os.path.samefile(a, b)
    except OSError:
        return False


_paths = [("src", cfg["src"]), ("out", cfg["out"]), ("report", cfg["report"])]
for _i, (_ka, _a) in enumerate(_paths):
    for _kb, _b in _paths[_i + 1:]:
        if _same(_a, _b):
            print("BODY_MAX refused: %s and %s are the same file (%s); nothing written" % (_ka, _kb, _a))
            raise RuntimeError("BODY_MAX refused: %s aliases %s" % (_ka, _kb))
for _k, _p in _paths[1:]:
    if os.path.islink(_p) or (os.path.exists(_p) and os.stat(_p).st_nlink > 1):
        raise RuntimeError("BODY_MAX refused: %s %s is a symlink or hard link" % (_k, _p))
report = {"ok": False, "max": str(rt.maxVersion()), "objects": {}}
try:
    rt.resetMaxFile(rt.name("noPrompt"))
    if not rt.importFile(cfg["src"], rt.name("noPrompt"), using=rt.FBXIMP):
        raise RuntimeError("FBX import failed")
    t0 = time.perf_counter()
    weld = float(rt.units.decodeValue("1mm"))
    for o in list(rt.objects):
        if rt.superClassOf(o) != rt.GeometryClass or str(o.name).upper().startswith("UCX_"):
            continue
        rt.convertToPoly(o)
        before = [int(rt.polyop.getNumVerts(o)), int(rt.polyop.getNumFaces(o))]
        o.weldThreshold = weld
        rt.polyop.weldVertsByThreshold(o, rt.execute("#{1..%d}" % rt.polyop.getNumVerts(o)))
        rt.polyop.deleteIsoVerts(o)
        rt.addModifier(o, rt.Cap_Holes())
        rt.collapseStack(o)
        rt.convertToPoly(o)
        report["objects"][str(o.name)] = {"before_v_f": before,
                                          "after_v_f": [int(rt.polyop.getNumVerts(o)), int(rt.polyop.getNumFaces(o))]}
    if not report["objects"]:
        raise RuntimeError("no geometry object to clean")
    rt.FBXExporterSetParam("Triangulate", False)
    rt.FBXExporterSetParam("Animation", False)
    if not rt.exportFile(cfg["out"], rt.name("noPrompt"), using=rt.FBXEXP):
        raise RuntimeError("FBX export failed")
    report["wall_time_s"] = round(time.perf_counter() - t0, 3)
    report["weld_system_units"] = weld
    report["system_unit"] = str(rt.units.SystemType)
    report["ok"] = True
except Exception as exc:  # noqa: BLE001 - reported; the driver appends no row
    report["error"] = f"{type(exc).__name__}: {exc}"
with open(cfg["report"], "w", encoding="utf-8") as f:
    json.dump(report, f)
print("BODY_MAX " + json.dumps(report))
