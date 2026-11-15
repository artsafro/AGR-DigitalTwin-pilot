# Cold reproduction #1315 — intake checkpoints v001 / v002

Current status: **v012/r1 accepted continuous hedge construction [D301], not delivered**.
See [CONTINUATION-v012.md](CONTINUATION-v012.md): all4,582plant IDs/points/heights
and38MAF retained; actual162,159/334,422render triangles. Correct one-based public
xView witness decoding removes all NPMFlora faces/vertices/bowties; actual crown
support minima78.225%/78.655%,0below68%. D300construction-picture gate CLOSED.
Whole-file validators stillFAIL. Native39/48MAFface loss remains; a fresh native
original-library Bench025 already fails37faces. A new copy-only MAF constructive
repair/C44 model choice is explicit; no technical waiver or library edit requested.

Historical status: **v011/r2 continuous hedge-volume candidate [D298], not delivered**.
See [CONTINUATION-v011.md](CONTINUATION-v011.md):4,535hedge census plants merged
into physical run volumes; all4,582plant IDs/points/heights and38MAF retained.
Actual162,743/334,928render triangles; independent actual-export support minimum
78.225%/78.655%,0below68%. Original individual heights are recorded in the census,
not independent merged-mesh bboxes; envelope top differences up to0.181/0.222m
are disclosed. Separate90plant construction pilot/native readback is ready for
[D300] picture choice; technical xView/validator FAILs are NOT offered for approval.
Rejected r3/r5 experiments are retained; r2 is the preferred candidate, not final.

Historical v010/r1 **REJECTED by [D298]**: cell-trim yielded31–32% crowns despite
retaining IDs/points/heights. [CONTINUATION-v010.md](CONTINUATION-v010.md) retains
the measured failure; [D294] did not approve that new whole-site loss.

Historical status: **v009/r2 actual site replication [D291], not delivered**.
See [CONTINUATION-v009.md](CONTINUATION-v009.md): 4,576 accepted changed-copy shrubs
replicated, all4,582 plants/38MAF retained, actual157,141/617,840 render triangles.
One interim Flora atlas packed/read back; whole-site validators still FAIL. Three
bounded hedge repairs failed. A separate cell-trim eight-plant option is xView-clean
but shrinks individual crowns below the retained band; model-owner decision needed,
NOT approval of technical FAILs. The old isolated shrub picture gate is CLOSED.
Historical v008/r2 pilot is documented in [CONTINUATION-v008.md](CONTINUATION-v008.md).
Historical v007/r1 continuation follows; its then-open C44 route decision is answered by D300.

Historical v007 status: **v007/r1 technical continuation; v006/r5 composition accepted [D287], not delivered**.
See [CONTINUATION-v007.md](CONTINUATION-v007.md). All 38 MAF remain accepted-by-picture,
not article-matched; all 4,582 plants retained. Native Max verifies 172,437 /806,914
render triangles; raw-export controls 4,620/4,620 per profile. Metric VPM hedge-shell
spacing repaired on copies; whole-file xView still FAIL. The earlier UCX_427 alarm
is a float32 normal false positive: independent double planes show all 600 convex;
175,688 sampled surface distances <=79.836 mm, not a continuous coverage proof.
NPM native public validator now runs (FAIL); VPM import succeeds but regulatory
computation times out/crashes. Source-library star crossings expose unresolved C44
before a topology/silhouette-changing route; no intentional-crossing waiver applied.
Other technical/material/atlas/skirt/gap/checker work remains worker-owned. No PR or
readiness claim. Earlier continuation documents are immutable historical checkpoints.

Historical v002 status: **source authority answered; height/PartsList gates open, not delivered**.
Boundary and 52 source symbols exported/read back as source-only DXF. No constructed Ground/UCX,
library placements, model exports, delivery validators, visual approval or SINTEZ run.
No readiness increase claimed. The v001 facts/questions below are historical; v002 closes authority
questions and is the continuation state at the end of this report.

## Verified source facts

