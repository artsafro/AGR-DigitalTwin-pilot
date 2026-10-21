# Ground v015 — retained-tongue / strict texel contract checkpoint

2026-10-21; code `d59afac5e8b6fbbebdf668c8f34e58a4641d21f3`. **Not a delivery and not review-ready.** No PR or review queue entry has been published.

## Completed construction and binding repair

- Shared binder now measures actual loop triangles while retaining polygon topology, raw material IDs and UV arrays. Tests-first `029b3d5`: RED 3 failed / 1 passed; `8839ccc`: GREEN 123 passed including real Blender 5.1.2 triangle, quad, nonplanar and concave fixtures.
- v005 texture binding and independent FBX checks genuinely completed, but the v014-to-v005 distance probe then found 10 sampled losses >10 mm, max 36.894262 mm. Those assets are diagnostic only; they must not be used as the final v009 native receipt.
- A <=2.1 mm vertex weld had erased much longer, 3 mm wide tongues. Tests-first `d840deb` pins the surface-reach loss. Retained short edges now fit the unchanged source-outline and movement bands; connected ends share a feasible translation. A 6.3 mm unconstrained construction was rejected for contour residuals; the constrained 5.9 mm version left a 1.7264974e-8 m2 uncovered wedge.
- Existing-endpoint coverage restoration is bounded strictly below 50 micrometres and preserves face/vertex inventories. The real-derived 17-vertex fixture shows why corner-only distance is insufficient: all wedge corners lie on retained boundary edges while its interior is missing. Interior witnesses repair the geometry instead of waiving a small nonzero area. Tests-first `df04b26`, `7e9f908`; combined final focused repair selection: 48 passed.

## Reproducible CPU candidate v009

```text
uv run python jobs/VATUTINO-SITE/build_ground_v015.py --adapter-json C:/x/t_d94665f2/paving_ground_inputs_v4.json --source-master C:/x/t_d94665f2/ground_v014/ground_master_vpm.json --d150-reference tmp/d150-original-surface-v001.npz --out C:/x/t_eb1c51ca/ground-v015-build-v009
```

This exact command exited 0. No cached pair hints were used: all safety proofs were recomputed. The output path must be a fresh version on a replay. No source files or numeric acceptance thresholds were changed.

| Profile | Quads | Triangles | Triangle share | Triangle-equivalent | Relief max, mm | UV px/m |
|---|---:|---:|---:|---:|---:|---|
| NPM | 18983 | 8513 | 30.960867035% | 46479 | 9.966668128 | 11.444772–30.175539 |
| VPM | 18312 | 9855 | 34.987751624% | 46479 | 9.966668128 | 589.626404–1442.109134 |

Both profiles: mixed/alternate-fan xView combinations 0; spacing under-band 0; unaccepted over-band 0; original frozen D150 samples 24/24; mirrored surface variants 0. Raw strict D129 classifications remain in report.json, as required by the separately authorized D157 whole-Ground <=35% residual exception.

Source coverage at 2.2 mm: uncovered beyond tolerance 0.0; outside beyond tolerance 0.0; off-outline edges 0; nonmanifold 0. Existing-endpoint correction: 24.388294 micrometres, 5 iterations. D169 remains the only approved ABC contour exception.

CPU fixed-fan v014<->v009 sampled distance: 6.047013 mm maximum in both directions; 0 samples above 10 mm. Source->candidate: 229747 samples; candidate->source: 229782 samples per profile. This is a diagnostic 7-point-per-triangle measurement, NOT a continuous Hausdorff certificate or an exported-file readback. The independent complete TIN-relief oracle remains the separate 9.966668 mm result above.

## Per-slot quad / residual inventory

Raw D129 reasons are retained, not silently relabelled by D157. Other residuals include semantic/UV/export-safe pairing boundaries and are covered only by the explicit whole-Ground D157 exception, not by a texel waiver.

### NPM

