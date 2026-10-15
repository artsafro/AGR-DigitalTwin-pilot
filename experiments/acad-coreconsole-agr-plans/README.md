# AutoCAD core console vs ezdxf (throwaway)

Measurement prototype, with accepted run-v002 measurements in `evidence/measurements.json` and analysis in [`docs/experiments/acad-coreconsole-agr-plans.md`](../../docs/experiments/acad-coreconsole-agr-plans.md). Use a new output directory for every rerun.

The first scratch run, `run-v001`, exposed a false green: each native write returned wrapper status `timeout` and exit 5 after 60 seconds, while the done marker and drawing files were present, and the harness still reported success. That run is not a pass. A corrected harness is required before any native success claim.

`etalon.json` is metadata and file hashes, not mesh geometry. Coordinates come from `spec.json`, the extracted etalon proxy, expanded with `Spec.expanded_floors`. The benchmark fixtures are synthetic. Openings are closed rectangles in the wall plane (`x_m`, `w_m`, `sill_m`, `h_m` along the unit wall direction) and have no plan depth. Level markers are points at `0,0,elevation` for every level, including the roof. Roof contours and terrace parapets are not created.

Both writers consume the same feature dictionaries (`expected.json`). The ezdxf reader and the AutoLISP reader rebuild coordinates separately. Comparison is by unique layer, entity kind, closed flag, and vertex coordinates (cyclic or reversed polylines allowed) with a 0.01 mm tolerance. An empty readback is a failure.

AutoCAD is invoked only as `python <wrapper> acad --card t_3d8b70a4 --file ... --out ... --timeout 60 --wait 30 --max-chars 2000` with optional `--dwg`. Save and DXFOUT forms are `DWG_SAVE` and `DXF_FORM` in `experiment.py`. Scripts end with one newline. The body sets `FILEDIA` and `CMDECHO` with `setvar`; a command-line prefix is not written, because a blank script line repeats the previous command. A native call is `call_ok` only when the outer return code is 0, the wrapper status is `ok`, the wrapper code is 0, and the call did not time out. Wrapper status `timeout` or exit 5 is a timeout even when a marker and files exist. A failed write stops that repetition immediately: no further native calls, no later repetitions, and no AutoCAD probes. Read and cross-check calls need `call_ok`, a done marker, and a passing compare. A missing mandatory call or compare fails the run. `documented_open_failure` is partial evidence and does not make the run successful. The wrapper is left unchanged. `--offline-only` skips AutoCAD calls and the AutoCAD probes. Wrapper seconds are kept to one decimal.

Output directory must not already exist. Suggested path:

`C:/Users/artsafro/.hermes/profiles/dt-experimenter-cursor/cache/scratch/agr-autocad-t_3d8b70a4/run-v001`

```text
uv run --with ezdxf==1.4.3 python experiments/acad-coreconsole-agr-plans/experiment.py --inputs C:/Users/artsafro/AppData/Local/Temp/agr-exp-t_3d8b70a4 --output C:/Users/artsafro/.hermes/profiles/dt-experimenter-cursor/cache/scratch/agr-autocad-t_3d8b70a4/run-v001 --wrapper WRAPPER.py --repeats 3
uv run --with ezdxf==1.4.3 python experiments/acad-coreconsole-agr-plans/experiment.py --inputs C:/Users/artsafro/AppData/Local/Temp/agr-exp-t_3d8b70a4 --output C:/Users/artsafro/.hermes/profiles/dt-experimenter-cursor/cache/scratch/agr-autocad-t_3d8b70a4/run-v001-offline --wrapper WRAPPER.py --repeats 3 --offline-only
uv run --with ezdxf==1.4.3 pytest experiments/acad-coreconsole-agr-plans/test_experiment.py -q
```

`results.json` holds timings, audits, comparisons, and probe classifications. `.scr` and `.lsp` files are written beside the logs. Tests use labeled synthetic data and do not start AutoCAD.
