"""Bind Vatutino Ground diffuse maps to M_Vatutino_Ground_<Slot> (issue #340).

Plan and check are pure Python. The Blender script next to this file only runs on a
copy of the source FBX and only after the plan has exactly one verified map per slot.
v001 textures are never a source. Delivery FBX is written only under
C:/x/vatutino-ground-textured/v001.

new-case: Ground diffuse binding table from an FBX readback plus a recipe manifest.
"""
import argparse
import hashlib
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

REQUIRED_SLOTS = (
    "TileLight",
    "TileDark",
    "TileRed",
    "Gravel",
    "Pebbles",
    "Mulch",
    "LawnRolled",
    "LawnReinforced",
    "FlowerBed",
    "Skirt",
    "CurbGarden",
    "Stairs",
)
PROFILES = ("npm", "vpm")
PROFILE_SIZE = {"npm": 2048, "vpm": 4096}
DENSITY_BAND = {"npm": (10.0, 40.0), "vpm": (520.0, 1706.0)}
# TEX-17 / [D097]: the band is the relief surface. The perimeter skirt is excluded;
# v014 records Skirt UV area 0 and measures density on every other face.
DENSITY_EXEMPT = frozenset({"Skirt"})
MATERIAL_NAME = re.compile(r"^M_Vatutino_Ground_([A-Za-z0-9_]+)$")
OUTPUT_DIR = Path("C:/x/vatutino-ground-textured/v001")
TEXTURE_ROOT = Path("C:/x/vatutino-ground-textures/v003")
V001_TEXTURES = Path("C:/x/vatutino-ground-textures/v001")
V002_TEXTURES = Path("C:/x/vatutino-ground-textures/v002")
FBX_NAME = "SM_Vatutino_Ground.fbx"
_PNG = b"\x89PNG\r\n\x1a\n"
_BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe")


class BindError(ValueError):
    """The binding cannot be planned or written."""


def texture_filename(slot: str, profile: str) -> str:
    if profile == "npm":
        return f"T_Vatutino_Ground_Diffuse_{slot}.png"
    if profile == "vpm":
        return f"T_Vatutino_Ground_Diffuse_{slot}.1001.png"
    raise BindError(f"unsupported profile {profile!r}")


def assert_texture_root(path) -> Path:
    root = Path(path)
    if _same(root, V001_TEXTURES) or _within(root, V001_TEXTURES):
        raise BindError("v001 textures are refused")
    if _same(root, V002_TEXTURES) or _within(root, V002_TEXTURES):
        raise BindError("v002 textures are left untouched")
    if not _same(root, TEXTURE_ROOT):
        raise BindError(f"texture directory must be {TEXTURE_ROOT}")
    return root


def material_names(readback) -> list[str]:
    if not isinstance(readback, dict) or not readback:
        raise BindError("readback is empty or unsupported")
    meshes = readback.get("meshes")
    names = []
    if isinstance(meshes, list) and meshes:
        for mesh in meshes:
            if not isinstance(mesh, dict) or not isinstance(mesh.get("materials"), list):
                raise BindError("mesh material slots are missing")
            if re.fullmatch(r"UCX_SM_Vatutino_Ground_[0-9]{3}", mesh.get("name", "")) and not mesh["materials"]:
                continue
            if not mesh["materials"]:
                raise BindError("mesh material slots are empty")
            for slot in mesh["materials"]:
                names.append(_material_name(slot))
    if not names:
        materials = readback.get("materials")
        if not isinstance(materials, list) or not materials:
            raise BindError("readback has no material slots")
        for item in materials:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                names.append(_material_name(item["name"]))
            elif isinstance(item, dict):
                raise BindError("unsupported material slot")
            else:
                names.append(_material_name(item))
    if len(names) != len(set(names)):
        raise BindError("duplicate material slot")
    return names


def _material_name(name) -> str:
    if not isinstance(name, str) or not MATERIAL_NAME.fullmatch(name):
        raise BindError(f"slot name not matching M_Vatutino_Ground_<Slot>: {name!r}")
    return name


