# UCX fit: distance stride, one outside outlier, and inside zeros

Status: research (report only). `delivery_passed=false`. No metric, budget, tolerance, or gate is adopted.

Declared main SHA `1a417376af6be46872ba1c6a7aa4bfcf32c33cec` (task statement). Git was not run, so this note does not re-resolve the worktree HEAD. Source bytes executed: `tools/methods/methods_metrics.py` sha256 `5336efb18bac3644ef127d7a99b20aea36c33ce895d0cf27e05910bbf67253ef` (unchanged after the probe). NumPy 2.5.3. Scratch: `C:/x/t_2d7a4372/probe_ucx_distance_stride.py` and `probe_ucx_distance_stride.json`.

## Summary

`ucx_fit` sets `distance_stride` from outside-point count times welded UCX triangles over `FIT_MAX_PAIRS` (400,000,000). It then keeps every inside sample at distance 0 and every stride-th outside sample in sample-array order. On a frozen unit-box population of 9 inside zeros and 8 outside distances (0.0625, 0.125, 0.25, 0.375, 0.5, 0.75, 2, and an isolated 5 m outlier), an in-memory copy whose only change was a lower `FIT_MAX_PAIRS` forced stride 2 (`FIT_MAX_PAIRS` 72) and stride 3 (40). With the outlier at outside index 7, `model_to_ucx_max_m` fell from 5.0 to 2.0 at both strides; `samples` stayed 17 while `measured_samples` fell to 13 and 12. Keeping all 9 zeros moved p95 from the outside-only retained values 1.775 and 1.8375 to 1.1 and 1.1062, and cut every `share_over_m`. Putting that same outlier on outside index 0 left the max at 5.0, so the drop follows the index rule. These orders are injected samples. Production `_samples` is a different order. All 18 committed `ucx-collisions` rows record `distance_stride` 1. Stride greater than 1 on a catalog row is exposure unproven.

## Findings

### F1 — what the reducer does (read)

`tools/methods/methods_metrics.py`:

- `FIT_MAX_PAIRS = 400_000_000` at line 27. `FIT_MAX_POINTS = 60_000` at line 26 is a separate surface-sample cap (`sample_stride`), not `distance_stride`.
- `DEVIATION_STEPS_M = (0.10, 0.30, 1.00)` at line 30. Shares use `d > x` (line 368).
- `_inside_any` at lines 249–256: a point is inside a piece when it lies in that piece’s AABB (tol 1e-6) and on the inner side of every plane.
- `point_triangle_distance` at lines 259–282 is the outside distance.
- `_samples` at lines 285–293: `np.unique(np.round(sample_surface(...), 4), axis=0)`, which sorts lexicographically, then a coarser spacing, then `pts[::stride]` only if the set still exceeds `FIT_MAX_POINTS`.
- `ucx_fit` at lines 318–375. The distance reducer is lines 328–341 and the published reduction is lines 366–368:

```python
dstride = max(1, math.ceil(len(out_pts) * len(tri) / FIT_MAX_PAIRS))
sel = np.nonzero(~inside)[0][::dstride]
measured[inside] = True
measured[sel] = True
dist[sel] = best
d = dist[measured]
```

`model_to_ucx_max_m` is `round(float(d.max()), 4)`. `model_to_ucx_p95_m` is `round(float(np.percentile(d, 95)), 4)`. Each share is `round(float((d > x).mean()), 5)`. Inside samples are all in `d`, at 0. Outside samples enter `d` only at ranks `0, dstride, 2*dstride, ...` in the order of `np.nonzero(~inside)`.

The docstring (lines 318–320) and `docs/methods/README.md` lines 68–71 say the shares are measurements. They are not an R11–R13 verdict. [D134] (`docs/decisions.md`, `docs/domain/areas/ucx.md` lines 37–40) makes the limits one-sided, model surface to UCX. The area file marks R11–R13 L2 coverage `none` (lines 43–48). This function is the methods-catalog measurement, not that gate.

### F2 — callers and tests (read)

| Site | Role |
|---|---|
| `tools/methods/run_variant.py:241-242` | Only production caller. Class `ucx-collisions` stores the dict on `class_metrics.ucx_fit`. |
| `tools/methods/results_md.py:76-99` | Prints max, p95, UCX-outside share, and envelope-uncovered share. It does not print `distance_stride`, `samples`, or `measured_samples`. |
| `tests/methods/test_methods_catalog.py:119-141` `test_row_covers_every_metric_field` | Asserts max `0.0` and a volume. Does not read `distance_stride`. |
| `tests/methods/test_methods_catalog.py:264-271` `test_ucx_fit_reports_uncovered_model_part` | Partial cover max about 0.5 m; loose box max `0.0`. |
| `tests/methods/test_methods_catalog.py:338-342` `test_ucx_without_hull_is_an_error_not_a_fit` | Missing hull raises `MetricError`. |
| `tests/methods/test_methods_catalog.py:638-661` `test_end_to_end_tiny_fbx_in_blender` | Opt-in Blender test, max `< 0.01`. Not run here. |

