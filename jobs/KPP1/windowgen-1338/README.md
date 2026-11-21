# #1338 KPP1 window generator test (measurement only)

Measurement only: it does NOT replace the accepted KPP1 v005 and is not a delivery. Choosing the profile is a
separate decision for Artem. Nothing under `outputs/package-*-v00x` or any delivery folder was touched. All builds
are new copies in `jobs/KPP1/outputs/build-wg1338-*` (gitignored, local).

Program per step:
- Stage 1, the OBJ round trip and its readback, in Blender 5.1. The KPP1 pipeline and its readbacks are Blender-native and run headless; Max adds nothing for an OBJ readback.
- Stage 2, the stage-6 build, the NPM export and the renders, in Blender 5.1. `build_kpp1.py`, `export_npm.py` and `render_preview.py` are Blender scripts, and the accepted v005 was built with the same chain.

Inputs (read-only copies): `source-v001`, `census-v001` and `textures-v001` from
`.claude/worktrees/laughing-hawking-e62961/jobs/KPP1/outputs/`. Library: `library/windows/window_types.json` and
`standard.json` at the branch head.

## Stage 1: isolated types (`scripts/windowgen_stage1.py`, result `stage1_readback.json`)

`winplace_core.plan` gets one isolated opening per type, with the type's own size, and places that type with no
findings. Then `build_type(variant='vpm')` builds the mesh, `to_obj` writes it, Blender `wm.obj_import` imports it
(forward Y, up Z) and the readback is compared. `build_type` always calls `standardize` (windowgen_core.py:341): an
outer edge within `outer_snap_m` (0.15 m) snaps to the F100 face of 57 mm. The library panes at 50 mm therefore move
7 mm inward, and inner edges at a 50 mm transom/mullion gap stay where they are.

| Type | W x H m | library panes_m [x0,z0,x1,z1] | standardized glass fields | verts built/readback | faces built/readback | parts | readback bbox | glass y | diff |
|---|---|---|---|---|---|---|---|---|---|
| KPP1-W01 | 1.18 x 1.80 | [0.05,0.05,1.13,1.75] | [0.057,0.057,1.123,1.743] | 36/36 | 33/33 | frame 32, glass 1 | [0,0,0]-[1.18,0.1,1.8] | 0.08 | none |
| KPP1-W02 | 1.18 x 5.45 | 4 panes, z 0.05-0.875 / 0.925-2.0 / 2.05-3.75 / 3.8-5.4 | z 0.057-0.875 / 0.925-2.0 / 2.05-3.75 / 3.8-5.393, x 0.057-1.123 | 96/96 | 90/90 | frame 86, glass 4 | [0,0,0]-[1.18,0.1,5.45] | 0.08 | none |
| KPP1-W03 | 2.00 x 1.80 | [0.05,0.05,0.975,1.75], [1.025,0.05,1.95,1.75] | [0.057,0.057,0.975,1.743], [1.025,0.057,1.943,1.743] | 56/56 | 52/52 | frame 50, glass 2 | [0,0,0]-[2.0,0.1,1.8] | 0.08 | none |

Open semantic question (reported, not decided): `KPP1-W01.source.glass_m` = [1.08, 1.70] and `panes_m` equal the
whole AGS68 window bbox from the Revit spec (`b["windows"]` is exactly that bbox, 50 mm inside the bay). It is open
whether a library "pane" is the glass or the AGS68 unit. If it is the unit, the windowgen glass (7 mm inside the
bbox) is too large by the AGS68 frame+sash, which the accepted rule assumes to be 70 mm (`WINDOW_FRAME`).

## Stage 2: new KPP1 copy (`build_kpp1.py` with `KPP1_WINDOWGEN=<new report.json>`)

