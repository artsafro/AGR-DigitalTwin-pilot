# Issue #1112 — current-menu observation

## Boundary

Offline static check, Max 2026 menu only; no Max connection, UI click, script execution,
menu editing or installation. Source menu was copied unchanged to
`C:/x/t_1ca9121b/myscripts.octopus`. Source and copy SHA-256:
`2ddf39126b7f6008ce517bfb0400b20404163a08d8e666bbd82c752436f1a814`.

Source:
`C:/Users/artsafro/AppData/Local/Autodesk/3dsMax/2026 - 64bit/ENU/scripts/Octopus/octopus/myscripts.octopus`.

Mapping supplied explicitly for this observation:
`userStartupScripts=C:/Users/artsafro/AppData/Local/Autodesk/3dsMax/2026 - 64bit/ENU/scripts/startup`.
This is the standard user startup directory, not a live `getDir` readback. A different
runtime configuration must be supplied/confirmed rather than guessed. The installed
`max_ui_startup.ms` is present here, but none of the four referenced AGR Viz scripts is.
Archived scripts were found under `scripts/max-ui/moved_to_repo_20261108/`; that directory
is not substituted as the startup mapping just to produce passing output.

## Reproduction

```bash
uv run python tools/max/viz/check_octopus_buttons.py C:/x/t_1ca9121b/myscripts.octopus \
  "Clean Mtl" "Smart Attach" "Forest Color" "MultiSub Dedupe" \
  "Master MultiSub" "Viz Materials" "Mat Slots" \
  --max-dir "userStartupScripts=C:/Users/artsafro/AppData/Local/Autodesk/3dsMax/2026 - 64bit/ENU/scripts/startup"
```

Exit **1**, raw JSON: `C:/x/t_1ca9121b/checker-current.json`.

| Label | found | active | command_nonempty | filein_paths_exist | Missing file in mapped startup directory |
|---|---|---|---|---|---|
| Clean Mtl | true | true | true | false | agr_viz_materials.ms |
| Smart Attach | true | true | true | false | agr_viz_materials.ms |
| Forest Color | true | true | true | false | agr_forest_color.ms |
| MultiSub Dedupe | true | true | true | false | agr_viz_materials.ms |
| Master MultiSub | true | true | true | false | agr_viz_materials.ms |
| Viz Materials | true | true | true | false | agr_viz_panel.ms |
| Mat Slots | true | true | true | false | agr_mat_slots.ms |

The requested **seven PASS** evidence is not established. This failure is retained,
not relabelled as a successful installation; installation repair is outside this card.
A decision is required: accept the real failing evidence for this checker-only card,
or provide a corrected menu/environment copy and confirmed target-Max mapping.

## Tests so far

- Tests-first commit `d14a1270`: `uv run pytest -q tests/test_check_octopus_buttons.py
  -p no:cacheprovider --basetemp=C:/x/t_1ca9121b-red`: **1 failed** because checker
  was absent, before implementation.
- Initial literal-only implementation: **1 passed** (inactive fails, same clone active passes).
- Parser expansion RED: **9 failed, 7 passed** (comment-only commands, unresolved/dynamic
  calls, unknown mapping and missing-target naming); lexer/explicit mappings fixed those:
  **16 passed**.
- XML hardening RED: **3 failed, 25 passed** (unknown button tag, DTD entity and duplicate
  command); scoped rejection fixes: **28 passed**.
- Full suite/evals/PR not yet run or opened: held pending the real-data evidence decision;
  the one-full-suite allowance remains unused.

All fixtures are synthetic and all tests invoke the checker in a fresh process.
Read-only hardlink/alias and preexisting `.partial` sentinels retain their bytes;
duplicate requests/labels fail; pass/fail/pass file removal tests reject stale success.
No output-file option exists; a colliding `--output` request is rejected before any writes.
Existence is point-in-time only; the checker does not promise concurrent filesystem locking.

Historical feature source/parser/retro: source not in repo, standalone replacement authorized
by repair comment on card `t_1ca9121b`.
