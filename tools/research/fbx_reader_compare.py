"""new-case: compare legacy import_scene.fbx with Blender 5 wm.fbx_import.

The diff is pure data. A headless Blender process only builds a snapshot.
Nothing here edits a checker, and nothing deletes an input file.
"""
import argparse
import hashlib
import json
import math
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

BLENDER = os.environ.get("TWINQA_BLENDER") or r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe"
OBJECT_KEYS = ("name", "triangles", "material_ids", "uv_layer_count", "uv_bbox")


class SnapshotError(ValueError):
    """Empty, partial, or non-finite readback data. Never a pass."""


def _lock_path():
    if os.environ.get("AGR_BLENDER_LOCK"):
        return os.environ["AGR_BLENDER_LOCK"]
    base = os.environ.get("LOCALAPPDATA")
    tmp = os.path.join(base, "Temp") if base else tempfile.gettempdir()
    return os.path.join(tmp, "agr-blender-session.lock")


def _same_path(output, inputs):
    out = Path(output).resolve()
    for item in inputs:
        src = Path(item).resolve()
        if out == src:
            return True
        try:
            if src.exists() and out.exists() and os.path.samefile(src, out):
                return True
        except OSError:
            continue
    return False


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SnapshotError(f"{label} is not a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise SnapshotError(f"{label} is not finite")
    return number


def _whole(value, label):
    if isinstance(value, bool) or not isinstance(value, int):
        raise SnapshotError(f"{label} is not an integer")
    return value


def validate_snapshot(snapshot):
    if not isinstance(snapshot, dict) or "objects" not in snapshot or "embedded_images" not in snapshot:
        raise SnapshotError("partial snapshot")
    objects = snapshot["objects"]
    images = snapshot["embedded_images"]
    if not isinstance(objects, list) or not isinstance(images, list):
        raise SnapshotError("partial snapshot")
    if not objects:
        raise SnapshotError("empty snapshot")
    seen = set()
    clean_objects = []
    for index, obj in enumerate(objects):
        if not isinstance(obj, dict) or any(key not in obj for key in OBJECT_KEYS):
            raise SnapshotError(f"partial object {index}")
        name = obj["name"]
        if not isinstance(name, str) or not name or name in seen:
            raise SnapshotError(f"bad object name {index}")
        seen.add(name)
        triangles = _whole(obj["triangles"], f"{name} triangles")
        if triangles < 1:
            raise SnapshotError(f"empty mesh {name}")
        ids = obj["material_ids"]
        if not isinstance(ids, list) or not ids:
            raise SnapshotError(f"partial material ids {name}")
        material_ids = [_whole(item, f"{name} material id") for item in ids]
        layers = _whole(obj["uv_layer_count"], f"{name} uv layers")
        if layers < 0:
            raise SnapshotError(f"bad uv layer count {name}")
        bbox = obj["uv_bbox"]
        if layers == 0:
            if bbox is not None:
                raise SnapshotError(f"partial uv bbox {name}")
            clean_bbox = None
        else:
            if not isinstance(bbox, list) or len(bbox) != 4:
                raise SnapshotError(f"partial uv bbox {name}")
            clean_bbox = [_number(item, f"{name} uv") for item in bbox]
            if clean_bbox[0] > clean_bbox[2] or clean_bbox[1] > clean_bbox[3]:
                raise SnapshotError(f"partial uv bbox {name}")
        clean_objects.append({
            "name": name,
            "triangles": triangles,
            "material_ids": material_ids,
            "uv_layer_count": layers,
            "uv_bbox": clean_bbox,
        })
    clean_images = []
    for index, image in enumerate(images):
        if not isinstance(image, dict) or any(key not in image for key in ("name", "sha256", "size")):
            raise SnapshotError(f"partial image {index}")
        digest = image["sha256"]
        size = image["size"]
        if not isinstance(image["name"], str) or not image["name"]:
            raise SnapshotError(f"partial image {index}")
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise SnapshotError(f"partial image {index}")
        if not isinstance(size, list) or len(size) != 2:
            raise SnapshotError(f"partial image {index}")
        clean_images.append({
            "name": image["name"],
            "sha256": digest,
            "size": [_whole(size[0], "image size"), _whole(size[1], "image size")],
        })
    clean_objects.sort(key=lambda item: item["name"])
    clean_images.sort(key=lambda item: (item["name"], item["sha256"]))
    return {"objects": clean_objects, "embedded_images": clean_images}


def diff_snapshots(left, right):
    left, right = validate_snapshot(left), validate_snapshot(right)
    differences = []
    left_names = {item["name"] for item in left["objects"]}
    right_names = {item["name"] for item in right["objects"]}
    if left_names != right_names:
        differences.append({
            "kind": "name",
            "missing": sorted(left_names - right_names),
            "extra": sorted(right_names - left_names),
        })
    right_by_name = {item["name"]: item for item in right["objects"]}
    for obj in left["objects"]:
        other = right_by_name.get(obj["name"])
        if other is None:
            continue
        for key in ("triangles", "material_ids", "uv_layer_count", "uv_bbox"):
            if obj[key] != other[key]:
                differences.append({"kind": key, "name": obj["name"]})
    if left["embedded_images"] != right["embedded_images"]:
        differences.append({"kind": "embedded_images"})
    return {"diff": len(differences), "differences": differences}


def _load_json(path):
    text = Path(path).read_text(encoding="utf-8")
    if not text.strip():
        raise SnapshotError("empty input")

    def reject(constant):
        raise SnapshotError(f"non-finite JSON {constant}")

    try:
        return json.loads(text, parse_constant=reject)
    except json.JSONDecodeError as exc:
        raise SnapshotError(f"partial JSON: {exc}") from exc


def _write_json(path, payload):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, allow_nan=False)
    handle, name = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=str(target.parent))
    temporary = Path(name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def diff_cli(left, right, output):
    inputs = [left, right]
    if _same_path(output, inputs):
        return 2
    try:
        payload = diff_snapshots(_load_json(left), _load_json(right))
    except (OSError, SnapshotError):
        return 1
    if _same_path(output, inputs):
        return 2
    _write_json(output, payload)
    return 0


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _acquire(card, wait, timeout):
    path = _lock_path()
    deadline = time.time() + wait
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, json.dumps({"card": card, "pid": os.getpid(), "t": time.time(), "timeout": timeout}).encode())
            os.close(fd)
            return path
        except FileExistsError:
            try:
                info = json.loads(Path(path).read_text(encoding="utf-8"))
                holder_timeout = float(info.get("timeout", 7200))
            except (OSError, ValueError, TypeError):
                holder_timeout = timeout
            try:
                if time.time() - os.path.getmtime(path) > holder_timeout + 300:
                    os.remove(path)
                    continue
            except OSError:
                pass
            if time.time() >= deadline:
                raise SnapshotError("blender lock busy")
            time.sleep(2)


