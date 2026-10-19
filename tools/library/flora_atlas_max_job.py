"""Headless 3ds Max 2026 job: one Flora atlas on a copy of a placed scene.

Run:
  python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --file tools/library/flora_atlas_max_job.py

The original scene file is hashed before and after. The edited scene is saved as a new
file next to that copy. Atlas packing is the repo tool (uv), not a second packer.

AGR_FLORA_SCENE       scene copy to create (synth) or load
AGR_FLORA_SCENE_OUT   new .max path (default: <scene stem>-flora-atlas.max beside the copy)
AGR_FLORA_CATALOGUE   flora-library-v1 JSON
AGR_FLORA_OUT_DIR     atlas PNG + report directory (outside the repo, under C:/x)
AGR_FLORA_ADDRESS     address token, e.g. SYNTH
AGR_FLORA_REPO        repository root
AGR_UV                uv executable
AGR_FLORA_RESULT      JSON receipt path
AGR_FLORA_SYNTH       "1" builds a synthetic quad per catalogue species, then atlases it
AGR_FLORA_MIN_TILE    optional longer-side warning threshold
"""

import hashlib
import json
import math
import os
import subprocess
import sys


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def max_path(path):
    return os.path.abspath(path).replace("\\", "/")


def path_keys(path):
    text = os.fspath(path)
    keys = {os.path.normcase(os.path.normpath(os.path.abspath(text)))}
    try:
        keys.add(os.path.normcase(os.path.normpath(os.path.realpath(text))))
    except OSError:
        pass
    return keys


def paths_alias(left, right):
    if path_keys(left) & path_keys(right):
        return True
    if os.path.lexists(left) and os.path.lexists(right):
        try:
            return os.path.samefile(left, right)
        except OSError:
            return False
    return False


def _require_env(env, name):
    value = env.get(name, "").strip()
    if not value:
        raise RuntimeError("missing " + name)
    return value


def preflight_job(env):
    """Resolve every Max-job path and refuse aliases before any file is created."""

    scene = _require_env(env, "AGR_FLORA_SCENE")
    catalogue = _require_env(env, "AGR_FLORA_CATALOGUE")
    out_dir = _require_env(env, "AGR_FLORA_OUT_DIR")
    address = _require_env(env, "AGR_FLORA_ADDRESS")
    repo = _require_env(env, "AGR_FLORA_REPO")
    uv = _require_env(env, "AGR_UV")
    result = _require_env(env, "AGR_FLORA_RESULT")
    scene_out = env.get("AGR_FLORA_SCENE_OUT", "").strip()
    if not scene_out:
        stem, _ext = os.path.splitext(scene)
        scene_out = stem + "-flora-atlas.max"
    if not address or any(not (ch.isalnum() or ch == "_") for ch in address):
        raise RuntimeError("refusing to write; address is unsupported")
    synth = env.get("AGR_FLORA_SYNTH", "").strip() == "1"
    writes = [
        scene_out,
        result,
        os.path.join(out_dir, "placed-scene.json"),
        os.path.join(out_dir, "flora-atlas.json"),
        os.path.join(out_dir, "T_%s_Flora_d_1.png" % address),
        os.path.join(out_dir, "T_%s_Flora_o_1.png" % address),
    ]
    if synth:
        writes.append(scene)
    if os.path.lexists(out_dir) and not os.path.isdir(out_dir):
        raise RuntimeError("refusing to write %s; it resolves to %s" % (out_dir, out_dir))
    protected = [catalogue, uv]
    if not synth or os.path.lexists(scene):
        protected.append(scene)
    if os.path.lexists(scene_out):
        protected.append(scene_out)
    _refuse_aliased_writes(writes, protected)
    return {
        "scene": scene,
        "scene_out": scene_out,
        "catalogue": catalogue,
        "out_dir": out_dir,
        "address": address,
        "repo": repo,
        "uv": uv,
        "result": result,
        "synth": synth,
    }


