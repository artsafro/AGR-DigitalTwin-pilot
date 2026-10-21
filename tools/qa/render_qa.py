"""Numerical preview QA, not delivery/aesthetic acceptance.

new-case: evaluated Blender projection, opaque geometric visibility and terrain contact.
Run Blender 5.1.2 --background --factory-startup --python-exit-code 1
--python tools/qa/render_qa.py -- --scene preview.blend --config qa.json
--report report.json --renders C:/x/render-qa/unique-run

All destinations must be new. No scene is saved. See render_qa.md for limits.
"""
import argparse
import hashlib
import json
import math
import shutil
import tempfile
from pathlib import Path
import sys
import time

DEFAULTS = {"crop_margin": 0.02, "minimum_coverage": 0.05, "floating_m": 0.01,
            "background_rgb": [0.0, 0.0, 0.0], "background_tolerance": 0.01}


def validate_config(raw):
    """Strict explicit object roles; no inferred ground-resting parts."""
    allowed = {"targets", "cameras", "ground_resting", "ground_objects", "thresholds"}
    if not isinstance(raw, dict) or set(raw) - allowed:
        raise ValueError(f"Unknown config keys or invalid config: {raw}")
    out = dict(raw)
    for key in ("targets", "cameras", "ground_resting", "ground_objects"):
        values = out.setdefault(key, [])
        if not isinstance(values, list) or any(not isinstance(v, str) or not v for v in values):
            raise ValueError(f"Invalid {key}: {values}")
        if len(set(values)) != len(values) or (key in ("targets", "cameras") and not values):
            raise ValueError(f"Empty or duplicate {key}: {values}")
    if not set(out["ground_resting"]) <= set(out["targets"]):
        raise ValueError("ground_resting must be a subset of targets")
    if out["ground_resting"] and not out["ground_objects"]:
        raise ValueError("ground_resting requires ground_objects")
    if set(out["targets"]) & set(out["ground_objects"]):
        raise ValueError("targets and ground_objects must be disjoint")
    thresholds = out.get("thresholds", {})
    if not isinstance(thresholds, dict) or set(thresholds) - DEFAULTS.keys():
        raise ValueError(f"Unknown thresholds: {thresholds}")
    thresholds = {**DEFAULTS, **thresholds}
    for key, value in thresholds.items():
        values = value if key == "background_rgb" else [value]
        if not isinstance(values, list) or (key == "background_rgb" and len(values) != 3):
            raise ValueError(f"Invalid {key}: {value}")
        if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in values):
            raise ValueError(f"Nonfinite/negative {key}: {value}")
        if key != "floating_m" and any(v > 1 for v in values):
            raise ValueError(f"Out of range {key}: {value}")
    if thresholds["minimum_coverage"] == 0:
        raise ValueError("minimum_coverage must be positive")
    out["thresholds"] = thresholds
    return out


def verdicts(obj, frame, facts, thresholds):
    """At a numerical boundary, fail conservatively with an explicit boundary code."""
    failures = []
    def fail(code):
        failures.append({"object": obj, "frame": frame, "code": code})
    bbox = facts["bbox"]
    if any(not math.isfinite(v) for v in bbox + facts["depth"] + [facts["coverage"]]):
        raise ValueError(f"Nonfinite measurement: {obj} / {frame}")
    if (len(bbox) != 4 or bbox[0] > bbox[2] or bbox[1] > bbox[3]
            or len(facts["depth"]) != 2 or facts["depth"][0] > facts["depth"][1]
            or not 0 <= facts["coverage"] <= 1 or type(facts["visible_faces"]) is not int
            or facts["visible_faces"] < 0):
        raise ValueError(f"Invalid measurement: {obj} / {frame}")
    # Behind-camera objects are empty, not spuriously cropped by mirrored projection.
    if facts["depth"][1] > 0:
        outside = max(-bbox[0], -bbox[1], bbox[2] - 1, bbox[3] - 1)
        if outside > thresholds["crop_margin"]:
            fail("cropped")
        elif math.isclose(outside, thresholds["crop_margin"], abs_tol=1e-9):
            fail("crop_boundary")
    if facts["coverage"] < thresholds["minimum_coverage"] or facts["visible_faces"] == 0:
        fail("empty")
    elif math.isclose(facts["coverage"], thresholds["minimum_coverage"], abs_tol=1e-9):
        fail("coverage_boundary")
    gap = facts["ground_gap_m"]
    if gap is not None:
        if not math.isfinite(gap):
            raise ValueError(f"Nonfinite ground gap: {obj} / {frame}")
        if gap > thresholds["floating_m"]:
            fail("floating")
        elif math.isclose(gap, thresholds["floating_m"], abs_tol=1e-9):
            fail("floating_boundary")
    return failures