No test assigns `FIT_MAX_PAIRS` or asserts `distance_stride`. Pytest was not run.

### F3 — committed rows (read)

`docs/methods/ucx-collisions/results.jsonl` has 18 `ucx_fit` objects (R1–R18). The other `docs/methods/**/results.jsonl` files contributed none. Sixteen `benchmark/**/*.json` and `*.jsonl` files contain neither `ucx_fit` nor `distance_stride`.

Every UCX row records `distance_stride` 1, `sample_stride` 1, and `samples == measured_samples`. Rows with stride greater than 1: none. Exposure of stride greater than 1 on a catalog row is unproven.

Stored `samples * triangles.ucx` is an upper bound on the pair count in the formula (outside points are at most `samples`; weld only drops triangles). The largest product is R12 `tow02` / `slice-prisms`: 44,343 × 7,056 = 312,884,208, which is under 400,000,000, so the formula yields stride 1. That matches the stored field. The FBX files were not remeasured.

| Row | Object | Variant | samples | measured | distance_stride | UCX tris | samples × UCX tris | max m |
|---|---|---|---:|---:|---:|---:|---:|---:|
| R1 | kpp1 | kernel-boxes | 39374 | 39374 | 1 | 4128 | 162535872 | 0.01 |
| R2 | kpp1 | slice-prisms | 39374 | 39374 | 1 | 488 | 19214512 | 0.0015 |
| R3 | kpp1 | part-boxes | 39374 | 39374 | 1 | 12 | 472488 | 0.0 |
| R4 | kpp1 | part-hulls | 39374 | 39374 | 1 | 12 | 472488 | 0.0 |
| R5 | kpp1 | single-hull | 39374 | 39374 | 1 | 12 | 472488 | 0.0 |
| R6 | ac08 | kernel-boxes | 10962 | 10962 | 1 | 84 | 920808 | 0.0035 |
| R7 | ac08 | slice-prisms | 10962 | 10962 | 1 | 44 | 482328 | 0.0015 |
| R8 | ac08 | part-boxes | 10962 | 10962 | 1 | 12 | 131544 | 0.0 |
| R9 | ac08 | part-hulls | 10962 | 10962 | 1 | 12 | 131544 | 0.0 |
| R10 | ac08 | single-hull | 10962 | 10962 | 1 | 12 | 131544 | 0.0 |
| R11 | tow02 | kernel-boxes | 44343 | 44343 | 1 | 3456 | 153249408 | 0.0035 |
| R12 | tow02 | slice-prisms | 44343 | 44343 | 1 | 7056 | 312884208 | 0.5836 |
| R13 | tow02 | part-boxes | 44343 | 44343 | 1 | 12 | 532116 | 0.0 |
| R14 | tow02 | part-hulls | 44343 | 44343 | 1 | 12 | 532116 | 0.0 |
| R15 | tow02 | single-hull | 44343 | 44343 | 1 | 12 | 532116 | 0.0 |
| R16 | kpp1 | slice-prisms | 39374 | 39374 | 1 | 452 | 17797048 | 0.0082 |
| R17 | ac08 | slice-prisms | 10962 | 10962 | 1 | 24 | 263088 | 0.0015 |
| R18 | tow02 | slice-prisms | 44343 | 44343 | 1 | 4832 | 214265376 | 0.0099 |

### F4 — frozen population and analytic distances (verified-by-run)

Synthetic unit box `[0, 1]^3` for both the model mesh and `UCX_SM_Test_Main_001` (12 triangles after weld). Voxel work stayed on that box: `voxel_m` 0.25, `ucx_volume_m3` 1.0, `model_envelope_m3` 2.047 on every run. Those three fields did not change with the injected distance samples.

Distance samples were injected by replacing `_samples` in memory. `_inside_any`, the selection expression, and `point_triangle_distance` were the functions from each loaded module. `sample_spacing_m` 0.0 and `sample_stride` 1 in the tables below are the values the injection returned. They are not a `sample_surface` measurement.

Nine inside points, analytic distance 0: the 0.25 / 0.75 corners of the open cube plus `(0.5, 0.5, 0.5)`. Eight outside points on the ray `y=0.25`, `z=0.5`, `x=1+distance`, so the closest point is the interior of one +X triangle (off the face diagonal `z=y`). Distances are binary64-exact and straddle 0.10, 0.30, and 1.00. The 5 m point is the single largest.

