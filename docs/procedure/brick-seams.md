# Brick/panel course-grid calculation (#1510)

Scope: VPM-OKS agent calculation only. No live DCC calls or automatic source cuts.
`agr brick-seams --config CONFIG.json --out NEW.json` delegates to
`tools/materials/brick_seams.py`, then `adapters/max/agr_tools/seams_core.py`.
All calculation/command dependencies are stdlib; `python -S` is tested. The existing
chart and fold cores are reused, not reimplemented. `course_grid_cut` re-exports the
same page assembler, and the earlier page CLI calls it directly.

## JSON contract

Required keys (unknown/missing keys refuse):

- `schema`: `brick-seams/1`; `mode`: `mesh` or `pages`.
- `course_height_m`, `panel_step_m`, `repeat_m`: finite positive metres. A full
  appearance repeat must contain whole course/panel periods (arithmetic tolerance
  1e-9 periods); never rescale to force fit. `course_panel` contains physical
  `[horizontal / panel_step_m, vertical / course_height_m]` coordinates per corner.
- `texel_px_m`: 512–1706; `tile_px`: 2048 or 4096; `tile_budget`: explicit 1–10
  sequential tiles starting at 1001. No automatic budget increase.
- `data`: mode-specific payload, **or** `inputs`: hash-bound file-role references
  `{role: {"path": "file.json", "sha256": "64 lowercase hex characters"}}`.
  Relative input references resolve against the config's parent; CLI config/output
  paths remain relative to the caller's working directory.

`mesh` data: `rows` (object, source face index, source vertex indices, XYZ metres),
`seam_edges` (explicit permissions in `course_grid_chart.build_chart` format),
`z0_m`, `border_px` (>0), `udim_tile` (within the explicit budget). File role:
`mesh` containing this complete data object. The core finds complete vertical
shared edges, builds a common chart and folds by whole repeats. Chart conflicts,
invalid topology, nonfinite coordinates and overflow refuse without output.
Selection/finish authority belongs to the caller; there is no automatic material
selection, opening detection or bevel inference. Partial-edge contacts are not
certified by the chart core.

`pages` data/file roles: `partitions`, `brick_fold`, `placements`, following the
existing `course_grid_pages` structures. Each partition names its source and
explicit chart/XYZ pieces; each support patch must have exactly one mapped
placement/member within budget. Plain brick pieces use the explicitly enumerated
fold translations. Source footprints and support translations must already be
approved: the command neither guesses them nor treats a nominal panel grid as
permission to cut geometry. Unknown/missing members, duplicate sources/pieces,
cross-tile pieces and dropped/unplaced input refuse.

Output is one `brick-seams-result/1` envelope: input hashes, plan and explicit
`passed=false`. Exit 0 means **calculated**, not QA passed. No bitmap texture or
native model is produced by this command. The output must be new, distinct from
all inputs (including hardlinks), and its `.partial` name must be unused. Hashes
are checked before and after calculation and immediately before publication;
this is a bounded snapshot check, not a filesystem lock against arbitrary future
source edits. Windows uses no-replace rename; POSIX uses exclusive hardlink
publication. A previous output is preserved on refusal, never promoted to a new
success; callers must check this invocation's exit and config hash.

## Exercised evidence

Root: `G:/Мой диск/AGR-evidence/1510-brick-seams/` (binary evidence outside Git).
`run-v003` contains both configs, input JSON, result envelopes, independent
readbacks, before/after **offline UV wireframe renders**, and `shared-layout.json`.
These are not native/lit renders or user visual acceptance.

- Real #1326: replay of the approved v150 source-support partitions/placements,
  **771 sources / 1,671 pieces / 803 supports**, tiles **1001/1002**, UV delta **0**
  (limit 1e-12), XYZ delta **0 m**, exact source/joint/patch/tile correspondence.
  This is placement replay, not automatic reconstruction of the pilot's entire
  source classification, protected finalizer or native QA. Nominal course height
  is 3.15/38 m; `panel_step_m=repeat_m` is the full-repeat diagnostic grid, while
  the actual irregular panel joints remain the explicit source supports.
- The final `run-v003/shared-layout.json` is byte-identical to the layout baked
  in `run-v002`; SHA256:
  `447cbea9b59357a9c59c17cf71542ffebe6f00550c3d1be3c2016ae2749e3e49`.
  Separate replay through the existing `course_grid_bake` with NumPy/Pillow/
  SciPy/Shapely exited 0: **6/6 PNG files byte-identical** to #1326 v180 (which
  matches the accepted-stage maps). It consumed the new shared-core layout,
  not the original layout file. See `run-v002/bake`, `bake-config.json` and seal.
- Second object: explicitly **synthetic** four-wall ring, 1 m sides, .25 m
  courses, .5 m panel step, tile 1001, 512 px/m. Independent UV inversion verifies
  all eight source vertices' heights, all four wall widths and continuity at
  four vertical edges; maximum course residual **0**. Not a real building or a
  second approved material/delivery.
- Generated probe: seed 1510, 150 translated rings; 150/150 retain inputs,
  four faces, single-tile containment and continuous course phase.
- Failed `run-v001` is preserved: DriveFS rejects hardlinks (WinError 1); the
  Windows no-replace rename repair has regression coverage and ran on DriveFS.

Re-run a config only into a new output path:

```bash
uv run agr brick-seams --config "G:/Мой диск/AGR-evidence/1510-brick-seams/run-v003/1326-config.json" --out "NEW.json"
uv run --with scipy python -m tools.materials.course_grid_bake --config "G:/Мой диск/AGR-evidence/1510-brick-seams/run-v002/bake-config.json" --output "NEW_DIRECTORY"
```

The sealed `replay_1510.py` records input reconstruction and independent readback;
run it with a new absolute directory using this repository's uv environment.
Small readbacks and full file hashes are in `docs/research/brick-seams-1510/`.

## Not done (explicit NOW scope)

- AGR Tools stage-6 button and plugin packaging/installation.
- Any live or fresh native Max run/readback and native one-UDIM acceptance.
- Automatic reconstruction of arbitrary panel/bevel supports; bitmap generation
  for the synthetic object; arbitrary library texture selection.
- NPM conversion, atlas-path decisions, final #1326 package acceptance, replication
  and user visual acceptance. The original source-stair xView baseline remains
  unchanged. No global `passed=true` is claimed.

Full suite: deferred to merge batch (rule 68).
