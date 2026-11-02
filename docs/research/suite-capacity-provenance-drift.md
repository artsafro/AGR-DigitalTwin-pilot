# Suite-slot capacity: why worker instructions, coordination rules and receipts say 2, 4 and 3

## Summary

The effective full-suite capacity on this PC is set by exactly one runtime chain in
`C:/Users/artsafro/hermes_kanban/scripts/suite_slot.py`: an explicit `--slots N` wins, else the
`AGR_SUITE_SLOTS` environment variable (when a non-zero integer), else `configured_slots()` which reads
`hermes_kanban/suite_slots.json` and falls back to `4` when that file is missing or invalid. The file
currently holds `{"slots": 3}`, so **the effective limit today is 3**, and no CLI/env override is set in
normal use. The numbers 2, 4 and 3 reach workers through three *instruction-only* locations that have
drifted apart and none of which is the runtime source: every worker `SOUL.md` says **"at most 2 full
suites … (rule 43)"** (stale: rule 43 was raised from 2 to 4 on 2026-10-20 but the SOUL copies were never
updated); `COORDINATION_RULES.md` itself is internally split — rule 43 says **4**, rule 58 says **3**; and
`suite_slot.py`'s own docstring/usage still say **2** (docstring) and **4** (fallback) alongside the config
**3**. The pilot repository `artsafro/AGR-DigitalTwin-pilot` hardcodes none of these numbers (its only
`suite_slot.py` mention is the perf lane, `docs/agents/WORKFLOW.md:432-434`), so the drift lives entirely
in the external harness and the deployed profiles it feeds. Receipt analysis of the frozen
`kpi/suite_slot_runs.jsonl` snapshot (88 lines, 2026-10-21: 64 completed rows) shows queue wait
(`waited_s`, median 22 s) is recorded separately from run time (`ran_s`, median 1506 s), repeated card
attempts keep both exit rows (failure not erased), and the observed peak overlap over `[started, ended)`
intervals is a **lower bound of 3** — while `holders_at_start` is lock-file residue that can exceed the
configured count (observed 3 and 4 under a `slots=2` config) and must not be read as a concurrency peak.

## Findings

### F1 — The one runtime chain that decides the effective limit

**Verified by reading** `suite_slot.py` (SHA-256 `7c6a46219138f1073ac7a46ef99a8dcb24ad734b780a1825e51fa0cdb7a34b24`).

The `--slots` argument default is evaluated once per invocation (line 153):

```python
ap.add_argument("--slots", type=int, default=int(os.environ.get("AGR_SUITE_SLOTS", "0")) or configured_slots())
```

`configured_slots()` (lines 133-138):

```python
def configured_slots() -> int:
    """Slot count from hermes_kanban/suite_slots.json ({"slots": N}); 4 when absent (2026-10-20 A/B of 3 vs 4)."""
    try:
        return max(1, int(json.load(open(SLOTS_FILE, encoding="utf-8"))["slots"]))
    except (OSError, ValueError, KeyError, TypeError):
        return 4
```

Traced precedence (from source, not guessed):

1. **CLI `--slots N`** — highest precedence (argparse ignores the default when the flag is passed).
2. **`AGR_SUITE_SLOTS` env var** — wins when set to a non-zero integer; `int("0")` or an empty/unset var
   is falsy and falls through to `configured_slots()`. Observed edge from inspection only: a non-integer
   value makes `int(...)` raise `ValueError`, which is *not* caught here, so the invocation crashes before
   doing anything (no fallback applies).
3. **`hermes_kanban/suite_slots.json`** `{"slots": N}` — the current file is `{"slots": 3, "set_at":
   "2026-10-21 01:58", "why": "32 logical CPUs, 15 GB free; cards hit 90m runtime cap waiting for a slot
   (t_da42bf1b waited 3136 s)"}` (SHA-256 `48eb938dc9ded7763104cdd31fb4aa5baaff1c2501d6d1a1bf0caa4dabf6d04a`).
4. **Hard-coded fallback `4`** — when the JSON is missing or unparsable (the four exception types above).

The lock/ticket namespace (lines 15, 60, 160, 167, 200): slot locks are
`%LOCALAPPDATA%/Temp/agr-suite-slot-<i>.lock` for `i in range(a.slots)`; the FIFO queue is
`%LOCALAPPDATA%/Temp/agr-suite-queue` with tickets named `<priority>-<time_ns>-<pid>.ticket`
(priority 0 merges/orchestrator, 1 reviews, 2 cards, 3 experiments/autoresearch, read from the `agr-pilot`
kanban DB); the run receipt records `holders_at_start` as the count of lock files over a fixed
`range(8)` (line 200), not `range(a.slots)`.

### F2 — Provenance matrix: location → stated count → runtime effect vs instruction only

