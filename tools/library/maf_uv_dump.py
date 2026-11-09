"""Dump per-material UV faces of library MAF FBX files that reference texture images.

Pattern: verify actual artifacts, not exporter return codes (docs/domain/patterns/INDEX.md).
new-case: UV readback of library MAF FBX for the atlas-cell material ID list (#524).

Run (Blender 5.1.2, headless, read-only; never saves any .fbx):
    blender --background --factory-startup --python-exit-code 1 \
      --python tools/library/maf_uv_dump.py -- <FBX_DIR> <LIST_TXT> <OUT_JSON>

`<LIST_TXT>` holds one FBX file name per line (the MAFs whose materials carry image
nodes, from `library/maf/fbx_materials.json`). `<OUT_JSON>` must be a NEW path.
Per FBX: every material with its image nodes (name + raw filepath) and every face
assigned to it as a UV polygon from the active UV layer (``uv_layer: null`` and no
faces when the mesh has no UV layer - recorded, never guessed). A listed FBX that is
missing or fails to import is an ``error`` row; the run still exits nonzero at the end.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy


def _images(mat):
    out = []
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return out
    for node in mat.node_tree.nodes:
        if node.type == "TEX_IMAGE" and node.image is not None:
            out.append({"name": node.image.name, "filepath": node.image.filepath})
    return out


def _clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def dump_file(path: Path) -> dict:
    bpy.ops.import_scene.fbx(filepath=str(path))
    mats: dict[str, dict] = {}
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        me = obj.data
        uvl = me.uv_layers.active
        slots = [s.material for s in obj.material_slots]
        for poly in me.polygons:
            mat = slots[poly.material_index] if poly.material_index < len(slots) else None
            key = mat.name if mat is not None else "<none>"
            rec = mats.setdefault(key, {"images": _images(mat), "uv_layer": uvl.name if uvl else None,
                                        "faces": []})
            if uvl is None:
                continue
            rec["faces"].append([round(c, 5) for li in poly.loop_indices for c in uvl.data[li].uv])
    return {"materials": mats}


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(argv) != 3:
        raise SystemExit("usage: maf_uv_dump.py -- <FBX_DIR> <LIST_TXT> <OUT_JSON>")
    fbx_dir, list_txt, out_json = Path(argv[0]), Path(argv[1]), Path(argv[2])
    if out_json.exists():
        raise SystemExit("refusing to overwrite existing output: " + str(out_json))
    names = [ln.strip() for ln in list_txt.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not names:
        raise SystemExit("empty FBX list: " + str(list_txt))
    rows, errors = [], 0
    for name in names:
        row = {"fbx": name}
        path = fbx_dir / name
        try:
            if not path.is_file():
                raise FileNotFoundError(str(path))
            row.update(dump_file(path))
        except Exception as exc:  # noqa: BLE001 - report every file, fail at the end
            row["error"] = str(exc)
            errors += 1
        _clear()
        rows.append(row)
        print("AGR_UV_DUMP_FILE", name, "error" if "error" in row else len(row["materials"]), flush=True)
    result = {"blender": bpy.app.version_string, "fbx_dir": str(fbx_dir), "files": rows}
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with out_json.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False)
    print("AGR_UV_DUMP", len(rows), "errors", errors, out_json)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
