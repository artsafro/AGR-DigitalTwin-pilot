"""NPM "star" Flora objects and their VPM shell from an approved map pair [D102].

Pattern: n/a | new-case: #1146 Flora route A steps 3-4 (star builder, VPM = closed shell of the star).

NPM: n vertical planes (tree 4 = 8 tris, bush 3 = 6 tris) rotated 180/n degrees around the
vertical axis, each carrying the species' diffuse + opacity map. The plane is the plant's
opaque bbox plus a small margin (D155: slightly larger than the plant, no clipped pixels),
scaled so the plant's opaque height equals the target height; the plant base sits SINK m
below the pivot [D100]. UVs are the same rectangle of the 0-1 image.
VPM: every plane becomes a closed shell (front, back offset by THICKNESS with flipped
normals, 4 rim quads = 12 tris per plane, FLO-11 0.003-0.01 m), UVs moved into a given UDIM
tile [D210]. The tile has no default: an unknown tile is an error, never 1001.

Geometry is pure Python (tested without a DCC); `--fbx` writes and reads back an FBX through
Blender headless [D110]. Run: uv run python tools/flora/build_flora_star.py --spec <json> --out <dir>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BLENDER = os.environ.get("BLENDER_EXE", "C:/Program Files/Blender Foundation/Blender 5.1/blender.exe")
PLANES = {"tree": 4, "bush": 3}
SINK = 0.10
MARGIN = 0.015
THICKNESS = 0.005
TEXEL_VPM = (520.0, 1706.0)
KEY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


class StarError(ValueError):
    pass


def valid_key(key):
    """Return True if `key` is a path-safe species name (no path separators, no '..' escape)."""
    return isinstance(key, str) and KEY_PATTERN.fullmatch(key) is not None and ".." not in key


def plant_bbox(opacity_path):
    """Return (size, x0, y0, x1, y1) of opaque (>=128) pixels; x1/y1 exclusive, y down."""
    import numpy as np
    from PIL import Image
    image = Image.open(opacity_path)
    if image.mode not in ("L", "1"):
        raise StarError(f"{opacity_path}: opacity must be a grey map, got mode {image.mode}")
    if image.width != image.height:
        raise StarError(f"{opacity_path}: map must be square, got {image.width}x{image.height}")
    a = np.asarray(image.convert("L"))
    binary = np.count_nonzero((a == 0) | (a == 255)) / a.size
    if binary < 0.99:
        raise StarError(f"{opacity_path}: opacity is not binary ({binary:.4f} < 0.99 of pixels 0/255)")
    mask = a >= 128
    if not mask.any() or mask.all():
        raise StarError(f"{opacity_path}: opacity must hold both plant and background")
    rows = np.flatnonzero(mask.any(axis=1))
    cols = np.flatnonzero(mask.any(axis=0))
    return image.width, int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1


def _finite_positive(name, value):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value <= 0:
        raise StarError(f"{name} must be a finite positive number, got {value!r}")


def star_mesh(kind, height_m, bbox, margin=MARGIN):
    """Return {'verts', 'tris', 'uvs' (per tri corner), 'planes', 'plane_rect'} for an NPM star."""
    if kind not in PLANES:
        raise StarError(f"unknown plant kind {kind!r}; expected one of {sorted(PLANES)}")
    _finite_positive("height_m", height_m)
    size, x0, y0, x1, y1 = bbox
    if not (0 <= x0 < x1 <= size and 0 <= y0 < y1 <= size):
        raise StarError(f"bbox {bbox} outside the {size}px image")
    pad = margin * size
    rx0, ry0 = max(0.0, x0 - pad), max(0.0, y0 - pad)
    rx1, ry1 = min(float(size), x1 + pad), min(float(size), y1 + pad)
    s = height_m / (y1 - y0)                      # metres per pixel
    cx = (x0 + x1) / 2.0
    zb = -SINK - (ry1 - y1) * s                   # plant base (pixel row y1) at -SINK
    zt = -SINK + (y1 - ry0) * s
    left, right = (rx0 - cx) * s, (rx1 - cx) * s
    u0, u1 = rx0 / size, rx1 / size
    v0, v1 = 1.0 - ry1 / size, 1.0 - ry0 / size
    verts, tris, uvs = [], [], []
    n = PLANES[kind]
    for k in range(n):
        a = math.pi * k / n
        c, sn = math.cos(a), math.sin(a)
        base = len(verts)
        for h, z in ((left, zb), (right, zb), (right, zt), (left, zt)):
            verts.append((h * c, h * sn, z))
        quad_uv = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
        for t in ((0, 1, 2), (0, 2, 3)):
            tris.append(tuple(base + i for i in t))
            uvs.append(tuple(quad_uv[i] for i in t))
    return {"verts": verts, "tris": tris, "uvs": uvs, "planes": n,
            "metres_per_px": s, "plane_px": (rx1 - rx0, ry1 - ry0),
            "plane_m": (right - left, zt - zb)}


def udim_offset(tile):
    if not isinstance(tile, int) or isinstance(tile, bool) or not 1001 <= tile <= 1100:
        raise StarError(f"UDIM tile must be an int in 1001..1100, got {tile!r}")
    return (tile - 1001) % 10, (tile - 1001) // 10


def vpm_shell(npm, tile, thickness=THICKNESS):
    """Closed shell per NPM plane: front, offset back (flipped), 4 rim quads; UVs in `tile`."""
    _finite_positive("thickness", thickness)
    if not 0.003 <= thickness <= 0.01:
        raise StarError(f"thickness {thickness} outside FLO-11 0.003-0.01 m")
    du, dv = udim_offset(tile)
    verts, tris, uvs = [], [], []
    for p in range(npm["planes"]):
        q = npm["verts"][4 * p:4 * p + 4]
        quv = [npm["uvs"][2 * p][0], npm["uvs"][2 * p][1], npm["uvs"][2 * p][2], npm["uvs"][2 * p + 1][2]]
        quv = [(u + du, v + dv) for u, v in quv]
        e1 = [q[1][i] - q[0][i] for i in range(3)]
        e2 = [q[3][i] - q[0][i] for i in range(3)]
        nrm = [e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]]
        ln = math.sqrt(sum(x * x for x in nrm))
        nrm = [x / ln * thickness for x in nrm]
        base = len(verts)
        verts += [tuple(v) for v in q]
        verts += [tuple(v[i] - nrm[i] for i in range(3)) for v in q]
        f, b = list(range(base, base + 4)), list(range(base + 4, base + 8))

        def quad(ids, uv4):
            tris.extend([(ids[0], ids[1], ids[2]), (ids[0], ids[2], ids[3])])
            uvs.extend([(uv4[0], uv4[1], uv4[2]), (uv4[0], uv4[2], uv4[3])])
        quad(f, quv)
        quad([b[0], b[3], b[2], b[1]], [quv[0], quv[3], quv[2], quv[1]])
        for i in range(4):
            j = (i + 1) % 4
            quad([f[j], f[i], b[i], b[j]], [quv[j], quv[i], quv[i], quv[j]])
    return {"verts": verts, "tris": tris, "uvs": uvs, "planes": npm["planes"], "tile": tile}


def closed_planes(mesh):
    """Number of planes whose 12 tris form a closed 2-manifold (every edge used twice)."""
    ok = 0
    for p in range(mesh["planes"]):
        edges = {}
        for t in mesh["tris"][12 * p:12 * p + 12]:
            for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                key = (min(a, b), max(a, b))
                edges[key] = edges.get(key, 0) + 1
        ok += all(c == 2 for c in edges.values())
    return ok


def metrics(mesh, tile=1001):
    du, dv = udim_offset(tile)
    zs = [v[2] for v in mesh["verts"]]
    xy = [math.hypot(v[0], v[1]) for v in mesh["verts"]]
    outside = sum(1 for tri in mesh["uvs"]
                  if any(not (du <= u <= du + 1 and dv <= v <= dv + 1) for u, v in tri))
    return {"tris": len(mesh["tris"]), "height_m": round(max(zs) - min(zs) - SINK, 4),
            "crown_m": round(2 * max(xy), 4), "uv_faces_outside_tile": outside}


def atlas_cell(cell, key):
    """Validate an atlas cell [u0, v0, u1, v1] inside 0-1 with positive area."""
    if not (isinstance(cell, list) and len(cell) == 4 and all(
            isinstance(c, (int, float)) and not isinstance(c, bool) and math.isfinite(c) for c in cell)):
        raise StarError(f"species {key}: atlas_cell must be [u0, v0, u1, v1], got {cell!r}")
    u0, v0, u1, v1 = cell
    if not (0 <= u0 < u1 <= 1 and 0 <= v0 < v1 <= 1):
        raise StarError(f"species {key}: atlas_cell {cell} must lie inside 0-1 with u0<u1, v0<v1")
    return u0, v0, u1, v1


def to_cell(mesh, cell):
    """Move every 0-1 UV of `mesh` (UV of the species map) into `cell` of the atlas."""
    u0, v0, u1, v1 = cell
    mesh["uvs"] = [tuple((u0 + u * (u1 - u0), v0 + v * (v1 - v0)) for u, v in tri) for tri in mesh["uvs"]]
    return mesh


def outside_cell(mesh, cell, tile=1001, eps=1e-9):
    du, dv = udim_offset(tile)
    u0, v0, u1, v1 = cell
    return sum(1 for tri in mesh["uvs"] if any(not (du + u0 - eps <= u <= du + u1 + eps
                                                    and dv + v0 - eps <= v <= dv + v1 + eps) for u, v in tri))


def _atlas_texel(texel, cell, size, bbox):
    """Texel in atlas pixels: source px/m x (cell px / source px) (G4: measured in the final atlas)."""
    cell_px = (cell[2] - cell[0]) * size
    return round(cell_px, 2), texel * cell_px / bbox[0]


def build_species(item, tile, atlas=None, vpm_atlas=None):
    """item: {key, latin, kind, height_m, band_m:[lo,hi], diffuse, opacity, material_id[, atlas_cell, vpm_atlas_cell]}.

    With `atlas` ({diffuse, opacity, size, material}) the UVs move into the item's atlas cell and
    the texel is also reported in atlas pixels (G4: measured in the final atlas, no upscaling).
    With `vpm_atlas` the VPM shell samples its own atlas cell `vpm_atlas_cell` instead [D246]."""
    for key in ("key", "latin", "kind", "height_m", "band_m", "diffuse", "opacity", "material_id"):
        if key not in item:
            raise StarError(f"species {item.get('key', '?')}: missing field {key!r}")
    for key in ("diffuse", "opacity"):
        if not Path(item[key]).is_file():
            raise StarError(f"species {item['key']}: {key} map not found: {item[key]}")
    lo, hi = item["band_m"]
    bbox = plant_bbox(item["opacity"])
    npm = star_mesh(item["kind"], item["height_m"], bbox)
    map_uvs = npm["uvs"]
    cell = atlas_cell(item.get("atlas_cell"), item["key"]) if atlas is not None else None
    if cell is not None:
        to_cell(npm, cell)
    vcell = atlas_cell(item.get("vpm_atlas_cell"), item["key"]) if vpm_atlas is not None else None
    vpm = vpm_shell(to_cell({**npm, "uvs": map_uvs}, vcell) if vcell is not None else npm, tile)
    m_npm, m_vpm = metrics(npm), metrics(vpm, tile)
    texel = 1.0 / npm["metres_per_px"]
    extra = {}
    if cell is not None and atlas is not None:
        cell_px, t_atlas = _atlas_texel(texel, cell, atlas["size"], bbox)
        extra["atlas"] = {"cell": list(cell), "cell_px": cell_px, "texel_px_per_m": round(t_atlas, 1),
                          "texel_ok": TEXEL_VPM[0] <= t_atlas <= TEXEL_VPM[1],
                          "uv_faces_outside_cell": {"npm": outside_cell(npm, cell),
                                                    "vpm": outside_cell(vpm, vcell or cell, tile)}}
    if vcell is not None:
        cell_px, t_vpm = _atlas_texel(texel, vcell, vpm_atlas["size"], bbox)
        extra["vpm_atlas"] = {"cell": list(vcell), "cell_px": cell_px, "texel_px_per_m": round(t_vpm, 1),
                              "texel_ok": TEXEL_VPM[0] <= t_vpm <= TEXEL_VPM[1],
                              "uv_faces_outside_cell": outside_cell(vpm, vcell, tile)}
    return {**extra,
        "key": item["key"], "latin": item["latin"], "kind": item["kind"],
        "material_id": item["material_id"], "bbox_px": list(bbox),
        "npm": m_npm, "vpm": {**m_vpm, "closed_planes": closed_planes(vpm), "planes": vpm["planes"],
                              "udim_tile": tile, "texel_px_per_m": round(texel, 1),
                              "texel_ok": TEXEL_VPM[0] <= texel <= TEXEL_VPM[1]},
        "height_in_band": lo <= m_npm["height_m"] <= hi,
        "expected_tris": {"npm": 2 * PLANES[item["kind"]], "vpm": 12 * PLANES[item["kind"]]},
        "_meshes": {"npm": npm, "vpm": vpm},
    }


def sha(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def _blender(script_args):
    cmd = [BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
           "--python", str(Path(__file__).resolve()), "--"] + script_args
    run = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    if run.returncode != 0:
        raise StarError(f"Blender failed ({run.returncode}): {run.stderr[-2000:] or run.stdout[-2000:]}")
    return run


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--spec", required=True, help="JSON: {udim_tile, species:[...]}")
    parser.add_argument("--out", required=True, help="new output directory (must not exist)")
    parser.add_argument("--fbx", action="store_true", help="write + read back FBX via Blender headless")
    args = parser.parse_args(argv)
    spec_path, out = Path(args.spec).resolve(), Path(args.out).resolve()
    if out.exists():
        raise SystemExit(f"output exists, refusing to overwrite: {out}")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if "udim_tile" not in spec:
        raise SystemExit("spec has no udim_tile (D210: first free tile after Ground); no default")
    items = spec.get("species") or []
    if not items:
        raise SystemExit("spec has no species")
    for item in items:
        if not valid_key(item.get("key")):
            print(f"invalid species key {item.get('key')!r}: must match ^[A-Za-z0-9_.-]+$ and not contain '..'",
                  file=sys.stderr)
            return 2
    keys = [i.get("key") for i in items]
    if len(set(keys)) != len(keys):
        raise SystemExit(f"duplicate species keys: {sorted(k for k in set(keys) if keys.count(k) > 1)}")
    inputs = {Path(i[k]).resolve() for i in items for k in ("diffuse", "opacity") if k in i} | {spec_path}
    if out in inputs or any(out in p.parents for p in inputs):
        raise SystemExit(f"output {out} aliases an input")
    atlas = spec.get("atlas")
    vpm_atlas = spec.get("vpm_atlas")
    if vpm_atlas is not None and atlas is None:
        raise SystemExit("spec vpm_atlas needs the NPM atlas too [D246]")
    for name, at in (("atlas", atlas), ("vpm_atlas", vpm_atlas)):
        if at is None:
            continue
        if not (isinstance(at, dict) and all(k in at for k in ("diffuse", "opacity", "size", "material"))):
            raise SystemExit(f"spec {name} needs diffuse, opacity, size, material")
        for k in ("diffuse", "opacity"):
            if not Path(at[k]).is_file():
                raise SystemExit(f"{name} {k} not found: {at[k]}")
            inputs.add(Path(at[k]).resolve())
        if out in inputs or any(out in p.parents for p in inputs):
            raise SystemExit(f"output {out} aliases an input")
    try:
        results = [build_species(i, spec["udim_tile"], atlas, vpm_atlas) for i in items]
    except StarError as error:
        raise SystemExit(str(error))
    partial = out.with_name(out.name + ".partial")
    if partial.exists():
        raise SystemExit(f"stale temp exists: {partial}")
    partial.mkdir(parents=True)
    meshes = {r["key"]: {"latin": r["latin"], "material_id": r["material_id"], **r.pop("_meshes")} for r in results}
    for r, i in zip(results, items):
        src = atlas if atlas is not None else i
        meshes[r["key"]].update(diffuse=str(Path(src["diffuse"]).resolve()),
                                opacity=str(Path(src["opacity"]).resolve()))
        if atlas is not None:
            meshes[r["key"]]["material"] = atlas["material"]
        if vpm_atlas is not None:
            meshes[r["key"]].update(vpm_diffuse=str(Path(vpm_atlas["diffuse"]).resolve()),
                                    vpm_opacity=str(Path(vpm_atlas["opacity"]).resolve()),
                                    vpm_material=vpm_atlas["material"])
    (partial / "meshes.json").write_text(json.dumps(meshes), encoding="utf-8")
    report = {"schema": "flora-star-v1", "spec": str(spec_path), "spec_sha256": sha(spec_path),
              "udim_tile": spec["udim_tile"], "species": results}
    for name, at in (("atlas", atlas), ("vpm_atlas", vpm_atlas)):
        if at is not None:
            report[name] = {"count": 1, "material": at["material"], "size": at["size"],
                            "diffuse": str(Path(at["diffuse"]).resolve()), "diffuse_sha256": sha(at["diffuse"]),
                            "opacity": str(Path(at["opacity"]).resolve()), "opacity_sha256": sha(at["opacity"])}
    if args.fbx:
        _blender(["build", str(partial / "meshes.json"), str(partial)])
        readback = json.loads((partial / "readback.json").read_text(encoding="utf-8"))
        report["fbx_readback"] = readback
    checks = []
    for r in results:
        checks.append(r["npm"]["tris"] == r["expected_tris"]["npm"] and r["vpm"]["tris"] == r["expected_tris"]["vpm"]
                      and r["height_in_band"] and r["npm"]["uv_faces_outside_tile"] == 0
                      and r["vpm"]["uv_faces_outside_tile"] == 0 and r["vpm"]["closed_planes"] == r["vpm"]["planes"]
                      and (all(v == 0 for v in r["atlas"]["uv_faces_outside_cell"].values()) if "atlas" in r else True)
                      and r.get("vpm_atlas", {}).get("uv_faces_outside_cell", 0) == 0)
    if args.fbx:
        for r in results:
            rb = report["fbx_readback"].get(r["key"], {})
            checks.append(rb.get("npm_tris") == r["npm"]["tris"] and rb.get("vpm_tris") == r["vpm"]["tris"]
                          and rb.get("npm_uv_outside") == 0 and rb.get("vpm_uv_outside") == 0
                          and rb.get("npm_materials") == 1 and rb.get("vpm_materials") == 1)
    report["geometry_passed"] = all(checks)
    report["texel_vpm_failures"] = [r["key"] for r in results
                                    if not r.get("vpm_atlas", r.get("atlas", r["vpm"]))["texel_ok"]]
    report["passed"] = False  # visual acceptance (route step 9) is a manual gate
    (partial / "report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    partial.rename(out)
    print(json.dumps({"out": str(out), "geometry_passed": report["geometry_passed"],
                      "species": len(results), "texel_vpm_failures": report["texel_vpm_failures"]}))
    return 0 if report["geometry_passed"] else 1


# ---------------------------------------------------------------- Blender side
def _bpy_build(meshes_json, out_dir):
    import bpy
    out_dir = Path(out_dir)
    data = json.loads(Path(meshes_json).read_text(encoding="utf-8"))

    def make_material(name, diffuse, opacity):
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        nt = mat.node_tree
        bsdf = nt.nodes["Principled BSDF"]
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(diffuse)
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        op = nt.nodes.new("ShaderNodeTexImage")
        op.image = bpy.data.images.load(opacity)
        op.image.colorspace_settings.name = "Non-Color"
        nt.links.new(op.outputs["Color"], bsdf.inputs["Alpha"])
        return mat

    def make_object(name, mesh, mat):
        me = bpy.data.meshes.new(name)
        me.from_pydata(mesh["verts"], [], mesh["tris"])
        uv = me.uv_layers.new(name="UVMap")
        for poly, tri_uv in zip(me.polygons, mesh["uvs"]):
            for li, (u, v) in zip(poly.loop_indices, tri_uv):
                uv.data[li].uv = (u, v)
        me.materials.append(mat)
        obj = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(obj)
        return obj

    readback = {}
    for key, m in data.items():
        for prof in ("npm", "vpm"):
            bpy.ops.wm.read_factory_settings(use_empty=True)
            vp = "vpm_" if prof == "vpm" and "vpm_diffuse" in m else ""  # VPM own atlas [D246]
            mat = make_material(m.get(f"{vp}material") or f"M_Flora_{m['material_id']}_{prof.upper()}",
                                m[f"{vp}diffuse"], m[f"{vp}opacity"])
            obj = make_object(f"SM_{key}_{prof.upper()}", m[prof], mat)
            obj["material_id"] = int(m["material_id"])
            path = out_dir / f"{key}_{prof}.fbx"
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True, path_mode="COPY",
                                     embed_textures=(prof == "npm"), axis_forward="-Z", axis_up="Y")
        for prof in ("npm", "vpm"):
            bpy.ops.wm.read_factory_settings(use_empty=True)
            bpy.ops.import_scene.fbx(filepath=str(out_dir / f"{key}_{prof}.fbx"))
            objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
            tris = sum(len(p.vertices) - 2 for o in objs for p in o.data.polygons)
            tile = m["vpm"].get("tile", 1001) if prof == "vpm" else 1001
            du, dv = (tile - 1001) % 10, (tile - 1001) // 10
            outside = 0
            for o in objs:
                uvl = o.data.uv_layers.active
                for p in o.data.polygons:
                    if any(not (du - 1e-5 <= uvl.data[li].uv[0] <= du + 1 + 1e-5
                                and dv - 1e-5 <= uvl.data[li].uv[1] <= dv + 1 + 1e-5) for li in p.loop_indices):
                        outside += 1
            zs = [(o.matrix_world @ v.co).z for o in objs for v in o.data.vertices]
            r = readback.setdefault(key, {})
            r[f"{prof}_tris"] = tris
            r[f"{prof}_uv_outside"] = outside
            r[f"{prof}_materials"] = len({s.material.name for o in objs for s in o.material_slots if s.material})
            r[f"{prof}_height_m"] = round(max(zs) - min(zs), 4)
            r[f"{prof}_sha256"] = sha(out_dir / f"{key}_{prof}.fbx")
    (out_dir / "readback.json").write_text(json.dumps(readback, indent=1), encoding="utf-8")


if __name__ == "__main__":
    try:
        import bpy  # noqa: F401  (present only inside Blender)
    except ImportError:
        sys.exit(main())
    blender_args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(blender_args) != 3 or blender_args[0] != "build":
        sys.exit(f"Blender side expects: -- build <meshes.json> <out_dir>, got {blender_args}")
    _bpy_build(blender_args[1], blender_args[2])
