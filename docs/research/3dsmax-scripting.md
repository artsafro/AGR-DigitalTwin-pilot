# 3ds Max Scripting & Headless Automation Research

> Research card: `t_3886573a`. Date: 2026-10-15. Evaluates 3ds Max headless CLI automation (`3dsmaxbatch.exe`), Python scripting (`pymxs`), I/O plugins (FBX, OBJ, glTF, USD), geometry manipulation, licensing, and repository integration.
> Evidence base: 26 registered URLs in Sources plus read repository code (research scope estimate: 40-55 min, no native runs).
> Methodology note: Static code reading and documentation analysis only. Distinguishes source-only statements and proposed design from code actually read. No DCC applications, installers, network services, or live mutations were run; runtime behavior is explicitly not tested.

## Summary

- `3dsmaxbatch.exe` provides headless CLI pipeline automation without desktop UI, executing Python or MAXScript tasks and terminating per job[1],[2].
- Python scripting in 3ds Max relies on `pymxs`, exposing the native MAXScript runtime engine strictly on the application's main thread[3],[4].
- Headless I/O is a documented feature candidate for FBX 2014 / 7.4 binary delivery once plugin classes are loaded and parameters pinned per delivery profile[7],[8], but cannot be promised as viable or confirmed FBX 7.4 compatibility without native live testing.
- OBJ is an optional transport format rather than a chosen delivery profile[15][16]; native glTF import is not established by reviewed exporter docs[6].
- USD import/export APIs are documented and illustrated in plugin development tests; installed-build compatibility remains unverified[9][25][26].
- Historical forum discussions state there is no special batch license required for `3dsmaxbatch.exe`, but this is not an authoritative current entitlement or single-machine seat guarantee[20],[21].
- Autodesk Cloud Rights marketing materials reference cloud batch rights in connection with collections, but do not settle local workstation or on-premise network use[18].
- Existing repository script `tools/max_profile_roundtrip.py` demonstrates batch roundtrip concepts from code reading, but production integration requires an external subprocess runner, strict schema validation, and independent verification.

## Findings

### 1. 3ds Max Batch Automation & Python Runtime Architecture

The 3ds Max Python scripting subsystem operates via `pymxs`, which exposes the native MAXScript runtime engine rather than providing an independent C++ SDK binding[4]. High-level orchestration, logging, JSON serialization, and filesystem operations execute in standard CPython 3, while scene graph entities, modifiers, and application commands are manipulated through `pymxs.runtime` (`rt`)[4].

Key runtime mechanics and syntax discrepancies:
- **Indexing Differences:** Wrapped MAXScript arrays accessed via Python use 0-based sequence indexing, whereas API vertex and face index arguments in mesh methods are 1-based[4],[5]. Map channels are not strictly 1-based: channel 0 represents vertex color, channel 1 represents default UV coordinates, and higher numerical channels are possible[5].
- **Symbol Wrapping:** MAXScript name literals require explicit conversion to symbol objects via `rt.Name('symbol')` (e.g., `rt.Name('meters')`, `rt.Name('noPrompt')`, `rt.Name('create')`)[4].
- **Object Equality vs Identity:** The `==` operator tests equality of wrappers referring to the same underlying 3ds Max node, whereas `is` tests Python object identity; distinct wrapper objects can reference the same scene entity[4].
- **Syntax Quirks & String Evaluation:** Reserved language keywords, path names (`$`), and wildcard node lookups require specialized syntax workarounds documented by Autodesk[19]. Calling `rt.execute()` evaluates arbitrary MAXScript expressions[19]; restricting `rt.execute()` strictly to trusted, static expressions and never interpolating untrusted external inputs is our architectural recommendation, not an Autodesk mandate.
- **By-Reference Parameter Passing:** Functions returning values through reference arguments use `pymxs.byref()` to wrap return variables[19] (a mechanism noted in documentation as version-dependent in exact wrapper syntax and behavior across Max releases).
- **Threading Model:** The 3ds Max application core and `pymxs` runtime execute exclusively on the main thread[3]. Background worker threads cannot safely mutate scene nodes, evaluate controllers, or access the MAXScript runtime without risking deadlocks or crashes[3]. Autodesk documentation explicitly deprecates `mxstoken`, leaving older thread-synchronization examples non-functional[3].