| # | Location | Stated count | Runtime effect vs instruction only | Evidence |
|---|---|---|---|---|
| 1 | `profiles/*/SOUL.md` (10 files: dt-worker, dt-worker-codex, dt-worker-cursor, dt-worker-agy, dt-worker-pi, dt-worker-deepseek, dt-reviewer, dt-experimenter, dt-experimenter-codex, dt-experimenter-cursor), lines 36-87 | **2** ("at most 2 full suites … (rule 43)") | Instruction only — injected into each worker's system prompt; not consulted by `suite_slot.py` | `grep -n "at most 2 full suites"` matches all 10; deployed `~/.hermes/profiles/*/SOUL.md` copies are byte-identical for the workers checked |
| 2 | `profiles/COORDINATION_RULES.md` rule 43, lines 340-344 | **4** ("At most 4 FULL test suites"; "4 slots") | Instruction only — prose that points at `suite_slot.py` | read lines 340-347 |
| 3 | `profiles/COORDINATION_RULES.md` rule 58, line 467 | **3** ("full suites still go through 3 suite slots") | Instruction only | read line 467 |
| 4 | `scripts/suite_slot.py` docstring, lines 3-7 | **2** then **4** ("at most 2 full suites at a time"; "2026-10-20: 4 slots") | Documentation only | read lines 1-12 |
| 5 | `scripts/suite_slot.py` usage line 9 | **2** (`[--slots 2]`) | Documentation only (example text) | read line 9 |
| 6 | `scripts/suite_slot.py` `configured_slots()` fallback, lines 137-138 | **4** | **Runtime** — fallback when `suite_slots.json` missing/invalid | read lines 133-138 |
| 7 | `hermes_kanban/suite_slots.json` | **3** | **Runtime** — current effective config | file content + SHA-256 |
| 8 | `scripts/suite_slot.py` `--slots` default, line 153 | env-or-config | **Runtime** — the precedence chain of F1 | read line 153 |

Only rows 6-8 have a runtime effect; rows 1-5 are prose that has drifted away from them.

### F3 — The "2" is a stale SOUL.md instruction, and its source is retrievable

The "injected 2-slot instruction" in a worker's context is the `SOUL.md` preamble that the harness
injects; its generating source is **retrievable and located**: all ten
`C:/Users/artsafro/hermes_kanban/profiles/*/SOUL.md` carry the same line

> `Full suite: run it … ONLY through …/suite_slot.py --card <card id> -- … — at most 2 full suites on this PC at once (rule 43); parallel suites crash Windows child processes (0xC0000142) …`

at lines 36-87 depending on the profile. It cites "rule 43", but the live rule 43 (COORDINATION_RULES
line 340) says **4** — the SOUL copies were not refreshed when rule 43 was edited on 2026-10-20. Deployed
copies under `~/.hermes/profiles/<profile>/SOUL.md` match the tracked source (checked for all six worker
profiles), so this is a source-vs-source drift, not a deploy failure. The experimenter/reviewer SOUL files
state the same "2". Because the source is identified, no "supplied-card-context" caveat is needed; the
instruction is simply stale relative to rule 43.

### F4 — COORDINATION_RULES contradicts itself (4 vs 3)

The same file `profiles/COORDINATION_RULES.md` (SHA-256
`923bd63e057433ca5ecdd2724eea14db451ec164fcfde8ab112732ba47e6bba0`) asserts two different capacities:

- **rule 43, line 340:** "At most 4 FULL test suites run on this PC at once: always through
  `suite_slot.py`"; **line 344:** "(updated 2026-10-20, user "добавь места") 4 slots".
- **rule 58, line 467:** "Board slots `max_active` 8 -> 10 …; full suites still go through 3 suite slots."

Rule 58 was written later (2026-10-21) and reflects the then-current `suite_slots.json=3`, while rule 43
was left at 4 — so the coordination rules themselves now contain both 4 and 3.

### F5 — Receipt analysis (2026-10-21 only), from the frozen snapshot

Snapshot recorded **before** analysis, 2026-10-21 20:14:09 +0200: `kpi/suite_slot_runs.jsonl` =
**88 lines**, SHA-256 `9af93ad7ed57dd767686cad19d2182e3d0c4a0cb7d12a8261b3f5eb4d336c076`; the frozen copy
was byte-identical after copying (`cp` + re-hash). The receipt schema (per `log_run`, lines 210-212) is
`{card, prio, slots, holders_at_start, queued, started, ended, waited_s, ran_s, exit}`.

2026-10-21 subset: **64 completed rows, 55 distinct cards**.

