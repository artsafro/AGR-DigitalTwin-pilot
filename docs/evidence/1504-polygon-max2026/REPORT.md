# Current-main AGR Tools polygon — Max 2026 (#1504)

Source: `9b7945d0b6ce0058020f63215b6497eb507190ef` (main at task start).
Job: `20261116-231246-t_aa346b71-native-v001`.
Application: 3ds Max 2026.3, exact build **28.3.0.30732**; embedded Python 3.11.12.
Native process: exit 0, 329.8 seconds; **0 diffs, known_bug 0**.
Total: 94 stations, 876 expectation rows, 127 presses/apply records.

## Measured table

| Base | Stations pass/total | Rows pass/total |
|---|---:|---:|
| 0.1 | 3/3 | 8/8 |
| 0.2 | 2/2 | 5/5 |
| 0.3 | 2/2 | 3/3 |
| 0.4 | 1/1 | 2/2 |
| 0.5 | 5/5 | 167/167 |
| 0.6 | 0/0 | 0/0 |
| 0.7 | 12/12 | 498/498 |
| 0.8 | 13/13 | 27/27 |
| 0.9 | 19/19 | 70/70 |
| 1.0 | 33/33 | 91/91 |
| 1.1 | 4/4 | 5/5 |

Base 0.6 is the Qt panel release: no polygon stations; 0/0 is not UI acceptance.

## Required #1020 buttons

| Station | Button | Rows | Result |
|---|---|---:|---|
| 1.0.3 | `scene.source_class` | 2 | OK |
| 1.0.5 | `model.attach_by_material` | 4 | OK |
| 1.0.6 | `model.move_apart` | 2 | OK |
| 1.0.7 | `model.grid_cleanup` | 2 | OK |
| 1.0.8 | `scene.small_parts` | 7 | OK |
| 1.0.11 | `model.glass_planes` | 3 | OK |

## Route and boundaries

Authorized by Artem: [2026-11-16 slot release](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1504#issuecomment-6930502674).
Initial read-only ping saw a foreign live Max; it ended before launch. A fresh process inventory was empty and both shared Max locks were absent. No foreign scene was attached, changed or closed.
Executed `uv run python test-polygon/run_polygon.py --version 2026 --out <worktree>/tmp/1504/native-v001`.
The standard runner invoked `dcc_batch.py max` and `build/run_inside_max.py` under the shared session lock. The inherited card variable was absent, so the stock runner logged its owner as `manual`; the unique worktree/output and command bind this run to t_aa346b71.
The stock polygon stages current-main runtime and generated slices into output/stage; it does not install or remove the user bundle. This certifies staged current-main runtime, not installed-MZP identity or panel clicks. No installed-bundle acceptance is inferred.
Synthetic fixtures only. No Max 2024 rerun, customer model, AC08 run, new buttons or excluded 1.x Ground tail. No expected/ JSON edits. Native exit and comparison are independently retained.
The PNG chart is generated from measured report.json, not a native viewport screenshot; other PNGs are the native fixture/apply textures. No UI/visual acceptance is claimed.

## Retained evidence

`G:/Мой диск/AGR-evidence/1504-polygon-max2026/20261116-231246-t_aa346b71-native-v001`
`SHA256SUMS.txt` seals 322 files, including raw actual.json, report.json, table.txt, max.log, fixture scenes, staged runtime and PNGs. Every copied file was SHA256-read back after copy.
The committed manifest is the same text as the external manifest. Large binaries stay outside git.

## Verification

Full suite: deferred to merge batch (rule 68).
The receipt regression proves presence and internal consistency of this historical receipt; it does not rerun Max or certify future code.