def _release(path):
    try:
        info = json.loads(Path(path).read_text(encoding="utf-8"))
        if info.get("pid") == os.getpid():
            os.remove(path)
    except (OSError, ValueError, TypeError):
        return


def _touch_lock():
    try:
        os.utime(_lock_path(), None)
    except OSError:
        return


def _choose_plant_source(objects, scratch):
    for preferred in ("B01", "AC08", "K02"):
        snapshot = _reload_snapshot(scratch / f"{preferred}_legacy_0.json")
        if snapshot and any(item["uv_layer_count"] > 0 and item["material_ids"] for item in snapshot["objects"]):
            return next(item for item in objects if item["id"] == preferred)
    return next(item for item in objects if item["id"] == "B01")


def _blender(script_args, scratch, timeout):
    _touch_lock()
    config = Path(scratch) / "blender-config"
    if config.exists():
        shutil.rmtree(config)
    config.mkdir(parents=True)
    env = os.environ.copy()
    for key in ("BLENDER_USER_CONFIG", "BLENDER_USER_SCRIPTS", "BLENDER_USER_DATAFILES"):
        directory = config / key.lower()
        directory.mkdir()
        env[key] = str(directory)
    command = [BLENDER, "--background", "--factory-startup", "--disable-autoexec",
               "--python-exit-code", "1", "--python", str(Path(__file__).resolve()), "--", *script_args]
    started = time.perf_counter()
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=timeout, env=env)
    return result.returncode, time.perf_counter() - started, (result.stderr or result.stdout)[-500:]


