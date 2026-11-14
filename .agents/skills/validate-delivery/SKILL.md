---
name: validate-delivery
description: 'Final check of a deliverable (NPM/VPM package, exported model, Unreal level, packaged build) against project priorities and delivery rules before it is reported done or handed over. Use before declaring a delivery complete or sending it to a client. Use when: «готово, можно отдавать?», «проверь пакет NPM перед отправкой», «финальная проверка модели».'
---

# Validate delivery

Validate the **delivered files**, not the working scene: re-read the exported result
(from the ZIP when there is one) in a clean scene/process and check that.
Run the machine checks: `py -3 tools/qa/validate_package.py <zip|fbx|geojson> --json`
(stages V001-V017; exit 0 passed, 1 fail, 2 review/not_run left). Stages it reports
`not_run` need the FBX scene (tools/blender readback) or manual review — never count them as pass.

## Decision first: which rule set

- **NPM / VPM package** → run the V001–V017 checks in `docs/domain/validation.md`;
  each check cites its regulation page.
- **Unreal / internal deliverable** → run the five priority checks below only.

## Checks

Run in priority order from `CLAUDE.md`. Each check ends as `pass`, `fail`,
`review: <conflict # or reason>` or `not checked: <reason>`.

1. **Architectural accuracy.** Key dimensions and element counts (floors, openings,
   facade modules) match the source report in `docs/sources/`.
2. **Scale and transforms.** Units (1 unit = 1 m), up axis, origin and pivots per
   profile, rotations reset (`docs/domain/geometry.md`).
3. **Materials.** Every material slot assigned and named per profile, no missing
   textures, maps/format/size/padding per profile (`docs/domain/materials.md`,
   `docs/domain/uv-textures.md`).
4. **Performance.** Triangle count per FBX against the profile budget; material and
   texture-set counts; texture resolutions.
5. **Visual fidelity.** Screenshots from fixed cameras (front and angled), compared
   with the approved reference or previous accepted version.

## Modelling gates (every modelling job, #1030)

Manual gates on the delivered geometry, on top of the checks above and V001-V017. Each starts as
`not checked`, ends as `pass` only with its measurement and the user's sign-off, and the same item is in the
checklist `docs/domain/validation.md`, "Modelling gates". No validator stage covers them, so a clean validator
run does not close them.

- **G1 Texture-joint continuity.** Starts `not checked`. Joint and pattern lines continue across every face border
  and cassette joints, and the joint phase is kept on each facade plane (`docs/domain/uv-textures.md`, "Project UV
  rules": keep joint phase; "Job-level UV/texture lessons": lines must continue across cassette joints). Measure:
  when the job has a texture spec and UV layout, run a lattice-crossing check (reference implementation, job-local:
  `jobs/elv-tc-vpm/scripts/joint_continuity_v008.py`, Blender); any unmatched crossing or a plane with more than one
  phase is `fail`. Otherwise, or in addition: front and angled renders of every joint-bearing face border, joint
  lines visible, compared by the user. A continuous element (cover strip, plank, cornice) cut into pieces is `fail`.
- **G2 Decor embed.** Starts `not checked`. Decor and attachments (arches, light fixtures, frames and similar)
  embed 10-20 mm into their facade, no floating stand-off ([D199], `docs/domain/geometry.md`: constructive embed
  >= 10 mm). Measure per decor object the depth of its contact face into the receiving surface: gap > 0 (floating)
  or a stand-off is `fail`, depth < 10 mm or > 20 mm is `fail`. A job exception exists only as a dated user decision
  (elv-tc-vpm keeps its 6 mm stand-off by [D197]). The V004 self-intersections these embeds create are planned per
  job and reported as `review: conflicts #44`, never removed by moving the decor.
- **G3 Edge loops.** Starts `not checked`. Edge loops and rings continue through the mesh; a loop that starts and
  stops mid-run is a defect even when the mesh is closed ([D200], `docs/domain/geometry.md`). Listed here as a gate;
  checked visually on the wireframe with the user.

Never change the geometry only to make a validator or one of these gates pass: read
[`docs/agents/working-principles.md#never-bend-geometry-to-pass-a-validator`](../../../docs/agents/working-principles.md#never-bend-geometry-to-pass-a-validator).

## Decision points

- A build report counter of skipped or failed elements (`*_fail`, `skipped`, `miss`, `dropped`, ...)
  above 0 is a `fail`, not a note (#1031): run `uv run python -m dt_ai.validate.build_counters
  --report <report.json> --counter <name>` (exit 1 = fail, a missing declared counter fails). The
  delivery is not passed until the count is 0 or the user accepts the listed exceptions (counter,
  exact count, quote and date). Where the spec gives a source face/plan count, compare it with the
  read-back output (`--source-count N --output-count M`); a difference is a `fail`.
- A check touching an entry in `docs/domain/conflicts.md` ends as `review` with that
  entry number; do not pick a side.
- Output of an external checker (SINTEZ AGR Checker, CheckToolBox, ucx_check) is
  evidence, not the verdict: map each finding to a check and a regulation page. A
  partial run (one function, isolated component) is not a checker pass.
- Manual checks (V015–V017, visual fidelity) need the user's sign-off; record who and
  when.

## Report

Write `docs/deliveries/<deliverable>-<YYYY-MM-DD>.md`: file paths with SHA-256, each
check with result and evidence (numbers, screenshots, commands), and the verdict.
Report the verdict for the `In production` section of `docs/PROJECT_STATE.md`: in the handoff from a task
branch, in the section itself only on `main` after the merge (`docs/agents/WORKFLOW.md`, "Project state").

## Completion

The verdict is `passed` only when every check is `pass` and every manual check is
signed, including the modelling gates G1-G3 of a modelling job. Any `fail`, `review`
or `not checked` makes it `not passed`, listed with what remains.
