# Hypothesis #84: transformed CAD plans retain 0.01 mm accuracy

## Verdict: CONFIRMED (tested subset only)

All four frozen transforms × three repetitions passed every mandatory route. Worst Euclidean XYZ error against the independently derived, unrounded-spec oracle: **1.9983118313e-6 mm**, below **0.01 mm**. There were **60/60 successful geometry readbacks**, **48/48 successful native calls**, and **24/24 DXF audits with zero errors and zero fixes**. Every read preserved 21 entities, 21 entity-bearing layers and 69 coordinate records, kinds, closure flags and INSUNITS=4.

This confirms serialization accuracy for synthetic straight-entity benchmark plan proxies, **not CRS/geodetic correctness, architectural extraction accuracy, delivery QA or full Spec serialization**. No production adapter was added.

## Question, inputs and frozen setup

Source: pilot issue #84 and `docs/experiments/acad-coreconsole-agr-plans.md`. Base: `3cf7c9358591a12813ec5bcbcb8e082ddf5fe342`. Methods: existing ezdxf plan encoder/reader and AutoCAD core-console encoder/native readers. No geometry precision workaround or recentering.

Copied `spec.json`, `object.json`, `etalon.json`, `tolerances.json` from tracked `benchmark/bench-b01-box`, `bench-b02-corner-niche`, `bench-b02t-terrace` to `C:/Users/artsafro/.hermes/profiles/dt-experimenter-cursor/cache/scratch/agr-autocad-t_5071f110/inputs/` before measurement. All 12 source and copy SHA256 values matched before/after (tracked `experiments/hyp-84/evidence/input-hashes.json`). No binary etalon was opened. `etalon.json` contains provenance, not vertices; these spec-derived references are not independent native architectural etalons. B02t terrace parapets are excluded.

Transforms are applied in **metres**, then converted to drawing mm:

1. Identity (fresh same-input baseline).
2. Rz(+37°), right-handed WCS about origin.
3. Translation `(600000, 7500000, 150)` m.
4. Rz(+37°), then that translation.

All contour vertices, four corners of every wall-plane opening and all level markers (including XY) are transformed. Six contours + six openings + nine points = 21 entities / 69 coordinate records. B01 L1 inherits its L0 opening. All drawings use WCS, UCS origin zero, INSUNITS=4, R2018 output. Native raw flags are LWPOLYLINE=1, 3D POLYLINE=9; point has no flag. Census includes all modelspace entity kinds, not just the legacy reader's filtered list. The 21 count refers to entity-bearing layers, not AutoCAD's reserved layer table entries.

AutoCAD ping: **2025, ACADVER 25.0, build V.72.0.0**, native exit 0. Python **3.14.7**, transient **ezdxf 1.4.3**. All native operations used sequential `dcc_batch.py acad` calls with card `t_5071f110`; no GUI, COM, Blender, Max or Revit. Each DWG reopen and DXF native read used a fresh process. Arbitrary AutoLISP is destructive-class and explicitly authorized here only in fresh scratch drawings. No original/source drawing, `data/`, wrapper, CI, dependency or production file was edited. Every console process exited; no created objects remain in a live user document. Generated drawings/logs stay in scratch, not Git.

## Baseline and independent oracle

Before prototyping was exercised, ran the unchanged legacy offline CLI with three repetitions on the same copied inputs: **21 entities / 69 coordinates**, round-trip error 0 mm, raw seconds **0.0236703, 0.0188487, 0.0188922**, median **0.0188922 s**. The original 11 focused tests passed (0.80 s). Production has no CAD serializer; this is a baseline of the existing experimental encoder, not a claimed production-export speedup.

The new task-local driver imports individual functions from the tracked legacy harness, but never its main, native launcher or historical card/path constants. To transform before mm conversion, it temporarily substitutes identity `to_mm`, obtains unrounded metre feature values, restores the function, applies the transform and retains the existing six-decimal-mm serialization. This is the minimal test-only generalization; it does not rotate already-rounded coordinates.

The oracle separately parses copied raw JSON with Decimal values, resolves typical-floor inheritance without `Spec.expanded_floors`, computes wall directions using Decimal square roots, and computes sin/cos(37°) with independent 50-digit Taylor series. It never consumes writer arrays, the writer's trigonometry or rounded coordinates. Oracle results are converted to binary64 only at final comparison; errors are therefore reported at that representation's resolution (about 1e-6 mm at the largest coordinates), not as exact arbitrary-precision native accuracy. Closed rings permit cyclic start/reversal equivalence, but raw vertex counts and flags must match exactly.

## Prediction table

Timing values are descriptive medians of three runs, not speedup predictions. Accuracy rows use the median of the three per-run maxima; all three maxima were identical within each transform/route. **Rejection still uses the maximum across every run**, never a median that could hide a failure.

