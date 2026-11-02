# Team scripts audit (Scripts from Telegram)

This is a static reading of the AGR team's working 3ds Max / AutoCAD / Python tool folder (issue #537). Inputs are the local copy `C:/x/scripts-telegram/` and the Drive folder `G:/Мой диск/AGR-evidence/Scripts from Telegram/`. The Telegram manifest is `manifest.json`, SHA256 `bc2a839589dc7e20bfdc0ea52fdf7937e2f3b4798ccab6ed8c6346d7a5a41645` (205 rows). Comparison baseline is pilot `main` `204e643c523fd2dc3ad6b931f2b621a6a22866a4`. Method: read source and `archive_inventory.json` only. No `.ms`, `.mcr`, `.lsp`, `.py`, `.exe`, `.mzp`, or `.dlu` from the folder was executed. Six in-house archives were extracted to a temp directory, read as text, and not committed. Third-party archives were not opened.

## Inventory

Full row-per-file data (name, size, SHA256, type, family, author, class, one-line purpose) is in [`team-scripts-inventory.json`](team-scripts-inventory.json). 106 rows = 99 technical files from `verification.json` plus 7 export artifacts. Hashes for the 99 technical files are copied from `verification.json`. Artifact hashes were computed in this worktree with `Get-FileHash`.

| Split | Count | What it is |
|---|---|---|
| In-house script files | 36 | 30 MaxScript, 2 Python, 3 AutoLISP, 1 `.mat` (34 `in-house` + 2 `in-house-utility`) |
| Unattributed utilities | 11 | MaxScript helpers with no author line in the header; owner unresolved (`unattributed-utility`) |
| In-house archives | 6 | `Для Артема.zip`, `AGR_Checker.zip`, `AGR_Zipper.zip`, `AGR_Zipper_.zip`, `Telegram Desktop.zip`, `UDIM_Tool_new.mzp` |
| Third-party | 46 | 35 archives, 6 programs, 4 MaxScript with an external author in the header, 1 reference PNG |
| Export artifacts | 7 | manifest, verification, archive inventory, export/media/document exclusions |
| Programs (type) | 6 | all third-party; none executed |
| Archives (type) | 41 | 6 in-house + 35 third-party |

Classification field in the JSON: `in-house` 40, `in-house-utility` 2, `unattributed-utility` 11, `third-party` 46, `export-artifact` 7.

