# TEC26 AC06 — material-ID Gate 1

## BUILD override — presentation authority (supersedes historical statements below)

**Built for review, not a passed AGR delivery.** The latest Artem answers on card
`t_6af403e8` (2026-10-22 16:37–16:39) govern: presentation slide39/40 first;
DWG/PDF only where the slides are silent. Historical Gate-1 fields and its old
solid-grey statements below are retained as history, not the current recipe.
BUILD authorization is the orchestrator note, not `build_allowed` in that packet.

| Hatch / region | Material | RAL / exact KPP RGB | Texture |
|---|---|---|---|
| Blue facade hatch, canopies | Sandwich panels | 5015 / 34,113,179 | Same approved source profile; vertical ribs |
| Light-grey wall hatch | Sandwich panels | 7047 / 208,208,208 | Same profile/noise recoloured, vertical ribs |
| Doors, porches, plinth, drainage | Painted metal / concrete | 7004 / 150,153,146 | Solid |
| Relief-glazing frames | Painted frame | 9016 / 246,246,246 | Solid |
| Sloping roof | Roof panels | 7004 / 150,153,146 | Solid, per explicit roof/fascia answer |
| Below-zero perimeter drop | Same source ID10 | 7047 / 208,208,208 | Plain; no ribs below zero |

| Original ID / region | Current finish | Source polygons / evidence |
|---|---|---|
| ID1 vertical fascia | Blue ribbed 5015 | 85; slide39/40 and explicit answer |
| ID1 other roof faces | Grey 7004 | 96; explicit answer; no vertex/ID change |
| ID2 sandwich canopies + broad vertical fascia | Blue ribbed 5015 | 177; legend; all 39 faces of three canopy components included |
| ID2 thin trims / snow guards | Blue solid 5015 | 494; same geometry, colour preserved |
| ID3 walls | Light-grey ribbed 7047 | All 300; legend, never plain grey |
| IDs4,6,7 | Solid 7004 | Same approved Gate-1 mapping |
| IDs5,8,9 | Solid 9016 | Same approved Gate-1 mapping |
| ID10 | Plinth7004 / below-zero plain7047 | Same approved split, same ID |
| ID11 / ID12 | Interior / map-free glass | Same source objects; glass alpha0.5 |

The ID2 classifier is **source-bound**, not a general material recognizer: broad
vertical faces have height/width >0.08m; canopy components lie entirely below
3.0m (actual maximum 2.902m; next roof-trim component begins at3.081m).
The source dump is pinned by the build manifest. New geometry needs a new mapping.

Slide39 line spacing is approximately8.53px over465px/10.9m; slide40 approximately
8.53px over575px/13.5m. Nominal step0.20m; full grids **55 /55 /68 /68 bays**
(A–D /D–A /1–3 /3–1). These are full grid bays, **not equal counts of visible
black pixel strokes**: pipes, canopies and windows occlude some positions.
The supplemental `export-grid-probe.json` independently verifies888 vertical
triangles per export and55/55/68/68 full rib centres, phase residual≤1.39µm.
No AC08 0.60m grid was copied. Both colours retain the same eight-pixel source
joint profile; only400 flat pixels per original600px period are removed.
There are no horizontal panel joints. Source image SHA256 is in `vpm_textures.json`.

New evidence: `G:/Мой диск/AGR-evidence/tec26-oks/AC06/build-v006/`:
`contact-sheet.png` (12 swatches, labels outside), `compare/` (flat colour),
`compare-cavity/` (edge-shaded preview), `renders/` (including full drop),
`audit-v006-final.json`, raw `qa_packages.json`, public validator reports and
`SHA256SUMS.txt`. Plates use slide|VPM|NPM at42.6px/m and retain discrepancies.
The slide39 top roof strip is blue in the graphic while the built sloping roof
is grey by the explicit answer; **this is visible, not retouched or called an
exact slide match**. User visual approval and final SINTEZ are pending.

See [BUILD_REPORT.md](BUILD_REPORT.md) for measured exports and remaining failures.

---

**Status: `approved-gate1`. Artem, 2026-10-22, approved colouring (`approved`: true). `build_allowed` stays false: VPM/NPM are a later card, and this packet must not start a build.**

