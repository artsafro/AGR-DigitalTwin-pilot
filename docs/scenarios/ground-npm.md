# Cell ground-npm — Ground + MAF + Flora, NPM

The site's Ground FBX inside the project NPM ZIP: Ground surface, GroundEl (MAF), Flora and GroundGlass, no
collisions. Stages: sources → Ground → MAF → Flora → optimisation to the budget → delivery. The OKS of the same
project are the `oks-npm` cell. Router table: [scenarios.json](scenarios.json); procedure: the `scenario` skill.

## Read first (in this order, only what the task touches)

1. [requirements-2026.md](../domain/requirements-2026.md) section «LP (NPM)» — the regulation rows.
2. The skill of the stage in play — it holds the step-by-step route:
   Ground → `.agents/skills/model-ground/SKILL.md`, MAF → `.agents/skills/model-maf/SKILL.md`,
   Flora → `.agents/skills/model-flora/SKILL.md`.
3. Area sheets: [ground-surface](../domain/areas/ground-surface.md), [groundel-maf](../domain/areas/groundel-maf.md),
   [flora](../domain/areas/flora.md), [package](../domain/areas/package.md).
4. The etalon below: `jobs/VATUTINO-SITE/ground-v015-route-a-session-20261104.md` and `placement-report.md`.
5. GeoAGR (the team's legacy Max combine) only when a task names a GeoAGR tool: `C:\x\GeoAGR-private\docs\reference\README.md`
   (outside the repo, read-only).

## Rules that bind this cell

| Topic | Rule |
|---|---|
| Budget | Ground + GroundEl + Flora ≤ 180 000 triangles (reg p.7 §3.6, [npm-vpm](../domain/npm-vpm.md)); the split is the user's decision — bring 2–3 options, never delete MAF or Flora yourself [D167] |
| Texel | NPM Ground 10–40 px/m at 2K [D097]; Vatutino's exception is bound to its master only [D193] |
| Ground master | one master for NPM and VPM, layered cake ([model-ground skill](../../.agents/skills/model-ground/SKILL.md)) |
| MAF | never substituted [D164]; lego parts with inserts [D165]; names `<spec position>_<catalogue id>_GroundEl` [D166]; one library ID list, site 512 set [D168]; sunk 10 cm onto Ground [D095] |
| Flora | height and crown ±20 %, colour per spec [D099]; one 2048 Flora atlas |
| Topology | xView clean [D152] |
| External data | placement by the customer's DWG (SPOZU); FNO from SINTEZ [D220] |

## Route by stage

| Stage | Route today | Status |
|---|---|---|
| SPOZU DWG intake | `tools/source/inspect_ground_dxf.py` (AutoCAD core console → DXF → `ezdxf`) | automated and tested |
| Ground surface | `src/dt_ai/geometry/ground_cake.py`, `ground_quads.py`; builder `jobs/VATUTINO-SITE/build_ground_v015.py` | library tested; builder job-local, no `dt ground` yet |
| MAF | `library/maf/catalogue.json`, `tools/library/maf_gen_bench.py`, `tools/materials/atlas_maf.py` | library + atlas automated; NPM light version and UV remap have no tool |
| Flora | `library/flora/catalogue.json`, `dt_ai.materials.flora`, `tools/flora/` | textures only accepted; no NPM star builder |
| Placement | `src/dt_ai/placement/engine.py` (MAF sinking, Flora points) | ran on Vatutino v014, `passed=false`; re-placement on v015 open (#298) |
| Optimisation | ProOptimizer in Max (Ground LOD, ad hoc) | manual |
| Delivery | `tools/qa/validate_package.py` (NPM stages), SINTEZ AGR Checker | no Ground package has reached passed=true |

## Etalons

- `jobs/VATUTINO-SITE` — Ground v015 NPM + VPM accepted 2026-11-04 (route A, [D193], PR #906); MAF 13 showcase
  positions accepted; placement 3289 instances, technical QA only.
- `jobs/COD-20207` — second site, v016 trial, not passed.

## Checks

`tools/qa/validate_package.py` NPM stages ([validation.md](../domain/validation.md)), `src/twinqa/maf_checks.py`,
`src/twinqa/flora.py`; `dt qa xview` [D152]; SINTEZ AGR Checker before the hand-off.

## Minimal contract (ask once, ≤ 5 questions, each with a recommendation)

- **Sources**: SPOZU DWG (which sheet is coverings, which is planting), relief, the MAF specification, the planting
  schedule; which wins on conflict.
- **Scope**: which stages (Ground only, + MAF, + Flora) and which existing master to build on.
- **Budget**: the target split of the 180 000 triangles, or permission to bring options [D167].
- **Library gaps**: MAF without a library model and species without a library match — model new or wait.
- **Не трогать**: source DWG, accepted masters (Vatutino v015), library originals on the drive.
- **Acceptance and pilot**: one block of the site end to end, a picture to the user, then the rest.

## Known gaps (do not assume a tool exists)

No shared `dt ground` command and no Ground benchmark; 7 of 12 GND rows and 14 of 24 MAF rows have no automatic
check; no NPM light-version tool for MAF and no star builder for Flora; the full Vatutino site (Ground + MAF + Flora,
#298) was never assembled and its real triangle count is not measured.
