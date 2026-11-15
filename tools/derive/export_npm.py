"""Shared NPM export step (`dt derive npm`): NPM OKS FBX from a VPM stage-6 master (headless Blender).

Pattern: n/a | new-case: one shared NPM export tool replacing the per-job export_npm.py copies (#1106).

Generalised from jobs/TEC26-OKS/scripts/export_npm.py (accepted AC08 pilot-v010 recipe = KPP1 v005 exporter with
an explicit spec and optional glass) plus the PSU275 extra-OKS options (--address, --index, --pivot).
Usage: blender --background --factory-startup --python tools/derive/export_npm.py -- \\
    <master.blend> <spec.json> <atlas_dir> <new_out_dir> [prefix] [--address A] [--index N] [--pivot x,y] [--keep-quads]
Same model as VPM (conflict #1); NPM changes on an export copy only: objects SM_<A>_<NNN>_Main / _MainGlass
(reg p.11-12 §3.3), UCX and REF_ data removed (reg App.1); alpha-cut back copies dropped (reg p.8 §3.13), the
copy facing away from the plan centre kept; one UV channel remapped from the VPM UDIM tile into its atlas region;
M_<A>_<NNN>_Main_1 (Base Color <- _d_, Alpha <- colour of _o_), glass M_Glass_01 alpha 0.5 (reg p.13 §3.5);
textures embedded (reg p.9 §5.1), triangulated unless --keep-quads (review copy, never a delivery), transforms
applied, pivot = plan centre Z 0 (or the shared --pivot of a multi-OKS package). Writes <out>/<prefix>_<A>_<NN>.fbx,
<out>/../export_npm_meta.json and <out>/../NPM_export_tri.blend (both refused if they already exist).
#1505: <atlas_dir>/npm_atlas.json must be bound to this master (`master.sha256` = SHA-256 of <master.blend>, `udims`
= its finish tiles; tools/derive/npm_atlas.py --master): otherwise refused before any write (atlas_unbound /
atlas_master_mismatch / atlas_udim_mismatch). After the FBX: export_meta.json stores master_sha256 and
<out>/../derivation/<fbx>.derivation.json (master path + master_sha256 + FBX sha256) is written for
`agr build-manifest build --derivation <out>/../derivation`; a master edited during the export is refused.
"""
import argparse
import importlib.util
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
RECIPE = os.path.normpath(os.path.join(HERE, "..", "..", "jobs", "TEC26-OKS", "scripts"))
_OWNER = os.path.normpath(os.path.join(HERE, "..", "..", "adapters", "max", "agr_tools", "udimtile_core.py"))
_ownspec = importlib.util.spec_from_file_location("udimtile_core_export_npm", _OWNER)
_udimtile = importlib.util.module_from_spec(_ownspec)
_ownspec.loader.exec_module(_udimtile)
_BM = os.path.normpath(os.path.join(HERE, "..", "..", "adapters", "max", "agr_tools", "build_manifest.py"))
_bmspec = importlib.util.spec_from_file_location("build_manifest_export_npm", _BM)
_bm = importlib.util.module_from_spec(_bmspec)
_bmspec.loader.exec_module(_bm)


def face_udim(cu, cv):
    """(tile, u_tile, v_tile) of a face centroid via udimtile_core (#1337, #1376). A centroid outside u in [0, 10),
    v >= 0 or not finite raises UdimDomainError (a ValueError); before #1376 u tile 10 silently became 1011."""
    tile = _udimtile.udim_tile(cu, cv)
    tu, tv = _udimtile.tile_origin(tile)
    return tile, tu, tv