Building name, read from the supplied PDF title block and DWG layout `3`, entity
`19C767`: **Пункт редуцирования газа 1**. Drawing code `22E56-АР2-1002-AC.06`.
Pilot `origin/main` at start: `442f0b695a91f9abc180783c26978fbe85fefcf9`.
Target downstream: both NPM/VPM; this card produces neither.

## Authority (operator decisions during this card)

DWG **R1 governs finishes**; PDF fills only missing DWG information. Same-DWG
model legend/title block apply; no other-building/template finish note was used.
The scene geometry is final: dimension discrepancies do not authorize geometry
changes or block this texture task. No dimension conflict was adjudicated here.
Actual census layer names/handles are authoritative. Blue RAL 5015 sandwich wall
panels take vertical joints only (see “Panel texture rules (supersede solid-without-joints)”);
count and step stay `?` until this building’s colour sheet dimensions them. RAL 7047
wall panels stay solid colour. Glass: **KPP M_Glass_01, NPM alpha 0.5,
VPM per standard**. Keep the required perimeter drop below zero on the same ID,
without cutting or adding IDs. Gate 1 colours that drop as wall colour.

Gate 1 (Artem, 2026-10-22) approves colouring only. Geometry, topology, UCX and
multisub IDs stay exactly as in the source scene. This card does not build VPM
(UDIM) or NPM (2048 atlas). `build_allowed` remains false so a later card, not
this packet, is what may build. Same RAL as KPP uses the exact KPP colour.

## Sources and sheet locators

Copies: `C:/x/tec26-oks/AC06/sources-v001/`. Exact input hashes and byte sizes are
in `materials.json.inputs`; external `SHA256SUMS.txt` covers the evidence copies.
Originals were not edited. PDF and DWG source/copy hashes were compared again
at publication. No RAL was inferred from a mesh colour or generic material name.

- `22E.pdf`: one raster physical page, **printed sheet 2**, “План на отметке 0.000.
  План кровли”. Evidence `drawing-p1.png` is 3572×1684 pixels. Title block region:
  `(2460,1320)-(3565,1680)`. Panel legend: `(2880,380)-(3545,760)`.
- PDF legend: three-layer sandwich panels with basalt-based mineral-wool infill,
  **120 mm**. Roof is labelled sandwich panels. PDF does not specify RAL.
- `22E56-АР2-1002-AC.06_R1.dwg`: read-only text extraction through locked
  `dcc_batch.py acad`, AutoCAD **2025**, `ACADVER=25.0`, `INSUNITS=4` (mm).
  Receipt: `acad-text-run-v001.json`; extraction: `dwg-text-v001.txt`.
- Facades in DWG Model: `BA82E` = 1–3 at `(146296.0,76333.4)` mm;
  `DBF13` = 3–1 at `(147861.0,67031.4)`; `19C226` = А–Д at
  `(121003.0,76333.4)`; `19C227` = Д–А at `(121067.0,67031.4)`.
- Roof plan `FD2FE` at `(148494.0,24594.5)` mm. Section 1–1 `19DB85` at
  `(149595.0,-2842.8)`; also `1A42F2` at `(193784.0,122228.0)`.
  DWG paper layout `3` title is “Разрез 1-1”, entity `19C770`.
- Finish legend **`136EBB`**, Model `(119514.0,54096.4)` mm:
  sandwich panels/canopies **RAL 5015**; sandwich panels **RAL 7047**;
  porches, doors, plinth, rainwater system **RAL 7004**;
  lightweight relief-construction frames **RAL 9016**.
- DWG panel specification `14741E` at `(118487.0,46630.7)` mm;
  reinforced-concrete slab `147424` at `(118487.0,44173.1)` mm.
  No other finish/RAL text was found by the text traversal; proxy graphics and
  absent external references are not a proof of completeness.

Shared #558 `ac06.dxf` is truncated (no ENDSEC/EOF); normal ezdxf read failed.
An independent `ezdxf.recover` diagnostic retained 21942 Model entities, with
2 fixes / 0 remaining auditor errors. `dwg-facades-recovered.png` is supplemental:
proxy SHELL colour support warns, paper layouts are incomplete. Its colours and
missing geometry are **not** authoritative evidence. The finish legend above was
read directly in AutoCAD from the DWG copy, not inferred from recovery.

## Scene census (readback, not a new scene build)

