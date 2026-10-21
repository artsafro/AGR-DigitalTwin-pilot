# Team plugins audit (Artem's 3ds Max / Blender setup)

This is a static reading of Artem's 3ds Max / Blender plugin and script folder (issue #538), a second pass on the method in [`team-scripts-audit.md`](team-scripts-audit.md) (#537). The local copy is `C:/x/3dsmax-plugins/` (6108 files). `_copy_log.json` records 7182 skipped files (exe, msi, dll, dlo, dlu, dlm, pyc, pyd, max, images, pdf, and files over 50 MB) as `[relative_path, size_bytes]`. The log does not record a Drive path (`drive_folder` is null). Comparison baseline is pilot `main` `9373df60572554fb0dcfa692fa6e172266bbf43a`. A file whose SHA256 equals a row in `team-scripts-inventory.json` is marked `covered-by-537` and is not analysed again. No plugin, script, installer, or exe was installed or run. `.cuix` and `.mnux` in this copy are UTF-8 XML with a BOM, not zip archives; they were parsed as XML. `.mzp` files that are in-house were not required to be unpacked: the in-house material is loose `.ms` / `.mcr` / `.py`. Third-party archives were not opened.

## Inventory

Full row-per-file data is in [`team-plugins-inventory.json`](team-plugins-inventory.json). 13290 rows = 6108 copied files plus 7182 skipped entries. Copied-file hashes were computed in this pass with SHA256. Skipped rows have `sha256: null` and were classified from the file name only.

| Split | Count | What it is |
|---|---|---|
| in-house | 37 | MaxScript, Python, and encrypted `.mse` written for this work |
| in-house-utility | 17 | Small helpers (align, attach, wire color, layer tools, build scripts) |
| third-party | 267 | Plugin binaries, installers, and third-party script packages |
| third-party-resource | 12680 | Textures, icons, samples, Bercon source, and the texture-tool Python venv |
| covered-by-537 | 34 | Same SHA256 as a row in the #537 inventory |
| hotkey-config | 4 | `my_set_2024.hsx` (two copies), Rizom `.kbd`, `Hotkeys!.txt` |
| workspace | 73 | `.cuix`, `.mnux`, Octopus presets, and the other Max UI files |
| document | 121 | Readmes, the hotkey and Lumen notes, PDFs by name |
| export-artifact | 57 | PyInstaller output, `__pycache__`, and the built texture-tool exes |

Classification counts above are the JSON `classification` field. 37 + 17 + 267 + 12680 + 34 + 4 + 73 + 121 + 57 = 13290.

Version families with more than one file (latest marked in the JSON):

| Family | Files | Latest |
|---|---|---|
| Flora Atlas | `Flora Atlas.mcr` (no V1.2 header), `Flora Atlas V1.2.mcr`, `Andrew_scripts/FloraAtlas.ms` | V1.2 (the macro and the Andrew `.ms`; they are not byte-identical) |
| Optimise_info | `Optimise_info.ms`, `Optimise_info_2.ms` | `_2` (the only diff is a trailing blank line) |
| h_instancer | loose `H_instancer-1.0.mcr` and `developer_tools-h_instancer-1.0.mcr` | loose file (the two files are byte-identical, version 1.0) |
| Texture Map Generator | `import tkinter as tk2_v2.py` (title 2.0), `texture_map_generator.py` (single file), package `texture_map_generator/` | package `__init__.py` version 2.0.0 |
| my_set_2024 | empty `.hsx` under `Hotkeys_Workspaces_Scripts/`, assigned `.hsx` under `Плагины 3dMax/` | the assigned file (8030 bytes) |
| MultiScatter | 1.615 (Max 2016–2021) and 1.630 (Max 2024) | 1.630 |
| MultiTexture | 2.01 and 2.04, one binary per Max year | 2.04 for Max 2026 |
| Project Manager | 2.92.09 and 3.35.75 | 3.35.75 |
| UVTools | 3.2m and 3.3.05 | 3.3.05 |
| Smart Merge | 2.19 and 2.28 | 2.28 |
| SiNi Software | 2.0.0 and 2.0.2 | 2.0.2 |
| Copitor | v1.61, v2, v2.3, v3 | v3 (that file is `covered-by-537`) |
| Octopus presets | `2026-2-10-11-49-27` and `2026-2-10-12-46-37` | 12:46 |
| Max workspace 2024 | `Workspace1`, `2024_new`, `Workspace_2024`, `artsafro__usersave__` | `artsafro__usersave__` (toolbar matches the daily tools) |
| Glue / Quad Cap Pro | one binary per Max year | parallel year builds of Glue (unversioned) and Quad Cap Pro 1.01, not successive tool versions |

`Andrew_scripts/` copies of `FloraAtlas.ms`, `FreeSpot_Tools.ms`, `Ground_Tools.ms`, `Interier_Box.ms`, `Poly Actions Copy_V6.ms`, `Region_Cut.ms`, `Texture_Zaglushki_Ground.ms`, `UCX_Check.ms`, `UCX_Tools.ms`, and `Udim_Geo_Json.ms` are byte-identical to the members of `Для Артема.zip`. That zip is `covered-by-537`. The loose files are not, because #537 hashed the zip, not the members. `Maf Tools.mcr`, `NUM2CIRCLE.lsp`, `SelectNumbers.lsp`, and `UDIM Viewer_V1.4.ms` in the same folder match #537 rows byte for byte and are `covered-by-537`.

## Already covered by #537

No new per-script card. Purpose and production step are copied from `team-scripts-inventory.json`.

