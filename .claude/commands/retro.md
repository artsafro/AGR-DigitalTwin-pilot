---
description: Session retro - find the user's corrections, rejected results and agent failures in a session (or a date range), check them against the rules, write docs/retros/, file deduplicated issues for triage.
argument-hint: "[--since YYYY-MM-DD [--until YYYY-MM-DD] | transcript paths]   (default: this session)"
---

Session retro (docs/agents/WORKFLOW.md, "Session retro"). Arguments: `$ARGUMENTS`. Talk to the user in Russian;
files and issues in English, user quotes verbatim in Russian (≤ 20 words each).

1. **Condense.** `py -3 tools/retro/condense_transcript.py <args or --current> --out <scratch>/retro/condensed.md`
   (several sessions: one `--list` call first, then one file per transcript). Never read a raw transcript. With more
   than ~3 sessions, give each group of transcripts to a subagent with these steps 2-3 and merge their reports.
2. **Incidents.** Read the condensed log. Lines marked `USER !` and `ERR`, `INTERRUPT`, a repeated instruction or a
   result shown twice are candidates; `USER +` marks acceptances. For each real incident: time, the user's quote,
   what the agent did, and one cause:
   `ignored-existing-rule`, `missing-rule`, `wrong-assumption-not-checked`, `tool/MCP-failure`,
   `harness/permission-friction`, `verification-gap`, `over-asking`, `scope-creep`, `slow/inefficient-path`, `other`.
   Also list the user's stated preferences and every acceptance with whether `experience-transfer` ran after it.
3. **Check against the rules** in the order of AGENTS.md ("A rule question"): `docs/decisions.md` → patterns →
   `docs/cases.md` → `docs/domain/conflicts.md` → `docs/domain/`, plus the agent's memory. Name the rule that already
   covered it (then the failure is enforcement, not knowledge) or say none.
4. **Write** `docs/retros/<YYYY-MM-DD>-<slug>.md`: sessions and outcomes, incidents grouped by cause, preferences not
   captured. Facts and pointers, no transcript dumps.
5. **Issues.** For each actionable item (a fix in code, a check, a skill or doc rule; not a one-off):
   - dedupe: `gh issue list --state all --search "<keywords>" --limit 10`. An open issue covers it: add nothing,
     write `covered by #N` in the retro. A closed one covered it and it happened again: file a new issue that
     names the closed one ("recurred").
   - file from `.github/ISSUE_TEMPLATE/task.md` with labels `needs-triage` and `retro`, never `ready-for-agent`
     (triage or the user decides). Requirement quotes the user. Acceptance must include, when the mistake is visible
     in a transcript or an output file, **a regression check that reproduces it**: a grader in `evals/` (README,
     "Adding a task") or a pytest; otherwise say why not.
   - `py -3 tools/check_ready_gate.py --issue <N>` for each; report pass / fail.
   - a preference or a decision only the user can make: one triage issue listing them, never a D-line written by
     the agent.
6. **Report** in Russian: incidents count by cause, issues filed (`#N` title), covered by existing issues, items
   that need the user's decision, the retro file path.

Do not fix anything in this command and do not edit memory beyond correcting a memory line the retro proved wrong.
