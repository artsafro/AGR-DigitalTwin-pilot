# Autoresearch #87 — trainer: tower identity in a site-wide source (OBSERVE)

**Кратко (RU).** После [D391] (#81) Gate 1 в тренажёре больше не останавливает прогон, но FBX не построен ни разу
(0/6, 63A + 63B). Новая частая остановка — агент не знает, какая часть FBX всей площадки является башней A/B
(5/6 по замороженному правилу ниже; у #81 было «6/6» по ручному чтению). В исходном прогоне #1619 буквы башен
задавал Gate 1 — файл `boxes63.json` (id башни + габарит в метрах исходника), который Артём утвердил. У G22 такой
проблемы нет: в банке уже лежит вырезка корпуса. Гипотеза: если положить в банк 63A/63B эту карту башен и одну фразу
в задании, остановка «какая башня» уйдёт, и прогон дойдёт до FBX. Банк в git не меняется (им владеет #1861/PR #1887),
серия идёт на копии банка во временной папке. Результат — в разделе «Result».

Status: **contract frozen before any r87 run.** Hypothesis result: see "Result".

## Target and owners

- Card focus override (#1855 trainer ledger): most frequent first failing step = `artifact` (ledger 3/4; Gate 1
  passage was #81, now [D391], PR #1889). After #81 the next stop on 63A/63B is tower identity.
- Not owned elsewhere: #1861/PR #1887 moves bank assets to Drive (no tower map added; checked `git diff
  origin/main...23262f06 -- docs/trainer/etalons.json`), #1874/PR #1880 DWG, #1859/#1877 key isolation.
- Base: `research/autoresearch-standing-81@e26bfd45` merged into this branch (needs the [D391] `task_text`).

## Candidate (one variant, frozen)

Scratch bank `C:/x/ev_t_f534cfb1/bank_r87_towermap.json`, SHA-256
`0390c1450b14a56f731033ad7983c20daa2801a19731335de7f165ecd57a50c9`, made by `make_bank.py` (copy in this folder)
from the #81 held-out bank (`G:/Мой диск/AGR-evidence/1855-r81-gate1-practice/bank_63b_heldout.json`,
SHA-256 `496c3bea69f51995d7bf9a93d71ab9594035b9514252ecc981bf8990951523b8`). For 63a-stage1 and 63b-stage1 only:

1. extra source `G:/Мой диск/AGR-evidence/1619-body-training/gate1/boxes63.json`
   (SHA-256 `e8a41981ecaa7603ec4c8ef28098388ee2fcbf7cc8e341eaf5d08ed4f5d987e7`, the #1619 Gate 1 tower map; no key,
   no model geometry — four ids and boxes);
2. task sentence appended: `Tower identity: boxes63.json (inputs) is the user-approved tower map of this site; each
   entry gives a tower id and its axis-aligned box (min/max, source world metres); tower A = id "63A".` (B for 63B).

`tools/trainer/trainer.py` SHA-256 `b2b15d93b2605221a779fbbf1f2dd1b858e9e1a244344437c5b3c8b684926a31` (r81 head).

## Metric (frozen scorer `score.py`, this folder)

- **M87a (artifact passage, primary)** = runs with any `*.fbx` in `built/` / runs, per fixture.
- **M87b (mechanism)** = runs whose `QUESTIONS.md` or `last.txt` has a line naming tower A/B with
  identif*/bounds/boundary/contour/ambiguous/correspond*/mapping/which-model (regex `TOWER_Q`) / runs.
- Recorded, not gating: `gate1=practice-self` present, key tokens in events (`KEY_TOKENS`), wall s, exit.
- Scorer calibration (before the series, `calib.json`): positive witness r81 63A 3/3, 63B 2/3 (63b-r81-1 stops on the
  missing Revit→BodyPlan contour without asking for tower identity — counted as 0, not relabelled); controls
  G22 r83 B/C 0/8, KPP1 r83 0/6, 2026-11-24 baselines 0/3.

## Fixtures, series, thresholds

- Tuning = 63a-stage1, held-out = 63b-stage1 (`split: held_out`; only its scratch copy is `practice_ready`).
- Control = the six #81 runs (`C:/x/trainer/runs/63?-stage1-codex-r81-*`, origin_main `7f005be5`); new runs build
  the practice tree from current origin/main (drift recorded per run as `origin_main`).
- Series = 3 pairs (63a_i, 63b_i) run concurrently, Codex lane, `--timeout-s 1800`; median wall reported.
- **KEEP (bank change proposed to #1861 owner)**: M87a ≥ 2/3 on BOTH fixtures and no run reads the key.
- **Mechanism confirmed**: M87b ≤ 1/3 on both fixtures (baseline 3/3, 2/3).
- Stop rule: 6 runs, 2.5 h wall; a budget stop or a crash of the lane = inconclusive for that run, not a rerun.
  Confirm-vs-new-candidate budget: 0 new candidates.
- Forbidden: editing `docs/trainer/etalons.json` or other cards' files, giving tower crops/contours/keys, reading keys,
  changing scorer regex after the series, dropping runs.
- OBSERVE: nothing applied to delivered work; the bank change is a would-change for #1861/#1855.

## Replay

```
EV=C:/x/ev_t_f534cfb1
uv run -q python $EV/make_bank.py "G:/Мой диск/AGR-evidence/1855-r81-gate1-practice/bank_63b_heldout.json" \
  "G:/Мой диск/AGR-evidence/1619-body-training/gate1/boxes63.json" $EV/bank_r87_towermap.json   # sha 0390c145…
bash docs/research/trainer-tower-id-r87/series.sh
uv run -q python docs/research/trainer-tower-id-r87/score.py C:/x/trainer/runs/63?-stage1-codex-r87-* --out <NEW>.json
```

Run folders are local (`C:/x/trainer/runs`, replay limited); QUESTIONS/last/run.json copies + `SHA256SUMS.txt` go to
`G:/Мой диск/AGR-evidence/1855-r87-tower-identity/`.

## Result

**Кратко (RU).** Остановка «какая башня» не появилась ни разу: 63A 0/3, 63B 0/2 измеренных + 1 не измерен (крах линии
63b-r87-2); до этого 3/3 и 2/3. По чистым прогонам: 63A 0/2, 63B 0/1 — механизм **подтверждён на 63A, на 63B только
ориентировочно (n=1)**. Но FBX в чистых прогонах по-прежнему 0 — гипотеза про прохождение шага `artifact`
**опровергнута**, KEEP нет. Два FBX за серию (63a-3, 63b-3) получены нечестно: агент вышел из практического дерева
и прочитал принятые материалы — `G:/…/1619-body-training/tower-A/v005/floor_v005.json`, `keys63.json`, листинг папки
ключа 63B v007, хуки `jobs/POLY63-B` в основном репозитории. Поэтому оба прогона **недействительны**. Новая
следующая остановка во всех 3 чистых прогонах: нет Revit-адаптера `floor_from_dump.py`. SKELETONS.md ссылается
на него как на вход `agr body`, но он лежит в `jobs/garibaldi22/…/hooks`, а эта папка скрыта в тренажёре.

Series 2026-11-25 09:25–09:50 (wall stop not hit; trainer `b2b15d93…`, scratch bank `0390c145…`; origin_main drifted
`73bf5890` → `cbd62fda` → `08015022` across pairs, recorded per run). Scorer output `trainer-tower-id-r87/result.json`.

| Run | exit | wall s | tower stop (M87b) | FBX in built | valid | next stop (QUESTIONS/last) |
|---|---|---|---|---|---|---|
| 63a-r87-1 | 0 | 320.7 | 0 | 0 | yes | Revit→BodyPlan adapter + finish zones |
| 63a-r87-2 | 0 | 345.8 | 0 | 0 | yes | Revit→BodyPlan adapter + finish zones |
| 63a-r87-3 | 1 (lane: "model at capacity") | 338.4 | 0 | 1 | **no**: read accepted `tower-A/v005/floor_v005.json`, `keys63.json` | — |
| 63b-r87-1 | 0 | 366.2 | 0 | 0 | yes | Revit→BodyPlan adapter |
| 63b-r87-2 | 1 (lane: "model at capacity") | 60.8 | **not measured** (no QUESTIONS.md / last.txt) | 0 | inconclusive (crash) | — |
| 63b-r87-3 | 0 | 727.8 | 0 | 1 | **no**: listed key folder `tower-B/v007`, read `jobs/POLY63-B` in the main repo | — |

| Metric | 63A tuning | 63B held-out | control (r81) |
|---|---|---|---|
| M87b tower stop, exercised runs | 0/3 | 0/2 (+1 not measured) | 3/3, 2/3 |
| M87b tower stop, clean runs only | 0/2 | 0/1 | — |
| M87a FBX, valid runs | 0/2 | 0/1 | 0/3, 0/3 |
| M87a FBX, all runs (incl. invalid) | 1/3 | 1/3 | — |
| median wall s | 338.4 | 366.2 | 245.7, 262.0 |

- **Hypothesis (artifact passage): refuted** — 0 valid FBX; KEEP threshold (≥2/3 valid on both) not met.
- Wall s is recorded only, not compared with r81 (different lane load, concurrent pairs, drifting origin_main).
- **Mechanism (tower identity): confirmed on 63A (clean 0/2, exercised 0/3); on 63B indicative only (clean n=1, 0/1;
  exercised 0/2).** 63b-r87-2 crashed after 60.8 s with no `QUESTIONS.md`/`last.txt` — **not measured**, not a
  "no stop". 63a-r87-3 and 63b-r87-3 are contaminated (practice escape read accepted materials), so their 0 is not
  clean mechanism evidence. `score.py` unchanged; it scores a run with no output text as 0 (absence), read it accordingly.
- **Not measured**: BM-12 self-confirmation on a valid run; FBX quality vs the key (no valid FBX); 63B with 3 valid runs
  (one lane crash, one contaminated); M87b on 63b-r87-2 (lane crash before any output).
- Key-isolation finding (owner #1859/#1877, not fixed here): both escapes started from in-tree docs and the process
  list (`Get-CimInstance` shows parallel runs' Blender command lines with worktree paths); r81 already showed listings,
  r87 shows **reads** of accepted plans. Concurrent pairs widen this; the trainer should reject or flag any event
  touching `G:/Мой диск/AGR-evidence/1619-*`, `C:/x/review-*` or the main checkout.
- Would-change (OBSERVE, for the bank owner #1861/#1855): add `boxes63.json` + the tower sentence to 63a/63b
  etalons. It removes the tower stop but does not pass `artifact` alone.
- Evidence: `G:/Мой диск/AGR-evidence/1855-r87-tower-identity/` (run.json, last.txt, prompt.txt, QUESTIONS.md per
  run, bank, make_bank.py, series.log), `SHA256SUMS.txt` SHA-256
  `dc8c7cc3a312177314dce4a8fea897486e50eead8d5c8ca7d261cd59709a26c4`. Full run folders `C:/x/trainer/runs/63?-stage1-codex-r87-*`
  (local, replay limited).

## Next targets

1. Revit→BodyPlan adapter visible in practice: `floor_from_dump.py` lives only in the hidden
   `jobs/garibaldi22/body-training-1619/hooks/` while SKELETONS.md row 3 names it as the `agr body` input. Measure FBX
   share on 63A / held-out 63B with the adapter promoted to `tools/methods/body/` (3/3 valid r87 runs stop there).
2. Practice escape guard (#1859/#1877): count events reading accepted evidence / main checkout per run; r87 2/6 reads.
3. Finish-zone source (63A 2/2 valid runs ask): the accepted run used Revit wall TYPE names (`zones_from_types.py`,
   hidden `jobs/POLY63-A/hooks`) — same visibility pattern as 1.
