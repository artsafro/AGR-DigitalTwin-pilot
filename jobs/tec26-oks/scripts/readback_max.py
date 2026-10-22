"""Re-import the truba FBX files and run overlap / backface checks.

Runs inside a fresh 3ds Max. Open the untouched scene copy with --scene so the
source mesh can be checked, then reset and import each FBX. Writes the receipt
next to the packages and into jobs/tec26-oks/scripts/qa-receipt.json.

Does not save.

new-case: FBX re-import readback with xView overlap/backface/winding checks.
"""
from __future__ import annotations

import json
import os

import pymxs

rt = pymxs.runtime

HERE = os.path.dirname(os.path.abspath(__file__))
VPM = r"C:/x/tec26-oks/package-vpm/SM_Truba_1/SM_Truba_1.fbx"
UCX = r"C:/x/tec26-oks/package-vpm/UCX_SM_Truba_1_Main.fbx"
NPM = r"C:/x/tec26-oks/package-npm/SM_Truba_1_003_Main.fbx"
OUTS = [
    r"C:/x/tec26-oks/qa-receipt.json",
    os.path.join(HERE, "qa-receipt.json"),
]

HELPERS = r"""
fn agrWorldBox obj = (
    local lo = in coordsys world obj.min
    local hi = in coordsys world obj.max
    #(lo.x, lo.y, lo.z, hi.x, hi.y, hi.z)
)
fn agrDegreeStats obj = (
    local n = polyop.getNumFaces obj
    local quads = 0
    local other = 0
    local tris = 0
    local i
    for i = 1 to n do (
        local d = polyop.getFaceDeg obj i
        tris += d - 2
        if d == 4 then quads += 1 else other += 1
    )
    #(n, quads, other, tris)
)
fn agrOverlap obj = (
    local rv = #()
    local rf = #()
    OverlappingVertices.tolerance = 0.002
    OverlappingFaces.tolerance = 0.005
    local tv = "err"
    local tf = "err"
    local vc = -1
    local fc = -1
    try (
        tv = (OverlappingVertices.Check currentTime obj &rv) as string
        vc = rv.count
    ) catch (
        tv = "failed"
        vc = -1
    )
    try (
        tf = (OverlappingFaces.Check currentTime obj &rf) as string
        fc = rf.count
    ) catch (
        tf = "failed"
        fc = -1
    )
    #(vc, fc, tv, tf)
)
fn agrBackRays obj samples = (
    local m = snapshotAsMesh obj
    local tmp = Editable_mesh name:"AGR_RAY_TMP"
    tmp.mesh = m
    tmp.transform = obj.transform
    local lo = in coordsys world tmp.min
    local hi = in coordsys world tmp.max
    local c = (lo + hi) / 2.0
    local rad = (length (hi - lo)) * 0.75 + 5.0
    local front = 0
    local back = 0
    local miss = 0
    local i
    for i = 1 to samples do (
        local y = 1.0 - (2.0 * ((i - 0.5) / samples))
        local ring = sqrt (amax 0.0 (1.0 - y * y))
        local theta = 137.508 * i
        local dir = normalize [((cos theta) * ring), y, ((sin theta) * ring)]
        local origin = c + (dir * rad)
        local aim = normalize (c - origin)
        local hit = intersectRayEx tmp (ray origin aim)
        if hit == undefined then miss += 1
        else (
            local nrm = getFaceNormal tmp.mesh hit[2]
            if (dot nrm aim) > 0.0 then back += 1 else front += 1
        )
    )
    delete tmp
    delete m
    #(front, back, miss)
)
fn agrEdgeDir verts a b = (
    local n = verts.count
    local k
    for k = 1 to n do (
        local v = verts[k]
        local nxt = if k == n then verts[1] else verts[k + 1]
        if v == a and nxt == b do return 1
        if v == b and nxt == a do return -1
    )
    0
)
fn agrWinding obj = (
    local ne = polyop.getNumEdges obj
    local bad = 0
    local openE = 0
    local multi = 0
    local i
    for i = 1 to ne do (
        local faces = polyop.getEdgeFaces obj i
        if faces.count == 1 then openE += 1
        else if faces.count > 2 then multi += 1
        else if faces.count == 2 do (
            local ev = polyop.getEdgeVerts obj i
            local d1 = agrEdgeDir (polyop.getFaceVerts obj faces[1]) ev[1] ev[2]
            local d2 = agrEdgeDir (polyop.getFaceVerts obj faces[2]) ev[1] ev[2]
            if d1 != 0 and d1 == d2 do bad += 1
        )
    )
    #(bad, openE, multi, ne)
)
fn agrCheckerNames = (
    local n = 0
    local s = ""
    try (n = xViewChecker.getNumCheckers()) catch (return "no-interface")
    local i
    for i = 1 to n do (
        local nm = ""
        try (nm = xViewChecker.getCheckerName i) catch (nm = "?")
        s += nm + "|"
    )
    s
)
fn agrFaceIds obj = (
    if (canConvertTo obj Editable_Poly) == false do return ""
    local n = polyop.getNumFaces obj
    local acc = #()
    local i
    for i = 1 to n do (
        local id = polyop.getFaceMatID obj i
        while acc.count < id do append acc 0
        acc[id] += 1
    )
    local s = ""
    for i = 1 to acc.count where acc[i] > 0 do (
        s += (i as string) + ":" + (acc[i] as string) + ","
    )
    s
)
"""


