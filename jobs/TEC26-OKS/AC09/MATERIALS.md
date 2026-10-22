# AC09 — material proposal / Gate 1 STOP (not approved)

Building: **Контейнер системы автоматического контроля вредных выбросов (САКВ)**.
Title block: `22Е56-АР2-1002-АС.09.dwg`, layout2, handles3437/3438 at
(499.713,27.7392,0)/(504.356,23.9892,0) paper mm.
Pilot main at start: `442f0b695a91f9abc180783c26978fbe85fefcf9`.

**awaiting_gate1; passed=false. All finishes unapproved. No NPM/VPM build, geometry/UV/material
assignment edits or delivery export.** IDs, editor slots and UDIMs are distinct concepts.

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
  explicitly a Model-space group, NOT invented sheet1. Ribs visible, no module/joint dimensions established.
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
| Sandwich panels RAL5015 | solid, no invented joints | D4B;27521.4,-943.967,0; facades p1 |
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
| 1 |188|376|38.713608|0/0| Mixed roof, corner frame, plinth, below-zero extrusion -> **?** | ? | isolated ID1, z=-2.0383..2.5675; blue facade trim not evidence for all regions |
| 2 |50|100|18.757031|0/0| Wall panels -> **RAL5015** | solid | D4B+facades p1+isolated ID2 |
| 3 |40|80|1.901034|0/0| Window frame outlines -> **RAL9016** | solid | 1C5A+isolated ID3 |
| 4 |39|66|1.771651|0/0| Door/handle -> **RAL7004** | metal | D4D+isolated ID4 |
| 5 |12|24|0.940521|0/0| Window reveals/thickness -> **RAL9016 proposed** | solid | ID5 behind ID3, extension of1C5A, not independently specified |
| 6 |0|0|0|8/3.216858| Glass -> **KPP M_Glass_01** | glass | handle369, orchestrator rule6, KPP export_npm.py:152–157 |
| 7 |18|36|27.345944|0/0| Interior walls/floor/ceiling -> **?** | ? | isolated ID7, floor/ceiling each4.898m², section no finish |
| 8 |0|0|0|0/0| empty, keep | none | census; resolved rule4 |
| 9 |0|0|0|0/0| empty, keep | none | census; resolved rule4 |
| 10 |0|0|0|0/0| empty, keep | none | census; resolved rule4 |

Areas summed triangle surface, not projected/visible; JSON retains unrounded values. ID1 is NOT
all wall panel, ID7 NOT exterior roof. Both stay pink gaps. Later per-face finish groups inside ID1
may be needed without geometry change; none built here. Generic source names/ID colours do not prove RAL.

## KPP exact colour reuse

Hash-pinned maps_kpp sources and jobs/KPP1/materials.json: RAL5015 tile1007, RAL7004 tile1001,
RAL9016 tile1009. Chips use existing modal pixels(34,113,179)/(150,153,146)/(246,246,246),
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

## Questions for Artem — STOP

1. Approve/correct this proposal **on the contact sheet**: ID2 RAL5015, ID3 RAL9016,
   ID4 RAL7004, ID5 RAL9016 reveals (extension proposal), ID6 KPP glass.
2. ID1 mixes roof, exterior frame, plinth and below-zero faces. Which finishes for these subregions?
   May later material work distinguish face groups without changing geometry? No single whole-ID finish evidenced.
3. Specify visible interior ID7 wall/floor/ceiling finishes; no interior finish schedule found.
4. Ribs drawn without established module/profile: approve solid RAL5015 without synthetic joints,
   or provide panel profile/module dimensions.

Layer, edition, old roof elevation, glass convention and empty slots resolved, NOT blind user questions.
Await actual Gate-1 approval. No full-suite/PR/review/delivery-completion claim at this blocked stage.
