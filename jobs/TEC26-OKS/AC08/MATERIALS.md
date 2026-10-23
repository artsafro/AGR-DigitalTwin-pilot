# TEC26-OKS / AC08 — Gate 1 material proposal

**Building:** Контейнер низковольтных комплектных устройств (НКУ) (low-voltage switchgear container).
**Status:** Gate 1 approved by Artem 2026-10-22 (#565); the proposal below is the intake record. The binding
finishes are the facade legend that follows (machine form: `vpm_textures.json` `legend`, checked by
`finish_map.validate_legend` before textures, build and the acceptance renders).
**Pilot main at intake:** `442f0b695a91f9abc180783c26978fbe85fefcf9`.

## Facade legend (binding)

Authority (Artem 2026-10-22, all TEC26): the presentation slide «Схема фасадов ... Цветовое решение» decides
colours, bands, rib direction and rib count [D171]; the «Условные обозначения» legend of the colour sheets is
binding. AC08 = slide **49** of `deck.pptx` (`ppt/media/image78.png`, SHA256 `256f32da…08a8fd`): four blue ribbed
facades, blue edging with a thin dark outline, grey door on 2-1, grey plinth strip under every facade. No RAL 7047
sandwich and no RAL 9016 glazing frames exist on this building.

| Hatch (slide / DWG legend) | Material | RAL | Texture | Finish (ID) | Colour = KPP |
|---|---|---|---|---|---|
| Сэндвич-панель - RAL 5015 (blue rib field, slide 49; DWG 1395) | sandwich panel | RAL 5015 | ribbed: Artem's joint, 30 ribs long / 12 short (slide 49) | `PanelVJ30_RAL5015` (ID2, 1-2 / 2-1) | Metal_RAL5015 (34,113,179) |
| same | sandwich panel | RAL 5015 | ribbed: same joint, 12 ribs | `PanelVJ12_RAL5015` (ID2, А-Б / Б-А) | Metal_RAL5015 (34,113,179) |
| Edging of the sandwich wall (frame band, corners, top/bottom; slide 49 blue, dark outline) [D170] | sandwich wall edging | RAL 5015 | plain + dark field outline | `Frame_RAL5015` (ID1 above ±0.000) | Metal_RAL5015 (34,113,179) |
| Крыльца, двери - RAL 7004 (DWG 1397; slide 49 grey door) | door | RAL 7004 | plain | `Door_RAL7004` (ID3) | Door_RAL7004 (150,153,146) |
| Цоколь - RAL 7004 (slide 49 grey strip; legend rule «Крыльца, двери, цоколь, ... — RAL 7004») | plinth | RAL 7004 | plain | `Plinth_RAL7004` (ID1 at/below ±0.000) | Door_RAL7004 (150,153,146) |

## Sources and interpretation

The only file in the AC08 source directory is `22Е56-АР2-1002-АС.08.dwg` (679359 bytes).
No `_R1.dwg` or PDF exists there. Its verified copy is
`C:/x/tec26-oks/AC08/sources-v001/AC08.dwg`, SHA256
`cb90ed375df4fd708b7a69c6d018600347953245f0f6bde396f394bee3e1fa52`.
Originals were read only; the copy matches the original hash.

Per the orchestrator's rules posted on this card, the title block and the legend of this same DWG
apply; final scene geometry is not revised from template dimensions/elevations.

- Issued facade sheet **1**, title block proxy **514**, paper-space XY **(506.590,27.739)**:
  building name above; drawing number at **(527.313,52.500)** = `22Е56-АР2-1002-АС.08`.
  Sheet number `1` at **(596.844,23.750)**. View titles: Facade A–B, 1–2, B–A, 2–1,
  colour solutions. The recovered first frame visibly says total **3**, while duplicate title block
  proxy **2120** says sheet 1, total **2**; inconsistent totals are retained, not interpreted as
  proof that separate numbered construction sheets were delivered.
- Facade legend **1395**, model-space XY **(61753.625,-10160.289)**:
  `Сэндвич-панель - RAL 5015`.
- Facade legend **1397**, model-space XY **(61753.625,-11863.719)**:
  `Крыльца, двери - RAL 7004`.
- Plan / roof plan / section construction views are present in **model space**, approximately
  X **3000..34000**, Y **-12500..13500**. These are identified by their geometry, not falsely
  assigned a published sheet number. Roof plan is the horizontally elongated ribbed rectangle
  below the equipment plan. The section is to its right.
- **1399**, XY **(21258.467,-6840.458)**; **2AF2**, XY **(32226.993,-6840.458)**;
  proxy **25D4**, XY **(16646.579,11183.681)**: three-layer sandwich panels,
  basalt mineral-wool infill, **100 mm**. Proxy **3C25** at **(26066.261,9072.781)**
  and **3DE6** at **(19782.601,5501.825)** repeat this construction.
- Proxy **3DE6**, XY **(19782.601,4826.825)**: reinforced-concrete slab.
- Proxy **26FC**, XY **(-44377.189,3847.916)**: profiled galvanized metal sheet with polymer
  coating / 100 mm mineral wool / profiled galvanized sheet. This belongs to the red-crossed-out
  older model-space construction region: retained as non-governing evidence, not used to assign
  a roof finish or joint pitch.
- NKU-specific note **1ADF**, paper-space XY **(440.578,-43.890)**: 20-foot container dimensions,
  height **2591 mm**, project zero **170.50**. Scene body height is approximately **2.591 m**
  (world Z -0.040793..2.550209), consistent with this reference. No placement/CRS approval implied.

### Explicit exclusions and limits

Note **1D3D** describes guard posts 1–4 and elevations 166.05 / 162.65 / 163.75 / 162.75;
**2123** gives 320.35. These are template remnants ignored per the orchestrator, not questions
re-escalated to Artem. Proxy 26FC's crossed-out region is not the active colour legend.
No active legend independently specifies a roof RAL, frame RAL or exposed foundation finish.
No dimensioned panel/joint/profile module was verified: do not invent a cassette grid from the ribs.

AutoCAD core console **2025**, read-only copy, supplied text and DXF diagnostics.
DXFOUT exit 0 was insufficient: normal ezdxf reading failed with `missing ENDSEC tag`.
`ezdxf.recover` subsequently read the diagnostic with **0 remaining audit errors, 2 repairs**
(orphan layout records). Proxy graphics yielded **230 text fragments from 148 proxies**.
Native TEXT/MTEXT plus proxy fragments are retained separately. The reconstructed drawing images
are **recovered diagnostic views, not certified native plots**; viewport completeness is not claimed.
`drawing-text.json` preserves the selected handles, spaces and coordinates. No invented PDF pages.

## Scene census and ID mapping

Reuse #558's saved `C:/x/tec26-oks/census/oks.json`, no additional Max session.
3ds Max **2026.3**, file saved in Max 2024 format, Z up, system meters, unit scale **1.0**.
Actual layer **008** (accepted by the orchestrator, not `0.0.0.8`):

- **АС.08**, handle **172**, Editable Poly, **193 vertices / 180 polygons / 348 triangles**.
- **Colizii_044**, handle **343**, **8 vertices / 6 polygons / 12 triangles**, no material.
  It is the existing collision candidate, not renamed, rebuilt or independently UCX-validated here.
- Multi/Sub **Material #3**, handle **4155**, IDs/slots **1..10**.
  IDs **4,5** are populated but have no faces. IDs **6..10** are null and stay empty.
- UV channel 1 exists: **275 UV vertices / 348 triangle faces**. Source scale is identity.
  General topology, delivery pivots, CRS and collision readiness were not checked in this Gate-1 card.

Areas below are actual tessellated world-space surface areas from the census, not facade projections.
Polygon counts and triangle counts are intentionally distinct. Existing source IDs are preserved;
this is not a remap to the standard's semantic ID ranges or UDIMs.

| Source ID | Polygons | Triangles | Area m² | Geometry from ID views | Proposed finish | Map type | Evidence / decision |
|---|---:|---:|---:|---|---|---|---|
| 1 | 127 | 254 | 60.50952526944401 | Roof, perimeter frame and skirt/foundation extending down to Z=-2.046546 | **?** mixed ID; visible frame could be blue 5015, roof/foundation unproven | **?** | Actual census + `id1-isolated.png`; facade legend does not resolve all these surfaces. Q1 |
| 2 | 15 | 30 | 35.3280560120449 | Wall infill panels on all sides | Sandwich panel, **RAL 5015**, RGB **34,113,179** | **solid**, no invented joints | DWG 1395 + 1399/2AF2/25D4, ID views; exact KPP Metal_RAL5015 solid tile 1013. Q2/Q3 |
| 3 | 38 | 64 | 1.6974531660811787 | Door assembly including leaf/frame/handle geometry | Door, **RAL 7004**, RGB **150,153,146** | **solid** | DWG 1397, green door in ID views; exact KPP Door_RAL7004 solid tile 1010. Q2 |
| 4–5 | 0 | 0 | 0 | Populated unused submaterials | Unused, not assigned | n/a | Multi/Sub census |
| 6–10 | 0 | 0 | 0 | Empty slots | Remain empty | n/a | Multi/Sub census |

ID 1 is deliberately **not** painted uniformly with a guessed RAL. Its roof/frame/foundation
membership makes a single finish unsafe. The contact sheet marks it magenta, not a finish.
The proposal image is diagnostic visualization only; it does not modify the master mesh.
No glass was identified as a separate used-ID surface; none is invented. If glass is later found,
use KPP `M_Glass_01` (NPM alpha 0.5; VPM per standard), not the door colour.

## KPP colour provenance

`jobs/KPP1/materials.json` names `Metal_RAL5015` UDIM 1013 and `Door_RAL7004` UDIM 1010.
The corresponding `maps_kpp/T_Kpp_1_Diffuse_1.<tile>.png` files were actually opened:

| RAL | Tile | Size | Pixel verification | SHA256 |
|---|---:|---|---|---|
| 5015 | 1013 | 256×256 RGB | 65536/65536 = (34,113,179) | `1d978c478b119565a77a2b503ce8b1f09d95425156ccd83c90021459dc14c4a2` |
| 7004 | 1010 | 256×256 RGB | 65536/65536 = (150,153,146) | `765b8504bfb70793698a541cfd88cf839a0c5bbf6cb3cb3b76cb52bacd382969` |

Using solid 1013 avoids transplanting the cassette seams/noise of KPP's textured 1007 onto
sandwich panels. No RGB was guessed from an online RAL chart or sampled from a DWG screenshot.

## Review evidence

**Contact sheet:** `G:/Мой диск/AGR-evidence/tec26-oks/AC08/evidence-v002/contact-sheet.png`.
Other files alongside it: `ids-front.png`, `ids-reverse.png`, `ids-side.png`, `ids-top.png`,
`id1-isolated.png`, `proposal.png`, `dwg-issued-sheet1.png`, `dwg-facades-complete.png`,
`dwg-plans-sections.png`, full recovered model/layout views and readback diagnostics.
Labels sit outside swatches; unused IDs and null slots are hatched and labelled.
ID rendering uses actual census triangle buffers via Matplotlib, no synthetic building geometry,
no lighting-based colour inference; UCX is excluded from finish renders.
Full evidence has `SHA256SUMS.txt`; compact file hashes/bytes are in `materials.json`.
Source copies remain under `C:/x/tec26-oks/AC08/`. Large binaries are not committed or put in LFS.

## Verification

Focused contract regression through `suite_slot.py --card t_2e18a13b`:
**RED 9 failed** (missing `materials.json` before the data commit), **GREEN 9 passed**.
The tests cover every used ID, polygon/triangle counts, retained empty slots, explicit unknown ID 1,
proposal status, exact KPP RGB values and the unapproved gate. No production code was introduced.
Independent NumPy recomputation from all **348/348** census triangles reproduced the three stored
areas exactly. Drive readback verified **27/27** evidence file sizes and SHA256 values; the checksum
file intentionally does not list itself. Contact-sheet pixel probes matched **3/3** swatches
(magenta unknown, KPP blue, KPP grey). Source/output contact-sheet paths are different files.
The **79 native text records** and **230 proxy text fragments** remain available in the external evidence.
These are static evidence/contract checks, not material acceptance or general delivery validation.
No full suite was requested at this Gate-1 stop (the card specifies focused tests); run the required
full-suite gate before a subsequent first code-review request if the task advances to that stage.

## Gate-1 questions for Artem

1. **ID 1** combines roof, frame and below-ground skirt/foundation. May those surfaces be split by
   finish later, and what are the roof/frame and exposed foundation finishes? Proposed visible
   frame: blue RAL 5015; roof/foundation stay **?** until answered. See isolated ID 1, not a blind ID list.
2. Approve **ID 2 = RAL 5015 sandwich panels**, **ID 3 = RAL 7004 door** on this contact sheet?
3. With no verified dimensioned joint/profile pitch, keep **solid colours without joints**, or supply
   the manufacturer's panel/profile module?

**STOP:** these are proposals for Gate 1 only. User approval, production build, final delivery QA,
NPM/VPM export and publication are separate and have not happened.
