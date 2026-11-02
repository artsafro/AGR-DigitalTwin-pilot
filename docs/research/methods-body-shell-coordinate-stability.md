# Methods closed shells: does translation alone change the verdict?

Status: research (report-only, synthetic metric evidence). `delivery_passed=false`.

Pinned source SHA: `58397b1d815c1b0957207159d57e95a9fce2fee7`.
Measured file: `tools/methods/methods_metrics.py`, SHA-256 `3fff60eaba5999e2eb2076767695e52a64ea0c742159f95550762579d7792dc7`.
Interpreter: CPython 3.14.7 (MSC v.1944 64 bit, AMD64). NumPy 2.5.3.
Probe: `C:/x/t_8d6b9ef6/probe.py`. Raw rows: `C:/x/t_8d6b9ef6/run1.json`, `run2.json`, `run3.json`. Cross-run compare: `C:/x/t_8d6b9ef6/summary.json` (`runs_identical: true`, 75 rows).

The question was raised from #758's large-coordinate boundary. This session did not open the issue tracker (`gh` was not run). The issue text is not in the worktree. The measurements below are of `closed_shells` on the frozen synthetic corpus, not a reading of the issue body.

## Summary

Translation alone can change the public `closed_shells` verdict, and on this corpus it does so in one place. A right tetrahedron with 0.25 m orthogonal edges is a closed shell at the origin and at `(1000,-1000,0)`, `(-1170,-14200,0)` and `(600000,7500000,150)`. The same four closed variants (base winding, full reverse, and two hand-chosen face orders), shifted by the labelled synthetic stress `(2**24, 2**24, 2**24)`, come back open with `open_reasons == {"zero enclosed volume": 1}` and share `0.0`. Weld grouping does not change on any of the 75 rows: every vertex stays its own key, and the representative index list matches the identity translation. The stage that moves is the world-origin sum `a · (b × c) / 6` compared with `weld_m**3`. At the stress shift those four tetra terms are `-1048576, -1048576, -1048576, 3145728` and sum to `0`. A 0.125 m box at the same shift stays closed (share `1.0`) while its world volume reads `174762.66666666666` instead of `0.001953125`, because the gate only rejects a volume that is too small. A 1 m box stays exactly `±1` at every translation here, including the stress. Subtracting vertex 0 and summing triple products with `math.fsum` recovers the analytic signed volume on every closed row. That recentering is a measurement, not an adopted fix, and these dyadic shells do not certify survey-coordinate exports.

## Findings

### F1 — Grouping does not change (verified by run)

`closed_shells` welds with `key = np.round(v / weld_m).astype(np.int64)` and `np.unique` (`tools/methods/methods_metrics.py` lines 619-620, 628). `SHELL_WELD_M` is `1e-4` (line 525). Its float hex is `0x1.a36e2eb1c432dp-14`. The returned `weld_m` has that same hex on every row.

On all 75 rows the partition is singletons, `collapsed == 0`, and `grouping_changed_vs_identity` is false. Representative index lists, identical at every translation of a shape:

| shape | partition | `rep_index` (first vertex of each sorted key) |
|---|---|---|
| both boxes | `(0,)..(7,)` | `[0, 4, 3, 7, 1, 5, 2, 6]` |
| tetrahedron | `(0,)..(3,)` | `[0, 3, 2, 1]` |

Absolute keys do move. Vertex 0 at the stress shift has key `[167772160000, 167772160000, 167772160000]`, which is `round(2**24 / 1e-4)` as measured. The index partition does not. Adding the translation and subtracting it back was bitwise exact for every vertex of every row (`translation_add_and_sub_exact` true). Input lists were unchanged after `closed_shells` and after the transcript (`inputs_unchanged` true). So the mesh that reached the volume formula was exactly the local mesh plus the translation, not a weld merge and not a mutated array.

### F2 — The public verdict changes on four rows, all the same stage (verified by run)

`closed_shells(rb)` was called with the default weld. A local transcript of the same gates matched the public dict on every row (the probe aborts if the hex-canonical dicts differ). Each mesh is one component.

Gate order, read from lines 646-655 and confirmed by the `why` string that matched the public `open_reasons`: edge used twice, then duplicated triangle, then opposite winding, then `area2 <= weld_m**2`, then `abs(vol6.sum()) / 6 <= weld_m**3`.

