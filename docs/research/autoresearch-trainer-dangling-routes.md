# Autoresearch #119 — dangling route references in trainer practice trees (OBSERVE)

Card t_f454aa44 (standing #119, focus override #1855: most frequent first failing step). Research only: no
product, bank, task-text, scorer or delivered-package change.

## Краткое содержание (RU)

**Гипотеза H119: подтверждена (статически). Готовность к ревью: отдельно, OBSERVE, без изменений продукта.**

- Практические деревья тренера (git archive + неизменённый `scrub_worktree`) на head `8a2fa635` содержат
  маршрутные документы, которые называют файлы, удалённые скрабом. M119 (медиана 3 повторов, разброс 0):
  G22 **5** (из них инструментов 2), 63A **15** (14), KPP1 **15** (11).
- Свидетель: `floor_from_dump.py` на G22 найден 3/3. Класс не только G22: на 63A и KPP1 (не использованы для
  поиска свидетеля) 14 и 11 скрытых инструментов. 16 возмущений из 16 сдвинули счёт как ожидалось, 2 не
  применимы (`not_exercised`). Маршрутные файлы скраб не удаляет (0 на всех).
- Кто ссылается: `docs/agents/skeleton-harvest/2026-11-23.md` (18), `docs/agents/SKELETONS-stages.md` (8, в т.ч.
  `floor_from_dump.py`, `build_quad_master.py` и банк `docs/trainer/ETALONS.md` на всех трёх эталонах),
  `routes/revit-intake.md` (4: `jobs/KPP1/scripts/{dump_source,extract_openings,inspect_source,match_ids}.py` —
  маршрут Revit-приёма в практике KPP1 указывает на скрытые скрипты), `docs/agents/CAPABILITIES.md` (3).
- Сохранённые прогоны (59 измерено, 9 `not_measured`: их head нет в репозитории): 25 из 37 прогонов G22/63A/63B
  называли в командах `floor_from_dump.py` — инструмент, которого нет в их дереве. Но влияние на побег и
  артефакт **не показано**: побег 7/25 против 3/12 у не искавших, чистых FBX 0 в обеих группах. Связь слабая и
  смешана с эталоном (все 9 чистых FBX — KPP1, где ни один прогон не искал скрытые инструменты).
- Что бы изменили (не применено): владелец тренера добавляет предполётную проверку практического дерева,
  перечисляющую висячие маршрутные ссылки, а банк/владельцы маршрутов решают: продвинуть инструмент из `jobs/`
  в `tools/` (как #1928 для `floor_from_dump`) или не называть его в маршруте. Живая проверка эффекта на
  артефакт — следующий шаг, не этот.

## Why this target

- Ledger `docs/trainer/ledger.json` @8a2fa635: first failing step `artifact` 3/4, `sources-dwg` 1/4.
  Stored scored runs (`C:/x/trainer/runs/*/score.json`, 35): `artifact` 20 (all "no FBX in the built result"),
  `form_v2` 7, `bounds` 7, `vlm` 1 (`not_run`).
- Owned artifact levers, not repeated here: #1917 (FBX-first sentence), #1928 (G22 Revit NPZ adapter,
  promotes `floor_from_dump`), #98/#99/#118 explicit FBX/ZIP selection, #113/#114/#116 lineage tokens,
  #112 untuned-etalon admission and host isolation (owner decision), #1955 form key, #1866 DWG.
- Observation that opened this target: `g22-k2-stage1-codex-r111-1` escaped (E93) at command 21:
  `Get-ChildItem C:/Users/artsafro/agr-pilot/AGR-DigitalTwin -Filter floor_from_dump.py -Recurse`.
  The practice tree's route doc `docs/agents/SKELETONS-stages.md` names `floor_from_dump`, but the only file
  (`jobs/garibaldi22/body-training-1619/hooks/floor_from_dump.py`) is removed by the scrub
  (`hidden_repo_paths`). A route that names a tool the practice tree does not contain makes the practice
  unpassable by the route and invites a search outside the tree. #1928 fixes one instance; nothing counts
  the class.

## Metric (frozen)

**M119(tree)** = number of distinct repo files `f` such that
1. `f` is named in a *route-critical* text file of the practice tree, and
2. `f` exists in the tree of the head the practice tree was archived from (`git ls-tree -r <head>`), and
3. `f` is absent from the practice tree.

Route-critical files: `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` and `*.md` / `*.json` under `docs/agents/`,
`routes/`, `docs/procedure/`, `docs/domain/`, `docs/scenarios/`, `.agents/skills/`.

A name is matched by `[A-Za-z0-9_.\\/-]+\.(py|ps1|ms|json|md|npz|yaml|yml|toml)` (backslashes normalised to `/`,
leading `./` stripped, case kept). A name with `/` is a repo path (also tried as a suffix of head paths when it
is not a full head path: it counts when every head file ending in `/<name>` is absent). A bare name counts only
for tool extensions `.py`, `.ps1`, `.ms`, when every head file with that basename is absent from the tree.
Names that exist nowhere in head are `stale` (reported, not counted). `M119_tools` = the `.py/.ps1/.ms` subset.

Secondary (association on stored runs, not a KEEP criterion): for each stored run with `events.jsonl` and `wt/`,
compute M119 on its own `wt/` against its own `origin_main`; `hit` = a shell command (E93 `commands()`) names a
dangling basename of that run; `escape` = E93 verdict (`audit.py` sha256
`e78e4927947eab306b6fc004c98a0f1f9140ef752eab35eb5bdd93feb5f96ec3` from
`origin/research/autoresearch-standing-93`); `fbx` = `built/` contains an `.fbx`.

## Hypothesis H119 (frozen)

At head 8a2fa635 the practice trees of the ready etalons contain dangling route references; the witness
(`floor_from_dump.py` on `g22-k2-stage1`) is among them, and the class is not G22-only.

- **confirmed** if (a) the witness is counted on G22 in 3/3 reps, and (b) M119_tools >= 1 on at least one
  etalon not used to find the witness (`63a-stage1` or `kpp1-v004`), and (c) all perturbations move as expected.
- **refuted** if (a) holds and M119_tools = 0 on both held-out etalons (the class is the single #1928 instance).
- **inconclusive** otherwise (witness not counted, a perturbation off, a budget stop).
- Association: report `escape-or-noFBX` rate for `hit` vs `not hit` runs; expected direction hit >= not hit.
  Reported only; with few hit runs it is labelled weak.

## Fixtures, reps, perturbations (frozen)

- Head `8a2fa635` (origin/main at card start); bank `docs/trainer/etalons.json` at that head (sha256 recorded).
- Ready etalons: `kpp1-v004`, `g22-k2-stage1`, `63a-stage1` (63B/63C not practice-ready: not built).
- Tree = `git archive <head>` + unchanged `tools.trainer.trainer.scrub_worktree(dst, e)` in a NEW scratch dir
  (no git init / commit: not needed for counting). 3 reps per etalon; median and spread [min, max].
- Perturbations on a copy of the rep-1 tree (expected delta of M119, per variant):
  - P1 route doc names a hidden head file of that etalon (full path): +1
  - P2 route doc names an existing tree file: 0
  - P3 route doc names a path that is nowhere in head: 0 (stale +1)
  - P4 P1 path written with backslashes: +1
  - P5 the P1 line in a non-route file (`docs/research/`): 0
  - P6 bare basename of a hidden-only head tool (G22: first sorted `.py` basename whose every head file is
    under `jobs/garibaldi22/`, absent and not already counted): +1
  - P1/P4/P5 use the first sorted hidden `.md` head file under the etalon's `hidden_repo_paths` that is not
    already counted. Amended before the first measurement (harness review), not after a number.
- Accepted/rejected fixtures: none exist for this static check; the "rejected" side is the stored runs that
  escaped or ended without FBX. Untouched etalon/perturbation inputs are labelled `not_exercised`.

## Budget and stop rule (frozen)

Static only, no agent runs, no DCC. One measured pair (G22 rep 1) fixes the per-tree time; stop at 45 min wall
or after 3 reps x 3 etalons + perturbations + stored runs, whichever first. A budget stop is `inconclusive`.
Confirm-vs-new-candidate budget: one candidate (the metric above), no alternative regex after the first number.

## Forbidden shortcuts

Changing the regex, scope list or counting after the first measured number; editing the bank, trainer,
task text, scrub, tests or any delivered package; deselecting tests; touching other cards' files; counting
`stale` names; reading keys.

## Would-change (OBSERVE)

If confirmed: trainer owner adds a practice-tree preflight that lists dangling route references (or the bank
keeps those tools / hides the docs). Not applied here.

## Replay

```bash
git show origin/research/autoresearch-standing-93:docs/research/trainer-escape-r93/audit.py > .r119/AUDIT.py
uv run --frozen python docs/research/trainer_dangling_r119/measure.py --audit .r119/AUDIT.py \
  --out C:/x/ev_t_f454aa44/r119-NEW
```

## Round log

Contract frozen in 7d4560a4 (before any number); harness f89f4858, perturbation selection amended before the
first measurement (P6 / P1 pick the first hidden file not already counted); full head sha pinned a1bbf310.
One run, `C:/x/ev_t_f454aa44/r119-1` (host-local, trees 264 MB not kept in git), copied receipt below.

| Etalon | reps | M119 median [min,max] | M119_tools median [min,max] | tree build s | stale names |
| --- | --- | --- | --- | --- | --- |
| g22-k2-stage1 | 3 | 5 [5,5] | 2 [2,2] | 9.0-9.8 | 373 |
| 63a-stage1 | 3 | 15 [15,15] | 14 [14,14] | 8.8-8.9 | 373 |
| kpp1-v004 | 3 | 15 [15,15] | 11 [11,11] | 9.2-9.4 | 373 |

Perturbations (rep-1 tree, expected / observed delta): G22 P1 +1/+1, P4 +1/+1, P5 0/0, P2 0/0, P3 0/0,
P6 (`envelope_check.py`) +1/+1; 63A and KPP1 P1/P4/P5/P2/P3 all as expected, P6 `not_exercised`.
Route-critical files removed by the scrub: 0 on every tree (clean check). Wall 221.1 s, run_status `finished`.

Stored runs (own `wt/` vs own `origin_main`): 59 measured, 9 `not_measured` (g22 r115 C1-C3/D1-D3, r97 C1-C3:
head not in this repo). Hit = a command names a dangling tool basename.

| Group | n | escape (E93) | FBX | FBX and no escape |
| --- | --- | --- | --- | --- |
| hit (all `floor_from_dump.py`) | 25 | 7 | 5 | 0 |
| not hit, non-KPP1 | 12 | 3 | 1 | 0 |
| not hit, KPP1 | 22 | 0 | 9 | 9 |

## Result

**H119 confirmed** (criteria a/b/c all true in the receipt). Dangling route references are a deterministic,
measured property of every ready practice tree; the class is not the single #1928 instance.
**Not measured:** any effect on `artifact` passage or escape rate — the stored association is weak and
confounded by etalon (non-KPP1 escape 7/25 hit vs 3/12 not hit; 0 clean FBX in both). No live runs, no KEEP,
no product change.

Receipt: `docs/research/trainer_dangling_r119/receipt.json` (raw bytes sha256
`ca56fe35f7fff3062b027db7150f4379b004c873073a8098ed696c793b93520c`), inputs: head 8a2fa635, bank
`016aab0c…6635`, trainer.py `16fd8edb…4b5`, measure.py `439c3a42…735`, E93 audit `e78e4927…ec3`.
Replay of the current-head series is fully Git-bound; the stored-run table is replay limited
(`C:/x/trainer/runs` lives on this host only).

Next targets:
1. Trainer owner: a practice preflight that lists dangling route references per etalon (would-change of #119),
   and a decision per reference: promote the tool to `tools/` or hide/neutralise the route line in practice.
2. Live A/B on G22 after #1928 lands: count runs that search for `floor_from_dump.py` outside the tree and
   escape-free FBX passes (baseline from this table: 14/21 measured stored G22 runs named it).
3. KPP1 Revit intake: `routes/revit-intake.md` points at 4 hidden `jobs/KPP1/scripts/*`; check whether the
   KPP1 practice task is meant to use the Revit trail at all (bank owner), before any KPP1 intake research.
