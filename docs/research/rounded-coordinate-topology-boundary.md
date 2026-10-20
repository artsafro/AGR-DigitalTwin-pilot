# Rounded coordinate identity: Connect and Shell topology boundary

## Summary

Both rounded keys can merge different valid input coordinates, not just coincident boundaries.  
Narrow convex quads produce repeated output indices and zero-area faces in both public APIs.  
Separated unit quads can instead become joined or duplicate faces without repeated indices.  
Shell accepts the frozen counterexamples with its default validation tolerance and explicit metres.  
All 492 corrected-run evaluations preserved input arrays and their tested metadata alignment.  
Keys select the first encountered original position, not a rounded output position.  
Translation across rounding cells changes merging; input order changes the representative.  
This is synthetic API exposure, not evidence of a defect in an inspected real model.  
No identity/repair policy is chosen; this is a report only, `delivery_passed=false`.

## Findings with sources

### Frozen standalone corpus and reproduction

The following corpus and measurements were written before the first probe execution.
No random input, adaptive search, decimal half-step fixture, DCC or native export is used.
All arrays are float64, finite; every face has four different source indices.
`shared` uses an indexed exact common edge; `coincident` uses duplicate coordinates but
separate indices. The other pairs use separate indices throughout. `adjacent` leaves
an X gap between coplanar unit vertical rectangles; `parallel` leaves a Y gap between
unit vertical rectangles; `narrow` uses two disjoint positive-width vertical rectangles.
Signs negate all coordinates. Fixed translations add `(t*h,t*h,t*h)`,
`t in (0,.45,1.05)`, with `h=10**(-8)` for Connect and `10**(-9)` for Shell.
Gaps/widths are `(.2,.4,.6,1.2)*h`. Shell also has unit exterior rectangles with
positive inward thickness at those same four multiples (`depth`). All Shell inputs
carry unit normal `(0,-1,0)`, explicit metres and nonempty synthetic source refs;
default `tolerance_m=1e-7` is not weakened. No claim of architectural suitability is
made for sub-nanometre strips: admissibility here means geometrically convex,
nonzero-area and accepted by the present API.

Run from the repository root with `uv run python -` and the block below on stdin.
It emits every row as JSON, verifies JSON round-trip float identity (including hex),
and prints summaries. It imports only the two studied kernels, NumPy and the standard
library; it never imports pytest or the independent weld kernels.

