# TEC26 AC06 build review — 2026-10-22

Status: **built for review; NOT a passed AGR delivery**.

Source/authority and every remaining check: [BUILD_REPORT.md](../../jobs/TEC26-OKS/AC06/BUILD_REPORT.md).
Current finish legend: [MATERIALS.md](../../jobs/TEC26-OKS/AC06/MATERIALS.md).
Machine manifest: [BUILD_MANIFEST.json](../../jobs/TEC26-OKS/AC06/BUILD_MANIFEST.json).

## Versioned artifacts

Drive: `G:\Мой диск\AGR-evidence\tec26-oks\AC06\build-v006`.
SHA256 manifest: `SHA256SUMS.txt` there; tracked copy
`jobs/TEC26-OKS/AC06/DRIVE-SHA256SUMS.txt`. 143 files verified after copy.

| File | SHA256 |
|---|---|
| `package-vpm/SM_Prg_1.zip` | `dab64df8f7b906a821038c3a66544a5dee361c5dfeb0128ab11dc6df34c44182` |
| `package-vpm/SM_Prg_1/SM_Prg_1.fbx` | `197805f0cda4727758a8b491d7f9f22ca13b28cb5e00f07d688bdbbad42d2de4` |
| `package-npm/0000_Prg_1.zip` | `1b3d4a624f49c008cea56ac16949dcca1693f3da49964ae66b8c42295bc896b4` |
| `package-npm/0000_Prg_1/0000_Prg_1_01.fbx` | `7b08f0b560ed14c6cc521bf30ea76b98e825bcde827b4bcfc7bd6432551afb22` |
| `build/Prg_1_VPM_master.blend` | `a6335a5448bcad309219ac357bbe09782d908793c67f3b2a270ae9d12716bf61` |
| `audit-v006-final.json` | `a612a14de50ba27957575b581fc881a661c32c103e83e2e92be88ab9138f0476` |
| `contact-sheet.png` | `a579a70b0226889ca6afeaf0fad8c7a613ddc046bab06208940eae4cdac95d82` |

## Actual verification

- Exported ZIP FBX readback: 5596 main + 12 glass triangles in each profile;
  21 UCX / 516 triangles in VPM, none in NPM.
- Job-local source/presentation/texture audit: 104/104 measured checks pass;
  924 patterned triangles measure 999.9583–1000.0841 px/m, target 1000.
- Public xView on master/VPM/NPM: zero face pairs, vertex pairs and bowties.
- Focused tests: 34 passed. Hostile subprocess probes: 5/5; real inputs unchanged.
- Public package validator **fails**, reports retained: VPM 3 pass/3 fail/1 review/
  5 not_run; NPM 4 pass/2 fail/2 not_run. Missing GeoJSON/Ground, source topology
  findings and four source UCX intersections are NOT waived by the local audit.
- Four slide|VPM|NPM plates, flat and cavity-shaded variants. Full rib grids
  55/55/68/68 bays at nominal 0.20m; visible stroke counts are not certified.
  The grey sloping roof follows the explicit answer; slide39 discrepancy is visible.
- Regression evals: 0 passed/0 failed/10 not measured (no Claude transcript),
  receipt validated with exit0. Final full-suite output is reported in the PR.

## Still open

Artem visual acceptance (including rib layout and roof appearance), final SINTEZ
on accepted exports, source-geometry QA dispositions and complete whole-site
NPM/VPM packaging/address/GeoJSON. Code review or build audit cannot approve
these for the user. No images were labelled accepted or retouched to conceal differences.
