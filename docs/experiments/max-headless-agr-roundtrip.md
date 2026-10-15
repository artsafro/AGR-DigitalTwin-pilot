# Experiment: headless 3ds Max AGR roundtrip

Date: 2026-10-15. Card: `t_69ee7ca0`. Base: `91795c0`.
Branch: `experiment/max-headless-agr-roundtrip`.
Research: [`3dsmax-scripting.md`](../research/3dsmax-scripting.md).

## Question and scope

Can this project's existing FBX tool and benchmark meshes run without an open Max,
at what cost, and what is lost through FBX/OBJ? Two methods only:

1. **Batch independent jobs in one headless process**, versus one process per job.
   Claim: amortize startup without changing the existing tool's output.
2. **Construct engine dumps through pymxs and verify FBX/OBJ transport** using native
   and offline readback. Claim: preserve geometry and benchmark semantics, cheaply
   enough to be an optional Max bridge. FBX and OBJ are variants of this one method.

This is an internal geometry experiment, **not an NPM/VPM delivery**. UV, textures,
full normal/winding equivalence, visual acceptance and manual gates remain unchecked.
No production implementation was replaced. No other DCC was run. Max 2024 was not
run: 2026 answered, and the optional version comparison would not close these gaps.

## Setup and input integrity

- Windows workstation; Max **2026.3 / 28.3.0.30732**, bundled Python **3.11.12**.
  Offline project environment: `uv`, Python 3.14.7, repository-pinned dependencies.
- All native sessions: `python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max`.
  Serialized wrapper lock, explicit `--card t_69ee7ca0`, no `--scene`, initially zero
  objects and empty document name. Geometry jobs explicitly set metres, scale 1.
- Scratch root (called `S` below):
  `C:/Users/artsafro/.hermes/profiles/dt-experimenter-codex/cache/scratch/agr-exp-t_69ee7ca0/`.
  Exports/readbacks: `S/agr-3dsmax-t_69ee7ca0/`. The runner itself additionally writes
  its prescribed logs under `%LOCALAPPDATA%/Temp/agr-3dsmax-t_69ee7ca0/`.
- `prepare.py` first copies `object.json`, `spec.json`, `etalon.json`, `tolerances.json`
  and etalon FBX to S; **all subsequent reference use is on those copies**. Original
  FBX files were found read-only in `C:/Users/artsafro/AGR-DigitalTwin/data/benchmark/`;
  pilot `data/` was absent. Neither original repository nor any data file was written.
- Copied FBX hashes match the tracked manifests:
  B01 `a109aa9a9f25c72e8d4869ee43b0b33aee009f5c248caf62388c4dcb0c7816d9`;
  B02 `611dc7ec5fcb19f20b52656563519abf6e604b4cea81013c76daa5df717239b3`.
- These are **synthetic project benchmark buildings**, not a customer model.
  `etalon.json` is an asset manifest, not mesh coordinates: mesh generation uses
  the existing `from_spec.build(Spec, BuildInputs.from_object(object.json))`.
- Cleanup removes only job-owned nodes. Batching resets only its private initially
  empty scene after saving each new output; it never connects to a live artist scene.

## Measurements

Native process times are wrapper seconds (0.1 s resolution), excluding lock wait;
all successful calls acquired the lock without a busy result. Internal operation
clocks use `time.perf_counter`. Medians use three runs unless labelled single.
File reads are warm-cache measurements, not storage throughput. No confidence
interval or isolated-host performance guarantee is claimed.

### Method 1 — same input, same existing tool, different process granularity

Both arms run **unchanged** `tools/max_profile_roundtrip.py`, on the same copied B01
FBX, with fresh output directories, including `.max` save and FBX re-export.
`existing_job.py` supplies the documented `config` value via `maxOps.mxsCmdLineArgs`;
`batch_existing.py` repeats that identical operation three times per session.
The external wrapper has no argument passthrough, so this tiny launcher is needed.