One shared `glass_rects(b)` feeds `surround_cell` and the relief cuts in `openings`. Without the env variable it
returns exactly the accepted rule: the baseline copy reproduces v007's `main_tris` 24 262 / `glass_tris` 76. With
the env variable it uses the `kind='glass'` fields of `build_type(vpm)` placed at the bay's lower-left corner, with no
scaling, centring or mirroring. The glass stays at `D_GLASS` (30 mm behind the frame face, KPP1 depth). Plan:
`windowgen-plan-1338.json`, which holds both sources, the old and the new rects, and the per-side deltas of every bay.

Bays: 20 (S 10, N 7, W 3; E none; the N feature has no bays). Substituted 20, excluded 0. win.place matched
18 x W01, 1 x W02 and 1 x W03, and every type glass field matched exactly one source contour. **Excluded ambiguous
matches: none on KPP1.** The exclusion path (field count, no type, a field outside its contour or more than
`apply_tol_m` = 30 mm inside it, opaque fields, a mirrored asymmetric source) is covered by the tests in
`tests/jobs/test_kpp1_windowgen_1338.py`.

Outer frame offset = glass inset inside the matched source contour, per side u0/u1/z0/z1 in mm (new / accepted):

| Facade | Bay id | Type | Contour (src) | new u0 u1 z0 z1 | accepted u0 u1 z0 z1 |
|---|---|---|---|---|---|
| N | 1614434, 1614440, 1614446, 1614452, 1614458, 1614577, 1614571 | W01 | window | 7 7 7 7 | 70 70 70 70 |
| S | 1614470, 1614464, 1614535, 1614541, 1614565, 1614559, 1614529, 1614547, 1614553 | W01 | window | 7 7 7 7 | 70 70 70 70 |
| W | 1614781, 1614787 | W01 | window | 7 7 7 7 | 70 70 70 70 |
| S | 1614476 | W02 | 0 window z 1.25-2.075 | 7 7 7 0 | 70 70 70 70 |
| S | 1614476 | W02 | 1 glass z 2.125-3.2 | 7 7 0 0 | 0 0 0 0 |
| S | 1614476 | W02 | 2 window z 3.25-4.95 | 7 7 0 0 | 70 70 70 70 |
| S | 1614476 | W02 | 3 window z 5.0-6.6 | 7 7 0 7 | 70 70 70 70 |
| W | 1614583 | W03 | 0 window u 5.5-6.425 | 7 0 7 7 | 70 70 70 70 |
| W | 1614583 | W03 | 1 window u 6.475-7.4 | 0 7 7 7 | 70 70 70 70 |

Triangles (`export_npm_meta.json`, same scripts and inputs, Blender 5.1.2):

| Build | main_tris | glass_tris | Main quads (qa_master) | Glass quads | t-junctions | leaks |
|---|---|---|---|---|---|---|
| accepted v007 package (laughing-hawking outputs) | 24 262 | 76 | - | - | - | - |
| baseline copy `build-wg1338-base2` (branch, no env) | 24 262 | 76 | 12 149 | 38 | 17 | 0 |
| windowgen copy `build-wg1338-wg2` | 23 594 | 68 | 11 815 | 34 | 17 | 0 |

The card's "old ~26k/150k" does not match these files. The accepted chain measures 24 262 main / 76 glass
triangles; I found no 150k figure in the v006 or v007 `export_npm_meta.json`.

## Screenshots (Workbench, textured; not committed, rule 57)

The renders are in `G:/Мой диск/AGR-evidence/1338-windowgen/`; their hashes are in `evidence-SHA256SUMS.txt`
(14 files):
- `close_{base2,wg2}_{W01_S,W02_S,W03_W}.png` are close-ups of the accepted and windowgen versions.
- `{base2,wg2}_W0x_*.png` are tight crops.
- `{base2,wg2}_full_SW.png` are full views.

Note: facade u runs along +x on N (`FACADES` in build_kpp1.py), so N is mirrored when seen from outside. All three
types are mirror-symmetric, so this does not change any number here. An asymmetric type would be excluded rather
than mirrored (test `test_no_symmetry_assumption_mirrored_asymmetric_source_excluded`).
