# ECC practices vs our agent rules

Date: 2026-10-26.

ECC main: `25278e7d7b6cf6e6a4e7a6c8e10f14ff22f0eb5b` (read-only clone `C:/x/ecc`, cited below as `ecc/…`).
Pilot main: `4c863c1a4616f1812595536d0507f53034e9acfe` (this worktree).

Related note, not repeated here: [`docs/research/agent-harness-practices.md`](agent-harness-practices.md) (pass@k, budgets, stuck detection, why unbounded loops and auto-merge stay out).

## Method

Top-level practices are the ones ECC states as the system, not the skill catalog: the loop and the six contrasts in `ecc/README.md:135` and `ecc/README.md:1223`, the five principles in `ecc/AGENTS.md:9`, every file in `ecc/rules/common/`, the three guides (`ecc/the-shortform-guide.md`, `ecc/the-longform-guide.md`, `ecc/the-security-guide.md`), the three contexts, and the verification / eval / instinct skills those guides name.

Mapped against `AGENTS.md`, `docs/agents/WORKFLOW.md`, `docs/agents/REVIEW_CHECKLIST.md`. `docs/agents/task-intake.md` is not in this worktree. A search for `Karpathy` and `working principles` hits only the task card, so PR #711's principles are not in this tree.

`MISSING` means no line in those files states the practice. A nearby line is named in the note and is not an equivalent. `different` means a real line covers the same job with other wording or a tighter bound.

Colouring failures used for drafts are only `docs/retros/2026-10-22-tec26-colouring-claude.md` and `docs/retros/2026-10-22-tec26-colouring-codex.md`.

## Table

