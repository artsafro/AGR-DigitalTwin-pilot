# AutoCAD core console plans versus ezdxf

## Question and scope

Can the project's current B01, B02 and B02t floor contours, openings and level elevations survive DWG/DXF serialization with measurable accuracy, and which route suits a CI machine without AutoCAD?

This is an isolated experiment, not a production exporter or an AGR delivery. No production engine, extractor, checker, shared capability registry or source asset is changed. The two candidate methods are AutoCAD 2025 core-console AutoLISP and offline ezdxf. No research report was supplied: the card instead names `docs/agr/inventory/autocad-menus.json`, `.agents/skills/autocad-mcp/SKILL.md` and `docs/agents/CAPABILITIES.md`. The menu inventory contains no reusable external-script macro references.

## Inputs and baseline

Base commit: `91795c019461699ce4c223e5fd2f595fe45859f9`.
Inputs copied before inspection: `object.json`, `etalon.json`, `spec.json` and `tolerances.json` from `benchmark/bench-b01-box`, `benchmark/bench-b02-corner-niche` and `benchmark/bench-b02t-terrace` into `C:/Users/artsafro/AppData/Local/Temp/agr-exp-t_3d8b70a4/`.

Important limitation: `object.json` defines the object frame/build inputs; `etalon.json` contains hashes/provenance of external MAX/FBX files, **not vertices**. Geometric references here are the committed etalon-derived `spec.json` copies, not a fresh independent extraction from the MAX/FBX etalons. No other DCC was run. These are benchmark fixtures, not plans of a real building.

The current project has no DXF/DWG serializer in `src/` (only intake format labels). Its current `Spec.expanded_floors()` and `geometry.from_spec.build()` are the baseline, not an invented legacy CAD exporter. The engine produces a mesh rather than a plan, so its timings are contextual and not an equivalent-work speedup comparison. Three builds per fixture, imports excluded, `BuildInputs(parapet_thickness_m=.3, facade_id=1, reveal_id=6, roof_id=21, opening_id=11)`:

| Current engine | Raw build seconds | Median seconds | Mesh vertices | Triangles |
|---|---|---:|---:|---:|
| B01 | 0.016270, 0.015185, 0.014615 | 0.015185 | 156 | 282 |
| B02 | 0.025005, 0.024556, 0.025039 | 0.025005 | 263 | 472 |
| B02t | 0.038039, 0.035833, 0.034736 | 0.035833 | 370 | 648 |

`uv run dt profiles check`: 3 profiles / hashes / traceability OK.
`uv run dt schemas --check`: 11 schemas OK.

Initial offline-suite baseline: 1762 passed, 5 failed, 2 skipped, 11 DCC tests deselected (170.81 s). Four failures were the inherited `MSYS_NO_PATHCONV=1` / `MSYS2_ARG_CONV_EXCL=*` causing native Python to receive `/c/...` paths from shell fixtures; the fifth was a long temporary path truncating a diagnostic in `test_agent_trace::test_bad_middle_line`. The targeted rerun with the two environment variables unset and a shorter per-card path gave 28 passed, 1 skipped. A subsequent full run overlapped Cursor's temporary hiding of `.claude/settings.json`; its seven missing-settings failures are invalid experimental evidence, not production regressions. Full suite must be verified only after Cursor exits.

## Setup and safety

- AutoCAD ping used only `python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py acad --ping`: ACADVER 25.0, core build V.72.0.0, 1.2 s, exit 0. Native calls below are sequential through the same wrapper and explicit card id; no COM or GUI session is used.
- AutoLISP is destructive arbitrary-code execution under the project's risk register. This card explicitly authorizes creation and saves only in isolated new scratch drawings. Nothing is written into `data/` or over accepted files. Per-run drawings and sidecars have new paths.
- Geometry is local WCS, converted from project metres to drawing millimetres with explicit INSUNITS=4. Floor contours use closed lightweight polylines; openings use closed 3D rectangles on their wall planes (not invented depth footprints); all level heights, including roof, use points on identified layers.
- ODA File Converter was not found on PATH or in the standard ODA/Open Design Alliance installation folders; no system software was installed.
- ezdxf 1.4.3 was provisioned through `uv run --with ezdxf==1.4.3`, with no project dependency/lockfile edits.

## Results

Accepted measurements are **run-v002**, after fixing and retesting the harness. Three repetitions batch all three benchmarks into one drawing: **21 entities, 69 coordinate records** (6 closed floor contours, 6 closed opening rectangles and 9 level points). B01's typical upper floor correctly inherits its opening. No missing or duplicate layers; closed flags, entity types and units matched in every readback.

