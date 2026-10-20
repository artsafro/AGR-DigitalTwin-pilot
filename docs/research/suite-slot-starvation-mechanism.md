# Suite-slot waiting: can newer waiters repeatedly overtake an older card?

## Summary

- **Yes, the pre-queue exclusive-file + polling mechanism can starve a live waiter indefinitely in principle:** no reservation exists; a newcomer polling during a free-slot window can win the exclusive create before an older waiter’s next 15-second poll.
- The checked script SHA-256 is `390da67fe650aeae1d0bef197c3577edf5758d4473b6dff38b39b7979b6a339e`.
- Important qualification: the inspected script already has a ticket queue and oldest-live-waiter admission gate (lines 60–126, 141–165), so the simple polling-phase overtaking described above is not the normal path in this checked version.
- Existing evidence says the #351 card waited 3,300 seconds without acquiring a slot and an operator reported repeated newer-suite acquisitions; it does not include authoritative per-slot acquire/release timestamps.
- Thus starvation is mechanistically possible in the earlier unqueued algorithm, and the contemporaneous report is credible evidence of repeated overtaking, but the exact historical sequence and reported ~45-minute event are not independently proven by holder/acquisition records.
- The deterministic model below reproduces the unqueued mechanism only; it does not model or test the live script, acquire locks, or run pytest.
- No scheduling policy is adopted or changed here; proposals remain subject to the user's decision.

## Findings

### 1. Admission, polling phase, stale-PID takeover, and release

**Verified by reading** `C:/Users/artsafro/hermes_kanban/scripts/suite_slot.py` (SHA-256 above; line references are from the inspected file):

- `pid_alive` uses Windows `OpenProcess`/`GetExitCodeProcess` or POSIX `kill(pid, 0)` to decide whether a recorded holder PID is live (18–35).
- `try_take` first uses `os.open(... O_CREAT | O_EXCL ...)`; an existing lock with a live PID is unavailable. If its PID is dead (or the record is unreadable), the function waits until the file mtime is at least five seconds old, removes the file, and recursively retries the exclusive create (38–57). This is stale-PID recovery, not queue fairness; there is no explicit lock-holder timestamp in the lock JSON beyond `since` formatted only as `%H:%M:%S` (56).
- The script defines a shared queue directory and a priority function (60–96). Live ticket names are sorted; tickets with dead PIDs are removed (98–115). A ticket is admitted when its position is nonzero and no greater than the number of currently absent lock files, bounded below by one (118–126).
- Each invocation creates a ticket with priority, `time_ns`, PID and card; while waiting it checks queue position and free slots, attempts each slot, reports at minute intervals, then polls again after 15 seconds (129–165). The ticket is removed in a `finally` after leaving the admission loop (161–165).
- The command runs only after a lock was acquired; its `finally` removes that lock (176–183).
- The module docstring still describes 15-second polling (10–11), while the in-code comment explicitly documents a FIFO change on 2026-10-20 and says the old no-queue behavior let whoever polled first take a freed slot (141–143). The code implements ticket ordering with priorities before arrival order; it is not strict global FIFO across priority classes.

**Mechanism conclusion:** Under the older no-ticket algorithm, polling phase can repeatedly decide the winner: if a slot becomes free just after the older waiter's poll and a younger process takes it before the older process's next poll, the older process gets no reservation and this pattern may repeat without a bound. Two occupied slots also explain delay without starvation: a waiter cannot progress until either holder releases or is identified as dead. In the checked queued implementation, a still-live earlier ticket in the same priority class should be eligible before a later one when a slot is observed free; priority ordering can intentionally place a newer higher-priority waiter first. Races between checking queue state/free count and claiming lock files remain separate from the intended ticket ordering, and are not established as an actual failure here.

### 2. Deterministic discrete-event reproduction (unqueued algorithm only)

This small model freezes the older waiter's polls at times 0, 15, 30, 45; each younger waiter polls exactly at a release instant, before the older waiter's next poll. Two slots are initially held. Each younger suite holds its acquired slot for five model-time units. The model treats acquisition as an atomic exclusive-create winner and tracks occupancy; it uses no real lock files, sleeps, subprocesses, or pytest. The control has no younger arrivals and releases the initial holders at t=5.

```python
# Deterministic toy model of poll-first admission, NOT suite_slot.py.
slots = 2
active = {"H0", "H1"}
max_active = len(active)
old_waiter = "A"
old_polls = [0, 15, 30, 45]
releases = [5, 20, 35, 50]
newcomers = ["B", "C", "D", "E"]
log = []

for poll, release, newcomer in zip(old_polls, releases, newcomers):
    # One initial/younger holder releases at the specified instant.
    released = sorted(active)[0]
    active.remove(released)
    log.append((release, "release", released, len(active)))

    # Frozen polling phase: younger process claims the vacancy before A polls.
    active.add(newcomer)
    max_active = max(max_active, len(active))
    log.append((release, "admit", newcomer, len(active)))

    # A's next poll is later, after the younger holder has finished and
    # a further younger arrival takes the released vacancy (next iteration).
    # Thus every modeled admission goes to a younger waiter, never A.
    log.append((poll, "A-poll", "still blocked", len(active)))

print("overtaking admissions:", [e[2] for e in log if e[1] == "admit"])
print("A acquired:", any(e[1] == "admit" and e[2] == old_waiter for e in log))
print("maximum active:", max_active, "capacity:", slots)

# No-contention control: holders finish, then A polls an available slot.
control_active = {"H0", "H1"}
control_active.remove("H0")  # release at t=5
control_active.remove("H1")  # release at t=6
control_active.add("A")      # A's poll at t=15
print("control A admitted:", "A" in control_active, "active:", len(control_active))
```

