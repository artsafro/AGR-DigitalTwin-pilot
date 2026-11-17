# AC08 (TEC26-OKS) — AGR Tools stages 0–9 in Max 2026 + native D221 (#1513, child of #1105)

## Кратко (RU)

AC08 впервые прогнан **кнопками AGR Tools 1.1.0** через этапы 0–9 в собственном batch 3ds Max **2026.3 (28.3.0.30732)**
на **реальной геометрии** AC08 (`AC08_source_geomfinal.fbx`). Сквозной прогон **не завершён**: этап 6 `vpm.build`
отказал на гейтах `seam` (до 3,58 px на внутренних рёбрах) и `texel` (>1 %), поэтому этапы 7–8 отказали, а этап 9
заблокирован (`export.zip` = planned, пакета нет, `qa.package` не запускался). Гейты не ослаблялись; отказ сохранён.
Диагностический прогон с временной подстановкой материала id 1 показал: отказ `vpm.build` **не зависит** от
нерешённого материала — это поведение `vpm.build` на геометрии/UV AC08 (owner: AGR Tools runtime, `vpm.build`).
**D221 подтверждён нативно** на явно СИНТЕТИЧЕСКОЙ фикстуре (у AC08 нет стекла): два стеклянных id 39 и 48 — все
грани в UDIM 1001, `agr_udim_table` = {39: 1001, 48: 1001}, тело плотно {2: 1001, 11: 1002}, карт стекла нет;
FBX прочитан обратно независимо. `passed=true` не заявляется; приёмка Артёма — отдельно и не дана.

## Authorization, environment, ownership