def _refuse_aliased_writes(writes, protected):
    for index, left in enumerate(writes):
        for right in writes[index + 1:]:
            if paths_alias(left, right):
                raise RuntimeError("refusing to write %s; it resolves to %s" % (left, right))
        for source in protected:
            if paths_alias(left, source):
                raise RuntimeError("refusing to write %s; it resolves to %s" % (left, source))


def reject_unsupported_uvs(inventory):
    """Refuse UVs outside 0..1 before the job creates a directory or saves a scene."""

    if not isinstance(inventory, dict):
        raise RuntimeError("unsupported scene inventory")
    objects = inventory.get("objects")
    if not isinstance(objects, list) or not objects:
        raise RuntimeError("unsupported scene inventory")
    for obj in objects:
        if not isinstance(obj, dict):
            raise RuntimeError("unsupported scene inventory")
        faces = obj.get("faces")
        if not isinstance(faces, list) or not faces:
            raise RuntimeError("unsupported scene inventory")
        for face in faces:
            if not isinstance(face, dict):
                raise RuntimeError("unsupported scene inventory")
            uvs = face.get("uvs")
            if not isinstance(uvs, list) or len(uvs) < 3:
                raise RuntimeError("unsupported UV")
            for pair in uvs:
                if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                    raise RuntimeError("unsupported UV %s" % (pair,))
                u, v = pair[0], pair[1]
                if (
                    isinstance(u, bool) or isinstance(v, bool)
                    or not isinstance(u, (int, float)) or not isinstance(v, (int, float))
                    or not math.isfinite(float(u)) or not math.isfinite(float(v))
                    or u < 0 or u > 1 or v < 0 or v > 1
                ):
                    raise RuntimeError("unsupported UV %s" % (pair,))


def main():
    plan = preflight_job(os.environ)
    from pymxs import runtime as rt

    scene = plan["scene"]
    catalogue_path = plan["catalogue"]
    out_dir = plan["out_dir"]
    address = plan["address"]
    repo = plan["repo"]
    uv = plan["uv"]
    result_path = plan["result"]
    scene_out = plan["scene_out"]
    catalogue = json.loads(open(catalogue_path, encoding="utf-8").read())
    if plan["synth"]:
        rt.resetMaxFile(rt.Name("noPrompt"))
        nodes = build_synth(rt, catalogue)
        if not rt.saveMaxFile(max_path(scene), quiet=True):
            raise RuntimeError("failed to save the synthetic scene copy")
    else:
        if not rt.loadMaxFile(max_path(scene), quiet=True, useFileUnits=True):
            raise RuntimeError("cannot load " + scene)
        nodes = flora_nodes(rt)
    before = sha256_file(scene)
    inventory = dump_scene(rt, nodes)
    reject_unsupported_uvs(inventory)
    os.makedirs(out_dir, exist_ok=True)
    inventory_path = os.path.join(out_dir, "placed-scene.json")
    with open(inventory_path, "w", encoding="utf-8") as handle:
        json.dump(inventory, handle)
    report = pack(uv, repo, inventory_path, catalogue_path, out_dir, address, scene)
    apply_atlas(rt, nodes, report)
    if not rt.saveMaxFile(max_path(scene_out), quiet=True):
        raise RuntimeError("failed to save the atlas scene")
    after = sha256_file(scene)
    if before != after:
        raise RuntimeError("scene copy hash changed")
    checked = read_back(rt, scene_out, report)
    receipt = {
        "species_count": report["species_count"],
        "fill_percent": report["fill_percent"],
        "scale_factor": report["scale_factor"],
        "atlas_count": report["atlas_count"],
        "atlas_size": report["atlas_size"],
        "warnings": report["warnings"],
        "scene_sha256_before": before,
        "scene_sha256_after": after,
        "scene": max_path(scene),
        "scene_out": max_path(scene_out),
        "material_name": report["material"]["name"],
        "material_ids": checked["material_ids"],
        "uv_ok": checked["uv_ok"],
        "one_material": checked["one_material"],
    }
    with open(result_path, "w", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=2)
    print(
        "AGR_FLORA_OK species=%d scale=%s fill=%.4f"
        % (receipt["species_count"], receipt["scale_factor"], receipt["fill_percent"])
    )


