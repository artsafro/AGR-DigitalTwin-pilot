# Autoresearch #95 — trainer: body FBX first on KPP1 / G22 (OBSERVE)

**Кратко (RU).** В ledger тренажёра чаще всего проваливается шаг `artifact` (3/4: KPP1, G22, 63A). После [D391]
(самоподтверждение Gate 1 в тренажёре) и #1880 (DWG) заново прогоняли только 63A/63B, а KPP1 и G22 — нет. Проверка
инструментов: общий DWG-маршрут (контур L03 → `plan_adapter_dwg.py` → `agr body`) за ~10 с даёт KPP1 валидный FBX,
и следующий проваленный шаг — `bounds` (высота 3,9 вместо 8,65 м, плюс элемент на 4 м к востоку). Значит, FBX
не появляется из-за поведения агента, а не из-за нехватки инструментов. Гипотеза H95: одна фраза в задании практики
(«сначала тело-FBX из доступных источников, вопросы по поздним этапам — в QUESTIONS.md») поднимет долю прогонов с
FBX. Серия парная: B = задание как на main, C = задание + фраза (копия банка во временной папке, git-банк не
меняется). Настройка — KPP1, контрольный объект, не использованный для настройки, — G22. Результат — в разделе «Result».

Status: **contract frozen before any r95 practice run.** Hypothesis result: see "Result".

## Target and owners

- Focus override (#1855): ledger `docs/trainer/ledger.json` @ `afc930ea` = 4 rows; `artifact` 3/4, `sources-dwg` 1/4
  (#1874/#1880 merged). Most frequent step = `artifact`.
- Not owned elsewhere: #87/#88–#92 own the 63A/63B Revit route (tower map, window keys, jamb alignment), #93/#94 the
  escape audit (reused here read-only), #1861 the bank, #1877 the Blender guard. KPP1/G22 have no post-D391 run
  (backlog #87 line: "If #1880 merges: re-run KPP1 cold once").
- Texture/atlas fallback: inactive (ledger rows exist). Form topic: closed.

## Tool witness (measured 2026-11-25, before the contract; not a practice run)

Inputs: `C:/x/trainer/runs/kpp1-v004-codex-20261124/built/plan-contours.json` (L03 contour made by that cold run,
SHA-256 `635fd799…7d6`). Commands, all shared tools on `afc930ea`:

```
uv run python tools/methods/body/plan_adapter_dwg.py kpp1_contours_l03.json cfg_min.json plan_min   # {"materials":{"WALL_A":[0.8,0.8,0.8]},"zone":"WALL_A"}
uv run agr body --blender "C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" plan_min/plan_band0.json body_min
uv run agr trainer score kpp1-v004 --built body_min --out score_min.json
```

Result: artifact pass (body.fbx `18a1206e…d86d`, 266 quads), readback pass, topology pass, **bounds fail 4.75 m**
(built box z 0..3.9, x −14.985..12.611; key z 0..8.65, x −15.185..16.676), form fail p95 4.76 m, package fail (no ZIP).
Score report SHA-256 `ad78c80d…696f`. Scratch: `C:/x/ev_t_04777f53/` (replay limited; numbers are in this file).

## Contract (frozen before any measurement)

- **Metric M95** = per arm and fixture, the share of practice runs whose `agr trainer score` has `artifact = pass`
  (a binary Kaydara FBX in `built/` that is not the key). Secondary: `first_failing_step`, wall s, input tokens,
  E93 escape count.
- **Arms.** B = `uv run agr trainer run <id> --out <dir>` (bank `docs/trainer/etalons.json`, SHA-256
  `016aab0c…6635`). C = the same with `agr trainer --bank C:/x/ev_t_04777f53/bank_r95_C.json` made by
  `make_bank.py` (SHA-256 `51c6e51e…ed3a`); the only change is the `CANDIDATE` sentence appended to the two tasks.
- **Fixtures.** Tuning = `kpp1-v004` (ledger rows 1 and 4). Held-out = `g22-k2-stage1` (NPZ crop route, never used
  to word the sentence). Practice tree = `origin/main` `afc930ea0d668f83616ead331a671b023d197546` for every run.
- **Series.** 3 B + 3 C per fixture, 12 runs, `--timeout-s 1800`, at most 2 runs at a time (never two KPP1 runs at
  once: one accoreconsole at a time). Order: pair i = (KPP1 B_i ‖ G22 C_i), then (KPP1 C_i ‖ G22 B_i).
- **Positive trigger witness:** a B run that ends without FBX while asking for a later-stage source (finish, GeoJSON,
  levels) in QUESTIONS.md or last.txt. If no B run shows it, the candidate is `not_exercised` for that fixture.
- **Counting.** A run with an E93 escape (`docs/research/trainer-escape-r93/audit.py` @
  `origin/research/autoresearch-standing-93`) counts as artifact **fail** in C and is reported separately in B.
  A run that reads the key counts as fail. Runs are never re-run or dropped; a crash/timeout is a fail with its reason.
- **Keep threshold (hypothesis CONFIRMED):** C artifact ≥ 2/3 on BOTH fixtures AND C − B ≥ 2 runs on at least one
  fixture AND C not worse than B on the other; escapes in C ≤ escapes in B.
  **REFUTED:** C ≤ B on both fixtures, or B already ≥ 2/3 on both (sentence not needed; record the new first stop).
  Anything else = **inconclusive**.
- **Expected direction / bounds:** artifact share C ≥ B; first_failing_step moves from `artifact` to `bounds` (KPP1)
  or `bounds`/`topology`/`form` (G22); wall per run ≤ 1800 s.
- **Stop rule:** 12 runs or 3 h wall from the first launch; a budget stop = inconclusive for this run, published with
  the exact next command. Confirm-vs-new-candidate budget: 0 new candidates (one variant only).
- **Forbidden:** editing the git bank, the key, delivered packages, production skills/gates or other cards' files;
  re-wording the sentence after the first run; counting escaped or key-reading runs as passes; deselecting runs.
- **OBSERVE:** the result is recorded; any adoption of the sentence into `tools/trainer/trainer.py` `task_text` goes
  through a normal PR by the #1855 owner.

Replay: `uv run --frozen python docs/research/trainer-artifact-first-r95/make_bank.py docs/trainer/etalons.json NEW.json`
(must print `51c6e51e…ed3a`), then the run/score commands in `receipt.json` (written after the series).

## Result

(filled after the series)
