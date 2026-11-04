# Why Plan/Readiness/Hypotheses cards run to the runtime cap and then finish in < 2 min on retry

Research card t_a963b7cc (board `agr-pilot`, no GitHub issue). Read-only investigation, 2026-11-04.
All times are local (CET, UTC+1). Every finding below was **verified by me** (SQL queries on the
databases read with `?mode=ro`, log greps, code reads). No web sources were used: the question is about
this machine's board, and no outside claim is made.

## Summary

- All 7 timed-out runs (t_65acf66b x3, t_eec72caf x2, t_a6b04776 x2) ran on model `gpt-6.1-sol`
  (provider `openai-codex`). Their session in the profile `state.db` has **0 API calls, 0 tokens, 0 tool
  calls**. The only stored message is the kill notice `An automated delivery was interrupted ...`,
  written at the moment of the kill.
- Classification for all 7 runs: **provider stall**. The first model turn never completed. Whether the
  HTTP request was even sent is unmeasured, because the worker child wrote nothing to any log.
  None of the runs was a tool hang, finished-but-no-transition, or a real overrun.
- This is not specific to these cards. Since the gateway restart on 2026-11-03 12:11, **23 of 23**
  `gpt-6.1-sol` kanban runs on this board made 0 API calls: 9 timed_out, 14 reclaimed. Before that, 34 of
  35 runs made 4-28 API calls. The latest cases are today: t_6a275c07 was killed twice at 7200 s
  (08:11, 10:12), and t_cc45680d was reclaimed (12:58).
- The provider itself was reachable. On the same night, `gpt-6.1-sol` **one-shot** (non-kanban) sessions
  on dt-reviewer at 23:40 and 00:02 made their API call and closed normally. So the stall is specific to
  the **kanban managed-worker path with openai-codex**.
- Nothing ends the stall early. The worker pid stays alive, and the dispatcher extends the claim on `pid_alive`
  with no heartbeat required. Stale reclaim needs 4 h. That leaves `max_runtime_seconds` as the only bound.
- "Finishes in < 2 min on retry" is not the same work getting faster. The successful retries ran on
  **Claude** after the user rerouted them at 00:06 ("Codex-driven runs hang under the board"):
  t_eec72caf took 48 s with 6 API calls and t_65acf66b took 119 s with 14. t_a6b04776 was never rerouted
  and is still `blocked`.
- t_65acf66b and t_eec72caf have the same start and kill times: the cause is shared, and the timing is
  mechanical (see Finding 4).

## Findings

### 1. Per-run table

Sources: `task_runs` and `task_events` in `C:/Users/artsafro/.hermes/kanban/boards/agr-pilot/kanban.db`.
The session id comes from the `owner_admitted` event of each run; it also matches the
`Session: local-...` lines in `boards/agr-pilot/logs/<id>.log`. Each session row and its messages come from
`C:/Users/artsafro/.hermes/profiles/<profile>/state.db` (tables `sessions`, `messages`,
`session_model_usage`). Sessions are stored there; there are no per-session transcript files.

