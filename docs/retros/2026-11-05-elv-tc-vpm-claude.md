# Retro 2026-11-05: job elv-tc-vpm — VPM OKS «СРЕDА», Elevatornaya 1A (Claude version)

Job `jobs/elv-tc-vpm/TASK.md`, branch `job/elv-tc-vpm`, PR #969. Task: a VPM-only OKS package from a Revit 2023 FBX
(595k tris, no materials) and the AGR booklet (42 sheets). Later a customer TZ arrived (PureRef board, their blend
scene, their blank ZIP). NPM was out of scope.

Sources: the main session transcript `271fa1bc-…jsonl` and its 24 subagent transcripts. Each was parsed by a script,
so the numbers below come from timestamps, not memory. Also used: `git log main..job/elv-tc-vpm` (26 commits),
`TASK.md`, `outputs/*/` and `docs/decisions.md` D201–D200. Times are local (UTC+1).

Numbers: wall-clock **20:14 → 12:33, 16 h 19 min**. Take out the night (01:20 → 07:02, 5 h 42 min) and the
session ran **~10.6 h**. **24 background agents** ran **~9.3 h** in total, and **34 user messages** came in: 7 of
them were about the permission/YOLO detour, 6 were acceptances. There were 2 context compactions (02:15, 10:11),
2 merge conflicts with `main`, 2 full test-suite runs (the first failed, the second took 56 min), 5 delivery
versions and 8 builds. The user accepted every version shown to him on the first look (pilot, v002, v003, v004,
v005), and the job as a whole at 12:33. After «можно отдавать» he still found 7 defects, listed in section 3.
`passed` stays false: the FNO code/name and the УКЭП `.sig` must come from the customer, and SINTEZ has not been
rerun on v005.

## 1. Timeline

| Phase | Wall-clock | Agents (min) | User wait | Result |
|---|---|---|---|---|
| Intake | 20:14–21:24 (70 min) | rules 3, booklet 3, FBX inventory 6, FBX↔album 28, windows/finish map 20, D15 images 10 (one more killed) | ~15 min (answers 20:29, 20:33; D15 21:01–21:24) | FBX matches the album to 1 mm, so FBX is primary. 212 duplicates and ~3500 interior objects to delete; disputes D01–D16 |
| Permission detour | 21:27–21:35 (8 min) | — | user-driven | allowlist, `blender -b` / `py -3` forms, `/yolo` `/safe`; session switched to bypass |
| Pilot И-А | 21:24–22:52 (88 min) | clean copy + parts 18, library ELV-01..17 15, build 42, UV/UDIM/textures 20 | Gate 1 parts 1 min; acceptance 4 min | 18.8k tris, xView 0. «Пилот принимаю» 22:52, commit `0baf02a4` |
| Whole building | 22:52–01:20 (148 min) | geometry 42, lighting layout 14 (parallel), lights + door + full UV/textures 53, UCX/pivot/GeoJSON/package v001 16, V004 classify + fix + delivery v002 34 | 5 min (23:40 «Геометрией») | v001 failed V004 with 8 101 self-intersections; v002 got it down to 4. V011 open (MSK/FNO) |
| Night | 01:20–07:02 | — | 5 h 42 min | — |
| v002 acceptance | 07:02–07:50 (48 min) | renders day/night 11, Max 2024 xView 5/2 mm 26 | 17 min (questions 07:03 → «Принимаю все» 07:20) | xView 0/0 on 962 meshes; «Принимаю всё» 07:49 |
| Push / PR | 07:50–08:18 (28 min) | — | — | merge conflict (`decisions.md`, `window_types.json`); full suite run 1 failed on 2 zip tests (pytest junk dir in the repo); PR #969. Run 2 took 56 min in the background, to 09:16 |
| Customer TZ analysis | 08:18–09:16 (58 min) | PureRef extract 9, blank vs ours 14, clarification sheets 25 | 3 + 5 min | PureRef 2.x is a page DB, so signature carving failed and a page reader was written. The blank is the same building (IoU 97–98 %) with nothing the TZ asks for. Our base kept |
| v003 (name, GeoJSON, 7024, strips, capsules, doors) | 09:16–10:23 (67 min) | build v007 + delivery v003 **65** (17 min of it polling the Max xView gate) | 1 min | 41 978 tris, xView 0/0, SINTEZ fails only on FNO/УКЭП. Wood #C4ABAA flagged pink by us |
| v004 (wood colour) | 10:23–10:44 (21 min) | tex v005 + delivery v004 18 | 1 min | #C1AE93; geometry hash-identical to v003, so the Max xView rerun was skipped. «Принимаю» |
| Max review | 10:44–11:09 (25 min) | — | user in Max ~10 min | v004 opened in its own Max 2026; the UDIM Viewer 1.4 launch failed once (8 min). User: quads + 4 screenshots |
| v005 (joints, strip, corner glass) | 11:09–12:20 (71 min) | build v008 + delivery v005 **65** | 1 min | D198 work FBX; 423 → 4 unmatched joint crossings; P44 34 → 3 meshes; 106 corner panes as shells. Second merge conflict: D196 taken by `main`, renumbered (4 min) |
| Final view + acceptance | 12:20–12:33 | — | — | v005 work FBX + UDIM Viewer in Max 2026; «Глобально работу я принимаю» |

