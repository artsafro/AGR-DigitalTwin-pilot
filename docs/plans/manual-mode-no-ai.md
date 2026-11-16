# Manual mode without AI: chunk inventory (#1374)

Status: inventory only, 2026-11-15 (finish-or-close audit of #1374). Nothing here is implemented by this note; the
gaps are filed as issues. Synthetic data: none.

Requirement (Artem 2026-11-14, #1374, voice, summarized): every pipeline chunk worked out with agents must be usable
by hand in 3ds Max as one compact tool per chunk that reads and writes JSON. Principle: one implementation - the core
behind the agent command gets the Max button, no second pipeline. [D293] keeps AGR Tools as the ideal for Artem's
manual mode, not a requirement for the agent.

Gate of #1374: cold runs pass end-to-end (#1315 still open on 2026-11-15) and the compaction stage (#1298, #1359,
#1361 closed). The child issues below carry the gate as `Blocked by: #1315`; none is `ready-for-agent`, because each
needs live Max (Artem's) or an Artem decision.

## What already exists

AGR Tools 1.1.0 (`adapters/max/agr_tools/runtime.py`, `CHANGELOG.md`, #1024) ships the OKS conveyor: stages 0-9 + the
agent stage, one big button per stage (`docs/plans/agr-tools-suite.json` `stages`, `docs/plans/agr-tools-1.x.md`).
Each button is a `*_max.py` frontend on a stdlib `*_core.py`. This is the «collapsed wrapper per chunk» #1374 asks for
on the OKS side. The agent side is `agr` (thin aliases [D271], `agr --help`) and the compaction cards #1404-#1410.

## Chunks

| # | Chunk (#1374) | Core | Max button (AGR Tools 1.1) | Agent command | Status | Follow-up |
|---|---|---|---|---|---|---|
| 1 | Openings from Revit/DWG/PDF -> JSON | `openings_core.py`, `intake_core.py`; job-local `jobs/KPP1/scripts/extract_openings.py` | stage 0 `source.intake` | none shared (`routes/revit-intake.md`) | partial | #1511 |
| 2 | Body by hand | `body_core.py` helpers | stage 1 `body.prepare` | - | done (no button expected) | - |
| 3 | Windows / doors by opening sizes | `winplace_core.py`, `windowgen_core.py`, `library/windows/` | stage 2 `win.place`, `win.generate` | #1405 (open) | windows done; doors gap | #1509 |
| 4 | Railings by spline | none (R3 recipe is manual) | none | none | gap | #1508 |
| 5 | Roof membrane separate from parapet | `roof_core.py` (R6, #1352) | stage 4 `body.roof` | - | done | - |
| 6 | Unwrap + brick/panel seams in 1 UDIM | `seams_core.py` + existing chart/fold; explicit source support pages | stage 6 `vpm.build` (no seams step) | `agr brick-seams --config JSON --out NEW.json` ([contract](../procedure/brick-seams.md)) | agent calculation only; button/native readback not done | #1510 |
| 7 | UCX by script | `ucx10_core.py`, `capsule_core.py` | stage 3 `body.capsules`, stage 9 `ucx.gap`, `ucx.stairs` | `agr ucx` = unavailable -> #1404 (open) | Max done; agent command open | #1404 |
| 8 | Attributes JSON + export + archive | `export_meta.py`, `package_core.py`, `passport_core.py` | stage 0 `project.passport`, stage 9 `pack.deliver` | `agr export-meta`, `package-vpm`, `package-npm` (#1361) | done | - |
| 9 | VPM -> NPM (planes, atlas, PAD 16 [D278]) | `npm_core.py`, `atlas_core.py`, `facadeatlas_core.py` | stage 7 `npm.build` | `agr vpm-to-npm` | done | - |
| 10 | Ground DWG -> Max (quads, textures by ID) | ground v015 route (`dt ground`) | none (1.x tail `model.ground_*`) | `agr ground`; #1406 (open) | Max gap | #1507 |
| 11 | Ground UV islands per UDIM, skirt, collisions | ground v015, `ucx10_core.py` | none (1.x tail `ucx.ground`) | #1406, #1404 (open) | Max gap | #1507 |
| 12 | MAF/Flora from DWG by specification JSON | `place_core.py`, `placegeo_core.py`, `assets_core.py` (#1044) | assets browser (`assets_max.py`), `placegeo_max.py`; no conveyor stage | #1407, #1410 (open) | partial | #1507 |
| 13 | Package and export (Ground/MAF/Flora) | as row 8 | stage 9 `pack.deliver` (OKS) | `agr package-npm` / `package-vpm` | done on the cores; no Ground stage | #1507 |

Artem's #1374 comment (procedural BODY from Revit JSON + Viz Tools Smart Attach) is a roadmap idea: #1512.

## Order when the gate opens

1. #1511 openings and #1510 seams (shared cores, agent aliases first, then the button).
2. #1509 doors and #1508 railings (need Artem's sources/dimensions).
3. #1507 Ground / MAF / Flora stage after #1404, #1406, #1407, #1410.
4. Each child ends with a manual-mode recipe in `docs/procedure/` and a «no AI» dry run by Artem on one object.