| run | card | profile / model | claimed -> killed | elapsed / limit | msgs | API calls | tool calls | last tool call | gap to kill | waiting on | class |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2954 | t_65acf66b Plan | dt-worker-codex / gpt-6.1-sol | 11-03 12:12:58 -> 12:53:21 | 2423 / 2400 | 1 | 0 | 0 | none | n/a (whole run) | model provider, first turn | provider stall |
| 2958 | t_65acf66b Plan | dt-worker-codex / gpt-6.1-sol | 11-03 13:07:44 -> 13:48:43 | 2458 / 2400 | 1 | 0 | 0 | none | n/a | model provider, first turn | provider stall |
| 2963 | t_eec72caf Readiness | dt-reviewer / gpt-6.1-sol | 11-03 15:22:03 -> 16:03:01 | 2457 / 2400 | 1 | 0 | 0 | none | n/a | model provider, first turn | provider stall |
| 2968 | t_eec72caf Readiness | dt-reviewer / gpt-6.1-sol | 11-03 23:17:18 -> 23:57:28 | 2409 / 2400 | 1 | 0 | 0 | none | n/a | model provider, first turn | provider stall |
| 2969 | t_65acf66b Plan | dt-worker-codex / gpt-6.1-sol | 11-03 23:17:18 -> 23:57:28 | 2409 / 2400 | 1 | 0 | 0 | none | n/a | model provider, first turn | provider stall |
| 3007 | t_a6b04776 Hypotheses | dt-hypothesizer / gpt-6.1-sol | 11-04 03:02:56 -> 03:48:12 | 2715 / 2700 | 1 | 0 | 0 | none | n/a | model provider, first turn | provider stall |
| 3014 | t_a6b04776 Hypotheses | dt-hypothesizer / gpt-6.1-sol | 11-04 03:58:27 -> 04:43:35 | 2708 / 2700 | 1 | 0 | 0 | none | n/a | model provider, first turn | provider stall |
| 2976 (retry, ok) | t_eec72caf | dt-reviewer / claude-opus-5-5 | 11-03 23:46:42 -> 23:47:30 | 48 / 2400 | 14 | 6 | 7 | `kanban_complete` at t+48 s | 0 s | - | completed |
| 2977 (retry, ok) | t_65acf66b | dt-worker / claude-opus-5-5 | 11-03 23:46:42 -> 23:48:41 | 119 / 2400 | 29 | 14 | 14 | `kanban_complete` at t+119 s | 0 s | - | completed |

Common features of the 7 timed-out runs:
- `sessions.message_count = 1`, `api_call_count = 0`, `input_tokens = output_tokens = 0`. There is no
  `session_model_usage` row, and `end_reason = ws_orphan_reap`.
- The single message is an `assistant` row stored at t+2409 to t+2716 s, the second of the kill. Its text
  is `An automated delivery was interrupted and was not run again...` (the template in
  `hermes-agent/agent/turn_failure_copy.py:67`). Not even the user prompt was stored. In the healthy Claude
  retries the user message is stored at t+10 s and the first assistant message at t+15 s.
- The run has no `heartbeat` event at all. Its events are `claimed`, `spawned`, `owner_admitted`,
  `worker_bound`, two `claim_extended {reason: pid_alive}` (at about +15 min and +30 min), and then
  `worker_lost {EOFError}` + `timed_out` + `gave_up` in the same second.
- The worker pids have **no line at all** in `profiles/dt-worker-codex/logs/managed-worker.log` or
  `profiles/dt-reviewer/logs/managed-worker.log`. The profile `agent.log` only shows `ws accepted` and
  `Vision auto-detect: using main provider openai-codex (gpt-6.1-sol)` at the start, and `ws closed ...` +
  `Managed worker lost: EOFError` at the kill (for example `profiles/dt-hypothesizer/logs/agent.log`,
  2026-11-04 03:02:58 / 03:48:12).

### 2. It is the openai-codex kanban path, not the cards

I joined every run on this board since 2026-11-01 with its session's model:

| model | runs before 11-03 12:11 | API calls > 0 | runs after 11-03 12:12 | API calls > 0 |
|---|---|---|---|---|
| gpt-6.1-sol (dt-reviewer, dt-worker-codex, dt-hypothesizer) | 35 | 34 | 23 (9 timed_out, 14 reclaimed; dt-reviewer 13, dt-worker-codex 8, dt-hypothesizer 2) | **0** |
| Claude models (all runs since 11-01) | - | - | - | none of them has 0 API calls |

- Outside kanban, the provider works. In `profiles/dt-reviewer/state.db`, the `gpt-6.1-sol` sessions with
  `source = oneshot` started 2026-11-03 23:40:41 and 2026-11-04 00:02:45 each have `api_call_count = 1` and
  `end_reason = cli_close`. That is between the two failing nights. In
  `C:/Users/artsafro/.hermes/auth.json` the openai-codex credential pool entry has `last_status = ok` and no
  error fields set; the access token is valid until 2026-11-05.
- Earlier repair comments blamed the unfinished `hermes update` of 12:11. That fits when the problem started.
  But it does not explain the runs after the user finished the update and restarted the gateway at 23:17
  (runs 2968 and 2969), or the runs on 11-04.
- Root cause inside Hermes: **unmeasured**. The worker child logs nothing before the kill, so these data
  cannot show whether it blocked before sending the request (credential or worker bootstrap) or while
  waiting for a response stream that never ends. I read `hermes-agent` at HEAD `b200f5bc60`
  (2026-11-03 20:49 CET), which is later than the 12:11 update, so a line-level root cause would need
  instrumentation, not more reading.