def build_synth(rt, catalogue):
    nodes = []
    for index, species in enumerate(catalogue["species"]):
        material_id = int(species["material_id"])
        name = "flora_%d" % material_id
        x = index * 4
        rt.execute("""
global agrNode = mesh numverts:4 numfaces:2
setVert agrNode 1 [-1,-1,0]
setVert agrNode 2 [1,-1,0]
setVert agrNode 3 [1,1,0]
setVert agrNode 4 [-1,1,0]
setFace agrNode 1 1 2 3
setFace agrNode 2 1 3 4
meshop.setMapSupport agrNode 1 true
meshop.setNumMapVerts agrNode 1 4 keep:false
meshop.setMapVert agrNode 1 1 [0,0,0]
meshop.setMapVert agrNode 1 2 [1,0,0]
meshop.setMapVert agrNode 1 3 [1,1,0]
meshop.setMapVert agrNode 1 4 [0,1,0]
meshop.setMapFace agrNode 1 1 [1,2,3]
meshop.setMapFace agrNode 1 2 [1,3,4]
setFaceMatID agrNode 1 %d
setFaceMatID agrNode 2 %d
update agrNode
agrNode.name = "%s"
agrNode.pos = [%d,0,0]
""" % (material_id, material_id, name, x))
        node = rt.getNodeByName(name)
        if node is None or node == rt.undefined:
            raise RuntimeError("synthetic node was not created: " + name)
        nodes.append(node)
    if not nodes:
        raise RuntimeError("catalogue has no species")
    return nodes


def flora_nodes(rt):
    nodes = []
    for node in list(rt.objects):
        if str(rt.superClassOf(node)) != "GeometryClass":
            continue
        if not rt.canConvertTo(node, rt.Mesh):
            continue
        nodes.append(node)
    if not nodes:
        raise RuntimeError("scene has no geometry")
    return nodes


def dump_scene(rt, nodes):
    objects = []
    for node in nodes:
        faces = []
        count = int(rt.getNumFaces(node))
        for face in range(1, count + 1):
            material_id = int(rt.getFaceMatID(node, face))
            map_face = rt.meshop.getMapFace(node, 1, face)
            indices = [int(map_face.x), int(map_face.y), int(map_face.z)]
            uvs = []
            for index in indices:
                point = rt.meshop.getMapVert(node, 1, index)
                uvs.append([float(point.x), float(point.y)])
            faces.append({"material_id": material_id, "uvs": uvs})
        objects.append({"name": str(node.name), "faces": faces})
    return {"schema": "flora-placed-v1", "objects": objects}


def pack(uv, repo, inventory_path, catalogue_path, out_dir, address, scene):
    tool = os.path.join(repo, "tools", "library", "flora_atlas_from_scene.py")
    command = [
        uv, "run", "python", tool,
        "--scene-json", inventory_path,
        "--catalogue", catalogue_path,
        "--out-dir", out_dir,
        "--address", address,
        "--scene", scene,
    ]
    minimum = os.environ.get("AGR_FLORA_MIN_TILE", "").strip()
    if minimum:
        command.extend(["--min-tile-px", minimum])
    completed = subprocess.run(command, cwd=repo, capture_output=True)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or b"").decode("utf-8", "replace")[-4000:]
        raise RuntimeError("atlas tool failed: " + detail)
    report_path = os.path.join(out_dir, "flora-atlas.json")
    report = json.loads(open(report_path, encoding="utf-8").read())
    if report.get("atlas_count") != 1:
        raise RuntimeError("atlas tool did not keep a single atlas")
    return report


