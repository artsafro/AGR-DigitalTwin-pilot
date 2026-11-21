# sokolniki-uvk1000 - #1784 building by the lattice method

Step 1 (lines sheet before building): openings list from the Revit FBX by the shared step
`tools/methods/body/revit_fbx_dump_blender.py` (Blender 4.4; 5.1.2 crashes on this FBX) ->
`tools/methods/body/openings_from_revit_fbx.py` with `openings_config.json` (this job's only file) -> lines by the
#1736 core `plan_adapter_dwg.lines_from_facades` + `lines_sheet.render` (PR #1770 head 8279609f, read-only).

```
blender44 -b --factory-startup --python tools/methods/body/revit_fbx_dump_blender.py -- C:/x/sokolniki-npm/intake/oks/src_copy/sokolniki_ar_r23_v1.fbx C:/x/ev_1784/sok_dump.json
uv run python tools/methods/body/openings_from_revit_fbx.py C:/x/ev_1784/sok_dump.json jobs/sokolniki-uvk1000/openings_config.json C:/x/ev_1784/sok_open_d.json
```

Result: 8 593 objects -> 59 facade lines (46 with elements), 1 644 objects in the openings spec, 184 exterior walls,
1 231 insets (rooftop cage, mesh fence, canopies, roofs, fins), 5 534 dropped with reasons. Global levels 47 (all
opening edges, snap 0.10 m). Evidence: `G:/Мой диск/AGR-evidence/1784-sokolniki-lattice/step1/` + `SHA256SUMS.txt`.
Status: step-1 sheet waits for Artem's OK; nothing built. Night session `C:/x/sokolniki-npm/` is read-only.
