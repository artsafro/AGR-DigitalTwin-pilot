# Synthetic IFC Offline Intake Pilot

This directory contains experimental offline intake utilities for synthetic IFC4 models.

> [!WARNING]
> This is a synthetic IFC pilot, **not** a native Revit importer and **not** a generic IFC importer.
> `delivery_passed=false`: no customer delivery or production acceptance claims are made.

## Classification & Provenance

- **Classification**: Experimental `new-case` scoped strictly to synthetic IFC fixtures.
- **Provenance**: Hypothesis [#107](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/107); report: [../../docs/experiments/hyp-107.md](../../docs/experiments/hyp-107.md).
- **Pattern Status**: This is not a proven generic IFC pattern and no registry pattern is claimed.
- **Contracts**: Synthetic one-wall-per-edge constraint; strict mode is default with report-only explicit geometric opt-in; `delivery_passed=false`.

## Wall Binding Modes

The pilot provides two wall binding strategies for associating IFC wall elements with floor contour edges:

1. **Strict mode (`binding="strict"`) [Default]**:
   - Requires walls to be named following the bounded synthetic contract `W0000..Wnnnn`.
   - Each wall index maps directly to the corresponding contour edge index.
   - Refuses un-named, renamed, or arbitrary family/type wall names.

2. **Geometric mode (`binding="geometric"`) [Explicit opt-in]**:
   - Name-independent, report-only alternative binder.
   - Ignores `wall.Name` and `wall.Tag` completely.
   - Walls are sorted deterministically by `GlobalId` and entity id for diagnostics; `Name` and `Tag` are ignored.
   - Resolves wall-to-edge binding purely from building-local coordinate placements and contour edge frames.

### Explicit Opt-in Example

```python
from pathlib import Path
import pilot

# Default: strict contract (fails if walls are renamed)
spec, report = pilot.extract(Path("model.ifc"))

# Explicit opt-in: geometric binding (accepts renamed synthetic walls)
spec, report = pilot.extract(Path("model.ifc"), binding="geometric")
```

Unknown binding modes raise `pilot.IntakeError`:
```python
pilot.extract(Path("model.ifc"), binding="unknown")  # raises IntakeError
```

## Geometric Binder Contract & Numerical Limits

- **Origin Tolerance**: `1e-4` metres (`ORIGIN_TOLERANCE_M`).
  Max component residual of building-local wall origin to edge start `[x, y, storey_z]` must be `<= 1e-4` m.
- **Normalized X-Axis Tolerance**: `1e-4` (`AXIS_TOLERANCE`).
  Max component residual of normalized local X-axis to edge unit direction `[dx, dy, 0.0]` must be `<= 1e-4`.
- **Unique 1-to-1 Placement**:
  - Cardinality must match exactly: `len(walls) == len(edges)`.
  - Exactly one eligible edge per wall.
  - Exactly one eligible wall per edge.
  - Fail-closed: returns complete `{edge_idx: wall}` mapping or raises `UnresolvedBinding`. Never returns partial mappings or name fallbacks.

## Diagnostic Evidence Fields

When geometric binding fails, `pilot.UnresolvedBinding` (subclass of `pilot.IntakeError`) is raised with a structured, JSON-compatible `evidence` dictionary:

- `reason`: String code (`"cardinality_mismatch"`, `"unresolved_mapping"`, `"invalid_or_duplicate_wall_global_id"`).
- `n_walls`: Total wall count in the storey.
- `n_edges`: Total edge count in the contour.
- `walls_without_edge`: Sorted list of wall `GlobalId` strings that matched no edge.
- `walls_with_multiple_edges`: Dictionary `{wall_gid: [sorted edge indices]}` for ambiguous walls.
- `edges_without_wall`: Sorted list of integer edge indices that matched no wall.
- `edges_with_multiple_walls`: Dictionary `{"<edge_idx>": [sorted wall_gids]}` for edges matched by multiple walls.
- `eligible_pairs`: Sorted list of `[wall_gid, edge_idx, origin_error, axis_error]`.
- `invalid_ids`: Sorted list of invalid or duplicate `GlobalId` strings (if any).

Successful calls record evidence on `pilot.bind_walls_geometric.last_evidence`, reset on each invocation.

## Synthetic-Only Limitations

Geometric binding in this pilot is strictly scoped to synthetic fixtures:
- No reversed axes or mirrored wall coordinate systems.
- No split or segmented walls along a contour edge.
- No shifted location lines (origin must be at the edge vertex).
- No Revit Axis semantics or native family parsing.
- No production adapter integration.
- No CRS (Coordinate Reference System) or MSK-77 georeferencing transforms.
- Delivery status: `delivery_passed=false`.
