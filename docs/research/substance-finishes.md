# Substance finishes feasibility — issue #1258

## Status: blocked before the two pilots

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

Required unblock: provide a working supported procedural Substance runtime
(Designer/SAT, or a working licensed Sampler Brickwall path) or explicitly approve
changing the procedural-pilot requirement. Do not mark this issue complete or open
a closing PR while both real finish pilots and their comparison remain undelivered.
