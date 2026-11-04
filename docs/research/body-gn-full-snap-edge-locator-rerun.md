# Body GN TOW02: unbalanced-edge locator rerun on the full-snap variant

Research card t_b0dfbdf1 (report only, no writer change). Parent: `docs/research/body-gn-pwn-branch-edges.md` (t_03a8a042, PR #840, still open, merged into this branch; this PR uses its branch `docs/research-body-gn-pwn-branch-edges` as base, per the card). Blender 5.1.2 headless, scratch copies only.

## Summary

- **Target missed.** On the exact self-intersection of the weld output, the full snap has **3** unbalanced edges, not 0. Unchanged has 7, only_8_10 has 4 (both reproduce t_03a8a042 exactly).
- **The boolean output of the full snap does have 0 unbalanced edges** (unchanged 4, only_8_10 4). The census agrees: 10,498 polys, 0 duplicate keys, against 32,053 / 9,426 and 39,988 / 14,207. So "PWN result" is real for the boolean output, but the self-intersect proxy of t_03a8a042 does not reach 0 on it.
- **Band 2's 13.7 m split did not go away.** Band 2's top still has two float32 z values: `33335b41` (13.7) and `34335b41` (13.700001). Only the vertex-ref split moved: 41 / 877 (unchanged, only_8_10) -> **418 / 500** (full snap).
- **Same place, smaller crack.** The 3 snap edges sit at the same spot as the earlier ones (x 59.84-59.87, y 403.68-403.71). The 0.2002 m open-boundary edge (1 face) and its partner (edges 1 and 2 of the parent report) are gone. All 3 left have 3 incident faces (no open boundary) and lengths 0.0366 / 1e-6 / 0.0366 m.
- **The 65.4 m split (band 8) is gone** in full snap, as in only_8_10: band 8 top is single `cdcc8242` (1,041 refs). Band 7's top is single `9a99f541` (1,050 refs).
- **Verdict.** The 13.7 m split is not "lucky geometry" that vanished; it is still there. Why the boolean output is clean while the self-intersect proxy shows 3 odd edges is **not explained** by this run (see Open questions).

## Findings

All numbers are verified in this run (`C:/x/t_b0dfbdf1/run5.json`, `run5.log`).

| Variant | Boolean polys | Duplicate keys (same/opp) | Boolean-output unbalanced | Weld unbalanced | Self-intersect polys | **Self-intersect unbalanced** |
|---|---|---|---|---|---|---|
| unchanged | 32,053 | 9,426 (1/9,425) | 4 | 1,430 | 32,054 | **7** |
| only_8_10 | 39,988 | 14,207 (0/14,207) | 4 | 1,456 | 39,990 | **4** |
| full_snap | 10,498 | **0** | **0** | 1,460 | 38,411 | **3** |

Reading: the weld output has about 1,450 unbalanced edges in every variant (T-junctions before self-intersection), so that count does not separate the variants.

### Band tops (float32 z of top-face vertex refs, `measure_tops`)

| Variant | Band 2 top | Band 7 top | Band 8 top |
|---|---|---|---|
| unchanged | `33335b41` x41, `34335b41` x877 | `9999f541` x1050 | `cdcc8242` x719, `cecc8242` x322 |
| only_8_10 | 41 / 877 (same) | `9999f541` x1050 | `cdcc8242` x1041 (single) |
| full_snap | `33335b41` x**418**, `34335b41` x**500** | `9a99f541` x1050 | `cdcc8242` x1041 (single) |

Only band 2 has two top z values in any variant besides band 8 (unchanged). Other bands are single in all three.

### Where band 2's split went (418 / 500)

The JSON rewrite of full snap moves every band's `z0` to its float32 value (bands 1, 2, 4, 6, 7, 8, 10, 11 change; 0, 3, 5, 9, 12 are bit-equal). For band 2, `z0` 10.3 -> 10.300000190734863 changes the float32 `band_h = z1 - z0`. Each band 2 top face is extruded with that one height, and the result `z0 + band_h` rounds to either `33335b41` or `34335b41` depending on the face's own float32 z0 after the earlier pipeline stage. The share landing on the lower value rose from 41 to 418 refs of 918. The split is therefore **still in band 2's top**, just balanced differently. Which faces moved was not located per face (not measured; see next tasks). The split position in space is the same crack: the 3 snap edges lie at the same (x, y) as parent edges 1-4.

### Remaining unbalanced edges on the full snap (self-intersect output)

z as float32 hex; `33335b41` = 13.699999809, `34335b41` = 13.700000763.

| # | Endpoint A | Endpoint B | Length m | Faces | Net | Incident faces |
|---|---|---|---|---|---|---|
| 1 | 59.842, 403.706, `33335b41` | 59.872, 403.685, `33335b41` | 0.0366 | 3 | -1 | vert quad 10.3->13.7, vert tri (1 ulp), down tri |
| 2 | 59.842, 403.706, `33335b41` | 59.842, 403.706, `34335b41` | 1e-6 | 3 | +1 | vert tri (1 ulp), vert 7-gon 10.3->13.700001, vert quad 13.7->13.700001 |
| 3 | 59.872, 403.685, `33335b41` | 59.842, 403.706, `34335b41` | 0.0366 | 3 | -1 | up tri, vert tri (1 ulp), vert quad 13.7->17.1 |

### Why no open riser any more (interpretation, not proven)

In the parent report the crack was a 0.2 m ring: edge 1 (1 face, open) and edge 2 (1 face) ran between the same two points one ulp apart. In the snap run, no edge has fewer than 3 faces and the 0.2 m edges are not unbalanced, so no boundary edge remains. The 1-ulp vertical triangle is still there, and with it the odd sums at its ends. Likely reason: the band 3 bottom quad and the band 2 top now share the same lower z (`33335b41`, 13.7) over more of the contour (418 vs 41 refs), so the long edges close on the same z. This was not tested per face.

### Boolean vs self-intersect (open)

The parent used the self-intersect output as the proxy for the `is_pwn` decision (`mesh_boolean.cc`, Blender v5.1.2, claimed in t_03a8a042, not refetched here). On full snap that proxy gives 3, yet the GN boolean output has 0 unbalanced edges and no twinned faces, which the parent report took as the PWN branch. Either the proxy is not what `is_pwn` sees (`mesh.intersect` goes through BMesh, which rejoins coplanar triangles and may merge faces; weld is one ulp-different from the GN input), or the three edges balance after BMesh reconstruction in a way this script does not model. The internal flag was not read.

### Reproducibility

- Script: `C:/x/t_b0dfbdf1/run5.py`, SHA-256 `0b0abb5d4d1a0a5a57ba57ef2e9b66a0ca18228e1f4be51e593074eb744044b4`. It is a copy of the frozen `C:/x/t_03a8a042/run4.py` (SHA-256 `ee19ad064356b410a4db58274a999dcd53b6c63ec5eb23c1ae4c8ec16f5afafd`, matches `FROZEN_SHA256SUMS.txt`, untouched). Differences: a `full_snap` variant loaded from `C:/x/t_ad9bc345/snapped_contours.json`, and a `measure_tops` call (from `snap.py`) per variant that adds a `tops` block to the JSON.
- Inputs (SHA-256): `snapped_contours.json` `21bbc3e2422c409ed2a24b9fbede247274340589b3837ab83172f92d7fecc532`; `in/contours.json` `92a83fc90efd039126f8b86b57ff7fae1002bea72868d7193e27b2904535152e` (unchanged after the run); `snap.py` `419f86fd8c525cce4cebe91c85aab42edb3df59c2cad38855c6a816885198e92`.
- Command (Git Bash, 64 s wall):

```
"C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" --background --factory-startup --python-exit-code 1 --python C:/x/t_b0dfbdf1/run5.py -- C:/x/t_b0dfbdf1/run5.json
```

Exit code 0; log ends "DONE"; Blender 5.1.2 (hash ec6e62d40fa9).

## How it applies to this repository

- `tools/methods/body/body_blender.py` (`_gn_tree`, cap construction): no change made. Snapping `z0` alone does not make a band's top a single float32 z; band 2 stays split. Any writer fix still has to make each band top a single float32 z, not only make interfaces coincide.
- `docs/research/body-gn-pwn-branch-edges.md`: its implication paragraph ("the JSON rewrite ... removes the 65.4 m split") is half confirmed: band 8 is single in the snap, band 2 is not. Its expectation of 0 unbalanced self-intersect edges on the snap is **not** confirmed (3).
- `docs/research/body-gn-z0-snap-attribute-probe.md`: its 418/500 figure is reproduced.
- Scratch only (not committed): `C:/x/t_b0dfbdf1/{run5.py,run5.json,run5.log,FROZEN_SHA256SUMS.txt}`.

## Proposed next tasks

1. **Body GN TOW02: per-face locator for band 2's 13.7 m top split** - extend run5.py to list which band 2 top faces land on `33335b41` vs `34335b41` in each variant (face centroid, source polygon, own float32 z0) and plot against the 3 remaining edges. Report only. Value S / effort S. Archive: no roadmap link.
2. **Body GN TOW02: test a single-z top variant** - in a scratch contours copy, set band 2's `z1` and band 3's `z0` so that float32 `z0 + band_h` is one value for all faces (or give the cap a constant top z), rerun run5.py; target 0 unbalanced edges on self-intersect and boolean. Report only. Value M / effort S. Archive: no roadmap link.
3. **Body GN TOW02: read the real `is_pwn` flag** - find out whether the 3 snap edges are real input to `is_pwn` (e.g. by evaluating the GN boolean with Blender debug output, or by reproducing the exact input mesh outside BMesh). Value M / effort M. Archive: no roadmap link.

## Open questions for the user

1. The card target was 0 unbalanced edges for the full snap on self-intersect; the measured value is 3. Should the work continue to a single-z variant (task 2), or is the boolean output's 0 unbalanced edges enough to adopt the full snap for TOW02?
2. Is there a Blender debug build, or a way to read the `pwn` flag, that you accept as the decisive check?
