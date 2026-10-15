# Revit for AGR: offline IFC semantic-loss ledger

Card: `t_4adf7009`. Base: `3cf7c9358591a12813ec5bcbcb8e082ddf5fe342`.
Research input: `origin/docs/research-bim-revit-agr:docs/research/bim-revit-agr.md`, proposal E1.
Estimate before implementation: 40–55 minutes, one method. No production code was replaced.

## Question and method selection

Can an offline IFC snapshot distinguish **storey elevations, structural slab bounds, rough openings and window fills**, preserve host/fill/containment relationships and explicitly expose missing relationships on our benchmark-derived geometry?

Selected **E1, narrowed to a semantic/geometry loss ledger**, not another IFC-to-spec adapter. The earlier card's supplied handoff already reported a synthetic IFC intake and K01 comparison; that branch was not inspected or copied. This experiment adds actual slab bounds, cut versus uncut wall volumes, distinct fill geometry and relationship-loss accounting. It does not repeat K01 spec comparison or claim contour recovery.

E2 (selection provenance through saved Blender/FBX transport) was not selected: it requires another profile's DCC. The research's Blender-hosted E1 invocation was replaced by direct offline Python, as authorized for this Revit profile. No Blender, Max, AutoCAD or Revit calls occurred. This card does not say the user opened Revit; neither live bridge was contacted and Revit was not started. Live latency, RVT persistence and exporter behavior remain **not measured**, not failed.

## Setup and input boundary

- Windows, CPython 3.14.7, IfcOpenShell 0.9.0; IFC4 and its default tessellation/Boolean geometry engine. No system software installed; `uv run --with ifcopenshell` supplied the experiment dependency without changing `pyproject.toml` or the lockfile.
- Copied B01/B02/B02t `spec.json`, `object.json`, `tolerances.json`, `etalon.json` where present. The driver consumes copies only. Baseline spec hashes were recorded before implementation and original/copy hashes matched after execution.
- The shell's actual `TMPDIR` initially resolved to system temp, contrary to the runtime description. The initial private copies/timing file were relocated into ignored worktree `tmp/agr-exp-t_4adf7009/`; all subsequent outputs and explicit pytest basetemp paths stayed inside this worktree. No writes into `data/`, original benchmarks or source/approved files.
- **All IFCs are synthetic transport fixtures**, generated from copied extracted specs, not independent architectural etalons and not Revit exports. The 0.20 m slab/wall thickness and fill inset are declared experiment choices, not measured benchmark construction. No binary etalon was opened.
- Six clean files: three benchmark shapes × metre/millimetre length units. Every file uses site → building → storey → product placement chains with a 23° Z rotation and (100, −50, 7) m translation. Structural slab top = level, underside = level −0.20 m. This is explicitly not the AGR inset-plate rule.
- Openings use `IfcRelVoidsElement`; windows use `IfcRelFillsElement`, with 20 mm insets from rough-opening edges. The void extends 1 mm past each wall face to avoid coplanar Boolean ambiguity. Geometry returned by IfcOpenShell is SI; placement coordinates are converted from project units once.
- `read_ledger(path)` independently reopens the saved IFC and accepts no expected spec. It records class census, file SHA-256 + GlobalIds, storey coordinates, slab bounds/volume, rough-opening bounds, fill bounds, relations, cut and uncut wall volumes, unsupported classes and missing-field issues. Synthetic names are comparison keys, not a proposed real-export ID crosswalk.
- The oracle separately derives world bounds and expected cut volumes from the copied Spec and polygon area. Writer and oracle share declared fixture constants but do not obtain measurements from one another. This is transport consistency, not independent architectural correctness.

### Commands actually exercised

Paths below are relative to this task worktree; output directories must be new.

```bash
uv run --with ifcopenshell python experiments/bim-revit-agr/ifc_probe.py \
  --inputs tmp/agr-exp-t_4adf7009 \
  --out tmp/agr-exp-t_4adf7009/run-v002 --repeats 3
uv run --with ifcopenshell pytest experiments/bim-revit-agr/test_ifc_probe.py \
  -q -p no:cacheprovider --basetemp=tmp/pytest-probe3
env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q \
  -p no:cacheprovider \
  --basetemp=C:/Users/artsafro/agr-pilot/AGR-DigitalTwin/.worktrees/t_4adf7009/tmp/pytest-final
uv run dt profiles check
uv run dt schemas --check
```

An additional offline `ifcopenshell.validate.validate(..., express_rules=True)` run on all six clean saved IFCs reported zero schema/EXPRESS issues each. This is not AGR delivery validation.

## Baseline versus prototype

Baseline, **before prototype implementation**: `Spec.model_validate_json(copied_file.read_text()).expanded_floors()`, five samples per fixture including disk read. Prototype: saved IFC open + relation scan + geometry creation + hash, three samples per clean case, excluding Python startup, generation and comparison. These are different operations: **no speedup claim** is justified. The baseline returns three levels/two expanded floors/two openings for each fixture; it has no native slab or IFC relationship census to compare.

| Fixture | Baseline spec parse/expand median (s) | IFC metres median (s) | IFC millimetres median (s) | IFC storeys/slabs/walls/openings/fills |
|---|---:|---:|---:|---|
| B01 box | 0.0001948 | 0.0347833 | 0.0329658 | 3/2/8/2/2 |
| B02 corner/niche | 0.0001919 | 0.0483782 | 0.0473073 | 3/2/14/2/2 |
| B02t terrace | 0.0002281 | 0.0465064 | 0.0475758 | 3/2/14/2/2 |

