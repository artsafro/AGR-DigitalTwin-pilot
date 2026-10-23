# xView: what remains between the 0.219 s contact core and the production gate?

Research card t_ba54882d (no GitHub issue). Technical findings only, `delivery_passed=false`. Pinned source:
`origin/main` = `dbbb717470079b7b3bdf4e889f3cf2a850c67a40` (the worktree HEAD; `git diff origin/main HEAD -- src` is empty).
Read-only: no source edit, no pytest, no DCC. Every `path:line` below is at that SHA. "verified" = I ran or read it;
"claimed" = prose of a doc/PR that I did not re-measure.

## Summary

- **Verified: nothing in `src/` imports the fast core.** `git grep inv_xview_fast|xview_lists` over `src` and `tools` finds only the
  definition (`inv_xview_fast.py:207`) and `tools/qa/xview_bench.py:292` (a string-named `importlib.import_module(...).xview_lists`);
  the other users are `tests/ops/test_inv_xview_fast.py`. The gate calls `inv_xview.part_report` (`xview_gate.py:182`); `mesh_report`
  does the same (`inv_xview.py:561`); `xview_state*` call `_pairs_found` (`inv_xview.py:728-738`, `:806`). So #553's merge did not change
  any production path (issue #556 "Adopt" is the open owner).
- The fast core is **a different, smaller function**, not a faster `part_report`: it returns only the contact rule (`inv_xview_fast.py:207-224`).
  It drops the area rule, pair `kind`, `separation_m`, tolerance/profile handling, the "no faces" report and the per-face detail
  the gate builds.
- **Measured (synthetic, 9 frozen controls, current APIs):** an area-only pair (crossing triangles, no contained vertex) is
  `face_pairs=[[1,2,"area",0.0]]` in `part_report`/`part_gate` (gate `passed=false`) and **empty in `xview_lists`**. Swapping
  the engine as-is would turn that gate verdict into a pass.
- Contract differences found by running both: empty faces (report vs `ValueError`), unvalidated tolerances in `part_report`
  (NaN `face_m` -> silent `()` on a mesh that has an `area+contact` pair), error message wording, `kind`/`separation` absent.
- Cost shape (synthetic only, TOW02 NPZ **not available locally -> not measured**): on two 400-quad sheets 3 mm apart,
  `part_report` 0.31 s vs `xview_lists` 0.012 s as separate full calls; cProfile of `part_report` puts 0.214 s of 0.319 s inside one
  `shapely` set operation called from `_area`. These are different algorithms with different outputs; the ratio is not "the speed-up".
- Bounded adoption (two proposals below): run the contact core first, then the **area rule only on candidates the area rule can
  still hit**, plus a pair-level parity check; incremental state is a second, separate step.

## Findings

### F1. Call graph (verified)

| Caller | Line | Callee | Engine |
|---|---|---|---|
| `xview_gate.gate_report` | `xview_gate.py:212,217,230` | `part_gate` (after `tol.validate()`) | |
| `xview_gate.part_gate` | `xview_gate.py:168,182` | `inv_xview.part_report(p.name, mesh, tol)` | baseline |
| `inv_xview.xview_report` / `xview_overlaps` | `inv_xview.py:517,526,529` | `part_report` | baseline |
| `inv_xview.mesh_report` | `inv_xview.py:551,561` | `part_report` | baseline |
| `inv_xview.part_report` | `inv_xview.py:503-514` | `vertex_pairs` (`:112`) + `face_pairs` (`:494`) | baseline |
| `inv_xview.face_pairs` | `inv_xview.py:494-500` | `_prepare` + `_pairs_found` (`:453`) -> `_contact` (`:375`) and `_area` (`:399`) per candidate | baseline |
| `inv_xview.xview_state` | `inv_xview.py:728-738` | `_pairs_found` (full) | baseline |
| `inv_xview.xview_state_incremental` | `inv_xview.py:741`, `:806` | `_pairs_found(..., active=hot[owner])` | baseline |
| `xview_lists` | `inv_xview_fast.py:207-224` | `vertex_pairs` (the baseline's own, `:218`) + `_triangulate` + `contact_pairs` (`:137`) | fast |
| `tools/qa/xview_bench.py` | `:292` | `importlib.import_module(a.candidate).xview_lists` | bench only |

`inv_xview_fast` imports from `inv_xview` (`inv_xview_fast.py:27`: `AREA_EPS_M2, XviewTolerance, _dot, _polygon_triangles,
vertex_pairs`) — it reuses the baseline's vertex pairing and polygon triangulation but not `_contact`, `_area`, `_grid_pairs`.
`inv_xview` does not import `inv_xview_fast`.

Docs agree: `docs/experiments/autoresearch-xview-speed.md:118-120` (claimed, read) says adopting "means running the area rule
only on the near-parallel pairs, or keeping the area rule as a separate slower pass"; table rows `:33,35` give 0.219 s (claimed,
quiet board, TOW02 export-v005 contact selection only).

### F2. What the gate consumes and `xview_lists` does not return (verified from `xview_gate.py:168-209`)

| Gate/report field | Source today | In `xview_lists` output? |
|---|---|---|
| `face_pairs[].kind` (`contact` / `area` / `area+contact`) | `_kind` (`inv_xview.py:490`) | **No.** pairs are `(i, j)` only |
| `face_pairs[].separation_m` | `_area` separation, `None` for pure contact | **No** |
| area-only pairs (hence `faces`, `face_pairs_by_kind["area"]`, `fpairs`, `passed`) | `_area` shapely overlap > `AREA_MIN_M2` with separation <= `face_m` | **No** — `contact_pairs` only fires on a contained vertex (`inv_xview_fast.py:137-204`) |
| `faces` (ids in any pair, incl. area-only) / per-face `partners`, `kinds` | `part_report` `faces` | `xview_faces` only (contact ids) |
| `offenders` strings (`f"{part} f{i}/f{j}: {kind}, {mm} mm"`, `"no faces"`) | `part_report` `inv_xview.py:503-514` | No |
| `passed` for an empty face list | `part_gate` -> `reasons=["no faces"]` | `ValueError` instead (`inv_xview_fast.py:216`) |
| tolerance by profile (`tolerance_for`) | `gate_report` `xview_gate.py:217` | none; default `XviewTolerance()` only |
| `bowtie_vertices`, `vertex_pairs[].kind` | `fans`, `_weld_map` over `vertex_pairs` + faces | vertex pairs: **yes, identical function** |
| state: `face_pairs` + sha256, `faces`, `xview_faces`, `links`, `runs` | `_state` (`inv_xview.py:713`) | No: state needs `kind` + `separation` per pair |

Replacing `part_report` with `xview_lists` directly therefore loses (a) every area-only pair, (b) `kind`, (c) separation,
(d) the report-instead-of-raise behaviour for empty meshes, (e) the pair inventory the incremental state hashes. (a) changes the verdict.

### F3. Frozen controls and current-API outputs (verified; script in the reproduction block, run once, output sha256 below)

Each control is two polygons; `A = (0,0,0),(2,0,0),(0,2,0)` unless stated. Values are raw outputs, not a policy.

| Control (construction) | `part_report.face_pairs` | `part_report.xview_faces` | `xview_lists.face_pairs` / `xview_faces` | `part_gate` passed / `overlapping_faces` |
|---|---|---|---|---|
| clean (B = A shifted by 10 m) | `[]` | `[]` | `[]` / `[]` | true / 0 |
| contact-only (B apex `(1,1,0)` on A's hypotenuse, body outside) | `[[1,2,"contact",null]]` | `[1,2]` | `[[1,2]]` / `[1,2]` | false / 2 |
| area-only (hexagram: two equilateral triangles, side 6, no vertex of one inside the other) | `[[1,2,"area",0.0]]` | `[]` | **`[]` / `[]`** | **false / 0** |
| combined (B = `(.5,.5),(3,.5),(.5,3)` coplanar) | `[[1,2,"area+contact",0.0]]` | `[1,2]` | `[[1,2]]` / `[1,2]` | false / 2 |
| boundary, B plane at z = 0.005 exactly | `[[1,2,"area+contact",0.005]]` | `[1,2]` | `[[1,2]]` / `[1,2]` | false / 2 |
| boundary, B plane at z = 0.0050001 | `[]` | `[]` | `[]` / `[]` | true / 0 |
| vertex-pair only (B vertex 1.9 mm from A vertex, B turned away) | `[]`, `vertex_pairs=[[1,4,0.0019]]` | `[]` | `[]` / `[]`, `vertex_pairs` identical | false / 0 (`kind: "bowtie"`) |
| concave notch (dart `(0,0),(4,0),(1,1),(0,4)`, triangle `(2,2),(5,2),(2,5)` in the notch, outside) | `[]` | `[]` | `[]` / `[]` | true / 0 |
| concave inside (triangle vertex `(1,0.4)` inside the dart) | `[[1,2,"area+contact",0.0]]` | `[1,2]` | `[[1,2]]` / `[1,2]` | false / 2 |

Could not be independently constructed: a **contact-only pair on the 5 mm boundary** (both boundary controls came out
`area+contact`, because a parallel plane that holds a vertex over A also overlaps A in area; a contact-only separation needs
a body outside A, which I did not build at z = 0.005 — left unconstructed, not guessed). An **area-only pair with separation
> 0** was also not built (the hexagram is coplanar, separation 0.0).

Malformed input (`xview_lists` / `part_report` / `mesh_report` / `part_gate`, all outputs in the run):

| Input | `part_report`, `mesh_report`, `part_gate` | `xview_lists` |
|---|---|---|
| faces `[]` | `part_report` returns empty tuples (offender `"no faces"`); `mesh_report` `passed=false,count=1`; gate `passed=false,"no faces"` | `ValueError: no faces: nothing to check (never an empty pass)` |
| 0 vertices, face (0,1,2) | `ValueError: face 0: index outside the vertices` | `ValueError: face index outside the vertices` (no face number) |
| out-of-range index; 2-sided face; repeated index; bool; fractional; NaN/inf vertex; vertices (3,2); self-intersecting quad | `ValueError` naming face/cause | `ValueError`, same cause (message differs for out-of-range and bool/fractional: "face index ...") |
| one zero-area triangle only | empty, `passed=true` (gate) | empty |
| NaN/inf vertex through `part_gate` | `ValueError: part 'p': vertices must be finite` | `ValueError: vertices must be finite` |

Tolerances on the **combined** control (a pair exists), second run: `part_report` does not validate `XviewTolerance` —
`face_m=NaN` -> `()` (a pair that exists is silently dropped), `face_m=-1` -> `()`, `face_m=inf` -> the pair, `parallel_cos_min=0` -> the pair;
`mesh_report` and `xview_lists` raise `ValueError` for all four; `gate_report` validates (`xview_gate.py:217`) but `part_gate` called directly does not. (Reported, not changed: no
policy proposed here.) An earlier run of the same tolerances on the *clean* control returned `[]` for NaN — uninformative, which is why the second run exists.

Incremental/state (verified): on the combined control with labels `["a","b"]`, `xview_state_incremental(..., changed=["b"])` and
`changed=[]` both equal `xview_state`; `contact_only_state_pairs=[[1,2,"contact",null]]`, `area_only_state_pairs=[[1,2,"area",0.0]]`;
dropping `face_pairs` from `previous` -> `ValueError ... incomplete report`; replacing it with `[]` ->
`ValueError ... do not match face_pairs_sha256` (the #554 review P1-2 is fixed at this SHA). The active mask exists only in the baseline
(`_grid_pairs(..., active)`, `inv_xview.py:306-362`); `contact_pairs` has no `active` parameter, so the incremental path cannot call it as-is.

### F4. Cost attribution (synthetic only; TOW02 NPZ not measured)

Search for a local TOW02 NPZ (`jobs/vyatskaya-tow02/outputs/review-v002/xview/arrays_ours.npz`, named in `tools/qa/xview_bench.py:170`):
that directory does not exist in the checkout and `data/` is out of bounds; one bounded filesystem search under `C:/x/job-retro-vyatskaya-tow02-*` found no `.npz`. **TOW02 timing: not measured.**
(An unbounded `find` of the whole tree timed out at 180 s and was abandoned; absence is "not found where looked", not "does not exist".)

Synthetic: two n x n quad sheets (n = 20, 800 polygons), second sheet shifted half a cell, one run each, Python 3.14.7, numpy 2.5.3,
other Hermes workers running on the same PC (load unknown; one run per figure, no medians — treat as order of magnitude):

| Case | `part_report` full call | `face_pairs` full call | `xview_lists` full call | pairs found by each |
|---|---|---|---|---|
| sheets 3 mm apart | 0.308 s wall / 0.313 s CPU | 0.314 s | 0.012 s | `part_report`: 1521 `area+contact`, 800 xview faces; `xview_lists`: 1521 pairs, 800 faces |
| sheets 0.5 m apart | 0.189 s | 0.177 s | 0.004 s | none / none |

cProfile of one `part_report` call (cumulative, own run, profile overhead included): 3 mm case `_area` 0.273 of 0.319 s, one
`shapely.set_operations` call 0.214 s; `_contact` two calls 0.012 s total; `_pairs_found` self 0.015 s. 0.5 m case: `_area` 0.156 of 0.181 s, shapely set operation 0.122 s **although no pair was found** — why the area prefilter
(`inv_xview.py:399-420`) still lets those candidate pairs reach shapely was not investigated. Do not subtract these rows: the two
functions compute different things; `xview_lists` here is the contact-only metric, never the full-gate speed.
Whole run (all 9 controls, malformed, state, both timing cases, profiling): 6.7 s wall.

### F5. Why the baseline cost is the area rule (verified for the synthetic case, claimed for TOW02)

In the synthetic case almost all baseline time is the shapely intersection for triangle pairs the `_area` function evaluates.
For TOW02 export-v005 the experiment doc claims baseline 40 s -> 0.219 s for the contact selection (`autoresearch-xview-speed.md:33,68`)
and the #554 review measured 7.25 s for the faster baseline with 185 contact faces; neither re-measured here.

## How it applies to this repository

- Gate: `src/dt_ai/ops/xview_gate.py:182` is the single seam. Everything after it (`:183-209`) uses `r.face_pairs` with `kind`/`separation`
  and `r.vertex_pairs`; a drop-in must reproduce those tuples exactly.
- Kernel: `src/dt_ai/ops/inv_xview.py:453-487` (`_pairs_found`) is where contact and area are decided per candidate triangle pair;
  `:471` (`_grid_pairs`) is the broad phase the area rule rides on. The bounded change lives here, not in `inv_xview_fast.py`.
- State/incremental: `inv_xview.py:728-815` use `_pairs_found` directly and need per-pair `kind` and `separation`.
- Bench/oracle: `tools/qa/xview_bench.py` compares only contact lists (`xview_faces`, `vertices`) — it cannot detect a missed area-only pair.

## Proposed next tasks

1. **Pair-level parity harness for contact core + area residual (S).** Title: "xView: prove contact-core + area-residual parity at pair level
   before adoption". Scope: a test/probe that, for the TOW02 NPZ (when present) and the F3 controls plus a seeded generated set (random
   coplanar triangle pairs, crossing-without-contained-vertex pairs, boundary ±1e-7 m), compares `face_pairs(mesh, tol)` (kind,
   separation) with a candidate = `xview_lists` pairs ∪ area pairs computed only for candidates the contact core missed. Input -> expected
   output pairs: (control `area_only_hexagram`) -> `[(1,2,"area",0.0)]`; (`contact_only`) -> `[(1,2,"contact",None)]`; (`combined`) ->
   `[(1,2,"area+contact",0.0)]`; (`clean`) -> `[]`; each also in the TOW02 case -> 185 contact faces, identical full pair list.
   Timing: separate full calls per implementation, N >= 5 alternating A/B in one process, wall + CPU, load recorded; report
   per-phase cProfile; never report the contact-only core as the gate time. Advances #556 (adopt owner; not roadmap-labelled) — `Advances #371` (Ground v015 xView-clean gate needs the faster check).
2. **Area rule on the candidate set only, behind the existing `part_report` signature (M).** Title: "xView: run `_area` only where it can still
   hit, keep `part_report` outputs bit-identical". Scope: inside `inv_xview`, reuse `_pairs_found` broad phase but call `contact_pairs`-style
   per-vertex search to classify contact, and call `_area` only on near-parallel pairs that survive the prefilter; keep the active-mask
   path (`inv_xview.py:806`) on the old code until a second card. Inputs -> outputs: every F3 control and the parity set of task 1 must
   yield identical `PartXviewReport` (`vertex_pairs`, `face_pairs` with kind and separation, `faces`, `xview_faces`, `offenders`);
   malformed inputs keep the baseline's `ValueError`s and `part_report`'s `no faces` report. Timing: the same A/B protocol on the TOW02
   NPZ, full call, plus the 0.5 m-apart synthetic case to explain the unexplained shapely cost of F4. Depends on task 1. `Advances #371`.

## Open questions for the user

1. Should an area-only pair stay a gate failure after adoption (current behaviour, kernel's extra rule) or is the 3ds Max xView
   selection (contact only) the authoritative gate for some profiles? (Decision, not a research fact.)
2. Where is a current TOW02 NPZ (`arrays_ours.npz`) kept now that `jobs/.../review-v002/xview/` is absent from this checkout?
3. Should `part_report`/`part_gate` validate `XviewTolerance` the way `mesh_report`, `xview_lists` and `gate_report` do? (F3: NaN `face_m` silently drops an existing pair.)

## Reproduction (self-contained; run from a checkout of the pinned SHA)

```
git checkout dbbb717470079b7b3bdf4e889f3cf2a850c67a40   # or a worktree at that SHA
PYTHONPATH=src uv run python xview_handoff_probe.py --time > out.json
```
`xview_handoff_probe.py` (sha256 `785266be5be3f3d05b6b3841f6d4913752608fe8dde667e03f184456bf740996`; its `out.json` sha256 `027cd780711310e6b3c7501148dcefd1170c9c9a065c50d32302b348f2169d78`
— the timing section differs run to run, the rest is deterministic):

```python
"""Read-only probe: current xView APIs on frozen synthetic controls. Usage: python xview_handoff_probe.py [--time]
Run from a checkout of the pinned SHA with `uv run python <file>` (imports dt_ai from the checkout)."""
import cProfile, hashlib, io, json, pstats, sys, time, traceback
import numpy as np
from dt_ai.ops import inv_xview, xview_gate
from dt_ai.ops.inv_quads import PolyMesh
from dt_ai.ops.inv_xview_fast import xview_lists

TOL = inv_xview.XviewTolerance()
S3 = 3 ** 0.5


def T(*pts):
    return [list(map(float, p)) for p in pts]


def two(a, b):
    return np.array(T(*a, *b)), [(0, 1, 2), (3, 4, 5)]


A = [(0, 0, 0), (2, 0, 0), (0, 2, 0)]
CONTROLS = {
    "clean": two(A, [(10, 0, 0), (12, 0, 0), (10, 2, 0)]),
    "contact_only": two(A, [(1, 1, 0), (3, 3, 0), (3, 4, 0)]),  # B apex on A's hypotenuse, body outside
    "area_only_hexagram": two([(0, 0, 0), (6, 0, 0), (3, 3 * S3, 0)],
                              [(6, 3 * S3 / 3 * 2, 0), (0, 3 * S3 / 3 * 2, 0), (3, -S3, 0)]),
    "combined": two(A, [(0.5, 0.5, 0), (3, 0.5, 0), (0.5, 3, 0)]),
    "boundary_sep_0.005_exact": two(A, [(0.5, 0.5, 0.005), (3, 0.5, 0.005), (0.5, 3, 0.005)]),
    "boundary_sep_0.0050001": two(A, [(0.5, 0.5, 0.0050001), (3, 0.5, 0.0050001), (0.5, 3, 0.0050001)]),
    "vertex_pair_only_1.9mm": two(A, [(10, 0, 0), (12, 0, 0), (10, 2, 0)]),  # patched below
    "concave_notch_outside": (np.array(T((0, 0, 0), (4, 0, 0), (1, 1, 0), (0, 4, 0), (2, 2, 0), (5, 2, 0), (2, 5, 0))),
                              [(0, 1, 2, 3), (4, 5, 6)]),
    "concave_inside": (np.array(T((0, 0, 0), (4, 0, 0), (1, 1, 0), (0, 4, 0), (1, 0.4, 0), (5, 0.4, 0), (5, 5, 0))),
                       [(0, 1, 2, 3), (4, 5, 6)]),
}
v, f = CONTROLS["vertex_pair_only_1.9mm"]
v[3] = [0.0019, 0, 0.0]            # 1.9 mm from vertex 0 of A, B otherwise far/rotated
v[4] = [0.0019, 0, 5.0]
v[5] = [0.0019, 5, 5.0]
CONTROLS["vertex_pair_only_1.9mm"] = (v, f)
MALFORMED = {
    "faces_empty": (np.array(T(*A)), []),
    "no_vertices": (np.zeros((0, 3)), [(0, 1, 2)]),
    "two_sided_face": (np.array(T(*A)), [(0, 1)]),
    "index_out_of_range": (np.array(T(*A)), [(0, 1, 3)]),
    "repeated_index": (np.array(T(*A)), [(0, 1, 1)]),
    "nan_vertex": (np.array(T((0, 0, 0), (1, 0, 0), (0, float("nan"), 0))), [(0, 1, 2)]),
    "inf_vertex": (np.array(T((0, 0, 0), (1, 0, 0), (0, float("inf"), 0))), [(0, 1, 2)]),
    "bool_index": (np.array(T(*A)), [(True, 1, 2)]),
    "fractional_index": (np.array(T(*A)), [(0.0, 1.5, 2)]),
    "bad_shape_vertices": (np.zeros((3, 2)), [(0, 1, 2)]),
    "degenerate_zero_area_only": (np.array(T((0, 0, 0), (1, 0, 0), (2, 0, 0))), [(0, 1, 2)]),
    "self_intersecting_quad": (np.array(T((0, 0, 0), (1, 1, 0), (1, 0, 0), (0, 1, 0))), [(0, 1, 2, 3)]),
}


def j(x):
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, (tuple, list)):
        return [j(i) for i in x]
    if isinstance(x, dict):
        return {str(k): j(w) for k, w in x.items()}
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return float(x)
    return x


def run(fn):
    try:
        return {"ok": j(fn())}
    except Exception as e:  # record, do not interpret
        return {"raised": f"{type(e).__name__}: {e}"}


def apis(v, f, tol=TOL):
    out = {}
    out["part_report"] = run(lambda: (lambda r: {"vertex_pairs": r.vertex_pairs, "face_pairs": r.face_pairs,
                                                  "vertices": r.vertices, "faces": r.faces, "xview_faces": r.xview_faces,
                                                  "offenders": r.offenders})(
        inv_xview.part_report("p", PolyMesh(np.asarray(v, float), tuple(tuple(x) for x in f)), tol)))
    out["mesh_report"] = run(lambda: inv_xview.mesh_report(v, f, "NPM", tol))
    out["xview_lists"] = run(lambda: xview_lists(v, tuple(tuple(x) for x in f), tol))

    def gate():
        p = xview_gate.Part("p", np.asarray(v, float), tuple(tuple(x) for x in f), None)
        r = xview_gate.part_gate(p, tol, "as-stored")
        return {k: r[k] for k in ("passed", "reasons", "overlapping_vertices", "overlapping_faces", "face_pairs_by_kind",
                                  "xview_faces", "bowtie_vertices")} | {"face_pairs": r["face_pairs"],
                                                                      "vertex_pairs": r["vertex_pairs"]}
    out["part_gate"] = run(gate)
    return out


def digest(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def grid_two_layers(n, dz):
    """Two n x n quad sheets (distinct vertices), second at z=dz and shifted by half a cell: dense contact+area pairs."""
    def sheet(off, z):
        xs, ys = np.meshgrid(np.arange(n + 1) + off, np.arange(n + 1) + off)
        return np.stack([xs.ravel(), ys.ravel(), np.full(xs.size, z)], 1)
    v1, v2 = sheet(0.0, 0.0), sheet(0.5, dz)
    k = n + 1
    q = [(i * k + j, i * k + j + 1, (i + 1) * k + j + 1, (i + 1) * k + j) for i in range(n) for j in range(n)]
    f = q + [tuple(x + len(v1) for x in t) for t in q]
    return np.vstack([v1, v2]), f


def timing():
    res = {}
    for n, dz in ((20, 0.003), (20, 0.5)):
        v, f = grid_two_layers(n, dz)
        t = tuple(tuple(x) for x in f)
        mesh = PolyMesh(v, t)
        row = {"polys": len(f)}
        for name, fn in (("part_report", lambda: inv_xview.part_report("p", mesh, TOL)),
                         ("face_pairs", lambda: inv_xview.face_pairs(mesh, TOL)),
                         ("xview_lists", lambda: xview_lists(v, t, TOL))):
            t0 = time.perf_counter(); c0 = time.process_time(); r = fn()
            row[name] = {"wall_s": round(time.perf_counter() - t0, 4), "cpu_s": round(time.process_time() - c0, 4)}
            if name == "part_report":
                row["n_face_pairs_by_kind"] = {k: sum(p[2] == k for p in r.face_pairs) for k in ("contact", "area", "area+contact")}
                row["n_xview_faces"] = len(r.xview_faces)
            if name == "xview_lists":
                row["lists_n_face_pairs"] = len(r["face_pairs"]); row["lists_n_xview_faces"] = len(r["xview_faces"])
        pr = cProfile.Profile(); pr.enable(); inv_xview.part_report("p", mesh, TOL); pr.disable()
        s = io.StringIO(); pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(14)
        row["cprofile_part_report_cum_top"] = [l[:150] for l in s.getvalue().splitlines() if "inv_xview" in l or "shapely" in l][:10]
        res[f"two_layers_n{n}_dz{dz}"] = row
    return res


if __name__ == "__main__":
    out = {"python": sys.version.split()[0], "numpy": np.__version__,
           "src_sha256": {p: digest(p) for p in ("src/dt_ai/ops/inv_xview.py", "src/dt_ai/ops/inv_xview_fast.py",
                                                   "src/dt_ai/ops/xview_gate.py")},
           "controls": {k: {"vertices": j(v), "faces": f, "results": apis(v, f)} for k, (v, f) in CONTROLS.items()},
           "malformed": {k: {"results": apis(v, f)} for k, (v, f) in MALFORMED.items()}}
    out["tolerance_variants"] = {k: run(lambda t=t: inv_xview.part_report("p", PolyMesh(*[np.array(T(*A, (10, 0, 0), (12, 0, 0), (10, 2, 0))), ((0, 1, 2), (3, 4, 5))]), t).face_pairs)
                                 for k, t in (("neg_face_m", inv_xview.XviewTolerance(face_m=-1)),
                                              ("nan_face_m", inv_xview.XviewTolerance(face_m=float("nan"))),
                                              ("cos_zero", inv_xview.XviewTolerance(parallel_cos_min=0.0)))}
    out["tolerance_variants_fast"] = {k: run(lambda t=t: xview_lists(np.array(T(*A)), ((0, 1, 2),), t))
                                      for k, t in (("neg_face_m", inv_xview.XviewTolerance(face_m=-1)),
                                                   ("nan_face_m", inv_xview.XviewTolerance(face_m=float("nan"))))}
    # state / incremental: two parts, labels per face
    v, f = CONTROLS["combined"]
    lab = ["a", "b"]
    st = inv_xview.xview_state(v, f, lab)
    inc = inv_xview.xview_state_incremental(v, f, lab, st, ["b"])
    inc0 = inv_xview.xview_state_incremental(v, f, lab, st, [])
    broken = dict(st); broken.pop("face_pairs")
    trunc = dict(st); trunc["face_pairs"] = []
    out["state"] = {"full": j(st), "incremental_changed_b_equals_full": j(inc) == j(st),
                    "incremental_changed_none_equals_full": j(inc0) == j(st),
                    "missing_face_pairs": run(lambda: inv_xview.xview_state_incremental(v, f, lab, broken, [])),
                    "emptied_face_pairs": run(lambda: inv_xview.xview_state_incremental(v, f, lab, trunc, [])),
                    "contact_only_state_pairs": j(inv_xview.xview_state(*CONTROLS["contact_only"], lab)["face_pairs"]),
                    "area_only_state_pairs": j(inv_xview.xview_state(*CONTROLS["area_only_hexagram"], lab)["face_pairs"])}
    if "--time" in sys.argv:
        out["timing"] = timing()
    print(json.dumps(out, indent=1, default=str))
```

The second tolerance run (F3) used:

```python
import numpy as np
from dt_ai.ops import inv_xview as X
from dt_ai.ops.inv_xview_fast import xview_lists
from dt_ai.ops.inv_quads import PolyMesh
v=np.array([[0,0,0],[2,0,0],[0,2,0],[.5,.5,0],[3,.5,0],[.5,3,0]],float);f=((0,1,2),(3,4,5))
for n,t in (("nan_face_m",X.XviewTolerance(face_m=float("nan"))),("cos_zero",X.XviewTolerance(parallel_cos_min=0.0)),("neg_face_m",X.XviewTolerance(face_m=-1)),("inf_face_m",X.XviewTolerance(face_m=float("inf")))):
    for api,fn in (("part_report",lambda:X.part_report("p",PolyMesh(v,f),t).face_pairs),("mesh_report",lambda:X.mesh_report(v,f,"NPM",t)["face_pairs"]),("xview_lists",lambda:xview_lists(v,f,t)["face_pairs"])):
        try: r=fn()
        except Exception as e: r="RAISE %s: %s"%(type(e).__name__,str(e)[:80])
        print(n,api,r)
```

Source hashes (sha256): `inv_xview.py` a377b27181216914a7e3d289c3c9231713bbf7a7a4acf9bf11900011c796004c,
`inv_xview_fast.py` a5d37850ead2f7863735c9ff6354a40d79de7f129ef3952bc24f3a9c3a4fa253,
`xview_gate.py` f9a70c339a85f4d66a1004ddce0468f8938f3394afb253ab76bac7b157fbfa7c. Input fixtures: none on disk (all synthetic, in the script).

## Sources

Verified by reading/running (no external web sources): `src/dt_ai/ops/inv_xview.py`, `inv_xview_fast.py`, `xview_gate.py`,
`tools/qa/xview_bench.py`, `tests/ops/test_inv_xview_fast.py`, `docs/experiments/autoresearch-xview-speed.md`,
`docs/domain/validation.md` (xView row, `:144`), pilot PR #554 review comment (claimed numbers 37.7 s -> 7.25 s, not re-measured),
pilot issue #556. N = 12.

## Agent trace

Card t_ba54882d, profile dt-worker-cursor, driver model claude-sonnet-5-5, no Cursor launch (research, read-only; one
probe script run through `uv run`). Not measured: TOW02 NPZ timing; the cause of the 0.122 s shapely cost on the 0.5 m case; machine load;
repeated-run medians. Created a `.venv` in the card's worktree via `uv run` (ignored by git).
