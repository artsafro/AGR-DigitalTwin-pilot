# Research: `bpy` wheel as a Blender-free native test lane — go / no-go

Card: t_3772ef12 (research, no GitHub issue). Date: 2026-10-15. All fixture data is SYNTHETIC.

## Summary

- **Verdict: conditional GO** as an *additional* lane for bpy-only scripts on hosts without
  `blender.exe` (CI, a second machine). **NO-GO** as a replacement for `blender.exe` on this
  workstation and **NO-GO** inside the repo's own environment.
- The wheel matching the baseline exists: `bpy==5.1.2`, `cp313-win_amd64`, 350.2 MB download,
  `Requires-Python ==3.13.*`, `numpy>=2.2,<3.0` [1][2]. Cold install 48 s, warm 1.3 s; 712 MB unpacked
  `bpy` package, 769 MB venv, ~777 MB uv cache (measured).
- It cannot join the repo venv: the repo `.venv` runs Python 3.14.7 (measured), the wheel is 3.13-only.
  It must live in a separate `uv venv -p 3.13`.
- NumPy: the wheel ran with the repo's pin `numpy==2.5.3`; `blender.exe` 5.1.2 bundles numpy 2.3.4 (measured).
- Fixture (cube via `bpy.data` + `bmesh`, FBX export + re-import): `export_scene.fbx` / `import_scene.fbx`
  present and `io_scene_fbx` enabled out of the box; vertices 8, faces 6, triangles 12, UV layer, sorted
  face normals, vertex coordinates and object transform are **identical** to the same script under
  `blender.exe --background --factory-startup` (measured). FBX files are 12 252 bytes each and differ in
  26 bytes (creation timestamp region).
- Two existing repo scripts run unchanged under the wheel and give byte-identical JSON to `blender.exe`:
  `tools/blender/fbx_readback.py` and `tests/dcc/connect_readback.py` (measured).
- No speed win on this machine: wheel 0.7–1.6 s per script (import alone 1.1 s cold), `blender.exe`
  0.9–1.1 s (single runs, n=1).

## Method (what was run)

Everything ran outside the repo dependency graph, in `C:/x/t_3772ef12/` (card scratch); no change to
`pyproject.toml`, `uv.lock` or `src/`. Blender was run only headless with `--factory-startup`; the user's
open Blender session was not touched.

```text
uv venv -p 3.13 venv                          # uv-managed CPython 3.13.3
uv pip install -p venv/Scripts/python.exe bpy==5.1.2 numpy==2.5.3   (UV_CACHE_DIR=<scratch>/uvcache)
venv/Scripts/python.exe fixture.py <out_wheel>
"C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" --background --factory-startup \
    --disable-autoexec --python-exit-code 1 --python fixture.py -- <out_exe>
# repo scripts, same FBX / same args, wheel vs exe:
venv/Scripts/python.exe tools/blender/fbx_readback.py -- <fbx> <json>
venv/Scripts/python.exe tests/dcc/connect_readback.py -- <dir>     (after `uv pip install -e .` into the scratch venv)
```

`fixture.py` (scratch, not committed): `read_factory_settings(use_empty=True)`; `bmesh.ops.create_cube(size=2)`
+ `recalc_face_normals`; `mesh.uv_layers.new("UVMap")`; object at (1, 2, 3); `export_scene.fbx(use_selection=True,
apply_unit_scale=True, axis_forward="-Z", axis_up="Y", mesh_smooth_type="FACE")`; reset; `import_scene.fbx`;
compare counts, sorted rounded (1e-4) face normals and vertex coordinates, location/rotation/scale.

## Findings

### F1. Available versions and size (source + verified)

PyPI lists `bpy` 4.4.0–5.2.2; latest is 5.2.2 [1]. 4.x and 5.0.x wheels are `cp311`; 5.1.0 onward are
`cp313` [1]. `bpy 5.1.2` (uploaded 2026-05-19, same build date as the installed `blender.exe` 5.1.2)
declares `requires_python ==3.13.*` and `requires_dist = cattrs, cython, numpy<3.0,>=2.2, requests,
zstandard` [2]. Sizes for 5.1.2: win_amd64 350.2 MB, manylinux_2_28_x86_64 390.9 MB, macOS arm64
238.5 MB, win_arm64 205.6 MB [1]. Verified by reading the PyPI JSON with a script.

### F2. Install cost (verified)

| Metric | Value |
|---|---|
| Cold install (download + unpack, 12 packages) | 48 s |
| Warm install from uv cache into a fresh venv | 1.26 s |
| `site-packages/bpy` | 712 MB |
| Whole venv | 769 MB |
| uv cache after install | ~777 MB |
| Python used | CPython 3.13.3 (uv-managed); `blender.exe` 5.1.2 embeds 3.13.9 |