| # | Practice | ECC file | Our equivalent | Note |
|---|---|---|---|---|
| 1 | Plan before code | `ecc/rules/common/development-workflow.md:17` | `docs/agents/WORKFLOW.md:24` | different: the plan follows the contract |
| 2 | Keep the plan as an artifact | `ecc/README.md:1223` | `docs/agents/WORKFLOW.md:190` | different: the requirement text stays; a later decision is appended |
| 3 | Search and reuse before new code | `ecc/rules/common/development-workflow.md:9` | `docs/agents/WORKFLOW.md:262` | different: reuse after a second repeat, not a registry search first |
| 4 | Read the source before writing | `ecc/contexts/research.md:10` | MISSING | nearest `docs/agents/WORKFLOW.md:15` says read the inputs; it does not require an extracted authority table. Draft 1 |
| 5 | Ask while researching | `ecc/contexts/research.md:8` | `docs/agents/WORKFLOW.md:113` | different: ask only unresolved questions that change the result |
| 6 | TDD: RED, then GREEN, with evidence | `ecc/README.md:1224` | `docs/agents/WORKFLOW.md:468` | different: RED replay of a regression, not a gate on every change |
| 7 | 80% coverage and unit, integration, and e2e | `ecc/rules/common/testing.md:3` | MISSING | our measured-check bar is `docs/agents/WORKFLOW.md:69`. Not adopted |
| 8 | A wrong check is fixed, not kept green | `ecc/rules/common/testing.md:25` | MISSING | nearest `docs/agents/WORKFLOW.md:32` forbids rewording a failed check. Draft 6 |
| 9 | A fresh context reviews the code | `ecc/README.md:1225` | `docs/agents/REVIEW_CHECKLIST.md:3` | the reviewer is not the author |
| 10 | Critical findings block the merge | `ecc/rules/common/code-review.md:55` | `docs/agents/REVIEW_CHECKLIST.md:39` | different label (P1). The merge still waits for the user: `docs/agents/REVIEW_CHECKLIST.md:38` |
| 11 | The result is evidence, not the claim | `ecc/README.md:1243` | `AGENTS.md:59` | exit 0 is not a finished model |
| 12 | Verify again after the change | `ecc/skills/verification-loop/SKILL.md:16` | MISSING | nearest `AGENTS.md:59` reads one export. Draft 2 |
| 13 | Record what worked with evidence | `ecc/the-longform-guide.md:46` | MISSING | nearest `AGENTS.md:59` checks the model file, not the published picture. Draft 3 |
| 14 | The confirmed plan is what runs next | `ecc/README.md:1234` | MISSING | nearest `docs/agents/WORKFLOW.md:190` appends the decision and does not stop the old path. Draft 4 |
| 15 | Distil the session and resume from that | `ecc/the-longform-guide.md:40` | `docs/agents/WORKFLOW.md:271` | handover, then a new context in the same worktree |
| 16 | Turn a repeated lesson into a skill | `ecc/the-longform-guide.md:89` | `docs/agents/WORKFLOW.md:355` | different: only after the user accepts; a skill waits for a second object (`docs/agents/WORKFLOW.md:361`) |
| 17 | Instincts with confidence scores | `ecc/README.md:1255` | MISSING | store is `ecc/skills/continuous-learning-v2/SKILL.md:3`. Not adopted |
| 18 | Hooks enforce checks outside the prompt | `ecc/README.md:1227` | `docs/agents/WORKFLOW.md:251` | skill gate and usage log |
| 19 | Scan the agent config as an attack surface | `ecc/README.md:1228` | MISSING | nearest `docs/agents/WORKFLOW.md:322` is an inventory, not a scanner. Not adopted |
| 20 | The safety boundary sits between the model and the action | `ecc/the-security-guide.md:259` | `docs/agents/WORKFLOW.md:363` | permission matrix |
| 21 | Do not skip permission checks | `ecc/rules/common/hooks.md:14` | `docs/agents/WORKFLOW.md:368` | `never` is not a prompt the model may override |
| 22 | Treat untrusted text as untrusted | `ecc/CLAUDE.md:11` | MISSING | no line in the mapped files. Not a cited colouring failure |
| 23 | Run untrusted work in a sandbox | `ecc/the-security-guide.md:126` | `docs/agents/WORKFLOW.md:392` | different: the guard asks; it is not a sandbox |
| 24 | Log tool name, input, and approval | `ecc/the-security-guide.md:283` | `docs/agents/WORKFLOW.md:252` | usage log; the trace fields are `docs/agents/WORKFLOW.md:291` |
| 25 | Kill the process group when the heartbeat stalls | `ecc/the-security-guide.md:314` | MISSING | already proposed in `docs/research/agent-harness-practices.md:106`. Not drafted |
| 26 | Keep persistent memory narrow | `ecc/the-security-guide.md:345` | `docs/agents/WORKFLOW.md:303` | different: one kind of fact, one file |
| 27 | Immutability | `ecc/rules/common/coding-style.md:3` | `AGENTS.md:58` | different: new versioned paths; do not overwrite sources |
| 28 | KISS, DRY, YAGNI | `ecc/rules/common/coding-style.md:17` | MISSING | our order is `AGENTS.md:14`. Slogans not adopted |
| 29 | Prefer small files | `ecc/rules/common/coding-style.md:37` | MISSING | no line cap in the mapped files |
| 30 | Do not swallow errors | `ecc/rules/common/coding-style.md:50` | `docs/agents/WORKFLOW.md:32` | a failed check is not reworded into a pass |
| 31 | Validate data at the boundary | `ecc/rules/common/coding-style.md:54` | `docs/agents/REVIEW_CHECKLIST.md:12` | a silent fallback that hides a failure is a finding |
| 32 | Leave the tail of the context window | `ecc/rules/common/performance.md:22` | `docs/agents/WORKFLOW.md:275` | different threshold: about 40–50% |
| 33 | Route the model by task size | `ecc/rules/common/performance.md:3` | MISSING | not adopted. Named agents: `AGENTS.md:3` |
| 34 | Delegate to a specialist | `ecc/rules/common/agents.md:30` | `docs/agents/WORKFLOW.md:213` | named read-only subagents |
| 35 | Parallelise independent work | `ecc/rules/common/agents.md:38` | `AGENTS.md:50` | different: one writing agent per worktree |
| 36 | The parent's last message includes the children's results | `ecc/rules/common/agents.md:55` | `docs/agents/WORKFLOW.md:229` | different: call the checker before "done" |
| 37 | Define the scope before a parallel split | `ecc/the-longform-guide.md:176` | MISSING | nearest `AGENTS.md:50`. Draft 5 |
| 38 | One git worktree per parallel stream | `ecc/the-longform-guide.md:191` | `AGENTS.md:50` | one task, one branch, one worktree |
| 39 | Conventional commit types | `ecc/rules/common/git-workflow.md:10` | `docs/agents/WORKFLOW.md:467` | different: an honest status message |
| 40 | PR text from the whole branch | `ecc/rules/common/git-workflow.md:16` | `docs/agents/WORKFLOW.md:88` | different: author receipts |
| 41 | Skills are the workflow surface | `ecc/AGENTS.md:177` | `AGENTS.md:41` | load the matching skill |
| 42 | Install few always-on rules | `ecc/README.md:1253` | `AGENTS.md:7` | this file, the area file, and the card |
| 43 | Keep the window small; persist the rest | `ecc/README.md:140` | `docs/agents/WORKFLOW.md:303` | the memory map |
| 44 | Cap enabled MCP tools | `ecc/the-shortform-guide.md:146` | MISSING | no numeric tool cap. Shared DCC owner: `AGENTS.md:56` |
| 45 | Checkpoint and regression evals | `ecc/the-longform-guide.md:157` | `docs/agents/WORKFLOW.md:51` | regression evals before review; not a timer |
| 46 | pass@k and pass^k | `ecc/the-longform-guide.md:163` | MISSING | already in `docs/research/agent-harness-practices.md:32`. Not adopted (`docs/research/agent-harness-practices.md:8`) |
| 47 | Start from a skeleton project | `ecc/rules/common/patterns.md:3` | `docs/agents/WORKFLOW.md:256` | different: rule of three, not a cloned template |
| 48 | Fix a broken build in small steps and re-check | `ecc/rules/common/performance.md:56` | `docs/agents/WORKFLOW.md:31` | classify, fix the cause, rerun |
| 49 | Web security checklist before every commit | `ecc/rules/common/security.md:5` | MISSING | SQL, XSS, CSRF, rate limits. Not this delivery. Action policy: `docs/agents/WORKFLOW.md:363` |
| 50 | Agent-first: the specialist works, the parent decides | `ecc/AGENTS.md:9` | `docs/agents/WORKFLOW.md:227` | only the main agent writes |

