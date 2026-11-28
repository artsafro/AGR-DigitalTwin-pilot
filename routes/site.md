# Site trail: Ground → MAF → Flora (`ground-npm`, `ground-vpm`)

Second trail (#1937, hygiene plan rec 9), following the [NPM/OKS template](npm-oks.md). Use the
[NPM](../docs/scenarios/ground-npm.md) or [VPM](../docs/scenarios/ground-vpm.md) cell for full profile rules and
limits. This trail documents the route; it does not approve any model or delivery.

## Entry

Passport first: `jobs/<ID>/passport.json` [D397], then [intake](../docs/agents/task-intake.md) and the cell block
(`uv run python tools/architecture/skeleton_guard.py --show ground-npm` or `--show ground-vpm`).
Confirm the exact PartsList at Gate 1 before construction. Keep the [eight gates](../docs/procedure/TASK_TO_MODEL.md)
in the job contract. If sources conflict or are missing, stop the dependent step; do not infer site data or assets.

Run `uv run agr --help` first. Choose Blender or Max per step and record why [D293]; confirm application,
version, document, units and ownership before DCC work. Read the area and skill for that step
([stage index](../docs/agents/SKELETONS-stages.md)). Write new versions; leave sources and library originals intact.

### Site intake checklist

Record these site facts in the existing job contract and [intake](../docs/agents/task-intake.md) (`passport.json` /
Gate 1 PartsList — not a new schema or approval policy), citing the source file/sheet/layer or confirmed user answer
for each item:

- **Boundary and stage footprint intent:** record source refs for the site/stage boundary and each footprint — keep as
  a **hole** or **cap** it; if capped, record the confirmed covering ID (never a general default).
- **Cover groups and IDs:** record source refs for which cover groups stay **distinct** vs **merged**, with explicit
  source-to-working (or old-to-new) ID mappings (never a general default).
- **Sport markings:** record source refs for named markings layer(s) and confirmed width, glyph treatment and export
  role, or record markings explicitly as **out of scope**.
- **Copied-DXF schedule inventory:** include **nested blocks** and **off-plot tables** (outside the plot boundary) in
  the stage 1 schedule inventory by citing their block/table source, not as site geometry.
- **Unresolved items:** if a required item has no source reference or confirmed answer, record it as **unresolved** and
  stop **only the dependent step** per current intake; never infer a cap, cover merge, width, glyph treatment, or export
  role.

## Stages: owner, boundary and evidence

**D293 order:** Flat Ground (hatches → IDs → seams/insets → textures and UV) → relief projection → texture fix
and skirt → VPM Ground UCX → MAF and Flora → NPM atlas version before export → checks → checker.
Steps 3–5 are checkpoints within one `agr ground site SPEC.json NEW_OUT`, not separate subcommands. For a manual
handoff, the help command identifies the build or evidence owner; it does not automate the manual work.

| # | Stage | Owner command and boundary | Rule | Evidence to retain |
|---|---|---|---|---|
| 1 | Sources and Gate 1 | `uv run agr inspect --help`; `uv run python tools/source/inspect_ground_dxf.py --help` inventories a copied DXF, not the original DWG or its intended semantics. | [D186] [D293]: SPOZU coverings, MAF and plant schedules, relief and source authority. | Source/copy SHA-256, units, sheet/hatch and copied-DXF schedule inventory (citing nested blocks and off-plot tables separately from site geometry), [Site intake checklist](#site-intake-checklist) source refs or unresolved items, confirmed PartsList hash. |
| 2 | Boundary and project zero | `uv run agr zero --help`; the verifier checks the written OBJ against relief and a supplied zero. It does not determine either boundary or zero. | [D279] [D293]: boundary and ±0.000 from the project, or ask. | Boundary and zero citations, separate ground mark and height system, exported Z check. |
| 3 | Flat Ground | `uv run agr ground site --help`; follow the [Ground sheet](../docs/domain/areas/ground-surface.md) and [R5](../docs/procedure/node-r5-ground.md). The builder writes triangulated OBJ, not a working quad FBX; v015 replays Vatutino only. | [D293] [D312]: hatches → working IDs → seams/insets, quads where possible in the working master. | Flat source overlay, covering and ID inventory via [Site intake checklist](#site-intake-checklist) (retained holes or confirmed cap covering IDs, source-to-working / old-to-new cover ID mappings, named marking layers or out-of-scope status), contours/holes, topology before triangulation. |
| 4 | Flat textures and UV | `uv run agr ground site --help` assigns tile UVs by used covers before projection; delivery maps are a separate check. | [D293] [D399]: new Site/Ground VPM UDIMs run consecutively from 1001 with no gaps, independent of working material IDs (#1898). | Verify tile-to-material mapping against export; keep `ground-udim.json` and `ground-udim.md` beside the archive, outside the ZIP. Leave delivered packages unchanged. |
| 5 | Relief, texture fix and skirt | `uv run agr ground site --help`; local level differences and steep strips may need separate DCC work. | [D293] [D251]: project in Z, preserve XY and IDs, fix textures, then skirt each outer perimeter ≥1 m down; exclude inner holes. | Relief overlay, projection misses, levels and UV seams; `ground-report.json` and exported skirt drop by outer edge. |
| 6 | Ground UCX (VPM only) | `uv run agr ucx --help`; `agr ucx MODEL OUT Ground` needs FBX/Blend, not Ground OBJ. That handoff is not wired. | [D330] [D298] [D098] [D134] [D433] [D436]: surface hulls only, no MAF/Flora UCX; gaps 2 mm–1 cm and one-sided Ground-to-UCX distance ≤10 cm; over the [D012] budget is reported, never refused, when the form needs it; convex within 1 mm. | Fresh hull readback, coverage, convexity/closure, gaps, distance, triangle budget line (`AGR_UCX budget:`) and V010 report. |
| 7 | MAF selection and build | Search the catalogue directly; use the [MAF sheet](../docs/domain/areas/groundel-maf.md) for modelling and catalogue misses. `uv run agr npm-light --help` is the optional MAF light/atlas owner, not a search tool. | [D402] [D094] [D403] [D164]: search `library/published/catalogue.json` (index `library/assets/maf_unified.json`); `library/maf/catalogue.json` is legacy only. Match spec image and DWG contour. ≤10 cm per axis is the same MAF; otherwise within ±10% is a variant to show Artem; beyond that, model new. No substitution. | Catalogue ID or source for new model, per-axis dimensions, variant decision if applicable, material IDs and silhouette/atlas readback. |
| 8 | Flora selection and build | Check the catalogue per the [Flora sheet](../docs/domain/areas/flora.md); if no accepted bush matches, `uv run python tools/flora/build_flora_star.py --help` builds from approved maps. | [D099] [D102] [D406]: match species/colour and height/crown ±20%; NPM star with separate opacity, VPM shell by default with diffuse alpha. | Schedule match, dimensions, map approval and silhouette readback. |
| 9 | Place on Ground | `uv run agr place --help` takes prepared paired NPM/VPM inputs. Single-profile placement uses `dt_ai.placement.engine` through the job adapter; Ground OBJ → placement inputs is not wired. | [D329] [D293] [D095] [D100] [D302]: same SPOZU points for both profiles, sink 10 cm; record Flora seed and off-Ground drops. | Instance IDs, positions and heights, profile parity, requested/placed/dropped counts and reasons. |
| 10 | NPM atlas and budgets | For a pair, derive from placed VPM or prepare both profiles in parallel. Ground shares geometry and coordinates; the OKS derive alias does not convert Ground. `uv run agr npm-light --help` covers MAF only; `uv run python tools/qa/master_topology.py --help` measures the working master. | [D293] [D167] [D301] [D404]: profile atlases and measured budgets; lighten job copies only. ProOptimizer is **off by default**. Artem chooses the NPM budget split. | Surface parity, atlas/UDIM and opacity readback, component/profile triangle totals and budget options if needed. |
| 11 | Export, readback and package | Assembled-site export is job/DCC work, not a generic command here. `uv run dt qa xview --help`; `uv run agr package-npm --help`; `uv run agr package-vpm --help`. See the [package sheet](../docs/domain/areas/package.md). | [D293] [D366] [D152]: triangulated delivery FBX, separate working FBX outside ZIP. | Versioned FBX and ZIP hashes; fresh exported-file topology, UV/maps, materials, names, units and transforms. |
| 12 | Validate, review and checker | `uv run agr validate --help` (VPM `--ground-area-m2` from documented S_ter − S_pz); `uv run agr open-review --help` for an authorised copy; `uv run agr checker --help` for installed SINTEZ. | [D352] [D365] [D300]: preliminary SINTEZ → Artem's visual decision → final SINTEZ on the accepted export hashes. | Validator findings including V008 UDIM sequence, manual checks, visual verdict, raw final checker results/version and absolute hand-off path to Artem. |

For site acceptance, accompany the Max 2026 QUAD review copy with a flat ID-colour copy [D420].
Preserve material IDs and cover names in `MS_REVIEW_ID`; do not change delivery materials.
The [Moskovsky job record](../jobs/moskovsky-sosh1200/STATE.md#evidence-location) locates the historical
ID-colour and site assembly scripts. They are evidence, not commands on this trail.

Help success is not a site run. `passed=true` requires all mandatory machine and manual gates on the same inputs
and exports. Keep technical QA, Artem's acceptance and publication separate; `review`, `not_run` and missing
evidence are not passes.
