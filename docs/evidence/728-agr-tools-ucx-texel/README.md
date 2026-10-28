# AGR Tools 0.3.0 — UCX collision and texel readout

Synthetic fixtures only. The package bundles a stdlib slice of
`tools/methods/ucx/ucx_variants.py` (single-hull, kernel-boxes, slice-prisms),
the stdlib UCX audit, and the texel formula from
`src/dt_ai/ops/texel_density_readout.py`. No team-script line is in the MZP.
Final binaries for this review round: `tmp/728-mzp/AGR-Tools-0.3.0-g.mzp`
and `AGR-Tools-0.3.0-h.mzp`. Headless Max cannot `fileIn` a startup script
whose path contains `Мой диск` (the written path becomes `???`); the native
run pointed `AGR_TEST_PACKAGE` at the ASCII worktree copy.

## Build

Two fresh builds after review round 1, SHA256
`1b1b7b42eb27a28f92595e35e2e33216caae9766cd07a5e5a925775fd9d5aceb`
(`AGR-Tools-0.3.0-g.mzp` and `AGR-Tools-0.3.0-h.mzp`, identical).

## Headless install

Max 2024.2.5 (26.2.5.192), Python 3.10, review round 1: wrapper status `ok`,
native exit **0**, 42.5 s. Markers:

```
AGR_REVIEW_R1 mesh=1 poly=1 plain=1 modifier=1 clipped_tris=16 stale=1 names=1
AGR_NATIVE_UCX_TEXEL clean=2 planted=2 dry_run_unchanged=true originals_unchanged=true texel_read_only=true
AGR_NATIVE_COMPLETE clean=3 planted=3 dry_run_unchanged=true originals_unchanged=true
```

xView physical-distance matrix on this run: **120/120**. Emitted-node readback:

| Case | Read / emitted world bounds (m) | Result |
|---|---|---|
| Editable Mesh, pos (20,30,40), scale (2,2,2) | (19,29,40)–(21,31,42), 12 triangles | pass, source snapshot unchanged |
| Editable Poly, same transform | same bounds, 12 triangles | pass |
| Plain Poly translate (5,6,7) | (4.5,5.5,7)–(5.5,6.5,8) | pass |
| XForm modifier +10 m | (9.5,-0.5,0)–(10.5,0.5,1) | pass |
| Clipped cube, same pos/scale | 16 triangles, bounds (20,30,40)–(22,32,42) | pass |
| Stale preview after +10 m | error `stale or altered ucx preview`, 0 nodes | pass |
| Second apply / existing `UCX_occupied_src_01` / two nodes named `same_name` | `occupied name …`, 0 new nodes | pass |

Max 2026 was not re-run on this sha. The earlier 0.3.0 package on Max 2026.3
(28.3.0.30732) finished the fixture with wrapper status `ok` and native exit
**4294967166** from the pre-existing `polyunwrapper_autoload.mse` CLR startup
error.

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