Utility provenance (issue #540). Presence in the folder is not proof of team ownership. Each utility row has a `provenance_evidence` field citing header lines 1-8 (or the cited author lines); the files were read as text and not run.

| Class | Files | Evidence |
|---|---|---|
| `third-party` | `zOffTy Tools-Copitor_v3.mcr`, `uniconnector_v4.23.3_0.ms`, `dragNDropReferences11.ms`, `imagecomphelper.ms` | header names Mathieu Jacquin (Gumroad Copitor), Nikolay Litvinov, Christoph Buelter (both Buelter files) |
| `in-house-utility` | `ClearCustomAttributesAndObjProp_010.ms`, `_001.ms` | no author line; macro category "A101" in `_010` (`_001` by family), the same label as in-house `A101AGRLP.ms`. Ownership is inferred from that label, not proven; team confirmation pending |
| `unattributed-utility` | `A-Tools_SelectSimilar.ms`, `CoronaProxyDisplay_EN.ms`, `IN_tools-detriangulator.mcr`, `VertexEdgeSplit_UI_v2.ms`, `edge_tool.ms`, `EdgeDistributor.ms`, `floor_trace_extrude.ms`, `MultiBridge.ms`, `Poly_X,Y,Z.ms`, `SelectConcavePolygons.ms`, `edge_connect_segments.ms` | only a macro category label (A-Tools, WunschTools, IN_tools, RUST Script), a local `fileIn` load path (`edge_connect_segments.ms:6`, not source attribution) or nothing; ownership unresolved, ask the team before treating any of them as an AGR tool |

Version families with more than one file (latest marked in the JSON):

| Family | Files | Latest |
|---|---|---|
| UDIM Viewer | `UDIM Viewer.ms` (file header v7.3), `UDIM Viewer_V1.2.ms`, `UDIM Viewer_V1.4.ms` | v1.4 |
| UDIM Texturing Tool | loose `.ms`, `UDIM_Texturing_Tool_12.ms` (UI v8.5), `UDIM_Tool_new.mzp` (UI v9.2) | v9.2 inside the mzp |
| UCX splitter | `UCX_new_11_09.ms`, `UCX_N_29.09.ms` | 2026-09-29 |
| VPM_to_NPM | `VPM_to_NPM__msg_123324.ms`, `VPM_to_NPM.ms` | `VPM_to_NPM.ms` |
| Collizii | `Collizii.ms`, `Collizii_2.ms` | v2 |
| Clear CA UDP | `_001`, `_010` | 010 |
| GridUVLayout | `GridUVLayout3.ms`, `GridUVLayout22.ms` | 22 |
| AlexYo AGR renamer | V11 file, `AlexYo_AGR_renamerV2.ms` (header V13) | V13 |
| AGR Zipper | `AGR_Zipper_.zip`, `AGR_Zipper.zip` | `AGR_Zipper.zip` (same v2.1 header, larger `agr_zipper.py`) |
| CheckToolBox | v1.4, v1.5 | v1.5, third-party, not read |
| CopyPasteDWG | two mzp | identical purpose; unsuffixed file marked latest; contents not read |
| PNG Compressor | two exe | third-party, not run |
| AtlasBuilder | full zip, portable zip | third-party, not read |

`Для Артема.zip` is a bundle, not a version. Inside it, `Maf Tools.mcr`, `NUM2CIRCLE.lsp`, and `SelectNumbers.lsp` match the loose files byte for byte. `Ground_Tools.ms` does not (46246 vs 47330 bytes). `Udim_Geo_Json.ms` is the same tool title as UDIM Viewer v1.4 and is not byte-identical (45843 vs 44682).

## In-house scripts

Order follows a production pass: Ground, MAF, Flora, UCX, UDIM/atlas, VPM to NPM, naming and export, checks, cleanup, modeling, lighting, AutoCAD, misc. Quotes are at most 15 lines.

### Ground_Tools

**Purpose.** Simplify Ground borders, retopologize fans, and build a terrain from heights.

**Production step.** Ground.

**Inputs/Outputs.** Selected border or mesh in the open Max scene. Outputs edited poly borders, rebuilt fan patches, or a terrain mesh. No file export.

**Algorithm.** Four rollouts. Poly Toolkit walks border and seam chains, drops points with Douglas–Peucker, and keeps corners above an angle. Fan Topology Fixer groups contiguous faces, finds corners, and rebuilds the patch. 3D-Terrain and Plane Terrain Deformer sample a height field (Delaunay in the deformer) and build a surface. The loose file was read; the copy inside `Для Артема.zip` is a reformatted sibling (diff about +1138/−1117 lines on ~1140 lines) with the same rollout names. Algorithm identity of the bundle copy was not line-reviewed.

**Hard-coded values.** From `Ground_Tools.ms`:

```
26:        spinner spnTolerance "Tolerance:" range:[0.01, 10000, 1.0]
28:        spinner spnAngleThreshold "Angle Threshold (deg):" range:[1, 180, 30]
34:        spinner spnIntTolerance "Seam Tolerance:" range:[0.0001, 100, 0.01]
915:    spinner spnSegs "Segments (Density):" range:[10,300,60]
916:    spinner spnMargin "Edge Margin (%):" range:[0,50,5]
```

Tolerance and seam tolerance are scene units (meters if the scene is metric). Defaults: border 1.0, corner 30°, seam 0.01, terrain segments 60, margin 5%.

**Limitations.** Not an AGR delivery check. No naming, density, or UCX logic.

**Diff vs older versions.** Single loose version plus the non-identical bundle copy. No version number in the header.

### Texture placeholders (bundle)

**Purpose.** Build 24-bit PNG placeholders plus ERM and Normal stand-ins for Ground textures.

**Production step.** Ground / UDIM/atlas.

**Inputs/Outputs.** User-picked textures and an output folder. Writes PNG files. Source: `Для Артема.zip` / `Texture_Zaglushki_Ground.ms`.

**Algorithm.** UI titled "Texture Placeholder Creator PNG 24-bit + ERM + Normal" (`Texture_Zaglushki_Ground.ms:8`). Collects source textures, derives output names, and writes diffuse, ERM, and normal placeholders through .NET imaging.

**Hard-coded values.** 24-bit PNG is in the rollout title. Exact pixel size and channel fills were not extracted as named constants beyond that title.

**Limitations.** Not run. Does not know the pilot rule that a flat metallic/roughness placeholder is 128×128 only.

**Diff vs older versions.** Bundle only.

### Region cut (bundle)

**Purpose.** Grow a polygon selection to the enclosing region in one click.

**Production step.** Modeling (used on Ground cuts and facade regions).

**Inputs/Outputs.** One selected polygon on Editable Poly. Output is a face selection. `Region_Cut.ms:12` button "FILL REGION (1-CLICK)".

**Algorithm.** From the selected face, fill the bounded region on the poly. UI is Max 2024 only.

**Hard-coded values.** None beyond Max 2024 and Editable Poly.

**Limitations.** Selection helper, not a geometric tolerance.

**Diff vs older versions.** Header says v16. No older file in the folder.

### Maf Tools

**Purpose.** One dialog for MAF UDIM packing, intersection check, glue, render-to-texture, ID colors, and notes.

**Production step.** MAF.

**Inputs/Outputs.** Selected MAF meshes and their maps. Can rewrite UVs, render textures, and store notes. Loose file equals the bundle copy (SHA256 match).

**Algorithm.** `MafTools_MainDialog` "Maf Tools v3.0" (`Maf Tools.mcr:3928`) hosts UDIM fit/pack, an intersection check, glue with offset and depth, bracket repair, render-to-texture, ID colors, and object notes. UDIM packing scales islands into the inner square after padding. Unit scale is converted from Max system units (inches, mm, cm, km tables around `Maf Tools.mcr:442`).

**Hard-coded values.**

```
2015:        spinner spn1Spacing "Spacing:" range:[0,1,0.02]
2029:        spinner spn2Padding "Padding:" range:[0.0,0.49,0.0]
2038:        spinner spn3TD "TD:" range:[0.001,99999,512]
2054:        spinner spn4AtlasW "Atlas Width UDIMs:" range:[1,50,1]
2055:        spinner spn4Gap "Padding:" range:[0.0,0.1,0.005]
2064:        spinner spn5Gap "Max gap:" range:[0,100000,5]
2806:        spinner spn_rtt_width "W:" range:[64,16384,4096]
```

**Limitations.** TD spinner is unlabeled (not explicitly px/m). Intersection check was not compared numerically with `Collizii_2.ms`.

**Diff vs older versions.** Only v3.0 in this folder.

### Maf_Fly

**Purpose.** Select every other mesh whose world AABB does not touch the one selected object.

**Production step.** MAF (clearance / scatter check).

**Inputs/Outputs.** Exactly one geometry object. Selects the non-touching set. `Maf_Fly.ms:11-13` treats AABB touch as intersection.

**Algorithm.** World box from node min/max. Anything that fails the six-plane overlap test is selected.

**Hard-coded values.** Touch counts as a hit. No millimeter epsilon.

**Limitations.** Bounding boxes, not surfaces. One reference object only.

**Diff vs older versions.** None.

### FloraAtlas (bundle)

**Purpose.** Pack flora textures into one diffuse atlas and a separate opacity atlas.

**Production step.** Flora.

**Inputs/Outputs.** Flora objects and their diffuse/opacity bitmaps. Writes PNGs. `FloraAtlas.ms:4-10` (header "Flora Atlas V1.2").

**Algorithm.** Crops UV islands, packs them, builds a 24-bit RGB atlas in C# (`Format24bppRgb`, `FloraAtlas.ms:246`), and a black/white opacity atlas when the diffuse has no alpha. Opacity generation defaults on.

**Hard-coded values.** 24-bit RGB atlas. Opacity map checkbox default on (`FloraAtlas.ms` rollout near the end, "Generate Opacity Map" checked true).

**Limitations.** C# is compiled inside Max when the script runs; that path was not executed. No texel-density check against 512–1706 px/m.

**Diff vs older versions.** V1.2 only, bundle only.

### UCX splitter

**Purpose.** Cut a mesh into convex UCX hulls, solid pieces, or boxes, then inset gaps.

**Production step.** UCX.

**Inputs/Outputs.** One polygon mesh. Creates `UCX_*` pieces on a tool layer and can delete the latest build. Latest file `UCX_N_29.09.ms`.

**Algorithm.** A 3D grid of draggable dividers splits the source. Each cell becomes a convex hull (vert cap), an exact solid slice, or a UBX box. Cells are shrunk by a gap. Neighbor hulls merge when protrusion stays under a max. Names are sanitized to ASCII letters, digits, and underscore. The 29.09 file adds a toolkit pager, a gap-fixer page, and an edge-splitter page that also exist as `UCX_Razdv.ms` and `Narezka_Ucx.ms`.

**Hard-coded values.**

```
23:fn UcxOuterPadding = 0.04
24:fn UcxDividerPad = 0.035
25:fn UcxMinSize = 1.0e-5
925:  spinner spnVerts "Max hull verts" range:[4, 64, 16]
928:  spinner spnGap "Gap (mm)" range:[0, 500, 5.0]
929:  spinner spnMaxDev "Max Protrusion (mm)" range:[0, 10000, 500.0]
932:  spinner spnMaxCollisions "Max Pieces" range:[1, 99999, 12]
```

`UcxOuterPadding` (0.04) and `UcxDividerPad` (0.035) are dimensionless fractions of a bbox side, not scene-unit distances. `UCX_N_29.09.ms:417` multiplies each bbox side by 0.04, and `:430-433` expand the outer cell bounds by that amount. `:210` multiplies 0.035 by the largest bbox side to extend the divider plane. Those factors size helper and grid extents. The interior nominal gap is independent of them: it comes from `UcxGetGapSys` (`:32-36`, spinner default 5 mm at `:928`). Protrusion default 500 mm. Piece cap default 12. Hull verts default 16.

Worked example (static arithmetic over those formulas; no Max run). Outer extension on a side = that side × 0.04. Divider extension = largest side × 0.035. For a cube of the side below, both apply to the same length:

| Bbox side | Outer extension | Divider extension |
|---|---|---|
| 1 m | 0.04 m | 0.035 m |
| 10 m | 0.4 m | 0.35 m |
| 100 m | 4 m | 3.5 m |

The nominal interior gap stays 5 mm at all three sizes.

**Limitations.** Piece count and protrusion are author defaults, not the regulation bands (10 cm / 30 cm / 1 m). The 0.04 and 0.035 factors size helper and grid extents; they are not the emitted clearance. Convexity is by construction (hull) and is not rechecked here.

**Diff vs older versions.** `UCX_new_11_09.ms` has the splitter only. `UCX_N_29.09.ms` adds `UcxNextCollisionName`, `rltUcxGapFixer`, `rltEdgeProjector`, and `rltCollisionToolkit`.

### UCX gap inset

**Purpose.** Open a gap by moving vertices inward along averaged normals.

**Production step.** UCX.

**Inputs/Outputs.** Selected geometry. Converts to Editable Poly. `UCX_Razdv.ms`.

**Algorithm.** Total gap default 5 mm; each object is inset by half (`UCX_Razdv.ms:16-17`, `51`). After the move it tries `autoEdge` at 45°. The same half-gap inset is the Gap Fixer page in `UCX_N_29.09.ms:1042` (nominal gap default 5, inset by half at line 1078).

**Hard-coded values.** Default total gap 5.0 mm. Range 0.1–100 mm. Auto-edge angle 45°.

**Limitations.** "Non-destructive" in the comment means it does not slice; it still moves vertices and converts the object class. Clearance on concave hulls is not the nominal gap.

**Diff vs older versions.** Standalone file versus the page inside the 29.09 toolkit. Same default and half-gap rule. The toolkit page does not call `autoEdge`.

### UCX edge split

**Purpose.** Copy and slice a poly by planes through the selected edges, optionally capping holes.

**Production step.** UCX (also general modeling).

**Inputs/Outputs.** One Editable Poly, edge selection. `Narezka_Ucx.ms:4-6` rollout "Edge Projector & Split v9". Cap holes defaults on.

**Algorithm.** Each selected edge defines a plane from its midpoint, edge direction, and the average normal of faces on that edge. Planes are flipped to one side, sorted, and used to split.

**Hard-coded values.** Normal length epsilon 0.0001 (`Narezka_Ucx.ms:43`). Editable Poly required.

**Limitations.** One object. No UCX naming.

**Diff vs older versions.** v9 standalone. The same rollout title "Edge Splitter" is embedded in `UCX_N_29.09.ms:1107`.

### UCX Toolkit v3.35 (bundle)

**Purpose.** Slice a shape, build collisions, slice a building by height, extrude to a target.

**Production step.** UCX.

**Inputs/Outputs.** Scene meshes. Settings in `userScripts\SliceShapeTool.ini` (`UCX_Tools.ms:9`).

**Algorithm.** Tabs: Slice Shape, UCX Collision, Building Slicer, plus extrude-to-target. Hidden constants fix weld, iteration cap, and vert cap (`UCX_Tools.ms:12-15`).

**Hard-coded values.** `FIXED_WELD_TOL = 0.0`, `FIXED_MAX_ITER = 500`, `FIXED_MAX_VERTS = 256`. Gap spinner default 2.0 mm (`UCX_Tools.ms:1456`). Building slicer height step default 3.0 (`UCX_Tools.ms:1661`).

**Limitations.** Different tool from the 29.09 splitter (gap default 2 mm here, 5 mm there). Weld tolerance 0 will not close numerical cracks.

**Diff vs older versions.** v3.35 only, inside the bundle.

### UCX Checker (bundle)

**Purpose.** Find intersecting UCX triangle pairs and select them.

**Production step.** UCX / checks.

**Inputs/Outputs.** Collision meshes in the scene. Fills a pair list. `UCX_Check.ms:7` "UCX Checker (Turbo v2)".

**Algorithm.** Segment–triangle and triangle–triangle tests (`UCX_Check.ms:34-73`). A pair is stored and can be selected. Tolerance constant `TOLERANCE = 0.01` (`UCX_Check.ms:19`). Degenerate determinant cutoff `1e-6` (`UCX_Check.ms:54`).

**Hard-coded values.** `TOLERANCE = 0.01` (scene units: 1 cm if meters). Parallel-edge epsilon 0.000001.

**Limitations.** Intersection only. No gap band, no convexity, no name mask. 1 cm tolerance is coarser than the pilot SAT epsilon of 0.01 mm.

**Diff vs older versions.** Turbo v2 only, bundle only.

### Collizii

**Purpose.** Check collision intersections and convexity, and in v2 try to fix triangulation.

**Production step.** UCX / checks.

**Inputs/Outputs.** Collision objects. Dialog selects bad faces. Latest: `Collizii_2.ms`.

**Algorithm.** v2 adds triangle–triangle intersection, bbox reject, convexity scoring with a 0.001 threshold, and a triangulation fix that keeps a repair only when the violation drops (`Collizii_2.ms:506-507`, `553`, `750`).

**Hard-coded values.** Convexity and face-violation cutoff 0.001. SAT interval epsilon `1e-6` (`Collizii_2.ms:218`).

**Limitations.** 0.001 is scene units (1 mm in meters), not the pilot overlap epsilon. No name or budget check.

**Diff vs older versions.** `Collizii.ms` lacks precise intersection, convexity issue listing, and triangulation repair. Those functions exist only in `Collizii_2.ms`.

### UDIM Viewer

**Purpose.** Load a texture folder (later: a GeoJSON job folder) and show or assign UDIM tiles.

**Production step.** UDIM/atlas.

**Inputs/Outputs.** Folder of images; v1.4 also `.max/.fbx/.obj/.3ds/.dae/.stl/.3dm` and a GeoJSON. Assigns materials and can hide `UCX_*`.

**Algorithm.** v1 browses a folder and lists channels (header "UDIM Viewer v7.3", `UDIM Viewer.ms:2`). v1.2 assigns matIDs from the UV tile on Editable Poly using the polygon's average UV, without `snapshotAsMesh`. v1.4 is a different tool: "GeoJSON + UDIM Importer" (`UDIM Viewer_V1.4.ms:2-8`) with recursive folders, hide UCX, and layers. The bundle file `Udim_Geo_Json.ms` is that same importer title and a different byte size.

**Hard-coded values.** v1.4 extensions listed above. `optHideUCX = true`, `optCreateLayers = true`, `optRecursive = true` (`UDIM Viewer_V1.4.ms:13-15`). Tile math lives in the MultiSub helper, not in the viewer header.

**Limitations.** v1.4 was not diffed line-by-line against `Udim_Geo_Json.ms`. Neither file checks padding or texel density.

**Diff vs older versions.** v1 → v1.2 adds in-place matID by UV (+37/−17 lines). v1.2 → v1.4 replaces the viewer rollout with the folder importer (function list is almost entirely new).

### UDIM Texturing Tool

**Purpose.** Work on UDIM tiles for both Editable Poly and Editable Mesh.

**Production step.** UDIM/atlas.

**Inputs/Outputs.** Selected mesh and a texture folder. Latest source is inside `UDIM_Tool_new.mzp`: `UDIM_Texturing_Tool.ms` rollout "UDIM Tool v9.2" and a grid rollout "UDIM Grid — 1001..1100".

**Algorithm.** A struct abstracts poly vs mesh (face count, UV, material ID). The grid shows tiles 1001–1100. v8.5 (`UDIM_Texturing_Tool_12.ms:403`, "UDIM TOOL v8.5") is the same idea with fewer mesh helpers.

**Hard-coded values.** Tile range 1001..1100 in the v9.2 grid title (`UDIM_Tool_new` / `UDIM_Texturing_Tool.ms` rollout at line 748).

**Limitations.** The loose `UDIM_Texturing_Tool.ms` (13085 bytes) is older than both v8.5 and the mzp. v9.2 vs v8.5 was compared by function names, not by a semantic diff of every button.

**Diff vs older versions.** Loose base and v8.5 share the core struct. v8.5 adds `buildUsageMap`, `ensureEditable`, face/UV getters. The mzp v9.2 adds a separate grid rollout and a folder dialog and is the largest file (35046 bytes). Treat v9.2 as latest.

### UDIM-MultiSub

**Purpose.** Set each face's material ID from its UV tile index.

**Production step.** UDIM/atlas.

**Inputs/Outputs.** Faces on poly or mesh, map channel. Writes material IDs.

**Algorithm.** Average UV of the face, then ID = 1001 + floor(U) + 10×floor(V).

```
1:fn getUDIMFromUV u v =
5:    return 1001 + udimU + (udimV * 10)
```

`UDIM-MultiSub_Universal(max22-26).ms:1-6`.

**Hard-coded values.** Base tile 1001, 10 tiles per row. Max 2022–2026 in the filename.

**Limitations.** This makes the working material ID equal the UDIM number. The pilot keeps those numbering schemes separate.

**Diff vs older versions.** One file.

### GridUVLayout

**Purpose.** Split every polygon in UV and recenter it on the repeating texture without changing phase.

**Production step.** UDIM/atlas.

**Inputs/Outputs.** One mesh. Rewrites channel-1 UVs. Latest `GridUVLayout22.ms`.

**Algorithm.** Header (`GridUVLayout22.ms:2-12`): cut all edges, then shift each polygon by an integer number of tile steps so it sits on the same phase of a tiled map, matching a RizomUV nudge. v22 adds `layoutPlugs`, `runPlugs`, and `udimTileOffset`.

**Hard-coded values.** Shifts are integer tile steps (`1/stepU`, `1/stepV` in the header comment). UI width 260 (`GridUVLayout22.ms:358`).

**Limitations.** Destroys existing seams. Not a packer and not a density check.

**Diff vs older versions.** `GridUVLayout3.ms` lacks the three plug/UDIM helpers.

### Facade atlas (`apply_atlas_uv.ms`)

**Purpose.** Turn facade face IDs into cameras, batch-render them, and apply the atlas UV.

**Production step.** UDIM/atlas (OKS facades).

**Inputs/Outputs.** A building mesh and a batch directory. Rollout "Facade Atlas Tool" (`apply_atlas_uv.ms:1-6`, `1591`).

**Algorithm.** Resolve cameras linked to the building, render with isolation, then apply the resulting atlas to the mesh UVs. Globals cover batch dir, isolate flag, and camera list.

**Hard-coded values.** Not reduced to a single padding or resolution constant in the header. The win64 `FacadeAtlasBuilder` zip also lists a copy of this script; that zip was not extracted.

**Limitations.** 1989 lines; only the header, rollout, and role were read, not every render setting. Do not treat unquoted numbers as confirmed.

**Diff vs older versions.** One loose file.

### 8-bit to 24-bit

**Purpose.** Convert images to 24-bit color, restricted to 256×256.

**Production step.** UDIM/atlas (placeholders).

**Inputs/Outputs.** Image path in, image path out. GUI via tkinter. `convert_8bit_to_24bit.py:7-14` rejects any size other than 256×256.

**Algorithm.** Open with PIL, check size, convert mode to 24-bit RGB, save.

**Hard-coded values.** Size must be 256×256.

**Limitations.** Not the pilot 128×128 one-colour metallic/roughness placeholder. Not executed.

**Diff vs older versions.** One file.

### VPM_to_NPM

**Purpose.** Turn a UDIM Multi/Sub object into an NPM copy with one atlas on tile 1001 and a separate opacity map.

**Production step.** VPM_to_NPM.

**Inputs/Outputs.** One OKS Main or Ground mesh. Writes `<name>_NPM` (source untouched), `<base>_D.1001.png`, and `<base>_Opacity.1001.png`.

**Algorithm.** For each material ID, crop the used UV rectangle from that tile's bitmap, scale it into a cell of one atlas, and move UVs with a uniform affine map (no bake). Flat or small textures are stacked as plugs. Diffuse is written without alpha. Opacity is black where transparent. Ground mode then checks texel density.

**Hard-coded values.** From `VPM_to_NPM.ms:30-38` and the rollout at 644–648:

```
30:	atlasSize = 2048,
31:	targetD = 35.0,
32:	plugD = 12.5,
33:	minD = 10.0,
34:	maxD = 40.0,
35:	padPx = 6,
36:	plugMaxPx = 512,
38:	plugCell = 16,
```

UI: atlas 1024 or 2048 (default 2048), OKS plug cell 16 px, ground texture texel 35 px/m, plug texel 12.5 px/m, pad 6 px. Plug test is texture ≤ 512 px (`VPM_to_NPM.ms:12`).

**Limitations.** Pad 6 px is under the NPM minimum of 8 px. Plug rule (≤ 512) is wider than the pilot 128×128 flat metallic/roughness exception. Mesh is not reduced; only UVs and maps change.

**Diff vs older versions.** `VPM_to_NPM__msg_123324.ms` is the same header and the same function names, 23 lines shorter. The later file adds the ground texel report and spinners `spCell`, `spD`, `spP`.

### AlexYo AGR renamer

**Purpose.** Rename the Standard material and its bitmap files to AGR `M` / `T` names and copy the files beside the old ones.

**Production step.** Naming.

**Inputs/Outputs.** Selected objects. Material must be Standard. Copies bitmaps in the same folder. Latest `AlexYo_AGR_renamerV2.ms` (header V13).

**Algorithm.** Strip the first two characters of the object name (the `SM` of `SM_...`), then `M` + rest + `_1`. Each bitmap slot is copied and renamed `T` + rest + suffix + `_1`.

**Hard-coded values.** Slot 1 only. V13 suffixes: diffuse `_d`, glossiness `_r`, specular and reflection `_m`, opacity `_o`, bump `_n` (`AlexYo_AGR_renamerV2.ms:55-62`). Category "AlexYo Tools".

**Limitations.** Standard material only. Multi/Sub and Physical materials are skipped. Dropping two characters assumes the `SM` prefix.

**Diff vs older versions.** V11 (`AlexYo_AGR_renamer.ms`) forces `.png`, uses `substring` length = full name count, and has no `_o` or `_n`. V13 keeps the original extension and adds those two slots.

### A101 low-poly naming and export

**Purpose.** Name NPM objects, materials, and maps, then export selected FBX.

**Production step.** Naming / export.

**Inputs/Outputs.** Picked Main, glass, Ground, GroundEl, Flora. User prefix and address. FBX next to the max file or under a chosen path.

**Algorithm.** Rollouts OKS, Ground, GroundEl, Flora, and "Make and export". Names are concatenated. Export sets FBX to binary, no animation, no cameras, no lights, textures embedded (`A101AGRLP.ms:1237-1241`).

**Hard-coded values.**

```
44:	fn MainObjectName = ("SM_" + edtAddress.text + "_" + formattedPrint spnOksNumber.value format:"3.3d" + "_Main")
45:	fn MainMatName = ("M_" + edtAddress.text + "_" + formattedPrint spnOksNumber.value format:"3.3d" + "_Main_" + spnSlotNumber.value as string)
47:	fn MainGlassMatName = ("M_Glass_" + formattedPrint spnGlassIndex.value format:"2.2d")
388:	fn GroundFbxName = (formattedPrint OksRoll.spnPrefix.value + "_" + OksRoll.edtAddress.text + "_" + "_Ground.fbx")
908:	fn MainFbxName = (formattedPrint OksRoll.spnPrefix.value + "_" + OksRoll.edtAddress.text + "_" + formattedPrint spnFbxNumber.value format:"2.2d" + ".fbx")
909:	fn GroundFbxName = (formattedPrint OksRoll.spnPrefix.value + "_" + OksRoll.edtAddress.text + "_Ground" + ".fbx")
```

OKS index is 3 digits. FBX part number is 2 digits. Glass material is `M_Glass_01`.. style. Glass index range 1–7. Slot range 1–10. Flora object `SM_<address>_Flora` (`A101AGRLP.ms:756`).

**Limitations.** Two `GroundFbxName` functions. The one at line 388 inserts an extra underscore before `_Ground`. The export path at 909 does not. Prefix is not forced to four digits. Export can overwrite after a yes/no prompt (`A101AGRLP.ms:1265`).

**Diff vs older versions.** One file (`A101AGRLP.ms`).

### One-by-one export

**Purpose.** Pack a high/low pair into one library ZIP.

**Production step.** Export (library, not the AGR address package).

**Inputs/Outputs.** Selection of `Name_high` and `Name_low`. ZIP contains FBX per part, PNG preview, a Max 2022 scene, and textures copied beside the `.max`. `AlexYo_OneByOneExport_Preview_v18.ms:2-11`.

**Algorithm.** Group by base name. Copy textures next to the max file and store file names only, so the scene resolves on another machine.

**Hard-coded values.** Suffixes `_high` / `_low`. Max save version 2022. Category "AlexYo Tools".

**Limitations.** Not the NPM/VPM zip naming. v18 versus v17 is described in the header only; v17 is not in the folder.

**Diff vs older versions.** v18 only.

### AGR Zipper

**Purpose.** Pack a folder to ZIP from the Explorer menu and check NPM or VPM file rules.

**Production step.** Export / checks.

**Inputs/Outputs.** A folder or an existing ZIP. GUI report. Does not parse mesh geometry. Latest `AGR_Zipper.zip` (`agr_zipper.py` header v2.1).

**Algorithm.** Name charset and length, flat ZIP, NPM vs VPM masks, PNG size and bit depth, GeoJSON presence rules. Installer writes a context-menu command (`install.py`, identical in both zips).

**Hard-coded values.** `agr_zipper.py:149-155`:

```
149:MAX_ZIP_GROUND  = 1   * 1024**3
150:MAX_ZIP_OKS     = 500 * 1024**2
151:MAX_ZIP_LOWPOLY = 1   * 1024**3
152:MAX_NAME_LEN    = 254
154:TEX_SIZES_LOW  = {128, 256, 512, 1024, 2048}
155:TEX_SIZES_HIGH = {256, 2048, 4096}
```

README also allows 32 bpp when a 2048 or 4096 image has alpha, and 8 bpp for 256×256 plugs (`README.txt:74-81`). NPM must not contain `.geojson`. VPM PNG count 3–2100.

**Limitations.** No FBX geometry, UCX, or UV checks. Alpha allowance conflicts with the NPM "no alpha" rule. Both zips say v2.1; the larger file is +17/−9 lines and was not semantically diffed.

**Diff vs older versions.** `AGR_Zipper_.zip` is the smaller `agr_zipper.py` (46115 vs 46668 bytes), same install and README hashes, same function names.

### agr_max_check

**Purpose.** Check an open Max scene against AGR limits before FBX export.

**Production step.** Checks.

**Inputs/Outputs.** Scene objects named `SM_...` / `UCX_...`. Listener text plus JSON (`cfgOutJson` under the Max temp dir). File `agr_max_check_37.ms` (changelog through v27).

**Algorithm.** Configurable mode low/high, role oks/ground, optional site area. Checks names, triangulation, reset transforms, pivot at origin, pivot at XY center within 10% of the bbox, duplicate verts, isolated verts, zero-length edges, UCX convexity, UCX intersections by ray parity, one UV channel, triangle budgets, and light spacing. Coplanar overlap on `_Main` uses a normal dot tolerance and a spatial hash. The header says the script was syntax-read and not run in Max (`agr_max_check_37.ms:25-27`). UCX closure is explicitly not implemented (`agr_max_check_37.ms:31-34`).

**Hard-coded values.** `agr_max_check_37.ms:221-253` and the light-index test at 460:

```
221:global cfgMode        = "high"
226:global cfgDupTolerance  = 0.002
229:global lowTrisOks       = 150000
230:global lowTrisGround    = 180000
231:global highTrisOks      = 1000000
238:global lightsMaxPerFbx  = 250
239:global lightMinDistOmni = 5.0
240:global lightMinDistSpot = 1.5
248:global cfgNormalDeviationPercent = 2.0
253:global cfgCoplanarDistTol        = 0.005
460:                    if num < 1 or num > 50 then
```

Low-poly mesh masks require a 3-digit index (`agr_max_check_37.ms:381-387`). High-poly UCX mask is `UCX_SM_*_Main_???` / `Ground` with three digits (`agr_max_check_37.ms:407-421`).

**Limitations.** The 2% dot (`cosTol` 0.98, about 11.5°) is the overlap candidate normal filter, wider than the pilot xView `>= 0.9999` (about 0.8°): the team filter tests more candidate pairs (higher recall, more false-positive risk), while the pilot filter tests fewer (higher precision, can miss pairs between about 0.8° and about 11.5°). Overlap can skip dense cells (`cfgOverlapMaxBucket = 500`) and can be cancelled. Light numbers are capped at 050 per type, which is not the regulation's 001–250. High-poly OKS fails only above 1_000_000, with no 150_000 review band.

**Diff vs older versions.** Only this file is in the folder. The changelog describes v19–v27 against unseen older copies. Do not treat missing files as present.

### AGR Checker (Python ZIP)

**Purpose.** Check a delivered ZIP (FBX, PNG, GeoJSON) and write an HTML report without Max.

**Production step.** Checks.

**Inputs/Outputs.** OKS and/or Ground ZIP. HTML report. Optional `--area-ga`. Source `AGR_Checker.zip`: `checks.py`, `model.py`, `fbx_parser.py`, `fbx_scene.py`, `agr_check.py`, `agr_gui.py`, FNO and address CSVs.

**Algorithm.** Archive mask and size, FBX 7.4 binary and meters, one `_Main` or `_Ground`, material names, triangle limits, duplicate and isolated verts, pivot, one UV channel, UCX names, closed and convex hulls, AABB overlaps, no UV and no materials on UCX, lights, PNG tiles, GeoJSON fields and 256×256 JPEG `imageBase64`, FNO code lookup. README states the FBX parser was not run on real Max files (`README.md:150-159`) and that UDIM margin, texel density, and shader type are not checked (`README.md:133-145`).

**Hard-coded values.** `model.py:73-96`: ZIP 500 and 1024 (compared as MiB via `/ (1024*1024)` in `checks.py:48-49`), OKS tris 1_000_000, collision 15_000 / 5% / 100_000 with a 50_000 small-model threshold, PNG count 3–2100, materials max 7, UDIM 1001–1100, lights 250, light index max 50, texture sizes {2048, 4096}, duplicate verts 0.002 m, pivot tolerance 1e-4 m, XY center 10%. Intersections are AABB (`checks.py:405-418`). Ground triangle tiers match the regulation table (`model.py:99-102`).

**Limitations.** AABB overlap flags touching boxes. No gap-band check. Pivot tolerance 0.1 mm is tighter than the pilot shared-pivot 1 mm. Light index max 50 disagrees with 001–250. Not executed here. Synthetic tests exist inside the zip and were not run.

**Diff vs older versions.** One zip. README says it shares limits with `agr_max_check_*.ms`. The shared limits match; the Max script's overlap angle and the checker's AABB method are extra.

### Overlapping faces (Blender)

**Purpose.** Select coplanar overlapping faces, xView-style.

**Production step.** Checks.

**Inputs/Outputs.** Active edit mesh. Selects faces. Two copies: loose `overlapping_faces.py` and `Telegram Desktop.zip` / `xview_overlapping_faces_improved.py`.

**Algorithm.** Loose file triangulates a BMesh copy, buckets by normal and plane distance, and selects pairs under a distance with a minimum overlap area (`overlapping_faces.py:1-12`). The improved file adds a viewport overlay and a tolerance-scaled normal test.

**Hard-coded values.** Loose defaults: 2.0 mm, 8.0°, min overlap ratio 0.20 (`overlapping_faces.py:170-183`). Improved default tolerance 0.002 scene units (`xview_overlapping_faces_improved.py:653-658`). The improved file also contains a hard-coded XYZ list in the sibling `deepseek_python_Select_Verts_By_List.py:8-12` (a one-off coordinate list, not a general tool).

**Limitations.** 2 mm and 8° do not match the pilot xView pair (vertices 2 mm, faces 5 mm, normals within 0.81°). The coordinate list is site-specific and must not be reused as a rule.

**Diff vs older versions.** The improved checker is a different script (overlay, default 0.002), not a strict superset of the loose file.

### Clear custom attributes

**Purpose.** Strip custom attributes and user-defined properties before export.

**Production step.** Cleanup.

**Inputs/Outputs.** Selected nodes. Latest `ClearCustomAttributesAndObjProp_010.ms`. Macro category "A101"; no author line, so team ownership is inferred from that label, not proven.

**Algorithm.** Always removes CA from the base object. Optional: CA on node, modifiers, materials; clear UDP; clear vertex channels 0, −1, −2; delete map channels 2+; rename channel 1 to `UV`.

**Hard-coded values.** From the header (`ClearCustomAttributesAndObjProp_010.ms:5-11`): extra map channels off by default; rename channel 1 to `UV` on by default.

**Limitations.** Can delete animation keys (`wipeAnimationKeys` exists only in 010). Destructive.

**Diff vs older versions.** `_001` is CA/UDP only. `_010` adds channel wipe, UV rename, and animation clearing.

### Modeling utilities

Each of these is a general mesh helper. None of them encodes an AGR numeric rule unless noted. Provenance per file is in the Inventory provenance table; owner unresolved means `unattributed-utility`.

**floor_trace_extrude.ms.** Typical-floor trace: plane to border edge, click snaps, extrude in plan (`delta.z = 0`). `floor_trace_extrude.ms:1-12`. Step: modeling.

**edge_tool.ms.** Border Loop Cleaner 0.2: keep corner-to-corner border paths, preview deletion of grid edges. Step: modeling.

**EdgeDistributor.ms.** Even spacing of verts, vertical edge rings, or face strips. Corner angle default 30° (`EdgeDistributor.ms:8`). Anchors do not move. Step: modeling.

**edge_connect_segments.ms.** Connect on selected edges with a segment count. Editable Poly or Edit Poly. The file header points at `C:\Users\artsafro\Desktop\zavod\scripts\mesh\` (`edge_connect_segments.ms:6`); a load path is not authorship, so the row is `unattributed-utility`. Step: modeling.

**MultiBridge.ms.** Bridge several edge or polygon pairs from one button. v1.3. Step: modeling.

**Poly_X,Y,Z.ms.** Select faces whose normal is closest to world X, Y, or Z. Step: modeling.

**SelectConcavePolygons.ms.** Mark a polygon concave when an edge has two faces whose arrangement fails the strict test. Step: modeling.

**AlexYo_ConcaveFixer.ms.** Dialog "Concave Polygon Fixer v1.2", category AlexYo Tools. Find and fix, not only select. Step: modeling.

**VertexEdgeSplit_UI_v2.ms.** Split an edge where a vertex lies on the segment. `VES_eps = 0.001` (`VertexEdgeSplit_UI_v2.ms:6`). Category "RUST Script". Step: modeling.

**uniconnector_v4.23.3_0.ms (third-party).** Flow-connect switcher. Header author Nikolay Litvinov, category "Niklit Scripts" (`uniconnector_v4.23.3_0.ms:2-7`). Name and purpose only. Step: modeling. Not an AGR rule.

**A-Tools_SelectSimilar.ms.** Select similar by edge count, area, topology, normal. Settings ini under user scripts. Step: modeling.

**IN_tools-detriangulator.mcr.** Remove edges that only exist to triangulate, Detriangulator v1.0, category IN_tools. Step: modeling. Matches the pilot preference for quads in the delivered Max file.

**Poly Actions Copy (bundle).** `Poly Actions Copy_V6.ms` header v7.6.0. Records poly edits and reapplies them. Backup mesh on by default. Shell modifier was removed in v7.6.0. Step: modeling.

**Interier_Box (bundle).** Interior Box Creator v1.37. Extrudes an interior box. Depth default 2.0 m, range 0.05–20 (`Interier_Box.ms:4-14`). Step: modeling (interior capsule).

**Limitations.** Author names on AlexYo, A-Tools, IN_tools, and RUST Script are labels from the file, not a verified person record; A-Tools, IN_tools and RUST Script rows are `unattributed-utility`. No numeric AGR threshold except the 0.001 m vertex-on-edge epsilon and the 2 m interior default.

**Diff vs older versions.** Only the files present. Concave fixer has no older copy here. Poly Actions header mentions v7.6.0 versus a removed Shell feature; older copies are absent.

### Lighting

**Light.ms.** Clone one Free Spot onto selected polygons, or all faces if none are selected (`Light.ms:1-4`). Step: lighting.

**FreeSpot_Tools.ms (bundle).** FreeSpot Optimizer v2.3. Create spots on polygons, then thin them. Defaults: max 250, min distance 1.5 m (`FreeSpot_Tools.ms:19-20`). Methods: grid, clusters, greedy edges. Step: lighting. 250 and 1.5 m match the spot rules; the script does not enforce the 5 m omni spacing.

**Light_Metr.ms.** Highlight objects closer than a distance. Default 1.5 m (`Light_Metr.ms:3`, spinner at line 13). Scope: selection or all geometry. Step: lighting. This is a proximity warning, not a light-type check.

**CoronaProxyDisplay_EN.ms.** Switch Corona Proxy viewport display. Category "WunschTools" (`CoronaProxyDisplay_EN.ms:3-12`). Step: lighting / utility. Renderer-specific; the delivery FBX must not contain Corona lights.

**Diff vs older versions.** One file each.

### AutoCAD LISP

**EXPORTCIRCLESCSV.lsp.** Command writes selected circle centers to CSV `X;Y;Z` (`EXPORTCIRCLESCSV.lsp:15-16`). Step: Ground (SPOZU points).

**NUM2CIRCLE.lsp.** Command turns numeric text into circles; comma is accepted as a decimal point (`NUM2CIRCLE.lsp:8-9`). Same bytes in the bundle.

**SelectNumbers.lsp.** Selects text of length 6 matching `XXX.XX` (`SelectNumbers.lsp:8-15`). Same bytes in the bundle.

**Limitations.** AutoCAD only. No coordinate-system check (MSK-77). Not run.

**Diff vs older versions.** One copy each, bundle duplicates identical.

### Misc

**dragNDropReferences11.ms (third-party).** Image drop becomes reference planes. Header author Christoph Bülter, 2012 (`dragNDropReferences11.ms:7-8`). Name and purpose only. Step: utility. Not an AGR material.

**imagecomphelper.ms (third-party).** Viewport composition lines (thirds, golden spiral). Header author Christoph Bülter, 2010–2013 (`imagecomphelper.ms:20-21`). Name and purpose only. Step: utility. No modelling effect.

**zOffTy Tools-Copitor_v3.mcr (third-party).** Mesh clipboard. Header names Mathieu Jacquin and the Gumroad Copitor product, v3 dated 2017 (`zOffTy Tools-Copitor_v3.mcr:1-7`). Name and purpose only. Step: utility. JSON class `third-party`.

**Volume_vision.mat.** 36864-byte material library. Not decoded and not quoted. Step: utility.

**deepseek_python_Select_Verts_By_List.py.** Builds a mesh from a baked coordinate list. Step: utility. One-off, not a reusable tool.

**Telegram xView script.** Covered under overlapping faces.

## Workflow map

Reconstructed from the tools themselves and from `docs/domain/npm-vpm.md`, `docs/domain/areas/ground-surface.md`, `groundel-maf.md`, `flora.md`, `ucx.md`, `uv-atlas.md`, `package.md`, `export-import.md`, and `validation.md`. This is the order the scripts support, not a claim that every job runs every script.

1. **Points and references.** AutoCAD `NUM2CIRCLE` / `SelectNumbers` / `EXPORTCIRCLESCSV` turn drawing text and circles into a point list. `dragNDropReferences11.ms` hangs images in Max. Pilot intake is the DWG/DXF inspector (`tools/source/inspect_ground_dxf.py`) and the architectural-source skill, not LISP.
2. **Ground surface.** `Ground_Tools.ms` simplifies borders and builds terrain. `Region_Cut.ms` fills a region. `Texture_Zaglushki_Ground.ms` makes stand-in maps. Pilot Ground is the layered-cake surface from SPOZU, density 10–40 px/m.
3. **MAF and flora.** `Maf Tools.mcr` packs UDIM, glues, renders, and checks intersections. `Maf_Fly.ms` finds boxes that do not touch. `FloraAtlas.ms` packs flora diffuse plus opacity. Pilot: one GroundEl set and one Flora set on NPM; VPM UDIM on one channel.
4. **OKS mesh.** Floor trace, edge distribute/connect, bridge, concave select/fix, detriangulator, interior box. Pilot: quads in the Max file, triangulate at export, material IDs in the 1–35 reading scheme.
5. **Collisions (VPM).** `UCX_Tools.ms` slices the building and the shell. `UCX_N_29.09.ms` builds hulls. `UCX_Razdv.ms` insets a gap. `Narezka_Ucx.ms` cuts by edges. `UCX_Check.ms` and `Collizii_2.ms` look for hits. Pilot: `ucx_build` plus V010 (names, slots, budget, SAT intersections, advisory gap).
6. **UV and atlases.** MultiSub writes IDs from tiles. UDIM Viewer v1.4 loads the job folder and hides UCX. Texturing tool v9.2 edits tiles 1001–1100. Grid UV keeps repeat phase. `apply_atlas_uv.ms` renders facades. `VPM_to_NPM.ms` collapses UDIM into one NPM atlas. `convert_8bit_to_24bit.py` fixes 256×256 plugs.
7. **Names.** `A101AGRLP.ms` assigns `SM_` / `M_` / `T_` and glass `M_Glass_NN`. AlexYo renamer copies bitmaps to `T..._d/_r/_m/_o/_n`.
8. **Lights.** `Light.ms` and FreeSpot Optimizer place spots (cap 250, spacing 1.5 m). `Light_Metr.ms` flags neighbors inside 1.5 m. Corona proxy display is viewport-only. Pilot: lights only in `SM_Address_Light.fbx`, omni ≥ 5 m, spot ≥ 1.5 m, names `Address_Spot_001`..`250`.
9. **Cleanup.** Clear CA/UDP 010, rename map channel 1 to `UV`, drop extra channels.
10. **Check in Max.** `agr_max_check_37.ms` on the open scene.
11. **Export.** A101 writes binary FBX with embedded textures and without cameras, lights, or animation. Zipper packs the folder and checks names. One-by-one export is a library pair ZIP, off this path.
12. **Check the ZIP.** AGR Checker (and Zipper's lighter name/PNG pass) on the archive. Pilot equivalent is `src/twinqa` (scene, naming, uv, png, geojson, bundle).

**Excluded documents.** `ИНСТРУКЦИЯ_ПОЛЬЗОВАТЕЛЯ.txt` and `Новые требования к НПМ+ВПМ.pdf` are excluded by user decision (Artem, 2026-10-21) as outdated; they are not used as a source; the workflow map above is built from the scripts themselves and the pilot `docs/domain/`.

## Gap table vs the pilot

Pilot values were read from `standards/NPM_STANDARD.yaml`, `standards/VPM_STANDARD.yaml`, `standards/material_id_ranges.yaml`, `src/twinqa/scene.py`, `src/twinqa/geometry/ucx_audit.py`, `docs/domain/npm-vpm.md`, `docs/domain/areas/ucx.md`, `docs/domain/areas/uv-atlas.md`, and `docs/decisions.md` (D010, D030, D098, D152, D160, D162).

| Script rule/check/threshold | Script source | Pilot equivalent | Status | Values |
|---|---|---|---|---|
| NPM mesh `SM_<address>_<NNN>_Main` | `A101AGRLP.ms:44` | `NPM_STANDARD.yaml` `oks_mesh_pattern` | same | 3-digit index, `_Main` / `_MainGlass` |
| NPM material `M_<address>_<NNN>_Main_<slot>` | `A101AGRLP.ms:45` | `material_pattern` | same | slot suffix after geometry |
| Glass material `M_Glass_` + 2 digits | `A101AGRLP.ms:47` | YAML pattern; conflict #17 | differs | script `M_Glass_01` style; YAML pattern does not encode it (regulation text does, status review) |
| FBX `{prefix}_{address}_{NN}.fbx` | `A101AGRLP.ms:908` | `archive` / `oks_fbx_pattern` territory code 4 digits | differs | script prefix is an unconstrained spinner; pilot requires 4-digit territory code |
| Ground FBX name with an extra underscore | `A101AGRLP.ms:388` | `ground_fbx_pattern` | differs | script `prefix_address__Ground.fbx` in Ground rollout; export rollout at line 909 has a single underscore; pilot `{code}_{Address}_Ground.fbx` |
| UCX name `UCX_SM_*_{Main\|Ground}_NNN` | `agr_max_check_37.ms:407`; `model.py` via `checks.py:381` | `VPM_STANDARD.yaml` naming; `naming.py` | same | three digits 001–999 |
| File name length ≤ 254, charset letters/digits/`_` | `agr_zipper.py:152` | `NPM_STANDARD.yaml` `max_characters` 254 | same | 254 |
| Scene unit meter, scale 1:1 | `model.py:90`; FreeSpot header | `NPM_STANDARD.yaml` `units` | same | 1 unit = 1 m |
| Duplicate vertices 0.002 m | `agr_max_check_37.ms:226`; `model.py:91` | D152 overlapping vertices 0.002 m | same | 0.002 m |
| Coplanar face distance 0.005 m | `agr_max_check_37.ms:253` | D152 overlapping faces 0.005 m | same | 5 mm |
| Overlap candidate normal filter 2% dot | `agr_max_check_37.ms:248` | xView about 0.81° (`docs/domain/validation.md`) | differs | script ~11.5°; pilot \|cos\| ≥ 0.9999 (team tests more pairs, higher recall; pilot tests fewer, higher precision) |
| Blender overlap 2 mm and 8° | `overlapping_faces.py:170-178` | D152: faces 5 mm, normals 0.81° | differs | script 2.0 mm and 8.0°; pilot 5 mm and 0.81° |
| Improved overlap tolerance 0.002 | `xview_overlapping_faces_improved.py:658` | D152 faces 0.005; verts 0.002 | differs | script default 0.002 for the face test; pilot face test is 0.005 m |
| Material ID = UDIM tile | `UDIM-MultiSub_Universal(max22-26).ms:5` | `material_id_ranges.yaml` groups 1–35; export renumbers to 1001+ | differs | script `1001+floor(U)+10*floor(V)` as the face ID; pilot IDs stay a reading scheme [D030] |
| Ground texel 10–40 px/m, target 35 | `VPM_to_NPM.ms:31-34` | NPM ground density 10–40; D160 | same | band 10–40 px/m (script default target 35, plugs 12.5) |
| Atlas cell padding 6 px | `VPM_to_NPM.ms:35` | NPM `island_padding_px_min` 8 | differs | script 6 px; pilot ≥ 8 px (VPM ≥ 16 at 2048 and ≥ 32 at 4096) |
| Plug if texture ≤ 512 px | `VPM_to_NPM.ms:12`, `plugMaxPx = 512` | NPM 128×128 only for flat metallic/roughness | differs | script ≤ 512 px; pilot 128 px and one-colour MR only |
| UCX triangle budget | `model.py:77-80` | `scene.py` `UCX_SMALL_MODEL` 50000, 15000, 0.05, 100000 | same | 15_000 under 50_000 else 5% capped at 100_000 |
| UCX outer pad 0.04 and divider 0.035 (fractions of the bbox side); gap default 5 mm | `UCX_N_29.09.ms:23-24`, `:210`, `:417`, `:430-433`, `:32-36`, `:928` | D098 band 0.002–0.01 m; D162 also flags gaps under 0.2 mm | differs | 0.04 and 0.035 scale helper/grid extents (bbox side 1 / 10 / 100 m → outer 0.04 / 0.4 / 4 m, divider 0.035 / 0.35 / 3.5 m). Emitted clearance is `UcxGetGapSys`, default 5 mm, inside the pilot 2 mm–1 cm band |
| UCX toolkit gap default 2 mm | `UCX_Tools.ms:1456` | D098 minimum 2 mm | same | 2 mm is the low edge of the band, not the whole rule |
| Max protrusion for hull merge 500 mm | `UCX_N_29.09.ms:929` | UCX R11/R12/R13: 0.10 / 0.30 / 1.0 m | differs | script one spinner at 500 mm; pilot three bands |
| UCX max pieces default 12 | `UCX_N_29.09.ms:932` | triangle budget only | missing | pilot has no piece-count cap |
| UCX intersection by AABB | `checks.py:405-418` | `scene.py` SAT, touch is not an overlap | differs | script overlapping boxes fail; pilot requires surface separation below −0.01 mm |
| UCX Checker tolerance 0.01 | `UCX_Check.ms:19` | SAT epsilon 0.01 mm | differs | script 0.01 scene units (1 cm if meters); pilot 0.01 mm |
| No materials and no UV on UCX | `checks.py:451-463` | R07 | same | forbidden |
| Pivot within 1e-4 m of origin | `model.py:94` | shared-pivot tolerance 0.001 m (`scene.py:36`) | differs | script 0.0001 m; pilot 0.001 m |
| Pivot at XY center within 10% of bbox | `model.py:95`; check added in `agr_max_check_37.ms` changelog v19 | `scene.py` `PIVOT_CENTRE_TOL_PCT = 10` | same | 10% |
| VPM OKS triangles fail above 1_000_000 | `model.py:76`; `agr_max_check_37.ms:231` | D010: 150_000 review, 1_000_000 fail | differs | script no review band; pilot 150_001–1_000_000 is review |
| NPM triangles 150_000 OKS / 180_000 Ground | `agr_max_check_37.ms:229-230` | `NPM_STANDARD.yaml` | same | 150_000 / 180_000 |
| VPM Ground tiers by area | `model.py:99-102` | `docs/domain/npm-vpm.md` table | same | 0.05 ha to 300k … above 1.5 ha to 4.5M |
| ZIP 500 MiB OKS / 1 GiB Ground and NPM | `agr_zipper.py:149-151`; `checks.py:48-49` | binary units [D015] | same | 500×1024² and 1024³ |
| VPM PNG 2048 or 4096 | `model.py:88` | `VPM_STANDARD.yaml` `allowed_square_sizes_px` | same | 2048, 4096 |
| Zipper high-poly also allows 256 and alpha 32 bpp | `agr_zipper.py:155`; `README.txt:76-80` | VPM sizes 2048/4096; NPM alpha forbidden | differs | script 256 and RGBA on large maps; pilot RGB, alpha forbidden on NPM |
| Lights ≤ 250; omni ≥ 5 m; spot ≥ 1.5 m | `agr_max_check_37.ms:238-240`; FreeSpot 250 / 1.5 m | `docs/domain/npm-vpm.md` lighting | same | 250, 5 m, 1.5 m |
| Light index 001–050 per type | `agr_max_check_37.ms:460`; `model.py:87` | names 001–250 | differs | script max 50; pilot 250 |
| UV channel 1 named `UV` | `agr_max_check_37.ms:42-44`; Clear 010 renames channel 1 | V008 one UV channel | differs | script also requires the channel name `UV`; pilot checks channel count |
| FBX 7.4 binary, embedded NPM textures, no cameras/lights/animation | `A101AGRLP.ms:1237-1241`; checker README | NPM/VPM asset format | same | binary 7.4/2014; NPM textures embedded |
| Materials ≤ 7 | `model.py:83` | VPM up to 7 materials | same | 7 |
| UDIM numbers 1001–1100 | `model.py:84-85` | `VPM_STANDARD.yaml` `udim_grid` | same | 1001..1100 (checker does not prove gap-free layout; README says that analytic is absent) |
| MAF TD spinner default 512 | `Maf Tools.mcr:2038` | VPM density 512–1706 px/m [D160]; NPM GroundEl set ≤ 512 px | differs | script label is `TD` with no unit; pilot px/m band and a 512 px set cap are different quantities |
| Strip CA, UDP, extra map channels | `ClearCustomAttributesAndObjProp_010.ms:5-11` | — | missing | no pilot gate removes CA/UDP or renames the channel |
| Library ZIP `Name_high` + `Name_low` | `AlexYo_OneByOneExport_Preview_v18.ms:5-8` | — | missing | pilot delivery ZIP is per address, not per library pair |

## Recommendations

Drafts only. Nothing was filed. Artem picks.

1. **Title.** NPM atlas packer from a UDIM mesh, with the pilot padding.
   **Action.** port to agent tool.
   **Why.** `VPM_to_NPM.ms` already crops by used UV, keeps an affine texel scale, writes a separate opacity map, and targets the NPM 10–40 px/m band. That is the missing bridge from a VPM-shaped Max mesh to an NPM atlas.
   **Draft follow-up issue.** title: Port VPM_to_NPM atlas pack (affine UV, opacity map) into the pilot. acceptance: pack a synthetic Multi/Sub mesh to one 2048 atlas; padding ≥ 8 px; ground texel inside 10–40 px/m; diffuse has no alpha; opacity is a separate map; source mesh unchanged; read the PNG back.

2. **Title.** Align the overlap check with xView before any Max script is copied.
   **Action.** port to gate.
   **Why.** The team checker and the pilot both use 5 mm face distance and 2 mm vertex distance. In `agr_max_check_37.ms:712` and `:892-894`, `cosTol` (default `1.0 - 2/100 = 0.98`, about 11.5°) is a candidate filter: `dotN >= cosTol` chooses which pairs are tested for overlap. A wider accepted angle includes more pairs. The team filter `>= 0.98` has higher recall (tests more candidate pairs, more false-positive risk). The pilot xView filter `>= 0.9999` (about 0.8°) has higher precision and skips pairs between about 0.8° and about 11.5°, so it can miss some. Opposite-normal inclusion (`dotN <= -cosTol` when `cfgOverlapIncludeOppositeNormals` is on) and the distance tolerances are separate policies. The Blender helper defaults to 2 mm and 8°. The high-poly triangle check also lacks the 150_000 review band.
   Static witness (`dot = cos(angle)`; include means the pair is a candidate, not that the faces overlap):
   - **0°** → dot `1.0`: team `1.0 >= 0.98` includes; pilot `1.0 >= 0.9999` includes → both include.
   - **5°** → dot `0.9961946981`: team `>= 0.98` includes; pilot `0.9962 < 0.9999` excludes → team includes, pilot excludes.
   - **20°** → dot `0.93969262`: team `0.9397 < 0.98` excludes; pilot excludes → both exclude.
   **Draft follow-up issue.** title: Record the team overlap candidate filter against the pilot xView filter. acceptance: document that `agr_max_check_37.ms` `cosTol` 0.98 is a candidate filter with higher recall and that the pilot `>= 0.9999` filter is more exclusive (higher precision, possible misses between about 0.8° and about 11.5°); opposite-normal and distance policies stay separate from the angle filter; no new angle-blocking rule is introduced; VPM triangle count between 150_001 and 1_000_000 stays review, not pass.

3. **Title.** Export cleanup for custom attributes, UDP, and the UV channel name.
   **Action.** port to gate.
   **Why.** `ClearCustomAttributesAndObjProp_010.ms` is the pre-export sweep found in the team folder (ownership inferred from macro category "A101"). The pilot checks channel count and does not remove CA/UDP or require the channel name `UV`.
   **Draft follow-up issue.** title: Flag custom attributes, UDP, and a map channel not named UV. acceptance: a mesh with a custom attribute fails the pre-export check; channel 1 not named UV is a finding; channels 2+ are listed; the check does not delete data unless a separate repair switch is on.

4. **Title.** Do not adopt the UCX generator pads.
   **Action.** rule.
   **Why.** `UCX_N_29.09.ms` extends helper and grid bounds by dimensionless fractions of the bbox side: outer `0.04` per axis (`:417`, `:430-433`) and divider `0.035` of the largest side (`:210`). Those are not a constant 40 mm or 35 mm clearance. A 10 m side extends 0.4 m outward and 0.35 m on the divider; at 1 / 10 / 100 m the outer extensions are 0.04 / 0.4 / 4 m and the divider extensions are 0.035 / 0.35 / 3.5 m. The final emitted collision gap is `UcxGetGapSys` (spinner default 5 mm, `:32-36`, `:928`), which is inside the project band of 2 mm–1 cm [D098]. A separate too-close check flags gaps under 0.2 mm [D162]. Hull merge still uses the 500 mm protrusion spinner.
   **Draft follow-up issue.** title: Record team UCX pad defaults as non-binding. acceptance: decisions entry states that 0.04 and 0.035 are bbox-side fractions for helper/grid extents, not fixed 0.04 m / 0.035 m gaps, and that 500 mm / 12 pieces are script defaults, not delivery rules; the delivery gap stays 2 mm–1 cm on the nominal gap, not on the pads; no builder change in that issue.

5. **Title.** Keep material IDs off the UDIM numbers.
   **Action.** rule.
   **Why.** `UDIM-MultiSub_Universal(max22-26).ms` writes `1001+floor(U)+10*floor(V)` into the face material ID. The pilot reading scheme is 1–35 and export renumbers tiles [D030]. Mixing them breaks the legend.
   **Draft follow-up issue.** title: Forbid MatID=UDIM as the working ID. acceptance: a note in `docs/domain/materials.md` cites this script; a check fails a face whose ID is ≥ 1001 on the working mesh; export may still emit tiles 1001–1100.

6. **Title.** Ignore the light-index cap of 50.
   **Action.** ignore.
   **Why.** `agr_max_check_37.ms:460` and `model.py` `light_num_max` 50 disagree with the regulation range 001–250, which the pilot already implements. The cap of 250 and the 5 m / 1.5 m spacing do match and need no new rule.
   **Draft follow-up issue.** title: Do not port light index 001–050. acceptance: issue closed as won't-do; pilot light names stay 001–250; the script line is quoted in the audit only.

7. **Title.** Reuse Flora and MAF atlas packing ideas.
   **Action.** port to agent tool.
   **Why.** `FloraAtlas.ms` packs a 24-bit diffuse plus a separate opacity atlas. `Maf Tools.mcr` already fits UDIM with padding and a TD control. The pilot has flora and MAF atlas code; the missing piece is the crop-and-opacity behaviour, not another unwrap plugin.
   **Draft follow-up issue.** title: Compare FloraAtlas opacity packing with the pilot flora atlas. acceptance: one synthetic shrub; diffuse atlas has no alpha; opacity is a second image; texel size stays inside the flora cap; no Zen UV or PolyUnwrapper code.

8. **Title.** Integer-phase grid UV for repeating maps.
   **Action.** port to agent tool.
   **Why.** `GridUVLayout22.ms` shifts polygons by whole tile steps so a tiled texture stays in phase. That is the repeatable part of the Rizom nudge the header describes, and it is smaller than adopting a commercial unwrapper.
   **Draft follow-up issue.** title: Add an integer-tile UV nudge for repeating materials. acceptance: a tiled quad moves by an integer U/V step only; phase inside the period is unchanged; non-repeating materials are left alone.

9. **Title.** Write the team NPM atlas defaults next to the 10–40 rule.
   **Action.** standard.
   **Why.** The packer defaults (2048 atlas, 35 px/m textures, 12.5 px/m plugs, 16 px plug cell) are usable job defaults inside a rule the pilot already has. Padding must be raised from 6 to 8 when they are copied.
   **Draft follow-up issue.** title: Record NPM atlas job defaults from VPM_to_NPM. acceptance: a short subsection in `docs/domain/uv-textures.md` lists 2048, 35 px/m, 12.5 px/m, 16 px cell, and states padding ≥ 8 px overrides the script's 6 px; no code change.

10. **Title.** Leave AutoCAD LISP as reference.
    **Action.** ignore.
    **Why.** Circle and `XXX.XX` text export duplicate what the DWG inspector already reads. Porting LISP into the agent path adds a second point format without a rule the DWG path lacks.
    **Draft follow-up issue.** title: Do not port NUM2CIRCLE or EXPORTCIRCLESCSV. acceptance: closed as won't-do unless a ground job shows points that exist only as AutoCAD text; the audit remains the record.

11. **Title.** Do not port third-party packs or the checker AABB test.
    **Action.** ignore.
    **Why.** Zen UV, PolyUnwrapper, window and road generators, Acrobat, PruneScene, rapidTools, AtlasBuilder and FacadeAtlasBuilder binaries, PNG compressors, Copitor, and the composition overlay are not AGR rules. `checks.py` AABB intersections are weaker than the pilot SAT. AtlasBuilder stays on issue #524 as a product, not as source to vendor from this folder.
    **Draft follow-up issue.** title: Keep third-party Telegram archives out of the repo. acceptance: no archive from the third-party list is committed; #524 is not duplicated; AGR Checker AABB overlap is not copied into `twinqa`.

12. **Title.** One-by-one library ZIP is not a delivery path.
    **Action.** ignore.
    **Why.** `AlexYo_OneByOneExport_Preview_v18.ms` packs `Name_high` / `Name_low` for a prop library. Delivery ZIPs stay address-based.
    **Draft follow-up issue.** title: Do not use OneByOne export for NPM/VPM packages. acceptance: closed as won't-do for delivery; library packaging can be a separate backlog line if a prop library is in scope.

## Missing inputs & limitations

- **Excluded documents.** `ИНСТРУКЦИЯ_ПОЛЬЗОВАТЕЛЯ.txt` and `Новые требования к НПМ+ВПМ.pdf` are excluded by user decision (Artem, 2026-10-21) as outdated. They are not used as a source.
- **Twelve large third-party files were not in the local copy** and were not opened. Name and purpose only: Acrobat Pro portable; `AGR_Arxiv_1.5_Windows` compiled archiver; `AtlasBuilder.zip` and `AtlasBuilder_portable_1.zip`; `FacadeAtlasBuilder-win64.zip`; `Backdrop Generator v2.0_Max2018+.rar`; `Road Markings Generator 2.0.rar`; `Materialize_1.78 (1).zip`; `MaximkaE_PngCompr.7z`; `PNG_Compressor.exe` and `PNG_Compressor__msg_28662.exe`; `TextureMapGeneratorV5.exe`.
- **Other third-party archives in the copy** (Zen UV, PolyUnwrapper, window/blinds generators, CheckToolBox, BMAX, PruneScene, UVTools, EdgeAlign, xCavity, SafeOrbit, Viewport Reflect, and the rest of the JSON `third-party` rows) were classified from `archive_inventory.json` and the file name. Contents were not read.
- **Authors.** AlexYo, A101, Nikolay Litvinov, Christoph Bülter, Mathieu Jacquin, WunschTools, IN_tools, and RUST Script are strings in the files. Where the JSON says `author_inferred: true`, the name is taken from a category or filename, not from a signature block. Bülter, Litvinov and Jacquin files are `third-party`; eleven utilities with no signature are `unattributed-utility` (owner unresolved).
- **Not executed.** No script, installer, or exe was run. AGR Checker's README says its FBX parser was not validated on real Max exports. `agr_max_check_37.ms` says the same about Max. Those limitations still stand.
- **Partial reads.** `apply_atlas_uv.ms`, `Maf Tools.mcr`, `agr_max_check_37.ms`, `UCX_Tools.ms`, and `A101AGRLP.ms` are long. Thresholds above are from the lines cited. Unquoted magic numbers in those files are not claimed. `Ground_Tools.ms` in the bundle was not line-matched to the loose file. The two Zipper copies differ by a small line count that was not interpreted. `Udim_Geo_Json.ms` was not line-matched to UDIM Viewer v1.4.
- **`Volume_vision.mat`** was not decoded.
- **`XViewInspectorMax.7z`** is an mzp plus two text files in the archive listing. It was not extracted (not on the in-house extract list).
- **Media.** `Скрипт_Ground_Tools.zip` is a video, listed in `document_exclusions.json` / archive inventory as media excluded to trash. It is not one of the 99 technical files.
