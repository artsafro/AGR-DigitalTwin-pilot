# Visual review publisher (#348)

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

`pending.json` uses UTF-8 JSON and atomic replace. All queue reads and
read-modify-write operations serialize through `.pending-lock`; a stale lock
times out rather than stealing another publisher's ownership. Inspect a stale lock manually before removing it.
Malformed JSON, duplicate keys and non-finite values are rejected unchanged.

Cleanup defaults to dry-run. `--apply` is destructive: inspect the listing first.
Only immediate `ci-receipt-*` and `t_*` directories older than the threshold are
eligible. Review/Flora stores and directories containing manifest-referenced
assets are protected; manifests are discovered recursively under `library/`.
Relative asset paths, including bare names such as `model.max` or `textures`, resolve from the manifest directory; absolute and relative
directory aliases resolve to the physical library before protection. Reparse candidates
are excluded. Files that merely have a scratch-directory name are ignored.

## Decision proposal

Proposed **D153** (D151 is used by open PR #372, D152 by open PR #380), not an approved new user decision: record the issue's review
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
| 24 concurrent appends / 8 threads, including slow native readers | all 24 rows retained | `test_parallel_append_preserves_all_entries`, `test_parallel_publish_preserves_rows_with_slow_queue_readers` |
| Known/unknown task verdict | update known, unknown error without writes | `test_verdict_updates_one_entry_and_rejects_unknown` |
| Old scratch, exact age threshold, nonfinite days | dry-run/default, strictly old only, invalid days error | `test_cleanup_dry_run_is_default_and_apply_deletes_only_old_scratch`, `test_exact_threshold_nan_and_empty_days_do_not_delete` |
| Review/Flora/ground manifest/relative manifest/file | protected paths and files retained | `test_cleanup_never_touches_review_flora_or_manifest_ground`, `test_cleanup_ignores_files_and_resolves_relative_manifest_paths` |
| Generated invalid slugs + protected scratch mix (seed 348) | unchanged store, excluded paths retained | `test_brute_force_escapes_and_protected_names` |
| Absolute/relative library paths through a Windows junction; dry-run, apply, repeat | physical library untouched; unrelated old scratch removed once | `test_cleanup_protects_manifest_library_through_directory_alias` |
| Renderer unavailable | error, never generate a synthetic preview | `test_render_failure_never_fabricates_preview` |
| Installed Max | FBX materials, framed camera, saved scene readback, actual preview | `test_max_dependent_merge_skips_when_max_absent` |
| Manifest `{"scene": "model.max"}` / `./model.max` / bare dir / absolute + relative junction; dry-run, apply, repeat | library kept in every form; only `ci-receipt-delete` listed then removed once | `test_cleanup_protects_bare_and_aliased_manifest_assets` |
| FBX with meshes named `Review_Camera`, `Review_Target` + `Control_Box` (real headless Max) | all 3 meshes in saved scene, 1 camera with a free name, render by that camera | `test_real_max_keeps_fbx_mesh_named_review_camera`, `test_max_job_never_deletes_source_nodes_named_like_review_camera` |

## DCC execution and verified publications

Publication defaults to **headless 3dsmaxbatch 2026** (2024 only when 2026 is
absent), through `dcc_batch.py` and its shared session lock. It never probes or
changes the user's live document or bridge configuration. COORDINATION_RULES 27
allows copy-based headless audits beside the safe-mode GUI. The live adapter is
not selected: the report writer is forbidden by live SAFE_MODE.

The Max job imports FBX materials, normalizes system units to metres, frames a
review-only camera, saves and reloads the scene, compares mesh/UV/material/
transform inventory, and renders a real PNG when none was supplied. Rendering
failure aborts publication; there is no synthetic preview fallback.

Verified 2026-10-20 with headless 3ds Max 2026.3 (build 28000):

- Ground v014, **final VPM with UCX**, source
  `C:/x/t_d94665f2/ground_v014/vpm_ucx/SM_Vatutino_Ground.fbx`:
  `C:/x/review/2026-10-20/348-ground-v014-review-v002/348-ground-v014-review-v002.max`.
  Final-path readback: 716 geometry nodes, 55,131 faces, 65,759 UV vertices;
  source uses placeholder materials (zero bitmap maps).
- Flora v003, source `C:/x/flora-library/v003/flora-library-v003.max`:
  `C:/x/review/2026-10-20/348-flora-library-v003-review-v002/348-flora-library-v003-review-v002.max`.
  Final-path readback: 99 geometry nodes, 42,601 faces, 97,375 UV vertices;
  all 122 bitmap paths exist.

Both final scenes reload with metre system units, scale 1.0, `Review_Camera`,
640x360 rendered previews, and README. Both were appended to pending.json;
prior Cursor publications were preserved without overwrite or acceptance.
Native startup emits an existing PolyUnwrapper autoload error (handled by the
shared wrapper), and Flora reports a legacy mental-ray custom-attribute DLL
warning; the job report and independent final-path readback completed.

These are internal review copies, not approved delivery packages. No visual
acceptance, botanical confirmation, final delivery QA or user verdict is claimed.
Ground's upstream limitations and Flora catalogue stand-ins/unverified identities
remain unchanged. The user must inspect the scenes before recording a verdict.

Cleanup `--days 7` dry-run found zero eligible directories on 2026-10-20; nothing
was deleted. Local machine evidence: `tmp/review-readback-v002.json`,
`tmp/review-readback-dcc-v002.json`, `tmp/review-cleanup-dry-run-v002.txt`.
