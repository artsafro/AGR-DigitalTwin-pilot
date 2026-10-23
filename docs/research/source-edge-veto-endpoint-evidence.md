# Rejected edge veto: what a small intersection parameter proves

`delivery_passed=false`. Synthetic controls only. This note does not adopt a veto, choose an epsilon, or classify the AC08 intersections.

Pins from the card. Git was not run, so those commits were not re-resolved. The bytes actually read are pinned by sha256:

| bytes | sha256 | card pin |
|---|---|---|
| `C:/x/t_e91744e1/hyp-638.md` | `3734f68aeb69a7a9cd855dc18b2da18ce9e5db4bd8999706cdd103c565e4d76c` | `origin/experiment/hyp-638` @ `141b757b0b6047f759ec30a54b4c4c970348cf0b` |
| `C:/x/t_e91744e1/run_hyp638.py` | `0895847b35d41f39c4161fd38293de6c2806b00fcb366111dda7bfffc72f6f13` | same SHA |
| `docs/research/source-face-concave-containment.md` (this worktree) | `acdd5d897d4aa29f8fa9412bcc1d1cdbd12db884a11fb70724104da3acb56a7e` | `main` @ `7d67db669fc63ffd9c240b8f5086cea2cff9cf0e` |
| `jobs/TEC26-OKS/scripts/qa_packages.py` (this worktree) | `87dd188c0b577cbae82c6fc1048fbbea7da8d544c8f4f88f2b1e6487a9e75269` | read with the concave report's main pin; not executed |
| executed probe `C:/x/t_e91744e1/probe_edge_veto.py` | `b05b2d8621d6582ac0bd228bd191ab9fbd546aad871a794701f08aef8d771014` | this run |

The concave report's own header still records an earlier pin, `45a35a2dca43ba4880b2a7f2359f376f2d4884fc`. That is that note's pin, separate from the card pin above.

## Summary

A strict proper-edge test fires when both segment parameters lie in the open interval (0, 1).
On this four-case matrix the dimensionless margin and the metre distance are different quantities.
Declared margin `1/100000000` is a real crossing at `1/1000` m, `1` m and `1000` m as the figure is scaled.
The same `1` m distance is margin `1/100000000` on a `100000000` m edge and margin `1/2` on a `2` m edge.
Absolute margin `1/100000000` is also a miss just outside the segment, and the float formula leaves it unvetoed.
An exact endpoint (`t=0`, `u=1/2`) becomes a binary64 veto at scale 1: `t` repr `2.775557561562892e-17`, vertex-to-line distance `2.4204707994160913e-16` m.
That class change is the decimal-to-binary64 conversion; the float division leaves the class `proper`. The same endpoint stays unvetoed at scales `0.001` and `1000`.
Hypothesis #638 records real-arm margins in `[5.5e-10, 6.2e-7]` and calls them endpoint noise. Those rows have no edge length and no exact rational on the stored floats. This matrix leaves the AC08 rows unclassified.

## Findings

Legend. **MEASURED** means a number printed by the probe or written in `hyp-638.md`. **INFERRED** means a reading of repository source this probe did not execute, or a conclusion that goes past those numbers. The probe is stdlib Python `3.14.7`, `mant_dig 53` (MEASURED). It does not import NumPy. The driver evaluates the same arithmetic on NumPy `float64` scalars (INFERRED: the scalar operations match; that identity was not executed).

### F1. What `t` and `u` are

READ from `run_hyp638.py` lines 39-60, and MEASURED by executing that copy. For a triangle edge from `a` to `b` and a polygon edge from `c` to `d`, with `r = b-a`, `s = d-c` and `ca = c-a`:

```
den = r.x * s.y - r.y * s.x
t   = (ca.x * s.y - ca.y * s.x) / den
u   = (ca.x * r.y - ca.y * r.x) / den
```

`t` is the parameter along the triangle edge. `u` is the parameter along the polygon edge. The point on the triangle edge is `a + t*r`. The veto keeps a pair only when `den != 0` and `0 < t < 1` and `0 < u < 1`. `den == 0` is skipped, including a zero-length edge and a parallel pair. There is no epsilon. The open margin used below is `min(t, 1-t, u, 1-u)`. It is positive exactly on a veto pair.

The driver calls this on the already projected plane: `qq[:, keep]` against `p2`, and `p2` is `p[:, keep]` from `_poly_geo` (READ, `run_hyp638.py` line 79 and `qa_packages.py` lines 73-74; the production matcher was not executed). `keep` drops the axis of the largest absolute Newell component. The first index wins a tie, which is `np.argmax`'s rule. MEASURED on two unit squares, where the dominant axis was unique so the tie was not used: an XY square gives normal `(0, 0, 2)`, drop axis 2, `keep = [0, 1]`. An XZ square gives normal `(0, -2, 0)`, drop axis 1, `keep = [0, 2]`. The matrix below is already in that 2D plane.

`qa_packages.match_source_faces` (lines 95-116) tests corners, a plane residual and a strict centroid. It does not compute `t` or `u` (INFERRED: source read, function not called). The veto exists only in the experiment copy.

### F2. The matrix

Base coordinates are decimal strings, metres at scale 1, before a fixed translation. Scales are the decimal strings `0.001`, `1` and `1000`, labelled `1e-3`, `1` and `1e3`. Translation is `0.1`, `0.2`, applied in `Decimal` and then converted once with `float`. This is not the AC08 shift. `hyp-638.md` records that shift as `[33.953392, 0.113387, 0.0]` (MEASURED as a quoted result in that report; not an input to this probe).

`float("0.001")` differs from `1/1000` by `2.081668e-20`. `float("0.1")` differs from `1/10` by `5.551115e-18` (MEASURED). Those literals are not multiplied in binary64. Each final coordinate is converted once.

Along-edge distance is `min(|t|, |1-t|) * (edge length)` from the line intersection to the nearest endpoint of that edge. `dist_tri` uses the triangle edge. `dist_poly` uses the polygon edge. `perp` is the distance from the triangle edge's start vertex to the infinite line of the polygon edge. `quant` is the largest absolute coordinate error of the binary64 conversion, in metres. `dquant_t` is exact `t` on the float `as_integer_ratio` values minus exact `t` on the declared decimals (input quantization, seen in the parameter). `arith_t` is the binary64 formula's `t`, read back through `as_integer_ratio`, minus exact `t` on those same float inputs (arithmetic error of the division formula).

Declared classes and parameters were identical at all three scales (MEASURED, `ASSERT_OK`):

