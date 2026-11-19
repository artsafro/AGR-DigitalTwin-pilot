# 3ds Max 2027.3 migration spike (#1697)

**Decision: WAIT.** Keep Max 2026, MAX-15 and FBX as the production baseline. Max 2027.3 opened the native test copy and performed both exchange exports, but the headless runs exited nonzero, the glTF route lost authored quads, and the official MCP loop and 2026 reopen are still pending. No production settings, scenes or code were changed.

## Host and evidence

- On 2026-11-19 the installed `C:/Program Files/Autodesk/3ds Max 2027/3dsmax.exe` reported `29.3.0.31295`. Its plugin directory contained both `KHRglTFImporter_adsk.dli` and `KHRglTFExporter_adsk.dle`.
- Process preflight repeatedly showed another Max 2027 process (PID 1455616, `uvtools-2027/max2027-signed/3dsmax.exe`); a separate batch/child pair also appeared during preflight. None was reserved for #1697. `max_exec.py` defaults to the newest interactive process unless pinned, and lack of a lock file is not proof that a document is available. No ping, attachment, launch, termination or change of settings was attempted on those processes or Max 2026. The [workstation ownership protocol](agents/dcc-offline-workflows.md#mcp-workflow-ownership-protocol-cooperative-not-enforced-by-this-helper) requires ownership through the workflow, not merely serial calls.
- Accepted fixture: [Vatutino Ground v015, route A](../jobs/VATUTINO-SITE/ground-v015-route-a-session-20261104.md). Source archive `G:/Мой диск/AGR-evidence/371-ground-v015-route-a-20261104/session-v001.zip`, SHA-256 `7441764b82ce799684b400a6dd90fcd7a61991ff575f3fbb00d77cef1fef52bb`. The Blender input was an exclusive copy of `artefacts/ground-v015-dcc-v001/textured/vpm/SM_Vatutino_Ground.fbx` (2,802,220 bytes; SHA-256 `39a45ab7004be8a1cf47a0c85b2d22f83d0e7b9a639c1c324344f5b914d3b188`, unchanged after execution). The native Batch input was a separate copy of `artefacts/ground-v015-native-v002/vpm/SM_Vatutino_Ground.max` from the same archive.
- Blender driver, log, counters and GLB: `G:/Мой диск/AGR-evidence/max2027-spike/blender-baseline-v001/`; four files verified against `SHA256SUMS.txt`. GLB hash `35dd01130b62e5a13b7f91d1b2d0b2034fb2ad0af6f7bc513006352e840e710f`.
- On 2026-11-20 the operator authorized headless work while PID 1472048 remained interactive. The approved `dcc_batch.py max --version 2027` wrapper took the shared Max lock with card tags; no calls targeted the open session or Max 2026. See `G:/Мой диск/AGR-evidence/max2027-spike/native-batch-v002/` for argv, logs, scripts, readback and `SHA256SUMS.txt` (23/23 files verified after copy; all four staged inputs matched their pre-run SHA-256). The native source copy (`9255951a2bc337773821885a43d613f96a7dd07071059c5260c9aec961d3f486`) opened in 4.20 s with system units 1 m, 728 meshes (727 UCX), 18,312 Ground quads and 9,855 triangles.
- Even the no-scene ping printed its completion marker then exited nonzero (44.6 s); substantive runs also wrote their markers but returned wrapper exit 1 / Max exit 4294967166 (`-130` as signed). The logs include `DeleteItem failed`, batch warnings for `viewportmanager.gup`, and a Prune Scene startup message. Cause not isolated. Stage results and independently readable artifacts remain useful; **unattended Batch is not green**. The main and follow-up batch invocations took 63.8 s and 76.1 s respectively, including startup/shutdown; these are not MCP timings.

## 1. Official MCP vs MAX-15

