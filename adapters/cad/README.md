# CAD adapter: SPOZU DWG -> Ground inputs

`adapters/cad` reads a SPOZU (СПОЗУ) drawing and returns one typed result for the layered-cake Ground
procedure (`.agents/skills/model-ground/SKILL.md`, steps 1-3 and 5). Issue #195; inventory #194
(`docs/research/spozu-vatutino-inventory.md`).

| File | Role |
|---|---|
| `dwg.py` | DWG -> DXF through the AutoCAD 2025 core console (`dcc_batch.py acad`, `DXFOUT` 2018). Always on a copy in a work dir; the source hash is checked before and after. Wrapper path: `DT_DCC_BATCH`. ODA is not used; the DXF library alone is not a DWG reader. |
| `spozu.py` | Config-driven reader (ezdxf + shapely): boundary polygon, covering polygons per type (hatches -> closed contours, holes kept, clipped to the plot), planting points (species label, schedule position), MAF points (product label, position when the schedule has one), elevation points (also inside container blocks). Units -> metres from `$INSUNITS` or the config. |
| `configs/<project>.yaml` | The per-project layer map. No layer name lives in code. First config: `vatutino_dom2.yaml` (from the #194 layer map). |

Usage:

```
uv run python -m adapters.cad.spozu <copy.dwg|file.dxf> --config adapters/cad/configs/vatutino_dom2.yaml \
    --workdir C:/x/<card> --json C:/x/<card>/ground_inputs.json
```

`SpozuResult.base_covering` is the covering type with the largest area in the plot (the base plane of
method C); `to_dict()` gives GeoJSON geometries in metres.

Validation findings (never repaired, never guessed): `open_contour`, `self_intersecting_contour`,
`degenerate_contour`, `overlapping_coverings` (pairwise area above `overlap_tol_m2`), `point_outside_boundary`,
`unmapped_layer` (effective layer of a model-space entity or of expanded block content, neither mapped nor in
`ignore_layers`; one finding per layer with model-space/in-block counts and example `ref`s; the graphics inside
point symbols are not expanded and never count), `boundary_not_found`,
`boundary_ambiguous`, `elevation_unparsed`, `label_missing` (a label configured as `attrib:<TAG>` is absent or
empty: the point keeps `label=None`, the block name is never substituted), `nested_cycle`, `nesting_too_deep`
(more than `MAX_NESTING` insert levels), `nested_unsupported` (block content on a mapped layer, or a nested
INSERT, that cannot be transformed, e.g. a bulged polyline under non-uniform scaling). Unknown units raise
`SpozuConfigError`. A hatch polyline path with `is_closed=0` is open unless its last vertex is its first.

Block content: every INSERT that is not a point symbol (planting, MAF, `z`-mode elevation) is expanded with
its composed transform (rotation, scale, mirror, nesting, MINSERT cells; a nested MINSERT is split into cells in its block's
coordinates before the parent transform, so row/column spacing is transformed too); an entity on layer `0` takes the
insert's layer. Every boundary/covering/point carries `ref`, the provenance path `<insert>>...><entity>`
(`#k` = MINSERT cell); `handle` is the source entity, `container` the enclosing insert path. A nested
boundary is selected in the config by its `ref`.

Tests: `tests/test_adapters_cad_spozu.py` (synthetic fixtures). `-m acad` runs the core-console round trip;
`DT_SPOZU_VATUTINO=<local copy .dwg/.dxf>` with `-m acad` runs the Vatutino counts.

Not implemented yet: Placement (UCS/МСК-77, zero mark, control points) with evidence and reversible
transforms; the Ground mesh, relief, MAF/Flora models, IFC.