| id | geometry at scale 1, before translation | declared primary result |
|---|---|---|
| `a_endpoint` | triangle `(2,1) (2,5) (3,5)`, polygon `(0,0) (4,2) (4,0)`. Vertex `(2,1)` lies on the first polygon edge. | `t=0`, `u=1/2`, class `endpoint`, margin `0`, `dist_tri=0`. Signs of `(den, t, u, 1-t, 1-u)` are `(-1, 0, 1, 1, 1)`. The other edge into that vertex is declared `t=1`, `u=1/2`, also `endpoint` (printed on the scale-1 veto row). No declared proper pair. |
| `b_near_cross` | triangle `(0,0) (100000000,0) (0,-10)`, polygon `(1,-1) (1,1) (2,1) (2,-1)`. | `t=1/100000000`, `u=1/2`, class `proper`, margin `1/100000000`. Signs all `+1`. `dist_tri` equals the scale (`1/1000`, `1`, `1000`). A second declared proper pair on the same triangle edge has `t=1/50000000`, `u=1/2`, and along-edge distance `2` at scale 1. |
| `c_near_miss` | triangle `(0,0) (4,0) (2,-2)`. Polygon is the rectangle `(2, 4e-8) (6, 4e-8) (6, 4+4e-8) (2, 4+4e-8)`. | `t=1/2`, `u=100000001/100000000`, class `miss`, margin `-1/100000000`. Sign of `1-u` is `-1`. `dist_poly` is the overshoot: `1/25000000000`, `1/25000000`, `1/25000`. No declared proper pair. |
| `d_clean` | triangle `(0,0) (2,0) (1,-1)`, polygon `(1,-1) (1,1) (3,1) (3,-1)`. | `t=u=1/2`, class `proper`, margin `1/2`. `dist_tri` equals the scale. One declared proper pair. |

Parallel pairs are skipped. MEASURED examples: `b_near_cross` skips `(0,1)`, `(0,3)`, `(2,0)`, `(2,2)` at every scale, and none of those pairs appear in the veto list.

### F3. The same margin is more than one distance

MEASURED from the declared oracle, which is exact on the decimal strings.

Same margin, three distances. Case `b` keeps margin `1/100000000` at every scale. The triangle edge that owns that minimum has length `100000`, `100000000` and `100000000000`. The along-edge distance is `1/1000` m, `1` m and `1000` m. The vertex-to-line distance `perp_decl` equals those three numbers, because the edges are perpendicular and the crossing is that far from the start vertex.

Same distance, two margins. At scale 1, case `b` and case `d` both have `dist_tri = 1`. The margins are `1/100000000` and `1/2`.

Same absolute margin, opposite predicates. At every scale, case `c` has margin `-1/100000000`. At scale 1 the overshoot `dist_poly` is `1/25000000` m, which is `4e-8` m. The binary64 formula classifies every `c` row as `miss` and vetoes none.

Wrong edge. Multiplying case `b`'s margin by the polygon-edge length yields `1/50000000000`, `1/50000000` and `1/50000` m. At scale 1 that product is `2e-8` m. The triangle-edge distance at that same row is `1` m. The margin is the minimum of four numbers. The metres belong to the edge that supplied the minimum. In the published #638 examples the small number is `t` or `1-t` and `u` is about one half (`7.69e-09` with `0.5176`, `0.99999994` and `5.56e-08` with `0.5176`, `5.56e-08` with `0.4824`). Those printed `u` values put the small factor on the triangle edge. The table does not give that edge's length, so the product is not determined (MEASURED absence: the columns are tri, owners, source, edge indices, `t`, `u`).

On a fixed edge, the distance tracks the parameter. Case `b`'s second hit at scale 1 has `t=1/50000000` and distance `2` m, twice the primary `t` and twice the primary distance, on the same edge of length `100000000`.

### F4. Quantization and arithmetic are different errors

MEASURED. For cases `b`, `c` and `d`, declared class, exact-on-float class and binary64 class agree at all three scales. `b` and `d` veto. `c` does not. At scale 1, case `b` has `dquant_t=1.428714e-24` and `arith_t=-1.219488e-24`. The binary64 `t` repr is `1e-08`. The `1` m crossing remains a crossing after both errors. At scale `1e-3` the binary64 `t` repr is `1.000000000000001e-08`, still a veto.

Case `a` separates the two errors.

| scale | declared | exact on the float coordinates | binary64 formula | veto | what moved the class |
|---|---|---|---|---|---|
| `1e-3` | `endpoint`, `t=0` | `miss` | `miss`, `t` repr `-8.470329472543077e-16` | false | quantization (`dquant_t=-8.673617e-16`). Arithmetic does not change the class (`arith_t=2.032879e-17`). `perp` on the float inputs is `3.1031676915590999e-18` m. |
| `1` | `endpoint`, `t=0`, `u=1/2` | `proper`, margin `6.765422e-17` | `proper`, `t` repr `2.775557561562892e-17`, `u` repr `0.5000000000000001` | true | quantization (`dquant_t=6.765422e-17`, equal to that exact-on-float margin). Arithmetic does not change the class (`arith_t=-3.989864e-17`). `perp` on the float inputs is `2.4204707994160913e-16` m. Coordinate `quant` is `3.552714e-16` m. |
| `1e3` | `endpoint`, `t=0` | `miss`, margin `-1.136764e-17` | `endpoint`, `t` repr `-0.0`, `u` repr `0.5` | false | quantization moves the exact predicate off the endpoint. Arithmetic then rounds that tiny negative `t` to `-0.0`, which the strict test treats as an endpoint. Neither class vetoes. `perp` on the float inputs is `4.0670115765573450e-14` m. |

`bin64_t == 2**-55` is false at scale 1 (MEASURED). The repr above is the value to quote.

At scale 1 the float loop also vetoes pair `(2, 0)`: declared `endpoint` with `t=1`, `u=1/2`; exact-on-float `proper`; binary64 `t` repr `0.9999999999999999` and `u` repr `0.5000000000000001`. Two edges that meet at the declared vertex, one parameter at 0 and one at 1, the polygon parameter at `1/2`. That is the shape of the printed #638 row for triangle 32 (two edges, `t` near 0 and near 1, `u` printed `0.5176`). The synthetic margin here is about `1e-16`. The printed AC08 values are about `1e-8`. The shapes match. The magnitudes are different measurements, and the match does not identify the AC08 row.

`den == 0` still never vetoes on the parallel pairs listed above. The scale-1 endpoint veto is a nonzero denominator whose parameters moved into `(0, 1)` when the decimals became binary64.

### F5. What #638 actually records