Expected deterministic output: overtaking admissions `['B', 'C', 'D', 'E']`; `A acquired: False`; maximum active `2 capacity: 2`; control `A admitted: True active: 1`. This is a constructive illustration of the old algorithm's lack of a fairness bound, not historical evidence. The script is deliberately not run: this is an embedded explanatory model, and no tests or suite runner are in scope.

### 3. What the historical evidence establishes—and does not

**Sources:** [pilot issue #361](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/361), [pilot PR #362](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/362) and its review comment; read-only Kanban history for card `t_8e0361be`.

- Issue #361 states that #347 reported a roughly 45-minute wait while newer suites acquired slots. It also records the unrelated test timing context; it does not attach a slot event log.
- PR #362's review comment reports the #351 worker's exact wait as **3,300 s**, “did not acquire a slot even once,” and says newer suites repeatedly took released slots. Another comment reports the process exited without running the full suite and that no matching native test process remained. These are contemporaneous operator/worker statements in the PR, not underlying slot telemetry.
- Kanban card `t_8e0361be` comments at 11:13 (worker) and 11:29 (worker handoff) record “>40 min” / **3,300 s**, both slots changing to `t_44756fec`/`t_daf29898`, and later identify a coordination reply from `t_44756fec` that its suite finished exit 0. Kanban event timestamps available for that card include lifecycle/heartbeat times, but do not record suite-slot lock acquisitions/releases or which PID held each lock at each instant. The card later notes a scheduler change to queue tickets; that does not itself prove the prior slot history.
- **Absent:** authoritative timestamps for #351's initial request/ticket creation, each poll, each slot's holder PID and acquisition time, each holder's release/stale takeover, #351's cancellation, and the alleged younger admissions. Without these, one cannot distinguish repeated overtaking from two long-running holders, stale lock-file delay, a waiter not actually alive/queued, or clock/logging gaps with certainty.
- The source script's `since` records only a wall-clock time-of-day (`HH:MM:SS`), and the printed “got”/waiting messages are process output rather than a durable centralized audit trail. The reviewed sources do not provide the needed per-transition evidence.

## How it applies to this repository

- `C:/Users/artsafro/hermes_kanban/scripts/suite_slot.py` is external to this repository; this report records it read-only and proposes no edits.
- The pilot's #347/#351 run accounts and #361/#362 discussion are the relevant operational records. The #351 worker reported waiting 3,300 seconds and no acquired run; its final report says full suite on the new head did not start.
- This repository's reports should distinguish “waited for capacity” from “starved by overtaking” unless holder/acquisition/release events support the latter. A future evidence capture could record monotonic timestamp, wall-clock timestamp, card/ticket, PID, slot index, admission/release/stale-removal event and reason; collection details and retention are policy choices for the owner.

## Proposed next tasks

1. **Capture slot lifecycle evidence for a bounded observation — value S / effort S.** If the owner wants stronger diagnosis, separately propose a read-only, privacy-minimal event record for enqueue, admission, holder release, stale-PID recovery and waiter exit, with monotonic and wall-clock times. Define retention and access with the user before any implementation; this is only a proposal, not permission to modify the runner.
2. **Review and decide fairness semantics for suite admission — value M / effort S.** Present candidate policies and their trade-offs to the user before changing scheduling. If a FIFO policy is selected, its proposed contract must include these input -> expected output pairs: `A waiting before B at a release -> A admitted first in a hypothetical FIFO design`; `one dead waiter before live B -> B can progress`; `two live holders -> third never admitted`. This report does not adopt FIFO or choose a new global suite budget.

## Open questions for the user

- Should suite scheduling remain priority-ordered, become strict arrival FIFO, or use another explicit policy? The current code's priority classes can intentionally allow a newer higher-priority ticket to precede an older lower-priority ticket.
- Is adding durable, privacy-minimal lifecycle telemetry acceptable, and what retention/access limits should apply?
- To establish the reported ~45-minute event, can the operator supply: (1) #351 enqueue/start and end/cancel timestamps; (2) per-slot lock create and release timestamps with holder PID/card; (3) PID liveness/stale takeover observations; (4) timestamps/card IDs for younger suite admissions; and (5) log clock/timezone and machine identity? A wait duration alone cannot establish starvation.

## Sources

- **Inspected directly:** `C:/Users/artsafro/hermes_kanban/scripts/suite_slot.py`, SHA-256 `390da67fe650aeae1d0bef197c3577edf5758d4473b6dff38b39b7979b6a339e`; cited line ranges refer to this exact inspected file.
- [Issue #361](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/361) — claim and original context, verified with `gh issue view`.
- [PR #362](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/362) — comments and review report, verified with `gh pr view`.
- **Read-only Kanban card history:** `t_8e0361be` — reported 3,300-second wait / newer admissions and later coordination note. These are authored reports, not independent lock telemetry.
