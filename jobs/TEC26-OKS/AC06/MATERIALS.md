# TEC26 AC06 — material-ID Gate 1

**Status: awaiting Artem; no material approval, no build authorization.**

Building name, read from the supplied PDF title block and DWG layout `3`, entity
`19C767`: **Пункт редуцирования газа 1**. Drawing code `22E56-АР2-1002-AC.06`.
Pilot `origin/main` at start: `442f0b695a91f9abc180783c26978fbe85fefcf9`.
Target downstream: both NPM/VPM; this card produces neither.

## Authority (operator decisions during this card)

DWG **R1 governs finishes**; PDF fills only missing DWG information. Same-DWG
model legend/title block apply; no other-building/template finish note was used.
The scene geometry is final: dimension discrepancies do not authorize geometry
changes or block this texture task. No dimension conflict was adjudicated here.
Actual census layer names/handles are authoritative. Undimensioned panel module:
**solid colour, no invented joints**. Glass: **KPP M_Glass_01, NPM alpha 0.5,
VPM per standard**. Keep the required perimeter drop below zero, with the adjacent
plinth finish, without cutting or adding IDs.

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
  Keep proposed RAL 7004 plinth finish, no new ID. Independent triangle/height-plane
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
All non-`?` assignments are **proposals based on component correspondence**, not
approved assignments. Panel module/joint spacing has not been measured.

| Material ID | Triangles | Area m² | Finish / RAL | Map type | Evidence / open point |
|---|---:|---:|---|---|---|
| 1 | 362 | 177.127566 | ? | ? | C,V,I: roof/upper fascia; propose solid 5015, Q1 |
| 2 | 1290 | 83.268399 | Canopies and roof trims / 5015 (proposed) | metal | C,V,L; trim inclusion requires confirmation |
| 3 | 444 | 94.417866 | Wall sandwich panels / 7047 (proposed) | solid | C,V,L; no dimensioned joint module established |
| 4 | 1576 | 4.984936 | Rainwater downpipes / 7004 (proposed) | metal | C,V,I,L; vertical pipes/elbows |
| 5 | 48 | 0.697030 | ? | ? | C,I: six thin strips above entrances; propose solid 9016, Q2 |
| 6 | 300 | 3.303690 | ? | ? | C,V,I: five ventilation assemblies; propose metal 7004, Q3 |
| 7 | 204 | 5.655707 | Doors / 7004 (proposed) | metal | C,V,L |
| 8 | 1008 | 21.514535 | Relief-glazing frames / 9016 (proposed) | metal | C,V,L |
| 9 | 60 | 7.950371 | ? | ? | C,I: three perimeter reveal rings, NOT drainage; propose solid 9016, Q4 |
| 10 | 176 | 105.289011 | Plinth including perimeter drop / 7004 (proposed) | solid | C,V,L; keep below zero |
| 11 | 128 | 116.797765 | ? | ? | C,I: visible interior box; propose KPP Interior solid, Q5 |
| 12 | 12 | 32.651300 | Glazing as KPP (proposed) | glass | C,V; M_Glass_01, NPM alpha 0.5, VPM standard |

Audit correction: initial contextual painter-view interpretation misclassified
ID 9 as drainage and left ID 4 unidentified. Isolated geometry proved ID 4 is
vertical downpipes and ID 9 window reveals. Tests-first commits `3640c92` and
`1e29ce8` preserve the ID correction and depth/drop regression. Final table
supersedes that first interpretation. Unknown finishes keep canonical `?` even
when an explicit candidate is shown under hatching.

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
`contact-sheet.png`: exactly one swatch per actual ID, no numbers inside swatches;
unknown IDs 1/5/6/9/11 are hatched over explicit candidates; labels remain outside.
Six unhatched colour proposals and KPP glass are not approvals. Four depth-correct
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

## Gate-1 questions for Artem — STOP

Approve the proposals on the contact sheet; only five drawing gaps remain:

1. **ID 1 roof/upper fascia:** confirm proposed **solid RAL 5015**. The own DWG
   names 5015/7047 sandwich panels but does not explicitly assign roof colour.
2. **ID 5 six thin strips above entrances:** are these luminaires? Confirm proposed
   **RAL 9016** housing/diffuser, or provide their specification.
3. **ID 6 five ventilation assemblies:** confirm proposed **RAL 7004 metal**, or
   give actual finish/perforation specification.
4. **ID 9 three window perimeter reveals:** confirm proposed **RAL 9016** with
   the frames, or specify their distinct finish.
5. **ID 11 visible interior box:** confirm shown **KPP Interior** neutral, or
   provide the interior finish specification.

Panel joints are not blocking: supply a dimensioned module only if joints are
required later; until then solid colour is authorized. No redundant layer, glass
or below-zero geometry question.

Gate 1 remains open. **Do not build VPM/NPM or publish accepted materials** until
these questions are answered. A draft PR/evidence packet is not Gate-1 approval.
