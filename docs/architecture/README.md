# Route maps: two reading views (#1425)

Start with the short scheme to answer how today's route hands artifacts to the next step.
Open its owners/migration table for rules, module owners, live-bypass counts, exact locations,
reasons for differences, migration issues and completion criteria. Russian labels are for Artem.

| Route | Short scheme (SVG / editable) | Owners and migration |
|---|---|---|
| НПМ / ОКС | [SVG](npm-oks-route-scheme.svg) / [Excalidraw](npm-oks-route-scheme.excalidraw) | [Table](npm-oks-route-owners.md) |
| ВПМ / ОКС | [SVG](vpm-oks-route-scheme.svg) / [Excalidraw](vpm-oks-route-scheme.excalidraw) | [Table](vpm-oks-route-owners.md) |
| Ground | [SVG](ground-route-scheme.svg) / [Excalidraw](ground-route-scheme.excalidraw) | [Table](ground-route-owners.md) |
| МАФ | [SVG](maf-route-scheme.svg) / [Excalidraw](maf-route-scheme.excalidraw) | [Table](maf-route-owners.md) |
| Флора | [SVG](flora-route-scheme.svg) / [Excalidraw](flora-route-scheme.excalidraw) | [Table](flora-route-owners.md) |
| Пакет и сдача | [SVG](package-route-scheme.svg) / [Excalidraw](package-route-scheme.excalidraw) | [Table](package-route-owners.md) |

## Source of truth and regeneration

Existing `*-route.events.yaml` and `*contexts.yaml` remain the only inputs. `scheme` in each events
YAML groups the existing ordered stages into at most seven handoffs; every stage must occur exactly
once and in order. `ru`, `artifact_ru` and `gate_ru` give the working step, passed artifact and acceptance
condition. Conditions are not claims that a real delivery has passed. Detailed event storms and context
interfaces remain available as supplementary views, not the starting canvas. Context arrows now bind
owner nodes, never duplicate lists; exact duplicate locations occur in the Markdown tables only.

```bash
uv run python tools/architecture/route_map.py
uv run python tools/architecture/route_map.py --check
uv run python tools/architecture/duplicate_guard.py
uv run python tools/architecture/regen_after_merge.py --merge origin/main   # merge conflict on maps (#1558)
```

Generated maps are `merge=ours` in `.gitattributes`: never resolve them by hand; merge, then regenerate
(`docs/agents/WORKFLOW.md`, "Merging PRs: generated maps and decision rows").

Both new views carry the same SHA-256 revision of their parsed YAML snapshot. This is the architecture
source revision, **not** a fabricated revision/hash of a customer's input or an execution receipt.
Each scheme separately names the source-revision evidence required by its route. A concrete run must
supply its actual revision/manifest; this documentation does not fill missing provenance.

Counts reuse `duplicate_guard.rows_of` and #1424's statuses. They count unique `(owner, at)` registry
locations across the maps relevant to that owner, not files, pink notes or historical copies. A repeated
map description is not an extra bypass. `historical`, `wrapper` and `own-duty` remain distinct and are
listed in the table. `live-bypass` rows link their migration issue, or explicitly say no card exists.
Run the existing guard to validate those declarations against actual call chains; generation itself
is not a second call-chain checker or a new package-control layer.

The export owner is explicit: Max `export_core.py`; Blender NPM `tools/derive/export_npm.py`, and the
existing job-specific VPM producer. ZIP writing stays in `package_core.py`; package composition and
validation remain the existing checks. No core, DCC protocol, runtime manifest or acceptance policy
is introduced or changed here. Technical QA, visual acceptance and publication stay separate.

PNG renders for Artem are external evidence under `G:/Мой диск/AGR-evidence/1425-route-maps/`
(with `SHA256SUMS.txt`), attached to the card's review handoff; no PNG or LFS pointer is committed.

## Adding documentation [D386]

Find the topic below and edit its owner. A separate file needs a PR rationale and an index entry: give a
new topic one owner, or add the new file in `Related` and link back to the owner from that file.
Use stable topic IDs; do not register copies under synonyms. The guard checks declarations and links,
not whether different topic names cover the same substance; that is a review check.

The check covers tracked `docs/` files. The decision ledger, generated project state and generated route
views with tracked source YAML do not get separate owners. Job evidence under `jobs/` is outside this index.
Only docs in the frozen `legacy_hidden_docs` cut in [search-noise.yaml](search-noise.yaml) are exempt while
they remain historical and hidden. Regenerating `.ignore` does not exempt new docs.

Put `Status: active (YYYY-MM-DD)`, `Status: done (YYYY-MM-DD)` or
`Status: superseded by <repo path> (YYYY-MM-DD)` immediately after each plan title (blank lines allowed).
For JSON plans use `status` and `status_date`. The date is the status classification date;
`done` describes the plan, not acceptance of the underlying production delivery.
Update search visibility with `uv run python tools/architecture/search_noise.py --write-ignore` after a status change.
Check ownership and status with `uv run python tools/architecture/search_noise.py --check-docs`.
Finished plans stay readable by direct link but are hidden from ordinary agent search.

## Planning owners