- AutoCAD 2025 core engine V.72.0.0 / ACADVER 25.0, INSUNITS=6 (metres).
- `sources.json`: DWG SHA-256 `f8cca7d93898a37eac633c99f0ceed21d3d6206737e5a6436096b281274b79c2`;
  MAF DOCX SHA-256 `577c5af4e36527b2eef3e19a447f8eaea251014b5733bfb44803459f3afd40d7`.
- Original DWG and frozen copy retain the source hash. DXFOUT rewrote the disposable AutoCAD copy
  to `8ff3ded8d84c4ed7eb39413393f1cf23305fe574d03a1e85e6c3da8e2851a67c` (not a pristine copy).
- ASCII DXF: 63,742,396 bytes, ENDSEC/EOF present, strict ezdxf 1.4.3 read succeeded;
  audit reported 0 remaining errors / 341 fixes. Fixes do not establish source-design correctness.
- Layouts: Model, 02_ГП. Model space: 77 INSERT, 490 LWPOLYLINE, 77 HATCH,
  275 CIRCLE, 3 ACAD_TABLE and other entities. Full database extraction: 1,734 text records.
- `1.1_Граница_ГПЗУ` contains legend samples, not the closed site boundary. Candidate:
  model-space LWPOLYLINE `33FBCEF`, layer `участки зоны`, closed, simple chord polygon area
  12,958.739 m², bounds (709.110, 11020.800)–(858.700, 11204.762). TEP table says 12,961.00 m².
  Candidate needs human confirmation under model-ground Step 2; it has NOT been adopted.
- Planting table `33EFCD8` / geometry `*T972` is inside block definition
  `Силикатный_350+150_Озеленение`, which has **zero INSERT references in the entire DXF database**.
  Finding that table is not proof it is the active approved planting plan.
- Vertical-planning definition `ACAD-Силикатный ВП_5 (пониженеие отметок)-Model16.10.2026`
  has 396 entities on `ГП_ПОР_Отметки и уклоны`, also **zero INSERT references**.
  Source text includes paired marks (e.g. 140.68/139.84); other definitions contain project-zero
  labels 142.10 and 142.70, and legend marks 177.05/176.48. No zero/column selected or flattened.

## Planting table extraction — authority unconfirmed

| Position | Source name | Source quantity | Size / issue |
|---|---|---|---|
| 1 | Пихта сибирская | 1 | h 2–3 m, crown >1.3 m |
| 2 | Клен красный «Red Sunset» | 4 | h 1.5–2 m, root ball |
| 3 | Клен остролистный | 6 | h >5 m, stem 7 cm |
| 4 | Сирень обыкновенная, сортовая | 17 | h >1.1 m; cultivar unspecified |
| 5 | Гортензия древовидная | 24 | h >0.9 m |
| 6 | Пузыреплодник калинолистный, 2-row hedge | 3360; 672.0 m² | caption says 5 plants / linear m |
| 7 | Пузыреплодник калинолистный «Лютеус», 1-row hedge | 1175; 235.0 m² | caption says 3 plants / linear m; do not infer linear length from m² |
| 8 | Хоста Allegan Fog, ожика лесная, тиарелла сердцелистная | 133.0 m² | no per-species counts/rates |
| 9 | Seeded lawn | 2427.2 m² | TEP table separately says 2426.22 m² |
| 10 | Rolled lawn | 523.0 m² | Ground texture, not Flora instances |

Table subtotals: 11 trees, 41 shrubs, 4535 hedge plants. These are textual schedule quantities,
NOT counts of source symbols or placements. Species/variant matches have not been certified.
Shared Flora catalogue contains Acer platanoides (107), Syringa vulgaris (116), Hydrangea arborescens
(207), Physocarpus opulifolius (211), P. opulifolius Luteus (234). No catalogue row for Abies sibirica,
Acer rubrum Red Sunset, Hosta Allegan Fog, Luzula sylvatica or Tiarella cordifolia was identified;
this is not yet an exhaustive disk-library absence finding. No substitutions made.

## Execution, attempts and evidence

