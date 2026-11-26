# Archive index

Tag `archive/2026-11` (annotated, on `origin`) points to `main` at `cb1ad1d4`, the last commit that still had every
path in the tag-based inventory, before the search-only section. Repo hygiene phase 2 removed those paths
from the tree so agents stop finding them in search; nothing
was rewritten in history. A citation of the form `archive/2026-11:<path>` names a file in that tag.

Read or restore a file:

```
git show archive/2026-11:<path>                      # print one file
git ls-tree -r --name-only archive/2026-11 -- <dir>   # list a removed folder
git restore --source archive/2026-11 -- <path>       # bring a file or folder back into the tree
```

Run `git fetch origin tag archive/2026-11` first if the tag is missing locally.

## Hygiene cleanup rule (2026-11-25)

- Cleanup hides paths from agent search through the search-noise generator (`tools/architecture/search_noise.py` -> `.ignore`) and lists them here; git keeps them. Physical deletion only after a trainer before/after measurement; hygiene batch 2 is the only deletion now. Cleanup batches go one PR at a time [D395].
- The 164 paths the hygiene auditors disagree on (`G:/Мой диск/AGR-evidence/hygiene-20261125/PLAN-ru-conflicts.csv`) stay keep until the owner of the trail decides [D396].
- The old OKS body route (hygiene batch 4) is archived only after the lattice has built an NPM body on at least one object [D392].

## Jobs (`jobs/<folder>/`)

