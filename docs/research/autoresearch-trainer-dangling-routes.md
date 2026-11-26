# Autoresearch #119 — dangling route references in trainer practice trees (OBSERVE)

Card t_f454aa44 (standing #119, focus override #1855: most frequent first failing step). Research only: no
product, bank, task-text, scorer or delivered-package change.

## Краткое содержание (RU)

Заполняется после замера (раздел Result). Контракт ниже заморожен до первого замера.

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

(after measurement)

## Result

(after measurement)
