# COD 20207 Ground v008 (#420)

Status: in progress; not passed. Historical attempts remain in gate-1-intake.md,
build-attempt-v001.md and overlay-repair-v002.md; this report supersedes only their
open curb-joint question, not their crash/failure receipts.

## Approved curb policy and build

Artem, card comment 2026-10-21 01:20: drive curb stays continuous; garden curb
ends at a 6 mm gap at source pairs 5252CE/527511 and 527BBC/527511.
The reusable builder now accepts a boolean `separate_curbs` site setting, enabled
in build-settings.json. It calls the tested existing detail primitive, without a
site-name branch. Legacy calls omit the setting and retain their previous order.

- Tests-first c046f40: fresh-process CLI RED 1 (unsupported policy setting).
- After wiring: tests/test_ground_site_settings.py + test_ground_curb_joints.py:
  17 passed, exit 0 (tmp/joint-config-{red,green}.log).
- `uv sync --extra cad`: exit 0.
- `uv run python jobs/VATUTINO-SITE/build_ground.py C:/x/ground-cod-22/intake-v001/cod_ground_inputs.json --site-settings jobs/COD-20207/build-settings.json --snap 0.003 --out C:/x/ground-cod-22/ground-v008`:
  exit 0; 11/11 geometry gates; 5852 total / 2514 surface triangles per profile;
  xView 0 vertex / 0 face pairs. No D150 exception.

Flatness means the approved common WCS zero datum, retained method-C covering
steps, +18 mm curb bases with 150/50 mm exposed sections, and 1 m skirt. This is
not a survey or relief validation. Copied-reference relief is diagnostic only.

FBX, texture, UCX, exported-file QA, comparison tables and review publication are
not yet claimed by this initial receipt.