- **Configured count per row** (`slots` field): 6 rows `slots=2`, 58 rows `slots=3`. The whole-log
  timeline reconstructs the A/B cycle: `slots=4` (10-20 14:50→16:21, 6 rows) → `slots=3` (10-20
  16:49+) → `slots=2` (10-20 20:23 → 10-21 02:06, 21 rows) → `slots=3` (10-21 02:38 → 19:03), matching
  the `set_at 2026-10-21 01:58` field of `suite_slots.json`.
- **Queue wait vs run time:** `waited_s` n=64, median 22 s, max 3150 s; `ran_s` n=64, median 1506 s,
  max 2603 s. 31 of 64 rows have `waited_s=0`. These are recorded as two separate fields — the receipt
  already distinguishes waiting from execution.
- **Exit codes:** 33× `0`, 28× `1`, 1× `2`, 1× `4`, 1× `1073807364` (= `0x40010004`). No row records
  `0xC0000142` (`3221225794`), the desktop-heap signature named in the SOUL/rule text.
- **Repeated attempts:** 8 cards appear more than once; three show `exit=1` followed by `exit=0`
  (`t_f0dd31b2`, `t_476231a8`, `t_357965e6`) — the failed row is retained, so the earlier failure is a
  separate attempt, not erased.
- **Overlap reconstruction (lower bound):** over `[started, ended)` intervals of the recorded completed
  rows, the maximum number simultaneously overlapping is **3** (whole log and 2026-10-21 alike). This is
  a **lower bound**: running-but-not-yet-logged processes and any run that never logged are absent.
- **`holders_at_start` is lock-file residue, not concurrency:** it counts lock files across a fixed
  `range(8)` (line 200) at the instant after acquiring a slot, including leftover locks from a previous
  higher-`slots` configuration. During the `slots=2` window it reported `3` in 18 rows and `4` in 2 rows —
  **above the configured 2** — while the interval-overlap peak stayed at 3. It must not be equated with
  an authoritative global peak.

### F6 — Acceptance observation pairs

| Acceptance point | Verdict | Concrete witness |
|---|---|---|
| config `slots=3` → trace selects 3 with no CLI override | Confirmed | `suite_slots.json={"slots":3}`; `--slots` default = `configured_slots()` = 3 when no flag/env (F1) |
| missing/invalid config → fallback 4, not 2 (inspection only) | Confirmed (inspection) | `configured_slots()` returns `4` on `OSError/ValueError/KeyError/TypeError` (lines 137-138); not executed |
| CLI `--slots N` → traced precedence, no guess | Confirmed | CLI > env `AGR_SUITE_SLOTS` (non-zero int) > `suite_slots.json` > `4`; env non-integer = uncaught `ValueError` (F1) |
| completed row `waited_s=0`/`ran_s=1578` → execution duration, not queue wait | Confirmed | `t_357965e6` attempt 1: `queued==started` 18:38:47, `waited_s=0`, `ran_s=1578`, `exit=1` → the 1578 s is run time |
| `exit=1` followed by `exit=0` → separate attempts, no erased failure | Confirmed | `t_357965e6` (18:38 exit 1 → 19:03 exit 0), `t_f0dd31b2`, `t_476231a8`; both rows remain |
| missing failure log → cause unresolved, never heap-crash attribution | Confirmed | receipt carries no stderr; `0x40010004` ≠ `0xC0000142` and no row equals `0xC0000142`, so heap crash is not attributable from receipts alone |

### F7 — Self-contained stdlib verification of the frozen bytes

The numbers above were produced by reading the frozen file with Python stdlib only (no scheduler import,
no lock acquisition, no sleeps). The aggregation logic is:

```python
import json, time
rows = [json.loads(l) for l in open("<frozen snapshot>", encoding="utf-8") if l.strip()]
today = [r for r in rows if time.strftime("%Y-%m-%d", time.localtime(r["started"])) == "2026-10-21"]
# queue vs run: min/median/max of waited_s and ran_s; exits: collections.Counter(r["exit"])
# overlap lower bound: sweep (started,+1)/(ended,-1) events, max running = 3
# holders_at_start by configured slots: e.g. slots=2 -> Counter({3:18, 4:2, 2:1})
```

Frozen-snapshot output (2026-10-21): 64 rows; exits `{0:33, 1:28, 2:1, 4:1, 1073807364:1}`;
`waited_s` median 22 / max 3150; `ran_s` median 1506 / max 2603; peak interval overlap 3;
`holders_at_start` `{1:6, 2:12, 3:46}`; under `slots=2` it reached 3 and 4.

## How it applies to this repository

