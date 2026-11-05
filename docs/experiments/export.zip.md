# Lab experiment L04: `export.zip` (AGR Tools 0.8)

Date 2026-11-04. Lab round L04 (TOOL-FOUNDRY step 3: check a button's sources in Max before it enters AGR Tools).
All data synthetic. No GeoAGR code is reproduced here (rule #853); references are `GeoAGR.ms:<line>` of GeoAGR 13.64.
Full evidence (job scripts, logs, VERDICT.json): GeoAGR-private branch `lab-exp/L04`, `work/lab-experiments/export.zip/`.

## Sources checked
- GeoAGR "Archivate All" (`File.btn_archivate`, GeoAGR.ms:66229-66472): run in 3ds Max 2024 batch through the AGR Lab
  runner, job `20261104-230505-a889c432`.
- Telegram AGR Zipper v2.1: **not available** (not in any repository; only the audit `docs/research/team-scripts-audit.md`).

## Findings (measured unless marked static)
1. The bundled archiver cannot create ZIPs: 7-Zip Console 23.01 without its codec library returns "Unsupported archive
   type", exit 2. No archive is produced; the handler reports only by file existence and never reads the exit code.
2. A VPM OKS archive would miss its `_Light` FBX (GeoAGR.ms:66307: the extra-FBX filter can never match). The Ground VPM
   archive does include `_Ground_Light.fbx`.
3. Members are chosen by substring: `SM_X_001` also takes `SM_X_0011.fbx` and its textures; every `_00N` name takes the
   `_00` branch (GeoAGR.ms:66292-66305).
4. All NPM FBX of the folder go into one archive regardless of address; the last `_Ground` file gives the name
   (GeoAGR.ms:66246-66253); the list file `zip.txt` stays in the delivery folder after an NPM-only run.
5. Static: Ground VPM archive limited to 500 MiB (standard: 1 GiB) and exactly 500 MiB fails (GeoAGR.ms:66340); NPM limit
   1 GiB is right; units are binary (D015). No name checks at all.
6. The pilot validator (`qa.package`) flags the compositions of findings 3 and 4 (V001 "FBX set", V012 "FBX names"),
   but cannot see finding 2 (`_Light` is optional in a VPM ZIP).

Verdict: GeoAGR source **broken**; recommendation **merge** — write the archiver anew, do not port the handler.

## Requirements the tool must meet
NPM-2.1-1.a, VPM-2.1-1.a, VPM-2.1-1.b, VPM-2.1-2.b (plan row). Standards: `standards/NPM_STANDARD.yaml` `archive`
(zip, ≤ 1 GiB, 2..21 FBX, Ground required, `{code4}_{Address}.zip`), `standards/VPM_STANDARD.yaml` `archive`
(one archive per OKS and per Ground; OKS ≤ 500 MiB, Ground ≤ 1 GiB; fbx + geojson + PNG, optional `_Light` FBX), D015.

## Proposed behaviour
- In-process ZIP writer (no external exe), new output path, never update an existing archive, no temp files left.
- Member lists from exact name grammar, per address: NPM `{code4}_{Address}_{01..20}.fbx` + `_Ground.fbx`; VPM
  `SM_{Address}[_NNN].fbx` (+ `_Light.fbx`, `.geojson`, `T_{Address}[_NNN]_*`), `SM_{Address}_Ground*` likewise.
- Refuse mixed addresses/codes; report sizes with `<=` binary limits; run `qa.package` on every archive written.

## Minimal acceptance test
Synthetic folder with NPM (2 parts + Ground), VPM OKS (fbx, `_Light`, geojson, 3 PNG), VPM Ground (same) and decoys
(`SM_X_0011.*`, `0123_Other_01.fbx`, `notes.txt`). Expected: exactly 3 archives `0123_X.zip`, `SM_X.zip`, `SM_X_Ground.zip`;
`SM_X.zip` contains `SM_X_Light.fbx` and no `_0011` member; decoys untouched and reported; a second run refuses to
overwrite; `qa.package` V001/V012 pass on all three; a 500 MiB+1 B OKS archive and a 1 GiB+1 B Ground archive are flagged.
