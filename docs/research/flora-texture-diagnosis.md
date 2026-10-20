# Flora texture diagnosis (#369)

- Причина: сохранённые UV привязали к картам с другой компоновкой; механизм подтверждён для 99/99 объектов, визуально — для шести видов.
- Уточнение по коре выполнено: исходный узкий остров липы проходит containment 99,5347%; покрытие всей полосы к нему неприменимо.
- Выполнен сырой расчёт 201 записи: 99 оригиналов + 99 v003 + 3 light; шесть расширенных листов просмотрены лично.
- Калибровка пока НЕ пройдена: у 16 323 исходных UV-компонент роль неизвестна; это ограничение классификатора, не доказательство дефекта оригиналов.
- Итоговые маршруты не выданы: 7 rebind и 1 star только предварительные, 91 требуют проверки источника; PR #377 draft, ассеты не изменены.

## Geometric recalibration [D155]

The previous bark-policy question is **answered**, not an open threshold decision.
Artem's voice decision (Kanban `t_49156f66`, comment 1542, coordination rule 48) and the
orchestrator's **2026-10-20 14:42 scope clarification** are recorded in the
[Flora sheet](../domain/areas/flora.md#geometric-sprite-coverage-d155) and [D155].

- Discrete VPM sprites: `area(island intersect sprite opaque bbox) / area(sprite opaque bbox)`,
  target 0.80–0.95; >0.95 only without neighbouring opaque sprites inside the island.
- Continuous bark: **>=95% of island area on bark pixels**, not coverage of an entire bark strip.
  V tiling along the strip is allowed by the rule. The current implementation reports islands crossing
  a repeated tile as unsupported; it does not silently accept them.
- NPM whole-plant planes: cover >=80% of the image region, with allowed extra transparent margin
  and no clipped opaque plant pixels (1 pixel tolerance). Both bbox/island ratio and
  `island_intersection_over_sprite_bbox` are stored. The prototype still reports the original
  0.80–0.95 bbox/island target separately; its raw `pass` is **not** a certified implementation of
  every clarified NPM case.
- Threshold opacity is >=128. Discrete sprite area is polygon union/intersection (Shapely 2.1.2).
  Bark containment uses a native-pixel raster on a reviewed region, consistently in numerator and denominator.

### Narrow bark witness: resolved and measured

The original-only image `tilia-original-bark-geometric-v001.png` remains a **historical baseline**:
its red/fail annotation describes the superseded whole-strip applicability, not the current bark verdict.
The image was personally viewed again. The narrow triangle lies on the continuous bark strip, separate
from the two foliage sprites. Current exact receipt:
`experiments/flora-texture-diagnosis/bark-containment-v002.json`.

Original `Tilia_cordata_VPM` / `19_Lipa_HP`, island 166 / face 332, 4096×4096 atlas:

| Method | Measurement | Result | Median seconds, same input ×3 |
|---|---:|---|---:|
| Historical generic sprite-bbox coverage | 7,930.757195 / 3,244,032 px² = 0.2444722245% | Wrong applicability to a continuous strip | 0.011435 |
| Reviewed opaque-bark containment | 8,557 / 8,597 raster pixels = 99.5347214144% | Pass (>=95%) | 0.013396 |
| Original discrete leaf card, control | 100% sprite-bbox coverage; 0 neighbouring opaque pixels | Pass under >95% exception | Not repeated for speed |

No speedup is claimed. The difference between polygon area and raster pixel counts is explicit.
Code footprint: `measure_sprite_coverage.py` grows from 212 to 406 lines; the raw comparison and
atlas-review helpers add 476 and 143 lines respectively. These remain diagnostic tools, not a
replacement for production checkers. Their geometry/classification heuristics are not simplified
into an unsupported universal acceptance flag.
See [the small experiment report](../experiments/flora-bark-containment.md).

### Full raw sweep and evidence

Current review bundle:
`C:/x/review/2026-10-20/flora-texture-diagnosis/raw-diagnostics-v004/index.html`.
All six `101/102/103/105/204/225.png` sheets append original/library/light candidate masks,
coloured UV edges and raw role/score summaries to the existing controlled renders. I opened all six
v003 sheets with `vision_analyze`; the v004 copies are **6/6 SHA-256-identical**. The only v004
re-seal corrects star metadata to permit independent geometry and UV vertex counts, without
changing any island metric, mask, render or sheet. `provenance.json` identifies the exact input hashes.

| Tag | Objects | UV components | Scored components | Raw applicable pass | Unknown geometry role | Unscored |
|---|---:|---:|---:|---:|---:|---:|
| Original Union | 68 | 26,504 | 25,752 | 4,289 | 16,042 | 752 |
| Original FLORIO | 31 | 1,443 | 1,443 | 839 | 281 | 0 |
| v003 | 99 | 27,947 | 22,856 | 0 | 16,323 | 5,091 |
| NPM light FBX | 3 | 326 | 325 | 0 | 113 | 1 |

These are **diagnostic flags**, not counts of defective plants or calibrated replacement failures.
Unknown/not-applicable islands also have `pass=false`; the categories must not be added as disjoint sets.
All faces are accounted for per object, with exact face lists and unknown/error reasons in `metrics.json`.
`distribution.json` reports min/q25/median/q75/max by tag and role. `routes.json` has 99 unique named
pairs and preserves source/library/light per-island ledgers. All 201 records have `accepted=false`
at the report boundary; no production assets were changed.

The source-only baseline before reviewed bark annotations also completed: 99 objects / 27,947
components, 8 objects with every component passing, 16,323 unknown geometry roles.
Its compact receipt is `experiments/flora-texture-diagnosis/source-calibration-baseline-v002.json`.
23 source bark regions (24 rectangles, including an L-shaped FLORIO region excluding grass)
were visually reviewed across nine atlas sheets. Exact basenames, bitmap hashes and rectangles:
`experiments/flora-texture-diagnosis/reviewed-bark-regions-v002.json`.

### Why calibration still fails — implementation limits, not another bark-policy question

The gate is deliberately still **failed**: first witness `Tilia_cordata_NPM`, island 3.
The current method groups UV faces by shared map indices and inherits shape roles from connected
3D elements. It does not resolve every duplicate-coordinate seam, curved card, joined star or
non-elongated branch assembly into authored semantic parts. For example, visible Cornus crossed
cards produce 65 UV components from 80 triangles, all with unknown roles under this classifier.
Calling these foliage or whole-plant planes solely because their UVs hit a convenient region would
be circular. A catalogue NPM label is not proof of whole-plant star geometry.

Independent plane checks record counts, absolute normal Z, global UV extent, opacity binding and
per-island UV extents. The source Spiraea NPM has 10 vertical planes and passes this candidate check;
source Tilia/Betula/Crataegus/Amelanchier contain complex multi-plane meshes, not a confirmed simple star.
The 12-plane cap and normal-Z tolerance 0.02 are diagnostic heuristics, **not user thresholds or a
certified star-arrangement gate**. The helper does not prove common-centre crossing or botanical identity.

RGB green/brown classification is only a **candidate display**, with purple unknown opaque pixels;
it is not an independent semantic ground truth. Reviewed bark containment is stored separately.
Touching atlas sprites remain ambiguous under alpha-only gutter segmentation. Unverified replacement
bark is never promoted to semantic pass. Thus the tool cannot yet deliver calibrated semantic masks
and final map/UV repair choices for every object.

| Provisional route | Count | Status |
|---|---:|---|
| `rebind_original_atlas` | 7 | Source VPM geometric rows pass; still provisional because the global gate fails |
| `keep_or_rebuild_star` | 1 | Source Spiraea NPM star; replacement tile is empty, so rebuilding correspondence is necessary |
| `source_validation_required` | 91 | Failed, unknown or not-applicable source role/cell/plane checks; no repair route invented |
| Definitive routes issued | 0 | Withheld, not an out-of-scope acceptance point |

Remaining acceptance: improve/annotate geometry-role and authored sprite-cell correspondence, calibrate
originals (or explicitly resolve their genuine non-applicability), then issue final per-object routes.
**No further full native extraction is required**; the arrays already contain all 99 pairs and 3 FBX.
Three Cursor rounds were used in this continuation. It needs an implementation handoff for the remaining
role/cell analysis, not another threshold clarification or an asset repair. Do not mark this diagnosis accepted.

Reproduction, using copied job/maps and fresh output directories:

```bash
uv run python tools/flora/review_atlas_regions.py --job tmp/all-job-v005.json --output <fresh review subdirectory>
uv run python tools/flora/measure_sprite_coverage.py --job tmp/all-job-v005.json --output <fresh source.json> --sources-only
# annotated-job-v006.json adds reviewed-bark-regions-v002.json using resolved copied bitmap paths
uv run python tools/flora/compare_sprite_diagnostics.py --job tmp/annotated-job-v006.json --output <fresh review subdirectory>
```

Current affected tests: **96 passed** (including decision-log checks), including explicit/missing/displaced bark masks, exact 95% boundary,
multiple reviewed rectangles, unknown/fail status rejection, independent UV indexing, raw 201-record /
99-route accounting, source gate failure preservation, path aliases, and empty/partial CLI subprocesses.
New tests fail against the copied `4def676` baseline (missing new API at collection); no fabricated no-op
baseline was used in this continuation. Source integrity: **236/236 unchanged SHA-256**, exact receipt
`experiments/flora-texture-diagnosis/source-integrity-v002.json`.
Full suite is the earlier receipt below, not rerun; current evals: 0 passed / 0 failed / 10 not measured,
exit 2, `tmp/evals/flora-texture-diagnosis-v002/report.json` (no Claude transcript/PR evidence).
Code was written by Cursor (grok-4.7-medium), with small driver verification fixes; no DCC ran in this continuation.

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
