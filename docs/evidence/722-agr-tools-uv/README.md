# AGR Tools 0.2.0 — UV nudge and UDIM to NPM atlas

Synthetic fixtures only. The package is built from the 0.1.0 adapter plus a
generated slice of `src/dt_ai/geometry/uv_nudge.py` and a stdlib port of the
UV layout in `tools/materials/npm_atlas_udim.py`. No team-script line is in
the MZP. Binaries: `G:/Мой диск/AGR-evidence/722-agr-tools-uv/`.

## Build

Two fresh builds, SHA256
`9dbe408ea754ed2769c91eca3542191c36f2ced0f35d7147ec8cc3d9af76bbc5`.

## Headless install

Max 2024.2.5 (26.2.5.192), Python 3.10.14: native exit **0**, 39.6 s.
Listener line:

```
AGR_TOOLS_REGISTERED version=0.2.0 category=AGR Tools macros=XView,Cleanup,MatID,Open,Nudge,NudgeApply,Atlas,AtlasApply
```

Completion marker:

```
AGR_NATIVE_COMPLETE clean=3 planted=3 dry_run_unchanged=true originals_unchanged=true
```

Max 2026.3 (28.3.0.30732), Python 3.11.12: the same marker and the same
fixture assertions, 43.0 s. Wrapper status `ok`. Native exit **4294967166**
is the pre-existing `polyunwrapper_autoload.mse` CLR startup error, not a
fixture failure.

## Buttons

| Button | Planted fixture | Clean fixture | Dry-run | Source after apply |
|---|---|---|---|---|
| UV integer-tile nudge | steps `[-3, 2]`, readback UV `(0.2, 0.2)…(0.2, 0.7)` | period `none`: zero findings, UV unchanged | snapshot unchanged | snapshot unchanged |
| UDIM -> NPM atlas | tiles `[1001]`, cell Grass `[0, 0, 87, 68]`, faces 1–2 move | export copy re-preview: zero findings | snapshot unchanged | snapshot unchanged |

Cross-tile UVs raise `crosses a UDIM`. A missing material and a missing
`AGR_ATLAS_MODE` are named errors. An unmapped nudge material names `brick`.
xView thresholds stay 0.002 m / 0.005 m: the physical-distance matrix is
**120/120** in 2024 and **120/120** in 2026.

## Parity with the Python tools

| Check | Python tool | Button | max abs |
|---|---|---|---|
| Nudge steps and UV | `uv_nudge.nudge_repeating_islands` | channel-1 readback | 0 |
| Atlas tiles, cell, UV | `npm_atlas_udim.pack` on the captured mesh | export-copy UV | 1.24e-9 |

Unit probes: 40/40 nudge-slice cases agree with the library (value or the
same error); 24/24 random flat quads agree with `pack` within 1e-6.
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
Apply writes channel 1 on a new export copy only.

Still not implemented: collision generator, texel-density readout, checked export.
