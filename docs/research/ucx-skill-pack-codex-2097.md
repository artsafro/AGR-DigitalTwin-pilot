# Codex UCX skill pack (oks- / ground-collision-builder) vs our UCX (#2097)

OBSERVE research. The UCX default, the cores, the D-rows and accepted deliveries are unchanged. New code is one
OBSERVE report (`agr ucx FBX REPORT.json Main|Ground --simplify-report`) and the ported checks in
`src/twinqa/geometry/ucx_seams.py`; nothing gates or refuses. Evidence:
`G:/Мой диск/AGR-evidence/2097-ucx-skill-pack/` (15 report JSON, Codex check outputs, `table.md`,
`SHA256SUMS.txt`, 27 files; the hash of SHA256SUMS.txt is
`ee0153ce5492cd32fac440a1ea0bb94068e93ee44c111072d6eba103d8ed740d`); working copy `C:/x/ev_2097/`.

## Inputs

| Item | Value |
|---|---|
| Pack | `C:/x/ucx-skills-codex-20261128/` (read-only copy), zip SHA-256 `90d706a9677e8ac420e20ac3c9e155f1cb4e8f3ed64643c2113524e72c93974b`, `MANIFEST.json` per-file hashes |
| OKS skill | `oks-collision-builder/SKILL.md` (edition 27.11.2026), `references/method.md`, `checks.md`, `scripts.md`, `source-requirements.md` (historical draft 06.11.2026), `scripts/check/*.py` (10), `scripts/gen/*.py` (K6 generators, not run) |
| Ground skill | `ground-collision-builder/SKILL.md` + `references/ground-collisions.md` (Garibaldi_22_Ground v007 profile) |
| Our side | `docs/domain/areas/ucx.md` R01-R18, [D012], [D098], [D134], [D339], `agr ucx`; the 2026-11-27 answers of #2050 as written in OPEN PR #2058 (D433 budget vs form, D434 Ground one-sided, D435 stairs = truncated pyramid, D436 convexity 1 mm, D437 gap stays D098 + D339) - not on main yet, cited as "#2058 D43x" |
| Cases | Codex 01-04, 10 of #2042 (`C:/x/ev_2042/run/<case>/{ours,codex}.fbx`) and the #2053 section-boxes FBX (`G:/Мой диск/AGR-evidence/2053-ucx-variants/review-r2/<case>/sec.fbx`) |

## 1. Rule diff

Classes: NEW (we have no such rule or check), SAME, CONFLICT (quote both; a question in section 4), N/A.