### 3. Why a stalled run lasts until the cap (dispatcher code)

- `hermes_cli/kanban_db.py:280`: `DEFAULT_CLAIM_TTL_SECONDS = 15 * 60`. In
  `hermes_cli/kanban_db.py:2445-2464` (`_extend_live_stale_claim`), an expired claim whose host-local worker
  pid is alive is **extended** (`claim_extended`, `reason: pid_alive`). Liveness alone counts; no heartbeat
  and no model progress are required. That matches the two `claim_extended` events per run.
- `hermes_cli/kanban_db_dispatch.py:746-787`: stale reclaim only fires after `stale_timeout_seconds`, which
  is `dispatch_stale_timeout_seconds` (default 4 h), and only when there is no heartbeat.
- `hermes_cli/kanban_db_dispatch.py:643-701` (`enforce_max_runtime`): this is the only path that ended
  these runs. On a dispatcher tick where `elapsed >= limit`, it sends SIGTERM (then SIGKILL after a 5 s
  grace) and records `error = f"elapsed {int(elapsed)}s > limit {limit}s"` (line 701). How far a run goes
  past the limit (9-58 s) depends on when the next tick comes.
- `gateway/session_managed_worker.py:713-716`: `Managed worker lost: EOFError` is logged when the
  child's pipe closes, which happens **because of** that SIGTERM. `worker_lost` and `timed_out` share
  the same second. It is a consequence of the kill, not the cause.

So for this board a provider stall on the first turn costs the full `max_runtime_seconds` (2400 s, 2700 s,
and 7200 s for t_6a275c07).

### 4. t_65acf66b and t_eec72caf: same start 1793744238, same kill 1793746648

- **Same start: one dispatcher tick.** The user's UNBLOCK comments came at 23:16:53 and 23:17:09
  (`unblocked` events 71444 and 71450). The next tick, 1793744238 (23:17:18), claimed five cards at once:
  runs 2968, 2969 and the reviewer runs 2970-2972.
- **Same kill: same limit and same tick.** Both cards have `max_runtime_seconds = 2400`, so
  `enforce_max_runtime` found both past the limit on the same tick, 1793746648 (elapsed 2409 s).
- **Cause: shared, not a coincidence, and not an interaction.** The two runs were in different profiles
  (dt-reviewer and dt-worker-codex) with separate `state.db` files. Both stalled for the same reason: the
  openai-codex kanban first turn never completed. Runs 2970-2972 from the same tick also made 0 API calls;
  they were reclaimed after about 927 s instead.

### 5. Side finding (not one of the 7 runs)

`profiles/dt-reviewer/logs/errors.log` shows `sequential tool kanban_complete timed out after 420.0s` three
times on 2026-11-04 (03:17:55, 04:17:29, 04:22:53; sessions `local-a2a219...`, `local-bf50fc...`,
`local-c1acdb...`). That is a real "finished but no transition" risk on other cards. It is not the cause of
the runs in this card.

## How it applies to this repository

- The pilot repo has no code on this path. The board, dispatcher and profiles live outside it:
  `C:/Users/artsafro/.hermes/hermes-agent/` (dispatcher),
  `C:/Users/artsafro/.hermes/profiles/{dt-hypothesizer,dt-worker-codex}/config.yaml` (lines 75 and 108:
  `default: "gpt-6.1-sol"`, `provider: "openai-codex"`; dt-reviewer is now on `claude-opus-5-5` /
  `anthropic`), and `C:/Users/artsafro/hermes_kanban/` (refill, COORDINATION_RULES). Per the card, none of
  them were changed.
- The effect on this repo is lost throughput. Coordination cards that feed `self_queue.json` and
  `kpi/readiness/*.json` (Plan, Readiness, Hypotheses) sit `running` for 40-45 min (2 h for implementation
  cards on dt-worker-codex) and then give up. Every board card routed to dt-worker-codex or dt-hypothesizer
  still has this risk today.
- `docs/research/harness2-vs-board.md` is the closest earlier research on board behaviour.

## Proposed next tasks

