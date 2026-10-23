# UCX edge-edge and plane-projection arithmetic

Status: report-only research; synthetic coordinates in metres; `delivery_passed=false`.

## Summary

Site 2 independently loses a stored endpoint: the diagonal/origin-segment case measures 813 distance ulps low.
Reversing the diagonal restores the exact stored distance; reversing the other segment or swapping the pair does not.
A decreasing axis segment also reproduces the loss; axis alignment is not an exactness guarantee.
The ordinary skew-interior and two-point controls remain unchanged under site-2-only endpoint preservation.
Plane projections show coordinate and returned-distance rounding, independently of site 1, but no inside/fallback flip in six cases.
In particular, an inaccurate reconstructed q need not change the returned plane distance or its branch.
Four #505 box gaps are unchanged controls, not new hull-level evidence; no new pair_relation finding is claimed.
No repair, threshold change, or revision of #501 is adopted; the #505 decision remains with the user.

## Findings

### Sources and command provenance

Read-only local sources, all at HEAD = local `origin/main`
`ed4d77452a13ec0ad31bec06bfa830a7b0d6f5f1`:

| Path | Git blob SHA | Relevance |
|---|---|---|
| `docs/domain/areas/ucx.md` | `c95309235fc2c96b976d478ffa6daadd1f69871e` | R09/R10; UCX intersection/gap coverage and limitations |
| `src/twinqa/geometry/ucx_audit.py` | `d179fcbc6c5804dafbef75f335b85c837bbe480a` | `_closest_on_segment`, `segment_segment_distance`, `point_triangle_distance`, `surface_distance` |
| `tests/qa/test_ucx_too_close_boundary.py` | `dd33d804693e0b542231d6b98d9c6044592364ec` | Four-gap corpus, pinned #501 witness; unchanged |
| `tests/qa/test_ucx_degenerate_area_boundary.py` | `a8956ac8fd654394f2e90eff65f1ecd090cb98c1` | Separate area-boundary characterization; not a distance oracle |

The #505 report is **not in this local origin/main tree**. Read via `git show` from
`origin/docs/research-ucx-distance-endpoint-cancellation`, commit
`7794ce0ff232721a5b8707afa8cb2f82728b7e89`, path
`docs/research/ucx-distance-endpoint-cancellation.md`, blob
`ec3863037980b8bda341b0e7648ff2f1f19f941a`.
Its F2/F4 describe site 2 and plane reconstruction as unmeasured; its proposed task
expects an edge-edge witness and exact interior/axis controls. Those expectations are
**source claims/proposals**, not measurements inherited by this report. Its recommendation
to repair both sites and revise #501 is not a decision taken here.

Own commands: read-only `git status --short`, `git rev-parse`, `git remote -v`,
`git ls-tree`, `git for-each-ref`, and report-only `git show`; no fetch or ref update.
Remote identifies `https://github.com/artsafro/AGR-DigitalTwin-pilot.git`.
The source files above were read directly; no other domain documents were consulted.
Three standalone `python -B` executions evaluated the same frozen corpus: the second
moved Fraction-to-Decimal conversion inside the 80-digit error context (removing
spurious ~1e-32 coordinate display residuals), and added mutable-input/interior checks.
The third executed the final fenced code and counted 40 segment variants, six plane
cases and four no-change controls, with all assertions completing. No run changed
geometry. Final probe line: `REPORT_CHECK: 40 segment variants + 6 plane cases + 4 no-change controls; all assertions completed`.
No pytest/full suite was run (0 tests); these are standalone arithmetic probes, not
suite acceptance. Final read-only status listed this new report as the only changed
path; `git diff --check` returned no diagnostics (the report was still untracked). Runtime: CPython 3.14.7, MSC v.1944 AMD64,
Windows 11 build 26200. Distances are from actual production calls, with equality
checks against explicitly instrumented copies. Rational minimizers use exact stored
floats; square roots use 90-digit Decimal, error rendering 80 digits. Report tables
abbreviate errors, not binary64 returned distances. No external issue status lookup
was performed; issue references reflect the supplied card/pinned report only.

### F1 — site 2 has an independent endpoint cancellation witness

