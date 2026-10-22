"""Rename the truba mesh and UCX, assign VPM/NPM materials, export FBX packages.

Runs inside 3ds Max (pymxs). The scene opened by dcc_batch is a copy. This
script saves only to a new .max under C:/x/tec26-oks/max-v001/ and exports only
to new paths under package-vpm and package-npm. It does not move or delete
geometry. Face ids are renumbered to the export slots in multisub-map.json.

UCX hulls are renamed and exported inside the VPM FBX (ucx.md R05, KPP) and
again as a separate UCX FBX. The VPM zip contains the visual FBX (UCX included),
the external PNGs and a manifest. The NPM FBX has no UCX.

Usage: dcc_batch.py max --file export_package_max.py --scene <copy.max>

new-case: rename + assign VPM/NPM materials + export FBX packages with UCX from a laid-out Max scene.
"""
from __future__ import annotations

import json
import os
import shutil
import zipfile

import pymxs

rt = pymxs.runtime

HERE = os.path.dirname(os.path.abspath(__file__))
MAP_PATH = os.path.join(HERE, "multisub-map.json")
MAT_PATH = os.path.join(HERE, "..", "materials.json")
TEX_DIR = os.environ.get("TEC26_TEX", r"C:/x/tec26-oks/textures-v001")
VPM_DIR = os.environ.get("TEC26_VPM", r"C:/x/tec26-oks/package-vpm/SM_Truba_1")
UCX_FBX = os.environ.get("TEC26_UCX", r"C:/x/tec26-oks/package-vpm/UCX_SM_Truba_1_Main.fbx")
NPM_DIR = os.environ.get("TEC26_NPM", r"C:/x/tec26-oks/package-npm")
MAX_OUT = os.environ.get("TEC26_MAX", r"C:/x/tec26-oks/max-v001/truba_named.max")
RENDER_DIR = os.environ.get("TEC26_RENDERS", r"C:/x/tec26-oks/renders")
RECEIPT = os.environ.get("TEC26_EXPORT_RECEIPT", r"C:/x/tec26-oks/export-receipt.json")