`weld_m**3` evaluates to `1.0000000000000002e-12`. The tetra stress sum is exact `0`, so that extra bit in the threshold is not what flips the row.

Closed variants (base, reversed, `perm_rev`, `perm_rot`) at identity, `(1000,-1000,0)`, `(-1170,-14200,0)` and `(600000,7500000,150)`:

| case | share | components | closed_components | open_reasons |
|---|---|---|---|---|
| box side 1 m | `1.0` (`0x1.0000000000000p+0`) | 1 | 1 | `{}` |
| box side 0.125 m | `1.0` | 1 | 1 | `{}` |
| tetra edge 0.25 m | `1.0` | 1 | 1 | `{}` |

The same closed variants at `(2**24, 2**24, 2**24)`:

| case | share | closed_components | open_reasons | verdict vs identity |
|---|---|---|---|---|
| box side 1 m | `1.0` | 1 | `{}` | unchanged |
| box side 0.125 m | `1.0` | 1 | `{}` | unchanged |
| tetra edge 0.25 m, all four variants | `0.0` (`0x0.0p+0`) | 0 | `{"zero enclosed volume": 1}` | changed |

Open-face controls (box: both triangles of the z=0 quad removed; tetra: hypotenuse triangle removed) stay `share 0.0`, `closed_components 0`, reason `edge not shared by exactly two triangles`, at every translation including the stress. The volume gate is not the one that decides them.

Three fresh interpreter processes wrote identical row payloads, including every `float.hex()` field.

### F3 — The arithmetic stage is the world-origin triple product, not the sum reduction and not the weld (verified by run)

World volume is `np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6` on the welded representatives (lines 630-631 and 654). `a, b, c` are positions in the translated frame. They are not edge vectors. Area uses `b - a` and `c - a` (line 630) and stays exact on this corpus: tetra `area2_min` `0.0625` (`0x1.0000000000000p-4`), 0.125 m box `0.015625` (`0x1.0000000000000p-6`), 1 m box `1.0`. Both are far above `weld_m**2` (`1e-8`).

`math.fsum` of those same world-origin terms equals the NumPy sum on all 75 rows (`world_volume_hex == world_fsum_volume_hex`). The pairwise reduction is not an extra error. The rounded terms already have the wrong sum.

Tetra, base winding, stress shift, the four world terms (vol6, before `/6`):

| term hex | decimal |
|---|---|
| `-0x1.0000000000000p+20` | `-1048576` |
| `-0x1.0000000000000p+20` | `-1048576` |
| `-0x1.0000000000000p+20` | `-1048576` |
| `0x1.8000000000000p+21` | `3145728` |

Sum `0`, volume `0.0` (`0x0.0p+0`). Identity on the same faces has terms `0, 0, 0, 0.015625` and volume `0.0026041666666666665` (`0x1.5555555555555p-9`), which is `(0.25**3)/6` in float64. Reversed winding at the stress shift is the negation of those four integers and also sums to `0`, so the absolute-value gate still fails. Both face-order permutations do the same: the sum is exact zero, so order does not matter there.

The independent recentered volume subtracts input vertex 0, forms the scalar triple product in Python floats, and sums with `math.fsum`. On this tetra, stress or not, that volume is `±0.0026041666666666665`, matching the analytic signed volume. The recentered terms at the stress shift are again `0, 0, 0, ±0.015625`. This shows the lost residual is the part of `a · (b × c)` that does not survive at world scale. It is not a patch, and it was not substituted into `closed_shells`.

### F4 — A wrong volume can stay closed, because the gate is one-sided (verified by run)

The predicate is `abs(volume) <= weld_m**3`. It does not compare the volume with the analytic solid.

0.125 m box, base winding, stress shift. Twelve world vol6 terms: five `262144` (`0x1.0000000000000p+18`), one `-262144`, six zeros in the positions listed in `run1.json`. Sum of terms `1048576`, volume `174762.66666666666` (`0x1.5555555555555p+17`). Analytic volume `0.001953125` (`0x1.0000000000000p-9` = `0.125**3`). Recentered volume equals that analytic value. Share stays `1.0`. The same world hex appears for `perm_rev` and `perm_rot`. Reversed winding at the same shift has world volume `218453.33333333334` (`0x1.aaaaaaaaaaaabp+17`), recentered volume `-0.001953125`, and share still `1.0`. So face order did not move this residual, and full reversal moved the residual without moving the verdict.