def apply_atlas(rt, nodes, report):
    tiles = {int(row["material_id"]): row["uv"] for row in report["ids"]}
    mat = rt.Standardmaterial()
    mat.name = str(report["material"]["name"])
    diffuse = rt.Bitmaptexture()
    diffuse.filename = max_path(report["material"]["diffuse"])
    opacity = rt.Bitmaptexture()
    opacity.filename = max_path(report["material"]["opacity"])
    mat.diffuseMap = diffuse
    mat.opacityMap = opacity
    for slot in ("bumpMap", "specularMap", "selfIllumMap", "displacementMap", "glossinessMap", "reflectionMap"):
        try:
            setattr(mat, slot, rt.undefined)
        except Exception:
            pass
    for node in nodes:
        rewrite_uvs(rt, node, tiles)
        node.material = mat
        rt.update(node)


def rewrite_uvs(rt, node, tiles):
    count = int(rt.getNumFaces(node))
    stored = []
    for face in range(1, count + 1):
        material_id = int(rt.getFaceMatID(node, face))
        if material_id not in tiles:
            raise RuntimeError("face material_id %s has no atlas tile" % material_id)
        map_face = rt.meshop.getMapFace(node, 1, face)
        uvs = []
        for index in (int(map_face.x), int(map_face.y), int(map_face.z)):
            point = rt.meshop.getMapVert(node, 1, index)
            uvs.append((float(point.x), float(point.y)))
        stored.append((material_id, uvs))
    rt.meshop.setNumMapVerts(node, 1, count * 3, keep=False)
    cursor = 1
    for face, (material_id, uvs) in enumerate(stored, start=1):
        u0, v0, u1, v1 = tiles[material_id]
        indices = []
        for u, v in uvs:
            rt.meshop.setMapVert(node, 1, cursor, rt.point3(u0 + u * (u1 - u0), v0 + v * (v1 - v0), 0.0))
            indices.append(cursor)
            cursor += 1
        rt.meshop.setMapFace(node, 1, face, rt.point3(indices[0], indices[1], indices[2]))
        rt.setFaceMatID(node, face, material_id)


def read_back(rt, scene_out, report):
    rt.resetMaxFile(rt.Name("noPrompt"))
    if not rt.loadMaxFile(max_path(scene_out), quiet=True, useFileUnits=True):
        raise RuntimeError("cannot reload " + scene_out)
    expected = {int(row["material_id"]): row["uv"] for row in report["ids"]}
    found = set()
    names = set()
    uv_ok = True
    one_material = True
    for node in list(rt.objects):
        if str(rt.superClassOf(node)) != "GeometryClass":
            continue
        material = node.material
        if material is None or material == rt.undefined:
            one_material = False
            continue
        names.add(str(material.name))
        diffuse = material.diffuseMap
        opacity = material.opacityMap
        if diffuse is None or diffuse == rt.undefined or opacity is None or opacity == rt.undefined:
            one_material = False
        for slot in ("bumpMap", "specularMap", "selfIllumMap"):
            extra = getattr(material, slot)
            if extra is not None and extra != rt.undefined:
                one_material = False
        count = int(rt.getNumFaces(node))
        for face in range(1, count + 1):
            material_id = int(rt.getFaceMatID(node, face))
            found.add(material_id)
            tile = expected.get(material_id)
            if tile is None:
                uv_ok = False
                continue
            map_face = rt.meshop.getMapFace(node, 1, face)
            for index in (int(map_face.x), int(map_face.y), int(map_face.z)):
                point = rt.meshop.getMapVert(node, 1, index)
                u, v = float(point.x), float(point.y)
                if u < tile[0] - 1e-4 or u > tile[2] + 1e-4 or v < tile[1] - 1e-4 or v > tile[3] + 1e-4:
                    uv_ok = False
    if names != {str(report["material"]["name"])}:
        one_material = False
    if found != set(expected):
        raise RuntimeError("readback material ids %s != %s" % (sorted(found), sorted(expected)))
    if not uv_ok or not one_material:
        raise RuntimeError("readback failed uv_ok=%s one_material=%s" % (uv_ok, one_material))
    return {
        "material_ids": sorted(found),
        "uv_ok": True,
        "one_material": True,
    }


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback = sys.exc_info()[1]
        sys.stderr.write("AGR_FLORA_FAIL %s\n" % traceback)
        raise
