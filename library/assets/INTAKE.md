# Asset intake: delivered project -> A101-standard candidates (#1024)

Standing scenario (Artem, 2026-11-07): from every delivered project, take the MAF and plants of its
specification, find them in the scene, bring them to the A101 standard and grow one library. A101 names,
articles and structure are the truth (owner 06.11.2026). Contracts: `docs/agr-tools/assets.md`
("Библиотека МАФ: контракт", "Черновик контракта «библиотечное растение»"); code: `adapters/max/agr_tools/
assets_library.py`, `assets_core.py`; library state: `library/assets/UNIFIED.md`.

The output is **candidates**, never the accepted library. Artem accepts each candidate; only then it moves to
`maf/a101`-style storage or the Flora library.

## Hard rules

- Work on copies only: hash the original (sha256) before the copy and after the run; they must match. Never
  save over a delivered scene, DWG, PDF or package.
- 3ds Max and Blender run in batch on copies (`hermes_kanban/scripts/dcc_batch.py max --version 2024 --scene
  <copy>`). Never drive a GUI Max that someone has open.
- Customer data (.max, FBX, PNG, textures, PDF) is never committed. Git gets code, JSON tables and Markdown.
- `G:/Мой диск/AGR-assets/` is a synced Google Drive. Ask Artem once per run before the first write there;
  write only into `_inbox/<project>/`.
- No licences, keys or `GeoAGR.ini`. Web sites are read-only (manufacturer pages for dimensions).

## Inputs per project

| What | Where it usually is | Notes |
|---|---|---|
| MAF schedule | ПЗУ / СПОЗУ sheet «Ведомость МАФ» (PDF, DWG table) | articles, maker, L×W×H, qty |
| Planting schedule | «Ведомость озеленения» / «Ассортиментная ведомость» | species, height, qty |
| Points | DWG blocks (`!_Маф.dwg`, `!_Озеленение.dwg`, СПОЗУ) | INSERT count = qty check |
| Scene | the delivered working .max (`blago.max`, `ITOG.max`) | the models to take |
| Delivered package | `*_Ground.fbx` (GroundEl, Flora) | what was actually shipped |

Delivered 3DVis projects live in `C:/Users/artsafro/Desktop/!3D viz/` (big PC). Projects of the customer A101
itself (Ватутино, Прокшино) are a separate source and are not part of this intake.

## Steps

1. **Registry.** Before the first project of a run, list what already exists (A101 archives, Union library,
   project sets, Flora v003, agent light NPM) so nothing is rebuilt. Keep it outside git
   (side-session notes or `C:/x/asset-intake/registry.md`).
2. **Schedule.** Copy the sources to `C:/x/asset-intake/<PID>/src/`. Read the tables into
   `spec/maf-schedule.json` and `spec/flora-schedule.json` (row shape = `jobs/VATUTINO-SITE/maf/site-schedule.json`:
   table, row, name verbatim, article, maker, L/W/H mm, material, qty, link, source page/handle). DWG -> DXF via
   `dcc_batch.py acad`, tables and INSERT counts with ezdxf. Record spec qty vs block count.
3. **Scene.** Batch-dump the scene copy, read-only: per node name, layer, instance group, size mm, pivot,
   tris, materials, proxies (Forest Pack / RailClone / CProxy are recorded, not expanded). Group into kinds
   (one record per unique geometry, with count). Guess MAF / flora / other from layer, name and size.
4. **Identify.** Each schedule row against the library and the scene, in this order:
   - article (`assets_library._article_key`, transliterated, `18694-1` -> `18694`) against A101 (`maf_unified.json`);
   - name (`translit`, `name_tokens`, `match_species` for Flora) against A101 and Flora v003;
   - dimensions ±10% against the A101 bbox and against the scene kind;
   - count: scene instances vs spec qty vs DWG blocks.
   Status per row:
   - `exists` — the A101 archive / Flora species matches by article or species and size ±10%; nothing to build;
   - `variant` — same article or species, but size or colour differs > 10%; never rescaled (Artem 07.11), flagged;
   - `new_model` — no library model, the scene has one: normalise it (step 5);
   - `not_identified` — no library model and no matching scene kind (or ambiguous): question for Artem.
   Only obvious unit errors (×10, ×1000) are rescaled. Write `<PID>/identify.json` and `identify.md`.
