# Component-local signed volume

`component_signed_volumes` is an optional, report-only diagnostic. It does not
change `check_orientation`, `checks.run`, hidden-mesh handling or pass/fail semantics.
It never repairs geometry or sets delivery status. Synthetic evidence remains
`delivery_passed=false`; this helper is not delivery certification.

## API

```python
from twinqa.geometry.component_volume import component_signed_volumes

# meshes: raw mesh-dump dictionaries, not a welded Soup.
rows = component_signed_volumes(meshes)
```

Each mesh has `name` (string), `vertices` (finite real N×3 coordinates) and
`triangles` (integer M×3 vertex indices). Lists and NumPy arrays are supported;
empty lists are accepted. Array shapes must be exact even when empty. Boolean,
complex and floating-point indices, negative/out-of-range indices, non-finite
coordinates and malformed mesh dictionaries raise `ValueError` rather than
being silently cast or wrapped. No triangles means no component rows.

Rows contain:

| Field | Meaning |
|---|---|
| `mesh` | Original mesh name |
| `triangle_ids` | Sorted original local triangle IDs; never welded/reindexed |
| `n_triangles` | Number of triangles in this component |
| `eligible` | All combinatorial/area prerequisites met |
| `reasons` | Empty when eligible; otherwise reason codes below |
| `status` | `measured` or `not_measured` |
| `signed_volume` | Signed cubic input units; `None` when ineligible |
| `sign` | +1, -1; `None` for zero volume or ineligible component |

Meshes stay separate. Within each mesh, triangles connect only through shared
undirected **index edges**, never coincident coordinates or a vertex alone.
Rows follow mesh order, then minimum triangle ID. Inputs are not modified.

## Eligibility and precision

- `open_or_nonmanifold_edge`: an edge does not have exactly two uses by distinct triangles.
- `inconsistent_winding`: a two-use manifold edge is not traversed in opposite directions.
  A boundary/nonmanifold edge alone does not also produce this reason.
- `degenerate_triangle`: repeated indices or triangle area ≤ 1e-12 × component bbox diagonal².
- `vertex_not_single_fan`: incident triangles at a vertex are disconnected **within the component**.

For eligible components, float64 coordinates are recentered on the mean of their
unique vertices, then `math.fsum(dot(a-r, cross(b-r, c-r))) / 6` is evaluated.
This avoids large-offset cancellation in the tested coordinate range. It does
not guarantee numerical stability for every possible magnitude/shape.

Negative volume is an orientation fact, **not automatically a defect**: a nested
cavity shell may legitimately be negative. Eligibility does not prove absence of
self-intersection. Open facades, arbitrary imported shells and cavity semantics
need independent domain interpretation. A positive scene sum cannot certify
individual components. No outwardness gate or generalized certification is added.

## Synthetic evidence

[Hypothesis #93](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/97) tested
100 m outer / 0.2 m inner boxes, two packings, three rigid transforms (including
7.5e6 m translation), and outward/inverted/open/inconsistent variants (24 cases).
The prior experiment measured max relative volume error 3.958e-9, 24/24 exact
component memberships and 12/12 control abstentions. The baseline missed 6/6
occluded inverted solids; the diagnostic made zero closed-component sign mistakes.
These are synthetic observations, not arbitrary imported-model guarantees or a
speed claim. Production regression tests reproduce the matrix with ≤1e-6 relative
error, three identical repeats, unchanged baseline results and the corrected
boundary-edge reason. See `tests/qa/test_component_volume.py`.
