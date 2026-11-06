# #979 base tests: which assertions still break when branches commit their station fragments

Research card t_9ec66fe1, 2026-11-05. Subject: `tests/max_tools/test_agr_tools_edits_090.py` on `origin/main` @ `bc5df513`.
All results come from commands I ran myself in scratch worktrees under `C:/x/t_9ec66fe1/`. Nothing was pushed from them, and the test file was not edited.

## Summary

- Not every branch named on the card still exists. Branch B (#994) and branch D (#990) are already merged. No `origin/improve/issue-979-*` branch exists yet for C, E1, E2 or E3. Issue #979 itself is **closed**, but A, C and E are still outstanding.
- Of the remaining branches, `improve/issue-979-place` (branch A, open PR #995) merges cleanly with `origin/main`. The base test file then gives **51 passed, 15 skipped, 0 failed** (`origin/main` alone: 56 passed, 10 skipped). The five extra skips are the five A tools; their stub checks now skip by design.
- `improve/issue-979-fragment-tests` (closed PR #987, a duplicate) **conflicts** with `origin/main` in the test file. That is class (c). Its fix already landed through #988 and #992, so the branch should be deleted rather than merged.
- To see what C and E will hit, I committed **synthetic** fragments for C and E into the merged A tree, regenerated `expected/` with `polygon_core.py --branch X`, and re-ran the tests:
  - A fragment with PASS and FAIL rows passes (C full, E1 full).
  - A fragment with only FAIL rows and its own reason passes.
  - A fragment with **no `expected` rows and its own `reason`** **fails** `test_polygon_has_32_new_stations_each_with_expected_and_reason` (C and E3 scenarios). This is class (a), and it is the gap #992 left open.
- Code-side probes:
  - A C glue function (`qa9_max.qa_normals`) is tolerated.
  - The release bump `VERSION = 0.9.0` breaks 3 tests. Two of them are class (a); `test_mcp_has_19_preview_only_tools` needs the MCP bridge constant updated, which is a sync step and not a brittle assertion. This is not a branch fragment, but it will hit whoever ships 0.9.0.

## Findings

### Branch × failing test × class × proposed fix

| Branch (state) | Failing test / assertion | Class | Proposed fragment-agnostic form |
|---|---|---|---|
| A `improve/issue-979-place` + main (PR #995 open) | none (51 passed, 15 skipped) | — | — |
| `improve/issue-979-fragment-tests` (PR #987 closed) | merge CONFLICT in `tests/max_tools/test_agr_tools_edits_090.py` | (c) | Do not merge; already replaced by #988 and #992. Delete the branch. |
| B (#994 merged), D (#990 merged) | none (in main: 56 passed, 10 skipped) | — | — |
| C, E1–E3 (no branch yet). Synthetic fragment with PASS and FAIL rows | none | — | — |
| C/E. Synthetic fragment with FAIL rows only + own `reason` | none | — | — |
| C/E. Synthetic station **without `expected` rows, with own `reason`** (C `qa.normals` + objects; E3 `qa.package` without objects) | `test_polygon_has_32_new_stations_each_with_expected_and_reason`, L482–485: `assert doc['reason'] == 'станция в работе, #979, ветка ' + OWNER[...]`. Got `'ждёт данных улиц (synthetic)'` or `'станция пакета (synthetic)'`. | (a) | Mirror the generator rule (`test-polygon/polygon_core.py` L1088: `st['reason'] if st['reason'].strip() else WORK_REASON`): `frag = core.load_fragments().get(b); own = frag and (frag['expected'] or frag['reason'].strip()); assert doc['reason'].strip() if own else doc['reason'] == core.WORK_REASON.format(core.OWNER[b])`. |
| C (code). Glue `qa_normals` added to `qa9_max.py` | none (50 passed, 16 skipped) | — | — |
| Release 0.9.0 (whoever bumps `VERSION`) | `test_rail_greys_the_09_actions_until_version_090` L365 `m.VERSION.startswith('0.8.')` | (a) | Make it conditional on the version: if `VERSION < 0.9`, the 0.9 rows are greyed out, otherwise they are shown. |
| Release 0.9.0 | `test_committed_macro_and_menu_files_are_generated` | (a) | Not brittle: the committed `agr_tools.mcr`/`menu.ms` must be regenerated in the same commit. |
| Release 0.9.0 | `test_mcp_has_19_preview_only_tools` L431 `bridge.RUNTIME_090 == runtime().VERSION` | (b) when skipped | Not brittle: the bump must also update `src/agr_mcp/max_side/max_bridge.py` `RUNTIME_090`. |

### Latent assertions I did not trigger (static reading, not executed)

| Assertion (line) | Would break when | Class | Fragment-agnostic form |
|---|---|---|---|
| L83 `rt.GLUE_090 == {'atlas_core.py': 'flora_atlas_max.py'}` | a branch maps another core to a non-default glue file (for example C `facade_core` → a shared glue) | (a) | `assert rt.GLUE_090.get('atlas_core.py') == 'flora_atlas_max.py'`; the per-tool `GLUE` check at L81 already pins each row. |
| L109–111 data owner C | C fills `data/procedural_classes.json` (`classes` stays a list: OK) or rewrites `data/streets/PROVENANCE.md` without the literal `Владелец: ветка **C**` | (a) | Keep only `owner == 'C'` and the presence of the file, or have C keep the owner line. |
| L114 `f.count('/') <= 2` | C ships `data/streets/<city>/<file>` | (b) | Intended rule (tested at L117–121); C must keep the data flat. |
| L343 `len(m.ACTIONS) == 61`, L360 `len(icons.names()) == 68` | a branch adds an extra action or icon outside the 19 plan rows | (b) | Plan-locked counts; adding one is out of plan. |
| L453 changelog `subs == ['Основа','A','B','C','D','E1','E2','E3']`, L451 heading `— в работе` | a branch adds its own `### ` sub-heading, or the release renames the 0.9.0 heading | (a) | Branches use `#### ` inside their own section. Release: `assert subs[:8] == [...]` and match the heading as `## 0.9.0 (#979)`. |

### Why the reason-only case is legitimate

- `polygon_core.load_fragments` docstring (L240): «Without expected rows the station is «в работе»». The generator at L1088 nevertheless lets a branch replace the placeholder with its own non-empty `reason`, and validation (L296–297) accepts a reason-only station.
- The test at L482 (`if frag and frag['expected']`) covers only the half of this rule that #992 needed. A branch that commits objects first and expected rows later, or a scene-level station like E3 `qa.package` without polygon objects, will trip it.
- Verified: a C fragment with PASS and FAIL rows really rewrote `expected/qa.normals.json` to `['pass','fail']` with an empty reason, and `write_branch('C')` rewrote all 5 C `expected/*.json` files. The PASS for that scenario is therefore not vacuous.

## How it applies to this repository

- `tests/max_tools/test_agr_tools_edits_090.py`: L482–485 is the one fragment-sensitive assertion left; L83, L109–111 and L451–453 are latent. L365 breaks at the release.
- `test-polygon/polygon_core.py`: L240 (docstring) and L1088 (generator) are the rule the test must mirror. `WORK_REASON` and `OWNER` are already exported; the test should use `core.WORK_REASON` instead of a literal.
- `test-polygon/stations/`: committed fragments are now A (branch only), B and D.
- Reproduce: `C:/x/t_9ec66fe1/probe.py`. It writes a synthetic `stations/<X>.json`, runs `uv run python test-polygon/polygon_core.py --branch X` and then `uv run pytest -q tests/max_tools/test_agr_tools_edits_090.py`, and restores the tree afterwards.

## Proposed next tasks

1. **#979 base test: the station reason follows the generator rule (fragment with reason, no expected rows).**
   - Scope: change only `test_polygon_has_32_new_stations_each_with_expected_and_reason` in `tests/max_tools/test_agr_tools_edits_090.py`, to the form in the table above, using `core.WORK_REASON`.
   - Regression test: a temporary `STATIONS_DIR` with a reason-only C fragment plus `write_branch` into a tmp `EXPECTED`. It fails before the change and passes after.
   - Owner: whichever #979 branch merges next (C or E), or a small standalone PR before them.
   - Value M / effort S.
   - Advances #298: branch C ships `qa.sintez`, which the Site slice SINTEZ verify uses. The link is indirect, because #979 itself is closed.
2. **#979 release 0.9.0 checklist: version bump touches runtime, ui_model, max_bridge, the generated mcr/menu, the rail test and the changelog heading.**
   - Scope: one docs list in `adapters/max/agr_tools/CHANGELOG.md` or the 0.9 plan doc, plus making L365 and L451 depend on the version.
   - Value M / effort S.
   - Archive: no roadmap link.
3. **Delete the stale branch `improve/issue-979-fragment-tests`.**
   - Scope: after user approval, delete the remote branch; PR #987 was closed as a duplicate and the branch conflicts with main.
   - Value S / effort S.
   - Archive: no roadmap link.

## Open questions for the user

1. #979 is closed, but branches C, E1, E2 and E3 have no branch yet and A (#995) is still open. Should C and E continue under #979, or under a new issue?
2. Is a station with objects, its own `reason` and no `expected` rows an intended state for C and E? `polygon_core` allows it; the test does not. If it is not intended, the generator at L1088 should drop the custom reason instead.
3. May the stale remote branch `improve/issue-979-fragment-tests` be deleted?

Sources: all findings are verified locally (commands above); no external sources were used.