Headless CLI execution model:
- `3dsmaxbatch.exe` is a dedicated CLI automation utility, not a persistent daemon server and not merely a command-line renderer[1],[2]. It requires a target script, accepts an optional scene file, initializes the engine without desktop UI, runs the task, and terminates[1].
- CLI Flags documented in[1],[2]:
  - `-sceneFile <path>`: optional scene file to load.
  - `-mxsString <key>:<value>` / `-mxsValue <key>:<value>`: passes CLI string/value arguments accessible inside scripts via `maxOps.mxsCmdLineArgs`.
  - `-log <file>`: 3ds Max system/session log output file.
  - `-listenerlog <file>`: MAXScript Listener output file.
  - `-i <file>`: 3ds Max configuration INI file (not an initialization script).
  - `-p <file>`: plugin configuration INI file (not a cleanup script).
  - `-dm`: dialog monitor switch that watches and closes modal plugin dialogs (defaults OFF; not a generic UI suppressor).
  - `-safescene`: safe scene script execution toggle; `-safescene ON` is our proposed explicit safe choice (the out-of-the-box default is not established in the reviewed documentation).
- Process Isolation & Subprocess Orchestration: Orchestration must occur via an external subprocess (e.g., Python `subprocess.run` managed via `uv run`), passing arguments to `3dsmaxbatch.exe`. Embedded `pymxs` is provided by 3ds Max's internal Python environment and cannot be substituted by an external virtual environment; source[4] focuses on the bundled runtime and does not establish that all pip installations are impossible inside Max Python, but our repository architecture mandates driving execution externally.

Proposed Unexecuted CLI Invocation Candidate (shell and version quoting must be validated, not copy-paste proven):
```cmd
"C:\Program Files\Autodesk\3ds Max 2026\3dsmaxbatch.exe" "C:\abs\tools\max_profile_roundtrip.py" -safescene ON -mxsString config:"\"C:/abs/config.json\"" -log "C:\abs\batch.log" -listenerlog "C:\abs\listener.log"
```

Process exit codes and safety guards:
- Exact batch failure exit codes from[1]:
  - `-100`: missing or invalid arguments.
  - `-110`: Max process cannot start.
  - `-120`: communication cannot be established or maintained with Max.
  - `-130`: Max reported error executing commands.
  - `-8`: license error.
- Documentation states that logged errors cause `3dsmaxbatch.exe` to return a non-zero exit code[1].
- Exit code 0 indicates that the batch runner executed its command sequence without caught errors from the host engine's perspective; however, in our project verification policy, exit code 0 does not prove artifact integrity or delivery QA completeness (this distinction is our project policy, not a claim from documentation that scripts silently fail).
- Modal dialog handling: relying on dialog monitoring (`-dm`) carries the engineering caution that suppressed interactive prompts (such as missing texture warnings or unit mismatches) may alter execution flow unexpectedly; this is an engineering caution rather than a proved failure mode.
- Production pipelines require external watchdog timers, unique job directories, SHA-256 evidence logging, fail-closed handling for missing plugins/XRefs, and single-concurrency execution.

### 2. I/O Interoperability: FBX, OBJ, glTF, and USD

Headless file input and output requires precise plugin class management and parameter pinning to guarantee compliance with delivery specifications:

