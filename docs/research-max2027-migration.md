# 3ds Max 2027.3 migration spike (#1697)

**Decision: WAIT.** Keep Max 2026, MAX-15 and FBX as the production baseline. Side-by-side Max 2027.3 is a test target, not a replacement. This is an interim report: the Blender control ran; none of the Max runtime acceptance checks ran. No production settings, scenes or code were changed.

## Host and evidence

- On 2026-11-19 the installed `C:/Program Files/Autodesk/3ds Max 2027/3dsmax.exe` reported `29.3.0.31295`. Its plugin directory contained both `KHRglTFImporter_adsk.dli` and `KHRglTFExporter_adsk.dle`.
- Process preflight repeatedly showed another Max 2027 process (PID 1455616, `uvtools-2027/max2027-signed/3dsmax.exe`); a separate batch/child pair also appeared during preflight. None was reserved for #1697. `max_exec.py` defaults to the newest interactive process unless pinned, and lack of a lock file is not proof that a document is available. No ping, attachment, launch, termination or change of settings was attempted on those processes or Max 2026. The [workstation ownership protocol](agents/dcc-offline-workflows.md#mcp-workflow-ownership-protocol-cooperative-not-enforced-by-this-helper) requires ownership through the workflow, not merely serial calls.
- Accepted fixture: [Vatutino Ground v015, route A](../jobs/VATUTINO-SITE/ground-v015-route-a-session-20261104.md). Source archive `G:/Мой диск/AGR-evidence/371-ground-v015-route-a-20261104/session-v001.zip`, SHA-256 `7441764b82ce799684b400a6dd90fcd7a61991ff575f3fbb00d77cef1fef52bb`. The Blender input was an exclusive copy of `artefacts/ground-v015-dcc-v001/textured/vpm/SM_Vatutino_Ground.fbx` (2,802,220 bytes; SHA-256 `39a45ab7004be8a1cf47a0c85b2d22f83d0e7b9a639c1c324344f5b914d3b188`, unchanged after execution). The same archive contains the small native VPM scene `artefacts/ground-v015-native-v002/vpm/SM_Vatutino_Ground.max` for the paired Max test; that member was not opened.
- Blender driver, log, counters and GLB: `G:/Мой диск/AGR-evidence/max2027-spike/blender-baseline-v001/`; four files verified against `SHA256SUMS.txt`. GLB hash `35dd01130b62e5a13b7f91d1b2d0b2034fb2ad0af6f7bc513006352e840e710f`. No native Max evidence is claimed.

## 1. Official MCP vs MAX-15

