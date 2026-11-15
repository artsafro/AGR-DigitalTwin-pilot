# Task intake: ask before building (user order 2026-10-22) [D186]

> «Когда я ставлю задачу, агент запускает алгоритм, по которому он меня начинает спрашивать по задаче, перед тем как
> приступать, и потом перегенерировать промпт и этот промпт раздавать ... проанализировать, достаточно ли всего агенту
> для выполнения, и если нужны уточнения, уточнить это заранее, чтобы ускорить выполнение задачи» (Artem, 2026-10-22).

Why: the TEC26 texturing job (jobs/TEC26-OKS, #558–#566) lost ~4 h and many tokens. The inputs were complete (DWG,
facade album, KPP etalon), but nobody asked the production questions before building: agents assumed a geometry
rebuild, KPP cassette joints and solid panels; the real answers (colour only, vertical joints only, Artem's own panel
texture, KPP texel, «если не влезает — аккуратно резать loop/ring») came one by one after wrong renders, while eight
cards ran in parallel on the wrong assumption.

## Who does what

- **Agent that receives a task directly from Artem** (Claude Code / Codex session in this repo, the Hermes
  orchestrator): run the full intake below BEFORE writing code, issues or cards.
- **Card worker** (the task came as a card/issue): run the **preflight** below at the start of the card.

## Check level [D273]

Record `level: fast | standard | full` in the task/card and state the selected level in the first message.
The orchestrator/agent sets it at intake by the [check-level table](../procedure/TASK_TO_MODEL.md#check-levels);
Artem overrides with one word (`fast`, `standard` or `full`). An agent may go up a level with a one-line
reason, never down on its own. Check level is separate from the `level:simple|medium|hard` dispatch label.
A card worker checks the field during preflight; if absent, select it by the table and state why.
Read the worker policy there before choosing readback, review and image evidence [D273].

## Full intake (task from Artem)

1. Read the sources yourself first (read only, 5–10 min): folders, the album/presentation slides that show the
   result, the etalon's maps and report. Ask about production choices, never about a path you were given.
2. Ask ONE batch of at most 5 questions, each with your recommendation first, only what the sources leave open.
   Quote what you already found («в презентации швы вертикальные, шаг ~0,6 м — так?»).
3. Write the task from his answers: his words verbatim under `## Requirement`; an explicit «Не трогать» list;
   numbers for every «как у X»; the source of every input; the acceptance picture; the fallback when something does
   not fit.
4. First piece, then the rest: one object / building / facade end to end (target 20–40 min), a picture to Artem, his
   «да» — only then the same script for the rest, in parallel. When Artem is online, use the opened scene
   and absolute path instead of the picture/render; apply the [check-level image limits](../procedure/TASK_TO_MODEL.md#check-levels) otherwise [D273].

## Preflight (card worker)

Before production work, check the card against the checklist. If an item that changes the result is open and the
sources + `docs/decisions.md` + the card/issue comments do not answer it: block ONCE at the start with ALL such
questions in one list, each with your recommended answer — do not guess and do not discover them one per run.
Items listed under «Не трогать» are never changed «to make it work»; a conflict with them is a question.

## Checklist

Common:
- Scope: what changes, what must NOT be touched (geometry, topology, UV, UCX, material IDs, names, other objects).
- Etalon: «как у X» in numbers — which file, which parameters (texel, tile size, map types, naming, palette).
- Inputs: which sheet / slide / file is the authority per item; which one wins on conflict (e.g. DWG `_R1` vs PDF).
- Multi-building/part sheets: mark `finish_sheets[].multi_building: true`; record each part's `finish_refs: [{image, bbox, crop}]` (original-image pixel bbox `[left, top, right, bottom]`, top-left origin, right/bottom exclusive), save a crop beside the analysis in external evidence, record the finish read from it in `legend_item`, and give subagent briefs the crop path rather than the sheet name; verify crop content/existence and image bounds before Gate 1.
- Output: what is delivered (VPM / NPM / both, package names, where) and the picture it is accepted by.
- Fallback: what to do when it does not fit or the source is silent.
- Pilot: which piece goes first.

Texturing (VPM UDIM / NPM atlas):
- Colour only, or may faces be cut (only loop/ring at joints)? How is the below-ground perimeter drop textured?
- Panels: joint direction (vertical / horizontal / grid), step, width, phase origin (±0.000, panel corner).
- Texture source per finish: Artem's texture / etalon tile / flat RAL; same RAL = the etalon's colour.
- Texel px/m and tile size (VPM 2048/4096); NPM atlas size, joints ≥ 1.5 px.
- Mixed material IDs (roof + frame + plinth in one ID): split by region without changing geometry?

Harness / hygiene / tooling tasks (issues touching `docs/agents/`, hooks, guards, evals, procedures, `tools/`):
- Before/after metric: ONE measurable number the change must move, agreed at intake. Examples: cold-entry
  tokens (`tools/state/entry_budget.py --check`, as in #1015), subagent / skill / command calls
  (`tools/hooks/usage_log.py stats --days N`), turns or wall time on a reference card, failing tests. Guard
  prompts per session: hook denials are counted by `tools/hooks/agent_trace.py --transcript <session.jsonl>`
  (the `Hook denials` field, from `permissionDecision` deny/reject in the transcript); guard asks are not
  measured today. Say how and when it is measured (on `origin/main` before, on the branch after; which
  command, which card / seed).
- Reuse an existing measure where one exists — the readiness evaluator `kpi/readiness/…json` (hermes_kanban),
  `tools/hooks/usage_log.py stats` (subagent / skill / command counts), the context-diet test
  `tests/test_context_diet.py` — rather than adding tooling.

Other areas (Ground, MAF, Flora, buildings through the kernel): add the questions their grillings
(`docs/grill/`) showed were missing.