| Folder | Status and pointer |
|---|---|
| `A-MAIN-ATLAS` | user accepted, tech QA open; reusable part in `technical_library/glb_atlas` |
| `B-MAIN-ATLAS` | sibling of A-MAIN-ATLAS; reusable part in `technical_library/glb_atlas` |
| `FACADE-SIGNS` | one-off v001 (2026-09-27) |
| `FACADES-ATLAS` | v003 tile accepted; `docs/cases.md` (Facades atlas) |
| `GLB-NPM` | v023 not accepted, stalled; its 56 job scripts in `adapters/sketchup/` were removed in phase 4 (see "Job scripts removed from shared folders") |
| `GROUND-PROJECTION` | historical v008 report; `docs/cases.md` (Ground contours); superseded by skill `model-ground` |
| `MASHI-LP` | scene audit accepted; `docs/cases.md` (MASHI-LP scene audit) |
| `MESH-OPT-AUDIT` | audit done 2026-09-28; reusable part in `technical_library/mesh_audit` |
| `REVIT-OPENINGS` | pilot snapshot, not accepted; `docs/cases.md` (SOSH1150 openings) |
| `UV-CONTINUOUS` | v006 accepted; `docs/cases.md`, `technical_library/UV_V006.md` |
| `WINDOW-ATLAS` | done v002; reusable part in `technical_library/window_atlas` |
| `WINDOW-FRAMES` | layout stage accepted; `docs/cases.md` (Window frames) |
| `flora-textures` | texture approval; `docs/cases.md` (Flora textures #190) |

## Experiments (`experiments/<folder>/`)

The report with the verdict stays in the tree: `docs/experiments/<report>.md`.

| Folder | Report | Verdict |
|---|---|---|
| `hyp-84` | `docs/experiments/hyp-84.md` | CONFIRMED |
| `hyp-89` | `docs/experiments/hyp-89.md` | CONFIRMED |
| `hyp-91` | `docs/experiments/hyp-91.md` | confirmed on frozen synthetic inputs |
| `hyp-93` | `docs/experiments/hyp-93.md` | CONFIRMED |
| `hyp-100` | `docs/experiments/hyp-100.md` | CONFIRMED |
| `hyp-101` | `docs/experiments/hyp-101.md` | CONFIRMED |
| `hyp-107` | `docs/experiments/hyp-107.md` | CONFIRMED |
| `hyp-281` | `docs/experiments/hyp-281.md` | REJECTED |
| `hyp-283` | `docs/experiments/hyp-283.md` | SUPPORTED on frozen synthetic inputs |
| `hyp-358` | `docs/experiments/hyp-358.md` | INCONCLUSIVE |
| `hyp-359` | `docs/experiments/hyp-359.md` | REJECTED |
| `hyp-386` | `docs/experiments/hyp-386.md` | CONFIRMED |
| `hyp-415` | `docs/experiments/hyp-415.md` | CONFIRMED |
| `hyp-603` | `docs/experiments/hyp-603.md` | CONFIRMED |
| `hyp-626` | `docs/experiments/hyp-626.md` | CONFIRMED |
| `hyp-638` | `docs/experiments/hyp-638.md` | REJECTED |
| `hyp-748` | `docs/experiments/hyp-748.md` | CONFIRMED |
| `hyp-766` | `docs/experiments/hyp-766.md` | CONFIRMED |
| `bim-3dsmax-agr` | `docs/experiments/bim-3dsmax-agr.md` | ADOPT |
| `bim-blender-agr` | `docs/experiments/bim-blender-agr.md` | method verdicts in report |
| `bim-revit-agr` | `docs/experiments/bim-revit-agr.md` | MAYBE |
| `blender-bpy-automation` | `docs/experiments/blender-bpy-automation.md` | method verdicts in report |
| `blender-exec-session` | `docs/experiments/blender-exec-session.md` | method verdicts in report |
| `max-headless-agr-roundtrip` | `docs/experiments/max-headless-agr-roundtrip.md` | adopt |
| `mcp-dcc-bridges` | `docs/experiments/mcp-dcc-bridges.md` | method verdicts in report |
| `scripts-logic` | `docs/experiments/scripts-logic.md` | method verdicts in report |

## Single files

| Path | Note |
|---|---|
| `docs/research/team-plugins-inventory.json` | 7.25 MB row-per-file inventory behind `docs/research/team-plugins-audit.md` |
| `docs/HARNESS_PLAN.md` | harness plan, frozen 2026-11-03; cited as `archive/2026-11:docs/HARNESS_PLAN.md` §N; current rules in `docs/pipeline.md`, `docs/decisions.md`, `docs/agents/WORKFLOW.md`, `docs/domain/` |
| `docs/prd/agent-ready-harness.md` | agent-ready harness spec (#118); decisions D088-D092 in `docs/decisions.md`; story 38 closed |

## Job scripts removed from shared folders

Repo hygiene phase 4 (2026-11-05) removed job- and object-specific scripts from shared folders
(`docs/agents/NAMING.md`: no version and no object code in shared tools). Each was unchanged since `cb1ad1d4`,
so the tag holds the last version. OBR22-K02 scripts were moved, not removed: `jobs/OBR22-K02/scripts/`,
`jobs/ORCH-OBR22-NPM/scripts/run_profile_pilot.py` (engine gap EG7 in `docs/backlog.md`).

| Paths | Owner | Note |
|---|---|---|
| `tools/{build_facades_textures_v004,check_facades_atlas,check_facades_max_roundtrip,check_facades_v005_package,export_facades_max,inspect_facades_atlas,package_facades_v004,probe_facades_uv,remap_facades_atlas,render_facades_atlas,stabilize_facades_phase,update_facades_600x1200}.py`, `tests/test_facade_corner_match.py` | `FACADES-ATLAS` | `tools/facades_texture_pattern.py` stays (shared); `experiments/hyp83` hashes `check_facades_max_roundtrip.py` and needs the tag to rerun |
| `tools/{probe_geoagr_ucx,probe_geoagr_uvdilate}.py` | GeoAGR review | `docs/agr/inventory/GEOAGR_13_63_REVIEW.md` |
| `tools/max_flora_{archive,inventory,transform_repair,tri_repair,verify}.py` | `experiments/flora-library-audit` | superseded by `adapters/max/agr_tools/place_core.py` (`place.flora_repair`) |
| `tools/audit_max_tool_sources.py`, `tools/bootstrap_evidence.py` | one-off workstation inventory; `SYNTH-001` | — |
| `adapters/sketchup/*` except `README.md`, `inspection.rb`, `prepare_package.py`, `prepare_readonly.py`, `probe_readonly.py`, `requirements-installed.txt`, `.gitignore` (56 files) | `GLB-NPM` | `check_model_clearance.py` lives on as `src/twinqa/clearance.py` |

Orphan docs (no test, doc or code named them on 2026-11-05):

- `docs/research/windows-frame-depth-tessellation-sensitivity.md`
- `docs/research/source-edge-veto-endpoint-evidence.md`
- `docs/research/geojson-json-nesting-report-boundary.md`
- `docs/research/methods-ucx-distance-stride-population.md`
- `docs/research/coverage-baseline.md`
- `docs/research/methods-body-shell-coordinate-stability.md`
- `docs/experiments/sliver-rule-etalon-check.md`
- `docs/research/capability-ticket-handoff-contract-gap.md`
- `docs/research/texel-density-metric-verdict-parity.md`
- `docs/research/rounded-coordinate-topology-boundary.md`
- `docs/research/ucx-scene-degeneracy-routing-parity.md`
- `docs/research/ucx-edge-edge-projection-arithmetic.md`
- `docs/research/tow02-engine-extraction.md`
- `docs/research/ecc-vs-our-rules.md`
- `docs/research/geojson-small-coordinate-precision-boundary.md`
- `docs/research/source-face-onedge-cover-exposure.md`
- `docs/research/ucx-float32-coordinate-budget.md`
- `docs/research/source-qa-raw-topology-boundary.md`
- `docs/research/embodied-cad-error-catalog-vs-checkers.md`
- `docs/research/zip-deflate-end-state-boundary.md`
- `docs/research/parts-schema-unvisited-vocabulary.md`
- `docs/research/uv-eligibility-semantic-boundaries.md`
- `docs/research/face-diff-uv-numeric-domain.md`
- `docs/research/retro-pilot-cards.md`
- `docs/research/adopt-pr-evidence-receipts.md`
- `docs/research/ucx-sintez-collision-crosscheck-contract.md`
- `docs/research/suite-capacity-provenance-drift.md`
- `docs/research/geojson-integer-float-report-boundary.md`
- `docs/research/geojson-glass-signature-key-order.md`
- `docs/experiments/autoresearch-evals-mutation.md`
- `docs/research/geojson-jpeg-decode-boundary.md`
- `docs/research/kpi-provenance-boundaries.md`
- `docs/research/development-c001-member-error-boundary.md`
- `docs/research/coordination-cards-hang-to-runtime-cap.md`
- `docs/research/test-suite-durations-profile.md`
- `docs/research/engiworld-benchmark-fit.md`
- `docs/research/kernel-mesh-index-coercion-boundary.md`
- `docs/research/cursor-wrapper-settings-test-exposure.md`
- `docs/research/red-main-after-229.md`
- `docs/research/zip-name-decoding-error-boundary.md`
- `docs/research/3ddd-ai-thread-pilot-solutions.md`
- `docs/research/agr-tools-atlas-npm-fixed-point.md`
- `docs/research/regression-evals-receipt-skips-census.md`
- `docs/research/worktree-claude-settings-missing-suite-failures.md`
- `docs/research/orientation-adaptive-bins.md`
- `docs/research/mangled-pytest-basetemp-in-worktrees-source.md`
- `docs/research/engine-seam-join-530.md`
- `docs/research/png-fixed-field-acceptance.md`
- `docs/research/model-ground-dry-walk-2026-10-16.md`
- `docs/experiments/issue-767-fbx-readers.md`
- `docs/research/bpy-linux-headless-probe.md`

## Hidden from search (still in the tree)

Batch B1 (#1885). These exact tracked files are hidden by the generated search block, not moved or
deleted. The tag-based recovery instructions above do not apply. Use `git ls-files -- <path>` to
confirm a file is still tracked, or `rg --files --no-ignore-dot` to bypass the root `.ignore` for a lookup.

To restore default search visibility, remove the matching row below and run
`uv run python tools/architecture/search_noise.py --write-ignore`. Do not edit `.ignore` directly.
This list does not repeat files hidden by the earlier historical data, docs or delivered-job script rules.

### `docs/experiments/`

- `docs/experiments/bim-3dsmax-agr.md` — Historical experiment report; not a current procedure.
- `docs/experiments/bim-blender-agr.md` — Historical experiment report; not a current procedure.
- `docs/experiments/bim-revit-agr.md` — Historical experiment report; not a current procedure.
- `docs/experiments/hyp-100.md` — Historical experiment report; not a current procedure.
- `docs/experiments/hyp-101.md` — Historical experiment report; not a current procedure.
- `docs/experiments/hyp-281.md` — Historical experiment report; not a current procedure.
- `docs/experiments/hyp-283.md` — Historical experiment report; not a current procedure.
- `docs/experiments/hyp-358.md` — Historical experiment report; not a current procedure.
- `docs/experiments/hyp-359.md` — Historical experiment report; not a current procedure.
- `docs/experiments/hyp-386.md` — Historical experiment report; not a current procedure.
- `docs/experiments/hyp-415.md` — Historical experiment report; not a current procedure.
- `docs/experiments/hyp-603.md` — Historical experiment report; not a current procedure.
- `docs/experiments/hyp-626.md` — Historical experiment report; not a current procedure.
- `docs/experiments/hyp-766.md` — Historical experiment report; not a current procedure.
- `docs/experiments/hyp-84.md` — Historical experiment report; not a current procedure.
- `docs/experiments/hyp-89.md` — Historical experiment report; not a current procedure.
- `docs/experiments/hyp-93.md` — Historical experiment report; not a current procedure.
- `docs/experiments/issue-105-author-receipts.md` — Historical experiment report; not a current procedure.

### `docs/experiments/issue-105-evidence/`

- `docs/experiments/issue-105-evidence/adoption-available-report.json` — Frozen author-receipt experiment output.
- `docs/experiments/issue-105-evidence/adoption-regression-report.json` — Frozen author-receipt experiment output.
- `docs/experiments/issue-105-evidence/generated.json` — Frozen author-receipt experiment output.
- `docs/experiments/issue-105-evidence/regression-report.json` — Frozen author-receipt experiment output.

### `docs/experiments/`

- `docs/experiments/revit-ifc-offline-intake.md` — Historical experiment report; not a current procedure.
- `docs/experiments/scripts-logic.md` — Historical experiment report; not a current procedure.
- `docs/experiments/tow02-hand-finish-face-diff.md` — Historical experiment report; not a current procedure.

### `docs/research/`

- `docs/research/ifc-intake-src-contract.md` — Unreferenced research note; retained for provenance.
- `docs/research/job-artifact-name-contract.md` — Unreferenced research note; retained for provenance.

### `experiments/fbxmaps-1760/`

- `experiments/fbxmaps-1760/native_smoke.py` — One-off native smoke for the FBX-map diagnostic.

### `jobs/4bk-k3-course-grid-1326/`

- `jobs/4bk-k3-course-grid-1326/numerical-repair-checkpoint-v166.json` — Superseded repair checkpoint; not a current source.
- `jobs/4bk-k3-course-grid-1326/repair-checkpoint-v026.json` — Superseded repair checkpoint; not a current source.

### `jobs/butovskaya-sosh1000/autoresearch/`

- `jobs/butovskaya-sosh1000/autoresearch/results.json` — Frozen one-off benchmark results, not a production input.

### `jobs/elv-tc-vpm/scripts/`

- `jobs/elv-tc-vpm/scripts/additions_summary_v007.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/blend_info.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/build_full_v006.py` — Pre-AGR Tools ELV geometry builder snapshot.
- `jobs/elv-tc-vpm/scripts/build_v008.py` — Pre-AGR Tools ELV geometry builder snapshot.
- `jobs/elv-tc-vpm/scripts/check_pilot.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/clarify_blend_probe_v001.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/clarify_booklet_pages_v001.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/clarify_compose_v001.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/clarify_crop_v001.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/clarify_nakl_verts_v001.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/clarify_openings_v001.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/compare_fbx_geometry_v004.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/contact_renders_v002.py` — Superseded review contact sheet or render.
- `jobs/elv-tc-vpm/scripts/contact_renders_v003.py` — Superseded review contact sheet or render.
- `jobs/elv-tc-vpm/scripts/contact_renders_v004.py` — Superseded review contact sheet or render.
- `jobs/elv-tc-vpm/scripts/customer_blend_ids_v001.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/customer_blend_inventory_v001.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/customer_blend_summary_v001.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/customer_compare_v001.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/customer_overlay_compose_v001.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/customer_overlay_render_v001.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/customer_register_v001.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/customer_textures_probe_v001.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/door_islands.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/draw_parts.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/export_check_fbx.py` — Superseded ELV export draft.
- `jobs/elv-tc-vpm/scripts/export_tex_check_fbx.py` — Superseded ELV export draft.
- `jobs/elv-tc-vpm/scripts/id_legend.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/light_diag.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/long_quads.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/make_parts_full_v001.py` — Superseded ELV PartsList generation.
- `jobs/elv-tc-vpm/scripts/make_parts_full_v002.py` — Superseded ELV PartsList generation.
- `jobs/elv-tc-vpm/scripts/make_parts_full_v003.py` — Superseded ELV PartsList generation.
- `jobs/elv-tc-vpm/scripts/make_parts_v002.py` — Superseded ELV PartsList generation.
- `jobs/elv-tc-vpm/scripts/make_tex_spec_v003.py` — Superseded ELV texture or UV draft.
- `jobs/elv-tc-vpm/scripts/make_textures_full_v005.py` — Superseded ELV texture or UV draft.
- `jobs/elv-tc-vpm/scripts/make_textures_full_v006.py` — Superseded ELV texture or UV draft.
- `jobs/elv-tc-vpm/scripts/measure_pilot.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/open_view_max2026_v001.ms` — Superseded Max scene-opening or xView helper.
- `jobs/elv-tc-vpm/scripts/open_view_max2026_v002.ms` — Superseded Max scene-opening or xView helper.
- `jobs/elv-tc-vpm/scripts/open_view_max2026_v003.ms` — Superseded Max scene-opening or xView helper.
- `jobs/elv-tc-vpm/scripts/part_probe_v001.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/pdf_revolving_door.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/pdf_revolving_door_b.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/pilot_boundary.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/plot_sections.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/png_colours_v007.py` — Superseded review contact sheet or render.
- `jobs/elv-tc-vpm/scripts/probe_glass_clusters_v007.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/probe_glass_v007.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/probe_strips_v007.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/pur_contact_sheet_v001.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/pur_crc_v001.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/pur_extract_v001.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/pur_find_v001.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/pur_idat_v001.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/pur_insert_find_v001.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/pur_layout_v001.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/pur_page_test_v001.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/pur_pages_v001.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/pur_pngwalk_v001.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/pur_probe_v001.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/pur_zprobe_v001.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/readback_fbx.py` — Draft FBX readback; use the shared readback for current work.
- `jobs/elv-tc-vpm/scripts/ref_clean.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/ref_dump.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/ref_inventory_full.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/ref_render.py` — Superseded review contact sheet or render.
- `jobs/elv-tc-vpm/scripts/ref_sections.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/render_delivery_v002.py` — Superseded review contact sheet or render.
- `jobs/elv-tc-vpm/scripts/render_delivery_v003.py` — Superseded review contact sheet or render.
- `jobs/elv-tc-vpm/scripts/render_full.py` — Superseded review contact sheet or render.
- `jobs/elv-tc-vpm/scripts/render_pilot.py` — Superseded review contact sheet or render.
- `jobs/elv-tc-vpm/scripts/render_tex.py` — Superseded review contact sheet or render.
- `jobs/elv-tc-vpm/scripts/render_tex_full.py` — Superseded review contact sheet or render.
- `jobs/elv-tc-vpm/scripts/si_pairs_v001.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/side_by_side_night.py` — Superseded review contact sheet or render.
- `jobs/elv-tc-vpm/scripts/strip_probe_v008.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/topology_breakdown_v001.py` — One-off ELV diagnostic or draft helper; retained for reproduction.
- `jobs/elv-tc-vpm/scripts/work_readback_v004.py` — Superseded ELV export draft.
- `jobs/elv-tc-vpm/scripts/xview_explain.py` — Superseded review contact sheet or render.
- `jobs/elv-tc-vpm/scripts/xview_max_gate.ms` — Superseded Max scene-opening or xView helper.
- `jobs/elv-tc-vpm/scripts/xview_max_gate_v003.ms` — Superseded Max scene-opening or xView helper.

### `jobs/ogorodnyj-proezd-zu4-3/`

- `jobs/ogorodnyj-proezd-zu4-3/LESSONS.md` — Job-local retrospective; not a general projection rule.

### `library/assets/intake/BUHV12/`

- `library/assets/intake/BUHV12/identify.json` — Closed intake snapshot; not the current published library.
- `library/assets/intake/BUHV12/identify.md` — Closed intake snapshot; not the current published library.
- `library/assets/intake/BUHV12/review.md` — Closed intake snapshot; not the current published library.
- `library/assets/intake/BUHV12/scene-map.json` — Closed intake snapshot; not the current published library.

### `library/assets/intake/PPT4/`

- `library/assets/intake/PPT4/identify.json` — Closed intake snapshot; not the current published library.
- `library/assets/intake/PPT4/identify.md` — Closed intake snapshot; not the current published library.
- `library/assets/intake/PPT4/review.md` — Closed intake snapshot; not the current published library.
- `library/assets/intake/PPT4/scene-map.json` — Closed intake snapshot; not the current published library.

### `library/assets/intake/VLAD-MAF-B2/`

- `library/assets/intake/VLAD-MAF-B2/identify.json` — Closed intake snapshot; not the current published library.

### `technical_library/evidence/`

- `technical_library/evidence/ALL_GROUPS_QA_20261001.json` — Frozen migration audit evidence.
- `technical_library/evidence/PR_AUDIT_20261001.json` — Frozen migration audit evidence.

### `technical_library/uv/`

- `technical_library/uv/corner_match.py` — One-off UV corner matching experiment.

### `test-polygon/build/`

- `test-polygon/build/topview.py` — One-off acceptance render helper; not a runtime dependency.

### `tests/blender/`

- `tests/blender/run_uv_compaction_1380.py` — Standalone historical UV compaction probe.

### `tests/data/`

- `tests/data/ground-v015-strict-corner.json` — Frozen strict-remesh witness from the retired Ground test.
- `tests/data/ground-v015-strict-taper.json` — Frozen strict-remesh witness from the retired Ground test.

### `tests/fixtures/`

- `tests/fixtures/pi_guard_smoke_task.txt` — Historical smoke prompt; not the maintained guard test driver.

### Batch B4 (#1932): pre-lattice BODY
The stage-1 BODY route is superseded by the lattice [D373], [D392]. Sokolniki NPM body v006 was accepted
[D409] (PR #1833), fulfilling the archive condition. Exact B4 paths below remain at their original
locations; search visibility is the only change to them. Retained consumers are listed in PR evidence.

#### Body experiments

- `experiments/body-gn-full-snap-edge-locator-rerun/drive.py` — Pre-lattice experiment; superseded for production BODY by [D373].
- `experiments/body-gn-full-snap-edge-locator-rerun/probe6.py` — Pre-lattice experiment; superseded for production BODY by [D373].
- `experiments/body-gn-full-snap-edge-locator-rerun/probe7.py` — Pre-lattice experiment; superseded for production BODY by [D373].
- `experiments/body-gn-full-snap-edge-locator-rerun/run8.py` — Pre-lattice experiment; superseded for production BODY by [D373].

#### Job evidence

- `jobs/KPP1/benchmark-1318/summary.json` — Frozen job evidence; not an active stage-1 BODY route [D373].
- `jobs/KPP1/benchmark-1318/telemetry.json` — Frozen job evidence; not an active stage-1 BODY route [D373].
- `jobs/KPP1/rerun-1230/xview-npm-r1-v002.json` — Frozen job evidence; not an active stage-1 BODY route [D373].
- `jobs/OBR22-K02/body-shell-adapter-verification.json` — Frozen job evidence; not an active stage-1 BODY route [D373].
- `jobs/OBR22-K02/body-shell-from-exterior-adapter.json` — Frozen job evidence; not an active stage-1 BODY route [D373].
- `jobs/OBR22-K02/exterior-adapter-verification.json` — Frozen job evidence; not an active stage-1 BODY route [D373].
- `jobs/PSU275/body-shell-vpm-adapter.json` — Frozen job evidence; not an active stage-1 BODY route [D373].
- `jobs/PSU275/oks/tanks/vpm_textures.json` — Frozen job evidence; not an active stage-1 BODY route [D373].
- `jobs/PSU275/oks/transformer/vpm_textures.json` — Frozen job evidence; not an active stage-1 BODY route [D373].

#### Regression tests

- `tests/jobs/test_kpp1_quad_master_v003_1563.py` — Historical comparators; still tracked and runnable by pytest.
- `tests/jobs/test_kpp1_quad_union_zones_1372.py` — Historical comparators; still tracked and runnable by pytest.
- `tests/test_body_contours.py` — Historical comparators; still tracked and runnable by pytest.
- `tests/test_body_optimization.py` — Historical comparators; still tracked and runnable by pytest.
- `tests/test_body_seam_compaction_1381.py` — Historical comparators; still tracked and runnable by pytest.
- `tests/test_body_training_1619_r3.py` — Historical comparators; still tracked and runnable by pytest.
- `tests/test_body_training_1619_r4.py` — Historical comparators; still tracked and runnable by pytest.
- `tests/test_body_training_1619_r6.py` — Historical comparators; still tracked and runnable by pytest.
- `tests/test_body_training_1619_r7.py` — Historical comparators; still tracked and runnable by pytest.
- `tests/test_body_training_1619_stage2.py` — Historical comparators; still tracked and runnable by pytest.

### Batch 5a (#1933): research and experiments

Exact paths below stay in Git at their original locations. Only default search visibility changes;
active consumers and their inputs remain visible. Explicit pytest invocations still work.

- `experiments/bim-autocad-agr/README.md` — Historical experiment instructions, not the active drawing intake route.
- `experiments/bim-autocad-agr/test_experiment.py` — Historical experiment tests, still runnable by exact path.
- `experiments/complexity-group-index/red.log` — Frozen pre-fix test output.
- `experiments/flora-texture-diagnosis/bark-calibration-v001.json` — Frozen bark calibration result.
- `experiments/flora-texture-diagnosis/bark_calibration.py` — Historical calibration script, not a library entrypoint.
- `experiments/flora-texture-diagnosis/calibration-original-tilia.json` — Frozen calibration of the original Tilia asset.
- `experiments/flora-texture-diagnosis/source-calibration-baseline-v002.json` — Frozen source calibration baseline.
- `experiments/flora-texture-diagnosis/source-integrity-v002.json` — Earlier source-integrity receipt; the cited v003 receipt stays visible.
- `experiments/flora-texture-diagnosis/test_calibration.py` — Historical experiment tests, still runnable by exact path.
- `tools/research/pdf_album/dimension-geometry-evidence.json` — Frozen PDF dimension geometry research receipt.

### Batch 5b (#1934): closed-job receipts

Under [D416], the exact historical TEC26 AC08 receipts below leave default search but stay in Git
at the same paths. The live-path guard still protects the rest of AC08, including v010.
The referenced KPP1 and 4bk course-grid inputs, current TEC26 evidence, and the exact inputs of retained tests stay in place.

- `jobs/TEC26-OKS/AC08/kernel-ops-v001/evidence/DRIVE-SHA256SUMS.txt` — Historical kernel trial checksum receipt.
- `jobs/TEC26-OKS/AC08/pilot-v006/DRIVE-SHA256SUMS.txt` — Superseded pilot receipt; current v010 evidence is not archived here.
- `jobs/TEC26-OKS/AC08/pilot-v006/Nku_1_VPM_master.blend.build.json` — Superseded pilot receipt; current v010 evidence is not archived here.
- `jobs/TEC26-OKS/AC08/pilot-v006/export_meta.json` — Superseded pilot receipt; current v010 evidence is not archived here.
- `jobs/TEC26-OKS/AC08/pilot-v006/export_npm_meta.json` — Superseded pilot receipt; current v010 evidence is not archived here.
- `jobs/TEC26-OKS/AC08/pilot-v006/npm_atlas.json` — Superseded pilot receipt; current v010 evidence is not archived here.
- `jobs/TEC26-OKS/AC08/pilot-v006/qa_master.json` — Superseded pilot receipt; current v010 evidence is not archived here.
- `jobs/TEC26-OKS/AC08/pilot-v006/qa_packages-review1.json` — Superseded pilot receipt; current v010 evidence is not archived here.
- `jobs/TEC26-OKS/AC08/pilot-v006/qa_packages.json` — Superseded pilot receipt; current v010 evidence is not archived here.
- `jobs/TEC26-OKS/AC08/pilot-v006/renders.json` — Superseded pilot receipt; current v010 evidence is not archived here.
- `jobs/TEC26-OKS/AC08/pilot-v006/sintez-summary.json` — Superseded pilot receipt; current v010 evidence is not archived here.
- `jobs/TEC26-OKS/AC08/pilot-v007/DRIVE-SHA256SUMS.txt` — Superseded pilot receipt; current v010 evidence is not archived here.
- `jobs/TEC26-OKS/AC08/pilot-v007/Nku_1_VPM_master.blend.build.json` — Superseded pilot receipt; current v010 evidence is not archived here.
- `jobs/TEC26-OKS/AC08/pilot-v007/export_meta.json` — Superseded pilot receipt; current v010 evidence is not archived here.
- `jobs/TEC26-OKS/AC08/pilot-v007/export_npm_meta.json` — Superseded pilot receipt; current v010 evidence is not archived here.
- `jobs/TEC26-OKS/AC08/pilot-v007/npm_atlas.json` — Superseded pilot receipt; current v010 evidence is not archived here.
- `jobs/TEC26-OKS/AC08/pilot-v007/qa_master.json` — Superseded pilot receipt; current v010 evidence is not archived here.
- `jobs/TEC26-OKS/AC08/pilot-v007/qa_packages.json` — Superseded pilot receipt; current v010 evidence is not archived here.
- `jobs/TEC26-OKS/AC08/pilot-v007/renders.json` — Superseded pilot receipt; current v010 evidence is not archived here.
- `jobs/TEC26-OKS/AC08/pilot-v007/sintez-summary.json` — Superseded pilot receipt; current v010 evidence is not archived here.
- `jobs/TEC26-OKS/AC08/pilot-v009/DRIVE-SHA256SUMS.txt` — Superseded pilot receipt; current v010 evidence is not archived here.
- `jobs/TEC26-OKS/AC08/pilot-v009/Nku_1_VPM_master.blend.build.json` — Superseded pilot receipt; current v010 evidence is not archived here.
- `jobs/TEC26-OKS/AC08/pilot-v009/compare.json` — Superseded pilot receipt; current v010 evidence is not archived here.
- `jobs/TEC26-OKS/AC08/pilot-v009/export_meta.json` — Superseded pilot receipt; current v010 evidence is not archived here.
- `jobs/TEC26-OKS/AC08/pilot-v009/export_npm_meta.json` — Superseded pilot receipt; current v010 evidence is not archived here.
- `jobs/TEC26-OKS/AC08/pilot-v009/npm_atlas.json` — Superseded pilot receipt; current v010 evidence is not archived here.
- `jobs/TEC26-OKS/AC08/pilot-v009/qa_master.json` — Superseded pilot receipt; current v010 evidence is not archived here.
- `jobs/TEC26-OKS/AC08/pilot-v009/qa_packages.json` — Superseded pilot receipt; current v010 evidence is not archived here.
- `jobs/TEC26-OKS/AC08/pilot-v009/renders.json` — Superseded pilot receipt; current v010 evidence is not archived here.
- `jobs/TEC26-OKS/AC08/pilot-v009/sintez-summary.json` — Superseded pilot receipt; current v010 evidence is not archived here.
