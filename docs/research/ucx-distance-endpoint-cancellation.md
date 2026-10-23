# UCX distance: which endpoint reconstructions change a strict boundary verdict?

Status: research (report-only, synthetic metric evidence; `delivery_passed=false`).

## Summary

PR #501 pins the strict `< 0.2 mm` too-close boundary (req 2.13.4, D162) but records that the
exact `TOUCH_M` reading is unreachable: two directly-placed unit boxes whose nearest X faces sit
at 0 and 0.0002 measure `0.00019999999999997797` instead of `0.0002`, so the strict rule classifies
`touch`, not `below_band`. This report isolates the arithmetic: the witness is produced by exactly
one reconstruction site — `_closest_on_segment`'s `t=1` return `a + (b-a)` inside the
vertex-triangle edge fallback — and only in one direction (the diagonal edge from the `1.0+0.0002`
corner toward the `0.0002` corner). An experiment-local substitution that returns the literal
endpoint when the already-clamped parameter equals 0 or 1 removes the witness for g=0.0002
(`touch` → `below_band`, gap exactly `0.0002`) and changes nothing for g ∈ {0, 0.000199, 0.000201}.
The same substitution on `segment_segment_distance` (site 2) changes nothing for this corpus. The
"one-ulp" wording in #501 is corrected here: the error is ~0.099 ulp at the 1.0-magnitude
coordinate where the cancellation happens, which is ~813 ulps at the 0.0002-magnitude gap itself.

## Findings

### F1 — the witness comes from one reconstruction site, in one direction

Source: `src/twinqa/geometry/ucx_audit.py` blob `d179fcbc6c5804dafbef75f335b85c837bbe480a`
(identical in worktree HEAD `c3ac83c` and `origin/main` `ed4d774`). Verified by running the code.

`surface_distance` (lines 265-279) takes the minimum over vertex-triangle distances (both ways) and
edge-edge distances. For #501's corpus the minimum is always a **vertex-triangle** pair: left-box
vertex `(0,0,0)` against a right-box triangle whose closest feature is a diagonal edge through
corner `(g,0,0)`. `point_triangle_distance` (227-237) rejects the plane projection (the vertex is
outside the triangle) and falls back to

```python
min(_norm(_sub(p, _closest_on_segment(p, x, y))) for x, y in ((a, b), (b, c), (c, a)))
```

`_closest_on_segment` (220-224):

```python
ab = _sub(b, a); den = _dot(ab, ab)
t = 0.0 if den < 1e-18 else max(0.0, min(1.0, _dot(_sub(p, a), ab) / den))
return (a[0] + ab[0] * t, a[1] + ab[1] * t, a[2] + ab[2] * t)
```

For the witness edge the call is `_closest_on_segment((0,0,0), (1.0002,0,1), (0.0002,0,0))` (the
triangle-4 edge `(5,0)`, a diagonal from `(1+g,0,1)` to `(g,0,0)`). The projection clamps `t` to
`1.0`, and the X coordinate is rebuilt as `(1.0 + 0.0002) + (0.0002 - 1.0002)` = `(1.0+0.0002) - 1.0`
= `0.00019999999999997797`. Measured directly (probe, not a production helper):

```
(1.0 + 0.0002) - 1.0            -> 0.00019999999999997797   # the witness, != 0.0002
1.0002 + (0.0002 - 1.0002)      -> 0.00019999999999997797   # a+(b-a), a=1.0002, b=0.0002: subtracts 1.0
1.0 + ((1.0+0.0002) - 1.0)      -> 1.0002                    # a=1.0, b=1.0002: rounds back up, exact
```

The cancellation is **direction-dependent**: rebuilding `a + (b-a)` loses the endpoint only when the
segment is directed *from* `1.0002` *toward* `0.0002`, because then `b - a = 0.0002 - 1.0002 = -1.0`
exactly and `a + (b-a) = 1.0002 - 1.0` subtracts the integer `1.0`. Reversing the segment
(`_closest_on_segment(p, (0.0002,0,0), (1.0002,0,1))`) clamps `t=0` and returns
`a + ab*0 = (0.0002,0,0)` exactly. An axis-aligned X-edge from `1.0` to `1.0002` does **not**
reproduce the witness: `1.0 + (1.0002 - 1.0)` rounds back up to `1.0002`. This is why the pinned
`WITNESS_0002` is the diagonal-edge `(1.0 + 0.0002) - 1.0`, not a plain axis-aligned round-trip.

### F2 — endpoint preservation flips exactly one corpus verdict, and only via site 1

Experiment-local substitution (never committed): a copy of `_closest_on_segment` that returns the
literal `a` when `t <= 0`, the literal `b` when `t >= 1`, and otherwise interpolates identically,
and an analogous copy of `segment_segment_distance` returning `p1`/`q1`/`p2`/`q2` when `s`/`t` is 0
or 1. Result for `boundary_pair(g)` (verified by probe):