```python
import sys, json, hashlib, platform
from collections import Counter, defaultdict
import numpy as np
sys.path.insert(0, 'src')
from dt_ai.geometry.connect import connect_quads
from dt_ai.geometry.shell import Mesh, shell_body

FACTORS = (.2, .4, .6, 1.2)
SHIFTS = (0., .45, 1.05)

def quad(x=0., y=0., width=1.):
    return np.array([[x,y,0.],[x+width,y,0.],
                     [x+width,y,1.],[x,y,1.]])

def corpus(d, depth=False):
    h = 10.**(-d)
    f = np.arange(8).reshape(2,4)
    v = np.vstack([quad(), quad(x=1.)])
    yield ('shared', v[[0,1,2,3,5,6]],
           np.array([[0,1,2,3],[1,4,5,2]]), .4)
    yield ('coincident', v, f.copy(), .4)
    for kind in ('adjacent','parallel','narrow') + (('depth',) if depth else ()):
        for a in FACTORS:
            g = a*h
            if kind == 'adjacent': q = [quad(), quad(x=1.+g)]
            elif kind == 'parallel': q = [quad(), quad(y=g)]
            elif kind == 'narrow': q = [quad(width=g), quad(x=2.,width=g)]
            else: q = [quad(), quad(x=2.)]
            for sign in (1,-1):
                for t in SHIFTS:
                    yield (f'{kind}/{a}/{sign}/{t}',
                           sign*np.vstack(q)+t*h, f.copy(),
                           g if kind == 'depth' else .4)

def oriented(q, normal):
    return q[::-1] if np.dot(np.cross(q[1]-q[0],q[2]-q[0]),normal)<0 else q

def metrics(v, f, expected, exterior_count=2):
    repeated = sum(len(set(face))<4 for face in f)
    area = [sum(np.linalg.norm(np.cross(q[i]-q[0],q[i+1]-q[0]))/2
                for i in (1,2)) for q in v[f]]
    # Compare original unrounded corresponding corners, not rounded keys.
    err = max(float(np.linalg.norm(v[face]-q,axis=1).max())
              for face,q in zip(f,expected))
    represented = defaultdict(set)
    for face,q in zip(f,expected):
        for i,p in zip(face,q): represented[int(i)].add(tuple(p))
    collisions = sum(len(points)>1 for points in represented.values())
    edges = Counter()
    for face in f[:exterior_count]:
        edges.update(tuple(sorted((int(a),int(b))))
                     for a,b in zip(face,np.roll(face,-1)))
    return dict(V=len(v),F=len(f),repeated=repeated,zero=int(sum(a==0 for a in area)),
                displacement=err,collision_ids=collisions,
                exterior_shared_edges=sum(n==2 for (a,b),n in edges.items() if a!=b))

rows=[]; frozen=[]
for route,d in [('connect',8),('shell',9),('private',9)]:
    for label,v,f,thickness in corpus(d,depth=route=='shell'):
        frozen.append([route,label,v.tolist(),f.tolist(),thickness])
        for reverse in (False,True):
            order = [1,0] if reverse else [0,1]
            ff=f[order].copy(); n=np.tile([0.,-1.,0.],(2,1))
            refs=[f'synthetic:{i}' for i in order]
            before=(v.tobytes(),ff.tobytes(),n.tobytes(),tuple(refs))
            expected=[]
            try:
                if route=='connect':
                    ov,of,parents=connect_quads(v,ff,max_side_m=3.9)
                    expected=[v[face] for face in ff]
                    aligned=(parents==[0,1] and
                             [order[p] for p in parents]==order)
                elif route=='private':
                    m=Mesh('synthetic')
                    for j,face in enumerate(ff):
                        m.face(v[face],n[j],material=[17,29][order[j]])
                        expected.append(oriented(v[face],n[j]))
                    ov=np.array(m.vertices); of=np.array(m.faces)
                    aligned=m.materials==[[17,29][i] for i in order]
                else:
                    result=shell_body(v,ff,n,thickness_m=thickness,name='synthetic',
                                      source_refs=refs,units='m')
                    m=result['mesh']; ov=np.array(m['vertices']); of=np.array(m['faces'])
                    fs=result['face_sources']
                    inner=v+np.array([0.,thickness,0.])
                    for source in fs:
                        fi=source['source_face']
                        if source['role']=='exterior': q=v[ff[fi]]; normal=n[fi]
                        else:
                            i,j=source['source_edge']
                            q=np.array([v[i],inner[i],inner[j],v[j]])
                            normal=np.cross(q[1]-q[0],q[2]-q[0])
                        expected.append(oriented(q,normal))
                    # Independent exact-index boundary oracle: no rounding.
                    uses=Counter(tuple(sorted((int(a),int(b)))) for face in ff
                                 for a,b in zip(face,np.roll(face,-1)))
                    boundary={e for e,count in uses.items() if count==1}
                    actual={tuple(sorted(s['source_edge'])) for s in fs if s['role']=='rim'}
                    aligned=(len(fs)==len(of)==len(m['materials']) and
                             all(s['source_ref']==refs[s['source_face']] for s in fs) and
                             m['materials']==[0]*len(of) and boundary==actual and
                             len(of)==2+len(boundary))
                immutable=before==(v.tobytes(),ff.tobytes(),n.tobytes(),tuple(refs))
                assert aligned and immutable
                assert len(expected)==len(of)
                serial=json.loads(json.dumps(dict(v=ov.tolist(),f=of.tolist()),allow_nan=False))
                assert [float(x).hex() for x in ov.flat]==[
                    float(x).hex() for x in np.array(serial['v']).flat]
                assert serial['f']==of.tolist()
                row=dict(route=route,label=label,reverse=reverse,status='accepted',
                         aligned=aligned,immutable=immutable,
                         **metrics(ov,of,expected))
                if label.startswith(('parallel/0.2/1/0.0','narrow/0.2/1/0.0',
                                     'depth/0.2/1/0.0')):
                    row.update(input=v.tolist(),output=ov.tolist(),faces=of.tolist(),
                               input_hex=[[float(x).hex() for x in p] for p in v])
            except ValueError as e:
                row=dict(route=route,label=label,reverse=reverse,status=str(e))
            rows.append(row)
print('ENV',platform.python_version(),np.__version__)
print('CORPUS_SHA256',hashlib.sha256(json.dumps(frozen,separators=(',',':'),
                                               allow_nan=False).encode()).hexdigest())
for row in rows: print('ROW',json.dumps(row,sort_keys=True))
for route in ('connect','shell','private'):
    rr=[r for r in rows if r['route']==route]
    accepted=[r for r in rr if r['status']=='accepted']
    print('SUMMARY',route,json.dumps(dict(calls=len(rr),accepted=len(accepted),
        statuses=dict(Counter(r['status'] for r in rr)),
        repeated_calls=sum(r['repeated']>0 for r in accepted),
        zero_calls=sum(r['zero']>0 for r in accepted),
        collision_calls=sum(r['collision_ids']>0 for r in accepted),
        max_displacement=max(r['displacement'] for r in accepted))))
    for kind in ('shared','coincident','adjacent','parallel','narrow','depth'):
        for a in FACTORS if kind not in ('shared','coincident') else (None,):
            group=[r for r in rr if r['label']==kind or
                   r['label'].startswith(f'{kind}/{a}/')]
            if group:
                counts=Counter((r.get('V'),r.get('F'),r.get('repeated'),r.get('zero'),
                                r.get('exterior_shared_edges'),r['status']) for r in group)
                print('GROUP',route,kind,a,repr(dict(counts)))
```