def _snapshot_from_scene(importer):
    import bpy

    note = {"blender": bpy.app.version_string, "importer": importer,
            "has_wm_fbx_import": hasattr(bpy.ops.wm, "fbx_import")}
    objects = []
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        mesh = obj.data
        mesh.calc_loop_triangles()
        if len(mesh.loop_triangles) < 1 or len(mesh.polygons) < 1:
            continue
        layers = list(mesh.uv_layers)
        if layers:
            umin = vmin = math.inf
            umax = vmax = -math.inf
            for layer in layers:
                for item in layer.data:
                    u, v = float(item.uv.x), float(item.uv.y)
                    if not math.isfinite(u) or not math.isfinite(v):
                        raise SnapshotError(f"non-finite UV on {obj.name}")
                    umin, umax = min(umin, u), max(umax, u)
                    vmin, vmax = min(vmin, v), max(vmax, v)
            if math.isinf(umin):
                raise SnapshotError(f"partial UV on {obj.name}")
            bbox = [round(umin, 6), round(vmin, 6), round(umax, 6), round(vmax, 6)]
        else:
            bbox = None
        objects.append({
            "name": obj.name,
            "triangles": len(mesh.loop_triangles),
            "material_ids": [int(poly.material_index) for poly in mesh.polygons],
            "uv_layer_count": len(layers),
            "uv_bbox": bbox,
        })
    images = []
    for image in bpy.data.images:
        if image.type != "IMAGE" or image.packed_file is None:
            continue
        packed = bytes(image.packed_file.data)
        images.append({"name": image.name, "sha256": hashlib.sha256(packed).hexdigest(),
                       "size": [int(image.size[0]), int(image.size[1])]})
    return {"blender_note": note, "snapshot": validate_snapshot({"objects": objects, "embedded_images": images})}


def _import_scene(importer, filepath):
    import bpy
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if importer == "legacy":
        result = bpy.ops.import_scene.fbx(filepath=filepath)
    elif importer == "wm":
        if not hasattr(bpy.ops.wm, "fbx_import"):
            raise SnapshotError("wm.fbx_import is not on this Blender")
        result = bpy.ops.wm.fbx_import(filepath=filepath)
    else:
        raise SnapshotError(f"unknown importer {importer}")
    if "FINISHED" not in set(result):
        raise SnapshotError(f"{importer} import status {result}")


def extract_cli(fbx, importer, output):
    if _same_path(output, [fbx]):
        return 2
    try:
        _import_scene(importer, str(Path(fbx).resolve()))
        payload = _snapshot_from_scene(importer)
    except Exception:
        return 1
    if _same_path(output, [fbx]):
        return 2
    _write_json(output, payload)
    return 0


def _mutate(kind):
    import bpy
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH" and len(obj.data.polygons)]
    if not meshes:
        raise SnapshotError("no mesh to mutate")
    obj = sorted(meshes, key=lambda item: item.name)[0]
    if kind == "control":
        return {"kind": kind, "name": obj.name}
    if kind == "material":
        mesh = obj.data
        if len(obj.material_slots) < 2:
            mesh.materials.append(bpy.data.materials.new("PlantedSecond"))
        mesh.polygons[0].material_index = 0 if mesh.polygons[0].material_index else 1
        return {"kind": kind, "name": obj.name, "face": 0, "material_index": int(mesh.polygons[0].material_index)}
    if kind == "uv":
        while obj.data.uv_layers:
            obj.data.uv_layers.remove(obj.data.uv_layers[0])
        return {"kind": kind, "name": obj.name, "uv_layer_count": 0}
    if kind == "rename":
        previous = obj.name
        obj.name = previous + "_renamed"
        return {"kind": kind, "before": previous, "after": obj.name}
    raise SnapshotError(f"unknown plant {kind}")