Evidence root: `G:/Мой диск/AGR-evidence/1315-cold-silikatny/v001/`, with `SHA256SUMS.txt`.
Sources: `G:/Мой диск/AGR-assets/silikatny/source/cold-1315-v001/`, with `SHA256SUMS.txt`.
Binary evidence and customer documents are outside git; compact documents only are committed.

Commands (from the task worktree):

1. `uv sync` — completed. No dependency or shared-tool code change.
2. `dcc_batch.py acad --card t_d9ae7dc0 --dwg <disposable-copy> --file intake.scr --out acad-result.json`
   — 33.8 s, exit 0, DXF completion sentinel verified, parser and hashes checked separately.
3. Read-only `ezdxf.readfile` inventories, nested block/table queries and catalogue queries.
4. `uv run python tmp/1315/v001/source_diagram.py` — 3428 source curves drawn, 0 failed conversions.
   Visual inspection confirms the red candidate and disclaimer. Hatches/text are intentionally not rendered;
   this is **a source-contour diagram, not native CAD plot, Ground mesh, pilot, or delivery evidence**.

Useful failed attempts preserved, no claimed passes:

- Inventory script named `inspect.py` shadowed stdlib inspect; renamed `source_inventory.py`, successful.
- DXF renderer: unavailable `Configuration` import corrected; then TEXT alignment `None` caused TypeError;
  audit-first route also failed. General DXF frontend renderer stopped, not used for evidence.
- Native plot attempt 1: UTF-8 Cyrillic layout interpreted as mojibake; no PDF.
- Native plot attempt 2: ASCII runtime layout lookup hit unsupported `layoutlist` in core console; no PDF.
- Native plot attempt 3: CP1251 script resolves layout, but existing page setup reports **No Matching Media**;
  no PDF exists. Wrapper exit 0 and completion sentinel do NOT prove plotting success. Plotting stopped.
- Targeted source-contour diagram avoids the failed text/layout/plot routes; it cannot replace native-sheet
  verification or exported-model readback. No fonts, user page setups or original DWG were changed.

No shared production code written. Ignored inspection/diagram scripts are retained in external evidence,
not proposed as shared builders. No earlier same-site result was read or reused.

## Per-area checkpoint and blockers (value / limit / owner)

| Area | Reproduced now | Value / required limit | Owner / next action |
|---|---|---|---|
| Ground | Source intake and candidate boundary only | 0 approved boundary candidates / exactly 1; 0 authoritative relief mappings / required design-mark mapping | Artem: confirm boundary and VP definition/zero; then source-based pilot |
| UCX | Nothing constructed | 0 hulls measured / closed convex, gap 2–10 mm, deviation <=100 mm, budget D012 | Worker after Ground approval; VPM only |
| MAF | DOCX pinned, library roots exist | 0 certified row-to-model/point matches / every specified row accounted for | Worker: parse all 32 specification rows and disk manifest on approved pilot; missing types listed |
| Flora | Buried schedule extracted | 0 authoritative planting-plan mappings / approved table + plan; row 8 rate absent / source-based rate required for scatter | Artem: confirm definition authority or supply current plan; worker reconciles points and library |
| Delivery | None | 0 exported/read-back profiles / NPM + VPM; open manual gates / no passed=true | Worker + Artem visual + SINTEZ owner after pilot |

Historical #906/#969/#1178 comparison, tool-call/elapsed reproduction totals and final per-area
validator findings remain **not measured** until actual reproduction; this intake does not equal them.

## Source-authority questions (one batch before construction)

1. Recommend using closed contour **33FBCEF** on `участки зоны` as drawn in red, preserving its actual
   contour rather than forcing the 12,961 m² table total. Confirm this as the projected-site boundary?
2. May the **unreferenced** `Силикатный_350+150_Озеленение` definition/table be the authority for this fresh PZU,
   or should a current planting DWG/sheet be supplied? Recommend confirming the plan+table together,
   not assigning species/counts from unreferenced data silently. For row 8, supply per-species rate/count,
   or explicitly keep its models unresolved; no invented scatter.
