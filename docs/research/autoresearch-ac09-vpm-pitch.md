# Autoresearch #79 — held-out specificity of the #78 VPM pitch census on AC09

**Кратко (по-русски).** Карточка t_724b61aa (standing #79), режим OBSERVE. Журнал тренера #1855 пока пуст
(у #1608 нет строки результата), поэтому работа идёт по запасному фокусу «качество текстур/атласа».
Проверяем замороженный в #78 счётчик шага швов (медиана построчных медиан) на третьем объекте, который
не использовался для настройки: финальный VPM TEC26 AC09 (Sakv_1). Если на всех 4 панельных
4K-тайлах ошибка шага ≤ 0.03 — счётчик специфичен и на чужом объекте; если хоть один тайл > 0.03 —
гипотеза опровергнута. Производственный код, пакеты и спецификации не меняются. Итог — в разделе
«Round log» ниже.

Contract frozen **before** any score on AC09 was computed (only the ZIP inventory and SHA-256 were read).

## Why this target

- Focus override (#1855 trainer): no ledger row exists yet (#1855 0 comments; #1608 only the
  2026-11-24 start decision) -> fallback NPM/VPM texture focus.
- Chain: #72 pitch census confirmed on AC08 v007 (rejected 600 mm) vs v010; #77 refuted its
  specificity on KPP1 (perforated tile); #78 fixed aggregation (median of row medians), confirmed on
  AC08 + KPP1 — but both objects were used for tuning. #78 next target: a third object before any gate.
- AC09 is an independent object (own facade pitch per field, 4 full panel tiles), delivered in
  `AGR-evidence/tec26-oks/FINAL-2026-10-22/manifest.json`; no rejection on record.
  Label = **delivered final, no explicit Artem accept/reject** (accepted control by delivery, not by a dated decision).

## Hypothesis H79

The unchanged #78 candidate `median_of_row_medians` gives E <= 0.03 on every measured AC09 full
Diffuse tile, while the AC08 v007 rejected tile still scores >= 1.0 in the same run.

## Metric and command

- E(tile) = |observed_px / expected_px - 1|; observed_px = #78 `candidate()` (pinned
  `origin/research/autoresearch-standing-78@1358b8262ce2f93a15d3125443c308305d31b8cf`, which itself
  pins #72 `e9179247`); expected_px = P[0] * 4096 / S from
  `jobs/TEC26-OKS/AC09/vpm_textures.json@b735e90f` (the commit that built the delivered ZIP, #566).
- E79 = max E over measured AC09 tiles. Binding by `udim` of each `kind=full` finish; the tile's
  modal RGB must equal the spec `rgb`, otherwise the tile is `not_exercised` (no score).
- Command: `uv run --frozen python docs/research/ac09-vpm-pitch-r79/replay.py tmp/r79-NEW`
- Fixture: `G:/Мой диск/AGR-evidence/tec26-oks/FINAL-2026-10-22/AC09_SAKV/VPM/SM_Sakv_1.zip`
  SHA-256 `e41c89a150434145ff8576216b09f71af95564882afea81f0b4ed9d9569ae832` (= build-v001 SHA256SUMS);
  checked every round. Expected measured tiles: 1001, 1002, 1008, 1009 (4096 px); 1003-1007 are
  256 px placeholders -> `not_exercised` (solid colour, no texel/pitch requirement).
- Positive control (same run, every round): AC08 v007 tile 1001 via the #71 loader (Drive pins), the
  same candidate, expected = AC08 `PanelVJ12_RAL5015`; must be >= 1.0 and equal the #78 receipt
  value 2.220998038374616 (|diff| <= 1e-9 = baseline parity).

## Witnesses (per measured AC09 tile, expected direction and bounds)

- `half_pitch` (columns x2, frequency doubles): E in [0.45, 0.55]; applies when clean E <= 0.03.
- `brightness_plus8`: |E - E_clean| <= 0.01 (invariance).
- `changed_px` recorded; 0 changed pixels -> `not_exercised`, reported as not measured.

## Rounds, budget, stop rule

- 3 fresh rounds (re-read ZIP bytes + SHA, re-decode). Median and spread of E79; spread <= 0.001.
- Budget: first round > 60 s or total > 240 s -> `budget_stop` -> inconclusive (not a hypothesis outcome).
- Confirm-vs-new-candidate budget: 1 candidate (the frozen #78 one), 0 new candidates. One run.
  An amendment is allowed only for an input/parity bug, recorded before re-running, never after seeing E79.

## Verdict rule

- `confirmed`: complete, 3 rounds, >= 3 AC09 tiles measured in every round, positive control >= 1.0 and
  parity true, spread <= 0.001, E79 median <= 0.03, all exercised witnesses in bound.
- `refuted`: complete and any measured AC09 tile E > 0.03 (positive control and parity true).
- otherwise `inconclusive`.

## Forbidden shortcuts

Changing rows / threshold / aggregation after seeing AC09; editing the spec, ZIP or any delivered
package; tuning on AC09; deselecting tiles that score badly (only the frozen binding rule may drop a tile);
touching other cards' files; production code changes (OBSERVE only).

## Round log

(filled after the run, see below)
