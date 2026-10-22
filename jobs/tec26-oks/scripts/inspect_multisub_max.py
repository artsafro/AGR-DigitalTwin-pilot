"""Read-only census of Tuba / Material #75 / Col_* in the opened truba scene.

Runs inside 3ds Max (pymxs) via dcc_batch.py. Writes a JSON receipt and does not
save, rename, or export. The opened file is a copy; this script never calls
saveMaxFile or saveNodes.

Usage: dcc_batch.py max --file inspect_multisub_max.py --scene <copy.max>
"""
from __future__ import annotations

import json
import os

import pymxs

rt = pymxs.runtime

OUT = os.environ.get("TEC26_CENSUS_OUT", r"C:/x/tec26-oks/census-multisub.json")

MXS = r"""
fn agrFaceIdCounts obj = (
    local n = polyop.getNumFaces obj
    local acc = #()
    local i
    for i = 1 to n do (
        local id = polyop.getFaceMatID obj i
        while acc.count < id do append acc 0
        acc[id] += 1
    )
    local s = ""
    for i = 1 to acc.count do (
        if acc[i] > 0 do s += (i as string) + ":" + (acc[i] as string) + ","
    )
    s
)
fn agrWorldBox obj = (
    local lo = in coordsys world obj.min
    local hi = in coordsys world obj.max
    #(lo.x, lo.y, lo.z, hi.x, hi.y, hi.z)
)
fn agrCheckerNames = (
    local s = ""
    local n = 0
    try (n = xViewChecker.checkerCount) catch (n = 0)
    local i
    for i = 1 to n do (
        local nm = ""
        try (nm = xViewChecker.getCheckerName i) catch (nm = "?")
        s += (i as string) + "=" + nm + "|"
    )
    s
)
"""


def _undef(value) -> bool:
    if value is None:
        return True
    try:
        return value == rt.undefined
    except Exception:
        return False


def _color(value):
    if _undef(value):
        return None
    try:
        return [int(round(float(value.r))), int(round(float(value.g))), int(round(float(value.b)))]
    except Exception as exc:
        return {"error": str(exc), "repr": str(value)}


def _bitmap(tex):
    if _undef(tex):
        return None
    info = {"class": str(rt.classOf(tex)), "name": None, "filename": None}
    try:
        info["name"] = str(tex.name)
    except Exception as exc:
        info["name_error"] = str(exc)
    for prop in ("filename", "fileName", "HDRIMapName"):
        try:
            if rt.isProperty(tex, prop):
                raw = getattr(tex, prop)
                if not _undef(raw) and str(raw) not in ("", "undefined", "None"):
                    info["filename"] = str(raw)
                    break
        except Exception as exc:
            info["filename_error"] = str(exc)
    return info


def _sub_info(sub, index: int) -> dict:
    if _undef(sub):
        return {"index": index, "empty": True}
    info = {
        "index": index,
        "empty": False,
        "class": str(rt.classOf(sub)),
        "name": str(sub.name),
        "maps": [],
    }
    for prop in ("diffuse", "Diffuse", "base_color", "basecolor", "color"):
        try:
            if rt.isProperty(sub, prop):
                rgb = _color(getattr(sub, prop))
                if rgb is not None:
                    info["diffuse_rgb"] = rgb
                    info["diffuse_prop"] = prop
                    break
        except Exception as exc:
            info.setdefault("color_errors", []).append(f"{prop}: {exc}")
    for prop in (
        "diffuseMap",
        "texmap_diffuse",
        "base_color_map",
        "opacityMap",
        "bumpMap",
        "texmap_bump",
        "reflectionMap",
    ):
        try:
            if not rt.isProperty(sub, prop):
                continue
            tex = getattr(sub, prop)
            if _undef(tex):
                continue
            info["maps"].append({"slot": prop, **(_bitmap(tex) or {})})
        except Exception as exc:
            info["maps"].append({"slot": prop, "error": str(exc)})
    return info


def _list_item(seq, index_1based: int):
    """Return item using both indexing conventions. MaxScript lists are 1-based;
    pymxs arrays are often 0-based. Prefer a defined material."""
    errors = []
    for key in (index_1based - 1, index_1based):
        try:
            return seq[key], key, None
        except Exception as exc:
            errors.append(f"{key}: {exc}")
    return None, None, "; ".join(errors)


