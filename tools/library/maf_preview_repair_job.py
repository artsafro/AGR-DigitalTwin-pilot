"""Repair blank MAF audit previews without changing source/exported geometry (#183).

New case: Scanline cannot show some legacy library materials. Render a neutral
shape-only preview from each saved per-MAF Max file, writing preview-v002 and a
separate JSONL. Original material-bearing .max/FBX/preview files are read-only.
Run through dcc_batch.py max; AGR_MAF_LIB and AGR_MAF_BLANK select the library
and a JSON list of IDs confirmed blank by test_real_maf_library_artifacts.
"""
import json
import os
import time
from pathlib import Path

import pymxs

rt = pymxs.runtime
lib = Path(os.environ.get("AGR_MAF_LIB", "C:/x/t_3e6ff1b3/library"))
blank_path = os.environ.get("AGR_MAF_BLANK", "C:/x/t_3e6ff1b3/blank_previews.json")
blank = set(json.loads(Path(blank_path).read_text(encoding="utf-8")))
rows = {}
for line in (lib / "built.jsonl").read_text(encoding="utf-8").splitlines():
    row = json.loads(line)
    rows[row["id"]] = row
outdir = lib / "preview-v002"
outdir.mkdir(exist_ok=True)
manifest = lib / "preview-v002.jsonl"
if manifest.exists():
    raise RuntimeError("versioned preview manifest already exists: " + str(manifest))
rt.execute(r'''
fn agrNeutralPreview n pngPath = (
    local bb = nodeGetBoundingBox n (matrix3 1)
    local ctr = (bb[1] + bb[2]) / 2.0
    local r = amax 0.001 ((length (bb[2] - bb[1])) / 2.0)
    local dir = normalize [1, -1.2, 0.8]
    local cam = Freecamera fov:40.0
    cam.transform = matrixFromNormal dir
    cam.pos = ctr + dir * (r / (sin 20.0) * 1.05)
    cam.dir = dir
    cam.clipManually = false
    local bmp = render camera:cam outputSize:[256,256] vfb:false quiet:true outputfile:pngPath
    if bmp != undefined do close bmp
    delete cam
)
''')
t0 = time.time()
with manifest.open("x", encoding="utf-8") as output:
    for key in sorted(blank):
        row = rows[key].copy()
        if not rt.loadMaxFile(row["max_path"], quiet=True, useFileUnits=True):
            raise RuntimeError("cannot read library file " + row["max_path"])
        nodes = list(rt.geometry)
        if len(nodes) != 1:
            raise RuntimeError("expected exactly one MAF in " + row["max_path"])
        node = nodes[0]
        rt.renderers.current = rt.Default_Scanline_Renderer()
        rt.backgroundColor = rt.color(205, 205, 205)
        node.renderable = True
        node.material = rt.StandardMaterial(diffuse=rt.color(80, 110, 140), twoSided=True)
        path = (outdir / (Path(row["max_path"]).stem + ".png")).as_posix()
        if Path(path).exists():
            raise RuntimeError("refusing preview overwrite " + path)
        rt.agrNeutralPreview(node, path)
        if not Path(path).is_file():
            raise RuntimeError("render missing " + path)
        row.update(preview_path=path, preview_style="neutral-shape-only",
                   preview_original_path=row["preview_path"])
        output.write(json.dumps(row, ensure_ascii=False) + "\n")
        output.flush()
print("AGR_PREVIEW_REPAIR count=%d seconds=%.1f max_version=%s" %
      (len(blank), time.time() - t0, rt.maxVersion()))
