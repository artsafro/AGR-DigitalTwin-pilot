# Revit API Automation and Headless Processing: Desktop, Cloud, and IFC Alternatives

**Scope and Estimate:** 40–50 min research review.
**Evidence Limits and Provenance:** Findings are grounded in fetched developer
documentation, open-source repositories, and local repository inspection at
commit baseline `a1052e3d3a3c5ef096028fb68982e1337da4eba4`. Evidence retrieval
utilized web searches, web extraction, GitHub API queries, and curl. No local or
cloud Revit software execution, no APS cloud WorkItem execution, and no IFC
command execution was conducted during this research task. Documented API
signatures, vendor-advertised support, and unverified design candidates are
explicitly distinguished.

## Summary

- Creating or modifying native Autodesk Revit models (`.rvt`) strictly requires
  the proprietary Revit DB engine[1][8][24].
- Desktop C# add-ins execute in-process on Revit's main thread and require an
  active `Transaction` scope for document mutations[1][3].
- In-host Python tools (pyRevit, RevitPythonShell) and Dynamo require a live
  Revit host for DB access[5][6][7].
- APS Design Automation runs headless Revit DB add-ins in the cloud via
  AppBundles and WorkItems, requiring UI-independent DB execution[8][24][25].
- APS consumption incurs cloud account charges (Free tier with monthly limits,
  Flex tokens, or Pay as You Go), with token rates unretrieved[9][11].
- IfcOpenShell provides an independent geometry and metadata engine for IFC
  schemas without Autodesk licensing, but cannot edit native `.rvt` models[13][14][17].
- Revit's `revit-ifc` add-in supports Link IFC and Export IFC, but full
  parametric roundtripping to editable native families is unestablished[12].
- For this repository, the recommended path retains the local `revit-http-2025`
  TwinPack extractor, pilots offline IFC parsing, and defers cloud automation.

## Findings

### 1. Desktop Installed and Licensed Revit API (C#)
- **Execution Model and Threading:** The desktop Autodesk Revit API supports in-
  process DLLs only; out-of-process standalone executables cannot bind directly
  to the native API[1]. All Revit database and UI calls must execute
  synchronously on Revit's main execution thread[1]. Asynchronous background
  workers or external modeless processes cannot invoke API calls directly and
  must route through the `ExternalEvent` framework (`IExternalEventHandler`,
  `ExternalEvent.Create()`, and `ExternalEvent.Raise()`), which Revit executes
  during subsequent Idling cycles[2].
- **Transaction Discipline:** All document mutations require an open, active
  `Transaction`[3]. `SubTransaction` and `TransactionGroup` provide
  organizational grouping and rollback control, but do not replace the
  requirement for an active `Transaction`[3]. Uncommitted transactions roll
  back automatically upon disposal[3].
- **Geometric Primitives and Construction Elements:** Built-in place
  construction elements (Walls, Floors, Ceilings, Roofs, Openings) and their
  `ElementTypes` represent core building geometry[4]. Geometric extraction
  yields a `GeometryObject` hierarchy comprising boundary-representation Solids,
  Faces, Edges, PolyLines, Points, and tessellated Meshes[23].
- **Internal Units and Conversions:** Internal database lengths in the Revit API
  use decimal feet. In local repository code
  (`tools/source/measure_spec_revit_twin.mjs`), lengths are converted from
  internal feet to metres using `FT = 0.3048`, while roof area and volume
  extraction observed quantities in square feet and cubic feet ($FT^2$, $FT^3$).
  Source[21] explicitly documents `UnitUtils.ConvertToInternalUnits` for
  converting metric inputs to internal units[21]. Reverse conversion functions
  from internal database units to display metrics were not documented in the
  retrieved extract[21].
- **Provenance:** Officially verified in Autodesk Developer Guides for Revit
  2025 and 2026[1][2][3]. Complementary class hierarchy details are confirmed
  in Main Reference 2025[23].

### 2. In-Host Python Scripting: pyRevit, RevitPythonShell, and Dynamo
- **pyRevit Framework:** pyRevit is an open-source (GPL-3.0) RAD framework
  providing rapid add-in authoring via IronPython, CPython, C#, and VB.Net[5].
  It bundles an extensible UI layer, telemetry, and a CLI utility (`pyrevit`)[5].
  The retrieved README documents the pyRevit CLI for managing environments,
  extensions, and configuration rather than batch host automation[5]. Community
  discussions note practical adoption of pyRevit for model QA slope and tag
  validation[19].