Let `g` mean the stored literal `0.0002`, `w = 0.00019999999999997797`,
`B=(g,0,0)`, and `O=(0,0,0)`. Exact stored values include
`g=7378697629483821/36893488147419103232` and
`1.0002=2252250173647985/2251799813685248`. These are not exact decimal
1/5000 and 5001/5000. All errors below are against represented coordinates unless
explicitly labelled otherwise.

For E the exact diagonal point is `B+u*(1.0002-g,0,1)` with `u>=0`;
its squared distance from `(0,y,0)` is
`(g+u*(1.0002-g))**2+u**2+y**2`. Each term is minimized at `u=0,y=0`.
Thus the unique nearest coordinates are B and O and distance is exactly stored g,
independently of any production helper. The second segment is specified at x=z=0,
y in [-1,1], not constructed by subtracting an offset from the first segment.
The decreasing axis case A has the same endpoint minimum. P collapses the second
segment to O; PP is two points and takes the early `_norm(r)` return.

Actual clamped parameters and coordinates (before pair swap):

| Case / first segment direction | Observed s,t | Original c1,c2 | Original distance | Site-2-only distance / coordinates |
|---|---|---|---|---|
| E, forward, either second direction | 1.0, 0.5 | (w,0,0), O | `0.00019999999999997797` | `0.0002`; B,O |
| E, reversed, either second direction | 0.0, 0.5 | B,O | `0.0002` | `0.0002`; B,O |
| P, forward | 1.0, 0.0 | (w,0,0), O | `0.00019999999999997797` | `0.0002`; B,O |
| P, reversed | 0.0, 0.0 | B,O | `0.0002` | `0.0002`; B,O |
| A, forward / reversed | 1.0,0.5 / 0.0,0.5 | as E | as E | `0.0002`; B,O |
| PP, any direction | not assigned (early return) | not reconstructed; input B,O | `0.0002` | unchanged |

Pair swap exchanges s/t and c1/c2, with **bit-identical distances** for every
corresponding case. All eight variants per row family were measured, including
redundant reversals of collapsed points. Reversing the first segment alone changes
original E/P/A distance by **813 ulps**, despite independently equal mathematical
distance. There are 12 low readings among the 40 segment variants (four each E/P/A).
For those 12, the x coordinate differs from the literal endpoint B.x, and absolute
coordinate **and distance** error is
`2.203640915576787762120147817768156528472900390625e-17 m`.
Signed error is -813 ulps at g/w (`ulp=2^-65`), or -0.0992431640625 ulps at
1.0002/1.0 (`ulp=2^-52`). The remaining 28 original distances equal stored g.
The substitution returns literal endpoints only for already-clamped 0/1 parameters;
all 40 substituted distances equal g. Site 1 and plane projection stay unchanged.
This isolates a site-2 witness, not a proposal or proof that all site-2 errors are fixed.

A is a counterexample to a *general* axis-exactness expectation in #505's proposal.
It is not a refutation of that report's specific increasing short edge from 1 to 1.0002:
A runs from 1.0002 down to g, so its rounded difference is -1.0.

### F2 — ordinary skew interior is unchanged, not evidence of general exactness

I consists of an x-axis segment and a y-directed segment at height stored g.
Their exact squared distance is x²+y²+g²; unique closest coordinates are
O and `(0,0,g)`, exact parameters 1/3 and 2/3 before reversals/swap.
The instrumented original has `s=0.3333333333333333`,
`t=0.6666666666666666` and these exact closest coordinates. Reversal changes
parameters to the corresponding 2/3 or 1/3 binary64 approximations; pair swap
exchanges them. All eight distances are `0.0002`, zero represented-geometry error,
with identical coordinates and interpolation under the endpoint-only substitution.
The parameters themselves are not exact rationals 1/3 and 2/3. This is a measured
negative control, **not** a claim that arbitrary interior interpolation is exact.
PP likewise measures stored g exactly in all eight variants without reconstruction.

### F3 — plane rounding is independent; no inside/fallback witness isolated

Exact oracle uses `n=(b-a)×(c-a)`, `t=((p-a)·n)/(n·n)`, `q=p-n*t`,
and three rational oriented-area signs (equivalently barycentric numerators).
For outside cases it independently minimizes rational squared point-edge distances.
It never calls a production distance helper. XI/XE/XO have normal (1,0,0);
TI/TE/TO have normal (1,0,1). On an exact edge counts as inside in these cases.

