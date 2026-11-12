# Substance finishes feasibility — issue #1258

## Status: capability report complete; finish pilots not verified [D259]

**Final scope, 2026-11-12:** Artem accepted closing this research with the
capability report and existing evidence, with **no more runtime attempts** [D259]
(Kanban t_ab5c23eb, USER DECISION 11:40, «принимаю рекомендацию»). This supersedes
[D260]'s remaining photo-to-tileable requirement and all historical unblock notes
below. No installation, licensing or production integration is authorised here.

Sampler 4.5 scripting is **not usable for the requested autonomous finish workflow
on this PC**: Brickwall and Make It Tile filter insertion crashes with 0xC0000005,
including script-thread and UI-callback routes. Basic API enumeration, image import
and one raw AI export worked; this is not a claim that all scripting fails.
Designer/SAT were not found in the inspected inventory; procedural `.sbsar` output
is **not verified**. No finished tileable Diffuse/ERM/Normal set, approved replacement
texture, measured complete-finish time or procedural benchmark is claimed.

### Final acceptance disposition

| Original acceptance | Final disposition under [D259] | Evidence |
|---|---|---|
| Installed inventory and exact agent commands | Delivered, with inspected-location limits | Inventory and command sections below; capability-v001 |
| Photo-to-tileable and procedural pilots | Not delivered; explicitly replaced by capability-only closure | Native crash checkpoints; Designer/SAT unavailable; six raw AI maps are diagnostic only |
| Same-finish side-by-side and time per finish | Partial diagnostic sheet delivered; finish quality/time not measured, no completion claim | photo-v002 partial-comparison.png; 77.67 s raw export, not a completed finish |
| Integration recommendation and follow-up proposals | Delivered as proposals, not production adoption or newly created issues | Recommendation below; resume only after a changed Substance installation |

Evidence re-read at finalisation: **41/41** manifest entries matched SHA-256;
no Adobe process was launched. Immutable evidence seals:

| Drive folder under `G:/Мой диск/AGR-evidence/1258/` | Entries verified | SHA-256 of `SHA256SUMS.txt` |
|---|---|---|
| `substance-capability-v001/` | 13/13 | `99ff80fefd378244b523842232fb4a6bdb3de5a15b2c5d41e89d1517b108ce6a` |
| `substance-photo-v002/` | 28/28 | `8746a6c4b034e03c8b587c1b469d3bc4fee58fceb4270079d2027f8184d1e812` |

The investigation is complete within the final approved scope; texture-production
readiness and user visual acceptance are not established. Historical sections below
preserve the sequence and failed results rather than relabelling them successful.

## Initial investigation (historical)

The following records the first run, before scope was narrowed:

Research date: 2026-11-12. Base inspected: `origin/main` at `f1fbe9a4`.
This is a partial capability investigation, **not** a completed finish benchmark.
No production pipeline, source scene, approved texture, installation, licence or
preferences were intentionally modified. No live Max or Blender calls were made.
No maps, comparison sheet, finish-time measurements or visual approval are claimed.

## Installed inventory and observed execution

Inventory sources: Windows uninstall registry (HKLM native/WOW6432Node and HKCU),
`C:/Program Files/Adobe`, PATH lookup, and the installed Sampler documentation.

| Tool | Evidence | Agent execution verdict |
|---|---|---|
| Sampler | Registry: 4.5.0; `C:/Program Files/Adobe/Adobe Substance 3D Sampler/Adobe Substance 3D Sampler.exe` | `--run-script-silent <absolute-script.py>` executes Python and exits; read-only enumeration returned exit 0 in 3.23 s. Not proof of a display-independent render service. |
| Sampler Python API | `Resources/pythonapi-doc/html`, `Resources/python`, `Resources/pythonsdk`; embedded `import substance_sampler` succeeded | Project and asset creation, filter discovery and image import were exercised; filter insertion crashes natively (below). This API is hosted by Sampler, not an independently verified Python renderer. |
| Painter | Registry: 10.0.0; `C:/Program Files/Adobe/Adobe Substance 3D Painter/Adobe Substance 3D Painter.exe` | Not launched; no headless claim. |
| Substance for Max | Registry: 2024 plugin 2.7.0; 2026 plugin 3.0.5 | Not exercised: live Max is out of scope. Presence does not prove a standalone renderer. |
| Designer | No matching registry entry or Adobe installation folder found | No executable available in inspected locations; no Designer graph pilot performed. |
| Automation Toolkit / `pysbs` | No matching registry entry or Adobe installation folder found | Not available in inspected locations. Do not infer a licensed SAT installation from Sampler's embedded engine DLLs. |
| `sbsrender`, `sbscooker`, `sbsbaker` | `shutil.which` returned `None` for all three; no matching executables in the recursive Adobe Substance installation inventory | Not runnable by these commands in this environment. |