def _mesh_facts(scene, config):
    import bpy
    from mathutils.bvhtree import BVHTree
    graph = bpy.context.evaluated_depsgraph_get()
    if any(instance.is_instance for instance in graph.object_instances):
        raise ValueError("Instanced geometry unsupported; realize instances before QA")
    meshes = {}
    vertices, triangles, owners = [], [], []
    for obj in scene.objects:
        if obj.hide_render:
            continue
        if obj.type == "MESH" and not obj.visible_get():
            raise ValueError(f"Viewport/render visibility mismatch: {obj.name}")
        if any(m.show_render != m.show_viewport for m in obj.modifiers):
            raise ValueError(f"Modifier viewport/render mismatch: {obj.name}")
        if obj.type not in {"MESH", "CAMERA", "LIGHT", "EMPTY"}:
            raise ValueError(f"Unsupported render object {obj.name}: {obj.type}")
        if obj.type != "MESH":
            continue
        for slot in obj.material_slots:
            material = slot.material
            if material and material.node_tree is not None:
                for node in material.node_tree.nodes:
                    if node.type in {"BSDF_TRANSPARENT", "BSDF_GLASS", "GROUP"}:
                        raise ValueError(f"Unsupported opacity/shader: {obj.name}/{material.name}")
                    if node.type == "BSDF_PRINCIPLED":
                        for key, expected in (("Alpha", 1), ("Transmission Weight", 0)):
                            socket = node.inputs.get(key)
                            if socket and (socket.is_linked or socket.default_value != expected):
                                raise ValueError(f"Unsupported {key}: {obj.name}/{material.name}")
        evaluated = obj.evaluated_get(graph)
        mesh = evaluated.to_mesh()
        try:
            world = [evaluated.matrix_world @ v.co for v in mesh.vertices]
            if not world or not mesh.polygons:
                raise ValueError(f"Empty mesh: {obj.name}")
            if any(not math.isfinite(c) for v in world for c in v):
                raise ValueError(f"Nonfinite vertex: {obj.name}")
            mesh.calc_loop_triangles()
            local_triangles = [tuple(t.vertices) for t in mesh.loop_triangles]
            meshes[obj.name] = (world, local_triangles)
            offset = len(vertices)
            vertices.extend(world)
            triangles.extend(tuple(i + offset for i in t) for t in local_triangles)
            owners.extend((obj.name, t.polygon_index) for t in mesh.loop_triangles)
        finally:
            evaluated.to_mesh_clear()
    for name in set(config["targets"] + config["ground_objects"]):
        if name not in meshes:
            raise ValueError(f"Missing, hidden or non-mesh object: {name}")
    return meshes, BVHTree.FromPolygons(vertices, triangles, all_triangles=True), owners


def _ground_gap(world, grounds, scale):
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    vertices, triangles = [], []
    for points, faces in grounds:
        offset = len(vertices)
        vertices.extend(points)
        triangles.extend(tuple(i + offset for i in face) for face in faces)
    tree = BVHTree.FromPolygons(vertices, triangles, all_triangles=True)
    lowest = min(v.z for v in world)
    top = max(max(v.z for v in vertices), lowest) + 1 / scale
    gaps = []
    for point in world:
        if abs(point.z - lowest) > 1e-6 / scale:
            continue
        location, _, _, _ = tree.ray_cast(Vector((point.x, point.y, top)), Vector((0, 0, -1)))
        if location is None:
            raise ValueError(f"No ground surface under lowest vertex {tuple(point)}")
        gaps.append((point.z - location.z) * scale)
    return min(gaps), max(gaps), len(gaps)


