# vyatskaya-tow02 NPM candidate `0213_Vyatskaya_Vl_47_49_05.fbx` (user hand finish) — 2026-10-21

Profile **NPM-OKS** (`validate-delivery`, V001-V017 of `docs/domain/validation.md`, LP 2026 rows of
`docs/domain/requirements-2026.md`, project decisions). Validator: delivery-validator agent, branch
`job/vyatskaya-tow02-review` (PR #525), 2026-10-21. Read-only on the user's files (hashes identical before and
after); background Blender 5.1.2 and the project venv only; no 3ds Max was started.

**Verdict: not passed.** 6 distinct fails (FBX triangle budget; transforms of 014/015; zero-area UVs; xView vertices
before the weld; 013 set named 014 vs [D156]; a 0.4 mm co-directional pair on 012/015), 4 review results, 4 not
checked, 3 manual gates open (V015, V017, visual).
Technical QA only; user acceptance and publication are separate.

## Files

| File | SHA-256 | Role |
|---|---|---|
| `C:/Users/artsafro/Desktop/!3D viz/NTR/26_Vyatskoe/001 - Моделирование НПМ с нуля/001 - Моделирование НПМ с нуля/for_placement/0213_Vyatskaya_Vl_47_49_05.fbx` (6 302 640 B) | `2fd800812c53d70f77960c0d08b91790510a285a59370ca6fcac43856271da68` | deliverable under test |
| `jobs/vyatskaya-tow02/outputs/review-v002/delivery/0213_Vyatskaya_Vl_47_49_05.fbx` (copy of `xview/user_copy/…`) | same | file the tools read |
| `…/for_placement/sceene.max` (copy `xview/user_copy/sceene.max`) | `d4e209269c988ba135916ae20b84bb1e9907a29d44ab26c8597d146987ff59f5` | quad source (not opened here) |
| `…/for_placement/0213_Vyatskaya_Vl_47_49_01..04.fbx` | `eb92988c…0004`, `1c55bf37…4425`, `02ef3fff…48dc`, `3c98513c…fbffa` | package convention only |
| `…/0200_Vyatskaya_Vl_47_49_02.fbx` (accepted reference, [D156]) | `4ccee127…5afc` | convention only |
| ours `jobs/vyatskaya-tow02/outputs/export-v005/SM_Vyatskaya_Vl_47_49_013_Main.fbx` | `ff8994dc…080a` | baseline only |

Embedded maps extracted from the FBX (`delivery/dump05/textures/`): `T_…_014_Main_d_1` `ccc0a0c2…a326` (=
our build-v030 `T_…_013_Main_d_1`), `_m_1` `3d7c8d12…4e5b`, `_r_1` `487377f7…6305`; `T_…_012_Main_{d,m,r}_1`
`77c7d85a…1451`, `b1580766…c72e`, `1ad6e135…a43c`.

## What the FBX holds (readback)

3ds Max 2024, FBX SDK 2020.3.4, binary 7400, UnitScaleFactor 100 (1 unit = 1 m), FBX Y-up (axis conversion
`PreRotation -90`, standard Max export). 4 meshes, no other objects, no hierarchy, 1 UV channel `UV` each, no colour
attributes.

| Object | Tris | Material | Transform after import |
|---|---|---|---|
| `SM_Vyatskaya_Vl_47_49_012_Main` | 16 528 | `M_…_012_Main_1` | loc (5172.325, 15208.124, 167.000), rot 0, scale 1 |
| `SM_Vyatskaya_Vl_47_49_015_Main` | 16 528 | `M_…_012_Main_1` | loc (5063.247, 15328.228, 167.000), **rot Z −180°** |
| `SM_Vyatskaya_Vl_47_49_013_Main` | 73 594 | `M_…_014_Main_1` | Max node T (4998.208, 15309.195, 167.454) + object offset (GeometricTranslation −46.343, −405.850, −2.011) → Blender origin (4951.864, 14903.346, 165.443); rot 0, scale 1, det +1 |
| `SM_Vyatskaya_Vl_47_49_014_Main` | 73 594 | `M_…_014_Main_1` | **det −1** (Blender: scale −1, rot (0, 180°, −55°)); same object offset |

