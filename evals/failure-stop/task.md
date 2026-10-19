# failure-stop (regression)

**What is checked.** No check was run again after it was blocked: two failures with the same cause, or three
failures, close that path until a stop record is saved. Expected: 0 attempts of a blocked check; measured: the
count, with the file, record number, command, number of open failures and the rule that blocked it.

**Why.** `docs/agents/WORKFLOW.md` step 6: "After two failures with the same cause, stop that path, save the
state and propose the next step"; `docs/agents/COMMANDS.md`: "Три попытки -> стоп, вопрос или issue". Repeating a
failing command is how a session burns an hour and ends with a reworded pass.

**Evidence.** `transcript`: every transcript of the branch kept at `/handover`,
`<main checkout>/logs/transcripts/<branch slug>-pr<N|none>-<session UUID>.jsonl`. The count of failures is per
session, so each file is read on its own. None found = not measured, exit 2; a line that is not a transcript
record (a torn last line included) with no violation = not measured.

**Detection rule** (grader `twinqa.evals.graders.failure_stop`). Read from the record structure only:

- an attempt = a main-session `tool_use` named `Bash`; its check is `input.command` normalized: a leading
  `cd <dir> &&` / `cd <dir>;` dropped, the values of `--output`, `-o`, `--basetemp` and `--run` dropped, every
  digit run as `N`, whitespace collapsed - so a new run folder is the same check;
- a failure = its `tool_result` with `is_error: true`; the cause = the last non-empty line of the result text,
  digit runs as `N`, lowercased (a count or a duration in the line does not make a new cause);
- blocked = the open failures of that check hold two with the same cause (`two failures with the same cause`) or
  three or more (`three failures of one check`); the next attempt is the violation;
- the open failures are cleared by a stop record - an `Edit` / `Write` / `MultiEdit` whose `file_path` ends with
  `pipeline/state.json` and whose written text holds `stops`, or an assistant text **starting** with a
  `Stop record:` / `Запись остановки:` label (optional Markdown heading, colon/dash separator).
  A quoted phrase, negation, promised future stop, blockquote or fenced example does not reset failures.
  A check's own failures are cleared by a run of it that succeeded;
- `isSidechain: true` records are left out: a subagent's retries are not the main agent's.

**References.** `fixtures/third-attempt.synthetic.jsonl` -> fail (1): SYNTHETIC, `uv run pytest -q
tests/test_x.py` fails twice with the same last line and is run a third time. `fixtures/stop-record.synthetic.jsonl`
-> pass: the same two failures, then a stop record (tried, numbers, next step), then the rerun; the look-alikes
are one failure of another command and a rerun after a success. `uv run dt evals --task failure-stop --references`.
