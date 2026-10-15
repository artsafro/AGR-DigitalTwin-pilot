# Toolchain smoke check, 2026-10-15 (#139)

Evidence for the `Headless toolchain smoke check` table in `docs/agents/CAPABILITIES.md`.
All runs were headless on the user's workstation: no GUI, no user scenes, scratch copies only
(scratch dir `<worktree>/tmp/issue139/`, git-ignored, not committed). The only test model is a
synthetic cube FBX generated in run 7. Nothing was installed or changed.

A smoke run proves that a tool starts and does one small thing. It is not delivery validation
(`passed=true`) and not acceptance.

- Runs: 18
- Total probe time: 149.381 s (main batch 144.515 s, supplemental version queries 4.866 s)
- Started 2026-10-15T15:57:17.401405+00:00, main batch finished 2026-10-15T15:59:41.917830+00:00, supplemental finished 2026-10-15T16:07:19.417262+00:00 (UTC)
- Paths: `<worktree>` = the card worktree, `%USERPROFILE%` = the user's home.

## Summary

| # | Run | Exit | Seconds | Last output line |
|---|---|---|---|---|
| 1 | [pdf_group_literal](#run-1-pdf_group_literal) | 2 | 0.418 | `` error: Group `pdf-review` is not defined in the project's `dependency-groups` table `` |
| 2 | [pdf_extra_fallback](#run-2-pdf_extra_fallback) | 0 | 3.454 | `` Installed 1 package in 89ms `` |
| 3 | [cad_group_literal](#run-3-cad_group_literal) | 2 | 0.082 | `` error: Group `cad` is not defined in the project's `dependency-groups` table `` |
| 4 | [cad_extra_fallback](#run-4-cad_extra_fallback) | 0 | 4.829 | `` CAD check SUCCESS: wrote and verified 1 LINE entity in <worktree>\tmp\issue139\test_line.dxf (start=(0.0, 0.0, 0.0), end=(10.0, 10.0, 0.0... `` |
| 5 | [speedtree_mcp_client](#run-5-speedtree_mcp_client) | 0 | 5.641 | `` CallToolRequest `` |
| 6 | [blender_version](#run-6-blender_version) | 0 | 0.296 | `` build system: CMake `` |
| 7 | [blender_synthetic_cube_fbx](#run-7-blender_synthetic_cube_fbx) | 0 | 2.311 | `` Blender quit `` |
| 8 | [blender_checktoolbox_addon_probe](#run-8-blender_checktoolbox_addon_probe) | 1 | 1.458 | `` Addon 'CheckToolBox_v1_5' is MISSING in Blender 5.1 (baseline 5.1.2; missing addon is fails, no install). Discovered modules: ['io_anim_b... `` |
| 9 | [blender_qa_checktoolbox_run](#run-9-blender_qa_checktoolbox_run) | 0 | 1.471 | `` ModuleNotFoundError: No module named 'CheckToolBox_v1_5' `` |
| 10 | [acad_dcc_batch_ping](#run-10-acad_dcc_batch_ping) | 0 | 4.306 | `` {"status": "ok", "exit_code": 0, "seconds": 4.0, "cmd": ["C:\\Program Files\\Autodesk\\AutoCAD 2025\\accoreconsole.exe", "/s", "%USERPROF... `` |
| 11 | [max_dcc_batch_ping](#run-11-max_dcc_batch_ping) | 0 | 120.212 | `` {"status": "ok", "exit_code": 4294967166, "seconds": 119.9, "cmd": ["C:\\Program Files\\Autodesk\\3ds Max 2026\\3dsmaxbatch.exe", "%USERP... `` |
| 12 | [blender_44_version](#run-12-blender_44_version) | 0 | 0.35 | `` build system: CMake `` |
| 13 | [blender_44_addon_probe](#run-13-blender_44_addon_probe) | 0 | 1.294 | `` Addon 'CheckToolBox_v1_5' detected. Version: unknown `` |
| 14 | [blender_44_qa_checktoolbox_run](#run-14-blender_44_qa_checktoolbox_run) | 0 | 1.941 | `` Blender quit `` |
| 15 | [pymupdf_installed_version](#run-15-pymupdf_installed_version) | 0 | 0.34 | `` 1.28.2 `` |
| 16 | [ezdxf_installed_version](#run-16-ezdxf_installed_version) | 0 | 0.317 | `` 1.4.3 `` |
| 17 | [pdf_cad_installed_versions](#run-17-pdf_cad_installed_versions) | 0 | 0.319 | `` pymupdf=1.28.2 ezdxf=1.4.3 `` |
| 18 | [speedtree_mcp_package_version](#run-18-speedtree_mcp_package_version) | 0 | 0.28 | `` 1.30.0 `` |

Notes on the summary: run 2's last line is uv's install message; its success line is in the output
below. Run 5's last line is server stderr logging; the success line is in stdout.

## Runs

### Run 1: pdf_group_literal

Literal command from the issue. `pyproject.toml` declares `pdf-review` as an optional extra, not a dependency group.

- Exit code: 2; seconds: 0.418; timed out: False
- Command:

```text
%USERPROFILE%\AppData\Local\Programs\Python\Python313\Scripts\uv.EXE run --offline --group pdf-review python <worktree>\tmp\issue139\pdf.py --pdf <worktree>\standards\source\Rasporyajenies19012026trebovaniya(2).pdf --out <worktree>\tmp\issue139\scratch_page1.png
```

stderr (tail):

```text
error: Group `pdf-review` is not defined in the project's `dependency-groups` table
```

### Run 2: pdf_extra_fallback

Same helper with the existing extra. Rendered page 1 to a scratch PNG and read it back (1232x1755 RGB).

- Exit code: 0; seconds: 3.454; timed out: False
- Command:

```text
%USERPROFILE%\AppData\Local\Programs\Python\Python313\Scripts\uv.EXE run --offline --extra pdf-review python <worktree>\tmp\issue139\pdf.py --pdf <worktree>\standards\source\Rasporyajenies19012026trebovaniya(2).pdf --out <worktree>\tmp\issue139\scratch_page1.png
```

stdout (tail):

```text
warning: The `fitz` API is deprecated and will be removed in future. Use `import pymupdf` instead.
PDF check SUCCESS: rendered page 1 to <worktree>\tmp\issue139\scratch_page1.png (1232x1755, mode=RGB, format=PNG, size=1266619 bytes)
```

stderr (tail):

```text
Installed 1 package in 89ms
```

### Run 3: cad_group_literal

Literal command from the issue. `cad` is an optional extra, not a dependency group.

- Exit code: 2; seconds: 0.082; timed out: False
- Command:

```text
%USERPROFILE%\AppData\Local\Programs\Python\Python313\Scripts\uv.EXE run --offline --group cad python <worktree>\tmp\issue139\cad.py --out <worktree>\tmp\issue139\test_line.dxf
```

stderr (tail):

```text
error: Group `cad` is not defined in the project's `dependency-groups` table
```

### Run 4: cad_extra_fallback

Wrote a 1-entity DXF (LINE) to scratch and read it back.

- Exit code: 0; seconds: 4.829; timed out: False
- Command:

```text
%USERPROFILE%\AppData\Local\Programs\Python\Python313\Scripts\uv.EXE run --offline --extra cad python <worktree>\tmp\issue139\cad.py --out <worktree>\tmp\issue139\test_line.dxf
```

stdout (tail):

```text
CAD check SUCCESS: wrote and verified 1 LINE entity in <worktree>\tmp\issue139\test_line.dxf (start=(0.0, 0.0, 0.0), end=(10.0, 10.0, 0.0), size=18442 bytes, ezdxf=1.4.3)
```

### Run 5: speedtree_mcp_client

Started the speedtree-mcp stdio server, listed tools, called `installation_info`. No `.spm` sample is tracked, so no inspect/export.

- Exit code: 0; seconds: 5.641; timed out: False
- Command:

```text
%USERPROFILE%\AppData\Local\CodexMCP\BlenderLab103\venv\Scripts\python.exe <worktree>\tmp\issue139\speedtree.py
```

stdout (tail):

```text
    "task_root": "<worktree>",
    "interface": "local files and separate CLI batch export",
    "active_gui_control": false,
    "supported_export_formats": [
      "fbx"
    ],
    "cli_verification": "requires a successful recorded fixture export"
  },
  "spm_samples_found": [],
  "spm_status": "no tracked spm samples exist in the repository; export skipped as planned"
}
SpeedTree MCP check SUCCESS: protocol=2025-11-25, tools=['installation_info', 'list_templates', 'list_presets', 'inspect_preset', 'inspect_spm', 'export_tree'], installed=True, spm_status='no tracked spm samples exist in the repository; export skipped as planned'
```

stderr (tail):

```text
[10/15/26 17:57:29] INFO     Processing request of type           server.py:733
                             ListToolsRequest                                  
                    INFO     Processing request of type           server.py:733
                             CallToolRequest                                   
```

### Run 6: blender_version

Baseline Blender version print.

- Exit code: 0; seconds: 0.296; timed out: False
- Command:

```text
"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" --background --factory-startup --version
```

stdout (tail):

```text
	build date: 2026-05-19
	build time: 01:37:34
	build commit date: 2026-05-18
	build commit time: 13:43
	build hash: ec6e62d40fa9
	build branch: blender-v5.1-release
	build platform: Windows
	build type: Release
	build c flags:  -Wall -Werror=implicit-function-declaration -Werror=return-type -Wno-tautological-compare -Wno-unknown-pragmas -Wno-char-subscripts -Wstrict-prototypes -Wmissing-prototypes -Wunused-parameter -Wundef -Wundef-prefix -Werror=unguarded-availability-new /W3 -Wno-c++98-compat -Wno-old-style-cast -Wno-unsafe-buffer-usage -Wno-missing-prototypes -Wno-sign-conversion -Wno-missing-field-in
	build c++ flags:  -Wall -Wno-tautological-compare -Wno-unknown-pragmas -Wno-char-subscripts -Wno-overloaded-virtual -Wno-sign-compare -Wno-invalid-offsetof -Wno-suggest-override -Wundef -Wundef-prefix -Wunused-parameter -Wmismatched-tags -Werror=unguarded-availability-new /W3 -Wno-c++98-compat -Wno-old-style-cast -Wno-unsafe-buffer-usage -Wno-missing-prototypes -Wno-sign-conversion -Wno-missing-f
	build link flags: /MACHINE:X64  /SUBSYSTEM:CONSOLE /STACK:2097152 /ignore:4049 /ignore:4217 /ignore:4221
	build system: CMake
```

### Run 7: blender_synthetic_cube_fbx

Generated the synthetic test FBX (one cube, scratch only) for the CheckToolBox run.

- Exit code: 0; seconds: 2.311; timed out: False
- Command:

```text
"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" --background --factory-startup --python <worktree>\tmp\issue139\make_cube.py -- <worktree>\tmp\issue139\synthetic_cube.fbx
```

stdout (tail):

```text
FBX export starting... '<worktree>\\tmp\\issue139\\synthetic_cube.fbx'
export finished in 0.0219 sec.
Synthetic cube FBX generated successfully: <worktree>\tmp\issue139\synthetic_cube.fbx (11836 bytes)
Blender 5.1.2 (hash ec6e62d40fa9 built 2026-05-19 01:37:34)
Blender quit
```

### Run 8: blender_checktoolbox_addon_probe

CheckToolBox add-on is not installed in Blender 5.1 (nothing installed by this check).

- Exit code: 1; seconds: 1.458; timed out: False
- Command:

```text
"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" --background --factory-startup --python <worktree>\tmp\issue139\probe_addon.py
```

stdout (tail):

```text
Blender 5.1.2 (hash ec6e62d40fa9 built 2026-05-19 01:37:34)
```

stderr (tail):

```text
Addon 'CheckToolBox_v1_5' is MISSING in Blender 5.1 (baseline 5.1.2; missing addon is fails, no install). Discovered modules: ['io_anim_bvh', 'bl_pkg', 'cycles', 'io_scene_fbx', 'io_scene_gltf2', 'hydra_storm', 'ui_translate', 'bl_ext.user_default.mcp', 'node_wrangler', 'pose_library', 'rigify', 'io_curve_svg', 'bl_ext.user_default.sintez_agr_checker', 'io_mesh_uv_layout', 'viewport_vr_preview']
```

### Run 9: blender_qa_checktoolbox_run

KPP1 script on Blender 5.1: add-on import fails. Blender exits 0 because `--python-exit-code` was not passed; counted as FAIL.

- Exit code: 0; seconds: 1.471; timed out: False
- Command:

```text
"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" --background --factory-startup --python <worktree>\jobs\KPP1\scripts\qa_checktoolbox.py -- <worktree>\tmp\issue139\checktoolbox_out.json <worktree>\tmp\issue139\synthetic_cube.fbx
```

stdout (tail):

```text
Add-on not loaded: "CheckToolBox_v1_5", cause: No module named 'CheckToolBox_v1_5'
Blender 5.1.2 (hash ec6e62d40fa9 built 2026-05-19 01:37:34)
Blender quit
```

stderr (tail):

```text
  File "<frozen importlib._bootstrap>", line 1387, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1360, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1310, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 488, in _call_with_frames_removed
  File "<frozen importlib._bootstrap>", line 1387, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1360, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1310, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 488, in _call_with_frames_removed
  File "<frozen importlib._bootstrap>", line 1387, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1360, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1324, in _find_and_load_unlocked
ModuleNotFoundError: No module named 'CheckToolBox_v1_5'
```

### Run 10: acad_dcc_batch_ping

AutoCAD 2025 core console ping through the shared wrapper.

- Exit code: 0; seconds: 4.306; timed out: False
- Command:

```text
%USERPROFILE%\.hermes\installs\691045f046226667\environments\ef7b1d93bfce4ddfaf1869f05dd9ed09\venv\Scripts\python.exe %USERPROFILE%\hermes_kanban\scripts\dcc_batch.py acad --ping --timeout 120 --wait 0
```

stdout (tail):

```text
{"status": "ok", "exit_code": 0, "seconds": 4.0, "warnings": []}
ping line(s): AGR_PING acad=25.0"AGR_PING acad=25.0"
log (tail):
C:\Program Files\Autodesk\AutoCAD 2025\accoreconsole.exe
Current Directory: %USERPROFILE%\AppData\Local\Temp\agr-autocad-t_21b721ee
Version Number: V.72.0.0 (UNICODE)
LogFilePath has been set to the working folder.
CoreHeartBeat
Regenerating model.
CoreHeartBeat
**** System Variable Changed ****
1 of the monitored system variables has changed from the preferred value. Use SYSVARMONITOR command to view changes.
AutoCAD menu utilities loaded.
Command:
Command:
Command:
Command: (princ (strcat "AGR_PING acad=" (getvar "ACADVER")))
AGR_PING acad=25.0"AGR_PING acad=25.0"
```

### Run 11: max_dcc_batch_ping

3ds Max 2026 batch ping. Ping value returned, but the startup script `polyunwrapper_autoload.mse` raised a .NET error and the native exit code is non-zero.

- Exit code: 0; seconds: 120.212; timed out: False
- Command:

```text
%USERPROFILE%\.hermes\installs\691045f046226667\environments\ef7b1d93bfce4ddfaf1869f05dd9ed09\venv\Scripts\python.exe %USERPROFILE%\hermes_kanban\scripts\dcc_batch.py max --ping --timeout 180 --wait 0
```

stdout (tail):

```text
{"status": "ok", "exit_code": 4294967166, "seconds": 119.9, "warnings": ["15.10.2026 17:59:12;  MAXScript Auto-load Script Error Exception: -- Runtime error: .NET runtime exception: Common Language Runtime detected an invalid program.; Error occurred in anonymous codeblock; filename: C:\\Users\\artsafro\\AppData\\Local\\Autodesk\\3dsMax\\2026 - 64bit\\ENU\\scripts\\startup\\polyunwr"]}
ping line(s): AGR_PING max=28000
log (tail):
-- PhysXPluginMfx Security Tool 1.3 disabled.
-- CRP Security Tool 1.1 disabled.
-- ADSL Security Tool 1.1 disabled.
--- process output ---
15.10.2026 17:57:42;  3ds Max Install Location: C:\Program Files\Autodesk\3ds Max 2026\
15.10.2026 17:57:42;  3ds Max Executable: 3dsmax.exe
15.10.2026 17:57:42;  Secure Mode: 'OFF'
15.10.2026 17:57:42;  Listener Log File: "%USERPROFILE%\AppData\Local\Temp\agr-3dsmax-t_21b721ee\listener.log"
15.10.2026 17:57:42;  Script command: " -mxs "(filein @\"%USERPROFILE%\AppData\Local\Temp\agr-3dsmax-t_21b721ee\ping.ms\")""
15.10.2026 17:57:47;  Product version: 3ds Max 2026.3 (28.3.0.30732)
15.10.2026 17:57:47;  Data collection and use is 'OFF'. Change your participation anytime in the Help menu of 3ds Max.
15.10.2026 17:58:19;  Initializing Python version: 3.11.12
15.10.2026 17:59:12;  MAXScript Auto-load Script Error Exception: -- Runtime error: .NET runtime exception: Common Language Runtime detected an invalid program.; Error occurred in anonymous codeblock; filename: %USERPROFILE%\AppData\Local\Autodesk\3dsMax\2026 - 64bit\ENU\scripts\startup\polyunwrapper_autoload.mse; position: 840; line: 29 
15.10.2026 17:59:22;  Task Completed with Error(s) - see above
15.10.2026 17:59:22;  3ds Max Shutting Down
```

### Run 12: blender_44_version

Blender 4.4 (the host KPP1 used for CheckToolBox) version print.

- Exit code: 0; seconds: 0.35; timed out: False
- Command:

```text
"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe" --background --factory-startup --version
```

stdout (tail):

```text
	build date: 2025-03-18
	build time: 03:22:03
	build commit date: 2025-03-17
	build commit time: 17:00
	build hash: 05377985c527
	build branch: blender-v4.4-release
	build platform: Windows
	build type: Release
	build c flags: /W3 /w34062 /w34100 /w34115 /w34189 /w35038 /wd4018 /wd4146 /wd4065 /wd4127 /wd4181 /wd4200 /wd4244 /wd4267 /wd4305 /wd4800 /wd4828 /wd4996 /wd4661 /wd4848 /we4013 /we4133 /we4431 /we4033 /DWIN32 /D_WINDOWS /W3 /nologo /J /Gd /MP /bigobj /Zc:inline  -openmp 
	build c++ flags: /W3 /w34062 /w34100 /w34115 /w34189 /w35038 /wd4018 /wd4146 /wd4065 /wd4127 /wd4181 /wd4200 /wd4244 /wd4267 /wd4305 /wd4800 /wd4828 /wd4996 /wd4661 /wd4848 /we4013 /we4133 /we4431 /we4033 /DWIN32 /D_WINDOWS /W3  /EHsc /nologo /J /Gd /MP /EHsc /bigobj /permissive- /Zc:__cplusplus /Zc:inline  -openmp 
	build link flags: /MACHINE:X64  /SUBSYSTEM:CONSOLE /STACK:2097152 /ignore:4049 /ignore:4217 /ignore:4221
	build system: CMake
```

### Run 13: blender_44_addon_probe

CheckToolBox v1.5 add-on found in the Blender 4.4 user profile.

- Exit code: 0; seconds: 1.294; timed out: False
- Command:

```text
"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe" --background --factory-startup --python <worktree>\tmp\issue139\probe_addon.py
```

stdout (tail):

```text
Blender 4.4.0 (hash 05377985c527 built 2025-03-18 03:22:03)
Addon 'CheckToolBox_v1_5' detected. Version: unknown
```

### Run 14: blender_44_qa_checktoolbox_run

KPP1 `jobs/KPP1/scripts/qa_checktoolbox.py` on Blender 4.4 with the synthetic cube: faces 6, doubles 0, intersect_faces 0.

- Exit code: 0; seconds: 1.941; timed out: False
- Command:

```text
"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe" --background --factory-startup --python-exit-code 1 --python <worktree>\jobs\KPP1\scripts\qa_checktoolbox.py -- <worktree>\tmp\issue139\legacy_checktoolbox.json <worktree>\tmp\issue139\synthetic_cube.fbx
```

stdout (tail):

```text
FBX version: 7400
CTB synthetic_cube.fbx:Synthetic_Cube {'faces': 6, 'doubles': 0, 'intersect_faces': 0}
Blender 4.4.0 (hash 05377985c527 built 2025-03-18 03:22:03)
Blender quit
```

### Run 15: pymupdf_installed_version

Version query.

- Exit code: 0; seconds: 0.34; timed out: False
- Command:

```text
%USERPROFILE%\AppData\Local\Programs\Python\Python313\Scripts\uv.EXE run --offline --extra pdf-review --extra cad python -c "import importlib.metadata; print(importlib.metadata.version('pymupdf'))"
```

stdout (tail):

```text
1.28.2
```

### Run 16: ezdxf_installed_version

Version query.

- Exit code: 0; seconds: 0.317; timed out: False
- Command:

```text
%USERPROFILE%\AppData\Local\Programs\Python\Python313\Scripts\uv.EXE run --offline --extra pdf-review --extra cad python -c "import importlib.metadata; print(importlib.metadata.version('ezdxf'))"
```

stdout (tail):

```text
1.4.3
```

### Run 17: pdf_cad_installed_versions

Version query.

- Exit code: 0; seconds: 0.319; timed out: False
- Command:

```text
%USERPROFILE%\AppData\Local\Programs\Python\Python313\Scripts\uv.EXE run --offline --extra pdf-review --extra cad python -c "import importlib.metadata; print('pymupdf=' + importlib.metadata.version('pymupdf'), 'ezdxf=' + importlib.metadata.version('ezdxf'))"
```

stdout (tail):

```text
pymupdf=1.28.2 ezdxf=1.4.3
```

### Run 18: speedtree_mcp_package_version

Version of the `mcp` package in the speedtree-mcp venv.

- Exit code: 0; seconds: 0.28; timed out: False
- Command:

```text
%USERPROFILE%\AppData\Local\CodexMCP\BlenderLab103\venv\Scripts\python.exe -c "import importlib.metadata; print(importlib.metadata.version('mcp'))"
```

stdout (tail):

```text
1.30.0
```

## Helpers

The helper scripts (`pdf.py`, `cad.py`, `speedtree.py`, `make_cube.py`, `probe_addon.py`, `smoke.py`)
lived in the scratch dir and are not part of the repository (the issue forbids new tools).
Each one does exactly what its run note says. `jobs/KPP1/scripts/qa_checktoolbox.py` is the tracked KPP1 script.
