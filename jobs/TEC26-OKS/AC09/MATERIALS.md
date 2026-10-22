# AC09 — material mapping / approved-gate1

Building: **Контейнер системы автоматического контроля вредных выбросов (САКВ)**.
Title block: `22Е56-АР2-1002-АС.09.dwg`, layout2, handles3437/3438 at
(499.713,27.7392,0)/(504.356,23.9892,0) paper mm.
Pilot main at start: `442f0b695a91f9abc180783c26978fbe85fefcf9`.

**approved-gate1; passed=false.** «Принимаю» (Artem, 2026-10-22, Gate 1 answer) accepts the
orchestrator finish mapping below. VPM/NPM are not built; technical QA and publication stay
separate statuses. No geometry change. IDs, editor slots and UDIMs stay distinct.

## Inputs and decisions

Orchestrator rules on this card (2026-10-22) settle revision, actual layer names, same-DWG legend,
KPP glass, empty slots, and final geometry. Only one DWG, no R1/PDF, exists in the AC09 directory,
re-inventoried after plotting. Original SHA256 remains
`feb22366bd7270f6912de797d9ffc0cc075d451cb154e3aaa1deaea96c88a5b5`.
Pristine copy `C:/x/tec26-oks/AC09/drawings-v002/ac09.dwg`, same SHA256, manifest beside it.
Earlier disposable `drawings-v001/ac09.dwg` was rewritten by DXFOUT; its hash is
`e4adf48e7ac6fed2cc7efd8d512e34048c281e259f160d51dacb9aefe608ddf0`. It is the working copy used
for text/plots, NOT byte-identical to the original. Original never edited; JSON distinguishes hashes.

AutoCAD2025 Core Engine V.72.0.0 / ACADVER25.0, INSUNITS4(mm), locked dcc_batch.py acad,
copy only, QUIT discarding plot/page-setup changes. #558 and independent DXFOUT both end at
XRECORD35B without ENDSEC/EOF; ezdxf rejects them despite wrapper exit0. AutoLISP fallback
recovered59 text/insert records (51 non-insert records in drawing-text.json); block walk204 lines.
First text attempt failed at prin1 extra argument, repaired with write-line/vl-prin1-to-string.
Optional layoutlist was unavailable; no nested-block transform verification is claimed.

## Native drawing evidence

Folder: **`G:/Мой диск/AGR-evidence/tec26-oks/AC09/gate1-v002/`**.

- `ac09-facades.pdf` p1: native Model plot window(-1000,-6000)–(40000,20000)mm,
  four blue-panel elevations and colour legend. No printed facade sheet title/number recovered;
  explicitly a Model-space group, NOT invented sheet1. Ribs are visible. The drawing does not
  dimension a module; joint scale is the KPP panel tile (Artem, 2026-10-22).
- `ac09-sheet2.pdf` p1: native layout2/printed sheet2 (`3443`), plan0.000 (`2374`, paper91.7101,283.955),
  section1-1 (`23EA`,269.028,283.955), roof (`2460`,444.483,283.955), title equivalents3439–343B.
  Plan/roof3000x2450 are envelope dimensions, not cladding module. No separate roof RAL established.
- Both PDFs rendered via PyMuPDF and visually inspected. CS_Gost2304.shx/russwin.shx substitution
  to simplex.shx and missing-font warnings retained; legend cross-checked with native entget text.
- ac09-viewports.lsp: 3 VIEWPORT records, all layout2; viewport11B3 targets(9744.14,-10424.1,0),
  view height9600; 247E targets(16278.5,-21276,0), height10287.7. Facade colour legend outside
  these sheet2 windows, hence separate Model plot rather than a false paper-sheet locator.

| Drawing finish/material | Map proposal | Model handle; insertion mm; native PDF |
|---|---|---|
| Sandwich panels RAL5015 | joints (KPP panel tile, same texel density/joint scale) | D4B;27521.4,-943.967,0; facades p1 |
| Porches/doors RAL7004 | metal | D4D;27521.4,-2647.4,0; facades p1 |
| Window frames RAL9016 | solid | 1C5A;27521.4,-4105.6,0; facades p1 |
| Three-layer sandwich100mm, basalt mineral wool | structural note, not module | FFD;12472.7,-20445.8,0; sheet2 p1 |
| Reinforced-concrete slab | finish/RAL unspecified | 1003;12472.7,-22195.1,0; sheet2 p1 |
| Concrete | finish/RAL unspecified | 8B0;56333.5,5967.98,0; unplaced Model detail outside facade window |

