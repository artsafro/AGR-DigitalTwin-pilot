# Decision log: detail

Verbatim original rows of `docs/decisions.md` that were longer than one line of rule. `docs/decisions.md` is the
index and stays authoritative for the one-line rule; each section below is the full original row, kept word for word,
for the quotes, locators and context the short row leaves out. The short row links here with
`detail: docs/decisions-detail.md#d<n>`.

## D010

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D010 | 2026-10-07 | C1: the VPM triangle table is the hard limit; project target <= 150 000 triangles per OKS FBX in VPM as in NPM. Clarified 2026-10-15 (#141): 150 000 is the budget of the one mid-poly master per OKS FBX from which NPM and VPM are derived | `docs/domain/conflicts.md` #1, `docs/domain/npm-vpm.md`, `docs/domain/areas/body.md` BODY-G | chat Extended by [D161] (2026 regulation ceiling confirmed). |

## D097

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D097 | 2026-10-15 | Artem: "texel density is per linear metre: NPM 10-40 at 2K, VPM 520-1706 at 4K" — pixels per linear metre: NPM Ground 10-40 px/m with 2K textures, VPM 520-1706 px/m with 4K textures, consistent with [D021]; project note: "the NPM Ground budget is 180 000" triangles (reg p.7 §3.6), starting split surface 50k / MAF 60k / Flora 70k | `docs/domain/conflicts.md` #4 | #175, user (Artem), Ground grilling rounds 2-3 VPM lower bound superseded by [D160]; all other provisions unchanged. |

## D098

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D098 | 2026-10-15 | Artem: "UCX: as the regulation, except the gap - from 2 mm to 1 cm, the regulation's 0.02-1 cm is a typo" — gap between collision pieces 2 mm - 1 cm inclusive is the project rule; reg p.36 §13.4 has a typo; a check reports gaps outside the band (implementation out of scope here) | `docs/domain/conflicts.md` #15, `docs/domain/areas/ucx.md` R10 | #175, user (Artem), Ground grilling rounds 2-3 Extended by [D162] (both UCX gap checks). |

## D100

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D100 | 2026-10-15 | Flora placement: SPOZU points have no rotation; authoring pivot on SPOZU point, slightly above lowest point to sink 10 cm into Ground; random Z rotation and scale +-10 % inside +-20 % tolerance; final FBX resets transforms and shares origin | `docs/domain/geometry.md` | #187 (Flora grilling round 1 Q6 and round 2 Q7-Q8; user Artem: "SPOZU points have no rotation; pivot on point, slightly above lowest point to sink into Ground when projected. random Z rotation and scale +-10 % inside +-20 % tolerance. sinking 10 cm as MAF") |

## D102

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D102 | 2026-10-15 | VPM bush: default is shell of NPM star; detailed model only on explicit request; study library VPM bushes and follow their logic (recommendation until then) | `docs/domain/geometry.md` | #187 (Flora grilling round 2 Q10; user Artem: "default VPM bush = shell of NPM star; detailed only on explicit request; study library VPM bushes and follow their logic, until then recommendation") |

## D134

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D134 | 2026-10-19 | UCX R11-R13 distance limits are one-sided, model surface -> UCX: Ground <= 10 cm, pedestrian-reachable OKS <= 30 cm, remaining OKS <= 1 m. Exposed UCX -> model distance is diagnostic only, not a tolerance failure; target completeness and functional-void preservation still apply | `docs/domain/areas/ucx.md` R11-R13, `docs/domain/geometry.md`, `src/dt_ai/geometry/ucx_build.py` | user 2026-10-19, #166 |

## D135

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D135 | 2026-10-19 | (decided 2026-10-16, recorded 2026-10-19) Transform rotation is 0 for both NPM and VPM after reset; geometry is rotated to DWG contour during placement and reset bakes plan angle into vertex positions | `docs/domain/conflicts.md#npm-vpm-plan-rotation-after-reset`, `docs/domain/validation.md`, `docs/domain/areas/derivation.md` DER-07, `docs/domain/geometry.md` | #214 (user Artem) |

## D140

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D140 | 2026-10-09 | The window-type library (#4) reads `Win_Typical.max` only, names types by form and size with no project, treats the same subdivision within 2 cm as one type, counts fields from the row under the fanlight, keeps a balcony door and window as one frame, and leaves every entry unconfirmed until the user names it | `tools/library/build_window_types.py` | backfill #138 (tools/library/build_window_types.py; tests/test_window_types.py; #4) |

## D146

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D146 | 2026-10-13 | On the experimental from_source path only (build="from_source"), a decor mesh was left out of the body topology checks, because the body is never cut (OBJ03 2a); rejected for delivery acceptance by D079 (#117): a new passing model needs topology on every mesh incl. decor, and from_spec keeps the strict checks | `src/twinqa/geometry/checks.py` | backfill #138 (src/twinqa/geometry/checks.py; OBJ03 2a) |

## D147

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D147 | 2026-10-13 | On the experimental from_source path only (build="from_source"), an open loop flat on a horizontal face at its height was closed by contact (seated: a wall standing on a slab); from_spec keeps the strict open-edge rule, and after D079 (#117) this does not relax topology acceptance of a new delivery | `src/twinqa/geometry/checks.py` | backfill #138 (src/twinqa/geometry/checks.py) |

## D150

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D150 | 2026-10-20 | Vatutino Ground only: accept the 12 steep/flatter-junction vertices and their 6 associated face centres at the measured gaps in the frozen exception manifest, explicitly pinned by source/geometry and sample IDs; keep the 20 mm gate for every other sample and all lower-bound/other gates unchanged. This is not a general spacing-rule relaxation | `jobs/VATUTINO-SITE/ground-gap-exceptions.json`, `jobs/VATUTINO-SITE/ground-build-v014.md`, `jobs/VATUTINO-SITE/build_ground.py` | Artem option a, card #295 comment 2026-10-20; D150 reserved in [PR #308](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/308#issuecomment-6282784444) after checking open-PR reservations D136-D149 |

## D152

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D152 | 2026-10-20 | Every NPM/VPM deliverable handed to Artem is (1) xView-clean: Overlapping Vertices at 0.002 m = 0 and Overlapping Faces at 0.005 m = 0 (kernel invariant `xview_overlaps`, report-only until the v014 parity is accepted); (2) quad-dominant: triangles only where needed per the `quad_dominance` invariant [D129]; triangulation is an export-time option, never the delivered .max; (3) one material ID per texture (Multi/Sub-Object in Max, one FBX material per texture slot, fixed ID order recorded in the job). Artem: "мне лучше модели в квадах отдавать и на id разбиты по текстурам". (D151 is taken by the open #350 branch.) | `src/dt_ai/ops/inv_xview.py`, `docs/research/xview-parity-ground-v014.md`, NPM/VPM delivery | chat (user 2026-10-20), issue #370 |

## D153

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D153 | 2026-10-19 | (decided 2026-10-19, recorded 2026-10-20) Relief/layer-step tolerance is 1 cm: add TIN-edge cuts only in 4 m cells deviating by more than 1 cm; other cells stay 4 x 4 m; method C remains. Required TIN edges may be closer than 1 m in those correction cells (orchestrator clarification, not a user minimum-spacing rule) | `src/dt_ai/geometry/ground_cake.py`, `tests/test_ground_cake.py` relief refinement | backfill #337: Artem "разница в 1 см не страшна", [#295 comment 6265799957][ground-refinement-source]; [#308 clarification](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/308#issuecomment-6267750172) |

## D154

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D154 | 2026-10-19 | (decided 2026-10-19, recorded 2026-10-20) On steep relief raise a layer locally so the normal gap to the base is 5-20 mm (V004 band); flat ground keeps nominal +6 / +12 mm. D150 remains a separate frozen Ground exception, not authority for this earlier rule | `src/dt_ai/geometry/ground_cake.py` `raise_steep_layers`, `tests/test_ground_cake.py` | backfill #337: Artem "on steep relief raise a layer LOCALLY", [#295 comment 6274902891][ground-gap-source]; [#308](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/308#issuecomment-6274902436) |

## D155

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D155 | 2026-10-20 | Flora UV coverage is geometric for discrete images: VPM island/sprite-bbox intersection 80–95%, >95% only without neighbouring opaque sprites; continuous bark strips require >=95% island-area containment on bark, with V tiling allowed, not strip coverage; NPM whole-plant planes cover >=80% of the plant region and may extend beyond its bbox, no opaque clipping (1 px tolerance); retain the original bbox/island target in diagnostics; calibrate on valid original controls, not opacity density; report failing originals as source defects/limitations with separate listed repair routes, never lower the 80% threshold or edit originals in the diagnosis | `docs/domain/areas/flora.md`, `docs/research/flora-texture-diagnosis.md` | Artem voice decision, Kanban t_49156f66 comment 1542 (2026-10-20), coordination rule 48; scope clarified by orchestrator on the same card at 14:42 (continuous bark containment, discrete-image coverage); supersedes interim metric proposals; Artem accepted source-defect/limitation routing and valid-control calibration, Kanban t_49156f66 comment 20:27 (2026-10-20) |

## D156

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D156 | 2026-10-20 | Vyatskaya TOW02 NPM = OKS 013 of `0200_Vyatskaya_Vl_47_49` (names `SM_/M_/T_Vyatskaya_Vl_47_49_013_Main*`), as the accepted reference `SM_Vyatskaya_Vl_47_49_013_Main` (`0200_Vyatskaya_Vl_47_49_02.fbx`). Its atlas is a module atlas, not baked elevations: walls and every non-window part are solid swatches, only windows are drawn (dark frame + white glass, types from the source), glass polygons laid on them; palette of the accepted `atlas_2048_1` (wall #303031, roof #a3a3a3, glass #fafaff; m/r binary) | `jobs/vyatskaya-tow02/STATE.md`, `jobs/vyatskaya-tow02/scripts/texture_atlas_blender.py` | user 2026-10-20 (session takeover); D156 after checking main (D152) and open-PR reservations up to D155 |

## D157

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D157 | 2026-10-20 | Ground NPM option (a) supersedes D192: pair v014 triangles using D129 mergeability, accept up to 35 % residual triangles by polygon count for Ground NPM; Extension 2026-10-21, Artem «принимаю рекомендации» (card #371 18:21): Ground v015 NPM and VPM both use this whole-Ground ≤35 % paired-residual exception instead of strict D129, with per-slot reasons; export, xView and relief checks remain mandatory. Restore the 50,000 surface-polygon cap; the 180,000 whole-Ground triangle budget, 10 mm relief tolerance, fixed texture material IDs and xView 0/0 at 0.002/0.005 m remain unchanged. Keep D150 accepted exceptions, re-pin their identities if changed. Reject the 90k Steiner and coarse remesh routes. If xView cannot be cleaned in the authorized session, stop with the remaining offender list; this is not mesh acceptance. Extension 2026-10-21 22:57, Artem (card #371): strict-remesh from checkpoint 7ac17a9 replaces the pair-only construction restriction; texel_ready remains mandatory, aspect <=8 and VPM edge <=4 m, no texel exception. Define the strict-remesh plan separately and keep 50,000 surface polygons / 180,000 whole-Ground triangles and all other numerical thresholds unchanged | `docs/domain/areas/ground-surface.md`, `jobs/VATUTINO-SITE/ground-v015-pairing-session.md` | Artem accepted recommendation, card #371 comment delivered 2026-10-20 20:57; D153-D155 remain reserved externally |

## D158

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D158 | 2026-10-20 | Capability eval A (#390) may run with the operator-prepared Codex home, no OS sandbox, and auto-discovered external user skills as recorded limitations. Label the result repository + user skills, never repository-only; list loaded/named external skills. A separate Windows-account clean run is follow-up, not part of this acceptance | `evals/capability-b01/task.md`, `evals/capability-b01/reference.json` | Artem accepted the recommendation on card t_fd239f23 (operator comments 2026-10-20 16:11 and 20:27); #390 |

## D159

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D159 | 2026-10-20 | Extend D158 to capability eval B (#391): reference on closed pilot #111 may use C:/x/codex-eval-home without OS sandbox and with auto-discovered external user skills. Label repository + user skills and list loaded/named skills. A separate Windows account/VM remains later follow-up, not this acceptance | `evals/capability-ticket/task.md`, `evals/capability-ticket/reference.json` | Artem accepted the recommendation on card t_dad8c227 (operator comments 2026-10-20 23:43 and 23:5x); extends D158 |

## D160

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D160 | 2026-10-20 | VPM diffuse texel density lower bound is 512 px/m (SINTEZ 1.6.1), superseding only the 520 lower bound of D097; upper 1706 and NPM Ground 10-40 px/m are unchanged | `docs/domain/requirements-2026.md` | Artem “принимаю”, pilot #431, [PR #429 report §6 and proposed tasks](research/sintez-agr-checker-dissection.md#6-conflicts-with-docsdecisionsmd--docsdomain-listed-not-resolved--for-artem) |

## D161

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D161 | 2026-10-20 | VPM OKS regulation ceiling is 1 000 000 triangles per FBX excluding collision; the project target remains 150 000 per OKS FBX and one mid-poly master under D010. This extends, not relaxes, D010 | `docs/domain/npm-vpm.md` | Artem “принимаю”, pilot #431, [PR #429 report §6 and proposed tasks](research/sintez-agr-checker-dissection.md#6-conflicts-with-docsdecisionsmd--docsdomain-listed-not-resolved--for-artem) |

## D162

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D162 | 2026-10-20 | Check BOTH SINTEZ too-close UCX gap < 0.2 mm and the project D098 gap band 2 mm-1 cm inclusive; retain separate findings rather than replacing either check. UCX parity implementation is a separate task | `docs/domain/validation.md` | Artem “принимаю”, pilot #431, [PR #429 report §6 and proposed tasks](research/sintez-agr-checker-dissection.md#6-conflicts-with-docsdecisionsmd--docsdomain-listed-not-resolved--for-artem) |

## D163

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D163 | 2026-10-20 | UKEP signature verification is the applicant's responsibility, not ours; only report a missing signature file as info, not a blocking failure. Do not infer cryptographic validity from file presence. New checks are separate work | `docs/domain/validation.md` | Artem “принимаю”, pilot #431, [PR #429 report §6 and proposed tasks](research/sintez-agr-checker-dissection.md#6-conflicts-with-docsdecisionsmd--docsdomain-listed-not-resolved--for-artem) |

## D165

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D165 | 2026-10-21 | Every MAF decomposes lego-style into parts (vertical posts, horizontal bars, hung parts) joined with inserts (врезки) so the mesh does not multiply; fasteners are not modelled; ladder steps and rails are one mesh, the slide is a separate mesh inserted into the platform, the handrail inserts into the posts. Artem: "любой МАФ разбивается как лего" | `docs/domain/areas/groundel-maf.md`, `.agents/skills/model-maf/SKILL.md` | MAF grilling rounds 2026-10-21, issue #489 |

## D168

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D168 | 2026-10-21 | One library-wide MAF material ID list (light wood, dark wood, black cap, grey cap, solid colours, patterned wood, ...) is approved once; MAFs are assigned these IDs and a site composes its 512 set from the IDs it uses; new IDs only with Artem's approval. Artem: "approved once by the user" | `docs/domain/areas/groundel-maf.md`, `.agents/skills/model-maf/SKILL.md` | MAF grilling rounds 2026-10-21, issue #489 |

## D169

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D169 | 2026-10-22 | TEC26 sandwich-panel joints: the rib COUNT per facade comes from the building's own facade colour-solution sheet (AC08: long 30 ribs / short 12), spread evenly and symmetrically over the whole panel field, vertical joints only; the user texture gives the look of one joint, never the repeat. Artem via operator: rejected the 0.60 m v007 | `tests/jobs/test_tec26_ac08_pilot.py`, `jobs/TEC26-OKS/AC08/PILOT_REPORT.md` | PR #574 issuecomment-6342141336 |

## D170

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D170 | 2026-10-22 | All TEC26 buildings: the outer wall / frame band around the rib field (corners, top and bottom edging) is blue RAL 5015 like the panels with the sheet's thin dark outline, not RAL 7004; RAL 7004 only for doors, porches/steps, the plinth strip and parts the sheet shows grey; supersedes the Gate-1 «каркас 7004». Artem on AC08 v008: «почему внешняя стенка серая, когда как в презе должна быть синяя» | `tests/jobs/test_tec26_ac08_pilot.py`, `jobs/TEC26-OKS/AC08/PILOT_REPORT.md` | chat (operator note on card t_0cae7834, #559) |

## D171

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D171 | 2026-10-22 | All TEC26 buildings: the presentation `ТЭЦ26 на РР (1).pptx` facade slides «Схема фасадов ... Цветовое решение» are the authority for colours, colour bands, rib direction, rib count/step and which surfaces are blue / light grey / dark grey (DWG/PDF only where the slide is silent); the «Условные обозначения» legend is binding (sandwich RAL 5015 and RAL 7047 = the same ribbed sandwich texture, porches/doors/plinth/drainage RAL 7004, glazing frames RAL 9016, same RAL = KPP colour, no untextured sandwich wall); the acceptance picture is slide / VPM / NPM at one scale with the rib count under each. Artem: «почему-то сравнение с DWG по материалам, хотя есть преза», «Даже в DWG написано: сэндвич-панель и RAL» | `jobs/TEC26-OKS/scripts/finish_map.py` (`validate_legend`), `jobs/TEC26-OKS/scripts/compare_facades.py`, `tests/jobs/test_tec26_ac08_pilot.py` | chat (operator notes on card t_0cae7834, #559) |

## D172

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D172 | 2026-10-21 | Glass quads (flat window, 4 points, 90 deg corner, 6 points): a flat four-corner window with no bend keeps 4 points (one quad) so the glass has no breaks and no smoothing trouble; a corner bend keeps its segments so the bend stays; a 90 deg corner window is one element with a shared edge and 6 points (two quads). Quote: "на всех 4 угольных без изгиба окнах я оставил 4 точки чтобы не было изломов и проблем чо глаживанием, а на угловых изгибах я оставил сегменты чтобы сохранить изгиб, также обрати внимание как я сделал угловые окна под 90 градусов, раньше там были не сшиты точки и один плейн торчал из другого я сделал им общую грань, чтобы не они сшились и был единый элемент с 6 точками" | `docs/domain/geometry.md`, `docs/domain/areas/windows.md`, `docs/domain/patterns/opening-plane.md`, `docs/domain/patterns/INDEX.md`, `jobs/vyatskaya-tow02/STATE.md` | backfill #534 (decided 2026-10-21, logged 2026-10-23): 07124eda L1027, 2026-10-21T09:53:31Z; issue #534 |

## D173

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D173 | 2026-10-21 | 3ds Max xView overlap check, same thresholds as D152, not a second tolerance: Overlapping Vertices at 0.002 m and Overlapping Faces at 0.005 m; the gap between polygons is more than 5 mm. D152 remains the zero-count delivery rule. Quotes: "x vertices на 0,002 м проверяем а x overlapping faces на 0,005м"; "Перевел в меш, соответственно, выводил все точки на 0,002 метра. И провел оверлаппинг вертекс. У меня 0 точек показало. Теперь я прогнал оверлаппинг faces, у меня показало 1000 фейсов."; "для того, чтобы был расстояние между полигонами больше 5 миллиметров". Context only: "ок, жду результат xView" | `docs/domain/validation.md`, `docs/domain/geometry.md`, `docs/domain/patterns/INDEX.md`, `jobs/vyatskaya-tow02/STATE.md` | backfill #534 (decided 2026-10-21, logged 2026-10-23): 07124eda L1614, 2026-10-21T10:13:22Z; 07124eda L1899, 2026-10-21T10:48:12Z; 07124eda L1977, 2026-10-21T10:52:30Z; context 07124eda L1358, 2026-10-21T10:00:04Z; issue #534 |

## D174

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D174 | 2026-10-21 | Overlap fix by embed or move, not by cutting: move or sink the mesh (roof railing 6 mm into the drip; non-convex roof folds, flip the diagonal and shift 6 mm; where meshes meet joint to joint, sink one into the other by several millimetres; move balcony meshes instead of cutting them). The 6 mm figures are the agreed shifts in those sentences; a universal minimum of 6 mm for every overlap, and how it sits next to the 10 mm constructive embed, is open in conflicts.md. Quotes: "Ограждение кровли. Увести линию ограждения на 6 мм вглубь отлива."; "Лучше не обрезать, а утапливать. То есть, если там есть возможность, у нас идут стык в стык, то можно просто утопить один в другой на несколько миллиметров"; "Невыпуклые клады на крыше. Перевернуть диагональ, это согласен. Сдвиг 6 мм, согласен."; "Можно не обрезать, можно просто подвинуть, взять балкончики и чуть-чуть их подвигать, если они заходят, то есть вверх-вниз, вместе со стеклом, с ограждениями, на них просто, то есть не резать ничего, а просто подвинуть сами меши." | `docs/domain/geometry.md`, `docs/domain/conflicts.md`, `docs/domain/patterns/INDEX.md`, `jobs/vyatskaya-tow02/STATE.md` | backfill #534 (decided 2026-10-21, logged 2026-10-23): 07124eda L1977, 2026-10-21T10:52:30Z; issue #534 |

## D175

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D175 | 2026-10-21 | Weld wording, needs user confirmation. The quotes support a shared edge so corner-window points stitch, a welded trim in some places and a move in others, and bringing overlapped points together. They do not say welding is limited to coincident seam points. Quotes: "раньше там были не сшиты точки и один плейн торчал из другого я сделал им общую грань, чтобы не они сшились и был единый элемент с 6 точками"; "где-то нужно подрезать геометрию с welded, где-то нужно просто ее подвинуть"; "свести перехлёстнутые точки, это верно" | `docs/domain/conflicts.md`, `docs/domain/geometry.md`, `docs/domain/patterns/INDEX.md`, `jobs/vyatskaya-tow02/STATE.md` | backfill #534 (decided 2026-10-21, logged 2026-10-23): 07124eda L1027, 2026-10-21T09:53:31Z; 07124eda L1977, 2026-10-21T10:52:30Z; issue #534 |

## D176

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D176 | 2026-10-21 | F8 option A, accepted: align the upper wall to the lower wall and split both walls so they share points; keep the baskets. The acceptance names the option just offered. Offered: "Вариант A: верхнюю стену притянуть к нижней и разрезать обе стены так, чтобы у них были общие точки (рекомендую). Вариант B: уступ 6,5 мм." Accepted: "да, F8 вариант A, корзины оставить". | `docs/domain/conflicts.md`, `docs/domain/patterns/INDEX.md`, `jobs/vyatskaya-tow02/STATE.md` | backfill #534 (decided 2026-10-21, logged 2026-10-23): dda7a500 L71, 2026-10-21T12:03:59Z; dda7a500 L80, 2026-10-21T12:04:36Z; issue #534 |

## D177

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D177 | 2026-10-21 | Before export in 3ds Max, convert to Mesh and then Weld at 0.002 m. Do not round-trip through Poly after that weld: converting to Poly shows an overlap, Weld removes it, then Mesh and Poly again and the points drift. Quotes: "Скорее всего если сделать перевод в меш и велд на 0.002 метра максе то оверлап уйдет"; "Там прикол в максе что если переводишь в поли, то появляется оверлап если свелдить то пропадает потом в меш потом опять в поли и точки как бы разьежаутся, пока не понял почему, поэтому перед экспортом мы всегда кидаем в меш и потом уже велдим" | `docs/domain/export-import.md`, `docs/domain/patterns/INDEX.md`, `jobs/vyatskaya-tow02/STATE.md` | backfill #534 (decided 2026-10-21, logged 2026-10-23): 1a55b0bc L691, 2026-10-21T19:56:33Z; 1a55b0bc L739, 2026-10-21T19:59:49Z; issue #534 |

## D178

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D178 | 2026-10-21 | Weld fixes vertices, not faces. After a 0.002 m weld the user still had overlapping faces. Quotes: "Фейсы это не фиксит только точки"; "Перевел в меш, соответственно, выводил все точки на 0,002 метра. И провел оверлаппинг вертекс. У меня 0 точек показало. Теперь я прогнал оверлаппинг faces, у меня показало 1000 фейсов." | `docs/domain/validation.md`, `docs/domain/export-import.md`, `docs/domain/patterns/INDEX.md`, `jobs/vyatskaya-tow02/STATE.md` | backfill #534 (decided 2026-10-21, logged 2026-10-23): 1a55b0bc L849, 2026-10-21T20:06:28Z; 07124eda L1899, 2026-10-21T10:48:12Z; issue #534 |

## D179

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D179 | 2026-10-21 | Step strips narrower than 1 cm (the quote says "уже одного сантиметра"): removal is not approved. The user named those strips, was not sure, and leaned toward trimming the side walls, then said the second point would be looked at later. Exact 10 mm is not covered by "narrower than". This is not D153 (Ground relief, 1 cm) and it is not a rule that overlaps or other defects below 1 cm are skipped; both questions stay open in conflicts.md. Quote: "Ступени, убрать полоски уже одного сантиметра. Не уверен, тут скорее надо подрезать будет вот этот вот боковые стенки. Для того, чтобы убрать там тест-стык. Короче, по второму пункту еще посмотрим." | `docs/domain/geometry.md`, `docs/domain/patterns/floor-step.md`, `docs/domain/patterns/INDEX.md`, `docs/domain/conflicts.md`, `jobs/vyatskaya-tow02/STATE.md` | backfill #534 (decided 2026-10-21, logged 2026-10-23): 07124eda L1977, 2026-10-21T10:52:30Z; issue #534 |

## D180

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D180 | 2026-10-22 | Team-script defaults that differ from the regulation are NON-BINDING and no agent copies them; format per item: script value / pilot value / what stays binding. (1) UCX generator pads `UcxOuterPadding` 0.04 and `UcxDividerPad` 0.035 (`UCX_N_29.09.ms:23-24`, `:210`, `:417`, `:430-433`) are fractions of the bbox side for helper/grid extents (10 m side -> 0.4 m / 0.35 m), not fixed 0.04 m / 0.035 m gaps / pilot UCX gap band D098 0.002-0.01 m, D162 / the pilot band stays binding. (2) Hull merge 500 mm and 12 pieces (`UCX_N_29.09.ms:929`, `:932`) / UCX R11/R12/R13 protrusion 0.10 / 0.30 / 1.0 m / the three bands stay binding, the piece count is a script default. (3) Light index 001-050 (`agr_max_check_37.ms:460`) / names 001-250 / 001-250 stays binding. (4) A101 bitmap ladder 128-2048 squares and the 8-bit warning (`A101AGRLP.ms:1307-1327`) / delivery PNG is 24-bit, VPM sizes 2048 and 4096 / 24-bit and 2048/4096 stay binding; the alpha error matches the NPM ban and stays. (5) Flora Atlas padding 2 px and size list up to 8192 (`Flora Atlas.mcr:870-876`, `Flora Atlas V1.2.mcr:1449-1455`) / padding >= 8 px (NPM `island_padding_px_min`), sizes 2048/4096 / the pilot values stay binding. (6) Team overlap candidate angles about 11.5 deg (`cosTol` 0.98, `agr_max_check_37.ms:248`) and 8 deg (`overlapping_faces.py:170-178`) / xView about 0.81 deg, abs(cos) >= 0.9999 [D152] / the pilot value stays binding. Artem: "Мерж, принимаю рекомендации" | `docs/research/team-scripts-audit.md`, `docs/research/team-plugins-audit.md`, `docs/domain/validation.md`, `docs/domain/uv-textures.md` | Team-script audits #537/#538 (PR #539, #545), issue #551 |

## D182

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D182 | 2026-10-21 | Building facade elements that reach the ground (TOW02: the 26 fins) are extended about 1 m below ground level (z 0) so the building sits on the relief; the user's TOW02 finish used 0.808 m. Artem: "Опуск был под рельеф, лучше на метр опускать" | `jobs/vyatskaya-tow02/REVIEW-514.md` §9, `jobs/vyatskaya-tow02/STATE.md` | backfill (renumbered from D169-D171: id clash with TEC26 on main; review #514, PR #525) |

## D184

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D184 | 2026-10-21 | Finish colours follow the object's previous accepted iteration and the source: on TOW02 the copings (отливы), roof and band are dark, as in the old model and the source. Artem: "это цвет по прошлой модели, я посмотрел как была покрашена старая итерация и также да в исходнике кажется тоже там были отливы темные" | `jobs/vyatskaya-tow02/REVIEW-514.md` §9 | backfill (renumbered from D169-D171: id clash with TEC26 on main; review #514, PR #525) |

## D185

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D185 | 2026-10-22 | Job `vyatskaya-tow02` is closed at the review stage: the user's hand-finished `for_placement/0213_Vyatskaya_Vl_47_49_05.fbx` stays as delivered, no further 3ds Max fixes. Of the validate-delivery findings, the zero-area UV triangles are agreed; the texture findings are not accepted, because the texture requirements and rules still need work. Artem: "можно пока что закрыть жобу. Нет смысла мне в Максе опять все править, потому что я уже поправил. В плане неразвернутых полигонов согласен, с текстурами не согласен, потому что нужно еще допиливать мозги, требования, правила" | `docs/deliveries/vyatskaya-tow02-npm-user-v05-2026-10-21.md`, `docs/cases.md`, `jobs/vyatskaya-tow02/STATE.md` | Review #514, PR #525 (renumbered from D172) |

## D186

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D186 | 2026-10-22 | A new task from Artem goes through task intake before any code, issue or card: read the sources, ONE batch of <= 5 production questions with recommendations, a spec with his words + «Не трогать» + numbers, one first piece accepted, then fan out; card workers run a preflight and ask all open questions once at the start. Artem: "когда я ставлю задачу, агент запускает алгоритм, по которому он меня начинает спрашивать по задаче, перед тем как приступать" | `docs/agents/task-intake.md`, `AGENTS.md` | Telegram voice 2026-10-22 after TEC26 lost ~4 h |

## D187

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D187 | 2026-11-02 | Methods class building-body (#727) is measured on a narrower scope: plan contours and level heights are measured from the existing benchmark mesh, and every building-body row in `docs/methods/building-body/results.jsonl` is marked `synthetic` with its reason (`run_variant.py --synthetic`). Opening subtraction stays a capability tested on a synthetic schedule. Real DWG plans for kpp1/ac08/tow02 are a follow-up issue; the work does not wait for them. | methods / building-body (#727) | Artem via orchestrator, Kanban t_ccb189e5 (option a) |

## D188

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D188 | 2026-11-02 | Methods class ground-terrain (#733): the second Ground builder setting is a METHODS-ONLY build (`tools/methods/ground/builder_methods_only.py`); it skips the Ground quality gate, lists every failed gate in the methods table, and is never a delivery. No new [D150]-style exception; VATUTINO-SITE gates stay unchanged. | methods / ground-terrain (#733) | Artem via orchestrator, Kanban t_8548a050 (option b) |

## D191

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D191 | 2026-10-21 | Vatutino Ground v015 only: close the source footprint hole 0 notch by the exact XY triangle A=(-7691.007,-15248.688), B=(-7691.2305,-15248.001), C=(-7691.016,-15248.688), area 0.0030915 m2; disclose the approved contour deviation (sampled closing edge up to 4.317305 mm from original outline). All numerical thresholds unchanged: outline 2.2 mm, relief 10 mm, xView 0.002/0.005 m. Keep original inputs immutable; this is contour approval, not delivery acceptance | `jobs/VATUTINO-SITE/ground-notch-approval-v015.json`, `docs/domain/areas/ground-surface.md` | backfill (renumbered from D169 on merge with main, id clash with TEC26): Artem "принимаю", explicit authorization in card #371 comment 2026-10-21 16:58 |

## D192

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D192 | 2026-10-20 | Historical permission, superseded by D157 (not active). Vatutino Ground v015 only: allow up to 90,000 surface quads, a narrow exception to D097, using the conforming Steiner remesh from checkpoint 8612bcc; reject the coarse 4/5/6 m variants. Relief tolerance 10 mm, zero sub-5 mm gaps, xView cleanliness, quad dominance, and the NPM 180,000 whole-Ground triangle limit remain unchanged. Re-measure D150 junction exceptions by world coordinates before acceptance; this cap permission is not acceptance of any mesh | `docs/domain/areas/ground-surface.md`, `jobs/VATUTINO-SITE/ground-v015-90000-checkpoint.md` | backfill (renumbered from D170 on merge with main, id clash with TEC26): Artem accepted the recommendation, card #371 comment delivered 2026-10-20 20:27 |

## D193

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D193 | 2026-11-04 | Vatutino Ground v015 only, route A: deliver the v009 paired-fan candidate [D157] with a recorded `texel_ready` (#346) exception limited to the frozen per-face list (at most 8,511 NPM / 11,430 VPM faces, never a face not on the list; UV density stays inside D097). The remaining xView Overlapping Faces are fixed by construction, never by an exception; if they cannot be cleaned the session stops with the offender list. All other thresholds unchanged (50,000 polygons, 35 % triangles, 180,000 triangle-equivalent, relief 10 mm, outline 2.2 mm, xView 0.002/0.005 m, D150, D191). Artem: «принимаю рекомендации» | `jobs/VATUTINO-SITE/ground-v015-route-proposal-20261104.md`, `docs/domain/areas/ground-surface.md` | card t_e35c49dd comment 2026-11-04 20:21, issue #371 |

## D194

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D194 | 2026-11-04 | AGR Tools test polygon (#885) layout: one coloured base per tool version (База 0.1 ... 0.x) with a corner caption, stations inside each base (object + caption: which button, what result), a named top camera per base, captions readable at the default view; every new button ships with its station. User verdict on the first preview: «нифига непонятно» -> visual step-by-step guide with real Max screenshots. | `test-polygon/` (README, ACCEPTANCE.md, catalog.json, GUIDE/) | issue #885 comments 2026-11-04 (Artem, voice + preview verdict), PR #887 |

## D195

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D195 | 2026-11-04 | Methods class building-body, drawing rerun (#735): no DWG plan or Revit openings census exists for kpp1 / ac08 / tow02 (`openings_spec.json` is not on disk and cannot be regenerated: the census has no `openings.objects.json`), so all three objects stay synthetic like [D187]; no rebuild, every building-body row keeps its `synthetic` mark, and RESULTS.md shows each synthetic row next to its drawing row ("not measured: no drawing row"). A real DWG/Revit rerun is a follow-up only if Artem asks. Artem: «да» | `docs/methods/building-body/` (#735) | Kanban t_90a45688 comment 2026-11-04 23:05 |

## D196

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D196 | 2026-11-04 | AGR Tools: a face matID outside the Multimaterial `materialIDList` is a BLOCKING MatID finding (`empty_slot`) in the MatID check and the export gate, even though the 3ds Max FBX export wraps it onto a listed sub-material (the face gets another material in the delivery); the textures check keeps measuring the wrapped slot with the advisory `tex_matid_wrapped` | `adapters/max/agr_tools/checks_core.py` (`listed_submaterial_index`), `adapters/max/agr_tools/runtime.py` (`matid`, `_slot_gaps`) | issue #844 comment 2026-11-04 (Artem); renumbered from D195 on merge with main (id clash with #735) |

## D197

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D197 | 2026-11-05 | Job elv-tc-vpm delivery v002: attachments stand off their receiving surface by 6 mm instead of the 10 mm constructive embed, so V004 counts no embeds (max 4, the remaining pilot niche frame faces accepted); UCX names keep the project YAML form `UCX_SM_<Address>_Main_NNN`; V007 DirectX review on flat normal tiles accepted. Job-scoped; project-wide rules stay open (conflicts #43-#46). Renumbered D196 -> D197 at the main merge (main took D196). | job elv-tc-vpm; conflicts #44-#46 | Artem in chat, 2026-11-05 («Принимаю все») |

## D198

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D198 | 2026-11-05 | Every delivery of an OKS model also gets a non-triangulated work FBX (quads / n-gons as built; same pivot, object and material names, material slots and UVs as the delivered FBX; no UCX), next to the package, not inside it. The delivered FBX stays triangulated per the regulation (reg p.29 §3.17, V003) and [D152]. First applied: job elv-tc-vpm delivery v004 (`work_export_v004.py`). Renumbered D197 -> D198 at the main merge (main took D196). | all delivery jobs; [D152] | Artem in chat, 2026-11-05 («я хочу геометрию получать не триангулированную… Да, делай») |

## D199

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D199 | 2026-11-05 | Future modelling: decor and attachments (arches, light fixtures, frames and similar) are embedded 10-20 mm into the facade they sit on, closing the gap, instead of a stand-off that leaves them visibly floating. For job elv-tc-vpm the 6 mm stand-off of [D197] stays (the user fixes it by hand). The V004 self-intersection count of such embeds (conflicts #44) must be planned for per job. | all modelling jobs; geometry.md; conflicts #44 | Artem in chat, 2026-11-05 («лучше делать… врезку… на 10 на 20 миллиметров, тем самым закрывая щели… на будущее») |

## D200

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D200 | 2026-11-05 | Future modelling: edge loops and rings are continued through the mesh; a loop that starts and stops mid-run (welded, but not carried on) is a defect even when the mesh is closed. For job elv-tc-vpm v005 it is accepted as is (the user fixes it by hand). | all modelling jobs; geometry.md | Artem in chat, 2026-11-05 («кое-где идет луп, потом он обрывается… хочется луп этот продлить») |

[ground-refinement-source]: https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/295#issuecomment-6265799957
[ground-gap-source]: https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/295#issuecomment-6274902891