def _quad(node):
    raw = [float(v) for v in list(rt.agrWorldBox(node))]
    return [round(v, 4) for v in raw]


def _stats(node):
    raw = [int(v) for v in list(rt.agrDegreeStats(node))]
    return {"poly_faces": raw[0], "quads": raw[1], "other": raw[2], "triangles": raw[3]}


def _overlap(node):
    raw = list(rt.agrOverlap(node))
    return {
        "overlapping_vertices_0_002m": int(raw[0]),
        "overlapping_faces_0_005m": int(raw[1]),
        "vertex_result": str(raw[2]),
        "face_result": str(raw[3]),
    }


def _rays(node, samples=96):
    try:
        raw = [int(v) for v in list(rt.agrBackRays(node, samples))]
        return {"samples": samples, "front_first_hit": raw[0], "back_first_hit": raw[1], "miss": raw[2]}
    except Exception as exc:
        return {"samples": samples, "error": str(exc)}


def _as_poly(node):
    """xView and polyop need an Editable Poly. Conversion is on the imported copy only."""
    kind = str(rt.classOf(node))
    if kind == "Editable_Poly":
        return kind
    rt.convertToPoly(node)
    return kind


def _node_info(node, with_checks: bool) -> dict:
    kind = str(rt.classOf(node))
    if kind == "Editable_Poly":
        verts = int(rt.polyop.getNumVerts(node))
        faces = int(rt.polyop.getNumFaces(node))
    else:
        verts = int(rt.getNumVerts(node))
        faces = int(rt.getNumFaces(node))
    info = {
        "name": str(node.name),
        "class": kind,
        "verts": verts,
        "faces_before_convert": faces,
        "material": None if node.material == rt.undefined else str(node.material.name),
        "material_class": None if node.material == rt.undefined else str(rt.classOf(node.material)),
        "bbox": _quad(node),
    }
    if node.material != rt.undefined and rt.isProperty(node.material, "numsubs"):
        info["material_slots"] = int(node.material.numsubs)
    if kind != "Editable_Poly":
        _as_poly(node)
    if str(rt.classOf(node)) == "Editable_Poly":
        info.update(_stats(node))
        info["face_material_ids"] = str(rt.agrFaceIds(node))
    if with_checks and info["verts"]:
        print("CHECK", info["name"], kind)
        info["xview"] = _overlap(node)
        info["backface_rays"] = _rays(node)
        if str(rt.classOf(node)) == "Editable_Poly":
            print("WINDING", info["name"])
            try:
                wind = [int(v) for v in list(rt.agrWinding(node))]
                info["winding"] = {
                    "flipped_edges": wind[0],
                    "open_edges": wind[1],
                    "nonmanifold_edges": wind[2],
                    "edges": wind[3],
                }
            except Exception as exc:
                info["winding"] = {"error": str(exc)}
    return info