No yellow RAL in recovered AC09 text. No other-building finish borrowed. Roof correction36B1
(25439.7,-10124.7,0) mentions former+2.330, 36B0 says corrected; informational drawing conflict,
not a geometry change or user question under orchestrator rule1. Area notes21FC/21FF
(6.30/19.28m²) are not finish evidence or scene-rescaling instructions. Layout2 note259F
(304.027,-18.1194,0): factory-ready SAKV, floor0.000=absolute171.27, not coating specification.
No recovered note explicitly says «Посты охраны»; no such template leftover invented. If later found,
other-object notes are excluded per rule3, not used to override the same-DWG SAKV legend.

Plot failures retained: attempt1 `_Model` nonexistent layout; attempt2 `_As displayed` split answers,
timeout180s; attempt3 actual `Model`, `_A` succeeded with readable PDF. Paper plot first omitted
hide-paperspace answer; extra `_N` succeeded. All logs/scripts on Drive; nominal exit0 never sufficient.

## Scene and per-ID proposal

Reuse #558 C:/x/tec26-oks/census/oks.json; no new Max session. Scene copy:
C:/x/tec26-oks/sources-v001/Vlad_OKS/04-09 Geometry Final.max, Max2026.3, fileversion26000,
meters/1unit per m/Zup. Actual layer **009** accepted by orchestrator: main АС.09 handle173,
glass АС.09_Glass handle369, collision Colizii_043 handle342 (12triangles/no material/not renamed UCX).
Other layers excluded. Main/glass share Multi/Sub Material#7 handle4439, 10slots, 8–10empty.
Native/snapshot bbox difference: main0.000003814697265625m; glass/collision0m.

Six orthographic **software census renders** in id-colours.png (front/back/sides/top/bottom),
not native Max renderer output. isolated-ids.png shows each populated opaque ID separately;
proposed-finishes.png shows unchanged geometry with proposed finish colours. Camera changes
are not geometry edits. No topology/UV/delivery QA certification.

| ID | Main polygons | Main triangles | Main area m² | Glass triangles/area m² | Geometry -> proposed finish | Map | Evidence/limitation |
|---|---:|---:|---:|---|---|---|---|
| 1 |188|376|38.713608|0/0| Same ID, no geometry change. Roof and frame **RAL7004**; plinth and below-grade drop **RAL5015** plain wall colour without joints (adjacent wall). Perimeter drop below +-0.000 keeps that plain wall colour, no separate ID | split (UV / face groups) | Gate 1 decision; KPP colour tiles 1001 and 1007, joints not used on the drop |
| 2 |50|100|18.757031|0/0| Wall panels -> **RAL5015** KPP blue cassette tile with joints, same texel density and joint scale as KPP VPM. Phase z=0.000. Below +-0.000 the perimeter drop is plain 5015 without joints | joints (KPP panel tile, same texel density/joint scale) | D4B+facades p1+isolated ID2; maps_kpp T_Kpp_1_Diffuse/Normal_1.1007 |
| 3 |40|80|1.901034|0/0| Window frame outlines -> **RAL9016** | solid | 1C5A+isolated ID3 |
| 4 |39|66|1.771651|0/0| Door/porch -> **RAL7004** KPP grey | metal | D4D+isolated ID4 |
| 5 |12|24|0.940521|0/0| Window reveals/thickness -> **RAL9016** | solid | Gate 1; same KPP white as the frames |
| 6 |0|0|0|8/3.216858| Glass -> **KPP M_Glass_01** | glass | handle369, orchestrator rule6, KPP export_npm.py:152–157 |
| 7 |18|36|27.345944|0/0| Interior walls/floor/ceiling -> **KPP Interior** | solid | jobs/KPP1/materials.json Interior, UDIM 1011; no hex stored here |
| 8 |0|0|0|0/0| empty, keep | none | census; resolved rule4 |
| 9 |0|0|0|0/0| empty, keep | none | census; resolved rule4 |
| 10 |0|0|0|0/0| empty, keep | none | census; resolved rule4 |