- **RevitPythonShell (RPS):** RPS provides an interactive IronPython interpreter
  and scripting host licensed under MIT[6]. The repository README advertises
  support across Revit versions 2024, 2025, and 2026 running IronPython 3.4[6].
  This represents vendor-advertised compatibility rather than workspace-tested
  support[6]. Runtime dependencies, IronPython 3.4 compatibility, and
  environment stability must be tested empirically before adoption[6].
- **Dynamo Host Dependency:** Dynamo enables visual programming and Python
  scripting within Revit[7]. The retrieved primer demonstrates accessing the
  Revit database via `RevitServices`
  (`DocumentManager.Instance.CurrentDBDocument`) in an active Revit host
  session[7].
- **Evidence Gap (Source 18):** Full text retrieval and JSON API extraction for
  Reddit thread r/Revit (`dynamo_vs_revit_plugins`) failed with HTTP 403[18].
  The search snippet indicates a discussion contrasting Dynamo against compiled
  plugins, but the failure link serves only as a valid record of coverage scope
  rather than a source of body facts[18].

### 3. Headless Cloud Execution: APS Design Automation for Revit
- **Headless Cloud Architecture:** Autodesk Platform Services (APS) Design
  Automation for Revit runs the core Revit engine as a cloud microservice
  without desktop UI[8][20][24]. Custom operations are packaged as AppBundles
  (zipped `.bundle` archives holding add-in DLLs and manifests), registered as
  Activities, and invoked via WorkItems over REST endpoints[9][24].
- **Add-In Contract and Reference Implementation:** Add-ins targeting Design
  Automation implement `IExternalDBApplication` and subscribe to
  `DesignAutomationBridge.DesignAutomationReadyEvent`[24][25]. Driver
  inspection of reference sample `aps-revit-file-parameters-exchange`
  (`HandleParameters.cs`, master SHA `34ea1e7f9882f2bd13c975eca286aae008ca9065`)
  demonstrates database operations: reading `data.RevitDoc`, collecting elements
  via `FilteredElementCollector`, extracting parameters via `BuiltInParameter`
  IDs, mutating inside a `Transaction`, and persisting via `SaveAs`[10][25].
  Note: Source[25] documents database-level code and does not contain cloud URL
  or WorkItem orchestration[25].
- **UI-Independent Workflow and Error Handling:** The conversion guide removes
  `RevitAPIUI`, WPF, and Windows Forms references; it uses DB-only entry points.[24]
  Its default bridge error handler suppresses warnings, attempts default error
  resolution, and rolls back failed actions when resolution fails; custom
  `FailuresProcessing` code is therefore not universally required.[24]
  Proposed acceptance: capture warnings, rollback status, timeouts, and artifact
  checks explicitly rather than treating job completion as geometry acceptance.
  The tutorial limits file writes to the working directory and children; its
  network restriction text is historical guidance to recheck against the chosen
  engine and current restrictions before deployment.[24]
- **Cost, Billing, and Licensing:** APS services incur consumption charges
  billed against Autodesk developer accounts (Free tier with monthly limits,
  Flex tokens, or Pay as You Go)[9][11]. Specific token burn rates and unit
  prices were not retrieved from current pricing sheets and remain unverified[11].
  Source[20] provides historical 2019 Forge demo context, not current
  pricing or cloud model capacity limits[20].
- **Provenance and Test Status:** Cloud execution contracts are verified from
  official APS developer guides[8][9][24]. Database-level operations are
  confirmed via reference code inspection[25]. APS cloud access has not been
  tested or authenticated in this workspace.

### 4. Revit-Free Processing: IfcOpenShell and IFC Interoperability
- **Engine Independence and Architecture:** IfcOpenShell provides an open-source
  C++ and Python geometry kernel and schema toolkit for IFC2x3 and IFC4[17]. It
  executes without requiring an Autodesk Revit license or cloud engine for
  reading and writing IFC data[13][17]. Open-source licensing obligations
  differ by subpackage (core LGPL-3.0, with OpenCASCADE and CGAL geometry kernel
  dependencies)[13][17].
