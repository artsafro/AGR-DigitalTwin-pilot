# Known AGR Tools bugs seen by the test polygon

The polygon is not changed to hide these. `expected/` still states the contract.
`known_bug` on the row records the live result. A live match is not a mismatch and is not OK:
the table prints `НЕ OK (известная ошибка #886)`, and `report.json` counts those rows in `known_bug`.
The process exit code stays the mismatch count. Do not fix the tool in this folder.

No open entries.

## Closed

- `census-usedmaps-drops-missing-file` (#886, closed in #979 branch E3): `scene.census` / `qa.preflight` on
  `SM_Polygon_007_Main` (a `Bitmaptexture` whose file is absent) gave no `missing_map`, because `usedMaps` drops such a
  bitmap. The census glue (`suite_max._shared_maps`) now also reads the shared bitmap enumerator of `tex_max`
  (`_scene_maps`: materials of the nodes, scene materials, AssetManager), and `suite_max._bitmap_paths` (#886) walks
  the texmap tree; the row is fail `missing_map` live (Max 2024 job of #979 E3), no `known_bug`.
