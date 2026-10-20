# Visual review publisher (#348) — work in progress

## Interface

```bash
uv run python tools/review/publish.py --task 348 --slug ground-v014 --fbx SOURCE.fbx --png PREVIEW.png --what "Проверить масштаб и материалы."
uv run python tools/review/verdict.py --task 348 --status changes --note "Уточнить материалы."
uv run python tools/review/cleanup.py --days 7
```

Publication creates `C:/x/review/YYYY-MM-DD/N-slug/` with a Max scene, previews and
README. An existing folder is rejected, not overwritten. Existing `.max` sources
are also accepted through `--fbx`, for the Flora library. The command does not
apply a verdict automatically. `verdict` updates all publications of that task;
use a distinct task number when separate asset verdicts are required.

`pending.json` uses UTF-8 JSON and atomic replace. Read-modify-write operations
serialize through `.pending-lock`; a stale lock times out rather than stealing
another publisher's ownership. Inspect a stale lock manually before removing it.
Malformed JSON, duplicate keys and non-finite values are rejected unchanged.

Cleanup defaults to dry-run. `--apply` is destructive: inspect the listing first.
Only immediate `ci-receipt-*` and `t_*` directories older than the threshold are
eligible. Review/Flora stores and directories containing manifest-referenced
assets are protected; manifests are discovered recursively under `library/`.
Relative asset paths resolve from the manifest directory. Reparse candidates
are excluded. Files that merely have a scratch-directory name are ignored.

## Decision proposal

Proposed **D151**, not an approved new user decision: record the issue's review
folder layout and pending/verdict convention. Recheck the ID against main and
all open PR reservations before adding it to `docs/decisions.md`. No decision-log
or shared workflow edit is included while the proposal is unconfirmed.

## Acceptance table / test seams

The card specifies the CLI, filesystem store and fake Max adapter as public seams.
The initial implementation/tests were inherited from Cursor. The safety tests
were committed and run RED before the corresponding repairs.

| Input | Expected result | Test |
|---|---|---|
| FBX + fake adapter + existing pending row | Max/PNG/README + preserved prior row | `test_publish_creates_review_folder_and_appends_pending` |
| Missing/empty source, empty what, invalid slug/task | error, no publication writes | `test_fail_closed_publish_writes_nothing`, `test_missing_png_and_empty_source_write_nothing` |
| Malformed/duplicate/nonfinite pending JSON | error, original bytes untouched | `test_malformed_pending_is_untouched`, `test_invalid_json_preserves_bytes` |
| Output aliases source by path or hardlink | error, unchanged input | `test_output_path_that_resolves_to_input_writes_nothing`, `test_hardlink_pending_alias_is_untouched` |
| Symlink date folder escapes root | error, no external writes | `test_symlink_escape_writes_nothing` (skips without symlink privilege) |
| Adapter or atomic replace fails | no committed folder or queue update | `test_adapter_failure_leaves_no_folder`, `test_atomic_replace_failure_restores_pending_and_folder` |
| Repeat same publication | reject, first publication preserved | `test_second_publish_same_slug_keeps_one_entry` |
| 24 concurrent appends / 8 threads | all 24 rows retained | `test_parallel_append_preserves_all_entries` |
| Known/unknown task verdict | update known, unknown error without writes | `test_verdict_updates_one_entry_and_rejects_unknown` |
| Old scratch, exact age threshold, nonfinite days | dry-run/default, strictly old only, invalid days error | `test_cleanup_dry_run_is_default_and_apply_deletes_only_old_scratch`, `test_exact_threshold_nan_and_empty_days_do_not_delete` |
| Review/Flora/ground manifest/relative manifest/file | protected paths and files retained | `test_cleanup_never_touches_review_flora_or_manifest_ground`, `test_cleanup_ignores_files_and_resolves_relative_manifest_paths` |
| Generated invalid slugs + protected scratch mix (seed 348) | unchanged store, excluded paths retained | `test_brute_force_escapes_and_protected_names` |
| Renderer unavailable | error, never generate a synthetic preview | `test_render_failure_never_fabricates_preview` |
| Installed Max | FBX materials, framed camera, saved scene readback, actual preview | `test_max_dependent_merge_skips_when_max_absent` |

## Current blocker / recovery

2026-10-20: Max 2024 is reachable through `max_exec.py --ping`, native bridge
`safeMode=true`. The live adapter's self-contained MAXScript was refused before
execution with `SAFE_MODE` because the machine-report writer uses `createFile`.
The bridge source confirms `createfile` is an explicit blocked command. Do not
obfuscate it, switch to another file-writing API, change bridge configuration,
or start headless Max alongside the GUI without user authorization. Live jobs
use hold/fetch to preserve the user's document; batch jobs use `dcc_batch.py`.

Focused result after safety fixes: 35 passed, 1 skipped, 1 DCC failure (SAFE_MODE).
The Max script itself has NOT executed successfully; camera/readback/unit-rescale
and rendered-preview changes still require real Max verification. The full suite
has not been rerun in this recovery attempt. Use `suite_slot.py --card t_5bc043c7`
for the required full run after DCC access is resolved.

Prior Cursor publications exist in `pending.json` under task #348:

- `C:/x/review/2026-10-20/348-ground-v014/348-ground-v014.max`
- `C:/x/review/2026-10-20/348-flora-library-v003/348-flora-library-v003.max`

Existence and file sizes were observed, not accepted as proof of visual correctness.
Do not overwrite them. Publish corrected copies with new slugs after readback.
No visual acceptance, final delivery QA or user verdict is claimed.