| Sample i | xyz | Analytic m | Outside rank |
|---:|---|---:|---:|
| 0–8 | inside lattice above | 0 | — |
| 9 | (1.0625, 0.25, 0.5) | 0.0625 | 0 |
| 10 | (1.125, 0.25, 0.5) | 0.125 | 1 |
| 11 | (1.25, 0.25, 0.5) | 0.25 | 2 |
| 12 | (1.375, 0.25, 0.5) | 0.375 | 3 |
| 13 | (1.5, 0.25, 0.5) | 0.5 | 4 |
| 14 | (1.75, 0.25, 0.5) | 0.75 | 5 |
| 15 | (3.0, 0.25, 0.5) | 2 | 6 |
| 16 | (6.0, 0.25, 0.5) | 5 | 7 |

`_inside_any` matched the analytic solid-box predicate on all 17 points. `point_triangle_distance` matched the analytic distance with max abs error 0. Pair count for 8 outside points × 12 triangles = 96. `ceil(96/72)=2`, `ceil(96/40)=3`, `ceil(96/400000000)=1`. The lowered modules were `exec` copies of the file with that one assignment replaced. Replacing the token back recovered the original source text. The unmodified `exec` copy matched the production module’s published distance and volume fields on the canonical population.

Full-population oracle (all 17 analytic distances, same `np.percentile(d, 95)` and the same `round` calls): max 5.0, p95 raw `2.599999999999998` published 2.6, shares 0.41176 / 0.29412 / 0.11765 (7/17, 5/17, 2/17). Zero fraction 9/17.

### F5 — stride 1 control, then stride 2 and 3 (verified-by-run)

Published `ucx_fit` fields. An independent reconstruction of `measured = all inside zeros + outside[::stride]` using the module’s own point-triangle distances matched max, p95, shares, `samples`, and `measured_samples` on every run (`predicted_matches_published`).

| Run | FIT_MAX_PAIRS | stride | samples | measured | max m | p95 m | share >0.10 / >0.30 / >1.00 | 5 m kept | zero fraction |
|---|---:|---:|---:|---:|---:|---:|---|---|---:|
| production and unmodified copy | 400000000 | 1 | 17 | 17 | 5.0 | 2.6 | 0.41176 / 0.29412 / 0.11765 | yes | 9/17 |
| canonical outside index 7 | 72 | 2 | 17 | 13 | 2.0 | 1.1 | 0.23077 / 0.15385 / 0.07692 | no | 9/13 |
| canonical outside index 7 | 40 | 3 | 17 | 12 | 2.0 | 1.1062 | 0.16667 / 0.16667 / 0.08333 | no | 9/12 |

Stride 2 keeps outside ranks 0, 2, 4, 6 (sample indices 9, 11, 13, 15): distances 0.0625, 0.25, 0.5, 2. The 5 m point at rank 7 is absent, so the max is the remaining 2 m point. Raw p95 `1.0999999999999979`, published 1.1. Stride 3 keeps ranks 0, 3, 6 (indices 9, 12, 15): 0.0625, 0.375, 2. Raw p95 `1.1062499999999988`, and `round(..., 4)` is 1.1062. The 2 m point remains in both canonical runs, so the missing maximum is that one 5 m sample.

### F6 — inside zeros reweight p95 and the shares (verified-by-run)

On the canonical stride-2 retained outside set `{0.0625, 0.25, 0.5, 2}` alone, p95 is 1.775 and the shares are 0.75 / 0.5 / 0.25. The same four distances plus all 9 zeros (what `ucx_fit` publishes) give p95 1.1 and shares 0.23077 / 0.15385 / 0.07692. Stride 3 outside-only `{0.0625, 0.375, 2}` gives p95 1.8375 and shares 0.66667 / 0.66667 / 0.33333; with the 9 zeros, p95 is 1.1062 and the shares are 0.16667 / 0.16667 / 0.08333. Zero fraction rises from 9/17 to 9/13 and 9/12 because the stride drops outside points and leaves every inside zero in `d`.

The no-inside control uses the same eight outside points and the same lowered caps. Stride 2: samples 8, measured 4, max 2.0, p95 1.775, shares 0.75 / 0.5 / 0.25. Stride 3: measured 3, max 2.0, p95 1.8375, shares 0.66667 / 0.66667 / 0.33333. Those p95 and share figures equal the outside-only column of the mixed runs. With no zeros, the zero-fraction channel is absent and the outlier still leaves the max.

The all-inside control (9 zeros, `FIT_MAX_PAIRS` 72 and the production cap) reports `distance_stride` 1, because `len(out_pts)` is 0 so `ceil(0)` is 0 and `max(1, 0)` is 1. Max, p95, and all three shares are 0. Measured samples equal 9.

### F7 — outlier on and off the retained indices (verified-by-run)

The other outside points keep their relative order. Only the slot of the 5 m point changes. This is an injected permutation. It is a separate probe from the order `_samples` can emit: that order is the sorted unique of rounded `sample_surface` points, then possibly `sample_stride`. These five slots were not produced by `sample_surface`.

A point at outside rank `k` is retained when `k % distance_stride == 0`.