- **FBX Plugin Loading:** FBX classes must be loaded before parameters can be accessed or modified; calling `pluginManager.loadClass FbxImporter`[7] and `pluginManager.loadClass FbxExporter`[8] is an explicit way to ensure they are available if not already loaded, though it is not always a mandatory initialization step if classes are already resident in memory.
- **FBX Import Execution:** In Python, the scripted import call is `rt.importFile(file_path, rt.Name("noPrompt"), using=rt.FBXIMP)`[7]. The syntax `using:rt.FBXIMP` mixes MAXScript named argument syntax with Python and is invalid in Python. Furthermore, official documentation [7] specifies `#create` for the import mode (`rt.FBXImporterSetParam('Mode', rt.Name('create'))` proposed for symbol compliance), whereas current repository code (`tools/max_profile_roundtrip.py`) passes the raw string `'create'`; whether passing the string `'create'` is accepted interchangeably with the symbol `rt.Name('create')` is an unverified compatibility question requiring native testing, not a fix to be made here.
- **FBX Exporter Parameter Access:** Parameter getters (`FbxExporterGetParam`) and setters (`FbxExporterSetParam`) configure export properties once the exporter is loaded[8].
- **FBX Version Documentation Discrepancy:** The official Autodesk documentation parameter table for `FileVersion` ends at `"FBX201300"`[8], whereas local repository scripts (`tools/max_profile_roundtrip.py`) specify `"FBX201400"`. This mismatch represents an unresolved compatibility gap between documentation and runtime; it is not definitive proof that the documentation page is stale or that the parameter value works as intended without live verification.
- **Profile-Specific FBX Parameter Candidates (Local Delivery Rules):** The requirement for FBX 7.4 (2014) binary delivery and profile-specific export rules comes from local project specifications in `docs/domain/export-import.md`, not from Autodesk documentation[8]. The following snippets represent proposed, unexecuted version-checking candidates for pipeline integration:
  - *NPM Profile Candidate:* `rt.FBXExporterSetParam('EmbedTextures', True)`, `rt.FBXExporterSetParam('ASCII', False)`, `rt.FBXExporterSetParam('FileVersion', 'FBX201400')`, `rt.FBXExporterSetParam('UpAxis', 'Z')`, `rt.FBXExporterSetParam('Cameras', False)`, `rt.FBXExporterSetParam('Lights', False)` (with embedded PNG textures matching internal texture node names per `docs/domain/export-import.md`).
  - *VPM Profile Candidate:* `rt.FBXExporterSetParam('EmbedTextures', False)`, textures stored externally with file paths stripped from material nodes, DirectX normal map orientation (Y-negative), single default layer, lights exported strictly to separate `SM_<Address>_Light.fbx` per `docs/domain/export-import.md`.
- **OBJ Format Interface:** Exporter and importer settings files are retrieved via `objExp.getIniName()`, `objExp.getPresetIniName()`, and `objImp.getIniName()`, queried and updated via `getIniSetting` and `setIniSetting`[15],[16].
- **OBJ Settings State & Profile Role:** Settings paths come from the plugin's `getIniName()`, which is not necessarily `3dsmax.ini`[15],[16]. Modifying these INI files alters shared defaults, requiring state backup or isolated profile management. In our pipeline, OBJ serves as an optional intermediate transport format rather than our chosen delivery profile.
- **glTF Exporter Integration:** The `GLTF_Export` plugin exposes JSON configuration methods (`saveTo3dsmaxINI`, `loadFrom3dsmaxINI`, `toJsonStr`, `fromJsonStr`, `toJsonFile`, `fromJsonFile`)[6]. The presence or status of a native stock glTF importer is unknown and not established by the reviewed exporter documentation[6].
- **USD Interoperability:** Supports `.usda` (ASCII) and `.usdc` (binary) import/export; `.usdz` is export-only[9]. Developer test code in Autodesk's USD repository confirms API usage: `python_export_camera_test.py`[25] tests `CreateOptions` and `ExportFile`, while `import_options_test.ms`[26] tests `USDImporter.CreateOptions` and `ImportFile`. These developer tests reflect active development, not verified compatibility in standard desktop installations.

### 3. Geometry Pipeline & QA Verification

Manipulating meshes and verifying geometry in headless 3ds Max requires navigating low-level mesh data structures:

- **Mesh Construction & Internal Caches:** `Editable_Mesh` and `TriMesh` vertex and face indexing arguments in MAXScript APIs are 1-based[5]. Calling `update <mesh>` refreshes internal mesh caches[5].
- **Texture Vertices & Face Mapping:** Document[5] explicitly warns that passing `tverts` to the mesh constructor alone does not build texture faces; explicit texture face mapping (e.g., via `buildTVFaces`, `setTVFace`) is required to associate texture vertices with mesh geometry[5]. Finite coordinate validation, index bounds checking, and explicit per-corner map topology are recommended.
- **ADN Sample Code Audit:** Code read from the ADN DevTech repository confirms API mechanics. In `mesh_and_cpv.py`[23], vertices, faces, vertex colors, and map channels are configured explicitly before calling `update`. In `poly_object.py`[24], despite its filename, the script constructs a triangular pyramid with vertex colors using `rt.mesh` (there are no smoothing groups in the read source code). Both scripts execute `resetMaxFile #noPrompt`[23],[24], demonstrating destructive scene resets that must never run in an artist's environment.
- **Synthetic Data-to-Mesh Construction Candidate (Unexecuted):** Minimal conceptual demonstration based on documentation[5] and ADN samples[24] showing low-level `TriMesh` construction without destructive `resetMaxFile`:
  ```python
  # SYNTHETIC UNEXECUTED EXAMPLE (Static design candidate, not verified in live DCC)
  import pymxs
  rt = pymxs.runtime

  # Vertices supplied as rt.Point3 objects [5],[24]
  vertices = [rt.Point3(0.0, 0.0, 0.0), rt.Point3(1.0, 0.0, 0.0), rt.Point3(0.0, 1.0, 0.0)]
  # Faces supplied as rt.Point3(1, 2, 3) (1-based indices) [5]
  faces = [rt.Point3(1, 2, 3)]

  # Construct mesh and refresh internal caches without resetMaxFile
  mesh = rt.mesh(vertices=vertices, faces=faces)
  rt.update(mesh)
  ```
  *Note:* In production delivery pipelines, calling `rt.mesh(vertices=..., faces=...)` alone does not produce a delivery-ready asset; explicit separate corner UV/map faces (`setTVFace` / `buildTVFaces`) and face material IDs (`setFaceMatID`) are required before delivery. Furthermore, building quad master models must remain strictly separate from triangular export copies per project domain rules.
- **xView Automated Inspection:** Documentation for `IsolatedVertices.Check` does not require the checker to be active in an interactive viewport[22], but its headless runtime behavior remains unverified. The returned enumeration value indicates the kind of result elements returned (e.g., vertices, edges, or faces), not a boolean clean/pass status[22]. xView functions as an element query tool and does not replace comprehensive delivery verification.
- **QA Verification Matrix & Local Standards:** QA thresholds and inspection criteria derive from local standards (`docs/domain/validation.md` and `docs/domain/conflicts.md`) rather than universal defaults:
  - *Units & Scale:* System units set to meters (`rt.units.SystemType = rt.Name('meters')`).
  - *Transforms:* Transform validation must not require identity full world matrices, since valid object placement has translations. In accordance with local profile rules (not a new decision), check rotation and scale separately from profile pivot and world placement, verify source dimensions, and evaluate the matrix determinant and reflection flags to ensure correct surface normals without inverted winding.
  - *Topology:* Profile-dependent tolerances (per `docs/domain/validation.md`) for detecting non-manifold geometry, zero-area triangles, duplicate vertices, and coplanar overlaps (not a universal 2 mm threshold across all geometry). Finite coordinate validation and index bounds checking recommended.
  - *Boundaries:* Classification of intentional open edges (facade perimeters) without automated destructive welding.
  - *UV & Materials:* Explicit per-corner map topology on map channel 1, UV coordinate bounds, profile atlas and UV layout per `docs/domain/uv-textures.md` (e.g., VPM sequential UDIM 1001..1100 grid vs. NPM embedded atlas regions and allowed texture sizes), absence of mirrored islands where forbidden, and correct Material IDs.
  - *Readback:* Full re-import of exported FBX in a clean process to verify raw geometry, transforms, and texture bindings.

### 4. Licensing, Cloud Deployment & Legal Entitlements

Headless pipeline operations have distinct legal and commercial licensing boundaries:

- **Batch Licensing Clarification:** A 2020 Autodesk community forum reply[21] only states that there is no special batch license required for running `3dsmaxbatch.exe`; it does not confirm that additional seats or licenses are never required.
- **Multi-Node & Farm Ambiguity:** A 2021 community discussion[20] reports no observed license consumption during tests and notes Autodesk staff uncertainty, but leaves an automated 10-machine farm deployment query without a definitive answer. Historical forum posts cannot be converted into legal entitlement.
- **Current Legal Entitlement Requirements:** Current local scene processing, named-user / network / Flex licensing models, virtual machine or cloud CI runners, process concurrency, and rendering/plugin licensing all require current, written clarification from Autodesk or an authorized reseller.
- **Cloud Rights & Marketing Boundaries:** Autodesk marketing materials reference cloud batch rights (running on remote VMs or cloud infrastructure) in connection with the Media & Entertainment (M&E) Collection[18], but marketing text does not settle local workstation or on-premise network use.
- **Cloud Deployment Caveat:** Autodesk cloud deployment documentation mentions deleting `atf_converter` and `IwATFExport.dle` when configuring cloud batch images[17]. This caveat is recorded strictly for reference from official documentation and was never performed.

### 5. Platform Ecosystem & Community Evidence

Community scripts, repositories, and learning resources provide context on real-world automation practices:

- **ADN HowTos:** MIT-licensed practical examples provided by Autodesk Developer Network[10]; README read, examined as passive code samples without installing packages.
- **ScriptSpot Community Tools:** The ScriptSpot portal page description for Jos Balcaen's "Batch Export/Import" script[14] advertises optional features such as box-method reset transforms, moving geometry to origin, deleting TurboSmooth modifiers, and optional rotations. These are advertised options on the page description, not proven defaults or source-audited behaviors; our review read the web page and visible launcher excerpt only and did not download or audit the full script package. CGSociety was not separately verified as ScriptSpot covers the requested community tool alternative.
- **Developer Forums:** Reddit community threads[11],[12] show recurring user queries regarding command-line automation comparable to `mayapy` or `hython`, pointing to `3dsmaxbatch.exe`. For evidence gathering, main posts were read via extraction, while Reddit JSON fallback returned HTML so comments were not recovered and were accessible via search snippets only; this represents an explicit evidence gap for thread discussions.
- **Educational Video Material:** The tutorial video titled `Scripting for Artists in 3ds Max 2020+ | Python 3ds Max #1` (YouTube `EiMNwO4buOQ`)[13] was examined via a retrieved transcript excerpt covering the introductory 0–95 seconds (not a full transcript read). The presenter describes older tutorials as relevant only through 3ds Max 2020, positioning the video as a beginner introduction to Python in 3ds Max. It serves as introductory educational material, not proof of headless production automation.

| Source Category | Ledger IDs | Verification Type | Reliability / Confidence |
|---|---|---|---|
| Official Autodesk Documentation | [1],[2],[3],[4],[5],[6],[8],[9],[15],[16],[17],[19],[22] | Web extraction / documentation read | High (primary source, though doc gaps exist in FBX table) |
| Official Documentation Fallback | [7] | Curl fallback read | High (primary source for FBX import parameters) |
| Marketing Material | [18] | Marketing page read | Contextual (marketing material, not a technical developer doc) |
| Official Autodesk Developer Code | [10] (README), [23],[24],[25],[26] (code) | Source code read via GitHub API | High (actual code; runtime execution unverified) |
| Autodesk Community & Support Forums | [20],[21] | Forum threads read via curl / web extraction | Medium (vendor staff statements; unresolved multi-seat policy) |
| Community Scripts & Portals | [14] | Portal description and launcher excerpt read | Medium-Low (advertised features; full script not downloaded; CGSociety not verified) |
| Social & Video Ecosystem | [11],[12] (main posts via extraction, comments via snippets only), [13] (transcript excerpt 0-95s) | Main posts via extraction, comments via snippets only, partial transcript read | Contextual (confirms user workflows; not CI evidence) |

## How It Applies to This Repository

Integrating headless 3ds Max automation into the AGR-DigitalTwin codebase connects directly to existing tools and pending adapters:

