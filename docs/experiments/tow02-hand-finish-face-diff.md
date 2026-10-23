# Experiment: TOW02 — where did the user's hand finish change faces (export-v005 vs the user's final FBX)?

Card t_056e4cd4 (experiment, no GitHub issue). Report under test: `docs/research/tow02-hand-finish-face-diff.md`
(card t_87c6a6f9, branch `docs/research-tow02-hand-finish-face-diff`). The research ran without any DCC, so this card
checks its two adoptable methods against Blender 5.1.2 headless.

## Question

1. **M1, pure-Python FBX reader + triangle matcher** (proposed task 4, "reusable `fbx_face_diff` tool"): does the
   reader read the same geometry as Blender's FBX import, does the diff give the same counts, and what does it cost?
2. **M2, part label from UV swatch + z** (the research's own approximation; proposed task 3, "per-face part id
   side-car"): how many labels does it get wrong against the 37 real source objects, and does that change the H2
   verdict?

## Setup

- Inputs are copies in `%TEMP%/agr-exp-t_056e4cd4/` with the same SHA-256 prefixes as the research:
  `v005.fbx` = export-v005 `SM_Vyatskaya_Vl_47_49_013_Main.fbx` `ff8994dc4b7c`, `user05.fbx` = the user's
  `for_placement/0213_Vyatskaya_Vl_47_49_05.fbx` `2fd800812c53`, `tow02_tex_v030.blend` = build-v030 master (37 `TOW02_*`
  objects, 35 407 faces), `atlas_layout.json`, `ovl_pairs.json`. Nothing under `jobs/` or `data/` was written.
- Blender: `C:/Program Files/Blender Foundation/Blender 5.1/blender.exe` 5.1.2 headless, `--factory-startup`. The live
  4.4.0 session was not used.
- Scripts are in `experiments/tow02-hand-finish-face-diff/`:
  - `face_diff.py` is the research script, unchanged.
  - `bl_dump.py` dumps from Blender: `fbx` mode gives world verts, polygons and loop UVs after `import_scene.fbx`;
    `blend` mode gives world face centroids and normals per object.
  - `compare_readers.py` (M1) compares the readers vertex by vertex and re-runs the matcher on the Blender geometry.
  - `part_truth.py` (M2) matches the v005 faces to the source-object faces (centroid within 5 mm, normal dot >= 0.99,
    one to one) and builds a confusion matrix and the H2 share with the true labels.

```
blender -b --factory-startup --python bl_dump.py -- fbx %T%/v005.fbx SM_Vyatskaya_Vl_47_49_013 %T%/bl_v005.json
blender -b --factory-startup --python bl_dump.py -- fbx %T%/user05.fbx SM_Vyatskaya_Vl_47_49_013 %T%/bl_user05.json
blender -b --factory-startup %T%/tow02_tex_v030.blend --python bl_dump.py -- blend %T%/bl_parts.json
python compare_readers.py %T%      python part_truth.py %T%
```

## Results

### M1: reader and matcher, pure Python vs Blender 5.1.2 import

| measure | pure-Python reader (research) | Blender 5.1.2 import |
|---|---|---|
| v005: verts / faces | 44 000 / 35 407 | 44 000 / 35 407, same polygon lists |
| v005: max vertex deviation | 0 (FBX doubles) | 0.069 mm (float32) |
| user 013: verts / faces | 45 315 / 73 594 | 45 315 / 73 594, same polygon lists |
| user 013: object placement | ignored (raw local vertices) | translation **(4951.864, 14903.346, 165.443) m** |
| user 013: max deviation vs raw | n/a | 15 705 m in world; 0.546 mm after subtracting the translation (float32 at 15 km) |
| diff counts (unchanged / moved / deleted / added tris) | 33 256 / 1 292 / 859 / 4 634 | world: 0 / 0 / 35 407 / 73 594; minus the translation: 33 256 / 1 292 / 859 / 4 634 (identical) |
| runtime | read + match 3.59 s (median of 3.85 / 3.59 / 3.57) | import + dump wall 1.9 s (v005) + 3.3 s (user), import alone 0.10-0.12 s / 0.91-0.93 s (3 runs each), then match 3.0 s, about 8.2 s in total |

The FBX properties explain the user file. The model `013_Main` has `Lcl Translation (4998.2075, 167.454, -15309.1953)`
(Y-up), `PreRotation (-90, 0, 0)` and `GeometricTranslation (-46.3433, -405.8496, -2.0115)`. Blender folds these into
one object translation of (4951.864, 14903.346, 165.443) m in Z-up. So the research summary line "same coordinates:
the user only moved the pivot" is **wrong**. The mesh shape keeps our frame, but the user's final object stands
15.7 km away at z +165.44 m: the `for_placement` placement. Nothing in `jobs/vyatskaya-tow02/` or `docs/` records
this offset (`git grep` on origin/main finds no hit). The raw reader gets the right shape diff because it ignores the
node transform. That is also its failure mode: it would not notice a moved or rotated object, and it would not
notice a small hand nudge made at node level.

### M2: part labels, UV swatch + z vs the true source object (build-v030)

All 35 407 v005 faces matched one to one to the 35 407 source faces (max centroid distance 2.995 mm, from the join
weld).

| research label -> true group | faces |
|---|---:|
| correct (TOW02_top 2 796, ac_basket 2 283, ac_railing_glass 732, body 20 227, fins 8 458, top_glass 86) | 34 582 |
| TOW02_top -> body (louvre / coping / body objects at z >= 64.7) | 619 |
| body -> ac_basket | 200 |
| TOW02_top -> ac_basket | 6 |
| **label accuracy** | **97.67 %** |

| H2 measure | research labels | true labels |
|---|---:|---:|
| changed triangles | 8 936 | 8 936 |
| in TOW02_top / top_glass / ac_railing_glass or z >= 64.7 | 2 539 | 2 539 |
| **H2 share (threshold 80 %)** | **28.41 %** | **28.41 %** |
| changed tris per part: body / TOW02_top | 704 / 674 | 723 / 655 |

The changed v005 triangles by true object are: `TOW02_ac_railing_glass` 1 332, `TOW02_ac_coping` 1 240, fins 906,
`TOW02_top` 464, `TOW02_louvre` 206, `TOW02_railing_glass` (the top railings) 60, `TOW02_body` 48, `TOW02_top_glass` 44,
`TOW02_coping` 2. The research merged `TOW02_railing_glass` into `ac_railing_glass`. Split out, the "top railings"
the user named account for only 60 changed triangles.

## Verdicts

| method | verdict | reason |
|---|---|---|
| M1: pure-Python FBX reader + triangle matcher (`fbx_face_diff`) | **adopt, with a transform report** | It reads the same topology as Blender, more precisely (doubles instead of float32, which costs 0.55 mm at 15 km), gives counts identical to the matcher run on Blender geometry, and is about 2x faster. It needs no DCC lock. It must print each model's `Lcl Translation/Rotation/Scaling`, `PreRotation` and `Geometric*`, and offer a world-space mode. Today it hides a 15.7 km placement offset. |
| M2: UV swatch + z part labels | **maybe** (good enough for this verdict; replace with a per-face part id) | 97.67 % of labels are correct and the H2 share does not change (28.41 % rejected in both). The 825 wrong labels shift per-part counts by 19 tris, and the scheme cannot split `TOW02_railing_glass` from `TOW02_ac_railing_glass`. The research's side-car proposal (task 3) is the exact fix and costs less than keeping the heuristic up to date. |

H2 is confirmed **rejected** with ground-truth part labels: 28.41 % < 80 %.

## Proposed follow-up tasks (no GitHub issues created)

1. **`tools/qa/fbx_face_diff.py`: promote the research reader + matcher, with a transform report** (adopt M1).
   Scope: move `read_fbx`/`mesh`/matcher from `face_diff.py`, add a node-transform report (Lcl T/R/S, PreRotation,
   Geometric*, UnitScaleFactor) and a `--world` flag. Add a test on two tiny synthetic FBX files written by Blender
   5.1.2: (a) the same mesh with one quad moved 10 mm must give 1 moved; (b) a node translated by 15 km must give
   counts unchanged in local mode and the offset in the report. Size S-M.
2. **TOW02 / NPM placement offset: confirm (4951.864, 14903.346, 165.443) m** (from M1). Ask the user whether the
   `for_placement` translation is the delivery placement that our export should carry (as a node transform or a
   documented offset), and record it in `jobs/vyatskaya-tow02/STATE.md`. Size S, needs input from the user.
3. **Per-face part id side-car in `join_export_blender.py`** (research task 3, supported by M2). Scope: write
   `{face_index: tow02_src_part}` JSON next to the FBX. Acceptance: `part_truth.py` with the side-car instead of the
   .blend gives 100 % labels. Size S.

## Optional corner audit of "unchanged" faces (hypothesis #603, adopted)

`experiments/tow02-hand-finish-face-diff/audit_correspondence.py` replays pass 1 of `face_diff.py` (same grid,
limits, face order and quad diagonals) and checks every face it calls unchanged with an independent corner test:
for each selected triangle pair, `min over 6 vertex permutations of max_k dist(a[k], b[perm[k]])` in raw local
metres must be `<= 0.001` (exactly 1 mm passes); a face passes only if all its triangles pass. It is a research
helper, **not a production or delivery gate** (`delivery_passed` is always false; node transforms are ignored).

    python experiments/tow02-hand-finish-face-diff/audit_correspondence.py SOURCE.fbx TARGET.fbx OUT.json

Exit 0 = pass fraction >= `--fraction` (default 0.99), 1 = below, 2 = bad input (missing/non-FBX file, target not
fully triangulated, n-gon source, NaN/inf, output path that resolves to an input, input changed during the run).
Tests: `tests/test_tow02_face_correspondence_audit.py`.

Measured on copies of export-v005 (`ff8994dc...`) vs the user's 013_Main (`2fd80081...`): 33,251 of 33,256
unchanged faces pass (99.985 %). **Known residual: 5 faces (0.015 %)** have corner offsets of 1.0-2.0 mm while
their centroids match within 1 mm: v005 face / user triangle 35321/29005 (1.986 mm), 35336/29029 (1.50 mm),
35380/29038 (1.50 mm), 33613/63297 (1.01 mm), 33614/63300 (1.01 mm). The user013 self-check gives 73,594/73,594.
