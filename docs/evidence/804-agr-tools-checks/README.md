# #804 AGR Tools 0.5.0 — native evidence (synthetic)

All scenes are disposable synthetic fixtures built by `tests/max_tools/run_agr_tools_checks_native.py`
inside the batch document. No production asset is opened. FBX paths (`C:/o/...`) are only
`AGR_EXPORT_PATH` user-property values; nothing is exported.

## Package

- `python tools/max/build_agr_tools.py tmp/AGR-Tools-0.5.0-final.mzp` gives
  SHA256 `eed7181977429261443cc48f9657b6de2ab378c9569ffac09706870d7afe3d33`. This is the same
  byte-identical package as the natively tested `-r2` build (the builder is reproducible).
- The MZP is not committed (no Git LFS). Rebuild it with the command above.

## Runs (shared lock, `dcc_batch.py max --version <v> --card t_d01d4740`)

| Max | Wrapper | Native exit | Seconds | Markers |
| --- | --- | --- | --- | --- |
| 2024.2.5 (Python 3.10.14) | ok | 0 | 58.8 | NAMES, TRIS, TEXTURES, PIVOT, GEOJSON, COMPLETE |
| 2026.3 (28.3.0.30732, Python 3.11.12) | ok | 4294967166 | 49.5 | NAMES, TRIS, TEXTURES, PIVOT, GEOJSON, COMPLETE |
| 2024.2.5, r4 (review r1 fix) | ok | 0 | 38.1 | + TEXTURES_ATLAS, COMPLETE |
| 2026.3, r4 (review r1 fix) | ok | 4294967166 | 40.4 | + TEXTURES_ATLAS, COMPLETE |

Run r4 uses the package built at commit `bd282efb`: `tools/max/build_agr_tools.py` gives SHA256
`7ab03ac037edefd31e070c2443f5576f497677f6a053af669a9757d79613d946` (printed in-Max as
`AGR_PACKAGE_SHA256`). The r2 SHA256 above belongs to the pre-review package.

The Max 2026 exit code comes from a pre-existing startup CLR error in `polyunwrapper_autoload.mse`,
not from the fixture. The same error is in #707 and #722. The completion marker is printed after the
results file is created exclusively.

Run r1 (Max 2024) found a real defect: the macro path raised `KeyError: 'agr_tools_runtime'`
because `bootstrap.py` does not register the runtime module in `sys.modules`. It was fixed
test-first (`test_checks_050_works_when_loaded_like_bootstrap`, RED then GREEN) before r2.

## What each run asserts

- Names: slot-2 material legal (D4); `MainGlass` and `UCX_*_Ground_*` are not taken as Main or
  Ground (D2); a planted bad name gets `name_case`, `name_suffix` and `name_type`; no FBX path gives
  `fbx_unmapped`.
- Triangles: per-FBX sums 150 000 (`tri_at_limit`), 150 012 (`tri_limit`) and 170 000 Ground
  (pass). GeoAGR summed the selection to 470 012 and would have failed the Ground FBX (D8).
- Textures: the first object's 1000 px map is reported (D1). An empty `usedMaps` array gives
  `tex_missing`, and glass without maps is dropped with a reason (D3). A missing file gives
  `tex_missing`. A UV gap of 10 px at 2048 gives `tex_padding`; a 20 px gap passes (16 px rule).
- Textures per atlas (review r1): a two-slot Multimaterial object whose two islands cover the
  same UV square in two different atlases gives `[]` (r1 pooled them: false `tex_padding`); two
  objects of one FBX sharing one atlas with touching islands both get `tex_padding` (r1: silent
  `[]`), with nothing dropped.
- Pivot: Z 0.05 m gives `pivot_z` + `pivot_mismatch`, and UCX is dropped with a reason. With
  centimetre system units the same 0.05 units are 0.5 mm, which passes, so units are respected.
- Macros `AGRToolsNames/Tris/Textures/Pivot` run as buttons and select offenders.
  `AGRToolsGeojson` is registered; its file dialog is not opened in batch.
- GeoJSON: broken JSON, `{}`, a missing file, a wrong extension and an empty path all give `fail`
  findings from `twinqa.geojson` or the guard, with no exception.
- Read-only: a state digest is taken before and after every check and macro and is unchanged. It
  covers handle, name, class, triangle count, transform, pivot, material, user properties and
  modifier count.

Files: `max<v>-native-log.txt` and `max<v>-native-log-r4.txt` (marker lines), `max<v>-report-excerpt.json` (JSON report excerpt
per button), `SHA256SUMS.txt`.