Reused #558 `C:/x/tec26-oks/census/oks.json` and geometry readbacks from
`C:/x/tec26-oks/max-readback-v002/`. Source scene copy:
`C:/x/tec26-oks/sources-v001/Vlad_OKS/04-09 Geometry Final.max`.
3ds Max 2026.3 census; source file version `[26000,26000]`; metres, 1 unit/m, Z up.
Actual layer **`006`** is authoritative per operator clarification; no layer question.

- `АС.06`, handle 170: 3118 vertices, 5596 triangles; Multi/Sub `Material #6`,
  12 slots with actual IDs 1–12. All IDs 1–11 occur on this mesh.
- `АС.06_Glass`, handle 378: 24 vertices, 12 triangles, material ID 12.
  Main's unused slot 12 is used by Glass. No empty submaterial slots or unused IDs for the combined building.
- 21 `Colizii_*` objects on layer 006, listed with handles/counts in JSON.
  They are **collision candidates**, not verified/renamed UCX delivery objects.
- ID measurements are triangle counts and triangulated surface area in m²,
  **not** Editable Poly polygon counts, net facade quantities or unique exposed area.
- Final Gate views are **Blender 5.1.2, headless Cycles CPU**, depth-correct,
  with UCX excluded, a gold world-space **±0.000 m** reference, and neutral shaded
  views alongside ID colours. All 5608 source triangles reconstructed from the
  exact readback; no source scene/geometry changed. ID glass opaque diagnostically;
  neutral shading is not final finish/glass preview. No production scene saved.
- Earlier painter projections are archived diagnostics, **not Gate images**:
  they could falsely show hidden/interior triangles across the roof.
- ID 10 contains the **required perimeter drop**, reaching **−2.025103807 m**.
  The ID stays 10: no new ID and no geometry change. The approved plinth finish
  remains RAL 7004. The drop below ±0.000 takes wall colour (ID 3, RAL 7047)
  by a UV/atlas region or a face-group split inside the same ID. Mixed IDs may
  also carry roof 7004 and frame 7004 the same way. Independent triangle/height-plane
  intersections show complete four-side rectangular perimeter coverage at **0 and
  −1 m: 8/8**. `perimeter-drop-probe.json` records spans, gaps and side minima.
  Coordinate tolerance 0.0001 m handles roundoff, not modelling movement. This is
  reach evidence, not whole-model topology or export acceptance.

## Material-ID table

Legend **L** = DWG `136EBB` locator above. **V** = `depth-iso.png` and
`depth-reverse.png`, labelled depth-correct shaded/ID pairs. **I** =
`depth-isolated.png`, seven isolated groups with shaded/ID comparison.
**C** = measured census
`objects/handle=170` (ID 12: handle 378). The JSON preserves full precision.
All twelve IDs are **Gate-1 approved** colour assignments. Same RAL as KPP uses
the exact KPP colour. No approved ID is a blue RAL 5015 sandwich wall panel, so
none were switched to joints. ID 3 stays solid RAL 7047. ID 2 stays metal RAL 5015
canopies and trims. Rib count and step on the colour sheets are `?`.

| Material ID | Triangles | Area m² | Finish / RAL | Map type | Evidence / open point |
|---|---:|---:|---|---|---|
| 1 | 362 | 177.127566 | Roof sandwich panels and upper fascia / 7004 | solid | C,V,I; KPP 7004, not 5015 |
| 2 | 1290 | 83.268399 | Canopies and roof trims / 5015 | metal | C,V,L |
| 3 | 444 | 94.417866 | Wall sandwich panels / 7047 | solid | C,V,L; RAL 7047, not the blue 5015 wall panel; stays solid |
| 4 | 1576 | 4.984936 | Rainwater downpipes / 7004 | metal | C,V,I,L; vertical pipes/elbows |
| 5 | 48 | 0.697030 | Strips over entrances / 9016 | solid | C,I; luminaires, colour only, no emission |
| 6 | 300 | 3.303690 | Ventilation assemblies / 7004 | metal | C,V,I; five ventilation assemblies |
| 7 | 204 | 5.655707 | Doors / 7004 | metal | C,V,L |
| 8 | 1008 | 21.514535 | Relief-glazing frames / 9016 | metal | C,V,L |
| 9 | 60 | 7.950371 | Window reveals / 9016 | solid | C,I; three perimeter reveal rings, not drainage |
| 10 | 176 | 105.289011 | Plinth / 7004; drop below ±0.000 = wall colour 7047 | solid | C,V,L; same ID, no geometry change |
| 11 | 128 | 116.797765 | KPP Interior | solid | C,I; visible interior box; KPP Interior tile 1011 |
| 12 | 12 | 32.651300 | Glazing as KPP | glass | C,V; M_Glass_01, NPM alpha 0.5, VPM standard |