Areas summed triangle surface, not projected/visible; JSON retains unrounded values. ID1 is not
one wall-panel finish: roof and frame are RAL 7004, plinth and the below-grade drop are plain wall
colour RAL 5015 without joints, assigned later as UV regions or face groups inside the same ID. ID7 is KPP
Interior, not the exterior roof. Generic source names and ID colours do not prove RAL. Same RAL as
KPP uses the hash-pinned maps_kpp chips already listed below. KPP Interior is referenced by name
from `jobs/KPP1/materials.json`; this record does not invent a hex for it.

## KPP exact colour reuse

Hash-pinned maps_kpp sources and jobs/KPP1/materials.json: RAL5015 tile1007
(`T_Kpp_1_Diffuse_1.1007` / `T_Kpp_1_Normal_1.1007`, KPP finish `Cassette_RAL5015`), RAL7004 tile1001,
RAL9016 tile1009. ID2 uses that cassette tile with its joints at the same texel density and joint
scale as KPP VPM (VPM diffuse+normal; NPM atlas, joints >= 1.5 px like make_npm_atlas.py). Phase
starts at z=0.000. `C:/x/tec26-oks/census/kpp-recipe.md` was not present. Chips use existing modal pixels(34,113,179)/(150,153,146)/(246,246,246),
not calibrated RAL conversion. Full original maps remain authoritative; chips are not delivery maps.
KPP NPM glass linear base(.75,.82,.82), alpha.5, roughness.05, no maps (export_npm.py:152–157).
Glass chip is opaque linear-to-sRGB base colour, not transparency simulation. VPM glass separate,
no maps, properties per standard at build time; package_vpm.py:37–39 values are explicitly proposals,
not approved AC09 values. No repeat glass question already resolved by orchestrator.

## Contact sheet and checks

**G:/Мой диск/AGR-evidence/tec26-oks/AC09/gate1-v002/contact-sheet.png**:
ten swatches, labels outside, pink hatch=unknown, empty slots marked, six ID views+six finish views.
Separate isolated-ID views explain the proposal. SHA256SUMS.txt pins PDFs/images/buffers/scripts/logs;
no binary or LFS committed. Focused tests check proposals/unknowns/empty slots, face accounting,
source locators, KPP identity, glass policy and fail-closed approval status, not delivery compliance.

## Verification receipt (checkpoint only)

Tests-first commit `9685723`: focused suite RED **1 failed / 1 passed** (missing geometry_evidence),
then GREEN **2 passed** through suite_slot.py on the proposed mapping. Drive manifest **20/20**
file hashes matched; input/KPP/pristine-copy hashes **10/10** matched. Native PDFs **1 page each**.
Main/glass triangle accounting **682/8**. `passed=false` and all ten slots remain unapproved.
Full suite and author eval receipts deferred until actual Gate-1 answer and first PR review request.

## Gate 1 decision

«Принимаю» (Artem, 2026-10-22, Gate 1 answer). The four open questions are resolved:

1. ID2 RAL 5015, ID3 RAL 9016, ID4 RAL 7004, ID5 RAL 9016 reveals, ID6 KPP `M_Glass_01` (NPM alpha 0.5).
2. ID1 stays one material ID. Roof RAL 7004 (not 5015), frame RAL 7004, plinth and below-grade drop
   are plain wall colour RAL 5015 without joints (adjacent wall). Perimeter drop below +-0.000 keeps
   that plain wall colour and gets no separate ID. Later UV regions or face groups may carry those
   finishes; geometry is unchanged.
3. ID7 walls, floor and ceiling are KPP Interior.
4. Panel joints are resolved by Artem, 2026-10-22. New rule from Artem (2026-10-22, supersedes "solid colour without joints" for panels): ID2 blue sandwich panels (RAL 5015) use the KPP VPM panel texture WITH its joints (blue cassette tile(s) of maps_kpp T_Kpp_1_Diffuse/Normal_1.10xx, see C:/x/tec26-oks/census/kpp-recipe.md if present) at the SAME texel density and joint scale as KPP VPM, in VPM (diffuse+normal) and NPM (atlas, joints >= 1.5 px like make_npm_atlas.py). Joint phase starts at +-0.000; the perimeter drop below +-0.000 stays plain panel colour WITHOUT joints (underground). Geometry unchanged.
   Slots 8-10 stay empty.

Non-blocking, not finish questions: roof elevation +2.330 (note 36B1) versus the corrected note (36B0);
sandwich thickness 120 mm versus 150 mm. Recovered note FFD still says 100 mm. Neither conflict changes
geometry or the approved colours. Contact sheet on Drive is unchanged. passed=false.