A broader recursive Program Files search timed out at 90 s: it is **not** evidence
that no toolkit exists anywhere on disk. No installer was downloaded or run.
Sampler ships `Resources/assets/StarterAssets/Brickwall Pattern.sbsar`; a bundled
archive alone is not a tested procedural finish or an authorised replacement for Designer/SAT.

### Exact commands and local primary references

Run from this card's worktree. Probe scripts and logs are preserved in the evidence
folder below; `tmp/` is ignored, not a shared production tool.

```bash
"C:/Program Files/Adobe/Adobe Substance 3D Sampler/Adobe Substance 3D Sampler.exe" --run-script-silent "C:/Users/artsafro/agr-pilot/AGR-DigitalTwin/.worktrees/t_ab5c23eb/tmp/substance-probe/probe.py"
"C:/Program Files/Adobe/Adobe Substance 3D Sampler/Adobe Substance 3D Sampler.exe" --run-script-silent "C:/Users/artsafro/agr-pilot/AGR-DigitalTwin/.worktrees/t_ab5c23eb/tmp/substance-probe/inspect.py"
"C:/Program Files/Adobe/Adobe Substance 3D Sampler/Adobe Substance 3D Sampler.exe" --run-script-silent "C:/Users/artsafro/agr-pilot/AGR-DigitalTwin/.worktrees/t_ab5c23eb/tmp/substance-probe/attempt2.py"
"C:/Program Files/Adobe/Adobe Substance 3D Sampler/Adobe Substance 3D Sampler.exe" --run-script-silent "C:/Users/artsafro/agr-pilot/AGR-DigitalTwin/.worktrees/t_ab5c23eb/tmp/substance-probe/attempt3.py"
```

Commands were invoked with Python `subprocess` to capture the real native exit code
and bound execution time; the wrapper's own exit 0 does **not** mean Sampler passed.
`attempt2.py` was subsequently changed to a selected-asset probe: its current file
reproduces `attempt4.log`, not the original `attempt2.log`. The original attempt's
changes are documented in the table below, rather than claiming byte-identical provenance.

Primary API references, relative to Sampler's `Resources/pythonapi-doc/html/_generate/`:
`substance_sampler.Asset.html` (`import_images`, `insert_filter`, `export_material`),
`substance_sampler.create_project.html`, `substance_sampler.create_asset.html`,
`substance_sampler.run_in_main_thread.html`, `substance_sampler.Parameter.html`,
`substance_sampler.Metadata.html`, `substance_sampler.wait_for_computation.html`.
The latter documents a `None` return; it is not a boolean pass receipt.

## Runtime failures and bounded repair attempts

| Probe | Different approach | Observed result |
|---|---|---|
| Read-only | Enumerate API, filters and materials without a project | Exit 0; `probe-result.json`: `api_available`. |
| Initial stack | Create project with new path, create asset, insert Brickwall | Native exit **3221225477 (0xC0000005)**; no result JSON. Last checkpoint unavailable; do not attribute an exact failing call. `inspect.log`. |
| Repair 1 | Pre-create output directory; execute work through `run_in_main_thread`; add durable checkpoints | Project and asset creation succeeded; last checkpoint `filters_discovered`; crash on `asset.insert_filter(Brickwall, 0)`, exit **3221225477**. `attempt2.log`. |
| Repair 2 / alternate route | Selected asset; import a copied OBR22 atlas via `image_to_material_AI_powered`, no Brickwall filter | Exit **0**; checkpoint `computed`, `wait_status: "None"`. No exported maps; only an import capability probe, not a tileable-finish pilot. `attempt3.log`. |
| Repair 3 | Apply selected-asset finding to the procedural route, still on main thread and existing directory | Again last checkpoint `filters_discovered`, native exit **3221225477** inserting Brickwall. `attempt4.log`. |

