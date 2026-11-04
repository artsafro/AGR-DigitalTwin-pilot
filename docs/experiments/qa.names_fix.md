# Lab experiment L03: `qa.names_fix` (AGR Tools 0.8)

Source check before the button enters AGR Tools (`docs/plans/agr-tools-suite.json`, row `qa.names_fix`, verdict `merge`).
Executed 04.11.2026 through the AGR Lab runner (3ds Max 2024 batch), GeoAGR 13.64 Personal runtime, synthetic scene
(`synthetic_*` objects, PhysicalMaterial with three bitmaps) and synthetic files. No GeoAGR code here, only
`GeoAGR.ms:<line>` references (rule #853). Evidence: GeoAGR-private branch `lab-exp/L03`, `work/lab-experiments/qa.names_fix/`.

Job: `20261104-230842-38aeaa99`.

## Sources
| Source | Status |
|---|---|
| GeoAGR Material Cloner (`GeoAGR.ms:55620-55769`) | run live |
| Telegram `AlexYo_AGR_renamerV2.ms` (V13), `A101AGRLP.ms` naming UI | **not available** in any repository (the "A101 extra underscore (:388)" note cannot be checked) |

## Behaviour of the GeoAGR source (measured)
Material Cloner is not a renamer of objects. For each target whose name has `_NNN_` it clones the donor's material, renames
the material and its bitmaps from the donor index to the target index, copies the texture files under the new index and
repoints the maps.
- Object names: never changed. Works on the live scene, not on export copies.
- Index detection: first `_NNN_` (3 digits) in the name; names without it are skipped (Listener only).
- Target's own material: **replaced** without notice.
- Clones are independent (maps not shared with the donor); the donor is unchanged.
- Existing destination file: **kept** (no overwrite). The plan note "Material Cloner overwrites files" is not reproduced.
- The index is replaced in the **whole path**: a folder named `_001_` becomes `_002_`, the copy fails, but the map is
  still repointed to the non-existent file.
- Missing donor file: map still repointed to a non-existent `_NNN_` file.
- Reporting: Listener lines only; final "Done!" does not mention failures. In batch mode the messageBoxes are not shown.

## Requirements the AGR Tools button must meet
Row reqs: NPM-2.10-3.3.a, NPM-2.10-3.4.a, VPM-2.11-0.a, VPM-2.10-4.3 (`adapters/max/agr_tools/README.md`: SM/T/M masks,
OKS 001..020, SlotNumber; `T_…_{Diffuse,ERM,Normal}_{Slot}.{UDIM}`).
- Work on export copies only; rename objects, materials and map files by the NPM/VPM masks (one renamer replacing three).
- Index/mask substitution only in the file name, never in folder names.
- Copy files without overwriting; repoint a map only if its file exists afterwards; list every failure in the result.
- Never silently replace a material that a target already has; report it.

## Minimal acceptance test (proposal)
Synthetic copy scene: donor `SM_Test_001_Main` with D/ERM/N bitmaps (one in a folder named `_001_`, one missing), targets
`_002_`, `_003_` (destination file already exists), no-index object, object with its own material. Pass if: names of all
objects/materials/maps match the masks; donor scene untouched; existing `_003_` file md5 unchanged; no map points to a
missing file; folder names unchanged; the result lists the skipped object, the missing file and the replaced material.