- **Geometric Processing and Iteration:** Geometry processing is performed via
  `ifcopenshell.geom.create_shape()` or `ifcopenshell.geom.iterator()`,
  utilizing geometry kernels such as `hybrid-cgal-simple-opencascade`[13].
  Iterators process products, extracting vertices, triangulated faces, edges,
  and material slot IDs, while supporting representation filters (e.g. `Body`,
  `Tessellation`, or raw geometry with openings unapplied)[13].
- **Spatial Hierarchy, Placements, and Units:** Object positions are parsed into
  4x4 transformation matrices using `ifcopenshell.util.placement.get_placement`,
  resolving storey elevations (`get_storey_elevation`) and local coordinate
  systems[14][16]. Project unit extraction, caching, and conversion to SI
  metres are handled by `ifcopenshell.util.unit` (`calculate_unit_scale`,
  `convert_file_length_units`)[15].
- **Geometry Creation and Semantics:** Elements (`IfcWall`, `IfcBeam`) can be
  constructed with assigned material layer profiles, 4x4 matrix placements, and
  half-space solid clippings (clipping normals point toward discarded material)[14].
  Opening lifecycles separate void features (`IfcOpeningElement`) from
  infill components (doors/windows), requiring independent removal calls
  (`remove_feature` vs `remove_product`)[14].
- **Architectural Boundaries and Roundtripping:**
  1. *RVT vs IFC:* IfcOpenShell operates strictly on IFC schema objects and
     cannot directly create or modify native proprietary `.rvt` files[14][17].
  2. *Revit IFC Interoperability:* Autodesk's open-source `revit-ifc` add-in
     handles Link IFC and Export IFC[12]. Direct "Open/Import IFC" and "Link
     IFC" represent distinct operations in Revit[12]. While Link IFC imports
     reference geometry, native parametric roundtripping (editing imported IFC
     elements as full native Revit families and preserving parametric
     constraints upon re-export) is not established by retrieved sources and
     must be empirically validated before reliance[12].
- **Version Drift:** Fetched documentation exhibits version drift across
  sources: IfcOpenShell unit utilities reference v0.8.5[15], placement
  utilities reference v0.9.1[16], and the GitHub default branch is v0.9.0[17].
  Similarly, Autodesk documentation spans Revit 2018[4] and 2025[3][22].
  Related developer guidelines also reference Revit 2026[1][2]. Concrete
  implementations require strict pinning of schemas and library releases.

### 5. Safe Extraction Design Invariants and Extraction Matrix
The following extraction invariants represent a PROPOSED design aligned with
local repository code (`src/dt_ai/spec/revit_twin.py`,
`tools/source/measure_spec_revit_twin.mjs`) rather than universal external
rules:
1. **Persistent Identity and Provenance:** Tracking elements across files and
   re-exports requires source-qualified identity, such as document identifier
   plus Revit `UniqueId` or IFC `GlobalId` plus source file hash[13][14]. As a
   repository design decision, document-local numeric integer IDs (e.g. Revit
   `ElementId` integer values) are preserved for fast local lookups, while
   source-qualified identities are used for persistent provenance.
2. **Uncut Wall Prisms Strategy:** Extracting walls as uncut body prisms on
   location lines with separate opening records is a local specification
   strategy (`src/dt_ai/spec/revit_twin.py`), designed for robust 2D/3D spec
   generation rather than universal faithful boundary-representation geometry.
3. **Host Association and Orientation:** Wall-hosted doors and windows require
   explicit host IDs and orientation flags (`CanFlipFacing`, `CanFlipHand`,
   `FacingFlipped`, `HandFlipped`, `Mirrored`)[22] to reconstruct opening
   reveals, sills, and handedness without geometric ambiguity.
4. **Coordinate Stacks and Linked Documents:** While IFC placement utilities
   detail 4x4 affine matrix hierarchies[16], native Revit API transformation
   multiplication across nested RVT links is not substantiated by retrieved
   extracts and remains unverified.
5. **Phases and Design Options:** Construction phases and design options must be
   explicitly selected and user-approved during intake rather than universally
   filtering out demolished or secondary variants.
