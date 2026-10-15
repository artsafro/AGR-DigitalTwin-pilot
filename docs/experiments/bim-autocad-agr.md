# AutoCAD for AGR: detecting silent plan-reader loss

## Question and selection

Does a fail-closed DXF census prevent the existing experimental plan reader from silently accepting changed or omitted CAD content, without losing the project's supported contours, openings and levels?

Selected **one method: E2**, strict offline entity/feature census, with an independent headless AutoLISP inventory as its reference. Research: `origin/docs/research-bim-autocad-agr:docs/research/bim-autocad-agr.md`, read as explicitly authorized by this card. Base: `3cf7c93`, branch `experiment/bim-autocad-agr`, card `t_a0bf33bc`. Scope estimate was 35–50 minutes inside the approximately 60-minute time box.

This extends `docs/experiments/acad-coreconsole-agr-plans.md`; it does not repeat its serialization-speed contest. E1 frame recovery is deferred. E3 independent mesh sections requires a different program/session and was not attempted. .NET, live COM/multiCAD and ODA conversion were not evaluated. ODAFileConverter was absent on PATH and the standard `Program Files/ODA` and `Program Files/Open Design Alliance` directories did not exist; no software was installed.

## Inputs, scope and support contract

- Copied `object.json`, `etalon.json`, `spec.json`, `tolerances.json` for B01/B02/B02t before use: 12 input files. Scratch root: `C:/Users/artsafro/.hermes/profiles/dt-experimenter-cursor/cache/scratch/agr-autocad-t_a0bf33bc/run-v002/`.
- Geometry comes from copied etalon-derived Specs through the prior experiment's `build_features`, **not** fresh independent MAX/FBX measurements. All generated CAD is synthetic proxy data. `etalon.json` is provenance/hash metadata, not vertices. B02t's terrace-specific mesh is not represented in this narrow wire format.
- Three unchanged drawings: each has 7 entities; together 21 features and 69 coordinate records. B01 has 19 coordinates; B02 and B02t have 25 each. Local WCS, drawing millimetres, INSUNITS=4; no georeferencing claim.
- Six synthetic variants per B02/B02t: nonzero bulge; HATCH with an outer ring and inner hole; nested rotated/nonuniformly scaled INSERT; nonexistent xref; added SPLINE; opened contour. Thus 15 drawings, including 12 adversarial drawings.
- Added unsupported objects coexist with the original features: this deliberately checks whether an apparently complete expected feature set can hide extra source geometry. The bulge/open-contour variants instead alter an existing feature.
- The baseline is `experiments/acad-coreconsole-agr-plans/experiment.py::read_dxf` plus `compare_features`, unchanged. There is still no production CAD parser to replace. The baseline was measured before executing the strict phase.
- Strict acceptance is limited to straight closed LWPOLYLINE, closed straight 3D POLYLINE and POINT, explicit mm units and one feature per layer. Unknown types, curves, unsupported polyline modes, blocks/xrefs, open contours, duplicate feature layers and empty documents reject. Any diagnostic empties the entire feature output; rejected partial geometry is never presented as a successful extraction.
- Recursive INSERT inventory preserves handles and parent chains, but does **not** normalize transforms. Cycles, depth limits and missing blocks are explicit. Ordinary xrefs are marked `unresolved_xref`; `missing_xref` specifically labels the synthetic known-missing path. Xref files are never opened. This is not a filesystem resolver.

## Setup and commands

Python 3.14.7; ezdxf 1.4.3 supplied by `uv --with`, no dependency/lockfile changes. AutoCAD ping succeeded: ACADVER 25.0, core V.72.0.0. The native stage only reads generated copies and prints identity plus model-space handle/type/layer census through `ssget`/`entget`; it neither saves nor exports. No COM, GUI document, Revit, Blender or 3ds Max was used.

```bash
python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py acad --ping
# S = fresh absolute scratch directory above, initially nonexistent.
uv run --with ezdxf==1.4.3 python experiments/bim-autocad-agr/experiment.py --scratch "$S" --phase prepare
uv run --with ezdxf==1.4.3 python experiments/bim-autocad-agr/experiment.py --scratch "$S" --phase baseline
uv run --with ezdxf==1.4.3 python experiments/bim-autocad-agr/experiment.py --scratch "$S" --phase strict
uv run --with ezdxf==1.4.3 python experiments/bim-autocad-agr/experiment.py --scratch "$S" --phase native \
  --wrapper C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py
uv run --with ezdxf==1.4.3 python experiments/bim-autocad-agr/experiment.py --scratch "$S" --phase summary
```