| Metric | Current baseline | Prototype result |
|---|---|---|
| Level/floor/opening interpretation | Existing Spec expansion | Same expected storey and rough-opening counts in all six cases; two synthetic slabs separately accounted |
| World position and unit handling | Spec SI coordinates | Max tested coordinate/elevation/bbox deviation **1.4211e-11 mm**; threshold 1 mm |
| Slab volume vs polygon area × thickness | No structural slab census | Max error **5.0982e-12 m³**; experiment threshold 1e-5 m³ |
| Wall geometry including opening subtraction | No IFC Boolean geometry | Max cut-volume error **7.0633e-12 m³**; threshold 1e-5 m³; every clean case has a wall with cut volume < uncut volume |
| Host/fill/containment identities | No IFC relation gate | Exact expected links retained in 6/6 cases; 12/18/18 contained products per B01/B02/B02t, each unit arm; two hosts + two fills per case |
| Missing relations | No IFC diagnostic path | **18/18** faults identified: six missing-host, six missing-fill, six missing-containment; all product IDs retained, exactly one association lost per injection |
| Wrong but existing links | Not an IFC operation | Three regressions reject links to a valid but wrong host, fill or storey |
| Existing project offline suite | Same unchanged production code | **2026 passed, 9 skipped, 12 deselected**, one known duplicate-ZIP-name warning, 216.93 s |
| Isolated prototype suite | Absent | **31 passed**, 2.72 s |
| Complexity | Existing validation + expansion, two public calls | 469-line driver/reader/writer/oracle, 135-line tests; no simplification claim; no production adapter/dependency changes |

Numerical errors are floating-point transport residuals, not real-world measurement accuracy. Full contour extraction, contour Hausdorff/area recovery and K01 checker results are **not measured**. Slab volume/bounds agreement is not a substitute for contour recovery.

Raw samples, baseline hashes, counts and comparisons: [`experiments/bim-revit-agr/results.json`](../../experiments/bim-revit-agr/results.json). The downloadable `evidence-v002.zip` contains the six clean and eighteen negative IFCs, their independent ledgers and original run results. `delivery_passed=false` throughout. The report-only CLI returns a file path; process exit 0 alone is not a passing comparison.

## Failures discovered and corrected

1. Cursor round 1: **6 failed, 21 passed**. `run-v001` on copied benchmarks likewise had failed comparisons. Passing a local matrix to `edit_object_placement` as though it were world-space, then manually reparenting, lost the translation/rotation and some opening subtraction. Slab offset was also wrong. The independent coordinate/volume oracle caught this; successful file creation was not accepted.
2. Cursor round 2 used explicit local IFC placements in project units, assigned containment before placement, moved slab undersides down 0.20 m and strengthened exact relationship comparisons. Tolerances were not relaxed. Final copied-benchmark run: **6/6 clean, 18/18 negative cases**. Three small driver-added regressions check wrong-but-valid IDs.
3. An initial repository-wide test attempt overlapped the wrapper temporarily hiding `.claude/settings.json`: **13 failed, 2013 passed, 9 skipped**. This was invalid setup evidence, not a product regression. After wrapper exit/restoration, the full unfiltered offline suite passed as above; no hook/settings changes remained.

## Verdict: E1 — MAYBE

**Useful now as a bounded offline diagnostic prototype:** small snapshot ledgers expose the difference between levels, structural slabs, already-cut walls, rough openings and smaller fills, without occupying Revit. Missing relationships remain explicit rather than being reconstructed from matching names or bounding boxes. Approximate per-snapshot automation cost on these tiny fixtures is 33–48 ms, plus unmeasured interpreter startup; it is not a building-scale throughput estimate.

**Not adopted as a production intake or live-Revit replacement.** No frozen KPP1 IFC paired with matching TwinPack/census was supplied to this worktree. Real exported class/relationship completeness, rooms/spaces, curtain hosts, links, phases/options, roof mapping, materials, source-ID crosswalk and georeferencing remain unverified. The supported product set is intentionally narrow; unsupported mandatory facts must block further adoption. Generic missing-fill warnings also require a real policy for legitimately unfilled voids. No native RVT editing, save/reopen, real exporter or Revit-session sharing claim was exercised.

### Proposed follow-up (not created as an issue/card)

**Title:** Validate the IFC semantic-loss ledger on a frozen KPP1 capture pair.

**Scope:** obtain an authorized versioned IFC plus matching TwinPack/spec/census from the same model revision, exporter version/settings, loaded-link/phase/options metadata and source hashes; run only on copies. Replace synthetic-name matching with an evidenced source-qualified identity crosswalk. Inventory unsupported products and legitimate unfilled voids; compare level/slab/rough-opening facts and exact relations, retaining K01's existing tolerances and open gates. Measure ≥3 offline reads plus separately measured authorized live capture if the user opens Revit. Adoption requires no silently missing mandatory facts. No new RVT export/session mutation is authorized by this report.

## Tooling and boundaries

Prototype written by Cursor (grok-4.7-medium), two completed wrapper rounds. Hermes drove actual execution, reviewed the files/results, added three small verifier regressions and wrote this report. Existing production scripts, standards, benchmarks, capability registry and project state were unchanged. No GitHub issues created. CI: not run (billing lock). Existing delivery/manual acceptance gates, including K01 engine stops, remain open.
