# Standing #56 — Observed aperture edges, OBSERVE result

**Русское резюме. H56 подтверждена в пределах трёх проверенных входов.** На 63B v007 зонд по наблюдаемому краю сработал: смещённый на 50 мм сегмент теперь приводит к «не измерено», а не к тихому пропуску зонда, как в #55. На 45 активных пробах — ни одной ложной числовой глубины свыше 15 мм; ещё 18 отрицательных контролей оставили глубину без изменения. Медиана F56 = 0, повторы [0, 0, 0], размах 0. Это тест считывания глубины на одном проёме в трёх входах, не доказательство точности формы здания и не основание включать новый гейт. Код рабочих проверок, модели и пакеты не изменены. PR нет.

## Clean readback and parity

Frozen contract `337989a5`; measured runner revision `59f1584927bb6057f91b01fc7269e4d03355eddb`, SHA-256 `ba2047338bdefa1084a0a7f2add599b266a7068b1fc0e850282362b6791f28f3`. Run status `complete`; timed pair 2.341 s, total 34.614 s (cap 180 s). All 30 independent Blender 5.1.2 imports preserved original frozen scorer payloads except candidate file path. Pin pre/postflight and #54 guards passed. G22 v002r1 retains six openings vs zero for v001. At 63B the 0.50 m source-wall interpretation yields v007 0/5 failed depths vs 5/5 failed for each rejected variant; the 0.71 m key interpretation reverses that order. Neither interpretation was adopted here.

| Input / target aperture | Clean depth median (m) | Observed edges, both slices (m) | Key edges (m) |
|---|---:|---|---|
| G22 `C_none`, `4259581` | 0.150040 | 1.139992 / 2.940064 | 1.1400 / 2.9401 |
| 63B accepted v007, `…194b464` | 0.499999 | 1.224342 / 3.368707 | 1.1376 / 3.4376 |
| 63B rejected v006, same aperture | 0.709980 | 1.137565 / 3.437663 | 1.1376 / 3.4376 |

Clean paired 63B margin (v006 minus v007) 0.209981 m in all three comparisons, range 0 m. This is measured separation, not a determination of architectural intent. The accepted v007 aperture still has its original edge mismatch against the key.

## Injected controls (section data only)

| Probe | Response on all three inputs × 3 reps | Left/right support change per sampled height |
|---|---|---|
| `rear_in`, `front_in` (±0.05 m) | `noncoplanar`, no depth | +1/+1 |
| `one_side` (+0.05 m) | `noncoplanar`, no depth | +1/0 |
| `tiny` (+0.01 m) | Numeric Δ −0.005031 / −0.005043 / −0.005005 m (G22/v007/v006) | +1/+1 |
| `rear_out`, `near_miss` | Numeric Δ 0 (negative controls) | 0/0 |
| `rail` | `flank_missing`, no depth | −1/−1 |

36/45 active probes fail closed, as expected; 9/45 return a sub-tolerance numeric change. No off-target changes beyond the frozen bounds; status spreads and numeric depth spreads among repeated observations are zero. No missing slots or `not_exercised` probes. These injected findings are not new native-geometry measurements. Shared section/datum primitives do not establish independent surface ownership: the anchor is independent of selected support **indices**, not independent of the gap detector itself.

## Not measured / next use

No judgement on whether the v007 narrow strips are the intended exterior/frame or a source-key mismatch; audit source and native face ownership before changing the aperture width reference. No new KPP1/Sokolniki pair, visual rubric score, Yes-bias, two-order decisions or κ. The v002 sheet/D375 and NW contour A cannot label exact model bytes by themselves. Results are ready for review as OBSERVE evidence, not for deployment.

## Replay and verification

Run the [contract command](../autoresearch-body-form-r56.md) from this branch to a fresh directory on the fixture PC. [Probe receipt](receipt.json): recorded runner/input references, per-height changes, per-probe spreads. Raw #54 output `C:/x/t_80b4168c-r56/run01/fresh/receipt.json`, SHA-256 `859ac7304bd735d331123718d86c124c42be6212b2ba59d877ec3f5b3ab2d101`. Original probe receipt `C:/x/t_80b4168c-r56/run01/receipt56.json`, SHA-256 `8f34fa7d7fae6a7ecc740b6e4fd6a4203cae54c14d42f4063656f81b22bc2e06`. See contract for fixture dependencies and conditional budget stop; no hidden key published.

Affected tests: `uv run --offline pytest -q tests/test_body_contours.py tests/test_verifier_1577.py tests/test_blender_exit_code_guard.py --basetemp C:/x/t_80b4168c-tests` — 122 passed. `bash C:/Users/artsafro/hermes_kanban/scripts/repo_guards.sh` — 542 passed, 1 warning; `repo_guards: GREEN`. Full suite not run (no production change, no PR).
