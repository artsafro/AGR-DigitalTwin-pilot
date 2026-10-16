"""Assemble the Flora agent library .max from audited scene copies.
Pattern: n/a | new-case: Flora agent library .max assembly from audited scene copies (#216).
"""
import hashlib
import json
import os

PIVOT_LIFT_M = 0.10
GRID_M = 12.0
LIBRARY_NAME = "flora-library-v002.max"


def layout_position(column, row, spacing=GRID_M):
    return (float(column) * spacing, float(row) * spacing, 0.0)


def pivot_target(min_x, min_y, max_x, max_y, lowest_z, lift=PIVOT_LIFT_M):
    return ((float(min_x) + float(max_x)) / 2.0, (float(min_y) + float(max_y)) / 2.0, float(lowest_z) + lift)


def pivot_for_bounds(bounds, lift=PIVOT_LIFT_M):
    """Pivot from world_vertex_bounds order (min_x, min_y, min_z, max_x, max_y)."""
    min_x, min_y, min_z, max_x, max_y = bounds
    return pivot_target(min_x, min_y, max_x, max_y, min_z, lift)


def material_name(object_name, material_id):
    stem = object_name
    for suffix in ("_NPM", "_VPM"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    return f"{stem}_ID{material_id}"


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def part_path(out_dir, scene_name):
    stem = scene_name[:-4] if scene_name.lower().endswith(".max") else scene_name
    return os.path.join(out_dir, "parts", stem + "-part.max")


def same_path(left, right):
    if not left or not right:
        return False
    return os.path.normcase(os.path.normpath(left)) == os.path.normcase(os.path.normpath(right))


def max_path(path):
    return os.path.abspath(path).replace("\\", "/")


def work_items(catalogue, audit):
    indexed = {entry["id"]: entry for scene in audit["scenes"] for entry in scene["entries"]}
    items = []
    for column, species in enumerate(catalogue["species"]):
        for row, profile in ((0, "NPM"), (1, "VPM")):
            record = species[profile.lower()]
            if record is None:
                continue
            entry = indexed[record["entry_id"]]
            name = species["objects"][profile]
            items.append({
                "scene": record["scene"], "handle": entry["source_handle"], "source_name": entry["source_name"],
                "source_bbox": entry["bbox_m"], "source_triangles": entry["triangles"],
                "object_name": name, "material_id": species["material_id"], "column": column, "row": row,
                "triangles": species["triangles"][profile], "material_name": material_name(name, species["material_id"]),
                "diffuse": species["maps"]["diffuse"], "opacity": species["maps"]["opacity"],
            })
    return items


def _runtime():
    from pymxs import runtime as rt
    return rt


def _missing(rt, node):
    return node is None or node == rt.undefined


def world_vertex_bounds(rt, node):
    mesh = rt.snapshotAsMesh(node)
    try:
        # snapshotAsMesh vertices are already in world space (#189 audit probe); do not apply a transform again.
        points = [rt.meshop.getVert(mesh, i) for i in range(1, int(mesh.numverts) + 1)]
    finally:
        rt.delete(mesh)
    if not points:
        raise RuntimeError("mesh has no vertices")
    xs, ys, zs = ([float(getattr(p, axis)) for p in points] for axis in "xyz")
    return min(xs), min(ys), min(zs), max(xs), max(ys)


def bbox_matches(found, expected, tol=0.001):
    return all(abs(float(a) - float(b)) <= tol for pa, pb in zip(found, expected) for a, b in zip(pa, pb))


def _same_source(rt, node, item):
    try:
        mesh = rt.snapshotAsMesh(node)
    except Exception:
        return False
    try:
        triangles = int(rt.getNumFaces(mesh))
    finally:
        rt.delete(mesh)
    box = rt.nodeGetBoundingBox(node, rt.matrix3(1))
    found = [[float(box[0].x), float(box[0].y), float(box[0].z)], [float(box[1].x), float(box[1].y), float(box[1].z)]]
    return triangles == int(item["source_triangles"]) and bbox_matches(found, item["source_bbox"])


def adopt(rt, source, item):
    clone = rt.copy(source)
    clone.parent = rt.undefined
    try:
        rt.setGroupMember(clone, False)
    except Exception:
        pass
    clone.isHidden = False
    clone.isFrozen = False
    rt.convertToMesh(clone)
    for face in range(1, int(rt.getNumFaces(clone)) + 1):
        rt.setFaceMatID(clone, face, int(item["material_id"]))
    rt.update(clone)
    clone.name = item["object_name"]
    cx, cy, cz = pivot_for_bounds(world_vertex_bounds(rt, clone))
    clone.pivot = rt.point3(cx, cy, cz)
    clone.pos = rt.point3(*layout_position(item["column"], item["row"]))
    return clone


def delete_others(rt, keep):
    keep_ids = {int(node.handle) for node in keep}
    for node in [node for node in list(rt.objects) if int(node.handle) not in keep_ids]:
        for child in list(node.children):
            child.parent = rt.undefined
        rt.delete(node)


def build_part(rt, scene_path, items, dest):
    rt.resetMaxFile(rt.Name("noPrompt"))
    if not rt.loadMaxFile(max_path(scene_path), quiet=True):
        raise RuntimeError("loadMaxFile failed: " + scene_path)
    created, failures = [], []
    by_name = {}
    for node in list(rt.objects):
        by_name.setdefault(str(node.name), []).append(node)
    for item in items:
        try:
            # Anim handles from the #189 audit are session-bound; match name + triangles + world bbox instead.
            matches = [node for node in by_name.get(item["source_name"], []) if _same_source(rt, node, item)]
            if len(matches) != 1:
                failures.append(f"{item['object_name']}: {len(matches)} nodes match audit {item['source_name']}")
            else:
                created.append(adopt(rt, matches[0], item))
        except Exception as exc:
            failures.append(f"{item['object_name']}: {exc}")
    delete_others(rt, created)
    if created:
        rt.saveMaxFile(max_path(dest), quiet=True)
    return bool(created), failures


def bind_materials(rt, species):
    by_name = {str(node.name): node for node in list(rt.objects)}
    for item in species:
        mat = rt.Standardmaterial()
        mat.name = material_name(item["objects"]["NPM"], item["material_id"])
        for slot, path in (("diffuseMap", item["maps"]["diffuse"]), ("opacityMap", item["maps"]["opacity"])):
            if not path:
                continue
            tex = rt.Bitmaptexture()
            tex.filename = path
            setattr(mat, slot, tex)
        for profile in ("NPM", "VPM"):
            node = by_name.get(item["objects"][profile] or "")
            if node is not None:
                node.material = mat


def _bitmap_name(rt, texture):
    return None if _missing(rt, texture) else str(texture.filename)


def read_object(rt, node, item):
    min_x, min_y, min_z, max_x, max_y = world_vertex_bounds(rt, node)
    centre_x, centre_y, _ = pivot_target(min_x, min_y, max_x, max_y, min_z)
    faces = int(rt.getNumFaces(node))
    ids = sorted({int(rt.getFaceMatID(node, face)) for face in range(1, faces + 1)})
    mat = node.material
    mat_name = None if _missing(rt, mat) else str(mat.name)
    diffuse = None if mat_name is None else _bitmap_name(rt, mat.diffuseMap)
    opacity = None if mat_name is None else _bitmap_name(rt, mat.opacityMap)
    name = item["object_name"]
    lift = float(node.pivot.z) - min_z
    pivot_xy = [float(node.pivot.x), float(node.pivot.y)]
    row = {
        "name": name, "exists": True, "triangles": faces, "material_ids": ids,
        "pivot_above_lowest_m": lift, "pivot_xy": pivot_xy, "bbox_centre_xy": [centre_x, centre_y],
        "material_name": mat_name, "diffuse": diffuse, "opacity": opacity,
    }
    checks = (
        (set(ids) != {item["material_id"]}, f"{name} material ids {ids}"),
        (abs(lift - PIVOT_LIFT_M) > 0.001, f"{name} pivot lift {lift}"),
        (abs(pivot_xy[0] - centre_x) > 0.001 or abs(pivot_xy[1] - centre_y) > 0.001, f"{name} pivot xy is off the bbox centre"),
        (mat_name != item["material_name"], f"{name} material {mat_name!r}"),
        (bool(item["diffuse"]) and not same_path(diffuse, item["diffuse"]), f"{name} diffuse {diffuse!r}"),
        (bool(item["opacity"]) and not same_path(opacity, item["opacity"]), f"{name} opacity {opacity!r}"),
        (faces != item["triangles"], f"{name} triangles {faces} != {item['triangles']}"),
    )
    return row, [text for failed, text in checks if failed]


def readback(rt, path, expected):
    rt.resetMaxFile(rt.Name("noPrompt"))
    if not rt.loadMaxFile(max_path(path), quiet=True):
        raise RuntimeError("library readback failed: " + path)
    by_name = {str(node.name): node for node in list(rt.objects)}
    rows, failures = [], []
    for item in expected:
        name = item["object_name"]
        node = by_name.pop(name, None)
        if node is None:
            rows.append({"name": name, "exists": False, "triangles": None, "material_ids": []})
            failures.append(name + " missing")
            continue
        try:
            row, row_failures = read_object(rt, node, item)
        except Exception as exc:
            row, row_failures = {"name": name, "exists": True, "triangles": None, "material_ids": []}, [f"{name}: {exc}"]
        rows.append(row)
        failures.extend(row_failures)
    unexpected = sorted(by_name)
    failures.extend("unexpected object " + name for name in unexpected)
    return rows, unexpected, failures


def _load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def assemble(job):
    for key in ("catalogue", "audit", "scenes", "copy_sha256", "out_dir", "report"):
        if key not in job:
            raise RuntimeError("FLORA_LIBRARY_JOB missing " + key)
    for name, expected_hash in job["copy_sha256"].items():
        if file_sha256(job["scenes"][name]).lower() != str(expected_hash).lower():
            raise RuntimeError("sha256 mismatch for " + name)
    target = os.path.join(job["out_dir"], LIBRARY_NAME)
    if os.path.exists(target):
        raise RuntimeError("refusing to overwrite " + target)
    for path in (target, *(part_path(job["out_dir"], name) for name in job["scenes"])):
        for source in job["scenes"].values():
            if same_path(path, source):
                raise RuntimeError("refusing to save over source scene " + source)
    os.makedirs(os.path.join(job["out_dir"], "parts"), exist_ok=True)
    catalogue, audit = _load(job["catalogue"]), _load(job["audit"])
    expected = work_items(catalogue, audit)
    grouped = {}
    for item in expected:
        grouped.setdefault(item["scene"], []).append(item)
    rt, failures, parts = _runtime(), [], []
    for scene_name, scene_path in job["scenes"].items():
        scene_items = grouped.pop(scene_name, [])
        if not scene_items:
            continue
        dest = part_path(job["out_dir"], scene_name)
        try:
            saved, part_failures = build_part(rt, scene_path, scene_items, dest)
            failures.extend(part_failures)
            if saved:
                parts.append(dest)
        except Exception as exc:
            failures.append(f"{scene_name}: {exc}")
    for scene_name, scene_items in grouped.items():
        failures.extend(f"{item['object_name']}: scene {scene_name} is not in the job" for item in scene_items)
    if parts:
        try:
            rt.resetMaxFile(rt.Name("noPrompt"))
            for path in parts:
                if not rt.mergeMAXFile(max_path(path), rt.Name("autoRenameDups"), rt.Name("renameMtlDups"), quiet=True):
                    raise RuntimeError("mergeMAXFile failed: " + path)
            bind_materials(rt, catalogue["species"])
            if not rt.saveMaxFile(max_path(target), quiet=True):
                failures.append("saveMaxFile failed: " + target)
        except Exception as exc:
            failures.append(f"assemble: {exc}")
    rows, unexpected = [], []
    if os.path.exists(target):
        try:
            rows, unexpected, read_failures = readback(rt, target, expected)
            failures.extend(read_failures)
        except Exception as exc:
            failures.append(f"readback: {exc}")
    else:
        for item in expected:
            rows.append({"name": item["object_name"], "exists": False, "triangles": None, "material_ids": []})
            failures.append(item["object_name"] + " missing")
    report = {
        "counts": {"expected": len(expected), "rows": len(rows), "unexpected": len(unexpected), "failures": len(failures)},
        "objects": rows, "unexpected": unexpected, "failures": failures, "passed": not failures,
    }
    folder = os.path.dirname(job["report"])
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(job["report"], "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    library_stem = os.path.splitext(LIBRARY_NAME)[0]
    print(f"{library_stem} passed={str(report['passed']).lower()} objects={len(expected)} failures={len(failures)}")
    return report


def main():
    job_path = os.environ.get("FLORA_LIBRARY_JOB")
    if not job_path:
        raise RuntimeError("FLORA_LIBRARY_JOB is unset")
    assemble(_load(job_path))


if __name__ == "__main__":
    main()