1 m box, base, stress shift. The twelve world terms are six `-16777216` and six `16777217`. Their sum is `6`, volume `1.0` exactly. Reversed winding is `-1.0` exactly. Same at the three smaller translations. Category (b) does not appear for the closed 1 m box: the measured world volume matches the analytic signed volume.

Classification on the closed variants:

| observation | rows |
|---|---|
| (a) grouping changed | none |
| (b) world volume differs from analytic, and the verdict changes | tetra, four closed variants, stress shift only |
| (b) and (c) world volume differs, verdict unchanged | 0.125 m box, four closed variants, stress shift only |
| world volume equals analytic signed volume, verdict unchanged | every other closed row, including both boxes and the tetra at `(600000, 7500000, 150)` |

### F5 — Open controls keep their reason while the unused volume number moves (verified by run)

The edge test fails first, so `open_reasons` does not mention volume. The world sum is still computed and, once a face is missing, it no longer cancels.

| case | translation | world volume | recentered volume | public reason |
|---|---|---|---|---|
| box 1 m open | identity, `1000`, `-1170` | `1.0` | `1.0` | edge not shared |
| box 1 m open | `(600000,7500000,150)` | `51.0` (`0x1.9800000000000p+5`) | `1.0` | edge not shared |
| box 1 m open | stress `2**24` | `5592406.333333333` (`0x1.5555595555555p+22`) | `1.0` | edge not shared |
| box 0.125 m open | identity, `1000`, `-1170` | `0.001953125` | `0.001953125` | edge not shared |
| box 0.125 m open | `(600000,7500000,150)` | `0.783203125` (`0x1.9100000000000p-1`) | `0.001953125` | edge not shared |
| box 0.125 m open | stress `2**24` | `174762.66666666666` | `0.001953125` | edge not shared |
| tetra open | identity, `1000` | `0.0` | `0.0` | edge not shared |
| tetra open | `(-1170,-14200,0)` | `160.10416666666666` (`0x1.4035555555555p+7`) | `0.0` | edge not shared |
| tetra open | `(600000,7500000,150)` | `-84376.5625` (`-0x1.4998900000000p+16`) | `0.0` | edge not shared |
| tetra open | stress `2**24` | `-524288.0` (`-0x1.0000000000000p+19`) | `0.0` | edge not shared |

The open box still shows recentered volume `1` or `0.001953125` because the removed quad contains vertex 0, so those two triangles contribute `0` after that subtraction. That is a property of this origin choice on this corpus. It is not evidence that an open shell encloses the solid. The public function never treats these rows as closed.

At identity the open 1 m box also has world volume `1.0`, for the same reason: vertex 0 is the world origin, and the removed face contributes nothing. The large-translation rows are where that coincidence stops.

### F6 — What the tests cover, and what was not run (read from code)

`tests/methods/test_building_body.py` calls `closed_shells` on synthetic meshes of a few metres (unit cube, a sheet, a weld collapse near 5 m). It does not translate by the shifts in this probe. Those tests were not executed.

`tests/test_source_class.py` (`test_brute_closed_shells_stay_monolithic` and the winding sweeps) does not call `methods_metrics.closed_shells`. It calls `source_facts`. That shell is different on purpose: `src/dt_ai/spec/source_class.py` lines 114-130 define a shell as "every undirected edge is used by exactly two triangles", and the docstring says winding is ignored and there is no signed-volume test. Its translations in that file are small (`(12,-4,7)`, `(-20,3,15)`, `(i*20,0,0)`). This probe did not run that function, and it did not run the orientation or UCX checkers.

`building_body` copies the `closed_shells` dict into the class row (`methods_metrics.py` line 679), renaming `reason` to `shell_reason`. A share change measured here would appear on that row. `building_body` itself was not called.

## How it applies to this repository

