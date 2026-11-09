"""#298 follow-up: the Vatutino NPM FBX embeds its PNGs (V006 / SINTEZ 2.5.1); VPM stays STRIP.

Pattern: new-case: site FBX texture-embedding regression (export kwargs read from the job script itself).

Root cause: in jobs/VATUTINO-SITE/assemble_delivery.py the `path_mode=...` and `embed_textures=...` keywords
sat inside the trailing `# MAF-18 / V003` comment of the `use_triangles=True,` line, so export_scene.fbx ran
with its defaults (path_mode='AUTO', embed_textures=False) for both profiles. The static test needs no Blender;
the repro exports one textured plane in background Blender 5.1 with the script's own keywords and is skipped
when Blender is not found.
"""
import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "jobs" / "VATUTINO-SITE" / "assemble_delivery.py"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def export_kwargs(profile: str) -> dict:
    """Keywords of the single bpy.ops.export_scene.fbx call, evaluated for `profile` (filepath dropped)."""
    calls = [n for n in ast.walk(ast.parse(SCRIPT.read_text(encoding="utf-8")))
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "fbx"
             and isinstance(n.func.value, ast.Attribute) and n.func.value.attr == "export_scene"]
    assert len(calls) == 1, f"expected one export_scene.fbx call, found {len(calls)}"
    out = {}
    for kw in calls[0].keywords:
        if kw.arg == "filepath":
            continue
        out[kw.arg] = eval(compile(ast.Expression(kw.value), str(SCRIPT), "eval"), {"__builtins__": {}},
                           {"profile": profile})
    return out


@pytest.mark.parametrize("profile,path_mode,embed", [("npm", "COPY", True), ("vpm", "STRIP", False)])
def test_export_call_passes_texture_keywords(profile, path_mode, embed):
    kw = export_kwargs(profile)
    assert kw.get("path_mode") == path_mode, kw
    assert kw.get("embed_textures") is embed, kw
    assert kw["use_triangles"] is True and kw["object_types"] == {"MESH"}


def test_export_kwargs_rejects_unknown_profile_names():
    # fail-closed witness: an unknown profile never yields an embedding NPM export
    kw = export_kwargs("ifc")
    assert kw["embed_textures"] is False and kw["path_mode"] == "STRIP"


REPRO = r'''
import json, sys
from pathlib import Path
import bpy
args = sys.argv[sys.argv.index("--") + 1:]
script, png, fbx, kwjson = Path(args[0]), Path(args[1]), Path(args[2]), args[3]
src = script.read_text(encoding="utf-8")
ns = {}
start = src.index("def solid_png")
exec(compile(src[start:src.index("\ndef material", start)], str(script), "exec"),
     {"struct": __import__("struct"), "zlib": __import__("zlib")}, ns)
ns["solid_png"](png, (200, 30, 30), 64)          # written to disk BEFORE it is loaded, as in the job
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_plane_add(size=2)
ob = bpy.context.active_object
mat = bpy.data.materials.new("M_Repro")
mat.use_nodes = True
tree = mat.node_tree
bsdf = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
node = tree.nodes.new("ShaderNodeTexImage")
node.image = bpy.data.images.load(str(png), check_existing=True)
tree.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
ob.data.materials.append(mat)
kw = json.loads(kwjson)
if kw.get("embed_textures"):
    node.image.pack()                             # same step as the job's NPM branch
kw["object_types"] = set(kw["object_types"])
bpy.ops.object.select_all(action="DESELECT")
ob.select_set(True)
bpy.ops.export_scene.fbx(filepath=str(fbx), **kw)
'''


def _blender():
    sys.path.insert(0, str(ROOT / "src"))
    from twinqa.scene import find_blender
    return find_blender()


@pytest.mark.parametrize("profile,expected_png", [("npm", 1), ("vpm", 0)])
def test_repro_fbx_png_blob_count(tmp_path, profile, expected_png):
    blender = _blender()
    if not blender:
        pytest.skip("Blender not found (DT_BLENDER or the pinned Blender 5.1 path)")
    src, out = tmp_path / "src", tmp_path / "out"
    src.mkdir()
    out.mkdir()
    png, fbx, script = src / "T_Repro_Diffuse.png", out / f"SM_Repro_{profile}.fbx", tmp_path / "repro.py"
    script.write_text(REPRO, encoding="utf-8")
    kw = export_kwargs(profile)
    kw["object_types"] = sorted(kw["object_types"])
    run = subprocess.run([blender, "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(script), "--",
                          str(SCRIPT), str(png), str(fbx), json.dumps(kw)],
                         capture_output=True, text=True, timeout=300, encoding="utf-8", errors="replace")
    assert run.returncode == 0 and fbx.is_file(), run.stderr[-2000:] or run.stdout[-2000:]
    data = fbx.read_bytes()
    assert data.count(PNG_MAGIC) == expected_png, (profile, data.count(PNG_MAGIC))
    assert png.read_bytes().startswith(PNG_MAGIC)  # the input PNG is untouched
    if profile == "npm":
        # validate_package V006 'embedded textures' fails when the readback finds no image (_no_texture_findings);
        # read back with the source PNG gone so only an embedded copy can satisfy it.
        png.unlink()
        sys.path.insert(0, str(ROOT / "tools" / "qa"))
        from twinqa.scene import readback
        import validate_package as vp
        rb = readback(fbx, blender=blender)
        assert rb.get("images") and all(i["packed"] for i in rb["images"]), rb.get("images")
        found = {}
        vp._no_texture_findings(found, "oks", fbx.name, rb)
        assert not [f for f in found.get("V006", []) if f.name == "embedded textures"]
