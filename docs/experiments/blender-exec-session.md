# Experiment: Blender session bridge (`blender_exec.py`) — latency, large output, errors, lock contention

Card `t_b4af19e2` (experiment, [blender]). Subject: `C:/Users/artsafro/hermes_kanban/scripts/blender_exec.py`
(client for the ahujasid blender-mcp add-on, port 9876). The script was read and measured, **not edited**.

## Question

Is the bridge workers use to drive the single open Blender fast, lossless and safe enough? Where does it fail,
and what should be fixed?

## Setup

- Blender 4.4.0, blender-mcp add-on on 127.0.0.1:9876, unsaved scene: 0 objects, 1 mesh, 2 materials.
- Harness: `experiments/blender-exec-session/harness.py` (sections `latency cubes output errors lock tmpdir`),
  raw numbers in `experiments/blender-exec-session/results.json`. It calls the CLI as a subprocess
  (what workers do) and, for comparison, the script's own `send()` directly (no interpreter start, no lock,
  no output cap).
- Run: `python experiments/blender-exec-session/harness.py` (≈ 3.5 min). Windows 11, Python 3.14.
- Scene before / after every section: `0 objects, 1 mesh` (all test objects are `agrexp_*` and removed).

## Results

### Latency (median of 10)

| Call | Median ms |
|---|---|
| CLI `--ping` | 124 (min 123, max 183) |
| CLI `--code "x = 1"` | 124 |
| raw `send()` ping / trivial code | 62 / 62 |
| bare `python -c "import argparse,json,socket,tempfile"` | 82 |

About half the CLI round trip is interpreter start-up; the add-on itself answers in ~60 ms (its main-thread
timer tick dominates). Fine for interactive work; 100 small calls cost ~12 s.

### 1000 cubes: one call vs 10 calls

| Method | 1 × 1000 | 10 × 100 | delete 1000 |
|---|---|---|---|
| `bpy.ops.mesh.primitive_cube_add` | 34.5 s | 30.7 s | 0.46 s |
| `bpy.data` + `bmesh.ops.create_cube` + `objects.link` | **0.41 s** | 1.94 s | 0.36 s |

Batching barely matters for `bpy.ops` (operator cost ~31–34 ms per cube grows with scene size); the data API is
**~85× faster**. Splitting into 10 calls adds ~0.15 s per call. The 34 s single call blocks Blender's UI.

### Largest print() that comes back intact

| print() size | CLI intact | CLI stdout | raw `send()` intact (time) |
|---|---|---|---|
| 1 KB, 10 KB, 19 KB | yes | full | yes (0.05 s) |
| 20 KB | **no** | 20 015 chars, `...[truncated]` | yes (0.05 s) |
| 100 KB, 1 MB | **no** | 20 015 chars | yes (0.05 / 0.2 s) |
| 5 MB | **no** | 20 015 chars | yes (0.75 s) |

The socket and the add-on carry 5 MB without loss; the loss is the CLI's own `out[:20000]` cap on the JSON
line. The cut output is **invalid JSON** and the exit code is still **0**, so a caller that parses stdout
breaks, and one that does not may silently use a partial result.

### Errors and long calls

| Case | Exit | Output | Time |
|---|---|---|---|
| `raise ValueError('boom')` | 1 | `{"status":"error","message":"Code execution error: boom"}` | 0.1 s |
| syntax error `def (` | 1 | `... invalid syntax (<string>, line 1)` | 0.1 s |
| `print('partial'); 1/0` | 1 | `... division by zero` — **the printed `partial` is lost**, no traceback/line | 0.1 s |
| `sleep(40)`, default `--timeout 300` | 0 | `woke` | 40.1 s |
| `sleep(40)`, `--timeout 10` | **2** | `"unreachable": timed out` — wrong: Blender is alive and still running the code | 10.1 s |
| `--ping` right after the timed-out call | 0 | success, but it **blocked 30 s** on the socket | 30.0 s |
| wrong port 9899 | 2 | unreachable (WinError 10061, localized message) | 2.2 s |

Blender stays responsive after errors. After a client timeout the code keeps running in Blender, the lock is
already released, and the next caller is blocked on the socket instead of getting `busy`.