Each phase defaults to three repetitions and refuses fewer than three. Native calls use the current card id and wrapper lock, sequentially, with `--timeout 60 --wait 30`. Each repetition gets a fresh `copy.dxf`, SCR and full result JSON. Native success requires wrapper/native success, no timeout/error token, completion marker, AutoCAD 25 identity, expected filename/units and exact handle/type/layer inventory agreement with a separate ezdxf read. The summary rejects missing/partial stages instead of trusting file existence.

Offline timings include file read, census/extraction and comparison, excluding imports, generation and uv startup. Strict rejection stops before coordinate comparison. Native times include wrapper/process startup and enumeration, not equivalent geometry work. The repository test suite ran concurrently with the measurement phases; small timing differences are not a controlled speedup claim. Native reference work is intentionally slower and independent.

## Measurements

All cells are median seconds of **three runs per drawing and route**. Every native inventory matched in all repetitions. B02 = corner-niche; B02t = terrace proxy.

| Drawing | Baseline read + compare | Strict census + compare/reject | Native census | Baseline verdict → strict verdict |
|---|---:|---:|---:|---|
| B01 clean | 0.005707 | 0.006864 | 1.438071 | accept → accept |
| B02 clean | 0.005895 | 0.006275 | 1.260280 | accept → accept |
| B02 bulge | 0.006333 | 0.007575 | 1.308376 | silent accept → reject |
| B02 HATCH hole | 0.007701 | 0.006873 | 1.306460 | silent accept → reject |
| B02 nested INSERT | 0.007084 | 0.008106 | 1.245468 | silent accept → reject |
| B02 missing xref | 0.007000 | 0.006446 | 1.881977 | silent accept → reject |
| B02 SPLINE | 0.007498 | 0.006621 | 1.377521 | silent accept → reject |
| B02 open contour | 0.006708 | 0.006583 | 1.151022 | reject → reject |
| B02t clean | 0.006942 | 0.006313 | 1.007626 | accept → accept |
| B02t bulge | 0.006282 | 0.006422 | 1.060985 | silent accept → reject |
| B02t HATCH hole | 0.006481 | 0.007983 | 1.037719 | silent accept → reject |
| B02t nested INSERT | 0.007317 | 0.006994 | 1.025503 | silent accept → reject |
| B02t missing xref | 0.006475 | 0.006347 | 1.056220 | silent accept → reject |
| B02t SPLINE | 0.006510 | 0.006536 | 0.983850 | silent accept → reject |
| B02t open contour | 0.005746 | 0.006079 | 1.161215 | reject → reject |

### Correctness and output differences

| Metric | Baseline | Strict prototype |
|---|---|---|
| Clean drawings accepted | 3/3 | 3/3 |
| Adversarial drawings correctly rejected | 2/12 | **12/12** |
| Unsupported/changed geometry silently accepted | **10/12** | **0/12** |
| Accepted clean output | 21 features / 69 coordinates total | Same counts, closure, units and coordinates |
| Max clean serialization deviation | 0 mm | 0 mm |
| Rejected output geometry | Baseline can retain apparently valid partial features | Empty feature result with explicit diagnostics |
| Independent native inventory | Reference only | 45/45 successful calls agree |

Both bulged drawings expose a **375 mm analytic sagitta** (1,500 mm first chord, bulge 0.5), while the old straight-vertex comparison reports zero deviation. Native census also sees seven main entities here: count equality cannot detect curvature loss. Strict diagnoses `curved_segment`.

HATCH, SPLINE and xref cases have eight main entities versus seven baseline features. Nested INSERT has eight main entities and ten recursively inventoried records; child provenance has two parent handles. Strict rejects all blocks rather than pretending it has transformed their geometry. A separate Shapely containment check confirms both generated HATCH inner rings are inside their outer rings; accepting or repairing holes is not claimed. No Hausdorff/area approximation budget is relevant because the method rejects curves rather than tessellating them. Coordinates of rejected geometry are **not** assigned a misleading 0 mm accuracy.

