# TEC26-OKS / AC08 — Gate 1 material approval

**Building:** Контейнер низковольтных комплектных устройств (НКУ) (low-voltage switchgear container).
**Status:** approved-gate1. Artem, 2026-10-22, quote: «Принимаю».
**Scope:** colouring only. Geometry, topology, UCX and multisub IDs stay exactly as in the source scene. This card builds nothing. VPM (UDIM tiles) and NPM (one 2048 atlas) are a separate card; pilot #559 first.
**Pilot main at intake:** `442f0b695a91f9abc180783c26978fbe85fefcf9`.

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
Those colours are Artem's Gate-1 approval, recorded below, not a second reading of the legend.
No dimensioned panel/joint/profile module was verified on this drawing. The KPP VPM blue cassette (tile 1007) was applied the same day and is superseded: it is not the panel source. All TEC26 buildings use vertical joints only, no horizontal joints, module 0.60 m at 1000 px/m, taken from Artem's texture as a colour, noise and joint-profile source. The perimeter drop below ±0.000 stays plain RAL 5015.

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

| Source ID | Polygons | Triangles | Area m² | Geometry from ID views | Approved finish | Map type | Evidence / decision |
|---|---:|---:|---:|---|---|---|---|
| 1 | 127 | 254 | 60.50952526944401 | Roof, perimeter frame and skirt/foundation extending down to Z=-2.046546 | Mixed ID, split by region inside the same ID: roof **RAL 7004** RGB **150,153,146**; frame **RAL 7004** RGB **150,153,146**; visible foundation/drop below 0.000 = wall colour **RAL 5015** RGB **34,113,179**. Part areas are null (census has no face split). | **solid** | Artem 2026-10-22. KPP tiles 1010 and 1013. Totals stay 127 / 254 / 60.50952526944401. |
| 2 | 15 | 30 | 35.3280560120449 | Wall infill panels on all sides | Sandwich panel, **RAL 5015**, RGB **34,113,179**, vertical joints only | **joints** (vertical only) | DWG 1395 + 1399/2AF2/25D4; flat colour KPP Metal_RAL5015 tile 1013 (34,113,179). Joints from Artem's texture, mean RGB (34,112,177), max channel delta 2. Approved. |
| 3 | 38 | 64 | 1.6974531660811787 | Door assembly including leaf/frame/handle geometry | Door, **RAL 7004**, RGB **150,153,146** | **solid** | DWG 1397; exact KPP Door_RAL7004 solid tile 1010. Approved. |
| 4–5 | 0 | 0 | 0 | Populated unused submaterials | Unused, not assigned | n/a | Multi/Sub census |
| 6–10 | 0 | 0 | 0 | Empty slots | Remain empty | n/a | Multi/Sub census |

ID 1 stays one material ID. Roof, frame and the drop are different colours by UV/atlas regions
or a face-group split inside that ID. No face, triangle or area is dropped: the ID 1 totals
remain 127 faces, 254 triangles and 60.50952526944401 m². Per-part areas are null because
`scene-census.json` stores ID 1 only as that aggregate.
The contact sheet still shows the intake diagnostic (magenta on ID 1); it is not the approved paint
and it does not modify the master mesh.
AC08 has no glass ID. The glass rule is still KPP: if glass is later found, use `M_Glass_01`
(NPM alpha 0.5; VPM per standard), not the door or wall colour. ID 2 panels are RAL 5015
with vertical joints only (no horizontal joints) for all TEC26 buildings. The joint profile,
colour and noise come from
`C:/x/tec26-oks/user-textures/panel_RAL5015_vertical_joints_4096.png`
(also Drive `AGR-evidence/tec26-oks/user-textures/`), SHA256
`2c255edc5f7a56fc8aca3038d0e0235327128ac6ae3c8c63e0be31a1f6386ece`.
Measured 4096×4096 RGB, mean RGB (34,112,177), 7 vertical dark joints 8 px wide every 600 px
(centres 270, 870, 1470, 2070, 2670, 3270, 3870). At 1000 px/m that is a panel module of 0.60 m
and a joint of 8 mm. 4096 is not a multiple of 600, so the image does not wrap seamlessly:
it is not tiled. Joints are laid at a 0.60 m period from each panel's start edge
(phase from ±0.000 / panel corner). The same look is used in VPM (diffuse and normal) and in
the NPM atlas (joints at least 1.5 px). Where a panel face does not fit a 4K tile, the only
allowed cut is an edge loop or ring (connect) across the panel at joint positions. Quads stay,
every cut is listed in the build report, and silhouette, normals, UCX and IDs stay unchanged.
Approved flat RGB stays KPP (34,113,179). The texture mean (34,112,177) is within a tolerance
of 2 per channel. ID 1 foundation keeps that wall colour. Doors, frames and porches stay solid
RAL 7004. The drop below ±0.000 stays plain RAL 5015.