| Operation | Baseline / raw runs (s) | Prototype / raw runs (s) | Result |
|---|---:|---:|---|
| Empty ping, 3 fresh sessions | 40.9 / 39.2 / 44.9; **median 40.9** | — | Max responds; installed startup warning |
| One B01 tool job per process | 39.8 / 41.5 / 46.1; **median 41.5/job** | — | 3/3 completed |
| Three identical B01 jobs per process | — | 72.7 / 94.1 / 56.6; **median 72.7/batch = 24.233/job** | 9/9 completed |
| Fresh-process readback vs original native etalon | 88 vertices / 150 triangles; 9/9 checker | 88 / 150; 9/9 checker | All 12 outputs; vertex and sampled surface deviation **0 mm**, bbox **0 mm** |
| Final verifier: all 12 above plus four first-repetition mesh exports | — | **53.8 s**, one session (single) | 16 files read, zero nodes left |

Measured per-job speedup: **1.713×**. Equivalently, three times the isolated median
is 124.5 s versus the measured 72.7 s batch median; the former is arithmetic, not a
separately measured three-process wall time. Large batch spread is retained, not
hidden: private-scene resets and host load materially affect total cost.

The existing tool runs headlessly with config, accepts string `Mode='create'` on
this install, preserves IDs `[1,6,11,21]`, and produces FBX 2014 exports. Directly
passing its filename to the wrapper **without config fails**, as it should:
`ValueError: Absolute config path required`. It is not a standalone wrapper CLI.
It still does not verify its own exported output; our separate verifier does that.

**Verdict: adopt** batching for opt-in offline jobs, not a daemon/live-scene service.

### Method 2 — unchanged engine baseline vs minimal pymxs transport prototype

The baseline is the project's current Python engine on copied B01/B02 specs. The
prototype consumes exactly those dumps: meshes with explicit 1-based triangle
indices and face IDs, plus LEVEL helpers. It intentionally has no material objects
or UV setup, so this is a feasibility test of the documented low-level construction,
not an implementation of a delivery profile. An entire session did two etalon
imports/dumps and 30 repeated operations (**32 timed operations**) in **54.6 s**
(single session; no median is claimed for that full session).

| Operation | B01 median s | B02 median s | Result / sample count |
|---|---:|---:|---|
| Current engine build | 0.016635 | 0.024064 | 156v/282t; 263v/472t; 3 runs each; checker **9/9** each |
| Native etalon import + dump | 0.333085 | 0.149842 | **Single** each, not medians; etalon 88v/150t and 252v/446t |
| Create engine mesh in Max | 0.007121 | 0.009971 | 3 each; consumes engine output, does not replace engine build |
| FBX export | 0.028264 | 0.035352 | 3 each |
| FBX import | 0.098978 | 0.088270 | 3 each |
| OBJ export | 0.029443 | 0.025156 | 3 each |
| OBJ import | 0.826603 | 0.794854 | 3 each |
| Offline FBX reader | 0.001176 | 0.001969 | median of per-file medians; 3 reads × 3 files each |
| Offline OBJ reader | 0.000591 | 0.001593 | same; excludes comparison time |

The two build timings are **not competing algorithms**: engine synthesis remains
necessary, and native mesh construction is additional cost. Import/export timings
exclude the roughly 41-second fresh-process overhead.

FBX explicitly loads importer/exporter and pins Animation=false, EmbedTextures=false,
ASCII=false, FileVersion=FBX201400, UpAxis=Z, Cameras/Lights=false, Triangulate=true,
ConvertUnit=m. Getter values confirmed the settings. Offline binary-header/node
reading independently found **7400**, Z-up, `UnitScaleFactor=100` (centimetres per
unit, i.e. a metre). No shared OBJ INI settings were changed: its installed defaults
are deliberately measured, not endorsed as a stable interchange contract.