- **`adapters/max/README.md` vs `tools/max_profile_roundtrip.py`:** While `adapters/max/README.md` states that the 3ds Max adapter is unimplemented, `tools/max_profile_roundtrip.py` exists in the repository as a candidate roundtrip script identified through code reading, not a functionally or runtime-verified implementation. It incorporates structural safety checks:
  - Checking empty initial state (`len(rt.objects) == 0` and empty `maxFileName`).
  - Requiring an absolute JSON configuration path.
  - Computing and recording input file SHA-256 hash (note: it computes and records the hash, but does not verify it against a pre-existing expected hash).
  - Enforcing fresh output paths to prevent accidental overwriting (`FileExistsError`).
  - Setting system units to meters (`rt.units.SystemType = rt.Name('meters')`).
  - Importing FBX, saving scene (`max-import.max`), and exporting roundtrip FBX (`max-roundtrip.fbx`).
  - Setting `operation_completed` conditionally derived from the failures list (`evidence['operation_completed'] = not evidence['failures']`, evaluating to `True` only when `failures` is empty) while explicitly leaving `delivery_passed = False` (it does not reimport its own output, and records only shallow vertex/triangle counts and material names rather than executing a general QA audit contract).
- **Architectural Gaps in `tools/max_profile_roundtrip.py`:**
  - Lacks explicit `pluginManager.loadClass` calls.
  - Does not read back or verify parameter values via `FbxExporterGetParam`.
  - Hardcodes `EmbedTextures = True`, conflicting with VPM delivery rules requiring external textures and stripped texture paths.
  - Lacks internal topological defect checks and does not perform its own reimport or cross-DCC audit.
- **Cross-DCC Checking Scripts in Repository:** Despite their filenames, `tools/export_facades_max.py` and `tools/check_facades_max_roundtrip.py` are Blender Python scripts (`import bpy`).
  - `tools/export_facades_max.py` strips extraneous UV layers, renames meshes, and exports FBX from Blender with `-Y` forward and `Z` up.
  - `tools/check_facades_max_roundtrip.py` imports Max's exported FBX into Blender and uses `mathutils.kdtree.KDTree` to compare corner positions with a candidate search radius of 0.002 (2 mm) and UV tolerance `max 2e-6` against Blender references. While a useful cross-DCC comparator candidate, it does not prove formal positional certification or full QA validation.
- **External Legacy MAXScript Tools (`docs/tools/max-scripts.md` Attribution):** The inventory of external tools documented in `docs/tools/max-scripts.md` reveals major regulatory non-compliance hazards:
  - `FloraAtlas.ms`: Saves diffuse as RGBA (forbidden in NPM), uses 2 px padding (norm >= 8 px), and leaves hidden backup objects.
  - `Ground_Tools.ms`: Forces meshes to Editable Poly (note: deleting DWG numeric text is performed by `NUM2CIRCLE.lsp`, not `Ground_Tools.ms`).
  - `Texture_Zaglushki_Ground.ms`: Hardcodes 256 px placeholders for all profiles, whereas NPM requires 128 px placeholders[D013].
  - `Maf Tools.mcr`: Calculates UDIM as 1000 + MatID, directly violating the project rule that MatID must not dictate UDIM tiles.
  - `UCX_Tools.ms` & `UCX_Check.ms`: Produce non-standard collision names, fail to enforce the regulation triangle budget, and miss nested collision volumes.
  - `A101AGRLP.ms`: Drops leading zeros in 4-digit codes (0313 -> 313) and destructively resets working objects.
- **Capability Status (`docs/agents/CAPABILITIES.md`):** `3dsmax-mcp` is recorded as CONFIGURED (historical ledger status only, not verified WORKING). Max 2024 and 2026 are recorded on the host machine, but no live host probing was performed during this research.
- **Benchmark K02:** Remains blocked in `docs/PROJECT_STATE.md` awaiting the user's `source.max` and `etalon.max` test assets.
- **Project Domain Constraints:** All Max operations must align with core project rules (`docs/domain/export-import.md`, `docs/domain/validation.md`, `docs/domain/conflicts.md`): operations must execute solely on managed export copies, quad master models must remain intact while producing separate triangulated delivery copies, system units must be meters, texture rules must strictly distinguish NPM (embedded) from VPM (external, paths stripped), and manual gates must remain `review`/`not_run`.

## Proposed Next Tasks (Recommendations)