| Case | Actual t | Actual q | Expected / observed branch | Returned distance | Absolute error m; signed ulps at returned distance |
|---|---|---|---|---|---|
| XI | `1.0` | `(w,.25,.25)` | inside / inside | `1.0` | 2.203640915576788e-17; +0.0992431640625 |
| XE | `1.0` | `(w,.5,.5)` | edge-inside / inside | `1.0` | 2.203640915576788e-17; +0.0992431640625 |
| XO | `1.0` | `(w,1.,1.)` | outside / fallback | `1.224744871391589` | 9.043817317355340e-17; -0.4072973230044835 |
| TI | `0.00019999999999999185` | `(.25,.25,-.25)` | inside / inside | `0.0002828427124746075` | 3.817304277584287e-20; +0.7041683506007406 |
| TE | `0.0002` | `(0.,.25,0.)` | edge-inside / inside | `0.000282842712474619` | 7.316889420200094e-21; -0.1349727865500642 |
| TO | `0.00019999999999999185` | `(-.25,.25,.25)` | outside / fallback | `0.3535535037303406` | 1.797508750598301e-17; -0.3238103895755886 |

Actual inside-test signs in case order:
`(.25,.5,.25)`, `(.5,0,.5)`, `(1,-1,1)`, `(.5,1,.5)`,
`(.5,1.5,0)`, `(.5,2,-.5)`.
Exact signs for TI are `(1/2,1+2^-55,1/2-2^-55)`; for TO they are
`(1/2,2-2^-55,-1/2+2^-55)`. Others equal the listed binary64 signs.
No sign crosses the production `>= -1e-15` boundary. This is a negative result
for a branch-change witness in this finite corpus, not a guarantee for boundary-adjacent
or differently scaled triangles. Triangle-winding symmetry was not measured here.

For X cases exact q.x=g but actual q.x=w: coordinate error is -813 ulps at g,
-0.0992431640625 ulps at input x≈1. For TI, exact q is
`(1/4-2^-56,1/4,-1/4+2^-56)`; TO has the opposite x/z signs.
Each changed x/z coordinate has absolute error `2^-56 = 1.3877787807814457e-17 m`,
0.25 ulp at the **returned** coordinate magnitude .25 (`ulp=2^-54`).
At the exact coordinate just below .25, spacing is `2^-55`, so this is 0.5 of
that spacing; the choice of ulp reference matters at powers of two. TE q is exact.
Other q coordinates are exact. Distance ulps are `2^-52` for XI/XE/XO,
`2^-64` for TI/TE, and `2^-54` for TO.

Crucially, the inside return is **`abs(t)*sqrt(nn)`**, not `norm(p-q)`.
XI/XE's returned 1.0 is the correctly rounded stored plane separation
`1-(g-w)`, despite inaccurate q.x; the sign test ignores that normal-direction
q error. TI and TE show that even a selected plane path with an unchanged inside
branch can have a nonzero returned-distance error. TE's q is exact while its
irrational distance rounds; TI's +0.704-ulps result exceeds half an ulp, but does
not establish q reconstruction as its cause. The plane inside path calls no site-1
helper, so these measurements are independent of `_closest_on_segment`.
No isolated **cancellation-caused wrong branch** or q-caused returned-distance
witness was found. No fix is claimed. XO/TO return edge fallback distances;
their total returned errors must not be called plane-return errors, and site 1
was intentionally not changed or separately isolated there.

Intended decimals differ: e.g. ideal TI projects to `(.25,.25,-.25)` with
t=.0002, whereas exact stored TI has the rational values above. TE's exact stored
distance is `sqrt(2)*g`, not the exact decimal `sqrt(2)/5000`. The reported errors
exclude decimal-to-binary64 input representation error; rational inputs in the code
make that distinction reproducible.

### F4 — no-change hull controls and scope limits

| #505 g | Original class / gap | Site-2-only class / gap |
|---|---|---|
| `0.0` | touch / `0.0` | unchanged |
| `0.000199` | touch / `0.000199` | unchanged |
| `0.0002` | touch / `0.00019999999999997797` | unchanged |
| `0.000201` | below_band / `0.000201` | unchanged |

These are explicitly **no-change controls**, not new arithmetic evidence and not a
new argmin proof. #505 attributes their argmin to site-1 vertex-triangle fallback;
this report does not re-prove or extend that hull-level claim. New E/P/A evidence
is direct segment evidence only. No hull embedding, surface-distance feature
competition, or new `pair_relation` / finding change is established. A direct segment
error is not a hull classification result.

