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

(filled after the series)
