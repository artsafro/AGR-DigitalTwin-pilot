# Kernel Mesh: invalid triangle-index provenance before xView checks

## Summary

- Pinned base: `origin/main` = `6e9f3faa22d0e05889c01e46ce15805ed9168a99` (2026-10-20).
- `invariants.Mesh` eagerly applies `np.asarray(triangles, dtype=int)`: fractional values are truncated, booleans become 0/1, and original dtype/value provenance is gone before invariant calls.
- This affects every repository call path that constructs `Mesh` before `xview_overlaps`, notably operation/contour results and direct scene construction; it is not introduced by `_as_poly`.
- Direct `PolyMesh` and `mesh_report` reject booleans/fractions; `mesh_report` additionally rejects non-integer NumPy face arrays by dtype.
- Strict validation at `Mesh` would be behavior-breaking for float-typed but integral faces and silently tolerated fractional/bool inputs; repository usage is predominantly integer-generated, but current contract is `dtype=int`.
- Frozen probe ran against the pinned source: `Mesh([[.1,1.9,2.9]])` stores `[0,1,2]`; the other two paths preserve/reject the raw values.
- Empty `mesh_report` can return a report, while empty `xview_overlaps` fails closed; neither outcome is delivery validation.
- No production behavior changed; report only, `delivery_passed=false`.

## Findings

### Version and evidence boundary

All code citations below refer to pinned `main` SHA `6e9f3faa22d0e05889c01e46ce15805ed9168a99`; line numbers are from that commit. PR #380 body and review history were read through `gh pr view 380 --repo artsafro/AGR-DigitalTwin-pilot`; it documents a previous defect fixed by preserving input validation in `_as_poly`/`mesh_report`, while explicitly leaving shared `Mesh` coercion unchanged. This report independently ran the small Python matrix below on that source. These are repository observations, not claims about external clients.

### Boundary trace

1. **Shared triangle constructor:** `src/dt_ai/ops/invariants.py:41-55`. `Mesh.__post_init__` casts vertices to float and triangles to platform `int` at lines 46-47, then shape/range-checks at 48-52. Thus integer-valued floats, fractional values and booleans become integer data before any invariant sees them. For finite `.1,1.9,2.9`, stored values become `0,1,2`; negative/out-of-range after conversion still raise. NaN raises `ValueError: cannot convert float NaN to integer`; infinity raises `OverflowError: cannot convert float infinity to integer`.
2. **Polygon mesh constructor:** `src/dt_ai/ops/inv_quads.py:63-89` (`PolyMesh`). At lines 75-81 it rejects Python/NumPy bool and any non-`int`/`np.integer`, then checks face length, range and repeated indices; it stores tuples of Python ints. It does not accept even exactly integral float values.
3. **Invariant adapter:** `src/dt_ai/ops/inv_xview.py:99-104` `_as_poly`. Existing `PolyMesh` passes through; `Mesh` is converted from already-cast `mesh.triangles` at line 103. No second coercion occurs, but provenance was lost at constructor time. `xview_report` / `xview_overlaps` at lines 369-389 route scene members through `part_report`; empty selection yields a failing `InvariantResult` (lines 381-389).
4. **Report API:** `src/dt_ai/ops/inv_xview.py:403-415`. `mesh_report` converts integer NumPy arrays to lists, rejects other NumPy face arrays by dtype at 408-410, then sends Python face elements into strict `PolyMesh` without `int()` conversion at 411-412. Python list of floats/bools therefore fails at `PolyMesh`; integer ndarray works. Empty faces are constructible and return a report, but not a validated delivery.
5. **Geometry guidance:** `docs/domain/geometry.md:69-70` describes NumPy operation-kernel meshes and editable-master topology; it does not specify accepted runtime index scalar types or float-integral policy.
6. **PR #380:** https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/380 — its review identified malformed indices being silently coerced by `mesh_report` and `_as_poly` and required raw validation; the merged fix addresses those paths but records shared `Mesh` coercion as out of scope.

### Frozen probe matrix (observed)

Probe executed with `uv run python` (repository dependencies); inputs were three vertices and one face unless noted. “xView” means a scene built via `Mesh` and then `xview_overlaps`; raw values cannot reach xView through this typed path without first constructing `Mesh`. The input object was not mutated in the controls; constructors create/convert stored arrays. No overlap/count result is a delivery-validation claim.

| Raw faces | `Mesh` result | `PolyMesh` result | `mesh_report` result | xView after `Mesh` |
|---|---|---|---|---|
| `[[0,1,2]]` list | `int64 [[0,1,2]]` | tuple `(0,1,2)` | returns report | returns `count=0` on this isolated triangle |
| `np.array([[0,1,2]], int)` | `int64 [[0,1,2]]` | tuple `(0,1,2)` | returns report | `count=0` |
| `np.array([[0.,1.,2.]])` | `int64 [[0,1,2]]` | `ValueError: face 0: index np.float64(0.0) is not an integer` | `ValueError: face indices are not an integer array (dtype float64)` | `count=0`; original floats no longer observable through mesh |
| `[[.1,1.9,2.9]]` | `int64 [[0,1,2]]` | `ValueError: face 0: index 0.1 is not an integer` | same `PolyMesh` error | `count=0`; truncation masked malformed input |
| `[[False,True,2]]` | `int64 [[0,1,2]]` | `ValueError: face 0: index False is not an integer` | same `PolyMesh` error | `count=0`; bool provenance masked |
| `[[-1,1,2]]` | `ValueError: triangle index outside the vertices` | `ValueError: face 0: index outside the vertices` | same `PolyMesh` error | same `Mesh` range error |
| `[[0,1,3]]` | `ValueError: triangle index outside the vertices` | `ValueError: face 0: index outside the vertices` | same `PolyMesh` error | same `Mesh` range error |
| empty `(0,3)` integer ndarray | stores `int64 (0,3)` | empty tuple | returns report | one-part scene result; not evidence of valid delivery |
| `[[0., NaN,2.]]` | `ValueError: cannot convert float NaN to integer` | `ValueError: face 0: index 0.0 is not an integer` (iteration stops at first element) | same `PolyMesh` error | same Mesh error |
| `[[0., Inf,2.]]` | `OverflowError: cannot convert float infinity to integer` | `ValueError: face 0: index 0.0 is not an integer` | same `PolyMesh` error | same Mesh error |

