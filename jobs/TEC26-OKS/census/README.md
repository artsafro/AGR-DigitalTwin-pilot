# TEC26 OKS intake — handoff and pilot recommendation

## Scope change (operator/user, 2026-10-22)

During this run the operator directed: prioritize kotelnya, publish scene census first to `C:/x/tec26-oks/census/`, narrow #558 to scene census + KPP recipe + pilot pick, skip drawings census except titles. Per-building drawings/material evidence now belongs to #561–#566 (AC.04–09); truba production/details to #560. Those are parallel cards, not branches read or merged here. No drawing RAL-to-ID assignments are approved by this intake.

Already-extracted drawing/office text from before that instruction is retained only at `C:/x/tec26-oks/pre-scope-change-drawings.json`; PDF images at `G:/Мой диск/AGR-evidence/tec26-oks/drawings-v002/`. The native AutoCAD 2025 DXFOUT run is in `C:/x/tec26-oks/acad-readback-v001/`. All six outputs lacked final ENDSEC/EOF; ezdxf recovery was required, so this is an **unvalidated text aid**, not authoritative complete CAD validation. Re-check titles/materials against the copies on each drawing card. No full drawings census is included in this PR.

## Ready for parallel readers

- Raw native JSON published first: `C:/x/tec26-oks/census/{oks,truba,kpp}.json`.
- Classified JSON: `C:/x/tec26-oks/census/{oks,truba,kpp}-classified.json`, mirrored in this folder as `{oks,truba,kpp}.json`. Use these to avoid classifying collision candidates as surfaces. All per-node handles, source names/layers, triangle and polygon-degree counts, per-ID face counts/areas, material/map trees, pivots/transforms and UV bounds are included.
- Source copies: `C:/x/tec26-oks/sources-v001/`, full inventory/hashes in `sources.json`, external `C:/x/tec26-oks/SHA256SUMS.txt`.
- ID diagnostic renders, native geometry buffers and both Max attempt logs: `G:/Мой диск/AGR-evidence/tec26-oks/scene-census-v002/`, checksummed there. `evidence.json` pins the manifest. Painter-sorted two-view diagnostic images are ID colours, **not RAL/material previews or geometry QA**.
- Native Max 2026.3 readback completed for all three copies. Native startup exit 4294967166 was tolerated by wrapper because of `polyunwrapper_autoload.mse`; completion markers and expected JSON were independently checked. No originals or live Max document were saved/changed.

## Scene findings

Actual layers are `004` … `009`, not `0.0.0.4` … `0.0.9`. Source naming is not AGR delivery naming: Cyrillic `АС.*`, `Tuba`, `Colizii_*`, `Col_*`, generic material/map names and absolute paths require explicit remapping later. Do not rename original sources or confuse source IDs with `standards/material_id_ranges.yaml` category IDs. Keep source IDs stable until an evidenced mapping is approved.

| Drawing | Source surface nodes | Surface tris, incl. separate glass | Collision candidates | Pilot complexity rank |
|---|---|---:|---:|---:|
| AC.08 | АС.08 | 348 | 1 | 1 |
| AC.09 | АС.09 + АС.09_Glass | 690 | 1 | 2 |
| AC.05 | АС.05 | 1290 | 2 | 3 |
| AC.04 | АС.04 | 5006 | 17 | 4 |
| AC.06 | АС.06 + АС.06_Glass | 5608 | 21 | 5 (tie) |
| AC.07 | АС.07 + АС.07_Glass | 5608 | 21 | 5 (tie) |

9 surfaces + 63 collision candidates in OKS copy. Collision candidates are inferred only from source labels, not validated convex UCX. Editable Poly degrees include ngons (not all mid-poly is quads). Every surface has map channel 1, but presence does not prove nondegenerate or delivery-ready UVs. AC.04–09 source materials have no texture maps; viewport colour is not RAL evidence. `scenes.md` contains all nodes and per-surface ID tables with unknown finishes explicitly `?`.

Truba: native `Tuba`, 50256 tris / 25128 quads, channel 1 exists with UV U up to 138.371 / V down to -97.786. 60 `Col_*` candidates. Six used IDs: 1,2,3,5,6,7; generic material `Material #75`; absolute source bitmap paths refer to unavailable historical A: drive. Staged basename matches are assets, not proof Max resolved those original paths. Actual headers: five 256² RGB colour maps; `railing_10mx1_2m_8posts_RGBA_2048.png` is **4096² RGBA despite filename/card description**. Missing full delivery structure: compliant names/paths, explicit VPM triplet/slot/tile mapping, ERM/Normal set, NPM atlas with RGB diffuse and separate opacity, delivery exports/readback/QA. #560 owns the next work; do not mutate from this census. `Col_002` native/snapshot bbox Z differs by 0.101089 mm; retain as unresolved, not a geometry pass.

## Titles only (DWG text locators)

Coordinates below are paper-space drawing coordinates, not metres/site coordinates. `Layout1`, title-block text, native copy identified in `sources.json`:

| AC | Title text | Locator (x,y), sheet |
|---|---|---|
| 04 | Локальные очистные сооружения | (508.10,28.49), Layout1; sheet identification delegated to #561 |
| 05 | Блок-модуль пенного пожаротушения | (501.55,26.05), Layout1; sheet identification delegated to #562 |
| 06 | Пункт редуцирования газа 1 | (302.40,25.97), Layout1; sheet identification delegated to #563 |
| 07 | Пункт редуцирования газа 2 | (301.87,25.97), Layout1; sheet identification delegated to #564 |
| 08 | Контейнер низковольтных комплектных устройств (НКУ) | text fragments (506.6,27.7) + (526.7,24.0), Layout1, sheet 1 at (596.8,23.8) |
| 09 | Контейнер системы автоматического контроля вредных выбросов (САКВ) | fragments (499.7,27.7) + (504.4,24.0), Layout1, sheet 2 at (596.5,23.8) |

AC.08 also contains model-space notes naming guard posts. Do not use those instead of the title block or assume their relationship; #565 resolves drawing scope. AC.08/09 have no supplied PDF; drawings coverage is not ranked as complete here.

## Pilot pick

**Provisional recommendation: AC.08 (НКУ)** — smallest measured scene, 348 triangles, three used material IDs, one collision candidate, no separate glass surface. It minimizes geometry/UV/material iteration cost. This is a recommendation, not Gate 1 or approval to start production. Confirm #565's material evidence first. **Fallback: AC.05** — 1290 triangles, four used IDs and supplied PDF; prefer it if #565 cannot fully evidence the three AC.08 IDs and #562 can evidence AC.05. AC.09 is smaller than AC.05 but adds glass and is DWG-only. No claim that one drawing is most complete is made before #561–566 return.

## One question list for Artem

No new drawing-unanswered material question is asserted by this narrowed census. Consolidate questions **after #561–566/#560** read the drawings; do not ask Artem to supply information already present there. Pending technical investigations (not user decisions): AC.08 drawing-scope notes, per-ID finish evidence, truba asset/version mismatch, source collision validation. The pilot choice can be finalized from those receipts; then build one building, obtain Artem's acceptance, and only then parallelize the remaining production models.