Total **180 244** triangles. 013 bbox X 4979.84-5016.57, Y 15293.08-15325.31, Z 164.634-244.693 m (80.06 m high).
014 is not an exact copy of 013: 306 fin-bottom vertices at local z −0.471 instead of −0.808, UVs differ up to 0.016.

## Checks

### Regulation stages (validator: `.venv/Scripts/python.exe tools/qa/validate_package.py <fbx> --profile npm --json --scene`, exit 1; `py -3` lacks `shapely`, the project venv has it)

| Check | Result | Evidence |
|---|---|---|
| V001 package (ZIP, composition, Ground FBX) | **not checked**: a single FBX was given; no ZIP, no Ground FBX | validator `not_run` |
| V002 FBX 7.4 binary | pass | header 7400 |
| V002 units 1 unit = 1 m | pass | UnitScaleFactor 100; 013 reads back 80.06 m high, in metres |
| V002 scale 1:1 | **fail** | 014 world scale −1 (mirror) — reg p.4, LP 1.2.1/2.3.14 |
| V003 triangulated, mesh-only, no hierarchy | pass | all faces degree 3; 4 meshes, parent none |
| V003 triangles per OKS FBX ≤ 150 000 | **fail** | 180 244 (−20.2 %) — reg p.7 §3.6, LP 2.3.6; split allowed exactly in this case (LP 2.2.1). 013 alone 73 594. The 0213 package files `_01`-`_04` hold 146 410 / 149 750 / 126 855 / 90 390; the older reference `0200_…_02` held these 4 OKS at 182 482 |
| V003 4 OKS in one FBX, separate objects | pass | reg p.6 §1.4 (≤ 20 OKS objects), p.7 §3.3 (separate, not merged) |
| V004 transforms (rotation 0, scale 1 after reset) [D135] | **fail** | 013 pass; 015 rotation −180°; 014 mirror. In `0200_…_02` all four were reset (rot 0, scale 1, det +1) — reg p.8 §3.14, LP 2.3.14 |
| V004 duplicates at 0.002 m (≤ 100 per mesh) | pass (regulation) | 013 and 014: 5 duplicate vertices each, 0 duplicate edges/polygons (`count_defects`, local) |
| V004 self-intersections at 0.002 m (≤ 100 per mesh) | **review: new conflict, not in `conflicts.md`** | 013 56 586 (local) / 53 876 (world readback), 014 56 586, 012 3 792, 015 3 806; ours export-v005 25 765 (quads). Constructive embeds (fins, glass planes, louvre ends, copings ≥ 10 mm) are allowed by the project rule in `docs/domain/geometry.md` and the OKS is one joined mesh, so the literal reg p.8 §3.7 / LP 2.3.7 count cannot be met; embed vs defect not classified |
| V004 isolated elements, zero-length edges | pass | 0 / 0 (013, 014) |
| V004 co-directional overlap 5 mm-2 cm (reg p.8 §3.9) | **fail (FBX)**; 013/014 pass | validator (world, all meshes): 232 pairs < 5 mm. Local float64: 013 0 and 014 0 pairs < 5 mm (6 640 in band each); 012: 2 pairs 0.40 / 0.70 mm (faces 11467/14290-14291, local z 6.62), mirrored in 015. The 4.5 mm world hit on 013 is float32 quantisation (~1 mm at 15 km) |
| V005 shaders | pass (FBX level) | ShadingModel Phong, no VRay/Corona/Arnold markers; the Max material class is not in the FBX (not checked in Max) |
| V005 maps per profile | pass | d + r + m (pair), no normal [D014], no opacity (no transparent parts; glass opaque in atlas, reg p.10 §7 method 1) |
| V006 PNG embedded, 2048², ≤ 3 MiB, no alpha, 8 bit, one size per set | pass | 6 maps packed, RGB 8-bit, max 746 476 B (`npm_texture_findings`) |
| V006 padding ≥ 8 px between islands with unique images | pass (note) | nearest islands of different colours ≥ 15 px apart; but 1 484 glass tris now start at x 491.13 px, 7.13 px from the edge of the white swatch (ours 8.0 px) — own-colour margin below 8 px, island gap still ≥ 8 |
| V012 mesh names `SM_{Address}_{NNN}_Main`, `_Main` suffix, OKS 012-015 | pass | validator grammar 4/4 |
| V012 FBX name `{prefix}_{Address}_{NN}` | pass (form) | `_05` after `_01`-`_04` of the same package |
| V012 prefix value | **review: sources disagree** | user's package uses `0213`; [D156] and `STATE.md` "Next" say `0200_Vyatskaya_Vl_47_49`; the territorial code cannot be checked here (no classifier, SINTEZ `lp_district_code` missing in twinqa) |
| V012 material / texture names of 013 | **fail vs [D156]** | 013 carries `M_…_014_Main_1`, `T_…_014_Main_{d,m,r}_1`; [D156] fixes `M_/T_…_013_Main*`; the accepted `0200_…_02` named the 013/014 shared set `013`, and 012/015 share `012` (named after the unmirrored original). Texture names equal their PNG file names (pass) |
| V014 Moscow coordinates, plan angle | **not checked**: no DWG/SPOZU overlay (V014 unimplemented) | coordinates are in the same frame as the other package OKS; heights absolute |
| V015 match with the approved project | manual, pending | — |
| V017 insertion point, zero mark, georef | manual, pending | — |

