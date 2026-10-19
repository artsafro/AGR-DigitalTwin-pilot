"""Write world-space triangles of the Flora library objects for the NPM/VPM surface-identity report.

Pattern: n/a | new-case: Flora library face dump for the NPM/VPM surface-identity report (#305).

Runs in headless 3ds Max (``dcc_batch.py max --file``) on a COPY of the library .max; the copy is loaded,
never saved. Job JSON (env FLORA_FACES_JOB): ``library`` (path of the copy), ``library_sha256`` (of the copy,
checked before loading), ``objects`` (object names), ``out`` (outside this repository).
Output: ``{"library_file", "library_sha256", "entries": {name: {"triangles": [...]}}, "failures": [...]}``.
A name that matches zero or several nodes is a failure, never a guess.
"""
import hashlib
import json
import os


def _load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _repo_root():
    return os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


def _inside(path, folder):
    try:
        return os.path.commonpath([os.path.abspath(folder), os.path.abspath(path)]) == os.path.abspath(folder)
    except ValueError:
        return False


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_job(job):
    for key in ("library", "library_sha256", "objects", "out"):
        if key not in job:
            raise RuntimeError("FLORA_FACES_JOB missing " + key)
    if _inside(job["out"], _repo_root()):
        raise RuntimeError("face dump must be written outside the repository")
    if os.path.normcase(os.path.abspath(job["out"])) == os.path.normcase(os.path.abspath(job["library"])):
        raise RuntimeError("out resolves to the library copy")
    if not isinstance(job["objects"], list) or not job["objects"]:
        raise RuntimeError("objects must be a non-empty list")
    if file_sha256(job["library"]).lower() != str(job["library_sha256"]).lower():
        raise RuntimeError("sha256 mismatch for the library copy")


def _triangles(rt, node):
    mesh = rt.snapshotAsMesh(node)
    try:
        # snapshotAsMesh vertices are already in world space; no extra node transform.
        verts = [rt.getVert(mesh, index) for index in range(1, int(rt.getNumVerts(mesh)) + 1)]
        points = [[float(p.x), float(p.y), float(p.z)] for p in verts]
        faces = []
        for index in range(1, int(rt.getNumFaces(mesh)) + 1):
            face = rt.getFace(mesh, index)
            faces.append([points[int(face.x) - 1], points[int(face.y) - 1], points[int(face.z) - 1]])
    finally:
        rt.delete(mesh)
    return faces


def write_faces(job):
    check_job(job)
    from pymxs import runtime as rt

    rt.resetMaxFile(rt.Name("noPrompt"))
    if not rt.loadMaxFile(os.path.abspath(job["library"]).replace("\\", "/"), quiet=True):
        raise RuntimeError("loadMaxFile failed")
    by_name = {}
    for node in list(rt.objects):
        by_name.setdefault(str(node.name), []).append(node)
    entries, failures = {}, []
    for name in job["objects"]:
        matches = by_name.get(name, [])
        if len(matches) != 1:
            failures.append({"object": name, "reason": f"{len(matches)} nodes match"})
            continue
        try:
            entries[name] = {"triangles": _triangles(rt, matches[0])}
        except Exception as exc:  # recorded per object, never dropped
            failures.append({"object": name, "reason": str(exc)})
    document = {
        "library_file": job.get("library_source", job["library"]),
        "library_sha256": str(job["library_sha256"]).lower(),
        "entries": entries,
        "failures": failures,
    }
    folder = os.path.dirname(os.path.abspath(job["out"]))
    os.makedirs(folder, exist_ok=True)
    with open(job["out"], "w", encoding="utf-8") as handle:
        json.dump(document, handle)
        handle.write("\n")
    print(f"flora-library-faces entries={len(entries)} failures={len(failures)}")
    return document


def main():
    job_path = os.environ.get("FLORA_FACES_JOB")
    if not job_path:
        raise RuntimeError("FLORA_FACES_JOB is unset")
    write_faces(_load(job_path))


if __name__ == "__main__":
    main()