| # | Codex rule (quote, short) | Our main | Class |
|---|---|---|---|
| C1 | OKS outward tolerance: «доступные нижние части, кровля и согласованные доступные зоны — до 30 см наружу; остальные части — до 1 м» | R12 «<= 30 cm model surface -> UCX at pedestrian-reachable lower OKS floors, stylobates and bridge/platform approaches»; R13 1 m elsewhere | numbers SAME; **roof at 30 cm is NEW** (R12 names no roof; source-requirements: «Крыши и балконы в PDF не названы отдельно — оставлены по записи Алины») -> Q2 |
| C2 | «Допуск — предел допустимого упрощения, а не обязательный отступ от фасада … Внутреннее недопокрытие этим допуском не разрешается» (tolerance bounds the UCX standing OUT of the facade; the model must not show through) | [D134] «limits are one-sided, model surface -> UCX … UCX -> model distance is diagnostic only» (the limit bounds the model standing outside the UCX; UCX overhang is not bounded) | **CONFLICT: the two rules bound opposite directions** -> Q1 |
| C3 | «Нормативный бюджет вычислять по применимому профилю, а не всегда как 5%»; 4000 was the K4 limit | [D012] < 50 000 -> 15 000 else min(ceil 5 %, 100 000); #2058 D433 over the budget is reported, not refused | SAME (our formula is the profile; K4 4000 N/A) |
| C4 | «Сохранять полигональную топологию; считать треугольники без применения Triangulate … если пользователь не задал иное»; Ground: «триангуляция UCX допустима только при явном согласовании» | R18 «Triangulated collision meshes in exported FBX» (reg p.29 §3.17), V003 reads UCX polygon degrees | **CONFLICT** -> Q3 |
| C5 | Ground: «Допуск 100 мм в обе стороны для описываемой поверхности» (ground-collisions.md, check 4) | R11 <= 10 cm one-sided [D134]; #2058 D434 «Ground UCX deviation stays one-sided … Codex's two-sided reading is not adopted» | CONFLICT already answered by Artem 2026-11-27 (D434) - one-sided stays; no new question |
| C6 | «Последний файл с ручными правками — база изменений; старый генератор не должен восстанавливать удалённое» | none: `agr ucx` always builds from the model; no "fix an existing UCX" mode | NEW (process) -> Q4 |
| C7 | Gap: OKS «2–10 мм, обычно 5–6 мм»; Ground «строго 2–10 мм по всей общей границе» | [D098] 2 mm - 1 cm, [D339] bands of the pair minimum; #2058 D437 | band SAME; **"over the whole shared border, not the pair minimum" is NEW** - ported as `seam_face_gaps` (section 3) |
| C8 | «Не ужимать все грани блока: зазор вводится у соседа, внешняя поверхность остаётся по зданию»; Ground: «Отступ для зазора применять к внутренним стыкам, а не … ко всему внешнему периметру» | `ucx_build` shrinks every box by gap/2 (#2042 K13), outer faces included | NEW method detail (1.5 mm inward on the outer shell at the default 3 mm gap); not a D-row; candidate, not measured here |
| C9 | Stairs: Ground «Каждую лестницу целиком закрывать одним замкнутым наклонным объёмом по согласованному образцу усечённой пирамиды»; OKS draft «одна усечённая пирамида на марш; площадки — отдельными блоками» | R14 truncated pyramid; #2058 D435 «only the truncated pyramid» | SAME (per flight + landings vs whole stair is detail; R14 says neither) |
| C10 | Convex, closed, no holes, no materials, no intersections, «численный порог документирован» | R06, R07, R09 V010 SAT; #2058 D436 convexity 1 mm | SAME |
| C11 | «Сначала крупные простые объёмы … Выпуклая оболочка каждой отдельной детали не является хорошей декомпозицией»; «Выступ не требует собственного блока … выдвинуть наружную плоскость основного объёма и поглотить деталь» | `ucx_build` voxel boxes; #2053 section-boxes variant (large section boxes) | NEW method (a) - measured as the `plane_shift` list (section 2), not adopted |
| C12 | Two mandatory passes: A empty / duplicate (full triangles, «Несколько взаимозаменяемых блоков нельзя удалять одновременно»); B over-split -> «удалить / поглотить с пересборкой / сохранить с причиной» | none (V010 checks validity, not usefulness) | NEW - implemented as the OBSERVE report (section 2) |
| C13 | Coverage by clipping source triangles with body half-spaces; «Проверка только центров треугольников пропускает узкие участки»; 10 mm QA margin «не разрешение утопить модель на сантиметр» | none exact (#2042 replay sampled points) | NEW - used by the report (margin 10 mm, tight 1 mm) |
| C14 | «Чистая сетка»: no micro-chamfers, narrow strips, coplanar extra edges; Ground «тонкие полигоны недопустимы» | none | NEW - ported as `sliver_report` (diagnostic thresholds 1 cm edge / 5 mm height, not a norm) |
| C15 | Ground: shared walkable heights equal at a common point; T-joints; triangular voids between several blocks | none (#2042 K21) | NEW, not ported (needs the Ground surface graph) - gap |
| C16 | Ground: min/max Z of every block vs the allowed bottom («проверка только верхней поверхности не обнаруживает провалы снизу») | none | NEW, not ported - gap |
| C17 | Ground: retaining walls from the source top polygon as one block; renumbering map old -> new | none | NEW (method / report) - not ported |
| C18 | Names `UCX_<exact Main name>_<n>`; Ground `UCX_SM_<Address>_Ground_<NNN>` | R08 V012 | SAME |
| C19 | Analysis-only mode: list, do not change the model | read-only intake [D237]; this report | SAME |
| C20 | Independent checker reads the FINAL FBX; «Collizii_2.ms … выполненным только при фактическом запуске» | `agr ucx` readback; AGR Tools off the trail [D393] | SAME |
| C21 | Roof: do not fill to the parapet top; parapet / overhang split only when one prism breaks the tolerance; arcs: one form-giving ridge, no fans of narrow faces | R01 functional voids; no roof rule | NEW (method), not ported |
| C22 | Balcony = bottom slab for K4; railings / conditioners per confirmed project list; canopies > 5 cm ask each time | R04 <= 5 cm no UCX, [D298] | SAME / project-specific N/A |
| C23 | Delivery to «Загрузки», Russian report, no renders unless asked | our delivery route | N/A |

## 2. Method candidates (OBSERVE), measured

`agr ucx FBX REPORT.json Main --simplify-report` (`src/dt_ai/geometry/ucx_simplify.py`, Blender dump
`tools/blender/ucx_mesh_dump.py`). Pass A: exact clipping of FULL source triangles by each body (margin 10 mm);
coverage 0 -> `delete`; coverage > 0 and unique 0 -> deleted one at a time, smallest first, re-measured. Pass B:
`merge` (two bodies across one seam whose hull adds no air beyond the seam) and `plane_shift` (a body in front of one
face of a neighbour, absorbed by moving that face out <= 0.30 m Main / 0.10 m Ground) - an upper-bound rebuild
hypothesis, the moved face stands out by `shift_m` and must be re-checked. Everything else `keep` with the reason.
Seam classes against [D098]: ok / tight (< 2 mm somewhere) / wedge (in band at one end, > 1 cm at the other) / slot
(> 1 cm everywhere, up to 30 cm); "open seams with source surface" = slots that hold source triangles (area clipped
by the slot prism; horizontal slabs inside the envelope count too, so this is a candidate, not a defect).

Runs: Blender headless, `--margin-m 0.01 --absorb-m 0.30`, all 15 exit 0 (8-519 s each).

| Case | Side | Bodies | Tris | Delete (empty / dup) | Merge | Plane shift | Tris saved (upper) | Keep | Seams ok / tight / wedge / slot | Open seams with source surface (m²) | Winding bad / inward | Slivers |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | default | 558 | 6696 | 1 (0 / 1) | 0 | 124 | 1488 | 433 | 1118 / 0 / 0 / 0 | 0 (0) | 0 / 0 | 0 |
| 01 | section-boxes | 896 | 10752 | 9 (0 / 9) | 1 | 122 | 1472 | 764 | 1937 / 0 / 0 / 443 | 326 (1050.0493) | 0 / 0 | 0 |
| 01 | Codex | 999 | 13108 | 3 (0 / 3) | 8 | 50 | 621 | 938 | 1651 / 0 / 0 / 144 | 57 (72.0335) | 0 / 0 | 2 |
| 02 | default | 562 | 6744 | 16 (0 / 16) | 0 | 81 | 972 | 465 | 1189 / 0 / 0 / 0 | 0 (0) | 0 / 0 | 0 |
| 02 | section-boxes | 841 | 10092 | 7 (0 / 7) | 1 | 112 | 1345 | 721 | 1593 / 0 / 0 / 362 | 300 (59.8192) | 0 / 0 | 0 |
| 02 | Codex | 467 | 6888 | 9 (9 / 0) | 5 | 98 | 1230 | 356 | 728 / 0 / 0 / 158 | 118 (102.4533) | 0 / 0 | 2 |
| 03 | default | 158 | 1896 | 7 (0 / 7) | 0 | 39 | 468 | 112 | 354 / 0 / 0 / 0 | 0 (0) | 0 / 0 | 0 |
| 03 | section-boxes | 676 | 8112 | 52 (0 / 52) | 4 | 195 | 2346 | 425 | 1662 / 0 / 0 / 880 | 223 (161.0253) | 0 / 0 | 0 |
| 03 | Codex | 298 | 4120 | 3 (0 / 3) | 4 | 46 | 837 | 245 | 579 / 0 / 0 / 132 | 75 (8.9711) | 0 / 0 | 0 |
| 04 | default | 285 | 3420 | 0 (0 / 0) | 0 | 192 | 2304 | 93 | 501 / 0 / 0 / 0 | 0 (0) | 0 / 0 | 0 |
| 04 | section-boxes | 753 | 9036 | 90 (0 / 90) | 0 | 199 | 2388 | 464 | 1308 / 0 / 0 / 293 | 197 (3788.5203) | 0 / 0 | 0 |
| 04 | Codex | 776 | 9670 | 1 (0 / 1) | 4 | 259 | 3375 | 512 | 1746 / 0 / 0 / 603 | 5 (0.5164) | 0 / 0 | 2 |
| 10 | default | 329 | 3948 | 1 (0 / 1) | 0 | 20 | 240 | 308 | 979 / 0 / 0 / 0 | 0 (0) | 0 / 0 | 0 |
| 10 | section-boxes | 857 | 10284 | 5 (0 / 5) | 6 | 121 | 1502 | 726 | 1945 / 0 / 0 / 755 | 620 (1451.7537) | 0 / 0 | 0 |
| 10 | Codex | 47 | 564 | 0 (0 / 0) | 0 | 0 | 0 | 47 | 68 / 0 / 0 / 2 | 2 (3.2635) | 0 / 0 | 0 |

Readings:
- Pass A finds real removals everywhere: Codex 02 (the user-finished v015) has 9 bodies with ZERO coverage of the
  model even with the 10 mm margin - the same class as K4 blocks 106/418 in their checks.md; our default has 0-16
  zero-unique duplicates per case, section-boxes 5-90 (case 04: 90 of 753, 12 % of its bodies).
- Pass B is a hypothesis list: `plane_shift` is large on every side (default case 04: 192 of 285 bodies) because a
  30 cm shift of a neighbour face swallows most thin boxes; the moved face then stands up to 30 cm out of the
  facade, which C2 / [D134] read differently (Q1). "Tris saved" is an upper bound before any rebuild.
- Seams: the default (shared grid) has no wedge or slot seam; section-boxes and Codex have slots 1-30 cm between
  facing faces (443-880 per case for section-boxes), many of them with source surface inside. The pair-minimum
  [D339] bands do not see this. Compared with #2053: section-boxes has more bodies than the default in every case and
  the most duplicate and slot findings; the report does not support it over the default. Pass B on the default is
  the cheaper next measurement (rebuild with plane shift, re-run R12/R13), not a parallel method.

## 3. Their check scripts

Read first (no network, no writes outside their cwd pickles). Run unmodified on 2 cases (03 default, 10 Codex) via
`C:/x/ev_2097/codex_chk/adapt.py` (our mesh dump -> their `o3.pkl`, `o3_obj.pkl`, `indep_check/blocks.pkl`).

| Script | What it checks | 03 default | 10 Codex | We have | Action |
|---|---|---|---|---|---|
| c12.py | plane violation, non-manifold, winding (`badori`), degenerate, negative volume, volume vs hull | all 0 | all 0 (viol 6e-6) | V010 convex / closed; no winding or inward test | **ported** `winding_report` |
| c2.py | SAT + LP overlap, pair distances in bands | 0 overlap, min 4.0 mm | 0 overlap, min 6.0 mm | V010 SAT, [D339] `pair_census` | none (covered) |
| c3.py | facing face pairs, gap over the whole overlap, unfilled share, model inside the gap | 361 pairs 4.0 mm, 0 in 1-30 cm | 68 at 6.0 mm, 2 slots 25.6 cm with model 8-11 cm inside | pair minimum only | **ported** `seam_face_gaps` (exact min/max over the overlap, + model-in-seam area) |
| c4v6.py | sampled (40 pts/m²) visible model > 1 cm outside UCX | inside 0.972, max 3.7 cm, 1.3 m² | inside 0.856, max 0.99 m, 2119 m² | R12/R13 manual (V016) | not ported: sampling, and its direction is Q1 |
| v5extra.py | misc incl. check 7 short edges / low triangles | - | - | none | **ported** `sliver_report` |
| bandchk.py, v5flush.py, ringchk.py | K4 / K6 project-specific zones (plinth band, flush, ring roof) | not run | not run | - | N/A (project numbers) |
| lib.py, load.py | helpers / FBX load | - | - | - | N/A |

## 4. Отчёт для Артёма

**Что берём (OBSERVE, ничего не блокирует, умолчание UCX не меняется).**
1. Два обязательных прохода упрощения из навыка Codex как отчёт `agr ucx FBX REPORT.json Main|Ground
   --simplify-report`: «удалить / поглотить с пересборкой / сохранить с причиной» по точному отсечению полных
   треугольников модели (запас 10 мм). Находит реальные пустышки: в принятой пользователем K2 (кейс 02) 9 блоков,
   не касающихся модели вообще; у нашего умолчания 0-16 дублей на кейс, у section-boxes 5-90.
2. Проверку шва по всей встречной грани (их c3), а не по минимуму пары: у нашего умолчания клиньев и щелей нет, у
   section-boxes 293-880 и Codex 2-603 щелей 1-30 см на кейс, часть - с поверхностью модели внутри.
3. Проверки обхода нормалей и тонких полигонов (их c12, v5extra). На 15 файлах обход везде чистый; тонких
   полигонов 2 у Codex в 01, 02, 04, у нас 0.

**Что конфликтует - вопросы.**
1. Направление допуска ОКС. Codex: «Допуск — предел … а не обязательный отступ … Внутреннее недопокрытие этим
   допуском не разрешается» - 30 см / 1 м ограничивают, насколько коллизия выступает НАРУЖУ, а модель торчать из
   коллизии не должна. У нас [D134]: «model surface -> UCX … UCX -> model distance is diagnostic only» - 30 см / 1 м
   ограничивают, насколько модель может быть ВНЕ коллизии, а вынос коллизии не ограничен. Это противоположные
   стороны. Рекомендация: оставить [D134] как есть до вашего ответа, а в отчёт добавить вторую сторону (площадь
   видимой модели вне коллизии > 1 см, как их c4v6) - наблюдать. Нужен ответ: должна ли модель быть полностью
   внутри коллизий (недокрытие запрещено), а 30 см / 1 м - предел выноса наружу?
2. Кровля 30 см. Codex относит кровлю к 30 см («кровля … до 30 см наружу»), у нас R12 кровлю не называет (по
   умолчанию 1 м). Рекомендация: 30 см только для доступных (эксплуатируемых) кровель и террас, остальные 1 м.
   Согласны?
3. Триангуляция UCX. Codex: сохранять полигоны, не триангулировать без явного согласования. У нас R18 по регламенту
   (стр. 29 §3.17): в FBX коллизии триангулированы, V003 это проверяет. Рекомендация: оставить регламент (R18);
   бюджет и так считается в треугольниках. Согласны?
4. Ручные правки как база. Codex: «последний файл с ручными правками - база; генератор не восстанавливает
   удалённое». У нас `agr ucx` всегда строит заново от модели, режима «исправить существующие UCX» нет.
   Рекомендация: записать правило в маршрут UCX - при доработке чужих или ручных UCX брать их файл как базу и
   мерить разницу покрытия до/после (этим отчётом), генератор по нему не запускать. Согласны?

Уже решено вами 27.11 (PR #2058, ещё не в main) и навыком не меняется: Ground односторонний (D434), лестница -
только усечённая пирамида (D435), допуск выпуклости 1 мм (D436), зазор 2 мм - 1 см (D437), бюджет можно превышать
ради формы (D433).

**Измеренный эффект.** На кейсах 01-04, 10 (15 файлов): удаляемых блоков у умолчания 0-16 (до 2,9 %), у
section-boxes 5-90 (до 12 %), у Codex 0-9; гипотеза поглощения сдвигом плоскости до 30 см - до 2 304 треугольников
у умолчания (кейс 04), но это верхняя оценка до пересборки, и она зависит от ответа на вопрос 1. section-boxes по
всем трём проходам хуже умолчания; параллельный метод не строим.

**Пробелы.** Ground-варианты #2053 (ground-coarse-faces) отчётом не прогонялись (Ground-ветка проверена только
юнит-тестами); проверки Ground C15-C17 (высоты на стыках, низ блоков, подпорные стены) не перенесены; пересборка
по спискам прохода Б не делалась; их генераторы K6 не запускались.

## Side finding (not changed here)

`ucx_core._convex_hull` (frozen Max core, used by the gap check of open PR #2058) returns a non-convex hull for two
boxes rotated 31° with a 4 mm seam: 198 m³ instead of 270 m³. Reported only; the report here uses its own hull.