### LP 2026 rows not covered by the stages

| Check | Result | Evidence |
|---|---|---|
| 4.1.3 no zero UV area / zero 3D area | **fail** | 013: 3 314 tris with zero UV area (2 960 on the white glass swatch = AC railing glass, z 10.97-66.61, 11.18 m²; 344 dark, 296 of them collapsed to one point = AC coping posts; 10 grey, z 54.6-55.2); 014 the same 3 314; 0 zero-3D-area tris. Ours export-v005: 0 per polygon |
| 4.1.4 lowest point 110-250 m | pass | 164.634 (013), 164.815 (014), 165.500 (012), 164.986 (015) |
| 4.1.5 pivot at the geometric centre (recommendation) | **review** | in Max the 013/014 pivot is at the XY bbox centre (4998.208, 15309.195), written as an object offset; Blender-based checkers (SINTEZ) see the origin 46.3 m / 405.8 m off. How SINTEZ reads GeometricTranslation is not verified |
| 4.1.6 exactly one UV map | pass | `UV` on every mesh |
| 4.1.1 / 4.1.2 colour attributes / 24-bit RGB | pass | none / RGB 8-bit |
| 2.4.5 materials = texture sets; 2.5.11 one set per OKS | pass | 2 materials, 2 sets; each OKS uses one set (twins share) |
| 2.5.10 opaque glass: white d and m, black r | pass | 4 414 white glass tris, all m 255 / r 0 |
| UVs outside our layout rects (1 097 tris, `diff/diff_report.json`) | pass | they sit on the uniform dark background `#303031` (1 084 416 px), none within 8 px of another colour; layout rects are build-internal, not a rule |
| Mirrored UV islands | n/a for NPM (VPM rule reg p.31) | 11 410 negative-winding tris, info only |

### Project decisions