| Route | Open, read objects/materials, check quads, edit, export FBX | Wall time / failure |
|---|---|---|
| Autodesk 2027.3 Tech Preview | Not run | Not measured; another interactive 2027 session is open and is excluded by the operator |
| [MAX-15 / current bridge](agents/CAPABILITIES.md#3ds-max--3dsmax-mcp) | Not run via bridge | No end-to-end time; 2027 Batch startup reported native bridge helpers loaded, not a successful client connection or edit |

[Autodesk preferences][prefs] and the [external client guide][external] say the server listens locally, needs an **interactive** Max session (not Max Batch), and uses a per-session endpoint and token. Regular `Read/write` adds undo/redo, not general script execution. `Safe MAXScript` adds scripts with approval by default; the approval UI needs an MCP Apps client. An [administrator option][admin] can skip the proposal step. That is not a filesystem sandbox: [Autodesk's sandbox guide][sandbox] says Safe Scene Script Execution still applies and recommends isolation for untrusted scripts. Neither setting was changed. For unattended runs keep the existing route until an isolated interactive pilot proves all five steps, including a modal-free export; the [known limitations][limits] list modal dialogs and INI writes as concrete risks. Do not relax the shared workstation's approvals or Safe Scene Execution as a migration workaround.

The [special terms][terms] include use during a current Max subscription while Autodesk makes the preview available; Autodesk can withdraw it. No separate server tariff or quota is stated in the cited docs. Local transport is not proof of fully offline use: Max licensing, the selected MCP client/model, its quota/cost, and operation without network access were not measured. The local server is not Autodesk Assistant.

## 2. Plugins and tools

| Component | Evidence on this host | 2027.3 status |
|---|---|---|
| AGR Tools | Installed bundle 1.1.0 logged macro registration; installed Python `matid` returned `missing_material` on a synthetic untextured box | Loads in Batch; one read-only command exercised, UI/full workflow not verified |
| GeoAGR | Found `Geoscript`, `GeoAGR Personal` and `GeoAGR Private` 2027 macros; each macro's referenced local target was absent at its declared path | Broken launch paths on this install; did not invoke error dialogs or infer an incompatible binary |
| UDIM MultiSub | `UDIM-MultiSub_Universal(max22-26).ms`: a copied script ran on a synthetic tile-1001 quad and created `Multimaterial`, face ID 1, material label `UDIM_1001.0` | Loads, but failed exact `UDIM_1001` name witness twice; not a proven 2027 regression without a reference run. [D030 separates working material IDs from UDIM numbers](domain/materials.md) |
| Forest Pack Pro | Installed 9.2.4 declares only 2026; no Forest class in fresh 2027 Batch | Needs a 2027 vendor build |
| RailClone Pro | Installed 7.0.8 declares only 2026; no RailClone class in fresh 2027 Batch | Needs a 2027 vendor build |
| Corona | No Corona renderer class in fresh 2027 Batch; no 2027 build established on this host | Not available to this batch, verify 2027 install and material/render smoke |
| V-Ray | No V-Ray renderer class in fresh 2027 Batch; no 2027 build established on this host | Not available to this batch, verify 2027 install and material/render smoke |

## 3. VPM exchange: the first glTF leg already loses quads

**Measured control, not a Max round trip:** Blender 5.1.2, factory-startup headless with `--disable-autoexec --threads 1 --python-exit-code 1`, imported the copied FBX, exported GLB, reset to an empty scene and read the GLB back. Exit 0, explicit completion marker, 7.148 s wall time (whole Blender control, not MCP). All 728 mesh names were present before and after (Ground + 727 UCX). Ground changed from **18,312 quads + 9,855 triangles to 0 quads + 46,479 triangles**. Imported Ground vertex count changed from 27,431 to 93,484. Both reads exposed one UV layer and the same twelve material slot names; neither establishes per-corner UV/UDIM parity, numeric material ID or assignment parity, geometry/winding parity, or normal-vector parity. Corner-normal counts were 102,813 and 139,437, not a normal comparison.

[Autodesk documents the integrated importer/exporter][gltf]. Max `KHRglTFImporter` read the Blender GLB in 3.24–3.40 s; `KHRglTFExporter` wrote glTF + BIN in 9.34 s and `FBXEXP` wrote FBX in 7.53 s. The initial glTF export probe failed closed because `KHRglTFExporter` and legacy `GLTF_Export` both matched; a fresh Batch selected `KHRglTFExporter` explicitly. Blender 5.1.2 independently read both outputs (exit 0). Each contains all 728 named meshes, including 727 UCX, one Ground UV layer, 46,479 Ground triangles and **zero Ground quads**. All Ground bounding-box extrema were within 0.02 mm of the Blender GLB control. Neither Max re-export restores omitted quad rings; core [glTF 2.0](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html) uses triangle-based surfaces. **Do not use glTF for the editable VPM master.**

| Ground triangles matching the Blender GLB control (46,479 total) | KHR glTF return | FBX return |
|---|---:|---:|
| World-position bins and oriented corner order | 45,323 | 45,265 |
| Same + per-corner UV bins | 45,323 | 45,265 |
| Same oriented positions + corner normal bins | 35,395 | 16,286 |
| Same oriented positions + material name | 45,323 | 45,265 |
| Same oriented positions + Blender material slot index | 45,323 | 0 |

These are whole-triangle intersection counts in fixed bins (0.1 mm positions, 0.00001 UV and 0.0001 normal components), not magnitude bounds on mismatches. Bin crossings alone can create mismatches; exact tested parity was not shown for geometry, UVs or normals. UV and named-material parity held for geometry-matched Ground triangles of both returns, not for every triangle or texture. On the initial Blender FBX → GLB leg, positions/winding matched 46,479, UVs 46,444, normals 30,241 and material names 46,479. UCX position/winding matches after the Max legs were 7,682 and 6,756 of 8,904 respectively; UCX had no UVs in any read. Native Max `getFaceMatID` histograms also show the GLB import shifting corresponding Ground populations from numeric IDs 1–12 to 2–13. Blender slot numbers are not a proxy for native Max IDs. Retain FBX as the production exchange; a visual-only glTF path would need separate texture/shading acceptance.

## 4. Mesh Cleaner vs AGR QA

[Autodesk documents distinct switches][cleaner] for isolated and internal dead Editable/Edit Poly vertices. AGR's [export scene QA](../src/twinqa/scene.py) checks isolated topology but does not read native dead flags from an exported mesh. On the native VPM Ground copy, a direct live-face reference count and `polyop.getDeadVerts` found **0 isolated / 0 dead**. The positive control injected one of each (isolated ID 27432, dead ID 27433). Both copies had 28,167 live faces. `MeshCleaner` loaded, but setting `repairDeadVertices` threw a read-only-property error. Default stack evaluation left `validationRan=false` on both; it returned 27,431 vs 27,432 snapshot vertices, not proof of dead cleanup, because snapshot can discard dead slots itself. Calling the exposed `meshCleanerInterface.ValidateMesh()` raised a native access violation in Batch on both inputs; `RepairMesh()` was not reached. **Headless detection/repair failed; same/more/less is not established.** No further headless retry: in the owned interactive session use Detect Problems and Repair Selected, checking the two counters separately and verifying unchanged face geometry, UVs and material IDs. Do not replace AGR QA with the modifier.

## 5. Save backward

**Write measured; 2026 reopen pending.** Batch wrote both 2027 and `saveAsVersion=2026` scratch files in 0.58 s combined. `native-batch-v002/vpm-save-as-2026.max` (2,809,856 bytes, SHA-256 `7da32158938d252c9b8d69ae2634758de421cd92fc54508d4cd3c482e6a39772`) is the operator test input. Open a further copy in an isolated 2026 acceptance session and record actual build, missing plugin/assets warnings, scene inventory and relevant QA. A successful save is not an open test. Do not attach to, close or repurpose any existing 2026 session.

## Resume criteria and effort

1. Reserve a disposable interactive installed 2027.3 session, with explicit PID/build/document/units and an approved official-MCP route that honors the full live-DCC lock; release any conflicting Max work first. Keep approvals on for the first test. Run each route from byte-identical, separately staged VPM `.max` copies and fresh output paths. Capture same-step wall times, approval wait, failures, script/export settings, and independently reopen each FBX. Treat timeout or a modal with unknown outcome as a stop, not a retry.
2. Resolve missing plugin builds/GeoAGR targets; verify interactive tool loads and test a render/material fixture. Complete Mesh Cleaner detection/repair and have the operator reopen the saved copy in 2026. Diagnose nonzero Batch exits before trusting overnight runs. Do not promote glTF as an editable route based on file readability.
3. Planning estimate, not a measured migration cost: 0.5–1 day for the locked pilot after the session, clients and plugin builds are ready; 1–3 additional engineer-days for a staging rollout if compatibility is clean. Plugin porting/rebuilds, install/licensing lead time and unattended security approval are excluded and not estimable yet. Host replacement and MCP replacement are separate decisions.

## Коротко для Артёма

**WAIT — пока не переходим.** 2027.3 Batch прочитал копию Ватутино, и Blender открыл оба обратных экспорта. Ни glTF, ни FBX после glTF не вернули **18 312 квадов**; индексы материалов и нормали не прошли проверку на сохранность. Оставляем 2026, MAX-15 и FBX. AGR Tools загрузился; у GeoAGR не найдены цели запуска; UDIM назвал материал `UDIM_1001.0`. Нужны сборки Forest Pack/RailClone под 2027 и проверка Corona/V-Ray. Batch возвращает ошибку даже после записи файлов. Осталось проверить оба MCP на своей интерактивной 2027.3, Mesh Cleaner и открытие уже записанной копии в отдельной 2026 у оператора. Рабочие сессии не трогал. После готовности среды: **0,5–1 день на пилот**, затем **1–3 инженерных дня** на пробный перенос при совместимости, без обновления плагинов.

[prefs]: https://help.autodesk.com/cloudhelp/2027/ENU/3dsMax-Customizing/files/preferences/GUID-CD3E7ED7-51C1-40FB-9AF4-A0929532143E.html
[external]: https://help.autodesk.com/cloudhelp/2027/ENU/3dsMax-MCP/files/GUID-48002624-B8CE-4F3C-A16C-DE80FD409E5A.html
[admin]: https://help.autodesk.com/cloudhelp/2027/ENU/3dsMax-MCP/files/GUID-6C4E10E5-7611-46D3-9F4E-EFE99BB9B716.html
[sandbox]: https://help.autodesk.com/cloudhelp/2027/ENU/3dsMax-MCP/files/GUID-AF7D4A97-6804-4651-A8A9-3BF0A6235B54.html
[limits]: https://help.autodesk.com/cloudhelp/2027/ENU/3dsMax-MCP/files/GUID-25CAA219-2BF8-46C9-82BA-F97D369B6026.html
[terms]: https://help.autodesk.com/cloudhelp/2027/ENU/3dsMax-MCP/files/GUID-17338963-38FE-4A13-A727-DCC64A965E39.html
[gltf]: https://help.autodesk.com/cloudhelp/2027/ENU/3dsMax-WhatsNew/files/whats_new_in_3ds_max_2027.3/GUID-38EA97CA-E0B8-45D2-9539-1BF47BDE494D.html
[cleaner]: https://help.autodesk.com/cloudhelp/2027/ENU/3dsMax-Modifiers/files/object-space_modifiers/GUID-BADE14D6-0646-4642-A37B-311594A65C81.html