- The verdict under test is `tools/methods/methods_metrics.py`, `closed_shells`, lines 604-665. The weld constant is line 525. The volume expression is lines 630-631. The rejecting comparison is line 654.
- The building-body methods row repeats that dict from line 679.
- Existing closed-shell examples live in `tests/methods/test_building_body.py` (origin-scale) and, under a different predicate, in `tests/test_source_class.py` plus `src/dt_ai/spec/source_class.py`.
- Nothing in this measurement selects a coordinate convention, a shell-eligibility rule, a new threshold, or an approval status. `delivery_passed=false`.

## Proposed next tasks

1. **Pin the measured verdicts.** Size S. `Advances #149` (L2 self-check on the BODY methods metric; `docs/research/capability-roadmap.md` describes L2 as the agent checking itself). Test-only, against `closed_shells`, no change to `SHELL_WELD_M` or the formula. Input: tetra vertices `(0,0,0), (0.25,0,0), (0,0.25,0), (0,0,0.25)`, outward faces `(0,3,2), (0,1,3), (0,2,1), (1,2,3)`, translation `(16777216, 16777216, 16777216)`, base and fully reversed. Expected: `closed_shell_share == 0.0`, `closed_components == 0`, `open_reasons == {"zero enclosed volume": 1}`. Input: the same tetra at `(600000, 7500000, 150)`. Expected: `closed_shell_share == 1.0`, `closed_components == 1`, `open_reasons == {}`. Input: 0.125 m box with `BOX_FACES` from the probe, same stress translation, base winding. Expected: `closed_shell_share == 1.0`, `closed_components == 1`. The issue tracker was not re-queried here. `#753` is the AC08 end-to-end seam, and `#298` is the SINTEZ/UCX seam used by other notes. Neither is this function.

2. **Decision sheet for the volume term, with the measured pairs and no formula change.** Size S. `Advances #149`. One page. Input pair A: the four stress tetra terms `-1048576, -1048576, -1048576, 3145728` (sum `0`, public reason `zero enclosed volume`) beside the recentered volume `0.0026041666666666665`. Input pair B: the 0.125 m stress box, world volume `174762.66666666666`, public share `1.0`, analytic `0.001953125`. Expected output: a question that records both pairs and asks whether a later change may subtract a mesh vertex before the triple product. The page must not edit `weld_m`, must not treat recentering as already accepted, and must not claim the survey-magnitude rows certify an export.

## Open questions for the user

1. Should the synthetic `(2**24, 2**24, 2**24)` stress be in scope for this methods gate, or only translations that already occur on an OKS mesh?
2. The volume test rejects only a sum that is too small. The 0.125 m box at `2**24` stays closed with a world volume about `1.75e5`. Is that the intended reading of "enclosed |signed volume| exceeds `weld_m**3`"?
3. `source_facts` calls a shell closed with no volume test. Should that predicate and `closed_shells` stay different? This note does not choose.

## Reproduction

Frozen before the run. Corpus: box side `1` m, box side `0.125` m, right tetrahedron edge `0.25` m. Translations: identity, `(1000,-1000,0)`, `(-1170,-14200,0)`, `(600000,7500000,150)`, and `SYNTHETIC` `(2**24, 2**24, 2**24)`. Variants: base, full winding reverse, two fixed face-order permutations, one open face. No perturbation search and no tolerance edit. Command: `uv run python C:/x/t_8d6b9ef6/probe.py` from the worktree. That process spawned three fresh interpreters (`--once 1`, `--once 2`, `--once 3`).