## KPP colour provenance

`jobs/KPP1/materials.json` names `Metal_RAL5015` UDIM 1013 and `Door_RAL7004` UDIM 1010.
The corresponding `maps_kpp/T_Kpp_1_Diffuse_1.<tile>.png` files were actually opened:

| RAL | Tile | Size | Pixel verification | SHA256 |
|---|---:|---|---|---|
| 5015 | 1013 | 256×256 RGB | 65536/65536 = (34,113,179) | `1d978c478b119565a77a2b503ce8b1f09d95425156ccd83c90021459dc14c4a2` |
| 7004 | 1010 | 256×256 RGB | 65536/65536 = (150,153,146) | `765b8504bfb70793698a541cfd88cf839a0c5bbf6cb3cb3b76cb52bacd382969` |

Flat RGB still comes from those solid tiles. Artem's texture mean (34,112,177) is the measured
noise of the joint source, not a replacement flat: the largest channel gap versus KPP
(34,113,179) is 2. ID 1 foundation keeps the KPP wall colour.

KPP cassette tile 1007 is superseded and is not the panel source. It remains here as the
history of the rule it replaced.

| Role | Tile | Size | SHA256 |
|---|---:|---|---|
| Cassette_RAL5015 diffuse (superseded) | 1007 | 4096×4096 RGB | `323ca26ba0685dc32f8afb12b9218a76e51570c39301b5d6606171f7f9660ee0` |
| Cassette_RAL5015 normal (superseded) | 1007 | 4096×4096 RGB | `73a3430cb255d2cf8ecbd6ab477248ad94a3d86f5850efedaf86d91787c4ee3d` |

Files were `maps_kpp/T_Kpp_1_Diffuse_1.1007.png` and `maps_kpp/T_Kpp_1_Normal_1.1007.png`.
That tile is 1000 px/m (4096 px over 4.096 m) with a 0.6 m by 0.55 m cassette and 8 mm joints.
`Cassette_RAL5015_Top` tile 1018 was never the panel source.
`C:/x/tec26-oks/census/kpp-recipe.md` was not on disk; the tile was identified from `maps_kpp` and `jobs/KPP1/scripts/vpm_textures.json`.
No RGB was guessed from an online RAL chart or sampled from a DWG screenshot.

The panel source is now Artem's file
`panel_RAL5015_vertical_joints_4096.png`, same SHA256 as
`C:/x/tec26-oks/user-textures/SHA256SUMS.txt`. Vertical joints only, module 0.60 m, joint 8 mm,
texel 1000 px/m, phase from the panel start edge. A face that does not fit a 4K tile may take
an edge loop or ring cut at joint positions only.

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