| Slot / fixed Max ID | v014 tris | v009 quads | v009 tris | D129 odd / pole | Other residuals |
|---|---:|---:|---:|---|---:|
| CurbGarden / 1 | 9844 | 4703 | 426 | 122 / 0 | 304 |
| FlowerBed / 2 | 134 | 48 | 38 | 8 / 0 | 30 |
| Gravel / 3 | 618 | 208 | 202 | 16 / 0 | 186 |
| LawnReinforced / 4 | 1311 | 467 | 377 | 33 / 0 | 344 |
| LawnRolled / 5 | 2088 | 668 | 752 | 132 / 0 | 620 |
| Mulch / 6 | 3263 | 1112 | 1039 | 87 / 13 | 939 |
| Pebbles / 7 | 291 | 76 | 139 | 11 / 0 | 128 |
| Skirt / 8 | 3578 | 1798 | 89 | 19 / 0 | 70 |
| Stairs / 9 | 100 | 64 | 8 | 4 / 0 | 4 |
| TileDark / 10 | 509 | 214 | 81 | 23 / 0 | 58 |
| TileLight / 11 | 21603 | 8438 | 4732 | 310 / 16 | 4406 |
| TileRed / 12 | 3004 | 1187 | 630 | 126 / 0 | 504 |

### VPM

| Slot / fixed Max ID | v014 tris | v009 quads | v009 tris | D129 odd / pole | Other residuals |
|---|---:|---:|---:|---|---:|
| CurbGarden / 1 | 9844 | 4703 | 426 | 122 / 0 | 304 |
| FlowerBed / 2 | 134 | 44 | 46 | 8 / 0 | 38 |
| Gravel / 3 | 618 | 193 | 232 | 16 / 0 | 216 |
| LawnReinforced / 4 | 1311 | 432 | 447 | 33 / 3 | 411 |
| LawnRolled / 5 | 2088 | 643 | 802 | 132 / 0 | 670 |
| Mulch / 6 | 3263 | 1049 | 1165 | 86 / 23 | 1056 |
| Pebbles / 7 | 291 | 71 | 149 | 11 / 0 | 138 |
| Skirt / 8 | 3578 | 1798 | 89 | 19 / 0 | 70 |
| Stairs / 9 | 100 | 64 | 8 | 4 / 0 | 4 |
| TileDark / 10 | 509 | 214 | 81 | 23 / 0 | 58 |
| TileLight / 11 | 21603 | 7947 | 5714 | 312 / 34 | 5368 |
| TileRed / 12 | 3004 | 1154 | 696 | 127 / 1 | 568 |

## Unresolved mandatory texel_ready contract (#346)

The unchanged shared checker `src/dt_ai/ops/inv_texel.py` is explicitly required by #371. Actual UV density passing does not make this size/shape invariant pass. Raw defaults: aspect <=8 in both profiles; NPM face side <=50.8 m; VPM hard side <=4 m, padded side (3.9375,4] m is review. No custom parameters or report-only profile were used.

| Source / candidate | NPM offending faces | VPM offending faces | VPM review faces |
|---|---:|---:|---:|
| Original v014 | 19350 | 22556 | 273 |
| CPU v009 | 8511 | 11430 | 374 |

| Slot | NPM v009 offenders | VPM v009 offenders | VPM max edge, m | VPM max aspect |
|---|---:|---:|---:|---:|
| CurbGarden | 3608 | 3658 | 5.182664 | 1305.943 |
| FlowerBed | 26 | 31 | 4.003351 | 3584.384 |
| Gravel | 79 | 163 | 5.658259 | 1341.564 |
| LawnReinforced | 120 | 378 | 5.658501 | 1356.338 |
| LawnRolled | 551 | 638 | 5.228051 | 863.174 |
| Mulch | 503 | 863 | 5.309967 | 1764.022 |
| Pebbles | 122 | 155 | 5.169788 | 662.338 |
| Skirt | 585 | 697 | 5.194241 | 333.333 |
| Stairs | 26 | 26 | 3.200009 | 34.136 |
| TileDark | 123 | 127 | 5.180925 | 620.865 |
| TileLight | 2423 | 4227 | 5.660986 | 4525.138 |
| TileRed | 345 | 467 | 5.181706 | 874.533 |

A generous D129 re-pairing feasibility probe ignores UV seams and all export-safety exclusions, but still enforces semantic slot/level and valid merged-quad geometry. It finds bad seed triangles with **no** eligible strict-texel partner:

- NPM: 14716 / 19423 bad seed triangles have no valid partner; naive longitudinal subdivision of existing quads alone adds 22284 faces. This is not a lower bound for a new remesher.
- VPM: 18641 / 22629 bad seed triangles have no valid partner; naive longitudinal subdivision of existing quads alone adds 22404 faces. This is not a lower bound for a new remesher.

