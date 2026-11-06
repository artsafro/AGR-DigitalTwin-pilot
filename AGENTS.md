# AGR-DigitalTwin — agent instructions

Shared by every agent (Claude Code, Codex, Antigravity). Agent-specific notes:
`CLAUDE.md`, `docs/agents/codex.md`, `GEMINI.md`. Talk to the user in Russian [D088]; write code,
commands, identifiers and docs in English.

A worker reads three things, then starts: this file, the card's area file `docs/domain/areas/<area>.md`, and the card.
Long form of the sections below: `docs/agents/agents-reference.md`.

## Goal

Produce delivery models from architectural sources — NPM and VPM per the Moscow
regulation, later IFC — for buildings (OKS), Ground, MAF (GroundEl), Flora and UCX
collisions, plus the interactive Unreal experience. Priorities, in order:
1. Architectural accuracy 2. Correct scale and transforms 3. Material correctness
4. Performance 5. Visual fidelity.

## Where things are

Read on demand, one line each. Read the domain file that matches the task before production work. Where sources disagree (`docs/domain/conflicts.md`), ask the user; never pick a side silently.

- Current state, next actions: `docs/PROJECT_STATE.md` (generated; `python tools/state/project_state.py`).
- Every dated user decision (`D<n>`): `docs/decisions.md`.
- Which kind of fact lives in which file: `docs/agents/WORKFLOW.md`, "Memory map".
- Who owns what (Claude / Codex / Antigravity): `docs/agents/ROLES.md`.
- Task loop, handoff, experience capture: `docs/agents/WORKFLOW.md`.
- Review questions, author receipts and how to run a Codex review: `docs/agents/REVIEW_CHECKLIST.md`, `docs/agents/WORKFLOW.md#before-requesting-review-author`.
- Tools, MCP routes and their verified status: `docs/agents/CAPABILITIES.md`.
- Production rules with citations (NPM/VPM, geometry, UV, materials, export, validation): `docs/domain/`.
- Open conflicts between sources: `docs/domain/conflicts.md`.
- Pipeline stages and their status: `docs/pipeline.md`.
- Unsolved work: `docs/backlog.md`.
- Removed closed jobs, experiments and orphan docs (tag `archive/2026-11`): `docs/ARCHIVE.md`.
- Accepted cases and lessons: `docs/cases.md`.
- Terms: `GLOSSARY.md`.
- Names for scripts, tools, jobs, outputs, branches and tags; object ids: `docs/agents/NAMING.md`, `jobs/REGISTRY.md`.
- Benchmark etalons and pattern registry: `benchmark/`, `docs/domain/patterns/INDEX.md`. Removed historical files: `docs/ARCHIVE.md`.
- Machine-readable rules: `standards/` (locked; change procedure in `standards/README.md`).
- AGR knowledge base (Russian originals, read-only): `docs/agr/INDEX.md` only, then the file it names.
- Code map, checks and plugin configuration: `docs/agents/agents-reference.md`.
- Modelling or reducing a model: read `docs/procedure/TASK_TO_MODEL.md` (fixed gates, free path, evidence checklist).
- Task skills: load the matching `.agents/skills/*/SKILL.md` and follow it step by step (details: `docs/agents/agents-reference.md#skills`).

A rule question ("is there a rule for ...?") is looked up in this order, and the first hit wins:
`docs/decisions.md` -> `docs/domain/patterns/INDEX.md` -> `docs/cases.md` -> `docs/domain/conflicts.md` ->
the matching `docs/domain/` file. `docs/agr/` is opened only through `docs/agr/INDEX.md`. A new user decision
gets a line in `docs/decisions.md` and its `[D<n>]` where it applies.

## Rules for every task

- A new task from Artem: task intake BEFORE code, issues or cards (sources first, one batch of <= 5 questions
  with recommendations, «Не трогать» + numbers, first piece accepted, then the rest). A card worker runs the
  preflight and asks all open questions once at the start: `docs/agents/task-intake.md` [D186].