No further crash retries or machine-wide repairs were attempted. Replacing Adobe
native engine binaries, installing software or changing GPU drivers/licensing is not
an in-worktree repair. The image-import success must not conceal the failing procedural route.

## Real OBR22 source located, not yet a valid sample pilot

Read-only source located outside the pilot checkout:
`C:/Users/artsafro/AGR-DigitalTwin/jobs/OBR22-K02/outputs/textured_v010/`.
Its `texture-recipe.json` states: brick face 250 x 65 mm, joint 10 mm,
half running bond, Diffuse only, PDF-derived candidate colours, no measured PBR maps.
The atlas used solely for the import capability probe was
`VPM_UDIM_Diffuse.1004.png`, 105656 bytes, SHA-256:
`a352621d66bcdeee46c9d8c6cef1b39d1034c9941d18dd3993253593754b6c17`.
Only a copy was passed to Sampler.

Visual inspection shows a mixed atlas with brick, grey/light tiles and unused
regions. It is **not** a pure tileable brick sample. The probe's `(4,4,0.01)`
physical-size argument was an API exercise, not measured source calibration.
Do not reuse it as a physical-scale receipt. The proposed library material 17
(`library/materials/materials_v002.json`) refers to RAL 8023 and a 250 x 65 mm brick,
but its sRGB `[166,94,46]` is explicitly a screen approximation, not measured RAL.
Library generation also documents a 257.14 mm horizontal pitch rather than the
260 mm OBR22 reference: do not silently substitute that set as an exact etalon.

## Proposed integration and remaining measurements

Keep Substance upstream of the finish library. Keep UDIM layout and delivery
packing in our pipeline; do not replace geometry/UV operations for this research.

- Sample route: isolate a calibrated brick-only crop from the existing job texture
  (or use a real supplied photograph), record its metre extent and hash, import,
  make tileable, then export and inspect the files. Generated source textures must
  remain labelled generated, never described as photographs.
- Procedural route: use a working Designer/SAT graph or a validated Sampler `.sbsar`
  route; expose bond, joint width, colour and wear. Store face/joint dimensions in
  metres, explicit seed, graph hash and parameter values. A graph parameter is not
  a measured material property.
- Catalogue mapping: material 17 / brick / RAL 8023 is a candidate binding, not a new
  catalogue decision. Preserve the RAL code separately from preview sRGB; compare
  with the same job's approved palette before accepting colour.
- Delivery: `T_{Address}_{TypeTexture}_{SlotNumber}.{UDIM}.png`, roles Diffuse/ERM/Normal;
  ERM = emissive/roughness/metallic, **not ORM**; DirectX normal; 8 bit/channel.
  Sampler export precision and normal orientation still need actual readback.
- Density: D097 with D160's corrected 512–1706 px/m; use a measured physical extent,
  not an invented square size or automatic import metadata.
- Measure elapsed processing and preparation time separately for each finish;
  record seam metrics, pitch, joint-width pixels, colour deviation and identical-view
  side-by-side sheets. Quality and speed relative to the current maps are **not measured**.