| g | baseline class / gap | preserve `_closest_on_segment` | preserve `segment_segment_distance` | both |
|---|---|---|---|---|
| 0.0 | touch / 0.0 | touch / 0.0 | touch / 0.0 | touch / 0.0 |
| 0.000199 | touch / 0.000199 | touch / 0.000199 | touch / 0.000199 | touch / 0.000199 |
| 0.0002 | **touch / 0.00019999999999997797** | **below_band / 0.0002** | touch / 0.00019999999999997797 | below_band / 0.0002 |
| 0.000201 | below_band / 0.000201 | below_band / 0.000201 | below_band / 0.000201 | below_band / 0.000201 |

`segment_segment_distance` (site 2, lines 240-262, reconstruction `c1 = p1 + d1*s`,
`c2 = p2 + d2*t` at 260-261) carries the **same** `p + d*s` pattern but is never the argmin for this
corpus, so preserving its endpoints changes nothing here. Its endpoint cancellation is therefore
**unmeasured in this corpus** (no edge-edge closest pair with a clamped endpoint at `1.0+small`).

### F3 — the "one-ulp" wording is about magnitude 1.0, not the gap

Measured numbers (probe, `math.ulp`):

```
ulp(1.0)      = 2.220446049250313e-16   (2^-52)
ulp(0.0002)   = 2.710505431213761e-20   (2^-65)   # same for 0.000199 and 0.000201
witness       = 0.00019999999999997797
abs error     = -2.2036409155767878e-17 m
error / ulp(1.0)     = -0.0992   (~ one tenth of one ulp at magnitude 1.0)
error / ulp(0.0002)  = -813.0    (813 ulps at the gap's own magnitude)
```

#501's "1 ulp below `TOUCH_M`" is imprecise. The absolute error is one-tenth of an ulp of the
**1.0-magnitude coordinate** where the `(1.0+0.0002)-1.0` subtraction happens; expressed at the
**gap's own magnitude** (0.0002) it is ~813 ulps. This report states both; it does not edit #501 or
historical evidence.

### F4 — remaining witnesses and input immutability

- Endpoint preservation is by-design silent for **interior** projections (`t` strictly in `(0,1)`):
  the interpolated `a + ab*t` is unchanged, so it fixes nothing an interior projection rounds away.
  A probe (`_closest_on_segment(mid, (0,0,0), (0.0002,0,0))`) returns bit-identical `0.0001` under
  baseline and preserve.
- The `point_triangle_distance` plane-projection path (`q = p - n*t`, line 232) has its own
  reconstruction arithmetic; it is not the witness here (the vertex is outside the triangle) and is
  not addressed by endpoint preservation.
- `segment_segment_distance` site-2 cancellation is structurally present but unmeasured in this
  corpus (F2).
- Inputs are not mutated: `pair_relation`/`pair_findings` only read `(verts, tris)`; #501's
  `test_findings_carry_req_2134_names_and_do_not_mutate_hulls` already asserts hull arrays are
  unchanged, and the experiment-local substitutions add no mutation.

## How it applies to this repository

- `src/twinqa/geometry/ucx_audit.py` — the two reconstruction sites:
  - `_closest_on_segment` (lines 220-224), called by `point_triangle_distance` (line 237) — the
    witness source.
  - `segment_segment_distance` (lines 240-262, reconstruction 260-261) — same pattern, not the
    argmin here.
- `tests/qa/test_ucx_too_close_boundary.py` (added by #501, blob `dd33d804693e0b542231d6b98d9c6044592364ec`,
  present only in `origin/main`, read via `git show`; not in this worktree at `c3ac83c`): pins
  `WITNESS_0002 = 0.00019999999999997797  # == 1.0 + 0.0002 - 1.0` and the `touch` verdict for
  g=0.0002. This report does not edit it.
- `docs/domain/areas/ucx.md` R09/R10 and `docs/domain/geometry.md` — the strict `< 0.2 mm` too-close
  rule (req 2.13.4, D162) whose exact boundary is the subject here.