Spent by kind (active ~10.6 h): background build/QA agents **~6.5 h** of the critical path, analysis agents
**~2.8 h** (most of it in parallel), my own coordination and git work **~1 h**, waiting on the user in daytime
**~1 h**. Rework rounds caused by defects (v001→v002, v003→v004, v004→v005) cost **~2.1 h** of wall-clock.

## 2. What was slow and why

| # | Symptom | Cost | Root cause | Evidence |
|---|---|---|---|---|
| S1 | Build agents ran 42–65 min each (v003 65, v008 65, lights/UV 53, building 42, pilot 42) | ~4.5 h critical path | Every round is a fresh agent. It rereads the context, writes the next versioned copy of the pipeline (`build_full_v00N.py`, `uv_tex_full_v00N.py`, `delivery_export_v00N.py`, `package_vpm_v00N.py` …), regenerates all textures, re-exports, repackages, and reruns every gate, even for 3 local fixes. The v008 agent waited on tools for only 16 of its 65 min; the other ~49 min went into authoring | subagents `a2072f2f` 211 tool calls, `ab62f9fd` 126; `scripts/` holds v001–v008 copies |
| S2 | 3ds Max xView gate ~23 min per run (`3dsmaxbatch` 2024, 1395 s), run 3×; the v003 agent polled it in 3-min `sleep` blocks for 17 min | ~70 min total, ~17 min on the critical path in v003 | Gate runs on all 961 nodes including 959 UCX boxes; the agent blocks instead of continuing other work | `a78efec6` final report; `a2072f2f` 10:03–10:19 |
| S3 | Full test suite: run 1 failed after ~25 min (2 zip tests), run 2 took 56 min (17 836 passed) | ~80 min machine time, PR evidence late | Repo-wide suite for a job branch; pytest temp dir inside the repo tripped `test_zip_deflate_end_state_controls`; fixed by `--basetemp` in the scratchpad | transcript 08:16, 09:16 (`3389.33s (0:56:29)`) |
| S4 | Rework rounds after defects | ~2.1 h (34 + 21 + 71 min) | Section 3: our checks do not measure what the user looks at (pattern continuity, element continuity, topology flow, gaps) | v001→v002, v003→v004, v004→v005 |
| S5 | Merge conflicts on decision IDs, twice | ~10 min, plus `sync_with_base_branch` refused (sandbox-protected files) | Decision IDs are global and sequential, so a long-lived job branch collides with `main` (D196 taken) and every reference has to be renumbered | commits `0beef6f0`, `5a8166bc` |
| S6 | Permission prompts mid-intake | ~8 min + agents re-told the command forms | Allow-list did not cover background Blender / `py -3` / `uv run`; fixed locally, then `/yolo` | 21:27–21:35 |
| S7 | D15 «dispute» was a misread of our own first pass; the user's «принимаю только d15» was misread too, and one agent was killed | ~23 min | First comparison read the album at the wrong axis; I took «only D15» as «accept only D15» | 21:01–21:24; `a5f498e3` «в первом разборе была ошибка» |
| S8 | Max launch for viewing | ~8 min, 1 rerun; 4 versions of `open_view_max2026_v00N.ms` in one day | UDIM Viewer 1.4 defines its rollout in its own scope, so the launcher could not find the dialog; Cyrillic paths forced ASCII staging (`C:\x\elv_view_v00N`, `C:\x\tools\UDIM_Viewer_V1.4.ms`) | 10:52–11:00 |
| S9 | PureRef 2.x board | ~5 min of a 9-min agent | `.pur` 2.x is a 4 KiB-page database; carving by PNG signatures returns broken images | `a371a9e5`, `pur_extract_v002.py` |

