# TEC26 AC06 — material-ID Gate 1

**Status: awaiting Artem; no material approval, no build authorization.**

Building name, read from the supplied PDF title block and DWG layout `3`, entity
`19C767`: **Пункт редуцирования газа 1**. Drawing code `22E56-АР2-1002-AC.06`.
Pilot `origin/main` at start: `442f0b695a91f9abc180783c26978fbe85fefcf9`.
Target downstream: both NPM/VPM; this card produces neither.

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
Actual layer is **`006`**, not `0.0.0.6` / `0.0.6`: confirm the correspondence.

- `АС.06`, handle 170: 3118 vertices, 5596 triangles; Multi/Sub `Material #6`,
  12 slots with actual IDs 1–12. All IDs 1–11 occur on this mesh.
- `АС.06_Glass`, handle 378: 24 vertices, 12 triangles, material ID 12.
  The main mesh's unused slot 12 is not an unused ID for the combined building.
- 21 `Colizii_*` objects on layer 006, listed with handles/counts in JSON.
  They are **collision candidates**, not verified/renamed UCX delivery objects.
- ID measurements are triangle counts and triangulated surface area in m²,
  **not** Editable Poly polygon counts, net facade quantities or unique exposed area.
- Diagnostic `ids-{iso,reverse,roof,front}.png` are software orthographic projections
  of the census triangle readback. No native Max render or geometry edit was run.
  Painter sorting has no z-buffer: coplanar/interior triangles can show through.
  These views identify groups but do not prove topology, visibility or finish approval.

## Material-ID table

Legend **L** = DWG `136EBB` locator above. **V** = `ids-iso.png` and
`ids-reverse.png`, labelled colour legend for that ID. **C** = measured census
`objects/handle=170` (ID 12: handle 378). The JSON preserves full precision.
All non-`?` assignments are **proposals based on component correspondence**, not
approved assignments. Panel module/joint spacing has not been measured.

| Material ID | Triangles | Area m² | Finish / RAL | Map type | Evidence / open point |
|---|---:|---:|---|---|---|
| 1 | 362 | 177.127566 | ? | ? | C,V: roof/upper fascia; Q1 |
| 2 | 1290 | 83.268399 | Canopies and roof trims / 5015 (proposed) | metal | C,V,L; trim inclusion requires confirmation |
| 3 | 444 | 94.417866 | Wall sandwich panels / 7047 (proposed) | joints | C,V,L; panel rhythm not measured |
| 4 | 1576 | 4.984936 | ? | ? | C,V: small detail/hardware group; Q2 |
| 5 | 48 | 0.697030 | ? | ? | C,V: small bright detail group; Q3 |
| 6 | 300 | 3.303690 | ? | ? | C,V: ventilation assemblies; Q4 |
| 7 | 204 | 5.655707 | Doors / 7004 (proposed) | metal | C,V,L |
| 8 | 1008 | 21.514535 | Relief-glazing frames / 9016 (proposed) | metal | C,V,L |
| 9 | 60 | 7.950371 | Rainwater system / 7004 (proposed) | metal | C,V,L; confirm all faces are drainage |
| 10 | 176 | 105.289011 | Plinth / 7004 (proposed) | solid | C,V,L |
| 11 | 128 | 116.797765 | ? | ? | C,V: additional large surface group; Q5 |
| 12 | 12 | 32.651300 | Glazing (geometry identified; optics unknown) | glass | C,V; separate Glass object; Q6 |

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

Evidence folder: **`G:/Мой диск/AGR-evidence/tec26-oks/AC06/evidence-v001/`**.
`contact-sheet.png`: exactly one swatch per actual ID, no numbers inside swatches;
unknown finish/optical parameters are hatched, labels remain outside. Six coloured
swatches are proposals, not approvals. Four ID projections and the drawing PNG are
alongside the sheet. No large binaries are committed or stored in Git LFS.

Regression RED at tests-first commit `c0d1f7a`: **5 failed** because the packet was
absent. Focused GREEN and final suite receipts are recorded in the PR/card.
Tests check this evidence snapshot only; they do not validate architectural mapping,
DCC render quality, UCX, VPM/NPM compliance or human acceptance.

## Gate-1 questions for Artem — STOP

1. **ID 1**: roof planes and upper fascia — what roof material/RAL and seam layout?
   Does 5015 in the legend cover the roof or only the blue facade band?
2. **ID 4**: identify the small hardware/detail components; confirm material/RAL.
3. **ID 5**: identify the small bright components; confirm material/RAL.
4. **ID 6**: confirm ventilation assembly material/RAL and metal versus perforation.
5. **ID 11**: identify the large additional surface group (interior/underside?);
   confirm finish and whether it is required. Projection can show hidden surfaces.
6. **ID 12**: confirm glazing type, tint and optical properties; no frame colour or
   invented glass shader is substituted.
7. Confirm proposed IDs **2=5015, 3=7047, 7/9/10=7004, 8=9016** (including all
   faces of each ID), and reuse of the exact KPP colour pixels shown above.
8. Confirm layer **006** is the intended source for АС.06, with its Glass mesh and
   21 collision candidates; the card's dotted layer names are absent from the census.

Gate 1 remains open. **Do not build VPM/NPM or publish accepted materials** until
these questions are answered. A draft PR/evidence packet is not Gate-1 approval.
