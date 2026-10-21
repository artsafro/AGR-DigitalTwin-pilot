# Render QA evidence — issue #440

Numerical framing only; **not aesthetic, material or delivery acceptance**.
Blender 5.1.2 `ec6e62d40fa9`, factory-startup, headless, `--python-exit-code 1`.
No PNG, BLEND or FBX is committed. Local renders: `C:/x/render-qa/t_4a2c4437-*`.

## Synthetic fixtures

Full per-frame numerical JSON: [synthetic-fixtures.json](synthetic-fixtures.json).

| Synthetic input | Expected failure codes | Actual | Checker seconds |
|---|---|---|---:|
| Cube resting on plane, good camera | none | pass | 1.6432 |
| Same, shifted camera | cropped | cropped | 0.0239 |
| Small grounded cube, below 5% coverage | empty | empty | 0.0243 |
| Cube raised 0.1 m | floating | floating | 0.0254 |
| Cube behind opaque blocker | empty | empty, zero visible faces | 0.0239 |

First frame includes renderer startup overhead. Reports contain unrounded measurements.

## Existing delivered Vatutino Ground v014

Source: `C:/x/t_d94665f2/ground_v014/npm/SM_Vatutino_Ground.fbx`, SHA-256
`94357c5f048ba3343035dfa44c9d0d89d83b3d6697dcfd9cc81c54739a6dc2ef`.
[Source inventory](vatutino-source.json): 27,281 vertices, delivered Ground only.
The producer verifies source bytes both before and after import and adds no mesh geometry.

The five camera transforms reproduce `tools/blender/ground_json_to_fbx.py:render` conventions,
not newly optimized framing. We retain their negative observations without retuning lens,
thresholds or camera distance. Preview engine Workbench, 256 × 256; PNG pixel stats are colour
coincidence diagnostics, not semantic masks. [Complete report](vatutino-v014.json).

| Camera | Actual verdict | Target coverage | Visible target faces | Background share |
|---|---|---:|---:|---:|
| top | pass | 0.332550 | 8629 | 0.637115 |
| oblique45 | cropped | 0.230347 | 7675 | 0.747894 |
| oblique135 | cropped | 0.269318 | 8198 | 0.707947 |
| oblique225 | cropped | 0.310669 | 8610 | 0.665329 |
| oblique315 | cropped | 0.276535 | 8028 | 0.700455 |

Final checker time **5.3314 s**; Blender process returns **1**, correctly preserving a failed
numerical report. Ground-resting parts are absent from this Ground-only model, explicitly
`not_applicable`, not measured grounding or whole-package pass. The real report binds the exact
preview BLEND, config and checker SHA-256 values and names every object/camera failure.

## Test receipts and probes

- RED commit `e902219`: initial public numeric-verdict test fails because checker module is absent.
  GREEN after implementation. Additional path/duplicate-key RED: 2 failed / 15 passed;
  hostile numeric-input RED: 6 failed / 31 passed; in-memory render mutation RED: stale pass;
  wholly offscreen RED: missing cropped code. Logs under this worktree's ignored `tmp/`.
- Final affected Python tests: **38 passed / 1 Blender test deselected**, 0.15 s.
- Explicit Blender test: **1 passed / 38 deselected**, 10.07 s, including fixture generator,
  fresh-process positive CLI, repeat-destination refusal and negative CLI exit **1** + failed JSON.
- Generated verdict oracle: **54/54** combinations (three crop margins × three coverages ×
  three terrain gaps × two face counts), independent literal expected failures.
- [Blender probes](blender-probes.json): **10/10** unit-scale, actual raised terrain, behind-camera,
  union-coverage, missing camera/object/terrain, empty mesh, changed in-memory geometry and
  precreated output hardlink witnesses. Unit-scale floating case correctly fails at 0.1 m.
- Path guard: existing input/output identity, hardlink, `..`, Windows case/separator and actual
  directory-junction aliases refuse publication; source bytes unchanged. Duplicate JSON keys and
  duplicate cameras/targets are rejected. Nonfinite/partial/unknown input and exact measured
  boundaries cannot yield pass. No persistent caches or predictable `.partial` files are used.
- Config rewrite during run: no pass report published. Before/after snapshots detect persistent
  changes, **not** adversarial changes restored between snapshots.
- Full suite and exact regression-eval receipt are in the PR body (run on the final implementation
  commit; no claim that unmeasured Claude telemetry passed).

Reproduction and limits: [render_qa.md](../../../tools/qa/render_qa.md).
