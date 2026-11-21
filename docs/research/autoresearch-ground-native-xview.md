# Standing #33 — Ground near-vertex counter vs native 3ds Max xView (OBSERVE)

## Итог (OBSERVE)

**H33 опровергнута** (по тексту контракта: серия завершена, правило нарушено на 5 из 9 входов; ярлык квитанции —
`inconclusive`, см. ниже). Нативный 3ds Max 2024 xView «Overlapping Vertices» 2 мм в состоянии Editable_Poly
(импорт FBX → `convertToPoly`, как в работе Артёма) находит близкие вершины там, где счётчик #32 на чтении Blender
даёт 0:

| вход | V репо (#32, Blender) | V Max (3 прогона, разброс 0) | вершин Blender → Max poly | Qv Max на T #32 |
|---|---|---|---|---|
| A1 Vatutino v015 (принят) | 0 | 0 | 27 431 → 27 431 | 0 |
| A2 Skolkovo (сдан) | 0 | 0 | 3 026 → 3 026 | 0 |
| A3 COD (сдан) | 0 | **310** | 1 504 → 1 755 | 1 106,7 |
| A4 Donskoy (сдан) | 0 | **307** | 6 766 → 6 971 | 266,3 |
| A5 Ostrov (сдан) | 0 | **278** | 15 108 → 15 303 | 93,4 |
| A6 Kasatkino (сдан) | 0 | **580** | 30 760 → 31 175 | 97,8 |
| A7 Volokolamskoe (сдан) | 0 | 0 | 10 548 → 10 548 | 0 |
| A8 Stolbovo (сдан) | 0 | 0 | 5 504 → 5 504 | 0 |
| W1 Vatutino v014 (не прошёл D152) | **0** | **118** (= #370) | — → 27 340 | 25,5 |

Что это значит: (1) счётчик #32 на чтении Blender слеп к классу дефекта, который видит Max после перевода в poly —
расщеплённые немногообразные вершины (в poly-состоянии у A3–A6 вершин больше, чем в FBX). (2) В нативном состоянии
четыре из семи **сданных** Артёмом NTR Ground несут 278–580 перекрытых вершин, а «плохой» v014 — 118; плотность
близких вершин в Max не отделяет принятые от непринятых (W1 25,5 ниже A3–A6). Значит, «0 близких вершин» — не
свойство принятого Ground в Max; Qv из #32 остаётся сигналом только на чтении Blender и на массивах SIL13.
(3) D152 требует xView 0/0 у каждой сдачи, но собственные сданные NTR Ground после FBX → poly дают OV до 580 и
OF до 852 — вопрос к Артёму, в каком состоянии он мерит xView (его .max, а не FBX → poly?). Внедрения нет, Ground не
строили и не правили, порог не предлагается.

## Frozen contract (before any measurement)

Continue #32 (`research/autoresearch-standing-32@ebb32458a5673e2b142d7fc5b273733621201d71`, candidate
`Qv = 10000 * V / T`, V = unique vertex indices in repo xView 2 mm pairs on the Blender readback of the
`*_Ground` part). #32 measured V only on Blender readbacks; Artem checks xView in 3ds Max on Editable_Poly.
#370 (`docs/research/xview-parity-ground-v014.md`) showed the node state matters: Vatutino Ground v014 NPM has
0 Overlapping Vertices as imported (Editable_mesh) and 118 after `convertToPoly`.

**Hypothesis H33 (this corpus only):** the #32 counter agrees with native Max on the presence of near vertices:
for every input, `(V_repo > 0) == (V_max > 0)`, where `V_max` is the 3ds Max 2026 xView "Overlapping Vertices"
count at 2 mm on the selected Ground node in the runner's `plain` mode (Editable_Poly, Artem's working state).

