# Ground NPM: measure a controlled atlas FBX round-trip

Research card `t_221bc412` (no GitHub issue). Pilot evidence only; synthetic diagnostic, not a production
derivation. No production data, site job, model/data edits, live Max/Blender session, acceptance threshold or
diagonal rule is implied by anything below.

## Summary

I built one synthetic sloped Ground patch in factory-startup headless Blender (explicit triangles, two UDIM
tiles, a fixed nonzero placement origin) and exported three FBX files that differ only where intended:
a VPM-style control (2 UDIM tiles), an NPM-style copy remapped into a single atlas tile (same vertices,
triangles, placement), and a copy with the same triangle inventory shifted +0.5 m in Z. Each was read back
fresh through `tools/methods/run_variant.py --class ground-terrain` against the control as the synthetic
reference. Result: the bound readback **does** distinguish the placed-surface change (it reports
`dz_max/p95/mean = 0.5 m` on equal sample counts), and it does **not** report a false deviation for the
atlas-only UV change (`dz = 0`, equal samples) — but the atlas/UDIM distinction itself is *not surfaced* by
the ground-terrain metric: `uv_present` is a mere boolean, and the two-tile → one-tile change is invisible to
the metric row (it exists only in the raw readback's `udim_tiles`, which the metric does not report).

## Findings

**Measured (this card, ran the commands; Blender 5.1.2, hash `ec6e62d40fa9`, build 2026-05-19, at
`C:/Program Files/Blender Foundation/Blender 5.1/blender.exe`).**

1. **Fixture round-trip is clean.** Each FBX read back as 4 vertices, 2 triangles, 1 UV channel.
   `udim_tiles` distinguishes the UV change exactly as injected: control `[1001, 1002]`, atlas `[1001]`,
   shifted `[1001, 1002]`; all `uv_outside_udim_grid = False`, `mirrored_uv_triangles = 0`. World vertices
   match the input (slope `z = x/10`; shifted copy `+0.5`). This is the "distinct UDIM/atlas UV tile
   evidence": it lives in the raw readback (`tools/blender/fbx_readback.py` line 146-147, `udim_tiles`), not
   in the metric row.

2. **Both sides are hash-bound and imported for every variant.** Every `run_variant.py` row reports
   `surface_verified = True` with `surface_evidence` on both `output` and `reference` sides reading
   `readback: bound by sha256`, `extra: bound by sha256`, `index_space: extra readback vertices`,
   `triangulation: imported loop triangles with their own vertex list`. No missing/unbound evidence.

3. **Atlas-only UV change is geometrically invisible to the ground-terrain metric.** Control-vs-control and
   atlas-vs-control are indistinguishable in the metric: both give `dz_max/p95/mean = 0.0`,
   `samples_reference = 100`, `samples_both = 100`, `samples_missing = 0`, `samples_extra = 0`,
   `uv_present = True`. The metric cannot tell the 2-tile control from the 1-tile atlas copy: `uv_present`
   is `all(m["uv_channels"] >= 1)` — a presence boolean, no tile range (verified in
   `tools/methods/methods_metrics.py` lines 801-804).

4. **Vertical shift is reported as the injected offset, not parity.** Shifted-vs-control gives
   `dz_max = 0.5`, `dz_p95 = 0.5`, `dz_mean = 0.5` m on the same sample counts
   (`samples_both = 100`, `missing = 0`, `extra = 0`). Equal counts, but a nonzero `dz` — the metric reports
   the geometry change, it does not treat equal triangle/sample counts as parity.

5. **`texel` is not measured for these synthetic files** — `"reason": "no single square diffuse texture size
   in the readback"` (no textures were embedded). Reported as **not measured**, not as a result.

**Read the code (this card).** The ground-terrain `dz` figures come from XYZ geometry only
(`top_z` / `sample_grid` over the reference XY bbox, `methods_metrics.py` lines 702-751, 816-840); the
placement origin is added from the `<fbx>.placement.json` sidecar (`origin_msk77_xyz`,
`methods_metrics.py` lines 542-561, 694); sha256 binding is `_bound` (lines 581-591) and the imported-triangle
requirement is `_strict_model_triangles` (lines 594-688). `run_variant.py` copies only `uv_present` (boolean)
into the ground class metrics; it never copies `udim_tiles`, `uv_outside_udim_grid` or `mirrored_uv_triangles`
from the readback (`run_variant.py` → `methods_metrics.ground_terrain`, lines 247-254 and 787-851).

## How it applies to this repository

- `tools/methods/run_variant.py` — the bound ground-terrain readback measured here (ground class metric is the
  only thing that reports the surface deviation; it does not report UDIM tile range).
- `tools/methods/methods_metrics.py` — `ground_terrain` (line 776), `_strict_model_triangles` (594),
  `placement_offset` (542), `_bound` (581); `uv_present` boolean at lines 801-804.
- `tools/blender/fbx_readback.py` — the raw readback that *does* carry `udim_tiles` (146-147),
  `uv_outside_udim_grid` (148), `mirrored_uv_triangles` (149), `uv_channels` (100).
- `tools/methods/extra_readback_blender.py` — the second Blender import whose loop triangles + own vertex list
  make `surface_verified` possible (imported, index-space-known).
- `src/twinqa/uv.py` — `udim_of`, `sequential_tiles` already exist and are used by V008 (Ground UV tile
  sequence, `src/twinqa/scene.py` line 1959-1967) but are not wired into the ground-terrain metric row.

## Proposed next tasks

1. **Surface the UDIM/atlas tile evidence in the ground-terrain metric row.**
   Copy `udim_tiles` (and optionally `uv_outside_udim_grid`, `mirrored_uv_triangles`) from the readback into
   `ground_terrain`'s output so an atlas-only remap is visible as `udim_tiles [1001, 1002] → [1001]` instead
   of collapsing to `uv_present = True`. Small, low-risk: the fields already exist in `fbx_readback.py`; only
   the metric needs to forward them. Value S / effort S. **Advances #1969** (the NPM-atlas handoff cannot be
   verified end-to-end while the round-trip metric hides the tile change).