- **The pilot repo is not a drift location.** `AGENTS.md`, `docs/agents/*` and `.agents/*` hardcode no
  suite-slot number. The only `suite_slot.py` reference in this repository is
  `docs/agents/WORKFLOW.md:432-434` ("Run the lane through the suite-slot limiter … it is not part of a
  card's full-suite receipt"), which names no count.
- The 2/4/3 drift lives **outside** the pilot repository, in `C:/Users/artsafro/hermes_kanban/` (the
  script, `suite_slots.json`, `COORDINATION_RULES.md`, the ten `profiles/*/SOUL.md`) and in the deployed
  `~/.hermes/profiles/*/SOUL.md` copies the harness injects into worker prompts. Pilot workers consume
  that injected instruction; this report is the pilot-side record of the discrepancy.
- The two parent reports this card was told to read — `docs/research/suite-slot-starvation-mechanism.md`
  (queue/overtaking mechanism; it checked script SHA `390da67f…`, an earlier version than the one
  inspected here) and `docs/research/default-suite-max-lock-exposure.md` (3ds Max selftest leaking into
  the default lane via a *different* lock, `agr-3dsmax-session.lock`) — do not cover this 2/4/3
  provenance drift, so this report does not repeat them.

## Proposed next tasks

> Both are unadopted; neither chooses a capacity or changes any runtime config. No roadmap issue is
> advanced by either, so each carries `Archive: no roadmap link` (the `roadmap` label on
> artsafro/AGR-DigitalTwin-pilot lists only product-capability blocks — Flora/MAF/Ground/roof-equipment —
> none harness-related).

**Proposal A — Reconcile the suite-slot capacity in instruction copies (docs/procedure hygiene).**
Align the ten `SOUL.md` "at most 2 … (rule 43)" lines, `COORDINATION_RULES.md` rule 43 (4) vs rule 58
(3), and the `suite_slot.py` docstring/usage (2/4) so that every instruction-only location either states
the same number or, better, points at `suite_slots.json` instead of hardcoding a number. This removes the
misleading prose; it is not a capacity decision (the runtime precedence is already fixed in code) and the
user retains ownership of the actual number.
*Input → expected output:* input = this drift inventory; expected output = `grep -rn "full suite"` over
`profiles/` + `COORDINATION_RULES.md` yields no "2" and every location names `suite_slots.json` as the
source, so a worker following any instruction lands on the same number as `suite_slot.py`'s default.
*Value/effort:* S (10 text files + 2 rule lines + one docstring). `Archive: no roadmap link`.

**Proposal B — Add error-signature capture to the suite receipt (receipt fidelity).**
Extend `suite_slot.py` `log_run` to record a bounded stderr tail plus a return-code classification
(pytest 1/2/4/5 vs Windows NTSTATUS such as `0x40010004`/`0xC0000142`) so a non-zero exit can later be
attributed (or a heap crash excluded) without guessing.
*Input → expected output:* input = a run exiting `0x40010004` with no error text; expected output = a
receipt row whose new `err` field carries the captured tail, letting the next analysis say "cause =
<stderr>" instead of "unresolved". No change to the slot count or admission logic.
*Value/effort:* S/M (one script change + receipt schema). `Archive: no roadmap link`.

## Open questions for the user

1. Which single number should be authoritative for full-suite capacity (2, 3, or 4), and should the
   instruction-only copies stop hardcoding a number in favor of deferring to `suite_slots.json`? This is a
   scheduling-policy decision the report deliberately does not make.
2. The A/B helper `suite_slot_ab.py` auto-writes `suite_slots.json` (currently 3) from throughput; should
   its winning count be re-synced into `COORDINATION_RULES.md` rule 43 and the `SOUL.md` copies whenever it
   changes, so the prose cannot drift again?

## Sources (hashes recorded read-only)

- `C:/Users/artsafro/hermes_kanban/scripts/suite_slot.py` — SHA-256 `7c6a46219138f1073ac7a46ef99a8dcb24ad734b780a1825e51fa0cdb7a34b24`
- `C:/Users/artsafro/hermes_kanban/suite_slots.json` — SHA-256 `48eb938dc9ded7763104cdd31fb4aa5baaff1c2501d6d1a1bf0caa4dabf6d04a` (`{"slots": 3, "set_at": "2026-10-21 01:58"}`)
- `C:/Users/artsafro/hermes_kanban/profiles/COORDINATION_RULES.md` — SHA-256 `923bd63e057433ca5ecdd2724eea14db451ec164fcfde8ab112732ba47e6bba0`
- `C:/Users/artsafro/hermes_kanban/kpi/suite_slot_runs.jsonl` — 88 lines, SHA-256 `9af93ad7ed57dd767686cad19d2182e3d0c4a0cb7d12a8261b3f5eb4d336c076` (frozen 2026-10-21 20:14:09 +0200)
- `C:/Users/artsafro/hermes_kanban/profiles/*/SOUL.md` (10 files) — "at most 2 full suites … (rule 43)"; representative hashes: dt-worker / dt-worker-codex / dt-worker-deepseek `1f34f061…`; dt-reviewer `35b1c8c4…`; others recorded during inspection.