### F3. NumPy compatibility (verified)

The wheel accepts any numpy `>=2.2,<3.0` [2]. Installed together with the repo's pinned `numpy==2.5.3`
(`pyproject.toml`, `uv.lock`), `import bpy, numpy` and the full fixture worked. `blender.exe` 5.1.2 uses
its bundled numpy 2.3.4 from `Blender 5.1/5.1/python/Lib/site-packages`. So a wheel lane tests repo code
against numpy 2.5.3, while production `blender.exe` runs it against 2.3.4 — a real difference to keep in
mind for numpy-heavy code such as `dt_ai.geometry.connect`.

### F4. FBX operator availability (verified, not assumed)

In the wheel: `hasattr(bpy.ops.export_scene, "fbx")` = True, `hasattr(bpy.ops.import_scene, "fbx")` =
True, `addon_utils.check("io_scene_fbx")` = (True, True), still True after
`read_factory_settings(use_empty=True)`. Same values under `blender.exe`. Exporter header in both files:
`Blender (stable FBX IO) - 5.1.2 - 5.15.0`, FBX version 7400.

### F5. Fixture parity: wheel vs `blender.exe` (verified)

| Check | wheel | blender.exe |
|---|---|---|
| export / import result | FINISHED / FINISHED | FINISHED / FINISHED |
| source vertices / faces / triangles | 8 / 6 / 12 | 8 / 6 / 12 |
| re-import vertices / faces / triangles | 8 / 6 / 12 | 8 / 6 / 12 |
| UV layers after re-import | `UVMap` | `UVMap` |
| sorted face normals (1e-4) | equal to source, equal across lanes | same |
| vertex coordinates (1e-4) | equal across lanes | same |
| re-import location / rotation / scale | (1,2,3) / (0,0,0) / (1,1,1) | same |
| FBX size | 12 252 B | 12 252 B |
| FBX byte diff | 26 bytes differ, first at offsets 340/369 inside `CreationTimeStamp` | — |
| wall time, fixture script | 1.62 s (import bpy 1.15 s, cold) | 1.05 s (whole process) |

Not checked: whether all 26 differing bytes are timestamp fields (only the first offsets were
inspected); larger meshes, materials, multiple UV sets, custom normals, animation.

### F6. Existing repo scripts run unchanged (verified)

- `tools/blender/fbx_readback.py` (used by `src/twinqa/scene.py` via `READBACK`) on the same FBX:
  output JSON byte-identical between lanes; wheel 0.71 s, `blender.exe` 0.93 s.
- `tests/dcc/connect_readback.py` (imports `dt_ai.geometry.connect` and numpy, saves and reopens a
  `.blend`): output JSON byte-identical; reports 12 vertices / 6 faces, `synthetic_readback_passed: true`.
  The script inserts `src/` into `sys.path` itself; the editable install into the scratch venv was not
  needed for it (its git-ignored `egg-info` was removed afterwards).
- Both scripts parse `sys.argv` after `--`, which works under plain `python script.py -- args` too.

### F7. Documented limits of the module build (source only)

Blender's manual [3] states: `bpy.app.binary_path` is empty (verified: `''` in the wheel); command-line
arguments are not available (no `--threads`, `--log`, `--python-exit-code`); the module behaves as if
`--factory-startup` was passed and ignores user startup/preferences; signal handlers and crash logs are
not set up; `importlib.reload(bpy)` raises — reset with `read_factory_settings()`; only one blend file per
process, use separate processes for isolation. On load the default scene (cube, camera, light) is present
[3]; the fixture therefore starts with `read_factory_settings(use_empty=True)`.

Consequences for this repo (inference): user add-ons/extensions that the AGR checks rely on (SINTEZ AGR
Checker under `%APPDATA%/Blender Foundation/Blender/4.4/extensions/...`, CheckToolBox) are not part of
the wheel and would need explicit installation into the module; that was not tried.

## How it applies to this repository

- Blender entry points that a wheel lane could serve (all spawn `blender.exe --background --factory-startup
  --python <script> -- args`): `src/twinqa/scene.py` (`find_blender`, `READBACK` =
  `tools/blender/fbx_readback.py`), `src/dt_ai/core/build.py` (`run_blender` → `adapters/blender/bridge.py`),
  `tools/qa/check_clearance.py`, `tools/qa/run_benchmark.py`, `tools/qa/run_from_source.py`.