6. **Handling Unknowns and Domain Defaults:** Properties absent from BIM sources
   must remain `unknown` (`null`) to surface structured questions, while
   preserving established repository defaults with provenance (notably OD1 /
   [D048]: `opening_depth_default_m = 0.4` m when reveal depth is absent).
   Existing domain defaults must never be silently overridden.

#### Extraction Matrix for Core Elements

| Category | Acquisition Command / Route | Extracted Fields & Units | Pipeline Mapping (`dt_ai`) | Limits and Semantics |
|---|---|---|---|---|
| **Levels** | `list_levels` via `revit-http-2025` | `id`, `name`, `elevation_m` (converted from `elevationMeters`) | In `markup.py`, mapped to `LEVEL_<name>` helpers for spec elevation baselines | Relative model elevation; absolute Baltic height requires drawings/user confirmation (e.g. [D009]). |
| **Roofs** | `list_elements` (`OST_Roofs`, paginated) + `get_element_info` via `revit-http-2025` | `id`, `type` (from raw element `name`), `base_level`, `base_level_m`, `offset_m` (converted via $FT$), `volume_m3` ($FT^3$), `area_m2` ($FT^2$) | In `markup.py`, generates `LEVEL_roof` helper (`base_level_m + offset_m + volume_m3 / area_m2`) per user decision [D045] | Mean thickness formula is an accepted project decision [D045] for covering elevation, not a general physical maximum; sloped surfaces and eaves require geometry export. |
| **Walls** | `twin_export_floor` (`floor.json` per band) | `id`, `locationLine` (contains XYZ coordinates in local code, projected to 2D for plan), `thickness` (m), `bboxMin`, `bboxMax`, `function` | In `revit_twin.py`, expanded as prisms along line ($\pm t/2$); corner joins extended by $t/2$ | Curved walls fall back to `reference.obj`; limitations on non-vertical or battered walls are unvalidated design candidates. |
| **Openings** | `twin_export_floor` (`floor.json` per band) | `id`, `hostId`, `point` (XYZ), `hand` (vector), `width`, `sill`, `head`, `height`, `bboxMin`, `bboxMax` | In `revit_twin.py`, transparent windows produce glass panes; doors produce span records; unglazed openings produce opening kind `grille` rather than guaranteed opaque geometry | Family bounding box used when insertion point is absent; reveal depth exceptions (measured vs default `opening_depth_default_m = 0.4` m) follow OD1 / [D048] rather than assuming depths are only deeper. |

### 6. Programmatic Construction Path (Build API)
Official Autodesk Revit API documentation for element creation demonstrates a
structured construction workflow grounded in documented signatures[26]:
- **Transaction Scope:** Programmatic element creation strictly requires an
  active, open `Transaction`[3][26].
- **Wall Construction:** A wall is created on a given level using an explicit
  baseline curve: `Wall.Create(document, wallLine, level.Id, true)`[26], where
  `wallLine` is a `Line` created via `Line.CreateBound(start, end)` and `level`
  provides the valid host `Level.Id`[26]. Note that the boolean `true` in this
  documented signature is a structural flag rather than a wall type selector;
  selecting a specific wall type requires choosing project-approved construction
  parameters and verifying the appropriate overload (e.g. passing a `WallType.Id`).
- **Family Symbol Resolution:** Hosted components (e.g. windows) are resolved
  using `FilteredElementCollector(document).OfCategory(BuiltInCategory.OST_Windows).WhereElementIsElementType().ToElements()`,
  obtaining target `FamilySymbol` objects[26].
- **Symbol Loading and Activation:** The target `FamilySymbol` must be loaded
  into the document and active before instantiation; attempting insertion with
  an inactive symbol throws an `ArgumentException`[26].
- **Hosted Instance Insertion:** Inserting a window into a wall uses the
  official method:
  `public FamilyInstance NewFamilyInstance(XYZ location, FamilySymbol symbol, Element host, StructuralType structuralType)`[26].
  The host `Element` must be one that explicitly supports insertion (e.g. the
  newly created `Wall`), and `structuralType` is set to
  `StructuralType.NonStructural` for windows[26].
