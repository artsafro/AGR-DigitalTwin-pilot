# IFC intake: what src/ contract would turn the #76 prototype into an adapter

Research card t_cbc6e5fa, 2026-10-15. Read-only on code: no Revit, no `data/`, no IFC was exported or parsed for
this note. Sources are cited inline: `[V]` = I read the code or ran the command myself, `[S]` = only the source says so.

## Summary

- The #76 prototype (`experiments/revit-ifc-offline-intake/pilot.py`, PR #76, open) writes a `Spec` **directly** from IFC.
  It only works because its own synthetic generator puts one wall per slab-contour edge, names them `W0000..Wnnnn`,
  and takes the **slab profile** as the floor contour. Real Revit exports do neither (findings 1-3).
- The repository already has the right seam: the Revit route is `twin-floor/1` band exports -> `revit_twin.to_dump` ->
  mesh dump -> `dt spec extract` (`src/dt_ai/spec/revit_twin.py`, `src/dt_ai/cli/main.py:205-206`) `[V]`. The extractor
  derives the contour and the `wall` index of every opening from wall prisms on **location lines** (#29). An IFC reader
  that emits the same `twin-floor/1` records makes the naming hack unnecessary: wall identity becomes
  `GlobalId` + `Tag` (Revit ElementId) + `Axis` line, and the contour-edge index is derived downstream, as for Revit.
- Minimal contract (section "Proposed contract"): IFC4 only; units from `IfcUnitAssignment`; an explicit frame
  entry in `object.json` `frames["<file>.ifc"]` (never inferred from `IfcBuilding`); walls from the `Axis`
  representation; openings via `IfcRelVoidsElement` + `IfcRelFillsElement`; every unsupported fact reported
  as a named stop or `unknown`, never dropped.
- K01 rows the prototype did **not** cover: roof covering, parapet top, parapet height (prototype sets `roof=None`);
  `opening_kinds_not_in_verdict` (grille) is vacuous without `kind`; `spec_extract` thresholds (`glass_frame_m`,
  `depth_exception_m`) need glass and reveal depth, which the prototype never reads. The `geometry` block of K01 is
  a delivery-mesh check, outside intake.
- Three S/M next tasks are proposed; the first one needs no real export.

## Findings

### 1. How the Revit IFC exporter names and identifies walls and openings

All from the `Autodesk/revit-ifc` source at master `3d7195e808` (2026-09-23) `[V: read the code]`.

- **Wall `Name`** = `Family:Type:ElementId`, e.g. `Basic Wall:Generic - 200mm:345678`, unless the user sets
  an `IfcName` / `NameOverride` parameter
  ([NamingUtil.cs](https://github.com/Autodesk/revit-ifc/blob/master/Source/Revit.IFC.Export/Utility/NamingUtil.cs),
  `GetNameOverride` lines ~201-215; the default name builder returns `fullName + ":" + CreateIFCElementId(element)`, ~line 503).
  Two walls of the same type differ only by the id suffix; a name carries no geometric order.
- **Wall `Tag`** = Revit ElementId as text, unless `IfcTag` / `TagOverride` is set (`GetTagOverride`,
  `CreateIFCElementId` in the same file).
- **`GlobalId`** = IFC-compressed form of a GUID derived from the element (`GUIDUtil.CreateGUIDString(Element)`,
  `ConvertToIFCGuid`), or the stored `IFC GUID` parameter
  ([GUIDUtil.cs](https://github.com/Autodesk/revit-ifc/blob/master/Source/Revit.IFC.Export/Utility/GUIDUtil.cs)).
  The export option "Store the IFC GUID in an element parameter after export" writes it back to the RVT `[S]`
  ([IFC Export Setup Options, Revit 2026 help](https://help.autodesk.com/cloudhelp/2026/ENU/Revit-DocumentPresent/files/GUID-E029E3AD-1639-4446-A935-C9796BC34C95.htm)).
- **Split walls**: with "Split Walls, Columns, Ducts by Level" one Revit wall becomes several `IfcWall`s; each
  part gets a sub-element GUID (`CreateSubElementGUID(element, subElementIndex + SplitInstanceStart - 1)`), but
  `Name`/`Tag` stay those of the one Revit element
  ([WallExporter.cs](https://github.com/Autodesk/revit-ifc/blob/master/Source/Revit.IFC.Export/Exporter/WallExporter.cs)
  ~lines 865, 1578-1590, 1764). So `Tag` is **not unique** per `IfcWall`; `GlobalId` is.
- **Wall representations**: the exporter writes an `Axis` representation from the wall's location curve
  (`CreateAxisShapeRepresentation`, ~line 1287) and exports `IfcWallStandardCase` only when an axis exists
  (~1401-1452). The body is an extrusion, an extrusion with `IfcBooleanClippingResult` (walls attached to roofs,
  `AddClippingsToBaseExtrusion`, ~585-690), a **tessellated** body in IFC4 Reference View (~636-687), or a BRep
  fallback when clippings meet openings (~608-612). The prototype accepts only the first.
- **Openings**: Revit has no physical opening objects for doors/windows; the exporter **always** creates an
  `IfcOpeningElement` per door/window `[S]`
  ([Autodesk support](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Opening-and-element-are-always-exported-together-to-IFC-from-Revit.html)).
  Its `Name` = the insert's `IfcName` override, else **the host wall's Name**; `ObjectType` = `"Opening"` or
  `"Recess"` (opening length < host width); linked by `IfcRelVoidsElement`
  ([OpeningUtil.cs](https://github.com/Autodesk/revit-ifc/blob/master/Source/Revit.IFC.Export/Utility/OpeningUtil.cs)
  ~440-477). Door/window openings get a GUID from `doorElem + levelHash + " IfcOpeningElement: " + index`, and only
  the first opening of a door/window gets an `IfcRelFillsElement`
  ([DoorWindowDelayedOpeningCreator.cs](https://github.com/Autodesk/revit-ifc/blob/master/Source/Revit.IFC.Export/Utility/DoorWindowDelayedOpeningCreator.cs)
  ~210-260). Consequence: opening names are useless for identity; the filler (`IfcDoor`/`IfcWindow`) and its `Tag` are the key.
- **`IsExternal`** (`Pset_WallCommon`) comes from an `IsExternal` parameter or the wall type Function
  ([CategoryUtil.cs](https://github.com/Autodesk/revit-ifc/blob/master/Source/Revit.IFC.Export/Utility/CategoryUtil.cs)
  `IsElementExternal`). In this repository it is **not** a safe filter: `revit_twin.py` reads walls of every
  function because KPP1 marks plinth cladding as inner walls `[V]`.
- **Coordinate base**: Shared Coordinates (default), Survey Point, Project Base Point, Internal, plus two "in True
  North" variants (`SiteTransformBasis`) `[S]` ([help page above](https://help.autodesk.com/cloudhelp/2026/ENU/Revit-DocumentPresent/files/GUID-E029E3AD-1639-4446-A935-C9796BC34C95.htm);
  secondary summary of the enum: [mintlify revit-ifc docs](https://mintlify.wiki/Autodesk/revit-ifc/export/coordinate-reference)).
  The same RVT therefore gives different raw coordinates per export setup.

### 2. What the IFC schema itself guarantees

buildingSMART IFC4.3 sources, `buildingSMART/IFC4.3.x-development` master `5d08761e63` (the HTML site returned 403 to
curl, the Markdown sources are the same text) `[V: read]`:

- `IfcWall` with a material layer set "is always represented geometrically by an 'Axis' and a 'SweptSolid' shape
  representation (or by a 'Clipping' geometry based on 'SweptSolid')"; the straight axis is a two-point
  `IfcPolyline` or trimmed `IfcLine` "parallel to the x-axis of the object coordinate system"; other walls may be
  'Brep' / 'SurfaceModel' only ([IfcWall.md](https://github.com/buildingSMART/IFC4.3.x-development/blob/master/docs/schemas/shared/IfcSharedBldgElements/Entities/IfcWall.md)).
  So `Axis` is the IFC equivalent of the Revit location line the extractor already uses (#29), but only for
  layered walls.
- `IfcRelVoidsElement` is one-to-one, "implies a boolean operation of subtraction" ([IfcRelVoidsElement.md](https://github.com/buildingSMART/IFC4.3.x-development/blob/master/docs/schemas/core/IfcProductExtension/Entities/IfcRelVoidsElement.md));
  a door/window is `IfcOpeningElement <- IfcRelFillsElement -> IfcDoor`, and the opening has **no**
  `IfcRelContainedInSpatialStructure` ([IfcRelFillsElement.md](https://github.com/buildingSMART/IFC4.3.x-development/blob/master/docs/schemas/core/IfcProductExtension/Entities/IfcRelFillsElement.md)).
  The prototype's `storey_of(host)` already takes the storey from the host, which matches.
- `IfcOpeningElement.PredefinedType` `OPENING` vs `RECESS`; omitted/`NOTDEFINED` means no assumption
  ([IfcOpeningElement.md](https://github.com/buildingSMART/IFC4.3.x-development/blob/master/docs/schemas/core/IfcProductExtension/Entities/IfcOpeningElement.md)).
- `IfcBuildingStorey.Elevation` "is for informational purposes only"; placement decides
  ([IfcBuildingStorey.md](https://github.com/buildingSMART/IFC4.3.x-development/blob/master/docs/schemas/core/IfcProductExtension/Entities/IfcBuildingStorey.md)).
  The prototype already uses the placement chain and has a test for a wrong `Elevation` `[V]`.
- `IfcMapConversion` maps the engineering system to a map CRS with one `Scale`, rotation from
  `XAxisAbscissa/XAxisOrdinate` and `Eastings/Northings/OrthogonalHeight`
  ([IfcMapConversion.md](https://github.com/buildingSMART/IFC4.3.x-development/blob/master/docs/schemas/resource/IfcRepresentationResource/Entities/IfcMapConversion.md)).
  It is the only standard place for MSK-77 data; the prototype ignores it.

### 3. IfcOpenShell helpers that replace prototype code

From the IfcOpenShell API docs `[S]` (the prototype uses 0.9.0 pinned, `[V]` in `pilot.py`):
`ifcopenshell.util.unit.calculate_unit_scale` (already used) ([unit](https://docs.ifcopenshell.org/autoapi/ifcopenshell/util/unit/index.html));
`util.representation.get_representation(element, context, "Axis")` and `get_reference_line(wall)` — "the reference
axis that goes in the +X direction" ([representation](https://docs.ifcopenshell.org/autoapi/ifcopenshell/util/representation/index.html));
`util.element.get_openings`, `get_filled_void`, `get_container` ([element](https://docs.ifcopenshell.org/autoapi/ifcopenshell/util/element/index.html)).
The prototype scans `f.by_type("IfcRelVoidsElement")` per opening (quadratic) and hand-rolls the storey lookup.

### 4. What the prototype does, read from its code `[V]`

`pilot.py` (777 lines, branch `experiment/revit-ifc-offline-intake`): `length_scale` accepts only `IfcSIUnit`
METRE (+prefix); `extract()` requires exactly one placed `IfcBuilding`; storeys from placement; **one `IfcSlab` per
storey, its swept polyline profile is the floor contour**; walls must be single `IfcExtrudedAreaSolid` bodies,
upright; `bind_walls` requires `len(walls) == len(contour edges)`, names `W%04d`, and origin/X axis on the edge within
0.1 mm; openings: exactly one `IfcRelVoidsElement` to an `IfcWall`, box = kernel vertices in host placement;
`frame.to_object` = inverse of the raw `IfcBuilding` placement scaled to metres; `roof=None`,
`opening_depth_default_m=0.4`; no `kind`, glass, `depth_m` exception, `level_from/level_to`, terraces, decor.

## How it applies to this repository

The existing chain and where an IFC reader plugs in `[V]`:

| Stage | File | Input contract |
|---|---|---|
| Live export | `tools/source/measure_spec_revit_twin.mjs` | revit-http bridge, writes index + band folders |
| Band records | `floor.json` `schema: "twin-floor/1"` | walls: `id`, `locationLine`, `thickness`, `bboxMin/Max`, `function`, `curved`; openings: `id`, `hostId`, `kind`, `point`, `hand`, `width`, `sill`, `head`, `height`, `bboxMin/Max`, `materials`/`transparency`; `curtainPanels`; band `{band, top, dir}` |
| Geometry | `reference.obj` | objects `<kind>_<revitId>` (curved walls, roofs) |
| Dump | `src/dt_ai/spec/revit_twin.py` `to_dump` / `load` | index `kind: "revit-twin"`, `levels`, `revit_levels`, `revit_roofs` |
| Spec | `dt spec extract --dump ... --object jobs/<ID>/object.json` (`src/dt_ai/cli/main.py:196-215`) | mesh dump + `object.json` `frames[<source>]` (`src/dt_ai/spec/mesh.py:83`) |
| Compare | `src/dt_ai/spec/compare.py` `compare_specs` | two specs + two reports (`roof.plane_m`, `roof.parapet_top_m`) + `tolerances.json` |

`jobs/KPP1/object.json` already keys frames by source (`"SM_Kpp_1.fbx"`, `"revit"`) with a `derived_from`
proof `[V]`. An IFC source is a third key; its matrix depends on the exporter's Coordinate Base (finding 1).
For KPP1 (Project Base Point = internal origin, angle 0 per `object.json`) a Project-Base-Point or Internal
export should give identity; Shared or Survey would not. This must be checked, not assumed.

`adapters/revit/README.md` states the adapter is not implemented `[V]`; the natural home is
`adapters/revit/ifc_intake.py` (or `src/dt_ai/spec/revit_ifc.py` beside `revit_twin.py`, if the user prefers
`src/` — open question 1).

### Proposed contract (minimal)

1. **Output** = a `revit-twin`-compatible index (`kind: "revit-twin"`, `source: "ifc"`) whose bands carry
   `schema: "twin-floor/1"` records plus `reference.obj`; `dt spec extract` and `compare_specs` stay unchanged.
   No `Spec` is written by the reader.
2. **Provenance** per file: SHA-256, `FILE_DESCRIPTION` view definition, `IfcApplication` name/version, schema,
   unit scale, coordinate-base guess (`unknown` unless the header states it), and per element `GlobalId`,
   `Tag`, `Name`.
3. **Units**: length scale from `IfcUnitAssignment`; any `IfcConversionBasedUnit` (feet) is either scaled
   explicitly or a stop; never default to metres.
4. **Frame**: records stay in the IFC project (WCS) frame, scaled to metres; the object system comes only from
   `object.json` `frames["<file>.ifc"]` with `derived_from`. `IfcSite`/`IfcBuilding` placements and
   `IfcMapConversion` are **reported**, not applied. (The prototype's building-local frame drops this information.)
5. **Wall identity**: `id` = `GlobalId`; `revit_id` = `Tag` when it parses as an integer, else `null`. `locationLine`
   from the `Axis` representation (2-point polyline/trimmed line -> straight; trimmed circle -> `curved: true` and
   body mesh into `reference.obj`); `thickness` from `IfcMaterialLayerSetUsage` sum, else from the body width
   across the axis; `bboxMin/Max` from the kernel mesh. A wall without `Axis` -> body mesh only + an `unknown_axis`
   fact. No `W0000` names anywhere.
6. **Openings**: walk `IfcRelVoidsElement` from each wall; filler via `IfcRelFillsElement`: `IfcDoor` -> `kind: door`,
   `IfcWindow` -> window (glass decided as in `revit_twin._openings`: transparent material, else grille);
   no filler -> `kind: null` + `unfilled_opening` fact; `RECESS` -> recess fact (not an opening). `point`, `hand`,
   `width`, `sill`, `head` from the opening body in the host axis frame; `hostId` = host `GlobalId`.
7. **Unsupported / unknown facts** are a list in the index, each `{fact, element GlobalId, reason}`, and each one
   maps to an extractor stop or question; counts per kind are in the report. Nothing is silently skipped
   (rule 5 of the extractor: every stop listed).

### Gap table

| Fact | Prototype source (`pilot.py`) | Real-export risk | Test |
|---|---|---|---|
| Length unit | `length_scale`: SI METRE only | Revit writes project units; a feet project gives `IfcConversionBasedUnit` -> rejected (claim not verified on a real file) | fixture with `IfcConversionBasedUnit` FOOT: scaled or named stop |
| Object frame | `file_to_building_metres` = inverse `IfcBuilding` placement | Coordinate Base (Shared/Survey/Project/Internal) moves the origin; the building frame is not `object.json`'s object system; MSK-77 needs `IfcMapConversion` | same model exported with two bases -> identical records after `frames[...]`; frame never inferred |
| Storey elevation | placement chain, not `Elevation` | Revit levels that are not floors (KPP1: -4,200, +7,700, +8,650) also become storeys | storey list -> `revit_levels` mapping from `object.json`, unmapped storeys reported |
| Floor contour | one `IfcSlab` profile per storey | KPP1 contour comes from walls at `contour_at_m` (plinth, cladding); slabs have holes, several per storey, or are tessellated | no slab needed: contour from wall prisms via `to_dump`, B01/B02 parity |
| Wall identity | `W%04d` name bound to slab edge | Names are `Family:Type:ElementId`; split-by-level walls share `Tag`; count != contour edges | real-style names + shuffled order + one split wall -> same spec |
| Wall location line | not read (body profile only) | `Axis` exists for layered walls; absent for in-place/BRep walls | wall without `Axis` -> `unknown_axis` fact, body mesh used |
| Wall body | single `IfcExtrudedAreaSolid` | Clipping (roof-attached), tessellated (Reference View), BRep fallback | one fixture per representation type, kernel bbox within 1 mm |
| Opening host | exactly one `IfcRelVoidsElement` to `IfcWall` | also hosted in `IfcCurtainWall`, slabs (shafts), `IfcWallStandardCase` (IFC2x3) | curtain-hosted window -> curtain opening record; slab void -> reported, not an opening |
| Opening kind | none | door/window only via `IfcRelFillsElement`; grilles are windows without transparent material | filled door/window/grille fixtures -> `kind`; grille stays out of the verdict |
| Opening name | `O%04d` (ignored) | Name = host wall name; only first opening of a filler has `IfcRelFillsElement` | multi-opening window: no duplicate opening records |
| Recess vs opening | not distinguished | `ObjectType`/`PredefinedType` `RECESS` | recess fixture -> not counted as opening |
| Glass / reveal depth | not read | `spec_extract.glass_frame_m`, `depth_exception_m` need pane extents and reveal depth | window with frame: `glass_w/h` within 0.2 m frame rule |
| Roof, parapet | `roof=None` | `IfcRoof` aggregating `IfcSlab ROOF`, slopes; parapet walls on the roof storey | roof covering plane and parapet top within 30 mm vs `revit_roofs` |
| Curved walls | rejected | Revit exports trimmed-circle axis; extractor needs native mesh | curved wall -> `curved: true` + mesh in `reference.obj` |
| Provenance | SHA-256, GlobalIds | + `Tag`, application/version, view definition, coordinate base | index carries them; missing header -> `unknown`, not a default |

### K01 rows and coverage

`compare_specs` rows (`src/dt_ai/spec/compare.py`) against `benchmark/bench-k01-kpp1/tolerances.json` `[V]`:

| Row | Threshold | #76 prototype | Through the proposed contract |
|---|---|---|---|
| level count, level elevation | equal / 0.03 m | covered (synthetic) | covered if storeys map via `revit_levels` |
| floors | equal | covered | covered |
| contour area / Hausdorff / kinks | 0.02 rel / 0.05 m / equal | covered, but contour = slab profile | covered via wall prisms (same path as Revit twin) |
| opening count, opening bbox | equal / 0.05 m | covered (no `kind`, so grilles would count) | covered; grilles excluded by `kind` |
| grille rows (info) | not in verdict | vacuous (0 = 0) | real |
| roof covering, parapet top, parapet height | 0.03 m | **uncovered** (`roof=None`) | needs roof records (task 3) |
| `spec_extract` glass_frame_m, depth_exception_m | 0.2 m / 0.1 m | **uncovered** | needs window/glass records |
| `geometry` block (bbox, silhouette, triangles, ...) | various | n/a: delivery mesh, not intake | n/a |

## Proposed next tasks

1. **IFC -> twin-floor/1 reader on synthetic fixtures (M).** Add a pure-Python reader (home per open question 1) that
   turns IFC4 into a `revit-twin` index (contract items 1-7), plus fixtures generated in tests with Revit-style naming
   (`Family:Type:ElementId`, shuffled order, one split wall, `Axis` + extrusion, clipping body, filled door/window,
   unfilled opening, recess). Acceptance: B01/B02/B02t through `dt spec extract` give the same specs as their etalons
   within K01 spec_compare thresholds; every unsupported case is a named fact; regression tests fail on the #76 `W0000`
   approach. Value high, effort M (~400-600 lines incl. tests). No real export needed.
2. **IFC frame and units contract (S).** Add `frames["<file>.ifc"]` handling and provenance: report `IfcSite`/
   `IfcBuilding` placement and `IfcMapConversion`, accept SI and conversion-based length units, never infer the object
   frame. Tests: one model written with shifted/rotated site placement and in feet -> identical records after the
   declared frame; missing frame entry -> stop. Value high (prevents silent misplacement), effort S.
3. **Validate on an approved KPP1 IFC export (M, needs user).** The user exports KPP1 from a copy with a recorded setup
   (IFC4 Reference View vs Design Transfer, Coordinate Base, split-by-level on/off); run task 1's reader and compare
   with the existing Revit twin spec (`jobs/KPP1/spec-compare-v003.md` route), including roof/parapet rows. Records
   which representations and naming the real file uses and closes or confirms the risks in the gap table. Value high,
   effort M; blocked on the export.

## Open questions for the user

1. Where should the reader live: `adapters/revit/` (DCC-adapter area, no `src/` package today) or
   `src/dt_ai/spec/revit_ifc.py` beside `revit_twin.py` (tested, importable by `dt spec extract`)?
2. For a future KPP1 IFC export, which Coordinate Base should be the standard: Project Base Point (identity for
   KPP1 per `object.json`) or Shared Coordinates (needed later for MSK-77)?
3. Is IFC2x3 Coordination View 2.0 (the exporter's default certified view) in scope, or IFC4 only?
4. May the reader add `ifcopenshell` as an optional dependency group in `pyproject.toml`, or must it stay
   `uv run --with ifcopenshell` (as in #76) until real-export validation?

## Sources

`[V]` read by me: PR #76 branch `experiment/revit-ifc-offline-intake` (`docs/experiments/revit-ifc-offline-intake.md`,
`pilot.py`, `results.json`); repository files named above; revit-ifc source files (NamingUtil, OpeningUtil,
DoorWindowDelayedOpeningCreator, GUIDUtil, WallExporter, CategoryUtil); buildingSMART IFC4.3 Markdown (IfcWall,
IfcRelVoidsElement, IfcRelFillsElement, IfcOpeningElement, IfcBuildingStorey, IfcMapConversion).
`[S]` source claims only: Autodesk IFC Export Setup Options (Revit 2026), Autodesk support article on openings,
mintlify revit-ifc coordinate reference (secondary), IfcOpenShell API docs (unit, representation, element).
Nothing here was run against a real Revit IFC file.
