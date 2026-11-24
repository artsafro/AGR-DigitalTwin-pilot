# Standing #55 — Reveal-flank ownership vs decoy segments, round 1

**Кратко. H55 опровергнута по замороженному правилу, но ложных глубин нет: F55 = 0 из 42.** На G22 все 7 «чужих» сегментов отработали как предсказано (в полосе и у края проёма → «не измерено», вне полосы и не у края → глубина та же, 0,01 м → сдвиг 0,005 м, сквозной поручень → «опоры нет»), 21/21, во всех трёх повторах. На 63B v007 четыре зонда (задний, передний, односторонний, 0,01 м) не изменили ничего: зазор в стене у v007 на 0,087 / 0,069 м уже ключа (замороженный счёт и так ставит ему `edges fail`), поэтому сегменты, поставленные по краям ключа, не касаются реального края и селектор их не берёт. Это не ошибка селектора, а слабость моего условия «зонд задействован» (не требовало касания наблюдаемого края). Код, модели, допуски не менялись; PR — только контракт, сценарий и квитанция.

## Calibration (reused #54, unchanged)

[Contract](../autoresearch-body-form-r55.md) frozen at `2d408c29`; script at `497c4b19` (SHA-256 `127ab112…`). #54 replay fetched from `cc470a6d` (SHA-256 `f1d1d5c5…` asserted) and run as is: status `complete`, 30 fresh Blender 5.1 imports, wall 34.0 s (cap 180 s), postflight pins OK, `all_guards = true`, #54 hypothesis reproduced `confirmed` (primary 4.8e-14 m, spread 0), parity of all 30 original reports, G22 A>R, 63B source-wall 0/5 (v007) vs 5/5 (v002–v006). Calibration holds, so H55 is scored.

## Decoy probes (2 accepted witnesses × 7 probes × 3 reps = 42 trials)

| Probe | G22 C_none `4259581` (status, Δdepth) | 63B v007 `…194b464` | Expected |
|---|---|---|---|
| `rear_in` 0.05 m | noncoplanar, — (counts 2/2) | measured, 0 (counts 1/1, decoy unused) | noncoplanar |
| `front_in` 0.05 m | noncoplanar, — | measured, 0 (unused) | noncoplanar |
| `one_side` 0.05 m | noncoplanar, — (2/1) | measured, 0 (unused) | noncoplanar |
| `rear_out` 0.20 m | measured, 0 | measured, 0 | measured, ≤0.001 |
| `near_miss` 0.06 m back | measured, 0 | measured, 0 | measured, ≤0.001 |
| `tiny` 0.01 m | measured, −0.00503 m | measured, 0 (unused) | measured, 0.001–0.010 |
| `rail` −0.08 m spanning | flank_missing | flank_missing | flank_missing |

- **F55 (false numeric depth > 0.015 m): 0/42.** Exercised by the frozen band rule: 42/42; as expected: 30/42 (the 12 misses are v007 × 4 probes × 3 reps); off-target changes: 0; status spread across reps: 0, depth spread 0.
- Fail-closed losses (clean measured → no depth): rear_in 3, front_in 3, one_side 3 (all G22), rail 6.
- Cause of the v007 misses (readback, rep 1): observed wall gap at both opening slices `1.224..3.369` m vs key `1.138..3.438` m; the face has 0.087 m strips `1.137..1.224` and `3.369..3.438` at d = 0. Decoys placed at key edges end 0.069–0.087 m from the observed edge (> 0.03 m edge tolerance) and are ignored — they behave as `near_miss`. The frozen score already reports `edges: fail, max edge delta 0.087 m` for this opening (the 63B key comes from the v002 builder ring, #51/#52).

## Decision

**Hypothesis:** `refuted` under the frozen rule (deviating status on exercised trials). Substantive reading: the #54 flank selector produced no false depth on any probe and failed closed on every edge-touching in-band decoy that actually reached it (G22); on 63B the edge-touching probes were **not measured** in substance because key-placed decoys missed the observed edge. Not a gate, not a general ownership proof. **Review readiness:** ready as OBSERVE evidence. No KEEP, no production code.

Lesson for the next contract: "exercised" must require the decoy to touch the *observed* gap edge (within 0.03 m), recorded per trial, else `not_exercised`.

## Replay

`python -X utf8 docs/research/autoresearch-body-form-r55/replay.py C:/x/<new dir>` from this branch (needs the fixture PC: C:/x/t_563a40f7, C:/x/t_fb3a0b98-r51, C:/x/autoresearch-body-form-r40, C:/x/t_1276e6bc-r53, Blender 5.1; pins checked by #54 code pre/post). Raw: `C:/x/t_c5f7b734-r55/run01/run/receipt.json` SHA-256 `d215ee1b…c58c5`; [receipt](receipt.json) = `receipt55.json` SHA-256 `4d867886…13a7`. Copies: `G:/Мой диск/AGR-evidence/standing55-body-form-flank-decoys/` (SHA256SUMS.txt `99b20631…2760`). Hidden keys not copied to Git.