- **Fixture (frozen):** A1–A8 = the #31 accepted FBX inputs, `C:/x/ev_t_193a0887/inputs/`, hashes as in
  `research/autoresearch-standing-31@8ee341f7:docs/research/autoresearch-ground-quality-harness/inputs.sha256`
  (Vatutino v015 + seven delivered NTR NPM). W1 = natural positive witness outside SIL13: Vatutino Ground v014 NPM
  `C:/x/t_d94665f2/ground_v014/npm/SM_Vatutino_Ground.fbx`, SHA-256
  `94357c5f048ba3343035dfa44c9d0d89d83b3d6697dcfd9cc81c54739a6dc2ef`. W1 is **rule-failed** (D152 xView-clean, Max
  118 OV in poly, #370) and superseded by v015 (D157); it is not an explicit Artem rejection of the file.
  SIL13 r1–r5 have no FBX (stopped before export) and the #1738 core outputs are OBJ only: the runner accepts
  `.fbx`/`.max`, so both are **not measured natively** here (no conversion stage is added).
- **Node:** the single `*_Ground` node named as in the #31 dumps (A) and `SM_Vatutino_Ground` (W1); no MAF/UCX/Flora.
- **Native command:** copies under `C:/x/ev_t_304e8c0c/max/run<k>/`, `tools/qa/xview_parity.py prepare_run` writes
  `jobs.txt` with a nonce, `python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --version 2026 --file
  tools/qa/xview_dump.ms` with `XVIEW_OUT=<run dir>`, accepted only when `xview_parity.py --check-run` passes.
  Three independent Max processes (run1–run3) in `plain`; run1 also `weldpoly` (perturbation).
- **Repo side:** A rows reuse the #32 receipt (V=0 on all eight, recomputed by #32's `measure`). W1 is dumped once with
  the #31 pipeline (`fbx_to_blend.py` at `8ee341f7` + `tools/blender/xview_dump.py` + `xview_gate.to_metres`) into
  `C:/x/ev_t_304e8c0c/dumps/W1_Vatutino_v014_NPM.npz`, then #32's `measure` three times.
- **Replay:** `../../.venv/Scripts/python.exe docs/research/autoresearch-ground-native-xview-r33.py <new.json>`
  from the worktree root (needs 3ds Max 2026 + Blender 5.1 on this workstation: replay limited to this PC).
- **Confirmed:** all three plain runs complete with zero spread on V_max, F_max, vertex and face counts per node,
  and the presence rule holds on all 9 inputs. **Refuted:** a completed series where any input breaks the rule
  (this includes W1 with V_repo = 0 while V_max > 0, i.e. the Blender-readback counter is blind to that defect class).
  **Inconclusive:** a series that could not be completed in budget or a failed check_run.
- **Expected directions (prior, not the verdict):** A1–A8 V_max = 0 (accepted); W1 V_max = 118 in plain (as #370).
  Perturbation `weldpoly` (weld 2 mm on the mesh, then poly): A stay 0; W1 stays > 0 (re-split of non-manifold
  vertices). Positive trigger witness: W1. Accepted control on which the rule fires: none known (#32 found V = 0 on
  all A); if any A has V_max > 0 it becomes the collateral control and is reported, never dropped.
- **Budget:** first pair = one Max call with A1 + W1 (plain); its wall time t1 projects a full 9-input call
  (`t_full ≈ t1 · (sum of faces)/(A1+W1 faces)`). Cap for the whole native series 45 min wall; if
  `3 · t_full + t_weldpoly > 45 min`, stop **inconclusive** and publish the next command. New-candidate budget: zero
  (no counter change is proposed in this card).
- **Recorded separately:** clean (plain, three runs), perturbed (weldpoly, run1), not measured (SIL13 r1–r5 native,
  #1738 OBJ native, VPM, faces/skirt/budget quality, visual deviation).
- **Forbidden:** fixture replacement, tolerance or validator changes, test deselection, edits to any delivered
  package or input, builds/repairs of Ground (#1738 owns them), saving any Max scene, touching other cards' files,
  using any result as a release gate. Owners: #1315/#1622 cold run, #1738 Ground core, #1742/#1770 body (closed).

**Amendment 1 (after the first-pair call failed, before any native count was obtained):** on 3ds Max 2026.3 the
runner stops with `XVIEW_ERROR -- .NET runtime exception: Operation is not supported on this platform.`
(`tools/qa/xview_dump.ms:83` compiles a helper with `Microsoft.CSharp.CSharpCodeProvider`, unsupported on .NET 8);
receipt `C:/x/ev_t_304e8c0c/r33.json` (`inconclusive`, first pair failed). The series runs on **3ds Max 2024**, the
route with retained native evidence (`docs/pipeline-tools.md`, #528). Everything else in the contract is unchanged.
Fixing the runner for 2026 is outside this card (side finding).

**Amendment 2 (after the 2024 first pair succeeded and run1 crashed at start-up, minidump 12:13, no listener output):**
receipt `C:/x/ev_t_304e8c0c/r33b.json` (`inconclusive`). Each Max call now waits until no `3dsmax.exe` is running,
plus 20 s; the whole series (first pair included) is re-run under the prefix `m2024b-`. Counts from `r33b` are
reported only as a cross-check, not as series runs. The first `m2024b-` attempt died in the harness itself
(`tasklist` text decoding returned `None` under the Russian code page) after its pair; `m2024c-` waited on the user's interactive Max 2026 sessions (stopped by a pre-created run dir).
The settle now counts only Max 2024 processes; the series runs as `m2024d-`.

## Round log

Receipt [`autoresearch-ground-native-xview-r33.json`](autoresearch-ground-native-xview-r33.json) = `C:/x/ev_t_304e8c0c/r33e.json`,
SHA-256 `56b5bbc147d60160df7d307bfe2f02658c4f9d38e34024f4edc92069e60d8a74`, harness at `3501d651`. Evidence (all Max
dumps, W1 Blender dump, failed attempts r33/r33b/r33d): `C:/x/ev_t_304e8c0c/` and the Drive copy
`G:/Мой диск/AGR-evidence/t_304e8c0c-ground-native-xview/`, manifest `SHA256SUMS.txt` (91 files) SHA-256
`99f635124b9db3f7328df4d676675391b2f834b0f3615b1f384bca2cad938ae6`, Drive copy verified with `sha256sum -c`.
Replay limited to this PC (3ds Max 2024 + Blender 5.1).

- **Budget:** first pair 214 s → projected series 2 156 s ≤ 2 700 s cap; actual Max calls pair 214 s, run1 464 s,
  run1wp 617 s, run2 444 s, run3 563 s, all `check_run` OK, every input hash unchanged before/after.
- **Clean (plain, run1–run3 + pair):** V_max zero spread on all 9 inputs; vertex/face/tri counts identical.
  F_max (Overlapping Faces, not part of H33) jitters by 1–2 faces on A5 (261/263), A6 (851/852), A8 (2/4); the
  harness stability gate included F_max, so the receipt's label is `inconclusive`. The refute clause of the contract
  (completed series, rule broken) is met on the hypothesis' own quantity: presence mismatch on A3, A4, A5, A6, W1,
  stable in all four plain calls. Verdict published: **refuted**; this does not depend on F_max.
- **Repo side:** A rows recomputed from the frozen #31 dumps, exact V/T parity with the #32 receipt on all eight
  (all V = 0). W1 dumped once through the #31 pipeline: V = 0, T = 46 343 (the same triangle count as Max), Qv 0,
  spread 0. Blender reads the same coordinates without the poly re-split, so the counter cannot see it.
- **Perturbed (weldpoly, run1wp):** weld 2 mm then poly. A1 v015 rises 0 → 118 OV (welding creates non-manifold
  vertices that poly re-splits), A2/A7/A8 stay 0, A3–A6 unchanged (310/307/278/580), W1 stays 118.
  Expected direction held for W1; for A1 it did not (the prior said accepted stay 0).
- **Positive witness:** W1 fires natively (118/351, identical to #370 on Max 2026). Accepted controls on which the
  native rule fires: A3, A4, A5, A6 (collateral impact = 4 of 7 delivered NTR Ground).
- **Not measured:** SIL13 r1–r5 natively (no FBX), #1738 OBJ natively (runner reads `.fbx`/`.max` only), Artem's
  own `.max` scenes of the NTR deliveries, VPM, faces/skirt/budget/visual quality.
- **Side findings (not fixed here):** `tools/qa/xview_dump.ms` fails on 3ds Max 2026.3 (`CSharpCodeProvider`,
  .NET 8) — the 2026 route is broken; a back-to-back Max 2024 batch start crashed once (minidump, 12:13).