5. **Normalise `new_model`.** Pilot first: one MAF and one plant end to end, a picture to Artem, his «да», then
   the rest (Artem 07.11).
   - MAF (A101 archive `Maker_Object_Article.zip`, name from `propose_maf_name`): `name.max`, `name.png`,
     `name_high.fbx`, `name_low.fbx`, `name.json` (schema 3 + `agr` block via `maf_template`). Millimetres, Z up;
     one object and one material `M_<name>_<ver>` per version; scale 1, no rotation; pivot at the XY centre at
     ground level; High with 4K `T_<name>_high_Diffuse/ERM/Normal`, Low with 512 `T_<name>_low_d`; Low lighter
     than High. Check with `audit_maf` on a one-item index.
   - Plant (`<species>_t<type>_h<cm>_high/_low`): pivot at the trunk base (tree) or bbox centre (shrub), 5–10 cm
     above the lowest vertex, same for both versions; one Standardmaterial named after the object, diffuse +
     opacity from one RGBA PNG; NPM shrub = cross of 2 quads; preview `<base>_PREVIEW.png` 1024² in the A101 style
     (`tools/assets/max_render_flora_previews.py`). Check against the plant contract.
   - Dimensions vs the schedule ±10%.
   - Provenance in the JSON (`agr.intake`): project, schedule row (table, row, verbatim name), scene file + sha256,
     node names and instance count, DWG block, date, tool versions.
6. **Stage.** `G:/Мой диск/AGR-assets/_inbox/<PID>/`: archives / plant folders, JSON, previews,
   `identify.md` and `review.md` (one line per candidate: picture, status, audit result, what Artem decides).
   Nothing goes into `maf/a101`, `a101_fixed` or `flora/a101`.
7. **Report.** Counts per status, what was staged, open questions. Artem's decisions go to `docs/decisions.md`.

## What the first run taught (2026-11-07)

- Delivered scenes are often **collapsed**: MAF/Flora live inside one `_GroundEl` / `_Flora` mesh on the project
  atlas. Split the mesh into elements and cluster them by nested XY bboxes; the kinds are then reconstructions
  (`source: "elements"`) without names. Join them to schedule rows by size (`size_candidates`) and by eye on a grey
  contact sheet, and record the join in `scene-map.json`.
- An NPM-only collapse (PPT4) has no High source: no candidate, say so.
- Look for the High source next to the NPM scene: `*_hp*.max`, the VPM scene, plant files with `FLORA_HP` /
  `FLORA_LP` layers (`Школа_flora.max`: a High/Low pair per plant, counts = schedule).
- Revit/DWG planting symbols come in as flat (H = 0) objects: points for counts, not models.
- Fence and gate schedules are GroundEl, not the MAF library (`out_of_scope`).
- Texture paths in delivered scenes point at other machines (`A:\Работа\…`, `C:\Users\Terminator\…`). Search by
  basename across `Desktop/!3D viz` and the backup `B:\Backup\Desktop\!3D viz`, and check the content: the same
  UDIM tile name exists in several projects with different pictures.
- Maker spelling: take it from existing A101 archives (`Aira`, not `propose_maf_name`'s `Ayra`).
- A bench's schedule H may be the seat height: flag, never rescale.

## Run log

| Date | Projects | Result |
|---|---|---|
| 2026-11-07 | BUHV12 (1-я Бухвостова вл.12 к.11, школа), PPT4 (ППТ-4 Рязановское) | BUHV12: 21 rows in scope -> 14 new_model, 5 variant, 1 exists, 1 not_identified; pilot `Aira_VeloparkovkaVelobox_VP043` (audit 0 findings) and `klen_tatarskiy_t1_h350` (contract 12/13, Low texel) in `_inbox/BUHV12`. PPT4: no candidates (NPM collapse, no qty, MAF xrefs missing). Tables: `library/assets/intake/` |
| 2026-11-07 | BUHV12, after Artem's «да» for the pilot | all `new_model` built: 11 MAF archives (`audit_maf` 0 findings each, sidecar and Max re-measure) and 3 plants (contract 11–12 of 12–13, texel only) in `_inbox/BUHV12`; questions in its `review.md` |