Execution note: the first execution completed the kernel calls and assertions but its row
printer failed because `zero` was a NumPy int64, not JSON serializable. The measurement
was changed to `int(sum(...))` and the identical frozen inputs were rerun. No corpus or
kernel change was made. Results below refer to the corrected reporting run.

### Measured results

Source snapshot: `6e9f3faa22d0e05889c01e46ce15805ed9168a99`; Python **3.14.7**, NumPy
**2.5.3**. Frozen corpus JSON SHA-256:
`8a044af14b3152ab3141ad2bf2c55ed354f6ff406d16198645fd3451217f7494`.
There are 74 Connect, 98 public Shell and 74 private Mesh input records, each evaluated
in both face orders: **492 accepted / 0 rejected**, including the controls. The first
run's printer failure is recorded above; these are not cumulative counts across runs.

| Route | Calls | Calls merging unequal positions | Calls with repeated indices | Calls with exactly zero area | Maximum corresponding-corner displacement (m) |
|---|---:|---:|---:|---:|---:|
| `connect_quads` | 148 | 66 | 22 | 22 | 6.000000163375319e-9 |
| `shell_body` | 196 | 82 | 38 | 38 | 6.000000496442226e-10 |
| private `Mesh.face` | 148 | 66 | 22 | 22 | 6.000000496442226e-10 |

Actual output signatures below use `(V,F,R,Z)`: output vertex count, face count,
faces containing repeated indices, exactly zero-area faces. Each factor group contains
12 calls (2 signs × 3 translations × 2 orders). `A/B` are the merged/unmerged
signatures, not proposed pass/fail labels. The private Mesh and Connect columns happen
to match in counts, but use different physical steps.

| Frozen family | Connect / private A; B | Public Shell A; B | .2h A/B | .4h A/B | .6h A/B | 1.2h A/B |
|---|---|---|---:|---:|---:|---:|
| adjacent | (6,2,0,0); (8,2,0,0) | (12,10,0,0); (16,10,0,0) | 10/2 | 10/2 | 2/10 | 0/12 |
| parallel | (4,2,0,0); (8,2,0,0) | (8,10,0,0); (16,10,0,0) | 10/2 | 10/2 | 2/10 | 0/12 |
| narrow | (4,2,2,2); (8,2,0,0) | (8,10,6,6); (16,10,0,0) | 10/2 | 10/2 | 2/10 | 0/12 |
| depth (Shell only) | — | (8,10,8,8); (16,10,0,0) | 8/4 | 8/4 | 0/12 | 0/12 |