- **Proposed Construction Workflow:**
  1. Open an active `Transaction` on the target document[3][26].
  2. Select target `Level` and choose project-approved construction parameters,
     verifying the overload to select target `WallType`[26].
  3. Create baseline wall along the baseline curve using the verified
     `Wall.Create` overload[26].
  4. Query and activate target window `FamilySymbol` from `OST_Windows`[26].
  5. Insert hosted window instance using `NewFamilyInstance(location, winType,
     newWall, StructuralType.NonStructural)`[26].
  6. Commit transaction and persist via `SaveAs` to a new versioned file path to
     preserve source assets[25].
  7. As a proposed acceptance step (not verified by reference sample[25] which
     only covers `SaveAs`), reopen the saved file in read-only mode to verify
     geometry, transforms, and element counts.
- **Verification Status:** While `Wall.Create` and `NewFamilyInstance`
  signatures are officially documented[26], they have not been executed in this
  workspace. Construction methods and overloads for Roofs, Floors, Levels, and
  openings were not retrieved in fetched extracts and remain unverified design
  candidates.

## How It Applies to This Repository

- **Generic Importer Status (`adapters/revit/README.md`):**
  `adapters/revit/README.md` documents an unimplemented future importer for
RVT/IFC IDs, levels, surfaces, and matrices into
`SourceElement`/`MasterBuilding`. It carries no verified geometric integration
claims.
- **Implemented TwinPack Pipeline:** The active Revit data extraction route is
  implemented in `tools/source/measure_spec_revit_twin.mjs` and
  `src/dt_ai/spec/revit_twin.py`.
  - `tools/source/measure_spec_revit_twin.mjs` communicates over HTTP with the
    local `revit-http-2025` add-in (port 7891; note that operational status is
    based on historical documentation in `docs/agents/CAPABILITIES.md` rather
    than freshly tested today). It invokes TwinPack commands
    `twin_floor_manifest` and `twin_export_floor` across all wall functions
    (`Exterior`, `Interior`, `Foundation`, `Retaining`, `Soffit`, `CoreShaft`),
    outputting versioned `floor.json`, `reference.obj`, and `twin-data.json`. It
    records `isModified` before and after as an evidence signal, though this
    does not provide an immutable read-only sandbox guarantee.
  - `src/dt_ai/spec/revit_twin.py` parses `twin-data.json`, constructing body
    prisms from location lines and thicknesses, resolving joins via corner
    extension, reading door spans and sill/head records without cutting body
    walls, identifying window transparency from material definitions, handling
    curved walls via OBJ geometry, and isolating attachment questions outside
    the main walls' convex hull rule ([D027]). This behavior is covered by
    synthetic tests in `tests/test_spec_revit_twin.py` (which validate offline
    specification logic rather than live Revit runtime execution).
  - `src/dt_ai/spec/markup.py` consumes `revit_levels` and `revit_roofs` from
    `twin-data.json`, generating `LEVEL_<name>` helpers and calculating the top
    of the roof covering (`LEVEL_roof` = base + offset + volume / area) per
    project decision [D045] and pattern `markup-helpers` (MH2).
- **Broken Route Warning (`docs/agents/CAPABILITIES.md`):** The `revit-twin` MCP
  route is broken (CONNECTION_CLOSED) and must not be used; only
  `revit-http-2025` is documented operational.
- **Intake Hierarchy Alignment (`src/dt_ai/intake/model.py`,
  `docs/HARNESS_PLAN.md` §15):**
  The intake model defines format priority ranking where `rvt` and `ifc` hold
top priority (Rank 1). Data must be classified by confidence (`measured`,
`read_from_drawing`, `estimated`, `unknown`), strictly enforcing
`null_is_unknown` where unverified fields cannot be assigned defaults.
- **Object Contexts and Decisions:**
  - *PSU275 (`docs/sources/psu275.md`):* Governed by user decisions [D008]
    (geometry reference is Revit only; missing parts from FBX S3) and [D009]
    (work in detached Revit 2025 copy `modified_1644.rvt`; candidate Baltic mark
    169.65 from drawing S1 p.2, not survey; no MSK-77 yet). Prior source
    documentation (recorded from a detached diagnostic copy with
    `isModified=true` historically, not inspected live today) notes: 25 levels
    (elevation −4.400 to +66.040), two unloaded RVT links (КМ structure and ВК
    plumbing), and ungeoreferenced placement (Project Base Point and Survey
    Point at 0/0/0, true north 0°, no coordinates).
  - *KPP1 (`benchmark/bench-k01-kpp1/`):* Prior documentation recorded parity
    between Revit spec extraction and mesh geometry (historical 0.0 mm contour
    difference documented in `spec-compare-v002.md`, not measured today).
    Benchmark tolerances (`benchmark/bench-k01-kpp1/tolerances.json`): level
    elevation $\pm 0.03$ m, contour area relative tolerance $0.02$, contour
    Hausdorff distance $0.05$ m, opening bounding box $0.05$ m, equal level and
    kink counts, and equal opening count (excluding vent grilles per
    `opening_kinds_not_in_verdict: ["grille"]`).
