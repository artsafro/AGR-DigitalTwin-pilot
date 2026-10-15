# routine-question (regression)

**What is checked.** Every question the agent put to the user was the user's to answer. Expected: 0 routine
questions; measured: the count, with the file, record number, question, category and the rule row that already
answers it. The row also lists the allowed questions with their category, and the questions no list recognizes.

**Why.** `docs/agents/COMMANDS.md`, "Что агент спрашивает, а что решает сам": the agent asks about the model
(врезка, глубина, уровень) and the object's data (id, отметки, what sits at height X), and decides the
implementation itself - "Решает сам: алгоритмы, кэши, структура PR, пороги подсказок, формат отчётов. Пишет в PR:
«решено: …, потому что …»". A question whose answer already stands in `docs/decisions.md` or in
`docs/domain/patterns/INDEX.md` costs the user the same minute twice.

**Evidence.**

| Name | Rule | Read for |
|---|---|---|
| `transcript` | `<main checkout>/logs/transcripts/<branch slug>-pr<N\|none>-<session UUID>.jsonl` | the questions |
| `decisions` | `docs/decisions.md` | the decision rows (`\| D<n> \| date \| decision \| ...`) |
| `patterns` | `docs/domain/patterns/INDEX.md` | the pattern rows (name, slug, what it does) |

No transcript = not measured, exit 2; a line that is not a transcript record (a torn last line included) with no
violation = not measured. A missing or unreadable `decisions` / `patterns` file stops the check (not measured):
without the rules a routine question cannot be told from a new one.

**Detection rule** (grader `twinqa.evals.graders.routine_question`). Deterministic, no model call. The questions,
read from the record structure only:

- the last `text` block of a main-session assistant record that ends the turn (the next conversation record is a
  human prompt, or the file ends) when its stripped text ends with `?`: the question is its last sentence;
- every `tool_use` named `AskUserQuestion`: each `input.questions[].question`;
- `isSidechain: true` records are left out: a subagent asks the main agent, not the user.

Each question is classified by lowercase substring match, first list that matches wins (the lists are the module
constants `ALLOWED_QUESTIONS`, `IMPLEMENTATION_WORDS` and `OVERLAP`):

| Category | Verdict | Keywords |
|---|---|---|
| `architecture` | allowed | architecture, архитектур, adr |
| `acceptance` | allowed | accept, approve, принимаешь, принять, утверд, приёмк, приемк |
| `destructive` | allowed | delete, remove, overwrite, reset, drop, удал, перезапис, снести |
| `publication` | allowed | push, merge, publish, release, pull request, пуш, смерж, мерж, опубликов |
| `branch_rename` | allowed | rename, переимен, branch -m |
| `model` | allowed | модел, model, врезк, inset, глубин, depth, level of detail, профил, npm, vpm, mid |
| `data` | allowed | отметк, высот, elevation, object id, данные объекта, object data, source file, исходник, размер, dimension |
| `implementation` | violation | algorithm, алгоритм, cache, кэш, кеш, pr structure, структур pr, split the pr, разбить pr, hint threshold, порог подсказ, report format, формат отчёт, формат отчет |

What no list names is weighed against the rule rows by word overlap: the words of >= 4 letters
(`[a-zа-яё0-9]{4,}`) minus a small stopword set (this, that, with, from, what, which, should, будет, нужно, этот,
какой, какие, можно, или); the score of a row is the share of the question's words it holds. The best row makes
the question a `decision_log` or a `pattern` violation when the score is >= `OVERLAP` (0.5) and at least 3 words
are shared; the detail's `match` is the decision id or the pattern slug. A question that reaches neither a
keyword nor a row is unclassified: with no violation beside it the check is not measured, never a silent pass.

**References.** `fixtures/algorithm-question.synthetic.jsonl` -> fail (1): SYNTHETIC, the turn ends with "Which
algorithm should I use for the hole triangulation, ear clipping or constrained Delaunay?" (`implementation`).
`fixtures/decided.synthetic.jsonl` -> pass: the same turn writes "Decided: ear clipping, because …" and asks
"Do you accept the model v012 for review?" (`acceptance`). Both references read
`fixtures/decisions.excerpt.md` and `fixtures/patterns.excerpt.md`, excerpts of the real files, so a new
decision or pattern cannot change a reference verdict. `uv run dt evals --task routine-question --references`.
