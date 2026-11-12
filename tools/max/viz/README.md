# AGR Viz — Octopus install verification

## Install check

After editing `myscripts.octopus` (keep a versioned backup first):

1. Run the read-only checker on that menu, requesting **all** installed button labels.
   Supply `--max-dir KEY=PATH` for each `getDir #KEY` used in the commands. Use the
   directory from the target Max configuration, not a directory selected because it
   happens to contain the scripts. This checker never contacts Max or executes MAXScript.

   ```bash
   uv run python tools/max/viz/check_octopus_buttons.py "C:/path/to/myscripts.octopus" \
     "Clean Mtl" "Smart Attach" "Forest Color" "MultiSub Dedupe" \
     "Master MultiSub" "Viz Materials" "Mat Slots" \
     --max-dir "userStartupScripts=C:/path/from/target-Max/scripts/startup"
   ```

2. Require exit 0 and `passed: true` for every requested label. Inspect `found`,
   `active` (the **first**, main action's attribute, not `IsActive` and not a later
   active action), `command_nonempty`, `filein_paths`, and `filein_paths_exist`.
   An inactive clone, duplicate/missing label, empty command, missing file or
   unresolvable `fileIn` is a failed install check. Error messages name missing paths.
3. Verify at least **one button by a real click in Octopus**, observing the expected
   tool/dialog/action. Record label, Max version, menu version/hash and observed result
   before reporting the tools installed. File existence, `fileIn` from the Listener,
   macro registration and this static checker are **not** click verification. Do not
   close the user's scene or restart Max without permission. If a click cannot be
   performed, report `static check only; click not verified`, not `installed`.

## Supported static inputs and limits

The parser supports `OctopusDataWrapper` XML with local and panel buttons and reads
only the first `buttonActionData/actionDataList` command. `active` remains a string
and `filein_paths` a list, matching `docs/agr/inventory/octopus-bindings.json`.
The button's `IsActive` must also be `true`.

Supported `fileIn` arguments are absolute quoted strings (normal MAXScript escapes
or verbatim `@"..."`) and `((getDir #KEY) + "/relative/file.ms")` with an explicit
absolute mapping. Matching is case-insensitive for `fileIn` and `getDir` keys;
button labels are exact. Strings/comments are lexed, not executed. Dynamic expressions,
relative literal paths (Max search context is unknown), DTDs and malformed input fail
closed. Commands without `fileIn` have an empty path list; the file check is vacuous,
not proof that their macros exist or execute successfully. Script contents, macro
availability and arbitrary MAXScript syntax/control flow are not validated. Existence
is a point-in-time observation, not a guarantee against later filesystem changes.

JSON goes only to stdout; exit 1 indicates a check/read/parse failure, exit 2 CLI usage
errors. There is no output-file option, cache or temporary file, so no input is modified.
Capture stdout yourself only to a **new** path that is not the menu or a script input.
For evidence use an unchanged menu copy and preserve its source/copy SHA-256.

## Current-menu finding (#1112)

The unchanged Max 2026 menu copy yields **seven FAIL**, with every requested button
found, active and non-empty. Four referenced scripts are absent from the standard
`ENU/scripts/startup` directory: `agr_viz_materials.ms`, `agr_forest_color.ms`,
`agr_viz_panel.ms`, and `agr_mat_slots.ms`. See
[evidence/issue-1112-current-menu.md](evidence/issue-1112-current-menu.md) for the
mapping, menu hash and per-button results. The mapping is an explicit standard-path
observation, not a live `getDir` readback.

Artem accepted this failing evidence for the checker-only card on 2026-11-12.
It is a correct diagnostic, **not** a successful installation. Installing the missing
scripts belongs to the max-ui tools; no live menu or scene was changed and no real
click was verified by this task. The install gates above remain mandatory.

## Source availability

The historical `feature/viz-material-tools` commit, original inventory parser and
`docs/retros/2026-11-08-viz-material-tools.md` are source not in repo. This small
standalone parser and install guide were authorized by the #1112 card repair note;
this directory does not claim to contain the historical Viz implementation.