def main() -> None:
    rt.execute(MXS)
    tuba = rt.getNodeByName("Tuba")
    if _undef(tuba):
        raise RuntimeError("node Tuba is missing")
    mat = tuba.material
    if _undef(mat):
        raise RuntimeError("Tuba has no material")

    numsubs = int(mat.numsubs) if rt.isProperty(mat, "numsubs") else 0
    slots = []
    id_list = []
    ml = mat.materialList if rt.isProperty(mat, "materialList") else None
    mid = mat.materialIDList if rt.isProperty(mat, "materialIDList") else None
    if ml is not None:
        try:
            ml_len = int(len(ml))
        except Exception:
            ml_len = numsubs
    else:
        ml_len = 0
    count = max(numsubs, ml_len)
    for i in range(1, count + 1):
        sub, used_index, err = (None, None, "no materialList")
        if ml is not None:
            sub, used_index, err = _list_item(ml, i)
        row = _sub_info(sub, i)
        row["pymxs_index"] = used_index
        if err and _undef(sub):
            row["index_error"] = err
        if mid is not None:
            id_item, id_index, id_err = _list_item(mid, i)
            if id_err and _undef(id_item):
                row["material_id_error"] = id_err
            else:
                try:
                    row["material_id"] = int(id_item)
                except Exception:
                    row["material_id"] = str(id_item)
                row["material_id_pymxs_index"] = id_index
            try:
                id_list.append(int(id_item))
            except Exception:
                id_list.append(None)
        slots.append(row)

    face_counts_raw = str(rt.agrFaceIdCounts(tuba))
    face_counts = {}
    if face_counts_raw not in ("", "undefined", "None"):
        for part in face_counts_raw.split(","):
            if not part:
                continue
            ident, count_s = part.split(":")
            face_counts[int(ident)] = int(count_s)

    box = list(rt.agrWorldBox(tuba))
    cols = []
    for obj in rt.objects:
        name = str(obj.name)
        if not name.startswith("Col_"):
            continue
        cbox = list(rt.agrWorldBox(obj))
        cols.append({
            "name": name,
            "class": str(rt.classOf(obj)),
            "layer": str(obj.layer.name) if not _undef(obj.layer) else None,
            "material": None if _undef(obj.material) else str(obj.material.name),
            "verts": int(rt.polyop.getNumVerts(obj)) if rt.canConvertTo(obj, rt.Editable_Poly) else None,
            "faces": int(rt.polyop.getNumFaces(obj)) if rt.canConvertTo(obj, rt.Editable_Poly) else None,
            "min": [round(float(v), 4) for v in cbox[:3]],
            "max": [round(float(v), 4) for v in cbox[3:]],
        })
    cols.sort(key=lambda row: row["name"])

    scene_path = ""
    try:
        scene_path = str(rt.maxFilePath) + str(rt.maxFileName)
    except Exception as exc:
        scene_path = f"unavailable: {exc}"

    payload = {
        "scene": scene_path,
        "system_type": str(rt.units.SystemType),
        "system_scale": float(rt.units.SystemScale),
        "mesh": {
            "name": str(tuba.name),
            "class": str(rt.classOf(tuba)),
            "layer": str(tuba.layer.name) if not _undef(tuba.layer) else None,
            "verts": int(rt.polyop.getNumVerts(tuba)),
            "faces": int(rt.polyop.getNumFaces(tuba)),
            "min": [round(float(v), 4) for v in box[:3]],
            "max": [round(float(v), 4) for v in box[3:]],
        },
        "material": {
            "name": str(mat.name),
            "class": str(rt.classOf(mat)),
            "numsubs": numsubs,
            "material_id_list": id_list,
            "slots": slots,
        },
        "face_material_ids": face_counts,
        "collision": cols,
        "xview_checkers": str(rt.agrCheckerNames()),
        "saved": False,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    print("CENSUS_OK", OUT)
    print("MESH", payload["mesh"]["verts"], payload["mesh"]["faces"], "minz", payload["mesh"]["min"][2])
    print("MAT", payload["material"]["name"], payload["material"]["class"], "subs", numsubs)
    print("FACE_IDS", face_counts_raw)
    print("COLS", len(cols))
    print("XVIEW", payload["xview_checkers"][:500])


main()
