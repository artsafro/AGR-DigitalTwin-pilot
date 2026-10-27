# AGR Tools 0.3.0 — UCX collision and texel readout

Synthetic fixtures only. The package bundles a stdlib slice of
`tools/methods/ucx/ucx_variants.py` (single-hull, kernel-boxes, slice-prisms),
the stdlib UCX audit, and the texel formula from
`src/dt_ai/ops/texel_density_readout.py`. No team-script line is in the MZP.
Final binaries: `G:/Мой диск/AGR-evidence/728-agr-tools-ucx-texel/`
(`AGR-Tools-0.3.0-c.mzp`, `AGR-Tools-0.3.0-d.mzp`). Headless Max cannot
`fileIn` a startup script whose path contains `Мой диск` (the written path
becomes `???`), so the native run used the ASCII fallback `C:/x/728/`.

## Build

Two fresh builds, SHA256
`450bd61bcae1e4fd122cbfe76512aa5c72682954d10ac321aaa430f388d0b24a`.

## Headless install

Max 2024.2.5 (26.2.5.192), Python 3.10: wrapper status `ok`, native exit **0**,
43.2 s.

Max 2026.3 (28.3.0.30732), Python 3.11: wrapper status `ok`, the same
completion markers, 42.3 s. Native exit **4294967166** is the pre-existing
`polyunwrapper_autoload.mse` CLR startup error, not a fixture failure.

Listener line, both versions:

```
AGR_TOOLS_REGISTERED version=0.3.0 category=AGR Tools macros=XView,Cleanup,MatID,Open,Nudge,NudgeApply,Atlas,AtlasApply,Ucx,UcxApply,Texel
```

```
AGR_NATIVE_UCX_TEXEL clean=2 planted=2 dry_run_unchanged=true originals_unchanged=true texel_read_only=true
AGR_NATIVE_COMPLETE clean=3 planted=3 dry_run_unchanged=true originals_unchanged=true
```

xView physical-distance matrix: **120/120** in 2024 and **120/120** in 2026.
Thresholds stay 0.002 m / 0.005 m.

## Buttons

| Button | Planted fixture | Clean fixture | Dry-run | Source after apply |
|---|---|---|---|---|
| UCX collision | L passage, kind `passage`, kernel-boxes, 2 pieces, 24 triangles | 1 m box, single-hull, 1 piece, 12 triangles, audit collision empty | object count unchanged | snapshot unchanged; new nodes `*_AGR_ucx_` and `UCX_<mesh>_01` |
| UCX unmapped kind | `part-boxes` names that kind and creates no nodes | — | — | — |
| Texel readout | UV 0–0.1, 1024 px, VPM, min 102.4 px/m, `texel_outside` | UV 0–1, min = median = 1024 px/m | no new nodes | snapshot unchanged |
| Texel unmapped material | map says `stone`, face is `brick` | error names `brick` | no scene edit | unchanged |

A missing `AGR_TEXEL_PROFILE` is an error naming the profile. `AGR_UCX_KIND`
is optional; when it is absent the kind is measured. The outside fraction
exactly at 5% is `at_threshold`. A UCX triangle count exactly equal to the
budget is a failure.

## Rollout

```
AGR Tools 0.3.0
[xView check]
[Pre-export clean-up (dry-run)]
[Apply preview to new export copies]
[MatID check]
[UV integer-tile nudge (dry-run)]
[Apply UV nudge to new export copies]
[UDIM -> NPM atlas (dry-run)]
[Apply NPM atlas to new export copies]
[UCX collision (dry-run)]
[Apply UCX to new export copies]
[Texel readout]
```

UCX names pieces `UCX_<mesh>_NN` and shows the audit verdict, including the
regulation name-mask count. Texel reads `AGR_TEXEL_PROFILE` (`NPM` or `VPM`)
and `AGR_TEXEL_MAP` (`name=pixels`).

Still not implemented: checked export.
