# COD 20207 build attempt v001/v002 (#420)

Status: **blocked after two identical real-build failures; not passed**.
Gate 1 source/model questions are closed. No FBX, completed comparison, PR or
review queue entry was produced. No full suite/eval receipt is claimed.

## Approved inputs and parts

Artem (card comment 2026-10-21 00:25) approved the orange 1670.085519 m2
unhatched SPOZU component as the building hole, all other unhatched parts as lawn,
and retaining coverings beneath the reference Main roof/canopy projection.
Flat means common zero datum without relief, retaining method-C +6/+12 mm offsets.
No D150 exception. Type 6 uses the approved type-2 tile fallback, not a newly
invented finish. See `gate-1-intake.md` for copies/source hashes and historical questions.

Before the real build:
- `uv sync --extra cad`: exit 0.
- Existing `ground_parts.py` on the copied adapter JSON: exit 0;
  `C:/x/ground-cod-22/intake-v001/parts-summary-v001.json`.
  Largest uncovered components 1670.1 / 16.6 / 14.0 / 2.2 / 1.3 / 0.1 m2.
- `PartsList.model_validate_json` through `dt_ai.core.models`: exit 0,
  **7 confirmed parts**, whole master allocation 150000 triangles per profile;
  surface allocations sum 50000, curbs 30000, skirt 10000. Allocations are not measurements.
- `parts.json` SHA-256 `4cfddbe8028377d619dfbda578f4fa624f66f7bc5630c83c65d310266c7a9509`.
- `build-settings.json` SHA-256 `107bd4f536b381c074bda82f1c83e848aab5b6a4ea53c5005075c0436addc32b`.

## Pipeline portability changes (not yet proven on real site)

The SAME `jobs/VATUTINO-SITE/build_ground.py` gets optional `--site-settings`:
explicit covering slots, a user-authorized flat datum and the name of the small
uncovered-area covering. It still calls `ground_cake.plan_layers`, `build_flat`,
projection, skirt, details, UV and all existing geometry gates. A four-corner
computational plane is explicitly labelled **not survey observations** in the report.
No second mesher or site-name branch is added. Legacy Vatutino path is unchanged.
Configured runs reject duplicate JSON keys, invalid settings, input/output aliases,
nonempty output directories and inputs changing during build. These guards still need
the complete card-required hostile probe matrix before eventual review.

Material slot labels are semantic decomposition only. Existing copied-reference
atlas identities and original UVs have NOT yet been transferred into tiling recipes;
no material/texture/readback acceptance is asserted.

## TDD evidence

Command family (each focused invocation, no full suite):
`env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q tests/test_ground_site_settings.py -p no:cacheprovider --basetemp=C:/x/t_3e9518e5-<run>`.

- Planner tests first, commit `36ba455`: **9 failed** (missing `site_plan`), exit 1.
- Planner implementation: **9 passed**, exit 0.
- Fresh-process CLI test first, commit `020e33b`: **1 failed / 13 passed**,
  missing `--site-settings`, exit 1. Negative CLI controls at this stage are not proof
  of individual guards because the flag itself was absent.
- CLI implementation: **14 passed**, exit 0.
- Real copied-input overlay regression first, commit `668fa59`:
  **1 failed**, exit 1, same GEOS exception as real build. This regression is still RED.
  It is skipped when the local copied input is unavailable, never replaced with synthetic data.
- After attempted precision repair: **14 passed / 1 failed**, exit 1.
  The unsuccessful precision edit was removed; no RED real-site test is represented as GREEN.

## Real execution and failed repair

1. `uv run python jobs/VATUTINO-SITE/build_ground.py C:/x/ground-cod-22/intake-v001/cod_ground_inputs.json --site-settings jobs/COD-20207/build-settings.json --out C:/x/ground-cod-22/ground-v001`
   -> **exit 1** before output directory creation.
2. Self-repair: set site boundary/covering precision to the existing master 1 mm
   noding grid before computing the lawn complement. Same command with
   `--out C:/x/ground-cod-22/ground-v002` -> **exit 1**, same error. Removed this
   unsuccessful edit instead of leaving an unvalidated source-coordinate adjustment.

Both failures: `shapely.errors.GEOSException: AssertionFailedException: Should never
reach here: Unable to determine overlay result geometry dimension`, in
`ground_cake.py:90`, `up = g.intersection(below)` within `plan_layers`.
The repaired-case pytest traceback shows `g` is a GeometryCollection containing
linework, while `below` is an empty Polygon. This suggests polygon-only filtering
of clipped/touching constituents needs investigation; it is NOT a verified fix.
Do not silently discard those constituents: report their source keys and reason/area.
The stop-after-two rule prevents a third build/repair in this run.

## Raw receipt hashes

| Receipt | SHA-256 |
|---|---|
| `tmp/site-red.log` | `08a38c9870ded3d64cfdc7a0c05b913bd3885a840db03e087978b2ca821bc103` |
| `tmp/site-cli-red.log` | `aca495ace120af260a77f0db665acdf691364e6bb619ccc0a8a701263e53d654` |
| `tmp/site-overlay-red.log` | `b30acfd71b370a1e5b06b1c62d550241ad5bf7ac13a823ed9a0f32592f8267de` |
| `tmp/cod-build-v001.log` | `813be7476048534205e58cb2073728f77321dab8eaf063a6ebcea6a9659d9458` |
| `tmp/cod-build-v002.log` | `7e6f5be97883b647e604ed9d5b5730fd250852203b662a5641bf52cff31d51d4` |
| `C:/x/ground-cod-22/intake-v001/parts-summary-v001.json` | `8ac7aa685fe1d1907722ac457527d0449c118723231de397cfcb167989c290e3` |

## Handoff

Next authorized repair: minimize and classify the real clipped-covering
GeometryCollection witness, add a workstation-independent regression, fix the reusable
planner rather than COD-specific geometry, preserve non-area dispositions, and get the
current real-source RED to GREEN. Then complete actual FBX export/readback, site/etalon
material transfer, UCX, xView, flatness, both comparison tables and review publication.
Full suite/evals/hostile self-review remain required before the FIRST review request.
No model question above is reopened. No DCC process was launched in this run; all
commands were foreground and have finished. Worktree changes are committed/pushed
on the existing issue branch; no PR is appropriate while acceptance is incomplete.
