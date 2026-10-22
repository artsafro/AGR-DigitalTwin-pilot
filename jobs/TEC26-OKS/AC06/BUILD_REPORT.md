# TEC26 AC06 — operational delivery build-v014

Completed per the operator's 2026-10-22 18:4x instruction: no new unit tests,
full suite, reviewer round or diagnostic evidence bundle. Final files:
`G:/Мой диск/AGR-evidence/tec26-oks/AC06/build-v014/` — two ZIP packages and
four `compare-*.png` plates;6/6 copies byte-verified. Only the mandatory basic
Drive checksum list accompanies those six files.

The NPM2048 atlas is now derived from the actual VPM Diffuse UDIM pixels,
with joint-preserving reduction, NOT a separately regenerated pattern.
RAL5015 blue sandwich and7047 light-grey sandwich follow own slides39/40;
facade-visible roof edge blue;7004 doors/plinth,9016 frames. Geometry/UCX/IDs
pipeline unchanged. All four actual image counts match; all eight blue/grey
contrast comparisons meet or exceed the slide.

| Facade | Ribs slide / VPM / NPM |
|---|---|
| A-D | 55 / 55 / 55 |
| D-A | 54 / 54 / 54 |
| 1-3 | 67 / 67 / 67 |
| 3-1 | 68 / 68 / 68 |

The south NPM image splits ONE joint into two strokes3px apart; measurement
counts one fitted grid position and retains both fragment coordinates, not an
extra rib. The next physical joint is about40px away. No missing ribs are filled.

This is an operational building deliverable, not a whole-site AGR/SINTEZ pass.
No formal v014 unit/full-suite result or Artem AC06 visual acceptance is invented.

## Historical v013 technical snapshot below

All v013 audit counts, NPM32mm generation notes and old comparison metrics below
are historical, NOT measurements of the v014 atlas. Use the final plates above.

### Historical heading: TEC26 AC06 — final build-v013 review packet

**Status: built for review, NOT a passed AGR delivery.** Current visual reference:
AC08 v010 (`ed743ab`, PR574; Artem «Да, похоже»). That approval is for AC08,
not an invented AC06 acceptance. Latest AC06 operator instructions supersede the
v006 grey projected roof band and nominal-width rib estimates.

## Inputs / scope