| Outside index of the 5 m point | Stride 2 max m | 5 m kept | Stride 3 max m | 5 m kept |
|---:|---:|---|---:|---|
| 0 | 5.0 | yes | 5.0 | yes |
| 1 | 0.75 | no | 0.75 | no |
| 2 | 5.0 | yes | 0.75 | no |
| 3 | 0.75 | no | 5.0 | yes |
| 7 (canonical) | 2.0 | no | 2.0 | no |

Index 0 is always kept. Index 7 is kept by neither stride 2 nor stride 3. When the outlier sits at index 1, the published max is 0.75: in that permutation the 2 m point is also off the lattice. The canonical row is the one where the 2 m point stays and only the 5 m point leaves.

### F8 — repeat and immutability (verified-by-run)

Each of the 19 calls above was repeated on the same readback. The two result dicts were equal. The readback, the extra dict, and the injected buffer were unchanged after both calls. `reason` was null.

## How it applies to this repository

- The measurement lives in `tools/methods/methods_metrics.py` (`ucx_fit`, lines 318–375). The pair cap is line 27. The selection that can drop one outside point is line 331. The population that still contains every inside zero is lines 337–341 and 366–368.
- The only production caller is `tools/methods/run_variant.py:242`, for class `ucx-collisions`.
- `docs/methods/README.md` lines 68–71 describe max, p95, and the three shares as one-sided measurements and say they are not the R11–R13 verdict. The README does not describe `distance_stride`.
- `docs/methods/ucx-collisions/RESULTS.md` is generated by `tools/methods/results_md.py` and shows max / p95. A future row with stride greater than 1 would still show only those two distance numbers.
- `docs/domain/areas/ucx.md` R11–R13 and [D134] remain one-sided limits with L2 coverage `none`. This catalog field is not that check.
- Tests under `tests/methods/test_methods_catalog.py` lock a covered cube (max 0), a half-covered cube (max about 0.5), and a missing hull. They do not lock the stride.

## Proposed next tasks

1. **Pin the measured stride rows on the frozen unit box.** Size S. Test-only, against `ucx_fit`, with `_samples` replaced by the 17-point sequence in this note and `FIT_MAX_PAIRS` set to 400,000,000, 72, and 40. Leave `_inside_any`, the line `np.nonzero(~inside)[0][::dstride]` expression, and `point_triangle_distance` as they are. Input: the canonical order (5 m at outside index 7) and the index-0 permutation. Expected: stride 1 publishes max 5.0, p95 2.6, shares 0.41176 / 0.29412 / 0.11765, measured 17; stride 2 publishes max 2.0, p95 1.1, shares 0.23077 / 0.15385 / 0.07692, measured 13; stride 3 publishes max 2.0, p95 1.1062, shares 0.16667 / 0.16667 / 0.08333, measured 12; outside index 0 keeps max 5.0 at strides 2 and 3. Value: a later edit of the reducer moves a known number. Effort S. `Advances #149`.

2. **Decision sheet for the quantity named by max, p95, and share when stride exceeds 1.** Size S. One page that places the canonical stride-2 row (max 2.0, p95 1.1, zero fraction 9/13) next to the outside-only figures for the same retained points (p95 1.775, shares 0.75 / 0.5 / 0.25), the full-population oracle (max 5.0, p95 2.6), and [D134]. The sheet asks which definition those three fields should keep: the current retained subset, a maximum over every outside sample, or a percentile that puts the dropped outside points back. It does not change `FIT_MAX_PAIRS`, the reducer, `RESULTS.md`, or any gate. Input: the canonical stride-2 published triple above. Expected output: a decision record that either keeps the current definition or names another one, with that row’s numbers written out as the consequence. Value: R12’s stored pair upper bound is already 312,884,208 of 400,000,000, so the cap is close enough that the meaning should be chosen before a catalog row crosses it. Effort S. `Advances #149`.

`#753` is the AC08 end-to-end seam in other notes, and `#298` is the SINTEZ/UCX seam. Neither names this reducer. The issue tracker was not queried (`gh` was not run).

An approximate population guarantee, a weighted percentile, or a guarantee that `model_to_ucx_max_m` is the maximum of every outside sample would need a user policy decision. [D134] fixes the one-sided limits and leaves zoning out of this metric. It does not define the subsample. This note does not adopt one.

## Open questions

1. When `distance_stride` exceeds 1, should `model_to_ucx_max_m` stay the max of the retained outside samples, or cover every outside sample?
2. Should the p95 and `share_over_m` denominator keep every inside zero after outside samples have been strided?
3. Is 400,000,000 still the intended pair cap, given R12’s stored upper bound of 312,884,208?

## Reproduction

The script below is the one that was run (`uv run python C:/x/t_2d7a4372/probe_ucx_distance_stride.py` from the worktree). It writes JSON only under `C:/x/t_2d7a4372/`. Injected points are labeled as injected inside the script.