- Tests skipped when Blender is absent: `tests/qa/test_scene.py`, `tests/qa/test_clearance.py`,
  `tests/qa/test_from_spec.py` (`find_blender() is None`), `tests/integration/test_pipeline.py`
  (`DT_BLENDER`). On a host without Blender these are exactly the tests a wheel lane could un-skip.
- Environment constraint: repo `.venv` is Python 3.14.7 and `pyproject.toml` says `requires-python >=3.12`;
  the wheel needs exactly 3.13. A wheel lane = separate 3.13 venv (+ `uv pip install -e .` if a script
  imports `dt_ai`/`twinqa` without its own `sys.path` insert), launched as a subprocess the same way as
  `blender.exe` — the repo already runs Blender work out-of-process, so swapping the executable is the
  smallest change (`<venv>/python.exe script.py -- args` instead of `blender.exe ... --python script.py -- args`).
- `tests/qa/test_scene.py::test_blender_roundtrip_through_validator` builds its cube with
  `blender.exe ... --python-expr MAKE_CUBE -- <fbx> <variant>`; under the wheel that becomes
  `python -c MAKE_CUBE -- <fbx> <variant>` (argv parsing after `--` must be checked; not run here).
- `--python-exit-code 1` has no equivalent; plain `python` already returns non-zero on an uncaught
  exception, so the existing scripts' failure semantics are preserved (inference; failure path not tested).
- CI: `.github/workflows/python-app.yml` runs on `ubuntu-latest` with Python 3.10; a wheel job would need
  its own 3.13 step and ~391 MB manylinux download per cold run [1]. Seen, not mine: the CI Python 3.10
  is below the project's `requires-python >=3.12`.
- `docs/agents/CAPABILITIES.md` lists Blender 4.4 and 5.1.2; no `bpy` wheel entry. Per AGENTS.md a tool
  becomes shared only after it is listed there on `main` — not done in this card.

## Proposed next tasks

1. **Wheel-lane runner for existing Blender scripts** — value M / effort S. Add an opt-in executor (env
   var such as `TWINQA_BPY_PYTHON=<3.13 venv python>`) next to `find_blender()` in `src/twinqa/scene.py`
   that runs `tools/blender/fbx_readback.py` as `python script -- args`; keep `blender.exe` the default.
   Acceptance: `tests/qa/test_scene.py` passes in both lanes on the synthetic etalon, outputs identical.
2. **Parity check on benchmark etalons** — value M / effort S. `benchmark/bench-*/` hold specs, not FBX
   files; take the etalon FBX/blend files that `tools/qa/run_benchmark.py --etalon ...` consumes, run
   `fbx_readback.py` / `measure_spec_blender.py` through both lanes and diff the JSON; record differences (expected none for the
   same 5.1.2 build). Gives the evidence base for trusting the wheel on real-size meshes, materials and
   multiple UV sets, which this card did not cover.
3. **Linux CI job with the manylinux wheel** — value M / effort M. Separate workflow job on Python 3.13
   with cached `bpy==5.1.2`, running only the Blender-dependent synthetic tests (items above).
   Needs the user's decision on CI scope and cache size (~0.8 GB).
4. **Version-pin policy `bpy` ↔ `blender.exe`** — value S / effort S. One line in
   `docs/agents/CAPABILITIES.md`: the wheel version must equal the baseline Blender version (5.1.2 now;
   PyPI already has 5.2.2), and the lane is re-verified on each Blender upgrade.

## Open questions for the user

1. Is a Blender-free lane needed at all on this workstation (where `blender.exe` 5.1.2 is installed and
   just as fast), or only for CI / other machines? This decides between "document and stop" and tasks 1–3.
2. Is ~0.8 GB disk (venv + cache) per machine/CI cache acceptable?
3. Should the wheel stay pinned to the Blender baseline (5.1.2) even though PyPI offers 5.2.2?
4. The AGR checker extensions are not in the wheel: should the lane stay limited to geometry/readback
   scripts, or should installing extensions into the module be researched?
5. Note on scope: the card policy says "do not run Blender", the card body asks for a headless
   `blender.exe --background --factory-startup` comparison; the body was followed (headless only). Confirm
   this is acceptable for future research cards.

## Sources

1. PyPI JSON, all releases of `bpy`: https://pypi.org/pypi/bpy/json (read 2026-10-15 by script)
2. PyPI JSON, `bpy 5.1.2`: https://pypi.org/pypi/bpy/5.1.2/json (read 2026-10-15 by script)
3. Blender Python API manual, "Blender as a Python Module":
   https://docs.blender.org/api/current/info_advanced_blender_as_bpy.html