Pinned source SHAs:
- `src/twinqa/geometry/ucx_audit.py` blob `d179fcbc6c5804dafbef75f335b85c837bbe480a`.
- `tests/qa/test_ucx_too_close_boundary.py` blob `dd33d804693e0b542231d6b98d9c6044592364ec`.
- `origin/main` = `ed4d77452a13ec0ad31bec06bfa830a7b0d6f5f1` (merge of #501); worktree HEAD =
  `c3ac83c2d6962c87147910986be1f94efdc18c6c` (merge of #500). PR #501 = `c379d6c` (test-only; does
  not change `ucx_audit.py`, confirmed by the identical blob SHA).

## Self-contained reproduction

```python
import math, sys
sys.path.insert(0, "<repo>/src")          # the pilot checkout
import twinqa.geometry.ucx_audit as ua

BOX_TRIS = [(0,1,3),(0,3,2),(4,6,7),(4,7,5),(0,4,5),(0,5,1),
            (2,3,7),(2,7,6),(0,2,6),(0,6,4),(1,5,7),(1,7,3)]
def box(lo, hi):
    return [(hi[0] if i & 4 else lo[0], hi[1] if i & 2 else lo[1], hi[2] if i & 1 else lo[2])
            for i in range(8)], list(BOX_TRIS)
def boundary_pair(g):
    return box((-1.0, 0.0, 0.0), (0.0, 1.0, 1.0)), box((g, 0.0, 0.0), (1.0 + g, 1.0, 1.0))

# baseline
a, b = boundary_pair(0.0002)
print(ua.pair_relation(a, b))            # ('touch', 0.00019999999999997797, 0.0)

# witness provenance (diagonal edge (5,0) of the right box)
c, a0 = (1.0 + 0.0002, 0.0, 1.0), (0.0002, 0.0, 0.0)
print(ua._closest_on_segment((0.0, 0.0, 0.0), c, a0))   # (0.00019999999999997797, 0.0, 0.0)
print((1.0 + 0.0002) - 1.0)                            # 0.00019999999999997797

# experiment-local endpoint-preserving substitute (never committed)
def _closest_preserve(p, a, b):
    ab = ua._sub(b, a); den = ua._dot(ab, ab)
    if den < 1e-18: return a
    t = ua._dot(ua._sub(p, a), ab) / den
    if t <= 0.0: return a
    if t >= 1.0: return b
    return (a[0] + ab[0] * t, a[1] + ab[1] * t, a[2] + ab[2] * t)

ua._closest_on_segment = _closest_preserve
print(ua.pair_relation(a, b))            # ('below_band', 0.0002, 0.0)
```

Concrete input → expected output pairs (oracle = literal stored value / analytic axis gap, not a
production helper):

| input | expected output |
|---|---|
| `_closest_on_segment((0,0,0), (1.0002,0,1), (0.0002,0,0))` (preserve) | `(0.0002,0,0)` — the exact stored endpoint |
| `_closest_on_segment(mid, (0,0,0), (0.0002,0,0))` (interior `t≈0.5`) | `(0.0001,0,0)` — unchanged interpolation |
| `boundary_pair(0.0)` → `pair_relation` | `touch`, gap `0.0` — unchanged |
| `boundary_pair(0.0002)` → `pair_relation` (preserve site 1) | `below_band`, gap `0.0002` |
| `segment_segment_distance` edge-edge cancellation | **unmeasured** in this corpus (no edge-edge argmin) |

## Proposed next tasks

### 1. Repair: return the literal endpoint in `_closest_on_segment` when the clamped parameter is 0 or 1, and revise #501's pinned witness — S

Scope: change `_closest_on_segment` (and, in the same coordinated card, `segment_segment_distance`'s
`c1`/`c2` reconstruction) to return the original endpoint instead of `a + ab*t` when the already
clamped parameter equals 0 or 1; no epsilon, threshold, SAT or classification-policy change. Update
`tests/qa/test_ucx_too_close_boundary.py` so g=0.0002 pins `below_band` / gap `0.0002` (drop the
`WITNESS_0002` special case) and add the endpoint-preservation and interior-invariance assertions
above. Expected: `boundary_pair(0.0002)` → `below_band`; `boundary_pair(g)` for g ∈ {0, 0.000199,
0.000201} unchanged; `_closest_on_segment` at a stored endpoint returns the identical coordinate.
This is a behaviour-changing repair and a revision of #501's pinned characterization, so it must be
a separate coordinated card after review, not part of this report. Value high / effort S.
Advances #149.

### 2. Extend the arithmetic audit to site 2 (`segment_segment_distance`) and the plane-projection path — S

Scope: characterise the same clamped-parameter cancellation in `segment_segment_distance` with a
crafted edge-edge corpus whose closest pair is a clamped endpoint at `1.0+small` (currently
unmeasured), and in `point_triangle_distance`'s `q = p - n*t` plane projection, recording absolute
errors in metres and ulps at the relevant magnitude. Expected: an edge-edge closest pair with the
same `(1.0+0.0002)-1.0` pattern reproduces the witness; interior and axis-aligned cases stay exact.
Deliverable is a report-only extension; any repair is deferred to the coordinated card above.
Value medium / effort S. Advances #149.

## Open questions for the user

1. The card asks to compare "separately and together" — both substitutions together equal site 1
   alone for this corpus. Is it acceptable to state that site 2's contribution is *unmeasured here*
   rather than constructing an out-of-corpus edge-edge witness for it (see proposal 2)?
2. Should the behaviour-changing repair (proposal 1) preserve endpoints at *both* sites in one card,
   or land site 1 first and site 2 after proposal 2's characterization?