**Immutability control:** no operation mutates supplied faces in the tested cases; `Mesh` stores a converted array, while `PolyMesh` stores immutable tuples. A caller retaining the original array can itself still observe its raw values, but passing the resulting `Mesh` onward cannot recover them. Reproduction:

```python
import numpy as np
from dt_ai.ops.invariants import Mesh
from dt_ai.ops.inv_quads import PolyMesh
from dt_ai.ops.inv_xview import mesh_report, xview_overlaps
v = np.array([[0.,0,0],[1,0,0],[0,1,0]])
cases = [
    ("int list", [[0,1,2]]), ("int ndarray", np.array([[0,1,2]], int)),
    ("float integral", np.array([[0.,1.,2.]])), ("fractional", [[.1,1.9,2.9]]),
    ("bool", [[False,True,2]]), ("negative", [[-1,1,2]]), ("out of range", [[0,1,3]]),
    ("empty", np.empty((0,3), int)), ("nan", [[0.,float("nan"),2.]]),
    ("inf", [[0.,float("inf"),2.]]),
]
for label, faces in cases:
    before = faces.copy() if isinstance(faces, np.ndarray) else repr(faces)
    for name, call in (
        ("Mesh", lambda: Mesh(v, faces)),
        ("PolyMesh", lambda: PolyMesh(v, tuple(tuple(row) for row in faces))),
        ("mesh_report", lambda: mesh_report(v, faces)),
        ("xview via Mesh", lambda: xview_overlaps({"p": Mesh(v, faces)}, "NPM")),
    ):
        try:
            result = call()
            print(label, name, "OK", getattr(result, "triangles", getattr(result, "faces", result)))
        except Exception as exc:
            print(label, name, type(exc).__name__, str(exc))
    if isinstance(faces, np.ndarray):
        assert np.array_equal(faces, before, equal_nan=True)
```

### Repository call-site inventory

Static search at pinned SHA found these relevant production constructors:

- `src/dt_ai/ops/operations.py:92,100,148`: operation results call `Mesh`; arrays are generated from existing integer topology / literal integer triangle tuples, with `np.array(tris)` at line 100 (inferred integer when source elements are ints). The xView scene check can inspect only after this constructor.
- `src/dt_ai/ops/contour.py:76-96,191`: contour triangulation/caps cast generated indices explicitly with `dtype=int` at lines 76, 87 and construct `Mesh` at 96 / 191. These are intended integer topology, not evidence of an intentional float/bool API.
- `src/dt_ai/ops/inv_xview.py:103,412`: adapter and report boundaries described above. `mesh_report` caller(s) should be audited for upstream data contract before changing it; PR #380 identifies build-report usage.
- Tests construct `Mesh` mostly from integer tuples / integer arrays, and explicitly use integer empty arrays (e.g. `tests/ops/test_contour.py:234`; `tests/ops/test_inv_texel.py:40`). Tests are repository evidence, not external-client evidence.

No inspected in-repository production caller deliberately supplies float or bool triangle indices. However `Mesh` is a public dataclass whose field annotation/comment says integer triangles (`invariants.py:43`) and whose implementation explicitly casts to `int`; whether external callers rely on float-integral arrays is unknowable from repository search. Strict rejection would also remove the current, though unsafe, acceptance of fractional/bool inputs. Treat it as a compatibility change until API consumers and intended float-integral policy are decided.

## How it applies to this repository

The defect boundary is `invariants.Mesh.__post_init__`, upstream of the shared operation-kernel invariant. `inv_xview._as_poly` is not the loss point; after constructing `Mesh`, it sees normalized integer triangles. Direct `PolyMesh` and `mesh_report` retain and validate raw values. Current documented geometry rules require valid topology but do not resolve whether `Mesh` should accept integral floats, so no policy is inferred here. Report-only research; `delivery_passed=false`.

## Proposed next tasks

1. **Decision and consumer audit for triangle index input types** — inventory downstream/external consumers and choose whether `Mesh` accepts only integer scalars or also exactly integral floats; publish a compatibility/migration decision before changing the contract. Example eventual strict behavior: raw `[[.1,1.9,2.9]]` -> named `ValueError`, rather than stored `[[0,1,2]]`. Value: M; effort: S.
2. **Boundary regression suite after policy approval** — add constructor-level regressions and generated probes for Python/NumPy bool, fractional/integral float, nonfinite, negative/range, and empty shaped arrays; separately assert original input immutability and xView cannot certify coerced invalid topology. Example: `[[False,True,2]]` -> named error before invariant execution. Value: M; effort: S.

## Open questions for the user

- Should `Mesh` reject every float dtype, including `[[0.,1.,2.]]`, or accept exactly integral finite floats while rejecting fractional/nonfinite values?
- Should bool indices receive a distinct diagnostic, and should validation be centralized in `Mesh` or at each public boundary?
- Which downstream API consumers, if any, rely on current dtype coercion? Until answered, do not change the shared contract.