MEASURED in `hyp-638.md`. Both real arms change `43/386` ordered owner tuples. The report's margin over those vetoes, `min(t, 1-t, u, 1-u)`, lies in `[5.5e-10, 6.2e-7]`. The first three printed rows are triangle 28 (`t=7.69e-09`, `u=0.5176`), triangle 32 (`t=0.99999994` and `5.56e-08`, `u=0.5176`) and triangle 33 (`t=5.56e-08`, `u=0.4824`). Synthetic label errors are 0 on 768 variants. The hypothesis is rejected. The report says an epsilon or a snap would be a new hypothesis.

The same report says every veto is a float-noise endpoint touch and that a vertex lands about `1e-8` of the way across the edge after the pivot shift. That sentence is the report's attribution. The table that supports the run has `t` and `u` and does not have edge lengths, `den`, stored coordinates, or an exact rational predicate. INFERRED from that gap, together with F3 and F4: a margin inside `[5.5e-10, 6.2e-7]` is also what case `b` produces for a crossing `1` m, `0.001` m or `1000` m from the endpoint, and a much smaller positive margin is what binary64 conversion does to case `a` at scale 1. The published band by itself does not establish the noise attribution. This matrix also does not establish the contrary. It contains no short edge and no small `den`, so it does not measure how large a false `t` can become when the intersection is ill-conditioned or the edge is short. The AC08 intersections are not declared wrong or safe here.

The printed `t` values in that table are already rounded. `1 - 0.99999994` is not a substitute for the raw `1-t` the margin aggregate was computed from.

### F6. Raw evidence a rejected edge still needs

A later row can support a float-noise attribution only when the stored numbers, not a shortened decimal reprint, determine both the predicate and the metres. For each rejected pair, the useful record is:

- triangle index, source-polygon index, triangle-edge index, polygon-edge index
- `keep`, and the 2D coordinates actually passed to the formula, as `float.hex` or `as_integer_ratio`
- the 3D coordinates as stored before projection, and the shift as stored (`hyp-638.md` quotes `[33.953392, 0.113387, 0.0]` for that run)
- binary64 `den`, `t`, `u`, and the veto boolean
- exact `den`, `t`, `u` and the class on those `as_integer_ratio` values
- both edge lengths, `dist_tri`, `dist_poly`, and `perp` from the nearby vertex to the source line, all from the exact-on-float parameters
- the open margin, and which of the four terms supplied it
- the other triangle edge incident to the same vertex, when two vetoes share one (the scale-1 pair `(0,0)` and `(2,0)` pattern)
- `den == 0` skips listed separately, so a parallel overlap is not mistaken for a pass of the strict test

For a JSON readback the parsed binary64 is the input. There is no second "declared decimal" unless the pre-round source is retained. Re-printing `7.69e-09` and parsing it again adds another rounding. The exact-on-float oracle is the predicate of the values the veto saw. The coordinate-conversion oracle in this probe exists because the matrix started from decimal strings. On AC08 those two oracles collapse into one unless the unrounded source is kept beside the floats.

## How it applies to this repository

- The live matcher has no edge veto: `jobs/TEC26-OKS/scripts/qa_packages.py`, `match_source_faces` at lines 95-116, projection `keep` in `_poly_geo` at lines 73-74, pivot shift at line 310. INFERRED from the source text. sha256 of the file read is above.
- The rejected candidate is the copy in `C:/x/t_e91744e1/run_hyp638.py`, `_cross` and `_proper_crossings` at lines 39-60, called at line 79. The behaviour of that formula on the matrix is MEASURED.
- The concave-containment note proposed this veto and gave the synthetic crossings #638 then accepted on its synthetic arm: `docs/research/source-face-concave-containment.md`. #638 rejected the same veto on the real AC08 arm (`hyp-638.md`). This note does not put the veto back.
- Package QA still treats containment as corners plus a strict centroid. A margin printed from an experiment log is not yet a length in the package report.

## Proposed next tasks

1. **Freeze the scale witness.** One future stdlib check, not a production change and not an epsilon, feeds case `b` and case `d` at scales `0.001`, `1` and `1000` with translation `(0.1, 0.2)`. Input `b` at scale 1 returns declared `t=1/100000000`, `u=1/2`, class `proper`, `dist_tri=1`, binary64 veto true, binary64 `t` repr `1e-08`. Input `b` at scale `0.001` returns the same declared `t` and class, `dist_tri=1/1000`, binary64 `t` repr `1.000000000000001e-08`, veto true. Input `b` at scale `1000` returns the same declared `t`, `dist_tri=1000`, binary64 `t` repr `1e-08`, veto true. Input `d` at scale 1 returns declared `t=u=1/2`, `dist_tri=1`, margin `1/2`, binary64 veto true. Value: the #638 band stays visibly dimensionless. Effort **S**. `Advances #149`.

2. **Freeze the endpoint and the miss beside that witness.** Same harness, still no production edit. Input `a` at scale 1 returns declared `endpoint` `t=0` `u=1/2`, exact-on-float `proper`, binary64 veto true, binary64 `t` repr `2.775557561562892e-17`, and pair `(2,0)` declared `t=1` `u=1/2` with binary64 `t` repr `0.9999999999999999`. Input `a` at scale `0.001` returns binary64 class `miss`, veto false, `t` repr `-8.470329472543077e-16`. Input `a` at scale `1000` returns exact-on-float `miss`, binary64 class `endpoint` with `t` repr `-0.0`, veto false. Input `c` at scale 1 returns declared `miss`, `u=100000001/100000000`, margin `-1/100000000`, `dist_poly=1/25000000`, binary64 veto false. Value: a positive margin from coordinate conversion and a positive margin from a real crossing stay as two expected rows. Effort **S**. `Advances #149`.

The card named open roadmap issues #426, #425, #371, #352, #349, #298 and #149. `gh` was not run. The source-face matcher is the seam `source-face-concave-containment.md` already links to #149 (NPM/VPM L2 self-checks). The other six are other seams. These two proposals stay on #149.

## Open questions for the user

1. For the 43 vetoes, can a later card attach the field list in F6 to the stored edges and the stored shift, without changing `match_source_faces` and without treating the result as a new threshold?
2. Case `a` at scale 1 shows the two-edge pattern of printed triangle 32 at a margin near `1e-16`, and case `b` shows margin `1e-8` as a `1` m crossing. The matrix has no small-`den` pair. Is one frozen near-parallel angle wanted before those AC08 rows are read, or is F6 on the existing rows the next measurement?

## Reproduction

Command, exit code 0: `python C:\x\t_e91744e1\probe_edge_veto.py`