| Route | Open, read objects/materials, check quads, edit, export FBX | Wall time / failure |
|---|---|---|
| Autodesk 2027.3 Tech Preview | Not run | Not measured; no dedicated interactive test session or approved lock route for official MCP |
| [MAX-15 / current bridge](agents/CAPABILITIES.md#3ds-max--3dsmax-mcp) | Not run | Not measured; installed v1.7.5 includes a 2027 GUP and manifest entry, but that does not prove the GUP loads or connects |

[Autodesk preferences][prefs] and the [external client guide][external] say the server listens locally, needs an **interactive** Max session (not Max Batch), and uses a per-session endpoint and token. Regular `Read/write` adds undo/redo, not general script execution. `Safe MAXScript` adds scripts with approval by default; the approval UI needs an MCP Apps client. An [administrator option][admin] can skip the proposal step. That is not a filesystem sandbox: [Autodesk's sandbox guide][sandbox] says Safe Scene Script Execution still applies and recommends isolation for untrusted scripts. Neither setting was changed. For unattended runs keep the existing route until an isolated interactive pilot proves all five steps, including a modal-free export; the [known limitations][limits] list modal dialogs and INI writes as concrete risks. Do not relax the shared workstation's approvals or Safe Scene Execution as a migration workaround.

The [special terms][terms] include use during a current Max subscription while Autodesk makes the preview available; Autodesk can withdraw it. No separate server tariff or quota is stated in the cited docs. Local transport is not proof of fully offline use: Max licensing, the selected MCP client/model, its quota/cost, and operation without network access were not measured. The local server is not Autodesk Assistant.

## 2. Plugins and tools

| Component | Evidence on this host | 2027.3 status |
|---|---|---|
| AGR Tools | Installed bundle 1.1.0 declares 2024–2027 | Eligible by manifest; load and command smoke unmeasured |
| GeoAGR | Existing workstation integration in the [inventory](agr/inventory/README.md) | 2027 load/command smoke unmeasured |
| UDIM MultiSub | `UDIM-MultiSub_Universal(max22-26).ms` does not declare 2027 | Unsupported by declaration; runtime unknown. Use only a copy: [D030 separates working material IDs from UDIM numbers](domain/materials.md) |
| Forest Pack Pro | Installed 9.2.4 declares only 2026 | This package needs a vendor build for 2027; load unmeasured |
| RailClone Pro | Installed 7.0.8 declares only 2026 | This package needs a vendor build for 2027; load unmeasured |
| Corona | Existing integration appears in the inventory; no 2027 build established | Verify vendor build, local install and renderer/material smoke |
| V-Ray | Existing integration appears in the inventory; no 2027 build established | Verify vendor build, local install and renderer/material smoke |

## 3. VPM exchange: the first glTF leg already loses quads

**Measured control, not a Max round trip:** Blender 5.1.2, factory-startup headless with `--disable-autoexec --threads 1 --python-exit-code 1`, imported the copied FBX, exported GLB, reset to an empty scene and read the GLB back. Exit 0, explicit completion marker, 7.148 s wall time (whole Blender control, not MCP). All 728 mesh names were present before and after (Ground + 727 UCX). Ground changed from **18,312 quads + 9,855 triangles to 0 quads + 46,479 triangles**. Imported Ground vertex count changed from 27,431 to 93,484. Both reads exposed one UV layer and the same twelve material slot names; neither establishes per-corner UV/UDIM parity, numeric material ID or assignment parity, geometry/winding parity, or normal-vector parity. Corner-normal counts were 102,813 and 139,437, not a normal comparison.

[Autodesk documents the integrated importer/exporter][gltf]. Core [glTF 2.0](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html) encodes triangle-based surfaces, not authored quad rings. Any reconstructed quads require a separate fidelity test; neither a glTF nor an FBX return leg can restore missing source quad boundaries by format alone. **Do not use glTF to carry the editable VPM master.** Its utility for already-triangulated review/visual assets remains open. Both Max return legs (glTF and FBX) are not run.

## 4. Mesh Cleaner vs AGR QA

[Autodesk documents distinct switches][cleaner] for isolated vertices and internal dead Editable/Edit Poly vertices. AGR's [export scene QA](../src/twinqa/scene.py) expects no isolated vertices/edges/polygons and also checks defects outside Mesh Cleaner's dead-vertex option. The Blender FBX control reported zero Ground vertices unreferenced by polygons; this is not evidence about native dead flags, which may not survive export. Clean parity, same/more/less, and any cleanup side effects are **not measured**. On a native VPM copy, compare unchanged baseline and a separate positive control containing one isolated and one dead poly vertex, detect before repair, isolate each checkbox, and compare IDs/counts plus unaffected geometry/UV/materials. Do not replace AGR QA with the modifier.

## 5. Save backward

Not run. Verify Save As 2026 on a new scratch copy, then have the operator open it in an isolated 2026 acceptance session and record actual build, missing plugin/assets warnings, scene inventory and relevant QA. A successful save is not an open test. Do not attach to, close or repurpose any existing 2026 session.

## Resume criteria and effort

1. Reserve a disposable interactive installed 2027.3 session, with explicit PID/build/document/units and an approved official-MCP route that honors the full live-DCC lock; release any conflicting Max work first. Keep approvals on for the first test. Run each route from byte-identical, separately staged VPM `.max` copies and fresh output paths. Capture same-step wall times, approval wait, failures, script/export settings, and independently reopen each FBX. Treat timeout or a modal with unknown outcome as a stop, not a retry.
2. In 2027.3, verify the plugin matrix with class/version plus one load/command smoke per row. Compare both Max exchange branches against frozen Blender input: world geometry, winding, per-corner UV/UDIM/normals, face-region mapping to material IDs and polygon degree, with UCX separate. Then run the native Mesh Cleaner comparison and operator 2026 reopen.
3. Planning estimate, not a measured migration cost: 0.5–1 day for the locked pilot after the session, clients and plugin builds are ready; 1–3 additional engineer-days for a staging rollout if compatibility is clean. Plugin porting/rebuilds, install/licensing lead time and unattended security approval are excluded and not estimable yet. Host replacement and MCP replacement are separate decisions.

## Коротко для Артёма

**WAIT — пока не переходим.** 2027.3 установлен, но живые тесты не запускал: Max занят другой сессией. Max 2026 не трогал. На принятом ВПМ Ватутино уже первый шаг в glTF убрал все **18 312 квадов**; glTF — кандидат для просмотра, не для редактируемого мастера. Официальный MCP локальный, но только для интерактивного Max; обход ручного подтверждения администратором предусмотрен, ночной цикл и экспорт не проверены. Оставляем MAX-15 и FBX. Нужны выделенный 2027.3 с согласованным маршрутом MCP, сборки Forest Pack/RailClone для 2027, проверка AGR Tools/GeoAGR/UDIM и Corona/V-Ray, затем Mesh Cleaner и открытие копии в изолированной 2026 у оператора. После готовности среды: **0,5–1 день на пилот**, затем **1–3 инженерных дня** на пробный перенос, если всё совместимо; сроки обновления плагинов сюда не входят.

[prefs]: https://help.autodesk.com/cloudhelp/2027/ENU/3dsMax-Customizing/files/preferences/GUID-CD3E7ED7-51C1-40FB-9AF4-A0929532143E.html
[external]: https://help.autodesk.com/cloudhelp/2027/ENU/3dsMax-MCP/files/GUID-48002624-B8CE-4F3C-A16C-DE80FD409E5A.html
[admin]: https://help.autodesk.com/cloudhelp/2027/ENU/3dsMax-MCP/files/GUID-6C4E10E5-7611-46D3-9F4E-EFE99BB9B716.html
[sandbox]: https://help.autodesk.com/cloudhelp/2027/ENU/3dsMax-MCP/files/GUID-AF7D4A97-6804-4651-A8A9-3BF0A6235B54.html
[limits]: https://help.autodesk.com/cloudhelp/2027/ENU/3dsMax-MCP/files/GUID-25CAA219-2BF8-46C9-82BA-F97D369B6026.html
[terms]: https://help.autodesk.com/cloudhelp/2027/ENU/3dsMax-MCP/files/GUID-17338963-38FE-4A13-A727-DCC64A965E39.html
[gltf]: https://help.autodesk.com/cloudhelp/2027/ENU/3dsMax-WhatsNew/files/whats_new_in_3ds_max_2027.3/GUID-38EA97CA-E0B8-45D2-9539-1BF47BDE494D.html
[cleaner]: https://help.autodesk.com/cloudhelp/2027/ENU/3dsMax-Modifiers/files/object-space_modifiers/GUID-BADE14D6-0646-4642-A37B-311594A65C81.html
