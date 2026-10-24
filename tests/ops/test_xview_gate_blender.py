"""#527 `dt qa xview` through headless Blender (opt-in: -m blender).

Synthetic: a .blend with the review #514 rail/soffit case placed at site coordinates (synthetic geometry).
TOW02: the review #514 inputs when they exist on this PC (git-ignored job outputs; set DT_TOW02_OUTPUTS).
Pattern: none | new-case: Blender tests of the overlap gate (#527).
"""
import json
import os
import subprocess
from pathlib import Path

import pytest

from dt_ai.cli.main import main
from dt_ai.core.blender_runner import blender_executable

pytestmark = pytest.mark.blender

MAKE_BLEND = r'''
import sys, bpy
out = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
def obj(name, verts, faces, loc):
    me = bpy.data.meshes.new(name); me.from_pydata(verts, [], faces); me.update()
    o = bpy.data.objects.new(name, me); o.location = loc; bpy.context.scene.collection.objects.link(o)
e = 0.012
obj("rail", [(0,0,0),(0,2,0),(2,2,0),(2,0,0),(-3.37+e,0.5,0.005),(-3.37+e,0.565,0.005),(e,0.565,0.005),(e,0.5,0.005)],
    [(0,1,2,3),(4,5,6,7)], (2201234.5, 412345.5, 152.25))
obj("clean", [(0,0,0),(1,0,0),(1,1,0),(0,1,0)], [(0,1,2,3)], (0, 0, 0))
bpy.data.objects.new("empty", None)
bpy.context.scene.collection.objects.link(bpy.data.objects["empty"])
bpy.ops.wm.save_as_mainfile(filepath=out)
'''


def test_blend_parts_local_at_site_coordinates(tmp_path, capsys):
    script = tmp_path / "make.py"
    script.write_text(MAKE_BLEND, encoding="utf-8")
    blend = tmp_path / "site.blend"
    subprocess.run([blender_executable(), "-b", "--factory-startup", "--python-exit-code", "1", "--python",
                    str(script), "--", str(blend)], check=True, capture_output=True, timeout=300)
    out = tmp_path / "r.json"
    code = main(["qa", "xview", str(blend), "--out", str(out)])
    rep = json.loads(out.read_text(encoding="utf-8"))
    assert code == 1 and [p["part"] for p in rep["parts"]] == ["clean", "rail"]
    rail = rep["parts"][1]
    assert rail["location"] == [2201234.5, 412345.5, 152.25] and rail["overlapping_faces"] == 2
    assert rep["parts"][0]["passed"] is True
    assert rep["input"]["dropped"] == [{"name": "empty", "type": "EMPTY", "reason": "not a mesh object"}]
    assert not list(tmp_path.glob("r.json.dump-*")) and not list(tmp_path.glob("*.partial"))
    out2 = tmp_path / "r2.json"
    assert main(["qa", "xview", str(blend), "--parts", "clean", "--out", str(out2)]) == 0


MAKE_SCALED = r'''
import sys, bpy
out, s = sys.argv[sys.argv.index("--") + 1], float(sys.argv[-1])
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system = "METRIC"
bpy.context.scene.unit_settings.scale_length = s
def obj(name, verts, faces, loc):
    me = bpy.data.meshes.new(name); me.from_pydata([tuple(c / s for c in v) for v in verts], [], faces); me.update()
    o = bpy.data.objects.new(name, me); o.location = tuple(c / s for c in loc)
    bpy.context.scene.collection.objects.link(o)
# nested parallel squares 3 mm apart (physical metres), off origin (float32 location exact at both scales)
obj("sq", [(0,0,0),(1,0,0),(1,1,0),(0,1,0),(0.25,0.25,0.003),(0.75,0.25,0.003),(0.75,0.75,0.003),(0.25,0.75,0.003)],
    [(0,1,2,3),(4,5,6,7)], (1234.5, 345.5, 152.25))
obj("clean", [(0,0,0),(1,0,0),(1,1,0),(0,1,0)], [(0,1,2,3)], (0, 0, 0))
bpy.ops.wm.save_as_mainfile(filepath=out)
'''


@pytest.mark.parametrize("scale", [1.0, 0.001])
def test_blend_scale_length_gives_same_physical_verdict(tmp_path, scale):
    """Review #541 P1-1: scale_length 0.001 (side 1000 / gap 3 BU) = scale_length 1 (side 1 / gap 0.003)."""
    script = tmp_path / "make.py"
    script.write_text(MAKE_SCALED, encoding="utf-8")
    blend = tmp_path / "scaled.blend"
    subprocess.run([blender_executable(), "-b", "--factory-startup", "--python-exit-code", "1", "--python",
                    str(script), "--", str(blend), str(scale)], check=True, capture_output=True, timeout=300)
    out = tmp_path / "r.json"
    assert main(["qa", "xview", str(blend), "--out", str(tmp_path / "." / "r.json")]) == 1
    rep = json.loads(out.read_text(encoding="utf-8"))
    assert rep["input"]["units"] == {"unit_system": "METRIC", "unit_scale": scale, "coordinates": "m"}
    sq = {p["part"]: p for p in rep["parts"]}["sq"]
    assert sq["overlapping_faces"] == 2 and rep["parts"][0]["passed"] is True
    assert max(abs(a - b) for a, b in zip(sq["location"], (1234.5, 345.5, 152.25))) < 1e-3
    assert sorted(x.name for x in tmp_path.iterdir()) == ["make.py", "r.json", "r.json.blender.log", "scaled.blend"]


TOW02 = Path(os.environ.get("DT_TOW02_OUTPUTS",
                            Path.home() / ".AGR-DigitalTwin_pilot/jobs/vyatskaya-tow02/outputs"))
OURS = TOW02 / "export-v005" / "SM_Vyatskaya_Vl_47_49_013_Main.fbx"
USER = TOW02 / "review-v002" / "xview" / "user_copy" / "0213_Vyatskaya_Vl_47_49_05.fbx"


@pytest.mark.skipif(not OURS.is_file(), reason="TOW02 export-v005 not on this PC")
def test_tow02_ours_v005_185_faces_0_vertices(tmp_path):
    out = tmp_path / "ours.json"
    assert main(["qa", "xview", str(OURS), "--out", str(out)]) == 1
    t = json.loads(out.read_text(encoding="utf-8"))["totals"]
    assert t["overlapping_faces"] == 185 and t["vertex_pairs"] == 0 and t["overlapping_vertices"] == 0


@pytest.mark.skipif(not USER.is_file(), reason="TOW02 user FBX _05 not on this PC")
@pytest.mark.parametrize("coords", ["local", "inplace"])
def test_tow02_user_05_0_faces_10_vertices(tmp_path, coords):
    out = tmp_path / "user.json"
    main(["qa", "xview", str(USER), "--parts", "SM_Vyatskaya_Vl_47_49_013_Main", "--coords", coords,
          "--out", str(out)])
    t = json.loads(out.read_text(encoding="utf-8"))["totals"]
    assert t["overlapping_faces"] == 0 and t["overlapping_vertices"] == 10 and t["vertex_pairs"] == 5
    assert t["bowtie_pairs"] == 5
