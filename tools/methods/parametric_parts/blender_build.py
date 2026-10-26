"""Build the bench and the KPP1 aerator in Blender, with a Geometry Nodes length socket.

new-case: Blender geometry-nodes variant for repeatable parts (#713).

Run with Blender --background --factory-startup --python-exit-code 1 --python this file.
The bench mesh is extruded at length 1 m and the Geometry Nodes Transform scale X is the
length socket (1.8 m, then 1.9 m). The aerator mesh is the recipe at the pipe length.
build_s is the Blender object build plus FBX export. The parameter-change timer is the
socket or mesh edit plus FBX export. Recipe math stays outside both timers.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mesh_recipe as recipe  # noqa: E402

OUT = Path(r"C:\x\methods\parametric-parts")


def _refuse(path: Path):
    if not str(path).lower().startswith(str(OUT).lower()):
        raise RuntimeError("refusing to write outside " + str(OUT))


def _node_group(name: str, length: float, drive_scale: bool):
    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    sock = ng.interface.new_socket(name="Length", in_out="INPUT", socket_type="NodeSocketFloat")
    sock.default_value = float(length)
    ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    n_in = ng.nodes.new("NodeGroupInput")
    n_out = ng.nodes.new("NodeGroupOutput")
    formed = ng.nodes.new("GeometryNodeTransform")
    combine = ng.nodes.new("ShaderNodeCombineXYZ")
    combine.inputs[0].default_value = 1.0
    combine.inputs[1].default_value = 1.0
    combine.inputs[2].default_value = 1.0
    ng.links.new(n_in.outputs[0], formed.inputs["Geometry"])
    if drive_scale:
        ng.links.new(n_in.outputs[1], combine.inputs[0])
    ng.links.new(combine.outputs[0], formed.inputs["Scale"])
    ng.links.new(formed.outputs["Geometry"], n_out.inputs[0])
    return ng, sock.identifier


def _object(name: str, verts, tris, length: float, drive_scale: bool):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], [tuple(t) for t in tris])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    ng, ident = _node_group(name + "GN", length, drive_scale)
    mod = obj.modifiers.new("Parametric", "NODES")
    mod.node_group = ng
    mod[ident] = float(length)
    return obj, ident


def _exclusive_path(directory: Path, suffix: str) -> Path:
    fd, name = tempfile.mkstemp(suffix=suffix, dir=str(directory))
    os.close(fd)
    os.remove(name)
    return Path(name)


def _export(obj, path: Path):
    _refuse(path)
    partial = _exclusive_path(path.parent, ".fbx")
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    try:
        bpy.ops.export_scene.fbx(
            filepath=str(partial),
            use_selection=True,
            apply_unit_scale=True,
            bake_space_transform=True,
            axis_forward="-Y",
            axis_up="Z",
            use_mesh_modifiers=True,
            mesh_smooth_type="FACE",
            add_leaf_bones=False,
            object_types={"MESH"},
            path_mode="STRIP",
        )
        os.replace(partial, path)
    except Exception:
        if partial.exists() and not (path.exists() and os.path.samefile(partial, path)):
            partial.unlink()
        raise


def _clear():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh)
    for ng in list(bpy.data.node_groups):
        bpy.data.node_groups.remove(ng)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    version = bpy.app.version_string
    jobs = [
        ("bench", "bench", lambda length: recipe.bench_mesh(1.0), 1.8, 1.9, True),
        ("aerator", "aerator", lambda length: recipe.aerator_mesh(length), recipe.PIPE_LENGTH_M, recipe.PIPE_LENGTH_PARAM_M, False),
    ]
    for slug, name, builder, base, changed, scale_length in jobs:
        _clear()
        mesh_value = 1.0 if scale_length else base
        verts, tris = builder(mesh_value)
        started = time.perf_counter()
        obj, ident = _object(name, verts, tris, base if scale_length else 1.0, scale_length)
        path = OUT / f"{slug}-blender.fbx"
        _export(obj, path)
        elapsed = time.perf_counter() - started
        rows.append({
            "part": slug,
            "tool": "blender",
            "kind": "build",
            "build_s": elapsed,
            "fbx": str(path),
            "version": version,
            "length_socket": base if scale_length else 1.0,
            "timing_boundary": "build + FBX export",
            "geometry_nodes": "GeometryNodeTransform scale X is the length socket" if scale_length else "GeometryNodeTransform scale stays 1; mesh is the recipe at the pipe length",
        })
        print("BUILT", json.dumps(rows[-1]))
        param_path = OUT / f"{slug}-blender-param.fbx"
        if scale_length:
            started = time.perf_counter()
            modifier = obj.modifiers["Parametric"]
            modifier[ident] = float(changed)
            obj.update_tag()
            bpy.context.view_layer.update()
            _export(obj, param_path)
            elapsed = time.perf_counter() - started
            note = "GeometryNodeTransform Length socket edit + FBX export"
        else:
            verts, tris = builder(changed)
            started = time.perf_counter()
            obj.data.clear_geometry()
            obj.data.from_pydata(verts, [], [tuple(t) for t in tris])
            obj.data.update()
            _export(obj, param_path)
            elapsed = time.perf_counter() - started
            note = "mesh replaced at the new pipe length + FBX export"
        rows.append({
            "part": slug,
            "tool": "blender",
            "kind": "param_change",
            "build_s": elapsed,
            "fbx": str(param_path),
            "version": version,
            "length_socket": changed if scale_length else 1.0,
            "timing_boundary": "parameter change + FBX export",
            "geometry_nodes": note,
        })
        print("BUILT", json.dumps(rows[-1]))
    recipe.publish_bytes(
        OUT / "blender-build.json",
        json.dumps({"version": version, "timing_boundary": "build + FBX export", "rows": rows}, indent=2).encode("utf-8"),
    )


if __name__ == "__main__":
    main()
