# xView runner acceptance (#528)

Native Max was not started. Rows below are the contract and the Python mirror of the same rules.
Expected Vyatskaya counts are recorded in `not-measured.json` and were not measured this round.

| Acceptance point | Concrete input | Expected output | Test |
| --- | --- | --- | --- |
| Hardlink output is rejected before any write | `out/a.json` hardlink of `source.max`, jobs.txt with two labels | DumpError naming the alias; source bytes unchanged; no `done.txt` or `failed.txt` | `test_preflight_rejects_hardlink_output_and_duplicate_label` |
| Duplicate labels are rejected before any write | jobs.txt labels `Same` and `same` | DumpError naming the label; no success marker | `test_preflight_rejects_hardlink_output_and_duplicate_label` |
| Cross-job hardlink | `out/b.json` hardlink of input `a.max` | DumpError alias; both sources unchanged | `test_preflight_rejects_cross_job_hardlink` |
| Staging hardlink | non-ASCII `a.max`, temp `xv_<sha>.max` hardlink of input `b` | DumpError alias; no copy over the other input | `test_preflight_rejects_staging_hardlink` |
| Preflight writes nothing on a bad jobs.txt | `jobs.txt` hardlink of the `.max`, and a 3-field line | nonzero error; input bytes unchanged; no `failed.txt` | `test_preflight_rejects_wrong_field_count_and_does_not_delete_input` |
| Native preflight is before createFile | `tools/qa/xview_dump.ms` source | `xv_preflight` call, then `ready = true`, then `createFile`; `GetFileInformationByHandle` present; slot read with `j.count >= 6` | `test_ms_preflight_precedes_writes` |
| Empty jobs.txt | empty file | error (nonce or no inputs); directory unchanged | `test_preflight_empty_jobs_txt_writes_nothing` |
| Control characters and `\|` | label `a\nb`, label `a\|b`, node `n\|weld\ninjected`, slot `1\|2` | `bad field` before `jobs.txt` exists | `test_prepare_rejects_separators_before_write` |
| Unknown slot is named | slot `glass`, slot `0` | DumpError naming the token; no output dir. Slot `2` is field 6 | `test_prepare_names_unmapped_slot` |
| Slot id against a material map | random ids and presence flags | unbound id or name is an error naming it; present id is kept | `test_probe_slot_binding` |
| Receipt matches the native parser | `prepare_run` of two models | `#nonce:` plus six-field lines; `preflight_jobs_txt` returns the same nonce and slot | `test_prepare_receipt_passes_native_preflight` |
| Complete result is the only success | two full native JSON files, matching nonce in `done.txt` | `check_run` returns both; `failed.txt` then fails | `test_check_run_accepts_only_a_complete_success` |
| Error, null, incomplete, wrong label, threshold 0, stale done | `{}`, `{"error":"checker failed"}`, `null`, `{"label":"wrong","saved":true}`, missing keys, `tolFaces` 0, other nonce | DumpError; result bytes unchanged | `test_check_run_rejects_error_null_incomplete_mismatch_and_stale` |
| CLI rejects an error JSON | `--check-run` on `{"error":"checker failed"}`, `{}`, `null`, wrong label | exit 2; result bytes unchanged | `test_check_run_cli_rejects_bad_result` |
| CLI rejects a stale done receipt | `done.txt` nonce differs from `jobs.txt` | exit 2; stderr contains stale | `test_check_run_cli_rejects_stale_done` |
| CLI accepts one real control | full schema for labels a and b, shared nonce | exit 0 | `test_check_run_cli_accepts_a_complete_directory` |
| Repeat run rotates the nonce | success, then `prepare_run` again, then the old nonce written back | new nonce; old done is stale | `test_repeat_run_rotates_nonce` |
| Preparation failure clears success | valid run, then `prepare_run(mode='bad')` | `done.txt` gone; `check_run` fails; source bytes unchanged | `test_prepare_failure_clears_success` |
| Bad mode still does not delete an input | `done.txt` hardlink of `source.max`, mode `bad` | alias error; source and hardlink bytes unchanged; no `jobs.txt` | `test_bad_mode_still_refuses_hardlinked_done_before_any_delete` |
| Partial run is not success | labels a,b,c; b missing; c truncated | error naming b and c | `test_check_run_names_every_missing_label` |
| Same-file probe | 32 layouts, NTFS file index as the oracle | agree, and preflight creates nothing | `test_probe_preflight_inode_identity` |
| Schema probe | 48 mutations of a full result | `check_run` matches the independent schema oracle | `test_probe_done_only_on_all_success` |
| Field probe | 40 labels and node names | control characters and `\|` never produce `jobs.txt` | `test_probe_fields_reject_controls` |
