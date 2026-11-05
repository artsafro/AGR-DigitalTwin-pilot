"""new-case: MAF colour-zone apply step. Apply #889 colour-zone material IDs in 3ds Max 2026. Run only via dcc_batch.py.

Reads each showcase FBX, assigns v006 material IDs (the job names the list), exports a new FBX. Vertex and face
counts are checked before the write and again on the node after the assignment. An
output path that is an input is refused and nothing is written. Inputs are not deleted.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

JOB = Path(r"C:\x\889-maf-colour-zones\apply-job.json")
# python.ExecuteFile gives no reliable __file__; the repo is the one that owns the job's ID list
# (<repo>/library/maf/material_ids_vNNN.json), never a hardcoded worktree.
ROOT = Path(json.loads(JOB.read_text(encoding="utf-8"))["ids"]).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "review"))
import maf_colour_zones as zones  # noqa: E402

import pymxs  # noqa: E402

rt = pymxs.runtime
REPORT = Path(r"C:\x\889-maf-colour-zones\applied.json")


def _write_error(message: str, report_path: Path = REPORT) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps({"ok": False, "error": message}, ensure_ascii=False), encoding="utf-8")


def _canon(name: str) -> str:
    text = (name or "").strip()
    if text.startswith("MAF_"):
        text = text[4:]
    return text


def _slot_names(node, mat_ids) -> dict:
    mat = node.material
    if mat is None:
        raise zones.ZoneError("mesh has no material")
    if rt.classOf(mat) == rt.Multimaterial:
        return {int(i): (None if sub is None else str(sub.name))
                for i, sub in zip(mat.materialIDList, mat.materialList)}
    return {mid: str(mat.name) for mid in set(mat_ids)}


def _read(node):
    kind = str(rt.classOf(node))
    if "poly" in kind.lower():
        nv = int(rt.polyOp.getNumVerts(node))
        nf = int(rt.polyOp.getNumFaces(node))
        verts, faces, mats = [], [], []
        for i in range(1, nv + 1):
            point = rt.polyOp.getVert(node, i)
            verts.append((float(point.x), float(point.y), float(point.z)))
        for i in range(1, nf + 1):
            raw = list(rt.polyOp.getFaceVerts(node, i))
            faces.append(tuple(int(v) - 1 for v in raw))
            mats.append(int(rt.polyOp.getFaceMatID(node, i)))
        return kind, verts, faces, mats
    nv = int(rt.getNumVerts(node))
    nf = int(rt.getNumFaces(node))
    verts, faces, mats = [], [], []
    for i in range(1, nv + 1):
        point = rt.getVert(node, i)
        verts.append((float(point.x), float(point.y), float(point.z)))
    for i in range(1, nf + 1):
        face = rt.getFace(node, i)
        faces.append((int(face.x) - 1, int(face.y) - 1, int(face.z) - 1))
        mats.append(int(rt.getFaceMatID(node, i)))
    return kind, verts, faces, mats


def _paint(node, ids, kind: str) -> None:
    if "poly" in kind.lower():
        for index, mid in enumerate(ids, start=1):
            rt.polyOp.setFaceMatID(node, index, int(mid))
        rt.update(node)
        return
    for index, mid in enumerate(ids, start=1):
        rt.setFaceMatID(node, index, int(mid))
    rt.update(node)


def _material(node, ids, colours: dict) -> None:
    used = sorted(set(int(i) for i in ids))
    multi = rt.Multimaterial()
    multi.name = node.name + "_zones"
    id_list = rt.Array()
    sub_list = rt.Array()
    for mid in used:
        hex_colour = colours[mid]
        sub = rt.Standardmaterial()
        sub.name = "ID_%d" % mid
        sub.diffuse = rt.color(int(hex_colour[1:3], 16), int(hex_colour[3:5], 16), int(hex_colour[5:7], 16))
        sub.showInViewport = True
        rt.append(id_list, mid)
        rt.append(sub_list, sub)
    multi.materialIDList = id_list
    multi.materialList = sub_list
    node.material = multi


def _one(path: Path, set_id: str, catalogue: dict, colours: dict, out_path: Path, report_path: Path) -> dict:
    zones.assert_distinct_paths({"input": path, "output": out_path, "report": report_path})
    if out_path.exists():
        raise zones.ZoneError(f"output exists, refusing to overwrite: {out_path}")
    rt.resetMaxFile(rt.Name("noPrompt"))
    rt.units.SystemType = rt.Name("meters")
    rt.units.SystemScale = 1.0
    if not rt.importFile(str(path).replace("\\", "/"), rt.Name("noPrompt"), using=rt.FBXIMP):
        raise zones.ZoneError(f"FBX import failed: {path}")
    geos = [obj for obj in rt.objects if str(rt.superClassOf(obj)) == "GeometryClass"]
    if len(geos) != 1:
        raise zones.ZoneError(f"{set_id}: expected 1 mesh, got {len(geos)}")
    node = geos[0]
    before_verts = int(rt.getNumVerts(node)) if "poly" not in str(rt.classOf(node)).lower() else int(rt.polyOp.getNumVerts(node))
    kind, verts, faces, mat_ids = _read(node)
    if len(verts) != before_verts or not faces:
        raise zones.ZoneError(f"{set_id}: empty mesh")
    names = _slot_names(node, mat_ids)
    # A multimaterial's slot 1 name is enough when every face points at it.
    used_names = []
    for mid in mat_ids:
        if mid not in names or not names[mid]:
            raise zones.ZoneError(f"unmapped material: {mid}")
        slot = _canon(names[mid])
        if slot not in zones.FINISH:
            raise zones.ZoneError(f"unmapped material: {names[mid]}")
        used_names.append(slot)
    if len(set(used_names)) == 1 and set_id in zones.POSITION_POLICY:
        split = zones.split_mesh({"vertices": verts, "faces": faces}, zones.POSITION_POLICY[set_id],
                                  catalogue, fastener_max_share=0.08)
        if split["vertices"] != [tuple(v) for v in verts] or list(split["faces"]) != list(faces):
            raise zones.ZoneError(f"{set_id}: split changed geometry")
        if len(split["material_ids"]) != len(faces):
            raise zones.ZoneError(f"{set_id}: dropped faces")
        ids = split["material_ids"]
        id_to_key = {}
        for entry in catalogue.values():
            if entry["id"] in id_to_key and id_to_key[entry["id"]] != entry["key"]:
                raise zones.ZoneError(f"duplicate material id {entry['id']}")
            id_to_key[entry["id"]] = entry["key"]
        keys = []
        for mid in ids:
            if mid not in id_to_key:
                raise zones.ZoneError(f"unmapped material: {mid}")
            keys.append(id_to_key[mid])
        zone_rows = zones.zone_rows_for_keys(keys, catalogue)
    else:
        ids = [zones.finish_colour(slot, catalogue)["id"] for slot in used_names]
        # Keep slot identity: zone name and colour come from the atlas slot.
        counts = {}
        for slot in used_names:
            counts[slot] = counts.get(slot, 0) + 1
        zone_rows = []
        for slot, count in sorted(counts.items()):
            fin = zones.finish_colour(slot, catalogue)
            zone_rows.append({**fin, "faces": count})
    if sum(row["faces"] for row in zone_rows) != len(faces):
        raise zones.ZoneError(f"{set_id}: dropped faces")
    if any(row["id"] >= zones.UDIM_AS_MATERIAL_ID or row["id"] < 1 for row in zone_rows):
        raise zones.ZoneError(f"{set_id}: material id >= 1001")
    by_id = {}
    for row in zone_rows:
        if row["id"] in by_id and by_id[row["id"]] != row["colour"]:
            raise zones.ZoneError(f"{set_id}: material id {row['id']} has two colours")
        by_id[row["id"]] = row["colour"]
    _paint(node, ids, kind)
    _material(node, ids, by_id)
    node.name = set_id + "_GroundEl"
    after_kind, after_verts, after_faces, _after_mats = _read(node)
    if len(after_verts) != len(verts) or len(after_faces) != len(faces):
        raise zones.ZoneError(f"{set_id}: vertices or faces changed")
    rt.select(node)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not rt.exportFile(str(out_path).replace("\\", "/"), rt.Name("noPrompt"), selectedOnly=True, using=rt.FBXEXP):
        raise zones.ZoneError(f"FBX export failed: {out_path}")
    return {"vertices": len(verts), "faces": len(faces), "vertices_after": len(after_verts),
            "faces_after": len(after_faces), "class": kind, "zones": zone_rows,
            "fbx": out_path.as_posix()}


def main() -> None:
    job = json.loads(JOB.read_text(encoding="utf-8"))
    report_path = Path(job["report"]) if job.get("report") else REPORT
    catalogue = zones.load_id_catalogue(json.loads(Path(job["ids"]).read_text(encoding="utf-8-sig")))
    colours = {entry["id"]: entry["target"] for entry in catalogue.values()}
    for row in zones.FINISH.values():
        colours[catalogue[row["id_key"]]["id"]] = row["colour"]
    colours[catalogue["cap_black"]["id"]] = catalogue["cap_black"]["target"]
    report_in = json.loads(Path(job["set"]).read_text(encoding="utf-8-sig"))
    out_dir = Path(job["out_dir"])
    applied = {"ok": True, "positions": {}}
    rt.pluginManager.loadClass(rt.FBXIMP)
    rt.pluginManager.loadClass(rt.FBXEXP)
    try:
        for pos in report_in["positions"]:
            set_id = pos["set_id"]
            applied["positions"][set_id] = {}
            for prof in ("npm", "vpm"):
                src = Path(pos[prof]["fbx"])
                dest = out_dir / prof / f"{set_id}.fbx"
                print("APPLY", set_id, prof, flush=True)
                applied["positions"][set_id][prof] = _one(src, set_id, catalogue, colours, dest, report_path)
        # One ID, one colour across every node of the set (#993); fail before the report is written.
        zones.check_id_colours((f"{sid}/{prof}", zone["id"], zone["colour"])
                               for sid, profs in applied["positions"].items()
                               for prof, info in profs.items() for zone in info["zones"])
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(applied, ensure_ascii=False, indent=1), encoding="utf-8")
        print("APPLIED", report_path, flush=True)
    except Exception as exc:
        _write_error(str(exc), report_path)
        raise


if __name__ == "__main__":
    main()