| Metric | Inputs | Baseline (current code) | Rejection threshold | Measured (median of N) | Verdict |
|---|---|---|---|---|---|
| Max Euclidean XYZ error | Identity, all readers | Legacy same-array round trip 0 mm; fresh independent oracle 3.018249678e-7 mm | Any sample >0.01 mm | N=3 per route; worst 3.018249678e-7 mm | CONFIRMED |
| Max Euclidean XYZ error | Rz37, all readers | Fresh identity above | Any sample >0.01 mm | N=3 per route; worst 6.734974905e-7 mm | CONFIRMED |
| Max Euclidean XYZ error | Translation, all readers | Fresh identity above | Any sample >0.01 mm | N=3 per route; worst 9.610960183e-7 mm | CONFIRMED |
| Max Euclidean XYZ error | Rz37 then translation, all readers | Fresh identity above | Any sample >0.01 mm | N=3 per route; worst 1.998311831e-6 mm | CONFIRMED |
| Exact semantic census | Each transform ×3 ×5 readers | 21 entities / 69 records, 6/6/9 kinds | Any lost/duplicate/extra entity, layer, vertex or wrong kind/closure/raw flag | Exact in 60/60 reads; no mismatch | CONFIRMED |
| Units and native identity | Every read / native call | INSUNITS=4, AutoCAD 25.0, WCS | Any incorrect unit/identity | Units 4 in 60/60 reads, identity valid in 48/48 native calls | CONFIRMED |
| DXF audit | Both DXFs per repetition | Clean identity DXFs | Any error or fix | 24/24 clean, 0 errors / 0 fixes | CONFIRMED |
| Process + marker + files + readbacks | All native operations | Identity 12/12 calls | Any failed call, missing marker/file/readback; unavailable AutoCAD = inconclusive | 48/48 calls, 60/60 geometry reads; zero busy retries | CONFIRMED |
| Offline write+read latency | Four transforms | Legacy 0.0188922 s; fresh identity 0.0296373 s | No timing rejection threshold | 0.0296373 / 0.0317466 / 0.0266917 / 0.0319738 s, N=3 each | Descriptive only |

## Accuracy maxima by class, transform and reader

Maxima across three repetitions, mm. `offline` = ezdxf own DXF; `read_dwg` = native DWG reopen; `ezdxf_native` = ezdxf reading native DXF; last two = AutoCAD reading offline/native DXF. Every row has exact 21/69 census and units 4.

| Transform | Reader | Contour max mm | Opening max mm | Level max mm |
|---|---|---:|---:|---:|
| identity | offline | 0 | 3.018243247e-7 | 0 |
| identity | read_dwg | 0 | 3.018249678e-7 | 9.094947018e-13 |
| identity | ezdxf_native | 0 | 3.018249678e-7 | 0 |
| identity | native_offline_dxf | 0 | 3.018223954e-7 | 9.094947018e-13 |
| identity | native_native_dxf | 0 | 3.018223954e-7 | 9.094947018e-13 |
| rotation37 | offline | 6.734974905e-7 | 6.281348662e-7 | 0 |
| rotation37 | read_dwg | 6.734968518e-7 | 6.281342718e-7 | 9.094947018e-13 |
| rotation37 | ezdxf_native | 6.734968429e-7 | 6.281348662e-7 | 0 |
| rotation37 | native_offline_dxf | 6.734968518e-7 | 6.281342718e-7 | 9.094947018e-13 |
| rotation37 | native_native_dxf | 6.734968518e-7 | 6.281342718e-7 | 9.094947018e-13 |
| translation | offline | 0 | 2.384185791e-7 | 0 |
| translation | read_dwg | 9.610960183e-7 | 9.610960183e-7 | 0 |
| translation | ezdxf_native | 9.536743164e-7 | 9.536743164e-7 | 0 |
| translation | native_offline_dxf | 9.610960183e-7 | 9.610960183e-7 | 0 |
| translation | native_native_dxf | 9.610960183e-7 | 9.610960183e-7 | 0 |
| rotation37_then_translation | offline | 9.830249847e-7 | 9.830249847e-7 | 0 |
| rotation37_then_translation | read_dwg | 1.066240300e-6 | 1.018524616e-6 | 0 |
| rotation37_then_translation | ezdxf_native | 1.066240300e-6 | 1.018524616e-6 | 0 |
| rotation37_then_translation | native_offline_dxf | 1.124618188e-6 | 1.018524616e-6 | 0 |
| rotation37_then_translation | native_native_dxf | 1.998311831e-6 | 1.066240300e-6 | 0 |

## Automation cost

Seconds, median of three; all raw samples in `experiments/hyp-84/evidence/measurements.json`. Offline write+read excludes imports, oracle, audit, uv startup and dependency installation. Native timings include wrapper and fresh process startup. Not equivalent-work throughput comparisons; machine load varied.

