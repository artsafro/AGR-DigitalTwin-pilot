# Flora — L1 requirement sheet

**Area and profiles:** Flora (vegetation model), NPM and VPM: trees, bushes, tall herbaceous
plants and modelled flower beds inside the Ground FBX; their geometry, the vegetation texture set,
naming, collision exclusion and placement. Out of scope: Ground relief and lawn-level greenery
drawn in the Ground texture (except the classification boundary, FLO-02), GroundEl/MAF (see
[GroundEl / MAF](groundel-maf.md)), OKS roof and stylobate greenery (part of the OKS), UCX
construction (see [UCX](ucx.md)) and package production.

**Readiness:** [roadmap §7.12](../../research/capability-roadmap.md#712-flora--l0--same-three-sub-areas-lower-priority)
records **L0**. This sheet is T-FLO-1, the L1 rule index; the `model-flora` skill (T-FLO-3) and
a Flora benchmark (T-FLO-4) are missing, so full L1 is not claimed. No Flora check exists beyond
generic Ground-scene subsets, so area L2 is not claimed; no user-accepted Flora case establishes
L3. **Future etalons:** the user's 3ds Max Flora library (NPM and VPM versions) and the project
planting schedules (PDF/DWG species lists) are the intended etalons for identification (T-FLO-2)
and the benchmark (T-FLO-4); none is identified or stored in the repository yet.

**Reading:** the table is an index, not replacement rule text. `reg p.N` is the one-based
physical page of [the supplied regulation](../../../standards/source/Rasporyajenies19012026trebovaniya(2).pdf);
`§S.I` is the table section printed in the left column of that page, then the item. Decisions
are indexed in [docs/decisions.md](../../decisions.md). The NPM regulation has a separate
`Flora` mesh and texture set; **the VPM regulation names no Flora object**: vegetation is part
of the Ground file and follows the Ground masks and texture contract. `L2 coverage` names
implemented checks only, with their limits; `none` means no automatic check for the complete row
today (a manual gate is not L2). Coverage was checked against
[the implementation inventory](../validation.md#implementation-status-inventory-static-audit),
[`scene_findings`](../../../src/twinqa/scene.py) and [`png.py`](../../../src/twinqa/png.py).
Conflicts are pointed to [conflicts.md](../conflicts.md), not decided here.

| Requirement | reg page | NPM | VPM | How it is checked | L2 coverage | Detail in |
|---|---|---|---|---|---|---|
| FLO-01 — Flora definition and membership | reg p.1–2 §2; reg p.21 §2 | Vegetation model = polygonal objects for all greenery roughly 2× or more above lawn level: bushes, trees, tall herbaceous plants, flower beds; lawn-level beds and grass are Ground texture; roof and stylobate greenery belongs to the OKS; plot or stage boundary as for Ground | Greenery (`озеленение`) is a mandatory Ground element when present in the project; roof and stylobate greenery belongs to the OKS; same plot or stage boundary | Manual inventory of the planting plan against the model, with lawn-level / above-lawn and roof / ground classification | none | [Profile terms](../npm-vpm.md#terms) |
| FLO-02 — Flower beds: texture or models | [D101]; reg p.1–2 §2 | Flower beds / small greenery named only as such in the specification are Ground texture; beds whose plants are listed are 3D models; big bushes always models | Same project rule | Manual comparison of the specification wording with the chosen representation | none | [Flora practice](../geometry.md#flora-project-practice-source-187-grilling-rounds-1-2-with-user-artem), [D101](../../decisions.md) |
| FLO-03 — Approved design, both profiles complete | reg p.4 §1.3; reg p.24 §1.3 | All greenery of the approved project present, implemented fully and identically in NPM and VPM | Same | Manual V015 against the approved drawings and the planting schedule; paired-profile count of plants, not topology equality | none | [Common profile contract](../npm-vpm.md#common-to-both), [manual QA](../validation.md) |
| FLO-04 — Species, size and colour match | [D099] | Species as in the planting schedule; height and crown diameter within ±20 %; leaf / flower colour per specification, otherwise per a photo search of the species name | Same | Manual comparison of measured height and crown diameter with the schedule; colour by eye against the specification or reference photo | none | [Flora practice](../geometry.md#flora-project-practice-source-187-grilling-rounds-1-2-with-user-artem), [D099](../../decisions.md) |
| FLO-05 — Ground FBX composition | reg p.6–7 §1.5; reg p.26 §1.4 | Ground FBX (≤ 22 texture sets) holds a separate vegetation geometry object containing all vegetation of the scene, with 1 texture set | Vegetation is inside the single Ground file with its other elements; no separate vegetation object or file is named | Manual object / material inventory of the exported Ground FBX | none | [NPM structure](../npm-vpm.md#npm-appendix-1), [VPM structure](../npm-vpm.md#vpm-appendix-2) |
| FLO-06 — NPM shared triangle budget | reg p.7 §3.6; [D097] | Ground + GroundEl + Flora total ≤ 180 000 triangles, not a Flora allowance; project starting split surface 50k / MAF 60k / Flora 70k [D097] | See FLO-07; do not reuse the NPM ceiling | Sum exported triangles of the complete Ground FBX; the split is a planning target, not a regulation limit | V003 — `scene_findings`, NPM `role=ground` total only | [Profile budgets](../npm-vpm.md#npm-appendix-1), [implementation](../../../src/twinqa/scene.py) |
| FLO-07 — VPM Ground budget | reg p.28–29 §3.10; [D010] | See FLO-06 | Ground limit by site area (S_ter − S_pz), excluding UCX, from 300 000 (≤ 0.05 ha) to 4 500 000 (> 1.5 ha) triangles; no separate vegetation allowance | Manual site-area calculation and whole-Ground triangle sum; V003 returns `review` for this limit | none | [VPM budget](../npm-vpm.md#vpm-appendix-2), [C1, decided by the user](../conflicts.md#a-inside-the-regulation) |
| FLO-08 — Vegetation texture set | reg p.10 §5.13; reg p.9 §5.2 | One texture set for all vegetation, ≤ 2048×2048 px; only the diffuse map and, if needed, the opacity map | No Flora-specific set; Ground UDIM texture contract applies | Manual set grouping over all Flora materials, image dimensions and map list; generic NPM size helper does not enforce the Flora set count or map list | none | [NPM textures](../uv-textures.md#npm-textures-app1), [VPM textures](../uv-textures.md#vpm-textures-app2), [C18, open](../conflicts.md#b-regulation-vs-local-yaml--docs) |
| FLO-09 — Texel density applicability | reg p.10 §6.2; reg p.31–32 §6.1–6.2 | Density requirements do not apply to vegetation geometry | No vegetation exemption stated: density applies to diffuse maps only (ERM, normal and placeholders exempt), 512–1706 px/m; for maps using the alpha channel a higher density from the range is recommended | Manual target classification (NPM) and metric UV inspection (VPM); V009 unimplemented | none | [Density applicability](../uv-textures.md#npm-textures-app1), [VPM density](../uv-textures.md#vpm-uv--udim) |
| FLO-10 — Geometry technique | reg p.7 §3.1; reg p.29 §3.16; [D102] | Minimum triangles for the silhouette; minor detail as texture on the atlas; project route: a bush is a "star" of textured planes (FLO practice) | Vegetation realistic, no stylization; recommended: model trunk and main large branches, small twigs and leaves as planes with an alpha-channel texture; default VPM bush = shell of the NPM star, a detailed bush only on request [D102] | Manual silhouette and realism review against the reference; triangle counts per plant from the library audit | none | [Geometry rules](../geometry.md#regulation-geometry-rules-both-profiles-unless-noted), [D102](../../decisions.md) |
| FLO-11 — Opacity and two-sided planes | reg p.9 §5.5, §5.8; reg p.36 §12.1–12.3 | Alpha channel forbidden; a separate opacity map only when transparent elements exist; no duplicated-offset thickness | Cut-outs as a black-and-white map (0–127 invisible, 128–255 visible) baked into the diffuse alpha; planes seen from both sides duplicated with a 0.003–0.01 m offset and flipped normals | Manual map and plane inspection per profile; do not share one export between profiles | none | [Geometry](../geometry.md#regulation-geometry-rules-both-profiles-unless-noted), [C7/C8 and C21](../conflicts.md) |
| FLO-12 — Mesh naming | reg p.10–11 §9.1; reg p.11 §10.1–10.2; reg p.11–12 §3.3; reg p.33 §10.1–10.3, §4.2 | `SM_{Address}_Flora` (suffix `_Flora` = vegetation); ≤ 254 characters; Latin, digits, underscore | No Flora mask: vegetation meshes follow `SM_{Address}_Ground`; same length and character rules | Manual internal-name inventory; V012 checks package names, not mesh masks | none | [NPM names](../geometry.md#naming---npm-reg-p10-13), [VPM names](../geometry.md#naming---vpm-reg-p33-36) |
| FLO-13 — Texture and material naming | reg p.11 §9.2; reg p.12–13 §3.4–3.5; reg p.34 §4.3–4.4 | `T_{Address}_Flora_d_1.png`, `T_{Address}_Flora_o_1.png`; material `M_{Address}_Flora_1`; editor names identical to PNG names | Ground masks `T_{Address}_Ground_{TypeTexture}_{Slot}.{UDIM}.png` and `M_{Address}_Ground_{Slot}` | Manual material / image name inventory against the masks | none | [NPM names](../geometry.md#naming---npm-reg-p10-13), [VPM names](../geometry.md#naming---vpm-reg-p33-36) |
| FLO-14 — NPM texture embedding | reg p.9 §5.1 | Flora PNG atlas embedded in the Ground FBX | Not applicable; external PNG maps in the Ground archive | Readback of packed-image flags; pixel extraction remains separate | V006 — `scene_findings`, embedding flags only | [NPM textures](../uv-textures.md#npm-textures-app1), [implementation limits](../validation.md#implementation-status-inventory-static-audit) |
| FLO-15 — No collision for vegetation | reg p.6–7 §1.5; reg p.36 §13.2 | No UCX: the NPM Ground FBX composition lists no collision geometry | Collision is built for the Ground surface only; vegetation (with MAF and lighting) is not taken into account | Manual check that no UCX mesh covers plants and that Ground-surface UCX remains | none | [Collision targets](../geometry.md#collision--ucx-vpm-only-npm-has-none-unless-customer-spec), [UCX sheet](ucx.md) |
| FLO-16 — Export triangulation | reg p.8 §3.11; reg p.29 §3.17 | Triangulated geometry in the derived FBX | Same | Read back face degrees from the export, not the editable master | V003 — `scene_findings`, triangulation only | [Geometry rules](../geometry.md#regulation-geometry-rules-both-profiles-unless-noted) |
| FLO-17 — Placement and transforms | reg p.10 §8.1–8.2; reg p.32–33 §9.1–9.5; [D100] | Moscow project coordinates and heights; plants on SPOZU points: authoring pivot slightly above the lowest point so the plant sinks 10 cm into the Ground; random Z rotation and scale ±10 % inside the ±20 % tolerance; transforms applied in the delivery | Same seating; then zero rotation, Ground-local origin and shared pivot of the Ground FBX | VPM rotation / scale / pivot subset via readback; manual seating depth and NPM georeferencing | V004 — `scene_findings`, applied rotation / scale subset; V013 — `_pivot_findings`, VPM origin / shared-pivot subset; V014 unimplemented | [Placement](../geometry.md#units-coordinates-pivots), [Flora practice](../geometry.md#flora-project-practice-source-187-grilling-rounds-1-2-with-user-artem), [D100](../../decisions.md) |

## Project practice

**Project practice, not regulation.** Source: the user's Flora grilling [D099, D100, D101, D102], rounds 1–2, 2026-10-15,
recorded in decisions issue [#187](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/187);
numbers carry their decision ids. Where a point has no decision id it is the user's described
working method from the same grilling, not a fixed rule.

- **Library.** One 3ds Max scene holds all Flora models, like the MAF library; each plant has an
  NPM and a VPM version, labelled on the left with Text objects giving plant type, NPM/VPM and
  dimensions. Triangle counts per tree and bush are taken from the library by audit, not invented
  ([#187](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/187), round 1 Q1, Q3).
- **Matching the planting schedule.** The model is the species of the schedule with its look
  (e.g. a red-leaved maple stays red-leaved); height ±20 % and crown diameter ±20 %; colour per
  the specification, otherwise per an internet photo search of the species [D099].
- **NPM and VPM technique.** NPM bush = a "star": one plane with the atlas texture and opacity,
  duplicated around the centre. VPM bush = by default a shell of that star; a more detailed,
  higher-polygon VPM bush only on explicit request; the agent studies the library VPM bushes and
  follows their logic, the default stands until then [D102].
- **Atlas route (2048).** By script or by hand: a reference image of the plant → a generated 2K
  front view on white without shadows → cut-out → black-and-white opacity → placed on the atlas,
  built up step by step. Agents may repeat this route with the image-generation tool; every new
  texture goes to the user for review before it enters the atlas, at least for the first 10–20
  species ([#187](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/187), round 1 Q4,
  round 2 Q9). The regulation cap stays FLO-08.
- **Flower beds.** Ground texture when the specification just says "flower beds" / small
  greenery; 3D models when it lists what is planted; big bushes are always models [D101].
- **Placement.** SPOZU points carry no rotation; the pivot goes on the point, slightly above the
  lowest point, so the plant sinks 10 cm into the Ground when projected (same as MAF [D095]);
  clones get a random Z rotation and scale ±10 %, inside the ±20 % tolerance; the delivered FBX
  still resets transforms and shares the profile origin [D100].
- **Budget start.** Inside the NPM 180 000 Ground total, the project starts from Flora 70k
  [D097]; this is a planning split, not a regulation limit.

## Source-image evidence

**17 requirement rows.** All numbers, units and limits from the regulation were visually checked
on PyMuPDF-rendered pages, not taken from OCR. Local renders: `C:/x/l1-evidence/flora/pNN.png`
(outside the repository, not committed, not needed to follow this sheet). PyMuPDF 1.28.2,
matrix `(1.6, 1.6)`, no alpha. Reproduce with
`uv run --extra pdf-review python` and
`pymupdf.open(...)[n - 1].get_pixmap(matrix=pymupdf.Matrix(1.6, 1.6), alpha=False).save(...)`.
Visually inspected pages: 2, 4, 6, 7, 9, 10, 11, 12, 13, 21, 24, 26, 28, 29, 31, 32, 33, 34, 36, 46.
Numbers from decisions ([D097], [D099], [D100]) are attributed to the user, not to a page.

Five short verbatim quotes transcribed from the images (Russian kept intentionally):

- **FLO-01 — reg p.2 §2:** «Модель растительности (далее – растительность). Выполняется в виде полигональных объектов»; «выше газона примерно в 2 и более раз: кусты, деревья, высокие травянистые растения, клумбы и пр.»
- **FLO-06 — reg p.7 §3.6:** «для благоустройства, его элементов и элементов растительности в сумме – 180 000».
- **FLO-08 — reg p.10 §5.13:** «один текстурный набор карт на все элементы, размером не более 2048x2048 пикселей»; «исключительно карта диффузного цвета и, при необходимости, карта прозрачности».
- **FLO-12 — reg p.12 §3.3:** «для растительности SM_Address_Flora» (example `SM_ProezdNansena_ZU_8_Flora`).
- **FLO-15 — reg p.36 §13.2:** «(наземные части: МАФ, элементы освещения и растительность в ней не учитываются)».

Further checked numbers: FLO-07 table 300 000 (≤ 0.05 ha) … 4 500 000 (> 1.5 ha) on p.28–29;
FLO-09 diffuse-only scope (p.31 §6.1), 512–1706 px/m and the alpha-channel recommendation on p.32; FLO-10 trunk / branches /
alpha planes on p.29 §3.16; FLO-11 alpha forbidden (p.9 §5.5), 0–127 / 128–255 and
0.003–0.01 m (p.36 §12.1, §12.3); FLO-12 ≤ 254 characters (p.11 §10.1); FLO-13 `Flora_d_1`,
`Flora_o_1`, `M_..._Flora_1` (p.13). The VPM vegetation examples are Fig. 6.1 on p.46.

## L2 gaps

The table has **17 rows**: **13** with `none` and **4** with partial coverage (FLO-06, FLO-14,
FLO-16, FLO-17). Every `none` row is listed; these are L2 ticket candidates, **not filed tickets**:

- **FLO-01:** above-lawn / lawn-level and roof / ground classification of greenery against the planting plan.
- **FLO-02:** specification-wording rule for flower beds as texture or models [D101].
- **FLO-03:** completeness against the approved design and paired NPM/VPM plant count.
- **FLO-04:** species, height / crown ±20 % and colour match against the planting schedule [D099].
- **FLO-05:** NPM separate vegetation object with one set; VPM vegetation inside the Ground file.
- **FLO-07:** VPM site-area calculation and hard Ground budget (C1 decided [D010]).
- **FLO-08:** one Flora set, ≤ 2048 px, diffuse + optional opacity only (C18 open).
- **FLO-09:** NPM density exemption for vegetation; VPM density on vegetation planes.
- **FLO-10:** silhouette economy, VPM realism and star / shell technique [D102].
- **FLO-11:** profile-aware opacity (NPM separate map, VPM diffuse alpha) and two-sided plane offset.
- **FLO-12:** internal mesh masks (`SM_{Address}_Flora` NPM, Ground masks VPM) and name syntax.
- **FLO-13:** Flora texture / material names and editor-to-PNG correspondence.
- **FLO-15:** absence of collision on vegetation while the Ground-surface UCX remains.

Partial rows also leave work: FLO-06 checks the Ground total, not the Flora 70k planning split;
FLO-14 checks embedding flags, not Flora pixels; FLO-17 does not check the 10 cm sinking, the
±10 % clone scale or NPM georeferencing. T-FLO-4 still waits for identified etalons from the
user's Flora library and planting schedules; no species, dimension or library identity is
invented here.