def _visibility(scene, camera, tree, owners, width, height):
    from mathutils import Vector
    corners = camera.data.view_frame(scene=scene)
    left, right = min(v.x for v in corners), max(v.x for v in corners)
    bottom, top = min(v.y for v in corners), max(v.y for v in corners)
    z = corners[0].z
    matrix = camera.matrix_world
    counts, faces = {}, {}
    for y in range(height):
        for x in range(width):
            point = Vector((left + (right - left) * (x + 0.5) / width,
                            bottom + (top - bottom) * (y + 0.5) / height, z))
            if camera.data.type == "ORTHO":
                origin = matrix @ Vector((point.x, point.y, -camera.data.clip_start))
                direction = (matrix.to_3x3() @ Vector((0, 0, -1))).normalized()
                distance = camera.data.clip_end - camera.data.clip_start
            else:
                local = point.normalized()
                origin = matrix @ (local * (camera.data.clip_start / -local.z))
                direction = (matrix.to_3x3() @ local).normalized()
                distance = (camera.data.clip_end - camera.data.clip_start) / -local.z
            _, _, index, _ = tree.ray_cast(origin, direction, distance)
            if index is not None:
                name, face = owners[index]
                counts[name] = counts.get(name, 0) + 1
                faces.setdefault(name, set()).add(face)
    return counts, faces


def _state(scene, meshes, cameras):
    geometry = tuple((name, tuple(tuple(v) for v in world), tuple(faces))
                     for name, (world, faces) in meshes.items())
    views = tuple((c.name, tuple(tuple(row) for row in c.matrix_world), c.data.type,
                   tuple(tuple(v) for v in c.data.view_frame(scene=scene)),
                   c.data.clip_start, c.data.clip_end) for c in cameras)
    settings = (scene.frame_current, scene.unit_settings.scale_length, scene.render.engine,
                scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage)
    return hashlib.sha256(repr((geometry, views, settings)).encode("utf-8")).hexdigest()


