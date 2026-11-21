# Skill evals and cold-run practice from AI-conference talks (#1711)

Source: «Дары Прометея» talk index (https://giftsofprometheus.com/agent), CLI `@giftsofprometheus/cli` 0.8.0,
anonymous search only, run once on 2026-11-20. Claims below are the index's Russian abstracts of the talks
("по словам спикера"), not verified transcripts. Numbers are the speakers' numbers, not ours.

## Кратко (русский, один экран)

- **Skill без eval не выпускают.** Индустрия (DeepMind, Supabase, Langfuse, WorkOS, Arize) меряет skill
  парой прогонов «со skill / без skill» на одних и тех же 10-120 задачах, 3-6 прогонов на задачу. Если без
  skill тоже проходит — skill удаляют, eval оставляют. Сгенерированные skills иногда ухудшают результат
  (97 % -> 77 % у WorkOS).
- **Оценивают результат, а не путь.** Проверка — детерминированная (regex, тесты, состояние базы/файла),
  LLM-судья — только там, где кодом нельзя; эксперт смотрит только расхождения. Наши 15 кейсов `evals/`
  проверяют транскрипт (процесс: загружен ли skill, остановился ли агент), а не модель на выходе.
- **Один прогон ничего не доказывает.** Надёжность = pass^k (все k прогонов успешны), а не pass@k.
  Наш холодный прогон #1608 — один прогон, без контрольной ветки «без SKELETONS/skills».
- **Сначала читать трассы.** Разбор трасс даёт ~80 % правок до любых сложных eval (Langfuse); дешёвый
  агент делает map по сессиям, сильная модель — reduce в `feedback.md` с повторяющимися ошибками
  (Terminal-Bench / Harbor). Провалы ценнее успехов для дистилляции skills.
- **Балласт режут экспериментом.** Абзац лишний, если после его удаления поведение не изменилось
  (Matt Pocock); 95 % skills заменили 553 строками gotchas, eval — с 68 до 6 минут (WorkOS).
  `description` — это триггер: короткие директивы + негативные кейсы, проверять «грузится / не грузится».
- **Средний балл прячет компромисс** (+17 safety / −17 completion = 0); 100 % значит, что eval слабый.
  Целевая функция цикла улучшения решает всё: оптимизация «по числу ходов» выкинула чтение документации.
- **3D/DCC:** найден один доклад (Blender MCP): меньше и непохожие инструменты — точнее выбор; evals
  для CAD/DCC-агентов в индексе нет — наш случай придётся мерить своими валидаторами.

Предложения P1-P5 (ниже) готовы стать issues после «принимаю». Ничего не установлено в репо/профили.

## Safety note on the CLI package

| Item | Finding |
|---|---|
| Package | `@giftsofprometheus/cli@0.8.0`, `npm pack` tarball `giftsofprometheus-cli-0.8.0.tgz`, sha256 `9ebd1ed39d405ed777046df3abaff6578297a1a748e951a8df32db7a4b361349`, sha1 `2f2008aac5b9eeb678381789381f3332af3178af` (= registry `dist.shasum`) |
| Contents | 8 files, 127 KB: `dist/index.js`, `dist/render.js`, `dist/skill-files.js`, `skills/giftsofprometheus/SKILL.md`, `skills/history.json`, README, LICENSE, package.json |
| Install scripts | none (`scripts` has only lint/test/build/check/format/typecheck/prepublishOnly; no `preinstall`/`install`/`postinstall`) |
| Dependencies | `zod`, `commander` only |
| Network | `https://giftsofprometheus.com` (`/api/knowledge/`, `/api/account/`, `/api/auth/device/`; overridable by `GIFTSOFPROMETHEUS_URL`) and `https://registry.npmjs.org/@giftsofprometheus/cli/latest` (daily update check, 1.5 s timeout; off with `GIFTSOFPROMETHEUS_NO_UPDATE_CHECK` or `CI`) |
| Files written | `~/.config/giftsofprometheus/` (`credentials.json`, `login.json`, `onboarding.json`, `update.json`, mode 0600). `skill update` / `skill personalize` rewrite only an existing `giftsofprometheus` SKILL.md under `~/.{agents,claude,codex,cursor}/skills/` or the cwd's same folders — never run here |
| Processes | `spawn` only to open the login URL in a browser (`open`/`xdg-open`; skipped on Windows and with `GIFTSOFPROMETHEUS_NO_BROWSER`) |
| How it was run | `npx -y @giftsofprometheus/cli@0.8.0 --json talks search|get ...` from `C:/x/gop-cli/` with `GIFTSOFPROMETHEUS_NO_UPDATE_CHECK=1 GIFTSOFPROMETHEUS_NO_BROWSER=1`; afterwards `~/.config/giftsofprometheus` did not exist and the worktree had no changes. npx keeps its own copy in the npm cache (`_npx`). No login, no `skills add`, no `skill update` |
| Free vs login | `talks search`, `talks get` (title, Russian abstract, speakers, event, YouTube link, duration) work anonymously. `ask` (transcript passages), `talks content` (transcript, chapters, `--outline`) answer «Требуется вход» |

Verdict: safe for a one-off read-only search. Not installed anywhere.

**Timestamps:** chapters and transcript timestamps are behind the login (`talks content --outline` ->
«Требуется вход»), so each practice cites the talk's YouTube link and total duration instead. Getting
minute marks needs Artem's e-mail login (out of scope of this card).

## Search log

20 anonymous `talks search` queries, 311 unique talks: `skills` (296 hits), `agent skills` (282), `evals` (552),
`agent evals` (425), `coding agent evaluation` (100), `LLM as a judge` (138), `traces`, `observability`,
`context engineering`, `memory` (181), `long-running agents` (55), `benchmark` (185), `SWE-bench` (34),
`cold start` (9, all serverless latency, not relevant), `CAD` (2, none relevant), `3D` (13), `Blender` (4),
`harness` (271), `Claude Code` (165), `regression` (49). About 25 abstracts were read in full.

## Practices

Each row: practice -> talk (speaker, org, event, link, duration). Abstract wording is paraphrased.

### A. Skill evals: with vs without the skill

1. **Ship a skill only with an eval; compare with and without it.** If the model passes without the skill,
   delete the skill and keep the eval to bring it back on the first regression. Run the eval on every
   SKILL.md edit, do not merge unless it improves, 3-6 runs per case, more than one harness; 117 cases checked
   with regexes (no LLM judge) raised valid code to ~90 %. Skills Bench: AI-generated skills sometimes hurt.
   — «Не выпускайте skills без evals», Philipp Schmid (Google DeepMind), AI Engineer World's Fair 2026,
   https://www.youtube.com/watch?v=0vphxNt4wyk (22 min).
2. **A skill changes behavior only when an eval shows it.** Without the skill the agent created a Postgres view
   that bypassed RLS; with it, `security_invoker`. Compare runs with/without, deterministic checks plus
   LLM judge; a wrong check produced a false fail; the same scenario did not always pass. `description` is the
   trigger: test cases where the skill must load and where it must not.
   — «Проблема с навыками…», Pedro Rodrigues (Supabase), AI Engineer Europe 2026,
   https://www.youtube.com/watch?v=GmAQKINjv1E (79 min).
3. **Evidence over claims; fewer skills.** State-machine harness: implementer -> reviewer -> closer only after a
   check passes; test output hashed (SHA-256) so a claimed pass cannot be faked. One doc-generated skill took
   task accuracy 97 % -> 77 %; deleting 95 % of skills for 553 lines of gotchas cut eval time 68 -> 6 min.
   Fix the harness, not the output.
   — «Как я удалил 95 % skills…», Nick Nisi (WorkOS), AI Engineer Europe 2026,
   https://www.youtube.com/watch?v=vy7o1g2iHY8 (18 min).
4. **Hill-climbing a skill needs a reproducible environment and a measurable result.** Doer + teacher loop writes
   `strategy.md`, frozen into SKILL.md when runs stop improving; cost per run $12 -> $3 in two iterations, the
   third iteration failed — check the result at every step; trigger re-learning on failure, not on a timer.
   — «Hill-climbing skills», Shubhankar Srivastava (Browserbase), AI Engineer World's Fair 2026,
   https://www.youtube.com/watch?v=p7gaxmCUiIU (52 min).
5. **Failures distil better skills than successes.** 36 % -> 100 % task success after reusing a distilled skill
   (sample size not given); similar runs merged into one skill.
   — «От 36 % до 100 %…», Rafal Wilinski (Runlayer), AI Engineer World's Fair 2026,
   https://www.youtube.com/watch?v=u-o0sW9nwmk (19 min).

### B. Clean environment, repeated runs, outcome grading

6. **Task = directory: instruction + sandbox + verifier.** Build the eval before choosing the model (Ramp built
   SWE-bench on its own codebase); agentic map-reduce over 32 Codex sessions produced `feedback.md` with
   recurring errors that became tasks.
   — «Всё — это rollout», Ryan Marten, Alex Shaw (Laude Institute, Terminal-Bench/Harbor), AI Engineer World's
   Fair 2026, https://www.youtube.com/watch?v=jRCpXUjz4CI (21 min).
7. **Turn traces into replayable Docker tasks.** The agent sees only `instruction.md` and the environment; the
   oracle solution and verifiers are hidden; the oracle proves the task is solvable; the verifier checks the
   final state; experts review only judge/check disagreements; tasks are binned easy/medium/hard by success rate;
   every production failure becomes a pre-release regression task.
   — «От трассировок agents к симуляциям», Rustem Feyzkhanov (Snorkel AI), AI Engineer World's Fair 2026,
   https://www.youtube.com/watch?v=Ib5t2RLtxvM (20 min).
8. **Reliability is pass^k, not pass@k.** Run each case k times; evaluate graph nodes and retries, not only the
   final answer; the eval set must evolve with the agent architecture.
   — «Ваш агент эволюционировал. А evals — нет.», Ameya Bhatawdekar (Braintrust), AI Engineer World's Fair 2026,
   https://www.youtube.com/watch?v=nxokqOq1imY (24 min).
9. **A few lucky manual runs say nothing about reliability.** Dataset constants vs task variables; simple
   pass/fail scoring readable in logs.
   — «Evals — это не модульные тесты», Ido Pesok (Vercel), AI Engineer World's Fair 2025,
   https://www.youtube.com/watch?v=L8OoYeDI_ls (15 min).
10. **No benchmark? Generate inputs with a known answer and check them in code** (seeded violations, deleted
    clauses, templates); LLM-judge noise was nearly as hard as the task.
    — «Как тестировать AI-агентов, когда нет готового бенчмарка», Nathanael Weill (Air Canada),
    https://www.youtube.com/watch?v=c_SPW__jF9w (20 min).
11. **Completion claims are checked by deterministic hooks** at session end / pre-commit; good guardrails allow a
    cheaper model.
    — «Почему ваш coding agent не всегда следует вашим правилам», Talha Sheikh (Checkout.com), AI Engineer
    Europe 2026, https://www.youtube.com/watch?v=MpZzWMdmQCE (10 min).

### C. Reading traces first

12. **Trace review gives ~80 % of the needed fixes before complex evals.** Traces showed the agent instrumented
    from stale model knowledge before reading docs; optimising the skill for fewer turns made the agent drop doc
    lookups; 3 of 6 proposed improvements accepted, each reviewed by a human.
    — «Skill issue: Langfuse», Marc Klingen (Langfuse), AI Engineer Europe 2026,
    https://www.youtube.com/watch?v=vNCY9kXXyDQ (24 min).
13. **Regression sets from real traces; averages hide trade-offs** (+17 action safety, −17 task completion,
    mean 0); every failure becomes a test; keep protected success cases.
    — «Исправление агента сломало что-то ещё», Sofia Jakovcevic (Arize),
    https://www.youtube.com/watch?v=v5tm5EAzsAs (19 min).
14. **Give the coding agent traces, evals, annotations and logs**: it found silent tool failures; updating a stale
    tool raised success 0 % -> ~90 % where more context did not help.
    — «Дайте агенту развернуться», Ankur Duggal (Arize), AI Engineer World's Fair 2026,
    https://www.youtube.com/watch?v=_zUp6y9bDU8 (36 min).

### D. Trimming skills (ballast) and length

15. **Four checks for a skill: invocation, structure, leading words, pruning.** Steps vs references, branch-only
    material behind a pointer; a paragraph is ballast if removing it does not change behavior.
    — «Создание отличных skills для агентов», Matt Pocock (AI Hero), AI Engineer World's Fair 2026,
    https://www.youtube.com/watch?v=UNzCG3lw6O0 (21 min).
16. **Length limits moved (~2000 rules) but failures became silent and model-specific;** instruction order alone
    changes quality (46-model study); read the whole output.
    — «Какой длины могут быть ваши skills…», Laurie Voss (Arize), https://www.youtube.com/watch?v=XzJD1bvXKjs (22 min).
17. **Skills are supply chain:** static scan + run in a sandbox watching processes, files, network; deterministic
    rules plus an LLM pass, in local + CI + PR comments.
    — «По тексту skill не понять, что он сделает», Roey Ben Chaim (Zenity), AI Engineer Code 2026,
    https://www.youtube.com/watch?v=_7P580m4kPY (14 min); «Как мы проверили 2 000 AI skills», Lucas Palma
    (Nubank), AI Engineer World's Fair 2026, https://www.youtube.com/watch?v=iKQ78wyJEXU (16 min).

### E. Eval difficulty, harness, memory

18. **100 % means the eval is wrong:** raise difficulty at 85-90 %; keep old cases; the agent must not judge its
    own eval. — «Если ваш AI набирает 100 %…», Ramakrishnan Lokanathan (eSlams),
    https://www.youtube.com/watch?v=7WUzHIF32vA (19 min).
19. **Most production failures are harness failures:** one owner per state, ordered writes, every external call
    ends in success/error/timeout/cancel with a receipt. — «Ваш агент не подвёл. Подвёл harness.»,
    Vinoth Govindarajan (OpenAI), AI Engineer World's Fair 2026, https://www.youtube.com/watch?v=BInpv7lGp1o (18 min).
20. **Memory only helps when the task does not fit the context;** a ranked decision journal beat vector RAG;
    irrelevant memory costs tokens and misleads. — «Memory harnesses для долго работающих исследовательских
    агентов», Stefania Druga (Sakana AI), AI Engineer World's Fair 2026,
    https://www.youtube.com/watch?v=R3-anFK1YM8 (13 min). The session log as the durable agent state: «Лог и
    есть агент», Ishaan Sehgal (Omnara), https://www.youtube.com/watch?v=UPwGaM2MKHY (15 min).
21. **3D/DCC:** an LLM drives Blender through MCP by writing scripts; with 14-15 tools it often picked the wrong
    one, fewer and clearly distinct tools helped. No eval method is described. — «Blender MCP и будущее
    инструментов для творчества», Siddharth Ahuja, AI Engineer World's Fair 2025,
    https://www.youtube.com/watch?v=nnktgWtfJHE (17 min). `CAD` returned no relevant talk.

## Mapping onto our setup

| Our piece | Today | Gap vs practice |
|---|---|---|
| Cold run #1608 (open, blocked by #1315) | one fresh Codex run, metrics JSON, `validate_package` result, gap issues | one run (no pass^k); no control arm without SKELETONS.md/skills, so the gain of the skeleton is not measured (practices 1, 2, 8) |
| `evals/` (15 cases, `dt evals --suite regression`) | graders read transcripts: skill loaded, failure stop, branch name, PR trace | process graded, not the delivered model; no with/without-skill pair per skill; no negative trigger cases (1, 2, 7) |
| `.agents/skills/*/SKILL.md` (21 skills, 146 KB; 7 over 8.5 KB) | written by hand, weekly promotion in SKELETONS.md | no ablation: unknown which paragraphs change behavior (3, 15, 16) |
| `docs/agents/SKELETONS.md` + reviewer checklist | stages, verifier in observe mode, reviewer rule [D325] | reviewers read claims and receipts; traces of the run are not mined across cards (12, 6) |
| `mesh_quality_score` / autoresearch keepers | one score per run, keep/discard on it | a scalar can hide a trade-off between checks; 100 % pass on a fixed set stops informing (13, 18, 12-objective) |

## Proposals (each ready to become an issue on «принимаю»)

**P1. #1608 as an A/B with k runs (with vs without skeleton).**
What: run the cold task in two arms on the same object and commit of origin/main — A: repo as is; B: same repo
with `docs/agents/SKELETONS.md` and `.agents/skills/` hidden (a throwaway worktree) — k=3 fresh sessions each.
Report pass^3 and pass@3 on `validate_package`, tokens, wall time, new-code lines per arm.
File: #1608 specification + its metrics JSON schema (`arm`, `run_index`, `k`). Cost: 6 cold runs instead of 1
(~6x tokens of #1608). Gain: the first measured effect of SKELETONS/skills; a no-gain result is a deletion
candidate list (practice 1).

**P2. Outcome evals per production skill, 10-20 cases incl. negative triggers.**
What: for `model-maf` and `validate-delivery` first, add `evals/<skill>-outcome/` cases whose grader runs the
existing deterministic checkers on the produced artefact (`validate_package`, `twinqa` MAF findings,
`mesh_quality_core`) instead of the transcript; 3-5 cases where the skill must NOT load (description trigger).
Each case runs with and without the skill. Files: `evals/`, `src/twinqa/evals/runner.py`. Cost: medium (one
grader type + 2x15 cases; DCC-free fixtures where possible). Gain: skills judged by result, not by "was loaded".

**P3. Skill ballast ablation, starting with the 7 skills over 8.5 KB.**
What: with P2 in place, remove one section at a time and rerun the skill's eval (3 runs); a section whose removal
changes nothing moves to `references/` or is deleted; record before/after bytes and pass rate. Files:
`.agents/skills/{model-flora,model-maf,model-ground,writing-for-agents,analyze-architectural-source,validate-delivery,diagnosing-bugs}/SKILL.md`.
Cost: low per skill after P2. Gain: shorter context per card; evidence from WorkOS/DeepMind that trimmed or
removed skills can raise accuracy.

**P4. Trace-first triage before new checks (map-reduce over transcripts).**
What: a weekly job reads the last N session logs (Claude transcripts in the main checkout's
`logs/transcripts/*.jsonl`, the same files `dt evals` reads; Hermes worker sessions from the profile state) and
the #1608 run:
a cheap model summarises each session (map), a strong one writes `feedback.md` with recurring errors and their
counts (reduce); each recurring error becomes either a regression eval case or a SKELETONS gap line. Files: new
`tools/evals/trace_triage.py`, output under `docs/research/`. Cost: low-medium (tokens per week). Gain: per
Langfuse ~80 % of fixes come from traces; complements the reviewer checklist, which only sees one card.

**P5. Keeper and score hygiene for `mesh_quality_score` and autoresearch loops.**
What: keepers report the per-check vector and refuse a keep when any protected check drops, even if the scalar
rises; when a fixed benchmark passes 100 % (or >= 90 %), the loop must add harder cases before claiming a gain;
the loop's objective may not reward fewer steps alone. Files: `tools/qa/mesh_quality_core.py`, the keep/discard
rule of the `autoresearch` skill (Hermes profile skill, not in this repo) and the report template of
`docs/research/autoresearch-*.md`. Cost: low. Gain: no hidden trade-offs (Arize +17/−17) and no
saturated metrics.

## Not adopted

- LLM-as-a-judge as the main grader: our checks are geometric and deterministic; a judge only for the VLM
  verifier step that already exists (observe mode).
- Remote MCP distribution of skills (Runlayer) and skill marketplaces: we keep skills in git.
- Self-writing skills without a human review: contradicts the reviewed-merge rule.