Executed file sha256 `b05b2d8621d6582ac0bd228bd191ab9fbd546aad871a794701f08aef8d771014`. Listing of that file:

```python
"""Synthetic matrix for a strict proper-edge parameter test.

Copy of the scalar formula in experiments/hyp-638/run_hyp638.py (_cross, _proper_crossings):
strict 0 < t < 1 and 0 < u < 1, den == 0 never vetoes, no epsilon.
Coordinates are decimal strings. Scales "0.001", "1", "1000" and translation
("0.1", "0.2") are applied in Decimal, then converted to binary64 once.

Stdlib only. Not AC08. Not a production veto. delivery_passed is not claimed.

Usage: python probe_edge_veto.py
"""
import math
import sys
from decimal import Decimal, getcontext
from fractions import Fraction

getcontext().prec = 80

TX = Decimal("0.1")
TY = Decimal("0.2")
SCALES = (("1e-3", Decimal("0.001")), ("1", Decimal("1")), ("1e3", Decimal("1000")))

# (id, triangle, polygon, primary (tri_edge, poly_edge))
# Base coordinates are metres at scale 1 before the fixed translation.
CASES = (
    (
        "a_endpoint",
        (("2", "1"), ("2", "5"), ("3", "5")),
        (("0", "0"), ("4", "2"), ("4", "0")),
        (0, 0),
    ),
    (
        "b_near_cross",
        (("0", "0"), ("100000000", "0"), ("0", "-10")),
        (("1", "-1"), ("1", "1"), ("2", "1"), ("2", "-1")),
        (0, 0),
    ),
    (
        "c_near_miss",
        (("0", "0"), ("4", "0"), ("2", "-2")),
        (
            ("2", "0.00000004"),
            ("6", "0.00000004"),
            ("6", "4.00000004"),
            ("2", "4.00000004"),
        ),
        (0, 3),
    ),
    (
        "d_clean",
        (("0", "0"), ("2", "0"), ("1", "-1")),
        (("1", "-1"), ("1", "1"), ("3", "1"), ("3", "-1")),
        (0, 0),
    ),
)


def sign(x):
    if x == 0:
        return 0
    return 1 if x > 0 else -1


def cross(r, s):
    return r[0] * s[1] - r[1] * s[0]


def _cross(r, s):
    """Driver formula. r and s are length-2 binary64 pairs."""
    return r[0] * s[1] - r[1] * s[0]


def _proper_crossings(t2, p2):
    """Copy of run_hyp638.py _proper_crossings. den == 0 is skipped. No epsilon."""
    out = []
    skipped = []
    for i in range(3):
        a, b = t2[i], t2[(i + 1) % 3]
        r = (b[0] - a[0], b[1] - a[1])
        for j in range(len(p2)):
            c, d = p2[j], p2[(j + 1) % len(p2)]
            s = (d[0] - c[0], d[1] - c[1])
            den = _cross(r, s)
            if den == 0.0:
                skipped.append((i, j))
                continue
            ca = (c[0] - a[0], c[1] - a[1])
            t = _cross(ca, s) / den
            u = _cross(ca, r) / den
            if 0.0 < t < 1.0 and 0.0 < u < 1.0:
                out.append((i, j, float(t), float(u)))
    return out, skipped


def classify(t, u, den):
    if den == 0:
        return "parallel"
    if (0 < t < 1) and (0 < u < 1):
        return "proper"
    if (0 <= t <= 1) and (0 <= u <= 1):
        return "endpoint"
    return "miss"


def dec_to_frac(d):
    return Fraction(d)


def sqrt_decimal(fr):
    if fr < 0:
        raise ValueError("negative")
    return (Decimal(fr.numerator) / Decimal(fr.denominator)).sqrt()


def fmt_dist(dist_sq):
    num, den = dist_sq.numerator, dist_sq.denominator
    rn, rd = math.isqrt(num), math.isqrt(den)
    if rn * rn == num and rd * rd == den:
        return str(Fraction(rn, rd))
    return format(sqrt_decimal(dist_sq), ".16e")


def sci(fr):
    if fr == 0:
        return "0"
    return format(Decimal(fr.numerator) / Decimal(fr.denominator), ".6e")


def fmt_param(fr):
    text = str(fr)
    if len(text) <= 48:
        return text
    return sci(fr)


def map_points(pts, scale):
    declared, floats = [], []
    quant = []
    for x, y in pts:
        dx = Decimal(x) * scale + TX
        dy = Decimal(y) * scale + TY
        fx, fy = dec_to_frac(dx), dec_to_frac(dy)
        bx, by = float(dx), float(dy)
        rx, ry = Fraction(*bx.as_integer_ratio()), Fraction(*by.as_integer_ratio())
        declared.append((fx, fy))
        floats.append((bx, by))
        quant.append(abs(rx - fx))
        quant.append(abs(ry - fy))
    return declared, floats, max(quant)


def edge(pts, i):
    return pts[i], pts[(i + 1) % len(pts)]


def exact_pair(a, b, c, d):
    r = (b[0] - a[0], b[1] - a[1])
    s = (d[0] - c[0], d[1] - c[1])
    den = cross(r, s)
    ca = (c[0] - a[0], c[1] - a[1])
    t_num = cross(ca, s)
    u_num = cross(ca, r)
    if den == 0:
        return {
            "den": den, "t": None, "u": None, "t_num": t_num, "u_num": u_num,
            "class": "parallel", "open_margin": None,
            "dist_tri_sq": None, "dist_poly_sq": None,
            "len_tri_sq": r[0] * r[0] + r[1] * r[1],
            "len_poly_sq": s[0] * s[0] + s[1] * s[1],
        }
    t = Fraction(t_num, den)
    u = Fraction(u_num, den)
    len_tri_sq = r[0] * r[0] + r[1] * r[1]
    len_poly_sq = s[0] * s[0] + s[1] * s[1]
    ft = min(abs(t), abs(1 - t))
    fu = min(abs(u), abs(1 - u))
    return {
        "den": den, "t": t, "u": u, "t_num": t_num, "u_num": u_num,
        "class": classify(t, u, den),
        "open_margin": min(t, 1 - t, u, 1 - u),
        "dist_tri_sq": ft * ft * len_tri_sq,
        "dist_poly_sq": fu * fu * len_poly_sq,
        "len_tri_sq": len_tri_sq,
        "len_poly_sq": len_poly_sq,
        "signs": (sign(den), sign(t), sign(u), sign(1 - t), sign(1 - u)),
    }


def float_pair(a, b, c, d):
    r = (b[0] - a[0], b[1] - a[1])
    s = (d[0] - c[0], d[1] - c[1])
    den = _cross(r, s)
    if den == 0.0:
        return {"den": den, "t": None, "u": None, "class": "parallel", "veto": False}
    ca = (c[0] - a[0], c[1] - a[1])
    t = _cross(ca, s) / den
    u = _cross(ca, r) / den
    veto = bool(0.0 < t < 1.0 and 0.0 < u < 1.0)
    return {"den": den, "t": t, "u": u, "class": classify(t, u, den), "veto": veto}


def perp_sq(point, c, d):
    """Squared distance from point to the infinite line through c and d."""
    s = (d[0] - c[0], d[1] - c[1])
    w = (point[0] - c[0], point[1] - c[1])
    den = s[0] * s[0] + s[1] * s[1]
    num = cross(w, s)
    return Fraction(num * num, den)


def keep_axes(verts):
    """Copy of qa_packages._poly_geo keep selection, on binary64 coordinates."""
    n = [0.0, 0.0, 0.0]
    for i, a in enumerate(verts):
        b = verts[(i + 1) % len(verts)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    dom = max(range(3), key=lambda i: (abs(n[i]), -i))
    # np.argmax returns the first maximum. Tie key above prefers the smaller index.
    keep = [i for i in range(3) if i != dom]
    return n, dom, keep


def analyse(case_id, tri_s, poly_s, primary, scale):
    tri_d, tri_f, q_tri = map_points(tri_s, scale)
    poly_d, poly_f, q_poly = map_points(poly_s, scale)
    i, j = primary
    a, b = edge(tri_d, i)
    c, d = edge(poly_d, j)
    declared = exact_pair(a, b, c, d)
    af, bf = edge(tri_f, i)
    cf, df = edge(poly_f, j)
    float_inputs = [
        (Fraction(*p[0].as_integer_ratio()), Fraction(*p[1].as_integer_ratio()))
        for p in (af, bf, cf, df)
    ]
    on_float = exact_pair(float_inputs[0], float_inputs[1], float_inputs[2], float_inputs[3])
    floated = float_pair(af, bf, cf, df)
    vetoes, skipped = _proper_crossings(tri_f, poly_f)
    declared_proper = []
    for ii in range(3):
        aa, bb = edge(tri_d, ii)
        for jj in range(len(poly_d)):
            cc, dd = edge(poly_d, jj)
            row = exact_pair(aa, bb, cc, dd)
            if row["class"] == "proper":
                declared_proper.append((ii, jj, row["t"], row["u"]))
    arith_t = arith_u = None
    if floated["t"] is not None and on_float["t"] is not None:
        arith_t = Fraction(*floated["t"].as_integer_ratio()) - on_float["t"]
        arith_u = Fraction(*floated["u"].as_integer_ratio()) - on_float["u"]
    veto_rows = []
    for ii, jj, bt, bu in vetoes:
        decl = exact_pair(*edge(tri_d, ii), *edge(poly_d, jj))
        fins = [
            (Fraction(*p[0].as_integer_ratio()), Fraction(*p[1].as_integer_ratio()))
            for p in (*edge(tri_f, ii), *edge(poly_f, jj))
        ]
        onf = exact_pair(*fins)
        veto_rows.append((ii, jj, decl["class"], decl["t"], decl["u"], onf["class"], bt, bu))
    return {
        "id": case_id,
        "scale": scale,
        "quant_max": max(q_tri, q_poly),
        "declared": declared,
        "on_float": on_float,
        "float": floated,
        "arith_t": arith_t,
        "arith_u": arith_u,
        "vetoes": vetoes,
        "skipped_den0": skipped,
        "declared_proper": declared_proper,
        "perp_decl_sq": perp_sq(a, c, d),
        "perp_float_sq": perp_sq(float_inputs[0], float_inputs[2], float_inputs[3]),
        "dquant_t": None if on_float["t"] is None else on_float["t"] - declared["t"],
        "dquant_u": None if on_float["u"] is None else on_float["u"] - declared["u"],
        "veto_rows": veto_rows,
    }


def expect_declared(case_id, row):
    d = row["declared"]
    t, u = d["t"], d["u"]
    if case_id == "a_endpoint":
        return d["class"] == "endpoint" and t == 0 and u == Fraction(1, 2) and row["declared_proper"] == []
    if case_id == "b_near_cross":
        pairs = {(ii, jj) for ii, jj, _, _ in row["declared_proper"]}
        return (
            d["class"] == "proper"
            and t == Fraction(1, 100_000_000)
            and u == Fraction(1, 2)
            and pairs == {(0, 0), (0, 2)}
        )
    if case_id == "c_near_miss":
        return (
            d["class"] == "miss"
            and t == Fraction(1, 2)
            and u == 1 + Fraction(1, 100_000_000)
            and row["declared_proper"] == []
        )
    if case_id == "d_clean":
        pairs = {(ii, jj) for ii, jj, _, _ in row["declared_proper"]}
        return d["class"] == "proper" and t == Fraction(1, 2) and u == Fraction(1, 2) and pairs == {(0, 0)}
    return False


def line_for(row, scale_name):
    d, f, g = row["declared"], row["on_float"], row["float"]
    return " ".join(
        [
            f"{row['id']:14}",
            f"{scale_name:5}",
            f"decl={d['class']:8}",
            f"exact_f={f['class']:8}",
            f"bin64={g['class']:8}",
            f"veto={str(g['veto']):5}",
            f"t={fmt_param(d['t'])}",
            f"u={fmt_param(d['u'])}",
            f"margin={fmt_param(d['open_margin'])}",
            f"ft={fmt_param(f['t'])}",
            f"fu={fmt_param(f['u'])}",
            f"fmargin={fmt_param(f['open_margin'])}",
            f"dist_tri={fmt_dist(d['dist_tri_sq'])}",
            f"dist_poly={fmt_dist(d['dist_poly_sq'])}",
            f"len_tri={fmt_dist(d['len_tri_sq'])}",
            f"len_poly={fmt_dist(d['len_poly_sq'])}",
            f"quant={sci(row['quant_max'])}",
            f"dquant_t={sci(row['dquant_t'])}",
            f"dquant_u={sci(row['dquant_u'])}",
            f"arith_t={sci(row['arith_t'])}",
            f"arith_u={sci(row['arith_u'])}",
            f"perp_decl={fmt_dist(row['perp_decl_sq'])}",
            f"perp_on_float={fmt_dist(row['perp_float_sq'])}",
            f"signs_den_t_u_1mt_1mu={d['signs']}",
            f"den={fmt_param(d['den'])}",
            f"bin64_t={g['t']!r}",
            f"bin64_u={g['u']!r}",
            f"vetoes={[(i, j) for i, j, _, _ in row['vetoes']]}",
            f"den0_skip={row['skipped_den0']}",
        ]
    )


def main():
    print("probe_edge_veto")
    print("python", sys.version.replace("\n", " "))
    print("mant_dig", sys.float_info.mant_dig)
    print("translation_declared", str(dec_to_frac(TX)), str(dec_to_frac(TY)))
    scale_q = Fraction(*float(Decimal("0.001")).as_integer_ratio()) - Fraction(1, 1000)
    trans_q = Fraction(*float(Decimal("0.1")).as_integer_ratio()) - Fraction(1, 10)
    print("quant_of_float_0.001_vs_1/1000", sci(scale_q))
    print("quant_of_float_0.1_vs_1/10", sci(trans_q))
    xy = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0))
    xz = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 0.0, 1.0), (0.0, 0.0, 1.0))
    print("keep_xy", keep_axes(xy))
    print("keep_xz", keep_axes(xz))
    print("SUMMARY")
    rows = []
    failures = []
    by_case = {}
    for case_id, tri_s, poly_s, primary in CASES:
        seen_tu = []
        for name, scale in SCALES:
            row = analyse(case_id, tri_s, poly_s, primary, scale)
            rows.append((name, row))
            by_case.setdefault(case_id, []).append(row)
            print(line_for(row, name))
            for ii, jj, dc, dt, du, fc, bt, bu in row["veto_rows"]:
                print(
                    f"VETO {case_id} {name} pair={ii},{jj} decl={dc} t={fmt_param(dt)} u={fmt_param(du)} "
                    f"exact_f={fc} bin64_t={bt!r} bin64_u={bu!r}"
                )
            seen_tu.append((row["declared"]["t"], row["declared"]["u"]))
            if not expect_declared(case_id, row):
                failures.append(
                    f"{case_id} {name} declared {row['declared']['class']} "
                    f"t={row['declared']['t']} u={row['declared']['u']} "
                    f"proper={row['declared_proper']}"
                )
        if len(set(seen_tu)) != 1:
            failures.append(f"{case_id} declared t,u changed across scales: {seen_tu}")
    print("COMPARE")
    b = {n: r for (n, r) in ((name, row) for name, row in rows if row["id"] == "b_near_cross")}
    c = {n: r for (n, r) in ((name, row) for name, row in rows if row["id"] == "c_near_miss")}
    d = {n: r for (n, r) in ((name, row) for name, row in rows if row["id"] == "d_clean")}
    a = {n: r for (n, r) in ((name, row) for name, row in rows if row["id"] == "a_endpoint")}
    for name, _scale in SCALES:
        br, cr = b[name]["declared"], c[name]["declared"]
        print(
            f"same_abs_margin {name} "
            f"b_margin={fmt_param(br['open_margin'])} b_dist_tri={fmt_dist(br['dist_tri_sq'])} "
            f"b_margin_times_poly_len={fmt_dist(br['open_margin'] * br['open_margin'] * br['len_poly_sq'])} "
            f"c_margin={fmt_param(cr['open_margin'])} c_dist_poly={fmt_dist(cr['dist_poly_sq'])}"
        )
    br, dr = b["1"]["declared"], d["1"]["declared"]
    print(
        f"same_metres scale=1 b_dist_tri={fmt_dist(br['dist_tri_sq'])} b_margin={fmt_param(br['open_margin'])} "
        f"d_dist_tri={fmt_dist(dr['dist_tri_sq'])} d_margin={fmt_param(dr['open_margin'])}"
    )
    for name, _scale in SCALES:
        ar, gr = a[name]["declared"], a[name]["float"]
        print(
            f"endpoint_vs_bin64 {name} decl={ar['class']} bin64={gr['class']} "
            f"bin64_t={gr['t']!r} bin64_u={gr['u']!r} "
            f"quant={sci(a[name]['quant_max'])} arith_t={sci(a[name]['arith_t'])} "
            f"perp_on_float={fmt_dist(a[name]['perp_float_sq'])} "
            f"class_quant_flip={a[name]['declared']['class'] != a[name]['on_float']['class']} "
            f"class_arith_flip={a[name]['on_float']['class'] != a[name]['float']['class']}"
        )
    # Second proper hit on b, scale 1: parameter and metres.
    # Recompute edge (0, 2) exactly at scale 1 from the stored primary's polygon by rerunning analyse details.
    b1 = None
    for name, row in rows:
        if row["id"] == "b_near_cross" and name == "1":
            b1 = row
    second = [item for item in b1["declared_proper"] if (item[0], item[1]) == (0, 2)]
    print(
        "b_second_proper_scale1",
        [(ii, jj, fmt_param(t), fmt_param(u), fmt_dist((t * t) * b1["declared"]["len_tri_sq"])) for ii, jj, t, u in second],
    )
    print("a_scale1_bin64_t_eq_2**-55", a["1"]["float"]["t"] == 2**-55)
    if failures:
        print("ASSERT_FAIL")
        for item in failures:
            print(item)
        return 1
    print("ASSERT_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

```