- One task = one branch = one worktree = one writing agent. Branch names, prefixes and tags:
  `docs/agents/NAMING.md`. `main` stays clean; work reaches it by reviewed merge.
  A second agent in someone else's worktree only reads, researches or reviews.
- A worktree branch with an auto-generated name (`claude/<words>-<hex6>`, e.g. `claude/laughing-hawking-e62961`)
  is renamed by `NAMING.md` before the first commit: the agent proposes one name in one line, the user
  confirms, then `git branch -m`. The pre-commit gate blocks commits on such a branch.
- One owner per DCC scene, MCP port and export folder at a time; worktrees do not isolate them.
- Before any DCC call confirm the application, document, units and version; start read-only.
  Saves and exports go to a new versioned path. Never overwrite sources or approved versions.
- A successful import or exit code 0 is not a finished model: read the exported file back
  and check topology, UV, materials and transforms (`validate-delivery` skill).
- `passed=true` is forbidden while any mandatory check or manual gate is open.
  Technical QA, user acceptance and publication are separate statuses.
- Mark synthetic data as synthetic. Never present it as data of a real object.
- Apply the [Permission matrix](docs/agents/WORKFLOW.md#permission-matrix) for action
  permissions and its named guard rules/gates; it is the single policy for all agents.
- Update `docs/PROJECT_STATE.md` only on `main` after a merge, by regenerating it
  (`python tools/state/project_state.py`; ≤ 80 lines, fixed sections; `docs/agents/WORKFLOW.md`);
  in task branches report state changes in the final summary.
- A new tool counts as shared only after it is listed in `docs/agents/CAPABILITIES.md` on `main`.
- Four working principles (assumptions first, simplest fit, surgical changes, verified done): `docs/agents/working-principles.md`.

## AGR Tools 1.0 — конвейер ОКС (#1024)

Правила волны 1.0. Контракты К1–К5 — в `issue_body.md` волны. Решения Артёма 06.11.2026 приоритетнее.

- **Паспорт проекта обязателен (К1).**
  - У каждого проекта есть `jobs/<ID>/passport.json` и `PASSPORT.md`.
  - Схема — `schemas/ProjectPassport.schema.json`. Битая схема — ошибка.
  - Сцена хранит в file properties `agr_passport` путь и sha паспорта.
  - Новый проект начинается командой «завести проект». Без паспорта этапы 1–9 не запускаются.
- **Роли и метки.**
  - Роль объекта — user property `agr_role`, слой `<ROLE>_*`.
  - Метка проёма — `OPEN_<nnn>`, хелпер высоты — `LEVEL_<name>`.
  - Константы и валидаторы — `adapters/max/agr_tools/contract_core.py`. Меняется только маленьким PR.
- **Окна (К2).**
  - Библиотека окон — стандарт: `library/windows/window_types.json`, `standard.json`.
  - Тип, не прошедший критерии, получает `status: quarantine`. Агенту и `win.place` он не предлагается.
  - Артём подтверждает изменения библиотеки **одним листом превью «было → стало»**. Решение пишется в `confirmations.json`.
  - Новые типы агент предлагает только черновиком в `library/windows/drafts/`. В библиотеку он попадает через тот же лист.
- **Библиотеки на Google Диске (К5).**
  - Лежат в `G:\Мой диск\AGR-assets\<lib>\`. Список, версии и связь с git — в `library/README.md`.
  - Читать только с копии в своей scratch-папке. Оригинал на Диске не открывать и не менять.
- **Агент в Max.**
  - Пишет только в слой `AGENT_*` и только через MCP-операции меню D108.
  - Результат попадает в сцену через `agent.accept` (шлюз инвариантов, откат при нарушении).
  - Apply подтверждается только кнопкой в доке или UI. Подтверждение в чате не считается.
  - `agr_exec_unsafe` в мосте агента запрещён.
- **Механика роя — Sonnet.** Лабораторные отчёты, обновление `expected`, `CHANGELOG`, документы и слияния делает Sonnet. Геометрию, архитектуру и контракты ведёт основная модель.