### Lock contention

| Case | Result |
|---|---|
| A runs 15 s; B `--ping --wait 3` | B exit **3** `busy` after 4.1 s (2 s poll granularity) |
| A runs 15 s; C `--ping --wait 60` | C waits, succeeds after 10.2 s (A ends ~9.5 s after C starts, plus up to 2 s lock poll); lock removed after |
| Lock file content | `{"card": "manual", ...}` — `HERMES_KANBAN_TASK` is not in a terminal subprocess env, so the owner is anonymous |
| A runs 8 s; B with `TEMP/TMP/TMPDIR` pointing elsewhere, `--wait 1` | B exit **0** — **lock bypassed**; B only waited on the socket (6.6 s) |

The lock path is `tempfile.gettempdir()`, which follows `TMPDIR`/`TEMP`/`TMP`. Hermes profiles set `TMPDIR`
to per-profile scratch dirs (here it was `/tmp`, which native Python ignores, so it fell back to
`%LOCALAPPDATA%\Temp` by luck). Two workers with valid but different temp dirs get two different locks and can
interleave their scripts in one Blender session. Blender's own main-thread queue serializes single commands,
so there is no crash, but multi-call sequences of two cards can mix.

Other code-reading findings (not measured): stale-lock takeover at 30 min while `--timeout` is user-settable
above 1800 s; `send()` re-parses the whole buffer after every 64 KB chunk (quadratic, 0.75 s at 5 MB — harmless).

## Methods and verdicts

The card has no research report; the "methods" are the two fix candidates the measurements support,
prototyped as the raw `send()` path / alternate env in the harness (the script is not edited).

| Method | Baseline | Prototype | Verdict |
|---|---|---|---|
| M1. Lossless output: no 20 KB cap on the JSON line (or cap only `result.result` and keep JSON valid; `--out <file>` for big results; non-zero exit or `"truncated": true` on cut) | intact ≤ 19 KB, invalid JSON + exit 0 above | raw path intact to 5 MB, 0.75 s | **adopt** |
| M2. Fixed lock path independent of `TMPDIR` (e.g. `%LOCALAPPDATA%\Temp\agr-blender-session.lock` or next to the script) | lock bypassed with a different temp dir (exit 0 instead of 3) | same path for all callers → exit 3 as in the normal case | **adopt** |
| Use `bpy.data` instead of `bpy.ops` for bulk geometry (worker guidance, not a script change) | 34.5 s / 1000 cubes | 0.41 s | **adopt** (as a note in the Blender skill/CAPABILITIES) |
| Batch many small calls into one | 10 × 100 = 1.94 s vs 0.41 s (data API); no gain with ops | — | maybe: only matters for >50 calls |

## Proposed follow-ups (not created as issues)

1. **blender_exec.py: valid, lossless output** — remove the `out[:20000]` cut or replace it with a
   JSON-preserving cap on `result.result` + `"truncated": true` + exit 4; add `--out <path>` to write the full
   response to a file. Acceptance: harness `output` section intact at 5 MB via `--out`, stdout always valid JSON.
2. **blender_exec.py: one lock for all profiles** — compute `LOCK` from `%LOCALAPPDATA%` (or an
   `AGR_BLENDER_LOCK` env), write `HERMES_KANBAN_TASK`/`--card` and the timeout into it, refresh mtime while the
   call runs, and make `STALE_S` ≥ `--timeout`. Acceptance: harness `tmpdir` section gives exit 3.
3. **blender_exec.py: honest timeout** — on `socket.timeout` after connect, return `{"status":"timeout"}` and
   exit 5 (not `unreachable`/2), and keep the lock until Blender answers a ping (Blender is still running the
   code). Also return the captured stdout and `traceback.format_exc()` on error (needs an add-on-side wrapper:
   run user code inside `try/except` that prints the traceback, since the add-on drops stdout on error).
4. **Docs**: in the Blender skill / `docs/agents/CAPABILITIES.md` note: bulk geometry via `bpy.data`/`bmesh`,
   not `bpy.ops` (85×); keep single calls short (a call blocks Blender's UI); ~0.12 s overhead per call.
