"""new-case: opt-in native real-fixture parity harness

Pinned AC08 S00/S12/S14 fixtures. Binary FBX and companion readbacks stay
outside git. ``delivery_passed`` is false: this harness does not certify a
delivery and does not change production xView predicates.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import shutil
import sys
import time
from pathlib import Path

DELIVERY_PASSED = False
FIXTURE_ROOT_ENV = "AC08_XVIEW_FIXTURE_ROOT"
NATIVE_DUMP_ENV = "AC08_XVIEW_NATIVE_DUMP"

STATES = {
    "S00_source": {"AC08_body": 143, "AC08_knob": 24, "AC08_plate": 13},
    "S12_join_parts_AC08_body_AC08_plate": {"AC08_body_J_AC08_plate": 156, "AC08_knob": 24},
    "S14_join_parts_AC08_body_AC08_knob": {"AC08_body_J_AC08_knob": 167, "AC08_plate": 13},
}

HASHES = {
    "fbx/S00_source.fbx": "2142e12af1f2f97f51a09dd58e98496eba6d74ff0bd4913706f3128654cccba1",
    "fbx/S12_join_parts_AC08_body_AC08_plate.fbx": "8d119ed3e077f1f4a7a1d394fa955a664fa4474fc7da6fab9417eca3b06b0195",
    "fbx/S14_join_parts_AC08_body_AC08_knob.fbx": "b1177ac2079f388dad1283a87c201b39353db7a4263d0f294e3f587fc07b24a9",
    "readback/S00_source.json": "fbf6eb6c94d506a3d627f3c152755136fdb720c09c88a6858de35f451ecb589f",
    "readback/S12_join_parts_AC08_body_AC08_plate.json": "363c2465fa5c12704242f5f264155c7a2409a7520fb168eae3f6bee9be9f1882",
    "readback/S14_join_parts_AC08_body_AC08_knob.json": "a1f5de678cb2ade9fd4a78a6568d953a21ac6dd0c8f3156447d3408463cc2b60",
}

_PARITY = None
_REPEAT_KEYS = ("vertices", "faces", "overlap_vertices", "overlap_faces", "verts_type", "faces_type", "num_verts", "num_faces")


class HarnessError(Exception):
    """Fail closed. Status is fail; empty input is never pass or not_run."""

    def __init__(self, message, mesh=None):
        self.mesh = mesh
        self.status = "fail"
        text = f"{mesh}: {message}" if mesh else str(message)
        super().__init__(text)


def pinned_table():
    meshes = [{"state": state, "mesh": name, "polygons": count}
              for state, parts in STATES.items() for name, count in parts.items()]
    return {"hashes": dict(HASHES), "meshes": meshes}


def fixture_root():
    raw = os.environ.get(FIXTURE_ROOT_ENV)
    return Path(raw) if raw else None


def _rel(root, rel):
    return Path(root).joinpath(*Path(rel).parts)


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_pinned_hash(rel, digest):
    want = HASHES[rel]
    if digest != want:
        raise HarnessError(f"hash mismatch: {rel}")
    return want


def verify_hashes(root):
    rows = []
    for rel, want in HASHES.items():
        path = _rel(root, rel)
        if not path.is_file():
            raise HarnessError(f"absent fixture: {rel}")
        got = sha256_file(path)
        if got != want:
            raise HarnessError(f"hash mismatch: {rel}")
        rows.append({"path": rel, "sha256": got})
    return rows


def fixture_skip_reason(env=None):
    if env is None:
        env = os.environ
    raw = env.get(FIXTURE_ROOT_ENV)
    if not raw:
        return "AC08_XVIEW_FIXTURE_ROOT unset"
    root = Path(raw)
    if not root.is_dir():
        return f"AC08_XVIEW_FIXTURE_ROOT absent: {raw}"
    missing = [rel for rel in HASHES if not _rel(root, rel).is_file()]
    if missing:
        return "fixture files absent: " + ", ".join(missing)
    return None


def parity_module():
    global _PARITY
    if _PARITY is None:
        repo = Path(__file__).resolve().parents[2]
        spec = importlib.util.spec_from_file_location(
            "xview_parity_ac08", repo / "tools" / "qa" / "xview_parity.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _PARITY = module
    return _PARITY


def _compare(dump):
    return parity_module().compare(dump)


def native_max_selected(markexpr):
    """True when -m positively selects native_max.

    The default addopts expression matches a native_max test without naming
    the marker, so a substring check is not enough: the expression must accept
    a native_max item and reject an item with no marks.
    """
    if not markexpr or "native_max" not in markexpr:
        return False
    from _pytest.mark.expression import Expression
    compiled = Expression.compile(markexpr)
    selected = compiled.evaluate(lambda name: name == "native_max")
    vacuous = compiled.evaluate(lambda name: False)
    return bool(selected) and not bool(vacuous)


def ping_max():
    script = Path("C:/Users/artsafro/hermes_kanban/scripts/max_exec.py")
    if not script.is_file():
        return False, "max_exec.py absent"
    proc = __import__("subprocess").run(
        [sys.executable, str(script), "--ping"],
        capture_output=True, text=True, timeout=120,
    )
    detail = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode == 0, detail


def native_skip_reason(markexpr, env, ping=None):
    env = env or {}
    dump = env.get(NATIVE_DUMP_ENV)
    if dump:
        if not Path(dump).is_file():
            return f"AC08_XVIEW_NATIVE_DUMP absent: {dump}"
        return None
    if native_max_selected(markexpr or ""):
        ok, detail = (ping or ping_max)()
        if not ok:
            return f"native_max ping failed: {detail}"
        return None
    return "native marker missing: set AC08_XVIEW_NATIVE_DUMP or select pytest -m native_max"


_FROZEN_CONTEXT = (
    ("m_per_unit", 1, "metre units"),
    ("tol_v_units", 0.002, "2 mm vertex tolerance"),
    ("tol_f_units", 0.005, "5 mm face tolerance"),
)
_POLY_CLASS = "Editable_Poly"


def _failure_text(failures):
    if not isinstance(failures, list):
        return f"failures: {failures!r}"
    return "failures: " + "; ".join(map(str, failures))


def _reject_nonfinite(value, what, mesh=None):
    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise HarnessError(f"non-finite {what}: {value!r}", mesh=mesh)
        return
    if isinstance(value, dict):
        child = value.get("name") if isinstance(value.get("name"), str) else mesh
        for key, item in value.items():
            _reject_nonfinite(item, key if not what else f"{what}.{key}", child)
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_nonfinite(item, f"{what}[{index}]", mesh)


def _frozen_context(item):
    for key, want, label in _FROZEN_CONTEXT:
        value = item.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            kind = "unsupported units" if key == "m_per_unit" else "non-finite"
            raise HarnessError(f"{key}: {value!r} {kind} ({label})")
        if not math.isfinite(value):
            raise HarnessError(f"{key}: {value!r} is non-finite ({label})")
        if float(value) != float(want):
            raise HarnessError(f"{key}: {value!r} is not frozen {label} ({want})")


def _import_context(item):
    """Reject a failed or unpinned import before grouping can drop it."""
    state, rep = item["state"], item["rep"]
    if "import_ok" not in item:
        raise HarnessError(f"import_ok missing for {state}/{rep}")
    if item["import_ok"] is not True:
        raise HarnessError(f"import_ok {item['import_ok']!r} for {state}/{rep}")
    _frozen_context(item)
    if item.get("failures"):
        raise HarnessError(_failure_text(item["failures"]))
    nodes = item.get("nodes")
    if not isinstance(nodes, list):
        return
    for node in nodes:
        if not isinstance(node, dict):
            raise HarnessError("incomplete dump")
        name = node.get("name")
        if node.get("class") != _POLY_CLASS:
            raise HarnessError(f"class {node.get('class')!r} is not {_POLY_CLASS}", mesh=name)
        if "geometry_unchanged" not in node:
            raise HarnessError("geometry_unchanged missing", mesh=name)
        if node.get("geometry_unchanged") is not True:
            raise HarnessError(f"geometry_unchanged {node.get('geometry_unchanged')!r}", mesh=name)
        if node.get("error"):
            raise HarnessError(str(node["error"]), mesh=name)
        _reject_nonfinite(node, "", name)


def _require_campaign(grouped, synthetic):
    missing = [state for state in STATES if state not in grouped]
    unknown = [state for state in grouped if state not in STATES]
    pinned = [state for state in grouped if state in STATES]
    if synthetic:
        if unknown and pinned:
            raise HarnessError("unknown state " + ", ".join(unknown))
        return
    if missing and unknown:
        raise HarnessError("unknown state " + ", ".join(unknown))
    if missing:
        raise HarnessError("missing state " + ", ".join(missing))
    if unknown:
        raise HarnessError("extra state " + ", ".join(unknown))


def _require_reps(state, reps):
    missing = [rep for rep in (1, 2) if rep not in reps]
    unknown = [rep for rep in reps if rep not in (1, 2)]
    if not missing and not unknown:
        return
    bits = []
    if unknown:
        bits.append("unknown rep " + ", ".join(str(rep) for rep in unknown))
    if missing:
        bits.append("missing rep " + ", ".join(str(rep) for rep in missing))
    raise HarnessError("; ".join(bits) + f" for state {state}")


def _signature(node):
    return tuple(node.get(key) for key in _REPEAT_KEYS)


def _check_repeat(first, second):
    left = {node.get("name"): node for node in first.get("nodes") or []}
    right = {node.get("name"): node for node in second.get("nodes") or []}
    for name in sorted(set(left) | set(right), key=lambda item: "" if item is None else str(item)):
        if name not in left or name not in right or _signature(left[name]) != _signature(right[name]):
            raise HarnessError("repeat mismatch between the 2 imports", mesh=name)


def _inventory(state, nodes):
    if not isinstance(nodes, list) or not nodes:
        raise HarnessError("incomplete dump")
    present = []
    for node in nodes:
        if not isinstance(node, dict) or not node.get("name"):
            raise HarnessError("incomplete dump")
        present.append(node["name"])
    if len(present) != len(set(present)):
        duplicate = next(name for name in present if present.count(name) > 1)
        raise HarnessError(f"duplicate node {duplicate}", mesh=duplicate)
    if state not in STATES:
        return
    missing = [name for name in STATES[state] if name not in present]
    unknown = [name for name in present if name not in STATES[state]]
    if unknown and missing:
        raise HarnessError(f"unknown node {unknown[0]}", mesh=unknown[0])
    if missing:
        raise HarnessError(f"missing node {missing[0]}", mesh=missing[0])
    if unknown:
        raise HarnessError(f"extra node {unknown[0]}", mesh=unknown[0])
    by_name = {node["name"]: node for node in nodes}
    for name, count in STATES[state].items():
        faces = by_name[name].get("faces")
        if not isinstance(faces, list) or len(faces) != count:
            raise HarnessError(f"wrong polygon count {len(faces) if isinstance(faces, list) else None} != {count}",
                               mesh=name)


def _counts(node):
    name = node.get("name")
    pairs = (
        ("verts_count", "overlap_vertices"),
        ("faces_count", "overlap_faces"),
        ("num_verts", "vertices"),
        ("num_faces", "faces"),
    )
    for count_key, list_key in pairs:
        if count_key not in node:
            continue
        values = node.get(list_key)
        if not isinstance(values, list) or node[count_key] != len(values):
            raise HarnessError("count inconsistent with list", mesh=name)


def _finite(node):
    name = node.get("name")
    verts = node.get("vertices")
    if not isinstance(verts, list) or not verts:
        raise HarnessError("incomplete dump", mesh=name)
    for vert in verts:
        if not isinstance(vert, (list, tuple)) or len(vert) != 3:
            raise HarnessError("incomplete dump", mesh=name)
        for coord in vert:
            if isinstance(coord, bool) or not isinstance(coord, (int, float)) or not math.isfinite(coord):
                raise HarnessError("non-finite coordinate", mesh=name)


def _row_ids(node, row):
    max_v = set(node.get("overlap_vertices") or [])
    max_f = set(node.get("overlap_faces") or [])
    ours_v = (max_v - set(row["vertices_only_max"])) | set(row["vertices_only_ours"])
    ours_f = (max_f - set(row["faces_only_max"])) | set(row["faces_only_ours_contact"])
    stored = dict(row)
    stored["ours_vertex_ids"] = sorted(ours_v)
    stored["ours_contact_ids"] = sorted(ours_f)
    return stored


def _one(item, node):
    name = node.get("name")
    if node.get("error"):
        raise HarnessError(str(node["error"]), mesh=name)
    _counts(node)
    _finite(node)
    payload = {
        "m_per_unit": item.get("m_per_unit"),
        "tol_v_units": item.get("tol_v_units"),
        "tol_f_units": item.get("tol_f_units"),
        "nodes": [node],
    }
    try:
        rows = _compare(payload)
    except parity_module().DumpError as exc:
        raise HarnessError(str(exc), mesh=name) from exc
    if len(rows) != 1 or not rows[0].get("equal"):
        raise HarnessError("symmetric difference", mesh=name)
    return _row_ids(node, rows[0])


def evaluate(dump):
    if not isinstance(dump, dict) or not isinstance(dump.get("imports"), list) or not dump["imports"]:
        raise HarnessError("empty input")
    synthetic = dump.get("synthetic") is True
    failures = dump.get("failures")
    if failures:
        raise HarnessError(_failure_text(failures))
    seen = set()
    parsed = []
    for item in dump["imports"]:
        if not isinstance(item, dict) or "state" not in item or "rep" not in item:
            raise HarnessError("incomplete dump")
        rep = item["rep"]
        if isinstance(rep, bool) or not isinstance(rep, int):
            raise HarnessError(f"unknown rep {rep!r} for state {item['state']}")
        ident = (item["state"], rep)
        if ident in seen:
            raise HarnessError(f"duplicate state/rep {item['state']}/{rep}")
        seen.add(ident)
        parsed.append(item)
    for item in parsed:
        _import_context(item)
    grouped = {}
    for item in parsed:
        grouped.setdefault(item["state"], {})[item["rep"]] = item
    _require_campaign(grouped, synthetic)
    rows = []
    for state, reps in grouped.items():
        _require_reps(state, reps)
        _check_repeat(reps[1], reps[2])
        for rep in (1, 2):
            item = reps[rep]
            nodes = item.get("nodes")
            _inventory(state, nodes)
            for node in nodes:
                rows.append(_one(item, node))
    return {
        "status": "pass",
        "delivery_passed": False,
        "synthetic": synthetic,
        "rows": rows,
        "mesh_import_rows": len(rows),
    }


def confirm_native(dump):
    if not isinstance(dump, dict) or dump.get("synthetic") is True:
        raise HarnessError("synthetic dump cannot confirm native parity")
    report = evaluate(dump)
    if report["mesh_import_rows"] != 14:
        raise HarnessError(f"expected 14 mesh/import rows, got {report['mesh_import_rows']}")
    return report


def python_baseline(root):
    parity = parity_module()
    rows = []
    for state, expected in STATES.items():
        path = _rel(root, f"readback/{state}.json")
        document = json.loads(path.read_text(encoding="utf-8"))
        meshes = {mesh["name"]: mesh for mesh in document["meshes"]}
        for name, count in expected.items():
            if name not in meshes:
                raise HarnessError("missing mesh", mesh=name)
            geometry = meshes[name]["face_geometry"]
            polygons = geometry["polygons"]
            if len(polygons) != count:
                raise HarnessError(f"wrong polygon count {len(polygons)} != {count}", mesh=name)
            poly = parity.PolyMesh(
                __import__("numpy").asarray(geometry["vertices"], dtype=float),
                tuple(tuple(face) for face in polygons),
            )
            produced = parity.part_report(name, poly, parity.XviewTolerance())
            rows.append({
                "state": state,
                "node": name,
                "polygons": len(polygons),
                "vertex_ids": len(produced.vertices),
                "xview_faces": len(produced.xview_faces),
                "synthetic": False,
                "delivery_passed": False,
            })
    return rows


def _conflicts(inputs, out):
    same = parity_module().same_file
    return any(same(src, out) for src in inputs)


def write_report(inputs, out, dump):
    if _conflicts(inputs, out):
        return 2
    try:
        report = evaluate(dump)
    except HarnessError:
        return 2
    Path(out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0


def render_native_ms(work):
    code = (
        "import runpy; runpy.run_path("
        + repr(str(Path(__file__).resolve()))
        + ", run_name='ac08_xview')['native']("
        + repr(str(Path(work)))
        + ")"
    )
    return (
        "holdMaxFile()\n"
        "try (python.Execute " + json.dumps(code) + ") catch "
        "(format \"AC08_XVIEW_ERROR %\\n\" (getCurrentException()))\n"
        "fetchMaxFile quiet:true\n"
    )


def prepare(work, source=None):
    root = Path(source) if source is not None else fixture_root()
    if root is None:
        raise HarnessError("AC08_XVIEW_FIXTURE_ROOT unset")
    if not root.is_dir():
        raise HarnessError(f"AC08_XVIEW_FIXTURE_ROOT absent: {root}")
    verify_hashes(root)
    work = Path(work)
    if work.exists():
        raise HarnessError(f"work directory exists: {work}")
    work.mkdir(parents=True)
    for rel in HASHES:
        destination = _rel(work, rel)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_rel(root, rel), destination)
    verify_hashes(work)
    (work / "native.ms").write_text(render_native_ms(work), encoding="utf-8")
    print("PREPARED", work, "hashes", len(HASHES))
    return work


def native(work):
    """Run inside 3ds Max. Holds the current scene and restores it."""
    import pymxs

    runtime = pymxs.runtime
    work = Path(work)
    result = {
        "application": "3ds Max live",
        "max_version": list(runtime.maxVersion()),
        "python": platform.python_version(),
        "delivery_passed": False,
        "imports": [],
        "failures": [],
    }
    old_units = runtime.units.SystemType, runtime.units.SystemScale
    old_v, old_f = runtime.OverlappingVertices.tolerance, runtime.OverlappingFaces.tolerance
    start = time.perf_counter()
    try:
        runtime.units.SystemType = runtime.Name("meters")
        runtime.units.SystemScale = 1.0
        checkers = {str(runtime.xViewChecker.getCheckerName(i)): i
                    for i in range(1, int(runtime.xViewChecker.getNumCheckers()) + 1)}
        for rep in range(2):
            for state, expected in STATES.items():
                runtime.delete(runtime.objects)
                runtime.FBXImporterSetParam("ResetImport")
                runtime.FBXImporterSetParam("Mode", runtime.Name("create"))
                runtime.FBXImporterSetParam("ConvertUnit", "m")
                runtime.FBXImporterSetParam("SmoothingGroups", True)
                runtime.FBXImporterSetParam("Animation", False)
                ok = runtime.importFile(str(work / "fbx" / (state + ".fbx")), runtime.Name("noPrompt"), using=runtime.FBXIMP)
                item = {
                    "state": state, "rep": rep + 1, "import_ok": bool(ok),
                    "m_per_unit": 1, "tol_v_units": 0.002, "tol_f_units": 0.005,
                    "nodes": [], "failures": [],
                }
                result["imports"].append(item)
                nodes = list(runtime.geometry)
                if sorted(str(obj.name) for obj in nodes) != sorted(expected):
                    item["failures"].append("inventory mismatch")
                for obj in nodes:
                    record = {"name": str(obj.name), "class": str(runtime.classOf(obj))}
                    item["nodes"].append(record)
                    if runtime.classOf(obj) != runtime.Editable_Poly:
                        record["error"] = "not Editable_Poly"
                        continue

                    def arrays(target=obj):
                        verts = [[float(c) for c in runtime.polyop.getVert(target, i)]
                                 for i in range(1, int(runtime.polyop.getNumVerts(target)) + 1)]
                        faces = [[int(v) for v in runtime.polyop.getFaceVerts(target, i)]
                                 for i in range(1, int(runtime.polyop.getNumFaces(target)) + 1)]
                        return verts, faces

                    record["vertices"], record["faces"] = arrays()
                    record["num_verts"] = len(record["vertices"])
                    record["num_faces"] = len(record["faces"])
                    if record["num_faces"] != expected.get(record["name"]):
                        record["error"] = "polygon count mismatch"
                    runtime.clearSelection()
                    runtime.select(obj)
                    runtime.execute("max modify mode")
                    runtime.OverlappingVertices.tolerance = runtime.units.decodeValue("2mm")
                    runtime.OverlappingFaces.tolerance = runtime.units.decodeValue("5mm")
                    for label, prefix, selection in (
                            ("Overlapping Vertices", "verts", runtime.polyop.getVertSelection),
                            ("Overlapping Faces", "faces", runtime.polyop.getFaceSelection)):
                        runtime.polyop.setVertSelection(obj, runtime.BitArray())
                        runtime.polyop.setFaceSelection(obj, runtime.BitArray())
                        runtime.xViewChecker.activeIndex = checkers[label]
                        runtime.xViewChecker.on = True
                        runtime.xViewChecker.runCheck(runtime.currentTime)
                        native_kind = runtime.xViewChecker.getCurrentReturnVal()
                        expected_kind = runtime.Name("Vertices" if prefix == "verts" else "Faces")
                        kind = "#" + str(native_kind)
                        count = int(runtime.xViewChecker.getCurrentOutputCount())
                        ids = [int(i) for i in selection(obj)] if count > 0 else []
                        runtime.xViewChecker.on = False
                        record[prefix + "_type"] = kind
                        record["overlap_vertices" if prefix == "verts" else "overlap_faces"] = ids
                        record["verts_count" if prefix == "verts" else "faces_count"] = count
                        if native_kind != expected_kind or len(ids) != count:
                            record["error"] = "checker type/count failure: " + label
                    record["geometry_unchanged"] = arrays() == (record["vertices"], record["faces"])
                (work / "native.json").write_text(json.dumps(result), encoding="utf-8")
    except Exception as exc:
        result["failures"].append(type(exc).__name__ + ": " + str(exc))
    finally:
        runtime.xViewChecker.on = False
        runtime.OverlappingVertices.tolerance, runtime.OverlappingFaces.tolerance = old_v, old_f
        runtime.units.SystemType, runtime.units.SystemScale = old_units
        result["seconds"] = time.perf_counter() - start
        (work / "native.json").write_text(json.dumps(result), encoding="utf-8")
        print("AC08_XVIEW_NATIVE", len(result["imports"]), result["failures"])


def compare_work(work, out, baseline_only=False):
    work = Path(work)
    out = Path(out)
    inputs = [_rel(work, rel) for rel in HASHES]
    native_path = work / "native.json"
    if native_path.exists():
        inputs.append(native_path)
    if _conflicts(inputs, out):
        return 2
    try:
        verify_hashes(work)
        report = {
            "delivery_passed": False,
            "synthetic": False,
            "baseline": python_baseline(work),
        }
        if not baseline_only:
            if not native_path.is_file():
                raise HarnessError("empty input")
            dump = json.loads(native_path.read_text(encoding="utf-8"))
            report["native"] = confirm_native(dump)
            report["status"] = "pass"
        else:
            report["status"] = "pass"
    except HarnessError as exc:
        print(f"ac08-xview-native-parity: {exc}", file=sys.stderr)
        return 2
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "delivery_passed": False,
                      "baseline": [(row["state"], row["node"], row["polygons"], row["vertex_ids"], row["xview_faces"])
                                   for row in report["baseline"]]}, indent=2))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("stage", choices=("prepare", "compare"))
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--baseline-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.stage == "prepare":
            prepare(args.work, args.source)
            return 0
        if args.out is None:
            print("compare requires --out", file=sys.stderr)
            return 2
        return compare_work(args.work, args.out, baseline_only=args.baseline_only)
    except HarnessError as exc:
        print(f"ac08-xview-native-parity: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