| Route / operation, all fixtures together | Raw seconds, 3 runs | Median seconds | Matched entities / coordinates | Max round-trip deviation, mm |
|---|---|---:|---|---:|
| Current project CAD export | not implemented | n/a | no CAD output | n/a |
| ezdxf DXF write + parse/readback, in process | 0.023816, 0.017702, 0.019248 | **0.019248** | 21 / 69 each | 0 |
| AutoCAD create + DWG save + DXF export, one process | 1.645739, 1.618036, 1.405600 | **1.618036** | checked by later readers | see below |
| AutoCAD reopen DWG + enumerate, second process | 1.801933, 1.756831, 1.484864 | **1.756831** | 21 / 69 each | 1.29e-12 |
| AutoCAD read ezdxf-produced DXF | 1.089845, 1.191718, 1.137946 | **1.137946** | 21 / 69 each | 3.86e-12 |
| AutoCAD read native-produced DXF | 1.582124, 1.349062, 1.472085 | **1.472085** | 21 / 69 each | 3.86e-12 |
| ezdxf read native-produced DXF | not separately timed | n/a | 21 / 69 each | 9.09e-13 |

Native timings are high-resolution wall time around the wrapper subprocess, including startup/IPC overhead. The wrapper's own rounded seconds are preserved in evidence (write: 1.5, 1.5, 1.3 s; DWG read: 1.6, 1.4, 1.4 s). All 12 accepted native calls returned wrapper status `ok`, wrapper code 0 and native code 0. Median of the paired native write+DWG-read times is **3.374867 s**. Offline timings exclude imports, fixture normalization, uv startup and dependency installation; native timings include a fresh process per operation. This small fixture measures workflow latency, not large-plan throughput or a normalized kernel speed ratio.

Native DWG: 33,899 bytes; native DXF: 132,567 bytes; offline DXF: 29,516 bytes, each consistent across repetitions. `ezdxf.Document.audit()` on all six produced DXFs reported **0 errors and 0 fixes**. No curves, nested blocks, attributes, external references, rotated UCS/OCS, georeferencing, materials or full mesh topology are covered. The prototype is not a lossless serializer for every Spec field: terrace parapets, reveals/depth, roofing and delivery meshes are out of scope. In particular B02t's contour/level/opening plan matches B02 but does not exercise its terrace parapet geometry.

### Accuracy against the reference proxy

The round-trip table compares CAD readback with the shared serialization input rounded to six decimal places in mm, **not** with an independent MAX/FBX etalon. A separate verifier read the native DXF and recomputed coordinates from unrounded spec values and wall directions, plus Shapely contour areas. It confirmed:

| Spec-derived fixture | Contour max error mm | Contour area difference m² | Opening max error mm | Level max error mm |
|---|---:|---:|---:|---:|
| B01 | 0 | 0 | 0 | 0 |
| B02 | 0 | 0 | 3.01824e-7 | 0 |
| B02t | 0 | 0 | 3.01824e-7 | 0 |

The nonzero opening error is the prototype's decimal quantization at the oblique wall, not a drawing-unit loss. v002 native DXF coordinates were independently asserted equal to those verified in v001. These errors are below the experiment's 0.01 mm serialization threshold; they do not certify benchmark mesh checks or AGR acceptance. Current production geometry-checker behavior remains exercised by the unchanged offline test suite, not misapplied to a 2D/3D-wire plan as though it were a delivery mesh.

### Failure visibility and fixes

| Probe / observed failure | Native/wrapper behavior | Required detection |
|---|---|---|
| Undefined AutoLISP function | wrapper `ok`, exit 0; log says `no function definition: AGR-DELIBERATE-UNDEFINED-FUNCTION` | error text and missing completion marker; exit 0 is insufficient |
| Missing DWG | native exit 76, wrapper exit 1 / `error`; `Cannot find the specified drawing file` | failed process status + missing marker + missing input |
| Missing offline DXF | `FileNotFoundError` | normal exception, no fabricated result |
| Initial SCR with extra blank line | produced valid files and marker, then repeated a command and timed out after about 60 s, 3/3 runs | reject despite correct geometry; require wrapper/native success **and** marker **and** readback |

