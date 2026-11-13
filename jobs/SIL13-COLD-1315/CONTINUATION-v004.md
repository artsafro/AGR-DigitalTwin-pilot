# #1315 — source-wide continuation v004/r3

Status: **not complete, not delivered, `passed=false`**. Cells `ground-npm` and
`ground-vpm`. The first v003/r3 geometric fragment is accepted under [D280]; this
is not acceptance of its materials, maps, technical failures or the new source-wide
candidate. Gate 1 site/composition/zero/plan/5.6 m decisions remain closed.

## New authority and source resolution

Artem delegated the remaining pilot decisions to the orchestrator:
https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1315#issuecomment-6864798809.
[D280] records that exact limited decision and the conditional lawn fallback.

**The fallback was not used.** The disputed 17.008947 m2 has actual source rubber
hatches inside transformed modelspace INSERT **33FBCCB / A$C8bceaf9b**, layer
`ГП_Резиновое покрытие`, colour **18**. Child indices 13 and 14 contribute
15.636278 and 1.372669 m2 respectively; their union covers the entire former gap,
with 0 m2 unresolved. Closed garden-border contour 33FBCAF is 608.0 m2, not a lawn
material declaration. A raw-coordinate search of block definitions alone missed
the hatches; transformed recursion was essential. The pilot's earlier lawn/rubber
lookup is historical, not the full PZU covering inventory.

Source investigation:
- Modelspace and non-inserted definitions: 46 valid raw-coordinate hatch regions
  intersecting the plot, seven invalid source rings/contours diagnosed. A separate
  2,494-INSERT definition search retained 25 diagnostic parse errors; it is not
  presented as a successful exhaustive absence test.
- Final actual-modelspace recursive hatch extraction: **244 hatch regions**,
  **24 covering rows**, **0 extraction errors**. Walls, roof/MAF hatches and other
  non-Ground layers remain in the full inventory, not silently treated as Ground.
- Source 33FBCC1 and 33FC417 self-touches were decomposed by source-edge noding and
  even-odd parity, not `buffer(0)`; newly added boundary length **0 m**. This is
  geometric interpretation, not permission to change a conflicting design.
- A flattened HATCH can omit its repeated first vertex. The initial decomposition
  therefore missed valid rings. Explicit closure, required by the HATCH entity
  contract, yielded all 24 rows and zero errors. Failed logs remain preserved.

## Actual constructed/exported/read-back result

One source master, flat first then source TIN projection, 3 m cells cut at TIN
edges. Diagnostic IDs/colours only, no material appearance claim.

| Measurement | Result / limit |
|---|---|
| Approved plot | 12,958.738864 m2, boundary 33FBCEF |
| Actual known covering union | 9,455.589905 m2; not claimed to be all required Ground |
| Known covering outside design TIN | **7.597235 m2**, excluded; no extrapolated heights |
| Source material intersection union | **7.504316 m2**, excluded; no invented precedence |
| Supported, conflict-free candidate extent | about 9,440.488354 m2; see exact summary and readback |
| Other source area without classified Ground hatch | **3,503.148960 m2**, including building/MAF regions; NOT all labelled missing paving |
| Source controls | 1,670 original controls, maximum sampled Z residual 3.437322e-10 m |
| NPM | Ground **46,614 tris**, six copied Acer **60 tris**, total **46,674**; below 180,000 for this incomplete composition only |
| VPM | Ground **46,614 tris**, six copied Acer **6,420 tris**, total **53,034**; final area band not asserted without resolved OKS footprint |
| FBX header | Binary 7400, **UnitScaleFactor=100**, unit object scale; V002 passes both profiles |
| Fresh readback | Both exported FBX: exact triangle counts, finite vertices, all triangles, one UV channel per mesh |
| Six plant controls per profile | Max sinking error 5.336909e-9 m; max height error 2.217246e-7 m; same accepted source points and seed 1315 |

Recoverable local origin is XY (783.905, 11112.780845748445), project zero 142.10 m.
This is not a delivered MSK-77/GeoJSON certificate. Per-source material roots,
excluded regions, raw bounds and full failed findings are in
`source-wide-summary-v004.json` and the external evidence.

The eight nested `ФВ-2` hatches are **25.2 m2 each** and belong to the canopy/MAF
plan, not an authoritative Ground covering assignment. Candidate OKS contour
**33FBD7A**, layer `Defpoints`, has area **3,389.939224 m2**; its layer name alone
cannot certify the official footprint operand or authorize filling the remaining
unhatched areas. No Ground was invented under those objects. No prior same-site
model, builder, transforms or result was consulted.

## Real technical failures and repair evidence

1. Unit regression exercised real Blender exports: default options fail the
   assertion with **UnitScaleFactor=1** (exit 1). `FBX_SCALE_UNITS` passes with
   **100** and an exact **2 x 2 x 2 m** readback (exit 0). Header correction is
   measured, not achieved by rescaling the site or weakening the validator.
2. Original source-wide BMesh cleanup timed out at 240 s. An instrumented revision
   reproduced the long cleanup stack and was stopped as an owned process. The
   next revision used linear-time exact float32-coordinate deduplication and
   explicit zero-area face accounting. It exported successfully. **110 zero-area
   derived faces per profile** were removed and named in the drop list; no
   nonzero-area face was silently deleted. This is not a successful topology gate.
3. Public xView on each final FBX exits **1**, `passed=false`: **465 overlapping
   faces, 4,753 overlapping vertices, 858 bow-tie vertices**. This new source-wide
   result is not the accepted pilot's historical xView 0/0. No downstream build
   step or UCX construction is declared complete after these failures.