| File | #537 purpose | Production step |
|---|---|---|
| `Hotkeys_Workspaces_Scripts/8BIT_TO_24BIT&COMPRESS/convert_8bit_to_24bit.py` | 8-bit to 24-bit PNG conversion for 256×256 plugs | UDIM/atlas |
| `Hotkeys_Workspaces_Scripts/texmapgen_errors/ConcaveFixer.ms` | Find and fix concave polygons | modeling |
| `Плагины 3dMax/A101AGRLP.ms` | Low-poly naming UI for OKS, Ground, GroundEl, Flora and FBX export | naming |
| `Плагины 3dMax/AlexYo_AGR_renamerV2.ms` | Copy bitmaps to `T..._d/_r/_m/_o/_n` names | naming |
| `Плагины 3dMax/AlexYo_ConcaveFixer.ms` | Find and fix concave polygons | modeling |
| `Плагины 3dMax/BMAX_3dsmax_v1.19.mzp` | Third-party connector package | n/a |
| `Плагины 3dMax/ClearCustomAttributesAndObjProp_001.ms` | Strip custom attributes and UDP | cleanup |
| `Плагины 3dMax/ClearCustomAttributesAndObjProp_010.ms` | Strip CA/UDP, extra channels, rename channel 1 to UV | cleanup |
| `Плагины 3dMax/Collizii.ms` | Intersection check | UCX |
| `Плагины 3dMax/CoronaProxyDisplay_EN.ms` | Corona Proxy viewport display | lighting |
| `Плагины 3dMax/dragNDropReferences11.ms` | Drop images in as reference planes | utility |
| `Плагины 3dMax/EdgeDistributor.ms` | Even spacing of verts, rings, or strips | modeling |
| `Плагины 3dMax/Light.ms` | Clone a Free Spot onto polygons | lighting |
| `Плагины 3dMax/Light_Metr.ms` | Highlight objects closer than a distance | lighting |
| `Плагины 3dMax/Maf_Fly.ms` | Select meshes whose bounds do not touch | MAF |
| `Плагины 3dMax/MultiBridge.ms` | Bridge several edge or polygon pairs | modeling |
| `Плагины 3dMax/Objects Normal Fix v.2.4.mzp` | Third-party normal fix | n/a |
| `Плагины 3dMax/Poly_X,Y,Z.ms` | Select faces by world axis | modeling |
| `Плагины 3dMax/rapidToolsInstaller_v1.14.mzp` | Third-party rapidTools | n/a |
| `Плагины 3dMax/UDIM Viewer_V1.2.ms` | UDIM viewer | UDIM/atlas |
| `Плагины 3dMax/VertexEdgeSplit_UI_v2.ms` | Split an edge at a vertex | modeling |
| `Плагины 3dMax/xCavity_2.0.1.zip` | Third-party cavity tool | n/a |
| `Плагины 3dMax/Для Артема.zip` | In-house bundle (Ground, MAF, Flora, UCX, and the rest) | utility |
| `Плагины 3dMax/Andrew_scripts/Maf Tools.mcr` | MAF UDIM, glue, render, ID colors | MAF |
| `Плагины 3dMax/Andrew_scripts/NUM2CIRCLE.lsp` | Turn numeric text into circles | Ground |
| `Плагины 3dMax/Andrew_scripts/SelectNumbers.lsp` | Select `XXX.XX` text | Ground |
| `Плагины 3dMax/Andrew_scripts/UDIM Viewer_V1.4.ms` | UDIM viewer v1.4 | UDIM/atlas |
| `Плагины 3dMax/Copitor_v3/zOffTy Tools-Copitor_v3.mcr` | Mesh clipboard | utility |
| `Плагины 3dMax/imagecomphelper-master/imagecomphelper.ms` | Viewport composition lines | utility |
| `Плагины 3dMax/Project_Manager_3.35.75/.../ProjectManager_3.mzp` | Project browser | n/a |
| `Плагины 3dMax/Prune Scene/PruneScene3.6.2.mzp` | Scene cleaner | n/a |
| `Плагины 3dMax/Prune Scene/PruneScene3.6.2 — копия.zip` | Same bytes as the Prune Scene mzp | n/a |
| `Плагины 3dMax/UVTools_3.2m/.../UVTools_3.2m.mzp` | UV tools 3.2m | n/a |
| `Плагины Blender/CheckToolBox v1.5.zip` | Blender checker | n/a |

The one-line purposes in that table are shortened from the JSON. The JSON copies the #537 purpose string verbatim.

## In-house scripts

Order follows a production pass, then the new helpers, then the Andrew copies of the #537 bundle. Quotes are at most 15 lines. Andrew cards state the byte match and do not re-derive thresholds already cited in #537.

### layers_polycount

**Purpose.** Print a polygon total for every layer and mark layers over 100000 polygons.

**Production step.** Checks.

**Inputs/Outputs.** Every geometry node in the open scene. Writes lines to the listener. No file export. `Hotkeys_Workspaces_Scripts/layers_polycount.ms`.

**Algorithm.** Sum `getPolygonCount` per layer, sort descending, and prefix `***` when the total is above 100000.

**Hard-coded values.**

```
45:    if polyCount > 100000 then
46:        format "*** %: % polygons\n" layerName polyCount
```

**Limitations.** Polygons, not triangles. Per layer, not per FBX. Not an export gate.

**Diff vs older versions.** One file.

### Optimise_info

**Purpose.** Move the heaviest meshes onto a layer named `Optimise`, and objects that use very large bitmaps onto `Optimise Tex`.

**Production step.** Checks.

**Inputs/Outputs.** Scene geometry and bitmap textures. Renames moved objects with a `_from` suffix and changes their layer. `Optimise_info.ms` and `Optimise_info_2.ms`.

**Algorithm.** Take the top N meshes whose face count is above a minimum and the top N bitmaps whose width and height are both above a minimum. Create the two layers if they are missing.

**Hard-coded values.** From the call at the bottom of `Optimise_info_2.ms` (same numbers in `Optimise_info.ms`):

```
125:heavyTextures = findHeavyTextures 10 4096
126:moveHeavyObjectsToLayer 20 100000
```

Top 10 textures, both sides strictly greater than 4096. Top 20 objects with more than 100000 faces. The listener also prints a top-10 preview inside each new layer.

**Limitations.** Face count, not triangles. A 4096 map is not flagged. Non-square and smaller illegal sizes are not flagged. Renames and re-layers the scene.

**Diff vs older versions.** `_2` drops one trailing blank line. The calls and thresholds match.

### density

**Purpose.** Draw a per-face texel-density number in the viewport.

**Production step.** UDIM/atlas.

**Inputs/Outputs.** One editable mesh or editable poly. Draws text. No file export. `Плагины 3dMax/density.ms`.

**Algorithm.** For an editable poly, triangle-sum the UV area on map channel 1 and divide by the world face area. The mesh branch draws the face index instead of a density.

**Hard-coded values.**

```
42:						if totalAreaWorld > 0 and totalAreaUV > 0 then TexelDensity =  4096 * sqrt(totalAreaUV / totalAreaWorld)
```

The 4096 is a map size in pixels. The result is px per scene-unit length only if the scene unit is the meter and the map is 4096.

**Limitations.** Not a pass/fail check. Channel 1 only. One selected object.

**Diff vs older versions.** One file.

### id_subtract

**Purpose.** Remove a list of material IDs from the current polygon selection.

**Production step.** Modeling.

**Inputs/Outputs.** One editable poly. Changes the face selection. `Плагины 3dMax/id_subtract.ms`.

**Algorithm.** Parse comma, semicolon, or space separated integers and clear those IDs in the selection.

**Hard-coded values.** Default exclude text is `1,2,5` (`id_subtract.ms:5`). No geometric tolerance.

**Limitations.** Selection helper. The default IDs are an example, not a legend.

**Diff vs older versions.** One file.

### Three-point align

**Purpose.** Move, rotate, and optionally scale the selection so three picked points land on three target points.

**Production step.** Modeling.

**Inputs/Outputs.** One selected object and six viewport picks. Rewrites the node transform. `Плагины 3dMax/3pt_align.mcr`.

**Algorithm.** Header "ThreePointAlign v 1.31 - 04.09.17 - (c) M. Breidt". Builds a matrix from point 1–2–3 and from point 4–5–6, then offers a flip, a normal offset, and a uniform scale. Category `MB Tools`. The artsafro toolbar and the Octopus `myscripts` menu both call `macros.run "MB Tools" "ThreePointAlign"`.

**Hard-coded values.** None that encode an AGR length. Negative scale after a flip is called out in the header as a known limitation.

**Limitations.** Quote-ware utility, not an AGR check. On the daily menu.

**Diff vs older versions.** v1.31 only.

### h_instancer

**Purpose.** Replace the selection with instances of one picked object, copying rotation and scale.

**Production step.** MAF.

**Inputs/Outputs.** One picked master and a selection. Creates instances and can delete the selection. `H_instancer-1.0.mcr`. Category `Developer Tools`.

**Algorithm.** For each selected node, `instance` the master, copy position, and optionally rotation, scale, and the old name, then delete the selection if "replace selection" is on.

**Hard-coded values.** Replace, scale, and rotation checkboxes default on (`H_instancer-1.0.mcr:21-23`). No spacing distance.