def slot_token(material: str) -> str:
    match = MATERIAL_NAME.fullmatch(material)
    if not match:
        raise BindError(f"slot name not matching M_Vatutino_Ground_<Slot>: {material!r}")
    return match.group(1)


def build_plan(npm_readback, vpm_readback, manifest, texture_root, npm_fbx=None, vpm_fbx=None) -> dict:
    root = assert_texture_root(texture_root)
    maps = _manifest_maps(manifest)
    by_profile = {profile: {} for profile in PROFILES}
    for entry in maps:
        by_profile[entry["profile"]][entry["slot"]] = entry
    for profile in PROFILES:
        missing = [slot for slot in REQUIRED_SLOTS if slot not in by_profile[profile]]
        if missing:
            raise BindError(f"partial manifest for {profile}: {', '.join(missing)}")
    verified = {profile: {} for profile in PROFILES}
    for entry in maps:
        verified[entry["profile"]][entry["slot"]] = _verify_map(root, entry)
    plan = {"bindings": {}, "ground_slots_without_map": {}, "manifest_slots_without_material": {}}
    readbacks = {"npm": npm_readback, "vpm": vpm_readback}
    for profile in PROFILES:
        names = material_names(readbacks[profile])
        mesh_slots = [slot_token(name) for name in names]
        if len(mesh_slots) != len(set(mesh_slots)):
            raise BindError("duplicate material slot")
        mesh_set = set(mesh_slots)
        bindings = []
        for name in names:
            slot = slot_token(name)
            entry = verified[profile].get(slot)
            if entry is None:
                continue
            bindings.append({"slot": slot, "material": name, **entry})
        if len(bindings) != len({item["slot"] for item in bindings}):
            raise BindError("a slot would receive more than one map")
        plan["bindings"][profile] = bindings
        plan["ground_slots_without_map"][profile] = [slot for slot in mesh_slots if slot not in verified[profile]]
        plan["manifest_slots_without_material"][profile] = [
            slot for slot in verified[profile] if slot not in mesh_set
        ]
    sources = {}
    for label, path in (("npm_fbx", npm_fbx), ("vpm_fbx", vpm_fbx)):
        if path is not None:
            sources[label] = {"path": str(path), "sha256": _sha256(Path(path))}
    if isinstance(manifest, dict) and manifest.get("manifest_path"):
        sources["manifest"] = {"path": str(manifest["manifest_path"]), "sha256": _sha256(Path(manifest["manifest_path"]))}
    plan["sources"] = sources
    return plan


def assert_bindable(plan) -> None:
    if not isinstance(plan, dict) or not plan.get("bindings"):
        raise BindError("empty plan")
    for profile in PROFILES:
        bindings = plan["bindings"].get(profile)
        if not isinstance(bindings, list) or not bindings:
            raise BindError(f"empty {profile} bindings")
        slots = [item["slot"] for item in bindings]
        if len(slots) != len(set(slots)):
            raise BindError("a slot would receive more than one map")
        missing_map = list(plan.get("ground_slots_without_map", {}).get(profile) or [])
        missing_material = list(plan.get("manifest_slots_without_material", {}).get(profile) or [])
        if missing_map:
            raise BindError(f"Ground slot with no manifest map ({profile}): {', '.join(missing_map)}")
        if missing_material:
            raise BindError(f"manifest slot with no Ground material ({profile}): {', '.join(missing_material)}")
        if any(slot not in slots for slot in REQUIRED_SLOTS):
            raise BindError(f"partial bindings for {profile}")


def output_conflicts(output_dir, inputs, texture_root=None) -> str | None:
    output = Path(output_dir)
    if _same(output, V002_TEXTURES) or _within(output, V002_TEXTURES):
        return "output would overwrite v002 textures"
    roots = [V001_TEXTURES, V002_TEXTURES, TEXTURE_ROOT]
    if texture_root is not None:
        roots.append(Path(texture_root))
    for root in roots:
        if _same(output, root) or _within(output, root):
            return "output path resolves to a texture input"
    for raw in inputs:
        if raw is None:
            continue
        item = Path(raw)
        if _same(output, item) or _within(output, item) or _within(item, output):
            return "output path resolves to an input"
    return None


