# Revit as a source — intake, inventory, export, VPM/NPM modelling (#1362)

**Route for agents; reuse only.** Not approval of any model, export or delivery. It adds no code:
steps without a shared tool are listed under "Candidate commands", not implemented.

## Кратко (для Артёма)

Revit — это **источник**: модель заказчика читаем и по ней моделируем ВПМ/НПМ ОКС, но саму модель
не меняем. Порядок: (1) хешированная **копия** RVT 2022 → 2025, исходник не сохраняется;
(2) инвентаризация только чтением: уровни и ±0.000, единицы, базовая точка/точка съёмки,
категории, семейства/типы, материалы, связи, рабочие наборы → `sources.json` и PartsList;
(3) экспорт в **новые версионные** папки: FBX по группам, TwinPack-срезы этажей, IFC офлайн как запасной путь;
(4) моделирование: геометрию Revit (треугольники FBX) используем как измеряемую подложку и
источник размеров/ID/типов, а quad-мастер строим заново (окна — генератор окон, BODY — рецепт R6);
(5) готово, когда все факты из модели или от Артёма, а не придуманы, и экспорт прочитан обратно.
Пробный прогон на KPP1 (Revit был запущен, но оба add-in не отвечали) — по сохранённым дампам:
[DRY-RUN](../jobs/KPP1/revit-intake-1362/DRY-RUN.md). Он нашёл 9 пробелов, которые этот маршрут теперь закрывает (таблица «Hot spots» и чек-лист).

## Entry: narrow context, explicit contract

