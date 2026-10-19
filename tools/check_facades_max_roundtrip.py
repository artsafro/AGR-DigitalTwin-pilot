"""Read FBX exported by live Max and compare all corner UV/positions to Blender."""
from collections import Counter
import json
from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from technical_library.uv.corner_match import match_corners

out = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
bpy.ops.import_scene.fbx(filepath=str(out / "max_roundtrip.fbx"))
reference = json.loads((out / "blender-reference.json").read_text(encoding="utf-8"))
report = {}

for name, ref in reference.items():
    o = bpy.data.objects[name]
    m = o.data
    uv = m.uv_layers[0]
    corners = [
        [*(o.matrix_world @ m.vertices[m.loops[i].vertex_index].co), *uv.data[i].uv]
        for p in m.polygons
        for i in p.loop_indices
    ]
    expected = ref["corners"]
    res = match_corners(expected, corners)
    assert res.perfect, (name, res.cardinality, len(expected), len(corners))
    assert len(m.polygons) == ref["faces"]
    assert dict(Counter(str(len(p.vertices)) for p in m.polygons)) == ref["degrees"]
    report[name] = {
        "faces": len(m.polygons),
        "corners_checked": len(corners),
        "reference_corners": len(expected),
        "matching_cardinality": res.cardinality,
        "max_uv_error": res.max_uv_error,
        "max_position_error_m": res.max_position_error_m,
        "polygon_degrees_preserved": True,
    }

(out / "max-roundtrip-qa.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report))
