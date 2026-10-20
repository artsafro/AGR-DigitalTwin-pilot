# Flora texture diagnosis (#369)

- Диагностика НЕ принята: нужна область применения геометрического правила к непрерывной текстуре коры.
- Полные вершины, UV, грани и material IDs извлечены для 99/99 пар и трёх light FBX; новых изменений ассетов нет.
- По решению Артёма считаем покрытие bbox, не плотность opacity: исходная карточка листвы липы проходит с 100%.
- Но исходный bark-island покрывает лишь 0,244472% цельной полосы коры, хотя UV корректно лежит на коре; это новый случай калибровки.
- Сохранены картинка, 19 исходных объектов / 11 889 островов и полный native-инвентарь; заменам новые оценки и итоговые маршруты не выданы.

## Geometric recalibration [D155]

Artem's voice decision recorded on Kanban `t_49156f66`, comment **1542** (2026-10-20),
now coordination rule 48, supersedes both interim 95% density/class-support proposals.
The decision is recorded without changing its threshold in the
[Flora sheet](../domain/areas/flora.md#geometric-sprite-coverage-d155) and decision log [D155].
The previous opaque-area calibration is historical evidence, **not the current metric**.

- VPM: `area(island intersect sprite opaque bbox) / area(sprite opaque bbox)`;
  target 0.80–0.95. Above 0.95 only when no neighbouring sprite opaque pixel lies in the island.
- NPM whole-plant plane: `area(plant opaque bbox) / area(island)`; target 0.80–0.95,
  zero clipped opaque pixels with 1 native-pixel tolerance.
- Opacity threshold is >=128. Geometric area is exact polygon union/intersection (Shapely 2.1.2),
  not opaque pixel counts. Opacity sampling/clipping uses the actual 2048/4096 images.
- Original project atlases use an independently alpha-segmented **candidate cell** for their plant region;
  a replacement per-species map is a whole texture. Candidate cells are separated by >=1.5%-image empty
  gutters without using UVs. Touching sprites may remain ambiguous: this is not an authored cell manifest.

### A new original-only failure: continuous bark, not foliage density

Inspected picture:
`C:/x/review/2026-10-20/flora-texture-diagnosis/tilia-original-bark-geometric-v001.png`.
The green leaf-card outline surrounds its branch sprite; the red narrow triangle lies entirely within
bark, far from the foliage sprites. Cyan rectangles show independently measured alpha bboxes.
The picture was opened with `vision_analyze` after generation.

Original `Tilia_cordata_VPM` / `19_Lipa_HP`, original `.1035` atlas, 4096 x 4096:

| Original component | Geometry role | Island polygon area, px² | Target bbox area, px² | Geometric coverage | Neighbour opaque pixels | Result |
|---|---|---:|---:|---:|---:|---|
| Island 0, faces 0/30 | foliage card | 388,986.097656 | 227,700 | 100.000000% | 0 | Pass (>95% exception explicitly allowed) |
| Island 166, face 332 | trunk | 7,930.757195 | 3,244,032 | 0.244472% | 0 | Fail if every bark island must cover >=80% of the full strip |

Exact measured receipt: `experiments/flora-texture-diagnosis/bark-calibration-v001.json` (includes native inventory SHA-256).

The bark target is `[3304,0,4096,4096]` in native pixels. Its island samples opaque bark at
99.5347% raster density; that density is recorded only as supporting evidence, **not substituted
for the geometric score**. The foliage card formerly reported at ~13.56% density now passes correctly.

This is not just duplicated UV indices hiding an adjacent continuous island. Face 332's neighbouring
geometry faces 339, 775 and 794 differ at their shared vertices in UV by 0.009893–0.195873 UV units;
these are real seams. Role classification is inherited from the connected 3D element: the trunk
is non-planar, vertically elongated and >=20% of object height. Planar cards use an SVD ratio <=0.001;
NPM full-height plane candidates additionally span >=75% of object height. Unknowns stay unknown.
These diagnostic shape rules are not botanical truth or a certified star-arrangement detector.

**Decision needed:** does 80–95% sprite coverage apply to every island sampling a continuous bark
strip too, knowingly rejecting this original, or does continuous bark use role/region containment
while the geometric coverage target applies to discrete foliage/whole-plant sprites?
No exemption, new threshold, UV welding or atlas crop was invented to force the original to pass.

### Checkpoint and deliberately uncompleted acceptance

Published checkpoint:
`C:/x/review/2026-10-20/flora-texture-diagnosis/geometric-calibration-v001/index.html`.
It links the exact full native inventory, per-island partial metrics, partial distributions and
candidate class-mask overlays. Source roles, unknown lists and every face index are retained.

| Evidence | Actual result |
|---|---|
| Detailed source arrays | Union 68/68 + FLORIO 31/31; all 99 named source pairs |
| Detailed v003 arrays | 99/99, including per-face IDs and explicit MultiMaterial ID lists |
| Light FBX native readback | 3/3 with detailed arrays and direct opacity-slot settings |
| Original-only geometric checkpoint | 19 objects, 11,889 islands; complete face accounting per measured object |
| New replacement/light geometric scores | 0; stopped at the original-calibration gate |
| Final repair routes / follow-up issue | Not issued; original calibration is unresolved |
| Candidate pixel classes | RGB green/brown hypotheses plus explicit unknown opaque pixels; NOT semantic ground truth |
| Focused tests at checkpoint | 69 passed, including native-ROI geometry, exact bark-triangle regression and fail-closed original gate |

The former missing 89 detailed pairs no longer require native extraction. Do **not** rerun it merely
because the initial inventory stored details only for the selected six. Reuse hash-verified
`inventory-all.json` in the published checkpoint (`inventory-all-v005.json` in private scratch).

Remaining after the bark-policy answer: validate the atlas-cell/role annotation, complete original
calibration and separate NPM plane/star arrangement checks, then score all 99 replacements and 3 FBX,
finish the six semantic pass/fail sheets, issue final per-object repair-route counts, and propose the
single fix follow-up. The existing six render sheets below remain qualitative evidence, not a substitute.
No final semantic masks or 99-object acceptance distribution are claimed here.

Reproduction (fresh output paths required):

```bash
# all-job-v005.json selects all material IDs and sets inventory-all-v005.json
export FLORA_DIAG_JOB="<worktree>/tmp/all-job-v005.json"
python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --ping --card t_49156f66
python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --file tools/flora/diagnose_texture_max.py --card t_49156f66
uv run python tools/flora/measure_sprite_coverage.py --job <all-job.json> --output <fresh metrics.json> --pictures <fresh folder>
# The source-only run was intentionally stopped after the calibration witness; .partial.json is NOT complete.
uv run python experiments/flora-texture-diagnosis/bark_calibration.py --job <all-job.json> --metrics <partial.json> --output <fresh witness.png>
uv run python tools/flora/sheet_sprite_coverage.py --job <all-job.json> --metrics <partial.json> --pictures <folder> --witness <witness.png> --output <fresh checkpoint>
```

Native extraction completed under Max 2026.3 with zero unmatched objects; no MAX save or asset export.
The existing startup warning still makes the native exit nonzero although current completion markers
and complete per-object arrays are present; wrapper status alone was not used as success evidence.
The original-only measurement was stopped and no owned analysis/native process remains at handoff.
Full-suite receipt remains the earlier 7,122 passed / 2 known #361 timing failures; this docs/tools
rework uses focused tests and does not claim a new full-suite pass.

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

Proposed follow-up issue title: **Flora: rebuild map-to-UV correspondence before republishing the library**.
Scope: preserve all stable IDs and identity gaps; classify the 99 original bindings into project-atlas
crops, component leaf/bark layouts and multi-submaterial cases. Select a reviewed route per object:
retain/bake the original appearance, or rebuild UV/geometry for the approved full-plant map. A global
V flip or one affine UV rescale is not a general fix for component atlases. Validate original-vs-new
front/45/top cutouts, explicit opacity/color policy and bark/leaf correspondence; only then rebuild
NPM light and rerun readback/checkers. Publish to new versions only after visual review. No follow-up
issue was created and no fix was implemented in this diagnosis card.