Small items: 2 compactions, so the summary was rebuilt twice. Every subagent tried `update_plan` once and got a hook
error. Bash heredoc quoting failed 4×.

## 3. Defects found by the user after we called the work done

| # | Defect | Found | Cost | Why our checks missed it | Check that would catch it |
|---|---|---|---|---|---|
| F1 | Texture joints do not meet on the upper rows (under the parapet); 423 unmatched crossings on 95 edges, 31 planes / 705 m² with mixed phases | Max review 11:01 (screenshot 1) | most of the 71-min v005 round | `uv_tex_full_v007.py` picked the joint phase per face. Faces with no FBX joints nearby fell back to `min(u) − 3 cm`. Our gates (validator, xView, `uv_qa`: density, mirror, fallback) look at one face at a time, and the contact-sheet renders were too small to show a 20 mm joint | `joint_continuity_v008.py` (unmatched crossings across shared edges, phases per plane) as a gate on every textured build, plus close-up renders of the parapet and corners |
| F2 | Cover strip P44 cut into 34 pieces | Max review | part of v005 | v003 resolved clashes with lights/Arktos/joints by cutting the strip with 6 mm gaps, the cheapest way to keep V004/xView at 0. No check compares connected components per part with the parts list | per-part component count vs `expected_pieces` in the parts list; rule: on a clash, move the minor element, never cut the continuous one |
| F3 | Corner glass built as closed solids (edge faces) instead of a 6 mm two-face shell | Max review | part of v005 | xView/validator pass closed boxes; no rule or check describes how glass topology should look | MainGlass check: each pane has 2 opposite faces and 0 edge faces |
| F4 | Wood #C4ABAA reads pink | flagged by us in the v003 report; user agreed | one delivery round, 21 min | Colour taken from an underexposed photo (hue from the photo, lightness from RAL 1001). We noticed only on the finished renders | a swatch sheet (candidate vs booklet render vs accepted colour, with ΔE) before the build, not after the package |
| F5 | Hand-off was triangulated; hard to edit | 11:01 «я хочу геометрию получать не триангулированную…» | 1 round-trip, small | [D152] keeps quads only in the master; the review artefact was never defined, so the user got the delivered FBX | **[D198] (user rule)**: a non-triangulated work FBX next to every delivery, read back against the package |
| F6 | Edge loops / rings stop mid-run (welded, but not carried on) | 12:33 «кое-где идет луп, потом он обрывается… хочется луп этот продлить» | user fixes it by hand | Parts are generated separately and then welded. Closed-mesh, open-edge and xView checks all pass on such a mesh | **[D200] (user rule)**: count T-vertices / valence-3 vertices inside flat quad regions of the work FBX; report and fix before the hand-off |
| F7 | Decor floats on a stand-off instead of a 10–20 mm embed | 12:33 «…висят в воздухе… лучше делать… врезку… на 10 на 20 миллиметров» | user fixes it by hand | We chose the 6 mm stand-off ourselves (v002, [D201]) because V004 counts embeds as self-intersections. The user accepted the recommendation at 07:20 without seeing a close-up of the gap. The validator-vs-rule conflict (#44) was settled on the validator's side | **[D199] (user rule)**: embed 10–20 mm and budget the V004 count per job; a gap check that flags any attachment 1–30 mm off its host |

Pattern: our gates prove the file is legal (validator, xView, readback, SINTEZ). Nothing proves it looks finished
to a modeller in Max (continuous patterns, elements and loops; no gaps; editable topology). All 7 defects are in
that second class.

## 4. What went well

- Intake took 70 min with 3 parallel readers (3–6 min each). The 1 mm FBX↔album match was measured on 67 columns,
  not assumed.
- Pilot first, then the whole building. The pilot was accepted 88 min after «начинай». By 01:20 the whole building
  was done: textures, 498 lights from the vector PDF, 960 UCX, packaged.
- The V004 failure (8 101) was classified before fixing: 3 real defects (rafters, box-in-box shafts, open face) and
  the rest embeds. Nothing was suppressed.
- The customer blank analysis was sound. The PureRef 2.x reader works; the overlay gives IoU 97–98 %; the
  validator compared both packages. Every recommendation was accepted, and our model stayed the base.
- v004 proved the geometry hash-identical to v003 and skipped a 23-min Max gate on that evidence.
- v005 fixed the root cause in the generator, not the symptom, and added a checker with before/after numbers.
- Max was always opened in our own separate process; the user's open sessions were never touched.
- Every version shown was accepted at first sight. Daytime user wait totalled ~1 h; the user answered within minutes.

## 5. What a faster run would have looked like (same inputs)

1. Intake + pilot as done (~2.5 h). The pilot check also covers what the user checks in Max: the work FBX in quads
   [D198], joint continuity, element and loop continuity [D200], and embeds [D199].
2. Whole building with the same checks before the package. No v001→v002 round: embeds planned from the start.
3. TZ round as done (58 min).
4. v003 as one in-place patch of the pipeline: the wood swatch decided before the build, strips and corner glass
   continuous by rule, quick gates in the loop, Max xView once on the final candidate.

Estimate: the v003→v004 and v004→v005 rounds disappear (~1.5 h). Build agents shrink by ~30 min each through the
fast path. That is ~7.5 h active instead of ~10.6 h, with no defects left for the user's hands.

## 6. What to change (ranked by time saved)

| # | Change | Where | Saves | Status |
|---|---|---|---|---|
| 1 | **Look-finished gate** before any hand-off: joint continuity (promote `joint_continuity_v008.py`), components per part vs parts list, glass shells (2 faces), loop terminations / T-vertices in flat quad regions, attachment gap 1–30 mm. Runs on the work FBX | `tools/qa/` + `validate-delivery` skill; Codex to generalise (`docs/backlog.md`) | ~1.5 h per job (F1–F3, F6, F7) | **Proposal**; `joint_continuity_v008.py` exists in the job |
| 2 | **Rework fast path**: patch the generator in place (no new `_v00N` copy of the whole pipeline), regenerate only the affected tiles/parts, run quick gates (Blender xView, validator, look-finished); Max xView + SINTEZ only on the final candidate | `docs/procedure/TASK_TO_MODEL.md`, build agent prompt | ~30–40 min per round (S1) | **Proposal** |
| 3 | User rules as defaults: work FBX in quads next to every delivery | `docs/domain/export-import.md` | 1 round-trip per job | **User rule [D198]**, recorded |
| 4 | Embed decor/attachments 10–20 mm; plan the V004 count per job instead of a stand-off | `docs/domain/geometry.md`, conflicts #44 | avoids a v001→v002-type round (~35 min) and hand-fixing | **User rule [D199]**, recorded; geometry.md and conflicts wording **open** |
| 5 | Continue edge loops and rings; a loop ending mid-run is a defect | `docs/domain/geometry.md` + check in #1 | hand-fixing time | **User rule [D200]**, recorded |
| 6 | Clash rule: move the minor element, never cut a continuous one (strip, cornice, parapet) | `docs/domain/geometry.md` | part of a round (F2) | **Proposal** |
| 7 | Max xView gate on Main/MainGlass only (UCX checked by its own rule); the agent keeps working while it runs, no sleep-polling | `xview_max_gate` script → shared tool | ~15 min per run (S2) | **Proposal** |
| 8 | Full suite once per PR, in the background, `--basetemp` outside the repo by default | `docs/agents/WORKFLOW.md` author receipts, `suite_slot.py` | ~25 min failed run (S3) | **Proposal** (a narrower suite for job-only diffs needs a decision) |
| 9 | Colour pick from a photo → swatch sheet with ΔE to references, approved before the build | job procedure, materials.md | ~20 min (F4) | **Proposal** |
| 10 | Shared Max viewer launcher: ASCII staging, UDIM Viewer rollout lookup, status file, own process | `adapters/max/` or `tools/`, CAPABILITIES.md | ~10 min per Max open (S8) | **Proposal**; 4 job scripts to merge |
| 11 | Job-local decision IDs until merge (or allocation at merge) | `docs/decisions.md` procedure, test_decisions | ~10 min per conflict (S5) | **Proposal** |

None of the proposals is applied in this branch. D201–D200 are recorded; the rest waits for «да».

## 7. Questions to the user

1. Should the look-finished gate (#1) block a hand-off, or only report? Blocking adds ~5 min per build.
2. In rework rounds, is it fine to skip Max xView and SINTEZ until the final candidate (#2, #7)? The final
   package would still pass both before it goes out.
3. With [D199] on embeds, V004 counts each embed. Do we raise the per-job V004 tolerance, or document the embeds as
   an accepted deviation in each delivery report? This decides conflicts #44.