def geometry_deltas(before, after) -> dict:
    left, right = _geometry(before), _geometry(after)
    for key, label in (("raw_material_layers", "raw material layers"), ("polygons", "topology")):
        if key in before or key in after:
            if not before.get(key) or before.get(key) != after.get(key):
                raise BindError(f"{label} differ or are missing")
    if before.get("collision_geometry") != after.get("collision_geometry"):
        raise BindError("collision geometry differs")
    if left["triangles"] != right["triangles"]:
        raise BindError(f"triangle count {left['triangles']} != {right['triangles']}")
    if left["material_ids"] != right["material_ids"]:
        raise BindError("per-face material ids differ")
    vertex = _max_delta(left["vertices"], right["vertices"], "vertex")
    uv = _max_delta(left["uvs"], right["uvs"], "uv")
    if vertex != 0.0 or uv != 0.0:
        raise BindError(f"geometry delta vertex {vertex} uv {uv}")
    return {"vertex": vertex, "uv": uv, "triangles": left["triangles"]}


def density_report(faces, profile: str, expected_slots=None) -> dict:
    if profile not in DENSITY_BAND:
        raise BindError(f"unsupported profile {profile!r}")
    if not isinstance(faces, list) or not faces:
        raise BindError("empty density input")
    low, high = DENSITY_BAND[profile]
    px = PROFILE_SIZE[profile]
    grouped = {}
    for face in faces:
        if not isinstance(face, dict):
            raise BindError("unsupported density face")
        slot = face.get("slot")
        if not isinstance(slot, str) or not slot:
            raise BindError("density face has no slot")
        world = _positive_finite(face.get("world_area_m2"), "world area")
        uv_area = _nonnegative_finite(face.get("uv_area"), "uv area")
        value = 0.0 if uv_area == 0.0 else px * math.sqrt(uv_area / world)
        if not math.isfinite(value):
            raise BindError("non-finite density")
        grouped.setdefault(slot, []).append(value)
    report = {}
    outside = []
    for slot, values in grouped.items():
        lo, hi = min(values), max(values)
        report[slot] = {"min": lo, "max": hi, "faces": len(values)}
        if slot not in DENSITY_EXEMPT and (lo < low or hi > high):
            outside.append(slot)
    if expected_slots is not None and set(grouped) != set(expected_slots):
        raise BindError("partial slot density")
    if outside:
        raise BindError(f"density outside {low}-{high}: " + ", ".join(
            f"{slot} {report[slot]['min']}-{report[slot]['max']}" for slot in outside
        ))
    return report


def mismatch_count(bindings, readback) -> int:
    if not isinstance(bindings, list) or not bindings:
        raise BindError("empty bindings")
    if not isinstance(readback, dict) or not readback.get("materials") or not readback.get("images"):
        raise BindError("empty readback")
    images = {}
    for image in readback["images"]:
        if not isinstance(image, dict) or not isinstance(image.get("name"), str):
            raise BindError("unsupported readback image")
        size = image.get("size")
        if not isinstance(size, (list, tuple)) or len(size) != 2:
            raise BindError("unsupported image size")
        images[image["name"]] = {"name": image["name"], "size": [_exact_int(size[0]), _exact_int(size[1])]}
    observed = {}
    for mat in readback["materials"]:
        if not isinstance(mat, dict) or not isinstance(mat.get("name"), str):
            raise BindError("unsupported readback material")
        if mat["name"] in observed:
            raise BindError("duplicate readback material")
        observed[mat["name"]] = mat
    mismatches = 0
    for binding in bindings:
        mat = observed.get(binding["material"])
        if mat is None:
            mismatches += 1
            continue
        base = [item for item in mat.get("maps") or [] if isinstance(item, dict) and item.get("socket") == "Base Color"]
        if len(base) != 1 or base[0].get("image") != binding["file"]:
            mismatches += 1
            continue
        image = images.get(binding["file"])
        if image is None or image["size"] != [binding["size"], binding["size"]]:
            mismatches += 1
    expected_names = {binding["material"] for binding in bindings}
    for name in observed:
        if name.startswith("M_Vatutino_Ground_") and name not in expected_names:
            mismatches += 1
    return mismatches


