# 3dsmaxbatch −130: night native runs (card t_9e5904d6)

Isolated headless 3ds Max 2026.3 (28.3.0.30732), one process at a time via
`hermes_kanban/scripts/dcc_batch.py max --version 2026 --file <fixture> --wait 0 --timeout 180`,
2026-11-24 03:15–03:20, no GUI, no user scene. Synthetic scene only (one box / dummies).
Raw fixtures, run JSON, records and `merge_src.max`:
`G:/Мой диск/AGR-evidence/t_9e5904d6-maxbatch-130/` (hashes: `SHA256SUMS.txt` here, 19 files, verified).

| Arm | Fixture | Native exit | Result |
|---|---|---|---|
| a1 file control | `logging.FileHandler`, 20 lines, record JSON | 0, `Task Completed Successfully`, warnings [] | 20 lines in file, record complete, 1 object |
| b stdout | `logging.StreamHandler(sys.stdout)`, otherwise identical | **0**, `Task Completed Successfully`, warnings [] | 20 lines in listener log, record complete |
| a2 file control | same as a1 | 0 | same as a1 |
| c control | uncaught `RuntimeError`, no logging | **4294967166 (−130)**, `Task Completed with Error(s)` | traceback in listener |
| merge (first try) | MAXScript with top-level `local` | **4294967166 (−130)** | compile error `no local declarations at top level`; fixture bug |
| merge | same-name material + parent-name collision, `#mergeDups #useSceneMtlDups #neverReparent #noRedraw quiet:true` | 0 in 55 s, no dialog hang | `ok=true`; merged child takes the scene material (blue); child keeps its merged parent, scene parent untouched |

Findings:

- The MaxRescue claim (a stdout StreamHandler alone causes −130) **does not reproduce** on Max 2026.3 with this
  launcher: the stdout arm is a clean native 0, the same as both file controls.
- −130 reproduces deterministically for any **uncaught script error** (Python exception or MAXScript compile
  error): 3dsmaxbatch reports `Task Completed with Error(s)` and returns −130. That fits the earlier incidents
  (startup CLR exception, script errors) better than stdout.
- Explicit non-prompt merge flags (`#useSceneMtlDups`, `#neverReparent`) merge headless without a dialog and
  give the expected material/hierarchy. The static guard in `tests/test_max_batch_io_contract.py` stays: file
  logging still keeps diagnostics out of the listener, and explicit merge policies are what we measured.