| Item | Value |
|---|---|
| Slot | Artem 2026-11-16 «Макс вроде освободился, можно использовать» (#1513 issue comment); #1504 closed (Max serialized) |
| Max | `3dsmaxbatch.exe` 3ds Max 2026.3 (28.3.0.30732), Python 3.11.12; owned batch processes only, via `hermes_kanban/scripts/dcc_batch.py max --version 2026 --card t_e38d6fb5` (shared session lock) |
| First call | read-only `dcc_batch.py max --ping` (05:58, exit 0); no 3dsmax.exe was running before or after (only foreign `3dsmax-mcp` servers, untouched) |
| Document | empty batch document (driver asserts `not maxFileName`), units metres, scale 1.0; scenes saved only under the run folder |
| AGR Tools | runtime 1.1.0 from main `c62cedddde111b8732c6ea48dafc34946d9dc992`, MZP built by `tools/max/build_agr_tools.py`, sha256 `c2d985b215443896175fee0021f63d1cf6dec20c5beb51a7a698bfd06d7e990c`, installed into the run folder (no user folders). The user-installed AGR Tools 1.1.0 also registers at batch start; its MZP identity is **not** certified |
| Scene owner | card t_e38d6fb5 (dt-worker); Artem's Max sessions not touched |

## Inputs (pinned)

| Input | Path | sha256 |
|---|---|---|
| AC08 source FBX (accepted geometry export of node `АС.08` + `Colizii_044`, #753) | `G:/Мой диск/AGR-assets/tec26/ac08/source/AC08_source_geomfinal.fbx` → scratch copy | `9cae468e714118c501dfffa77531aabecd88662c4e34d0be57274d446bb3e5fd` |
| AC08 drawing | `.../ac08/source/22E56-AR2-1002-AC08.dwg` | `cb90ed375df4fd708b7a69c6d018600347953245f0f6bde396f394bee3e1fa52` (= `materials.json` drawing sha) |
| Material evidence | `jobs/TEC26-OKS/AC08/materials.json`, `PILOT_REPORT.md` (v010 legend) | in git |
| Passport | **none in git** (`jobs/TEC26-OKS/passport.json` absent); stage 0 `project.passport` wrote one into the run folder only | run evidence |

Source readback: `АС.08` 348 tris, ids {1: 254, 2: 30, 3: 64} tris, bbox X 30.92..36.98, Y −1.11..1.33, Z −2.05..2.55 m.
Face-id map (harness, not a decision): 2 → 11 `panel_ribbed_ral5015`, 3 → 2 `paint_ral7004` (evidenced);
**1 → 999 sentinel** (roof + frame + skirt = `unresolved_mixed_id`, awaiting Artem; 999 is not a library id).
Delivered v010 packages (`.../ac08/v010/*.zip`) were not opened or changed.

## Nine-stage table (run-v004, final)

| Stage | Big button | Status | Receipt (codes / refusal) |
|---|---|---|---|
| 0 Паспорт | project.passport | findings | `role_missing` ×2; `source.intake` done: copy moved by −origin_m (30, −2, −3), size 6.059 × 2.438 × 4.597 m (scale 1.0); `scene.source_class` done |
| 1 Бадик | body.prepare | done | levels L1 = 3.0 m (±0.000 after intake), roof 5.550 m; attach → `BODY_MultiMat0_001`; move_apart 0 moved; grid_cleanup, small_parts done |
| 2 Окна | win.place | ambiguous | «нет проёмов и меток» — AC08 has no openings/markers; win.generate, glass_planes skipped |
| 3 Капсулы | body.capsules | done (no-op) | `no_openings` |
| 4 Крыша | body.roof | done (no-op) | `no_roof_loop`, no slab |
| 5 Материалы | mat.table | findings | `id_not_in_library` (id 999 = unresolved id 1); `mat.tiles` refused (empty input) |
| 6 ВПМ | vpm.build | **refused** | preview `seam` (≤ 3.580 px internal/chain edges), `texel` (> 1 %): «nothing to build»; retry without library_path — same; `udim.distortion` findings (anisotropy, degenerate_uv, texel_scale) |
| 7 НПМ | npm.build | **refused** | `uv_off_grid` (no VPM copy exists); `atlas.facade_strip` done |
| 8 НПМ→ВПМ | npm.to_vpm | **refused** | no npm table / nothing selected; `udim.udims_to_ids` `udim_ambiguous` |
| 9 Сдача | pack.deliver | ambiguous → **stage blocked** | A (nothing skipped): qa.preflight fail (`fbx_ground_missing` ×8), qa.names fail (`name_symbols`/`name_separator` on source sub-materials `Material #3 Slot #9/#10`), qa.tris pass, ucx.audit pass, light.check error (no lights), qa.sintez error (no report), ucx.gap error, qa.omk_te fail (no table), export.checked fail (`cleanup`), **export.zip planned (not written)**. B (labelled skips) also blocked. `export.place_by_passport` refused (no FBX) |

Per-button receipts (status, codes, report file names, timings, triangles per stage): `receipt.json`; raw reports
`run-v004/reports/*.json` on Drive. Harness steps (not buttons): source hidden after intake; ±0.000 = 3.0 m after the
intake shift; working VPM name `Nku_1_VPM_Main` for `qa.names_fix`; `AGR_EXPORT_PATH`/`AGR_ZERO_M=3.0000` artist inputs;
1 node moved to layer 0.

Separate outcomes (none is user acceptance):

| Gate | Outcome |
|---|---|
| Master QA before triangulated export (stage 9 checks) | blocked (see stage 9) |
| Delivery export / package | not written (export.zip planned) |
| qa.package | skipped: no archive |
| SINTEZ AGR Checker | not run (Blender extension; `qa.sintez` refused without its report) |
| Artem's acceptance | not requested; open |
| passed | **false** |

## Diagnostic run (run-v003, not acceptance)

`AC08_ID1_DIAG=1` (id 1 → `paint_ral5015`, temporary, labelled DIAGNOSTIC): stage 5 becomes done, but stage 6
`vpm.build` is refused with the same `{seam: 1, texel: 1}` and 7–9 stay refused/blocked. So the stage-6 blocker is
independent of the material decision.

## D221 native check (SYNTHETIC fixture — AC08 has no glass)

Fixture: Box 6 × 3 × 4 m, 4 segments, face ids cycling 11 / 2 / 39 / 48; `vpm.build` with `glass_ids [39, 48]`,
`library_path` = library copy → **done** (no findings).

| Check | Result |
|---|---|
| Glass copy `SYNTH_D221_Body_glass_VPM_001` | 128 tris, ids {39: 64, 48: 64}; every face in tile 1001; UV u 0..0.833, v 0..1 |
| `agr_udim_table` (glass) | {39: 1001, 48: 1001} — agrees with the faces |
| Body copy numbering | {2: 1001, 11: 1002} — dense, glass ids absent |
| Maps written | `T_Synth_1_{Diffuse,ERM,Normal}_1.{1001,1002}.png` + `vpm_table.json`; **no glass map**, no `T_*_MainGlass` |
| Independent readback (FBX `SYNTH_D221_vpm.fbx` sha256 `38084fe4…` in run-v004, imported into a reset scene) | glass node 128 tris, sub-materials `ID_039`/`ID_048`, all faces in 1001; body `ID_002` → 1001, `ID_011` → 1002; pos 0, scale 1, rotation identity |

Harness note: `vpm.build` copies carry no material (`material: None`); for the FBX readback the harness assigned a
Multi/Sub whose sub names carry the ids (FBX renumbers Max ids).

AC08 output readback: no delivery FBX exists, so the harness exported the stage-9 working nodes
(`SM_Nku_1_HARNESS_NOT_DELIVERY.fbx`, labelled, not a delivery) and read it back: `SM_Nku_1_Main` 348 tris / 193 verts,
3 materials, bbox Z 0.954..5.550 (±0.000 at 3.0), identity transform, UV u −0.083..1.0 (source UVs; no VPM layout);
7 `UCX_SM_Nku_1_Main_001..007` boxes of 12 tris each.

## Remaining blockers (exact)

1. **Stage 6 `vpm.build` refuses real AC08** (`seam` ≤ 3.58 px, `texel` > 1 %) → owner: AGR Tools runtime (`vpm.build`
   on real-building geometry). Fixing it is a code change outside this execution card.
2. **Material of source id 1** (roof + frame + skirt, `unresolved_mixed_id`) → owner: Artem (materials.json questions).
3. **AC08 passport** is not in git (`jobs/TEC26-OKS/passport.json`) → owner: K1 / AC08 job (needs project facts).
4. Stage 9 inputs absent for AC08: Ground FBX (`fbx_ground_missing`), ОМК ТЭ table, lights, SINTEZ report; source
   sub-material names with spaces (`Material #3 Slot #9/#10`) fail qa.names.
5. Stage 2/3/4 are no-ops on AC08 (no openings, no roof loop) — recorded as such, not as a passing window/roof run.

This card's native acceptance is therefore **not met**: the failing evidence and owners are retained; the issue
should stay open (PR uses `Refs #1513`).

## Evidence

`G:/Мой диск/AGR-evidence/1513-ac08-agr-stages/v001/` — 353 files sealed by `SHA256SUMS.txt`
(sha256 `2711d49713e9ce8f74608b567e9d5a8b8c21b6dc5c525a5e02f8c440b5b4bb02`), `sha256sum -c` OK after copy;
committed copy `DRIVE-SHA256SUMS.txt`. Runs: v001 (first harness version), v002 (with ±0 bug: AGR_ZERO_M=0.0 after the
intake shift → false `drop_short`), v003 (DIAGNOSTIC id 1), **v004 (final)**; Max logs `max-run-v00*.json`; MZP; driver.
The staged `installed/` runtime (1262 files per run) is omitted: reproducible from the MZP.

Reproduce: `env -u VIRTUAL_ENV AGR_TEST_OUTPUT=<new dir> AGR_TEST_PACKAGE=<mzp> AGR_TOOLS_REPO=<worktree>
AC08_FBX=<scratch copy> AGR_PYTHON=<worktree>/.venv/Scripts/python.exe python
C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --file tests/max_tools/run_ac08_stages_native.py
--version 2026 --card <card>`.
