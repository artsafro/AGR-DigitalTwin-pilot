# AGR Tools 0.4.0 — Checked export

Synthetic fixtures only. One button runs the existing gates on export copies,
then writes one FBX and reads it back. No production scene, no NPM/VPM package,
no new thresholds, no GeoAGR code.

Binaries and FBX stay out of the repo:

`G:/Мой диск/AGR-evidence/731-agr-tools-checked-export/`

The same files are also under `C:/x/731-evidence/` (the path Max `fileIn`s).

## Build

Two fresh builds of the package the native runner installed. SHA256
`c3b6f810ea1014e1e98efa433e0b36a218e9d6e6797845380ff5151c40426865`
(`AGR-Tools-0.4.0-r6.mzp` and `AGR-Tools-0.4.0-r6b.mzp`, 237554 bytes, identical).
Builder stdout is `build.txt`. The listener line `AGR_PACKAGE_SHA256` is the
hash of the file `fileIn` installed, and it equals this receipt.

## Headless install

Max 2024, Python 3.10: wrapper status `ok`, native exit **0**, 79.7 s.
Log: `max2024-native-log.txt`. Max `fileIn` needs an ASCII path, so the runner
wrote `C:/x/731-evidence/max2024-r6`.

Max 2026 was not re-run this round. `max2026-native-log.txt` is the previous
package and its hash is not this receipt.

```
AGR_PACKAGE_SHA256 c3b6f810ea1014e1e98efa433e0b36a218e9d6e6797845380ff5151c40426865
AGR_TOOLS_REGISTERED version=0.4.0 category=AGR Tools macros=XView,Cleanup,MatID,Open,Nudge,NudgeApply,Atlas,AtlasApply,Ucx,UcxApply,Texel,Export
AGR_REVIEW_731 names=exact ucx_dirty=1 offenders=1 cleanup_first=1 stale_move=1 probes=4
AGR_REVIEW_R3 missing_material=1 udim_no_texel=1 xview_no_texel=1 ucx_no_texel=1
AGR_NATIVE_EXPORT clean=1 gates=cleanup,matid,xview,ucx
AGR_NATIVE_COMPLETE clean=3 planted=3 dry_run_unchanged=true originals_unchanged=true
```

xView thresholds stay 0.002 m / 0.005 m. The 0.1.0–0.3.0 native checks in the
same runner still passed (`AGR_NATIVE_UCX_TEXEL`, `AGR_REVIEW_R1`,
`AGR_REVIEW_R2`).

## Per-gate fixtures

`checked-export/` contains the clean FBX, the exact-name probes
(`SM_probe_0`..`3`, `SM_control`, `SM_body` + `UCX_SM_body_01`) and their
reports. Planted gates, the dirty UCX hull, the clean-plus-dirty pair, the
cleanup-before-missing-material cases, the moved stale preview, and the
round-3 refusals (`missing-material`, `bad-matid-no-texel`, `xview-no-texel`,
`ucx-no-texel`) wrote no FBX, no report and no `.partial`. Readback names are `synthetic_export_clean`,
`SM_control`, `SM_body` and `UCX_SM_body_01` with no `001`/`002` suffix.

| Gate | Planted defect | Stopped | Commit | File written |
|---|---|---|---|---|
| cleanup | map channel 2 and `note=planted` | `cleanup` | `gate failed: cleanup` | no |
| matid | face material id 1001 | `matid` | `gate failed: matid` | no |
| xview | two triangles 1 mm apart | `xview` | `gate failed: xview` | no |
| ucx | two intersecting `UCX_SM_Addr_Main_*` boxes | `ucx` | `gate failed: ucx` | no |
| matid | `SM_missing_material`: UV-clean quad, valid face ids, material undefined, VPM/brick texel UDPs | `matid`, finding `missing_material` names that node and its evaluated faces | `gate failed: matid`, no throw | no |
| matid | `SM_bad_matid_missing_texel`: brick, face MatID 1001, UDP exactly `MapChannel:1 = UV` | `matid`, finding `udim_id` with those face ids; texel not run | `gate failed: matid`, no throw | no |
| xview | `SM_xview_no_texel`: triangles 1 mm apart, no texel metadata | `xview` | `gate failed: xview`, no throw | no |
| ucx | `SM_ucx_no_texel` plus intersecting hulls, texel profile `nope` | `ucx` | `gate failed: ucx`, no throw | no |
| clean | one UV quad, VPM, brick=1024 | none | pass | `clean.fbx` |

Dry-run of the clean quad left the directory empty and the source snapshot
unchanged. After commit the source snapshot was still unchanged.

The macro `AGRToolsExport` ran on the clean node after the FBX already
existed. That press is a new dry-run of the same selection, so the report
status is `fail` with `existing_target` and the existing FBX is left in
place. That is the export JSON line in the listener.

## Readback

| Host | Dry-run objects | triangles | materials | unit scale | axis | Written FBX readback |
|---|---|---|---|---|---|---|
| Max 2024 clean | 1 | 2 | 1 | 100.0 | Z-up | 1 / 2 / 1 / 100.0 / Z-up, name `synthetic_export_clean` |
| Max 2024 `SM_body` + `UCX_SM_body_01` | 2 | 14 | 1 | 100.0 | Z-up | names `SM_body`, `UCX_SM_body_01` |

Units `m`. FBX binary 7.4 (`UnitScaleFactor` 100).

## Rollout text

From `adapters/max/agr_tools/README.md`:

```
[Checked export]
```

```
First rollout complete: xView, pre-export clean-up, MatID, UV integer-tile
nudge, UDIM to NPM atlas, UCX collision, texel readout and checked export.
```