Both orders of `shared` return `(6,2,0,0)` for Connect/private and `(12,8,0,0)`
for Shell. Both orders of `coincident` return `(6,2,0,0)` for Connect/private but
`(12,10,0,0)` for Shell. Shell suppresses rims using original **index** adjacency,
not its coordinate lookup. Thus coincident-but-unindexed boundaries still get two
internal rims even though exterior vertex identities have merged. The exact-index
oracle expects six boundary edges for `shared`, eight for every other pair;
Shell emits exactly those rim counts. This agreement does not certify the resulting
coordinate topology.

For adjacent pairs the exterior common-edge count changes from 0 to 1; for parallel
pairs it changes from 0 to 4, i.e. duplicate exterior faces. The control has one
common exterior edge. For collapsed narrow faces the script's raw edge multiplicity
counter also counts a traversed edge twice *within a face*: do not interpret that
value as an independent inter-face adjacency result. Repeated-index/area diagnostics
are decisive there. Area is the sum of two triangle cross-product norms on original
or emitted coordinates, with exact `==0` for the reported zero counts, not an
application tolerance. No `np.round` oracle is used; it occurs only in the kernels.
All quads fit `max_side_m=3.9`, so these experiments isolate identity with no extra
subdivision. Source trace establishes the same lookup is used for generated grid
points; subdivision-heavy incidence was not separately measured.

**Concrete serialized witnesses (positive sign, zero translation, original order):**

- Connect `narrow/.2`: original first rectangle X endpoints are `0.0` and `2e-09`
  (`0x1.12e0be826d695p-29`); second endpoints are `2.0`, `2.000000002`.
  Output vertices are `[[0,0,0],[0,0,1],[2,0,0],[2,0,1]]`, faces
  `[[0,0,1,1],[2,2,3,3]]`. Both positive-area inputs become zero-area faces.
- Shell/private `.2h` is actually serialized as `2.0000000000000003e-10`
  (`0x1.b7cdfd9d7bdbcp-33`), not an exact decimal .0000000002. Shell's
  first narrow exterior emits `[0,0,1,1]`, retaining `(0,0,0)` and
  `(2.0000000000000003e-10,0,1)` as representatives. Two exteriors and four
  horizontal rims have repeated indices/zero area; the other four rims have area.
  Its input cross norms are about `2e-10`, above the default `tolerance_m**2=1e-14`;
  all convexity signs are likewise above that threshold. This is not a validation bypass.
- Unit-width `parallel/.2` yields identical exterior index sequences:
  Connect `[[0,1,3,2],[0,1,3,2]]`, Shell/private `[[0,1,2,3],[0,1,2,3]]`.
  Their source rectangles were on different Y planes. No face has repeated indices,
  so a repeated-index-only diagnostic would miss this topology change.
- Shell `depth/.2` keeps both unit exteriors intact, but all eight rims collapse to
  patterns such as `[0,0,1,1]`. Positive thickness alone does not protect generated rims;
  the current API has no minimum-thickness-versus-identity check.

**Cell placement and representative order:** for each of adjacent/parallel/narrow,
positive `.2h` and `.4h` merge at shifts 0 and 1.05h but do not merge at .45h.
Negative-coordinate `.2h` and `.4h` merge at all three shifts; negative `.6h` merges
at .45h only. Positive `.6h` never merges in these shifts. Both signs at 1.2h
remain distinct. These statements concern the actual generated binary64 values,
not a universal formula for decimal-cell endpoints. The depth fixture has the same
original Y for both signs and merges at shifts 0 and 1.05h for .2h/.4h only.

Reversing parallel `.2h` face order retains Y=`2e-09` instead of `0.0` in Connect,
and Y=`2.0000000000000003e-10` instead of `0.0` in Shell/private. Counts do not
change. These are the original unrounded coordinates, not the decimal key position.
Corresponding-corner error is measured against each original face/rim before lookup,
not against a rounded reference. Shell's reported maximum includes the binary64
addition of thickness to the offset plane. The probe verifies hex-identical JSON
readback of **all output coordinates and indices** for all 492 calls; no native or
float32 serialization is exercised. Representative examples carry input hex values.

