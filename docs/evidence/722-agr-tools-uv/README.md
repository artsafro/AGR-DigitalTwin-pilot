# AGR Tools 0.2.0 — UV nudge and UDIM to NPM atlas

Synthetic fixtures only. The package is built from the 0.1.0 adapter plus a
generated slice of `src/dt_ai/geometry/uv_nudge.py` and a stdlib port of the
UV layout in `tools/materials/npm_atlas_udim.py`. No team-script line is in
the MZP. Binaries: `G:/Мой диск/AGR-evidence/722-agr-tools-uv/`.

## Build

Two fresh builds, SHA256
`acf2cdab7ae6d5b08bb87c528617be0a39abf1acb6cd0763f6d67edc466569eb`.

## Headless install

Max 2024.2.5 (26.2.5.192), Python 3.10.14: native exit **0**, 41.0 s.
Listener line:

```
AGR_TOOLS_REGISTERED version=0.2.0 category=AGR Tools macros=XView,Cleanup,MatID,Open,Nudge,NudgeApply,Atlas,AtlasApply
```

Completion marker:

```
AGR_NATIVE_COMPLETE clean=3 planted=3 dry_run_unchanged=true originals_unchanged=true
```

Max 2026.3 (28.3.0.30732), Python 3.11.12: the same marker and the same
fixture assertions, including the 8×8 corner `(140, 210, 40)` and the atlas
samples `(255, 0, 0)` / `(8, 0, 247)`, 41.1 s. Wrapper status `ok`. Native
exit **4294967166** is the pre-existing `polyunwrapper_autoload.mse` CLR
startup error, not a fixture failure. OCIO is left on; atlas PNGs are saved
with `outputColorConversion:#noConversion`.

## Buttons

| Button | Planted fixture | Clean fixture | Dry-run | Source after apply |
|---|---|---|---|---|
| UV integer-tile nudge | steps `[-3, 2]`, readback UV `(0.2, 0.2)…(0.2, 0.7)` | period `none`: zero findings, UV unchanged | snapshot unchanged | snapshot unchanged |
| UDIM -> NPM atlas | tiles `[1001]`, cell Grass `[0, 0, 87, 68]`, faces 1–2 move | export copy re-preview: zero findings | snapshot unchanged | snapshot unchanged |
| Textured atlas | 8×1 red/blue, cell `[0, 0, 24, 19]`, U `0.00439453125..0.00712890644`; atlas pixel blue `(8, 0, 247)` | flat Kd Grass stays a colour plug | dry-run UV unchanged | source bitmap stays 8×1 |
| Diffuse alpha | white 8×1, alpha `[0,0,0,0,255,255,255,255]`, cell `[0, 0, 24, 19]`, opacity samples `0` and `247` | dropping alpha is the plug cell `[0, 0, 40, 20]` | dry-run unchanged | source alpha `0` and `255` stay |
| Opacity without diffuse | `map_d without map_Kd is not supported` | no export copy created | no bitmap read required | source object count unchanged |

Cross-tile UVs raise `crosses a UDIM`. A missing material and a missing
`AGR_ATLAS_MODE` are named errors. An unmapped nudge material names `brick`.
xView thresholds stay 0.002 m / 0.005 m: the physical-distance matrix is
**120/120** in 2024 and **120/120** in 2026.

## Parity with the Python tools

| Check | Python tool | Button | max abs |
|---|---|---|---|
| Nudge steps and UV | `uv_nudge.nudge_repeating_islands` | channel-1 readback | 0 |
| Atlas tiles, cell, UV | `npm_atlas_udim.pack` on the captured mesh | export-copy UV | 1.24e-9 |
| Textured 8×1 red/blue cell and UV | `npm_atlas_udim.pack` | export-copy UV and atlas pixel | UV < 1e-6; pixel `(255,0,0)` / `(8,0,247)` |
| White bitmap with varying alpha | same packer, texture cell `[0,0,24,19]` | opacity bitmap samples | UV < 1e-6; alpha `0` and `247` |
| Random bitmap size and alpha | `pack` cells and UV | stdlib atlas | 12/12 within 1e-6; pixels within 1 level |
| Grey `map_d` plus `map_Kd` | `pack` cells, UV, image | stdlib atlas | 8/8 |
| `map_d` without `map_Kd` | `AtlasError` of that name | same error, no copy | match |

Unit probes: 40/40 nudge-slice cases agree with the library (value or the
same error); 24/24 random flat quads agree with `pack` within 1e-6.
12/12 random bitmap sizes and alphas and 8/8 opacity maps agree on layout
within 1e-6. 32/32 scanline reads rebuild the image; one `width*height`
span does not.
An output path that resolves to an input writes nothing. A UV difference of
exactly 1e-6 is an error.

## Rollout

```
AGR Tools 0.2.0
[xView check]
[Pre-export clean-up (dry-run)]
[Apply preview to new export copies]
[MatID check]
[UV integer-tile nudge (dry-run)]
[Apply UV nudge to new export copies]
[UDIM -> NPM atlas (dry-run)]
[Apply NPM atlas to new export copies]
```

Nudge reads `AGR_UV_PERIODS` (`name=pu,pv` or `name=none`). Atlas reads
`AGR_ATLAS_MODE` (`ground` or `oks`) and `AGR_ATLAS_SIZE` (`1024` or `2048`).
Apply writes channel 1 on a new export copy. A diffuse bitmap is also
replaced on that copy by a new gamma-1 PNG of the atlas (and a separate
opacity PNG when the packer emits one). Flat Kd colours are not rewritten.
`map_d` without `map_Kd` is rejected before a copy exists.

Still not implemented: collision generator, texel-density readout, checked export.