All 12 original input hashes and their copied hashes, all 15 generated drawing hashes, and all 45 native per-call copy hashes remained unchanged. The read-only native processes exited; no experiment objects were placed into a live document, so there are none to remove. Generated binaries and full logs remain in card-specific scratch; nothing was written into `data/`.

## Tests, failure evidence and complexity

- Existing plan experiment before prototype measurements: **11 passed**, 0.74 s.
- Cursor round 1 preparation stopped on invalid `BLOCK_RECORD.flags`; focused tests gave **3 failed / 9 passed** with the same API error. No performance sample was accepted from this aborted preparation (`run-v001`). A stop record was posted; round 2 reads/writes xref flags only on `BLOCK` and adds stronger failure tests. This setup exception is not claimed as a RED architectural assertion.
- The first combined test collection hit duplicate module name `test_experiment`; `--import-mode=importlib` repairs the invocation without editing the old experiment.
- Final focused command: `uv run --with ezdxf==1.4.3 pytest -q --import-mode=importlib experiments/bim-autocad-agr experiments/acad-coreconsole-agr-plans ...`: **31 passed**, 1.38 s (20 new tests, 11 unchanged existing). Includes baseline silent acceptance, all six variants, parent provenance, units, unsupported polylines, empty documents, native status/marker/inventory failures and incomplete summary rejection.
- Full current offline repository suite, after Cursor restored project settings: `env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -m 'not blender and not dcc' --basetemp=C:/x/t_a0bf33bc`: **2026 passed, 9 skipped, 12 deselected**, 288.41 s. One expected duplicate-ZIP-member warning. Skipped/deselected tests are not passes; no other DCC was launched.
- `uv run dt profiles check`: **3 profiles**, hashes/traceability OK. `uv run dt schemas --check`: **11 schemas** OK.
- Prototype harness: **655 Python lines**, tests **316 lines**; existing baseline reader entry point **33 lines**. New `strict_read` entry point is 15 lines plus census/extraction/diagnostic helpers. Production changes: **0 lines**. This improves failure visibility, not code-size simplicity; the whole harness should not become a production dependency.
- CI: not run (billing lock).

Tracked evidence: `experiments/bim-autocad-agr/evidence/results.json` contains raw timing samples, diagnostics, inventories, statuses, source/drawing hashes and copy checks. Full native logs and original phase JSON are in scratch. `README.md` contains reproduction commands. The comparison demonstrates a failure of the previous experimental reader, not an existing production parser regression. Delivery mesh checkers are exercised by their existing tests, not misapplied to plan wires.

## Verdict and follow-up

**ADOPT: fail-closed census before plan-feature acceptance**, for the explicitly narrow straight-entity contract. It removes all ten observed silent acceptances while preserving every clean proxy at 0 mm serialization deviation. The approximately millisecond offline census is practical; there is no reliable speed win demonstrated. The native census is a useful optional compatibility/reference check, not a full native geometric extractor or a new mandatory CI dependency.

**Proposed task — Add a fail-closed DXF intake contract and loss diagnostics.** Extract a small adapter from this experiment, pin ezdxf, require complete entity provenance/unsupported inventory and empty geometry on rejection. Preserve the three clean fixtures and six adversarial classes as regression cases; keep native AutoCAD census optional and wrapper-only. Define a real layer/feature schema instead of treating unique layers as an architectural rule. Generalize xref diagnostics without the synthetic known-path shortcut. Validate actual source DWGs with explicit units/control points before opening the accepted support contract to arbitrary plans. Do not silently approximate curves, normalize blocks or infer courtyard semantics without separately measured shape budgets and policy.

Seen, not mine: rotated UCS/OCS and large offsets remain E1; terrace-specific mesh sections remain E3; self-intersections, ordinary multiple objects per layer, attributes, source semantics and paper-space content need independent coverage. This experiment validates neither IN5 architectural extraction nor MSK-77, materials, FBX, V001–V017/manual gates or official AGR delivery. No issues or follow-up cards were created; production pipeline and project state are unchanged.

Prototype and regression tests written by Cursor (grok-4.7-medium), two rounds. Hermes drove native/offline execution, inspected real payloads, verified hashes and analytic controls, and wrote this report. The PR Agent trace is generated by `tools/hooks/agent_trace.py`; unavailable transcript measurements remain explicitly unmeasured.