Audit correction: initial contextual painter-view interpretation misclassified
ID 9 as drainage and left ID 4 unidentified. Isolated geometry proved ID 4 is
vertical downpipes and ID 9 window reveals. Tests-first commits `3640c92` and
`1e29ce8` preserve the ID correction and depth/drop regression. Final table
supersedes that first interpretation. Every ID 1–12 is approved; none remain `?`.

## KPP colour reuse (no invented RAL conversion)

`jobs/KPP1/materials.json` supplies the existing finish-to-tile identity. Actual
`maps_kpp/T_Kpp_1_Diffuse_1.<tile>.png` pixels supply colours. Each swatch uses the
**most frequent exact RGB pixel** from its source map; source hashes, counts and
method are retained in JSON. This is KPP colour reuse, not a calibrated RAL sample
or permission to copy KPP cassette construction onto AC06 sandwich panels.

| RAL | Existing KPP finish | Tile | Exact reused RGB |
|---|---|---:|---|
| 5015 | Metal_RAL5015 | 1013 | 34,113,179 |
| 7047 | Cassette_RAL7047 | 1006 | 208,208,208 |
| 7004 | Plinth_RAL7004 | 1001 | 150,153,146 |
| 9016 | Frame_RAL9016 | 1009 | 246,246,246 |

## Evidence and checks

Evidence folder: **`G:/Мой диск/AGR-evidence/tec26-oks/AC06/evidence-v004/`**.
Geometry renders stay there. Contact-sheet swatches for ID1 (7004) must match
KPP 7004 (exact RGB 150, 153, 146 from Plinth_RAL7004, tile 1001). The v004
sheet still hatches the pre-approval gaps and is not the approved swatch set.
Approved swatches: `G:/Мой диск/AGR-evidence/tec26-oks/AC06/evidence-v005/contact-sheet.png`.
That folder is a copy of v004; v004 was not overwritten. The ID1 swatch pixel is
KPP 7004 RGB 150, 153, 146. `evidence-v005/SHA256SUMS.txt` covers the copy.
Four depth-correct
building view pairs and seven isolated shaded/ID pairs, 22 raw Blender renders,
receipts, drawing PNG and scripts are alongside. No large binaries/Git LFS committed.
ID 11's neutral candidate uses separately hashed KPP Interior tile 1011; it is not
drawing evidence of the interior finish. Glass swatch is symbolic, not a tint.
Independent geometry count/area parity **12/12**, source/copy SHA256 **2/2**, frozen
input hashes **8/8**. External SHA256 manifest covers published evidence.

Regression RED at tests-first commit `c0d1f7a`: **5 failed** because the packet was
absent. Isolated correction RED: **1 failed** (`3640c92`); depth/drop RED:
**2 failed** (`1e29ce8`). Final focused receipt is recorded in PR/card.
One full suite on the pre-steering packet: **13354 passed, 1 failed, 19 skipped,
179 deselected**. Existing TOW02 <=10 s performance assertion measured **10.8 s**.
Exact test on detached starting main, import path verified: **1 passed in 6.58 s**.
This does not relabel the failed full run green. No checker/tolerance changes;
no final Gate-approved-head full suite is claimed.
Tests check this evidence snapshot only; they do not validate architectural mapping,
DCC render quality, UCX, VPM/NPM compliance or human acceptance.

## Gate-1 answers

Artem, 2026-10-22. Quoted verbatim:

```
Принимаю
1. Sandwich panels: solid colour without joints (module not confirmed in drawings).
2. Roof: RAL 7004 grey (as KPP 7004), NOT 5015.
3. Mixed ID: parts may be painted differently (roof 7004, frame 7004, plinth/drop = wall colour) without geometry change - via UV/atlas regions or face-group split inside the same ID.
4. Panels RAL 5015 = KPP blue, doors/frames/porches RAL 7004 = KPP grey, glass as KPP; drop below ±0.000 = wall colour.
AC06 specifically: ID1 roof 7004; ID5 strips over entrances RAL 9016 (luminaires: colour only, no emission); ID6 ventilation 7004; ID9 window reveals 9016; ID11 interior box = KPP Interior.
Scope (Artem): only colouring; geometry, topology, UCX and multisub IDs stay exactly as in the source scene. Later cards build VPM (UDIM) / NPM (2048 atlas); do NOT build them here. Geometry checks are reported only, never fixed.
```