Intake contract regression through `suite_slot.py --card t_2e18a13b` (before this approval):
**RED 9 failed** (missing `materials.json` before the data commit), **GREEN 9 passed**.
The approval pass updates that contract to approved-gate1, the mixed ID 1 region split,
approved ID 2/ID 3, exact KPP RGB values and the empty/unused slots.
Focused `tests/test_tec26_ac08_materials.py`: **RED 9 failed, 5 passed** on the pre-approval
data, **GREEN 14 passed** after the first approval record. The 2026-10-22 joints revision of that
record: **RED 4 failed, 13 passed** before the cassette data, **GREEN 17 passed** after it.
The later same-day vertical-joints revision (cassette tile 1007 superseded): **RED 5 failed, 14 passed**
before the texture record, **GREEN 19 passed** after it.
No production code was introduced.
Independent NumPy recomputation from all **348/348** census triangles reproduced the three stored
areas exactly. Drive readback verified **27/27** evidence file sizes and SHA256 values; the checksum
file intentionally does not list itself. Contact-sheet pixel probes matched **3/3** swatches
(magenta unknown, KPP blue, KPP grey). Source/output contact-sheet paths are different files.
The **79 native text records** and **230 proxy text fragments** remain available in the external evidence.
These are static evidence/contract checks, not material acceptance or general delivery validation.
No full suite was requested at this Gate-1 stop (the card specifies focused tests); run the required
full-suite gate before a subsequent first code-review request if the task advances to that stage.

## Recorded Gate-1 approval

Artem, 2026-10-22, quote: «Принимаю».

1. Sandwich panels. Original answer, Artem 2026-10-22: solid colour, no joints (module not confirmed in the drawings). Superseded the same day, 2026-10-22: «Не вижу швов на панелях. В КПП есть текстура для VPM со швами — можно такой же тексель, как в VPM КПП, взять на панелях и такой же на наших домиках сделать в VPM и NPM» and «ниже ±0.000 без швов (под землёй не видно)». That cassette reading (KPP Cassette_RAL5015 tile 1007, diffuse and normal) is itself superseded the same day and is not the panel source. Latest instruction, Artem 2026-10-22, for all TEC26 buildings: «Панели неверные, должны быть вертикальные швы только; текстуру пришлю; если не влезает, можно аккуратно порезать через loop или ring». Blue sandwich panels (RAL 5015) have vertical joints only, no horizontal joints. Texel matches KPP VPM: 1000 px/m on a 4K UDIM. Module 0.60 m, joint 8 mm, phase from each panel start edge (±0.000 / panel corner). Source file `panel_RAL5015_vertical_joints_4096.png` supplies colour, noise and the joint profile and is not tiled. VPM uses diffuse and normal; the NPM atlas keeps joints at least 1.5 px. If a panel face does not fit a 4K tile, cutting is an edge loop or ring at joint positions only, quads kept, every cut listed in the build report; silhouette, normals, UCX and IDs stay unchanged. The perimeter drop below ±0.000 stays plain RAL 5015.
2. Roof: RAL 7004 grey (same as KPP 7004), not 5015.
3. Mixed ID 1 may be painted differently (roof 7004, frame 7004, plinth/below-grade drop = wall colour)
   without changing geometry, via UV/atlas regions or a face-group split inside the same ID.
4. Panels RAL 5015 = KPP blue, doors/frames/porches RAL 7004 = KPP grey, glass as KPP.
   The drop below ±0.000 takes the wall colour.

AC08 assignment: ID 2 panels 5015 with vertical joints only, ID 3 door 7004, mixed ID 1 roof 7004 / frame 7004 /
visible foundation/drop = plain wall colour RAL 5015. No open question remains.
The build (VPM UDIM tiles, NPM one 2048 atlas) is a separate card and starts with pilot #559.
This card builds nothing.

## Updated contact sheet (approved state)
`G:/Мой диск/AGR-evidence/tec26-oks/AC08/evidence-v003/contact-sheet-approved.png` (sha256 394acc07fc598b8e11af770dda079b7829275edab0df63043a545eb222d65146); one swatch per ID/part, no numbers inside swatches, gaps (slots 4-10) crossed out. Earlier ID renders: evidence-v002.