def check_scene(scene, raw_config, renders):
    """Measure the current frame for each named camera; render to a NEW directory.

    Pixel-centre geometric visibility uses every output pixel, including occluders.
    Coverage is the union of target hits; per-object shares are reported separately.
    """
    import bpy
    from bpy_extras.object_utils import world_to_camera_view
    started = time.perf_counter()
    config = validate_config(raw_config)
    scale = scene.unit_settings.scale_length
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("Invalid scene unit scale")
    if scene.render.use_border or scene.render.use_multiview or scene.render.film_transparent:
        raise ValueError("Border, multiview and transparent-film renders unsupported")
    if scene.compositing_node_group is not None or (scene.sequence_editor and scene.sequence_editor.strips):
        raise ValueError("Compositor/sequencer unsupported (including file-output side effects)")
    def collections(collection):
        if collection.hide_render or collection.hide_viewport:
            raise ValueError(f"Collection visibility override unsupported: {collection.name}")
        for child in collection.children:
            collections(child)
    collections(scene.collection)
    cameras = []
    for name in config["cameras"]:
        camera = scene.objects.get(name)
        if camera is None or camera.type != "CAMERA" or camera.data.type not in {"ORTHO", "PERSP"}:
            raise ValueError(f"Missing or unsupported camera: {name}")
        if any(abs(v - 1) > 1e-6 for v in camera.matrix_world.to_scale()):
            raise ValueError(f"Scaled camera unsupported: {name}")
        if camera.data.dof.use_dof:
            raise ValueError(f"Depth of field unsupported: {name}")
        cameras.append(camera)
    width = int(scene.render.resolution_x * scene.render.resolution_percentage / 100)
    height = int(scene.render.resolution_y * scene.render.resolution_percentage / 100)
    if width <= 0 or height <= 0 or width * height > 4194304:
        raise ValueError("Resolution must be 1..4194304 pixels")
    meshes, tree, owners = _mesh_facts(scene, config)
    frozen_state = _state(scene, meshes, cameras)
    grounds = [meshes[name] for name in config["ground_objects"]]
    gaps = {}
    for name in config["ground_resting"]:
        try:
            gaps[name] = _ground_gap(meshes[name][0], grounds, scale)
        except ValueError as exc:
            raise ValueError(f"{name}: {exc}") from exc
    renders = Path(renders)
    renders.mkdir(parents=True, exist_ok=False)
    report = {"schema": "render-qa-v1", "blender": bpy.app.version_string,
              "frame_number": scene.frame_current, "units_m_per_unit": scale,
              "source_metadata": scene.get("render_qa_source"),
              "config": config, "visibility": "opaque geometry, every output pixel centre",
              "frames": [], "status": "fail"}
    old = (scene.camera, scene.render.filepath, scene.render.image_settings.file_format,
           scene.render.image_settings.color_mode, scene.render.use_file_extension)
    try:
        for index, camera in enumerate(cameras):
            tick = time.perf_counter()
            scene.camera = camera
            bpy.context.view_layer.update()
            counts, faces = _visibility(scene, camera, tree, owners, width, height)
            total = sum(counts.get(n, 0) for n in config["targets"])
            frame = {"camera": camera.name, "objects": [], "failures": [],
                     "coverage": total / (width * height)}
            for name in config["targets"]:
                projected = [world_to_camera_view(scene, camera, p) for p in meshes[name][0]]
                facts = {"object": name,
                         "bbox": [min(p.x for p in projected), min(p.y for p in projected),
                                  max(p.x for p in projected), max(p.y for p in projected)],
                         "depth": [min(p.z for p in projected), max(p.z for p in projected)],
                         "coverage": frame["coverage"],
                         "object_coverage": counts.get(name, 0) / (width * height),
                         "visible_faces": len(faces.get(name, set())),
                         "ground_gap_m": gaps[name][0] if name in gaps else None,
                         "ground_contact": {"minimum_m": gaps[name][0], "maximum_m": gaps[name][1],
                                            "lowest_vertices": gaps[name][2]} if name in gaps else "not_applicable: not declared ground-resting"}
                failures = verdicts(name, camera.name, facts, config["thresholds"])
                if facts["depth"][0] <= camera.data.clip_start and facts["depth"][1] >= camera.data.clip_start:
                    failures.append({"object": name, "frame": camera.name, "code": "near_clip"})
                if facts["depth"][1] >= camera.data.clip_end:
                    failures.append({"object": name, "frame": camera.name, "code": "far_clip"})
                frame["objects"].append(facts)
                frame["failures"].extend(failures)
            image_path = renders / f"frame_{index:04d}.png"
            scene.render.filepath = str(image_path.resolve())
            scene.render.image_settings.file_format = "PNG"
            scene.render.image_settings.color_mode = "RGB"
            scene.render.use_file_extension = True
            # Render privately, then publish without replacing any pre-existing file.
            with tempfile.TemporaryDirectory(prefix="render-", dir=renders) as private:
                private_image = Path(private) / "frame.png"
                scene.render.filepath = str(private_image.resolve())
                bpy.ops.render.render(write_still=True)
                with image_path.open("xb") as output, private_image.open("rb") as source:
                    shutil.copyfileobj(source, output)
            fresh_meshes, _, _ = _mesh_facts(scene, config)
            if _state(scene, fresh_meshes, cameras) != frozen_state:
                raise ValueError(f"Scene changed during render: {camera.name}")
            image = bpy.data.images.load(str(image_path.resolve()), check_existing=False)
            try:
                if tuple(image.size) != (width, height):
                    raise ValueError("Rendered dimensions changed")
                pixels = list(image.pixels)
                background = config["thresholds"]["background_rgb"]
                tolerance = config["thresholds"]["background_tolerance"]
                if any(not math.isfinite(v) for v in pixels):
                    raise ValueError("Nonfinite rendered pixels")
                matched = sum(all(abs(pixels[i + c] - background[c]) <= tolerance for c in range(3))
                              for i in range(0, len(pixels), 4))
                frame["pixels"] = {"width": width, "height": height, "count": width * height,
                                   "background_share": matched / (width * height),
                                   "colour_space": "Blender loaded PNG linear RGB", "path": str(image_path.resolve()),
                                   "sha256": _digest(image_path)}
            finally:
                bpy.data.images.remove(image)
            frame["status"] = "fail" if frame["failures"] else "pass"
            frame["seconds"] = time.perf_counter() - tick
            report["frames"].append(frame)
    finally:
        (scene.camera, scene.render.filepath, scene.render.image_settings.file_format,
         scene.render.image_settings.color_mode, scene.render.use_file_extension) = old
    report["status"] = "pass" if all(f["status"] == "pass" for f in report["frames"]) else "fail"
    report["seconds"] = time.perf_counter() - started
    return report