## Drafted rules

Six gaps. Each is a MISSING row that matches a colouring failure. Wording is ours. Nothing here is copied into a rule file.

### 1. Extract the authority before the first card

Row 4. Failure: the orchestrator did not open the presentation before assigning work, and there was no step that reads the sources first (`docs/retros/2026-10-22-tec26-colouring-claude.md:56`). The same run handed out paths instead of an extracted facade and legend (`docs/retros/2026-10-22-tec26-colouring-codex.md:57`).

Before the first card of a visual job, open the named authority (facade slides and legend) and write a table: id, material, colour, texture, and the counts taken from that source.
A card starts from that table. A guess, a crop of a texture, or "as the etalon" is not the table.

### 2. A fix rebuilds the named delivery

Row 12. Failure: after the generator was fixed, the exporter still used the old textures, and the archive did not match the contract, because the code fix was not tied to a rebuild of the final artifact (`docs/retros/2026-10-22-tec26-colouring-codex.md:73`).

A fix to a generator, exporter, or map is unfinished until the delivery named in the contract is rebuilt from that fix and read back.
The previous archive, a previous texture version, or a passing generator test does not carry over.

### 3. The published picture is the evidence

Row 13. Failure: the published yellow sample did not match the recorded RGB while the material JSON was correct, because the check read the JSON and not the published picture (`docs/retros/2026-10-22-tec26-colouring-codex.md:76`).

For a colour or facade result, compare the picture that was actually published with the named source slide.
A correct material record, a face count, or a local audit does not replace that picture.

