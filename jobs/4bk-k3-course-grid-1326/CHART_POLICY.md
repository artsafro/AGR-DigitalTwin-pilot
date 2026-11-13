# Chart-seam policy checkpoint — #1326

Status: **stair seam question answered YES; main-wall ring termination pending**.
`pilot_passed=false`. Artem's exact 2026-11-13 answer is in `seam-approval.json`;
`LOOP_POLICY.md` is the current checkpoint. The question and measurements below are
retained as the historical pre-answer record, not a request to answer it again.
The 771-face finish cohort is confirmed; see `finish-approval.json`. No additional
material, geometry cut, density reduction, extra tile or replication is proposed here.
Check level: full for the eventual reusable tool; this checkpoint is not review-ready.

## One question, with recommendation

May the brick pattern break across explicitly declared **existing perimeter edges of
the stair's thin end/underside returns**, while these faces remain ID1 brick and remain
inside the 771-face cohort? Recommended: yes, keep the main wall/floor-join courses
continuous and use those existing return edges as chart seams. Example at source vertex
516: red face 450, yellow underside 467, blue end face 468. Candidate existing seam
edges are 450/467 and/or 450/468; this is **not a new geometry cut**.

If the <=0.1 px full-bond gate must instead cover every shared edge of all three faces,
that interpretation conflicts with the no-distortion limit at the closed fans below.
Please specify which existing return edges may carry a pattern discontinuity; the agent
will record exact exception edges before continuing. Finish approval alone did not
specify a chart-seam exception. This question does not reopen the confirmed finish IDs.

## Fresh source-bound witness

Blender **5.1.2 background**, copied `K3_assembly_v006.blend`, metric scale 1.0.
Source and hash-identical working copy remain unchanged. Source-face readback:
2,015 faces, of which 771 ID1 target and 1,244 protected. Original ten source/map hashes
were checked again: **10/10 equal**. No daytime Max connection or scene switch.

`corner-audit-v001.json` was produced from a new read-only Blender process using
`tmp/1326_faces.py`. The report's SHA256 pins the complete face/XYZ/UV readback;
its durable copy is listed in `chart-evidence-v001.json`. It lists all target face
keys and all protected keys; no faces were dropped. Face and vertex indices are 0-based.

The reusable audit uses `uvlayout_core.tri_normal` and source mesh connectivity, not
UV coincidence or historical joint counts. At a closed three-face fan, a continuously
unfolded planar chart needs the face angles to sum to 360 degrees. For anisotropy `k`,
the maximum change of one angle under an affine map is
`2*asin((k-1)/(k+1))`. At `k=1.02`, the summed three-angle budget is only **3.403765 degrees**.
The measured defects here are **63.432232–90.002911 degrees**, on real source faces.
The shortest incident edges are about **30 mm** (about **15.36 px** at 512 px/m), not
zero-length artefacts. A seamless isometric chart cannot close these fans. Separate
chart seams avoid this conflict without changing geometry or finish IDs.

| Stair vertex | Three ID1 faces | Angle sum, degrees | Defect, degrees |
|---:|---|---:|---:|
| 484 | 454, 488, 489 | 269.997089 | 90.002911 |
| 487 | 453, 454, 488 | 296.562444 | 63.437556 |
| 488 | 454, 486, 489 | 270.002911 | 89.997089 |
| 491 | 453, 454, 486 | 296.567768 | 63.432232 |
| 512 | 465, 470, 472 | 269.999455 | 90.000545 |
| 514 | 449, 465, 470 | 270.000470 | 89.999530 |
| 516 | 450, 467, 468 | 269.998658 | 90.001342 |
| 517 | 450, 468, 469 | 269.999290 | 90.000710 |
| 518 | 451, 467, 468 | 270.001342 | 89.998658 |
| 519 | 451, 468, 469 | 270.000655 | 89.999345 |

This is a **conditional chart-continuity obstruction**, not a proof that one UDIM is
impossible. No new packing trial has been certified. More tiles alone do not remove
intrinsic corner curvature; do not ask for extra tiles as a substitute for this policy.
The audit covers closed three-face fans only; no absence-of-other-defects claim follows.

## Diagnostic picture and preserved scene

`G:/Мой диск/AGR-evidence/1326-stylobate-course-grid/chart-policy-v002/stair-vertex516-labelled.png`

The image shows the **actual source mesh** in temporary diagnostic colours, not proposed
finishes, brick UVs or a textured acceptance render. Red/yellow/blue faces all remain
brick in the confirmed manifest. Rendered and visually inspected: all three faces and
their common corner are visible. No scene was saved by the render script.
The first render attempt failed because the source scene has no World; the second
created a diagnostic World in memory and succeeded. Failed directory v001 contains no
render; successful v002 is separately hashed, never overwriting an earlier output.

Existing unmodified Max 2026 source-only inspection copy (quads), not opened:
`G:/Мой диск/AGR-evidence/1326-stylobate-course-grid/intake-v001/3k_intake_v001.max`.
Opening still requires Artem's **«открой»** and must not switch his daytime scene.

## Tests and commands

Before (RED): `09ac61bf`, new test imported the missing public audit;
`pytest -q tests/test_course_grid_audit.py` -> 1 collection error (`ModuleNotFoundError`).
After (GREEN): the same regression and additional input/CLI tests -> **17 passed**.
Generated rigid-transform probe: seeds 0–19 -> **20/20** corner defects retained.
Fresh-process CLI exits 1 for a non-passing audit; malformed/empty inputs and existing
or aliased outputs exit 2 without writing or deleting an input. No audit can return
`passed=true`, including a single face without corner witnesses.

Run from repository root:

```text
uv run python -m tools.materials.course_grid_audit <source-face-readback.json> <new-report.json> --material-id 1
```

Readback script, render script, raw readback, audit snapshot, raw audit and images are
sealed with `SHA256SUMS.txt` under `chart-policy-v002`; see `chart-evidence-v001.json`.
The CLI is an incomplete reusable **preflight slice**, not `agr unwrap-atlas` or a
finished packing/unwrap implementation. It is not registered as a shared capability.
No full suite has been run on this checkpoint; the once-per-PR full suite remains due
before the first review, after the policy and implementation are complete. No PR opened.

## Research section 5 — truthful current status

| Metric | Fresh measurement / open gate |
|---|---|
| Course/bond phase | No new output; approved seam exceptions pending. Source corner witness above is geometric, not a measured phase residual. |
| Panel joints | Proposed 10 mm inside owner / centre 5 mm inward unchanged; no new D/ERM/N raster or joint sample certificate. |
| Directional density | Existing source UV minimum 511.433889 px/m, maximum 512.566855; baseline fails legal lower bound. No pilot UV correction claimed. |
| Unique/padded union | Not measured; no new tile layout. |
| Islands/reuse | 771 target source faces traced; not a new island/representative count. |
| Tile/padding/orientation | No pilot output; no passing padding, mirror or tile certificate. |
| Preservation | Ten source/map hashes 10/10 equal; working copy hash identical; no UV/geometry/material writes saved. |
| Artem visual verdict | Pending; the diagnostic picture is not pilot acceptance. |

Next: record the permitted existing chart-seam edges -> resolve one common chart with
explicit exceptions -> classify joint masks and equivalent appearances -> fixed-density
one-tile fit -> new export/fresh readback -> numeric table + stage close-ups -> Artem's
visual verdict. On real fit failure, preserve density and ask extra tile vs authorized
loop cut as required by [D275]; do not conflate it with this chart-policy question.