- **Test Suite Execution Status:**
  Exact execution `env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q --basetemp=.pt2 --tb=short`
  yields 1337 passed, 4 skipped, 1 warning. An initial PermissionError and
  subsequent MSYS-path conversion failures were repaired command-locally without
  source edits. There is no pending clean suite. Synthetic unit tests pass in
  the test suite, but they validate offline specification logic rather than live
  Revit runtime behavior.
- **Code-Inspected Risks:** In `tools/source/measure_spec_revit_twin.mjs`,
  localized Russian parameter queries (`Смещение от уровня`, `Объем`, `Площадь`)
  and hardcoded server paths
  (`C:/Users/artsafro/INTERACTIVE_TOUR/RevitMCPServer`) represent code-inspected
  risks across language packs or workstations rather than confirmed runtime
  defects.

## Proposed Next Tasks

### 1. Offline IFC Intake Pilot with KPP1 Benchmark Validation
Develop an offline, Revit-free intake parser utilizing `ifcopenshell` to inspect
IFC models deposited in `jobs/<JOB>/sources/`. The parser will extract spatial
hierarchies (`IfcBuildingStorey`), calculate storey elevations via
`ifcopenshell.util.placement.get_storey_elevation`[16], read project unit
scales[15], and validate extraction against KPP1 benchmark tolerances
(`benchmark/bench-k01-kpp1/tolerances.json`: levels $\pm 0.03$ m, contour area
rel 0.02, Hausdorff 0.05 m, opening bbox 0.05 m, equal level and kink counts,
equal opening count excluding grilles per `opening_kinds_not_in_verdict`) per
HARNESS_PLAN benchmark tolerances.
- **Value:** L
- **Effort:** M (optional estimate: 3–4 days).

### 2. Parameter Extraction Resilience via BuiltInParameter IDs
Refactor parameter queries in `tools/source/measure_spec_revit_twin.mjs` to
retrieve roof parameters using language-agnostic BuiltInParameter IDs rather
than localized Russian names (`Смещение от уровня`, `Объем`, `Площадь`).
Before changing the parameter queries, confirm whether the underlying
`revit-http-2025` bridge endpoints accept BuiltInParameter integer IDs or enum
strings. Note that BuiltInParameters represent internal enum IDs rather than
bilingual names; localized template cascades remain unverified.
- **Value:** M
- **Effort:** S (optional estimate: 1 day).

### 3. Grid and Axis Helper Extraction for Spec Generation (MH3)
Extend `tools/source/measure_spec_revit_twin.mjs` and `src/dt_ai/spec/markup.py`
to query Revit Grids (`list_elements` with `OST_Grids`) and generate
`AXIS_<name>` helper lines in `twin-data.json`, linking to backlog MH3
(`docs/backlog.md`) and the HARNESS_PLAN `markup-helpers` pattern to bind
opening positions to architectural structural axes.
- **Value:** M
- **Effort:** M (optional estimate: 2 days).

### 4. Headless Cloud Design Automation Feasibility Study
Conduct a scoped technical study to evaluate packaging the TwinPack extractor as
an APS AppBundle (`IExternalDBApplication`)[24][25]. The study will evaluate
cloud storage egress and explicit failure processing handlers[24]. It will also
determine Forge/APS authentication requirements and Flex token billing
impact[9][11] before any cloud migration.
- **Value:** S
- **Effort:** L (optional estimate: 5–7 days).

## Open Questions for the User

1. **IFC Test Model and Acceptance Criteria:** What approved test sample (e.g.
   KPP1 IFC export or vendor model), IFC schema version (IFC2x3 vs IFC4), and
   export view/exporter settings should be used to validate the offline
   IfcOpenShell intake pilot against benchmark tolerances?
