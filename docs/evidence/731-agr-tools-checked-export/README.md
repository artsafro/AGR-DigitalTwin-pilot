# AGR Tools 0.4.0 — Checked export

Synthetic fixtures only. One button runs the existing gates on export copies,
then writes one FBX and reads it back. No production scene, no NPM/VPM package,
no new thresholds, no GeoAGR code.

Binaries and FBX stay out of the repo:

`G:/Мой диск/AGR-evidence/731-agr-tools-checked-export/`

The same files are also under `C:/x/731-evidence/` (the path Max `fileIn`s).

## Build

Two fresh builds of the package the native runner installed. SHA256
`536753134c7031ae33228d0d8a6d5b4fdf6674a7a09877d158c6b70bd17cea71`
(`AGR-Tools-0.4.0-e.mzp` and `AGR-Tools-0.4.0-f.mzp`, 234135 bytes, identical).
Builder stdout is `build.txt`. The listener line `AGR_PACKAGE_SHA256` is the
hash of the file `fileIn` installed, and it equals this receipt.

## Headless install

Max 2024, Python 3.10: wrapper status `ok`, native exit **0**, 51.4 s.
Log: `max2024-native-log.txt`. Output directory
`C:/x/731-evidence/max2024-r3`.

Max 2026.3 (28.3.0.30732), Python 3.11: wrapper status `ok`, 50.8 s.
3ds Max itself exited **4294967166** because of the pre-existing
`polyunwrapper_autoload.mse` CLR startup error (recorded as a dcc_batch
warning, not a fixture failure). The runner reached `AGR_NATIVE_COMPLETE`.
Log: `max2026-native-log.txt`. Output directory
`C:/x/731-evidence/max2026`.

Both logs:

```
AGR_PACKAGE_SHA256 536753134c7031ae33228d0d8a6d5b4fdf6674a7a09877d158c6b70bd17cea71
AGR_TOOLS_REGISTERED version=0.4.0 category=AGR Tools macros=XView,Cleanup,MatID,Open,Nudge,NudgeApply,Atlas,AtlasApply,Ucx,UcxApply,Texel,Export
AGR_NATIVE_EXPORT clean=1 gates=cleanup,matid,xview,ucx
AGR_NATIVE_COMPLETE clean=3 planted=3 dry_run_unchanged=true originals_unchanged=true
```

xView thresholds stay 0.002 m / 0.005 m. The 0.1.0–0.3.0 native checks in the
same runner still passed (`AGR_NATIVE_UCX_TEXEL`, `AGR_REVIEW_R1`,
`AGR_REVIEW_R2`).

## Per-gate fixtures

`checked-export/` in each output directory contains only `clean.fbx` and
`clean.report.json`. The planted gates wrote no FBX, no report and no
`.partial`.

| Gate | Planted defect | Stopped | Commit | File written |
|---|---|---|---|---|
| cleanup | map channel 2 and `note=planted` | `cleanup` | `gate failed: cleanup` | no |
| matid | face material id 1001 | `matid` | `gate failed: matid` | no |
| xview | two triangles 1 mm apart | `xview` | `gate failed: xview` | no |
| ucx | two intersecting `UCX_SM_Addr_Main_*` boxes | `ucx` | `gate failed: ucx` | no |
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
| Max 2024 | 1 | 2 | 1 | 100.0 | Z-up | 1 / 2 / 1 / 100.0 / Z-up, error null |
| Max 2026 | 1 | 2 | 1 | 100.0 | Z-up | 1 / 2 / 1 / 100.0 / Z-up, error null |

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
