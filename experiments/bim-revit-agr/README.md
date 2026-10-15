# Synthetic IFC4 semantic-loss probe

Throwaway offline transport of a project `Spec` into IFC4 and back through tessellation. It does not import Blender, call Revit, or accept a delivery. `delivery_passed` is always false.

```text
uv run --with ifcopenshell python experiments/bim-revit-agr/ifc_probe.py --inputs COPY_ROOT --out NEW_ROOT --repeats 3
```

`COPY_ROOT` is a copy that contains `*/spec.json` (the bench cases live in directories named `bench-b01-box`, `bench-b02-corner-niche`, `bench-b02t-terrace`). The tool never reads the repository `benchmark/` tree. `NEW_ROOT` must not exist; it is created exclusively. Optional `baseline.json` is recorded only. No speedup is claimed: spec validation and IFC intake are different work.

Each spec is written twice, in metres and in millimetres. The building placement is a 23 degree Z rotation plus a translation of (100, -50, 7) m. Storeys keep the spec level names. Expanded floors get a 0.20 m slab whose top is the level and whose bottom is 0.20 m below it (not an AGR plate), and 0.20 m walls up to the next level. Each opening is an `IfcOpeningElement` void (`IfcRelVoidsElement`) with an `IfcWindow` fill (`IfcRelFillsElement`) inset by 0.02 m. The void is 1 mm deeper than the wall on each face so the Boolean is not coplanar; the reader reports that rough-opening body, not the fill. Names are synthetic keys only. Provenance in each ledger is the IFC SHA-256 and GlobalIds.

`read_ledger(path)` reopens the file from disk. It does not take a spec. Storey coordinates come from the placement chain scaled by the length unit once. Mesh coordinates come from the geometry engine in metres. Wall `volume_cut_m3` uses default opening subtraction; `volume_uncut_m3` disables it. Missing host, fill, or spatial containment is an issue taken from the relations, not from equal names or boxes.

The runner recomputes expected storey coordinates, slab boxes and volumes (shapely area), rough-opening boxes, and cut wall volumes from the copied spec. Clean agreement is 1 mm and 1e-5 m3. Each clean file is intaken `--repeats` times (default 3); the median excludes generation. Each clean file is then cloned three ways by deleting one void relation, one fill relation, or one containment link. Those 18 files are intaken once and must flag the missing association.

Unsupported, and not a production result: recovering a spec contour from IFC, rounded corners, roofs, materials and families, georeferencing, and a real Revit export.

`results.json` holds compact samples, deviations, and timings. One ledger JSON per IFC sits in `ledgers/`. IFC files sit in `ifc/`.

## Relation multimap (`new-case`)

`relation_multimap.py` is marked as `new-case` (no registered pattern applies from `docs/domain/patterns/INDEX.md`). It provides a report-only census helper for synthetic IFC void, fill, and containment relations, capturing raw evidence (`relation_id`, `source_id`, `endpoint_id`) without picking arbitrary winners. Conflicting associations are reported as unresolved cardinality conflicts (`diagnostics` with `kind="cardinality"`, `status="unresolved"`, and `selected_endpoint=None`).

Boundary: synthetic-only evaluation on generated IFC models. It claims no real Revit export compatibility and no production adapter policy.