2. **Add a synthetic atlas-vs-UDIM regression to the methods catalog.**
   A tiny fixture like this card's (two triangles, one seam, two tiles vs one) plus a ground-terrain row that
   asserts `dz = 0` for the atlas copy and the tile list changes, so a future regression that confuses an
   atlas remap with a surface change (or vice-versa) is caught. Value M / effort S. **Advances #1969**.

3. **Decide where the NPM-atlas "assembled export" gate reads its tile evidence.**
   Once `udim_tiles` is surfaced, confirm the assembled-export check reads the metric row rather than the raw
   readback, so the single bound readback becomes the source of truth for both geometry and UV-tile facts.
   Value M / effort M. **Advances #1969**.

## Open questions for the user

1. Should the ground-terrain metric surface `udim_tiles` (and `uv_outside_udim_grid` / `mirrored_uv_triangles`)
   in its class metrics, or is UV-tile evidence expected to come from a separate V008-style check rather than
   from `run_variant.py`? (This card shows the current metric cannot distinguish the atlas-only change.)
2. For the NPM atlas handoff (#1969), is "atlas-only remap must produce `dz = 0`" the acceptance you want the
   metric to encode, or is a positive `udim_tiles == [1001]` assertion also required?
3. Is a synthetic two-triangle fixture representative enough for the NPM-atlas acceptance, or should the
   regression use a real (small) Ground slice with the actual atlas material/UV layout?

## Evidence (commands, hashes, outputs)

Blender version: `Blender 5.1.2`, build date 2026-05-19, hash `ec6e62d40fa9`.

Fixture generation (headless, factory startup):

```text
"C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" --background --factory-startup \
  --python-exit-code 1 --python C:/x/ev_t_221bc412/make_ground_patch.py
```

`make_ground_patch.py` builds a 10×10 m sloped patch (`z = x/10`), two explicit triangles, triangle 0 in UDIM
1001 and triangle 1 in UDIM 1002 (atlas copy remaps triangle 1 into `[0,1)`), placement origin
`[497123.456, 2195432.109, 128.5]` written to each `<fbx>.placement.json`.

FBX sha256 (all distinct → the atlas remap and the shift both change the bytes):

```text
09c51cf0a91c8473d7f279156334c41b0f11f12707f699ef2642a14336d60c84  ground_control.fbx (11692 B)
10a0832f269b777325288fd991732e38ec536b16a1895982cc3952e8e6cc7e47  ground_atlas.fbx   (11660 B)
313c37aaee3d1e6551dee58ff0ee4507222eaa1afa972dda112844bb78021553  ground_shifted.fbx (11692 B)
```

Measurement (three fresh same-file readbacks, one row each):

```text
uv run python tools/methods/run_variant.py C:/x/ev_t_221bc412/ground_control.fbx \
  --bench synthetic-ground-patch --class ground-terrain --variant control \
  --benchmarks C:/x/ev_t_221bc412/benchmarks.json --results C:/x/ev_t_221bc412/results.jsonl \
  --synthetic "synthetic ground patch (research t_221bc412)"
# ... same command with ground_atlas.fbx / ground_shifted.fbx (variants atlas / shifted)
```

Result table (`class_metrics.ground`, from `results.jsonl` R1-R3):

| variant | surface_verified | dz_max / p95 / mean (m) | samples ref/both/missing/extra | uv_present | output sha256 (first 12) |
|---|---|---|---|---|---|
| control | True | 0.0 / 0.0 / 0.0 | 100 / 100 / 0 / 0 | True | `09c51cf0a91c` |
| atlas   | True | 0.0 / 0.0 / 0.0 | 100 / 100 / 0 / 0 | True | `10a0832f269b` |
| shifted | True | 0.5 / 0.5 / 0.5 | 100 / 100 / 0 / 0 | True | `313c37aaee3d` |

Every row: `surface_evidence` on both `output` and `reference` sides = `readback: bound by sha256`,
`extra: bound by sha256`, `index_space: extra readback vertices`, `triangulation: imported loop triangles
with their own vertex list`, `verified_import: true`. `texel` = **not measured** (no texture size) on all rows.

Raw readback `udim_tiles` (from `tools/blender/fbx_readback.py`): control `[1001, 1002]`, atlas `[1001]`,
shifted `[1001, 1002]`.

Unusable readback: none — all three FBX files imported and read back, all rows bound by sha256.
