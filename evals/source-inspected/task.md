# source-inspected (regression)

**What is checked.** Every architectural source the task touched (`.max`, `.rvt`, `.fbx`, `.blend`, `.skp`,
`.dwg`, `.ifc`) was read by the `source-inspector` subagent in one of the task's sessions. Expected: 0
uninspected sources; measured: the count, with the first file and record that referenced each.

**Why.** `docs/agents/WORKFLOW.md`, "Triggers": a new or updated source makes the `analyze-architectural-source`
skill and the `source-inspector` subagent mandatory. The inspector reports units, layers, levels and slab
candidates without pulling the scene dump into the main context; work started on an uninspected source is the
usual cause of a wrong scale, a missed level or a dropped part.

**Evidence.** `transcript`: every transcript of the branch kept at `/handover`,
`<main checkout>/logs/transcripts/<branch slug>-pr<N|none>-<session UUID>.jsonl`. All the files are the sessions
of one task, so an inspection in any of them counts for a source referenced in another. None found = not
measured, exit 2; a line that is not a transcript record (a torn last line included) with no violation = not
measured.

**Detection rule** (grader `twinqa.evals.graders.source_inspected`). Read from the record structure only:

- a source reference = a path token in the input of a main-session `tool_use`: `Bash` `input.command`, `Read`
  `input.file_path`, or any string value of a DCC MCP call's `input` (`DCC_SKILLS`), matched by `SOURCE`
  (a file name with one of the extensions above);
- not a source: a token whose path holds a folder segment `outputs`, `runs`, `benchmark`, `logs`, `fixtures`,
  `Temp` or `tmp` (case-insensitive), and a name starting with `model.` - those are what the pipeline produced,
  not what came in. A name inside an assistant text is never a reference: only tool inputs count;
- inspected = a `tool_use` named `Agent` or `Task` with `input.subagent_type == "source-inspector"` whose
  `input.prompt` names the normalized source path and whose joined result succeeded (`is_error` is not true,
  `success` is not false). A failed inspector does not cover a source; a missing result leaves that source
  not measured unless another successful inspection covers it;
- `isSidechain: true` records are left out: what a subagent read is not what the main session worked on.

The key is the normalized path (case-insensitive, slash-normalized): one violation per source, however often
it was referenced. Matching uses trailing path segments; a basename-only inspection cannot cover a source
reference that includes a directory.

**References.** `fixtures/no-inspector.synthetic.jsonl` -> fail (1): SYNTHETIC, the main agent reads and dumps
`data/sources/obj03/source.max` itself. `fixtures/inspected.synthetic.jsonl` -> pass: the inspector goes first,
and the look-alikes (an engine output, a benchmark etalon, a source name quoted in a text, a sidechain `Read`)
ask for nothing. `uv run dt evals --task source-inspected --references`.