| Check | Result | Evidence |
|---|---|---|
| [D152] (1) xView-clean, Vertices 2 mm / Faces 5 mm | **fail as delivered** | xView (Max 2024) on the FBX 013: Vertices **10** (5 coincident pairs, 0.0 mm, band corners local z 76.25 ×4 / 69.45 ×1), Faces 0 (`xview/user_fbx05.keep`). Cross-check `inv_xview` on 013 local: 5 pairs = the same 10 ids, 0 faces (1:1); 014 the same. After weld 2 mm: `inv_xview` 0 / 0; xView after Editable Mesh + Weld 0.002 m 0 / 0 (`xview/user_max013_weldmesh.json`, 5 welded) |
| [D152] (2) quads in the master, triangles in the FBX | pass | FBX triangulated (reg); `sceene.max` 013 = 36 864 polys: 36 726 quads, 136 tris, 2 n-gons (`xview/user_max013.json`) |
| [D152] (3) one material per texture set | pass | one slot per mesh |
| [D135] rotation 0 after reset | **fail** | see V004 transforms (014, 015) |
| [D156] OKS 013, module atlas, palette | names fail (above); atlas pass | `T_…_014_Main_d_1` pixel-identical to our build-v030 atlas |
| [D169] fins ~1 m below ground | 013 pass; **014 review** | 013 fin bottoms local z −0.808 (abs 164.634), the value D169 records; 014 −0.471 m. Relief not available, so "sits on the relief" is not checked |
| [D170] wall angles squared to ~90° | **not checked**: no angle measurement in this run | REVIEW-514 §1 says the 51.8-57.8 wall link is not measured |
| [D171] copings, roof, band dark | pass | coping 283 m², roof 27 m², band → `#303031` (`diff/diff_report.json` finish transitions) |

### Priority checks (skill)

1. Architectural accuracy — **not checked** against a source report (none for TOW02 in `docs/sources/`); REVIEW-514 §1:
   user 013 = export-v005 + translation, 92.4 % of vertices within 0.1 mm, listed changes only.
2. Scale and transforms — fail (014 mirror, 015 rotation); 013 pass.
3. Materials — names fail vs [D156]; maps, sizes, embedding pass; zero-UV fail (LP 4.1.3).
4. Performance — fail on the FBX budget (180 244 > 150 000); per OKS 013 73 594 within the 150 000 target [D161].
5. Visual fidelity — **manual, pending**: Workbench renders of 013 front / angled / back, user vs ours, in
   `jobs/vyatskaya-tow02/outputs/review-v002/delivery/renders/`; comparison with the approved project needs the user.

## Open questions for the user (review items)

1. Prefix: `0213` (the current package) or `0200` ([D156], STATE "Next")? If `0213`, D156 and STATE need an update.
2. Shared set of the 013/014 twins: name it `013` as [D156] and `0200_…_02`, or was `014` deliberate?
3. Self-intersections at 0.002 m: the joined OKS with ≥ 10 mm embeds gives ~56 600 (reg ≤ 100). Accept embeds as the
   project reading (as in every accepted OKS: 012 has 3 792), or classify / change the joins? New conflict for
   `docs/domain/conflicts.md`.
4. 014 fins only 0.471 m below its zero — intended for its relief, or should it match 013 (0.808, ~1 m per [D169])?
5. Pivot of 013/014 written as an object offset (LP 4.1.5 recommendation only): keep, or make it offset-free like 012?
6. Package (outside this FBX, not validated): OKS numbers run 001-041 with 029 missing, while reg p.11-12 §3.3 /
   LP 2.10.3.3 give 001-020 without gaps.

## What the user should change before sending

In 3ds Max, on `sceene.max` (a new versioned save), in this order:

1. **Split the FBX to ≤ 150 000 triangles each** (V003; reg p.7 §3.6, LP 2.3.6, 2.2.1). Suggestion:
   `0213_Vyatskaya_Vl_47_49_05.fbx` = 013 + 014 (147 188; one shared set) and `_06.fbx` = 012 + 015 (33 056); or
   012 + 013 / 014 + 015 (90 122 each). Numbering stays ascending without gaps.