def accept_readback(bindings, readback) -> int:
    count = mismatch_count(bindings, readback)
    if count != 0:
        raise BindError(f"binding mismatches = {count}")
    return count


def bind_delivery(npm_readback, vpm_readback, manifest, texture_root, npm_fbx, vpm_fbx, output_dir, dcc=None, extra_inputs=()) -> dict:
    output = Path(output_dir)
    if not _same(output, OUTPUT_DIR):
        raise BindError(f"output directory must be {OUTPUT_DIR}")
    inputs = [texture_root, npm_fbx, vpm_fbx, *extra_inputs]
    if isinstance(manifest, dict) and manifest.get("manifest_path"):
        inputs.append(manifest["manifest_path"])
    elif not isinstance(manifest, dict):
        inputs.append(manifest)
    conflict = output_conflicts(output, inputs, texture_root)
    if conflict:
        raise BindError(conflict)
    plan = build_plan(npm_readback, vpm_readback, manifest, texture_root, npm_fbx, vpm_fbx)
    assert_bindable(plan)
    for src in (npm_fbx, vpm_fbx):
        if _same(output, Path(src).parent) or _within(output, Path(src).parent):
            raise BindError("output would overwrite a #295 FBX folder")
    if output.exists() and any(output.iterdir()):
        raise BindError("output folder already contains files")
    created = not output.exists()
    output.mkdir(parents=True, exist_ok=True)
    written = []
    try:
        runner = dcc or default_dcc
        reports = {}
        for profile, src in (("npm", npm_fbx), ("vpm", vpm_fbx)):
            destination = output / profile / FBX_NAME
            destination.parent.mkdir(parents=True, exist_ok=True)
            written.append(destination)
            result = runner(profile, Path(src), Path(texture_root), plan["bindings"][profile], destination)
            geometry_deltas(_load_json(result["before"]), _load_json(result["after"]))
            faces = _load_json(result["after"])["faces"]
            reports[profile] = density_report(faces, profile, [item["slot"] for item in plan["bindings"][profile]])
            accept_readback(plan["bindings"][profile], _load_json(result["readback"]))
        plan["density"] = reports
        (output / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
        (output / "density.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
        return plan
    except Exception:
        if created:
            shutil.rmtree(output, ignore_errors=True)
        else:
            for path in written:
                path.unlink(missing_ok=True)
        raise


def stage_source_copy(src, dest) -> None:
    source, target = Path(src), Path(dest)
    if _same(source, target):
        raise BindError("copy destination resolves to the source")
    if target.exists():
        raise BindError("copy destination already exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    if _same(source, target):
        raise BindError("copy destination resolves to the source")


def default_dcc(profile, source_fbx, texture_root, bindings, out_fbx):
    with tempfile.TemporaryDirectory(prefix=".ground-bind-", dir=out_fbx.parent) as folder:
        work = Path(folder)
        copy = work / "source.fbx"
        stage_source_copy(source_fbx, copy)
        before = work / "before.json"
        after = out_fbx.with_suffix(".fingerprint.json")
        readback = out_fbx.with_suffix(".readback.json")
        spec = work / "bind.json"
        spec.write_text(json.dumps({
            "profile": profile,
            "texture_root": str(texture_root),
            "bindings": bindings,
        }), encoding="utf-8")
        _run_blender(Path(__file__).with_name("bind_ground_textures_blender.py"), ["fingerprint", copy, before])
        _run_blender(Path(__file__).with_name("bind_ground_textures_blender.py"), ["bind", copy, spec, out_fbx])
        _run_blender(Path(__file__).with_name("bind_ground_textures_blender.py"), ["fingerprint", out_fbx, after])
        reader = Path(__file__).resolve().parents[1] / "blender" / "fbx_readback.py"
        _run_blender(reader, [out_fbx, readback])
        # Fingerprints must outlive the temp copy. before.json is moved beside the FBX.
        staged_before = out_fbx.with_suffix(".source-fingerprint.json")
        shutil.copyfile(before, staged_before)
        return {"before": staged_before, "after": after, "readback": readback}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="bind_ground_textures")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "bind"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--npm-readback", required=True)
        cmd.add_argument("--vpm-readback", required=True)
        cmd.add_argument("--manifest", required=True)
        cmd.add_argument("--textures", required=True)
        cmd.add_argument("--npm-fbx")
        cmd.add_argument("--vpm-fbx")
        cmd.add_argument("--out", required=True)
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:
        return int(exc.code) if exc.code else 0
    try:
        manifest = _load_json(args.manifest)
        if not isinstance(manifest, dict):
            raise BindError("manifest is unsupported")
        manifest["manifest_path"] = str(Path(args.manifest))
        npm = _load_json(args.npm_readback)
        vpm = _load_json(args.vpm_readback)
        if args.command == "plan":
            out = Path(args.out)
            inputs = [args.manifest, args.textures, args.npm_readback, args.vpm_readback, args.npm_fbx, args.vpm_fbx]
            if output_conflicts(out, inputs, args.textures) or _same(out, Path(args.manifest)):
                raise BindError("output path resolves to an input")
            plan = build_plan(npm, vpm, manifest, args.textures, args.npm_fbx, args.vpm_fbx)
            if out.exists():
                raise BindError("plan output already exists")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        else:
            if not args.npm_fbx or not args.vpm_fbx:
                raise BindError("bind requires both source FBX paths")
            bind_delivery(
                npm, vpm, manifest, args.textures, args.npm_fbx, args.vpm_fbx, args.out,
                extra_inputs=(args.npm_readback, args.vpm_readback, args.manifest),
            )
    except BindError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


def _manifest_maps(manifest) -> list[dict]:
    if not isinstance(manifest, dict):
        raise BindError("manifest is unsupported")
    maps = manifest.get("maps")
    if not isinstance(maps, list) or not maps:
        raise BindError("manifest maps are empty")
    parsed = []
    seen = set()
    for entry in maps:
        if not isinstance(entry, dict):
            raise BindError("unsupported manifest map")
        slot, profile = entry.get("slot"), entry.get("profile")
        if not isinstance(slot, str) or not re.fullmatch(r"[A-Za-z0-9_]+", slot):
            raise BindError("unsupported manifest slot")
        if profile not in PROFILE_SIZE:
            raise BindError(f"unsupported profile {profile!r}")
        filename = entry.get("file")
        if filename != texture_filename(slot, profile):
            if profile == "vpm":
                raise BindError(f"VPM map without the .1001 UDIM tile: {filename!r}")
            raise BindError(f"map file name does not match the profile: {filename!r}")
        digest = entry.get("sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise BindError("manifest sha256 is unsupported")
        size = entry.get("size")
        if not isinstance(size, (list, tuple)) or len(size) != 2:
            raise BindError("manifest size is unsupported")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in size):
            raise BindError("non-finite manifest size")
        if [_exact_int(size[0]), _exact_int(size[1])] != [PROFILE_SIZE[profile], PROFILE_SIZE[profile]]:
            raise BindError(f"{profile} map size must be {PROFILE_SIZE[profile]}")
        key = (profile, slot)
        if key in seen:
            raise BindError(f"duplicate manifest map for {profile} {slot}")
        seen.add(key)
        parsed.append({"slot": slot, "profile": profile, "file": filename, "sha256": digest, "size": PROFILE_SIZE[profile]})
    return parsed


def _verify_map(root: Path, entry: dict) -> dict:
    path = root / entry["file"]
    if path.name != entry["file"] or not _within(path, root):
        raise BindError("map path escapes the texture directory")
    if not path.is_file():
        raise BindError(f"manifest map file missing: {entry['file']}")
    digest, size = _sha256_and_png_size(path)
    if digest != entry["sha256"]:
        raise BindError(f"sha256 differs from the manifest: {entry['file']}")
    expected = entry["size"]
    if size != (expected, expected):
        raise BindError(f"{entry['profile']} map is {size[0]} px, not {expected}")
    return {"file": entry["file"], "sha256": digest, "size": expected}


def _sha256_and_png_size(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        header = stream.read(24)
        digest.update(header)
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    if len(header) < 24 or header[:8] != _PNG or header[12:16] != b"IHDR":
        raise BindError(f"not a PNG: {path.name}")
    width, height = struct.unpack(">II", header[16:24])
    if width <= 0 or height <= 0 or width != height:
        raise BindError(f"PNG size is unsupported: {path.name}")
    return digest.hexdigest(), (width, height)


def _sha256(path: Path) -> str:
    if not path.is_file():
        raise BindError(f"input file missing: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _geometry(payload) -> dict:
    if not isinstance(payload, dict):
        raise BindError("geometry is unsupported")
    triangles = payload.get("triangles")
    if isinstance(triangles, bool) or not isinstance(triangles, int) or triangles <= 0:
        raise BindError("triangle count is unsupported")
    ids = payload.get("material_ids")
    if not isinstance(ids, list) or not ids:
        raise BindError("material ids are empty")
    parsed_ids = []
    for value in ids:
        if isinstance(value, bool) or not isinstance(value, int):
            raise BindError("material id is unsupported")
        parsed_ids.append(value)
    return {
        "triangles": triangles,
        "material_ids": parsed_ids,
        "vertices": _points(payload.get("vertices"), 3, "vertex"),
        "uvs": _points(payload.get("uvs"), 2, "uv"),
    }


def _points(values, width: int, label: str):
    if not isinstance(values, list) or not values:
        raise BindError(f"{label} list is empty")
    points = []
    for point in values:
        if not isinstance(point, (list, tuple)) or len(point) != width:
            raise BindError(f"{label} is unsupported")
        coords = []
        for coord in point:
            if isinstance(coord, bool) or not isinstance(coord, (int, float)) or not math.isfinite(coord):
                raise BindError(f"non-finite {label}")
            coords.append(float(coord))
        points.append(coords)
    return points


def _max_delta(left, right, label: str) -> float:
    if len(left) != len(right):
        raise BindError(f"{label} count differs")
    worst = 0.0
    for a, b in zip(left, right):
        for x, y in zip(a, b):
            worst = max(worst, abs(x - y))
    if not math.isfinite(worst):
        raise BindError(f"non-finite {label} delta")
    return worst


def _exact_int(value) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise BindError("non-finite image size")
    if isinstance(value, float) and not value.is_integer():
        raise BindError("non-integer image size")
    return int(value)


def _positive_finite(value, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise BindError(f"non-finite or empty {label}")
    return float(value)


def _nonnegative_finite(value, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise BindError(f"non-finite or empty {label}")
    return float(value)


def _load_json(path):
    if isinstance(path, dict):
        return path
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BindError(f"unreadable JSON: {exc}") from exc


def _run_blender(script: Path, args) -> None:
    exe = os.environ.get("TWINQA_BLENDER") or (str(_BLENDER) if _BLENDER.is_file() else "")
    if not exe:
        raise BindError("Blender executable not found")
    command = [exe, "--background", "--factory-startup", "--python-exit-code", "1",
               "--python", str(script), "--", *map(str, args)]
    completed = subprocess.run(command, capture_output=True, text=True)
    print(json.dumps({"command": command, "exit_code": completed.returncode}), flush=True)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()
        tail = detail[-1] if detail else f"exit {completed.returncode}"
        raise BindError(f"Blender failed: {tail}")


def _same(left, right) -> bool:
    if _key(left) == _key(right):
        return True
    try:
        return os.path.samefile(left, right)
    except OSError:
        return False


def _within(path, parent) -> bool:
    try:
        Path(_key(path)).relative_to(Path(_key(parent)))
    except ValueError:
        return False
    return not _same(path, parent)


def _key(path) -> str:
    return os.path.normcase(os.fspath(Path(path).resolve()))


if __name__ == "__main__":
    sys.exit(main())