**Limitations.** Instances are a scene convenience. Delivery meshes are not an instance graph.

**Diff vs older versions.** `developer_tools-h_instancer-1.0.mcr` is the same bytes. The artsafro toolbar binds `h_instancer` / `Developer Tools`.

### Object randomizer

**Purpose.** Jitter position, rotation, and scale of the selection.

**Production step.** MAF.

**Inputs/Outputs.** The selection. Rewrites transforms. `objectrandomizerv3.ms`.

**Algorithm.** Independent min/max per axis, absolute or relative. Uniform scale is on by default and all three channels start disabled until their checkbox is turned on.

**Hard-coded values.** Move defaults −6..6 (the Y max spinner is also −6). Rotate −45..45 degrees. Scale −10..10 percent (`objectrandomizerv3.ms:30-61`).

**Limitations.** Author defaults for a scatter look. Not a planting distance.

**Diff vs older versions.** v3 only in this folder.

### Quick Attach

**Purpose.** Attach many objects into editable-poly chunks.

**Production step.** Modeling.

**Inputs/Outputs.** The selection. New poly objects. `quickattach_v1.82.mcr`. Header credits Morozov Anton. Category `# Scripts`.

**Algorithm.** Walks the selection and starts a new mesh every N objects. Can also target splines.

**Hard-coded values.** `seq = 300` (`quickattach_v1.82.mcr:9`).

**Limitations.** Not on the hotkey set read here. No AGR naming.

**Diff vs older versions.** v1.82 only.

### Random wire color

**Purpose.** Paint one wire color per instance group.

**Production step.** Utility.

**Inputs/Outputs.** Selected geometry and shapes. Sets `wirecolor`. `RandomWireColor.mcr`. Category `Nik Scripts`.

**Algorithm.** Groups instances, then assigns one HSV color to the group.

**Hard-coded values.** Hue 0–255, saturation 140, value 150–240 (`RandomWireColor.mcr:39-41`).

**Limitations.** Viewport color only.

**Diff vs older versions.** One file.

### Vertex cleaner

**Purpose.** Select and delete vertices whose stored weight is under a threshold.

**Production step.** Modeling.

**Inputs/Outputs.** The current editable poly (`$`). Deletes vertices. `ShivaTools_VertexCleaner (2).mcr`. Header "Vertex Cleaner 1.0 by Yegor Tsyba". The artsafro toolbar binds `VertexCleaner` / `Shiva Tools`.

**Algorithm.** `vx_sort` keeps a vertex when `vx_weight[i] <= trash_val * 0.01573`, selects those vertices, and removes them.

**Hard-coded values.** Spinner default 10, range 0–100 (`ShivaTools_VertexCleaner (2).mcr:33`). Factor 0.01573 at line 19.

**Limitations.** The weight is not a meter distance. Not the pilot 0.002 m vertex weld.

**Diff vs older versions.** The "(2)" file only.

### Zamena

**Purpose.** Replace every object whose name matches a pattern with a copy of a picked source.

**Production step.** Modeling.

**Inputs/Outputs.** A picked source and a name search. Deletes the matches and inserts copies. `Andrew_scripts/Zamena_V2.ms`. Header says 3ds Max 2024.

**Algorithm.** Substring or exact match, then a copy that can keep world rotation, scale, name, and parent.

**Hard-coded values.** Keep scale, rotation, and name default on (`Zamena_V2.ms:27-29`). No numeric AGR threshold.

**Limitations.** Name match is not the AGR `SM_` / `UCX_` scheme.

**Diff vs older versions.** V2 only. Not inside `Для Артема.zip`.

### Flora Atlas (older macro)

**Purpose.** Pack flora bitmaps into one atlas.

**Production step.** Flora.

**Inputs/Outputs.** Flora objects and their bitmaps. Writes an atlas image. `Плагины 3dMax/Flora Atlas.mcr`. Button text "Flora Atlas", category "Flora Tools".

**Algorithm.** Shelf-pack cropped tiles into a 24-bit bitmap. This file has no "V1.2" header and was not line-matched to the V1.2 macro.

**Hard-coded values.** Size list `256, 512, 1024, 2048, 4096, 8192`, dropdown selection 4 (2048). Padding spinner range 0–128, default 2. UV channel default 1 (`Flora Atlas.mcr:870-876`).

**Limitations.** Padding 2 px is below the pilot minimum of 8 px. 8192 is not a VPM size.

**Diff vs older versions.** This is the older of the two loose macros. See V1.2.

### Flora Atlas V1.2

**Purpose.** Pack a 24-bit flora diffuse atlas and a separate opacity atlas.

**Production step.** Flora.

**Inputs/Outputs.** Flora objects and diffuse/opacity bitmaps. Writes PNGs. `Flora Atlas V1.2.mcr`. Header lists UV crop, alpha, and opacity when the diffuse has no alpha.

**Algorithm.** Same shelf pack as the Andrew `FloraAtlas.ms` that #537 already described. `Format24bppRgb` at `Flora Atlas V1.2.mcr:249`. This macro is 51163 bytes; `Andrew_scripts/FloraAtlas.ms` is 51024 bytes and matches the zip member, so the two V1.2 texts are not the same file.

**Hard-coded values.** Same size list and the same defaults as the older macro: 2048 selected, padding 2, channel 1 (`Flora Atlas V1.2.mcr:1449-1455`).

**Limitations.** Same padding and size-list issues. C# inside the script was not executed.

**Diff vs older versions.** V1.2 adds the opacity-atlas header. The Andrew `.ms` is the zip member #537 read as FloraAtlas V1.2.

### Index-color plugs

**Purpose.** Turn 256×256 images into flat 8-bit palette PNGs.

**Production step.** UDIM/atlas.

**Inputs/Outputs.** A folder of images. Writes PNGs, either beside the input under `converted` or over the originals if that mode is chosen. `Hotkeys_Workspaces_Scripts/index_color/index to rgb.py`. Window title says "256x256 в 8-бит заглушки".

**Algorithm.** Skip any image that is not 256×256. Convert to RGB, average the pixels, build a 256-color palette whose first entry is that average, and fill every pixel with palette index 0. Save as PNG mode `P`.

**Hard-coded values.** Size test `(256, 256)` at `index to rgb.py:242`. Palette length 256 at lines 257–263. Fill with index 0 at line 270.

**Limitations.** This is the opposite of `convert_8bit_to_24bit.py` (that file is `covered-by-537` and writes 24-bit RGB). An 8-bit indexed plug is not a delivery PNG.

**Diff vs older versions.** One source file. `IndextoRgbConverter.exe` is a built exe in the skipped set and was not run.

### Texture Map Generator

**Purpose.** Build diffuse, ERM, and normal maps, and rename files into a UDIM scheme.

**Production step.** UDIM/atlas.

**Inputs/Outputs.** Image files and an output folder. Writes maps. Package `texture_map_generator/` version 2.0.0 (`__init__.py`). The single-file `texture_map_generator.py` and `import tkinter as tk2_v2.py` (window title "Texture Map Generator 2.0") are earlier forms. `run_app.py`, `build_exe.py`, and `test_latin_check.py` launch or package it.