Applied to AC06:

- ID 1 roof and upper fascia: solid RAL 7004, the exact KPP 7004 colour, not 5015.
- ID 5 strips over entrances: solid RAL 9016. Luminaires are colour only, no emission.
- ID 6 ventilation: metal RAL 7004.
- ID 9 window reveals: solid RAL 9016.
- ID 11 interior box: KPP Interior.
- IDs 2, 3, 4, 7, 8, 10 and 12 keep their existing proposals, now approved.
  ID 10 plinth stays RAL 7004. The drop below ±0.000 on that same ID takes wall
  colour (ID 3, RAL 7047) with no geometry change.
- Mixed-ID rule: roof 7004, frame 7004, plinth/drop = wall colour, painted by
  UV/atlas regions or a face-group split inside the same ID.

`build_allowed` stays false. Colouring is approved; building VPM/NPM is not.

Item 1 of the quote above (solid colour, no joints) is **`superseded_by`**
`panel_texture_rules` for blue RAL 5015 sandwich wall panels. The quote itself
is unchanged.

## Panel texture rules (supersede solid-without-joints)

Artem, 2026-10-22. These rules replace Gate-1 item 1 for every ID whose finish
is a blue RAL 5015 sandwich wall panel (`map_type` `solid` → `joints`, joint
style `vertical_ribs`). RAL 5015 metal canopies and trims stay as they are
unless they are wall panels. `build_allowed` stays false. This section records
the rule only; it does not build VPM or NPM.

1. Blue sandwich panels (RAL 5015): vertical joints only, no horizontal joints.
   Texel matches KPP VPM: 1000 px/m on a 4K UDIM. The same look is used in VPM
   (Diffuse + Normal) and in the NPM atlas (joints at least 1.5 px).
2. Joint count and step come from this building’s own facade «Цветовое решение»
   sheet, per facade. AC06 text evidence names the sheets and does not dimension
   count or step, so each facade is `?` with a question. AC08’s 30 ribs / 12 ribs
   at ~0.20 m are AC08-only and are not used here. 0.60 m is not invented either.
3. A darker frame band outlines each panel field (top, bottom and corners) as on
   the sheet. Doors stay RAL 7004. The plinth strip is grey.
4. `C:/x/tec26-oks/user-textures/panel_RAL5015_vertical_joints_4096.png` gives
   only colour, noise and the look of one joint (4096 px, mean RGB 34, 112, 177,
   joint 8 px). Joints are laid out per facade from rule 2, not tiled raw.
   Below ±0.000 (the perimeter drop) the colour is plain, with no joints.
5. Where a face does not fit one 4K tile, a clean edge loop or ring cut is
   allowed in the later build card. Quads stay. Silhouette, normals, UCX and
   IDs stay unchanged. Every cut is listed. Recorded here as a rule only.
6. Acceptance picture, later build card: each facade render next to the same
   facade of the sheet, same scale, with the rib count under both.

| Facade | Sheet title in DWG text | Rib count | Step | Question |
|---|---|---|---|---|
| 1-3 | Фасад 1-3. Цветовое решение (`BA82E`) | ? | ? | Count and step are not dimensioned in `dwg-text-v001.txt`. What are they? Do not copy AC08 ~0.20 m. |
| 3-1 | Фасад 3-1. Цветовое решение (`DBF13`) | ? | ? | Same question for this facade. |
| А-Д | Фасад А-Д. Цветовое решение (`19C226`) | ? | ? | Same question for this facade. |
| Д-А | Фасад Д-А. Цветовое решение (`19C227`) | ? | ? | Same question for this facade. |

Switched IDs: none. ID 2 remains metal RAL 5015 canopies and roof trims. ID 3
remains solid RAL 7047 wall sandwich panels. Open question: if the legend line
«Сэндвич-панели, козырьки - RAL 5015» includes wall-panel faces on another ID,
which ID are they?
