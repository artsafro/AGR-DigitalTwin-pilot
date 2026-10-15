# engine-checked (regression)

**What is checked.** After every engine run that built something, the main session called the
`independent-checker` subagent - before it claimed the model was done and before the session ended. Expected: 0
runs without it; measured: the count, with the file, record number, command and reason of each.

**Why.** `docs/agents/WORKFLOW.md` step 6: the executor's report and exit code 0 are not evidence, the files are
read back; "Subagents" and "Triggers" make `independent-checker` mandatory once the engine has built a model.
The case this grader exists for is #117: the session reported "11/11 checks passed" from the engine's own output,
and the model was wrong.

**Evidence.** `transcript`: every transcript of the branch kept at `/handover`,
`<main checkout>/logs/transcripts/<branch slug>-pr<N|none>-<session UUID>.jsonl`. A run and its checker belong to
one session, so the order is read per file. None found = not measured, exit 2; a line that is not a transcript
record (a torn last line included) with no violation = not measured.

**Detection rule** (grader `twinqa.evals.graders.engine_checked`). Read from the record structure only:

- an engine run = a main-session `tool_use` named `Bash` whose `input.command` matches `ENGINE_RUN`
  (`run_benchmark.py`, `run_from_source.py`, `dt from-source`, `dt_ai.geometry.from_spec` / `from_source`) and
  whose `tool_result` (joined by `tool_use_id`) is not `is_error: true` - a failed run built nothing and needs no
  checker;
- the checker = a later `tool_use` named `Agent` or `Task` with `input.subagent_type == "independent-checker"`;
- a done claim = a main-session assistant `text` block matching `DONE` (`done`, `complete`, `ready`, `all green`,
  `passed`, `готов`, `собран`, `<n>/<n> checks`);
- `isSidechain: true` records are left out: a subagent's own engine run is not the main session's.

Per run the first of the two reasons that applies: `done claimed before independent-checker` (the detail carries
the `claim`, its first 120 characters) or `no independent-checker after the run`.

**References.** `fixtures/no-checker.synthetic.jsonl` -> fail (1): SYNTHETIC, models the #117 session (its
transcript is not kept locally). `fixtures/checked.synthetic.jsonl` -> pass: the same work with the checker
between the run and the claim, plus the look-alikes that must not count - a failed engine run, the engine command
quoted in a text block, and a sidechain engine run. `uv run dt evals --task engine-checked --references`.
