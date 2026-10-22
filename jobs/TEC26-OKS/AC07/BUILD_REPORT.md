# TEC26 AC07 (Пункт редуцирования газа 2) — VPM + NPM build report (#564)

Recipe: AC08 pilot scripts (PR #574 snapshot, commit e2d07da) + AC07 spec `vpm_textures.json`.
Command: `jobs/TEC26-OKS/scripts/run_building.sh jobs/TEC26-OKS/AC07 C:/x/tec26-oks/AC07/build-v005`, then
`render_facades.py` and `compare_slides.py` (acceptance picture: slide | VPM | NPM, same scale 100 px/m, ±0.000 aligned).
Colour authority: presentation slides 44/45 + the binding legend (MATERIALS.md, «Build legend check»).

## Result (build-v005)

- VPM `SM_Prg_2.zip` sha256 aac8af96…; NPM `0000_Prg_2.zip` sha256 c1d04ed1…; `SM_Prg_2_Main` 5 596 tris (= source),
  `SM_Prg_2_MainGlass` 12 tris, 21 UCX (triangulated at export), geometry/IDs unchanged, ring cuts: none needed.
- Faces per finish: {"PanelVJ68": 147, "PanelVJ55": 238, "Roof_RAL5015": 96, "Trim_RAL5015": 671, "Metal_RAL7004": 796, "Insert_RAL7004": 200, "Door_RAL7004": 120, "Frame_RAL9016": 534, "Plinth_RAL7004": 88, "Interior": 64}.
- QA-PACKAGES PASS 102/102 (`qa_packages.json`), QA-MASTER in `build/qa_master.json`.
- Joints measured on the rendered pixels (never the spec value), visible + hidden by doors/windows:

| Facade | Row | Slide raster (dark runs, informative) | VPM | NPM | Contract |
|---|---|---|---|---|---|
| 1-3 | grey_z=0.30 | 62 | 58 (+9) | 58 (+9) | 67 joints OK |
| 1-3 | blue_z=3.00 | 68 | 66 (+1) | 66 (+1) | 67 joints OK |
| 3-1 | grey_z=0.30 | 71 | 62 (+5) | 62 (+5) | 67 joints OK |
| 3-1 | blue_z=3.00 | 67 | 66 (+1) | 66 (+1) | 67 joints OK |
| А-Д | grey_z=0.30 | 57 | 54 (+0) | 54 (+0) | 54 joints OK |
| А-Д | blue_z=3.00 | 56 | 54 (+0) | 54 (+0) | 54 joints OK |
| А-Д | roof_z=3.65 | 54 | 54 (+0) | 54 (+0) | 54 joints OK |
| Д-А | grey_z=0.30 | 56 | 54 (+0) | 54 (+0) | 54 joints OK |
| Д-А | blue_z=3.00 | 54 | 54 (+0) | 54 (+0) | 54 joints OK |
| Д-А | roof_z=3.65 | 53 | 54 (+0) | 54 (+0) | 54 joints OK |

Slide raster counts include dimension lines, labels and the wall outline; the contract is the sheet (67 / 54 joints
every 200 mm) and the slide roof rows (54 / 53 runs) confirm the roof step = the wall step.

## Evidence

- Local: `C:/x/tec26-oks/AC07/build-v005/` (+ `SHA256SUMS.txt`), log `build-v005.log`.
- Drive: `G:/Мой диск/AGR-evidence/tec26-oks/AC07/build-v005/` (compare PNGs, renders, packages, QA, `SHA256SUMS.txt`, 20 files, hashes re-read after copy).

## Questions for Artem

1. Round vents (ID6): the slide draws them as light circles with a dark inner shadow; the build paints them RAL 7004.
   Keep 7004 or light grey 7047?
2. Roof: the slide supersedes the Gate-1 «ID1 кровля 7004» - roof is now ribbed RAL 5015 down the slope at the wall
   step (54 joints). Confirm.
3. VPM glass in the preview renders is transparent (the room behind shows through); NPM glass is opaque light grey. OK?

Not sent to Artem by this card; the reviewer/orchestrator forwards the compare sheets.
