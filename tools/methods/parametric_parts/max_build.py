"""Build the bench and the KPP1 aerator in headless 3ds Max (pymxs).

new-case: 3ds Max variant for repeatable parts (#713).

Run only through dcc_batch.py on a blank session. Exports FBX of the meshes this script
creates. Nothing in the MAF library is opened or saved. build_s is mesh() plus FBX
export. The recipe is evaluated before the timer. The parameter change is a new mesh
at the new length plus FBX export, the same boundary.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

import pymxs

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mesh_recipe as recipe  # noqa: E402

rt = pymxs.runtime
OUT = Path(r"C:\x\methods\parametric-parts")


def _refuse(path: Path):
    if not str(path).lower().startswith(str(OUT).lower()):
        raise RuntimeError("refusing to write outside " + str(OUT))


def _mesh(name: str, verts, tris):
    obj = rt.mesh(
        name=name,
        vertices=[rt.Point3(float(x), float(y), float(z)) for x, y, z in verts],
        faces=[rt.Point3(int(a) + 1, int(b) + 1, int(c) + 1) for a, b, c in tris],
    )
    rt.update(obj)
    return obj


def _exclusive_path(directory: Path, suffix: str) -> Path:
    fd, name = tempfile.mkstemp(suffix=suffix, dir=str(directory))
    os.close(fd)
    os.remove(name)
    return Path(name)


def _export(obj, path: Path):
    _refuse(path)
    partial = _exclusive_path(path.parent, ".fbx")
    rt.select(obj)
    try:
        rt.exportFile(str(partial), rt.Name("noPrompt"), selectedOnly=True, using=rt.FBXEXP)
        if not partial.is_file():
            raise RuntimeError("FBX export did not write " + str(partial))
        os.replace(partial, path)
    except Exception:
        if partial.exists() and not (path.exists() and os.path.samefile(partial, path)):
            partial.unlink()
        raise


def _one(slug: str, kind: str, verts, tris):
    rt.delete(list(rt.objects))
    started = time.perf_counter()
    obj = _mesh(slug, verts, tris)
    path = OUT / (f"{slug}-max-param.fbx" if kind == "param_change" else f"{slug}-max.fbx")
    _export(obj, path)
    elapsed = time.perf_counter() - started
    row = {
        "part": slug,
        "tool": "max",
        "kind": kind,
        "build_s": elapsed,
        "fbx": str(path),
        "version": str(rt.maxVersion()),
        "triangles_in_max": int(rt.getNumFaces(obj)),
        "timing_boundary": "parameter change + FBX export" if kind == "param_change" else "build + FBX export",
    }
    print("BUILT " + json.dumps(row))
    return row


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rt.execute("units.SystemType = #meters")
    rt.execute("units.SystemScale = 1.0")
    rt.pluginManager.loadClass(rt.FBXEXP)
    rt.FBXExporterSetParam("Animation", False)
    rt.FBXExporterSetParam("Cameras", False)
    rt.FBXExporterSetParam("Lights", False)
    rt.FBXExporterSetParam("EmbedTextures", False)
    rt.FBXExporterSetParam("SmoothingGroups", False)
    rt.FBXExporterSetParam("Triangulate", False)
    rt.FBXExporterSetParam("UpAxis", "Z")
    rows = [
        _one("bench", "build", *recipe.bench_mesh()),
        _one("bench", "param_change", *recipe.bench_mesh(recipe.BENCH_LENGTH_PARAM_M)),
        _one("aerator", "build", *recipe.aerator_mesh()),
        _one("aerator", "param_change", *recipe.aerator_mesh(recipe.PIPE_LENGTH_PARAM_M)),
    ]
    recipe.publish_bytes(
        OUT / "max-build.json",
        json.dumps({"timing_boundary": "build + FBX export", "rows": rows}, indent=2).encode("utf-8"),
    )
    rt.delete(list(rt.objects))


if __name__ == "__main__":
    main()
