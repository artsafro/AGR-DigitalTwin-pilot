# Body corner windows — standing #23 (OBSERVE)

**Кратко.** #22 нашёл, что сигнал отклонённого 63C v001 сидит в одном и том же углу на каждом этаже. Здесь
проверяем причину на уровне исходного floor.json: окно, которое общий построитель stage 1 кладёт поверх
угла контура. В stage 2 тот же построитель такие окна уже отказывает (`straight(tol_deg=1.0)`), в stage 1 — нет.
Ядро, оценку и модели не меняем.

## Frozen contract (written before the replay below was run)

**Continues** #12/#13 (origin/main) and #19–#22 (63C localization, branch `research/autoresearch-standing-22`
@ `8e44c0a2`). Not owned elsewhere: #1722 (63B stage 2), #1649 (atlas), #1609/#1627 (KPP1), #1736/#1742
(builder) are not touched.

**One number.** `margin_primary` = corner-spanning stage-1 windows on rejected 63C v001 minus the maximum on
the accepted training floors. A window is corner-spanning when the builder's own predicate
`straight(run_points(ring, s0, s1), tol_deg=1.0)` is false; both functions are loaded verbatim (AST) from
`jobs/garibaldi22/body-training-1619/hooks/floor_from_dump.py` blob `3b865d46` (= origin/main `346b9b12`).
Pass: `margin_primary` ≥ 1. Held-out check: every G22 floor = 0; any positive is listed as a false-positive
candidate for Artem, not relabelled.

**Secondary (declared after a look).** Before writing this contract I looked at the training floors with a
vertex-angle script (63C v001 = 4, v002 = 0, 63A = 0, 63B v007 A = 1 at a 7.1° kink, B = 0). `tol_deg = 15`
is therefore chosen after seeing training data and is reported only as secondary; G22 floors were not looked at.

**Attribution.** Share of the 63C v001 irregular face area (core `_angles`, corner > 15° off 90°, all dump
faces; #13 counted 176 faces) whose XY centroid lies within 2.0 m of a corner flagged above. Same for
accepted v002. Supporting evidence only.

**Fixture.** 10 floor.json inputs (`G:/Мой диск/AGR-evidence/1619-body-training/`: tower-C v001/v002,
tower-A v005 (byte-identical to v004), tower-B v007 floor_A/floor_B; held-out G22 round1-k3 j6, round2-k1 z/z2,
round2b-k1 v003, round4-k2-stage1 v002) + 2 retained #15 dumps (`C:/x/ar15/r1/tmp/63C-v00{1,2}.1/dump.json`).
SHA-256 per input in `autoresearch-body-corner-windows-harness/inputs.json`, checked before and after.
G22 floor→version mapping is by directory name and not re-verified; no G22 version was rejected for corners.

**Replay.** `../../.venv/Scripts/python.exe docs/research/autoresearch-body-corner-windows-harness/replay.py OUT.json`.
3 repeats in one process; payloads must be byte-identical (paired spread 0), else `noisy` and nothing is reported.

**Budget / stop.** One replay (≤ 5 min). Zero builder, score or threshold candidates are applied; the round
stops at the first complete receipt. If the margin passes and held-out is clean, the result is a *would change*
for a separate PR: run the existing stage-2 corner refusal in stage 1 as well (refuse or split the window).

**Forbidden.** Editing inputs, delivered packages, builder/QA/tolerances, other cards' files; deselecting
tests; promoting any build. Clean checks: hashes, repeat identity, builder blob parity. Injected: none.
Not measured: native readback, Blender rebuild with the rule, design-drawing attribution, 63B v001–v006
(mesh-only artefacts, no floor.json), KPP1 (different builder).
