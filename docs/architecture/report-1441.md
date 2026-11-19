# Duplicate register reconciliation — #1441

Кратко: выводы AI Council 15.11 подтверждены по исходникам, спорная кровля KPP1 и упаковщик TEC26
оказались живыми. ЭЛВ **не сдан**, включая v006 вне репозитория (факт Артёма от 2026-11-15 в #1441).
Упаковщики v001–v005 — заменённые черновики; v006 — текущий кандидат, а не историческая сдача.
Возобновление сдачи ELV **не разрешено**: #1104 остаётся parked до слова Артёма.

## Authority and boundary

Base: merged PR #1428, commit `d95bcf37b2171d9781b77a90c98f355047afbd69`.
Council input: [last orchestrator comment on #1424](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1424)
(the issue thread is authoritative; the station-1 findings are dated 2026-11-15 14:00).
This is a source/call-chain audit, not a fresh model run, delivery receipt or user acceptance.
The old ELV PASSPORT sentence calling v005 an accepted candidate is not proof of delivery and no longer
qualifies ELV for `finished_jobs`. Existing job documents and approved assets are not rewritten here.

## Council findings, checked individually

Paths below are relative to the repository. Line numbers refer to the source at the base above;
no job implementation was edited by this reconciliation.

| Finding | Source / current chain | Decision and register effect |
|---|---|---|
| KPP1 `vpm_ucx.py:50` | `build_kpp1.py:26,1013-1022` calls `pieces`, `hull`, convexity and overlap checks | Agree with council: building-specific construction, `own-duty` vs `ucx10_core` gap measurement. #1404 is not thereby completed. |
| PSU275 `vpm_ucx.py:45` | Its generated UCX and overlap check at :51-53 do not calculate minimum gap | Agree: `own-duty`, not a copy of gap measurement. |
| TEC26 `ucx_tri_core.py:44` | `geom_core()` loads `adapters/max/agr_tools/geom_core.py` (:19-33), `triangulate_piece` calls `gc.ucx_plan` | Agree: `wrapper`, with geom_core as its actual owner, not ucx10_core. |
| TEC26 `ucx_triangulate_vpm.py:29` | `import ucx_tri_core as core` (:17), then `core.triangulate_piece` | Agree: wrapper of the local wrapper; the complete chain ends at geom_core.ucx_plan. |
| ELV `ucx_dev_by_part_v001.py:24` | Loads existing meshes; :45-55 measures Main-to-UCX distance | Agree: read-only diagnostic, `own-duty`; remove the false builder / 960 UCX label. |
| SREDA UCX owner | `delivery_export_v005.py:43,227` -> `tools/blender/ucx_build.py` -> `src/dt_ai/geometry/ucx_build.py` | Agree on builder identity; correct the council's word “delivered”: these are candidate exports, not a delivered ELV result. Add missing owner. |
| PSU275 second builder | `scripts/run_oks.sh:22` -> `vpm_stage5_oks.py:75-88`, hulls and meshes at :79-82 | Agree: add separate owner; constructing specified pieces is not the gap checker. Module-level implementation is explicitly labelled `<module>`, not an invented function. |
| `ucx10_core` unused by jobs | Job-local builders above do not call ucx10_core; it remains the Max gap owner | Agree: retain owner, do not misclassify builders as copies of the measuring duty. |
| KPP1 UV vs atlas_core | `run_stage.sh:13` -> `build_kpp1.py:1124-1143` -> `vpm_uv.pack_uv`, period/density-specific VPM work | Agree: `own-duty` vs the NPM atlas owner. The separate `tile_offset` formula remains a live UDIM bypass. |
| TEC26 UV copy | `AC09/run_building.sh:24` -> recipe_adapter -> `build_master.py:34,93-94` -> local vpm_uv | Agree: live copy of KPP1 UV; move to a context owned by KPP1 vpm_uv rather than mislabelling it a duplicate of atlas_core. No existing VPM-copy compaction card is assumed (`step: -`). |
| VPM UDIM in Max | `adapters/max/agr_tools/vpm_max.py:123` uses `vpm_core.build`, with table generation at :206 | Agree: add `vpm_core.py` owner; not a jobs/ caller and not the NPM atlas. |
| Shared VPM package facade | `tools/derive/package_vpm.py:135` calls `package_core._write_zip`, not zip_apply | Agree: wrapper of the writer, not evidence of zip_apply acceptance. No package guarantee is added. |
| Shared NPM package facade | `tools/derive/package_npm.py:28,41` calls zip_plan and _write_zip, not zip_apply | Agree: same writer/acceptance distinction; facade code unchanged. |
| TEC26 local ZIP | `AC09/run_building.sh:28` explicitly executes `$S/package_vpm.py`; S is `../scripts` (:8); `tests/test_shared_tools_1106.py:92-105` preserves that caller | Dispute settled: **live bypass**, not historical. Correct both context-map rows; future compaction targets package_core (#1377 owner). Byte parity with a shared writer is not delegation to it. |
| Shell NPM one-liners | `AC09/run_building.sh:31`, `PSU275/scripts/run_all.sh:28` write ZipFile directly | Agree: scanner currently scans Python files, not Python embedded in shell strings. Known coverage boundary, not a claim of complete packaging compaction. Do not expand the scanner or edit jobs in this audit. |
| SINTEZ KPP1 and TEC26 | `run_agr_checker.py:47` in each script dumps external SINTEZ; KPP1 run_all.sh:31 launches it; TEC26 AC08 pilot records its checker outputs | Agree: `own-duty` vs twinQA validate_package. TEC26 remains a launcher copy of KPP1; its consolidation is still #1379 / PR #1431, not “already compacted”. |
| PSU275 body owner | `scripts/massing_surface.py:18` produces run_body_shell input; `tools/run_body_shell.py:11,40` calls shell_body; `scripts/vpm_stage5.py:87` reads body-shell.json | Agree: add `src/dt_ai/geometry/shell.py`; no claim that geometry has been rebuilt in this audit. |
| KPP1 roof :358-443 | Current `scripts/run_all.sh:20` -> `run_stage.sh:13` -> `build_kpp1.main:1100,1118` -> `roof:421`; constants :358-359 define the local gap/overlap | Dispute settled: **live bypass** of roof_core, no roof_core import/call. Add the precise roof row under roof_core, `step: #1381`. Related seal rows also become live, not historical. `load_spec:194` itself is configuration intake (`own-duty`), not a mesh operation. |

## ELV draft reconciliation

`package_vpm_v006.py:1-10,46-55` preserves the current v006 candidate (okrug fix from #1107), consumes the
v005 export, and reports `package_report_v006.json`. This supersedes packaging v001–v005; it does not
establish a v006 delivery. Migrate this live writer to package_core in compaction; do not execute it now.
The accepted-looking folder names and the word “delivery” in historical script headers are not receipts.

Removing ELV from finished_jobs also exposes its UDIM rows. `TASK.md:174-177` identifies
`uv_tex_full_v008.py` as the current candidate's UV route: its two tile formulas are live, with no assigned
compaction card. Older uv_tex_full / v007 / pilot drafts and the v001 readback are `superseded`; current
readbacks, source probes and render diagnostics are `own-duty`, not delivery claims. All of these rows
carry explicit Russian reasons. No ELV row remains `historical` by relying on the old passport sentence.

## Checker changes and verification limits

### Main integration delta (PR #1484)

The original council findings above describe the audit base. The main merge retains the completed
#1379 SINTEZ/master-QA migration: KPP1/TEC26 shims no longer have duplicate rows; the checker rule
still lists the frozen ELV v003 diagnostic (`own-duty`, not delivered) and PSU275 master QA
(`historical`). The package/VPM maps also keep the frozen ELV diagnostic without a delivery claim.
#1397's migrated UDIM formulas stay removed from the allowlist and live-bypass baseline; the source
raw-tile diagnostic stays `own-duty`. The reconciled registry has 41 live-bypass rows, not the
pre-merge 52. No migrated implementation was reverted; no new decision ID was allocated.

- Explicit `entrypoints` have a canonical existing `.py` owner and a nonempty evidence substring in an
  existing file. They supply shell-command/candidate roots missed by Python imports. No shell interpreter
  or new runtime classifier is introduced; the rest of the existing conservative BFS remains unchanged.
- A `superseded` row needs a Russian reason and must not be reachable. It never requires/creates a
  delivered-job claim. The independent exhaustive status oracle now covers 80 combinations.
- Importlib-loader recognition supports TEC26's existing wrapper; merely printing an owner path does
  not make a helper a wrapper. The existing new-copy and live-bypass ratchets remain active.
- New baseline entries are corrected reachability of existing files, not permission to add new copies.
- Counts in report-1424 are `(at, hash)` copies: TEC26 ZIP has a described row and a pinned row.
  A zero count relative to validate_package/ucx10_core does not complete SINTEZ/UCX construction work.
- #1425 / PR #1444 did not edit the YAML owner inventories (checked its handoff); this change supplies
  the missing owners. Its generator branch is not copied. The only renderer-code delta here recognizes
  the explicit `<module>` owner because PSU275's builder has no top-level function.

## Evidence receipts

Tests-first commit `f4953152`: new regressions **14 failed** before the fix (`tmp/1441-red.log`).
First integration: **505 passed / 20 failed** (`tmp/1441-affected1.log`): missing module-level owner
support, body-index mutation fixtures, the deliberately obsolete “nine historical packagers” assertion,
and the not-yet-refreshed report. Those failures are retained, not relabelled as passing.
Final affected command/counts and eval receipts are recorded on the PR head.
Full suite: deferred to merge batch (rule 68).
No DCC calls, model writes, package writes or delivery acceptance were performed.