Both are proposals only. Each one touches the Hermes dispatcher, profiles or ops tooling, so **it is the
user's decision** whether and where to do it.

### A. Watchdog: zero-API-call kanban run -> end it early and name the provider (M)

Scope: in the dispatcher tick (next to `enforce_max_runtime`, `hermes_cli/kanban_db_dispatch.py:643`),
or in the managed worker, end a run whose session has `api_call_count = 0` and no heartbeat
`N = 300 s` after `worker_bound`. The run should end with a distinct outcome (e.g. `provider_stall`), and its
event payload should name the profile, provider and model. A regression test would replay the run 2969
event sequence.
- Input: a run with `worker_bound` at T, no heartbeat, session `api_call_count = 0` at T+300 s ->
  expected: the run ends at about T+300 s with `outcome = provider_stall {provider: openai-codex,
  model: gpt-6.1-sol}`, and the card goes to `ready` or `blocked` with that reason (not at T+2400 s with
  `elapsed 2409s > limit 2400s`).
- Input: a healthy Claude run (2977: first API call at t+15 s) -> expected: no change.
Value: high (it saves 35-115 min per stalled run). Effort: M. `Archive: no roadmap link` (none of the open
roadmap issues #149, #298, #349, #352, #371, #425, #426, #753, #790, #792 covers board infrastructure).

### B. Read-only board probe: zero-API-call runs per profile/model (S)

Scope: a read-only script (in `hermes_kanban/`, not in this repo) that joins `task_runs` x `owner_admitted`
x `<profile>/state.db.sessions`, as done for this report. For each profile and model it lists the runs
that are past 300 s with `api_call_count = 0`, plus the first time this happened. The refill or the user can
run it before routing cards to a lane.
- Input: the current `agr-pilot/kanban.db` + profile `state.db` files -> expected: `dt-worker-codex
  gpt-6.1-sol: 0/8 runs made API calls since 2026-11-03 12:12`, `dt-hypothesizer gpt-6.1-sol: 0/2`,
  `dt-reviewer gpt-6.1-sol: 0/13`, Claude profiles: no flag.
- Input: a board with only healthy runs -> expected: an empty report and exit 0.
Value: medium (the next stalled lane shows up within one card instead of after a night). Effort: S.
`Archive: no roadmap link`.

## Open questions for the user

1. dt-hypothesizer and dt-worker-codex still use `openai-codex / gpt-6.1-sol`, and every kanban run on them
   since 2026-11-03 12:12 has stalled. That includes t_6a275c07, killed twice at 7200 s today. Should they
   move to Claude (as dt-reviewer was at 00:06), or should routing to them pause until Hermes is fixed?
2. Should the stall be reported upstream to Hermes? The evidence: a kanban managed worker with openai-codex
   makes 0 API calls, while one-shot sessions with the same credentials work. Rows and session ids are in
   the table above.
3. t_a6b04776 (Hypotheses 2026-11-04 03:02) is `blocked`. Should it be retried on a Claude profile or archived
   in favour of the next Hypotheses card?

## Sources (all local, read by me)

1. `C:/Users/artsafro/.hermes/kanban/boards/agr-pilot/kanban.db`: `task_runs`, `task_events`, `task_comments`.
2. `C:/Users/artsafro/.hermes/kanban/boards/agr-pilot/logs/{t_65acf66b,t_eec72caf,t_a6b04776}.log`.
3. `C:/Users/artsafro/.hermes/profiles/{dt-worker-codex,dt-reviewer,dt-hypothesizer,dt-worker}/state.db`:
   `sessions`, `messages`, `session_model_usage`.
4. `profiles/*/logs/agent.log`, `errors.log`, `managed-worker.log`.
5. `profiles/{dt-hypothesizer,dt-worker-codex,dt-reviewer}/config.yaml` (lines 75, 108).
6. `C:/Users/artsafro/.hermes/auth.json` (status fields and token expiry only; no secrets copied).
7. `hermes-agent/hermes_cli/kanban_db_dispatch.py:643-701, 746-787`.
8. `hermes-agent/hermes_cli/kanban_db.py:280, 2445-2464`.
9. `hermes-agent/gateway/session_managed_worker.py:713-725`.
10. `hermes-agent/agent/turn_failure_copy.py:67`.
