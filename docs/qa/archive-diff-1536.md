# Archive version-diff evidence (#1536)

## Scope and usage

`uv run python tools/qa/archive_diff.py previous.zip new.zip --expect-changed Main:uv --report diff-v002.json`

Run before showing or packing a new version; compare exported FBXs before packing,
then the actual ZIPs after packing. Repeat the declaration for each exact object and
category. Bare object names allow all of that object's changes. Unknown names/categories
are errors. Duplicate suffixes are errors even when declared. No export is repaired.

Readback is raw binary FBX 7400/7500, using the existing `twinqa.fbx_header` node/property
walker and `export_core` arrays/polygons. It avoids DCC-generated duplicate names and
preserves original object names, vertex indices and polygon topology. ZIPs are never
extracted; every member gets a hash, every FBX is read, duplicate object names across
FBXs fail. Non-FBX member changes and global metadata changes have no object exemption.
ASCII FBX, non-mesh models, animation/skin objects and unsupported mappings fail closed.
This gate is not a complete validator, SINTEZ parity, or user acceptance.

Displacements compare corresponding raw vertex indices in **file units**; bboxes are
object-local. Model properties/hierarchy are protected separately. Changed vertex counts
make displacement explicitly unmeasured, not zero. `above_tolerance_count` is strictly
above the declared tolerance; `moved_count` also includes a nonzero displacement exactly
at the threshold (conservative failure). UV changes compare complete raw layers and layer
selection, not only their presence. Reindexing can produce conservative false differences.
SHA-256 snapshots detect persistent concurrent input changes, not edits restored between
snapshots. Reports use exclusive creation and never overwrite an old report or input.
Consume the current process exit code; an old report is not a receipt for a rejected run.

## Real archived versions (read-only)

Source root: `C:/Users/artsafro/Desktop/!3D viz/Dima_Andrew/3_sreda/itog/Blender/`.
No synthetic data or DCC import was used in this run. Declared changes: **none**.

```bash
uv run python tools/qa/archive_diff.py \
  'C:/Users/artsafro/Desktop/!3D viz/Dima_Andrew/3_sreda/itog/Blender/v003/SM_Elevatornaya_Vl_1_A.zip' \
  'C:/Users/artsafro/Desktop/!3D viz/Dima_Andrew/3_sreda/itog/Blender/v004/SM_Elevatornaya_Vl_1_A.zip' \
  --report tmp/archive-diff-real-v003-v004.json
```

- Exit **1**, status **fail**; 384 objects, 431 diagnostics (including member/global changes).
- Change categories: geometry 40, UV 1, materials 2, model properties/hierarchy 384.
  These are conservative raw version differences, not 431 independently confirmed model defects.
- `SM_Elevatornaya_Vl_1_A_Main`: **374** displaced vertices; maximum **120.4359359741211** file units.
  Both versions: 77,770 vertices, 130,721 faces. Bbox max X: 44.37000274658203 → 80.6859359741211.
- Previous ZIP SHA-256: `fc05fa537b3f61c4c08827cd21d0ddf63385c8a40a09560d9c453f2448143180`.
- New ZIP SHA-256: `778ccf4511fd4a0c8e6c04923bc768aa1f567f0b0392a9767f558fe3507e643c`.
- Full JSON report SHA-256: `bfc5a10dd0092dd848bf76276dc6b5b17f1bc7abfef743e5e1016b95b6b6e0d0`.
- Full report: native artifact `archive-diff-real-v003-v004.json` on Kanban card `t_d20cc0ba`;
  generated worktree path `tmp/archive-diff-real-v003-v004.json`. No binary assets are committed.

## Regression boundary

Synthetic binary fixtures reproduce 374 X-only shifts, unintended UCX UV layers,
MainGlass/untouched-object protection, duplicate suffixes, scoped declarations, and
unchanged pairs. Generated probes move 1/2/17/373/374 vertices on each of three axes.
Additional negatives cover NaN/inf, partial readback, unknown array encodings, unmapped
slots/layers, unsupported objects, unsafe ZIP members, input aliases, racing report
hardlinks, input mutation, stale report reuse and fresh-process exit statuses.

Full suite: deferred to merge batch (rule 68). Exact affected-test receipts are in the PR.