Read AGENTS.md, the card, `jobs/<ID>/{TASK.md,STATE.md,LESSONS.md,sources.json,object.json}`, then
[revit-mcp skill](../.agents/skills/revit-mcp/SKILL.md) (risk gate + session rules [D237]) and the
Revit rows of [CAPABILITIES](../docs/agents/CAPABILITIES.md#dcc-tool-risk-classes). For the modelling
steps continue with [routes/npm-oks.md](npm-oks.md) (`oks-npm`), [BODY](../docs/domain/areas/body.md),
[windows](../docs/domain/areas/windows.md), [derivation](../docs/domain/areas/derivation.md) and
[TASK_TO_MODEL](../docs/procedure/TASK_TO_MODEL.md). Check [conflicts](../docs/domain/conflicts.md) before
picking a value where Revit and a drawing disagree; never pick a side silently.

Session rules [D237] apply from the first call: read-only by default, study first, one Revit request at
a time, never invent a dimension/level/type/parameter, finish with ids + checked/open lists.

## Route by step

| Step | Tool today (reuse) | Boundary / risk class | Evidence required |
|---|---|---|---|
| 1. Intake: copy | Native Revit UI: open the RVT 2022 source, upgrade, *Save As* a new 2025 copy (no MCP save tool exists, revit-mcp skill) | Source is never saved; a workshared source is opened **detached**; the detached copy is never synced or saved by an MCP check | `sha256` of the source before and after, `sha256` + size + mtime of the copy, both in `jobs/<ID>/sources.json` (`kind: customer-source` / `working-copy`) |
| 1. Intake: route | `python C:/Users/artsafro/hermes_kanban/scripts/revit_exec.py --ping` (exit 0 ok, 2 unreachable, 3 busy), then `--cmd get_document_info` | `revit-http-2025` (port 7891) = read-only inspection, under the lock `agr-revit-live.lock`; `revit-bridge` (named pipe) = FBX export only; not interchangeable | Document title/path equals the hashed copy, `modified=false`; unreachable → offline (step 3c), say so |
| 2. Inventory | `revit-http-2025` read-only tools: `revit_get_document_info`, `revit_list_levels`, `revit_list_categories`, `revit_list_elements` (paged, per category), `revit_list_families`, `revit_list_materials`, `revit_get_linked_files`, `revit_get_worksets`, `revit_get_model_health`, `revit_get_element_info`/`revit_get_parameter` for named elements | Read-only class only. `revit-bridge` `agr_census` is **not** read-only in the risk table (only `revit_status` is): do not use it for inventory until it is inspected | One inventory JSON in a new versioned folder + the checklist below filled; `modified=false` before and after |
| 3a. Export: FBX groups | `node jobs/KPP1/scripts/export_revit_groups.mjs <elements.json> <new_out_dir> [groups]` (RevitBridge `agr_export_fbx`, groups by element id) — job-local precedent; copy and adapt the group filter per job | `versioned-write`: needs task authorization and a new folder. An unknown category name exports the **whole model**, so group by element ids | Per group: element count, bytes, `savedDocument=false`; every category of the census is in a group or in a drop list with its reason |
| 3b. Export: storey bands | `node tools/source/measure_spec_revit_twin.mjs <new-folder>` (TwinPack `twin_floor_manifest` / `twin_export_floor`; refuses an existing folder), then `uv run dt spec extract --dump <folder>/twin-data.json --object jobs/<ID>/object.json --output <new>` (`src/dt_ai/spec/revit_twin.py`) | Export only; `modified_before`/`modified_after` recorded by the script | `twin-data.json` (coordinates, levels, roofs), per band `floor.json` + `reference.obj`, spec report + questions merged into `jobs/<ID>/questions.md` |
| 3c. Export: offline | Revit unavailable: IFC exported by Artem/customer + [revit-ifc-offline-intake](../experiments/revit-ifc-offline-intake/README.md) | Synthetic-IFC pilot, **not** a native Revit or generic IFC importer, `delivery_passed=false` | Use only for what its strict/geometric contract covers; everything else is a question |
| 4. Modelling | Blender: import FBX groups (`jobs/KPP1/scripts/inspect_source.py`, `dump_source.py`, `match_ids.py`), OBR22 chain ([accepted workflow](../docs/agr/case_studies/OBR22_ACCEPTED_WORKFLOW.md): contour → openings → shell → windows → instances → UV); windows: [window_types.json](../library/windows/window_types.json) + windowgen (`adapters/max/agr_tools/windowgen_core.py`, [#1338 test](../jobs/KPP1/windowgen-1338/README.md)); openings: `jobs/KPP1/scripts/extract_openings.py`; BODY/roof/parapet: [R6](../docs/procedure/node-r6-oks-body-facade.md) | Revit FBX is triangulated: a measured underlay (ids, types, materials, dimensions, transform), **not** the quad master. Rebuild the master; reuse real Revit geometry only as reference (curved walls, roofs in `reference.obj`) | Source overlay / Hausdorff vs the Revit reference, ids matched, every Revit part either built or listed with a reason |
| 5. NPM/VPM, export, review | [routes/npm-oks.md](npm-oks.md) steps 5–8 | Same gates as any OKS job | Exported-file readback, xView, checker, Artem's visual verdict |

**Program per step** (choose and say why in one line, [D270]): Revit — only for reading and exporting the
RVT (nothing else opens it); Blender — FBX import, census, contour/shell/UV build (the KPP1 and OBR22
chains are Blender scripts run headless); 3ds Max — AGR Tools windowgen/checker steps and the Max 2026
quad acceptance view. Confirm application, document, units and version before each DCC call.

## Inventory checklist (step 2, read-only)

Record each line with its value **and** the call that produced it; a missing value is a question, not a default.

1. **Document**: title, path, Revit version, workshared / detached, `modified` flag; equals the hashed copy.
2. **Units**: display units (e.g. «Миллиметры») *and* the unit of each dump field. Revit internal length is
   **feet**: `revit_list_levels`/census elevations may be in feet (KPP1: −13.7795 = −4.200 m); convert and say so.
3. **Levels and ±0.000**: every level with name and elevation in m; which are storeys, which are structural or
   parapet levels (KPP1: +7.700 structural, +8.650 parapet are not floors, [D045]); levels below 0.000 named
   with their use. Record in `object.json` `levels` / `revit_levels`.
4. **Coordinates**: Project Base Point, Survey Point, shared elevation and angle to true north
   (`twin-data.json` `coordinates`); 0.000 as an absolute mark goes to the placement-height fields of
   [#1330](../docs/research/placement-heights-1330.md) ([D279]): project zero vs ground mark, `height_system`
   stays `unknown` unless a source names it. The frame into object coordinates goes to `object.json` `frames`.
5. **Categories present** with instance counts: walls (by function and type: exterior / inner / facade
   layers), curtain walls + panels + mullions, windows, doors, roofs, floors, stairs (runs, landings,
   stringers), railings, generic models, equipment; non-facade categories (ceilings, furniture, plumbing,
   mass) go to the drop list with a reason.
6. **Families / types** used by the facade with their dimensions (width, height, sill, thickness) from
   parameters, not from the mesh.
7. **Materials / finishes** with `instanceCount > 0` and their colour codes (RAL); names may be bare codes («1021»).
8. **Linked models** (`revit_get_linked_files`) and **worksets** (`revit_get_worksets`): list, or an explicit empty
   list; a linked model is a separate source with its own hash and transform.
9. **Model health** warnings that touch facade elements.

Into `jobs/<ID>/sources.json`: RVT source and copy (path, sha256, size, version, role), each export folder
(tool, args, hashes via `SHA256SUMS.txt`). Into the PartsList (`dt_ai.core.models.PartsList`): one part per
facade group with its Revit ids/types and source kind `model`; user Gate 1 before any build.

## Export rules (step 3)

- Outputs go to `jobs/<ID>/outputs/<stage>-v00N/` (gitignored) or `C:/x/<job>/...`; never into an existing folder,
  never over an accepted version. Large binaries (FBX, OBJ) are not committed: copy them to
  `G:/Мой диск/AGR-evidence/<issue>-<topic>/` + `SHA256SUMS.txt` (fallback `C:/x/<topic>/evidence/`), commit the hashes and the path.
- Names: group FBX `<group>.fbx` + `<group>.export.json` sidecar (document, types, element ids); band
  exports `band-<n>/floor.json` + `reference.obj` + `twin-data.json`. Write absolute paths into sidecars only
  together with the folder hash; a moved folder makes them stale.
- Which to export: FBX groups when the job builds from meshes (KPP1); storey bands when the spec extractor
  (contour, levels, openings) is the next step; both may be needed. Interior is not exported for a facade
  model (OBR22: a full Revit interior was the wrong composition).

## Done criteria

- Intake: copy hashed, source hash unchanged, route and document confirmed, `modified=false` before and after
  every session; no save, sync or reload issued by an agent.
- Inventory: all nine checklist lines filled with value + call, or listed as an open question.
- Export: every census category is in an exported group or in the drop list with a reason; per-group counts
  match the census; hashes recorded; no output path equals an input or an accepted version.
- Modelling: every dimension, level, type and finish traces to a Revit call, a drawing or Artem; overlay vs
  the Revit reference measured; then the npm-oks definition of done. `passed=true` only per npm-oks.

## Facts that come from Artem, never invented ([D237] rule 4)

Which source wins when Revit and the drawings/PDF disagree (OBR22: facade PDFs over Revit; KPP1 [D238]);
whether a part is facade or attachment (entrance frames, vestibules [D027]); roof/parapet heights when
Revit has only structural levels ([D254]); what to do with levels below 0.000; the height system and the
placement fit ([D262], [D279]); finishes missing from Revit materials; the profile/window variant choice
(#1338); whether a detached copy may ever be saved.

## Hot spots from real jobs — what the route now prevents

| Job | What went wrong | Route rule |
|---|---|---|
| KPP1 | `agr_export_fbx` with an unknown category name exports the whole model | Step 3a: groups by element id; counts per group checked |
| KPP1 | Revit door families carry 3D swing volumes; raw Revit stair triangles; concave joined roof triangles | Step 4: FBX is an underlay; stair rebuilt from parameters, roof quads split |
| KPP1 | Facade layers modelled as inner walls (plinth cladding); entrance frames 0.70 m outside L1 | Checklist 5 by function *and* type; attachments are questions [D027] |
| KPP1 | Roof level is not a Revit level (7.700 structural + 0.209 covering = 7.909) | Checklist 3; [D045] / [D254], from Artem when unclear |
| KPP1 #1330 | RVT hash unavailable, 0.000 taken from a cached observation | Step 1: hash source and copy into `sources.json`; re-inventory instead of trusting old dumps |
| KPP1 #1336 | Latin «C» in «Cтеклопакет» silently dropped glass | Match family/type names after casefold + homoglyph normalisation (`extract_openings.py` `norm`); unmatched names are a reported list |
| OBR22 | Full interior from Revit, all panel coordinates propagated over the facade, 19 UDIM | Export rules: no interior; OBR22 workflow order; shared UV groups |
| OBR22 | Revit MCP became unavailable mid-job | Work from the saved extraction and say so; no claim of a new live test |
| TEC26 | Intake used copied Max scenes, not RVT; its KPP is KPP1 (`object.json` id `tec26-kpp1`) | No Revit-specific lesson beyond KPP1; scene intake rules stay in TEC26 STATE |

## Candidate commands (not implemented)

1. `agr revit-inventory --out NEW.json [--sources jobs/<ID>/sources.json]` — the step-2 checklist in one
   read-only pass over `revit_exec.py` (feet→m, `modified` before/after, refuses an existing output).
   Today: one `revit_exec.py --cmd` per item; the KPP1 `inspect_revit.json` has no committed producer.
2. `agr revit-export-groups --elements E.json --groups GROUPS.json --out NEW` — generalised
   `export_revit_groups.mjs`: group config instead of KPP1 name filters, drop list with reasons, sidecar
   with `savedDocument`, `elementCount`, `bytes`. Today: job-local script, those fields only on stdout.
3. `agr source-hash --source RVT --copy RVT25 --job ID` — hash before/after into `sources.json`. Today: `sha256sum`
   by hand; the upgrade itself stays native Revit UI (no tool can do it).
4. `agr revit-twin --out NEW` — alias of `node tools/source/measure_spec_revit_twin.mjs` followed by
   `dt spec extract --dump`. Today: the two commands above.

These are proposals for a later card; `agr --help` shows only what exists.