2. **Cloud Automation Policy and Budget:** Does project security policy permit
   uploading proprietary site models (e.g. PSU275/TEC-26) to Autodesk Platform
   Services cloud servers for headless processing, and is there an authorized
   APS subscription or Flex token budget?
3. **Desktop Runtime and Version Support:** For local automation scripts, what
   specific Revit versions (2024, 2025, 2026) and execution environments (in-
   process .NET add-in vs `revit-http-2025` bridge) are required as baseline
   targets for production deployment?

## Sources

[1] https://help.autodesk.com/cloudhelp/2026/ENU/Revit-API/files/Revit_API_Developers_Guide/Introduction/Getting_Started/Using_the_Autodesk_Revit_API/Revit_API_Revit_API_Developers_Guide_Introduction_Getting_Started_Using_the_Autodesk_Revit_API_Deployment_Options_html.html
[2] https://help.autodesk.com/cloudhelp/2026/ENU/Revit-API/files/Revit_API_Developers_Guide/Advanced_Topics/Revit_API_Revit_API_Developers_Guide_Advanced_Topics_External_Events_html.html
[3] https://help.autodesk.com/cloudhelp/2025/CHS/Revit-API/files/Revit_API_Developers_Guide/Basic_Interaction_with_Revit_Elements/Revit_API_Revit_API_Developers_Guide_Basic_Interaction_with_Revit_Elements_Transactions_html.html
[4] https://help.autodesk.com/cloudhelp/2018/ENU/Revit-API/Revit_API_Developers_Guide/Revit_Geometric_Elements/Walls_Floors_Ceilings_Roofs_and_Openings.html
[5] https://github.com/pyrevitlabs/pyRevit
[6] https://github.com/architecture-building-systems/revitpythonshell
[7] https://primer.dynamobim.org/10_Custom-Nodes/10-5_Python-Revit.html
[8] https://aps.autodesk.com/automation-apis
[9] https://tutorials.autodesk.io/tutorials/design-automation/execute-workitem
[10] https://github.com/autodesk-platform-services/aps-revit-file-parameters-exchange
[11] https://aps.autodesk.com/pricing
[12] https://github.com/Autodesk/revit-ifc
[13] https://docs.ifcopenshell.org/ifcopenshell-python/geometry_processing.html
[14] https://docs.ifcopenshell.org/ifcopenshell-python/geometry_creation.html
[15] https://docs.ifcopenshell.org/autoapi/ifcopenshell/util/unit/index.html
[16] https://docs.ifcopenshell.org/autoapi/ifcopenshell/util/placement/index.html
[17] https://github.com/IfcOpenShell/IfcOpenShell
[18] https://www.reddit.com/r/Revit/comments/140r3uw/dynamo_vs_revit_plugins
[19] https://reddit.com/r/bim/comments/1mexq4x/anyone_building_aiml_automations_with_ifcopenshell
[20] https://www.youtube.com/watch?v=PkdBM0cFrN4
[21] https://help.autodesk.com/cloudhelp/2025/ENU/Revit-API-MainReference/files/html/b5e8d065-d274-62f8-7b5d-89722f7c44f3.htm
[22] https://help.autodesk.com/cloudhelp/2025/ITA/Revit-API/files/Revit_API_Developers_Guide/Revit_Geometric_Elements/Family_Instances/Revit_API_Revit_API_Developers_Guide_Revit_Geometric_Elements_Family_Instances_FamilyInstances_html.html
[23] https://help.autodesk.com/cloudhelp/2025/DEU/Revit-API/files/Revit_API_Developers_Guide/Revit_Geometric_Elements/Geometry/Revit_API_Revit_API_Developers_Guide_Revit_Geometric_Elements_Geometry_GeometryObject_Class_html.html
[24] https://aps.autodesk.com/en/docs/design-automation/v3/tutorials/revit/step1-convert-addin
[25] https://github.com/autodesk-platform-services/aps-revit-file-parameters-exchange/blob/master/ExportImportExcelPlugin/HandleParameters.cs
[26] https://help.autodesk.com/cloudhelp/2025/ENU/Revit-API-MainReference/files/html/61601fe7-6d7e-e600-192d-207aa31c381c.htm
