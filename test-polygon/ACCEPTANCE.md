# Acceptance table

Review round 1 of PR #887 (issue #885). Result is the offline pytest run on this worktree.
Live Max is not part of these rows.

| # | Acceptance point (quote from the issue/card) | Input (exact) | Expected output | Test | Result |
|---|---|---|---|---|---|
| R1 | "Known bug shown as OK. … A known-bug row prints `НЕ OK (известная ошибка #886)`; report.json and the summary line get a separate known_bug count (distinct from mismatches; exit code stays = mismatches only)" | expected `fail [missing_map]` + `known_bug {got_expect: pass, got_codes: []}`, live `pass []` for `scene.census` / `SM_Polygon_007_Main` | row result `НЕ OK (известная ошибка #886)`, not `OK`; `known_bug` count = 1; mismatches for that row = 0 | `tests/max_tools/test_polygon_compare.py::test_known_bug_live_pass_is_not_ok_and_counts_apart` | pass |
| R2 | "compare_report([{name:'A',expect:'pass',codes:[]}], {'status':'fail','objects':[{'name':'A','findings':[]}]}) returns [] today. Mirror claimed_pass: a report status of fail with no derived codes gives mismatch claimed_fail" | `[{name:'A', expect:'pass', codes:[]}]` and `{'status':'fail','objects':[{'name':'A','findings':[]}]}` | mismatch kind `claimed_fail` | `tests/max_tools/test_polygon_compare.py::test_claimed_fail_when_status_fail_has_no_codes` | pass |
| R3 | "export.checked and export.cleanup lack a PASS station … cleanup apply runs on a copy (apply_status pass) as a reported row, then the checked export runs on the cleaned copy into a NEW path with FBX readback, expected pass" | `expected/export.cleanup.json` and `expected/export.checked.json`; copy name `SM_Polygon_001_Main_AGR_export_`; report `status pass`, `findings []`, `plan.readback` null | both buttons have a `pass` row and a `fail` row; missing readback is mismatch kind `readback`; existing `export-pass/<copy>.fbx` is refused | `tests/max_tools/test_polygon_export_pass.py::test_cleanup_and_checked_export_have_pass_and_fail_rows`, `test_export_pass_without_readback_is_a_mismatch`, `test_checked_export_target_is_a_new_fbx_path`, `test_missing_produced_export_run_is_a_mismatch` | pass |
| E4 | edge: empty input | `{}`, `None`, `{'status':'pass','objects':[]}` against expected object `A` | mismatch kind `empty` | `tests/max_tools/test_polygon_compare.py::test_empty_report_is_a_mismatch` | pass |
| E5 | edge: malformed / partial input | report object `extra` set to NaN, +Inf, -Inf | mismatch kind `non_finite`; never a pass | `tests/max_tools/test_polygon_compare.py::test_nan_and_inf_are_mismatches_and_never_a_pass` | pass |
| E5b | edge: not_run | `plan.findings[0].status == not_run` for `__scene__` | mismatch kind `not_run` | `tests/max_tools/test_polygon_compare.py::test_not_run_and_claimed_pass_are_mismatches` | pass |
| E6 | no false positive on an unknown button | `load_expected('no-such-button')` | `KeyError` naming `no-such-button` | `tests/max_tools/test_polygon_compare.py::test_unmapped_button_is_an_error_naming_it` | pass |
| E6b | path alias: output inside the input, or report and temp the same file | `check_paths(src, src/out, …)` and `check_paths(src, out, same.json, same.json)` | `SystemExit`; the input file is unchanged; nothing is created | `tests/max_tools/test_polygon_paths.py::test_output_inside_input_and_same_file_aliases_are_refused` | pass |

Totals: 8 rows, 11 tests, 8/8 pass. Full suite: filled after `suite_slot.py`.