**Alignment and immutability:** 492/492 calls satisfy the assertions. Connect parent
IDs are `[0,1]` relative to submitted order and correctly select caller-owned identities;
Connect has no material argument. Shell has equal face/source/material lengths,
source refs agree with source-face indices, and each exact-index boundary has its rim;
all Shell material IDs remain its API default 0. Private calls preserve the supplied
17/29 material IDs through either submission order, including duplicate output faces.
Vertices, indices, normal arrays and source-ref lists remain byte/value-identical to
snapshots. The private per-face argument is an advanced-indexed copy of the frozen
vertex array; source inspection also confirms `Mesh.face` makes its own `np.array`
copy. Alignment can remain correct while geometry is invalid: provenance is not QA.

### Source mechanism and external evidence

All repository line references below are at the snapshot SHA above. Primary kernel
permalinks: [Connect lines 6–59](https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/6e9f3faa22d0e05889c01e46ce15805ed9168a99/src/dt_ai/geometry/connect.py#L6-L59),
[Shell lines 9–92](https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/6e9f3faa22d0e05889c01e46ce15805ed9168a99/src/dt_ai/geometry/shell.py#L9-L92).

- `connect.py:10–20` propagates opposite-edge counts using exact source index pairs;
  `:22–35` then uses a **global** 8-decimal coordinate key, independent of source
  components or edges. `:30` stores the first original bilinear `point.tolist()`.
  `:37` checks only the maximum side length, so collapse does not violate it.
  Public `:50–59` checks finite arrays and distinct source indices, but not positive
  output area or distinct output indices. The frozen inputs are geometrically convex
  regardless of that limited validation.
- `shell.py:12–20` flips winding when necessary, uses a global 9-decimal key and
  stores first original `v.tolist()`. There is no post-lookup degeneracy check.
  `:26–51,57–67` validate metadata, normals and original quad geometry; `:70–75`
  records source-index incidence. `:77–90` offsets original coordinates and sends
  rims through the same lookup without testing the resulting rim area. The tolerance
  is used for geometric validation/plane solving, **not** as identity key precision.
- First-party [NumPy `round` documentation, Notes](https://numpy.org/doc/stable/reference/generated/numpy.round.html#notes)
  was fetched during this investigation. It says exactly halfway values round to
  nearest even, but also explicitly calls the algorithm “fast but sometimes inexact”
  and describes decimal representation and power-of-ten scaling errors. That source
  explains why treating these keys as an exact decimal or Euclidean tolerance contract
  would be unjustified. The present execution verifies only the frozen non-half-step
  examples; it does **not** establish universal half-even/boundary behavior from literals.

### Scope and verification limitations

The three separately owned weld studies/kernels were not invoked by the standalone
probe, and their contracts are not inferred here. Nonfinite handling, very large
coordinates, float32/native export and the appropriate precision policy are outside
this investigation. Public finite checks are noted only to establish admissibility.
The real-world frequency of sub-step gaps or narrow faces was not sampled.

Harness deviation: although the research card requested no pytest/full suite, the
higher-priority harness explicitly required
`env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider --basetemp=C:/x/pi-t_5937557c`.
That separate call timed out at **400 seconds** with progress at 45%; there is no
final pytest totals line and no full-suite pass claim. Last captured line:
`................................`. No rerun was made. The 492-call research results
above come solely from the standalone NumPy block, not from pytest.

## How it applies (file paths)

Read-only static caller inventory (`rg` across repository Python files, excluding
`data/`), before making reachability claims; references use the same SHA:

| Path / lines | Route and significance |
|---|---|
| `tools/quad_connect.py:7–11` | Compatibility wrapper calls public Connect with default 3.9 m. |
| `tools/prepare_floor_uv.py:10,102–107` | Wrapper caller; remaps materials, finish IDs and parent faces. Subsequent UV work is not a proof that an identity collision is unreachable. |
| `jobs/PSU275/scripts/connect_surface.py:16–32` | Direct Connect; propagates facade/finish by parents and records min/max edges, without a repeated-index rejection at this call site. |
| `jobs/MASHI-LP/scripts/build_master.py:8,70–91` | Direct Connect after shell construction; propagates patch/material arrays and may run `conform` afterward. The latter is a separate algorithm, not evidence that this collision is repaired. Script uses a historical hard-coded root; not executed here. |
| `tools/run_body_shell.py:19–43,48–72` | Reviewed-source public Shell with explicit units, normals, tolerance, refs; audits before save and records failed audit evidence. Public-kernel counterexamples do not prove this whole caller publishes an invalid model. |
| `tools/build_shell_windows.py:26–36,78–122` | Public Shell for BODY (.4 m); private Mesh calls for window frame/pane/rim geometry with materials 1/2. Direct Mesh route has no `shell_body` validation gate. |
| `tests/test_connect_adapter.py:13–23,40–65` | Existing parent/material-decision and shared-edge/winding/immutability controls; no decimal-step collision corpus. |
| `tests/test_shell_adapter.py:14–60` | Existing exterior/rim/provenance, validation, corner and shared-index controls; no decimal-step identity cases. |
| `tests/dcc/connect_readback.py:14–51` | Synthetic Connect native readback test source was inspected, not executed. |
| `tests/test_shell_windows.py:21–35` | Downstream audit examples concern overlap/crossing; not proof of complete coverage of the present inputs. |

The inventory establishes concrete tool routes into both identity tables, not that
any saved real source contains these synthetic pathologies. No dynamic-import
reachability completeness is claimed. Domain context is `docs/domain/geometry.md`
(quad masters, no zero edges, shared surfaces without blind merge-by-distance) and
`docs/domain/areas/body.md` (BODY-J/BODY-X and manual gates). Neither the regulation's
0.002 m duplicate criterion nor the project's .4 m Shell value defines a replacement
coordinate-identity policy. Existing review/acceptance gates remain required.

## Proposed next tasks

### 1. Freeze diagnostic-only kernel characterization

Retain the exact `.2h`, sign +, shift 0 fixtures from this report as future diagnostic
cases, without modifying the identity policy: `connect narrow` → `(V,F,R,Z)=(4,2,2,2)`;
`public shell narrow` → `(8,10,6,6)`; `public shell depth` → `(8,10,8,8)`;
`parallel` → duplicate exterior index cycles with R=Z=0. Pair each with the `.45h`
translation → unmerged signatures from the table. Include exact-index control,
parent/ref/material and hex JSON checks. Expected results describe the current
measurement, not a newly accepted output contract. **Value: M; effort: S.**

### 2. Measure exposure at one reviewed caller boundary

With an explicitly approved source/output owner, first replay the frozen indexed
`shared` → Shell `(12,8,0,0)` and split-index `coincident` → `(12,10,0,0)` through
an in-memory caller diagnostic. Then measure counts of unequal pre-lookup positions
sharing output IDs, repeated-index faces and coordinate displacement on one approved
real input; that real-input count is unknown, not an expected zero. Keep coordinate
and source-index adjacency separate, preserve source hashes and report audit gates
without saving/repairing a production model. No new issue is created here.
**Value: M; effort: M.**

## Open questions

- What identity is intended: source vertex/edge lineage, exact coincident coordinates,
  or a spatial relationship? Is deduplication allowed across disconnected components?
- If spatial identity is intended, what units, precision/tolerance, cell-placement
  invariance and representative-order requirements should it have? No value is chosen.
- Should source-coordinate equality affect Shell boundary-rim suppression, or must
  reviewed source indices remain authoritative? How should provenance then be represented?
- Which diagnostics are mandatory after lookup, and should collisions be reported,
  rejected or repaired? Who authorizes repair and its geometric displacement budget?
- What feature/thickness admissibility is expected at each caller, rather than merely
  accepted by today's kernel validation? Which approved real inputs may be measured?
- Nonfinite and large-coordinate policy remains outside scope; a separate decision
  is required before extending conclusions there. Native readback, real-model exposure,
  review/user acceptance, a completed full-suite result and any PR creation remain undone.
  The driver owns git/PR actions; no push or PR was attempted here. Any eventual PR
  target is exclusively `artsafro/AGR-DigitalTwin-pilot`.

No code, tests, schemas, procedures, dependencies, CI or data files are changed.
`delivery_passed=false`.

