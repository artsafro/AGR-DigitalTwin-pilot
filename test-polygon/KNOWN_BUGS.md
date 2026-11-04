# Known AGR Tools bugs seen by the test polygon

The polygon is not changed to hide these. `expected/` still states the contract.
`known_bug` on the row records the live result. A live match is not a mismatch and is not OK:
the table prints `НЕ OK (известная ошибка #886)`, and `report.json` counts those rows in `known_bug`.
The process exit code stays the mismatch count. Do not fix the tool in this folder.

## census-usedmaps-drops-missing-file

- button: `scene.census` and `qa.preflight` (preflight includes the census finding)
- object: `SM_Polygon_007_Main` in `polygon_all`
- expected: `scene.census` fail `missing_map`; `qa.preflight` fail `fbx_objects`, `missing_map`
- got: `scene.census` pass (no findings); `qa.preflight` fail `fbx_objects` only
- evidence: Max 2024 and Max 2026 (`C:/x/test-polygon/run2024`, `run2026`), both mismatch count 0 only because this `known_bug` matches the live pass. The polygon assigned `Bitmaptexture fileName:"C:/x/test-polygon/missing/T_Polygon_007_Main_d_1.png"` (file absent). `tex.check` on the same node returned `tex_missing` / `material has no texture maps`, the empty `usedMaps` result (same witness as `tests/max_tools/run_agr_tools_checks_native.py`, defect D3). `scene.census` only flags paths `usedMaps` returns, so a bitmap Max will not list never becomes `missing_map`. `suite_max._materials` is the reader.
