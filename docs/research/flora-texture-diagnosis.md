# Flora texture diagnosis (#369)

- Причина: UV всех 99 объектов сохранили, но назначили карты с другой компоновкой; дефект виден на шести видах, light его наследует.
- Решение Артёма 20:27 применено: исходные дефекты/ограничения перечислены отдельно, порог 80% не снижен, исходники не правились.
- Контроли проходят: липа ВПМ 664/664, боярышник ВПМ 264/264, спирея NPM 10/10 островов; у 74/99 исходников есть отдельные замечания.
- Для 99/99 выданы рекомендации: 24 восстановить атлас, 12 сначала исправить исходные UV, 2 уточнить области, 7 развернуть звезду, 54 перестроить NPM.
- Диагностика готова к ревью, не приёмка ассетов: шесть листов и все маршруты в HTML; отдельное исправление — #411, опубликованные файлы неизменны.

## Final decision and calibration (v006)

Artem accepted the source-limitation recommendation on **2026-10-20**, recorded in
Kanban `t_49156f66` at **20:27**, handed to this worker at 20:46. This resolves the
blanket-all-originals calibration blocker, not the source defects themselves.
[D155](../decisions.md) and the [Flora sheet](../domain/areas/flora.md#geometric-sprite-coverage-d155)
record the scope: **calibrate on valid originals; list and route failing originals as
source defects/limitations; do not lower 80% or modify any original**.

The new offline finalizer consumes the existing v005 metrics and native inventory.
It verifies their SHA-256 against the saved measurement provenance, 201 exact face
ledgers and 99 unique source/library pairs plus 3 light records. It does not recompute
or relabel raw scores, masks, roles or `pass` fields. The historical all-originals
raw gate remains **failed**; the independent control-calibration gate is **passed**:

| Original control | Passing / total charts | Result |
|---|---:|---|
| `Tilia_cordata_VPM` | 664/664 | Pass, including reviewed bark containment |
| `Crataegus_mollis_VPM` | 264/264 | Pass |
| `Spiraea_japonica_NPM` | 10/10 | Pass, whole-plant-plane control |
| Total | 938/938 | Control calibration only, not asset acceptance |

The Padus counterexample remains a **source geometric failure**, not an exception:
`Padus_maackii_VPM`, intact 8-triangle chart (faces 182–185, 298–301), covers
**67.5942243645%** of the single branch-sprite bbox `[488,2403,1803,3845]` in
`T_cheryomuha_maakha_d_1.png`, with **29,353 opaque pixels outside** at 1px tolerance,
and no neighbouring opaque sprites. The atlas/witness was visually inspected in the
preceding run; the red outline visibly excludes the right-hand leaves. See
`padus-original-sprite-crop-v002.png/json` beside the review index. No new DCC run.

## All 99 repair recommendations

Final here means **a named diagnostic recommendation for every object**, not a
validated repair or source-quality certification. The manifest is generated from
measured per-chart evidence and independent NPM plane checks, never by eye:
[`final-routes-v006.json`](../../experiments/flora-texture-diagnosis/final-routes-v006.json).
Full per-island source issue lists, exact faces, scores, clipping and reasons are in
`C:/x/review/2026-10-20/flora-texture-diagnosis/final-routes-v006/routes.json`.
Each route still requires post-repair visual validation. No repair was executed.

| Recommendation | Objects | Why / chosen follow-up |
|---|---:|---|
| `restore_or_bake_original_atlas` | 24 | VPM raw source rows clean: restore original component atlas correspondence; if packaging requires species maps, bake equivalent component maps under retained UVs, not whole-plant photos |
| `repair_source_uv_then_restore_or_bake_atlas` | 12 | VPM measured sprite/containment failures: explicitly repair source correspondence on a new copy before restoring/baking; Padus belongs here |
| `resolve_source_atlas_region_then_restore_or_bake` | 2 | VPM missing/ambiguous region measurement: resolve the named limitation first; do not invent a map or certify a physical defect |
| `remap_star_to_whole_plant_image` | 7 | NPM candidate stars: map each plane to the whole-plant diffuse/opacity image, then validate crossing geometry and silhouette |
| `rebuild_whole_plant_star_and_uv` | 54 | NPM construction not certified as a whole-plant star: rebuild/verify star geometry and UVs for the approved image rather than merely rebind component-card UVs |
| Total | **99** | Disjoint, unique named objects; **no source_validation_required catch-all** |

The 99 comprise **38 VPM / 61 NPM** objects. 25 originals have all raw chart rows
passing; **74** contain a failure or limitation. Their issue ledger distinguishes
**5,537 measured geometric failures** from **3,074 applicability/measurement
limitations** (8,611 rows total; categories describe chart diagnostics, not 8,611
independently confirmed bad plants). Non-star NPM parts, unclassified atlas regions,
missing metric support and non-finite scores remain limitations, never forced passes.
A failed candidate cell is not proof of bad authoring: touching sprites and inferred
cells require source review in #411. The 457 unscored source charts remain recorded;
**zero unknown geometry roles does not mean zero unmeasured metrics**.

### Selected species routes

| Species / ID | NPM recommendation (source issues / charts) | VPM recommendation (source issues / charts) |
|---|---|---|
| Tilia / 101 | Rebuild whole-plant star + UV (132/141) | Restore/bake component atlas (0/664) |
| Betula / 102 | Rebuild whole-plant star + UV (42/57) | No catalogue VPM counterpart in this measured pair set |
| Crataegus mollis / 103 | Rebuild whole-plant star + UV (34/38); light inherits incompatibility | Restore/bake component atlas (0/264) |
| Amelanchier / 105 | Rebuild whole-plant star + UV (214/701), FLORIO source; light inherits it | Repair source UV failures, then restore/bake (1110/2964), Union source |
| Cornus sericea / 204 | Rebuild/verify whole-plant star + UV (11/11); bent authored cards are not full-height flat planes under this diagnostic; light inherits crop | No catalogue VPM counterpart in this measured pair set |
| Spiraea japonica / 225 | Remap star to whole-plant image (0/10 original; replacement 10/10 failed) | Restore/bake component atlas (0/20) |

NPM plane checks retain candidate count, normal-Z, opacity enable and UV extent.
The 12-plane cap / normal-Z tolerance 0.02 are diagnostic heuristics, not user
thresholds; common-centre crossing is **not certified**. A conservative rebuild
recommendation means verify/rebuild in the follow-up, not that every authored NPM
is physically invalid. No global affine UV transform repairs all component atlases.

## Geometric recalibration [D155]

- VPM discrete sprite: polygon-union intersection / independent opaque-sprite bbox,
  0.80–0.95; >0.95 allowed only without neighbouring opaque pixels inside the island.
- Continuous bark: >=95% island raster area on reviewed bark pixels, not coverage of
  the whole strip. Tilia island 166 passes **8,557/8,597 = 99.5347214144%**; the
  superseded whole-strip score was **0.2444722245%**. V wrapping is permitted by
  policy, but multi-tile unsupported measurements remain limitations in the ledger.
- NPM whole-image planes: >=80% plant-region coverage, transparent margin allowed,
  no clipped opaque pixels (1px tolerance). Raw bbox/island ratio and intersection
  ratio remain visible. The prototype raw 0.80–0.95 target is not certified for all
  margin cases; the finalizer never turns those rows into passes.
- Alpha threshold >=128; native bitmap dimensions; geometric polygon area is not
  opaque density. Scores and distributions are beside `geometry-diagnostics-v005/index.html`.

### Masks and evidence boundary

The six coloured sheets include original / library / light masks and UV overlays.
Empty is opacity <128; foliage/bark RGB classes are **candidate displays**, with
purple unknown opaque pixels, not independently validated semantic ground truth.
The 23 reviewed source bark-region annotations (24 rectangles) are stored separately
in `reviewed-bark-regions-v002.json`; containment uses those reviewed regions, not a
brown-colour fallback. Generated whole-plant replacement maps have no reviewed
component-bark layout; their trunk scores are not certified semantic passes.

Accordingly **asset_accepted=false**, **semantic_masks_certified=false**. This is a
completed diagnostic with explicit source/measurement limitations and repair routes,
not an L2 semantic acceptance checker. Independent semantic certification of all
atlas cells and corrected assets belongs to the proposed repair's acceptance, not
a claim made by these heuristic diagnostic masks. The user decision permits reporting
source limitations rather than requiring every original to pass; it does not approve
bad texturing, candidate masks or repaired assets.

## Reproduction and final checks

```bash
uv run python tools/flora/finalize_texture_diagnosis.py \
  --metrics C:/x/review/2026-10-20/flora-texture-diagnosis/geometry-diagnostics-v005/metrics.json \
  --inventory C:/Users/artsafro/AppData/Local/Temp/agr-3dsmax-t_49156f66/inventory-all-v005.json \
  --provenance C:/x/review/2026-10-20/flora-texture-diagnosis/geometry-diagnostics-v005/provenance.json \
  --output <fresh versioned review subdirectory>
```

`final-routes-v006/index.html` links the six previously viewed v005 sheets; root
`index.html` and the exactly-one `#369` queue entry point to the final routes.
No render/map pixels were changed. The 51 controlled renders / 14 overlays, native
slot/gamma controls and 201 measured records are retained. Source integrity was
rechecked this continuation: **236/236 protected hashes unchanged**.

New regression RED: **17 failed**, tests-first commit `f3072e5` (finalizer absent).
GREEN: **29 finalizer tests passed**; **155 affected tests passed** in the final combined run,
including independent control-score/boundary checks and fresh-process positive CLI, changed/stale inputs,
duplicate JSON keys, failed/unknown/review/non-finite controls, incomplete/duplicate
records and face ledgers, direct/relative/hardlink aliases. No failed original is
mutated into a pass. Focused suite/eval receipts are recorded in the PR.
The earlier full suite below is retained per rule 49; it was not rerun.

Historical iteration details, not current blockers:
[geometry decomposition](../experiments/flora-geometry-decomposition.md),
[bark containment](../experiments/flora-bark-containment.md),
`raw-diagnostics-v004-summary.json` and `geometry-diagnostics-v005-summary.json`.
Geometry decomposition reduced 27,947 UV-index components to 17,332 edge-continuous
charts, 16,323 unknown geometry roles to zero, preserving 201/201 face ledgers.
Three-run median legacy 1.086303s / prototype 2.372741s: **2.18424x slower**, not a speedup.
Roles derive from 3D normals/manifold boundaries, never convenient UV/pixel labels.

## Evidence and scope

Review entry: `C:/x/review/2026-10-20/flora-texture-diagnosis/index.html`.
Sheets: `101.png`, `102.png`, `103.png`, `105.png`, `204.png`, `225.png`.
Each contains front, 45-degree azimuth and top renders of original / v003 / light where available,
then the two diffuse/UV overlays. All six final sheets were opened with `vision_analyze`, not inferred
from file names. Supplemental Union #105 VPM renders and overlays are linked below the six sheets.
Machine evidence lives beside the HTML: `inventory.json`, `affected-objects.json`, `summary.json`,
`render-receipts.json`, `source-integrity.json`, `native-texture-controls.json`.

Native renderer: **3ds Max 2026.3, headless, Default Scanline Renderer**, via `dcc_batch.py max` only.
Live Max 2024 responded with `safeMode=true`; library reads followed the documented headless audit route
in `model-flora` / coordination rule 27. No live scene was loaded, held, saved or changed. No Blender ran.
Scenes/maps/FBX were copied to `%LOCALAPPDATA%/Temp/agr-3dsmax-t_49156f66/` before inspection.
The source scenes and all 236 protected input files have equal before/after SHA-256 hashes.

This is a diagnosis, not asset acceptance, a botanical review or a fix. Approved generated map pixels
are not declared wrong botanically: their **layout is incompatible with the retained source UVs**.

## Original objects and actual bindings

All rows below were matched uniquely by source object name. Inventory matching covers all 99 objects:
68 source counterparts in Union and 31 in FLORIO; zero unmatched/ambiguous rows. The material names and
paths are read from the scenes, not guessed from the species name.

| ID / species | Original object / material | Original diffuse bitmap | Opacity source |
|---|---|---|---|
| 101 Tilia cordata | `Lipa_melkolistnaya_HP` / `Lipa_melkolistnaya` | `T_77_17_0150309_6155_D_7_Ground_Diffuse_1.1030.png` | Alpha of that same PNG, separate Bitmap node |
| 102 Betula pendula | `Bereza_LP` / `Bereza` | `Maps_Bereza_01.png` | Alpha of that same PNG |
| 103 Crataegus mollis | `Boyaryshnik_LP` / `Boyaryshnik_myagkovatyy` | `Maps_Boyaryshhnyak_01.png` | Alpha of that same PNG |
| 105 Amelanchier lamarckii, NPM | `_irga_lamarka_t1_h150_low` / `_low_atlas_flora_2BT_1` | `_low_atlas_flora_2BT_1_d.png` | Separate `_low_atlas_flora_2BT_1_o.png`, intensity |
| 204 Cornus sericea | `Deren_otprysk_LP` / `Deren_otpryskovyy` | `T_Deren_otpryskovyy_01.png` | Alpha of that same PNG |
| 225 Spiraea japonica | `SpireyaYaponskya_LP` / `M_Flora_d` | `T_77_07_0004008_95_K_6_Flora_d_1_borrzhieub3f.png` | Separate `T_77_07_0004008_95_K_6_Flora_o_1_h9e57j2t3qvh.png`, intensity |

**#105 provenance matters:** its NPM catalogue source is FLORIO, not Union. Its actual source atlases
were found alongside `FLORIO_2BT_2022.max` (not in a `maps/` child), then copied. Comparing Union's
larger VPM mesh as if it were the NPM source would be misleading. Union does contain
`Irga_Lamarka_HP` / `Irga_Lamarka`, bound to `T_Irga_Lamarka_01.png` for diffuse and alpha.
That exact object and its v003 VPM counterpart were also rendered in all three views and overlaid;
the supplementary comparison likewise shows the lost trunk and chopped crown.

Our six bindings resolve to `C:/x/flora-library/v001/maps/<species-slug>/diffuse-v001.png` and
`opacity-v001.png`; the three light FBX retain those same bindings. There is no unresolved generated
map in the tested six. Resolving a file path (#312) is not a UV-layout conversion.

## Per-species diagnosis from pictures

`U/V` below are actual channel-1 bounds, identical in original and v003. They are not inferred crop boxes.

| Species | Original layout and UV coverage | v003 defect visible in final sheet | Light FBX |
|---|---|---|---|
| Tilia | Two branch cards on left + bark on right; U 0.05956–0.97240, V 0.03630–0.97527 | Bark islands now point into white/right edge of whole-tree map: trunk disappears. Branch cards sample cropped whole-tree regions, giving overlapping hard-edged foliage panels. | Not available |
| Betula | Branch patches left, birch bark strip right; U 0.10432–0.92906, V 0.03835–0.95452 | Bark islands miss the replacement's central trunk; disconnected rectangular/triangular crown fragments replace the original fine-leaved silhouette. | Not available |
| Crataegus | Small branch patch plus tall narrow bark strip; U 0.20259–0.88569, V 0.09142–0.73502 | Old bark UVs land right of the replacement trunk; stems are mostly cut out. Crown becomes repeated chopped portions of a full tree. | Same defect, not repaired by pruning faces |
| Amelanchier NPM | Shared FLORIO project atlas: foliage tile near upper left and bark near lower right; U 0.02904–0.94317, V 0.02383–0.80332 | Old foliage tile samples the replacement's mostly white upper-left region; bark strip samples white lower-right region. Visible result is sparse floating leaf fragments, without stems. | Same sparse fragments and missing stems |
| Cornus | Original complete shrub card occupies a central subrectangle; U 0.29523–0.71212, V 0.34782–0.71785 | The same subrectangle now crops the middle of a differently framed full shrub. The frame is filled with leaf/stem pixels, exposing square card edges; top view is a hard-edged star. Opacity is enabled, not missing. | Same square crop / hard-edged star |
| Spiraea | Small top-left tile of shared project atlas; U 0.01280–0.19040, V 0.83089–0.96177 | This rectangle is blank in the new full-shrub image and black in its opacity. **Entire v003 object disappears.** Original front/45-degree views remain visible. Original top is edge-on vertical cards, a separate geometry fact. | Not available |

### Alternative causes checked

- **Wrong UV/map correspondence: confirmed.** No UV adaptation accompanied the texture replacement.
- **Introduced V flip, tiling/offset or wrong map channel: not supported.** All selected diffuse and opacity
  nodes use channel 1, U/V tiling 1, offsets/angles 0, mirror false, tile true, in original and library.
  Exact per-corner UV hashes agree for all 99 source/library pairs; maximum UV deviation is zero.
  Overlay image V=0 is deliberately at the bottom, covered by tests.
- **Missing opacity binding: rejected for the tested objects.** Both slots are enabled at 100% in the
  native receipts. Original RGBA cases use alpha (`monoOutput=1`, `rgbOutput=1`, `alphaSource=0`);
  project atlases use separate intensity opacity. Our maps use separate intensity opacity
  (`monoOutput=0`, `rgbOutput=0`), which is appropriate to those files. It samples the wrong UV region.
- **Gamma/color management: a secondary difference, not the missing-trunk/crop cause.** Union loads
  Gamma, FLORIO loads Unmanaged, v003 loads OCIO_Default. Uncontrolled renders therefore had different
  background levels. Final renders force Gamma/display 2.2 and explicit PNG save gamma 2.2 after every
  scene load. All 17 final front backgrounds equal RGBA `(223,223,223,0)`. The layout defects remain.
  Native opened PNG input gamma is approximately 2.2; all 198 stored source bitmap instances are `.png`,
  not `.tx`. This is not a claim that opacity filtering/color management is delivery-certified.

## Decoder control: do not misdiagnose an invisible original

The first Tilia original-opacity render was blank, while clay and diffuse-only controls were visible.
A native `openBitmap/getPixels` probe isolated incorrect indexed-PNG decoding in Max 2026: at an opaque
bark sample the indexed file reports alpha 0, while its pixel-identical RGBA re-encoding reports 255.
The control was reproduced for all three indexed PNGs in the copied maps. This is a separate native
reader problem, not evidence that Tilia's source UVs are bad or that its original opacity is absent.

Only scratch copies were re-encoded P→RGBA; decoded RGBA bytes were checked equal before/after for
all three files. No image was generated, recolored, UV-remapped or published as a new asset. Overlays
use the original copied pixels. `native-texture-controls.json` records the native samples; final
render receipts name both the source copy and any lossless diagnostic decoder copy. Source map files
remain byte-identical. The indexed decoder behavior is established for this tested Max build, not
asserted for every Max version.

## Baseline versus library/light: measurements

Front cutout pixels are counts with render alpha >127 at 512×512, **not** a botanical accuracy score.
Geometry deviation compares same-index vertices after subtracting each world bbox center (placement
removed, no scaling/rotation fitting); it is not a continuous Hausdorff bound.

| ID | Original triangles | v003 triangles | Light triangles | Front pixels original → v003 → light | Max centered vertex deviation, mm |
|---|---:|---:|---:|---|---:|
| 101 | 357 | 357 | n/a | 47,212 → 52,645 → n/a | 0.000358 |
| 102 | 446 | 446 | n/a | 31,937 → 51,594 → n/a | 0.005249 |
| 103 | 488 | 488 | 96 | 55,184 → 40,544 → 37,290 | 0.003816 |
| 105 | 979 | 979 | 225 | 33,784 → 5,194 → 4,775 | 0.011651 |
| 204 | 80 | 80 | 36 | 66,003 → 116,541 → 114,312 | 0.019083 |
| 225 | 20 | 20 | n/a | 84,325 → 0 → n/a | 0.041962 |

51 final native renders completed. Median per-render time: 1.103 s; original Union 1.045 s,
FLORIO 1.106 s, v003 1.203 s, light 1.055 s (at least 3 view renders per group).
These are medians across views/assets, **not** three repetitions of an identical workload or a speedup
claim. Final wrapper wall time, including loading/startup/shutdown: 195.5 s. Initial 45-view,
uncontrolled-color run: 170.8 s; not a fair runtime comparison because payload/settings differ.

### Which of the 99 share the cause?

`compare_inventory` and `replacement_evidence` inspect every named source/library pair. Results:
**99/99 identical UV hashes and triangle counts; 99/99 replace all source bitmap basenames with the
new species-map basenames.** `affected-objects.json` enumerates the exact 99 names and source/map pairs.
Source material classes: 81 Standard and 18 MultiMaterial; library replaces those with species Standard
materials. The 18 source MultiMaterials also lose their original submaterial organization and require
slot-aware follow-up inspection.

This proves the same unsafe replacement-without-remapping mechanism for 99 objects; it does **not**
claim 99 individually viewed appearance failures. Visual confirmation covers the six requested species
and the additional Union #105 VPM counterpart. Existing stand-in/identity limitations remain unchanged.

The code path explains the result: `build_flora_library_max.adopt` copies source geometry/UVs and
assigns species face IDs; `bind_materials` creates Standard materials and attaches the new species
images without rebuilding UVs or baking source component atlases. Rebinding paths cannot repair that
semantic mismatch. `build_flora_npm_light` prunes faces using the already-incompatible binding, so
similarity to the faulty v003 baseline is not correctness against the original.

## Reproduction and checks

```bash
uv sync
uv run python tools/flora/prepare_texture_diagnosis.py \
  --union "<original FLORA_Union_v1.max>" --florio "<original FLORIO_2BT_2022.max>" \
  --library C:/x/flora-library/v003/flora-library-v003.max \
  --light-fbx C:/x/flora-light/v001/fbx --catalogue library/flora/catalogue.json \
  --work "<fresh private %TEMP%/agr-3dsmax-<card>/ directory>"
export FLORA_DIAG_JOB="<private job.json>"
python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --ping --card t_49156f66
python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --file tools/flora/diagnose_texture_max.py --card t_49156f66
python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --file tools/flora/probe_texture_diagnosis_max.py --card t_49156f66
python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --file tools/flora/render_texture_diagnosis_max.py --card t_49156f66
uv run python tools/flora/sheet_texture_diagnosis.py "<job.json>" "<fresh review directory>"
uv run pytest tests/test_flora_texture_diagnosis.py -q -o addopts='' --basetemp=C:/x/t_49156f66-probes
```

The committed prepare script was also exercised on the real inputs in `repro-v001`: all 236 protected
source hashes match the experimental setup; all three decoder copies preserve exact RGBA pixels.
Native scripts never save MAX scenes or export assets. No binaries are committed. Known native startup
`polyunwrapper_autoload.mse` and missing legacy mental-ray attribute warnings are preserved in wrapper
logs; wrapper status alone was not accepted as proof. Completion markers, JSON records, image counts,
pixels, visual inspection and source hashes were checked independently.

Pure-Python RED: 13 assertion/probe failures with intentional no-op helpers; initial GREEN: 28 tests.
After adding the calibration-only probe: 34 focused tests passed. The full suite on `94dc00a`
completed with 7,122 passed / 2 failed / 14 skipped / 63 deselected in 1,688.16 s. Both failures are
load-sensitive orientation wall-clock budgets, tracked by pilot issue #361. Both reproduce on a
`27daa64` baseline source copy: box 11.2246 s versus 10 s, slivers 8.0641 s versus 5 s. No orientation
code or budget was changed here. This receipt is not a globally green suite.
Additional probes include 99-key generated accounting, empty/partial/unsupported/non-finite evidence,
UV boundaries, invalid topology/no output, duplicate bitmap display names, hardlink/input-output alias
rejection and AST checks excluding scene-save/export calls. Full suite receipt is recorded in the PR.
Regression evals: `tmp/evals/flora-texture-diagnosis/report.json`: 0 passed / 0 failed / 10 not measured,
exit 2 (no Claude transcript/PR evidence); this is not an eval pass. CI: not run (billing lock).

## Verdicts and proposed separate follow-up issue

**Reject:** treating species-map approval, resolved file paths, equal geometry/UVs or a light-vs-v003
silhouette test as proof of correct texturing. **Adopt:** direct slot-path/UV-overlay/original-render
comparison as an appearance prerequisite. **Maybe:** scratch-only lossless PNG decoder control;
retain the native defect receipt and avoid generalizing it to other builds.

Separate proposed repair: [#411 — Flora: rebuild map-to-UV correspondence before republishing the library](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/411).
Scope: preserve all stable IDs and identity gaps; classify the 99 original bindings into project-atlas
crops, component leaf/bark layouts and multi-submaterial cases. Select a reviewed route per object:
retain/bake the original appearance, or rebuild UV/geometry for the approved full-plant map. A global
V flip or one affine UV rescale is not a general fix for component atlases. Validate original-vs-new
front/45/top cutouts, explicit opacity/color policy and bark/leaf correspondence; only then rebuild
NPM light and rerun readback/checkers. Publish to new versions only after visual review. Issue #411 was created as the explicitly requested single follow-up after duplicate search; it is not labelled ready for dispatch. No fix was implemented in this diagnosis card.