4. Public delivery validators both exit **1**. Machine stages: NPM **1 pass /
   3 fail / 2 review / 2 not_run**; VPM **2 pass / 5 fail / 0 review / 5 not_run**.
   V002/header is fixed. Remaining findings include Ground topology counter 5,950
   and 40 zero-length edges, skirt check refusing broken face geometry, 59
   co-directional pairs below 5 mm, missing maps, VPM 8 mirrored Ground UV
   triangles, diagnostic vegetation name, and **0 UCX**. Nominal 1.001 m skirt is
   NOT claimed validated while that geometry check fails. Source-library Flora
   counters are 162 NPM / 29,240 VPM. Full raw reports are retained.

These are worker-owned technical repairs, not requests to waive a limit. New
source-authority decisions below gate the dependent full-site geometry; they do
not turn technical failures into user-owned blockers.

## Area-by-area reproduction status

| Area | Reproduced now | Value / limit / owner |
|---|---|---|
| Ground | Actual source-wide known-covering diagnostic, exported/read back in both profiles; former pink pilot gap source-resolved | 7.597235 m2 outside TIN / 0 invented heights; 7.504316 m2 source intersections / no invented precedence. Source owner chooses data treatment; worker repairs topology/UV/skirts/textures, curbs and full coverage |
| UCX | No construction yet; validator correctly fails zero hulls | Worker after resolved surface and clean overlap postcondition. VPM only, closed/convex, gap 2–10 mm, deviation <=100 mm, D012; none waived |
| MAF | All 32 schedule rows remain accounted for by v002; eight canopy footprints newly recognized in actual nested source extraction | No certified SKU-to-library match or placed MAF in this run. Missing entries stay listed, not modelled or substituted; do not claim disk-wide absence from the earlier limited lookup |
| Flora | Six original library maples retained in both profiles, with fresh numerical seating/height readback | Acer maps owned by #1316, A101 pending v002; not a question to Artem again. Other 46 point plants, 4,535 hedge plants and unresolved 133 m2 flowerbed remain unplaced; cultivar/target/atlas checks remain open |

Historical comparison remains the independent post-pilot comparison in
[PILOT-v003.md](PILOT-v003.md): #906 is an accepted different-site Ground case,
#969 is an OKS case, #1178 includes accepted Flora appearance/atlas work. This
source-wide diagnostic reaches none of their delivery/appearance acceptance by
inheritance. No readiness increase is claimed.

## Commands, integrity and evidence

Route: source-only `uv run --extra cad --with shapely` inventory, recursive
INSERT/hatch decomposition; scoped scipy/Shapely buffers; Blender **5.1.2**
`--background --factory-startup --disable-autoexec --threads 1 --python-exit-code 1`
build/readback/renders; public `dt qa xview`; public
`tools/qa/validate_package.py <actual Ground FBX> --profile <npm|vpm> --scene --json`.
No live-user DCC scene or source/library file was saved. No new shared Python
module or dependency change; job-local drivers are external hashed evidence.
No instrumented total tool-call or elapsed-time metric exists; none is invented.

External root: `G:/Мой диск/AGR-evidence/1315-cold-silikatny/v004/`.
`evidence-v004.json` indexes **60/60 byte-equal copied files**, plus SHA256SUMS.txt.
Both original/copy DWG and original/copy DOCX still match pinned source hashes:
**4/4** equal. Fresh exports, failed logs, drivers, unit regression artifacts,
source searches, readback, xView and validators are all included.

Review sheet: `review-sheet-NOT-ACCEPTED.png`, SHA-256
`0daa4db81d2859ee642affadf6d748a84d94faf087980bd880051f723f2e2d9f`.
Left is explicitly source-only; right is a native render of the actual exported
VPM FBX. Neither is a completed/accepted site. The full sheet was visually read.

Affected documentation tests: `uv run pytest -q tests/test_decisions.py
 tests/test_ground_surface_requirement_sheet.py -p no:cacheprovider
 --basetemp=C:/x/t_d9ae7dc0-v004-docs` -> **35 passed in 2.22 s**. No full suite
was run: no shared production code changed and no completed PR is being requested.
The real unit regression above is separate from these documentation tests.

## Required new data decisions (one batch, not repeated pilot questions)

1. Resolve the exact **7.597235 m2** of known coverings outside the authorized
   design TIN: provide boundary design controls, or explicitly authorize a bounded
   nearest-source-triangle linear continuation as a disclosed assumption. No
   extrapolation has been executed; existing marks/flat heights are not substitutes.
2. Resolve **7.504316 m2** of intersecting material source regions: recommend
   source AutoCAD redraw order for intersecting covering hatches (not arbitrary
   first-entry mapping), with this exception list fixed and reviewed on the full
   site image. Largest pair is pavement/lawn 6.127536 m2; Rubber18/Rubber253 is
   1.019175 m2. No such precedence has been applied yet.
3. Confirm the true OKS footprint (candidate **33FBD7A, 3,389.939224 m2**) and
   Ground treatment under the eight **25.2 m2 ФВ-2 canopy footprints**, plus the
   approximately **23.140566 m2** unhatched strip at the building. Recommend the
   source OKS footprint as an exclusion, but obtain the intended covering of the
   canopy/entry regions rather than using their roof/MAF hatch as Ground material.

Then update the full-site PartsList, rebuild and repair the resolved whole-site
surface, require xView zero contact pairs, construct/read back UCX and matching
library placements, complete atlases/validators, obtain the full-site picture
verdict and finally complete SINTEZ. Do not reopen the closed boundary, zero,
5.6 m nominal, pilot geometry or former pink wedge questions. No PR/reviewer
handoff while the construction acceptance remains incomplete.
