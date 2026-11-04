# Building-body GN: z0 snap through a Top-face attribute

`delivery_passed=false`. This is a report-only probe. It makes no writer or GN production change and adds no method variant. It changes no tolerance, receipt, gate or benchmark row. The contours are `synthetic_drawing: true`, so this is not a drawing-backed test of a real building. Counts here do not certify the exterior or the normals.

## Summary

This report runs the snap that `docs/research/body-gn-union-interface-mechanism.md` could not run. Each cap face gets an INT face attribute `band_id`. Extrude Mesh carries it to its `Top` faces, so the float32 top z of each band can be read without the vertex-index layout rule that blocked the earlier probe.

- **Baseline reproduced exactly.** Weld has 0 duplicate keys. The boolean has **9,426** (1 same, 9,425 opposite). After merge, dissolve and triangulate there are 14,942 triangle extras: 14,145 from duplicate n-gon pairs and **797** from non-duplicate n-gons.
- **The snap.** It covered 10 of the 12 interfaces. Interfaces 13.7 m and 65.4 m were skipped because the lower top has two float32 z values. After the snap, the one exact UNION gives **0** duplicate keys, 0 coordinate extras and 0 horizontal extras. Polygons drop from 32,053 to 10,498. After triangulate, 7 extras remain, all from non-duplicate n-gons (area 29.948): 1 at 10.3 m, 1 at 13.7 m and 5 at 17.1 m.
- **The cause is not "the planes now coincide".** Only 2 of the 10 snaps changed a float32 `z0` (band 8 at 30.7 m, band 10 at 69.45 m). Applying only those two makes things **worse**: 12,558 (band 8 only), 11,066 (band 10 only) or 14,207 (both) duplicate keys. Each interface that becomes exactly coincident gains twins of its own: 1,389 at 30.7 m and 1,641 at 69.45 m.
- **What the full snap also changed.** Rewriting JSON `z0` as the float64 of its float32 value changes the float32 band height of 7 bands. That moves band 7's top one ulp, so 30.7 m is split again but the other way round. It also redistributes band 2's split top at 13.7 m and removes band 8's split top at 65.4 m.
- **Mechanism (consistent, not proven).** Blender 5.1.2 exact boolean checks once, globally, whether the self-intersected mesh is PWN (piecewise constant winding number). If any edge has a non-zero orientation sum, it uses the raycast path for the whole mesh. On the full snap, Hole Tolerant gives a bitwise-identical output (it has no effect on the cell path). On the baseline it changed the output (32,053 → 32,055 polys, earlier report). Edge balance on the boolean output: 0 unbalanced edges on the full snap, 4 to 8 on every variant with twins.
- **Verdict: consistent but unisolated.** The z0 snap as specified removes all cycle-key twins on this input. The isolation shows that coincidence alone adds twins. The zero result follows a global solver path switch, and a single ulp elsewhere in the building can flip it. This is not a repair recipe.

## Findings

Labels: **verified** means run here or source code read here. **Source claims** means taken from a cited report or URL and not re-derived.

### Sources and versions (verified)

