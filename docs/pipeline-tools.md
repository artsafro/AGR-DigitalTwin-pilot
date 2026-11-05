# Pipeline tool catalogue

Details of the shared pipeline and delivery-QA tools: status, command line, exit codes, limits. The one-line
registry that makes a tool shared is `docs/agents/CAPABILITIES.md`, "Shared tools"; production stages and their
status: `docs/pipeline.md`.

## Pipeline core (src/dt_ai, technical_library, tools)

Environment and test commands: `docs/agents/agents-reference.md`.

### `dt` CLI — `src/dt_ai/`
- Status: WORKING on the synthetic job (`jobs/SYNTH-001`): `dt profiles check`, `dt schemas --check`,
  `dt build`, `dt validate`, `dt index-pdf`, `dt registry merge`. Real-object use goes through the
  accepted-case tools below. `passed` is always false in this version.
- Geometry adapters (Exterior, Shell, Connect) with `AdapterReport` and Blender readback:
  proven on Obr22 (`docs/cases.md`). RunRecord inspection: `tools/harness_status.py`
  (skill `run-evidence`).

### Spec extractor — `tools/source/measure_spec_blender.py` + `dt spec extract` / `dt spec merge-questions`
- Status: WORKING on synthetic data (Claude, 2026-10-08; issues #5, #16, #6, #7): Blender 5.1 dumps
  triangles and `LEVEL_<name>` helpers; `dt spec extract --dump --object --output` writes spec v0.1
  (`schemas/Spec.schema.json`), a report and `<spec>.questions.md`. Levels are input; roof confirmed at
  the top input level; strict full-height level contour (`contour_at_m` in object.json when it asks);
  kinks, rounded corners; typical floors written once (`typical_of` / `repeat_to`, `Spec.expanded_floors()`); openings from holes in the body or glass panes (`source`); door recesses from the floor are openings (`kind` door, or window when glass fills the height), relief <= 10 cm is no kink, panes of one frame are one opening with `panes`, an opening across a level is one record with `level_from` / `level_to` (spec v0.2, #31). Spec v0.3 (#36): opening = hole with frame (mesh: the reveal; Revit: frame or curtain wall, else the family box), glass as `glass_w` / `glass_h`, `depth_m` only as an exception. Vent grilles are openings of kind `grille` (Revit: window elements without a transparent material). `dt spec extract --tolerances` reads the `spec_extract` thresholds.
  `dt spec merge-questions --report --version --into jobs/<object>/questions.md` keeps one questions
  list per object with stable ids and kept answers.
- Limits: `window_type` is always null (no material ids in the dump; window library #4); no
  attachments; roofs: drainage slopes up to 10° are one roof
  (area-weighted height, ±10 cm), separate roof parts and caps are read (#9); steeper roofs are a question.
  First real run: KPP1 v005 spec v001 (`jobs/KPP1/STATE.md`). `object.json` may give `frames` per source. Pattern: `docs/domain/patterns/wall-from-contour.md`.
- Revit path, wall lines (Claude, 2026-10-08, #29; the bounding-box route of #10 was removed after it):
  `node tools/source/measure_spec_revit_twin.mjs <new-folder>` calls the TwinPack commands of the
  revit-http add-in (`twin_floor_manifest`, `twin_export_floor` with every wall function; not in the MCP
  tool list, called through `revitClient.callRevit`), writes `floor.json` + `reference.obj` per band and
  `twin-data.json` (with the document's Levels and Roofs since MH2: `list_levels`, `list_elements` OST_Roofs,
  `get_element_info`; object.json `revit_levels` turns them into LEVEL_ helpers, `src/dt_ai/spec/markup.py`); `dt spec extract --dump <twin-data.json>` reads it (`dt_ai.spec.revit_twin`): walls as
  prisms on their location lines (any angle; curved walls from their real geometry), glass by material
  transparency, doors from records, attachments by the main-walls hull rule (user decision 2026-10-08 [D027]). The
  document is not modified (flag checked before and after); files go only to the new folder.
  KPP1: contours equal to the mesh path (0.0 mm), `jobs/KPP1/spec-compare-v002.md`.
- Intake check (Claude, 2026-10-11, IN1, historical archive/2026-11:docs/HARNESS_PLAN.md §15): `dt intake check --dir jobs/<JOB>/intake` validates
  `sources.json` / `spec-draft.json` (schemas `IntakeSources`, `IntakeSpecDraft`), `picture.md` (Facts and
  Contradictions tables) and `questions.md`: sources and confidence of every fact, null = unknown, images at
  most estimated, the primary source by priority, the scale anchor; reports `buildable`. Procedure: skill
  `analyze-architectural-source`, intake mode. Adapters per format: IN2-IN7.
- Spec comparison (Claude, 2026-10-08, #11): `dt spec compare --a <spec> --b <spec> --tolerances
  benchmark/<id>/tolerances.json --output <cmp.json>` (+ `.md`): rows per criterion of historical archive/2026-11:docs/HARNESS_PLAN.md §4
  with both values, threshold and reference side, contour difference regions; thresholds, reference
  sides and whether a verdict is given come from tolerances.json. KPP1: `jobs/KPP1/spec-compare-v001.md`.

### Window type list — `library/windows/window_types.json` (#4)
- Status: WORKING (Claude, 2026-10-09): 46 entries; 37 confirmed and named by the user (W01–W07, D01–D03, KPP1-W01–W03,
  WT-01–WT-24; `library/windows/confirmations.json`), the rest `unconfirmed`; 24 from `Win_Typical.max` (WT-01–WT-24, read from 3ds Max
  without changes into `library/windows/sources/win-typical-max-v001.json`; duplicates by subdivision + size ±2 cm get
  `same_as`) — SOSH1150
  typology v003 (11 types, 6 size variants; CW_021, CW_022, D04 kept as not typed) and 3 KPP1 candidates from the
  Revit spec. Rebuilt by `tools/library/build_window_types.py` from the user's library files (read only); handing
  null, sashes not in the sources. The spec's `window_type` index waits for confirmed entries.

### Operation library — `technical_library/`
- Status: WORKING per package README (Russian): `glb_atlas`, `uv_continuous` (UV v006),
  `window_atlas`, `texture_tiles`, `mesh_audit`. Scope of each = its accepted case.

### Album page reader — `src/dt_ai/album/` (#317, kernel C5; D127)
- Status: on `main` (from `improve/issue-317-kernel-c5-vector-pdf-album-reader-axes-d`, Hermes dt-worker, 2026-10-19),
  validated on SYNTHETIC PDFs generated at test time only (`dt_ai.album.synthetic`), no real album yet.
- Use: `uv run --extra pdf-review python -c "from dt_ai.album import read_page, reading_to_json; print(reading_to_json(read_page('sheet.pdf', 1)))"`.
  One vector page -> paths, segments, text runs, axes, horizontal dimensions, level marks, legend (swatch RGB + label),
  scale from one axis dimension (`scale_axes=("1","2")` or the left-most), `dimension_mismatch` / `level_mismatch`
  findings; deterministic JSON with sha256, page number and PyMuPDF version.
- Limits: fail-closed statuses `not_vector` / `no_text_layer` / `empty`, scale `unknown` without an axis dimension;
  vertical dimension chains, OCR, PDFIMPORT fallback and multi-page indexing are not covered.

## Delivery QA (tools/qa, src/twinqa, standards/)

### Standards layer — `standards/`
- Status: WORKING (2026-10-06; loader tests). One loader for both packages: `twinqa.profiles`.
- NPM/VPM profiles, validator spec V001-V017, 232-rule traceability, SHA-256 lock, regulation PDF
  (plain Git blob). Fields touched by `docs/domain/conflicts.md` carry `conflicts:` entries; checks
  report them as review. Machine-readable twin of `docs/domain/`.

### Package validator — `tools/qa/validate_package.py`
- Status: WORKING for archive composition, names, FBX header, VPM maps, UDIM sequence, GeoJSON
  (V001, V002 header, V007, V008 sequence, V011, V012); `--scene` adds V003/V004/V006/V008/V013 via
  Blender. Everything else is `not_run`; V015-V017 are manual.
- `py -3 tools/qa/validate_package.py <zip|fbx|geojson> [--profile npm|vpm] [--json] [--scene]`;
  exit 0 passed / 1 fail / 2 review or not_run left.
- Not yet: NPM embedded-atlas pixel rules (PNG bytes inside FBX), units, UCX (V010), texel density
  (V009), coordinates vs MSK-77 (V013/V014).

### FBX readback — `tools/blender/fbx_readback.py`
- Status: WORKING (2026-10-06; Blender 4.4 and 5.1 background, cube roundtrip tests)
- Triangles, polygon degrees, UV channels, UDIM tiles, mirrored UV, transforms, embedded images.

### UCX builder — `src/dt_ai/geometry/ucx_build.py`, `tools/blender/ucx_build.py`
- Status: TOOL ONLY (2026-10-19, #166): Main measured on 4 etalon meshes (KPP1, PSU275, Skolkovo, Mashi),
  Ground on synthetic surfaces only (`tests/test_ucx_build.py`); no real-object delivery acceptance.
- `blender --background --factory-startup --python-exit-code 1 --python tools/blender/ucx_build.py --
  <model.fbx|.blend> <out.fbx> <Main|Ground> [cell= gap= with=<obj,...>]`; exit 0 built / 3 Ground over
  `tol` (one-sided vertical deviation or uncovered strip; reverse footprint overhang is diagnostic [D134]) / 2 failed (incl. a missing `with=` name, a UCX
  that names no model object) / 4 refused (output aliases input). Replaces only the UCX of the input
  objects; other targets' UCX are kept and their triangles are reserved from the whole-file [D012]
  budget (kept + new over the limit -> exit 2, no FBX). Job scripts: `build_into_scene(...)`, pass
  `reserved_triangles=` for UCX already in the file.
- Facade-oriented 8-vertex boxes (Main) or quadtree hexahedra (Ground), 4 mm gap, [D012] budget; check
  the output with `tools/blender/ucx_audit.py` and the validator scene checks.

### Methods catalog runner — `tools/methods/run_variant.py`, `tools/methods/ucx/run_benchmarks.py` (#706)
- Status: WORKING (dt-worker, 2026-10-25): 18 measured ucx-collisions rows on KPP1 / AC08 / TOW02
  (`docs/methods/ucx-collisions/results.jsonl`); tests `tests/methods/test_methods_catalog.py` (+1 `-m blender`).
- `uv run python tools/methods/run_variant.py <out.fbx|.zip> --bench <id> --class <class> --variant <name>
  [--variant-report <out>.variant.json] [--render view=png ...]`: one JSON row (wall time, triangles, objects,
  xView 2 mm / 5 mm, UCX V010 + V012, texel min / median, file size, MatID slots, SSIM or null, class metrics);
  exit 0 appended / 2 measurement error / 4 refused. RESULTS.md: `tools/methods/results_md.py`.
- Benchmark set: `benchmark/methods/benchmarks.json` (private sources by sha256 under `C:/x/methods/src`).
  Catalog: `docs/methods/README.md`.

### Overlap gate (xView parity) — `dt qa xview`, `src/dt_ai/ops/inv_xview.py`, `src/dt_ai/ops/xview_gate.py` (#527)
- Status: WORKING (dt-worker, 2026-10-21; #370 / #380 kernel, #527 CLI). `inv_xview` reproduces 3ds Max xView
  Overlapping Vertices (2 mm) / Overlapping Faces (5 mm, contact rule) without Max; the `area` rule adds pairs xView misses.
- `uv run dt qa xview <file.fbx|.blend|.npz> --out <new report.json> [--parts NAME ...] [--profile NPM|VPM]
  [--coords local|inplace|as-stored] [--blender <exe>]`. FBX / .blend go through headless Blender 5.1.2
  (`tools/blender/xview_dump.py`, evaluated meshes, float64); default `local` = object location subtracted. Report per
  object: Overlapping Vertices / Faces counts and ids, vertex pairs (`double` / `bowtie`), face pairs with partner,
  kind (contact / area / area+contact), separation and centres, bow-tie (non-manifold) vertices, dropped non-mesh
  objects, input SHA-256, units. Blender units become metres via `scene.unit_settings.scale_length` (a missing,
  non-positive or non-finite scale, or system NONE with scale != 1, is an error). Report and `<report>.blender.log`
  are published no-clobber: a file created at either name by another writer is kept and the run exits 2.
  Exit 0 pass, 1 overlaps, 2 error (no verdict).
- Measured on vyatskaya-tow02 (review #514): ours export-v005 185 faces (= xView ids 1:1, centres <= 0.50 mm) and
  0 vertices, ~35 s; user FBX `_05` object 013: 0 faces, 10 vertices = 5 coincident pairs, all `bowtie`, local and
  in place. Postcondition of every build / fix step: `docs/procedure/TASK_TO_MODEL.md`.
- Limits: pairs only within one object (a joined mesh is one object, as in xView); FBX / .blend need Blender.

### 3ds Max xView runner — `tools/qa/xview_dump.ms` (#528)
- Status: contract-tested and native-measured on Max 2024 (2026-10-24) via the supported batch route `dcc_batch.py max --version 2024 --file tools/qa/xview_dump.ms` (3dsmaxbatch, shared lock, run on copies); this is the only launcher evidenced by the retained `SUMMARY.md` and the four JSON (the JSON carry no launcher identity). The startup invocation `3dsmax.exe -U MAXScript tools/qa/xview_dump.ms` below is documented but has no retained native measurement.
  `3dsmax.exe -U MAXScript tools/qa/xview_dump.ms` with `XVIEW_OUT` (alias `TOW02_XV_OUT`) a directory that
  already contains `jobs.txt`. The receipt line is `#nonce:<id>`; each model is exactly six fields
  `label|path|node|mode|material|slot`. Path is `.fbx` (import into a reset scene) or `.max`
  (`loadMaxFile` quiet, `useFileUnits`, never saved). Empty node = the largest mesh by polygon count; a name
  that is not in the scene is an error naming it. Modes: `plain`, `weld` (Editable Mesh, weld all vertices at
  `units.decodeValue "2mm"`, checks stay on the mesh), `weldpoly` (same weld, then Editable Poly). Face tolerance
  `units.decodeValue "5mm"`. A non-ASCII path is copied to `XVIEW_TEMP` under an ASCII name; the copy's SHA-256
  must equal the source. The opened file is hashed before and after; a change is an error.
  `xv_preflight` runs before any `createFile`, `deleteFile` or stage copy. It rejects duplicate labels,
  `|` and control characters, a wrong field count, a non-canonical slot token, and same-file identity
  (normalized path and `GetFileInformationByHandle`) across inputs, `<label>.json`, `jobs.txt`, `report.jsonl`,
  `done.txt`, `failed.txt` and the ASCII staging copy. A preflight failure exits before any write.
  `prepare_run` writes a fresh nonce into `jobs.txt` and is mirrored by `preflight_jobs_txt` for a hand-written
  file; it does not have to be running for the script to refuse an alias. It removes this run's `done.txt` and
  `<label>.json` only after that check, including when preparation itself fails, and never when the path is an input.
  Field 6 is the slot (`count >= 6`). An unknown slot or material is an error naming it.
  The script copies the nonce into `done.txt` and each result, and writes `done.txt` only when every job succeeds.
  `quitMax` does not set a process exit code (`System.Environment.Exit 1` is attempted on failure). `check_run`
  requires the jobs.txt nonce in `done.txt` and in every result, a complete dump (the keys the script writes),
  no `error` key and no `failed.txt`. `{}`, null, a mismatched label, a partial schema or a done receipt from
  another nonce exits 2.
  JSON: nonce, scene inventory, dropped nodes, counts, every flagged face (Max face id, material id, area, centre)
  and every flagged vertex (id, position). Job twin `jobs/vyatskaya-tow02/scripts/xview_review.ms` points here.
  One Max owner; lock `%LOCALAPPDATA%\Temp\agr-3dsmax-session.lock`.
  Vyatskaya evidence (measured 2026-10-24): [SUMMARY.md](../jobs/vyatskaya-tow02/evidence/xview-528/SUMMARY.md),
  [ACCEPTANCE.md](../jobs/vyatskaya-tow02/evidence/xview-528/ACCEPTANCE.md),
  [v005_plain.json](../jobs/vyatskaya-tow02/evidence/xview-528/v005_plain.json) (185 faces / 0 vertices),
  [013_plain.json](../jobs/vyatskaya-tow02/evidence/xview-528/013_plain.json) (0 faces / 10 vertices),
  [013_weld.json](../jobs/vyatskaya-tow02/evidence/xview-528/013_weld.json) (0 faces / 0 vertices),
  [013_weldpoly.json](../jobs/vyatskaya-tow02/evidence/xview-528/013_weldpoly.json) (0 faces / 10 vertices),
  [hashes_before.txt](../jobs/vyatskaya-tow02/evidence/xview-528/hashes_before.txt),
  [hashes_after_src.txt](../jobs/vyatskaya-tow02/evidence/xview-528/hashes_after_src.txt),
  [hashes_after_copies.txt](../jobs/vyatskaya-tow02/evidence/xview-528/hashes_after_copies.txt).

### Face overlap check — `tools/qa/check_clearance.py`
- Status: WORKING (2026-10-06; AGR boundary cases + FBX planes 3 mm apart)
- Near-parallel faces closer than 5 mm (profile), on faces JSON or FBX via
  `tools/blender/export_faces.py`. Hits need classifying (embed vs defect).

### Engine — `src/dt_ai/geometry/from_spec.py`
- Status: WORKING on synthetic specs only (2026-10-09, `tests/qa/test_from_spec.py`): the B01 fixture
  spec builds a model that passes all benchmark checks against the synthetic box; no real etalon yet.
- `build(spec, BuildInputs)` -> mesh dump (format of `measure_spec_blender.py`): walls by contour,
  holes with reveals and planes, roof, parapet; quads, welded, no T-junctions, no Shell (C23);
  plane seat by profile (C24 final, user 2026-10-10 [D037]: `npm_min` full opening depth, `mid` half).
  Build inputs not in the spec (parapet thickness, material IDs) are required arguments.
- Floor steps (pattern floor-step, 2026-10-10): a contour per floor, ledge (roof ID) / soffit (facade ID).
- Oblique walls (pattern non-90-corner, 2026-10-10): trapezoid strips for horizontal faces; B02 green end to end.
- Terraces (pattern terrace, spec v0.4 `terraces`, 2026-10-10): a parapet on a floor-step ledge (outer / inner
  face, cap, walkable part); the extractor does not read them yet.
- Not yet: rounded corners, an x-extreme sharp corner (triangle), terraces as walkable roofs, attachments, corner, touching or
  roof-level openings, cross-level openings in a typical template, writing a Blender
  scene / FBX (errors, never guesses).

### Benchmark run — `tools/qa/run_benchmark.py`
- Status: WORKING on a synthetic etalon FBX (2026-10-10, `tests/qa/test_from_spec.py`, Blender 5.1):
  etalon FBX -> spec -> engine model -> `tools/export/export_mesh_blender.py` (.blend + FBX, slot
  index + 1 = material id, LEVEL_ empties) -> FBX readback -> etalon self-check and model report.
- `uv run python tools/qa/run_benchmark.py --etalon <fbx> --object <object.json> --tolerances <t.json> --output <new folder>`;
  exit 0 both pass / 1 a check fails / 2 a step stops or a check is not measured.

### Build by source modules — `src/dt_ai/geometry/from_source.py`, `tools/qa/run_from_source.py`
- Status: EXPERIMENTAL (user, 2026-10-14 [D079]): on OBJ03 it did not give an acceptable model - open polygons,
  flipped normals, excess mesh, while the own checks passed (blind spots: normals, decor topology; issue #117).
  Tests pass on synthetic sources (`tests/qa/test_from_source.py`). What it does: the model rebuilt
  module by module from the source (`jobs/<OBJ>/modules/modules.json`, `build_as` per group) - walls per storey
  (quads), slab and deck boxes (quad fill clipped by the outline, CDT fallback counted), decor one box per
  element, planes for the roof enclosure, glass railings per ledge side - and its spec measured by the same
  modules; the same checkers as the spec path. Beside `from_spec`, not instead of it.
- `uv run dt from-source --dump <source dump> --modules <modules.json> --object <object.json> --output <new folder>`
  (model dump, spec, report); `uv run python tools/qa/run_from_source.py ... --tolerances <t.json> --output <new folder>`
  adds the FBX export, readback and checks (etalon = the source without `skip` modules).
- Pattern primitive-first (2026-10-14): two deliveries in the output folder - `modules/` (`modules-scene.json`,
  `modules.blend`: collections per group, instances share a type mesh) and `npm/` (`model.blend`, `model.fbx`); the
  blocking `complexity` check (`src/twinqa/geometry/complexity.py`) when the tolerances have a `complexity` block.

### Benchmark geometry checks — `tools/qa/check_geometry.py`
- Status: WORKING on synthetic boxes only (2026-10-09, `tests/qa/test_geometry_checks.py`); no
  real etalon yet (B01, issue #12). Logic in `src/twinqa/geometry/`.
- Model vs etalon mesh dumps (`tools/source/measure_spec_blender.py`, now with `polygon_sizes`):
  bbox, levels, storey areas, silhouettes, mesh (manifold, open edges, n-gons, overlaps), triangle
  budget, opening planes, material ID ranges; thresholds from `benchmark/<id>/tolerances.json`.
- `uv run python tools/qa/check_geometry.py <model-dump> <etalon-dump> --spec <spec.json> --tolerances <t.json> --output <report.json>`;
  exit 0 pass / 1 fail / 2 not measured or bad input.

### 3ds Max production scripts (external)
- Status: CONFIGURED (inventory only, not run) — see `docs/tools/max-scripts.md` for which
  script serves Flora, Ground, MAF, UCX, lights, and their rule mismatches.

## Project workflows

### `analyze-architectural-source`, `validate-delivery` (project skills)
- Status: CONFIGURED (written against `docs/domain/`; not yet run on a real source)

### Placement engine — `src/dt_ai/placement/engine.py` (#316)
- Status: on `main` (from `improve/issue-316-placement-engine-pure-flora-maf-placemen`, Hermes dt-worker, 2026-10-19);
  synthetic tests only (`tests/test_placement_engine.py`), not yet run on a real Ground or SPOZU table (#296).
- Use: `place(points, ground_vertices, ground_triangles, library, seed=<int>, label_map=None)` -> report dict;
  `report_json(report)` for byte-stable JSON; CLI `uv run python -m dt_ai.placement.engine --input in.json
  --output out.json` (exit 0 pass / 3 review / 1 fail / 2 bad invocation).
- Does: Flora [D100] and MAF [D095] seating 0.10 m below the topmost Ground, seeded rotation/scale (Flora),
  DXF INSERT rotation (MAF), bottom-face delete/review [D096], fail-closed findings per point [D108].
- Limits: pure numpy/shapely, no DCC instancing; MAF dimensions [D094] only reported; nested-block rotation is
  whatever `PointItem.rotation` carries.