Mutable input vectors were copied and compared after original/substitute segment
calls and plane calls; hull arrays were compared after original/substituted
`pair_relation`. All were unchanged. Site-2 substitution was restored in `finally`;
site 1 and `point_triangle_distance` function identities were unchanged.
No infinity, NaN, near-degenerate-length, near-parallel, scale sweep, or real-delivery
claim is made. The corpus is small and finite, not an error bound.

### Frozen corpus and reproduction

The following finite literals were written before the first arithmetic probe. No random
search, parameter sweep, or outcome-driven input replacement is used. Each segment pair
has all eight combinations of reversing either segment and swapping pair order.
The independently placed second segment in E has its nearest point at the origin.
P is a point-segment control, PP a two-point control, A an axis control, and I an
interior-interior skew control (orthogonal horizontal directions, vertical separation).
Plane cases use an axis plane x=0.0002 and a tilted plane x+z=0, each with a clearly
inside, exactly edge, and clearly outside mathematical projection. Exact stored-float
geometry, rather than ideal decimal geometry, is the primary oracle.

Run the fenced code with `python -B` from this worktree (stdlib only). It loads only the
allowed production module; no pytest, dependencies, source writes, or bytecode writes.
The `exec` copies below are explicitly **instrumented copies**, not production changes.
Only the process-local site-2 substitution is installed temporarily, then restored.