| Transform | Offline write+read | Native create/save/export | DWG reopen | ezdxf native DXF read | Native offline DXF read | Native own DXF read | Paired write+DWG reopen |
|---|---:|---:|---:|---:|---:|---:|---:|
| identity | 0.0296373 | 1.8088551 | 1.5462925 | 0.0223566 | 1.2279630 | 1.6671327 | 3.3551476 |
| rotation37 | 0.0317466 | 1.8073697 | 1.6389517 | 0.0286590 | 1.4342656 | 1.5863350 | 3.4334392 |
| translation | 0.0266917 | 1.7980579 | 1.6603188 | 0.0197545 | 1.4267253 | 1.7669226 | 3.4583767 |
| rotation37_then_translation | 0.0319738 | 2.2284352 | 1.8843137 | 0.0237509 | 1.4886624 | 2.0928220 | 3.9210699 |

Fail-closed requirements combine outer subprocess status, wrapper status/native exit, completion marker, identity, nonempty files, full census and independent readback. A marker/file alone never passes. SCR uses exactly one terminal newline. Log parsing consumes only full payload `log`, avoiding duplicate entity markers from stdout JSON. Busy exit 3 is retried separately; none occurred. Native command timeout is 60 s, outer timeout 120 s. Availability was established before the matrix; unavailable AutoCAD cannot support offline-only confirmation.

## Tests, limitations and adoption scope

Focused final post-copy-safety suite: **16 passed** (5 new hypothesis tests + 11 unchanged legacy tests), 0.79 s; 28 third-party pyparsing deprecation warnings. Tests exercise typical-floor inheritance, independent transform composition and marker XY, all four real offline DXF round trips, a 0.011 mm rejection, missing entities, wrong closure/raw flags, extra unsupported LINE, nonfinite coordinates, audit errors/fixes, status/marker/identity/unit failures, busy retry/exhaustion and fresh-output refusal. An initial test incorrectly expected an undefined layer to be an ezdxf audit failure (4 passed / 1 failed); changed the corruption to an undefined **linetype**, verified to produce an actual audit fix. This was a test-fixture correction, not a measured serialization failure. Final tests copy the reference JSON fixtures to test-local scratch before use.

Profiles: **3 valid**. Schemas: **11 valid**. Unchanged production offline suite: **2026 passed, 9 skipped, 12 deselected**, 280.13 s; one existing duplicate-ZIP-member warning. This runs the current project's production/checker regressions, not delivery checks on wire drawings. CI: not run (billing lock). Excluded/skipped tests are not called green; no DCC tests from other programs were executed.

Prototype complexity: 655 driver lines plus approximately 259 test lines, reusing the existing 680-line experimental harness. Production changes: zero. This is measurement scaffolding, not a simplification or production dependency proposal.

- **ADOPT — offline transformed-plan regression coverage.** Proposed follow-up title: `Add transformed straight-plan DXF regression fixtures`. Scope: `tests/test_plan_dxf_transforms.py`, independent unrounded expected geometry, frozen four-transform matrix, exact raw semantic census, units, nonfinite and >0.01 mm negative probes. Keep curves/blocks/UCS variants/terrace parapets and delivery checks explicitly unsupported. No benchmark edits or CI changes in this experiment.
- **ADOPT — optional native compatibility regression coverage.** Proposed follow-up title: `Add opt-in transformed DWG/DXF compatibility checks`. Scope: opt-in tests beside `experiments/acad-coreconsole-agr-plans/test_experiment.py`, wrapper-only sequential calls, fresh DWG reopen and both DXF cross-readers, exact-one-newline scripts, call+marker+readback/audit gates. AutoCAD absence must skip/inconclusive, not an offline-only confirmation.

No issues or adoption tasks were created; implementation remains separate. No CRS, MSK-77, architectural or delivery certification follows from these measurements.

## Reproduction

```bash
# First copy the 12 tracked JSON inputs to a new per-card scratch inputs folder.
uv run --with ezdxf==1.4.3 python experiments/acad-coreconsole-agr-plans/experiment.py \
  --inputs <COPIED_INPUTS> --output <FRESH_BASELINE_DIR> \
  --wrapper C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py --repeats 3 --offline-only
python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py acad --ping --card t_5071f110
uv run --with ezdxf==1.4.3 python experiments/hyp-84/experiment.py \
  --inputs <COPIED_INPUTS> --output <FRESH_MATRIX_DIR> \
  --wrapper C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py --card t_5071f110 --repeats 3
uv run --with ezdxf==1.4.3 pytest -q --import-mode=importlib \
  experiments/hyp-84 experiments/acad-coreconsole-agr-plans --basetemp=<CARD_SCRATCH_TEST_DIR>
env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q \
  -m 'not blender and not dcc' --basetemp=<SHORT_CARD_SCRATCH_SUITE_DIR>
uv run dt profiles check
uv run dt schemas --check
```

The CLI calls a fully passing result `accepted`; the report/issue policy maps that to **CONFIRMED**. Evidence contains raw timings, counts, class maxima, statuses, identities and audit totals; full native logs and binary outputs reside only in `matrix-v001` under the scratch root above. Agent authorship: driver/tests written by Cursor (grok-4.7-medium), one round; Hermes performed baseline/native executions, verification, small test-fixture/copy safety edits and report. PR Agent trace is generated by `tools/hooks/agent_trace.py`; unavailable transcript-derived counters are not invented.
