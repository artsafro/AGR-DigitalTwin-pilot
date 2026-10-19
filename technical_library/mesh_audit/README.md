# Общая инвентаризация сетки

Одна операция вместо локальных копий basic inventory/readback в Ground, MASHI,
Revit, знаках, mesh optimization и продуктовых Blender-кейсах. Не заменяет
специализированный contour, BVH, CheckToolBox, геометрический fit и AGR Checker.

`core.py` — чистая топология по массивам; `blender.py` — чтение blend/FBX и отчёт.
Входы и выбранные object/collection задаются явно. Отчёт должен быть новым;
сцена не сохраняется, SHA входа проверяется до/после.

```powershell
& <blender.exe> --background --factory-startup --disable-autoexec --python-exit-code 1 --python technical_library/mesh_audit/blender.py -- --source <source.blend> --output <new-report.json> --collection LP
```

Повторяемые `--object`/`--collection` ограничивают набор; совместное использование
даёт пересечение этих фильтров. Без фильтров — все mesh текущей сохранённой сцены.
Извлекаются world XYZ × scene unit scale, polygon-size histogram, компоненты,
границы/multi-face/loose edges, material interfaces, дубли, UV finite/bounds.
Материал — индекс слота, не доказательство реального Max Material ID.

Дубли считаются внутри каждого объекта: rounded vertices (8 decimals), faces
по отсортированным индексам. Fan area пригодна как диагностика нулевой площади,
а не доказательство корректности вогнутых/самопересекающихся ngon. Fan triangles
— счётчик n−2, не evaluated-модификаторы. Не проверяются межобъектные overlaps,
растяжение UV, texel density, сохранение исходного контура, shaders, BVH/визуальный вид.
`delivery_passed=false` всегда: basic inventory не сдача модели.

Each mesh object report includes three topology diagnostic counters that leave
`delivery_passed=false` unchanged:
- `inconsistent_winding_edges`: `twinqa.geometry.winding.same_direction_edges`, shared with the twinqa orientation check. Manifold edges with exactly two loop sides winding in the same direction; sides with a repeated vertex (a == b) are skipped.
- `near_duplicate_vertices`: vertices with an earlier vertex within `--near-m`
  (default 0.001 m, recorded as `near_duplicate_threshold_m`), including exact duplicates.
- `self_intersecting_polygons`: counts polygons exhibiting bounded nondegenerate
  planar proper-crossing semantics (triangles return False directly).

For each face, the classifier uses maximal-triple projection: it enumerates all
unordered vertex triples with `itertools.combinations`, selects the nonzero
cross product of maximum squared magnitude, drops the coordinate with the
largest absolute cross component, and projects the remaining axes to 2D. This
avoids Newell normal cancellation on bowtie polygons and first-triple collinearity.

For each unordered pair of boundary edges, adjacent pairs sharing endpoints
(including wraparound) are excluded. A proper crossing is registered when
segment endpoints have strictly opposite orientations beyond a +/-1e-10 m² strict
tolerance in square metres for both segments. The polygon count is incremented
at the first proper crossing found (counting each self-intersecting polygon once
rather than counting intersection pairs).

Collinear-only compatibility: collinear-only faces return False (no projection
performed) and do not raise new exceptions; the companion `zero_area_faces_fan`
diagnostic is preserved and this zero return is not a clean-certification claim.

Planarity is NOT validated, and zero diagnostic flags do NOT certify a mesh as
valid, clean, or delivery-ready.

Unsupported scope: collinear overlap, nonadjacent touch, repeated vertices,
nonplanar faces, mesh-to-mesh intersections, and general 3D intersections are
not supported.

The report retains report-only flags (`intersection_test_performed=false`,
`delivery_passed=false`) with explicit no delivery certification and no
production speedup claim. For background hypothesis and validation rationale,
see [docs/experiments/hyp-91.md](../../docs/experiments/hyp-91.md).

[REPLAY.json](REPLAY.json): 9 запусков Blender4.4 на фактических сохранённых
blend/FBX, SHA всех входов неизменны. Ground blend и FBX: 33103 vertices /
32392 quads / 18 slots; ранее допустимые исходные overlaps сохранены. MASHI:
605194 faces / 615536 triangles, LP/Revit/LP_old не переименованы. Знаки:
8 mesh / 1144 faces. Остальные файлы — readback, не повторная визуальная приёмка.

Исходные версии/происхождение: [SOURCE.json](SOURCE.json), [реестр](../SOURCE_COVERAGE.jsonl) и [группы](../GROUP_REVIEW.md).
Blender API сверено через Context7 `/websites/blender_api_4_2`: raw meshes,
UV loops; фактический runtime4.4. Общие синтетические edge/duplicate/component
fixtures в tests/test_shared_library.py не заменяют реальные DCC-прогоны.
