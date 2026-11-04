# Can AGR Tools atlas.npm ever pass? Fixed point of `atlas_core.pack` (#888)

Research card t_2fc054ed. Report only; no change to `adapters/`, no Max run, `test-polygon/` untouched.
Everything marked **(measured)** was run by the author with `docs/research/agr-tools-atlas-npm-fixed-point-probe.py`
(pure Python, imports `adapters/max/agr_tools/atlas_core.py` directly; output identical from the scratch copy in `C:/x/t_2fc054ed/`).

## Summary

- A PASS station **exists in `ground` mode** (measured): feed `pack` its own output and the second pack moves no UV by more than 1.4e-17 (plug materials: exactly 0). `atlas_preview` would then report no `atlas_cell` finding.
- After one pack in `oks` mode it does **not**: plug-only meshes need 3 extra passes (cell flips 34 -> 35 -> 34 px, delta 2.4e-4), textured meshes 5 extra passes (delta 4.1e-2, 2.6e-3, 1.6e-4, 1.0e-5, 6.3e-7).
- Cause of the `oks` drift (read from code): `fits(1.0)` (atlas_core.py:562) fixes the scale at 1 source-texture pixel, but packed UVs are normalised to the 2048 atlas while `_src_px` (L138-143) and `x0..x1` (L516) multiply UVs by the *original* texture `W,H` (128 px in the probe). Each pass the island shrinks by about W/size until the cell is `2*(pad+1)+1 = 19` px. `ground` is immune: its scale comes from geometric density (`_bounds` L439, `target` 35 px/m), not from texture size.
- So "pack is not idempotent" (#888) is true for `oks`, false for `ground` after one prior pack. The first pack always moves (pass-1 max delta 0.69..0.99 on every probe), which is the honest meaning of `atlas_cell`.
- Recommendation: keep `atlas_cell` as a real finding, add a `ground` PASS station built from a pack result, and treat `oks` non-convergence as a separate check/decision. Decision stays with the user.

## Findings

Setup (measured): `pack(..., size=2048, pad=8)`, materials as in `tests/max_tools/test_agr_tools_uv.py` (plug colours; textured = 128x128 gradient). Tolerance = `runtime.UV_TOL` 1e-6, strict (`assert_uv_close` treats a difference equal to `tol` as an error, runtime.py:42-43); delta = max |du|,|dv| over a face's corners. `pack` knows only `mode='ground'|'oks'` (atlas_core.py:451-452; `_atlas_settings` rejects anything else, runtime.py:1086-1088). "npm" in the card is the button name `atlas.npm`, not a pack mode; measured here as `oks`.

Notation: pass 1 = `pack(x)` vs `x`; pass n = `pack` of the previous output vs that output.

| mesh | mode | pass 1 max delta/face | passes until changed=[] | last deltas | cells (px) at the end |
|---|---|---|---|---|---|
| A one plug quad | ground | 0.796 | 2 | 0 | G 68x56 |
| A | oks | 0.790 | 4 | 2.4e-4, 2.4e-4, 0 | G 34x30 (35 in pass 2) |
| B two plugs, tiles 1001+1002 | ground | 0.796 / 1.800 | 2 | 0 / 0 | C 43x43, G 68x56, one tile 1001 |
| B | oks | 0.790 / 1.838 | 2 | 0 / 0 | C, G 34x30 |
| C one textured quad | ground | 0.746 | 2 | 1.4e-17 | T 162x121 |
| C | oks | 0.764 | 6 | 4.1e-2, 2.6e-3, 1.6e-4, 1.0e-5, 6.3e-7 | T 19x19 (from 108x82) |
| D 2 textured + 1 plug | ground | 0.746 / 0.844 / 0.696 | 2 | 0 | P 43, S 123, T 162x121 |
| D | oks | 0.764 / 0.852 / 0.688 | 6 | 6.3e-7 (faces 1,2); face 3 stops at pass 3 | P 34, S 19, T 19 |
| E plug, UV fills tile 0..1 | ground | 0.996 | 2 | 0 | G 68x56 |
| E | oks | 0.988 | 2 | 0 | G 34x34 |

(1) Idempotence: `pack(pack(x)) == pack(x)` holds in `ground` for every probe (<= 1.4e-17) and in `oks` for B and E; A, C, D converge only after 3-5 more passes. Pass-1 delta is never below 0.69, so a mesh that was not produced by `pack` cannot pass.

(2) What moves in `oks`: the cell size, not the origin. Origin = `_shelf` (L173-186, deterministic order `-dh,-dw,name`); pad = `_cell` (L146-152, `gap = pad+1`, constant). The island bbox shrinks because `x0..x1 = (u - tu) * W` (L516) uses the original texture `W` while output UVs are `x/size`. Rounding is a second, smaller effect: `_cell` uses `ceil` (L149-150), so plug cells flip 34/35 px (A, oks), delta 2.4e-4 > 1e-6. Not verified: whether the real scene, after atlas apply, rebinds faces to the 2048 atlas image (then `W` = 2048 and no shrink). The probe reuses the original material specs, so textured-`oks` numbers are the worst case for a second pack on the same material set.

(3) PASS station: yes in `ground`. Minimal: `u1, fu1 = pack(A)` outputs; `atlas_preview`'s comparison on `(A.vertices, u1, A.faces, fu1)` gives `changed = []`. B's two-tile source collapses to one tile (`[1001, 1002]` -> `[1001]`). Geometry, unit and material specs must stay the same; `ground` density (`_face_texel`) depends on vertices/`unit_m`, not on UVs, which is why it converges.

Not measured: real Max `atlas_preview` (needs Max); `ground` inputs that raise `AtlasError` (texel spread outside 10..40 px/m); meshes needing more than one shelf row.

## How it applies to this repository

- `adapters/max/agr_tools/runtime.py:1102-1140` (`atlas_preview`): `atlas_cell` means "layout differs from the pack result". It is the correct verdict for any mesh not produced by `pack`; failing every pre-atlas polygon object is consistent with it.
- `test-polygon/expected/atlas.npm.json` (per #888): "fail for every object" matches pass-1 deltas >= 0.69. A `ground` PASS object can be generated deterministically from `pack` output.
- `adapters/max/agr_tools/atlas_core.py:146-152, 516, 562`: the `oks` first-fit `k = 1.0` times texture-size-relative `src_px` is the non-idempotent part.
- `tests/max_tools/test_agr_tools_uv.py:170-179` already asserts the single-plug `ground` fixed point at 1e-9; this report extends it to textured and two-tile meshes and shows `oks` lacks it.

## Options of #888, with evidence

1. **`atlas_cell` informational (never fails)**: hides a real defect (unpacked UVs ship) and leaves the button with no check. The pass-1 deltas (0.69..0.99) are whole islands moving, not rounding noise. Not recommended alone.
2. **A pass case exists / pack fixed**: for `ground` nothing in `pack` needs fixing (fixed point after one extra pass); the polygon just lacks a PASS station. For `oks` the drift is a defect only if the post-atlas material keeps the original `W,H`; that needs one native check before `pack` is changed.

Recommendation: option 2 in two steps: (a) add a `ground` PASS station from `pack` output (no `adapters/` change); (b) separate decision on `oks` after checking what material `atlas.npm` leaves behind. Keep `atlas_cell` a failing finding.

## Proposed next tasks

1. **Polygon PASS station for atlas.npm (ground)**: one `test-polygon` object whose UVs are `pack(mesh A)` output, an expected entry with no findings, and a pure-Python test regenerating it and asserting per-face delta < 1e-6. Effort S, value M. Advances #149.
2. **`oks` convergence check on real atlas output**: rerun the probe's `oks` case with `W=H=size` (post-atlas material); if textured `oks` still drifts, fix `src_px`/`k` in `atlas_core` and add an `oks` idempotence test. Effort M, value M. Advances #149.
3. **Extend the fixed-point test in `test_agr_tools_uv.py`** to textured and two-tile `ground` meshes (probe cases B, C). Effort S, value S. Archive: no roadmap link.

## Open questions for the user

- After `atlas.npm` apply, are faces rebound to the 2048 atlas material (so a re-check sees `W=H=2048`)? Decides whether the `oks` drift is real.
- Should the polygon carry a PASS station for `ground` only, or must `oks` pass too?
- Is a layout that needs 3-5 repeated applications to stop moving acceptable for `oks`, or must one apply be final?

## Agent trace

Card t_2fc054ed, profile dt-worker-cursor, driver claude-sonnet-5-5; measurements and text produced by the driver directly (research card, no Cursor run). Sources: repository code only, no external URLs. Not measured: real Max behaviour; CI (billing lock).