One owner per planning responsibility (#1868, #1869, #1870); the others are historical and point to it.

| Responsibility | Owner | Historical |
|---|---|---|
| Idea intake | `hermes_kanban/moltbook/ideas.md` (outside this repo) | - |
| Actionable queue | [backlog.md](../backlog.md) | - |
| Roadmap record | [research/roadmap-149-audit.md](../research/roadmap-149-audit.md) | [research/capability-roadmap.md](../research/capability-roadmap.md) |
| AGR Tools scope [D393] | [agr-tools/OVERVIEW.md](../agr-tools/OVERVIEW.md) | [plans/agr-tools-1.x.md](../plans/agr-tools-1.x.md), [plans/agr-tools-suite.md](../plans/agr-tools-suite.md), [plans/manual-mode-no-ai.md](../plans/manual-mode-no-ai.md) |
| MCP design, shipped [D394] | `src/agr_mcp/README.md`, `agr-mcp` in [agents/CAPABILITIES.md](../agents/CAPABILITIES.md) | [plans/agr-mcp-target.md](../plans/agr-mcp-target.md) (closed target), [plans/agr-mcp.md](../plans/agr-mcp.md) |

## Documentation ownership

| Topic | Owner | Related |
|---|---|---|
| adr/0001-material-ids-are-a-reading-scheme | [adr/0001-material-ids-are-a-reading-scheme.md](../adr/0001-material-ids-are-a-reading-scheme.md) |  |
| agents/agents-reference | [agents/agents-reference.md](../agents/agents-reference.md) |  |
| agents/agr-tools-1-0-rules | [agents/agr-tools-1.0-rules.md](../agents/agr-tools-1.0-rules.md) |  |
| agents/agr-tools-impl-rules | [agents/agr-tools-impl-rules.md](../agents/agr-tools-impl-rules.md) |  |
| agents/capabilities | [agents/CAPABILITIES.md](../agents/CAPABILITIES.md) |  |
| agents/codex | [agents/codex.md](../agents/codex.md) |  |
| agents/commands | [agents/COMMANDS.md](../agents/COMMANDS.md) |  |
| agents/dcc-offline-workflows | [agents/dcc-offline-workflows.md](../agents/dcc-offline-workflows.md) |  |
| agents/decision-trees | [agents/decision-trees.json](../agents/decision-trees.json) | [agents/decision-trees/ground-npm.md](../agents/decision-trees/ground-npm.md), [agents/decision-trees/ground-vpm.md](../agents/decision-trees/ground-vpm.md), [agents/decision-trees/library-publish.md](../agents/decision-trees/library-publish.md), [agents/decision-trees/maf-npm-to-vpm.md](../agents/decision-trees/maf-npm-to-vpm.md), [agents/decision-trees/npm-to-vpm.md](../agents/decision-trees/npm-to-vpm.md), [agents/decision-trees/oks-npm.md](../agents/decision-trees/oks-npm.md), [agents/decision-trees/oks-npm-lite.md](../agents/decision-trees/oks-npm-lite.md), [agents/decision-trees/oks-vpm.md](../agents/decision-trees/oks-vpm.md), [agents/decision-trees/sintez-fix.md](../agents/decision-trees/sintez-fix.md), [agents/decision-trees/vpm-to-npm.md](../agents/decision-trees/vpm-to-npm.md) |
| agents/domain | [agents/domain.md](../agents/domain.md) |  |
| agents/examples/swarm/writers-json | [agents/examples/swarm/writers.json](../agents/examples/swarm/writers.json) |  |
| agents/harness-inventory | [agents/harness-inventory.md](../agents/harness-inventory.md) |  |
| agents/issue-tracker | [agents/issue-tracker.md](../agents/issue-tracker.md) |  |
| agents/job-scripts-baseline-txt | [agents/job_scripts_baseline.txt](../agents/job_scripts_baseline.txt) |  |
| agents/kanban | [agents/KANBAN.md](../agents/KANBAN.md) |  |
| agents/merge-policy | [agents/MERGE_POLICY.yaml](../agents/MERGE_POLICY.yaml) | [agents/MERGE_POLICY.md](../agents/MERGE_POLICY.md), [agents/STEWARD_NOTE.md](../agents/STEWARD_NOTE.md) |
| agents/naming | [agents/NAMING.md](../agents/NAMING.md) |  |
| agents/review-checklist | [agents/REVIEW_CHECKLIST.md](../agents/REVIEW_CHECKLIST.md) |  |
| agents/roles | [agents/ROLES.md](../agents/ROLES.md) |  |
| agents/skeleton-harvest/2026-11-23 | [agents/skeleton-harvest/2026-11-23.md](../agents/skeleton-harvest/2026-11-23.md) |  |
| agents/skeleton-template-json | [agents/skeleton.template.json](../agents/skeleton.template.json) |  |
| agents/skeletons | [agents/SKELETONS.md](../agents/SKELETONS.md) | [agents/SKELETONS-stages.md](../agents/SKELETONS-stages.md) |
| agents/skeletons-json | [agents/skeletons.json](../agents/skeletons.json) |  |
| agents/task-intake | [agents/task-intake.md](../agents/task-intake.md) |  |
| agents/triage-labels | [agents/triage-labels.md](../agents/triage-labels.md) |  |
| agents/workflow | [agents/WORKFLOW.md](../agents/WORKFLOW.md) |  |
| agents/working-principles | [agents/working-principles.md](../agents/working-principles.md) |  |
| agr-tools/assets | [agr-tools/assets.md](../agr-tools/assets.md) |  |
| agr-tools/flow-svg | [agr-tools/flow.svg](../agr-tools/flow.svg) |  |
| agr-tools/guide | [agr-tools/GUIDE.md](../agr-tools/GUIDE.md) |  |
| agr-tools/overview | [agr-tools/OVERVIEW.md](../agr-tools/OVERVIEW.md) | [plans/agr-tools-1.x.md](../plans/agr-tools-1.x.md), [plans/agr-tools-suite.md](../plans/agr-tools-suite.md), [plans/manual-mode-no-ai.md](../plans/manual-mode-no-ai.md) |
| agr-tools/release-0-9-0-acceptance | [agr-tools/release-0.9.0-acceptance.md](../agr-tools/release-0.9.0-acceptance.md) |  |
| agr/adapter-extraction | [agr/ADAPTER_EXTRACTION.md](../agr/ADAPTER_EXTRACTION.md) |  |
| agr/adapter-report | [agr/ADAPTER_REPORT.md](../agr/ADAPTER_REPORT.md) |  |
| agr/body-shell-adapter | [agr/BODY_SHELL_ADAPTER.md](../agr/BODY_SHELL_ADAPTER.md) |  |
| agr/case-studies/casefile-index | [agr/case_studies/CASEFILE_INDEX.md](../agr/case_studies/CASEFILE_INDEX.md) |  |
| agr/case-studies/facades-atlas-partial-acceptance | [agr/case_studies/FACADES_ATLAS_PARTIAL_ACCEPTANCE.md](../agr/case_studies/FACADES_ATLAS_PARTIAL_ACCEPTANCE.md) |  |
| agr/case-studies/glb-a-main-atlas | [agr/case_studies/GLB_A_MAIN_ATLAS.md](../agr/case_studies/GLB_A_MAIN_ATLAS.md) |  |
| agr/case-studies/glb-ab-reference-and-planes | [agr/case_studies/GLB_AB_REFERENCE_AND_PLANES.md](../agr/case_studies/GLB_AB_REFERENCE_AND_PLANES.md) |  |
| agr/case-studies/glb-b-main-atlas | [agr/case_studies/GLB_B_MAIN_ATLAS.md](../agr/case_studies/GLB_B_MAIN_ATLAS.md) |  |
| agr/case-studies/glb-sketchup-connection | [agr/case_studies/GLB_SKETCHUP_CONNECTION.md](../agr/case_studies/GLB_SKETCHUP_CONNECTION.md) |  |
| agr/case-studies/ground-contours-and-npm | [agr/case_studies/GROUND_CONTOURS_AND_NPM.md](../agr/case_studies/GROUND_CONTOURS_AND_NPM.md) |  |
| agr/case-studies/kpp1-vpm-npm-v005 | [agr/case_studies/KPP1_VPM_NPM_V005.md](../agr/case_studies/KPP1_VPM_NPM_V005.md) |  |
| agr/case-studies/mashi-lp-scene-audit | [agr/case_studies/MASHI_LP_SCENE_AUDIT.md](../agr/case_studies/MASHI_LP_SCENE_AUDIT.md) |  |
| agr/case-studies/obr22-accepted-workflow | [agr/case_studies/OBR22_ACCEPTED_WORKFLOW.md](../agr/case_studies/OBR22_ACCEPTED_WORKFLOW.md) |  |
| agr/case-studies/psu275-vpm-npm-delivery-v003 | [agr/case_studies/PSU275_VPM_NPM_DELIVERY_V003.md](../agr/case_studies/PSU275_VPM_NPM_DELIVERY_V003.md) |  |
| agr/case-studies/readme | [agr/case_studies/README.md](../agr/case_studies/README.md) |  |
| agr/case-studies/skug26-k5-ac-screens-vpm | [agr/case_studies/SKUG26_K5_AC_SCREENS_VPM.md](../agr/case_studies/SKUG26_K5_AC_SCREENS_VPM.md) |  |
| agr/case-studies/sosh1150-continuous-wall-uv-fbx | [agr/case_studies/SOSH1150_CONTINUOUS_WALL_UV_FBX.md](../agr/case_studies/SOSH1150_CONTINUOUS_WALL_UV_FBX.md) |  |
| agr/case-studies/template | [agr/case_studies/TEMPLATE.md](../agr/case_studies/TEMPLATE.md) |  |
| agr/case-studies/vyatskaya-tow02-midpoly | [agr/case_studies/VYATSKAYA_TOW02_MIDPOLY.md](../agr/case_studies/VYATSKAYA_TOW02_MIDPOLY.md) |  |
| agr/case-studies/window-frames-box-lights | [agr/case_studies/WINDOW_FRAMES_BOX_LIGHTS.md](../agr/case_studies/WINDOW_FRAMES_BOX_LIGHTS.md) |  |
| agr/decisions/adr-0001-synthetic-scope | [agr/decisions/ADR-0001-synthetic-scope.md](../agr/decisions/ADR-0001-synthetic-scope.md) |  |
| agr/decisions/adr-0002-source-discrepancies | [agr/decisions/ADR-0002-source-discrepancies.md](../agr/decisions/ADR-0002-source-discrepancies.md) |  |
| agr/decisions/adr-0003-contracts | [agr/decisions/ADR-0003-contracts.md](../agr/decisions/ADR-0003-contracts.md) |  |
| agr/decisions/adr-0004-reuse-installed-toolchains | [agr/decisions/ADR-0004-reuse-installed-toolchains.md](../agr/decisions/ADR-0004-reuse-installed-toolchains.md) |  |
| agr/decisions/obr22-facade-pdf-uv-trial | [agr/decisions/OBR22_FACADE_PDF_UV_TRIAL.md](../agr/decisions/OBR22_FACADE_PDF_UV_TRIAL.md) |  |
| agr/decisions/obr22-npm-scale-v012 | [agr/decisions/OBR22_NPM_SCALE_V012.md](../agr/decisions/OBR22_NPM_SCALE_V012.md) |  |
| agr/decisions/obr22-procedural-textures-v010 | [agr/decisions/OBR22_PROCEDURAL_TEXTURES_V010.md](../agr/decisions/OBR22_PROCEDURAL_TEXTURES_V010.md) |  |
| agr/decisions/obr22-shared-uv-v011 | [agr/decisions/OBR22_SHARED_UV_V011.md](../agr/decisions/OBR22_SHARED_UV_V011.md) |  |
| agr/digital-twin-ai-project-brief | [agr/DIGITAL_TWIN_AI_PROJECT_BRIEF.md](../agr/DIGITAL_TWIN_AI_PROJECT_BRIEF.md) |  |
| agr/examples/readiness-evidence-json | [agr/examples/readiness-evidence.json](../agr/examples/readiness-evidence.json) |  |
| agr/examples/readme | [agr/examples/README.md](../agr/examples/README.md) |  |
| agr/examples/verification-json | [agr/examples/verification.json](../agr/examples/verification.json) |  |
| agr/experience-capture | [agr/EXPERIENCE_CAPTURE.md](../agr/EXPERIENCE_CAPTURE.md) |  |
| agr/exterior-adapter | [agr/EXTERIOR_ADAPTER.md](../agr/EXTERIOR_ADAPTER.md) |  |
| agr/geometry-quality-mdc | [agr/geometry-quality.mdc](../agr/geometry-quality.mdc) |  |
| agr/geometry-rules | [agr/GEOMETRY_RULES.md](../agr/GEOMETRY_RULES.md) |  |
| agr/index | [agr/INDEX.md](../agr/INDEX.md) |  |
| agr/inventory/applications-json | [agr/inventory/applications.json](../agr/inventory/applications.json) |  |
| agr/inventory/autocad-menus-json | [agr/inventory/autocad-menus.json](../agr/inventory/autocad-menus.json) |  |
| agr/inventory/blender-preferences-json | [agr/inventory/blender-preferences.json](../agr/inventory/blender-preferences.json) |  |
| agr/inventory/catalog-csv | [agr/inventory/catalog.csv](../agr/inventory/catalog.csv) |  |
| agr/inventory/catalog-html | [agr/inventory/catalog.html](../agr/inventory/catalog.html) |  |
| agr/inventory/catalog-json | [agr/inventory/catalog.json](../agr/inventory/catalog.json) |  |
| agr/inventory/coverage-json | [agr/inventory/coverage.json](../agr/inventory/coverage.json) |  |
| agr/inventory/duplicates-json | [agr/inventory/duplicates.json](../agr/inventory/duplicates.json) |  |
| agr/inventory/fbx-runtime-json | [agr/inventory/fbx-runtime.json](../agr/inventory/fbx-runtime.json) |  |
| agr/inventory/folder-followup-evidence-json | [agr/inventory/folder-followup-evidence.json](../agr/inventory/folder-followup-evidence.json) |  |
| agr/inventory/geoagr-13-63-evidence-json | [agr/inventory/geoagr-13.63-evidence.json](../agr/inventory/geoagr-13.63-evidence.json) |  |
| agr/inventory/geoagr-13-63-review | [agr/inventory/GEOAGR_13_63_REVIEW.md](../agr/inventory/GEOAGR_13_63_REVIEW.md) |  |
| agr/inventory/integration-plan | [agr/inventory/INTEGRATION_PLAN.md](../agr/inventory/INTEGRATION_PLAN.md) |  |
| agr/inventory/max-runtime-json | [agr/inventory/max-runtime.json](../agr/inventory/max-runtime.json) |  |
| agr/inventory/mcp-registrations-json | [agr/inventory/mcp-registrations.json](../agr/inventory/mcp-registrations.json) |  |
| agr/inventory/mse-evidence-json | [agr/inventory/mse-evidence.json](../agr/inventory/mse-evidence.json) |  |
| agr/inventory/mse-review | [agr/inventory/MSE_REVIEW.md](../agr/inventory/MSE_REVIEW.md) |  |
| agr/inventory/npm-vpm-map | [agr/inventory/NPM_VPM_MAP.md](../agr/inventory/NPM_VPM_MAP.md) |  |
| agr/inventory/octopus-bindings-json | [agr/inventory/octopus-bindings.json](../agr/inventory/octopus-bindings.json) |  |
| agr/inventory/packages-json | [agr/inventory/packages.json](../agr/inventory/packages.json) |  |
| agr/inventory/readme | [agr/inventory/README.md](../agr/inventory/README.md) |  |
| agr/inventory/stage-map-json | [agr/inventory/stage-map.json](../agr/inventory/stage-map.json) |  |
| agr/inventory/zavod-and-max-plugins-review | [agr/inventory/ZAVOD_AND_MAX_PLUGINS_REVIEW.md](../agr/inventory/ZAVOD_AND_MAX_PLUGINS_REVIEW.md) |  |
| agr/lessons/sketchup-composite-window-openings | [agr/lessons/SKETCHUP_COMPOSITE_WINDOW_OPENINGS.md](../agr/lessons/SKETCHUP_COMPOSITE_WINDOW_OPENINGS.md) |  |
| agr/local-orchestration/engineering | [agr/local-orchestration/ENGINEERING.md](../agr/local-orchestration/ENGINEERING.md) |  |
| agr/local-orchestration/run-evidence | [agr/local-orchestration/RUN_EVIDENCE.md](../agr/local-orchestration/RUN_EVIDENCE.md) |  |
| agr/readiness-report | [agr/READINESS_REPORT.md](../agr/READINESS_REPORT.md) |  |
| agr/readme | [agr/README.md](../agr/README.md) |  |
| agr/research/max-workbench/expanded-inventory-json | [agr/research/max-workbench/expanded-inventory.json](../agr/research/max-workbench/expanded-inventory.json) |  |
| agr/research/max-workbench/expansion-2026-09-27 | [agr/research/max-workbench/EXPANSION_2026-09-27.md](../agr/research/max-workbench/EXPANSION_2026-09-27.md) |  |
| agr/research/max-workbench/inventory-json | [agr/research/max-workbench/inventory.json](../agr/research/max-workbench/inventory.json) |  |
| agr/research/max-workbench/review | [agr/research/max-workbench/REVIEW.md](../agr/research/max-workbench/REVIEW.md) |  |
| agr/research/max-workbench/scan-summary-txt | [agr/research/max-workbench/scan-summary.txt](../agr/research/max-workbench/scan-summary.txt) |  |
| agr/sintez-checks-1-6-1-json | [agr/sintez_checks_1.6.1.json](../agr/sintez_checks_1.6.1.json) |  |
| agr/traceability-html | [agr/traceability.html](../agr/traceability.html) |  |
| agr/uv-reuse-mdc | [agr/uv-reuse.mdc](../agr/uv-reuse.mdc) |  |
| agr/uv-rules | [agr/UV_RULES.md](../agr/UV_RULES.md) |  |
| agr/workflow/pipeline | [agr/workflow/pipeline.md](../agr/workflow/pipeline.md) |  |
| architecture/contexts-yaml | [architecture/contexts.yaml](contexts.yaml) |  |
| architecture/flora-contexts-yaml | [architecture/flora-contexts.yaml](flora-contexts.yaml) |  |
| architecture/flora-route-events-yaml | [architecture/flora-route.events.yaml](flora-route.events.yaml) |  |
| architecture/ground-contexts-yaml | [architecture/ground-contexts.yaml](ground-contexts.yaml) |  |
| architecture/ground-route-events-yaml | [architecture/ground-route.events.yaml](ground-route.events.yaml) |  |
| architecture/hygiene-profile-yaml | [architecture/hygiene-profile.yaml](hygiene-profile.yaml) |  |
| architecture/maf-contexts-yaml | [architecture/maf-contexts.yaml](maf-contexts.yaml) |  |
| architecture/maf-route-events-yaml | [architecture/maf-route.events.yaml](maf-route.events.yaml) |  |
| architecture/npm-oks-route-events-yaml | [architecture/npm-oks-route.events.yaml](npm-oks-route.events.yaml) |  |
| architecture/package-contexts-yaml | [architecture/package-contexts.yaml](package-contexts.yaml) |  |
| architecture/package-route-events-yaml | [architecture/package-route.events.yaml](package-route.events.yaml) |  |
| architecture/report-1359 | [architecture/report-1359.md](report-1359.md) |  |
| architecture/report-1424 | [architecture/report-1424.md](report-1424.md) |  |
| architecture/report-1441 | [architecture/report-1441.md](report-1441.md) |  |
| architecture/report-routes-maf-flora-package | [architecture/report-routes-maf-flora-package.md](report-routes-maf-flora-package.md) |  |
| architecture/report-routes-vpm-ground | [architecture/report-routes-vpm-ground.md](report-routes-vpm-ground.md) |  |
| architecture/route-map-and-doc-ownership-index | [architecture/README.md](README.md) |  |
| architecture/search-noise-yaml | [architecture/search-noise.yaml](search-noise.yaml) |  |
| architecture/vpm-oks-contexts-yaml | [architecture/vpm-oks-contexts.yaml](vpm-oks-contexts.yaml) |  |
| architecture/vpm-oks-route-events-yaml | [architecture/vpm-oks-route.events.yaml](vpm-oks-route.events.yaml) |  |
| archive | [ARCHIVE.md](../ARCHIVE.md) |  |
| cases | [cases.md](../cases.md) |  |
| cases/staropetrovskiy-npm-planters-v008 | [cases/staropetrovskiy-npm-planters-v008.md](../cases/staropetrovskiy-npm-planters-v008.md) |  |
| ci/runner-setup | [ci/runner-setup.md](../ci/runner-setup.md) |  |
| decisions-detail | [decisions-detail.md](../decisions-detail.md) |  |
| deliveries/vatutino-ground-2026-10-20 | [deliveries/vatutino-ground-2026-10-20.md](../deliveries/vatutino-ground-2026-10-20.md) |  |
| deliveries/vatutino-site-2026-11-09 | [deliveries/vatutino-site-2026-11-09.md](../deliveries/vatutino-site-2026-11-09.md) |  |
| deliveries/vyatskaya-tow02-npm-user-v05-2026-10-21 | [deliveries/vyatskaya-tow02-npm-user-v05-2026-10-21.md](../deliveries/vyatskaya-tow02-npm-user-v05-2026-10-21.md) |  |
| domain/areas/body | [domain/areas/body.md](../domain/areas/body.md) |  |
| domain/areas/decor | [domain/areas/decor.md](../domain/areas/decor.md) |  |
| domain/areas/derivation | [domain/areas/derivation.md](../domain/areas/derivation.md) |  |
| domain/areas/flora | [domain/areas/flora.md](../domain/areas/flora.md) |  |
| domain/areas/ground-surface | [domain/areas/ground-surface.md](../domain/areas/ground-surface.md) |  |
| domain/areas/groundel-maf | [domain/areas/groundel-maf.md](../domain/areas/groundel-maf.md) |  |
| domain/areas/package | [domain/areas/package.md](../domain/areas/package.md) |  |
| domain/areas/textures | [domain/areas/textures.md](../domain/areas/textures.md) |  |
| domain/areas/ucx | [domain/areas/ucx.md](../domain/areas/ucx.md) |  |
| domain/areas/ucx-evidence/review | [domain/areas/ucx-evidence/review.md](../domain/areas/ucx-evidence/review.md) |  |
| domain/areas/uv-atlas | [domain/areas/uv-atlas.md](../domain/areas/uv-atlas.md) |  |
| domain/areas/windows | [domain/areas/windows.md](../domain/areas/windows.md) |  |
| domain/conflict-choices-2026-10-09 | [domain/conflict-choices-2026-10-09.md](../domain/conflict-choices-2026-10-09.md) |  |
| domain/conflicts | [domain/conflicts.md](../domain/conflicts.md) |  |
| domain/export-import | [domain/export-import.md](../domain/export-import.md) |  |
| domain/fbx-metallic-channel | [domain/fbx-metallic-channel.md](../domain/fbx-metallic-channel.md) |  |
| domain/geometry | [domain/geometry.md](../domain/geometry.md) |  |
| domain/materials | [domain/materials.md](../domain/materials.md) |  |
| domain/npm-vpm | [domain/npm-vpm.md](../domain/npm-vpm.md) |  |
| domain/patterns/attached-decor | [domain/patterns/attached-decor.md](../domain/patterns/attached-decor.md) |  |
| domain/patterns/contour-niche | [domain/patterns/contour-niche.md](../domain/patterns/contour-niche.md) |  |
| domain/patterns/facade-decor-inset | [domain/patterns/facade-decor-inset.md](../domain/patterns/facade-decor-inset.md) |  |
| domain/patterns/floor-step | [domain/patterns/floor-step.md](../domain/patterns/floor-step.md) |  |
| domain/patterns/index | [domain/patterns/INDEX.md](../domain/patterns/INDEX.md) |  |
| domain/patterns/markup-helpers | [domain/patterns/markup-helpers.md](../domain/patterns/markup-helpers.md) |  |
| domain/patterns/non-90-corner | [domain/patterns/non-90-corner.md](../domain/patterns/non-90-corner.md) |  |
| domain/patterns/opening-plane | [domain/patterns/opening-plane.md](../domain/patterns/opening-plane.md) |  |
| domain/patterns/parapet | [domain/patterns/parapet.md](../domain/patterns/parapet.md) |  |
| domain/patterns/primitive-first | [domain/patterns/primitive-first.md](../domain/patterns/primitive-first.md) |  |
| domain/patterns/roof-inset-plane | [domain/patterns/roof-inset-plane.md](../domain/patterns/roof-inset-plane.md) |  |
| domain/patterns/roof-screen-enclosure | [domain/patterns/roof-screen-enclosure.md](../domain/patterns/roof-screen-enclosure.md) |  |
| domain/patterns/terrace | [domain/patterns/terrace.md](../domain/patterns/terrace.md) |  |
| domain/patterns/typical-floor-repeat | [domain/patterns/typical-floor-repeat.md](../domain/patterns/typical-floor-repeat.md) |  |
| domain/patterns/vent-grille | [domain/patterns/vent-grille.md](../domain/patterns/vent-grille.md) |  |
| domain/patterns/wall-from-contour | [domain/patterns/wall-from-contour.md](../domain/patterns/wall-from-contour.md) |  |
| domain/requirements-2026 | [domain/requirements-2026.md](../domain/requirements-2026.md) |  |
| domain/sources | [domain/sources.md](../domain/sources.md) |  |
| domain/uv-textures | [domain/uv-textures.md](../domain/uv-textures.md) |  |
| domain/validation | [domain/validation.md](../domain/validation.md) |  |
| evidence/1365-review-textures/native-max-json | [evidence/1365-review-textures/native-max.json](../evidence/1365-review-textures/native-max.json) |  |
| evidence/render-qa/blender-probes-json | [evidence/render-qa/blender-probes.json](../evidence/render-qa/blender-probes.json) |  |
| evidence/render-qa/readme | [evidence/render-qa/README.md](../evidence/render-qa/README.md) |  |
| evidence/render-qa/synthetic-fixtures-json | [evidence/render-qa/synthetic-fixtures.json](../evidence/render-qa/synthetic-fixtures.json) |  |
| evidence/render-qa/vatutino-source-json | [evidence/render-qa/vatutino-source.json](../evidence/render-qa/vatutino-source.json) |  |
| evidence/render-qa/vatutino-v014-json | [evidence/render-qa/vatutino-v014.json](../evidence/render-qa/vatutino-v014.json) |  |
| experiments/2026-11-02-dreamsim-ac08/results-csv | [experiments/2026-11-02-dreamsim-ac08/results.csv](../experiments/2026-11-02-dreamsim-ac08/results.csv) |  |
| experiments/2026-11-02-dreamsim-ac08/results-json | [experiments/2026-11-02-dreamsim-ac08/results.json](../experiments/2026-11-02-dreamsim-ac08/results.json) |  |
| experiments/acad-coreconsole-agr-plans | [experiments/acad-coreconsole-agr-plans.md](../experiments/acad-coreconsole-agr-plans.md) |  |
| experiments/bim-3dsmax-agr | [experiments/bim-3dsmax-agr.md](../experiments/bim-3dsmax-agr.md) |  |
| experiments/bim-blender-agr | [experiments/bim-blender-agr.md](../experiments/bim-blender-agr.md) |  |
| experiments/bim-revit-agr | [experiments/bim-revit-agr.md](../experiments/bim-revit-agr.md) |  |
| experiments/blender-bpy-automation | [experiments/blender-bpy-automation.md](../experiments/blender-bpy-automation.md) |  |
| experiments/blender-exec-session | [experiments/blender-exec-session.md](../experiments/blender-exec-session.md) |  |
| experiments/blender-handoff | [experiments/blender-handoff.md](../experiments/blender-handoff.md) |  |
| experiments/blender-mesh-audit-live | [experiments/blender-mesh-audit-live.md](../experiments/blender-mesh-audit-live.md) |  |
| experiments/body-capsules | [experiments/body.capsules.md](../experiments/body.capsules.md) |  |
| experiments/body-roof | [experiments/body.roof.md](../experiments/body.roof.md) |  |
| experiments/flora-bark-containment | [experiments/flora-bark-containment.md](../experiments/flora-bark-containment.md) |  |
| experiments/flora-geometry-decomposition | [experiments/flora-geometry-decomposition.md](../experiments/flora-geometry-decomposition.md) |  |
| experiments/flora-library-audit | [experiments/flora-library-audit.md](../experiments/flora-library-audit.md) |  |
| experiments/flora-library-audit-findings | [experiments/flora-library-audit-findings.md](../experiments/flora-library-audit-findings.md) |  |
| experiments/hyp-100 | [experiments/hyp-100.md](../experiments/hyp-100.md) |  |
| experiments/hyp-101 | [experiments/hyp-101.md](../experiments/hyp-101.md) |  |
| experiments/hyp-107 | [experiments/hyp-107.md](../experiments/hyp-107.md) |  |
| experiments/hyp-281 | [experiments/hyp-281.md](../experiments/hyp-281.md) |  |
| experiments/hyp-283 | [experiments/hyp-283.md](../experiments/hyp-283.md) |  |
| experiments/hyp-358 | [experiments/hyp-358.md](../experiments/hyp-358.md) |  |
| experiments/hyp-359 | [experiments/hyp-359.md](../experiments/hyp-359.md) |  |
| experiments/hyp-386 | [experiments/hyp-386.md](../experiments/hyp-386.md) |  |
| experiments/hyp-415 | [experiments/hyp-415.md](../experiments/hyp-415.md) |  |
| experiments/hyp-603 | [experiments/hyp-603.md](../experiments/hyp-603.md) |  |
| experiments/hyp-626 | [experiments/hyp-626.md](../experiments/hyp-626.md) |  |
| experiments/hyp-638 | [experiments/hyp-638.md](../experiments/hyp-638.md) |  |
| experiments/hyp-663 | [experiments/hyp-663.md](../experiments/hyp-663.md) |  |
| experiments/hyp-748 | [experiments/hyp-748.md](../experiments/hyp-748.md) |  |
| experiments/hyp-766 | [experiments/hyp-766.md](../experiments/hyp-766.md) |  |
| experiments/hyp-84 | [experiments/hyp-84.md](../experiments/hyp-84.md) |  |
| experiments/hyp-89 | [experiments/hyp-89.md](../experiments/hyp-89.md) |  |
| experiments/hyp-91 | [experiments/hyp-91.md](../experiments/hyp-91.md) |  |
| experiments/hyp-93 | [experiments/hyp-93.md](../experiments/hyp-93.md) |  |
| experiments/issue-105-author-receipts | [experiments/issue-105-author-receipts.md](../experiments/issue-105-author-receipts.md) |  |
| experiments/issue-105-evidence/adoption-available-report-json | [experiments/issue-105-evidence/adoption-available-report.json](../experiments/issue-105-evidence/adoption-available-report.json) |  |
| experiments/issue-105-evidence/adoption-regression-report-json | [experiments/issue-105-evidence/adoption-regression-report.json](../experiments/issue-105-evidence/adoption-regression-report.json) |  |
| experiments/issue-105-evidence/generated-json | [experiments/issue-105-evidence/generated.json](../experiments/issue-105-evidence/generated.json) |  |
| experiments/issue-105-evidence/regression-report-json | [experiments/issue-105-evidence/regression-report.json](../experiments/issue-105-evidence/regression-report.json) |  |
| experiments/light-check | [experiments/light.check.md](../experiments/light.check.md) |  |
| experiments/light-export | [experiments/light.export.md](../experiments/light.export.md) |  |
| experiments/max-headless-agr-roundtrip | [experiments/max-headless-agr-roundtrip.md](../experiments/max-headless-agr-roundtrip.md) |  |
| experiments/mcp-dcc-bridges | [experiments/mcp-dcc-bridges.md](../experiments/mcp-dcc-bridges.md) |  |
| experiments/model-attach-by-material | [experiments/model.attach_by_material.md](../experiments/model.attach_by_material.md) |  |
| experiments/model-move-apart | [experiments/model.move_apart.md](../experiments/model.move_apart.md) |  |
| experiments/npm-build | [experiments/npm.build.md](../experiments/npm.build.md) |  |
| experiments/npm-to-vpm | [experiments/npm.to_vpm.md](../experiments/npm.to_vpm.md) |  |
| experiments/place-drop-to-ground | [experiments/place.drop_to_ground.md](../experiments/place.drop_to_ground.md) |  |
| experiments/place-flora-repair | [experiments/place.flora_repair.md](../experiments/place.flora_repair.md) |  |
| experiments/place-replace | [experiments/place.replace.md](../experiments/place.replace.md) |  |
| experiments/place-schedule | [experiments/place.schedule.md](../experiments/place.schedule.md) |  |
| experiments/qa-address | [experiments/qa.address.md](../experiments/qa.address.md) |  |
| experiments/qa-omk-te | [experiments/qa.omk_te.md](../experiments/qa.omk_te.md) |  |
| experiments/revit-ifc-offline-intake | [experiments/revit-ifc-offline-intake.md](../experiments/revit-ifc-offline-intake.md) |  |
| experiments/scripts-logic | [experiments/scripts-logic.md](../experiments/scripts-logic.md) |  |
| experiments/tex-plug-colour | [experiments/tex.plug_colour.md](../experiments/tex.plug_colour.md) |  |
| experiments/tow02-hand-finish-face-diff | [experiments/tow02-hand-finish-face-diff.md](../experiments/tow02-hand-finish-face-diff.md) |  |
| experiments/ucx-gap | [experiments/ucx.gap.md](../experiments/ucx.gap.md) |  |
| experiments/ucx-rename | [experiments/ucx.rename.md](../experiments/ucx.rename.md) |  |
| experiments/udim-distortion | [experiments/udim.distortion.md](../experiments/udim.distortion.md) |  |
| experiments/udim-ids-to-udims | [experiments/udim.ids_to_udims.md](../experiments/udim.ids_to_udims.md) |  |
| experiments/udim-matid-unwrap | [experiments/udim.matid_unwrap.md](../experiments/udim.matid_unwrap.md) |  |
| experiments/udim-rescale | [experiments/udim.rescale.md](../experiments/udim.rescale.md) |  |
| experiments/vlm-6view-checklist-objects-json | [experiments/vlm-6view-checklist.objects.json](../experiments/vlm-6view-checklist.objects.json) |  |
| experiments/vpm-build | [experiments/vpm.build.md](../experiments/vpm.build.md) |  |
| experiments/vpm-build-maps | [experiments/vpm.build-maps.md](../experiments/vpm.build-maps.md) |  |
| experiments/win-generate | [experiments/win.generate.md](../experiments/win.generate.md) |  |
| experiments/win-place | [experiments/win.place.md](../experiments/win.place.md) |  |
| grill/modeling-architecture-2026-10-16 | [grill/modeling-architecture-2026-10-16.md](../grill/modeling-architecture-2026-10-16.md) |  |
| ground-site-1535 | [ground-site-1535.md](../ground-site-1535.md) |  |
| handoff | [HANDOFF.md](../HANDOFF.md) |  |
| handoff-template | [HANDOFF.template.md](../HANDOFF.template.md) |  |
| herdr | [HERDR.md](../HERDR.md) |  |
| library/audit | [library/AUDIT.md](../library/AUDIT.md) |  |
| library/audit-counts-json | [library/audit-counts.json](../library/audit-counts.json) |  |
| library/evidence-json | [library/EVIDENCE.json](../library/EVIDENCE.json) |  |
| library/outside-retrieval-1316 | [library/outside-retrieval-1316.md](../library/outside-retrieval-1316.md) |  |
| library/publish | [library/PUBLISH.md](../library/PUBLISH.md) |  |
| library/template | [library/TEMPLATE.md](../library/TEMPLATE.md) |  |
| library/visual-loop | [library/visual-loop.md](../library/visual-loop.md) |  |
| library/window-seating-1449 | [library/window-seating-1449.md](../library/window-seating-1449.md) |  |
| methods/building-body/kpp1-drawing/mapping-questions | [methods/building-body/kpp1-drawing/mapping-questions.md](../methods/building-body/kpp1-drawing/mapping-questions.md) |  |
| methods/building-body/kpp1-drawing/plan-account-json | [methods/building-body/kpp1-drawing/plan-account.json](../methods/building-body/kpp1-drawing/plan-account.json) |  |
| methods/building-body/kpp1-drawing/plan-contours-json | [methods/building-body/kpp1-drawing/plan-contours.json](../methods/building-body/kpp1-drawing/plan-contours.json) |  |
| methods/building-body/kpp1-drawing/sheet-census-json | [methods/building-body/kpp1-drawing/sheet-census.json](../methods/building-body/kpp1-drawing/sheet-census.json) |  |
| methods/building-body/results-jsonl | [methods/building-body/results.jsonl](../methods/building-body/results.jsonl) |  |
| methods/building-body/variants | [methods/building-body/VARIANTS.md](../methods/building-body/VARIANTS.md) |  |
| methods/ground-terrain/results | [methods/ground-terrain/RESULTS.md](../methods/ground-terrain/RESULTS.md) |  |
| methods/ground-terrain/results-jsonl | [methods/ground-terrain/results.jsonl](../methods/ground-terrain/results.jsonl) |  |
| methods/ground-terrain/variants | [methods/ground-terrain/VARIANTS.md](../methods/ground-terrain/VARIANTS.md) |  |
| methods/ground-terrain/when | [methods/ground-terrain/WHEN.md](../methods/ground-terrain/WHEN.md) |  |
| methods/readme | [methods/README.md](../methods/README.md) |  |
| methods/sources/agent-lookup/questions-json | [methods/sources/agent-lookup/questions.json](../methods/sources/agent-lookup/questions.json) |  |
| methods/sources/variants | [methods/sources/VARIANTS.md](../methods/sources/VARIANTS.md) |  |
| methods/texturing-by-drawings/variants | [methods/texturing-by-drawings/VARIANTS.md](../methods/texturing-by-drawings/VARIANTS.md) |  |
| methods/ucx-collisions/results | [methods/ucx-collisions/RESULTS.md](../methods/ucx-collisions/RESULTS.md) |  |
| methods/ucx-collisions/results-jsonl | [methods/ucx-collisions/results.jsonl](../methods/ucx-collisions/results.jsonl) |  |
| methods/ucx-collisions/variants | [methods/ucx-collisions/VARIANTS.md](../methods/ucx-collisions/VARIANTS.md) |  |
| methods/ucx-collisions/when | [methods/ucx-collisions/WHEN.md](../methods/ucx-collisions/WHEN.md) |  |
| methods/windows-glazing/results-jsonl | [methods/windows-glazing/results.jsonl](../methods/windows-glazing/results.jsonl) |  |
| methods/windows-glazing/variants | [methods/windows-glazing/VARIANTS.md](../methods/windows-glazing/VARIANTS.md) |  |
| papercuts/readme | [papercuts/README.md](../papercuts/README.md) |  |
| pipeline | [pipeline.md](../pipeline.md) |  |
| pipeline-flora-textures | [pipeline-flora-textures.md](../pipeline-flora-textures.md) |  |
| pipeline-tools | [pipeline-tools.md](../pipeline-tools.md) |  |
| planning/agr-mcp-target-design | [plans/agr-mcp-target.md](../plans/agr-mcp-target.md) | [plans/agr-mcp.md](../plans/agr-mcp.md) |
| planning/agr-tools-command-catalogue | [plans/agr-tools-suite.json](../plans/agr-tools-suite.json) |  |
| planning/capability-roadmap-149-closure | [research/roadmap-149-audit.md](../research/roadmap-149-audit.md) | [research/capability-roadmap.md](../research/capability-roadmap.md) |
| planning/unsolved-work-backlog | [backlog.md](../backlog.md) |  |
| plans/425-maf-route-2026-11 | [plans/425-maf-route-2026-11.md](../plans/425-maf-route-2026-11.md) |  |
| plans/flora-426-route-2026-11 | [plans/flora-426-route-2026-11.md](../plans/flora-426-route-2026-11.md) |  |
| plans/system-audit-1298 | [plans/system-audit-1298.md](../plans/system-audit-1298.md) |  |
| plans/telegram-findings-rollout | [plans/telegram-findings-rollout.md](../plans/telegram-findings-rollout.md) |  |
| procedure/accepted-geometry | [procedure/ACCEPTED_GEOMETRY.md](../procedure/ACCEPTED_GEOMETRY.md) |  |
| procedure/brick-seams | [procedure/brick-seams.md](../procedure/brick-seams.md) |  |
| procedure/evidence/1445/accepted-2026-11-14-json | [procedure/evidence/1445/accepted-2026-11-14.json](../procedure/evidence/1445/accepted-2026-11-14.json) |  |
| procedure/evidence/1445/accepted-v004-json | [procedure/evidence/1445/accepted-v004.json](../procedure/evidence/1445/accepted-v004.json) |  |
| procedure/evidence/1445/dry-run | [procedure/evidence/1445/dry-run.md](../procedure/evidence/1445/dry-run.md) |  |
| procedure/evidence/1445/rejected-v008e-json | [procedure/evidence/1445/rejected-v008e.json](../procedure/evidence/1445/rejected-v008e.json) |  |
| procedure/node-r1-colouring | [procedure/node-r1-colouring.md](../procedure/node-r1-colouring.md) |  |
| procedure/node-r2-library-maf | [procedure/node-r2-library-maf.md](../procedure/node-r2-library-maf.md) |  |
| procedure/node-r3-fence-railing-gates | [procedure/node-r3-fence-railing-gates.md](../procedure/node-r3-fence-railing-gates.md) |  |
| procedure/node-r4-window-glazing | [procedure/node-r4-window-glazing.md](../procedure/node-r4-window-glazing.md) |  |
| procedure/node-r5-ground | [procedure/node-r5-ground.md](../procedure/node-r5-ground.md) |  |
| procedure/node-r6-oks-body-facade | [procedure/node-r6-oks-body-facade.md](../procedure/node-r6-oks-body-facade.md) |  |
| procedure/node-r7-flora-star-planes | [procedure/node-r7-flora-star-planes.md](../procedure/node-r7-flora-star-planes.md) |  |
| procedure/node-recipes | [procedure/NODE_RECIPES.md](../procedure/NODE_RECIPES.md) |  |
| procedure/oks-modelling-plan | [procedure/oks-modelling-plan.md](../procedure/oks-modelling-plan.md) |  |
| procedure/review-textures | [procedure/REVIEW_TEXTURES.md](../procedure/REVIEW_TEXTURES.md) |  |
| procedure/task-to-model | [procedure/TASK_TO_MODEL.md](../procedure/TASK_TO_MODEL.md) |  |
| procedure/task-to-model-dry-run | [procedure/task-to-model-dry-run.md](../procedure/task-to-model-dry-run.md) |  |
| project-state-milestones | [PROJECT_STATE.milestones.md](../PROJECT_STATE.milestones.md) |  |
| qa/component-volume | [qa/component-volume.md](../qa/component-volume.md) |  |
| qa/evidence/issue-111/regression/report-json | [qa/evidence/issue-111/regression/report.json](../qa/evidence/issue-111/regression/report.json) |  |
| qa/evidence/issue-111/verification-json | [qa/evidence/issue-111/verification.json](../qa/evidence/issue-111/verification.json) |  |
| research/3dsmax-scripting | [research/3dsmax-scripting.md](../research/3dsmax-scripting.md) |  |
| research/ac08-kernel-ops-752 | [research/ac08-kernel-ops-752.md](../research/ac08-kernel-ops-752.md) |  |
| research/agent-first-audit-2068 | [research/agent-first-audit-2068.md](../research/agent-first-audit-2068.md) |  |
| research/agent-harness-practices | [research/agent-harness-practices.md](../research/agent-harness-practices.md) |  |
| research/agent-step-waste-1273 | [research/agent-step-waste-1273.md](../research/agent-step-waste-1273.md) |  |
| research/agent-step-waste-1273/data/sessions-csv | [research/agent-step-waste-1273/data/sessions.csv](../research/agent-step-waste-1273/data/sessions.csv) |  |
| research/agent-step-waste-1273/measure-py | [research/agent-step-waste-1273/measure.py](../research/agent-step-waste-1273/measure.py) |  |
| research/autoresearch-pdf-dimensions | [research/autoresearch-pdf-dimensions.md](../research/autoresearch-pdf-dimensions.md) |  |
| research/autoresearch-trainer-artifact-first | [research/autoresearch-trainer-artifact-first.md](../research/autoresearch-trainer-artifact-first.md) |  |
| research/autoresearch-trainer-g22-adapter | [research/autoresearch-trainer-g22-adapter.md](../research/autoresearch-trainer-g22-adapter.md) |  |
| research/autoresearch-trainer-gate1 | [research/autoresearch-trainer-gate1.md](../research/autoresearch-trainer-gate1.md) |  |
| research/autoresearch-trainer-tower-id | [research/autoresearch-trainer-tower-id.md](../research/autoresearch-trainer-tower-id.md) |  |
| research/autoresearch-view-face-elv | [research/autoresearch-view-face-elv.md](../research/autoresearch-view-face-elv.md) |  |
| research/autoresearch-view-face-elv/fixture-json | [research/autoresearch-view-face-elv/fixture.json](../research/autoresearch-view-face-elv/fixture.json) |  |
| research/autoresearch-view-face-elv/posthoc-py | [research/autoresearch-view-face-elv/posthoc.py](../research/autoresearch-view-face-elv/posthoc.py) |  |
| research/autoresearch-view-face-elv/receipt-json | [research/autoresearch-view-face-elv/receipt.json](../research/autoresearch-view-face-elv/receipt.json) |  |
| research/autoresearch-view-face-elv/run-py | [research/autoresearch-view-face-elv/run.py](../research/autoresearch-view-face-elv/run.py) |  |
| research/autoresearch-view-face-elv/test-run-py | [research/autoresearch-view-face-elv/test_run.py](../research/autoresearch-view-face-elv/test_run.py) |  |
| research/autoresearch-view-face-grade | [research/autoresearch-view-face-grade.md](../research/autoresearch-view-face-grade.md) |  |
| research/autoresearch-view-face-grade/receipt-json | [research/autoresearch-view-face-grade/receipt.json](../research/autoresearch-view-face-grade/receipt.json) |  |
| research/autoresearch-view-face-grade/run-py | [research/autoresearch-view-face-grade/run.py](../research/autoresearch-view-face-grade/run.py) |  |
| research/autoresearch-view-face-grade/test-run-py | [research/autoresearch-view-face-grade/test_run.py](../research/autoresearch-view-face-grade/test_run.py) |  |
| research/bench-npm-derivation | [research/bench-npm-derivation.md](../research/bench-npm-derivation.md) |  |
| research/bim-3dsmax-agr | [research/bim-3dsmax-agr.md](../research/bim-3dsmax-agr.md) |  |
| research/bim-blender-agr | [research/bim-blender-agr.md](../research/bim-blender-agr.md) |  |
| research/blender-bpy-automation | [research/blender-bpy-automation.md](../research/blender-bpy-automation.md) |  |
| research/body-mesh-method | [research/body-mesh-method.md](../research/body-mesh-method.md) |  |
| research/body-mesh-method/loop-anatomy-py | [research/body-mesh-method/loop_anatomy.py](../research/body-mesh-method/loop_anatomy.py) |  |
| research/body-mesh-method/proto-lattice-py | [research/body-mesh-method/proto_lattice.py](../research/body-mesh-method/proto_lattice.py) |  |
| research/body-modelling | [research/body-modelling.md](../research/body-modelling.md) |  |
| research/body-modelling-1618/analyze-grid-py | [research/body-modelling-1618/analyze_grid.py](../research/body-modelling-1618/analyze_grid.py) |  |
| research/body-modelling-1618/band-census-py | [research/body-modelling-1618/band_census.py](../research/body-modelling-1618/band_census.py) |  |
| research/body-modelling-1618/curve-census-py | [research/body-modelling-1618/curve_census.py](../research/body-modelling-1618/curve_census.py) |  |
| research/body-modelling-1618/dump-mesh-py | [research/body-modelling-1618/dump_mesh.py](../research/body-modelling-1618/dump_mesh.py) |  |
| research/body-modelling-1618/wire-sheet-py | [research/body-modelling-1618/wire_sheet.py](../research/body-modelling-1618/wire_sheet.py) |  |
| research/body-modelling-summary-ru | [research/body-modelling-summary-ru.md](../research/body-modelling-summary-ru.md) |  |
| research/body-wall-layout-1446-json | [research/body-wall-layout-1446.json](../research/body-wall-layout-1446.json) | [research/body-wall-layout-1446.md](../research/body-wall-layout-1446.md) |
| research/bpy-wheel-viability | [research/bpy-wheel-viability.md](../research/bpy-wheel-viability.md) |  |
| research/checker-mutation-freeze-json | [research/checker-mutation-freeze.json](../research/checker-mutation-freeze.json) |  |
| research/cold-oks-sokolniki-2001 | [research/cold-oks-sokolniki-2001.md](../research/cold-oks-sokolniki-2001.md) |  |
| research/cold-oks-sokolniki-2001/cold-oks-score-py | [research/cold-oks-sokolniki-2001/cold_oks_score.py](../research/cold-oks-sokolniki-2001/cold_oks_score.py) |  |
| research/elv-agent-vs-delivered | [research/elv-agent-vs-delivered.md](../research/elv-agent-vs-delivered.md) |  |
| research/fab-megascans-licence-2026-11 | [research/fab-megascans-licence-2026-11.md](../research/fab-megascans-licence-2026-11.md) |  |
| research/flora-texture-diagnosis | [research/flora-texture-diagnosis.md](../research/flora-texture-diagnosis.md) |  |
| research/geojson-d220-customer-files | [research/geojson-d220-customer-files.md](../research/geojson-d220-customer-files.md) |  |
| research/geojson-overflow-caller-exposure | [research/geojson-overflow-caller-exposure.md](../research/geojson-overflow-caller-exposure.md) |  |
| research/ground-npm-atlas-fbx-roundtrip | [research/ground-npm-atlas-fbx-roundtrip.md](../research/ground-npm-atlas-fbx-roundtrip.md) |  |
| research/ground-site-moskovsky-gap-evidence | [research/ground-site-moskovsky-gap-evidence.md](../research/ground-site-moskovsky-gap-evidence.md) |  |
| research/guard-vs-dcg-2026-11 | [research/guard-vs-dcg-2026-11.md](../research/guard-vs-dcg-2026-11.md) |  |
| research/ifc-intake-src-contract | [research/ifc-intake-src-contract.md](../research/ifc-intake-src-contract.md) |  |
| research/job-artifact-name-contract | [research/job-artifact-name-contract.md](../research/job-artifact-name-contract.md) |  |
| research/job-retro-tec26-oks-pr570 | [research/job-retro-tec26-oks-pr570.md](../research/job-retro-tec26-oks-pr570.md) |  |
| research/job-retro-tec26-oks-pr574 | [research/job-retro-tec26-oks-pr574.md](../research/job-retro-tec26-oks-pr574.md) |  |
| research/job-retro-vyatskaya-tow02-pr392 | [research/job-retro-vyatskaya-tow02-pr392.md](../research/job-retro-vyatskaya-tow02-pr392.md) |  |
| research/job-retro-vyatskaya-tow02-pr515 | [research/job-retro-vyatskaya-tow02-pr515.md](../research/job-retro-vyatskaya-tow02-pr515.md) |  |
| research/kpi-card-kind-attribution-boundary | [research/kpi-card-kind-attribution-boundary.md](../research/kpi-card-kind-attribution-boundary.md) |  |
| research/kpp1-cold-skeleton-1608 | [research/kpp1-cold-skeleton-1608.md](../research/kpp1-cold-skeleton-1608.md) |  |
| research/link-info-inherit-fbx-2026-11 | [research/link-info-inherit-fbx-2026-11.md](../research/link-info-inherit-fbx-2026-11.md) |  |
| research/maf-npm-to-vpm-1745 | [research/maf-npm-to-vpm-1745.md](../research/maf-npm-to-vpm-1745.md) |  |
| research/max-ultra-mcp-vs-agr-mcp-plan | [research/max-ultra-mcp-vs-agr-mcp-plan.md](../research/max-ultra-mcp-vs-agr-mcp-plan.md) |  |
| research/mcp-dcc-bridges | [research/mcp-dcc-bridges.md](../research/mcp-dcc-bridges.md) |  |
| research/mesh-quality-1616/calibration-json | [research/mesh-quality-1616/calibration.json](../research/mesh-quality-1616/calibration.json) |  |
| research/mesh-quality-1616/observe-log-r1-jsonl | [research/mesh-quality-1616/observe-log-r1.jsonl](../research/mesh-quality-1616/observe-log-r1.jsonl) |  |
| research/mesh-quality-1616/observe-log-r2-jsonl | [research/mesh-quality-1616/observe-log-r2.jsonl](../research/mesh-quality-1616/observe-log-r2.jsonl) |  |
| research/mesh-quality-1616/observe-log-r3-jsonl | [research/mesh-quality-1616/observe-log-r3.jsonl](../research/mesh-quality-1616/observe-log-r3.jsonl) |  |
| research/mesh-quality-1616/observe-log-r4-jsonl | [research/mesh-quality-1616/observe-log-r4.jsonl](../research/mesh-quality-1616/observe-log-r4.jsonl) |  |
| research/mesh-quality-1616/report | [research/mesh-quality-1616/REPORT.md](../research/mesh-quality-1616/REPORT.md) |  |
| research/mesh-quality-1634 | [research/mesh-quality-1634.md](../research/mesh-quality-1634.md) |  |
| research/model-flora-dry-walk-2026-10-16 | [research/model-flora-dry-walk-2026-10-16.md](../research/model-flora-dry-walk-2026-10-16.md) |  |
| research/model-maf-dry-walk-2026-10-16 | [research/model-maf-dry-walk-2026-10-16.md](../research/model-maf-dry-walk-2026-10-16.md) |  |
| research/npm-atlas-padding-1331 | [research/npm-atlas-padding-1331.md](../research/npm-atlas-padding-1331.md) |  |
| research/ntr-pdf-corpus-pilot-json | [research/ntr-pdf-corpus-pilot.json](../research/ntr-pdf-corpus-pilot.json) | [research/ntr-pdf-corpus-pilot.md](../research/ntr-pdf-corpus-pilot.md) |
| research/pdf-album-binding-2b | [research/pdf-album-binding-2b.md](../research/pdf-album-binding-2b.md) |  |
| research/pdf-album-fallback | [research/pdf-album-fallback.md](../research/pdf-album-fallback.md) |  |
| research/pdf-album-pipeline | [research/pdf-album-pipeline.md](../research/pdf-album-pipeline.md) |  |
| research/pdf-model-audit-mode-a | [research/pdf-model-audit-mode-a.md](../research/pdf-model-audit-mode-a.md) |  |
| research/placement-heights-1330 | [research/placement-heights-1330.md](../research/placement-heights-1330.md) |  |
| research/pr-body-cross-card-contamination | [research/pr-body-cross-card-contamination.md](../research/pr-body-cross-card-contamination.md) |  |
| research/project-state-snapshot-freshness | [research/project-state-snapshot-freshness.md](../research/project-state-snapshot-freshness.md) |  |
| research/reuse-1296/benchmark | [research/reuse-1296/benchmark.md](../research/reuse-1296/benchmark.md) |  |
| research/reuse-1296/data/duplicate-groups | [research/reuse-1296/data/duplicate-groups.md](../research/reuse-1296/data/duplicate-groups.md) |  |
| research/reuse-1296/data/duplicates-csv | [research/reuse-1296/data/duplicates.csv](../research/reuse-1296/data/duplicates.csv) |  |
| research/reuse-1296/data/inventory-csv | [research/reuse-1296/data/inventory.csv](../research/reuse-1296/data/inventory.csv) |  |
| research/reuse-1296/data/snapshot-json | [research/reuse-1296/data/snapshot.json](../research/reuse-1296/data/snapshot.json) |  |
| research/reuse-1296/measure-py | [research/reuse-1296/measure.py](../research/reuse-1296/measure.py) |  |
| research/reuse-1296/report | [research/reuse-1296/report.md](../research/reuse-1296/report.md) |  |
| research/revit-api-automation | [research/revit-api-automation.md](../research/revit-api-automation.md) |  |
| research/roof-equipment | [research/roof-equipment.md](../research/roof-equipment.md) |  |
| research/scripts-logic | [research/scripts-logic.md](../research/scripts-logic.md) |  |
| research/shared-packaging-1361 | [research/shared-packaging-1361.md](../research/shared-packaging-1361.md) |  |
| research/sintez-agr-checker-dissection | [research/sintez-agr-checker-dissection.md](../research/sintez-agr-checker-dissection.md) |  |
| research/sintez-fix-1744 | [research/sintez-fix-1744.md](../research/sintez-fix-1744.md) |  |
| research/source-face-concave-containment | [research/source-face-concave-containment.md](../research/source-face-concave-containment.md) |  |
| research/source-finish-stream-cardinality | [research/source-finish-stream-cardinality.md](../research/source-finish-stream-cardinality.md) |  |
| research/source-new-vertex-quantization-boundary | [research/source-new-vertex-quantization-boundary.md](../research/source-new-vertex-quantization-boundary.md) |  |
| research/spozu-vatutino-inventory | [research/spozu-vatutino-inventory.md](../research/spozu-vatutino-inventory.md) |  |
| research/spozu-vatutino/main-inventory | [research/spozu-vatutino/main-inventory.md](../research/spozu-vatutino/main-inventory.md) |  |
| research/spozu-vatutino/paving-inventory | [research/spozu-vatutino/paving-inventory.md](../research/spozu-vatutino/paving-inventory.md) |  |
| research/substance-finishes | [research/substance-finishes.md](../research/substance-finishes.md) |  |
| research/team-plugins-audit | [research/team-plugins-audit.md](../research/team-plugins-audit.md) |  |
| research/team-scripts-audit | [research/team-scripts-audit.md](../research/team-scripts-audit.md) |  |
| research/team-scripts-inventory-json | [research/team-scripts-inventory.json](../research/team-scripts-inventory.json) |  |
| research/telegram-3dsmax-chat-2026-11 | [research/telegram-3dsmax-chat-2026-11.md](../research/telegram-3dsmax-chat-2026-11.md) |  |
| research/toolchain-smoke-2026-10-15 | [research/toolchain-smoke-2026-10-15.md](../research/toolchain-smoke-2026-10-15.md) |  |
| research/tow02-hand-finish-face-diff | [research/tow02-hand-finish-face-diff.md](../research/tow02-hand-finish-face-diff.md) |  |
| research/trainer-artifact-first-r95/analyze-py | [research/trainer-artifact-first-r95/analyze.py](../research/trainer-artifact-first-r95/analyze.py) |  |
| research/trainer-artifact-first-r95/make-bank-py | [research/trainer-artifact-first-r95/make_bank.py](../research/trainer-artifact-first-r95/make_bank.py) |  |
| research/trainer-artifact-first-r95/receipt-json | [research/trainer-artifact-first-r95/receipt.json](../research/trainer-artifact-first-r95/receipt.json) |  |
| research/trainer-artifact-first-r95/series-py | [research/trainer-artifact-first-r95/series.py](../research/trainer-artifact-first-r95/series.py) |  |
| research/trainer-g22-adapter-r97/analyze-py | [research/trainer-g22-adapter-r97/analyze.py](../research/trainer-g22-adapter-r97/analyze.py) |  |
| research/trainer-g22-adapter-r97/informational-json | [research/trainer-g22-adapter-r97/informational.json](../research/trainer-g22-adapter-r97/informational.json) |  |
| research/trainer-g22-adapter-r97/make-candidate-py | [research/trainer-g22-adapter-r97/make_candidate.py](../research/trainer-g22-adapter-r97/make_candidate.py) |  |
| research/trainer-g22-adapter-r97/receipt-json | [research/trainer-g22-adapter-r97/receipt.json](../research/trainer-g22-adapter-r97/receipt.json) |  |
| research/trainer-g22-adapter-r97/series-log | [research/trainer-g22-adapter-r97/series.log](../research/trainer-g22-adapter-r97/series.log) |  |
| research/trainer-g22-adapter-r97/series-py | [research/trainer-g22-adapter-r97/series.py](../research/trainer-g22-adapter-r97/series.py) |  |
| research/trainer-tower-id-r87/calib-json | [research/trainer-tower-id-r87/calib.json](../research/trainer-tower-id-r87/calib.json) |  |
| research/trainer-tower-id-r87/make-bank-py | [research/trainer-tower-id-r87/make_bank.py](../research/trainer-tower-id-r87/make_bank.py) |  |
| research/trainer-tower-id-r87/result-json | [research/trainer-tower-id-r87/result.json](../research/trainer-tower-id-r87/result.json) |  |
| research/trainer-tower-id-r87/score-py | [research/trainer-tower-id-r87/score.py](../research/trainer-tower-id-r87/score.py) |  |
| research/trainer-tower-id-r87/series-sh | [research/trainer-tower-id-r87/series.sh](../research/trainer-tower-id-r87/series.sh) |  |
| research/ucx-cases-codex-2042 | [research/ucx-cases-codex-2042.md](../research/ucx-cases-codex-2042.md) |  |
| research/ucx-etalon-analysis | [research/ucx-etalon-analysis.md](../research/ucx-etalon-analysis.md) |  |
| research/ucx-etalon-audit-2026-10-15-json | [research/ucx-etalon-audit-2026-10-15.json](../research/ucx-etalon-audit-2026-10-15.json) |  |
| research/vatutino-ground-80deg-step-source | [research/vatutino-ground-80deg-step-source.md](../research/vatutino-ground-80deg-step-source.md) |  |
| research/vatutino-ground-v015-outer-skirt-gap-20-edges | [research/vatutino-ground-v015-outer-skirt-gap-20-edges.md](../research/vatutino-ground-v015-outer-skirt-gap-20-edges.md) |  |
| research/vpm-course-grid-1314 | [research/vpm-course-grid-1314.md](../research/vpm-course-grid-1314.md) |  |
| research/xview-parity-ground-v014 | [research/xview-parity-ground-v014.md](../research/xview-parity-ground-v014.md) |  |
| retros/2026-10-22-tec26-colouring-claude | [retros/2026-10-22-tec26-colouring-claude.md](../retros/2026-10-22-tec26-colouring-claude.md) |  |
| retros/2026-11-05-elv-tc-vpm-claude | [retros/2026-11-05-elv-tc-vpm-claude.md](../retros/2026-11-05-elv-tc-vpm-claude.md) |  |
| retros/2026-11-05-sessions-retro-04-05 | [retros/2026-11-05-sessions-retro-04-05.md](../retros/2026-11-05-sessions-retro-04-05.md) |  |
| retros/2026-11-14-4bk-k3-modeling | [retros/2026-11-14-4bk-k3-modeling.md](../retros/2026-11-14-4bk-k3-modeling.md) |  |
| retros/2026-11-15-4bk-k3-gf-stylobate | [retros/2026-11-15-4bk-k3-gf-stylobate.md](../retros/2026-11-15-4bk-k3-gf-stylobate.md) |  |
| scenarios/ground-npm | [scenarios/ground-npm.md](../scenarios/ground-npm.md) |  |
| scenarios/ground-vpm | [scenarios/ground-vpm.md](../scenarios/ground-vpm.md) |  |
| scenarios/library-publish | [scenarios/library-publish.md](../scenarios/library-publish.md) |  |
| scenarios/npm-to-vpm | [scenarios/npm-to-vpm.md](../scenarios/npm-to-vpm.md) |  |
| scenarios/oks-vpm | [scenarios/oks-vpm.md](../scenarios/oks-vpm.md) |  |
| scenarios/scenarios-json | [scenarios/scenarios.json](../scenarios/scenarios.json) |  |
| scenarios/vpm-to-npm | [scenarios/vpm-to-npm.md](../scenarios/vpm-to-npm.md) |  |
| sources/psu275 | [sources/psu275.md](../sources/psu275.md) |  |
| sources/readme | [sources/README.md](../sources/README.md) |  |
| sources/vyatskaya-tow02 | [sources/vyatskaya-tow02.md](../sources/vyatskaya-tow02.md) |  |
| tools/max-scripts | [tools/max-scripts.md](../tools/max-scripts.md) |  |
| tools/openings | [tools/openings.md](../tools/openings.md) |  |
| trainer/entry-cost-1938 | [trainer/entry-cost-1938.md](../trainer/entry-cost-1938.md) |  |
| trainer/entry-cost-1938-json | [trainer/entry-cost-1938.json](../trainer/entry-cost-1938.json) |  |
| trainer/etalons | [trainer/ETALONS.md](../trainer/ETALONS.md) |  |
| trainer/etalons-json | [trainer/etalons.json](../trainer/etalons.json) |  |
| trainer/ledger-json | [trainer/ledger.json](../trainer/ledger.json) |  |
