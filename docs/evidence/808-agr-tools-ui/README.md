# #808 AGR Tools 0.6.0 native UI evidence

Synthetic scenes only (1000 generated boxes `SM_Synthetic_NNNN_Main`). Interactive `3dsmax.exe -silent -U PythonHost
tests/max_tools/run_agr_tools_ui_native.py`, driven by `tests/max_tools/drive_agr_tools_ui_native.py` (live-Max lock,
bundle install into `%APPDATA%/Autodesk/ApplicationPlugins`, uninstall, leftover diff).

| Run | Max | Theme | Result |
| --- | --- | --- | --- |
| native6 | 2026.3, PySide6 6.5.3, Python 3.11.12 | Dark | 29 PASS, 0 FAIL/ERROR (leaves dock area 1 + ini for native7) |
| native7 | 2026.3 | Light (`ame-light.clrx`, restored after) | 30 PASS incl. dock position from previous session |
| native9_2024 | 2024.2.5, PySide2 5.15.1, Python 3.10.14 | Dark | 25 PASS, SKIP menu (no CuiMenuManager < 2025) |
| mzp-native-2026 | 2026.3 batch | — | 0.4.0/0.5.0 native runners on the 0.6.0 MZP: AGR_NATIVE_COMPLETE, AGR_CHECKS_COMPLETE |

Max exit code 0xC0000409 after `quitMax` also occurs with an empty script and no AGR bundle (baseline run), so it
is not caused by AGR Tools.

Binaries (screenshots, bundle ZIP, MZP) are on Google Drive `G:/Мой диск/AGR-evidence/808-ui-native/` with
`SHA256SUMS.txt`. Native runs used bundle `4097e6ca849db19e3257ae10dc6a23dc147fa71cac4dba413620539300e85853`
and MZP `a0159e35ac9b26a6e4a6231cac374ad5a8868a292404e67261f7320015f76de2` (each rebuilt twice, identical).
Final branch head adds one pure-Python change after those runs (a cancelled batch report is `status: fail`,
`ui_model.run_batched`, unit-tested red/green): bundle `16bdd2ac4f71074b27b07661f48edccd375d26e5dd1b8fd25e953f60f67fda10`,
MZP `ce19758e74baad1c8818ce6b516676746a6c7fe0e78fdfd10f3c474eaa91c6b4`. A re-run in Max was not possible: another
3dsmax.exe session (not this card's) was open, and the driver refuses to start next to it.
