# Lab experiment L02: `scene.missing_maps` (missing maps)

This page reports how the GeoAGR 13.64 source behaved in 3ds Max 2024.2.1. It ran in the AGR Lab runner on synthetic
scenes on 04.11.2026; all texture files were synthetic and lived in the job's output folder. There is no GeoAGR code
here, only `GeoAGR.ms:<line>` references (rule #853). Evidence is in GeoAGR-private, branch `lab-exp/L02`,
`work/lab-experiments/scene.missing_maps/`.

- **Plan row:** `docs/plans/agr-tools-suite.json`, block `scene`, version 0.8, verdict `take_fix`.
- **GeoAGR source:** Project Map (`GeoAGR.ms:15548-16065`), its row helper `GeoAGR.ms:6314`, and the relink-candidate
  helper `GeoAGR.ms:1383` / `:855`.
- **Third-party "Collect Asset":** not in any repository, so it was **not available**.

## Measured
Runner jobs:
- `20261104-230541-09f07075` failed before any GeoAGR code ran, because my script used the reserved word `collect`.
- `20261104-230809-ded80b60` and `20261104-231034-b3fa027e` produced the measurements below.

**Project Map cannot list missing maps.** It builds its rows from `usedMaps`, and `usedMaps` returns nothing for a file
that does not exist. As a result, a material with a missing map shows an empty texture cell, which looks the same as a
material without maps. The AssetManager does list the missing paths. Two more list problems:
- `UCX_` objects appear in the first list, but Refresh drops them.
- Hidden objects are excluded.

**Relink candidate.** The source searches the scene assets for a file with the same base name and takes the first one
that exists (`GeoAGR.ms:1383`).
- When the missing map had a same-name file elsewhere in the scene, the candidate was found and relinked.
- When two candidates existed (another folder, another extension), one was chosen silently, with no ambiguity reported.

**Collect Selected to Path writes to disk and is fragile:**
- With no candidate it throws `Unable to convert: OK to type: FileName` (`GeoAGR.ms:15725`) and stops.
- In a two-row run, the second row's file had already been copied when the exception happened, but the scene still
  pointed at the missing path. Disk and scene were left inconsistent.
- If a different file with the same name was already in the project folder, it was deleted and replaced without a
  prompt.
- It renames bitmap nodes by default.
- The default project folder in an untitled scene is the relative path `Maps\`.

**Apply renames texture files on disk.** Preview + Apply renamed the object, the material and the file on disk
(`T_ok_d_1.png` → `T_okR_d_1.png`).

## Recommendation: `take_fix`
Only one idea is worth taking: search for candidates by base name. The list itself and the collect/rename actions should
not be taken. The new tool is read-only:
- Enumerate all bitmap-like maps through class instances and the AssetManager. UDIM `<UDIM>` tokens are expanded per
  tile.
- Check each path with `doesFileExist`.
- Report owner objects and materials, the path, `exists`, ranked candidates (same name and extension first) and an
  ambiguity flag.
- Include hidden and `UCX_` objects with a flag.
- Write JSON and a table.
- Do not copy, delete, rename or relink anything.

## Requirements the tool must meet
- NPM-2.1-1.b and VPM-2.4-2 (from the plan row `reqs`): textures of the delivery model must exist and match their names.
- Evidence from TEC26: the KPP folder had no ERM, and the railing texture was 4096 instead of 2048
  (`jobs/TEC26-OKS/STATE.md`). The report should therefore also give the resolution of the existing files.

## Minimal acceptance test (proposal)
The synthetic scene contains:
- one existing map;
- one missing map with no candidate;
- one missing map with one same-name candidate in another folder;
- one missing map with two candidates (`.png` in another folder and `.tga`);
- a hidden object and a `UCX_` object with missing maps;
- a material without maps;
- a UDIM bitmap with one of three tiles missing.

Expected results:
1. Every missing path is reported, including the hidden, UCX and UDIM-tile cases. The material without maps is not
   reported as missing.
2. The candidates are ranked, and the two-candidate case is flagged as ambiguous.
3. The files on disk, the scene file names, the node names and the undo stack are byte- and name-identical before and
   after the run.
4. The JSON lists each map once per path, with its owners, and the existing ones have a resolution.