def _geos():
    found = []
    for obj in list(rt.objects):
        try:
            if rt.superClassOf(obj) == rt.GeometryClass:
                found.append(obj)
        except Exception:
            continue
    return found


def _import(path: str) -> dict:
    rt.resetMaxFile(rt.Name("noPrompt"))
    rt.units.SystemType = rt.Name("meters")
    rt.FBXImporterSetParam("Mode", rt.Name("create"))
    try:
        rt.FBXImporterSetParam("ConvertUnit", "m")
    except Exception:
        pass
    ok = rt.importFile(path, rt.Name("noPrompt"), using=rt.FBXIMP)
    nodes = []
    for obj in _geos():
        visual = str(obj.name).startswith("SM_")
        nodes.append(_node_info(obj, with_checks=visual))
    return {"path": path, "import_ok": bool(ok), "geometries": nodes}


def main() -> None:
    print("STEP helpers")
    rt.execute(HELPERS)
    source = rt.getNodeByName("Tuba")
    if source == rt.undefined:
        raise RuntimeError("source Tuba missing")
    print("STEP source")
    source_info = _node_info(source, with_checks=True)
    cols = [str(obj.name) for obj in _geos() if str(obj.name).startswith("Col_")]
    checkers = str(rt.agrCheckerNames())
    def _safe(label, path):
        print("STEP", label)
        try:
            return _import(path)
        except Exception as exc:
            print("IMPORT_FAIL", label, exc)
            return {"path": path, "error": str(exc)}

    vpm = _safe("vpm", VPM)
    npm = _safe("npm", NPM)
    ucx = _safe("ucx", UCX)
    payload = {
        "system_units": "meters",
        "xview_tolerances_m": {"vertices": 0.002, "faces": 0.005},
        "xview_checker_names": checkers,
        "source": source_info,
        "source_collision_names": len(cols),
        "vpm": vpm,
        "npm": npm,
        "ucx": ucx,
        "saved": False,
    }
    def _summarize(block):
        geos = block.get("geometries") or []
        visual = [g for g in geos if str(g.get("name", "")).startswith("SM_")]
        hulls = [g for g in geos if str(g.get("name", "")).startswith("UCX_")]
        named = sorted(g["name"] for g in hulls)
        expected = [f"UCX_SM_Truba_1_Main_{i:03d}" for i in range(1, 61)]
        mats = sorted({g.get("material") for g in hulls})
        min_z = min((g["bbox"][2] for g in geos), default=None)
        return {
            "path": block.get("path"),
            "import_ok": block.get("import_ok"),
            "error": block.get("error"),
            "visual": visual,
            "ucx_count": len(hulls),
            "ucx_names_match_001_060": (named == expected) if hulls else "no hulls",
            "ucx_materials": mats,
            "min_z": min_z,
        }

    payload["vpm_summary"] = _summarize(vpm)
    payload["npm_summary"] = _summarize(npm)
    payload["ucx_summary"] = _summarize(ucx)
    full = json.dumps(payload, indent=2)
    os.makedirs(os.path.dirname(OUTS[0]), exist_ok=True)
    with open(OUTS[0], "w", encoding="utf-8") as handle:
        handle.write(full)
    compact = dict(payload)
    for key in ("vpm", "npm", "ucx"):
        compact.pop(key, None)
    with open(OUTS[1], "w", encoding="utf-8") as handle:
        json.dump(compact, handle, indent=2)
    print("READBACK_OK", OUTS[0])
    print("SOURCE_XVIEW", source_info.get("xview"), source_info.get("backface_rays"))


main()
