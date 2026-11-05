# Lab experiment L04: `qa.package` (AGR Tools 0.8)

Date 2026-11-04. Synthetic ZIPs plus FBX exported by GeoAGR Export LowPoly in the lab (job `20261104-230509-4d1b73d0`).
Evidence and scripts: GeoAGR-private branch `lab-exp/L04`, `work/lab-experiments/qa.package/`.

## Sources checked
- This repo's `tools/qa/validate_package.py` at `4e275ca1`: 22 ZIPs on the host (no DCC) and `--scene` readback on 3 ZIPs in
  a Blender 5.1 runner slot (host job `20261104-231040-ba8bdeb4`).
- Telegram AGR Checker / AGR Zipper: **not available** (archives deliberately not committed).
- GeoAGR has no equivalent button; its LowPoly rules check only reads ZIP size (GeoAGR.ms:9937).

## Findings
1. Works as documented: duplicate members, `..`/backslash paths, non-ZIP, nested folders, missing Ground, FBX 7500,
   wrong part names, mixed addresses, A101 `__Ground`, unexpected FBX in a VPM set, RGBA ERM/Normal are all failed;
   binary size limits are exact at the boundary (limit passes, limit+1 fails) for NPM 1 GiB, VPM OKS 500 MiB, Ground 1 GiB.
2. `--scene` readback works in the lab Blender slot and adds what the ZIP alone cannot show: GeoAGR FBX are not
   triangulated (V003), Flora in an OKS FBX and a wrongly derived address fail V012 mesh names.
3. Defect: without `--profile` the profile is guessed from content; an NPM archive `0127_X.zip` with a stray PNG is judged
   as VPM, and the report talks about a missing `SM_` main FBX instead of the foreign file.
4. Defect: V006 "embedded textures: all embedded" passes on FBX that contain no texture at all (vacuous pass).
5. Environment: the validator needs `shapely`; it does not import on the lab's system Python 3.11.
6. Not detectable from the ZIP: a VPM OKS archive without its `_Light` FBX (optional by standard) — the archiver must
   guarantee it (see `export.zip.md`).

Verdict: **as-documented**; recommendation **merge** (this validator is the button's engine; Telegram checkers add nothing
measurable now).

## Requirements
NPM-2.1-1.a, NPM-2.1-1.b, VPM-2.1-1.a, VPM-2.1-1.b, VPM-2.1-2.a, VPM-2.1-2.c, VPM-2.1-2.d (plan row);
`standards/DELIVERY_VALIDATOR.yaml` stages V001-V017; D015 binary units.

## Minimal acceptance test
The 22-case set of `make_and_validate.py` (GeoAGR-private evidence) as a pytest fixture, plus:
`0127_X.zip` with a stray PNG and no `--profile` → NPM profile, V001 "foreign files: preview.png";
NPM FBX without any embedded texture → V006 not pass; button runs `--scene` by default and reports exit 0/1/2 with the
stage table.