2. **Reset the transforms of 014 and 015** (V002/V004; [D135], reg p.8 §3.14, LP 2.3.14): Reset XForm, then collapse
   to Editable Mesh. On 014 (mirror) the reset flips the faces: flip the normals back before collapsing and check they
   face outwards. Target as in `0200_…_02`: rotation 0, scale 1, no mirror.
3. **Give the 3 314 zero-area UV triangles a real unwrap** on 013 and 014 (LP 4.1.3): the rebuilt AC railing glass
   (2 960 tris, z 11-66.6 m, collapsed to lines on the glass swatch), the AC coping posts (296 tris collapsed to a
   point), 48 more dark and 10 grey (ac_floor / perforated, z 54.6-55.2). Planar/box map them and place them back in
   their swatch; keep the glass islands inside x 492-516 px (8 px from the white edge at 484 / 524).
4. **Rename the 013/014 set to 013, if [D156] stands** (V012; reg p.12-13 §3.4-3.5, LP 2.10.3.4-5):
   `M_Vyatskaya_Vl_47_49_014_Main_1` → `M_Vyatskaya_Vl_47_49_013_Main_1`, maps `T_…_014_Main_{d,m,r}_1` →
   `T_…_013_Main_{d,m,r}_1`, PNG file names identical to the map names. Confirm the prefix (`0213` / `0200`) at the
   same time.
5. **Move the 012/015 co-directional pair apart** (V004; reg p.8 §3.9): faces 11467 vs 14290/14291 of 012 at local
   z 6.62 m are 0.40 / 0.70 mm apart; give them ≥ 5 mm (and the same on 015, its rotated copy).
6. **Relink the 013/014 maps to a folder of the package** before export: their paths now point into the repository
   scratch folder `jobs/vyatskaya-tow02/outputs/export-v005/SM_Vyatskaya_Vl_47_49_013_Main.fbm/`; the embedded content
   is correct, the link is fragile.
7. **Last step before each export: Editable Mesh + Weld 0.002 m on 013 and 014** ([D152] xView-clean): FBX now
   xView Vertices 10 / Faces 0 → 0 / 0 after the weld (measured). No Editable Poly round trip after it. Then export
   FBX 2014 binary, triangulated, embed media, and send the new files back for a readback (`validate-delivery`).

## Commands and evidence (`jobs/vyatskaya-tow02/outputs/review-v002/delivery/`, git-ignored)

- `validate_scene.json` / `validate_noscene.json`: the validator (exit 1 / 2); `readback.json`: `tools/blender/fbx_readback.py`.
- `scripts/dump_fbx_blender.py` → `dump05/` (local geometry, UVs, material links, extracted PNGs); `ours_v005/dump/`.
- `scripts/check_mesh_local.py` → `mesh_local_013.json`, `mesh_local_013_weld2mm.json`, `mesh_local_014.json`,
  `mesh_local_ours_v005.json` (`dt_ai.ops.inv_xview.mesh_report` NPM-OKS 2 mm / 5 mm / cos 0.9999 and
  `twinqa.geometry.topology.count_defects` 0.002 m, local coordinates).
- `scripts/check_codirectional.py` → `codir_012/013/014.json` (`twinqa.clearance.co_directional_pairs`, window 20 mm, local).
- `scripts/check_uv_atlas.py` → `uv_atlas_012/013/014.json`, `uv_atlas_ours_v005.json` (zero UV/3D area, padding by
  colour distance with wrap, glass m/r).
- `scripts/inspect_package_blender.py` → `package_ref/package_inventory.json` (`_01`-`_04`, `0200_…_02`).
- `scripts/render_views_blender.py` → `renders/`.
- Earlier evidence: `../xview/user_fbx05.keep`, `../xview/user_max013*.json`, `../diff/diff_report.json`,
  `../xcheck/XCHECK.md`.

State change for `docs/PROJECT_STATE.md` (In production, after merge): vyatskaya-tow02 NPM candidate `_05` (user) —
validate-delivery not passed: FBX budget, transforms 014/015, zero-UV, xView vertices (weld), 013 set naming; 6 review questions open.