The first prototype incorrectly reported overall success for the last case because it checked only the outer Python subprocess timeout, not the wrapper's timeout status. The driver caught this by reading the raw wrapper JSON. Cursor round 2 removed the extra command prefix/blank SCR input, emitted exactly one terminal newline, and made timeout/status/code, mandatory readbacks and repetition counts fail closed. Eleven focused tests now include regressions for wrapper timeout with valid-looking markers, nonzero status despite correct geometry, omitted cross-check, documented open failure, exact repeat count, unit/closed/duplicate/missing/1 mm mutations and a real offline DXF round trip. First-run timings are retained as rejected evidence; they are not pooled with accepted latency samples.

### Complexity and correctness

The isolated harness is 680 Python lines plus 241 test lines; it includes common feature generation, comparison, both encoders/readers, subprocess safety and deliberate failure probes. This is experiment scaffolding, not a proposed 680-line production dependency. Production code changes: **0 lines**. The baseline has no CAD exporter, so there is no justified claim of net simplification versus a current exporter. ezdxf avoids the native session lock, SCR prompts, completion-marker parsing and installed AutoCAD dependency; native automation buys actual DWG support and an independent Autodesk parser.

Corrected offline suite (before final harness fix): **1767 passed, 2 skipped, 11 deselected**, 235.91 s. Final post-fix rerun: **1767 passed, 2 skipped, 11 deselected**, 146.63 s; profiles (3) and schemas (11) checks also passed again. The excluded tests launch Blender/DCCs outside this card's program scope. The two skipped tests and excluded tests are not called green. Focused experiment suite: **11 passed**, 0.49 s. The actual `--offline-only --repeats 3` CLI path also completed successfully without a native call. No Revit, Blender or 3ds Max was run.

## Verdicts and proposed follow-ups

- **B — ezdxf: adopt for CI/offline plan DXF round trips.** On all three benchmark proxies it preserved units, levels, contours and opening rectangles, with 0 mm round-trip error; median 0.019248 s and clean DXF audits. This is not a DWG reader/writer. **Proposed task:** `Add an offline plan-DXF regression adapter`. Scope: extract the minimal typed feature contract and strict readback comparator, pin ezdxf, test B01/B02/B02t from copied fixtures in CI, preserve exact source-frame metadata and explicitly reject unsupported curves/blocks/terrace fields. Do not treat plan QA as delivery QA.
- **A — AutoCAD core console: adopt for optional native DWG generation and conformance checks, not the default CI path.** DWG and bidirectional DXF interoperability passed all three runs after fixing prompt termination; native write+reopen costs about 3.375 s per batch. It requires AutoCAD 2025 installation/licensing and sequential wrapper ownership. **Proposed task:** `Add an opt-in AutoCAD DWG/DXF compatibility gate`. Scope: keep wrapper-only execution, single-newline SCR termination, fail-closed process/marker checks, versioned output paths and native readback; add oblique/large-coordinate/curve/block fixtures before production generalization. Keep it explicitly optional on CI without AutoCAD.

No GitHub issues or follow-up cards were created. These are scoped adoption recommendations, not authorization to replace the production pipeline.

## Reproduction and evidence

```bash
# Use copies of the four JSON inputs per benchmark as described above.
uv run --with ezdxf==1.4.3 pytest -q experiments/acad-coreconsole-agr-plans
uv run --with ezdxf==1.4.3 python experiments/acad-coreconsole-agr-plans/experiment.py \
  --inputs C:/Users/artsafro/AppData/Local/Temp/agr-exp-t_3d8b70a4 \
  --output <NEW_ABSOLUTE_SCRATCH_RUN_DIRECTORY> \
  --wrapper C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py --repeats 3
# Add --offline-only to run without AutoCAD.
env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q \
  -m 'not blender and not dcc' --basetemp=C:/x/t_3d8b70a4-post
```

Tracked evidence: `experiments/acad-coreconsole-agr-plans/evidence/measurements.json` (raw accepted times/statuses/comparisons, independent source check, input hashes, first-run rejection), `baseline-engine.json`, `native-readback.txt`. Reproducible generated SCR/LISP and binary outputs remain only in the isolated scratch `agr-autocad-t_3d8b70a4/run-v002/`, not in Git/LFS. No live drawing objects remain: every core-console session exited; no unrelated GUI document was changed.

Agent authorship: prototype and regression tests written by Cursor (grok-4.7-medium), two rounds; Hermes drove real executions, independent verification and this report. The PR Agent trace is generated with `tools/hooks/agent_trace.py`; unavailable Claude-format transcript measurements are left explicitly unmeasured.
