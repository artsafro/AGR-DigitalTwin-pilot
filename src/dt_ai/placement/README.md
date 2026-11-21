# Placement

Контракт расположен в `core/models.py`. Преобразование реальных координат
не реализовано; отсутствие исходной отметки/точки вставки остаётся неизвестным.

## `engine.py` — Flora / MAF on SPOZU points (#316)

Pure numpy / shapely; no DCC, no user files. `place(points, ground_vertices, ground_triangles, library, seed)`
returns one instance per SPOZU point or a `failed` record with its code, plus findings, counts and input hashes.

- Points: `adapters.cad.spozu.PointItem`-shaped dataclasses or dicts (`x, y, z, label, handle, rotation`, ...).
  `label` is the library id, or is mapped through `label_map`.
- Ground: vertices (N x 3, m) + triangles (M x 3); height = topmost hit of a vertical downward ray.
- Library entry: `id`, `kind` (`flora` | `maf`), `bbox_min`, `bbox_max` (local, m); Flora also
  `schedule_height_m`, `schedule_crown_m` (model height / crown come from the bbox); MAF also `bottom_faces`
  (local polygons, `[]` when none) and optional `spec_dims_m` (L, W, H; deviation > 0.10 m reported [D094]).
- Instance: `handle, library_id, kind, pivot_x/y/z` (= point XY, Ground z), `rot_z_deg, scale, ground_z, sink_m`,
  `anchor_local` (local point placed on the pivot) and `matrix` (row-major 4x4, local -> world). MAF instances
  carry `bottom_faces` with `delete | review`, reasons and the minimal Ground-over-face gap.
- Flora [D100]: random rotation in [0, 360) and scale in [0.9, 1.1] narrowed to the schedule band +-20 % [D099],
  derived from sha256(seed, handle); the point rotation is ignored. MAF [D095]: rotation = DXF INSERT rotation,
  degrees counter-clockwise; scale 1.
- Status `fail` on any failed point or broken input (seed, Ground, library) [D108]; `review` on bottom faces
  to review or warnings; otherwise `pass`. `report_json` gives byte-identical output for the same inputs.

## `vpm_readback.py` — NPM -> VPM placement readback (#1731)

Pure gate of the VPM assembly step, run before the VPM export: every placed MAF / Flora instance's VPM world
position must equal its accepted NPM position minus the package pivot [D018], deviation strictly below
`TOL_M` = 1 cm (exactly 1 cm fails). `check` takes a labelled scene (`{handle: position}`); `check_points`
an unlabelled one (loose-part centres of the joined VPM Ground; each scene point matches one handle at most,
unmatched Ground parts are counted). Offenders carry a diagnosis: `pivot subtracted twice`,
`pivot not subtracted`, `off`, `missing in scene`. Empty input, non-finite values, a bad pivot / tolerance,
duplicate or extra handles fail. Rotation and SPOZU placement are out of scope.

Blender reader / pre-export hook: `tools/blender/vpm_placement_readback.py` (`check_before_export`, CLI modes
`objects` and `parts`). It calls `view_layer.update()` before every read: `matrix_world` is the identity right
after a library append, which made Staropetrovskiy VPM v001 subtract the pivot twice.