**Algorithm.** The UI offers save sizes `original`, `2048`, and `4096` (`ui.py:120`). Map types recognised by the renamer are Diffuse, ERM, and Normal (`utils.py:463-470`). A 256×256 image whose pixels are one color is reported as a plug (`utils.py:82-83`, `app.py:151`). The UDIM wizard button tells the user it is not implemented yet (`app.py:452`).

**Hard-coded values.** Name builder (`utils.py:521-525`):

```
521:    parts = ["T", address]
522:    if is_ground:
523:        parts.append("Ground")
524:    parts.append(map_type)
525:    new_name = "_".join(parts) + f"_{slot}.{udim}{ext.lower()}"
```

OKS pattern in the dialog: `T_Address_Type_Slot.UDIM.ext`. Ground: `T_Address_Ground_Type_Slot.UDIM.ext` (`dialogs.py:402-405`). Allowed filename characters are ASCII letters, digits, hyphen, underscore, and dot (`utils.py:196-206`). Roughness and metallic strength fall back to 0.5 (`save.py:328-333`). Preview 3D downscales to 512 (`preview_3d.py:294`).

**Limitations.** ERM is one map, not separate roughness and metalness files. Hyphen and dot are outside the pilot file-name charset. The venv under `.venv/` is third-party Python (matplotlib, PyOpenGL, and the rest) and was not read as a tool. Built exes were not run.

**Diff vs older versions.** The package is the latest split of the 2.0 GUI. The monolith and `tk2_v2` are the previous single files.

### VV layer helpers

**Purpose.** Add the selection to a layer, hide layers, select a layer's objects, or isolate layers.

**Production step.** Utility.

**Inputs/Outputs.** The selection and the layer manager. `VV_SuperLayer_Functions_1.5.ms`, header notes for unmodified, Shift, Ctrl, and Alt.

**Algorithm.** Layer-manager helpers. No mesh edit.

**Hard-coded values.** None that encode an AGR measure. Version 1.5 in the file name.

**Limitations.** Not on the hotkey list read here.

**Diff vs older versions.** 1.5 only.

### Ground_Tools (Andrew copy)

**Purpose.** Simplify Ground borders, retopologize fans, and build a terrain from heights.

**Production step.** Ground.

**Inputs/Outputs.** The open Max scene. `Andrew_scripts/Ground_Tools.ms` (47330 bytes).

**Algorithm.** Byte-identical to `Для Артема.zip` / `Для Артема/Ground_Tools.ms`. #537 already described that member as the reformatted sibling of the loose 46246-byte file. Rollouts were not re-read.

**Hard-coded values.** Those cited in #537 for the loose file (border tolerance 1.0, corner 30°, seam 0.01, terrain segments 60, margin 5%). Not re-measured on this copy.

**Limitations.** Same as #537. Not a delivery check.

**Diff vs older versions.** Matches the zip member. Does not match the loose telegram file (46246 bytes, different SHA256).

### FreeSpot_Tools (Andrew copy)

**Purpose.** Place Free Spots and thin them.

**Production step.** Lighting.

**Inputs/Outputs.** Selected polygons. `Andrew_scripts/FreeSpot_Tools.ms`.

**Algorithm.** Byte-identical to the zip member #537 described (FreeSpot Optimizer v2.3, cap 250, minimum distance 1.5 m).

**Hard-coded values.** Not re-measured. #537 cites max 250 and 1.5 m.

**Limitations.** Does not encode the 5 m omni spacing.

**Diff vs older versions.** Zip member only in this folder.

### FloraAtlas.ms (Andrew copy)

**Purpose.** Pack flora diffuse and a separate opacity atlas.

**Production step.** Flora.

**Inputs/Outputs.** Flora bitmaps. `Andrew_scripts/FloraAtlas.ms`.

**Algorithm.** Byte-identical to the zip member. Header in the file is "Flora Atlas V1.2". See the V1.2 macro card for the size list on the sibling macro.

**Hard-coded values.** Not re-measured beyond the V1.2 header already quoted in #537 (24-bit RGB, opacity map).

**Limitations.** Same as #537.

**Diff vs older versions.** Zip member. Not byte-identical to `Flora Atlas V1.2.mcr`.

### Interier_Box (Andrew copy)

**Purpose.** Extrude an interior box.

**Production step.** Modeling.

**Inputs/Outputs.** A box in the scene. `Andrew_scripts/Interier_Box.ms`.

**Algorithm.** Byte-identical to the zip member #537 described as Interior Box Creator v1.37, depth default 2.0 m.

**Hard-coded values.** Not re-measured.

**Limitations.** Interior helper, not an OKS shell rule.

**Diff vs older versions.** Zip member only.

### Poly Actions Copy (Andrew copy)

**Purpose.** Record poly edits and reapply them.

**Production step.** Modeling.

**Inputs/Outputs.** An editable poly. `Andrew_scripts/Poly Actions Copy_V6.ms`.

**Algorithm.** Byte-identical to the zip member. #537 cites header v7.6.0.

**Hard-coded values.** Not re-measured.

**Limitations.** No AGR threshold.

**Diff vs older versions.** Zip member only.

### Region cut (Andrew copy)

**Purpose.** Grow a polygon selection to the enclosing region.

**Production step.** Modeling.

**Inputs/Outputs.** One selected polygon. `Andrew_scripts/Region_Cut.ms`.

**Algorithm.** Byte-identical to the zip member #537 described (one-click fill, Max 2024).

**Hard-coded values.** None beyond Max 2024, as in #537.

**Limitations.** Selection helper.

**Diff vs older versions.** Zip member only.

### Texture placeholders (Andrew copy)

**Purpose.** Write 24-bit PNG placeholders plus ERM and normal stand-ins.

**Production step.** Ground.

**Inputs/Outputs.** Picked textures and a folder. `Andrew_scripts/Texture_Zaglushki_Ground.ms`.

**Algorithm.** Byte-identical to the zip member #537 described.

**Hard-coded values.** 24-bit PNG in the rollout title, as #537 cited. Not re-measured.

**Limitations.** Does not know the 128×128 flat metallic/roughness plug rule.

**Diff vs older versions.** Zip member only.

### UCX_Check (Andrew copy)

**Purpose.** Check UCX pieces against each other.

**Production step.** UCX.

**Inputs/Outputs.** UCX nodes in the scene. `Andrew_scripts/UCX_Check.ms`.

**Algorithm.** Byte-identical to the zip member. #537 cites tolerance 0.01 scene units on `UCX_Check.ms`.

**Hard-coded values.** Not re-measured.

**Limitations.** 0.01 scene units is 1 cm if the unit is the meter. Pilot SAT epsilon is 0.01 mm.

**Diff vs older versions.** Zip member only.

### UCX_Tools (Andrew copy)

**Purpose.** Slice a mesh into UCX pieces.

**Production step.** UCX.

**Inputs/Outputs.** One mesh. `Andrew_scripts/UCX_Tools.ms`.

**Algorithm.** Byte-identical to the zip member #537 described, including the 2 mm toolkit gap default.

**Hard-coded values.** Not re-measured. #537 cites the 2 mm gap.

**Limitations.** 2 mm is the low edge of the delivery band, not the whole rule.

**Diff vs older versions.** Zip member only.

### Udim_Geo_Json (Andrew copy)

**Purpose.** UDIM viewer sibling of UDIM Viewer v1.4.

**Production step.** UDIM/atlas.

**Inputs/Outputs.** A job folder. `Andrew_scripts/Udim_Geo_Json.ms` (45843 bytes).

