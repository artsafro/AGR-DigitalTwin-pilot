# Numerical render QA (issue #440)

`render_qa.py` checks a **preview scene**, not a delivery FBX/package or aesthetic quality.
It does not replace visual/user acceptance or V001–V017. Only Blender **5.1.2** is supported.
The source scene is opened read-only in a factory-startup process with embedded scripts disabled;
it is never saved. Each invocation needs new report and render destinations.

```bash
"C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" \
  --background --factory-startup --python-exit-code 1 \
  --python tools/qa/render_qa.py -- \
  --scene C:/x/render-qa/preview.blend --config qa.json \
  --report C:/x/render-qa/run-v001.json --renders C:/x/render-qa/run-v001
```

Exit **0** means all requested numerical frame checks passed; **1** means failed QA
(report written) or invalid/unsupported input (exception, no pass report). Never interpret
an existing report as success for a later invocation. Inputs and checker bytes are SHA-256
bound in the report and rechecked before publication. External images/libraries must exist;
unpacked tiled/movie paths are rejected rather than guessed. No persistent cache is used.

## One configuration

```json
{
  "targets": ["Building", "Stair"],
  "cameras": ["top", "oblique45"],
  "ground_resting": ["Building", "Stair"],
  "ground_objects": ["Terrain"],
  "thresholds": {
    "crop_margin": 0.02,
    "minimum_coverage": 0.05,
    "floating_m": 0.01,
    "background_rgb": [0.0, 0.0, 0.0],
    "background_tolerance": 0.01
  }
}
```

Only `targets` and `cameras` are mandatory. Thresholds default centrally in `DEFAULTS`.
Unknown/duplicate keys or names, non-finite values and missing objects/cameras are errors.
Ground-resting **parts must be separate named target mesh objects**; this is an explicit
semantic role, never inferred from names or assigned to overhangs/roofs. Ground meshes are
separate from targets. If no parts are declared, the report records grounding as
`not_applicable: not declared ground-resting`, not as measured terrain contact.

## Measurements

- **BBox:** evaluated world-space mesh vertices projected into normalized camera coordinates
  `[xmin, ymin, xmax, ymax]`; `(0,0)` is bottom-left, `(1,1)` top-right. Any edge overrun
  greater than 0.02 reports `cropped`, including wholly offscreen targets. Behind-camera
  objects report `empty` (projection is not meaningful). Near/far clipping has separate failures.
- **Empty:** first opaque geometric intersections at **every output pixel centre** (no random
  sampling), including non-target occluders. Union target coverage below 0.05 or zero visible
  target polygon IDs fails. Union coverage is shared across the target set; each object also
  records its own coverage and visible original polygon count. Small objects are not individually
  required to occupy 5%, but a completely invisible requested target fails by name.
- **Ground contact:** cast down onto the explicit evaluated terrain under every vertex tied
  for the object's minimum world Z (tie tolerance 1 micrometre). Report min/max vertical gap
  and vertex count; a part floats when the minimum gap exceeds 0.01 m (no lowest vertex rests).
  Multiply Blender distances by `scene.unit_settings.scale_length`; never assume Z=0 terrain.
  Missing terrain under any such vertex is an error. Negative gaps are recorded, not a
  penetration check. Disconnected semantic parts must be split/named before this check.
- **Exact thresholds:** conservative `crop_boundary`, `coverage_boundary`, `floating_boundary`
  failures within absolute `1e-9` of a boundary (plus Python's relative `isclose` tolerance).
  These explicitly distinguish uncertainty from the spec's strict greater/less-than failures.
- **Pixels:** render PNG, read it back in Blender and count RGB pixels within the configured
  per-channel tolerance of `background_rgb` in **loaded PNG linear RGB**. This is colour
  coincidence, not target segmentation; matching target/terrain colour also counts. The share
  is diagnostic, not an additional aesthetic gate. PNG hash, dimensions and timings are recorded.

Reports have one `frames` entry per requested camera at the current scene frame number.
Every numerical failure carries `object`, `frame` (camera name) and `code`. Every target
occurs in every frame's object list; invalid/unsupported elements raise named errors.

## Supported boundary and safety

Opaque, realized mesh geometry; perspective/orthographic unscaled cameras; at most 4,194,304
output pixels. Visibility is geometric, not shader/shadow/anti-alias visibility. Transparent/
transmissive Principled materials, transparent/glass/Holdout shader nodes and shader groups are refused.
Camera-ray-invisible meshes, object holdout/shadow catchers, view-layer material overrides,
additional enabled view layers, and layer-collection exclude/hide/holdout/indirect-only masks
are rejected by name before output, for targets and non-target occluders alike. These guards
are repeated after rendering so a render-time mask change cannot publish a stale pass.
Instances, non-mesh renderables, mismatched viewport/render modifier flags, hidden-viewport
renderable meshes, collection visibility overrides, depth of field, compositor/sequencer,
render border, multiview and transparent film are refused, not silently skipped. Apply modifiers
whose viewport/render subdivision levels differ before QA; render-dependent procedural effects
are outside the opaque geometric visibility contract. Camera framing and evaluated geometry are
fingerprinted again after each render; detected in-memory changes reject stale observations.
This detects before/after differences, not hostile edits restored between snapshots.

All report/render destinations are exclusively created. Case, spelling, junction and hardlink
aliases to existing inputs are rejected without writing. PNGs render to unique private temporary
directories and are published with exclusive creation, so a precreated target hardlink is never
replaced. No predictable `.partial` file is used. A failed run can retain diagnostic PNGs but
cannot publish a pass report. Use a new versioned directory for retries; do not delete sources.

## Reproduction

```bash
uv run pytest -q tests/test_render_qa.py
uv run pytest -q tests/test_render_qa.py -m blender -p no:cacheprovider \
  --basetemp=C:/x/render-qa/unique-test-run
# Real delivered Ground FBX hash and camera setup are pinned in this producer:
blender --background --factory-startup --python-exit-code 1 \
  --python tests/fixtures/render_qa_real.py -- C:/x/render-qa/unique-real-run
# Then run the checker above on preview.blend/config.json in that directory.
```

Fixtures are explicitly synthetic. The real producer does **not** invent terrain/parts or change
the delivered geometry; it adds only the five existing Ground preview camera conventions from
`tools/blender/ground_json_to_fbx.py:render`. Evidence: `docs/evidence/render-qa/`.