### 4. The latest decision is the next action

Row 14. Failure: after the light instruction was published, the card still ran the full suite and the reviewer, because the new instruction did not replace the workflow already in progress (`docs/retros/2026-10-22-tec26-colouring-codex.md:79`). Rules also changed under running cards, and those cards were not restarted (`docs/retros/2026-10-22-tec26-colouring-claude.md:81`).

When a later decision narrows the job, the next action follows that decision.
A run already in progress does not finish the superseded checks and then claim the new mode.

### 5. Siblings start from one published recipe commit

Row 37. Failure: fan-out was declared before a usable recipe was published, and build permission and technical dependencies were not one contract (`docs/retros/2026-10-22-tec26-colouring-codex.md:62`). Other buildings waited because the pilot recipe was not a commit on their cards (`docs/retros/2026-10-22-tec26-colouring-claude.md:70`).

Sibling cards start only from a named commit that contains the pilot recipe and the permission to build.
A review comment or a chat status is not that commit. One owner edits the shared recipe; the others edit object specs.

### 6. The check's denominator is the required set

Row 8. Failure: a 33/33 QA result allowed every ribbed surface to be replaced by a smooth one, because only the patterned faces the tool found were checked (`docs/retros/2026-10-22-tec26-colouring-codex.md:74`). A compare wrote match while an independent result was false, because a count stood in for the source (`docs/retros/2026-10-22-tec26-colouring-codex.md:75`).

A count of faces the checker happened to find is not proof that every required surface was checked.
If an independent comparison says fail, the report stays fail. Fix the checker or list the miss.

## Not adopted

- Row 7, the 80% line-coverage gate and mandatory e2e. Our bar is every measured regression check (`docs/agents/WORKFLOW.md:69`). On the colouring day the full suite was the waste (`docs/retros/2026-10-22-tec26-colouring-claude.md:62`, `docs/retros/2026-10-22-tec26-colouring-codex.md:90`).
- Row 17, instincts. They need the ECC install and a Stop hook (`ecc/skills/continuous-learning-v2/SKILL.md:3`). Accepted work already goes to cases (`docs/agents/WORKFLOW.md:355`). An automatic instinct would store the guesses this retro is about.
- Row 19, AgentShield. It is an installed scanner (`ecc/README.md:1228`), not a sentence in our rules.
- Row 25, process-group kill and heartbeat. The proposal is already in `docs/research/agent-harness-practices.md:106`. The colouring timeout did fire (`docs/retros/2026-10-22-tec26-colouring-claude.md:72`).
- Row 33, Haiku / Sonnet / Opus routing. This repo names Claude Code, Codex, and Antigravity (`AGENTS.md:3`).
- Row 46, pass@k as a target. Already recorded, and unbounded repeats stay out (`docs/research/agent-harness-practices.md:8`).
- Row 49, the web checklist (SQL, XSS, CSRF, rate limits) in `ecc/rules/common/security.md:5`.
- Row 28 and row 29, KISS/DRY/YAGNI and the 800-line file cap. Coding-style slogans, not a failure in these retros.
- Row 23 as a container sandbox, and row 44 as a numeric MCP cap. We are one trusted DCC workstation; the guard is not a sandbox (`docs/agents/WORKFLOW.md:392`), and one owner holds each DCC scene (`AGENTS.md:56`).

## Out of scope

- Language and framework packs under `ecc/rules/` other than `common/`, the 71 agents, and the 311 skills, except the three skills cited above.
- Install, marketplace, dashboard, tmux, mgrep, and hosted ECC Pro.
- Our rules that ECC does not state as a top-level practice: recitation (`docs/agents/WORKFLOW.md:173`), stop after two failures of the same cause (`docs/agents/WORKFLOW.md:32`), synthetic data (`AGENTS.md:63`), `passed=true` while a gate is open (`AGENTS.md:61`).
- Editing `AGENTS.md` or any other rule file. `docs/agents/task-intake.md` is absent here; its text is not invented from an unmerged PR.