3. Which vertical-planning definition/marks and project zero apply? Recommend using the embedded
   `...ВП_5...Model16.10.2026` only with explicit confirmation of design-vs-existing mark mapping and
   zero (142.10 vs 142.70). No flat-site assumption, no 177.xx legend marks as relief.

The scope/source-file choice already approved is not being asked again. These are newly observed
source-content ambiguities, which change the construction and require the model/data owner.

## v002 continuation — approved sources, source-only extraction

[D290] records issue comment 6852165269. Boundary 33FBCEF, the greening table/plan and the named VP
block are now authoritative. Do not repeat those questions. Project zero and design-mark selection
remain unanswered; no height is assigned. Flowerbed rates remain explicitly unresolved by approval.

### Actual outputs and source reconciliation

- `source-reconciliation-v002.json`: exact 13-vertex boundary (12,958.738864325082 m²),
  all 52 planting INSERT handles/XY and ten numbered MULTILEADER callouts.
- Source symbol totals **1 / 4 / 6 / 17 / 24** match all five point-plant schedule rows; **52/52**
  lie inside the approved boundary. Hedge schedule quantity 4535 is NOT 4535 extracted points.
- Callout **33F02F8 = position 2 / quantity 4** resolves the four `Липа мелколистная_30` glyphs
  to schedule position 2 (Acer rubrum Red Sunset). Do NOT substitute Tilia from the glyph name.
  Position 5 glyphs say Annabelle; catalogue Hydrangea arborescens is a candidate, not cultivar proof.
- `boundary-greening-SOURCE-ONLY.dxf`: new metre-unit DXF with one closed boundary polyline,
  52 POINTs and labels. Fresh-process parser readback: **13/13** boundary vertices and **52/52**
  point XY exact, **0** constructed surfaces. This is a source extraction, not a Ground model.
- `boundary-greening-SOURCE-ONLY.png`: visually checked annotated source plan with orange proposed
  pilot window XY [820,11024]–[850,11046], clipped to the approved boundary when built. Six position-3
  maples lie there. The picture explicitly says source-only, no relief or accepted pilot.
- PNG SHA-256 `26c3d06f132532844db3a45fe80c91f79e60738dbe094e272ccf7381dbb66c85`.
- `parts-pilot-draft.json`: public `dt_ai.core.models.PartsList` validates two draft parts and
  three unanswered questions; **status=draft, gate1=null**, no invented approval. SHA-256
  `60169190f8cea4fc0bbdb1b25e12ef471a0752896f158c6a3349143f72d0d553`.
  Proposed 20k/20k pilot planning budgets are allocations, NOT measured geometry or regulation ceilings.
  Full-site covering/MAF/hedge parts and UCX decomposition remain to be resolved; this draft does not
  certify their coverage and is not the eventual full-site PartsList.

### Library checks, not placement certification

`maf-library-search-v002.json` accounts for all **32/32** DOCX MAF rows. Search of the actual
`maf_spec_vedomost_3.xlsx` and 931 shared catalogue entries found no literal-SKU matches among the
24 rows with a parsed SKU. Eight rows have no such SKU; they are not silently dropped. A broader
numeric lookup found only unrelated `C_2007_Shezlong Lion` and `12012` candidates: rejected as identity
proof. This is **not** an exhaustive absence finding for unnamed objects or all library folders.
No dimension-only, first-entry or approximate-name substitution was performed; every row remains
explicitly unresolved in the search report, not presented as placed.

Read-only inspection of a SHA-256 verified `maf-npm.blend` copy in an agent-owned Blender **5.1.2**
process loaded **368 meshes**, recorded names and triangle counts, and exited without save/export.
Source/copy SHA-256 remained `52ef2222b13a7cb4f4c3b728ee27e827cfaeb49499f3e7d7d03a5f7364d661dd`.
The 368 meshes do not provide certified article mappings; generic object names are not proof of absence.
Dimension fields are labelled scene units, not asserted as source-file metre verification.
No prior Silikatny build, placement or report was used. No library file changed.