```python
"""Synthetic probe: ucx_fit distance_stride vs max / p95 / share_over_m.

Injected samples, not production surface sampling. Does not edit the repo.
Scratch only. Run from the worktree: uv run python C:/x/t_2d7a4372/probe_ucx_distance_stride.py
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(r"C:\Users\artsafro\agr-pilot\AGR-DigitalTwin\.worktrees\t_2d7a4372")
SRC = ROOT / "tools" / "methods" / "methods_metrics.py"
MAIN_SHA = "1a417376af6be46872ba1c6a7aa4bfcf32c33cec"  # declared by the task; git was not run
STEPS = (0.10, 0.30, 1.00)

# Unit solid box [0, 1]^3. Outside points sit on the ray x>1, y=0.25, z=0.5 so the
# closest surface point is the interior of the +X face (strictly off the quad diagonal z=y).
# Distances are binary64-exact dyadics / integers and straddle 0.10 / 0.30 / 1.00.
OUTSIDE = [
    ((1.0625, 0.25, 0.5), 0.0625),
    ((1.125, 0.25, 0.5), 0.125),
    ((1.25, 0.25, 0.5), 0.25),
    ((1.375, 0.25, 0.5), 0.375),
    ((1.5, 0.25, 0.5), 0.5),
    ((1.75, 0.25, 0.5), 0.75),
    ((3.0, 0.25, 0.5), 2.0),
    ((6.0, 0.25, 0.5), 5.0),  # isolated largest outlier, canonical outside index 7
]
INSIDE = [
    (0.25, 0.25, 0.25), (0.25, 0.25, 0.75), (0.25, 0.75, 0.25), (0.25, 0.75, 0.75),
    (0.75, 0.25, 0.25), (0.75, 0.25, 0.75), (0.75, 0.75, 0.25), (0.75, 0.75, 0.75),
    (0.5, 0.5, 0.5),
]
BOX_T = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
         (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]


def box(lo, hi):
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    return [[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
            [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]]


def mesh(name, verts, tris, *, materials=("M_Test_Main_1",)):
    polys = [list(t) for t in tris]
    m = {
        "name": name, "vertices": len(verts), "polygons": len(polys), "triangles": len(polys),
        "polygon_degrees": {"3": len(polys)},
        "bounds_m": [[min(p[i] for p in verts) for i in range(3)], [max(p[i] for p in verts) for i in range(3)]],
        "location": [0.0, 0.0, 0.0], "rotation_euler_deg": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0],
        "world_scale": [1.0, 1.0, 1.0], "parent": None, "uv_channels": 0,
        "materials": list(materials), "udim_tiles": [], "mirrored_uv_triangles": 0,
        "face_geometry": {"vertices": verts, "polygons": polys},
    }
    if name.startswith("UCX_"):
        m["hull"] = {"verts": verts, "tris": [list(t) for t in tris]}
        m["materials"] = []
    return m


def scene():
    model = mesh("SM_Test_Main", box((0, 0, 0), (1, 1, 1)), BOX_T)
    ucx = mesh("UCX_SM_Test_Main_001", box((0, 0, 0), (1, 1, 1)), BOX_T, materials=())
    rb = {
        "source": "C:/synthetic/SM_Test.fbx", "readback_ok": True, "blender": "synthetic",
        "meshes": [model, ucx], "other_objects": [], "images": [], "materials": [],
        "fbx_units": {"unit_scale_factor": 1.0, "original_unit_scale_factor": 1.0},
    }
    extra = {"ok": True, "meshes": {}}
    for m in rb["meshes"]:
        extra["meshes"][m["name"]] = {
            "slots": list(m["materials"]),
            "polygons_by_material_index": {"0": m["polygons"]} if m["materials"] else {},
            "tris": m["face_geometry"]["polygons"],
        }
    return rb, extra


def solid_box_distance(p, lo=0.0, hi=1.0):
    p = np.asarray(p, float)
    clamped = np.clip(p, lo, hi)
    if np.all((p >= lo) & (p <= hi)):
        return 0.0
    return float(np.linalg.norm(p - clamped))


def load_module(name: str, source: str):
    mod = type(sys)(name)
    mod.__file__ = str(SRC)
    sys.modules[name] = mod
    exec(compile(source, str(SRC), "exec"), mod.__dict__)
    return mod


def stats(values: np.ndarray) -> dict:
    d = np.asarray(values, float)
    return {
        "n": int(d.size),
        "max_raw": None if d.size == 0 else float(d.max()),
        "max_rounded_4": None if d.size == 0 else round(float(d.max()), 4),
        "p95_raw": None if d.size == 0 else float(np.percentile(d, 95)),
        "p95_rounded_4": None if d.size == 0 else round(float(np.percentile(d, 95)), 4),
        "share_over_m": {
            f"{x:.2f}": None if d.size == 0 else round(float((d > x).mean()), 5) for x in STEPS
        },
        "share_over_raw": {
            f"{x:.2f}": None if d.size == 0 else float((d > x).mean()) for x in STEPS
        },
        "n_zero": int(np.count_nonzero(d == 0.0)),
        "zero_fraction": None if d.size == 0 else float(np.count_nonzero(d == 0.0) / d.size),
    }


def fit_for_stride(pairs: int, stride: int) -> int:
    cands = [f for f in range(1, pairs + 1) if math.ceil(pairs / f) == stride]
    if not cands:
        raise SystemExit(f"no FIT_MAX_PAIRS yields stride {stride} for {pairs} pairs")
    return cands[len(cands) // 2]


def sequence(outside_pts, inside_pts):
    pts = [tuple(p) for p in inside_pts] + [tuple(p) for p in outside_pts]
    analytic = [solid_box_distance(p) for p in pts]
    return np.asarray(pts, float), np.asarray(analytic, float)


def place_outlier(k: int):
    """Outside order with the distance-5 point at outside index k. Other points keep their relative order."""
    base = [(p, d) for p, d in OUTSIDE if d != 5.0]
    outlier = [(p, d) for p, d in OUTSIDE if d == 5.0]
    assert len(outlier) == 1 and 0 <= k <= len(base)
    ordered = base[:k] + outlier + base[k:]
    return [p for p, _ in ordered], [d for _, d in ordered]


def bind_samples(mod, pts: np.ndarray):
    buf = {"arr": None, "before": None, "calls": 0}

    def _samples(v, t, max_points):
        buf["calls"] += 1
        arr = np.array(pts, dtype=float, copy=True)
        buf["arr"] = arr
        buf["before"] = arr.copy()
        return arr, 0.0, 1

    mod._samples = _samples
    return buf


def slim(fit: dict) -> dict:
    keys = (
        "samples", "sample_spacing_m", "sample_stride", "distance_stride", "measured_samples",
        "model_to_ucx_max_m", "model_to_ucx_p95_m", "share_over_m", "reason",
        "voxel_m", "ucx_volume_m3", "model_envelope_m3",
    )
    return {k: fit.get(k) for k in keys}


def run_fit(mod, pts: np.ndarray):
    rb, extra = scene()
    rb_before, extra_before = copy.deepcopy(rb), copy.deepcopy(extra)
    buf = bind_samples(mod, pts)
    a = mod.ucx_fit(rb, extra)
    immutable = {
        "rb": rb == rb_before,
        "extra": extra == extra_before,
        "injected_buffer": buf["arr"] is not None and np.array_equal(buf["arr"], buf["before"]),
        "samples_calls": buf["calls"],
    }
    b = mod.ucx_fit(rb, extra)
    immutable["repeat_equal"] = a == b
    immutable["inputs_after_second"] = rb == rb_before and extra == extra_before
    return a, immutable


def predicted(inside: np.ndarray, tri_dist: np.ndarray, dstride: int) -> dict:
    sel = np.nonzero(~inside)[0][::dstride]
    measured = np.zeros(len(inside), bool)
    measured[inside] = True
    measured[sel] = True
    values = np.zeros(len(inside), float)
    values[sel] = tri_dist[sel]
    kept = values[measured]
    outside_only = tri_dist[sel]
    return {
        "outside_index_in_sample": sel.tolist(),
        "outside_rank_kept": [int(np.nonzero(~inside)[0].tolist().index(i)) for i in sel.tolist()],
        "with_all_zeros": stats(kept),
        "outside_only_retained": stats(outside_only),
    }


def inventory() -> dict:
    rows = []
    files = sorted((ROOT / "docs" / "methods").rglob("results.jsonl"))
    bench = list((ROOT / "benchmark").rglob("*.jsonl")) + list((ROOT / "benchmark").rglob("*.json"))
    for path in files:
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            row = json.loads(line)
            fit = ((row.get("class_metrics") or {}).get("ucx_fit"))
            if not isinstance(fit, dict):
                continue
            samples = fit.get("samples")
            tris = (row.get("triangles") or {}).get("ucx")
            product = None if samples is None or tris is None else int(samples) * int(tris)
            rows.append({
                "file": str(path.relative_to(ROOT)).replace("\\", "/"),
                "line": i,
                "row": row.get("row"),
                "variant": row.get("variant"),
                "benchmark": row.get("benchmark"),
                "keys": sorted(fit),
                "distance_stride": fit.get("distance_stride", "ABSENT"),
                "samples": samples,
                "measured_samples": fit.get("measured_samples", "ABSENT"),
                "sample_stride": fit.get("sample_stride", "ABSENT"),
                "ucx_triangles_row": tris,
                "samples_times_ucx_triangles": product,
                "model_to_ucx_max_m": fit.get("model_to_ucx_max_m"),
                "model_to_ucx_p95_m": fit.get("model_to_ucx_p95_m"),
            })
    return {
        "results_jsonl": [str(p.relative_to(ROOT)).replace("\\", "/") for p in files],
        "benchmark_json_or_jsonl_count": len(bench),
        "ucx_fit_rows": rows,
        "rows_with_stride_gt_1": [r for r in rows if isinstance(r["distance_stride"], int) and r["distance_stride"] > 1],
        "rows_missing_distance_stride": [r["row"] for r in rows if r["distance_stride"] == "ABSENT"],
    }


def main():
    source = SRC.read_text(encoding="utf-8")
    disk_sha = hashlib.sha256(source.encode("utf-8")).hexdigest()
    token = "FIT_MAX_PAIRS = 400_000_000  # point x triangle pairs for exact outside distances (stride above this)"
    if source.count(token) != 1:
        raise SystemExit("FIT_MAX_PAIRS token count != 1")
    prod = load_module("ucx_probe_prod", source)
    if prod.FIT_MAX_PAIRS != 400_000_000:
        raise SystemExit("production FIT_MAX_PAIRS is not 400_000_000")

    rb0, extra0 = scene()
    pieces = prod._pieces(rb0)
    tri = np.concatenate([p["v"][p["t"]] for p in pieces])
    ntri = int(len(tri))
    canonical_pts, canonical_analytic = sequence([p for p, _ in OUTSIDE], INSIDE)
    inside = prod._inside_any(canonical_pts, pieces)
    analytic_inside = np.array([solid_box_distance(p) == 0.0 for p in canonical_pts])
    q = canonical_pts[:, None, :]
    tri_dist = prod.point_triangle_distance(q, tri[None, :, 0], tri[None, :, 1], tri[None, :, 2]).min(axis=1)
    tri_dist = np.where(inside, 0.0, tri_dist)
    n_out = int((~inside).sum())
    pairs = n_out * ntri
    fit2 = fit_for_stride(pairs, 2)
    fit3 = fit_for_stride(pairs, 3)

    copies = {
        "prod_4e8": prod,
        "copy_4e8": load_module("ucx_probe_copy_4e8", source),
        "copy_stride2": load_module("ucx_probe_copy_s2", source.replace(token, f"FIT_MAX_PAIRS = {fit2}  # probe override", 1)),
        "copy_stride3": load_module("ucx_probe_copy_s3", source.replace(token, f"FIT_MAX_PAIRS = {fit3}  # probe override", 1)),
    }
    # Prove the lowered copies differ from disk source by that one assignment only.
    diffs = {}
    for label, fit in (("copy_stride2", fit2), ("copy_stride3", fit3)):
        altered = source.replace(token, f"FIT_MAX_PAIRS = {fit}  # probe override", 1)
        diffs[label] = {
            "fit_max_pairs": copies[label].FIT_MAX_PAIRS,
            "source_equal_except_token": altered.replace(f"FIT_MAX_PAIRS = {fit}  # probe override", token) == source,
        }

    geom = {
        "ntri_after_weld": ntri,
        "inside_agrees_with_analytic": bool(np.array_equal(inside, analytic_inside)),
        "n_inside": int(inside.sum()),
        "n_outside": n_out,
        "pairs": pairs,
        "fit_stride2": fit2,
        "fit_stride3": fit3,
        "point_triangle_minus_analytic_max_abs": float(np.max(np.abs(tri_dist - canonical_analytic))),
        "per_point": [
            {
                "i": i,
                "xyz": [float(x) for x in canonical_pts[i]],
                "analytic_m": float(canonical_analytic[i]),
                "point_triangle_m": float(tri_dist[i]),
                "inside_any": bool(inside[i]),
            }
            for i in range(len(canonical_pts))
        ],
    }

    runs = []

    def one(label, mod, pts, note):
        fit, immutable = run_fit(mod, pts)
        ins = mod._inside_any(pts, pieces)
        qpts = pts[:, None, :]
        td = mod.point_triangle_distance(qpts, tri[None, :, 0], tri[None, :, 1], tri[None, :, 2]).min(axis=1)
        td = np.where(ins, 0.0, td)
        pred = predicted(ins, td, int(fit["distance_stride"]))
        published = slim(fit)
        match = (
            published["model_to_ucx_max_m"] == pred["with_all_zeros"]["max_rounded_4"]
            and published["model_to_ucx_p95_m"] == pred["with_all_zeros"]["p95_rounded_4"]
            and published["share_over_m"] == pred["with_all_zeros"]["share_over_m"]
            and published["measured_samples"] == pred["with_all_zeros"]["n"]
            and published["samples"] == int(len(pts))
        )
        runs.append({
            "label": label,
            "note": note,
            "fit_max_pairs": mod.FIT_MAX_PAIRS,
            "published": published,
            "immutable": immutable,
            "predicted_matches_published": match,
            "predicted": pred,
            "full_population_point_triangle": stats(td),
            "full_population_analytic": stats(np.array([solid_box_distance(p) for p in pts])),
            "outlier_distance_m": 5.0 if any(abs(solid_box_distance(p) - 5.0) < 1e-12 for p in pts) else None,
            "outlier_retained": bool(any(abs(td[i] - 5.0) < 1e-9 for i in pred["outside_index_in_sample"])) if pred["outside_index_in_sample"] or True else False,
        })

    one("canonical_prod", copies["prod_4e8"], canonical_pts, "unmodified FIT_MAX_PAIRS; outlier at outside index 7")
    one("canonical_copy_4e8", copies["copy_4e8"], canonical_pts, "exec of unmodified source; identity with production")
    one("canonical_s2", copies["copy_stride2"], canonical_pts, "FIT lowered so stride is 2; outlier at outside index 7")
    one("canonical_s3", copies["copy_stride3"], canonical_pts, "FIT lowered so stride is 3; outlier at outside index 7")

    for k in (0, 1, 2, 3, 7):
        outs, _ = place_outlier(k)
        pts, _ = sequence(outs, INSIDE)
        one(f"perm_out_index_{k}_s2", copies["copy_stride2"], pts,
            "selection probe: injected order, outlier at outside index %d, stride 2; not a production _samples order" % k)
        one(f"perm_out_index_{k}_s3", copies["copy_stride3"], pts,
            "selection probe: injected order, outlier at outside index %d, stride 3; not a production _samples order" % k)

    no_in_pts = np.asarray([p for p, _ in OUTSIDE], float)
    one("no_inside_s2", copies["copy_stride2"], no_in_pts, "no inside zeros; canonical outside order; stride 2")
    one("no_inside_s3", copies["copy_stride3"], no_in_pts, "no inside zeros; canonical outside order; stride 3")
    outs0, _ = place_outlier(0)
    one("no_inside_outlier0_s2", copies["copy_stride2"], np.asarray(outs0, float),
        "no inside zeros; outlier at outside index 0; stride 2")
    one("all_inside_s2", copies["copy_stride2"], np.asarray(INSIDE, float),
        "all samples inside; lowered FIT must still report distance_stride 1")
    one("all_inside_prod", copies["prod_4e8"], np.asarray(INSIDE, float),
        "all samples inside; production FIT")

    # Identity of the two stride-1 publishers on the canonical population.
    by = {r["label"]: r["published"] for r in runs}
    identity = by["canonical_prod"] == by["canonical_copy_4e8"]

    disk_after = hashlib.sha256(SRC.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    out = {
        "main_sha_declared": MAIN_SHA,
        "git_run": False,
        "numpy": np.__version__,
        "percentile_call": "np.percentile(d, 95)  # same call as ucx_fit; default method",
        "source": str(SRC),
        "source_sha256": disk_sha,
        "source_sha256_after": disk_after,
        "source_unchanged": disk_sha == disk_after,
        "fit_diffs": diffs,
        "geometry": geom,
        "stride1_copy_matches_prod": identity,
        "runs": runs,
        "inventory": inventory(),
        "reducer_lines": "tools/methods/methods_metrics.py:328-368",
    }
    dest = Path(r"C:\x\t_2d7a4372\probe_ucx_distance_stride.json")
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({
        "source_unchanged": out["source_unchanged"],
        "ntri": ntri,
        "pairs": pairs,
        "fit2": fit2,
        "fit3": fit3,
        "geom_err": geom["point_triangle_minus_analytic_max_abs"],
        "inside_ok": geom["inside_agrees_with_analytic"],
        "identity": identity,
        "rows": len(out["inventory"]["ucx_fit_rows"]),
        "stride_gt_1": out["inventory"]["rows_with_stride_gt_1"],
        "missing": out["inventory"]["rows_missing_distance_stride"],
        "runs": [
            {
                "label": r["label"],
                "stride": r["published"]["distance_stride"],
                "samples": r["published"]["samples"],
                "measured": r["published"]["measured_samples"],
                "max": r["published"]["model_to_ucx_max_m"],
                "p95": r["published"]["model_to_ucx_p95_m"],
                "share": r["published"]["share_over_m"],
                "match": r["predicted_matches_published"],
                "outlier_retained": r["outlier_retained"],
                "zero_frac_measured": r["predicted"]["with_all_zeros"]["zero_fraction"],
                "zero_frac_full": r["full_population_point_triangle"]["zero_fraction"],
                "p95_outside_only": r["predicted"]["outside_only_retained"]["p95_rounded_4"],
                "share_outside_only": r["predicted"]["outside_only_retained"]["share_over_m"],
                "p95_full": r["full_population_point_triangle"]["p95_rounded_4"],
                "immutable": r["immutable"],
                "voxel": r["published"]["voxel_m"],
            }
            for r in runs
        ],
    }, indent=2))


if __name__ == "__main__":
    main()
```