| Output comparison (all three files agree) | B01 | B02 |
|---|---:|---:|
| FBX counts, native and offline | 156v / 282t | 263v / 472t |
| OBJ counts, native and offline | 156v / 282t | 263v / 472t |
| Max bbox after native FBX/OBJ readback (m) | [0,0,0]–[10,10,7.199999809] | [0,0,0]–[12,9,7.199999809] |
| FBX max vertex deviation vs engine, mm | 0.000378 | 0.000441 |
| FBX max bbox deviation vs engine, mm | 0.000191 | 0.000191 |
| OBJ native max vertex deviation vs engine, mm | 0.000378 | 0.061137 |
| Raw offline OBJ bbox deviation vs Z-up engine, mm | **10000** | **9000** |
| Offline OBJ after explicit `(x,y,z) -> (x,-z,y)` conversion: max vertex deviation, mm | <0.000001 | 0.061373 |
| Engine vs etalon: sampled surface max deviation, mm | 0.000378 | 0.320546 |
| Native FBX vs etalon: sampled surface max deviation, mm | 0 | 0.320653 |
| Native OBJ vs etalon: sampled surface max deviation, mm | 0 | 0.358197 |
| Current engine checker vs etalon | **9/9** | **9/9** |
| Prototype FBX checker vs etalon | **7/9** | **7/9** |
| Prototype OBJ checker vs etalon | **6/9** | **6/9** |

**Deviation definition matters.** For transport with matching tessellation, max
vertex deviation is symmetric nearest-vertex distance. Engine/etalon tessellation
is different; their nearest-vertex distances are 948.68 / 3971.46 mm and must NOT be
interpreted as surface errors. Surface measurements above take vertices and triangle
centroids in both directions and compute closest point on each opposite triangle.
They are sampled lower bounds, **not certified continuous Hausdorff bounds**.

**Failures retained:** native FBX/OBJ reads return only material ID `[1]` when the
prototype assigns face IDs but supplies no material objects. FBX then fails
`opening_planes` and `mesh` (roof inset classification relies on roof ID 21).
OBJ additionally loses LEVEL helpers and fails `levels`. The mesh failure is **not
merely a triangle-versus-quad policy failure**: actual checker details identify lost
roof semantics. See `checker-results.json`. No source quads were altered; the native
prototype builds triangulated derived copies only.

The offline reader is a deliberately small Python-only diagnostic, not a general
FBX SDK: binary 7400, Z-up metres, identity geometry/ancestor transforms only; rejects
nonidentity placement instead of silently reporting local coordinates as world.
It ignores unrelated translated LEVEL helpers, but follows geometry parents. It
checks geometry/counts, not material connections/UV/corner normals. Native and
offline FBX geometry agree; OBJ's raw axis mismatch demonstrates why a same-DCC
roundtrip alone is insufficient.

**Verdict: maybe** for a verified geometry-only FBX bridge after semantic/material
mapping is implemented. **Reject the unconfigured OBJ variant** as an AGR twin
transport: its axis and metadata contract is missing. Neither prototype is suitable
for NPM/VPM adoption now. Existing-tool batching above remains valid because that
arm imports real material-bearing etalon FBX, rather than these incomplete meshes.

## Failure visibility

| Control | Wrapper seconds | Wrapper exit / status | Native exit and evidence |
|---|---:|---|---|
| Uncaught Python RuntimeError | 39.8 | 1 / error | 4294967166 = signed -130; traceback and `AGR_INTENTIONAL_FAILURE_t_69ee7ca0` |
| Missing script file | 0.0 (wall 0.137 s) | 1 / error | 4294967196 = signed -100; `Script File Not Found` |
| Existing tool, no config | 42.5 | 1 / error | -130; `Absolute config path required` |
| Successful ping and jobs | see tables | 0 / ok **with warning** | also -130 from installed `polyunwrapper_autoload.mse` startup error |

Native exit alone does not distinguish job success on this workstation. The wrapper
classifies the known startup exception as a warning; completion markers and actual
artifacts/readback were checked in addition. Missing-file control inherited the
previous listener log because the runner reuses its per-card log filename: current
process output correctly identifies the missing file, but old listener text can be
misleading. This external wrapper issue is recorded, not repaired outside our worktree.
The first pings used wrapper default card `manual`: terminal did not inherit the
Kanban task id. All subsequent native calls supply `--card` explicitly.

## Correctness, complexity and open gates

- Baseline and final project suite, same scope/inputs: **1767 passed, 2 skipped,
  11 deselected**, pytest times 153.30 s and 168.57 s (single suite runs, not performance
  medians). Deselected DCC/Blender tests were not run; no other DCC was launched.
- `uv run dt profiles check`: 3 profiles, source hash and traceability OK.
  `uv run dt schemas --check`: 11 schemas OK.
