# Review textures before user handoff (#1365)

This is a **review-copy** gate, not regulatory NPM/VPM validation or visual acceptance.
Run it on the exact saved file before opening that file for the user. Keep delivery
UDIMs, material slots, geometry and UV unchanged. Never repair a review source in place.

## Scope

Create a JSON scope listing **every textured object/ID being reviewed**, e.g.:

```json
{"ids":[{"object":"K3_TypFloor","id":1},{"object":"K3_Floor2Skirt","id":1}]}
```

Blender IDs are 1-based material slots, not exported UDIM numbers. Max IDs are actual
face material IDs, resolved through Multi/Sub's `materialIDList`, not list positions.
Names are exact. Empty, duplicate, unknown or unused IDs fail; no first-slot fallback.
The scope is an explicit human-reviewed inventory, not automatic textured-ID discovery.
Unlisted IDs are outside the receipt; never describe a subset as a whole-scene pass.

## Blender 5.1.2+

Use the shared isolated launcher (factory settings, auto-execution disabled,
`--python-exit-code 1`); it opens the `.blend` read-only and preserves source hashes:

```bash
uv run python -m dt_ai.core.blender_runner \
  --script tools/review/review_textures.py \
  --output-json tmp/review-v001.json --log tmp/review-v001.log -- \
  --scene "C:/path/review.blend" --scope tmp/review-scope.json --report tmp/review-v001.json
```

Require an active Material Output fed by Principled BSDF; Base Color must be linked
to Image Texture **Color**, with an existing file (all declared UDIM tiles) or packed
image. Unlinked/empty/muted/unsupported shader routes fail closed; reroutes are supported.
Procedural/generated-only images are not file evidence: save/pack a file image first.
No automatic render-script wiring, shader repair, saves or global settings changes.

Reports are exclusive-create: existing/stale reports, input aliases and hardlinks are
refused, not overwritten or deleted. A failed check still emits its per-ID findings;
Blender exits nonzero and the launcher reports that failure, not a successful receipt.

## Max 2026 / pymxs

Use the authorized live wrapper **only to inspect the current document**, after reading
its PID, file, dirty state and units. Do not load/reset a user's open scene for this check.
Inside Max Python, load `tools/review/review_textures.py` with `importlib.util`, then call
`module.run_max(scope_path, NEW_report_path)`; return 0 means pass, 1 means fail/review.
The report's `status` is authoritative: a successful MCP transport alone is not a pass.
When using MAXScript, propagate Python exceptions and inspect the JSON report separately.

Supported diffuse routes are Standard `diffuseMap` and Physical `base_color_map` with a
plain **Bitmaptexture** and a real image file. Unsupported shaders, wrappers and
MultiTile-only diffuse fail closed. This implementation uses the plain Bitmap option;
it does not infer that any Blend graph is an authorized UDIM Viewer route.

For joint-bearing IDs also declare `joint_m` and `tile_m` (physical span of that bitmap
at the reviewed mapping scale). Joint sampling is
`joint_m / tile_m * min(current_Nitrous_limit, bitmap_width, bitmap_height)`.
At/below 2 texels the result is `review`, never a readability pass. Missing dimensions
are `review: joint sampling not measured`; fix the scope, not the scene, to measure it.
Read `NitrousGraphicsManager.GetActiveViewportSetting().TextureSizeLimit` only. Changing global Nitrous limits,
display performance or other DCC settings is **ask-first**, even if it improves visibility.
This conservative gate does not prove viewport zoom, UV phase or visual approval.

### Isolated native Max regression (not the user's live scene)

`tests/max_tools/run_review_textures_1365.py:run(repo, NEW_evidence_directory)` requires
an empty Max 2026 and creates a labelled synthetic triangle with MultiTile, then replaces
its diffuse with Bitmap. It asserts fail -> pass -> repeated pass and writes a native JSON
receipt plus versioned synthetic `.max` files. Do not run it in a live scene; do not reset
or close the user's Max to make room. Once an authorized batch slot is free, call it from
a card-specific MAXScript wrapper using `python.Execute`, through:

```bash
python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max \
  --version 2026 --card t_3b38fc56 --file tmp/run-native-max.ms --out tmp/native-max-launch.json
```

The wrapper must propagate Python assertion failures; native artifacts belong outside git
in a new `G:/Мой диск/AGR-evidence/1365-review-textures/` version (fallback `C:/x/t_3b38fc56/evidence/`)
with `SHA256SUMS.txt`. A launch command is not execution evidence.

## Current measured evidence

Blender 5.1.2, headless, METRIC; two declared brick IDs in the historical 4BK pair:

- `C:/Users/artsafro/Desktop/!3D viz/!А101/63_4BK_vlad/build/blender/typ_module_v003.blend`:
  **fail**, both IDs: `Material #2`, Base Color has no link.
  SHA-256 `9dbc4658790e66d5ce5dfb2cf42636937785138a8b5ed18c93543aef923a98c5`.
- Same directory, `typ_module_v003_preview.blend`: **pass** for these two IDs only;
  `ID1_Brick_Bricks1` -> existing `inbox/Текстуры/Bricks1/Bricks1_Diffuse.png`.
  SHA-256 `b90bf7c0707c5f6b9f08932841d8f25798fdcd2eab7a49d9ec975bb3a84861d0`.
- Scope SHA-256 `9e72f4b208b447d7af0e4038b1cf59ec04250a8461600aa8e7ffb0ab13db3505`.
  Source bytes were hashed before/after each check and unchanged.

Max native synthetic scene run: **measured** in isolated 3dsmaxbatch, Max 2026.3
(28.3.0.30732), meters; MultiTile **fail** -> Bitmap **pass** -> repeated **pass**.
Fourteen additional probes cover sparse ID 7 mapping, unknown/unused/unmapped/duplicate
IDs, unsupported/missing maps, unmeasured and exactly-two-texel joints, and invalid scopes.
Receipt: `docs/evidence/1365-review-textures/native-max.json`; binaries and SHA256SUMS:
`C:/x/1365-review-textures/t_3b38fc56-native-v002/` (authorized local evidence fallback).
Run: `dcc_batch.py max --version 2026 --card t_3b38fc56 --file tmp/run-native-max-1365.py`
where the Python wrapper loads the fixture with `runpy.run_path` and calls `run(repo, evidence)`.
The parent evidence directory must exist; the fixture exclusively creates its version directory.
Viewport getter measured 1024. No global setting or user's live scene was changed.
Historical live identification (not used for the fixture): PID 969748, dirty `bukvi.max`,
386 objects. The resumed run used the card's explicit headless authorization only.

Full suite: deferred to merge batch (rule 68).
