# AC04 — Gate 1 material proposal

**Building (native DWG title):** «Локальные очистные сооружения поверхностных сточных вод».
Job `tec26-oks`, issue #561. Base `origin/main` at intake and resume:
`442f0b695a91f9abc180783c26978fbe85fefcf9`.
**Gate 1: awaiting Artem. No material assignment, model change or NPM/VPM build performed.**

## Sources and precedence

Hash-verified frozen copies: `C:/x/tec26-oks/AC04/sources-v003/`.
Full names, bytes and SHA256 are in `materials.json`; local `SHA256SUMS.txt` accompanies the copies.

| Input | SHA256 | Role |
|---|---|---|
| `22E56-АР2-1002-AC.04_R1.dwg` | `d34638d96ea51046e25b0376f4cd589c0725aeb15f2bccc4800ab3716b1a409b` | Governing finish/colour source, per orchestrator comment on this card, 2026-10-22 |
| `22Е56-АР2-1002-АС.pdf` | `97e324176ffc6c078f27849e98a08b530cbd1d07ddb3fe71b5fe66754dc1ccfe` | Supplemental plans, roof, section; one physical PDF page, printed sheet 2 |

The prior card comment called the DWG sheet 2. **Native readback corrects this:** layout `1`,
`E42B5` at (596.775, 23.6754) is sheet **1**, `E42BD` at (614.088, 23.5147) is the
**total of 2 sheets**. Title entities `E42B7/E42B8` at (508.101,28.4873)/(513.458,24.477)
name this building; `E4341` at (540.153,12.4066) names facades A–В, 1–2, В–A, 2–1 and colour solutions.
Coordinates here are layout millimetres; model coordinates below are drawing millimetres.

AutoCAD 2025 core console, `ACADVER=25.0`, `INSUNITS=4` (mm), opened the authorized copy
read-only through `dcc_batch.py acad --card t_ca2df933`. Native `entget` text readback contains
104 lines including header, title and legend; no extraction error, completion sentinel present.
`native-text-v002.txt` and full `native-run-v002.json` are in the evidence bundle.
Desktop originals remain hash-identical. The AutoCAD-opened v001 working DWG changed to
`253bdb2a9e2e2ddc64d79550b9e56f41035d3d025e1457947cb9e5ac5c4d2b75` after the session;
its bytes are NOT claimed preserved. The wrapper exit 0 did not prove immutability.
The native log shows `_QUIT`, `_N` and the discard prompt; the exact reason for copy mutation is
not established. A fresh v003 package was copied from the original and verified without another DCC open.
Native evidence records text from the original-revision working copy, not a certificate of the resulting DWG.

### Drawing facts and locators

| Evidence | Locator | Reading |
|---|---|---|
| Colour legend | DWG sheet 1; Model `170B10`, XY (52042.211,11555.882) | Sandwich panels and canopy RAL5015; porches/doors RAL7004; metal stair guards RAL1021 |
| Wall construction | Same DWG Model `170A72`, XY (51016.072,5498.213) | Three-layer sandwich panels, mineral-wool basalt infill, 150 mm |
| Enclosure note | Same DWG Model `B59E8`, XY (51016.072,3867.977) | Metal enclosing structures, 100 mm |
| Facade views | Model `1523A0..1523A3`, XY approximately (26073,55936), (26051,42344), (5257,55936), (5235,42344) | Own AC04 facade colour drawings; blue enclosure, yellow safety rail, grey entrance |
| Roof plan | Model `1A06DD`, XY (28962.926,-3242.342) | Roof plan heading; plan geometry supplementary, not a separate proven roof finish schedule |
| Plans / section | PDF physical page 1 / printed sheet 2; top-left plan, top-centre roof plan, top-right section 1–1 | Wall/roof sandwich construction shown; 120 mm appears in section callouts; not a finish override |
| PDF legend | Same page, lower centre, pixel region roughly x1870–2430,y1300–1600 in `pdf-sheet2.png` (3572×1684) | Sandwich with basalt mineral wool; metal enclosure 100 mm; reinforced concrete slab; reference marks |

`dwg-ac04-recovered.png` is a **diagnostic rendering of recovered DXF**, not a native plot certificate:
original DXF lacked ENDSEC; `ezdxf.recover` returned zero audit errors, with proxy SHELL face-colour warnings
when rendering. Native extraction independently verifies the actual text. Rendering shows no verified
joint-module dimension. White construction lines are not evidence of RAL9016 or perforation.
Other model-space template groups at x128000–222000 (legends `114EE3/114EE5`, `135AE3/135AE5`,
facades A–Б/Б–A) are excluded: they are not this object's A–В/В–A facade group.

**Dimension discrepancy retained:** DWG 150 mm vs PDF 120 mm. Orchestrator resolved its workflow impact:
existing mid-poly scene geometry is final; this card only proposes textures. No geometry correction
or silent drawing reconciliation. No unrelated standards conflict is decided here.

## Scene readback

Reuse #558 census `C:/x/tec26-oks/census/oks.json` and its existing `geometry-174.json` buffer;
no extra Max session, live scene access or reread of other buildings was needed.
Max 2026.3 census, metre system units, 1 unit/m, Z up. Source file version 26000.
`materials.json` pins hashes of scene copy, census and geometry.

Actual layer **004**, mesh **АС.04**, handle **174**, `Editable_Poly`, Multi/Sub **Material #35**.
2462 vertices, **2552 polygon faces / 5006 snapshot triangles**. UV channel 1 present.
Source IDs remain intact; these are not delivery SlotNumbers, UDIMs or the KPP IDs.
Empty Multi/Sub slots **6–10** have no material and no assigned faces; they stay empty.
17 collision meshes: handles **346–362**, same layer; all retained in the census inventory,
not included in finish-area sums or textured. UCX acceptance is not certified by this material report.

