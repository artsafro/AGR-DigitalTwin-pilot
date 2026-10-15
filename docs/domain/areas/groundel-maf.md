# GroundEl / MAF — requirement sheet

**Area and profiles:** GroundEl / small architectural forms (MAF), NPM and VPM.
In scope: project-specified fences, railings, furniture, lighting-mast geometry and planters within
Ground; their geometry, texture, naming and placement interfaces. Out of scope: Ground relief,
Flora, OKS roof landscaping, light-source production and package production themselves; library
identification and manufacturer/specification matching (T-MAF-1 awaits the user's local paths).

**Readiness:** [roadmap §4 and §7.11](../../research/capability-roadmap.md#4-coverage-matrix-upstream-main-ea7ecce)
records L0. This sheet adds the L1 rule index, pending calibration-format/user and docs review;
area patterns and a modelling skill are still missing, so full L1 is not claimed. Generic validator
subsets do not constitute area L2 (no MAF benchmark/identified etalon); no user-accepted MAF case
establishes L3. This is not a delivery acceptance.

**Reading:** the table is an index, not replacement rule text. `reg p.N` is the one-based PDF page
of [the supplied regulation](../../../standards/source/Rasporyajenies19012026trebovaniya(2).pdf).
Section numbers follow the rule-table numbering used by the linked domain files. NPM and VPM
have identical project representation, **not identical texture or naming contracts**: GroundEl's
NPM atlas limit and mesh suffix must not be transplanted into VPM's Ground rules.
`L2 coverage` names only implemented checks today, with their limits; `none` includes manual-only
checks. Coverage was checked against [the implementation inventory](../validation.md#implementation-status-inventory-static-audit),
[`scene_findings`](../../../src/twinqa/scene.py), and [`png.py`](../../../src/twinqa/png.py),
not inferred from the V-code specification. All scene subsets require exported-FBX readback;
this research ran no DCC or delivery validation.

| Requirement | reg page | NPM | VPM | How it is checked | L2 coverage | Detail in |
|---|---|---|---|---|---|---|
| MAF-01 — Area membership and bounds | reg p.1–2 §2; reg p.21 §2 | GroundEl polygonal elements; exclude relief, Flora and OKS roof landscaping; current plot/stage only | Same project scope, represented within Ground | Manual project-plan inventory and boundary/roof classification | none | [Profile terms](../npm-vpm.md#terms) |
| MAF-02 — Approved design and profile completeness | reg p.4 §1.3; reg p.24 §1.3 | All specified MAF present | Same project elements, including lighting masts and greenery | Manual V015: approved drawings/specification and paired-profile comparison; not a topology-equality test | none | [Common profile contract](../npm-vpm.md#common-to-both), [manual QA](../validation.md) |
| MAF-03 — Silhouette and courtyard furniture | reg p.7 §3.1; reg p.28 §3.3; reg p.29 §3.19; reg p.32 §7 | Silhouette-led simplification; minor detail via texture | Silhouette-led simplification; retain specified courtyard/niche furniture; the 5 cm baking clause concerns details recessed into/protruding from the main building geometry (curbs excepted), not a blanket MAF simplification threshold | Manual silhouette views against the project, including urns, tables, chairs and planters; check applicability before using a building-detail baking threshold | none | [Geometry rules](../geometry.md#regulation-geometry-rules-both-profiles-unless-noted), [courtyard scope](../npm-vpm.md#terms) |
| MAF-04 — Metric scale | reg p.4 §4, §2.1; reg p.24 §4, §2.1 | 1 unit = 1 m; scale 1:1 | Same | Manual exported system-unit and known-dimension readback; V002 header check does not verify units | none | [Units](../geometry.md#units-coordinates-pivots), [V002 limitation](../validation.md#implementation-status-inventory-static-audit) |
| MAF-05 — Scene structure | reg p.6 §1.3; reg p.7 §3.5; reg p.28 §3.1–3.2, §3.8; reg p.29 §3.11 | Clean scene; no geometry hierarchy/groups | Same; default collection only | Manual scene audit for hierarchy, animation, modifiers and collection structure; generic V003 object-type checks are insufficient | none | [Geometry rules](../geometry.md#regulation-geometry-rules-both-profiles-unless-noted) |
| MAF-06 — Ground geometry/glass separation | reg p.6–7 §1.5; reg p.10 §7; reg p.28 §3.4–3.5; reg p.32 §8.1 | Ground FBX contains separate GroundEl and, when present, GroundElGlass; translucent glass has no texture set | Ground / GroundGlass contract, not an invented GroundEl suffix | Manual object/material inventory and glass classification | none | [NPM structure](../npm-vpm.md#npm-appendix-1), [glass geometry](../geometry.md#regulation-geometry-rules-both-profiles-unless-noted) |
| MAF-07 — Shared NPM triangle budget | reg p.7 §3.6 | Ground + GroundEl + Flora total ≤ 180 000 triangles, not a per-MAF allowance | See MAF-08; do not reuse the NPM ceiling | Sum exported non-UCX triangles for the complete Ground FBX | V003 — `scene_findings`, NPM `role=ground` total only | [Profile budgets](../npm-vpm.md#npm-appendix-1), [implementation](../../../src/twinqa/scene.py) |
| MAF-08 — VPM Ground budget | reg p.28–29 §3.10; [D010] | See MAF-07 | Ground area-dependent table, excluding UCX; no separate per-MAF allowance | Manual site-area calculation and whole-Ground triangle sum; V003 currently returns `review` for this limit | none | [VPM budget](../npm-vpm.md#vpm-appendix-2), [C1, decided by the user](../conflicts.md#a-inside-the-regulation) |
| MAF-09 — Shared GroundEl atlas limit | reg p.10 §5.12; reg p.30 §5.1.2 | 1 texture set for all GroundEl; maps ≤ 512×512 px | VPM Ground texture contract instead; the NPM limit is not a VPM rule | Manual set grouping across all elements and image dimensions; generic NPM size helper does not enforce this cap | none | [NPM GroundEl textures](../uv-textures.md#npm-textures-app1), [VPM textures](../uv-textures.md#vpm-textures-app2) |
| MAF-10 — NPM density exemption | reg p.10 §6.2 | GroundEl exempt from relief-density requirements | No transfer of the NPM exemption; see MAF-17 | Manual target classification; do not grade GroundEl as NPM relief | none | [Density applicability](../uv-textures.md#npm-textures-app1), [C4, open for the user; relief units only](../conflicts.md#a-inside-the-regulation) |
| MAF-11 — Internal mesh naming and name syntax | reg p.11 §10.1–10.2; reg p.11–12 §3.3; reg p.33 §10.1–10.3, §4.2 | `SM_{Address}_GroundEl`, `SM_{Address}_GroundElGlass`; ≤ 254 characters; Latin/digits/underscore | `SM_{Address}_Ground`, `SM_{Address}_GroundGlass`; same length ceiling; VPM capitalization/separators | Manual internal-name inventory; V012 currently checks package names, not mesh masks | none | [NPM names](../geometry.md#naming---npm-reg-p10-13), [VPM names](../geometry.md#naming---vpm-reg-p33-36), [Address](../npm-vpm.md#common-to-both) |
| MAF-12 — Texture/material naming | reg p.12–13 §3.4–3.5; reg p.34 §4.3–4.4 | GroundEl texture/material masks and matching editor/PNG names | Ground texture/material masks and UDIM filename convention | Manual exported material/image inventory; package-level prefix validation is not internal-name validation | none | [NPM names](../geometry.md#naming---npm-reg-p10-13), [VPM names](../geometry.md#naming---vpm-reg-p33-36) |
| MAF-13 — NPM embedding flag | reg p.9 §5.1 | PNG atlases embedded in Ground FBX | Not applicable; external PNG contract in MAF-14 | Readback of packed-image flags; pixel extraction remains separate | V006 — `scene_findings`, embedding flags only | [NPM textures](../uv-textures.md#npm-textures-app1), [implementation limits](../validation.md#implementation-status-inventory-static-audit) |
| MAF-14 — Image-format checks | reg p.9 §5.2–5.3, §5.5; reg p.30 §5.1.1–5.1.4, §5.1.6–5.1.9; [D015], [D020] | Generic atlas dimensions, byte size and alpha policy; special GroundEl cap remains MAF-09 | External PNG dimensions, map triplets, bit depth and alpha policy | NPM helper requires separately supplied PNG bytes; VPM archive validator checks external maps; normal/ERM semantics include heuristics, not proof | V006 — standalone `npm_texture_findings` only, not embedded-pixel extraction; V007 — `vpm_texture_findings`, partial | [Texture rules](../uv-textures.md), [C12/C21, decided by the user](../conflicts.md), [PNG implementation](../../../src/twinqa/png.py) |
| MAF-15 — Materials, map semantics and padding | reg p.8–9 §4, §5.4, §5.6–5.10; reg p.29–30 §4; reg p.30 §5.1.5; reg p.31 §3.1–3.5; [D013], [D014], [D020] | NPM shader/map-pair/placeholder/glass rules; no normal delivery map | VPM shader/slot/glass rules, external paths cleared, map semantics and padding | Manual material-network and island-edge review; V005 unimplemented, V006/V007 do not measure padding | none | [Materials](../materials.md), [UV/textures](../uv-textures.md), [C5/C6/C21, decided by the user](../conflicts.md) |
| MAF-16 — Basic VPM UV contract | reg p.31 §2.1.1, §2.1.3–2.1.4 | NPM atlas contract, not UDIM | Single UV channel; sequential UDIM; no mirrored islands | Exported UV readback plus archive tile sequence; does not establish correct island stacking, seams or margins | V008 — `scene_findings` channel/mirroring; `uv.sequential_tiles` filename sequence | [VPM UV](../uv-textures.md#vpm-uv--udim), [UV implementation](../../../src/twinqa/uv.py) |
| MAF-17 — VPM density and remaining UV quality | reg p.31 §2.1.2, §2.1.5–2.2, §6.1; reg p.32 §6.2 | NPM exemption in MAF-10 | Diffuse 512–1706 px/m, formula texture length / polygon length; exempt ERM/Normal/placeholders; splitting, stacking, seams, margins and GroundGlass UV rules | Manual metric UV inspection and render; V009 unimplemented; V008 glass-name check covers MainGlass, not GroundGlass | none | [VPM UV/density](../uv-textures.md#vpm-uv--udim), [C10, image/OCR discrepancy](../conflicts.md#a-inside-the-regulation) |
| MAF-18 — Export triangulation | reg p.8 §3.11; reg p.29 §3.17 | Triangulate derived FBX geometry | Same | Inspect exported mesh face degrees, not the editable master | V003 — `scene_findings` triangulation | [Geometry rules](../geometry.md#regulation-geometry-rules-both-profiles-unless-noted) |
| MAF-19 — Applied transforms | reg p.8 §3.14; reg p.10 §8.1; reg p.29 §3.18; reg p.32 §9.1 | Apply transforms with project-plan rotation contract; manual angle comparison remains | Apply transforms with zero-rotation contract | Exported rotation/scale check; validator zero-rotation test is not NPM plan-orientation verification | V004 — `scene_findings`, VPM rotation/scale subset; NPM plan comparison unimplemented | [Coordinates/transforms](../geometry.md#units-coordinates-pivots), [implementation](../../../src/twinqa/scene.py) |
| MAF-20 — Topology and visible-surface quality | reg p.8 §3.7–3.10, §3.15; reg p.29 §3.11, §3.13–3.15 | General topology, spacing, normals and smoothing rules | Same profile-specific geometry rules | Manual mesh audit and views through/around furniture; V004 delivery checks transforms, not this topology contract | none | [Geometry rules](../geometry.md#regulation-geometry-rules-both-profiles-unless-noted), [QA procedure](../validation.md#general-qa-procedure-project) |
| MAF-21 — Cut-outs and two-sided opacity geometry | reg p.8 §3.13; reg p.9 §5.5, §5.8; reg p.36 §12.1–12.3; [D020] | Separate opacity map; no duplicated-offset thickness | Diffuse alpha and profile-specific duplicated-offset geometry when seen from both sides | Manual profile-specific geometry/map inspection; do not resolve the difference by sharing one export | none | [Geometry](../geometry.md#regulation-geometry-rules-both-profiles-unless-noted), [C7/C8 profile differences and C21, decided by the user](../conflicts.md) |
| MAF-22 — MAF/lighting/fence collision exclusion | reg p.6 §1.2; reg p.36 §13.2–13.3 | No UCX requirement in NPM | MAF, lighting elements and vegetation excluded from Ground collision; no collision for canopies, fences and railings ≤ 5 cm thick; do not omit the Ground-surface collision; every FBX except lighting FBX carries collision | Manual collision-target overlay with fence-thickness measurement; V010 triangle budgeting does not verify MAF exclusion | none | [Collision targets](../geometry.md#collision--ucx-vpm-only-npm-has-none-unless-customer-spec), [NPM package boundary](../npm-vpm.md#npm-appendix-1) |
| MAF-23 — Placement and shared pivots | reg p.10 §8.1–8.2; reg p.32–33 §9.1–9.5; [D018] | Moscow project coordinates/heights and plan orientation | Ground-local origin/shared pivots; project zero and paired GeoJSON placement | VPM pivot subset via readback; manual V017 for survey/project-zero truth and NPM georeferencing | V013 — `_pivot_findings`, local/shared/centre subset only; V014 and survey alignment unimplemented | [Placement](../geometry.md#units-coordinates-pivots), [C19, decided by the user](../conflicts.md#b-regulation-vs-local-yaml--docs) |
| MAF-24 — Lamp geometry versus light emission | reg p.4 §4; reg p.24 §4; reg p.33 §4.1; reg p.37 §14, §15.3; [D017] | Mast/fixture geometry retained; scene light sources removed | Fixture appearance in model, glow via ERM; environmental light sources in separate Ground Light FBX | Manual appearance/emission and file-assignment review; generic non-mesh rejection alone does not check the whole contract | none | [Lighting boundary](../npm-vpm.md#vpm-lighting-fbx-architectural-light-design), [C14, decided by the user](../conflicts.md#a-inside-the-regulation) |

## Source-image evidence

All numbers, units and limits stated in the table were visually checked on PyMuPDF-rendered PDF
pages, not accepted from OCR alone. Local renders: `C:/x/l1-evidence/groundel-maf/pNN.png` (outside
the repository, not committed, not required to follow this sheet). PyMuPDF 1.28.2; render matrix
`(1.6, 1.6)`, no alpha.
The repository declares `pdf-review` as an optional extra, not a dependency group; the working
command is `uv run --extra pdf-review python`, using `pymupdf.open(...)` and
`page.get_pixmap(matrix=pymupdf.Matrix(1.6, 1.6), alpha=False).save(...)`.
Visually inspected pages: 1, 2, 4, 6–13, 21, 24, 28–34, 36–37.
Decision-specific interpretations remain attributed to the user, not to the page image.
In particular, **MAF-05's VPM modifier/animation audit cites reg p.29 §3.11** (not only
the scene rules on p.28). On `tmp/issue-132/pdf-v003/p29.png`, the visible list headed
“Объекты геометрии не должны содержать” includes “ключей анимации” and
“дополнительных модификаторов”. VPM placeholder applicability is on p.31 §3.1–3.5.
A fresh PyMuPDF render of pages 4, 7, 10, 11, 12, 29 and 32 matched the inspected PNGs
byte-for-byte (7/7); no OCR extraction was used for this follow-up check.

Six independently reviewable row anchors (English translations of visible page wording; the
original images/PDF are authoritative):

- **MAF-04, reg p.4 §4 and §2.1** (`p04.png`): “scale 1:1”; “one conventional unit of measurement corresponds to one metre”. VPM repeats both on p.24.
- **MAF-07, reg p.7 §3.6** (`p07.png`, bottom): “for landscaping, its elements and vegetation elements in total — 180 000” triangular polygons. The number is shared, not per asset.
- **MAF-09, reg p.10 §5.12** (`p10.png`, top): “one texture set for all elements, no larger than 512 × 512 pixels”.
- **MAF-11, reg p.11 §10.1 and p.12 §3.3** (`p11.png`, `p12.png`): “must not exceed 254 characters”; visible masks `SM_Address_GroundEl` and `SM_Address_GroundElGlass`. VPM's Ground masks are on p.33, not the NPM masks.
- **MAF-22, reg p.36 §13.2** (`p36.png`, middle): collision is built only for Ground “(ground parts: MAF, lighting elements and vegetation in it are not taken into account)”; “for canopies, fences and railings not exceeding 5 cm in thickness, collision is not built”.
- **MAF-17, reg p.32 §6.2** (`p32.png`, top): “from 512 to 1706 px/m”; the rendered formula divides texture-side length by polygon length. C10 records the OCR discrepancy.

## L2 gaps

The table contains **24 requirement rows**: **17** with `none` and **7** with implemented partial
coverage. Every `none` row is listed below; these are L2 ticket candidates, **not filed tickets**:

- **MAF-01:** semantic membership, plot/stage boundary and roof exclusion.
- **MAF-02:** approved-source completeness and paired NPM/VPM representation.
- **MAF-03:** silhouette/minimal-detail judgement, building-only baking-clause applicability and courtyard-furniture preservation.
- **MAF-04:** exported system units and physical scale.
- **MAF-05:** hierarchy, modifiers, animation and collection audit.
- **MAF-06:** GroundEl/glass grouping and profile-specific mesh/material composition.
- **MAF-08:** VPM Ground area calculation and hard-budget check (C1 decided [D010]).
- **MAF-09:** all-elements shared-set count and special GroundEl atlas ceiling.
- **MAF-10:** exclusion of NPM GroundEl from relief-density grading.
- **MAF-11:** internal mesh masks and full-name syntax/length checks.
- **MAF-12:** internal material/image names and editor-to-PNG correspondence.
- **MAF-15:** shader/slot/map semantics, placeholder applicability and padding.
- **MAF-17:** general density, GroundGlass UV and remaining island-quality checks.
- **MAF-20:** topology, normals, smoothing, overlap/spacing and visible-surface defects.
- **MAF-21:** profile-aware cut-out and two-sided-opacity geometry validation.
- **MAF-22:** semantic exclusion of MAF/lighting from UCX, the ≤ 5 cm fence/railing exemption, while retaining Ground coverage.
- **MAF-24:** fixture appearance, emission semantics and separate light-source delivery.

Partial rows also leave work: MAF-13/14 embedded PNG pixel extraction and full semantics;
MAF-16 UV quality beyond its implemented subset; MAF-19 NPM plan-angle comparison;
MAF-23 NPM georeferencing, project-zero and survey alignment. No complete MAF L2 is claimed.
The [Maf Tools review](../../agr/inventory/ZAVOD_AND_MAX_PLUGINS_REVIEW.md#2-andrew-maf-tools-matidudim-плотность-и-упаковка--max-31)
is static prototype evidence, not a running validator or a MAF benchmark. Its MatID-to-UDIM
mapping is not a regulation rule. T-MAF-4 still needs identified user etalons from T-MAF-1;
no library identity, article, manufacturer dimensions or specification convention is invented here.

No new conflict is introduced. Existing C1/C19 and other decided entries retain their user
attribution; open C4 remains unresolved and is not used to impose density on NPM GroundEl.

## Follow-up verification

The supplied partial sheet already contained the p.29 §3.11 citation. Its unchanged baseline
passed **6/6** in-memory documentation checks: single table/exact columns; 24 sourced,
seven-cell rows; MAF-05 modifier source; complete 17-row gap inventory; five image-evidence
anchors; eight numeric/unit tokens matched to visually reviewed pages. There is no observed
historical RED on the supplied sheet, and none is claimed.

For the regression negative control, only `; reg p.29 §3.11` was removed from MAF-05's
source cell **in memory**, leaving the prose evidence untouched. The same six checks produced
**1 assertion failure, 5 passes**, specifically the missing modifier source. Restoring the
original string gave **6/6 GREEN**. This is a reconstructed omission, not a pre-fix revision run.
No test or tool file was added, preserving the sheet-only, documentation-only scope.

Exhaustive documentation probes: every row must have a source → blank each source cell →
**24/24** omissions rejected; every `none` row must appear in L2 gaps → remove each gap entry →
**17/17** omissions rejected; modifier attribution → remove only the p.29 citation → **1/1**
omission rejected. Numeric/unit assertions cover **8/8** tokens: 5 cm; 1 unit = 1 m; 1:1;
≤ 180 000; 1 texture set; ≤ 512×512 px; ≤ 254 characters; 512–1706 px/m. These are sheet
consistency/source checks, **not** generated meshes, image-limit validators or area L2 coverage.
The corresponding missing production probes remain in L2 gaps.

Full-suite command (run once):
`env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider --basetemp=C:/x/pi-t_3a9764bf`.
The process timed out after **400 seconds**, with progress last labelled **68%**; no final
pytest counts were produced. Final runner line: `Command timed out after 400 seconds`.
The full suite is therefore **incomplete, not GREEN**. Calibration-format/user and docs review
also remain open.
