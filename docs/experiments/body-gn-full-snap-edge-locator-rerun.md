# Experiment: Body GN TOW02: rerun the unbalanced-edge locator on the full-snap variant

Card t_c2691740 (experiment, report only, no writer change). Research report:
`docs/research/body-gn-full-snap-edge-locator-rerun.md` (t_b0dfbdf1). Blender 5.1.2 headless
(`--background --factory-startup --python-exit-code 1`), scratch copies in `C:/x/t_c2691740/` only. The live
Blender 4.4.0 session was not used.

## Question

The report found that full snap still leaves **3** unbalanced edges on the self-intersect output and that band 2's
13.7 m top still has two float32 z values (418 / 500 refs). It left the cause open. Two questions:
1. Does the report's result reproduce, and how stable and fast is it?
2. What splits band 2's top, and does removing that cause bring the self-intersect count to 0?

## Methods

- **M1: rerun of the locator** (the report's `run5.py`, unchanged; SHA-256 `0b0abb5d…44b4`), 3 runs.
- **M2: per-band top z without face->point mixing.** Hypothesis from reading the pinned tree: `Extrude Mesh` (FACES,
  not individual) gets `Offset = (0, 0, band_h)` from a **FACE** attribute. In region mode Blender averages the face
  offsets onto each vertex in float32 (sum of n values times `1/n`). The result depends on the vertex valence n, so
  `z0 + mean` can round to two float32 values. Two steps:
  - M2a (`probe6.py`): predict every top vertex z from its valence with numpy float32 (`f32(sum_n(h)) * f32(1/n)`)
    and compare with the extruded mesh.
  - M2b (`probe7.py`, `run8.py`): prototype tree. `band_h` is copied to a **POINT** attribute `band_h_pt`. Each cap
    vertex belongs to one band (0 conflicts measured). Extrude gets a constant zero offset, then
    `Set Position(Selection = Top, Offset = (0, 0, band_h_pt))`. Extruded vertices inherit the point attribute, so no
    mixing happens. `run8.py` is `run5.py` plus a monkeypatch of `P._gn_tree` (the pinned tree with this rewire) and
    of `build_cap_ids`. Everything else (weld, boolean, self-intersect, locator) is unchanged.

## Setup

```
python C:/x/t_c2691740/drive.py C:/x/t_c2691740/run5.py   run5   3   # baseline, 3 runs
python C:/x/t_c2691740/drive.py C:/x/t_c2691740/probe6.py probe6 1   # M2a
python C:/x/t_c2691740/drive.py C:/x/t_c2691740/probe7.py probe7 1   # M2b tops only
python C:/x/t_c2691740/drive.py C:/x/t_c2691740/run8.py   run8   1 (+ run8b 2)  # M2b full locator, 3 runs
```

`drive.py` calls `"C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" --background --factory-startup
--python-exit-code 1 --python <script> -- <out.json>` and times the wall clock. Inputs are read-only:
`C:/x/t_ad9bc345/{snap.py,probe.py,snapped_contours.json,in/contours.json}`. The frozen
`C:/x/t_03a8a042/run4.py` matches `FROZEN_SHA256SUMS.txt` (`ee19ad06…afafd`) and was not touched. Hashes of every
script and result are in `experiments/body-gn-full-snap-edge-locator-rerun/SHA256SUMS.txt` (hashes of the scratch files; git stores the copies with LF line endings). The scripts are copied
there. JSON and logs stay in `C:/x/t_c2691740/`.

## Results

### M1: the rerun reproduces the report byte for byte

All 3 runs exited with code 0. All 3 `run5_*.json` are byte-identical to each other (`c6d8c5e4…`) and to the report's
`C:/x/t_b0dfbdf1/run5.json`. Wall time per run: 63.6 / 64.7 / 70.9 s (median **64.7 s** for 3 variants).

### M2a: valence explains every top z (both variants, all 13 bands)

| Variant | Band 2 top z (valence -> hex) | Prediction hits (`sum * 1/n`) | Alternative (`sum / n`) |
|---|---|---|---|
| unchanged | n=1..7,10 -> `34335b41`; n=8,9 -> `33335b41` | **3,426 / 3,426** top verts | band 2: 286 / 308, band 8: 252 / 349 |
| full_snap | n=1,2,4,8,9 -> `33335b41`; n=3,5,6,7,10 -> `34335b41` | **3,426 / 3,426** | band 2: 189 / 308 |

This is the cause of the 41/877 -> 418/500 shift. Full snap moved band 2's `z0` by 1 ulp. That changed which
valences round down, so the split moved from rare valences (8, 9) to common ones (1, 2, 4). The split is a writer
artefact: the face-domain offset is averaged per vertex. It is not a property of the geometry. Bands other than 2
and 8 have the same 1-ulp mean errors, but rounding in `z0 + mean` hides them.

### M2b: point-domain offset, baseline vs prototype (Blender 5.1.2 headless)

| Metric | Baseline (pinned tree) unchanged | Prototype unchanged | Baseline full_snap | **Prototype full_snap** |
|---|---|---|---|---|
| Bands with >1 top z | 2, 8 | **none** | 2 | **none** |
| Band 2 top z (refs) | `33335b41` 41, `34335b41` 877 | `34335b41` 918 | 418 / 500 | `33335b41` 918 |
| Top z = `f32(f32(z0) + f32(h))` for every band | no (2, 8) | **yes** | no (2) | **yes** |
| Extrude: topology / max deviation | - | identical / 0.0076 mm (105 verts) | - | identical / 0.00095 mm (132 verts) |
| Boolean polys / duplicate keys | 32,053 / 9,426 | 34,797 / 11,196 | 10,498 / 0 | 10,508 / **0** |
| Boolean-output unbalanced edges | 4 | 4 | 0 | **0** |
| Weld unbalanced (T-junctions, not a criterion) | 1,430 | 1,386 | 1,460 | 1,376 |
| **Self-intersect unbalanced edges** | 7 | 4 | 3 | **0** |
| Self-intersect polys | 32,054 | 34,797 | 38,411 | 39,864 |
| Extrude eval, median of 3 (s) | 0.0083 | 0.0068 | 0.0064 | 0.0066 |
| Full locator per variant (s) | ~21.5 (64.7 / 3) | 20.1 (median of 3) | ~21.5 | 19.3 (median of 3) |

Three `run8` runs gave identical JSON apart from the timing field. With the prototype, the 4 unbalanced edges left in
"unchanged" are the parent report's 0.2 m open riser (1-face edges between `33335b41` and `34335b41`). Unchanged has
no snap, so band 3's JSON `z0` (13.7 = `33335b41`) does not meet band 2's single top (`34335b41`). The interface
mismatch remains, but the per-vertex split is gone.

Code size: the prototype adds 4 nodes (Named Attribute, Combine XYZ, Set Position, plus a constant extrude offset) and
about 10 lines in the cap builder (face -> point copy of `band_h`).

### The "full snap" here is the t_ad9bc345 probe snap, not the shipped `snap_band_z0` (#880)

Every `full_snap` number above was measured on the cached `snapped_contours.json` (SHA-256 `21bbc3e2…c7fecc532`).
That file was written by the scratch probe `C:/x/t_ad9bc345/snap.py` (SHA-256 `419f86fd…152e`, line 274), not by
any revision of `tools/methods/body/contours.py::snap_band_z0` (added later in `e6f38048`). The probe read each lower
band's top z in Blender on the **unsnapped** contours (face-domain extrude), in **one pass**, and **skipped** an upper
band when that lower top had two float32 z values. The shipped function computes `f32(f32(z0) + f32(z1 - z0))`
and walks the bands lower-first, so a snapped lower `z0` feeds the band above it.

`tools/methods/body/snap_diff.py` diffs the two sets band by band (input `C:/x/t_ad9bc345/in/contours.json`,
`92a83fc9…8e92`; report `snap_diff_tow02.json`, `6235976e…bb70`). Parent ids are the same for
all 12 snapped bands (band i -> i-1), and so are z1, polygons and vertex counts. Only `z0` differs, in 4 bands:

| Band | Parent | z1 | Vertices | Source z0 | Cached z0 (probe) | Shipped z0 | Cause |
|---|---|---|---|---|---|---|---|
| 3 | 2 | 17.1 | 338 | 13.7 | 13.7 | 13.699999809265137 | probe skipped: band 2's top had 2 float32 z (41 / 877 refs) |
| 8 | 7 | 65.4 | 349 | 30.7 | 30.69999885559082 | 30.700000762939453 | single pass: top of band 7 from its source z0 27.3; shipped uses the snapped 27.299999237060547 |
| 9 | 8 | 69.45 | 205 | 65.4 | 65.4 | 65.4000015258789 | probe skipped: band 8's top had 2 float32 z (719 / 322 refs) |
| 10 | 9 | 72.2 | 220 | 69.45 | 69.45000457763672 | 69.44999694824219 | single pass: top of band 9 from its source z0 65.4; shipped uses the snapped 65.4000015258789 |

Effect on the numbers above (Blender 5.1.2, `tests/methods/test_body_gn_point_domain.py` locator, rerun for #880):
face domain + snap gives **3** unbalanced edges on the cached file (main's test, report `cached/gn_point_domain_check.json`
`52ba5c3c…01fc`) and **6** on the shipped snap (PR #874's test at `2c4c2959`, report
`shipped/gn_point_domain_check.json` `b6e1f986…0ec2`); face domain without snap gives 7 and point domain + snap gives
**0** on both. `snap_diff.py` on the shipped snapped file (`shipped/snapped_contours.json` `8ea89d04…320f`) reports 13 / 13
bands equal. Evidence: `G:/Мой диск/AGR-evidence/880-cached-snap-diff/` with `SHA256SUMS.txt` (5 files, all OK).
So the M2b "Baseline full_snap" column (3, band 2 split 418 / 500) describes the probe snap only.
The adopted result (point-domain `band_h` + z0 snap -> 0) holds for the shipped `snap_band_z0`. The cached file
stays as frozen evidence (it is in `SHA256SUMS.txt` on Drive) and is not refreshed.

## Verdicts

| Method | Verdict | Reason |
|---|---|---|
| M1 rerun of the locator | **adopt (as a check)** | Deterministic (3/3 byte-identical, equal to t_b0dfbdf1), ~65 s for 3 variants. It is a cheap regression check for any writer change. |
| M2 point-domain `band_h` + Set Position(Top) | **adopt** | It removes the root cause of the 13.7 m split (valence-dependent float32 mean, predicted for 3,426 / 3,426 verts). With full snap it gives **0 unbalanced edges on self-intersect and boolean** (the card's target). Every band top becomes one float32 z = `z0 + h`. Moves are ≤ 0.0076 mm, topology is unchanged, runtime is the same. |

Answer to the research question: full snap's PWN result is not a lucky 13.7 m geometry. It is half a fix. The z0 snap
fixes the interfaces, and the point-domain offset fixes the per-vertex top split. With both, the self-intersect proxy
is 0.

## Proposed follow-up (adopt)

1. **Body writer: point-domain extrusion height in `tools/methods/body/body_blender.py`.** Scope: in the cap builder,
   write `band_h` (also) as a POINT attribute. In `_gn_tree`, use a zero extrude offset plus
   `Set Position(Selection = Top, Offset = (0, 0, band_h_pt))`. Test that every band top has one float32 z equal to
   `f32(z0) + f32(h)` on TOW02 (`benchmark/` fixtures), and run the locator (`run8.py` logic) for 0 self-intersect
   unbalanced edges with the z0 snap. Keep the old tree behind a flag until the TOW02 export/readback check passes.
2. **Body writer: z0 snap in the contour step** (from t_ad9bc345). Without it, "unchanged" keeps 4 unbalanced
   edges (the interface riser) even with M2. Needed together with item 1.

## Agent trace

- Card t_c2691740, profile dt-experimenter, branch `experiment/body-gn-full-snap-edge-locator-rerun`, Blender 5.1.2
  headless only (6 calls, 1.2-71 s each). No live session, no `data/` writes, frozen originals untouched.
