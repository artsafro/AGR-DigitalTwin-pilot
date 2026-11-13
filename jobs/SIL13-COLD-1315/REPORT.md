# Cold reproduction #1315 — intake checkpoint v001

Status: **blocked on source authority, not delivered**. No constructed geometry, placements,
exports, delivery validators, visual approval or SINTEZ run. No readiness increase claimed.

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
