# Background subagent time box

Checks #1539 using the main Claude Code transcript only. Background `Agent`/`Task`
launches (`run_in_background: true` or native string `"true"`) start independent clocks.
The prompt may declare `Time box: <positive finite number> min`; default: 30 min.
A stated but unsupported/invalid time box makes evidence incomplete, never green.

A successful, nonempty `TaskOutput` result for the launch's `agentId`, or `Read`
result for its exact `output_file`, resets that clock at result time, not request time.
Native user task-notifications with completed/failed/stopped status end that agent's
clock. Quoted assistant messages, sidechains, unrelated reads and `SendMessage`
requests do not establish that the main agent read progress. A terminal TaskOutput
status in `toolUseResult.status` also ends the clock. Every unattended interval
**>=** its limit fails; a late check cannot erase it. Checks must happen before the
boundary. Agents are scoped per transcript/session; duplicate records are ignored.

Empty, unreadable, unsupported, torn, invalid/nonmonotonic or timezone-free
transcripts and unfinished launches are not measured unless a definite lapse was
already found (failure wins). No-background complete Claude evidence passes vacuously.
The grader does not interpret prose to prove sourced constraints, simplify/stop
judgement, user notification or production permission; those remain author/reviewer
checks. It conservatively grades every background Agent, not a guessed production
classifier. It cannot see silent elapsed time beyond the last timestamp.

## References

- `unchecked.real-excerpt.jsonl`: native records 697, 698, 1845 (zero-based) from
  session `0a21d4de-b856-441d-aca7-6f9a100cd31c`, local Claude project
  `C--Users-artsafro--AGR-DigitalTwin-pilot--claude-worktrees-erm-maps-diffusers-42de36`.
  Projection preserves type, timestamp, uuid, sidechain flag, message and native
  toolUseResult verbatim; other record metadata omitted. Launch at
  2026-11-15T22:35:16.277Z; user intervention at 2026-11-16T00:05:54.456Z.
  Intermediate unrelated work is omitted, not presented as a complete transcript.
  Source interval inspection found no TaskOutput and only unrelated Read calls;
  the first status request was SendMessage at 23:45:47.839Z, already overdue.
  The issue's retro file is absent on the starting main; the native transcript is
  the provenance authority, not a reconstructed synthetic incident.
- `checked.synthetic.jsonl`: explicitly synthetic corrected schedule; read at 20 min,
  decision to continue/user update, completed output at 40 min. No real model work claimed.

Run: `uv run dt evals --task subagent-timebox --references --output tmp/timebox-refs`.
Tests: `tests/test_subagent_timebox.py`.
