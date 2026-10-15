# Offline IFC intake versus KPP1 tolerances

**Status: BLOCKED / incomplete experiment. No adoption verdict.** Baseline is measured; IFC generation, parse/extraction benchmarks and accuracy comparisons could not be executed because the required Cursor editing route produced no prototype in three attempts.

## Question and scope

Can a Revit-free IFC intake recover storeys, slab/wall outlines and hosted opening boxes within the project's K01 tolerances? One method: IfcOpenShell geometry and placement extraction. Source: `docs/research/revit-api-automation.md`, Proposed Next Tasks #1. The existing `jobs/KPP1/scripts/export_revit_groups.mjs` requires a live proprietary bridge and exports FBX, not IFC; it is not executed here. Revit is closed and was never started.

Time box: approximately 60 minutes. Only an isolated prototype is in scope, not production integration or a complete generic IFC importer.

## Inputs and baseline

No tracked `.ifc` input was found (`git ls-files '*ifc*'`). Committed B01/B02/B02t `spec.json` files are etalon-derived **specifications**, not newly read FBX/MAX geometry. Copies of their benchmark directories and K01 tolerances were made in `%TEMP%/agr-exp-t_b083dc71/` before use. Any generated IFC is explicitly **synthetic**, derived from these copies; this is serialization/intake feasibility evidence, not validation of Autodesk's IFC exporter or acceptance of KPP1.

Baseline commit: `91795c0`. `adapters/revit/README.md` explicitly says the generic RVT/IFC adapter is unimplemented. Current `dt spec extract` accepts existing mesh/TwinPack dumps, not IFC. There is therefore no existing offline IFC extractor whose speed or accuracy can honestly be compared head to head. The existing JSON+Spec validation route is a lower-cost control, not an equivalent geometry importer:

| Copied fixture | JSON read + current Spec validation median, seconds (5 runs) |
|---|---:|
| B01 | 0.000158100 |
| B02 | 0.000151300 |
| B02t | 0.000167200 |

Pre-prototype offline suite: **1767 passed, 2 skipped, 11 DCC tests deselected**, 169.30 s. Initial uncorrected environment: 4 failures / 1763 passes, all MSYS child-path conversions. Command-local repair (no production edits):

```bash
env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q \
  -m 'not dcc and not blender' --basetemp=.pt2 --tb=short
uv run dt profiles check
uv run dt schemas --check
```

Profiles and all 11 schemas pass. Scratch test trees were subsequently moved under ignored `tmp/t_b083dc71/` to avoid Cursor indexing temporary fixtures. CI: not run (billing lock).

## Acceptance boundaries

Use copied `benchmark/bench-k01-kpp1/tolerances.json`: equal level/floor/kink/opening counts; level elevation ±0.03 m; contour relative area 0.02 and Hausdorff 0.05 m; opening bbox 0.05 m. Grilles are excluded from the opening verdict by project policy. Unknown opening kind is not guessed to be a grille.

A comparator `match` is only a match on the rows it actually checked. Missing roof report values and `roof=None` skip roof/parapet rows in the current comparator; they must be listed as unsupported, not treated as evidence of correct roofing. Terrace semantics, materials and native Revit state are also outside this pilot.

## Results: baseline versus prototype

| Measurement | Current implementation / control | IFC prototype |
|---|---|---|
| Offline IFC intake | Not implemented (adapter README, CLI inspection) | Not produced; not tested |
| Parse/extraction median | JSON control above; not IFC geometry time | Not measured |
| Levels / contour / opening accuracy | No baseline IFC output | Not measured |
| Maximum output deviation, mm | Not applicable | Not measured |
| Current offline tests | 1767 pass, 2 skip, 11 deselected | No prototype tests available |
| Production code changed | 0 lines | 0 lines; no prototype code |

**Verdict: not assessed**, rather than adopt/maybe/reject. Tooling failure is not evidence for or against IfcOpenShell. Dependency import alone (`uv run --with ifcopenshell python -c "import ifcopenshell; print(ifcopenshell.version)"` -> `0.9.0`) proves availability, not extraction correctness. No performance improvement or project geometry acceptance is claimed. No follow-up adoption tasks are proposed because nothing was validated.

