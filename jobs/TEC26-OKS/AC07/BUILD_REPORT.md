# TEC26 AC07 (Пункт редуцирования газа 2) — VPM + NPM build report (#564)

Recipe: AC08 pilot-v010 scripts (origin/job/tec26-oks-pilot-ac08 ed743ab, merged in cceaa17; AC08 v010 = the accepted
TEC26 visual reference, Artem 2026-10-22 «Да, похоже») + AC07 spec `vpm_textures.json`.
Command: `jobs/TEC26-OKS/scripts/run_building.sh jobs/TEC26-OKS/AC07 C:/x/tec26-oks/AC07/build-v006`, then
`render_facades.py` and `compare_slides.py` (acceptance picture: slide | VPM | NPM, same scale 100 px/m, ±0.000 aligned).
Colour authority: presentation slides 44/45 + the binding legend (MATERIALS.md, «Build legend check»).

## Result (build-v006, review round 2 + orchestrator notes 2026-10-22 17:4x)

- Rib count: decision (a) of the orchestrator (17:45) - 55 / 68 even ribs (~198 mm; 54 / 67 joints = the DWG). The
  slide is measured on its own: grid pitch 0.201 m on all 10 rows, width/pitch 54.24 / 67.16 = a partial end panel ->
  ribs = ceil(width/pitch) = 55 / 68 (`slide_rib_estimate`, rule recorded in compare.json). All 4 facades `match`, rc 0.
- Joints dark and crisp on 5015 and 7047 (`joint_dark`: 8 mm core at 0.2 x the row colour + 12 mm darkening halo,
  normal x2); a 10 mm window around a joint reads <= 0.55 of the panel (test).
- Round vents ID6: vertical cap = light disc RAL 7047, the pipe/hood faces = dark RAL 7004 (`split: vertical`).
  In the orthographic compare the hood is edge-on, so the disc shows light with only a thin dark silhouette; the
  slide's dark crescent is not painted on the disc (flat-colour placeholder; would need a per-vent disc texture).
- ID10: plinth strip -0.019..+0.132 thin RAL 7004; the drop below ±0.000 (-2.025..-0.019) = wall colour RAL 7047 plain
  (no ribs). BUILD-DROP 4/4 sides covered on BelowGrade_RAL7047.
- VPM `SM_Prg_2.zip` sha256 f5808902…; NPM `0000_Prg_2.zip` sha256 1a089733…; `SM_Prg_2_Main` 5 596 tris (= source),
  `SM_Prg_2_MainGlass` 12 tris, 21 UCX (triangulated at export), geometry/IDs unchanged, ring cuts: none.
- QA-PACKAGES PASS 102/102 (`qa_packages-r4.json`). The run_building pass itself reported 100/102: the darkening halo of
  the joint hidden by the 1-3 door (x 5.479) shows 12 mm beside the door edge and was counted as an extra line; the
  checker now takes the painted joint footprint (joint half + halo) and absorbs at most ONE run that ends at the
  occluder within it (`hidden_partial` / `clipped` / `split`, listed per row), never a free-standing line.

| Facade | Row | Slide (measured) | VPM visible (+hidden) | NPM visible (+hidden) | Status |
|---|---|---|---|---|---|
| 1-3 | grey_z=0.30 | 68 ribs (pitch 0.201 m) | 59 (+9), partial 5.479 | 60 (+9), partial 5.479, split 3.891 | match |
| 1-3 | blue_z=3.00 | 68 ribs | 66 (+1) | 66 (+1) | match |
| 3-1 | grey_z=0.30 | 68 ribs | 62 (+5) | 62 (+5) | match |
| 3-1 | blue_z=3.00 | 68 ribs | 66 (+1) | 66 (+1) | match |
| А-Д | grey / blue / roof | 55 / 55 / 55 ribs | 54 / 54 / 54 | 54 / 54 / 54 | match |
| Д-А | grey / blue / roof | 55 / 55 / 55 ribs | 54 / 54 / 54 | 54 / 54 / 54 | match |

## Evidence

- Local: `C:/x/tec26-oks/AC07/build-v006/` (compare `compare-r3/`, renders, packages, `qa_packages-r4.json`), log
  `build-v006.log`.
- Drive: `G:/Мой диск/AGR-evidence/tec26-oks/AC07/build-v006/` (22 files + `SHA256SUMS.txt`, re-checked after copy;
  copy of the list: `build-v006-DRIVE-SHA256SUMS.txt`).

## Open

- Vents: the dark crescent of the slide circles is not painted (see above).
- VPM glass in the preview renders is transparent, NPM glass opaque light grey (unchanged from v005).

Not sent to Artem by this card; the reviewer/orchestrator forwards the compare sheets.

## Previous result (build-v005)

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