**Algorithm.** Byte-identical to the zip member. #537 did not line-match it to UDIM Viewer v1.4 (that viewer is 44682 bytes and is `covered-by-537` from `Andrew_scripts/UDIM Viewer_V1.4.ms`).

**Hard-coded values.** Not re-measured.

**Limitations.** Same title family as the viewer, different bytes.

**Diff vs older versions.** Zip member. Not the v1.4 file.

**Encrypted in-house scripts.**

Name and purpose only. Not decrypted, no per-script card.

- `ColorIDAssign.mse` — assign color material IDs.
- `DriverMaster.mse` — a driver or controller master, from the file name only.
- `UVtoMESH_02.mse` — build a mesh from UVs, from the file name only.
- `aa_stonePlacementTools_irregularStones_1x0.mse` — irregular stones, version 1.0.
- `aa_stonePlacementTools_stoneQuads_1x0.mse` — stone quads, version 1.0.
- `aa_stonePlacementTools_stoneWall_1x0.mse` — a stone wall, version 1.0.
- `aa_stonePlacementTools_utility_1x0.mse` — utility for that set, version 1.0.

## Hotkeys and workspaces

The live Max hotkey file is `Плагины 3dMax/my_set_2024.hsx`. The copy under `Hotkeys_Workspaces_Scripts/my_set_2024.hsx` is an empty `<MaxHotkeyTransformations>` and is not the working set. `hotkeys.docx` matches `Hotkeys!.txt`. Both notes disagree with the `.hsx` on several keys. Where they disagree, the `.hsx` is the binding that Max will load.

Daily Max bindings that resolve:

| Key | Resolves to | Class |
|---|---|---|
| CapsLock | `Octopus - artsafro` | workspace menu, see below |
| F9 | `rapidQCap` / rapidTools | third-party, file is `covered-by-537` |
| F11 | `fastBridge` / rapidTools | third-party, same installer |
| F8 | `LBTools - PAT Quad` and also `Reset Transforms Selected` | two assignments on one key; LBTools is not in this copy |
| F12 | Center Pivot | built-in PolyTools |
| Ctrl+Alt+F | xView overlapping faces | built-in checker |
| Ctrl+Alt+V | xView overlapping vertices | built-in checker |
| Ctrl+Shift+S | Swift Loop | built-in |
| Space | Maximize viewport | built-in (the note calls this collapse/expand) |
| `` ` `` | NURMS toggle | built-in |
| Ctrl+E | Convert to editable poly | built-in |
| Ctrl+U / Ctrl+Shift+U | UVW Map / Unwrap UVW | built-in |
| Ctrl+B | Bridge | built-in |
| Shift+W | Weld | built-in |
| Alt+L / Alt+R | Loop / Ring | built-in PolyTools |

Modifier keys in the same file (UVW Map, Unwrap, FFD, Smooth, Symmetry, Chamfer, Shell, Relax, OpenSubdiv, AutoSmooth, Turn to Poly, Extrude, Attach, Detach, Group) are stock modeling commands. They are daily, and they are not scripts from this folder.

`Hotkeys!.txt` also lists Spacing Tool as Shift+I, Cap as Alt+P, Quick Slice as Ctrl+Shift+Q, Slice Plane as Ctrl+Alt+S, and Connect as Ctrl+Shift+C, plus mouse-side buttons on a G403. Those keys are not assigned in `my_set_2024.hsx`. In the `.hsx`, Ctrl+Alt+S is Smooth, and Connect is Ctrl+Shift+X. Those note entries are unresolved against the live file.

`HOTKEYS_RIZOM.kbd` is a RizomUV map, not a Max map. Keys that are actually assigned (empty strings in the file are unbound): Pack `P`, Unfold `U`, Optimize `O`, Cut `C`, Weld `W`, texel-density pick `Alt-Q`, texel-density apply `Shift-Q`, overlaps `Alt-L`, pin `Alt-P`. This is the UV step's daily application. The Max-side bridge on the toolbar is `RizomuvBridge` / `Titus_Scripts` (`RizomuvBridge_1.5.1.mzp`).

Octopus preset `OctopusPresets-2026-2-10-12-46-37` is the later of the two exports. CapsLock opens `artsafro.octopus`, whose buttons only switch to other Octopus panels: Selection, Axis, Cloner, Views, Sini, Group, Modeling, Modifiers. `sini.octopus` runs SiNi IgNite, Pivot, Scribe, and Sculpt. `myscripts.octopus` is the script panel:

| Button | Resolves to | Class |
|---|---|---|
| A101LP | The body of `A101AGRLP.ms` pasted into the button (naming, maps, FBX) | `covered-by-537` |
| UVTools | `macros.run "Nik Scripts - UV Tools" "UVT_OpenUi"` | third-party UVTools 3.3.05 |
| 3Pt Align | `macros.run "MB Tools" "ThreePointAlign"` | in-house-utility |
| Copitor | `macros.run "zOffTy Tools" "Copitor"` | `covered-by-537` |
| UCX_Concave | Inline `selectStrictlyConcavePolygons` | same idea as the concave selector #537 already read; this button is not a separate file |
| GeoAGR | `macros.run "Geoscript" "GeoAGR"` | unresolved — no GeoAGR file in the copy |
| Editable Mesh | Convert to mesh | built-in |
| Reset Transform | `actionMan.executeAction 0 "0"` | unresolved — action id `0` is not a named command |

The artsafro toolbar (`artsafro__usersave__.cuix`) repeats the daily set: SiNi tools (IgNite, Sculpt, PreFlight, Forensic, Pivot, and the rest), GeoAGR, BMAX, RizomUV Bridge, Prune Scene, Pixamoon bitmap and library relink, h_instancer, UVTools, 3Pt Align, Collect Asset, Relink Bitmaps, Vertex Cleaner, Road Markings Generator, UE4 FBX Export (`TS_Tools`), xView Inspector, Copitor. V-Ray and Chaos Cloud buttons are also on that toolbar; the renderer installer in the skipped set is Corona 12, so those V-Ray buttons do not match the installer that was copied.

`Optimised-DefaultEngine.txt` is an Unreal `DefaultEngine.ini` fragment (virtual textures on, tile size 128, border 4). It is a workspace note, not a Max hotkey. `Lumen_Scene_Settings.docx` is an Unreal lighting recipe (directional light 50000 lux, Lumen GI and reflections, software and hardware ray tracing). It is not a Max script and not an NPM/VPM check.

## Third-party plugins

Shallow: name, version, purpose, step. 47 products have at least one `third-party` row. Six more appear only as `covered-by-537` files. Together that is 53 products. Archives were not opened. Skipped dll/dlo/exe rows are name-only.

On the daily menu or hotkeys: Octopus 3.16.0 (the shell itself), SiNi Software 2.0.2, UVTools 3.3.05, RizomUV bridge 1.5.1, rapidTools 1.14, Copitor 3, Prune Scene 3.6.2, Pixamoon (bitmap tracking and relink), BMAX 1.19, Relink Bitmaps 2.17, Collect Asset 2.099b, Road Markings Generator 2.0 (inside ArchViz Tools), xView Inspector, TS Tools 2014-09-11b.

Installed and not on the hotkey file: Chaos Corona 12 (lighting), BerconMaps 3.04 (procedural maps), MultiScatter 1.630 (flora/prop scatter; 1.615 is older), MultiTexture 2.04 (materials), FloorGenerator 2.10 and FloorGen Tools 1.5.1 (paving), Glue (year builds 2009 onward), Quad Cap Pro 1.01, PolyUnwrapper 4.5.0, PolySmoother 2.6.4, Adv.UV Normalizer 2.5.0, XFormer 2.5.9, Project Manager 3.35.75, Smart Merge 2.28, Smart Camera View 3.99, Edge Align (binaries labeled 2024–2027), MaxSU 1.10 (SketchUp bridge), Wall Worm Carver, RayFire 2024, tyFlow, CityTraffic, MadCar, AutoSnap, Populate 0.88/1.86, SplineLand 1.047, GrowFX MultiMap, Siger maps, ThinFilm, Complex Fresnel, clone, Camera Resolution Mod (encrypted), SweepProfile, geometry projection setup, free seamless textures 1.0 and fx_box 1.2 (Photoshop), Quad Remesher 1.3 (Blender), CheckToolBox 1.5 (Blender, covered), xCavity 2.0.1 (covered), Objects Normal Fix 2.4 (covered), imagecomphelper (covered). ArchViz Tools is one download of window, door, cabinet, blind, flame, and road generators; several bodies are encrypted `.mse`. A `plugin copy helper` batch copies that Max 2024 plugin set and was not run.

Resource files are not read one by one. The large groups are: Python venv OpenGL 5770, ArchViz Tools 2401, numpy 1300, pip 819, matplotlib 786, fontTools 675, PIL 211, BerconMaps 100, cv2 91. The rest of the 52 resource purposes are smaller packs of the same kind (icons, samples, language files, Prune Scene signatures).

## Workflow map

The twelve steps are the #537 map. Each step says whether this pass changed it.

1. **Points and references.** Unchanged. `NUM2CIRCLE` and `SelectNumbers` are the same bytes as #537. No new drawing tool.
2. **Ground surface.** Newly informed, rule unchanged. FloorGenerator 2.10, FloorGen Tools, SplineLand, and Populate are installed and are not on a hotkey. The in-house surface tool is still `Ground_Tools`, and the Andrew file is the zip member #537 already read. Pilot Ground remains the layered-cake surface, 10–40 px/m.
3. **MAF and flora.** Newly informed. MultiScatter is the scatter plugin. `h_instancer` is on the toolbar. Flora Atlas V1.2 is the packer, with padding 2 px and an 8192 size in the list. Object randomizer is a jitter helper and is not bound. Pilot: one GroundEl set and one Flora set on NPM; VPM UDIM on one channel.
4. **OKS mesh.** Newly informed. The live hotkeys are stock modifiers plus rapidTools bridge and quad-cap. 3Pt Align and Vertex Cleaner are on the menu. SiNi 2.0.2 is the modelling suite on the toolbar. Pilot: quads in the Max file, triangulate at export, material IDs in the 1–35 scheme.
5. **Collisions (VPM).** Newly informed. The Octopus button `UCX_Concave` selects concave pairs; it is not a new tolerance. `UCX_Tools` / `UCX_Check` Andrew copies are the zip members. `TS_NameUCXPrimitives.ms` writes `UCX_<mesh>_XX` for UE4, which is not the AGR name. Pilot: `ucx_build` plus V010.
6. **UV and atlases.** Newly informed. The UV application in daily use is RizomUV (pack, unfold, weld, texel density) via `HOTKEYS_RIZOM.kbd` and the Max bridge, with UVTools 3.3.05 on the Octopus menu. PolyUnwrapper and Adv.UV Normalizer are installed and not on the hotkey file. `density.ms` displays density as if the map were 4096. Texture Map Generator writes ERM names, not `_d/_r/_m/_n/_o`. The 24-bit 256 converter is the #537 file; `index to rgb.py` writes an 8-bit plug instead.
7. **Names.** Unchanged tool, newly confirmed as daily. The A101LP Octopus button is `A101AGRLP.ms`. Texmapgen's renamer is a second, different pattern and is not that button.
8. **Lights.** Newly informed. Corona 12 is the installer in the skipped set. Corona proxy display is the #537 script. The Lumen doc and `Optimised-DefaultEngine.txt` are Unreal settings, not the Max light FBX. Pilot light rules are unchanged.
9. **Cleanup.** Newly informed. Prune Scene and Relink Bitmaps are on the toolbar. `Optimise_info` moves heavy meshes to a layer before that cleanup. Clear CA/UDP 010 is still the #537 script.
10. **Check in Max.** Newly informed. xView faces and vertices are on Ctrl+Alt+F and Ctrl+Alt+V. xView Inspector and SiNi PreFlight are on the toolbar. `layers_polycount` and `Optimise_info` are listener sweeps and are not bound. `agr_max_check_37.ms` from #537 is not in this folder.
11. **Export.** Newly informed. A101 remains the AGR FBX path and is on the daily menu. `TS_UE4FBXExporter.ms` is a 2014 UE4 exporter, also on the toolbar, and is not the AGR package. Collect Asset gathers a scene and is not a delivery ZIP.
12. **Check the ZIP.** Unchanged. No new archive checker. The A101 error rollout (inside the covered file, and pasted on the A101LP button) checks square power-of-two sizes up to 2048 and warns when the bitmap is not 8 bits per pixel. Pilot ZIP checks stay `src/twinqa`.

## Gap table vs the pilot

Rows without `(new)` are the #537 table, copied forward so this pass has one table. Pilot values are those #537 cited from `standards/NPM_STANDARD.yaml`, `standards/VPM_STANDARD.yaml`, `standards/material_id_ranges.yaml`, `src/twinqa/scene.py`, `src/twinqa/geometry/ucx_audit.py`, `docs/domain/npm-vpm.md`, `docs/domain/areas/ucx.md`, `docs/domain/areas/uv-atlas.md`, and `docs/decisions.md` (D010, D030, D098, D152, D160, D162). `(new)` rows are thresholds read in this pass.

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
| Overlap candidate normal filter 2% dot | `agr_max_check_37.ms:248` | xView about 0.81° (`docs/domain/validation.md`) | differs | script ~11.5°; pilot \|cos\| ≥ 0.9999 |
| Blender overlap 2 mm and 8° | `overlapping_faces.py:170-178` | D152: faces 5 mm, normals 0.81° | differs | script 2.0 mm and 8.0°; pilot 5 mm and 0.81° |
| Improved overlap tolerance 0.002 | `xview_overlapping_faces_improved.py:658` | D152 faces 0.005; verts 0.002 | differs | script default 0.002 for the face test; pilot face test is 0.005 m |
| Material ID = UDIM tile | `UDIM-MultiSub_Universal(max22-26).ms:5` | `material_id_ranges.yaml` groups 1–35; export renumbers to 1001+ | differs | script `1001+floor(U)+10*floor(V)` as the face ID; pilot IDs stay a reading scheme [D030] |
| Ground texel 10–40 px/m, target 35 | `VPM_to_NPM.ms:31-34` | NPM ground density 10–40; D160 | same | band 10–40 px/m |
| Atlas cell padding 6 px | `VPM_to_NPM.ms:35` | NPM `island_padding_px_min` 8 | differs | script 6 px; pilot ≥ 8 px |
| Plug if texture ≤ 512 px | `VPM_to_NPM.ms:12` | NPM 128×128 only for flat metallic/roughness | differs | script ≤ 512 px; pilot 128 px and one-colour MR only |
| UCX triangle budget | `model.py:77-80` | `scene.py` `UCX_SMALL_MODEL` | same | 15_000 under 50_000 else 5% capped at 100_000 |
| UCX outer pad 0.04 and divider 0.035; gap default 5 mm | `UCX_N_29.09.ms` | D098 band 0.002–0.01 m | differs | pads scale with the bbox; emitted gap default 5 mm |
| UCX toolkit gap default 2 mm | `UCX_Tools.ms:1456` | D098 minimum 2 mm | same | 2 mm is the low edge of the band |
| Max protrusion for hull merge 500 mm | `UCX_N_29.09.ms:929` | UCX bands 0.10 / 0.30 / 1.0 m | differs | one spinner at 500 mm |
| UCX max pieces default 12 | `UCX_N_29.09.ms:932` | triangle budget only | missing | pilot has no piece-count cap |
| UCX intersection by AABB | `checks.py:405-418` | `scene.py` SAT | differs | boxes versus surface separation |
| UCX Checker tolerance 0.01 | `UCX_Check.ms:19` | SAT epsilon 0.01 mm | differs | script 0.01 scene units |
| No materials and no UV on UCX | `checks.py:451-463` | R07 | same | forbidden |
| Pivot within 1e-4 m of origin | `model.py:94` | shared-pivot tolerance 0.001 m | differs | script 0.0001 m; pilot 0.001 m |
| Pivot at XY center within 10% of bbox | `model.py:95` | `PIVOT_CENTRE_TOL_PCT = 10` | same | 10% |
| VPM OKS triangles fail above 1_000_000 | `model.py:76` | D010: 150_000 review, 1_000_000 fail | differs | script has no review band |
| NPM triangles 150_000 OKS / 180_000 Ground | `agr_max_check_37.ms:229-230` | `NPM_STANDARD.yaml` | same | 150_000 / 180_000 |
| VPM Ground tiers by area | `model.py:99-102` | `docs/domain/npm-vpm.md` | same | the area table |
| ZIP 500 MiB OKS / 1 GiB Ground and NPM | `agr_zipper.py:149-151` | binary units [D015] | same | 500×1024² and 1024³ |
| VPM PNG 2048 or 4096 | `model.py:88` | `allowed_square_sizes_px` | same | 2048, 4096 |
| Zipper high-poly also allows 256 and alpha 32 bpp | `agr_zipper.py:155` | VPM 2048/4096; NPM alpha forbidden | differs | script 256 and RGBA |
| Lights ≤ 250; omni ≥ 5 m; spot ≥ 1.5 m | `agr_max_check_37.ms:238-240` | lighting rules | same | 250, 5 m, 1.5 m |
| Light index 001–050 per type | `agr_max_check_37.ms:460` | names 001–250 | differs | script max 50 |
| UV channel 1 named `UV` | `agr_max_check_37.ms:42-44` | V008 one UV channel | differs | script also requires the name |
| FBX 7.4 binary, embedded NPM textures, no cameras/lights/animation | `A101AGRLP.ms:1237-1241` | NPM/VPM asset format | same | binary |
| Materials ≤ 7 | `model.py:83` | VPM up to 7 materials | same | 7 |
| UDIM numbers 1001–1100 | `model.py:84-85` | `udim_grid` | same | 1001..1100 |
| MAF TD spinner default 512 | `Maf Tools.mcr:2038` | VPM 512–1706 px/m [D160] | differs | spinner unit is unlabeled |
| Strip CA, UDP, extra map channels | `ClearCustomAttributesAndObjProp_010.ms:5-11` | — | missing | no pilot gate |
| Library ZIP `Name_high` + `Name_low` | `AlexYo_OneByOneExport_Preview_v18.ms:5-8` | — | missing | pilot ZIP is per address |
| (new) Star a layer above 100000 polygons | `layers_polycount.ms:45` | D010 review 150000 triangles, fail 1000000 | differs | polygons per layer, not triangles per file |
| (new) Move meshes with more than 100000 faces, top 20 | `Optimise_info_2.ms:126` | D010 | differs | faces, and 100000 is below the review band |
| (new) List bitmaps with both sides strictly above 4096, top 10 | `Optimise_info_2.ms:125` | VPM sizes 2048 or 4096 | differs | 4096 itself is kept; smaller and non-square maps are not flagged |
| (new) Display texel density as `4096 * sqrt(uvArea/worldArea)` | `density.ms:42` | D160, 512–1706 px/m | differs | assumes a 4096 map |
| (new) Flora atlas default 2048, padding 2 px, list includes 8192 | `Flora Atlas V1.2.mcr:1449-1455` | padding ≥ 8 px; VPM 2048/4096 | differs | 2 px and 8192 |
| (new) 256×256 image saved as an 8-bit palette PNG | `index to rgb.py:242-273` | 24-bit delivery PNG; 128 plug for flat MR only | differs | mode `P`, one flat color |
| (new) UDIM name `T_Address_Type_Slot.UDIM` or with `_Ground_`; types Diffuse, ERM, Normal | `utils.py:463-525` | `T..._d/_r/_m/_n/_o` | differs | ERM replaces separate roughness and metalness |
| (new) Filename letters, digits, hyphen, underscore, dot | `utils.py:196-206` | letters, digits, underscore | differs | hyphen and dot |
| (new) Square 128/256/512/1024/2048; bpp other than 8 is a warning; alpha is an error | `A101AGRLP.ms:1307-1327` | 24-bit; VPM 2048/4096; NPM alpha forbidden | differs | the 8-bit warning contradicts 24-bit; 4096 is absent; the alpha error matches NPM |
| (new) GroundEl bitmap cap argument 512 on `btnGElDiff.filename` | `A101AGRLP.ms:1374` | GroundEl set ≤ 512 px | differs | 512 matches the set cap; the property is not the button the UI writes (`btnGElDiffMap`) |
| (new) Nearly colinear 2-edge vertex if angle > 0.99° | `A101AGRLP.ms:248` | D152 vertex distance 0.002 m | missing | labeled "zero-length"; it is an angle test, and the calls that would run it on export objects are commented out |
| (new) UE4 shell name `UCX_<mesh>_XX` | `TS_NameUCXPrimitives.ms:29` | `UCX_SM_*_{Main\|Ground}_NNN` | differs | two digits, no `SM_` / `Main` token |
| (new) Vertex weight ≤ threshold × 0.01573, threshold default 10 | `ShivaTools_VertexCleaner (2).mcr:19` and `:33` | D152 0.002 m | missing | not a meter distance |

The two A101 rows are in a file marked `covered-by-537`. #537 did not put them in its gap table. They are listed here because the same source is the A101LP button on the daily menu, and the error rollout was read in this pass.

## Recommendations

Drafts only. Nothing was filed. Numbering continues from #537 (R1–R12). This is the second-pass set. Daily tools outrank scripts that are only present on disk.

13. **Title.** Do not port the A101 bitmap ladder or the 8-bit warning.
    **Action.** rule.
    **Why.** A101LP is the daily naming button, and its error rollout accepts squares from 128 through 2048 and warns when a bitmap is not 8 bits. Delivery PNGs are 24-bit. VPM sizes are 2048 and 4096. The alpha error does match the NPM ban and needs no new rule.
    **Draft follow-up issue.** title: Record the A101 bitmap ladder as non-binding. acceptance: a decisions note cites `A101AGRLP.ms:1307-1327`; 8-bit is not a delivery requirement; 4096 stays legal on VPM; the alpha ban is unchanged.

14. **Title.** Ask for GeoAGR before treating the daily menu as complete.
    **Action.** missing input.
    **Why.** The Octopus `myscripts` button and the artsafro toolbar both call `Geoscript` / `GeoAGR`. No file of that name is in the copy or the skipped list, so the purpose is unknown.
    **Draft follow-up issue.** title: Obtain GeoAGR. acceptance: the script file is named and hashed, or the button is recorded as retired; no behaviour is invented from the macro name.

15. **Title.** A texel readout must take the real map size.
    **Action.** port to agent tool.
    **Why.** `density.ms` multiplies by 4096. The pilot band is 512–1706 px/m and the map may be 2048 or 4096. The script is not on a hotkey, but it is the only in-house density display in this folder. Rizom's texel-density keys are the daily UV path and stay commercial.
    **Draft follow-up issue.** title: Compute texel density from the assigned map size. acceptance: a face with a known UV area and a 2048 map reports px/m from 2048, not from 4096; the 512–1706 band is the check; `density.ms` is not copied in.

16. **Title.** Do not adopt the 100000-face sweep.
    **Action.** ignore.
    **Why.** `layers_polycount.ms` and `Optimise_info_2.ms` use 100000 polygons or faces per layer or per object, then rename and move nodes. The pilot budgets are triangles per file, with a review band at 150000 and a fail at 1000000. The scripts are not on the hotkey set.
    **Draft follow-up issue.** title: Do not port Optimise_info. acceptance: closed as won't-do; the audit quotes the 100000 and 4096 calls; no scene-rewriting sweep is added.

17. **Title.** Do not adopt Flora Atlas padding of 2 px or the 8192 size.
    **Action.** rule.
    **Why.** Both Flora macros default the atlas to 2048 and the padding to 2, and the list goes up to 8192. #537 already asked to compare FloraAtlas opacity packing. This pass adds the padding and the extra size, which must not be copied with that packer.
    **Draft follow-up issue.** title: Keep flora atlas padding at 8 px or more. acceptance: the flora packer rejects padding under 8 px and rejects 8192; 2048 and 4096 remain the allowed squares.

18. **Title.** Do not port the 8-bit plug writer.
    **Action.** ignore.
    **Why.** `index to rgb.py` fills a 256×256 image with an 8-bit palette color. The sibling `convert_8bit_to_24bit.py` (#537) does the opposite and is the direction that matches 24-bit delivery. The built `IndextoRgbConverter.exe` was not run.
    **Draft follow-up issue.** title: Do not port index to rgb.py. acceptance: closed as won't-do; 256×256 indexed plugs are not a delivery output.

19. **Title.** Do not adopt Texture Map Generator file names.
    **Action.** ignore.
    **Why.** The tool is a real in-house map builder (version 2.0.0) and it is not on the Max hotkeys. Its names use ERM and allow a hyphen and a dot. Pilot texture names stay `_d/_r/_m/_n/_o` with letters, digits, and underscore. The UDIM wizard button is a stub.
    **Draft follow-up issue.** title: Keep ERM renames out of the pilot. acceptance: closed as won't-do for naming; a later issue can mine the map math only if a job needs an ERM packer.

20. **Title.** Leave h_instancer as a scene helper.
    **Action.** ignore.
    **Why.** It is on the toolbar, so it is used, and it replaces objects with instances. Delivery does not export an instance graph. MultiScatter is the other scatter tool and is commercial.
    **Draft follow-up issue.** title: Do not port h_instancer. acceptance: closed as won't-do; the audit records the toolbar binding.

21. **Title.** Ignore the UE4 UCX namer and exporter.
    **Action.** ignore.
    **Why.** `TS_NameUCXPrimitives.ms` writes two-digit `UCX_<mesh>_XX`. The toolbar also binds the 2014 UE4 FBX exporter. AGR collisions stay `UCX_SM_*_NNN` and the AGR FBX path stays A101.
    **Draft follow-up issue.** title: Do not port TS Tools. acceptance: closed as won't-do; the two-digit pattern is quoted only.

22. **Title.** Keep the daily commercial tools out of the repo.
    **Action.** ignore.
    **Why.** The hotkey and toolbar signal says Artem reaches for RizomUV, UVTools, SiNi, rapidTools, Prune Scene, Octopus, and Copitor every day, and Corona, MultiScatter, FloorGenerator, and BerconMaps are installed beside them. They are products, not rules. #537 R11 already excluded the Telegram third-party archives. This pass adds the ones that are actually bound.
    **Draft follow-up issue.** title: Do not vendor the bound commercial plugins. acceptance: no Rizom, SiNi, UVTools, Corona, MultiScatter, or FloorGenerator binary is committed; the audit is the record of which step uses each one.

23. **Title.** Treat `Hotkeys!.txt` as a draft, and the `.hsx` as the map.
    **Action.** rule.
    **Why.** The note and `hotkeys.docx` still assign Connect, Slice, Spacing, Cap, and Quick Slice to keys that `my_set_2024.hsx` gives to other commands. F8 is assigned twice. Building a pilot hotkey from the note would bind the wrong command.
    **Draft follow-up issue.** title: Record my_set_2024.hsx as the Max keymap. acceptance: the note's extra keys are listed as unbound in the hsx; no pilot keymap is generated from the docx.

## Missing inputs & limitations

- **Drive path.** `_copy_log.json` has `copied`, `bytes`, and `skipped` only. No Drive folder was available to name.
- **Skipped files (7182).** Classified from the name. That includes Corona 12, the Octopus installers, Glue and Quad Cap year binaries, tyFlow, RayFire, MultiScatter and FloorGenerator binaries, Populate, SplineLand, images, pdf, `.max` scenes, `.pyc`, and the built `TextureMapGeneratorV5.exe` / `IndextoRgbConverter.exe`. None of those bytes were read. `TextureMapGeneratorV5.exe` is the same name #537 listed as a large file that was not in the Telegram copy; here it is still only a skipped name.
- **PDFs** in `Hotkeys_Workspaces_Scripts/` (`Basic Optimization Unreal Engine 5.pdf`, GPU note, UE animation guide, UE hotkeys) were excluded by the copy and were not opened.
- **Encrypted `.mse`.** ColorIDAssign, DriverMaster, UVtoMESH, the four stone-placement files, ArchViz generator bodies, RayFire tool scripts, Prune Scene, and Camera Resolution Mod were not decrypted.
- **Not read inside.** Python venv packages, ArchViz sample scenes, Bercon C++ sources, Prune Scene virus signatures, and third-party `.mzp` / `.zip` contents (Quad Remesher, CheckToolBox, Rizom bridge, SweepProfile, Collect Asset, and the rest).
- **GeoAGR** and **LBTools** are bound and absent.
- **`workspace.max`** is a skipped scene file and was not opened.
- **Authors** on 3Pt Align, Quick Attach, Vertex Cleaner, and TS Tools are strings in the files.
- **Not executed.** Nothing was installed, imported into Max or Blender, or run.
- **Andrew zip matches** were confirmed by hashing zip members. The algorithms inside those members are the #537 reading, not a second line-by-line pass.
- **UI files.** `.cuix` and `.mnux` were XML, not zip. Bindings were read from that XML. Stock Max menu items in the large `.mnux` were not listed one by one; the toolbar and the Octopus presets are the daily set.
