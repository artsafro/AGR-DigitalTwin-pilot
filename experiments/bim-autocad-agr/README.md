# E2 — silent CAD feature loss

Throwaway probe. Measured evidence is in `evidence/results.json`; the experiment report is `docs/experiments/bim-autocad-agr.md`. Geometry written into scratch comes from `spec.json` through `Spec.expanded_floors` (synthetic proxy). `etalon.json` is metadata and hashes, not mesh geometry.

`strict_read` accepts only straight closed LWPOLYLINE, closed 3D POLYLINE and POINT, `INSUNITS` 4, unique feature layers. Anything else rejects the whole file (`accepted=false`, `features=[]`). It does not detect self-intersections and does not infer architectural holes from polylines. A HATCH on layer `hole` is an unsupported entity with two boundary paths, not a semantic hole. An empty model space is `empty_document`. INSERT and XREF are rejected (`block_not_normalized`). Xref flags and the xref path are read and written only on BLOCK (`block.block.dxf`), never on BLOCK_RECORD. The path is not opened or expanded. `missing_xref` means the synthetic known-missing path `C:/missing/agr-e2-xref.dwg` is unresolved; any other xref is `unresolved_xref`, also unresolved without a read. A missing block, a block cycle, or a nest at depth 16 emits `missing_block`, `block_cycle`, or `depth_limit` instead of stopping the inventory quietly. The AutoLISP census is a top-level model-space inventory reference, not a feature extractor. Native success parses `payload["log"]` once and scans stderr on its own; stdout is not combined with the log, because that JSON repeats escaped error tokens. Identity, inventory match and those diagnostics are stored separately on every attempt.

Baseline `read_dxf` skips unknown entities and ignores bulge, so bulge, hatch, nested insert, missing xref and spline can still compare equal to the original features. An open contour is already a baseline mismatch.

Entity coordinate frames: POINT and 3D POLYLINE coordinates are already stored directly in WCS, whereas elevated LWPOLYLINE (elevated LW) vertices are defined in 2D OCS with elevation and require conversion via the OCS extrusion normal. Regression tests cover synthetic extrusion normals (default `(0, 0, 1)`, negative-Z `(0, 0, -1)`, and tilted `(0, 0.6, 0.8)`), guarding against double-transform errors. This probe exercises synthetic limits only; it establishes no new production adapter and does not claim native AutoCAD parity.

Phases do not call each other. Scratch must be an absolute path outside the worktree and must not exist before `prepare`. Drawings, scripts and logs stay in that scratch. Repeats must be >= 3. Native AutoCAD is only `python <wrapper> acad --card t_a0bf33bc --dwg <copy.dxf> --file <census.scr> --out <census.json> --timeout 60 --wait 30`. The script is read-only, written with the baseline `write_script` (CRLF, one trailing newline), and prints `AGR_ID`, `AGR_RAW` and `AGR_CENSUS_DONE`. Success needs wrapper code 0, status `ok`, process exit 0, `ACADVER` starting with `25`, the opened document name, `INSUNITS` 4, and the same top-level handle/type/layer multiset. Exit 3 (busy) waits 5s and retries; two failures of the same cause abort. Native skips repetitions already marked ok.

Pinned dependency: `ezdxf==1.4.3`.

```text
uv run --with ezdxf==1.4.3 python experiments/bim-autocad-agr/experiment.py --scratch C:/abs/scratch/agr-e2-t_a0bf33bc --phase prepare --repeats 3
uv run --with ezdxf==1.4.3 python experiments/bim-autocad-agr/experiment.py --scratch C:/abs/scratch/agr-e2-t_a0bf33bc --phase baseline --repeats 3
uv run --with ezdxf==1.4.3 python experiments/bim-autocad-agr/experiment.py --scratch C:/abs/scratch/agr-e2-t_a0bf33bc --phase strict --repeats 3
uv run --with ezdxf==1.4.3 python experiments/bim-autocad-agr/experiment.py --scratch C:/abs/scratch/agr-e2-t_a0bf33bc --phase native --repeats 3 --wrapper WRAPPER.py
uv run --with ezdxf==1.4.3 python experiments/bim-autocad-agr/experiment.py --scratch C:/abs/scratch/agr-e2-t_a0bf33bc --phase summary --repeats 3
uv run --with ezdxf==1.4.3 pytest experiments/bim-autocad-agr/test_experiment.py -q
```

`summary` writes `scratch/summary.json` (raw offline times, inventories, diagnostics, compact native records, before/after hashes) even when a stage is missing. Copy that file to `experiments/bim-autocad-agr/evidence/results.json` after a real run. Baseline and strict each need the exact 15 case ids, no duplicates, and at least 3 timing samples per case. Native needs those same ids from `cases.json`, at least that file's repeat count of successful attempts (`ok` is true; failed attempts are not successes; extra successes on a known id are ignored) and no unknown case ids. `--summary` without native, or with an empty or partial case list, exits nonzero. A nonzero exit means the phase did not meet its contract; it is not a successful measurement.