MESH_VPM = "SM_Truba_1_Main"
MESH_NPM = "SM_Truba_1_003_Main"
MAT_VPM = "M_Truba_1_Main_1"
MAT_NPM = "M_Truba_1_003_Main_1"
SRC_MESH = "Tuba"

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
fn agrRemapFaces obj known = (
    local n = polyop.getNumFaces obj
    local bad = #()
    local i
    for i = 1 to n do (
        local id = polyop.getFaceMatID obj i
        if (findItem known id) == 0 do appendIfUnique bad id
    )
    if bad.count != 0 do return bad
    for i = 1 to n do (
        polyop.setFaceMatID obj i (agrApplySlot (polyop.getFaceMatID obj i))
    )
    #()
)
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
    for i = 1 to acc.count where acc[i] > 0 do (
        s += (i as string) + ":" + (acc[i] as string) + ","
    )
    s
)
fn agrCloneNamed src newName = (
    local dup = copy src
    dup.name = newName
    dup
)
fn agrSelect arr = (
    select arr
    selection.count
)
fn agrZeroBar = (
    local b = Box length:0.12 width:72 height:0.08
    b.name = "ZERO_000"
    b.pos = [-23, 0, 0]
    local lo = in coordsys world b.min
    local hi = in coordsys world b.max
    b.pos.z = b.pos.z - ((lo.z + hi.z) / 2.0)
    local m = Standardmaterial()
    m.name = "M_Zero_000"
    m.diffuse = color 220 30 30
    m.twoSided = true
    b.material = m
    b
)
fn agrRender cam path = (
    render camera:cam outputfile:path outputSize:[1280,960] vfb:off progressbar:false
    doesFileExist path
)
fn agrMakeCam name px py pz tx ty tz = (
    local cam = Targetcamera pos:[px,py,pz] name:name fov:40
    if cam.target == undefined then cam.target = Targetobject pos:[tx,ty,tz]
    else cam.target.pos = [tx,ty,tz]
    cam
)
fn agrMakeLights cx cy cz = (
    local key = Target_Direct pos:[cx+40,cy-50,cz+60] name:"Key_Preview" multiplier:1.3
    if key.target == undefined then key.target = Targetobject pos:[cx,cy,cz]
    else key.target.pos = [cx,cy,cz]
    local fill = undefined
    try (fill = Omnilight pos:[cx-30,cy+40,cz+10] name:"Fill_Preview" multiplier:0.45) catch ()
    if fill == undefined do fill = OmniLight pos:[cx-30,cy+40,cz+10] name:"Fill_Preview" multiplier:0.45
    fill
)
"""


def _box(node):
    raw = list(rt.agrWorldBox(node))
    return [round(float(v), 4) for v in raw]


def _assert_new(path: str, opened: str) -> None:
    dest = os.path.normcase(os.path.abspath(path))
    src = os.path.normcase(os.path.abspath(opened)) if opened else ""
    original = os.path.normcase(r"C:\Users\artsafro\Desktop\!3D viz\Dima_Andrew\2_kotelnya\Vlad_OKS\truba.max")
    copy = os.path.normcase(r"C:\x\tec26-oks\max-copy\truba.max")
    if dest in {src, original, copy}:
        raise RuntimeError(f"refusing to write over a source: {path}")


def _bitmap(path: str, alpha_source: int | None, notes: list):
    """alpha_source: 0 image alpha, 1 RGB intensity, 2 none. None leaves the default."""
    bmp = rt.Bitmaptexture()
    bmp.name = os.path.splitext(os.path.basename(path))[0]
    bmp.filename = path.replace("\\", "/")
    if alpha_source is not None:
        try:
            bmp.alphaSource = int(alpha_source)
        except Exception as exc:
            notes.append(f"alphaSource {alpha_source} on {bmp.name}: {exc}")
    return bmp


def _channel(bmp, channel: int, notes: list):
    """Mono Color_Correction of one bitmap channel. channel 0 red, 1 green, 2 blue."""
    cc = rt.Color_Correction()
    cc.name = f"{bmp.name}_c{channel}"
    try:
        cc.map = bmp
    except Exception as exc:
        notes.append(f"color map: {exc}")
    for prop, value in (
        ("rewireMode", 1),
        ("rewireR", channel),
        ("rewireG", channel),
        ("rewireB", channel),
    ):
        try:
            setattr(cc, prop, value)
        except Exception as exc:
            notes.append(f"{cc.name}.{prop}: {exc}")
    return cc


def _standard(name: str, notes: list) -> object:
    mat = rt.Standardmaterial()
    mat.name = name
    mat.twoSided = False
    return mat


def _assign_vpm(spec: dict, row: dict, notes: list):
    finish = spec["finishes"][row["finish"]]
    udim = int(finish["udim"])
    diffuse = os.path.join(TEX_DIR, f"T_Truba_1_Diffuse_1.{udim}.png")
    erm = os.path.join(TEX_DIR, f"T_Truba_1_ERM_1.{udim}.png")
    normal = os.path.join(TEX_DIR, f"T_Truba_1_Normal_1.{udim}.png")
    for path in (diffuse, erm, normal):
        if not os.path.isfile(path):
            raise RuntimeError(f"missing VPM map: {path}")
    # Point the exported material at the package copies, written before export.
    diffuse_out = os.path.join(VPM_DIR, os.path.basename(diffuse))
    erm_out = os.path.join(VPM_DIR, os.path.basename(erm))
    normal_out = os.path.join(VPM_DIR, os.path.basename(normal))
    mat = _standard(f"{MAT_VPM}_{row['finish']}", notes)
    alpha = 0 if row["finish"] == "Railing_Steel" else 2
    diff_bmp = _bitmap(diffuse_out, alpha, notes)
    mat.diffuseMap = diff_bmp
    mat.diffuseMapEnable = True
    erm_bmp = _bitmap(erm_out, None, notes)
    try:
        mat.glossinessMap = _channel(erm_bmp, 1, notes)
        mat.glossinessMapEnable = True
        mat.specularLevelMap = _channel(erm_bmp, 2, notes)
        mat.specularLevelMapEnable = True
    except Exception as exc:
        notes.append(f"ERM slots {row['finish']}: {exc}")
    bump = rt.Normal_Bump()
    bump.name = f"N_{row['finish']}"
    bump.normal_map = _bitmap(normal_out, None, notes)
    mat.bumpMap = bump
    mat.bumpMapEnable = True
    if row["finish"] == "Railing_Steel":
        mat.opacityMap = diff_bmp
        mat.opacityMapEnable = True
        mat.twoSided = True
    return mat


def _assign_npm(spec: dict, row: dict, notes: list):
    finish = spec["finishes"][row["finish"]]
    slot = int(finish["slot"])
    stem = f"T_Truba_1_003_Main"
    paths = {suffix: os.path.join(TEX_DIR, f"{stem}_{suffix}_{slot}.png") for suffix in ("d", "r", "m", "o")}
    for path in paths.values():
        if not os.path.isfile(path):
            raise RuntimeError(f"missing NPM map: {path}")
    outs = {suffix: os.path.join(NPM_DIR, os.path.basename(path)) for suffix, path in paths.items()}
    mat = _standard(f"{MAT_NPM}_{row['finish']}", notes)
    diff = _bitmap(outs["d"], 2, notes)
    mat.diffuseMap = diff
    mat.diffuseMapEnable = True
    mat.glossinessMap = _bitmap(outs["r"], 1, notes)
    mat.glossinessMapEnable = True
    mat.specularLevelMap = _bitmap(outs["m"], 1, notes)
    mat.specularLevelMapEnable = True
    mat.opacityMap = _bitmap(outs["o"], 1, notes)
    mat.opacityMapEnable = True
    if row["finish"] == "Railing_Steel":
        mat.twoSided = True
    return mat


def _multi(name: str, subs: list):
    multi = rt.Multimaterial()
    multi.name = name
    multi.numsubs = len(subs)
    for index, sub in enumerate(subs):
        multi.materialList[index] = sub
        try:
            multi.materialIDList[index] = index + 1
        except Exception:
            pass
    return multi


def _copy_maps(names: list[str], dest: str) -> None:
    os.makedirs(dest, exist_ok=True)
    for name in names:
        src = os.path.join(TEX_DIR, name)
        if not os.path.isfile(src):
            raise RuntimeError(f"missing texture: {src}")
        shutil.copy2(src, os.path.join(dest, name))


def _fbx_params(embed: bool) -> None:
    rt.FBXExporterSetParam("Animation", False)
    rt.FBXExporterSetParam("Cameras", False)
    rt.FBXExporterSetParam("Lights", False)
    rt.FBXExporterSetParam("EmbedTextures", embed)
    rt.FBXExporterSetParam("ASCII", False)
    rt.FBXExporterSetParam("FileVersion", "FBX201400")
    rt.FBXExporterSetParam("UpAxis", "Z")
    rt.FBXExporterSetParam("SmoothingGroups", True)
    rt.FBXExporterSetParam("Triangulate", False)
    try:
        rt.FBXExporterSetParam("Shapes", False)
    except Exception:
        pass
    try:
        rt.FBXExporterSetParam("ConvertUnit", "m")
    except Exception:
        pass


def _export(nodes, path: str, embed: bool) -> int:
    _fbx_params(embed)
    arr = rt.Array()
    for node in nodes:
        rt.append(arr, node)
    selected = int(rt.agrSelect(arr))
    if selected != len(nodes):
        raise RuntimeError(f"selection {selected} != {len(nodes)} for {path}")
    ok = rt.exportFile(path, rt.Name("noPrompt"), selectedOnly=True, using=rt.FBXEXP)
    rt.clearSelection()
    if not ok or not os.path.isfile(path) or os.path.getsize(path) < 1000:
        raise RuntimeError(f"FBX export failed: {path} ok={ok}")
    return os.path.getsize(path)


def _zip(folder: str, zip_path: str, names: list[str]) -> None:
    if os.path.exists(zip_path):
        os.remove(zip_path)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as handle:
        for name in names:
            handle.write(os.path.join(folder, name), arcname=name)


def _parse_counts(raw: str) -> dict:
    counts = {}
    for part in str(raw).split(","):
        if not part:
            continue
        ident, count = part.split(":")
        counts[int(ident)] = int(count)
    return counts


def _look_camera(name: str, position, target):
    cam = rt.agrMakeCam(
        name,
        float(position[0]), float(position[1]), float(position[2]),
        float(target[0]), float(target[1]), float(target[2]),
    )
    if cam is None or cam == rt.undefined:
        raise RuntimeError(f"camera was not created: {name}")
    return cam


def main() -> None:
    print("STEP helpers")
    rt.execute(HELPERS)
    print("STEP helpers_ok")
    mapping = json.loads(open(MAP_PATH, encoding="utf-8").read())
    spec = json.loads(open(MAT_PATH, encoding="utf-8").read())
    rows = sorted(mapping["mapping"], key=lambda row: int(row["export_slot"]))
    if [int(row["export_slot"]) for row in rows] != [1, 2, 3, 4, 5, 6]:
        raise RuntimeError("export slots are not 1..6")
    if mapping["unmapped"]:
        raise RuntimeError(f"unmapped slots: {mapping['unmapped']}")
    finishes = {row["finish"] for row in rows}
    if finishes != set(spec["finishes"]):
        missing = sorted(set(spec["finishes"]) - finishes)
        raise RuntimeError(f"finish not in the map: {missing}")

    case_lines = "\n".join(
        f"        {int(row['source_mat_id'])}: {int(row['export_slot'])}" for row in rows
    )
    known_ids = ", ".join(str(int(row["source_mat_id"])) for row in rows)

    opened = str(rt.maxFilePath) + str(rt.maxFileName)
    if str(rt.units.SystemType) != "meters":
        raise RuntimeError(f"system units are {rt.units.SystemType}, expected meters")
    for path in (VPM_DIR, NPM_DIR, os.path.dirname(MAX_OUT), RENDER_DIR, os.path.dirname(UCX_FBX)):
        os.makedirs(path, exist_ok=True)
    for path in (
        os.path.join(VPM_DIR, "SM_Truba_1.fbx"),
        UCX_FBX,
        os.path.join(NPM_DIR, "SM_Truba_1_003_Main.fbx"),
        MAX_OUT,
    ):
        _assert_new(path, opened)

    mesh = rt.getNodeByName(SRC_MESH)
    if mesh == rt.undefined:
        raise RuntimeError("Tuba missing")
    degrees = [int(v) for v in list(rt.agrDegreeStats(mesh))]
    before_box = _box(mesh)

    others = []
    cols = []
    for obj in list(rt.objects):
        name = str(obj.name)
        if name == SRC_MESH:
            continue
        if name.startswith("Col_"):
            cols.append(obj)
        else:
            others.append(name)
    cols_by_name = {str(obj.name): obj for obj in cols}
    expected = [f"Col_{index:03d}" for index in range(1, 61)]
    if sorted(cols_by_name) != expected:
        raise RuntimeError(f"collision names {sorted(cols_by_name)} != Col_001..Col_060")

    print("STEP remap")
    remap_result = rt.execute(
        "fn agrApplySlot id = (\n"
        "    case id of (\n"
        f"{case_lines}\n"
        "        default: 0\n"
        "    )\n"
        ")\n"
        "fn agrRemapNow obj = (\n"
        f"    local knownIds = #({known_ids})\n"
        "    local n = polyop.getNumFaces obj\n"
        "    local bad = \"\"\n"
        "    local seen = #()\n"
        "    local i\n"
        "    for i = 1 to n do (\n"
        "        local id = polyop.getFaceMatID obj i\n"
        "        if (findItem knownIds id) == 0 and (findItem seen id) == 0 do (\n"
        "            append seen id\n"
        "            bad += (id as string) + \",\"\n"
        "        )\n"
        "    )\n"
        "    if bad != \"\" do return bad\n"
        "    for i = 1 to n do (\n"
        "        local nid = agrApplySlot (polyop.getFaceMatID obj i)\n"
        "        if nid == 0 do return \"zero\"\n"
        "        polyop.setFaceMatID obj i nid\n"
        "    )\n"
        "    \"ok\"\n"
        ")\n"
        "agrRemapNow $Tuba\n"
    )
    if str(remap_result) != "ok":
        raise RuntimeError(f"unmapped face material ids: {remap_result}")
    counts = _parse_counts(rt.agrFaceIdCounts(mesh))
    expected_counts = {int(row["export_slot"]): int(row["faces"]) for row in rows}
    if counts != expected_counts:
        raise RuntimeError(f"face ids {counts} != {expected_counts}")

    mesh.name = MESH_VPM
    ucx_nodes = []
    for index in range(1, 61):
        node = cols_by_name[f"Col_{index:03d}"]
        node.name = f"UCX_SM_Truba_1_Main_{index:03d}"
        ucx_nodes.append(node)

    vpm_names = []
    for row in rows:
        udim = int(spec["finishes"][row["finish"]]["udim"])
        for kind in ("Diffuse", "ERM", "Normal"):
            vpm_names.append(f"T_Truba_1_{kind}_1.{udim}.png")
    npm_names = []
    for row in rows:
        slot = int(spec["finishes"][row["finish"]]["slot"])
        for suffix in ("d", "r", "m", "o"):
            npm_names.append(f"T_Truba_1_003_Main_{suffix}_{slot}.png")
    _copy_maps(vpm_names, VPM_DIR)
    _copy_maps(npm_names, NPM_DIR)

    print("STEP materials")
    notes: list[str] = []
    vpm_subs = [_assign_vpm(spec, row, notes) for row in rows]
    npm_subs = [_assign_npm(spec, row, notes) for row in rows]
    vpm_mat = _multi(MAT_VPM, vpm_subs)
    npm_mat = _multi(MAT_NPM, npm_subs)
    mesh.material = vpm_mat
    npm = rt.agrCloneNamed(mesh, MESH_NPM)
    npm.material = npm_mat

    mesh_box = _box(mesh)
    npm_box = _box(npm)
    if mesh_box[2] >= -1.0 or npm_box[2] >= -1.0:
        raise RuntimeError(f"perimeter drop lost: {mesh_box[2]} {npm_box[2]}")
    if abs(mesh_box[2] - before_box[2]) > 0.005:
        raise RuntimeError(f"min z moved from {before_box[2]} to {mesh_box[2]}")

    print("STEP save")
    rt.saveMaxFile(MAX_OUT, quiet=True)
    if not os.path.isfile(MAX_OUT):
        raise RuntimeError(f"save failed: {MAX_OUT}")

    vpm_fbx = os.path.join(VPM_DIR, "SM_Truba_1.fbx")
    npm_fbx = os.path.join(NPM_DIR, "SM_Truba_1_003_Main.fbx")
    # NPM copy is coincident. Export selection is explicit, so it stays out of the VPM file.
    print("STEP export")
    vpm_bytes = _export([mesh, *ucx_nodes], vpm_fbx, embed=False)
    ucx_bytes = _export(ucx_nodes, UCX_FBX, embed=False)
    npm_bytes = _export([npm], npm_fbx, embed=True)

    manifest_vpm = {
        "profile": "VPM",
        "fbx": "SM_Truba_1.fbx",
        "mesh": MESH_VPM,
        "material": MAT_VPM,
        "ucx_in_fbx": True,
        "ucx_reason": "ucx.md R05: a non-lighting VPM FBX carries its UCX. Separate UCX FBX is a sibling, not a zip member.",
        "separate_ucx": os.path.basename(UCX_FBX),
        "maps": vpm_names,
        "bbox_min": mesh_box[:3],
        "bbox_max": mesh_box[3:],
        "finishes": mapping["export_slots"],
        "empty_source_slots": mapping["empty"],
        "quads_preserved": True,
        "geojson": "not in this package",
    }
    manifest_npm = {
        "profile": "NPM",
        "fbx": "SM_Truba_1_003_Main.fbx",
        "mesh": MESH_NPM,
        "material": MAT_NPM,
        "ucx_in_fbx": False,
        "maps": npm_names,
        "no_normal": True,
        "bbox_min": npm_box[:3],
        "bbox_max": npm_box[3:],
        "finishes": mapping["export_slots"],
        "quads_preserved": True,
    }
    with open(os.path.join(VPM_DIR, "manifest.json"), "w", encoding="utf-8") as handle:
        json.dump(manifest_vpm, handle, indent=2)
    with open(os.path.join(NPM_DIR, "manifest.json"), "w", encoding="utf-8") as handle:
        json.dump(manifest_npm, handle, indent=2)
    vpm_zip = r"C:/x/tec26-oks/package-vpm/SM_Truba_1.zip"
    npm_zip = r"C:/x/tec26-oks/package-npm/SM_Truba_1_003_Main.zip"
    _assert_new(vpm_zip, opened)
    _assert_new(npm_zip, opened)
    _zip(VPM_DIR, vpm_zip, ["SM_Truba_1.fbx", "manifest.json", *vpm_names])
    _zip(NPM_DIR, npm_zip, ["SM_Truba_1_003_Main.fbx", "manifest.json", *npm_names])

    render_notes = []
    renders = {}
    try:
        rt.renderers.current = rt.Default_Scanline_Renderer()
        for node in ucx_nodes:
            node.isHidden = True
            node.renderable = False
        npm.isHidden = True
        npm.renderable = False
        zero = rt.agrZeroBar()
        zero_box = _box(zero)
        centre = (
            (mesh_box[0] + mesh_box[3]) / 2,
            (mesh_box[1] + mesh_box[4]) / 2,
            (mesh_box[2] + mesh_box[5]) / 2,
        )
        cam_34 = _look_camera("Cam_34", (centre[0] + 70, centre[1] - 90, centre[2] + 40), centre)
        cam_side = _look_camera("Cam_side", (centre[0], centre[1] - 110, centre[2]), centre)
        rt.agrMakeLights(float(centre[0]), float(centre[1]), float(centre[2]))
        clay = rt.Standardmaterial()
        clay.name = "M_Preview_Clay"
        clay.diffuse = rt.Color(190, 190, 190)
        mesh.material = clay
        shaded = os.path.join(RENDER_DIR, "truba_shaded.png").replace("\\", "/")
        renders["shaded"] = bool(rt.agrRender(cam_34, shaded))
        mesh.material = vpm_mat
        for sub in vpm_subs:
            try:
                sub.glossinessMapEnable = False
                sub.specularLevelMapEnable = False
                sub.bumpMapEnable = False
            except Exception as exc:
                render_notes.append(str(exc))
        finishes_path = os.path.join(RENDER_DIR, "truba_finishes.png").replace("\\", "/")
        base_path = os.path.join(RENDER_DIR, "truba_finishes_base.png").replace("\\", "/")
        renders["finishes"] = bool(rt.agrRender(cam_34, finishes_path))
        renders["finishes_base"] = bool(rt.agrRender(cam_side, base_path))
        renders["zero_bbox"] = zero_box
    except Exception as exc:
        render_notes.append(f"render failed: {exc}")

    receipt = {
        "opened_scene": opened,
        "saved_max": MAX_OUT,
        "other_objects_left_unexported": others,
        "degrees": {"faces": degrees[0], "quads": degrees[1], "other": degrees[2], "triangles": degrees[3]},
        "bbox_before": before_box,
        "bbox_vpm": mesh_box,
        "bbox_npm": npm_box,
        "face_ids_after_remap": counts,
        "material_notes": notes[:40],
        "material_note_count": len(notes),
        "fbx": {
            "vpm": {"path": vpm_fbx, "bytes": vpm_bytes, "ucx_embedded": 60},
            "ucx": {"path": UCX_FBX, "bytes": ucx_bytes, "hulls": 60},
            "npm": {"path": npm_fbx, "bytes": npm_bytes, "ucx_embedded": 0},
        },
        "zips": {"vpm": vpm_zip, "npm": npm_zip},
        "renders": renders,
        "render_notes": render_notes,
        "min_z_below_minus_1m": mesh_box[2] < -1.0 and npm_box[2] < -1.0,
    }
    os.makedirs(os.path.dirname(RECEIPT), exist_ok=True)
    with open(RECEIPT, "w", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=2)
    print("EXPORT_OK", vpm_bytes, ucx_bytes, npm_bytes)
    print("BBOX_Z", mesh_box[2], npm_box[2])
    print("TRIS", degrees[3], "QUADS", degrees[1], "OTHER", degrees[2])
    print("RENDERS", renders)
    print("NOTES", len(notes), (notes[:8] if notes else ""))
    if render_notes:
        print("RENDER_NOTES", render_notes)


main()
