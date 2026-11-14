# R4. Window / glazing

**Default level:** `standard` [D273]. Follow the [check-level policy](TASK_TO_MODEL.md#check-levels)
and [common contract](NODE_RECIPES.md#common-contract): **deviate if you state why in one line**.

## Steps

1. Choose the window per opening [D290]: if a library window (`library/windows/window_types.json`) fits the opening, place it with a small outline inset into the opening; if none fits, build it with the window generator (`adapters/max/agr_tools/windowgen_core.py`, #1338/#1345). Record the choice per opening type in the job report. [Source: Artem 2026-11-14, #1375](../../routes/npm-oks.md#branches-by-task-d290).
2. Extract openings from the authoritative drawings and assign frames and glass separate material IDs, with glass in MainGlass. [Source: KPP1 Revit DWG blocks, D238, R4 step 1](../research/agent-step-waste-1273.md#r4-window--glazing-standard).
3. Remove interior/hidden polygons; check frame/ground intersections and exclude glass below grade. [Source: Object 009 and Garibaldi, R4 step 2](../research/agent-step-waste-1273.md#r4-window--glazing-standard).
4. Count mullions against the current source opening schedule; report mismatches rather than copying a historical job's target count. [Source: KPP1 #1230 and tow02, R4 step 3](../research/agent-step-waste-1273.md#r4-window--glazing-standard).
5. Read the exported file back and run applicable window/cell validators; present source comparison or opened scene under [D273]. [Source: KPP1 / Object 009, R4 done](../research/agent-step-waste-1273.md#r4-window--glazing-standard).

## Definition of done

Opening and mullion counts match the source, frames/glass remain separate, hidden
polygons and below-grade glass are addressed, and exported-file readback plus applicable
validators are recorded. Artem accepts the picture or opened scene. Review committed
job scripts once and include them in the job's single PR [D273]. A clean count alone
is not a delivery certificate.