```python
import copy
import importlib.util
import inspect
import itertools
import math
import platform
import sys
from decimal import Decimal, localcontext
from fractions import Fraction as F

# Frozen literal corpus: defined before evaluating any distances.
SEGMENTS = {
    'E': ((1.0002,0.,1.), (.0002,0.,0.), (0.,-1.,0.), (0.,1.,0.)),
    'P': ((1.0002,0.,1.), (.0002,0.,0.), (0.,0.,0.), (0.,0.,0.)),
    'PP': ((.0002,0.,0.), (.0002,0.,0.), (0.,0.,0.), (0.,0.,0.)),
    'A': ((1.0002,0.,0.), (.0002,0.,0.), (0.,-1.,0.), (0.,1.,0.)),
    'I': ((-1.,0.,0.), (2.,0.,0.), (0.,-2.,.0002), (0.,1.,.0002)),
}
PLANE = {
    'XI': ((1.0002,.25,.25), (.0002,0.,0.), (.0002,1.,0.), (.0002,0.,1.)),
    'XE': ((1.0002,.5,.5), (.0002,0.,0.), (.0002,1.,0.), (.0002,0.,1.)),
    'XO': ((1.0002,1.,1.), (.0002,0.,0.), (.0002,1.,0.), (.0002,0.,1.)),
    'TI': ((.2502,.25,-.2498), (0.,0.,0.), (1.,0.,-1.), (0.,1.,0.)),
    'TE': ((.0002,.25,.0002), (0.,0.,0.), (1.,0.,-1.), (0.,1.,0.)),
    'TO': ((-.2498,.25,.2502), (0.,0.,0.), (1.,0.,-1.), (0.,1.,0.)),
}
GAPS = (0., .000199, .0002, .000201)  # #505 no-change controls only
TRIS = [(0,1,3),(0,3,2),(4,6,7),(4,7,5),(0,4,5),(0,5,1),
        (2,3,7),(2,7,6),(0,2,6),(0,6,4),(1,5,7),(1,7,3)]

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('ua', 'src/twinqa/geometry/ucx_audit.py')
ua = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ua)
print('RUNTIME', sys.version, platform.platform())

# Independent exact rational vector algebra: no production distance helper.
def sub(a,b): return tuple(x-y for x,y in zip(a,b))
def add(a,b): return tuple(x+y for x,y in zip(a,b))
def mul(a,t): return tuple(x*t for x in a)
def dot(a,b): return sum(x*y for x,y in zip(a,b))
def cross(a,b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def rational(v): return tuple(F.from_float(x) for x in v)
def clamp(x): return max(F(0),min(F(1),x))
def dec(x): return Decimal(x.numerator)/Decimal(x.denominator)
def root(x):
    with localcontext() as ctx:
        ctx.prec=90
        return dec(x).sqrt()
def metrics(x, exact):
    with localcontext() as ctx:
        ctx.prec=80
        if isinstance(exact,F): exact=dec(exact)
        err=Decimal.from_float(x)-exact
        return (str(abs(err)), str(err/Decimal.from_float(math.ulp(x))))
def seg_oracle(v):
    p,q,u,w=map(rational,v)
    d,h,r=sub(q,p),sub(w,u),sub(p,u)
    a,e,b,c,f=dot(d,d),dot(h,h),dot(d,h),dot(d,r),dot(h,r)
    candidates=[]
    def take(s,t):
        x,y=add(p,mul(d,s)),add(u,mul(h,t))
        candidates.append((dot(sub(x,y),sub(x,y)),s,t,x,y))
    # Exhaust the four boundary minimizers, then the stationary interior point.
    for s in (F(0),F(1)):
        take(s,clamp((f+b*s)/e) if e else F(0))
    for t in (F(0),F(1)):
        take(clamp((b*t-c)/a) if a else F(0),t)
    determinant=a*e-b*b
    if determinant:
        s,t=(b*f-c*e)/determinant,(a*f-b*c)/determinant
        if 0<=s<=1 and 0<=t<=1: take(s,t)
    return min(candidates)
def plane_oracle(v):
    p,a,b,c=map(rational,v)
    n=cross(sub(b,a),sub(c,a)); nn=dot(n,n)
    t=dot(sub(p,a),n)/nn; q=sub(p,mul(n,t))
    signs=[dot(cross(sub(y,x),sub(q,x)),n) for x,y in ((a,b),(b,c),(c,a))]
    inside=all(s>=0 for s in signs)
    distance2=t*t*nn if inside else min(seg_oracle((v[0],v[0],x,y))[0]
        for x,y in ((v[1],v[2]),(v[2],v[3]),(v[3],v[1])))
    return root(distance2),t,q,signs,inside

# Instrumented copies preserve all production arithmetic and return locals as trace.
source=inspect.getsource(ua.segment_segment_distance)
plane_source=inspect.getsource(ua.point_triangle_distance)
def instrument(src):
    lines=[]
    for line in src.splitlines():
        if line.lstrip().startswith('return '):
            indent=line[:len(line)-len(line.lstrip())]
            line=indent+'return ('+line.lstrip()[7:]+'), locals()'
        lines.append(line)
    ns=dict(vars(ua)); exec('\n'.join(lines),ns)
    name=src.split('def ')[1].split('(')[0]
    return ns[name]
def preserve_source(src):
    for dest,p,q,d,t in [('c1','p1','q1','d1','s'),('c2','p2','q2','d2','t')]:
        old=f'    {dest} = ('
        src=src.replace(old,f'    {dest} = {p} if {t} == 0.0 else {q} if {t} == 1.0 else (')
    return src
trace=instrument(source)
trace_preserve=instrument(preserve_source(source))
plane_trace=instrument(plane_source)
ns=dict(vars(ua)); exec(preserve_source(source),ns)
site2_only=ns['segment_segment_distance']
original=ua.segment_segment_distance
site1=ua._closest_on_segment
plane_original=ua.point_triangle_distance
saved=copy.deepcopy((SEGMENTS,PLANE,GAPS,TRIS))

for name,v in SEGMENTS.items():
    for rev1,rev2,swap in itertools.product((0,1),repeat=3):
        x=v[:2][::(-1 if rev1 else 1)]; y=v[2:][::(-1 if rev2 else 1)]
        args=y+x if swap else x+y
        oracle=seg_oracle(args); expected=root(oracle[0])
        prod=original(*args); observed,loc=trace(*args)
        changed,fix=trace_preserve(*args)
        assert prod==observed and changed==site2_only(*args)
        mutable=[list(v) for v in args]; before=copy.deepcopy(mutable)
        assert original(*mutable)==prod and site2_only(*mutable)==changed
        assert mutable==before
        if name=='I':
            assert observed==changed and loc['c1']==fix['c1'] and loc['c2']==fix['c2']
        # Both-point early return has no reconstructed c1/c2 in production.
        coords=(loc.get('c1',args[0]),loc.get('c2',args[2]))
        fixed_coords=(fix.get('c1',args[0]),fix.get('c2',args[2]))
        coorderr=[]
        for got,want in zip(coords,oracle[3:]):
            coorderr.append([metrics(z,w) for z,w in zip(got,want)])
        print('SEG',name,rev1,rev2,swap,'s,t',loc.get('s'),loc.get('t'),
              'c1,c2',coords,'oracle_s,t',str(oracle[1]),str(oracle[2]),
              'd',repr(prod),'abs_m,signed_ulp',metrics(prod,expected),
              'preserve',repr(changed),metrics(changed,expected),
              'fixed_coords',fixed_coords,'coordinate_errors',coorderr)

for name,args in PLANE.items():
    expected,t,q,signs,inside=plane_oracle(args)
    prod=plane_original(*args); measured,loc=plane_trace(*args)
    assert prod==measured
    print('PLANE',name,'t',repr(loc['t']),'q',loc['q'],
          'signs', [ua._dot(ua._cross(ua._sub(y,x),ua._sub(loc['q'],x)),loc['n'])
                    for x,y in ((args[1],args[2]),(args[2],args[3]),(args[3],args[1]))],
          'expected/observed_inside',inside,loc['inside'],
          'oracle_t,q,signs',str(t),tuple(map(str,q)),list(map(str,signs)),
          'q_errors', [metrics(z,w) for z,w in zip(loc['q'],q)],
          'd',repr(prod),'abs_m,signed_ulp',metrics(prod,expected))
    try:
        ua.segment_segment_distance=site2_only
        mutable=[list(v) for v in args]; before=copy.deepcopy(mutable)
        assert ua.point_triangle_distance(*mutable)==prod and mutable==before
    finally: ua.segment_segment_distance=original

def box(lo,hi):
    return ([tuple(hi[k] if i & (4>>k) else lo[k] for k in range(3))
             for i in range(8)],list(TRIS))
for g in GAPS:
    pair=(box((-1.,0.,0.),(0.,1.,1.)),box((g,0.,0.),(1.+g,1.,1.)))
    before=copy.deepcopy(pair)
    baseline=ua.pair_relation(*pair)
    try:
        ua.segment_segment_distance=site2_only
        after=ua.pair_relation(*pair)
    finally: ua.segment_segment_distance=original
    assert pair==before
    print('BOX_NO_CHANGE',repr(g),baseline,after,baseline==after)
assert (SEGMENTS,PLANE,GAPS,TRIS)==saved
assert ua._closest_on_segment is site1 and ua.point_triangle_distance is plane_original
assert ua.segment_segment_distance is original
print('IMMUTABLE_AND_RESTORED',True)
print('COUNTS 40 segment variants, 6 plane cases, 4 box controls')
```