- Starting main: `442f0b695a91f9abc180783c26978fbe85fefcf9`; no AC06 build there.
- Named parents merged into this feature branch: AC08 pilot through `ed743ab`
  and approved AC06 Gate-1 (#571). No shared scripts/checkers/standards edited.
- Own presentation slide39 (A–D, D–A) and slide40 (1–3, 3–1) are primary.
  Their exact image SHA256 values are in `vpm_textures.json` and comparison receipt.
  Source DWG/PDF copies and hashes remain in `materials.json.inputs`.
- Source scene read-only Max2026.3/metres, layer006: main handle170, glass378,
  21 collision candidates. The copied source scene was never saved or edited.
- Current material legend/regions: [MATERIALS.md](MATERIALS.md),
  `materials.json.production_build`. Historical Gate-1 `build_allowed=false`
  is retained as the old packet's scope marker, not a prohibition on this BUILD card.

## Executed build and readback

`PX_PER_M=200 bash jobs/TEC26-OKS/AC06/run_build.sh C:/x/tec26-oks/AC06/build-v013`
completed exit0. The runner uses AC08 v010's fixed-scale/camera recipe, preserves
separate map-free glass and runs the actual pixel comparison gate BEFORE
`AC06-BUILD-OK`. A mismatch or insufficient joint contrast returns nonzero.
Blender5.1.2 headless; fresh-process FBX readback from BOTH exported ZIPs.

- Master main: all3118 source vertices /2954 source polygons; same source IDs
  stored in `srcid`. Both FBXs:5596 main +12 glass triangles.
- Glass retains all24 vertices/6 source polygons; map-free, alpha0.5.
- VPM retains21 UCX /516 triangles; NPM has main+glass and no UCX.
- No weld, vertex movement, hull rebuild, ring cut or silhouette change.
  Source-corner cap triangulation is the explicitly requested export representation.
  Every polygon's directed boundary, positive projected triangle area and source
  corners are covered; no dropped/unmapped object or polygon.
- Facade-visible ID1 roof-edge surfaces are BLUE as the slide:157 blue polygons,
  24 non-visible7004 polygons. The source sloped surfaces themselves form the
  projected upper band; they are not left grey or hidden behind fake geometry.
- ID2:177 blue ribbed canopy/fascia faces,494 plain blue trim/snow-guard faces.
  ID3:ALL300 wall polygons ribbed7047. Thin plinth above zero remains7004;
  below-zero drop remains PLAIN7047 on ID10 to−2.0251m. Source visible plinth
  is0.1325m above zero versus the sheet's+0.120; geometry was not retuned.
- VPM:13 sequential UDIM triplets (8 full4096 patterned tiles,5 plain256 tiles).
  NPM:ONE2048 RGB diffuse atlas +separate2048 RGB `_o_`, embedded; no normal map.
- **1068/1068** patterned triangles measure **999.9583–1000.0742px/m**
  (target1000±1%);0 UV overflow. All5596 exported main triangles in EACH
  profile have the correct presentation finish (0 wrong finishes).
- Building-specific audit: **104/104 measured checks pass**.
  Public xView on master/VPM/NPM:0 face pairs,0 overlapping vertices,0 bowties;
  each exit0. CLI local default profile is NPM; raw per-profile mesh checks remain.

## Final acceptance pictures — measured pixels, not declared counts

Only `compare/compare-{A-D,D-A,1-3,3-1}.png` are the final review pictures.
Source|VPM|NPM at200px/m, aligned at±0.000, clipped at the slide's−0.200 ground.
Pixels outside the render are padded WHITE, not fake black outlines. Full raw
renders/iso retain the actual below-grade geometry. No source/model retouching.

The adapted AC08 v010 counter measures actual regular vertical strokes over
the blue field in each final panel. It retains all candidates, excluded
annotation/window/pipe outliers and exact source/control ROIs. It never copies
an expected rib number into a render caption. Asymmetric counts are intentional:
each facade's pitch = measured field width / its own measured slide ribs.

ΔY is Rec709 sRGB luma, column-profile P50−P05; grey patches are explicit in JSON.

| Facade | Ribs slide / VPM / NPM | Blue ΔY slide / VPM / NPM | Grey ΔY slide / VPM / NPM |
|---|---|---|---|
| A-D | 55 / 55 / 55 | 72.29 / 98.66 / 95.30 | 147.60 / 207.21 / 196.13 |
| D-A | 54 / 54 / 54 | 74.32 / 98.66 / 94.87 | 146.70 / 201.08 / 192.14 |
| 1-3 | 67 / 67 / 67 | 70.27 / 98.66 / 95.24 | 152.00 / 207.28 / 198.50 |
| 3-1 | 68 / 68 / 68 | 70.42 / 98.66 / 95.30 | 149.00 / 207.72 / 194.49 |

**4/4 count matches;8/8 colour/profile contrast comparisons ≥slide.**
The same approved panel noise is recoloured to KPP5015 and7047. Latest crisp-line
instruction overrides old8mm ink: VPM20mm and NPM32mm preserve a dark centre at
comparison/atlas scale. No horizontal panel joints; the actual field border
is outlined. Doors are7004, frames/reveals9016. No AC08 rib count was imported.

## Public full-delivery validator — still NOT passed

Actual final v012 `tools/qa/validate_package.py <zip> --profile <vpm|npm>
--json --scene` runs exit1. Raw reports are on Drive:
VPM3 pass /3 fail /1 review /5 not_run; NPM4 pass /2 fail /0 review /2 not_run.

- V001: missing VPM GeoJSON/address; NPM is a one-building ZIP without the
  mandatory whole-site Ground FBX. This is not a complete site delivery.
- V004:6992 duplicates/self-intersections plus a projected-clearance review.
  This metric is NOT the xView contact-pair count above. No threshold was changed
  or a failed finding converted into a pass. Geometry remains the approved source.
- V010:4 source UCX piece intersections (2.2/3.8mm). Source geometry/collision
  repair is explicitly outside the colour-only authorization; no silent repair.
- Temporary `Prg_1`/`0000`, manual AC06 visual approval and final SINTEZ remain open.
  No final publication-ready or whole-delivery `passed=true` is claimed.

Shared AC08 QA remains raw72/98 pass,26 fail: no-glass naming, equality of UCX
polygon counts despite triangulation, old one-finish-per-ID and density assumptions.
The AC06 audit names every inapplicable check and supplies independent stricter
source-bound proofs. All other raw checks remain active. Its schema requires
ALL98 raw keys, literal boolean statuses and a matching failure summary; empty,
partial or truthy-string evidence cannot pass. Raw reports were not edited green.

## Tests, hostile review and history

- Current focused regressions: **42 passed**, including historical Gate-1 cases.
- Observed REDs precede region/map/audit implementation, ID2/canopy coverage,
  UCX004 fan selection, strict raw status schema, crisp contrast/blue roof edge,
  pixel counter, opposite-facade counts and white out-of-bounds padding.
- Actual v009 comparison failed3–1 (67 versus68 measured after final resampling);
  the south recipe was separated from north, not a caption or checker weakened.
  v010/v011/v012 match all4. Earlier v006 nominal55/55/68/68 is historical only.
- UCX004 BEAUTY cap residual14.59µm exceeded the unchanged10µm supporting-plane
  bound. Another original-corner fan passes; concave negative controls still fail.
- Final hostile fresh-process probes: **5/5**. Declared raw false stays failure;
  truthy `fail` and empty checks refused; output/input hardlink and existing
  report/`.partial` sentinels preserve bytes. Duplicate/reversed/missing triangle,
  NaN/inf, exact20µm corner-boundary, duplicate-handle and input-change regressions
  fail closed. Actual input hashes remain unchanged.
- Source/destination hashes are verified; before/after snapshot checks do NOT
  claim detection of a hostile change restored between snapshots.
- Non-final full-suite attempts were explicitly stopped/discarded for author
  snapshot changes and new operator steering; no completed success claimed for
  them. Owned native children were checked absent before restarting. The final
  frozen full-suite command/counts are recorded in the PR, not invented here.
- Regression evals:0 passed /0 failed /10 not measured (no Claude transcript),
  receipt validation exit0. No fabricated telemetry or pytest-count substitution.

## Artifacts / continuation

`G:/Мой диск/AGR-evidence/tec26-oks/AC06/build-v013/` with `SHA256SUMS.txt`;
tracked current pointers: `BUILD_MANIFEST.json`, `DRIVE-SHA256SUMS.txt`.
Contains both ZIPs/FBXs, master, maps, source slides,12 swatches,4 final plates,
readbacks, raw public failures, audit, pixel comparison receipts and reproducers.
Binaries stay off git/LFS. Earlier diagnostic versions remain immutable on Drive;
7 verbose v002 git JSON copies were removed only after byte-identical Drive checks.

Next: independent code/material review and Artem's final AC06 picture acceptance;
final SINTEZ after that. Do not erase source QA failures or pretend a single
building is the whole-site AGR package. No further per-step questions are needed.
