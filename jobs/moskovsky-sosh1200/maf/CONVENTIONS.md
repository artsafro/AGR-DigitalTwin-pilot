# MAF conventions — moskovsky-sosh1200 (NPM site, swarm contract)

Every MAF worker reads this first. Pilot that set it: urn 28 + canopy 1 (2026-11-26,
positions 01 and 28, byte-matched to the master FBXs in the [#1985 draft catalogue](../../../library/published/catalogue.json)). Inputs: `maf_plan.md/.json` (rows, targets, pages),
`maf_points.json` (placement), `library_match.md` (library hits), `fence_kit.md` (fences), `TASK.md` (decisions).
Rules behind it: `.agents/skills/model-maf/SKILL.md`, `docs/domain/areas/groundel-maf.md`.

## 1. Frame, pivot, sinking

- Metres, Z up, 1:1. Pivot = horizontal bbox centre, Z 0 = ground (master pivot kept, A101 style).
- Ground-contact parts are modelled down to Z −0.10 (D095 sinking built in); bottom faces under ground are omitted.
  Placement = pivot on the DWG point at Z 0 (flat Ground ±0.000), rotation from `maf_points.json` `rot_deg`.
- Plan orientation of the master: long side along X, "front" (open side, seat side) towards −Y. Write the
  front/rotation assumption into the builder docstring; the placer checks it against the drawing block.

## 2. Names and files

- Catalogue id `<Manufacturer>_<NameTranslit>_<Article>` (A101 style): `Adanat_UrnaGorod_9004`,
  `GKVysota_TenevoyNavesNordik_VST1519-1`, `Robinzon_Plato1_6W3000-1`, `Taiga_Aerofon_IO1204`, `Pokolenie_…`.
- Object `<pos 2 digits>_<catalogue id>_GroundEl` [D166]; npm-light `set_id` = same without `_GroundEl`.
- Builder: `G:/Мой диск/AGR-evidence/1979-moskovsky-sosh1200/work/maf/scripts/<pos>_<slug>_vNNN.py`, `import maf_kit as K` (same folder; do
  not edit `maf_kit.py`, put new helpers in your script). The sealed scripts are receipts; work on a new copy.
- Outputs (never overwrite; next try = new vNNN): `<new-working-root>/maf-npm-vNNN/<group>/<pos>_<slug>/`
  `<object>_master_vNNN.blend`, `<object>_master_quad_vNNN.fbx`, `<object>_master_report.json`, `prev_*.png`.
- Source snapshots: `G:/Мой диск/AGR-evidence/1979-moskovsky-sosh1200/work/maf/src/` (sealed, read only); copy approved inputs into a new working directory + `SHA256SUMS.txt`; never write in `Desktop/!3D viz`,
  `G:/Мой диск/AGR-assets` or the job repo. Never touch running 3ds Max / Blender GUIs; headless only.

## 3. Geometry

- One model for NPM (and later VPM) [D164]; build directly at NPM density. Quads only in the master (0 tris, 0 n-gons).
- Lego shells, joints by sinking 10–20 mm into the neighbour, hidden faces omitted (inside a neighbour, under ground,
  under a roof). No fasteners, no booleans, no stray verts. Sharp by 45°.
- Round parts: 6–8 segments (posts, tubes), 8–10 for large visible cylinders; flat caps as quad strips.
- Tri target per item = `npm_tris_each_est` in `maf_plan.json` (urn 230, bench «Скарлет» 500, canopy 800, …).
  Report tris; above target +20 % → flag with the reason (pilot canopy 892 vs 800: 96 slats kept).
- Dimensions within 10 cm per axis [D094]: page > ledger > viz dummy. A library model outside the tolerance is not
  rescaled silently: rebuild at the page size from its structure (canopy precedent) or ask.

## 4. Two routes

- **A. Library hit** (`library_match.md` exact): copy the .max, export FBX with
  `G:/Мой диск/AGR-evidence/1979-moskovsky-sosh1200/work/maf/scripts/export_lib_fbx.ms` (3dsmaxbatch, list file `export_list.txt`), inspect parts
  (`inspect_fbx.py`, `slats.py`). If dims pass and tris ≤ 1.5× target → `agr npm-light` with `decimate_ratio` < 1 and the
  Weltbau→v007 map (§5). Otherwise (viz models of 8k–200k tris are the norm) rebuild light in Blender from the
  measured structure. Record the source path + sha256 in the builder docstring.
- **B. New** (none / near only): from the manufacturer page (dims) and renders; everything not on the page is
  ASSUMED in the docstring and becomes a verify line for Artem. No substitution by a near model [D164].
- Downloading manufacturer images/DWGs is approved by Artem (2026-11-26) for every MAF and fence position: save to
  `G:/Мой диск/AGR-evidence/1979-moskovsky-sosh1200/maf/refs/<pos>/` + `SHA256SUMS.txt`, images/PDF/DWG only, reference only, never execute.
- Library models are never decimated for NPM: rebuild light by their construction at the page size (answer 1).

## 5. Materials

Master material names `<ID>_<key>` from `library/maf/material_ids_v007.json` (`maf_kit.mat(id)`), by the page colour.
NPM atlas = job atlas 512 **v008** = v007 r2 + new cells 14 wood_light, 24 concrete, 9 green, 11 blue (answer 3;
built by the atlas worker in `G:/Мой диск/AGR-evidence/1979-moskovsky-sosh1200/work/maf/atlas/`). Masters keep their true master IDs; the
npm-light run happens after the atlas is ready (lead). Older map below = v007 fallback only:

| master ID | atlas cell | note |
|---|---|---|
| 1, 2, 3, 5, 6, 7, 8, 15, 18, 20, 23, 27, 28, 30, 33 | same | cells exist |
| 14 wood_light (larch / «светлый дуб») | 15 wood_medium | no 14 cell — **Artem to confirm** |
| 4 RAL 7047 / 25 / 12 | 3 paint_ral7040 | nearest grey |
| 22 cap_black, 13 brown dark | 1 / 2 | nearest dark |
| 24 concrete, Робинзон beige concrete | 5 paint_ral9003 | beige merged into 5 (v005) |
| 19 plywood, 32 HPL wood, 16, 17 woods | 15 / 33 by tone | |
| 9 green, 10 green dark, 11 blue | 8 / 2 / 3 — **Artem** | no cell |
| 29 rope | 28 | |
| 31 polycarbonate | GroundElGlass, no texture (MAF-06) | separate object `_GroundElGlass` |

Weltbau MAF_LIB multi-sub `MS_MAF_NN_*` → v007: 01 ral5012→11, 02 ral2003→6, 03 ral7016→2, 04 ral9005→1, 05 ral9003→5,
06 ral3020→7, 07 ral6018→8, 08 ral1023→6, 09 steel_galv→20, 10 steel_stainless→20, 11 wood_light→14, 12 wood_dark→16,
13 plywood→19, 14 plastic_hpl→by colour, 15 rubber_black→23, 16 rope→29, 17 glass_poly→31, 18 concrete→24, 19 sand→26,
20 fabric_flag / 26 flag_print→decal (ask), 21 mesh_wire→27, 22 plastic_bin→10, 23 sheet_profiled→30,
24 paint_project→ask, 25 paint_grey_light→4. But colours follow the manufacturer page, not the viz model.

## 6. UV / atlas / NPM export

- Atlas adapter `G:/Мой диск/AGR-evidence/1979-moskovsky-sosh1200/work/maf/atlas/maf_atlas_512_v007_adapter.json` (cell content minus the
  id-corner column; PNG copy `T_MAF_Atlas_v007_GroundEl_d_512_r2.png`, sha256 a30dac00…4b3f340 = r2).
- One `agr npm-light` run per group: spec `jobs/moskovsky-sosh1200/specs/maf_npm_light_<group>_vNNN.json`
  (template: `maf_npm_light_pilot_v001.json`), out `…/maf-npm-v001/<group>/npm` (a new folder outside the read-only evidence tree). It triangulates, box-
  projects UV into the cell, exports `npm/<set_id>.fbx`, gates dims / IoU / UV-in-slot.
- Independent readback: `G:/Мой диск/AGR-evidence/1979-moskovsky-sosh1200/work/maf/scripts/readback_npm.py` (tris, dims, IDs, UV inside cell, 0 faces on the id
  corner, non-manifold 0). Open edges are expected (omitted hidden faces).

## 7. Review copy and report

- Max 2026 QUAD review copy of the master: `G:/Мой диск/AGR-evidence/1979-moskovsky-sosh1200/work/maf/scripts/fbx_to_max.ms` (3dsmaxbatch; flat ID colours, D420)
  → `<group>/review/<set_id>_review_quad_vNNN.max` + readback txt. The lead opens scenes for Artem.
- Report line per item: object, route A/B, source, tris (target), dims vs page, IDs with faces, NPM FBX path,
  readback (UV out 0, corner 0), ASSUMED list, questions. ≤ 30 lines per item.
- Reusable masters are registered as drafts via `library-publish` (#1985, [D421]); use the [published catalogue](../../../library/published/catalogue.json), not the working export tree.
