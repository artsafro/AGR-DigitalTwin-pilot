"""Rebind Flora library diffuse and opacity slots onto published maps (#282).

Pattern: n/a | new-case: path binding only; geometry, pivots and material IDs stay as saved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MAPS_ROOT = "C:/x/flora-library/v001/maps"
LIBRARY_V003 = "C:/x/flora-library/v003/flora-library-v003.max"
PROTECTED_ROOTS = (
    "C:/x/flora-library/v001",
    "C:/x/flora-library/v002",
)
DCC_BATCH = r"C:\Users\artsafro\hermes_kanban\scripts\dcc_batch.py"
_REVIEW_PARTS = {"review", "temporary", "temp", "tmp"}
_SLOTS = ("diffuse", "opacity")


class RebindError(RuntimeError):
    """The rebind cannot be saved. Callers must leave inputs untouched."""


def _resolved(path) -> str:
    return os.path.normcase(os.path.normpath(os.path.realpath(os.path.abspath(os.fspath(path)))))


def _parts(path) -> list[str]:
    text = os.fspath(path).replace("/", "\\")
    return [part.lower() for part in text.split("\\") if part and part not in {".", ".."}]


def is_review_or_temporary(path) -> bool:
    if not isinstance(path, (str, Path)):
        return True
    parts = _parts(path)
    try:
        parts += _parts(os.path.normpath(os.fspath(path)))
    except (OSError, ValueError):
        return True
    for part in parts:
        if part in _REVIEW_PARTS or "review" in part or part.startswith("t_"):
            return True
    return False


def published_folder(path, slot: str, maps_root: str = MAPS_ROOT) -> str:
    """Return the single species folder under the published maps root.

    A path that stops on the maps root, or on the species folder, is the boundary
    and is rejected. The published slug is the folder already approved on disk
    (Späth is ``sp-th``), not a freshly derived stem.
    """
    if slot not in _SLOTS:
        raise RebindError("unsupported map slot")
    if not isinstance(path, str) or not path or is_review_or_temporary(path):
        raise RebindError(f"{slot} path is empty or points at a review folder")
    if Path(path).suffix.lower() != ".png":
        raise RebindError(f"{slot} path is not a png")
    root = _resolved(maps_root)
    target = _resolved(path)
    prefix = root + os.sep
    if not target.startswith(prefix):
        raise RebindError(f"{slot} path is outside the published maps")
    parts = target[len(prefix):].split(os.sep)
    if len(parts) != 2 or parts[1] != f"{slot}-v001.png" or not parts[0]:
        raise RebindError(f"{slot} path is not a published species map")
    if is_review_or_temporary(parts[0]):
        raise RebindError(f"{slot} folder is a review folder")
    return parts[0]


def assert_published_map(path, folder: str, slot: str, maps_root: str = MAPS_ROOT) -> None:
    found = published_folder(path, slot, maps_root)
    if os.path.normcase(found) != os.path.normcase(folder):
        raise RebindError(f"{slot} path is not the published map")


def _finite(value, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RebindError(f"unsupported {label}")
    if isinstance(value, float) and not math.isfinite(value):
        raise RebindError(f"{label} is not finite")


def plan_bindings(catalogue: dict, maps_root: str = MAPS_ROOT) -> list[dict]:
    if not isinstance(catalogue, dict):
        raise RebindError("catalogue is not an object")
    species = catalogue.get("species")
    if not isinstance(species, list) or not species:
        raise RebindError("empty species list")
    plan = []
    seen = set()
    for item in species:
        if not isinstance(item, dict):
            raise RebindError("species row is not an object")
        _finite(item.get("material_id"), "material id")
        if not isinstance(item.get("material_id"), int):
            raise RebindError("material id is not an int")
        latin = item.get("latin")
        if not isinstance(latin, str) or not latin.strip():
            raise RebindError("species latin is empty")
        maps = item.get("maps")
        objects = item.get("objects")
        if not isinstance(maps, dict) or not isinstance(objects, dict):
            raise RebindError("partial species row")
        if maps.get("review_status") != "approved":
            raise RebindError("unsupported review status")
        slots = {}
        folders = []
        for slot in _SLOTS:
            slots[slot] = maps.get(slot)
            folders.append(published_folder(slots[slot], slot, maps_root))
        if folders[0] != folders[1]:
            raise RebindError("diffuse and opacity are not the same published species")
        folder = folders[0]
        names = [("NPM", objects.get("NPM"))]
        if objects.get("VPM"):
            names.append(("VPM", objects.get("VPM")))
        if not isinstance(names[0][1], str) or not names[0][1]:
            raise RebindError("partial object names")
        for _profile, name in names:
            if not isinstance(name, str) or not name or name in seen:
                raise RebindError("partial or duplicate object name")
            seen.add(name)
            plan.append({
                "name": name,
                "material_id": item["material_id"],
                "folder": folder,
                "diffuse": slots["diffuse"],
                "opacity": slots["opacity"],
            })
    if not plan:
        raise RebindError("empty binding plan")
    return plan


def _inside(path: str, root: str) -> bool:
    return path == root or path.startswith(root + os.sep)


def conflicts(output, protected) -> bool:
    if output is None or output == "":
        return True
    try:
        target = _resolved(output)
    except (OSError, ValueError):
        return True
    for root in PROTECTED_ROOTS:
        if _inside(target, _resolved(root)):
            return True
    for item in protected or []:
        try:
            other = _resolved(item)
        except (OSError, ValueError):
            return True
        if target == other:
            return True
        if os.path.isdir(os.fspath(item)) and _inside(target, other):
            return True
    return False


def commit_new_file(output, protected, writer) -> None:
    if writer is None or conflicts(output, protected) or os.path.exists(os.fspath(output)):
        raise RebindError("refusing to write over an input or an existing file")
    writer(os.fspath(output))


def _row_ok(row: dict) -> None:
    if not isinstance(row, dict):
        raise RebindError("snapshot row is not an object")
    ids = row.get("material_ids")
    pivot = row.get("pivot")
    if not isinstance(ids, list) or not ids or not isinstance(pivot, list) or len(pivot) != 3:
        raise RebindError("partial snapshot")
    for value in ids:
        _finite(value, "material id")
    for value in pivot:
        _finite(value, "pivot")
    _finite(row.get("triangles"), "triangles")


def rebind_records(records: dict, plan: list[dict]) -> dict:
    if not isinstance(records, dict) or not records or not plan:
        raise RebindError("empty scene or plan")
    expected = {item["name"]: item for item in plan}
    if len(expected) != len(plan) or set(records) != set(expected):
        raise RebindError("partial scene")
    rebound = {}
    for name, row in records.items():
        _row_ok(row)
        item = expected[name]
        rebound[name] = {
            "diffuse": item["diffuse"],
            "opacity": item["opacity"],
            "material_ids": list(row["material_ids"]),
            "pivot": list(row["pivot"]),
            "triangles": row["triangles"],
        }
    return rebound


def exceeds(value, limit) -> bool:
    for number in (value, limit):
        _finite(number, "threshold")
    return value >= limit


def measure(rows: dict, plan: list[dict]) -> dict:
    if not isinstance(rows, dict) or not isinstance(plan, list):
        raise RebindError("unsupported measure input")
    expected = {item["name"]: item for item in plan}
    if len(expected) != len(plan):
        raise RebindError("duplicate plan names")
    for row in rows.values():
        _row_ok(row)
    matched = 0
    outside = 0
    found = 0
    for name, item in expected.items():
        row = rows.get(name)
        if row is None:
            continue
        found += 1
        for slot in _SLOTS:
            path = row.get(slot)
            published = item[slot]
            if isinstance(path, str) and not is_review_or_temporary(path) and _resolved(path) == _resolved(published):
                matched += 1
            else:
                outside += 1
    extra = [name for name in rows if name not in expected]
    return {
        "objects_expected": len(expected),
        "objects_found": found,
        "bindings_expected": len(expected) * 2,
        "bindings_matched": matched,
        "paths_outside": outside + 2 * len(extra),
        "extra": len(extra),
    }


def verdict(measured: dict) -> dict:
    keys = ("objects_expected", "objects_found", "bindings_expected", "bindings_matched", "paths_outside")
    if not isinstance(measured, dict) or any(key not in measured for key in keys):
        raise RebindError("partial verdict")
    values = [measured[key] for key in keys]
    for value in values:
        _finite(value, "count")
        if not isinstance(value, int) or value < 0:
            raise RebindError("unsupported count")
    expected_objects = measured["objects_expected"]
    expected_bindings = measured["bindings_expected"]
    passed = (
        expected_objects > 0
        and expected_bindings == expected_objects * 2
        and measured["objects_found"] == expected_objects
        and measured["bindings_matched"] == expected_bindings
        and measured["paths_outside"] == 0
        and measured.get("extra", 0) == 0
    )
    result = dict(measured)
    result["passed"] = passed
    result["status"] = "pass" if passed else "fail"
    return result


def hash_files(paths) -> dict:
    if not paths:
        raise RebindError("empty hash set")
    digest = {}
    for path in paths:
        target = os.fspath(path)
        if not os.path.isfile(target):
            raise RebindError("missing file " + target)
        digest[_resolved(target)] = hashlib.sha256(Path(target).read_bytes()).hexdigest()
    if not digest:
        raise RebindError("empty hash set")
    return digest


def assert_hashes_unchanged(before: dict, after: dict) -> None:
    if not isinstance(before, dict) or not isinstance(after, dict) or not before or not after:
        raise RebindError("empty hashes")
    if set(before) != set(after) or any(before[key] != after[key] for key in before):
        raise RebindError("approval asset hash changed")


def _max_path(path: str) -> str:
    return os.path.abspath(path).replace("\\", "/")


def _missing(rt, node) -> bool:
    return node is None or node == rt.undefined


def _bitmap_name(rt, texture):
    if _missing(rt, texture):
        return None
    try:
        name = texture.filename
    except Exception:
        return None
    if _missing(rt, name):
        return None
    return str(name)


def _snapshot(rt) -> dict:
    rows = {}
    for node in list(rt.objects):
        name = str(node.name)
        faces = int(rt.getNumFaces(node))
        ids = [int(rt.getFaceMatID(node, face)) for face in range(1, faces + 1)]
        mat = node.material
        diffuse = opacity = None
        if not _missing(rt, mat):
            diffuse = _bitmap_name(rt, getattr(mat, "diffuseMap", None))
            opacity = _bitmap_name(rt, getattr(mat, "opacityMap", None))
        rows[name] = {
            "diffuse": diffuse,
            "opacity": opacity,
            "material_ids": ids,
            "pivot": [float(node.pivot.x), float(node.pivot.y), float(node.pivot.z)],
            "triangles": faces,
        }
    return rows


def _geometry_same(before: dict, after: dict) -> bool:
    if set(before) != set(after):
        return False
    for name, left in before.items():
        right = after[name]
        if left["material_ids"] != right["material_ids"]:
            return False
        if left["pivot"] != right["pivot"]:
            return False
        if left["triangles"] != right["triangles"]:
            return False
    return True


def _apply(rt, plan: list[dict]) -> None:
    by_name = {str(node.name): node for node in list(rt.objects)}
    for item in plan:
        node = by_name.get(item["name"])
        if node is None:
            raise RebindError("missing object " + item["name"])
        mat = node.material
        if _missing(rt, mat):
            raise RebindError("missing material " + item["name"])
        for slot, key in (("diffuseMap", "diffuse"), ("opacityMap", "opacity")):
            tex = getattr(mat, slot)
            if _missing(rt, tex):
                tex = rt.Bitmaptexture()
                setattr(mat, slot, tex)
            tex.filename = item[key]


def _pivot_drift(before: dict, after: dict, limit: float = 1e-5) -> bool:
    """True when a pivot moved by at least `limit` (exactly `limit` is a drift)."""
    if set(before) != set(after):
        return True
    for name, left in before.items():
        for old, new in zip(left["pivot"], after[name]["pivot"]):
            if not math.isfinite(old) or not math.isfinite(new) or abs(old - new) >= limit:
                return True
    return False


def run_in_max(job_path: str) -> None:
    with open(job_path, encoding="utf-8") as handle:
        job = json.load(handle)
    output = job["output"]
    report_path = job["report"]
    protected = job["protected"]
    plan = job["bindings"]
    if conflicts(output, protected) or os.path.exists(output):
        raise RebindError("refusing to write over an input or an existing file")
    from pymxs import runtime as rt

    before = _snapshot(rt)
    _apply(rt, plan)
    after = _snapshot(rt)
    if not _geometry_same(before, after):
        raise RebindError("ids or pivots changed before save")
    os.makedirs(os.path.dirname(output), exist_ok=True)
    saved = rt.saveMaxFile(_max_path(output), quiet=True)
    if not saved or not os.path.isfile(output):
        if os.path.isfile(output):
            os.remove(output)
        raise RebindError("saveMaxFile failed")
    rt.resetMaxFile(rt.Name("noPrompt"))
    if not rt.loadMaxFile(_max_path(output), quiet=True):
        os.remove(output)
        raise RebindError("readback load failed")
    read = _snapshot(rt)
    measured = measure(read, plan)
    result = verdict(measured)
    result["ids_unchanged"] = set(before) == set(read) and all(
        before[name]["material_ids"] == read[name]["material_ids"] for name in before
    )
    result["pivots_unchanged"] = not _pivot_drift(before, read)
    result["triangles_unchanged"] = all(
        name in read and before[name]["triangles"] == read[name]["triangles"] for name in before
    )
    result["passed"] = bool(result["passed"] and result["ids_unchanged"] and result["pivots_unchanged"]
                             and result["triangles_unchanged"])
    result["status"] = "pass" if result["passed"] else "fail"
    result["rows"] = [
        {
            "name": name,
            "diffuse": read[name]["diffuse"],
            "opacity": read[name]["opacity"],
            "material_ids": sorted(set(read[name]["material_ids"])),
            "pivot": read[name]["pivot"],
            "triangles": read[name]["triangles"],
        }
        for name in sorted(read)
    ]
    if not result["passed"] and os.path.isfile(output):
        os.remove(output)
    folder = os.path.dirname(report_path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    print(
        "AGR_REBIND passed={passed} objects={found}/{expected} bindings={matched}/{bindings} outside={outside}".format(
            passed=str(result["passed"]).lower(),
            found=result["objects_found"],
            expected=result["objects_expected"],
            matched=result["bindings_matched"],
            bindings=result["bindings_expected"],
            outside=result["paths_outside"],
        )
    )
    if not result["passed"]:
        raise RebindError("readback failed")


def _load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _preserved_paths(plan: list[dict], source: str) -> list[str]:
    paths = [
        source,
        "C:/x/flora-library/v001/flora-library-v001.max",
        "C:/x/flora-library/v002/flora-library-v002.max",
        "C:/x/flora-library/v001/maps/library-v001.json",
        "C:/x/flora-library/v001/maps/library-batch2-v001.json",
        "C:/x/flora-library/v001/maps/library-190-copies-v001.json",
    ]
    for version in ("v001", "v002"):
        parts = Path(f"C:/x/flora-library/{version}/parts")
        if parts.is_dir():
            paths.extend(str(path) for path in parts.glob("*.max"))
    for item in plan:
        paths.extend(item[slot] for slot in _SLOTS)
    unique = []
    seen = set()
    for path in paths:
        key = _resolved(path)
        if key not in seen and os.path.isfile(path):
            seen.add(key)
            unique.append(path)
    return unique


def execute(catalogue_path: str, source: str, output: str, report: str) -> dict:
    catalogue = _load_json(catalogue_path)
    plan = plan_bindings(catalogue)
    for item in plan:
        for slot in _SLOTS:
            if not os.path.isfile(item[slot]):
                raise RebindError("published map is missing: " + item[slot])
    preserved = _preserved_paths(plan, source)
    before = hash_files(preserved)
    protected = list(preserved)
    if conflicts(output, protected) or os.path.exists(output):
        raise RebindError("refusing to write over an input or an existing file")
    if conflicts(report, protected):
        raise RebindError("report path is an input")
    work = tempfile.mkdtemp(prefix="agr-flora-rebind-")
    copy_path = os.path.join(work, "flora-library-source-copy.max")
    job_path = os.path.join(work, "rebind-job.json")
    batch_out = os.path.join(work, "dcc-batch.json")
    shutil.copy2(source, copy_path)
    job = {"output": os.path.abspath(output), "report": os.path.abspath(report), "protected": protected, "bindings": plan}
    with open(job_path, "w", encoding="utf-8") as handle:
        json.dump(job, handle)
    env = os.environ.copy()
    env["FLORA_REBIND_IN_MAX"] = "1"
    env["FLORA_REBIND_JOB"] = job_path
    command = [
        sys.executable, DCC_BATCH, "max", "--file", str(Path(__file__).resolve()),
        "--scene", copy_path, "--version", "2026", "--timeout", "900", "--out", batch_out,
    ]
    completed = subprocess.run(command, capture_output=True, env=env, text=True)
    assert_hashes_unchanged(before, hash_files(preserved))
    batch = {}
    if os.path.isfile(batch_out):
        batch = _load_json(batch_out)
    if completed.returncode != 0 or not os.path.isfile(report):
        if os.path.isfile(output):
            os.remove(output)
        raise RebindError(
            "dcc_batch exit {code} status {status}".format(
                code=completed.returncode, status=batch.get("status")
            )
        )
    result = _load_json(report)
    result["dcc_batch"] = {
        "command": command,
        "exit_code": completed.returncode,
        "status": batch.get("status"),
        "batch_exit_code": batch.get("exit_code"),
    }
    if result.get("status") != "pass" or result.get("passed") is not True:
        if os.path.isfile(output):
            os.remove(output)
        with open(report, "w", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=1)
            handle.write("\n")
        raise RebindError("readback did not pass")
    with open(report, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    shutil.rmtree(work, ignore_errors=True)
    return result


def main(argv=None) -> int:
    if os.environ.get("FLORA_REBIND_IN_MAX") == "1":
        run_in_max(os.environ["FLORA_REBIND_JOB"])
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalogue", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args(argv)
    try:
        result = execute(args.catalogue, args.source, args.output, args.report)
    except RebindError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(
        "objects {found}/{expected} bindings {matched}/{bindings} outside {outside}".format(
            found=result["objects_found"],
            expected=result["objects_expected"],
            matched=result["bindings_matched"],
            bindings=result["bindings_expected"],
            outside=result["paths_outside"],
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