def _digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_config(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate config key: {key}")
            result[key] = value
        return result
    return validate_config(json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique))


def validate_paths(scene, config, report, renders):
    """Read-only preflight; resolving spelling, symlinks and hardlink aliases."""
    scene, config, report, renders = [Path(p).resolve() for p in (scene, config, report, renders)]
    if not scene.is_file() or not config.is_file():
        raise ValueError("scene and config must exist")
    if scene == config or scene.samefile(config):
        raise ValueError("scene and config must be distinct")
    if scene.suffix.lower() != ".blend" or config.suffix.lower() != ".json" or report.suffix.lower() != ".json":
        raise ValueError("Expected .blend scene and .json config/report")
    if report.exists() or renders.exists():
        raise FileExistsError("Report and renders must be new; existing destinations are never overwritten")
    if report == renders or report.is_relative_to(renders) or renders.is_relative_to(report):
        raise ValueError("Report and render directory must be separate")
    for source in (scene, config):
        if report == source or source.is_relative_to(renders) or renders.is_relative_to(source):
            raise ValueError(f"Input/output alias: {source}")
    return scene, config, report, renders


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("scene", "config", "report", "renders"):
        parser.add_argument("--" + flag, required=True, type=Path)
    args = parser.parse_args(argv)
    scene, config, report, renders = validate_paths(args.scene, args.config, args.report, args.renders)
    settings = read_config(config)
    before = {str(path): _digest(path) for path in (scene, config, Path(__file__).resolve())}
    import bpy
    if bpy.app.version != (5, 1, 2):
        raise ValueError(f"Blender 5.1.2 required, got {bpy.app.version_string}")
    bpy.ops.wm.open_mainfile(filepath=str(scene), load_ui=False, use_scripts=False)
    # Bind external files as well; missing textures/libraries are errors, never defaults.
    for block in [*bpy.data.images, *bpy.data.libraries]:
        if getattr(block, "packed_file", None) or getattr(block, "source", None) == "GENERATED":
            continue
        name = getattr(block, "filepath", "")
        if name:
            path = Path(bpy.path.abspath(name, library=block.library)).resolve()
            if not path.is_file():
                raise ValueError(f"Missing external input: {path}")
            if path == report or path.is_relative_to(renders):
                raise ValueError(f"External input/output alias: {path}")
            before[str(path)] = _digest(path)
    result = check_scene(bpy.context.scene, settings, renders)
    changed = [path for path, digest in before.items() if not Path(path).is_file() or _digest(path) != digest]
    if changed:
        raise ValueError(f"Input changed during QA: {changed}")
    result["inputs_sha256"] = before
    report.parent.mkdir(parents=True, exist_ok=True)
    with report.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(f"RENDER_QA {result['status']}: {report}")
    if result["status"] != "pass":
        raise RuntimeError("Render QA failed; see report")
    return 0


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