The following tasks are proposals and architectural recommendations, not mandated project implementations:

1. **Written Entitlement Verification & Host Version Inventory**  
   Obtain formal written entitlement confirmation from Autodesk or authorized reseller prior to live execution, as no license-status probe can replace legal authorization. Once verified, run a lightweight external script to inventory installed 3ds Max versions (`3dsmaxbatch.exe` paths for 2024 and 2026) and execute a sandbox smoke script returning JSON evidence without modifying project data.  
   *Value: L · Effort: S*

2. **Formal Headless Max Runner Subprocess & Schema Contract**  
   Develop a production runner in `adapters/max/` implementing the adapter contract from `adapters/README.md`. Includes strict request/result JSON schemas, timeout watchdogs, exit code mapping, SHA-256 evidence logging, and negative test coverage for missing files and syntax errors.  
   *Value: L · Effort: M*

3. **Profile-Aware FBX Exporter & Multi-DCC Readback Bridge**  
   Upgrade `tools/max_profile_roundtrip.py` into a robust FBX exporter that dynamically handles NPM (embedded textures) and VPM (external textures, stripped paths, DirectX normal map orientation). Connect output verification to `tools/check_facades_max_roundtrip.py` and `twinqa` for independent post-export validation.  
   *Value: L · Effort: M*

4. **Dedicated Self-Hosted CI Runner Architecture (Design Recommendation)**  
   Design recommendation for CI execution architecture based on a dedicated authorized self-hosted Windows runner for native 3ds Max execution; standard CI runs pure logic only (linters, unit tests, schema validators). The native Max suite must be strictly opt-in and serialized (single-concurrency), with strict gates on file permissions, scene input, and output ownership, and retention of execution, system, and listener logs. (Note: no native CI has been executed; this is a proposed architecture).  
   *Value: M · Effort: M*

5. **Synthetic Data Mesh Fixture Suite for Max Pipeline**  
   Create synthetic mesh fixtures with complex UV seams, multi-material IDs, and intentional boundaries to validate Max's headless geometry generation, normal handling, and quad-to-triangle export conversions without relying on proprietary customer data.  
   *Value: M · Effort: M*

6. **Secondary Format Evaluation Matrix (OBJ Transport, glTF, USD)**  
   Develop isolated test modules for secondary interchange formats: assess OBJ as an unrigged geometry bridge with INI isolation, test `GLTF_Export` JSON configuration routines, and evaluate USD export compatibility for Unreal Engine staging.  
   *Value: S · Effort: L*

## Open Questions for the User

1. **Target 3ds Max Version & Plugin Pins:** Which specific 3ds Max version (2024 vs 2026) and specific plugin releases (FBX exporter/importer, USD, glTF) should be pinned as official pipeline standards?
2. **Authorized Run & Export Directories:** What specific local filesystem directories and ownership permissions are authorized for headless execution scratch files, temporary log outputs, and exported delivery artifacts?
3. **Batch Licensing Scope:** Has written vendor confirmation been obtained for headless batch runs on this workstation or network nodes, or is execution strictly confined to single-process runs on the primary workstation?
4. **Pipeline Architectural Role:** Should 3ds Max serve primarily as an intake and export/inspection station (with core procedural generation handled by Python/Blender), or should native Max modeling tools be automated via `pymxs`?
5. **Benchmark K02 Baseline Assets:** When will `source.max` and `etalon.max` be available to establish the formal K02 baseline?
6. **Secondary Interchange Priorities:** Beyond the mandatory FBX 7.4 binary delivery format, what priority should be assigned to secondary formats (OBJ transport, glTF, USD)?


## Sources