## How it applies to this repository

- `src/twinqa/geometry/ucx_audit.py`: site 2's c1/c2 reconstruction can lose a literal endpoint independently of site 1; plane q affects the inside test, while the selected plane distance is computed separately from t and nn.
- `tests/qa/test_ucx_too_close_boundary.py`: the #501 witness remains untouched. Its legacy “1 ulp” wording is not used as this report's quantitative oracle.
- `tests/qa/test_ucx_degenerate_area_boundary.py`: read-only boundary context, not evidence for the distance paths.
- `docs/domain/areas/ucx.md`: these arithmetic observations do not close R09/R10 coverage or any manual/delivery gate.
- This file is the sole deliverable. No production/test/report/threshold/SAT/schema/procedure/dependency edits or DCC work.

## Proposed next tasks

### Archive: optional hull-feature attribution for the site-2 witness

Scope: if the user needs a hull-level consequence rather than direct-segment evidence,
construct a separate frozen closed-convex hull corpus and enumerate all vertex-triangle
and edge-edge candidates to prove the surface-distance argmin, then compare original
and site-2-only measurements. Do not assume a segment witness wins the minimum or
change #501. Value M / effort M. **Archive: no roadmap link**: this run did not verify
an open roadmap/blocker issue for this optional extension; #505 is the supplied decision
context, not a newly verified roadmap issue. No issue was created.

## Open questions for the user

1. Does the independent site-2 endpoint witness suffice for the pending #505 decision, or is hull-level argmin evidence required before deciding? This report chooses neither repair adoption nor whether both sites should change together.
2. Is the negative inside/fallback result sufficient for now, or should a separately frozen, scale/boundary-adjacent plane corpus be commissioned? No plane repair is supported by the present observations.
