"""Write world-space vertices for Flora source meshes.

Pattern: n/a | new-case: Flora source vertex dump for VPM identity evidence (#216).

The dump is written to the job "out" path, which must be outside this repository.
Job JSON (FLORA_VERTICES_JOB): audit, scenes, copy_sha256, out.
"""
import importlib.util
import json
import os


def _load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _repo_root():
    return os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


def _assert_outside_repo(path):
    repo = _repo_root()
    candidate = os.path.abspath(path)
    try:
        inside = os.path.commonpath([repo, candidate]) == repo
    except ValueError:
        inside = False
    if inside:
        raise RuntimeError("vertex dump must be written outside the repository")


def _builder():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build_flora_library_max.py")
    spec = importlib.util.spec_from_file_location("build_flora_library_max_vertices", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _world_vertices(rt, node):
    mesh = rt.snapshotAsMesh(node)
    try:
        # snapshotAsMesh vertices are already in world space; do not apply a transform again.
        count = int(mesh.numverts)
        points = []
        for index in range(1, count + 1):
            point = rt.meshop.getVert(mesh, index)
            points.append([float(point.x), float(point.y), float(point.z)])
    finally:
        rt.delete(mesh)
    return points


def write_vertices(job):
    for key in ("audit", "scenes", "copy_sha256", "out"):
        if key not in job:
            raise RuntimeError("FLORA_VERTICES_JOB missing " + key)
    _assert_outside_repo(job["out"])
    builder = _builder()
    for name in job["scenes"]:
        if name not in job["copy_sha256"]:
            raise RuntimeError("sha256 missing for " + name)
        digest = builder.file_sha256(job["scenes"][name]).lower()
        if digest != str(job["copy_sha256"][name]).lower():
            raise RuntimeError("sha256 mismatch for " + name)
    audit = _load(job["audit"])
    by_scene = {}
    for scene in audit["scenes"]:
        scene_name = scene["source"]["scene"]
        by_scene.setdefault(scene_name, []).extend(scene["entries"])
    rt = builder._runtime()
    found = {}
    failures = []
    for scene_name, scene_path in job["scenes"].items():
        entries = by_scene.pop(scene_name, [])
        rt.resetMaxFile(rt.Name("noPrompt"))
        if not rt.loadMaxFile(builder.max_path(scene_path), quiet=True):
            for entry in entries:
                failures.append({
                    "entry_id": entry.get("id"),
                    "scene": scene_name,
                    "source_name": entry.get("source_name"),
                    "reason": "loadMaxFile failed",
                })
            continue
        by_name = {}
        for node in list(rt.objects):
            by_name.setdefault(str(node.name), []).append(node)
        for entry in entries:
            item = {
                "source_name": entry["source_name"],
                "source_triangles": entry["triangles"],
                "source_bbox": entry["bbox_m"],
            }
            try:
                matches = [
                    node for node in by_name.get(entry["source_name"], [])
                    if builder._same_source(rt, node, item)
                ]
                if len(matches) != 1:
                    failures.append({
                        "entry_id": entry.get("id"),
                        "scene": scene_name,
                        "source_name": entry.get("source_name"),
                        "reason": f"{len(matches)} nodes match",
                    })
                    continue
                found[entry["id"]] = {"points": _world_vertices(rt, matches[0])}
            except Exception as exc:
                failures.append({
                    "entry_id": entry.get("id"),
                    "scene": scene_name,
                    "source_name": entry.get("source_name"),
                    "reason": str(exc),
                })
    for scene_name, entries in by_scene.items():
        for entry in entries:
            failures.append({
                "entry_id": entry.get("id"),
                "scene": scene_name,
                "source_name": entry.get("source_name"),
                "reason": "scene is not in the job",
            })
    document = {"entries": found, "failures": failures}
    folder = os.path.dirname(os.path.abspath(job["out"]))
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(job["out"], "w", encoding="utf-8") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    print(f"flora-vertices entries={len(found)} failures={len(failures)}")
    return document


def main():
    job_path = os.environ.get("FLORA_VERTICES_JOB")
    if not job_path:
        raise RuntimeError("FLORA_VERTICES_JOB is unset")
    write_vertices(_load(job_path))


if __name__ == "__main__":
    main()