- Explicit experiment tests: **15 passed in 2.61 s**, including real exported FBX vs
  native positions/counts across 6 files, OBJ mismatch detection, parser errors and
  synthetic point-to-surface tests. Without local native exports, 8 integration
  cases explicitly skip; the synthetic tests still run.
- Initial test attempts exposed missing basetemp parents, long-path diagnostic
  truncation and inherited `MSYS_NO_PATHCONV=1` / `MSYS2_ARG_CONV_EXCL=*`. Parents
  were created, a short per-worktree basetemp used, and only those variables were
  removed from the test subprocess environment. No global setting or production
  file was changed. Subsequent full baseline and final runs are green.
- Code size: unchanged tool **65 lines**; batching launcher **33 added lines**;
  `native_job.py` **106 lines**; diagnostic offline reader **131 lines**. Whole
  experiment harness including tests/analysis/control scripts: **676 lines**.
  This buys observability, not a reduction in production complexity. No dependencies
  were added. Offline parser is intentionally throwaway, not a proposed shared API.
- Not checked: UV seams, textures/embedding, face normals equivalence, profile pivot
  and material compliance, visual review, K02 real assets and Max 2024 compatibility.
  `delivery_passed=false` throughout; project production state is unchanged.

## Verdicts and proposed follow-up

1. **Adopt — bounded headless batching.** Scope-limited 1.713× per-job gain on the
   identical current B01 job, 12/12 verified exports, 9/9 geometry checks each.
   **Proposed task title:** `Max: add opt-in serialized batch jobs with verified per-job results`.
   **Scope:** adapter request/result schema, fresh job directories, watchdog and lock,
   explicit config injection, per-job artifact hashes and fresh-process QA, bounded
   batch sizes, private-scene reset only, startup-warning classification without
   hiding job failures. Keep per-process fallback; do not build a live Max daemon.
2. **Maybe — engine-dump native interchange; reject stock OBJ defaults.** FBX geometry
   is viable, but 7/9 benchmark checks is a hard barrier. Material objects/IDs, UVs,
   helper sidecar policy and independent profile-aware readback need a separate design
   before adoption. No production fix or issue is created by this experiment.

## Reproduction and evidence

Harness: `experiments/max-headless-agr-roundtrip/`. Paths are intentionally pinned
to this card/workstation. For a new experiment use a new scratch root in all
`BASE`/`SCRATCH` constants; do not reuse existing `.max`/FBX/OBJ destinations.
`prepare.py` copies references first and verifies manifest hashes.

```bash
uv run python experiments/max-headless-agr-roundtrip/prepare.py
python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --ping --card t_69ee7ca0
# Repeat ping three times, retaining --out JSON in this experiment directory.
python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --card t_69ee7ca0 --file experiments/max-headless-agr-roundtrip/native_job.py --out experiments/max-headless-agr-roundtrip/native-session.json
# existing_job.py: three separate wrapper calls, each with a distinct --out.
# batch_existing.py: AGR_MAX_EXP_SESSION=0,1,2; three calls with distinct --out.
# fresh_job.py: one fresh process after all exports; no live scene.
uv run python experiments/max-headless-agr-roundtrip/analyze.py
uv run python experiments/max-headless-agr-roundtrip/aggregate.py
mkdir -p experiments/max-headless-agr-roundtrip/local
uv run pytest -q experiments/max-headless-agr-roundtrip/test_experiment.py --basetemp=experiments/max-headless-agr-roundtrip/local/test
# Project tests: remove inherited MSYS overrides only for this subprocess.
env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -m 'not blender and not dcc' --basetemp="$(pwd -W)/.tbase"
uv run dt profiles check
uv run dt schemas --check
```

Committed numeric evidence: `evidence.json` (raw timing samples, parameter getters,
completion markers, 16 fresh comparisons, all export FBX hashes), `baseline-engine.json`,
`comparisons.json`, `checker-results.json`, `controls.json` and test-run timing JSON.
Full listener/process logs are local ignored `*-session.json`; binary outputs and
full dumps remain in the card's scratch directory. Reproduction requires the locally
available, hash-matching etalons. No unexecuted data is represented as a measurement.