Stdout of that process:

```text
probe_edge_veto
python 3.14.7 (main, Sep  1 2026, 14:17:30) [MSC v.1944 64 bit (AMD64)]
mant_dig 53
translation_declared 1/10 1/5
quant_of_float_0.001_vs_1/1000 2.081668e-20
quant_of_float_0.1_vs_1/10 5.551115e-18
keep_xy ([0.0, 0.0, 2.0], 2, [0, 1])
keep_xz ([0.0, -2.0, 0.0], 1, [0, 2])
SUMMARY
a_endpoint     1e-3  decl=endpoint exact_f=miss     bin64=miss     veto=False t=0 u=1/2 margin=0 ft=-36028797018964/41538374868278262469656037905 fu=144115188075855/288230376151711 fmargin=-36028797018964/41538374868278262469656037905 dist_tri=0 dist_poly=2.2360679774997897e-3 len_tri=1/250 len_poly=4.4721359549995794e-3 quant=1.287859e-17 dquant_t=-8.673617e-16 dquant_u=-1.734723e-15 arith_t=2.032879e-17 arith_u=1.387779e-17 perp_decl=0 perp_on_float=3.1031676915590999e-18 signs_den_t_u_1mt_1mu=(-1, 0, 1, 1, 1) den=-1/62500 bin64_t=-8.470329472543077e-16 bin64_u=0.4999999999999983 vetoes=[] den0_skip=[(0, 1), (1, 2)]
a_endpoint     1     decl=endpoint exact_f=proper   bin64=proper   veto=True  t=0 u=1/2 margin=0 ft=6.765422e-17 fu=72057594037927939/144115188075855859 fmargin=6.765422e-17 dist_tri=0 dist_poly=2.2360679774997897e+0 len_tri=4 len_poly=4.4721359549995794e+0 quant=3.552714e-16 dquant_t=6.765422e-17 dquant_u=6.591949e-17 arith_t=-3.989864e-17 arith_u=4.510281e-17 perp_decl=0 perp_on_float=2.4204707994160913e-16 signs_den_t_u_1mt_1mu=(-1, 0, 1, 1, 1) den=-16 bin64_t=2.775557561562892e-17 bin64_u=0.5000000000000001 vetoes=[(0, 0), (2, 0)] den0_skip=[(0, 1), (1, 2)]
VETO a_endpoint 1 pair=0,0 decl=endpoint t=0 u=1/2 exact_f=proper bin64_t=2.775557561562892e-17 bin64_u=0.5000000000000001
VETO a_endpoint 1 pair=2,0 decl=endpoint t=1 u=1/2 exact_f=proper bin64_t=0.9999999999999999 bin64_u=0.5000000000000001
a_endpoint     1e3   decl=endpoint exact_f=miss     bin64=endpoint veto=False t=0 u=1/2 margin=0 ft=-1.136764e-17 fu=72057594037927932723/144115188075855868723 fmargin=-1.136764e-17 dist_tri=0 dist_poly=2.2360679774997897e+3 len_tri=4000 len_poly=4.4721359549995794e+3 quant=1.818989e-13 dquant_t=-1.136764e-17 dquant_u=-1.136938e-17 arith_t=1.136764e-17 arith_u=1.136938e-17 perp_decl=0 perp_on_float=4.0670115765573450e-14 signs_den_t_u_1mt_1mu=(-1, 0, 1, 1, 1) den=-16000000 bin64_t=-0.0 bin64_u=0.5 vetoes=[] den0_skip=[(0, 1), (1, 2)]
b_near_cross   1e-3  decl=proper   exact_f=proper   bin64=proper   veto=True  t=1/100000000 u=1/2 margin=1/100000000 ft=36028797018964/3602879701896397009715 fu=1/2 fmargin=36028797018964/3602879701896397009715 dist_tri=1/1000 dist_poly=1/1000 len_tri=100000 len_poly=1/500 quant=5.820766e-12 dquant_t=8.299708e-24 dquant_u=0 arith_t=1.835685e-24 arith_u=0 perp_decl=1/1000 perp_on_float=9007199254741/9007199254740992 signs_den_t_u_1mt_1mu=(1, 1, 1, 1, 1) den=200 bin64_t=1.000000000000001e-08 bin64_u=0.5 vetoes=[(0, 0), (0, 2)] den0_skip=[(0, 1), (0, 3), (2, 0), (2, 2)]
VETO b_near_cross 1e-3 pair=0,0 decl=proper t=1/100000000 u=1/2 exact_f=proper bin64_t=1.000000000000001e-08 bin64_u=0.5
VETO b_near_cross 1e-3 pair=0,2 decl=proper t=1/50000000 u=1/2 exact_f=proper bin64_t=1.999999999999988e-08 bin64_u=0.5
b_near_cross   1     decl=proper   exact_f=proper   bin64=proper   veto=True  t=1/100000000 u=1/2 margin=1/100000000 ft=36028797018963971/3602879701896396585251635 fu=18014398509481985/36028797018963968 fmargin=36028797018963971/3602879701896396585251635 dist_tri=1 dist_poly=1 len_tri=100000000 len_poly=2 quant=5.960464e-9 dquant_t=1.428714e-24 dquant_u=2.775558e-17 arith_t=-1.219488e-24 arith_u=-2.775558e-17 perp_decl=1 perp_on_float=36028797018963971/36028797018963968 signs_den_t_u_1mt_1mu=(1, 1, 1, 1, 1) den=200000000 bin64_t=1e-08 bin64_u=0.5 vetoes=[(0, 0), (0, 2)] den0_skip=[(0, 1), (0, 3), (2, 0), (2, 2)]
VETO b_near_cross 1 pair=0,0 decl=proper t=1/100000000 u=1/2 exact_f=proper bin64_t=1e-08 bin64_u=0.5
VETO b_near_cross 1 pair=0,2 decl=proper t=1/50000000 u=1/2 exact_f=proper bin64_t=2e-08 bin64_u=0.5
b_near_cross   1e3   decl=proper   exact_f=proper   bin64=proper   veto=True  t=1/100000000 u=1/2 margin=1/100000000 ft=1.000000e-8 fu=18014398509481983181/36028797018963968000 fmargin=1.000000e-8 dist_tri=1000 dist_poly=1000 len_tri=100000000000 len_poly=2000 quant=6.103516e-6 dquant_t=-3.830334e-25 dquant_u=-2.273182e-17 arith_t=5.922590e-25 arith_u=2.273182e-17 perp_decl=1000 perp_on_float=36028797018963968819/36028797018963968 signs_den_t_u_1mt_1mu=(1, 1, 1, 1, 1) den=200000000000000 bin64_t=1e-08 bin64_u=0.5 vetoes=[(0, 0), (0, 2)] den0_skip=[(0, 1), (0, 3), (2, 0), (2, 2)]
VETO b_near_cross 1e3 pair=0,0 decl=proper t=1/100000000 u=1/2 exact_f=proper bin64_t=1e-08 bin64_u=0.5
VETO b_near_cross 1e3 pair=0,2 decl=proper t=1/50000000 u=1/2 exact_f=proper bin64_t=2e-08 bin64_u=0.5
c_near_miss    1e-3  decl=miss     exact_f=miss     bin64=miss     veto=False t=1/2 u=100000001/100000000 margin=-1/100000000 ft=144115188075855/288230376151711 fu=144115189517007/144115188075856 fmargin=-1441151/144115188075856 dist_tri=1/500 dist_poly=1/25000000000 len_tri=1/250 len_poly=1/250 quant=1.334373e-17 dquant_t=-1.734723e-15 dquant_u=-6.111490e-15 arith_t=1.387779e-17 arith_u=5.551116e-17 perp_decl=1/500 perp_on_float=144115188075855/72057594037927936 signs_den_t_u_1mt_1mu=(-1, 1, 1, 1, -1) den=-1/62500 bin64_t=0.4999999999999983 bin64_u=1.000000009999994 vetoes=[] den0_skip=[(0, 0), (0, 2)]
c_near_miss    1     decl=miss     exact_f=miss     bin64=miss     veto=False t=1/2 u=100000001/100000000 margin=-1/100000000 ft=72057594037927939/144115188075855859 fu=6571600069175/6571600003459 fmargin=-65716/6571600003459 dist_tri=2 dist_poly=1/25000000 len_tri=4 len_poly=4 quant=3.552714e-16 dquant_t=6.591949e-17 dquant_u=-5.263558e-18 arith_t=4.510281e-17 arith_u=-5.551115e-17 perp_decl=2 perp_on_float=72057594037927939/36028797018963968 signs_den_t_u_1mt_1mu=(-1, 1, 1, 1, -1) den=-16 bin64_t=0.5000000000000001 bin64_u=1.00000001 vetoes=[] den0_skip=[(0, 0), (0, 2)]
c_near_miss    1e3   decl=miss     exact_f=miss     bin64=miss     veto=False t=1/2 u=100000001/100000000 margin=-1/100000000 ft=72057594037927932723/144115188075855868723 fu=72057594758503879475/72057594037927939096 fmargin=-720575940379/72057594037927939096 dist_tri=2000 dist_poly=1/25000 len_tri=4000 len_poly=4000 quant=3.637979e-13 dquant_t=-1.136938e-17 dquant_u=-3.877328e-21 arith_t=1.136938e-17 arith_u=1.612738e-16 perp_decl=2000 perp_on_float=72057594037927932723/36028797018963968 signs_den_t_u_1mt_1mu=(-1, 1, 1, 1, -1) den=-16000000 bin64_t=0.5 bin64_u=1.0000000100000002 vetoes=[] den0_skip=[(0, 0), (0, 2)]
d_clean        1e-3  decl=proper   exact_f=proper   bin64=proper   veto=True  t=1/2 u=1/2 margin=1/2 ft=72057594037928/144115188075855 fu=1/2 fmargin=72057594037927/144115188075855 dist_tri=1/1000 dist_poly=1/1000 len_tri=1/500 len_poly=1/500 quant=1.199041e-17 dquant_t=3.469447e-15 dquant_u=0 arith_t=-2.775558e-17 arith_u=0 perp_decl=1/1000 perp_on_float=9007199254741/9007199254740992 signs_den_t_u_1mt_1mu=(1, 1, 1, 1, 1) den=1/250000 bin64_t=0.5000000000000034 bin64_u=0.5 vetoes=[(0, 0)] den0_skip=[(0, 1), (0, 3)]
VETO d_clean 1e-3 pair=0,0 decl=proper t=1/2 u=1/2 exact_f=proper bin64_t=0.5000000000000034 bin64_u=0.5
d_clean        1     decl=proper   exact_f=proper   bin64=proper   veto=True  t=1/2 u=1/2 margin=1/2 ft=36028797018963971/72057594037927939 fu=18014398509481985/36028797018963968 fmargin=18014398509481983/36028797018963968 dist_tri=1 dist_poly=1 len_tri=2 len_poly=2 quant=8.881784e-17 dquant_t=2.081668e-17 dquant_u=2.775558e-17 arith_t=-2.081668e-17 arith_u=-2.775558e-17 perp_decl=1 perp_on_float=36028797018963971/36028797018963968 signs_den_t_u_1mt_1mu=(1, 1, 1, 1, 1) den=4 bin64_t=0.5 bin64_u=0.5 vetoes=[(0, 0)] den0_skip=[(0, 1), (0, 3)]
VETO d_clean 1 pair=0,0 decl=proper t=1/2 u=1/2 exact_f=proper bin64_t=0.5 bin64_u=0.5
d_clean        1e3   decl=proper   exact_f=proper   bin64=proper   veto=True  t=1/2 u=1/2 margin=1/2 ft=36028797018963968819/72057594037927932723 fu=18014398509481983181/36028797018963968000 fmargin=36028797018963963904/72057594037927932723 dist_tri=1000 dist_poly=1000 len_tri=2000 len_poly=2000 quant=9.094947e-14 dquant_t=3.410466e-17 dquant_u=-2.273182e-17 arith_t=-3.410466e-17 arith_u=2.273182e-17 perp_decl=1000 perp_on_float=36028797018963968819/36028797018963968 signs_den_t_u_1mt_1mu=(1, 1, 1, 1, 1) den=4000000 bin64_t=0.5 bin64_u=0.5 vetoes=[(0, 0)] den0_skip=[(0, 1), (0, 3)]
VETO d_clean 1e3 pair=0,0 decl=proper t=1/2 u=1/2 exact_f=proper bin64_t=0.5 bin64_u=0.5
COMPARE
same_abs_margin 1e-3 b_margin=1/100000000 b_dist_tri=1/1000 b_margin_times_poly_len=1/50000000000 c_margin=-1/100000000 c_dist_poly=1/25000000000
same_abs_margin 1 b_margin=1/100000000 b_dist_tri=1 b_margin_times_poly_len=1/50000000 c_margin=-1/100000000 c_dist_poly=1/25000000
same_abs_margin 1e3 b_margin=1/100000000 b_dist_tri=1000 b_margin_times_poly_len=1/50000 c_margin=-1/100000000 c_dist_poly=1/25000
same_metres scale=1 b_dist_tri=1 b_margin=1/100000000 d_dist_tri=1 d_margin=1/2
endpoint_vs_bin64 1e-3 decl=endpoint bin64=miss bin64_t=-8.470329472543077e-16 bin64_u=0.4999999999999983 quant=1.287859e-17 arith_t=2.032879e-17 perp_on_float=3.1031676915590999e-18 class_quant_flip=True class_arith_flip=False
endpoint_vs_bin64 1 decl=endpoint bin64=proper bin64_t=2.775557561562892e-17 bin64_u=0.5000000000000001 quant=3.552714e-16 arith_t=-3.989864e-17 perp_on_float=2.4204707994160913e-16 class_quant_flip=True class_arith_flip=False
endpoint_vs_bin64 1e3 decl=endpoint bin64=endpoint bin64_t=-0.0 bin64_u=0.5 quant=1.818989e-13 arith_t=1.136764e-17 perp_on_float=4.0670115765573450e-14 class_quant_flip=True class_arith_flip=True
b_second_proper_scale1 [(0, 2, '1/50000000', '1/2', '2')]
a_scale1_bin64_t_eq_2**-55 False
ASSERT_OK
```
