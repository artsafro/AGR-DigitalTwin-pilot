# Pipeline stages

Status of each production stage. Rules: `docs/domain/`; tools: `docs/agents/CAPABILITIES.md` (registry) and
`docs/pipeline-tools.md` (catalogue: commands, exit codes, limits);
open work: `docs/backlog.md` (IDs in the last column).
Status: **proven** (accepted on a real object) · **partial** · **tool only** (no real
object yet) · **missing**.
"Accepted" below is the user's review acceptance of a model; no package has passed the regulation check or the
SINTEZ AGR Checker yet (`passed=false` everywhere). State verified against `main` at `ec84f6f9` (2026-11-07).

## Building (OKS)

| # | Stage | Status | Where | Backlog |
|---|---|---|---|---|
| 1 | Register and analyze the source (Revit / FBX / SKP / DWG / PDF album) | tool only | skill `analyze-architectural-source`, Revit/AutoCAD/SketchUp MCP | P1 |
| 2 | Master building layer (elements, floors, openings, materials, sources) | tool only | [`Spec`](../src/dt_ai/spec/model.py#L165), [`Floor`](../src/dt_ai/spec/model.py#L63), [`Opening`](../src/dt_ai/spec/model.py#L32), [`Roof`](../src/dt_ai/spec/model.py#L87), [`Decor`](../src/dt_ai/spec/model.py#L125), [`RoofStructure`](../src/dt_ai/spec/model.py#L94) in `src/dt_ai/spec/model.py`; extractor [`extract_spec`](../src/dt_ai/spec/mesh.py#L1627); engine [`build`](../src/dt_ai/geometry/from_spec.py#L355) (structured spec models, extractor and geometry builder active in test suites; master building workflow/intake across arbitrary sources incomplete; no real-object delivery acceptance) | P2 |
| 3 | BODY: exterior-only quad surface, cuts at corners/openings | proven (Obr22; KPP1 v005 and PSU275 delivery-v003, 2026-10-07; ELV TC deliveries v002–v005, 2026-11-05, PR #969) | `src/dt_ai/geometry/exterior.py`, `connect.py`, `jobs/OBR22-K02/scripts/build_exterior_surface.py`; per-object job scripts in `jobs/KPP1/`, `jobs/PSU275/`, `jobs/elv-tc-vpm/` | — |
| 4 | Shell 0.4 m inward | proven (Obr22, PSU275 delivery-v003) | `src/dt_ai/geometry/shell.py`, `tools/run_body_shell.py` | C23 |
| 5 | Windows, stained glass, doors | partial (accepted per object: PSU275 NPM plane / VPM frame variants; ELV TC library types ELV-01..21 [D140]; shared generator is not arbitrary-source delivery acceptance) | `adapters/max/agr_tools/windowgen_core.py` / `agr window-generate` (#1405); `jobs/OBR22-K02/scripts/build_shell_windows.py` — historical [D327]; `technical_library/window_atlas/`, `library/windows/window_types.json`, REVIT-OPENINGS | P3 |
| 6 | Roof, decor, exterior equipment | tool only | [`extract_spec`](../src/dt_ai/spec/mesh.py#L1627) (roof/parapet/structures), [`extract`](../src/dt_ai/spec/decor.py#L375) (facade decor), [`build`](../src/dt_ai/geometry/from_spec.py#L355) (parapet cap, inset plates, decor solids, roof structures), [`check_decor`](../src/twinqa/geometry/checks.py#L632); roof structures `npm_min` screen planes only; mid/VPM shell and full exterior equipment coverage incomplete; no real-object delivery acceptance | P4 |
| 7 | Materials registry and IDs | partial | `src/dt_ai/materials/registry.py` | — |
| 8 | NPM atlas (embedded PNG, shared regions by finish) | proven (Obr22 v012, GLB) | `technical_library/glb_atlas/`, `texture_tiles/` | C21 |
| 9 | VPM UV/UDIM + Diffuse/ERM/Normal maps | proven (Obr22 v011, SOSH1150 v006) | `technical_library/uv_continuous/`, `src/dt_ai/geometry/uv.py` | C27, C29, C33 |
| 10 | UCX collisions (VPM) | partial (shipped inside accepted models: KPP1 v005 33 hulls, PSU275 23, ELV TC 960, Vatutino Ground v015 727 pieces / 0 overlaps / min gap 3.99 mm, #906; Main builder measured on 4 etalon meshes, #166; R02/R11-R14 coverage not measured, no package passed) | builder [`ucx_build`](../src/dt_ai/geometry/ucx_build.py) + `tools/blender/ucx_build.py`; audit `tools/blender/ucx_audit.py`; V010/V012 scene checks; job-local KPP1/PSU275 `vpm_ucx.py` | P5 |
| 11 | Lights FBX (VPM) | tool only (AGR Tools 1.1.0 `light.check` / `light.export` → `<stem>_Light.fbx`, synthetic scenes only; ELV TC `_Light.fbx` left to the user) | `adapters/max/agr_tools/` (`CHANGELOG.md`), `docs/agr-tools/OVERVIEW.md` | P6 |
| 12 | Coordinates MSK-77, zero mark, pivot | tool only (AGR Tools `export.place_by_passport`, `export.pivot_place` (#983), synthetic KPP1-like runs; ELV TC delivery-v003 records one MSK-77 point by hand, job-local). Placement by the customer's DWG is ours [D220] | `adapters/max/agr_tools/`, `docs/agr-tools/OVERVIEW.md`; validator V013 MSK-77 match `not_run` | P7 |
| 13 | GeoJSON (VPM) | tool only (validator V011; AGR Tools `export.geojson_write` output is not delivery-ready: the customer's GeoJSON is the reference until our own tool/skill is built from it; FNO code comes from SINTEZ after placement, УКЭП is the customer's [D220]) | `src/twinqa/geojson.py`, `adapters/max/agr_tools/` | P8 |
| 14 | FBX export + readback | proven | `tools/blender/fbx_readback.py`, `adapters/blender/bridge.py` | — |
| 15 | Package ZIP + validator V001–V017 | partial | `tools/qa/validate_package.py`, `src/dt_ai/validate/bundle.py` | Q1–Q4 |
| 16 | AGR Checker (SINTEZ) pass | partial (headless run of the Blender extension on KPP1 v005; deferred items open) | `jobs/KPP1/scripts/run_agr_checker.py` | Q5 |

## Territory and environment

| Stage | Status | Where | Backlog |
|---|---|---|---|
| Ground (NPM-territory) | proven (Vatutino Ground v015 NPM + VPM accepted 2026-11-04, PR #906, [D193]; Checker, GeoJSON, MSK-77 and #298 re-placement on v015 open; second site COD-20207 v016 is a trial) | layered cake `src/dt_ai/geometry/ground_cake.py`, quads `ground_quads.py`, `jobs/VATUTINO-SITE/build_ground_v015.py`, skill `model-ground`; earlier contours `archive/2026-11:jobs/GROUND-PROJECTION/` | P9 |
| MAF (GroundEl) | partial (Vatutino: 13 positions built, PR #320, geometry accepted 2026-11-04 with colour zones / material IDs open, issue #889, PR #991 open; «Верона» rows 2-10 accepted for the library [D202]; 119 MAF placed, run v006 technical QA only) | `tools/library/maf_site_set.py`, `tools/library/maf_gen_bench.py`, `tools/materials/atlas_maf.py`, `tools/review/maf_showcase.py`, `jobs/VATUTINO-SITE/maf/`, skill `model-maf` | P10 |
| Flora | tool only (textures of a three-species test list approved, #190; Vatutino placement run v006 placed 3,170 instances, technical QA only, geometry acceptance open; Flora atlas tool synthetic only) | `src/dt_ai/materials/flora.py`, `tools/library/flora_atlas_from_scene.py`, placement `tools/placement_site.py` + `src/dt_ai/placement/engine.py`, SpeedTree MCP, skill `model-flora` | P11 |

## Beyond NPM/VPM

| Stage | Status | Backlog |
|---|---|---|
| Unreal import and interactive experience | missing (no rules yet) | U1–U2 |
| IFC | missing | U3 |
