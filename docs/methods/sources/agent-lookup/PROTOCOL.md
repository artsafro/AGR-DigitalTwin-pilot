# Agent lookup experiment protocol (#712)

Frozen source: `4c863c1a4616f1812595536d0507f53034e9acfe` (pilot main at start).
Ground truth: commits `94946a8`, `1c5a220`, before any measured question session.
D186 and AC07 are not present in this snapshot; existing KPP1 and decided rules replace those examples.

## Acceptance table (written before runner code)

| Acceptance | Input | Expected | Test |
|---|---|---|---|
| 20 precommitted questions | frozen JSON | 8 repo / 6 job / 6 API, existing file:line | test_questions |
| One result per question and variant | 20 x A/B/C rows | exactly 60 unique pairs, same model, unique sessions | test_matrix |
| Fail closed | empty / partial / duplicate / unknown variant / error terminal | error, no adoption summary | test_invalid_matrix |
| Real accounting | uncached + cache read + cache creation + output | all four counted, finite nonnegative | test_tokens |
| Numeric correctness | finite number equal / unequal / string / bool / NaN | correct / wrong; invalid references rejected | test_numeric |
| Adoption threshold | equal baseline / +10% accuracy / -30% tokens / just below | not adopted / eligible / eligible / not adopted | test_adoption |
| Safe output | output aliases input; existing output | error without overwrite | test_output |
| Fresh-process CLI | validate checked-in measured results | exit 0; malformed matrix exit nonzero | test_cli |

## Controls fixed before measurement

- Answer model: `claude-sonnet-4-6`, fresh Claude Code process/session per question; no resume.
- Independent API judge: `claude-haiku-4-5-20251001`; frozen ground truth, no lookup tools.
- Identical user and system prompts across variants; available tools are the only treatment.
- A: Read/Grep/Glob only. B: same plus local graphify query/path/explain MCP adapter.
  C: same plus session-only context7 MCP. No web search/fetch or shell tool for answers.
- Local graphify `--code-only --no-cluster`: no semantic LLM, no upload, no PDFs/DWG.
  This indexes code, not Markdown prose: explicitly a constrained local-only test, not a claim about semantic graphify.
- graphifyy `0.9.96` (PyPI latest at start), context7 MCP `4.4.4` (npm latest at start), Claude Code `2.1.301`.
- Clone contains only frozen pilot main, not questions/answers/evidence. Graph output exists only for B.
- Context7 receives only public library/API questions, never repository prose, drawings or source snippets.
- Interleave variants by question, rotate A/B/C order. Serial sessions avoid machine contention.
- Total tokens include input, cache-read input, cache-creation input, output. Report cache components separately.
- Files read means explicit Read tool targets; Grep/Glob search scopes and MCP calls recorded separately.
  This does not pretend that a search scope is an exhaustive list of internally scanned files.
- Accuracy is fraction fully correct (partly reported separately, not silently counted correct).
  Adoption eligibility: relative accuracy improvement >=10% OR median-token reduction >=30%.
  Equality at the requested threshold qualifies. Eligibility is not authorization to adopt.
- Graph build/setup cost is separate from per-question wall times; no amortization hidden in medians.
- Failed transport, quota or malformed results are not measured answers. Preserve evidence; do not fill fabricated rows.
- No worker/global config edits or global installs. `--setting-sources ''`, `--strict-mcp-config`,
  `--no-session-persistence`, `--disable-slash-commands`, session settings disabling hooks/auto-memory.

## Preflight repair

`CLAUDE_CODE_SIMPLE=1` suppressed existing OAuth and returned `Not logged in` with zero tokens.
Removed that command-local environment variable; normal OAuth plus explicit isolated settings returned
`READY` (499 input / 5 output tokens). Neither preflight is part of the 60 measurements.
No credentials or global settings were changed.