[1] https://help.autodesk.com/cloudhelp/2023/ENU/3DSMax-Batch/files/GUID-48A78515-C24B-4E46-AC5F-884FBCF40D59.htm
[2] https://help.autodesk.com/cloudhelp/2022/ENU/3DSMax-Batch/files/GUID-0968FF0A-5ADD-454D-B8F6-1983E76A4AF9.htm
[3] https://help.autodesk.com/cloudhelp/2026/ENU/MAXDEV-Python/files/MAXDEV_Python_threading_html.html
[4] https://help.autodesk.com/cloudhelp/2026/ENU/MAXDEV-Python/files/MAXDEV_Python_using_pymxs_html.html
[5] https://help.autodesk.com/cloudhelp/2026/ENU/MAXScript-Help/files/3ds-Max-Objects-and-Interfaces/Editable-Meshes-Splines-Patches/Editable_Mesh-and-TriMesh/GUID-0532C071-4401-4846-8450-3DA5510A3883.html
[6] https://help.autodesk.com/cloudhelp/2026/ENU/MAXScript-Help/files/3ds-Max-Objects-and-Interfaces/Import-and-Export-Filters/GUID-47D7B030-1DB8-47E8-B462-C800D26480DA.html
[7] https://help.autodesk.com/cloudhelp/2026/ENU/MAXScript-Help/files/MAXScript-Tools-and-Interaction/Interacting-with-the-3ds-Max/FBX-Import-and-Export-Dialog/GUID-77CE3E5A-7AB1-4048-BD80-B127E0231FFA.html
[8] https://help.autodesk.com/cloudhelp/2026/ENU/MAXScript-Help/files/MAXScript-Tools-and-Interaction/Interacting-with-the-3ds-Max/FBX-Import-and-Export-Dialog/GUID-54B1F140-B304-48A2-9829-C68B345E2044.html
[9] https://help.autodesk.com/cloudhelp/2026/ENU/3dsMax-USD/files/USD-for-3ds-Max/GUID-F10D6301-D66C-48CE-8D33-65E482734A84.html
[10] https://github.com/ADN-DevTech/3dsMax-Python-HowTos
[11] https://www.reddit.com/r/3dsmax/comments/1df16z1/resources_for_learning_scripting_in_3ds_max
[12] https://www.reddit.com/r/3dsmax/comments/wy85tj/using_3ds_max_as_command_line_tool
[13] https://www.youtube.com/watch?v=EiMNwO4buOQ
[14] https://scriptspot.com/3ds-max/scripts/batch-exportimport
[15] https://help.autodesk.com/cloudhelp/2026/ENU/MAXScript-Help/files/3ds-Max-Objects-and-Interfaces/Import-and-Export-Filters/GUID-4BAF2F8E-4EAC-4276-A9A7-FF80EE597A45.html
[16] https://help.autodesk.com/cloudhelp/2026/ENU/MAXScript-Help/files/3ds-Max-Objects-and-Interfaces/Import-and-Export-Filters/GUID-639CF6E0-1B9F-4B05-9CE8-D6418162E0CE.html
[17] https://help.autodesk.com/cloudhelp/2026/ENU/3DSMax-Batch/files/GUID-820A51F0-FFE6-4ACC-B3C6-18D7EFA32FA7.htm
[18] https://www.autodesk.com/solutions/batch-rendering
[19] https://help.autodesk.com/cloudhelp/2026/ENU/MAXDEV-Python/files/using_pymxs/MAXDEV_Python_using_pymxs_pymxs_differences_html.html
[20] https://forums.autodesk.com/t5/3ds-max-forum/max-batch-licence/td-p/10334463
[21] https://forums.autodesk.com/t5/3ds-max-forum/regarding-3dsmaxbatch/td-p/9712391
[22] https://help.autodesk.com/cloudhelp/2025/ENU/MAXScript-Help/files/3ds-Max-Objects-and-Interfaces/Interfaces/Core-Interfaces/Core-Interfaces-Documentation/I-J-K/GUID-F5BEE9F6-6668-4D77-942E-DA844A88D496.html
[23] https://github.com/ADN-DevTech/3dsMax-Python-HowTos/blob/master/src/samples/pymxs/mesh_and_cpv.py
[24] https://github.com/ADN-DevTech/3dsMax-Python-HowTos/blob/master/src/samples/pymxs/poly_object.py
[25] https://github.com/Autodesk/3dsmax-usd/blob/dev/src/Tests/Integration/python_export_camera_test.py
[26] https://github.com/Autodesk/3dsmax-usd/blob/dev/src/Tests/Integration/import_options_test.ms