def plant_cli(fbx, kind, output):
    if _same_path(output, [fbx]):
        return 2
    try:
        _import_scene("legacy", str(Path(fbx).resolve()))
        note = _mutate(kind)
        import bpy
        status = bpy.ops.export_scene.fbx(filepath=str(Path(output).resolve()), use_selection=False,
                                          path_mode="AUTO", embed_textures=False)
        if "FINISHED" not in set(status):
            raise SnapshotError(f"export status {status}")
    except Exception:
        return 1
    if not Path(output).is_file() or Path(output).stat().st_size == 0:
        return 1
    note_path = Path(output).with_suffix(".note.json")
    if not _same_path(note_path, [fbx, output]):
        _write_json(note_path, note)
    return 0


def _cold_extract(fbx, importer, output, scratch, timeout):
    if _same_path(output, [fbx]):
        raise SnapshotError("output aliases input")
    if Path(output).exists():
        Path(output).unlink()
    code, seconds, tail = _blender(
        ["extract", "--fbx", str(fbx), "--importer", importer, "--output", str(output)],
        scratch, timeout)
    if code != 0 or not Path(output).is_file():
        return {"ok": False, "seconds": round(seconds, 3), "tail": tail}
    try:
        payload = _load_json(output)
        snapshot = validate_snapshot(payload["snapshot"])
    except (OSError, SnapshotError, KeyError, TypeError) as exc:
        return {"ok": False, "seconds": round(seconds, 3), "tail": str(exc)}
    return {"ok": True, "seconds": round(seconds, 3), "snapshot": snapshot,
            "blender_note": payload.get("blender_note")}


def _caught(control, mutant, kind):
    if control is None or mutant is None:
        return False
    try:
        result = diff_snapshots(control, mutant)
    except SnapshotError:
        return False
    return kind in {item["kind"] for item in result["differences"]}


def _preflight_inventory(scratch, objects, output):
    """Reject before any side effect when a generated path can touch an input or the output."""
    scratch = Path(scratch)
    ids = [item["id"] for item in objects]
    files, dirs = [], [scratch / "planted"]
    for ident in ids:
        for importer in ("legacy", "wm"):
            for index in range(3):
                files.append(scratch / f"{ident}_{importer}_{index}.json")
                dirs.append(scratch / f"cfg-{ident}-{importer}-{index}")
    for kind in ("control", "material", "uv", "rename"):
        files.append(scratch / "planted" / f"{kind}.fbx")
        dirs.append(scratch / f"plant-{kind}")
    for importer in ("legacy", "wm"):
        files.append(scratch / f"plant_control_{importer}.json")
        dirs.append(scratch / f"pc-{importer}")
        for kind in ("material", "uv", "rename"):
            files.append(scratch / f"plant_{kind}_{importer}.json")
            dirs.append(scratch / f"pm-{importer}-{kind}")
    protected = [Path(item["path"]) for item in objects] + [Path(output)]
    for target in protected:
        resolved = target.resolve()
        for generated in files:
            if _same_path(generated, [target]):
                raise SnapshotError(f"generated path aliases input/output: {generated.name}")
        for directory in dirs:
            root = directory.resolve()
            if resolved == root or root in resolved.parents:
                raise SnapshotError(f"input/output inside generated directory: {directory.name}")


