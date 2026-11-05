# Archive index

Tag `archive/2026-11` (annotated, on `origin`) points to `main` at `cb1ad1d4`, the last commit that still had every
path below. Repo hygiene phase 2 removed these paths from the tree so agents stop finding them in search; nothing
was rewritten in history. A citation of the form `archive/2026-11:<path>` names a file in that tag.

Read or restore a file:

```
git show archive/2026-11:<path>                      # print one file
git ls-tree -r --name-only archive/2026-11 -- <dir>   # list a removed folder
git restore --source archive/2026-11 -- <path>       # bring a file or folder back into the tree
```

Run `git fetch origin tag archive/2026-11` first if the tag is missing locally.

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