def parse(argv):
    ap = argparse.ArgumentParser(prog="dt derive npm", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("master")
    ap.add_argument("spec")
    ap.add_argument("atlas_dir")
    ap.add_argument("out")
    ap.add_argument("prefix", nargs="?", default="0000", help="4-digit district prefix (placeholder 0000)")
    ap.add_argument("--address", help="NPM address (default: from SM_<A>_Main); extra OKS share the main address")
    ap.add_argument("--index", type=int, default=1, help="OKS index inside the NPM package (NNN / NN), default 1")
    ap.add_argument("--pivot", help="x,y of one shared origin for every FBX of a multi-OKS NPM package")
    ap.add_argument("--keep-quads", action="store_true", help="untriangulated review copy (not a delivery)")
    ap.add_argument("--recipe-dir", default=RECIPE, help="directory with export_safety.py")
    a = ap.parse_args(argv)
    if not 1 <= a.index <= 99:
        ap.error(f"--index {a.index} outside 1..99")
    pivot = None
    if a.pivot is not None:
        try:
            pivot = [float(c) for c in a.pivot.split(",")]
        except ValueError:
            ap.error(f"--pivot {a.pivot!r} is not x,y")
        if len(pivot) != 2 or not all(math.isfinite(c) for c in pivot):
            ap.error(f"--pivot {a.pivot!r} must be two finite numbers x,y")
    a.pivot_xy = pivot
    return a


def main(argv):
    a = parse(argv)
    sys.path.insert(0, a.recipe_dir)
    from export_safety import require_udim_regions, validate_atlas

    out = os.path.abspath(a.out)
    meta_path = os.path.join(out, "..", "export_npm_meta.json")
    blend_path = os.path.join(out, "..", "NPM_export_tri.blend")
    shared_meta_path = os.path.join(out, 'export_meta.json')
    store = _bm.derivation_store(out)  # <out>/../derivation/: export-time record for the build manifest (#1505)
    inputs = [os.path.realpath(p) for p in (a.master, a.spec, a.atlas_dir)]
    for p in (out, meta_path, blend_path, store):
        r = os.path.realpath(p)
        if any(r == q or r.startswith(q + os.sep) or q.startswith(r + os.sep) for q in inputs):
            raise SystemExit(f"output {p} aliases an input")
    for p in (meta_path, blend_path):
        if os.path.lexists(p):
            raise SystemExit(f"output {p} already exists; choose a new version")
    atlas = json.load(open(os.path.join(a.atlas_dir, "npm_atlas.json"), encoding="utf-8"))
    texture_spec = json.load(open(a.spec, encoding="utf-8"))
    by_udim = validate_atlas(atlas, texture_spec)
    # #1505: the atlas must be bound to exactly this master revision; hashed before the master is opened
    master_sha = _bm.sha256_file(a.master)
    try:
        _bm.check_atlas_master(atlas, master_sha)
    except _bm.AtlasBindingError as exc:
        raise SystemExit(f"refused: {exc}") from None
    os.makedirs(out, exist_ok=True)
    if os.listdir(out):
        raise SystemExit(f"NPM out dir {out} is not empty")
    bpy.ops.wm.open_mainfile(filepath=a.master)
    sc = bpy.context.scene

    for o in list(bpy.data.objects):
        if o.name.startswith("UCX_") or any(c.name.startswith("REF_") for c in o.users_collection) or o.type != "MESH":
            bpy.data.objects.remove(o)
    for c in list(bpy.data.collections):
        if c.name.startswith("REF_"):
            bpy.data.collections.remove(c)

    mains = [o for o in sc.objects if o.name.endswith("_Main")]
    glasses = [o for o in sc.objects if o.name.endswith("_MainGlass")]
    if len(mains) != 1 or len(glasses) > 1:
        raise SystemExit(f"expected one *_Main and at most one *_MainGlass, got {[o.name for o in mains + glasses]}")
    main, glass = mains[0], (glasses[0] if glasses else None)
    vis = [o for o in (main, glass) if o is not None]
    A = a.address or main.name[3:-5]
    NNN, NN = f"{a.index:03d}", f"{a.index:02d}"
    names = main["finish_names"].split(",")
    alpha_ids = {i for i, n in enumerate(names) if "Alpha" in n}

    pts = [o.matrix_world @ v.co for o in vis for v in o.data.vertices]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    centre = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, 0.0))
    own_centre = centre.copy()  # alpha back copies: keep the one facing away from this OKS plan centre
    if a.pivot_xy is not None:
        centre = Vector(a.pivot_xy + [0.0])

    report = {"address": A, "prefix": a.prefix, "pivot_revit_internal_m": [round(centre.x, 4), round(centre.y, 4), 0.0]}

    # ---- Main: drop alpha back copies, remap UVs into the atlas
    bm = bmesh.new()
    bm.from_mesh(main.data)
    fl = bm.faces.layers.int["finish"]
    uv = bm.loops.layers.uv["UVMap"]
    plan_c = Vector((own_centre.x, own_centre.y, 0))
    alpha_faces = [f for f in bm.faces if f[fl] in alpha_ids]
    drop = set()
    for f in alpha_faces:
        if f in drop:
            continue
        c, n = f.calc_center_median(), f.normal
        for g in alpha_faces:
            if g is f or g in drop or g.normal.dot(n) > -0.99:
                continue
            d = g.calc_center_median() - c
            if abs(d.dot(n)) < 0.012 and (d - n * d.dot(n)).length < 0.02:
                # pair: keep the one facing away from the plan centre (horizontal planes: keep the up one)
                if abs(n.z) > 0.9:
                    keep_f = n.z > 0
                else:
                    keep_f = (c - plan_c).dot(Vector((n.x, n.y, 0))) >= 0
                drop.add(g if keep_f else f)
                break
    bmesh.ops.delete(bm, geom=list(drop), context="FACES_ONLY")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    # Check every retained face BEFORE remapping or saving the export copy.
    face_tiles = []
    try:
        for f in bm.faces:
            c = sum((loop[uv].uv for loop in f.loops), Vector((0, 0))) / len(f.loops)
            try:
                face_tiles.append((f, *face_udim(c.x, c.y)))
            except ValueError as exc:
                raise ValueError(f"face {f.index}: {exc}") from None
        require_udim_regions((tile for _, tile, _, _ in face_tiles), by_udim)
    except ValueError:
        bm.free()
        raise
    for f, tile, tu, tv in face_tiles:
        r = by_udim[tile]
        for loop in f.loops:
            loc = loop[uv].uv - Vector((tu, tv))
            loop[uv].uv = Vector((r["u0"], r["v0"])) + loc * r["size"]
    bm.to_mesh(main.data)
    bm.free()
    report.update({"alpha_back_copies_removed": len(drop), "faces_without_region": 0})

    # ---- clean layers / attributes not meant for delivery, apply transforms, pivot, triangulate
    for o in vis:
        me = o.data
        for uvl in [u for u in me.uv_layers if u.name != "UVMap"]:
            me.uv_layers.remove(uvl)
        for an in [x.name for x in me.attributes if x.name in ("finish", "uvx", "srcid")]:
            me.attributes.remove(me.attributes[an])
        for k in list(o.keys()):
            del o[k]
        me.transform(o.matrix_world)
        o.matrix_world = Matrix.Identity(4)
        me.transform(Matrix.Translation(-centre))
        if a.pivot_xy is not None:  # shared frame, origin at this OKS plan centre (SINTEZ 'точка отсчёта')
            off = Vector((own_centre.x - centre.x, own_centre.y - centre.y, 0.0))
            me.transform(Matrix.Translation(-off))
            o.location = off
        b = bmesh.new()
        b.from_mesh(me)
        if not a.keep_quads:
            bmesh.ops.triangulate(b, faces=b.faces, quad_method="BEAUTY", ngon_method="BEAUTY")
        b.to_mesh(me)
        b.free()
        me.shade_flat()
        for c in list(o.users_collection):
            c.objects.unlink(o)
        sc.collection.objects.link(o)

    main.name = main.data.name = f"SM_{A}_{NNN}_Main"
    if glass:
        glass.name = glass.data.name = f"SM_{A}_{NNN}_MainGlass"

    # ---- materials
    def image(path):
        if not os.path.isfile(path):
            raise SystemExit(f"atlas texture missing: {path}")
        img = bpy.data.images.load(path)
        img.name = os.path.splitext(os.path.basename(path))[0]
        img.pack()
        return img

    mm = bpy.data.materials.new(f"M_{A}_{NNN}_Main_1")
    mm.use_nodes = True
    nt = mm.node_tree
    for n in list(nt.nodes):
        if n.type not in {"BSDF_PRINCIPLED", "OUTPUT_MATERIAL"}:
            nt.nodes.remove(n)
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    td = nt.nodes.new("ShaderNodeTexImage")
    td.image = image(os.path.join(a.atlas_dir, f"T_{A}_{NNN}_Main_d_1.png"))
    to = nt.nodes.new("ShaderNodeTexImage")
    to.image = image(os.path.join(a.atlas_dir, f"T_{A}_{NNN}_Main_o_1.png"))
    to.image.colorspace_settings.name = "Non-Color"
    nt.links.new(td.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(to.outputs["Color"], bsdf.inputs["Alpha"])
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = 0.6
    main.data.materials.clear()
    main.data.materials.append(mm)

    if glass:
        mg = bpy.data.materials.new("M_Glass_01")
        mg.use_nodes = True
        gb = next(n for n in mg.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        gb.inputs["Base Color"].default_value = (0.75, 0.82, 0.82, 1.0)
        gb.inputs["Alpha"].default_value = 0.5
        gb.inputs["Roughness"].default_value = 0.05
        glass.data.materials.clear()
        glass.data.materials.append(mg)
    for o in vis:
        for p in o.data.polygons:
            p.material_index = 0

    for m in list(bpy.data.materials):
        if m.users == 0:
            bpy.data.materials.remove(m)

    for o in sc.objects:
        o.select_set(o in vis)
    fbx = os.path.join(out, f"{a.prefix}_{A}_{NN}.fbx")
    if os.path.lexists(os.path.join(store, os.path.basename(fbx) + _bm.DERIVATION_SUFFIX)):
        raise SystemExit(f"derivation record for {os.path.basename(fbx)} already exists in {store}; new version")
    bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, object_types={"MESH"},
                             axis_forward="Y", axis_up="Z", apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
                             global_scale=1.0, bake_space_transform=False, use_mesh_modifiers=False,
                             mesh_smooth_type="FACE", use_triangles=False, use_custom_props=False,
                             add_leaf_bones=False, bake_anim=False, path_mode="COPY", embed_textures=True)

    def tri(o):
        return sum(len(p.vertices) - 2 for p in o.data.polygons)

    sys.path.insert(0, HERE)
    from export_meta import record_export
    exported_top = max((o.matrix_world @ v.co).z for o in vis for v in o.data.vertices)
    record_export(fbx, source=a.master, top=float(exported_top), metadata_path=shared_meta_path,
                  master=a.master, master_sha256=master_sha)
    record = _bm.write_export_derivation([fbx], a.master, store, _bm.git_commit(os.path.join(HERE, "..", "..")),
                                         master_sha256=master_sha, inputs=[a.spec, a.atlas_dir])
    report.update({"fbx": fbx, "main_tris": tri(main), "glass_tris": tri(glass) if glass else 0,
                   "master_sha256": master_sha, "derivation": record})
    with open(meta_path, "x") as fh:
        json.dump(report, fh, indent=1)
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    print("EXPORT-NPM", json.dumps(report))


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