| Item | Value |
|---|---|
| Blender | 5.1.2, build `ec6e62d40fa9` (built 2026-05-19), `--background --factory-startup --python-exit-code 1`. Build hash equals `gh api repos/blender/blender/commits/v5.1.2` → `ec6e62d40fa9e9d1…` |
| Contours | `92a83fc90efd039126f8b86b57ff7fae1002bea72868d7193e27b2904535152e`, 13 bands, `synthetic_drawing: true`; same hash after every run |
| Snapped contours | `21bbc3e2422c409ed2a24b9fbede247274340589b3837ab83172f92d7fecc532` |
| Tree | pinned `_gn_tree` copied unchanged from `probe.py` `5b95306263979cd7a252fab02248a16cbe8e87d7252c37c3adc3c181928ab0b7` (#747 report; writer `24c94691:tools/methods/body/body_blender.py` lines 72–106) |
| Census | `census.py` `61bdfae6…`, `detail.py` `f9d6cb35…`, identical to the #746 evidence |
| Scripts (hashed before running) | `snap.py` `419f86fd8c525cce4cebe91c85aab42edb3df59c2cad38855c6a816885198e92`, `isolate.py` `770ae7ca3c72f3952f4142fc55a5669648e45079ba5e77671dbea95d32e36e0b`, `run3.py` (in `FROZEN_SHA256SUMS.txt`) |
| Exact-boolean source read | `https://raw.githubusercontent.com/blender/blender/v5.1.2/source/blender/blenlib/intern/mesh_boolean.cc`, SHA-256 `bef839d4…0711b`, `is_pwn` at line 1352, path switch at lines 3584–3600 |
| Evidence | `G:/Мой диск/AGR-evidence/t_ad9bc345-body-gn-z0-snap/` with 17 files, all OK under `SHA256SUMS.txt` (`run1.json` `58338b7f…`, `run2.json` `dcd9abe5…`, `run3.json` `2ab247da…`) |

### Measurement method (verified)

- `build_cap_ids` is `probe.build_cap` plus `band_id` (INT, FACE), filled in the same face order as `band_h`.
- The measurement tree is the pinned Extrude Mesh (`FACES`, Individual false, offset `(0,0,band_h)`) → Store Named Attribute `is_top` (BOOLEAN, FACE, value = Extrude `Top`).
- Control on a unit quad (`band_h=2`, `band_id=7`): 5 faces, 1 top face with `band_id` 7, side faces also 7, top z hex `00000040` (= 2.0).
- On the building, the measurement tree output equals the pinned extrude tap bitwise (coordinates and polygons), for both the unchanged and the snapped contours. Storing the attribute does not perturb the geometry.
- Snap rule: for each upper band whose JSON `z0` equals exactly one lower band's `z1`, if that lower band's Top faces carry a single float32 z, set upper `z0 :=` that value (written to JSON as float64), so `band_h = z1 − z0`. The rule is one-shot from the unchanged measurement. Otherwise skip.

### Top z per band, unchanged contours (verified)

Bands 0, 1, 3–7 and 9–12 each have one top z, and it equals `float32(z0) + float32(z1−z0)`. Two bands do not (skipped):

| Lower band | Nominal top | float32 top z (vertex refs) | Non-flat Top faces | Interface skipped |
|---|---|---|---|---|
| 2 | 13.7 | `33335b41` 13.699999809 (41), `34335b41` 13.700000763 (877) | 39 | upper band 3 |
| 8 | 65.4 | `cdcc8242` 65.400001526 (719), `cecc8242` 65.400009155 (322) | 206 | upper band 9 |

Inside one non-individual extrusion, some Top vertices land one ulp away from the others. This report does not say why (for example, averaging the offsets of neighbouring faces). It only records the split.

### Snap applied (verified)

| Upper band | Old z0 → new z0 (float32 hex) | float32 z0 changed | Residual before (ulp) |
|---|---|---|---|
| 1 / 2 / 4 / 5 / 6 / 7 / 11 / 12 | same hex | no (JSON float64 changed for 1, 2, 4, 6, 7, 11) | 0 |
| 8 (30.7) | `9a99f541` → `9999f541` | **yes** | +1 |
| 10 (69.45) | `66e68a42` → `67e68a42` | **yes** | −1 |

The JSON rewrite alone changes float32 `band_h` on bands 1, 2, 4, 6, 7, 10 and 11, for example band 7 `9a995940` → `9d995940`. In the snapped run that moves band 7's top to `9a99f541`, so 30.7 m stays split, now in reverse. It also changes band 2's top split to 418/500 vertex refs. Band 8's top becomes single at `cdcc8242`.

### Counts before and after (verified)

| Variant | Boolean polys | Duplicate keys (same/opp) | Coord extras | Horizontal extras area | Post-triangulate extras (dup-ngon / non-dup) | Triangles | Boolean output unbalanced edges |
|---|---|---|---|---|---|---|---|
| #746/#747 baseline (source claims) | 32,053 | 9,426 (1/9,425) | 9,356 | 3,782.442 | 14,942 (14,145 / 797) | 54,388 | — |
| unchanged, this run | 32,053 | **9,426 (1/9,425)** | 9,356 | 3,782.442 | 14,942 (14,145 / **797**) | 54,388 | 4 |
| **snap, 10 interfaces** | **10,498** | **0** | 0 | 0 | **7 (0 / 7)** | 16,554 | 0 |
| snap + Hole Tolerant | 10,498, bitwise identical to snap | 0 | 0 | — | — | — | — |
| only band 8 z0 (30.7) | 37,552 | 12,558 (0/12,558) | 12,477 | 4,817.807 | 19,758 (19,151 / 607) | 65,463 | 4 |
| only band 10 z0 (69.45) | 34,480 | 11,066 (0/11,066) | 10,993 | 4,404.852 | 16,747 (16,194 / 553) | 58,423 | 8 |
| bands 8 + 10 z0 | 39,988 | 14,207 (0/14,207) | 14,123 | 5,438.871 | 21,542 (21,206 / 336) | 69,485 | 4 |

In every row, weld duplicate keys are 0, with 1 coordinate extra (the known 10.3 m pair).

### Shared-plane interface faces (boolean output, faces whose vertices share one float32 z; verified)

| z | unchanged faces | unchanged horiz. extras | snap faces | snap extras | only 8 extras | only 10 extras |
|---|---|---|---|---|---|---|
| 6.9 | 2,373 | 882 | 609 | 0 | 882 | 882 |
| 10.3 | 2,786 | 1,105 | 568 | 0 | 1,105 | 1,105 |
| 13.7 | 754 + 413 (split) | 0 | 521 + 59 (split) | 0 | 0 | 0 |
| 17.1 | 3,387 | 1,345 | 693 | 0 | 1,310 | 1,345 |
| 20.5 | 3,513 | 1,431 | 651 | 0 | 1,431 | 1,431 |
| 23.9 | 3,500 | 1,413 | 674 | 0 | 1,413 | 1,413 |
| 27.3 | 3,704 | 1,502 | 696 | 0 | 1,502 | 1,502 |
| 30.7 | 347 + 345 (split) | 0 | 522 + 201 (split, reversed) | 0 | **1,389** (single plane) | 0 |
| 65.4 | 2,606 + 117 (split) | 806 | 651 (single) | 0 | 2,584 (single) | 806 |
| 69.45 | 501 + 420 (split) | 0 | 463 (single) | 0 | 0 | **1,641** (single plane) |
| 72.2 | 1,941 | 792 | 357 | 0 | 792 | 792 |
| 76.25 | 335 | 147 | 41 | 0 | 147 | 147 |

In the snap, 6.9 m has 609 faces. That is the same as the isolated 6.9 m pair in the earlier report, which had 0 extras. The interfaces whose geometry the snap did not touch (6.9, 10.3, 20.5 …) still lose all their twins. The effect is global, not local to the snapped planes.

### Why a global switch fits (verified by source reading, not by an internal flag)

In `mesh_boolean.cc` v5.1.2, `boolean_trimesh` computes `pwn = is_pwn(tm_si, tm_si_topo)` once on the whole self-intersected triangle mesh. `is_pwn` is false if any edge's orientation sum over its triangles is non-zero. If `!pwn`, the whole boolean uses `raycast_patches_boolean` (or `raycast_tris_boolean` when Hole Tolerant is on). Otherwise it uses `find_cells` and winding-number classification. URL: https://raw.githubusercontent.com/blender/blender/v5.1.2/source/blender/blenlib/intern/mesh_boolean.cc (lines 1352–1397, 3584–3600).

Two observations fit that switch. First, on the snap, Hole Tolerant leaves the output bitwise unchanged, as expected on the PWN branch. On the baseline it changed 2 polygons (earlier report), as expected on the raycast branch. Second, the boolean output edge balance is 0 on the snap and 4 to 8 on every twinned variant. The internal `pwn` flag was not read: no debug build, and `dbg_level` is a compile-time 0. So the mechanism is **consistent, not proven**. Edge balance on the weld output (1,418–1,516 unbalanced edges in every variant, from T-junctions before self-intersection) does not predict the branch.

## How it applies to this repository

- `tools/methods/body/body_blender.py` (`_gn_tree`, cap construction): the writer's twins depend on whether Blender's exact union takes its PWN branch for the whole building. Snapping `z0` is not a local fix. Making one interface exactly coincident adds twins there while the solver stays non-PWN. No change was made to that file.
- `docs/domain/areas/body.md` BODY-J (duplicate ceiling), BODY-N (triangulated readback), BODY-I and BODY-S (exterior ledges): the snapped run's 0 keys says nothing about which interface faces are exterior. Polygons fall to a third, so a BODY-S check on the ledges would be needed before any count is trusted.
- `docs/research/body-gn-union-interface-mechanism.md`: its open question, "the snap probe did not run", is answered here. Its "float32 gap observed, not isolated" now reads as follows: a gap removes twins locally on the raycast branch, and the snap removes them globally by a branch change.
- The scratch copy is `C:/x/t_ad9bc345/`. Evidence is on Drive (above). Nothing large is in git.

## Proposed next tasks

1. **Read the PWN branch directly for TOW02 variants.** Scope: report-only. Find the edges that make the self-intersected mesh non-PWN on the unchanged and the only_8_10 contours, without a debug build. Two ways: self-intersect a copy in Python (for example `bpy.ops.mesh.intersect` with the exact solver) and apply the `is_pwn` rule to its triangles, or take the boolean output and list the 4 to 8 unbalanced edges with their z and band. Report where the non-PWN edges sit: the 13.7 m in-band split, the 65.4 m in-band split, or elsewhere. No writer change. Value: it turns "consistent" into an identified cause and shows whether the in-band top splits (non-flat Top faces) are what blocks the PWN branch. Effort **S**. Archive: no roadmap link (#727 is closed; no open roadmap issue covers the GN body variant).
2. **Keep the writer change unscheduled.** Scope: no repair, snap, or new GN variant until the user has decided the #746 choices (repair versus new variant, exterior-ledge winding, overlap-area diagnostics, receipt semantics). The user should also see that a z0 snap can raise the twin count. Value: it prevents a fragile global-branch result from becoming a production edit. Effort **S**. Archive: no roadmap link.

## Open questions for the user

- The full snap gives 0 twins, but it does so by a global solver switch that one ulp elsewhere can undo. Snapping only the two bands whose float32 z0 changes adds 4,781 twins (9,426 → 14,207). Should the GN body line keep investigating (task 1), or be parked in favour of the kernel route (#753)?
- If a later repair targets the PWN branch, triangles drop to 16,554 from 54,388. Do you want BODY-S ledge exterior checked before any such count is reported?
- The 7 remaining post-triangulate extras (non-duplicate n-gons at 10.3, 13.7 and 17.1 m, area 29.948 m²) are coplanar overlaps. Should those be measured by area rather than keys, as #746 asked?

## Reproduction

```text
# hashes frozen before each run: C:/x/t_ad9bc345/FROZEN_SHA256SUMS.txt
B="C:/Program Files/Blender Foundation/Blender 5.1/blender.exe"
"$B" --background --factory-startup --python-exit-code 1 --python C:/x/t_ad9bc345/snap.py    -- C:/x/t_ad9bc345/run1.json   # ~50 s
"$B" --background --factory-startup --python-exit-code 1 --python C:/x/t_ad9bc345/isolate.py -- C:/x/t_ad9bc345/run2.json   # only_8 / only_10 / only_8_10
"$B" --background --factory-startup --python-exit-code 1 --python C:/x/t_ad9bc345/run3.py    -- C:/x/t_ad9bc345/run3.json   # edge balance, snap + Hole Tolerant
python C:/x/t_ad9bc345/summarize.py; python C:/x/t_ad9bc345/summarize2.py
```

Evaluations use mesh copies (`copy` → `evaluated_get` → `to_mesh` → `to_mesh_clear`), with no `validate` or `update`. The post-triangulate path is the same as the #747 `instrument2.py`: full tree including the 0.001 merge → `bm.from_mesh` → `dissolve_limit(0.0017)` → triangulate, with per-face source provenance. Openings schedule is empty. Policy note: the card policy says not to run DCC applications, while the card body asks for this probe to run in Blender. Blender was run headless on a scratch copy only, the same way as the earlier report. The open GUI session was not touched.
