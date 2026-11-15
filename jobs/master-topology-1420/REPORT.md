# Working-master topology before export — #1420

Read-only diagnostics, 2026-11-15. No geometry repairs, scene saves, delivery replacement
or user acceptance. Rule [D308]: prefer quads, allow/report unavoidable triangles,
fail any n-gon (>4 sides) **before export triangulation**. The check does not decide
whether a particular triangle could have been avoided.

## Measured inputs and results

| Master inspected | Program | Render objects | Triangles | Quads | N-gons | Verdict |
|---|---|---:|---:|---:|---:|---|
| ELV TC downloaded non-triangulated work FBX | Max 2026.3, headless copy | 2 | 443 | 19,943 | 438 | FAIL |
| KPP1 quad-v002 `.blend` (#1372) | Blender 5.1.2, new background process | 2 | 0 | 62,091 | 0 | PASS (this check only) |
| PSU275 editable `2PSU275_VPM_NPM_quads_v001.max` | Max 2026.3, headless copy | 60 | 61,096 | 185,752 | 3,066 | FAIL |

Every inspected object, including collision, has a row with full-precision
`triangle_share` (0..1) in `elv-objects.csv`, `kpp1-objects.csv`, `psu275-objects.csv`.
ELV Main: 423 triangles / 20,303 polygons, share 0.020834359454267842;
438 n-gons. MainGlass has 20 triangles and 501 quads, no n-gons.
KPP1's four UCX meshes each have 12 triangles (share 1); PSU275's 178 UCX meshes
have 4,200 triangles in total and no n-gons. Collision is explicit in the standalone
inventory; checked render export scopes its master gate to render nodes.
PSU275 includes the complete available editable project scene (not only one building):
`SM_Psu_1_001_Main` has 2 triangles, 35,395 quads and 71 n-gons;
`SM_77_05_0009005_117_001_Main` has 2,717 triangles, 32,982 quads and 2,481 n-gons.
Its 291 native dead polygon slots are separately reported with original IDs;
they are not live polygons and are not silently counted as quads.

### Provenance and limits

- ELV: `C:/Users/artsafro/Downloads/Telegram Desktop/SM_Elevatornaya_Vl_1_A_001_work_quads.zip`,
  member `SM_Elevatornaya_Vl_1_A_001_work_quads.fbx`, SHA-256
  `a6ad1a733c07c72e7590bef96dfa2132886ad4ffbc1fba02eb2ff8dde0a80ef1`.
  The archive name does not establish a v004/v005 identity. The fresh result confirms
  the 438 n-gons noted in `jobs/elv-tc-vpm/TASK.md`; other polygon counts differ and
  are reported as measured, not relabelled as historical v004 counts.
- KPP1: `G:/Мой диск/AGR-evidence/1372-kpp1-quad-master/v002/master-quad-v002.blend`;
  whole-file hash and Blender version are in the raw `kpp1-final.json`.
- PSU275: `C:/Users/artsafro/Downloads/Telegram Desktop/working LP_2PSU275_VPM_NPM_quads_v001.7z`,
  member `2PSU275_VPM_NPM_quads_v001.max`, SHA-256
  `376ad615a272f9de02beaf85a62867352645387e41a726836e4aa36cc94e9295`.
  This is the available editable scene; no claim that it is the unavailable historical
  `jobs/PSU275/outputs/build-v002/*.blend` or a freshly accepted delivery.
- Max source copies are metre scenes, system scale 1; before/after source hashes match.
  KPP1 source hash was checked before/after by the CLI. No live Max bridge was available;
  no GUI document was opened or switched. No user scene-opening decision was needed.

## Reproduction and access

Binary copies, raw object-local n-gon IDs, dead-slot accounting, native receipts,
failed diagnostic runs and source copies are sealed outside git:
`G:/Мой диск/AGR-evidence/1420-master-topology/v001/` + `SHA256SUMS.txt`.
`evidence.json` records all 18 file hashes; copied bytes were independently checked.
Only small text/CSV and hashes are committed; no Git LFS.

Agent CLI (fresh destination required):

```bash
uv run python tools/qa/master_topology.py MASTER.blend --out NEW.json
uv run python tools/qa/master_topology.py WORK_QUADS.fbx --out NEW.json
```

Max AGR Tools Python listener (the runtime shipped by this branch):

```python
import json
print(json.dumps(agr_tools_runtime.master_topology(list(rt.selection)), indent=2))
```

Pass explicit working-master nodes, not delivered triangle FBX. Checked Max export
calls the gate on render masters before `_tri_mesh` in preview AND commit. Empty,
unsupported and partial inventories raise errors; aliases/existing reports are not
replaced. The CLI also accepts a recorded JSON list of `{name, face_degrees}` rows;
its provenance explicitly says that this is not a fresh native-scene certificate.
Blender's active Triangulate modifier is refused instead of hiding the master n-gons.
Already-applied triangulation cannot be reconstructed; supply the actual editable
master. Max's `convertToPoly` is used only on disposable evaluated copies.

Native real-input driver and slot diagnostic are preserved in the evidence directory
as `1420-native.py` / `1420-slots.py`; use copies and a new report directory when replaying.
Native synthetic witness: `tests/max_tools/run_master_topology_native.py`, run through
`dcc_batch.py max --file ABSOLUTE_SCRIPT --card t_c1559f80`: exit 0, 3/3 degree verdicts
and 3/3 unchanged selection/topology/node inventories.

## Failures retained, not hidden

1. Native PSU275 read initially hit `getFaceVerts(None)` at dead slots. The first
   dead-ID implementation assumed BitArray iteration returned IDs and failed again.
   A frozen-list native diagnostic proved pymxs returns boolean flags; enumerating
   flags preserves source IDs. The combined regression was RED then GREEN; the
   final native real-input run exited 0 and produced both actual reports.
2. The first diagnostic iterated the live `rt.geometry` collection while adding and
   deleting copies and crashed Max. Frozen-list traversal passed. A first synthetic
   `Editable_Poly()` constructor also crashed; the repository's established
   plane→Poly→delete-faces construction passed, without changing production tolerances.
3. Broad affected tests initially returned 23 failures / 2,579 passed (plus skips/xfails):
   all failures were native Git subprocess startup `3221225794` (0xC0000142), not gate
   assertions. Task-owned children were confirmed stopped; isolated rerun of the
   complete two affected failure files passed 188/188. Raw logs remain in worktree tmp.

These are master-topology results only; xView, architecture, UV/materials, all delivery
validator stages and Artem's acceptance remain independent gates.