The probe proves that a different greedy tie-break alone cannot satisfy #346 for the fixed paired-v014 route. It does not prove that every possible remesher is impossible. Earlier Steiner/coarsening failures and their unchanged caps are preserved in the preceding checkpoint reports; no new whole-site mesher route has been silently started.

**Decision needed:** keep strict #346 and replace the selected paired-v014 construction with a separately specified strict remeshing plan, or explicitly authorize a bounded, enumerated v015 texel exception. D157 currently relaxes residual/D129 only; it is not a texel waiver. Until this choice, all raw failures remain failures and final DCC/publication is withheld.

## DCC provenance and open acceptance

- Headless Max 2024.2.5 really measured v005 NPM import and saved-Max reopen xView 0 vertices / 0 faces, 12 bitmaps and fixed 12 material IDs. The combined pre-save/reopen job exceeded 600 seconds before finishing both profiles (exit 5); its orphaned task-owned batch child was explicitly terminated. This is partial diagnostic evidence, not a clean final native run.
- A final-file-only v002 attempt refused to start under another `review-publisher` session lock (exit 3); no foreign process or lock was altered. Prepared v003 scripts additionally check each native bitmap basename against its fixed semantic material. They have not been run on v009.
- v005 Blender independent bound-FBX checks passed raw ID/UV/geometry parity, ours xView 0/0, relief and D150. Its real oblique PNG was rendered and viewed; a lost-tongue shape failure makes it ineligible for publication.
- v009 has not been exported to FBX/Max, texture-bound, collision-audited, or inserted into pending.json. Prepared versioned export, exact readback, placement-cache and native scripts are preserved with the archive for the next worker. #298 remains on v014; no stale placement exception is copied onto a new master hash.
- Final Max/FBX xView and map/ID readback, strict texel resolution, final UCX/placement compatibility, rendered review publication and a single PR remain open. No broad `passed=true`, model acceptance, or visual approval is claimed.

## Tests

- Frozen earlier full suite on da412dc: 12863 passed / 21 skipped / 170 deselected, exit 0, 1522.21 s, through suite_slot.py.
- Binding affected selection: 123 passed, 137.35 s. Pre-tongue final focused Ground/binding selection: 562 passed / 4 deselected, 243.03 s.
- Final frozen d59afac full suite: 12877 passed, 21 skipped, 174 deselected, 91 warnings in 2069.65s (0:34:29); exit 0. Command: `python C:/Users/artsafro/hermes_kanban/scripts/suite_slot.py --slots 2 --card t_eb1c51ca -- env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider --basetemp=C:/x/t_eb1c51ca/pytest-full-v002`. Private process TEMP/TMP/TMPDIR: `C:/x/t_eb1c51ca-process-temp-v002`. The earlier da412dc receipt was superseded after the new source-reach regression; this final run used frozen source/tests through process exit. No task-owned pytest child remains.
- dt profiles check: 3 profiles OK; dt schemas --check: 12 schemas OK. Regression evals: 0 passed / 0 failed / 10 not measured, exit 2 (no Claude transcript / no PR evidence), not an eval pass.

## Durable evidence

- Base archive: `G:\Мой диск\AGR-evidence\371-ground-v015-texel-contract-20261021\checkpoint-v001.zip`; SHA256 `f604c99d9456eff7566e03a6c31626b6f92df4afdfc47ca6f66e85f11f3d2eab`; 70306692 bytes; CRC and all 89 member hashes verified.
- Verification supplement: `G:\Мой диск\AGR-evidence\371-ground-v015-texel-contract-20261021\verification-supplement-v001.zip`; SHA256 `1cb9a44d6ef88952b20bc78222400b5cd536fae86fdd423c78d393ff0d600e77`; 65238 bytes; CRC and all 15 member hashes verified.
- Adjacent `SHA256SUMS.txt` pins both. Archives are explicitly NOT_DELIVERY. No binary is committed. VPM maps remain external assets from #340 at `C:/x/vatutino-ground-textures/v003`; their source manifest is included, not an invented substitute.
- Public invariant call `uv run python tmp/texel-v015-public-status-v001.py` exited **1**, reporting `passed=false`, `gating=true` for both profiles (8511 / 11430 offenders).
- Regression eval receipt was checked with `dt evals --check-receipt`: exit 0 verifies the real 0/0/10 unmeasured report, not an eval pass.
- All 12 producer source/input snapshots still match their report hashes after the final suite.
