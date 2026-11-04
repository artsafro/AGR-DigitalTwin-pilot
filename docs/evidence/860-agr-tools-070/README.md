# #860 AGR Tools 0.7.0 — evidence

Synthetic, disposable scenes only (built in memory by `tests/max_tools/run_agr_tools_suite_native.py`, never
saved: `scene_saved: false`). Not data of a real object.

Big files are on Drive, `G:/Мой диск/AGR-evidence/860-agr-tools-070/` (47 files); hashes in `SHA256SUMS.txt`
(same file here).

| File | What |
|---|---|
| `AGR-Tools-0.7.0.mzp` | MZP built from `e2fb97ec`, sha256 `30a83517…6bd98aff` |
| `AGR-Tools-0.7.0.bundle.zip` | Application Plugin Package, sha256 `7784ccac…befd80ef` |
| `final-2026-dark/smoke/max2026_dark_path.png` | «Путь» with live status after the run (Max 2026, Dark) |
| `final-2026-dark/smoke/max2026_dark_qa.png` | rail + tab «7 Проверки» (Dark), planned buttons greyed «в версии 0.x» |
| `final-2026-light/smoke/max2026_light_*.png` | the same in Max's own Light theme (`ame-light.clrx`, restored byte-identical) |
| `final-2024-dark/smoke/max2024_dark_*.png` | Max 2024 (PySide2 through `ui_qt.py`) |
| `*/smoke/<check>.json` | the 12 JSON reports of each run |

Here:

- `native-summary.json` — per run: Max version, theme, status + codes of the 12 checks, «Путь» status per block,
  «Следующий шаг», errors (none), clrx restore check.
- `native-excerpt-max2026.json` — per check: status, object count, first findings, plan keys; `units` with its
  plan findings.

Runner: `python tests/max_tools/drive_agr_tools_suite_native.py --pkg <extracted MZP>/agr_tools --out <new dir>
[--version 2024|2026] [--light]` → `dcc_batch.py max` (shared session lock, `3dsmaxbatch.exe`). The panel is a
real `AgrPanel` in Max's own Qt, grabbed offscreen (batch has no main window, so it floats).
Not run: the interactive MZP install + menu (`drive_agr_tools_ui_native.py`) — it refuses while any
`3dsmax.exe` runs, and two user Max 2024 sessions were open during this card.