```python
"""Frozen synthetic probe for methods closed_shells under translation.

Corpus literals are defined before any measurement. No search, no tolerance edits.
Scratch only. Does not modify the repository.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(r"C:\Users\artsafro\agr-pilot\AGR-DigitalTwin\.worktrees\t_8d6b9ef6")
OUT = Path(r"C:\x\t_8d6b9ef6")
METRICS = ROOT / "tools" / "methods" / "methods_metrics.py"

# --- frozen corpus (hand-written; do not generate by search) -----------------------

# Box corners in the same order as tests/methods/test_methods_catalog.py:box.
# 0 (0,0,0), 1 (s,0,0), 2 (s,s,0), 3 (0,s,0), 4 (0,0,s), 5 (s,0,s), 6 (s,s,s), 7 (0,s,s)
BOX_FACES = (
    (0, 2, 1), (0, 3, 2),  # z = 0 quad
    (4, 5, 6), (4, 6, 7),  # z = s quad
    (0, 1, 5), (0, 5, 4),
    (1, 2, 6), (1, 6, 5),
    (2, 3, 7), (2, 7, 6),
    (3, 0, 4), (3, 4, 7),
)
# Hand-chosen face-order permutations. Not a search.
BOX_PERM_REV = (11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0)
BOX_PERM_ROT = (5, 6, 7, 8, 9, 10, 11, 0, 1, 2, 3, 4)  # rotate left by 5

# Right tetrahedron, orthogonal edges of length 0.25 m, right angle at vertex 0.
# Outward faces. Analytic volume = edge**3 / 6.
TETRA_VERTS = (
    (0.0, 0.0, 0.0),
    (0.25, 0.0, 0.0),
    (0.0, 0.25, 0.0),
    (0.0, 0.0, 0.25),
)
TETRA_FACES = (
    (0, 3, 2),  # x = 0
    (0, 1, 3),  # y = 0
    (0, 2, 1),  # z = 0
    (1, 2, 3),  # hypotenuse
)
TETRA_PERM_REV = (3, 2, 1, 0)
TETRA_PERM_SWAP = (1, 0, 2, 3)  # swap the first two faces

TRANSLATIONS = (
    ("identity", (0.0, 0.0, 0.0)),
    ("t_1000_-1000_0", (1000.0, -1000.0, 0.0)),
    ("t_-1170_-14200_0", (-1170.0, -14200.0, 0.0)),
    ("t_600000_7500000_150", (600000.0, 7500000.0, 150.0)),
    ("SYNTHETIC_stress_2**24", (16777216.0, 16777216.0, 16777216.0)),  # 2**24 each axis
)


def box_verts(side: float) -> tuple[tuple[float, float, float], ...]:
    s = side
    return (
        (0.0, 0.0, 0.0),
        (s, 0.0, 0.0),
        (s, s, 0.0),
        (0.0, s, 0.0),
        (0.0, 0.0, s),
        (s, 0.0, s),
        (s, s, s),
        (0.0, s, s),
    )


def permute(faces, order):
    return tuple(faces[i] for i in order)


def reverse_winding(faces):
    return tuple(tuple(reversed(f)) for f in faces)


def cases():
    """Return the frozen (case, variant, faces, local_verts, analytic_abs, analytic_applies) rows."""
    box1 = box_verts(1.0)
    box8 = box_verts(0.125)
    rows = []
    specs = (
        ("box_side_1m", box1, BOX_FACES, 1.0, BOX_PERM_REV, BOX_PERM_ROT, (0, 1)),
        ("box_side_0.125m", box8, BOX_FACES, 0.125 ** 3, BOX_PERM_REV, BOX_PERM_ROT, (0, 1)),
        ("tetra_edge_0.25m", TETRA_VERTS, TETRA_FACES, (0.25 ** 3) / 6.0, TETRA_PERM_REV, TETRA_PERM_SWAP, (3,)),
    )
    for name, verts, faces, analytic, perm_a, perm_b, drop in specs:
        variants = (
            ("base", faces, True),
            ("reversed", reverse_winding(faces), True),
            ("perm_rev", permute(faces, perm_a), True),
            ("perm_rot", permute(faces, perm_b), True),
            ("open", tuple(f for i, f in enumerate(faces) if i not in drop), False),
        )
        for variant, vf, applies in variants:
            rows.append((name, variant, verts, vf, analytic, applies))
    return rows


CASES = cases()


def load_metrics():
    sys.path.insert(0, str(ROOT / "src"))
    spec = importlib.util.spec_from_file_location("methods_metrics", METRICS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def hx(x) -> str:
    return float(x).hex()


def translate(verts, shift):
    tx, ty, tz = shift
    return [[x + tx, y + ty, z + tz] for x, y, z in verts]


def snapshot(verts):
    return [[hx(p[0]), hx(p[1]), hx(p[2])] for p in verts]


def readback(verts, faces):
    return {"meshes": [{
        "name": "SM_Probe_Main",
        "face_geometry": {
            "vertices": verts,
            "polygons": [list(face) for face in faces],
        },
    }]}


def transcript(mm, rb):
    """Line-for-line decision transcript of closed_shells (methods_metrics.py 612-665).

    Also returns the weld partition and the world-origin triple-product terms the
    decision sums. This is a measurement copy, not a change to the module.
    """
    weld_m = mm.SHELL_WELD_M
    total, closed, comps, closed_comps = 0, 0, 0, 0
    reasons: dict[str, int] = {}
    diag = []
    for m in mm.model_meshes(rb):
        v, t = mm._fan(m)
        if not len(t):
            continue
        total += len(t)
        key = np.round(v / weld_m).astype(np.int64)
        _, remap = np.unique(key, axis=0, return_inverse=True)
        t = remap.reshape(-1)[t]
        keep = (t[:, 0] != t[:, 1]) & (t[:, 1] != t[:, 2]) & (t[:, 0] != t[:, 2])
        if (~keep).any():
            reasons["triangles collapsed by weld"] = reasons.get("triangles collapsed by weld", 0) + int((~keep).sum())
        t_kept = t[keep]
        groups_of = {}
        for idx, k in enumerate(key.tolist()):
            groups_of.setdefault(tuple(int(x) for x in k), []).append(idx)
        partition = tuple(sorted(tuple(sorted(g)) for g in groups_of.values()))
        rep_index = np.unique(remap.reshape(-1), return_index=True)[1]
        p = v[rep_index]
        if len(t_kept):
            a, b, c = p[t_kept[:, 0]], p[t_kept[:, 1]], p[t_kept[:, 2]]
            area2 = np.linalg.norm(np.cross(b - a, c - a), axis=1)
            vol6 = np.einsum("ij,ij->i", a, np.cross(b, c))
        else:
            area2 = np.zeros(0)
            vol6 = np.zeros(0)
        t = t_kept
        groups = mm._components([list(map(int, x)) for x in t]) if len(t) else []
        if len(t):
            d = np.concatenate([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]])
            e = np.sort(d, axis=1)
            _, inv, cnt = np.unique(e, axis=0, return_inverse=True, return_counts=True)
            inv = inv.reshape(-1)
            fwd = np.zeros(len(cnt), int)
            np.add.at(fwd, inv, (d[:, 0] < d[:, 1]).astype(int))
            per_tri = lambda x: x[inv].reshape(3, -1).all(axis=0)  # noqa: E731
            edge_two, edge_opp = per_tri(cnt == 2), per_tri(fwd == 1)
            _, tinv, tcnt = np.unique(np.sort(t, axis=1), axis=0, return_inverse=True, return_counts=True)
            dup = tcnt[tinv.reshape(-1)] > 1
        else:
            edge_two = edge_opp = dup = np.zeros(0, dtype=bool)
        comp_rows = []
        for g in groups:
            comps += 1
            g = np.asarray(g)
            if not len(t) or not edge_two[g].all():
                why = "edge not shared by exactly two triangles"
            elif dup[g].any():
                why = "duplicated triangle (doubled sheet)"
            elif not edge_opp[g].all():
                why = "inconsistent winding"
            elif (area2[g] <= weld_m ** 2).any():
                why = "zero-area triangle"
            elif abs(vol6[g].sum()) / 6.0 <= weld_m ** 3:
                why = "zero enclosed volume"
            else:
                closed_comps += 1
                closed += len(g)
                why = None
            if why:
                reasons[why] = reasons.get(why, 0) + 1
            comp_rows.append({
                "why": why,
                "n_tri": int(len(g)),
                "vol6_sum_numpy": None if not len(t) else float(vol6[g].sum()),
                "vol6_sum_fsum": None if not len(t) else float(math.fsum(float(x) for x in vol6[g])),
                "vol6_terms_hex": [] if not len(t) else [hx(x) for x in vol6[g]],
                "area2_min": None if not len(t) else float(area2[g].min()),
            })
        diag.append({
            "partition": partition,
            "rep_index": [int(i) for i in rep_index],
            "rep_hex": [[hx(x) for x in row] for row in p],
            "n_keys": int(len(partition)),
            "n_verts": int(len(v)),
            "collapsed": int((~keep).sum()),
            "components": comp_rows,
            "key0": [int(x) for x in key[0]],
        })
    if not total:
        public = {"closed_shell_share": None, "components": comps, "closed_components": closed_comps,
                  "open_reasons": reasons, "reason": "no model triangle"}
    else:
        public = {"closed_shell_share": round(closed / total, 5), "components": comps,
                  "closed_components": closed_comps, "open_reasons": dict(sorted(reasons.items())),
                  "weld_m": weld_m, "reason": None}
    return public, diag


def triple(a, b, c) -> float:
    return (a[0] * (b[1] * c[2] - b[2] * c[1])
            + a[1] * (b[2] * c[0] - b[0] * c[2])
            + a[2] * (b[0] * c[1] - b[1] * c[0]))


def recentered_from_mesh(mm, rb, origin):
    """Independent volume: subtract vertex 0, pure-Python triple product, math.fsum.

    Triangles and representatives follow the same weld indexing as closed_shells.
    """
    weld_m = mm.SHELL_WELD_M
    out = []
    ox, oy, oz = (float(origin[0]), float(origin[1]), float(origin[2]))
    for m in mm.model_meshes(rb):
        v, t = mm._fan(m)
        key = np.round(v / weld_m).astype(np.int64)
        _, remap = np.unique(key, axis=0, return_inverse=True)
        t = remap.reshape(-1)[t]
        keep = (t[:, 0] != t[:, 1]) & (t[:, 1] != t[:, 2]) & (t[:, 0] != t[:, 2])
        t = t[keep]
        rep_index = np.unique(remap.reshape(-1), return_index=True)[1]
        p = v[rep_index]
        terms = []
        for tri in t:
            a = p[int(tri[0])]
            b = p[int(tri[1])]
            c = p[int(tri[2])]
            aa = (float(a[0]) - ox, float(a[1]) - oy, float(a[2]) - oz)
            bb = (float(b[0]) - ox, float(b[1]) - oy, float(b[2]) - oz)
            cc = (float(c[0]) - ox, float(c[1]) - oy, float(c[2]) - oz)
            terms.append(triple(aa, bb, cc))
        total6 = math.fsum(terms)
        out.append({"vol6_fsum": total6, "volume": total6 / 6.0, "n": len(terms),
                    "terms_hex": [hx(x) for x in terms]})
    return out


def public_view(d):
    reasons = d.get("open_reasons") or {}
    return {
        "closed_shell_share": d.get("closed_shell_share"),
        "components": d.get("components"),
        "closed_components": d.get("closed_components"),
        "open_reasons": dict(sorted(reasons.items())),
        "weld_m": d.get("weld_m"),
        "reason": d.get("reason"),
    }


def canon_public(d):
    view = public_view(d)
    if view["weld_m"] is not None:
        view["weld_m_hex"] = hx(view["weld_m"])
        view["weld_m"] = hx(view["weld_m"])
    if isinstance(view["closed_shell_share"], float):
        view["closed_shell_share_hex"] = hx(view["closed_shell_share"])
        view["closed_shell_share"] = hx(view["closed_shell_share"])
    return view


def measure(mm):
    rows = []
    for name, variant, local, faces, analytic, applies in CASES:
        for tname, shift in TRANSLATIONS:
            verts = translate(local, shift)
            before = snapshot(verts)
            rb = readback(verts, faces)
            rb_pub = copy.deepcopy(rb)
            rb_tr = copy.deepcopy(rb)
            pub = mm.closed_shells(rb_pub)
            copied, diag = transcript(mm, rb_tr)
            if canon_public(pub) != canon_public(copied):
                raise SystemExit(
                    "transcript diverged from public closed_shells: "
                    + json.dumps({"public": canon_public(pub), "transcript": canon_public(copied),
                                  "case": name, "variant": variant, "translation": tname})
                )
            after_pub = snapshot(rb_pub["meshes"][0]["face_geometry"]["vertices"])
            after_tr = snapshot(rb_tr["meshes"][0]["face_geometry"]["vertices"])
            origin = verts[0]
            recent = recentered_from_mesh(mm, copy.deepcopy(rb), origin)
            world6 = diag[0]["components"][0]["vol6_sum_numpy"] if diag and diag[0]["components"] else None
            world6_f = diag[0]["components"][0]["vol6_sum_fsum"] if diag and diag[0]["components"] else None
            world = None if world6 is None else world6 / 6.0
            world_f = None if world6_f is None else world6_f / 6.0
            rec = recent[0]["volume"] if recent else None
            add_exact = all(
                hx(local[i][k] + shift[k]) == hx(verts[i][k]) and hx(verts[i][k] - shift[k]) == hx(local[i][k])
                for i in range(len(local)) for k in range(3)
            )
            rows.append({
                "case": name,
                "variant": variant,
                "translation": tname,
                "shift": list(shift),
                "analytic_abs": analytic,
                "analytic_abs_hex": hx(analytic),
                "analytic_applies": applies,
                "public": canon_public(pub),
                "public_raw_share": None if pub["closed_shell_share"] is None else pub["closed_shell_share"],
                "inputs_unchanged": before == after_pub == after_tr,
                "translation_add_and_sub_exact": add_exact,
                "partition": [list(g) for g in diag[0]["partition"]],
                "rep_index": diag[0]["rep_index"],
                "n_keys": diag[0]["n_keys"],
                "n_verts": diag[0]["n_verts"],
                "collapsed": diag[0]["collapsed"],
                "key0": diag[0]["key0"],
                "world_volume": world,
                "world_volume_hex": None if world is None else hx(world),
                "world_vol6_numpy_hex": None if world6 is None else hx(world6),
                "world_vol6_fsum_hex": None if world6_f is None else hx(world6_f),
                "world_fsum_volume_hex": None if world_f is None else hx(world_f),
                "world_terms_hex": diag[0]["components"][0]["vol6_terms_hex"] if diag[0]["components"] else [],
                "area2_min": diag[0]["components"][0]["area2_min"] if diag[0]["components"] else None,
                "area2_min_hex": None if not diag[0]["components"] or diag[0]["components"][0]["area2_min"] is None
                else hx(diag[0]["components"][0]["area2_min"]),
                "recentered_volume": rec,
                "recentered_volume_hex": None if rec is None else hx(rec),
                "recentered_terms_hex": recent[0]["terms_hex"] if recent else [],
                "why": diag[0]["components"][0]["why"] if diag[0]["components"] else None,
                "n_components_diag": len(diag[0]["components"]),
            })
    # grouping / verdict relative to identity, same case+variant
    by = {(r["case"], r["variant"], r["translation"]): r for r in rows}
    for r in rows:
        base = by[(r["case"], r["variant"], "identity")]
        r["grouping_changed_vs_identity"] = r["partition"] != base["partition"] or r["rep_index"] != base["rep_index"]
        r["verdict_changed_vs_identity"] = r["public"] != base["public"]
        r["n_keys_changed"] = r["n_keys"] != base["n_keys"]
    return rows


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def run_once(n: int):
    mm = load_metrics()
    rows = measure(mm)
    payload = {
        "run": n,
        "python": sys.version,
        "numpy": np.__version__,
        "metrics_sha256": file_sha256(METRICS),
        "shell_weld_m_hex": hx(mm.SHELL_WELD_M),
        "rows": rows,
    }
    (OUT / f"run{n}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def compare():
    loaded = [json.loads((OUT / f"run{n}.json").read_text(encoding="utf-8")) for n in (1, 2, 3)]
    bodies = [p["rows"] for p in loaded]
    same = bodies[0] == bodies[1] == bodies[2]
    versions = [{"python": p["python"], "numpy": p["numpy"], "metrics_sha256": p["metrics_sha256"],
                 "shell_weld_m_hex": p["shell_weld_m_hex"]} for p in loaded]
    summary = {"runs_identical": same, "versions": versions, "n_rows": len(bodies[0])}
    if not same:
        summary["note"] = "row payloads differ across processes"
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if "--once" in sys.argv:
        n = int(sys.argv[sys.argv.index("--once") + 1])
        run_once(n)
        return
    for n in (1, 2, 3):
        subprocess.run([sys.executable, str(Path(__file__).resolve()), "--once", str(n)], check=True)
    compare()


if __name__ == "__main__":
    main()
```
