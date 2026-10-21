"""Extract MAF library material appearance (colour + texture) from exported FBX files.

Pattern: verify actual artifacts, not exporter return codes (docs/domain/patterns/INDEX.md).
new-case: library-wide MAF material ID list from FBX material definitions.

Run (Blender 5.1.2, headless, read-only; never saves any .fbx):
    blender --background --factory-startup --python-exit-code 1 \
      --python tools/library/maf_material_extract.py -- <FBX_DIR> <OUT_JSON>

`<OUT_JSON>` must be a NEW path; the script refuses to overwrite. Each imported FBX
is read for its material nodes: the principled BSDF base colour and every TEX_IMAGE
node. Legacy (non-node) materials report `diffuse_color`. Colours are recorded as
0..1 floats AND as 8-bit hex so the downstream ID list can cluster solid colours.

Absent data is recorded, never guessed: a material with no principled BSDF has
`base_color: null`; a material with no image nodes has `textures: []`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy


def _hex8(rgb):
    if rgb is None:
        return None
    return "#{:02X}{:02X}{:02X}".format(
        *(max(0, min(255, int(round(v * 255)))) for v in rgb)
    )


def material_info(mat) -> dict:
    info: dict = {"name": mat.name, "base_color": None, "hex": None, "textures": []}
    if mat.use_nodes and mat.node_tree is not None:
        bsdf = next(
            (n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None
        )
        if bsdf is not None:
            col = [round(float(v), 6) for v in bsdf.inputs["Base Color"].default_value[:3]]
            info["base_color"] = col
            info["hex"] = _hex8(col)
        for node in mat.node_tree.nodes:
            if node.type == "TEX_IMAGE" and node.image is not None:
                info["textures"].append(
                    {"name": node.image.name, "filepath": node.image.filepath}
                )
    else:
        col = [round(float(v), 6) for v in mat.diffuse_color[:3]]
        info["base_color"] = col
        info["hex"] = _hex8(col)
    return info


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    if len(argv) != 2:
        raise SystemExit("usage: maf_material_extract.py -- <FBX_DIR> <OUT_JSON>")
    fbx_dir = Path(argv[0])
    out_json = Path(argv[1])
    if out_json.exists():
        raise SystemExit("refusing to overwrite existing output: " + str(out_json))
    if not fbx_dir.is_dir():
        raise SystemExit("FBX directory not found: " + str(fbx_dir))

    rows = []
    for path in sorted(fbx_dir.glob("*.fbx")):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        row = {"fbx": path.name}
        try:
            bpy.ops.import_scene.fbx(filepath=str(path))
            row["materials"] = [material_info(m) for m in bpy.data.materials]
        except Exception as exc:  # noqa: BLE001 - report, never crash the sweep
            row["error"] = str(exc)
        rows.append(row)

    result = {"blender": bpy.app.version_string, "fbx_dir": str(fbx_dir), "files": rows}
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with out_json.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=1)
    print("AGR_MAT_EXTRACT", len(rows), out_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