Flora candidates from the shared catalogue: 107 / 116 / 207 / 211 / 234, not certified placement
models. `flora/v003/flora-library-v003.max` exists and is hash-pinned in the external evidence.
Abies sibirica, Red Sunset and the flowerbed species stay unresolved. Catalogue 107 height 4.538 m
is not already compliant with the schedule's >5 m lower bound. Recommend a 5.6 m nominal target
with constrained +/-10% variation (minimum >5 m), pending user size/silhouette decision and actual
library readback. Do not invent crown targets or relabel cultivar identity. Physocarpus catalogue
bush IDs 211/234 are not proof of a hedge-range material-ID/model contract.

### Commands, environment and evidence

- `uv run --extra cad python tmp/1315/v002/inspect_approved.py` — inventory success, 68 greening
  entities and 563 VP-definition entities. Heights inspected as text only, not selected.
- `uv run --extra cad python tmp/1315/v002/reconcile.py` — 52 symbols and 32 MAF rows extracted.
- SELF-FIX: importing openpyxl in the project environment failed; scoped `uv run --with openpyxl`
  succeeded. No global installation, dependency-file or shared production-code changes.
- `uv run --extra cad --with openpyxl python tmp/1315/v002/source_package.py` — source-only DXF,
  image, handle/XY and per-row candidate reports. A missing text-style diagnostic was emitted;
  independent geometry readback succeeded, not claimed as native plot or typography certification.
- `blender.exe --background --factory-startup --python tmp/1315/v002/read_maf_blend.py` — 368-mesh
  copied-etalon inventory; Blender exited normally. `max_exec.py --ping` found Max 2026 reachable;
  no Max scene was opened, saved or mutated.
- `pytest -q tests/test_decisions.py tests/test_ground_surface_requirement_sheet.py` with explicit
  card/invocation basetemp and cleared inherited PYTEST_ADDOPTS — **35 passed / 0 failed**.
  No production fix/regression or new tracked Python module; full suite not started (no PR/review yet).
- Fresh-process DXF readback — exact source XY/vertices, units=6, no constructed surfaces.
- `uv run python tmp/1315/v002/seal_evidence.py` — **15/15 evidence hashes verified** and **4/4**
  original/preserved DWG+DOCX hashes equal. Scripts and binaries are preserved externally, not git.

Evidence: `G:/Мой диск/AGR-evidence/1315-cold-silikatny/v002/` + `SHA256SUMS.txt`;
compact inventory `evidence-v002.json`. Technical QA/user acceptance/publication all incomplete.
Source-only checks cannot substitute for export topology/UV/materials/transforms checks or xView.

### Per-area remaining work — v002 overrides the v001 blocker table

| Area | Reproduced | Value / required limit | Owner / next action |
|---|---|---|---|
| Ground | Approved boundary extracted/read back, pilot window proposed | 13/13 source vertices exact; 0 constructed surfaces / source-derived Ground NPM+VPM required | Artem: project zero/design mark; worker: covering contour/material mapping, confirmed PartsList, flat-first build then relief |
| UCX | No constructed collision | 0 measured hulls / convex closed VPM-only Ground hulls with 2–10 mm gaps and <=100 mm deviation | Worker after Ground; not a zero-hull pass |
| MAF | All schedule rows accounted for, actual XLSX + generic libraries inspected | 32/32 unresolved row records; 0 certified placements / exact library article-size matches required or explicit gaps | Worker: remaining manifest/unnamed-object identity audit; missing types never modelled |
| Flora | Numbered source symbols reconciled | 52/52 point symbols; 0 library placements; hedges 4535 count only; flowerbed 133 m² unresolved | Artem: pilot exact size; worker: cultivar/profile/size checks, source hedge geometry/rates and library placements |
| Delivery | Source-only DXF readback, not model QA | 0 NPM/VPM model exports or validator runs / both required | Worker after data/parts answers; then image gate before remainder, full readback and validators |

Historical #906/#969/#1178 comparison remains not measured: no constructed pilot or delivery is being
compared to accepted/historical models as if reproduction were complete. No readiness increase or PR
closure is warranted by this checkpoint.