## Proposed ID mapping

**All rows are proposals awaiting approval**, not a claim that source diagnostic colours prove RAL.
Areas are snapshot triangle areas in m², not a facade bill of quantities.
`only-N.png` isolates the actual face set for each ID. Blender **5.1.2 Workbench** native renders
use the census world vertices without changing geometry; each image pairs depth-correct ID colours
with a plain shaded view from the same orthographic camera. UCX are excluded. The diagnostic perimeter
line is at **±0.000 m**, not a geometry cut. No .blend or delivery model was saved.

| ID / source material | Polygon faces / triangles | Area m² | Geometric reading | Proposed finish | Map type | Evidence / limits |
|---|---:|---:|---|---|---|---|
| 1 / `1` | 439 / 780 | 179.668028 | Outer structural strips/enclosure, roof, canopy and deep base | RAL5015 shell/roof proposal; full perimeter drop uses adjacent-wall blue | solid | `170B10`, `only-1.png`; operator relay of Artem decision, 2026-10-22: retain drop with adjacent-wall finish |
| 2 / `Material #36` | 19 / 38 | 82.702408 | Broad recessed wall-panel infill | Sandwich RAL5015 | solid | `170B10`, `only-2.png`; Q4: no invented cassette grid |
| 3 / `Material #37` | 2 / 4 | 0.238398 | Two small panes in the openings | `M_Glass_01`, NPM opacity 0.5 | glass | `only-3.png`, KPP glass policy in orchestrator comment; not a RAL claim |
| 4 / `Material #38` | 166 / 332 | 2.934883 | Door and small opening frames | Door RAL7004; propose same grey for frames | metal | `170B10`, `only-4.png`; Q3: frame colour not explicitly specified by legend |
| 5 / `Material #39` | 1926 / 3852 | 24.248557 | Roof railings, ladder/cage assembly | RAL1021 | metal | `170B10`, `only-5.png`; railing geometry is already present, no alpha/perforation map invented |

**Perimeter drop resolved by Artem (operator relay, 2026-10-22):** retain the part below ±0.000
in both VPM and NPM; use the same finish as the adjacent facade, not a separate new ID. For AC04
this is the ID1 blue RAL5015 proposal. The former Q2 about a separate plinth finish is withdrawn.
`perimeter-drop.json` checks all four external shell wall planes: their bottom-edge intervals cover
the full wall length at z ≤ −1.0 m (coordinate grouping tolerance 0.0001 m); minima are
−2.003179 to −2.003180 m. **4/4 walls verified.** No cutting, extending, renumbering or fallback assignment. No independent roof membrane brand, frame RAL9016,
perforation, cassette module or hidden interior finish is inferred from KPP.

### KPP colour identity

Use exact existing KPP pixels, not a newly sampled PDF or a new RAL conversion:

| RAL | Exact sRGB byte triplet | Existing `maps_kpp` Diffuse tile | Reuse |
|---|---|---|---|
| 5015 | 34,113,179 | `T_Kpp_1_Diffuse_1.1013.png` | Solid metal blue; same base tint as cassette 1007, without importing its joints |
| 7004 | 150,153,146 | `T_Kpp_1_Diffuse_1.1010.png` | Door grey |
| 1021 | 238,201,0 | `T_Kpp_1_Diffuse_1.1004.png` | Stair yellow |

All pixels in each selected solid tile were checked; SHA256 is in each material's `kpp_reference`.
KPP names/UDIM references come from `jobs/KPP1/materials.json` and `scripts/vpm_textures.json`.
These are the existing project's approximate sRGB RAL representations, **not calibrated physical RAL**.
No KPP cassette scale is transferred. Glass uses the named KPP-style material and constant NPM opacity;
VPM separation/no-map constraints remain for the later build, not certified here.

## Evidence and questions for Artem

Drive: **`G:/Мой диск/AGR-evidence/tec26-oks/AC04/gate1-v005/`**.
Open **`contact-sheet.png`** first: unnumbered finish swatches, ID labels outside swatches,
empty slots marked separately, ID-colour views and isolated face groups. The glass swatch is a schematic
translucency cue, not a measured/approved KPP glass tint or a rendered opacity test.
`iso.png`, `reverse.png`, `roof.png`, `only-1.png` … `only-5.png`, drawing diagnostic and PDF
are full-size companions. Diagnostic colours are deliberately distinct from finish swatches.
`evidence.json` lists the exact files, byte counts and hashes; Drive `SHA256SUMS.txt` is the checksum list.
The local native-render folder is `C:/x/tec26-oks/AC04/evidence-v005/`.
Earlier v002–v004 software diagnostic images are superseded by native Blender v005 pairs and are
not published as final Gate images. `blender-context.json` and the native render log record version,
engine and context. The render and verification scripts are included for reproducibility. Binary evidence is not committed and no LFS is used.

1. **Q1 — Mapping approval:** approve ID1/2 blue, ID3 glass, ID4 grey, ID5 yellow on the contact sheet?
3. **Q3 — Small frames:** approve RAL7004 for the small frames sharing ID4 with the specified grey door?
4. **Q4 — Panel joints:** approve solid RAL5015 without fabricated joints, or provide the dimensioned panel module?

Stop at Gate 1. Review, texture approval and delivery acceptance are separate; none is automatically passed.
