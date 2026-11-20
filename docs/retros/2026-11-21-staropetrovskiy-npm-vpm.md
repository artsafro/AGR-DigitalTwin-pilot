# Retro 2026-11-21: Staropetrovskiy MAF NPM + VPM (one session)

## Session

- Transcript `job-staropetrovskiy-maf-npm-claude-prnone-f8d74c21-7ff7-43cc-9d2d-abafcb37c0b9.jsonl`, branch
  `job/staropetrovskiy-maf-npm-claude` (started as `claude/mav-modeling-staropetrovskiy-f8c285`), 2026-11-12 02:37 to
  2026-11-21 00:49, four context compactions. Work root `C:/x/staropetrovskiy-maf-claude/` (outside git).
- Job: NPM MAF for «Старопетровский проезд» from the PDF album (sheets 40-76), later placement on the customer
  Ground + Flora, shrubs in MAF planters, NPM package, then a VPM package for the same site.
- Outcome: NPM `final_2026-11-20/NPM/0205_ProezdStaropetrovskyi_ZU_7_A.zip` (v015) and VPM
  `final_2026-11-20/VPM/...` (v007) pass SINTEZ AGR Checker 1.6.1 with only signature / missing OKS (and the kept
  `ZU_area`) left; Artem sent both to the customer 2026-11-21 00:49.
- Acceptances: 11-12 03:36 first MAF pass («некоторые вещи меня прям поразили»); 11-12 13:24 geometry
  («принимаю геометрию»); 11-20 15:53 shrub sizing rule; 11-21 delivery sent. `experience-transfer` did not run after
  any of them (the delivery one is due in the handover).

## Incidents by cause

### ignored-existing-rule (3)

1. **11-20 14:39, separate NPM atlases.** «на Мафы один атлас, на флору другой атлас, на граунд третий атлас. У нас
   разные, забыл что ли?» The agent's plan merged them. Rule existed: `docs/domain/areas/groundel-maf.md` MAF-09
   (one GroundEl set ≤ 512), Flora atlas [D232]/[D246]. Enforcement; folded into the planting/site skill issue.
2. **11-12 13:16, renders.** «рендеры не нужно делать» (twice, then again at 13:24). The agent spent 07:34-09:19
   building Scanline showcase renders while Artem was online. Covered by [D273] (open the scene + absolute path
   instead of renders when Artem is online). Enforcement only; no issue.
3. **11-20 22:15, SINTEZ recommendations.** The agent reported two MAF recommendations as acceptable leftovers;
   Artem: «Рекомендации в синтезе мы тоже безболезненно правим», «Должны остаться ошибки только по подписи и
   отсутствие окс». Partly covered by [D104] (pass SINTEZ); the "recommendations too" scope is not a D-line yet:
   user decision, see triage issue.

### wrong-assumption-not-checked (3)

4. **11-20 15:28, planting spots.** The agent picked planting faces by material ID 26. Artem: «есть у них только
   один пиксель, который лежат на атласе, на песке… Материалы мы у мафов не меняем». Re-done by UV-on-sand-cell.
   No rule. Issue filed.
5. **11-20 15:44, shrub size.** Shrubs scaled down far below the customer's size. «кусты только слишком мелкие
   вышли… того же размер ставь», then «уменьшить до момента, пока он не перестанет пересекать». No rule. Same issue.
6. **11-20 16:10, customer maps.** «В фбкс были зашиты все нудные карты для флоры и граунда»: Max FBX import
   dropped the customer's Ground metallic maps (`..._Ground_m_1…7`); the agent took the scene state as the source.
   No import-readback rule. Folded into the metallic round-trip issue.

### tool/MCP-failure (2)

7. **Metallic slot vs SINTEZ 2.5.6.** `adapters/max/agr_tools/names_core.py` `SLOT_TABLE` maps metalness to
   `specularLevelMap` and treats `reflectionMap` as no role; SINTEZ reads the FBX `ReflectionFactor`/reflection
   channel, so check 2.5.6 failed and the Max importer put customer metallic maps where our table ignores them.
   Issue filed.
8. **Max 2026 batch FBX export ignores `Triangulate=False`.** A quad work FBX exported in batch came out
   triangulated. Not in `docs/agents/CAPABILITIES.md`. Issue filed.

### verification-gap (3)

9. **VPM MAF placement, pivot subtracted twice.** After a library append in Blender the agent read a stale
   `matrix_world` and subtracted the package pivot again; MAF stood off their places in VPM v001, caught only by
   the first SINTEZ round. No placement readback against the NPM positions. Issue filed.
10. **Per-island vs per-triangle UV checks (recurred, closed #432).** Our own checks judged mirrored UV, collapsed
    UV and tile overflow per island; SINTEZ judges per triangle. VPM needed rounds v001→v007 (7 667 out-of-tile
    faces, sub-512 px/m slivers, 169 mirrored, 434 line-collapsed faces), NPM had 8 944 point-collapsed sand faces.
    Issue filed (recurred).
11. **Duplicate vertices from per-face shrub verts.** 4 duplicate-vertex recommendations on NPM; the agent's
    shrub builder emitted per-face vertices. Folded into the parity issue (#10).

### missing-rule (1)

12. **11-20 17:39, no quad work FBX on this job.** «Квады не делать». [D198] is OKS-only, but the agent memory line
    "every delivery gets a work FBX" generalised it to a Ground/MAF site package. Memory line corrected by this
    retro (scope = OKS deliveries [D198]); the scope question goes to the triage issue.

### slow/inefficient-path (1)

13. **11-12 first pass budget.** After review fixes the placed MAF reached ~145k triangles against an 80k limit
    and needed a reduction round (option B, ~116k). Budget per instance count was not tracked during the review
    fixes. One-off; no issue.

Papercuts: none logged in `docs/papercuts/` for 2026-11-12..21.

## Preferences not captured

- SINTEZ recommendations are fixed too; only signature and missing OKS may remain (11-20 22:08 / 22:15).
- No quad work FBX for this site job (11-20 17:39); D198 stays OKS.
- VPM MAF: more segments on round parts, Normal/ERM solid stubs, 4K maps for non-uniform textures, 256×256 solid
  stubs for solid colours, try one 4K atlas before per-tile UDIMs; VPM shrubs = customer shrubs with alpha in the
  Diffuse channel, never new ones (11-20 17:45).
- Keep the customer GeoJSON as is («Оставляем как было по json», 11-20 22:18).

## Issues (labels needs-triage, retro; check_ready_gate pass on all six)

- #1729 metallic FBX slot round-trip (incidents 6, 7)
- #1730 Max 2026 batch FBX `Triangulate=False` (8)
- #1731 VPM placement readback vs NPM (9)
- #1732 per-triangle SINTEZ parity, recurred #432 (10, 11)
- #1733 planting in MAF planters + per-type atlases (1, 4, 5)
- #1734 user decisions (3, 12, preferences)