Follow-up proposals (not created as issues, and not substitutes for this card's acceptance):
1. After the two pilots: reviewed finish-library recipe/manifest and explicit RAL binding.
2. After the two pilots: graph variant batch benchmark with stable seed and physical-scale checks.
3. If the native failure persists in a supported setup: standalone minimal Adobe crash reproduction.

## Evidence and handoff

Partial runtime evidence: `G:/Мой диск/AGR-evidence/1258/substance-capability-v001/`,
with `SHA256SUMS.txt`. No customer atlas, scene or renders are committed to git.
The preserved files are discovery scripts, JSON checkpoints, logs and the source
recipe; no sheet or map output exists. `uv sync` succeeded. No new production code,
regression fix, full-suite receipt or completed acceptance is claimed.

The original procedural blocker is superseded by [D260]: no procedural pilot or
installation is required now. The narrowed photo-to-tileable acceptance is still
open for the separate Make It Tile native crash below.

## Continuation: real photo-route export and tile-filter blocker [D260]

### Calibrated existing job texture

A brick-only source was found read-only, better than the initial mixed v010 atlas:
`C:/Users/artsafro/AGR-DigitalTwin/jobs/OBR22-K02/outputs/shared_v011/VPM_Diffuse.1004.png`.
It is an existing job texture, **not asserted to be a facade photograph**. The
manifest refers to `Desktop/!3D viz/Alex_World/bricks.png`; original capture or
generation provenance was not independently verified.

- Source: 4096-square RGB8, SHA-256
  `cee95e4aa386e27c065e2f1df8a228a130830bd188e3db353ed7dd05650396ac`.
- `shared-uv-manifest.json`: finish **5**, full-tile region, **1024 px/m** for its
  VPM entries; therefore the full map covers **4 x 4 m**. Manifest SHA-256:
  `9a8efb81ec7358fb7cd8e83f20a2c4ad280b5e6a7af8b976e6b8d7e3ef50fec0`.
- Recipe: brick face 250 x 65 mm, joint 10 mm, half running bond. These are job
  reference dimensions, not independent photo measurements.
- Successful raw AI export: 2048-square over 4 x 4 m = **512 px/m**, exactly the
  D160-corrected D097 lower bound. The API's 0.01 m depth was experimental metadata,
  not measured relief amplitude.
- Tile-filter input: crop `(0,0,2130,2150)` / 1024 px/m =
  **2.080078125 x 2.099609375 m**, approximately eight pitches by 28 courses;
  not asserted pixel-perfect periodic. No tile-filter outputs exist.

### Execution and distinct repairs

| Experiment | Approach | Actual result |
|---|---|---|
| `photo_export_v001.py` | Entire import/wait/export in UI callback | Native 3221225477 (0xC0000005), 7.72 s; checkpoint `export_returned`, zero maps. A returned folder path is not completion. |
| `photo_export_v002.py` | Controller/export outside asynchronously dispatched UI callback | Native exit 0, 5.46 s, caught `IndexError: list index out of range`; zero maps. Callback had not populated assets before access. |
| `photo_export_v003.py` | Direct script-thread calls, `wait_for_computation`, explicit `ExportController.wait_for(120000)` | Native exit 0, **77.6666 s** wall / **73.5798 s** in-script; `WaitStatus.no_timeout`; six PNG files read back. |
| `photo_tile_v001.py` | Calibrated crop; AI import; Make It Tile insertion on script thread | Native 3221225477, **3.2738 s**, checkpoint `image_imported`; zero maps. |
| `photo_tile_v002.py` | Compute image first, insert on UI thread, await callback with `threading.Event` | Native 3221225477, **11.5807 s**, checkpoint `image_computed`; zero maps. |

The tile-filter attempts are distinct script-thread and synchronised UI-thread
routes, not repeated retries. No further procedural crash retries followed [D260].
The demonstrated export route does not repair native filter insertion. Adobe
binary/GPU/licensing repair is outside the research worktree.

`photo_tile_v001.log` records a directory-collision rejection before the filter
attempt; `photo_tile_v001_run2.log` records the native filter crash. Scripts retain
fresh-version directory guards. Failed evidence is not a tool to rerun blindly.
Commands below were wrapped in Python `subprocess.run(..., capture_output=True,
timeout=...)`; native return codes, not the wrapper exit, are the runtime verdict.

```bash
# Successful raw image-to-material export:
"C:/Program Files/Adobe/Adobe Substance 3D Sampler/Adobe Substance 3D Sampler.exe" --run-script-silent "C:/Users/artsafro/agr-pilot/AGR-DigitalTwin/.worktrees/t_ab5c23eb/tmp/substance-probe/photo_export_v003.py"
# Failed tileable attempts, each with its own new output directory:
"C:/Program Files/Adobe/Adobe Substance 3D Sampler/Adobe Substance 3D Sampler.exe" --run-script-silent "C:/Users/artsafro/agr-pilot/AGR-DigitalTwin/.worktrees/t_ab5c23eb/tmp/substance-probe/photo_tile_v001.py"
"C:/Program Files/Adobe/Adobe Substance 3D Sampler/Adobe Substance 3D Sampler.exe" --run-script-silent "C:/Users/artsafro/agr-pilot/AGR-DigitalTwin/.worktrees/t_ab5c23eb/tmp/substance-probe/photo_tile_v002.py"
# Partial-evidence generator; -P avoids historical inspect.py shadowing stdlib inspect:
uv run python -P tmp/substance-probe/seal_photo_evidence.py
```

Additional installed primary reference:
`Resources/pythonapi-doc/html/_generate/substance_sampler.ExportController.html`:
`wait_for` blocks until associated exports finish, cancelling on timeout. The
observed callback-order failure proves `run_in_main_thread` returning None is not
a completion receipt. Successful raw exports ran in script thread. Logs enumerate
desktop screens: this is silent automation, not proof of display-independent rendering.

### Partial map readback and visual comparison

Six **actual** 2048-square raw maps are in `substance-photo-v002/raw_ai_export/`:

| Channel | IHDR / Pillow readback | Unresolved delivery constraint |
|---|---|---|
| BaseColor | RGB, 8 bit/channel | Diffuse candidate; tileability and colour acceptance open. |
| Roughness | Grayscale, 8 bit | Inferred, not measured material property. |
| Metallic | Grayscale, 8 bit | Inferred, not independent physical-property evidence. |
| Normal | **RGBA, 16 bit/channel** | Invalid VPM export as-is: alpha, bit depth and DirectX convention unresolved. |
| Height | Grayscale, 16 bit | Diagnostic only; no calibrated relief amplitude. |
| AmbientOcclusion | Grayscale, 8 bit | Diagnostic only; never substitute for ERM emissive red. |

`partial-comparison.png`: existing job texture, AI BaseColor, raw Normal,
2 x 2 repeats and inferred roughness. Visual inspection shows recognisable
bond/joint geometry with reduced baked-looking edge shading in BaseColor, but a
repeat boundary remains visible. This unlit image sheet establishes neither
shader quality nor a tileable approved finish.

`readback.json` records file hashes, IHDR and diagnostic opposite-edge mean
absolute RGB difference after resizing a preview to 256-square. BaseColor X/Y:
**7.3711/12.1159**, current map: **13.4167/13.9622**, on 0-255 RGB. Lower preview
edge error is not proof of phase continuity, scale accuracy or superior quality.
The recorded Height preview uses Pillow's clipped 16-bit-to-RGB conversion; its
zero edge value must not be interpreted as a height-quality result.

**77.67 s is raw AI-export time, not time per completed tileable finish.** Completed
finish time is unmeasured; preparation/debugging were not separately timed.
No measured timing comparison against creation of the current texture is available.

### Recommendation and current follow-up proposals

Keep Substance upstream of the finish library. Its demonstrated role is source
lighting reduction and inferred channels; autonomous tiling remains blocked.
Do not replace the existing finish with this partial experiment. Do not rename raw
maps into a purported valid delivery: the required ERM/DirectX RGB8 triplet still
needs controlled conversion/readback after tileability succeeds.

Catalogue binding must distinguish OBR22 finish **5** from library material 17 /
RAL 8023; no automatic identity is established. Preserve RAL code separately from
screen sRGB and require palette review. A future graph should expose bond, face
size, joint width, colour and wear independently, recording metre units, seed,
graph hash and RAL identity. Parameter fidelity, procedural output and timings
remain **not verified** [D260].

Proposed follow-up scopes (not created as issues; card forbids issue creation):
1. After a Sampler update/reinstall, a later issue can reuse the same hashed
   source/crop to retest filter insertion and attempt the photo-to-tileable pilot.
   Do not resume attempts under this card [D259].
2. Once Designer + SAT exist, procedural `.sbsar` variant pilot with bond/joint/
   colour/wear, stable seed, physical-scale checks and exact render/cook commands.
3. Only after visual approval: finish-library recipe/provenance and RAL-binding
   manifest; no automatic library promotion now.

### Continuation evidence / handoff

`G:/Мой диск/AGR-evidence/1258/substance-photo-v002/` holds raw PNGs, partial sheet,
crop, scripts, checkpoints and logs, with `SHA256SUMS.txt`. The card comment records
the final seal hash/count. Initial `substance-capability-v001` remains unchanged.
No customer images, scenes or renders are committed; no shared Python modules
or production scripts are introduced. Probe scripts remain historical evidence,
not supported pipeline tools. Final local-suite/eval receipts belong to the PR body;
they verify this documentation branch, not a usable Substance workflow.

**Historical unblock superseded by [D259]:** no more attempts are required or
permitted here. A later issue resumes after Sampler update/reinstall or Designer
installation; it must independently verify runtime, tileability, physical scale,
ERM packing, RGB8 DirectX normals, visual quality and time per completed finish.
Raw export alone still does not satisfy the original texture-production requirement.