def measure_cli(args):
    scratch = Path(args.scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    output = Path(args.output)
    objects = [
        {"id": "AC08", "role": "v010", "path": args.ac08, "expect_sha256": args.ac08_sha},
        {"id": "B01", "role": "etalon", "path": args.b01, "expect_sha256": args.b01_sha},
        {"id": "K02", "role": "job-output", "path": args.k02, "expect_sha256": args.k02_sha},
    ]
    inputs = [item["path"] for item in objects]
    if _same_path(output, inputs):
        return 2
    for item in objects:
        if not Path(item["path"]).is_file():
            raise SnapshotError(f"missing {item['id']}")
        item["sha256"] = _sha256(item["path"])
        item["bytes"] = Path(item["path"]).stat().st_size
        if item["expect_sha256"] and item["sha256"] != item["expect_sha256"]:
            raise SnapshotError(f"sha256 mismatch {item['id']}")
    before = {item["id"]: item["sha256"] for item in objects}
    _preflight_inventory(scratch, objects, output)
    lock = None
    try:
        lock = _acquire(args.card, args.wait, args.timeout)
        report = {"objects": [], "planted": [], "inputs_unchanged": False}
        for item in objects:
            entry = {"id": item["id"], "role": item["role"], "sha256": item["sha256"], "bytes": item["bytes"],
                     "importers": {}}
            for importer in ("legacy", "wm"):
                runs = []
                for index in range(3):
                    out = scratch / f"{item['id']}_{importer}_{index}.json"
                    runs.append(_cold_extract(item["path"], importer, out, scratch / f"cfg-{item['id']}-{importer}-{index}", args.timeout))
                ok = [run for run in runs if run["ok"]]
                entry["importers"][importer] = {
                    "runs": [{"ok": run["ok"], "seconds": run["seconds"], **({} if run["ok"] else {"tail": run["tail"]})} for run in runs],
                    "median_seconds": statistics.median(run["seconds"] for run in runs),
                    "stable_diff": None,
                    "blender_note": ok[0]["blender_note"] if ok else None,
                }
                if len(ok) == 3:
                    diffs = [diff_snapshots(ok[0]["snapshot"], run["snapshot"])["diff"] for run in ok[1:]]
                    entry["importers"][importer]["stable_diff"] = max(diffs) if diffs else 0
            legacy_runs = [_reload_snapshot(scratch / f"{item['id']}_legacy_{index}.json") for index in range(3)]
            wm_runs = [_reload_snapshot(scratch / f"{item['id']}_wm_{index}.json") for index in range(3)]
            if legacy_runs[0] and wm_runs[0]:
                compared = diff_snapshots(legacy_runs[0], wm_runs[0])
                entry["cross"] = {"diff": compared["diff"], "differences": compared["differences"]}
            else:
                entry["cross"] = {"diff": None, "differences": [], "failed": True}
            entry["importers"]["legacy"]["snapshot_objects"] = _summary(legacy_runs[0])
            entry["importers"]["wm"]["snapshot_objects"] = _summary(wm_runs[0])
            report["objects"].append(entry)
        plant_source = _choose_plant_source(objects, scratch)
        for kind, expect in (("control", None), ("material", "material_ids"), ("uv", "uv_layer_count"), ("rename", "name")):
            planted = scratch / "planted" / f"{kind}.fbx"
            planted.parent.mkdir(parents=True, exist_ok=True)
            if _same_path(planted, [plant_source["path"]]):
                raise SnapshotError("planted output aliases input")
            if planted.exists():
                planted.unlink()
            code, seconds, tail = _blender(
                ["plant", "--fbx", plant_source["path"], "--kind", kind, "--output", str(planted)],
                scratch / f"plant-{kind}", args.timeout)
            record = {"kind": kind, "export_ok": code == 0 and planted.is_file(), "export_seconds": round(seconds, 3)}
            if not record["export_ok"]:
                record["tail"] = tail
            record["source_id"] = plant_source["id"]
            report["planted"].append(record)
        control = scratch / "planted" / "control.fbx"
        control_runs = {}
        for importer in ("legacy", "wm"):
            control_out = scratch / f"plant_control_{importer}.json"
            control_runs[importer] = _cold_extract(
                control, importer, control_out, scratch / f"pc-{importer}", args.timeout) if control.is_file() else {"ok": False}
        for kind, expect in (("material", "material_ids"), ("uv", "uv_layer_count"), ("rename", "name")):
            mutant = scratch / "planted" / f"{kind}.fbx"
            row = next(item for item in report["planted"] if item["kind"] == kind)
            row["importers"] = {}
            for importer in ("legacy", "wm"):
                mutant_out = scratch / f"plant_{kind}_{importer}.json"
                control_run = control_runs[importer]
                mutant_run = _cold_extract(mutant, importer, mutant_out, scratch / f"pm-{importer}-{kind}", args.timeout) if mutant.is_file() else {"ok": False}
                row["importers"][importer] = {
                    "caught": _caught(control_run.get("snapshot"), mutant_run.get("snapshot"), expect),
                    "control_ok": bool(control_run.get("ok")),
                    "mutant_ok": bool(mutant_run.get("ok")),
                    "seconds": round(mutant_run.get("seconds") or 0, 3),
                }
                if control_run.get("ok") and mutant_run.get("ok"):
                    compared = diff_snapshots(control_run["snapshot"], mutant_run["snapshot"])
                    row["importers"][importer]["diff"] = compared["diff"]
                    row["importers"][importer]["kinds"] = [item["kind"] for item in compared["differences"]]
        after = {item["id"]: _sha256(item["path"]) for item in objects}
        report["inputs_unchanged"] = after == before and all(Path(item["path"]).is_file() for item in objects)
        report["input_sha256"] = after
    finally:
        if lock:
            _release(lock)
    if _same_path(output, inputs):
        return 2
    _write_json(output, report)
    return 0 if report["inputs_unchanged"] else 1


def _reload_snapshot(path):
    if not Path(path).is_file():
        return None
    try:
        return validate_snapshot(_load_json(path)["snapshot"])
    except (OSError, SnapshotError, KeyError, TypeError):
        return None


def _summary(snapshot):
    if snapshot is None:
        return None
    return [{
        "name": obj["name"],
        "triangles": obj["triangles"],
        "faces": len(obj["material_ids"]),
        "uv_layer_count": obj["uv_layer_count"],
        "uv_bbox": obj["uv_bbox"],
        "embedded_images": len(snapshot["embedded_images"]),
    } for obj in snapshot["objects"]]


def _cli_argv(argv):
    """Blender keeps its own flags in sys.argv; script args follow '--'."""
    if argv is not None:
        return argv
    if "--" in sys.argv:
        return sys.argv[sys.argv.index("--") + 1:]
    return sys.argv[1:]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    diff = commands.add_parser("diff")
    diff.add_argument("--left", required=True)
    diff.add_argument("--right", required=True)
    diff.add_argument("--output", required=True)
    extract = commands.add_parser("extract")
    extract.add_argument("--fbx", required=True)
    extract.add_argument("--importer", choices=("legacy", "wm"), required=True)
    extract.add_argument("--output", required=True)
    plant = commands.add_parser("plant")
    plant.add_argument("--fbx", required=True)
    plant.add_argument("--kind", choices=("control", "material", "uv", "rename"), required=True)
    plant.add_argument("--output", required=True)
    measure = commands.add_parser("measure")
    measure.add_argument("--scratch", required=True)
    measure.add_argument("--output", required=True)
    measure.add_argument("--ac08", required=True)
    measure.add_argument("--ac08-sha", default="ca4715a446db660d2c82766d4be8547fac954c4fab1363ef171bde4b99a4277b")
    measure.add_argument("--b01", required=True)
    measure.add_argument("--b01-sha", default="a109aa9a9f25c72e8d4869ee43b0b33aee009f5c248caf62388c4dcb0c7816d9")
    measure.add_argument("--k02", required=True)
    measure.add_argument("--k02-sha", default="")
    measure.add_argument("--card", default="t_f24b8f78")
    measure.add_argument("--wait", type=float, default=120)
    measure.add_argument("--timeout", type=float, default=900)
    args = parser.parse_args(_cli_argv(argv))
    try:
        if args.command == "diff":
            return diff_cli(args.left, args.right, args.output)
        if args.command == "extract":
            return extract_cli(args.fbx, args.importer, args.output)
        if args.command == "plant":
            return plant_cli(args.fbx, args.kind, args.output)
        return measure_cli(args)
    except SnapshotError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