## Blocker and recovery attempts

Required writer: Cursor via the authorized `cursor-run.ps1 -Model grok-4.7-medium` wrapper, not direct CLI invocation. Driver/hermes was to execute and verify code. Three wrapper invocations produced **no files** in `experiments/revit-ifc-offline-intake/`:

1. Foreground wrapper: terminal returned `timed out after 420.0s` despite requesting 1800 s. The process was no longer present. Wrapper cleanup had not run; its hidden `.claude/settings.json` was restored from the preserved copy, without altering its contents.
2. Retried as a tracked background process. Cursor transcript recorded task/schema reads and an overbroad dependency search under the user home. After 905 s there were still no writes and stdout was empty; the driver stopped the process. Moving pytest scratch under ignored `tmp/` reduced indexing noise, but did not yield an implementation.
3. Final, reduced task: low-level IFC4 construction, exact file reads only, no dependency searches. Transcript showed the requested task/schema/B02 reads; after 638 s there were still no prototype files and stdout was empty. Stopped rather than exceeding the three-round limit. The precise internal Cursor/model cause remains unknown; no quota error was observed.

All launched Cursor sessions were stopped; `.claude/settings.json` restored byte-identically (`git diff -- .claude/settings.json` empty). Logs remain locally in `tmp/t_b083dc71/`; the earlier copied-reference baseline samples remain in `%TEMP%/agr-exp-t_b083dc71/baseline.json`. Prompt files are in the active profile scratch directory (`t_b083dc71-cursor-1.txt`, `t_b083dc71-cursor-3.txt`). No DCC session, RVT source, IFC source or `data/` content was modified.

## Remaining experiment and live-Revit boundary

After the editing route is restored, the remaining bounded experiment is:

1. Write isolated generator/extractor/tests; generate clearly synthetic IFC4 from copied B02 (optionally B01/B02t) in metre and millimetre variants, translated/rotated building plus nested storey/element placements.
2. Recover storeys/elevations, uncut wall footprints, slab contours and opening geometry/host relations from IFC only. Preserve source hash, GlobalId, units/frame and unknown fields. No geometry from oracle metadata.
3. Run at least three parse-only and parse+geometry timings; compare against the original copied specifications with the existing K01 comparator, plus unrounded maximum deviations and exact entity counts. Test missing units/geometry/hosts and just-inside/outside tolerance perturbations.
4. Rerun the same offline tests, publish the completed report and one experiment PR. Estimate: 20–35 minutes of implementation/measurement **if Cursor writes work**, excluding further environment repair.

Candidate checks that do not inherently require Revit once a suitable IFC exists: exported storey elevations/placements/units, represented wall/slab outlines, represented opening bbox/void-host relationships, counts and tolerance comparisons. **None has been measured on IFC in this attempt.**

Still needing a real approved export and, for native-state verification, a user-opened Revit: actual KPP1 exporter completeness/settings/version; source-versus-export coordinate alignment; native levels and roof/parapet semantics not exported; phases/design options/category filtering; unloaded or nested RVT links; native UniqueId/ElementId mapping and family handedness; native RVT modification/readback and IFC link/import parametric behavior. Materials and room/space boundaries could be inspected offline if exported, but this pilot does not test them. Synthetic B02 parity would still not establish these claims.

## Agent trace

- Sessions: not measured (no transcript)
- Written by: Report/baseline by Hermes; prototype was to be written by Cursor (grok-4.7-medium), but three attempts produced no code
- Subagents: not measured (no usage log, no transcript)
- Skills: not measured (no usage log, no transcript)
- Commands: not measured (no usage log, no transcript)
- Hook denials: not measured (no transcript)
- Retries: not measured (no transcript)
- Context at handover: not measured (no transcript)
- Duration: not measured (no transcript)
- Commits: `91795c0..91795c0` (0 commits)
