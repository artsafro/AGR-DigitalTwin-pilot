# Job retro: skug26-k5-ac (PR #1008)

Research card t_7bdcde52. Sources: the job's own artifacts on `origin/main` plus one session transcript.
Everything below was read or counted by me unless it is marked *(agent claim)*. Times are local (CET, UTC+1);
the transcript stores UTC.

## Summary

- Job: VPM 4K diffuse with alpha for two 3ds Max conditioner screens (Object004/005), UDIM 1004, hole count
  and texel matching a source FBX. Accepted by the user after one rework: «Видны, принято» (12:55). PR #1008 holds
  docs and job scripts only, and it was merged by artsafro with 0 reviews.
- Every acceptance line in the requirement was met: 4096² RGBA, tile 1004, 1300.0 px/m, and per-face hole counts
  90/25/180/72 from the FBX. One approximation was made: the FBX plates are 0.595 m deep and the model is 0.685 m,
  so the pitch was kept and the margins were split. Export, validation, render and regulation naming were
  out of scope and remain open.
- Time: the session ran 87 min (11:39–13:06). About 55 min (≈63 %) went to 3ds Max instability. Most of that
  was one hang: a MAXScript per-vertex loop on the 4.3 M-face FBX layer. The rest was one crash
  (`resetMaxFile`/`loadMaxFile` over MCP) and polling or waiting for Max. Productive DCC and texture work
  took about 15 min.
- The agent wrote 6 scripts: hole counting by Euler characteristic, per-element hole phase, texture and layout
  generation, UV in MAXScript, UV readback, and per-face hole verification. The UV readback and per-face
  feature verification are general. The texel check duplicated an existing engine module.
- Harness gaps:
  - The Max lessons went to the user-private Claude memory, not to the repo.
  - The 3ds Max skill lists `freeSceneBitmaps()` and `loadMaxFile` without warnings. `freeSceneBitmaps()`
    blacked out the whole building.
  - Intake questions were asked 29 min into the session, after a read-only probe had already hung Max.
  - The PR "Agent trace" says `not measured`.
  - The transcript is not under `logs/transcripts/`.

## 1. Requirement vs result

Sources: `jobs/skug26-k5-ac/STATE.md`, `docs/agr/case_studies/SKUG26_K5_AC_SCREENS_VPM.md`, transcript.
The job has no `object.json` (folder = `STATE.md` + `scripts/`), and `docs/backlog.md` has no entry that names
the job.

| Requirement line (STATE.md "Requirement" + intake) | Result | Numbers / evidence |
|---|---|---|
| VPM texture 4K | met | `T_K5_Diffuse_AC.1004.png` 4096², PNG header read *(STATE)* |
| with alpha channel | met (after rework) | Diffuse RGBA, holes alpha 0. After review the holes were also made dark in RGB (60,60,60), because alpha-only holes were invisible in the viewport |
| polygons laid out in UDIM | met | UV ch1, all 378 faces in tile 1004, 4 stacked islands (uvverify) |
| hole count "as in the screenshot", taken from the FBX layer | met | measured on the FBX: horizontal 18×5 = 90 front, 5×5 = 25 side; vertical 10×18 = 180, 4×18 = 72; every face holds exactly its count: 16×90, 32×25, 110×180, 220×72; 367 holes in the texture |
| match texel | met | 1300.0 px/m on every edge > 5 cm, both objects (user picked 1300 from the 1300–1390 range of his `konderi.psd`) |
| hole geometry equal to the FBX | partly | FBX plates are 0.595 deep and 0.60/1.95 high; the model is 0.685 and 0.58/1.944. Pitch kept, extra depth split between margins: an approximation, not a 1:1 match |
| flat ERM + Normal 4K (intake) | met | ERM (0,128,0) as the old AC ERM, Normal flat; both 4096² RGB |
| save as v003 + PNG, v002 untouched (intake) | met | v003 `FC54F439…`, v002 `DE274321…` hashed. Max crashed once over MCP; the agent checked the v002 mtime (11:29) *(agent claim, transcript 12:35)* |
| other sub-materials untouched | partly | material data was not changed. `freeSceneBitmaps()` blacked out the whole building in the viewport («у меня сейчас все здание черное», 12:57); the agent reloaded the 25 bitmaps (`missing=#()`). The user then said he would sort the OKS materials out himself |
| delivery (FBX export, validate-delivery, cutout render, regulation naming) | not (out of the accepted scope) | listed as open in STATE.md; thin-walled/double-sided not set |

## 2. What worked and what failed

**Keep doing**
- **Source geometry as truth, counted in Python.** One plate was exported to CSV and holes were counted from the
  Euler characteristic (χ = 2 − 2h) with vertex clustering (`holes.py`, scipy). Exporting with bulk
  `polyop.getVerts` took 944 ms for 2.16 M vertices, and one plate took 1.5–1.7 s (transcript 12:32).
- **Phase per element.** The hole-field offset was measured on each of the 126 elements, and 44 mirrored
  vertical units were found. A single template would have got them wrong.
- **Verification by readback, not by "UV written".** `uvdump.ms` → `uvverify.py` counts the alpha holes that
  fall inside every face polygon, so a count mismatch would be caught per face.
- **Intake via one multi-question with recommendations.** The 4 questions were answered in 102 s, all
  "Recommended" (12:08–12:10).
- **Save before risky viewport work.** v003 was saved at 12:50, before any capture.

**Failed, with cause**
1. **Max hang, ~39 min lost (11:40–12:20).**
   - What happened: a "read-only" probe ran `gProbe`/`gTopo` loops over 2.16 M vertices and per-edge
     `getFacesUsingEdge` on the 4.3 M-face FBX layer inside MAXScript. The MCP request timed out at 60 s,
     and four `"alive"` pings timed out too.
   - What it cost: the first Max (PID 340524) went away. The second one (316368) hung on «Untitled».
     The user finally asked «Убей зависший Max»; nothing was left to kill.
   - Cause: there is no size guard before a scripted loop, and the skill does not say "bulk export, then
     Python" for meshes over 1 M faces.
2. **Wrong faces deleted, then a crash (12:33–12:37).**
   - What happened: `polyop.detachFaces delete:true` renumbered the faces, so the second detach used stale
     indices. `max undo` over MCP did not revert the change. `resetMaxFile` + `loadMaxFile` over MCP then
     crashed Max.
   - Cause: the skill's own `maxscript-common-patterns.md` shows `loadMaxFile`/`resetMaxFile #noPrompt` as
     the normal batch pattern.
3. **7 failed UV-script submissions (12:46–12:49).**
   - Errors: MAXScript identifiers are case-insensitive (`n` == `N`, `i` == `I`), which caused `[inf,1595,inf]`
     and a division by the normal; there were also 4 "expected catch" syntax errors from one-line `local`
     usage.
   - Cause: a long script was written inline as one line instead of as a `.ms` file.
4. **First show rejected (12:52).**
   - Causes: `showInViewport=false` on the AC material, and holes that existed only in alpha were invisible
     against the beige wall in Default Shading.
   - Before this, the agent had reported «Готово» based on numbers only, because the agent viewport "has not
     redrawn" (12:50).
5. **Building blacked out (12:57).** `freeSceneBitmaps()` was called to reload the new maps, and it unloads
   every bitmap in the scene. The fix was a reload of the 25 bitmaps.
6. **Viewport capture returned stale frames (12:57).** The file size never changed between captures, so the
   agent fell back to a desktop screenshot.

## 3. What the agent wrote itself

Located in `jobs/skug26-k5-ac/scripts/` (235 lines in total). The inline code in the PR has no `Engine gap:` marker.

| Script | What it does | Engine candidate | Effort |
|---|---|---|---|
| `holes.py` (40) | hole grid of one exported plate: vertex clustering + connected components → hole centres, pitch, D | `dt_ai.geometry` "perforation readout" (holes from Euler χ + clusters). Wait for a second perforated object, as the PR itself says | M |
| `phase.py` (21) | per-element hole-field margins/mirroring from the per-element CSVs | part of the same adapter | S |
| `make_ac_tex.py` (71) | Diffuse RGBA (alpha holes + dark RGB), ERM, Normal at 4096², `layout_AC_1004.json`, preview | the generic part, "draw a hole grid into an island rect at texel T", could go to `dt_ai.materials.textures`; the rest is job-specific | S |
| `uv_ac.ms` (62) | planar UV per element: front + 2 sides, stacked islands, mirroring, 1300 px/m | job-specific; the generic "stack identical panels on one island" belongs to `dt_ai.geometry.uv` | M |
| `uvdump.ms` (15) | dumps per-face UV polygons to CSV. The paths are hard-coded to the session scratch dir | generic Max readback → `src/agr_mcp/max_side` read tool ("dump UV ch N of node to CSV") | S |
| `uvverify.py` (26) | counts alpha-0 blobs inside every face's UV polygon; also UDIM tile membership | generic "features per face from texture + UV" check → `twinqa` (UV/texture checks), usable as an L2 self-check | S |
| inline `gUVCheck` (Max, transcript 12:49) | min/max texel per object, island bounds | **duplicate**: `src/dt_ai/ops/texel_density_readout.py` already computes px/m per face and material against the locked bands (D160 512..1706). Feed it the dumped CSV instead | S |

## 4. Time (87 min, 11:39:25–13:06:15)

| Phase | From–to | Min | What / why |
|---|---|---|---|
| Orientation | 11:39–11:40 | 1 | skill `3dsmax-mcp-dev`, `task-intake.md` |
| Probe Object004/005 + FBX | 11:40–11:41:41 | 1.5 | per-vertex MAXScript loop on 4.3 M faces → timeout |
| **Max hang** | 11:41–12:10 | 28.5 | 4 × "alive" ping (4.5 min), two 600 s polling loops (20 min); useful in parallel: docs read, `konderi.psd` analysed (11:56); intake asked 12:08 |
| Waiting for the user | 12:10–12:22 | 11.5 | agent turn ended; user «Убей зависший Max» 12:20 (no process left), reopened v002 12:22 |
| Polling for Max load | 12:22–12:32 | 10 | one 600 s loop, then stopped manually |
| FBX measure (horizontal) | 12:32–12:33 | 1 | bulk `getVerts` + `holes.py` |
| **Detach error + crash** | 12:33–12:37 | 4 | stale face indices → undo failed → `loadMaxFile` crash; user reopened |
| Reconnect + detach + phase | 12:37–12:46 | 9 | stale pipe to a dead PID, a Max 2026 instance also running; phase batches each over the 60 s MCP timeout (3 timeouts) |
| UV script | 12:46–12:49:26 | 3 | 7 failed submissions (case-insensitive names, syntax) |
| Texel check, maps, save, verify, report | 12:49–12:52 | 2.5 | agent viewport did not redraw → reported on numbers |
| Rework after rejection | 12:52–12:55 | 2 | `showInViewport`, dark RGB holes |
| Case write-up + black building | 12:55–12:58:41 | 3.5 | `freeSceneBitmaps` side effect |
| Commit, push, PR, docs tests | 12:58–13:06 | 7.5 | 3.5 min user gap; docs tests 120 s (72 passed, 1 skipped) |

Max instability (hang + crash + waits + reconnect) took about 55 min, or 63 % of the session. Productive work took
about 15 min. The PR was opened at 13:06 and merged at 00:54 (Nov 6) with no review.

## 5. Harness and process problems

1. **No guard for heavy meshes over MCP.** `execute_maxscript` has a 60 s timeout, but the script keeps running
   in Max, so Max is blocked while the agent pings. Nothing checks the face count before a loop.
2. **The skill teaches the dangerous calls.** `~/.claude/skills/3dsmax-mcp-dev/maxscript-materials-textures.md:218`
   lists `freeSceneBitmaps()` only as "free bitmap caches". `maxscript-common-patterns.md:247,336,340` uses
   `loadMaxFile`/`resetMaxFile` as normal patterns. In this session both calls led to failures: the crash and
   the black building.
3. **Lessons were stored outside the repo.** The detach and `loadMaxFile` lessons were written to
   `~/.claude/projects/C--Users-artsafro--AGR-DigitalTwin-pilot/memory/max-mesh-edit-pitfalls.md` (user-private
   Claude memory). Codex, Antigravity and Kanban workers cannot see that file. The case write-up repeats the
   lessons, but no shared rule or skill changed (PR body: "no shared rule changed").
4. **Intake came after a DCC probe.** `docs/agents/task-intake.md` [D186] says to ask the questions before code.
   The agent read the file at 11:39:33, probed Max at 11:40, and asked at 12:08. The probe was read-only, but it
   was the action that hung Max.
5. **Long blocking polls.** Three 600 s shell loops (`until Responding`) hid the state from the user for 30 min.
   A single "Max is hung, close/kill it?" message at about 11:46 would have saved roughly 20 min.
6. **Agent viewport and capture are unreliable.** It reported "has not redrawn" (12:50) and returned stale
   frames (12:57). No visual self-check was possible before the first report.
7. **Traceability.**
   - The PR "Agent trace" is `not measured`.
   - The transcript is not in `logs/transcripts/` and was found only by grepping `~/.claude/projects`
     for `konderi.psd`.
   - STATE.md has no `Transcript:` line.
   - The branch had an auto name (`vpm-conditioner-texture-4k-a8199d`) and was renamed only at commit time
     (12:59).
8. **Paths in the job scripts point to the session scratch dir** (`uvdump.ms` writes to
   `AppData/Local/Temp/claude/...`), so the scripts cannot be replayed as committed.

## 6. The user's own words (transcript, local time)

- 11:39:25 — task (verbatim in STATE.md): «Object 004 и Object 005. Это двое кондиционер. Мне нужно сделать для
  них VPM текстуру 4К с альфа-каналом. … чтобы попасть и по текселю, и по количеству кружочков. …» + 3 screenshots.
- 12:10:14 — intake answers: «1300 px/m (Recommended)», «Дыры alpha 0, RAL1015 (Recommended)», «Ровные ERM+Normal
  4K (Recommended)», «v003 + PNG рядом (Recommended)».
- 12:20:49 — «Убей зависший Max»
- 12:22:06 — «"…\K5_VPM_textured_UV_v002.max" открываю в 24»
- 12:37:14 — «открыл сцену где есть 004 и 005»
- 12:52:51 — «я не виду альфы и дырочек» + screenshot (rejection of the first result)
- 12:55:03 — «Видны, принято» (acceptance)
- ≈12:56 — «Верни потом только материалы на ОКС». This is quoted by the agent in its question at 12:56:41; the
  original message is not a separate record in the transcript.
- 12:57:05 — «у меня сейчас все здание черное»
- 12:58:16 — «Другое — напишу»
- 12:58:37 — «Короче, все нормально, все, ты справился с задачей, можешь заканчивать. … я уже даже сам разберусь.
  Кондиционеры ты покрасил, главное, дай мне путь к диффузке, которую ты используешь, и все.»
- 12:59:10 — «комить и пуш»; 13:03:22 — "Create PR" command (UI).

## 7. Proposed next tasks and hypotheses

**T1. Max MCP heavy-mesh guard + bulk readback tool.** This adds a read tool in `src/agr_mcp/max_side`
(`max_bridge.py`) that exports a node's vertices, faces and UV channel N to CSV with bulk `polyop.getVerts`
and map calls, with no per-element MAXScript loops. A pre-check refuses scripted loops over nodes above
500 k faces and returns the face count. The tool replaces `uvdump.ms` and the probe loops of this job.
Value: H (it removes the cause of about 40 of the 87 min). Effort: M. Advances #149 (L2 self-checks need
safe readback).

**T2. Move the Max pitfalls into the repo skill.** Copy the four lessons into the repo's Max skill or
`docs/agents/CAPABILITIES.md` (3ds Max MCP route), each as a rule with a reason:
- `freeSceneBitmaps` is global; reload only your own maps.
- `detachFaces delete:true` renumbers faces.
- No `resetMaxFile`/`loadMaxFile` over MCP; ask the user to reopen the file.
- MAXScript names are case-insensitive.

Also flag the conflicting patterns in the user-level skill. Value: M. Effort: S. Archive: no roadmap link.

**T3. `twinqa` check "features per face" + texel from UV dump.** Generalise `uvverify.py` into a check. Inputs:
a UV CSV, a texture, an expected count per face (or per material), and a UDIM tile. Output: per-face findings.
Texel goes through the existing `dt_ai.ops.texel_density_readout`, not a new MAXScript. Unit test on a
synthetic 2-island texture. Value: M. Effort: S. Advances #149.

**T4. Viewport-visibility gate before "done" for texture jobs.** Before the first report the agent must:
- verify `showInViewport` and the bitmap load state;
- capture a frame where the new map is visible, or a desktop screenshot if the agent viewport is stale;
- for alpha cutouts, write the hole colour into RGB too, so the result reads in Default Shading.

Add this to the `validate-delivery`/texture area doc. Value: M. Effort: S. Advances #792 (VPM finish textures).

**T5. Transcript and trace capture for direct-chat jobs.** At commit time, copy or symlink the session JSONL to
`logs/transcripts/job-<job>-pr<N>-<uuid>.jsonl` and add a `Transcript:` line to STATE.md. Fill the PR
"Agent trace" from it. Value: M (retros like this one). Effort: S. Archive: no roadmap link.

**T6 (deferred). Perforation adapter.** This would take hole grids from source geometry and turn them into UDIM
islands with exact counts (`holes.py` + `phase.py` + `make_ac_tex.py`). Start it only when a second perforated
object arrives (PR #1008 "Out of scope"). Effort: L. Archive: no roadmap link.

**Hypotheses for the hypothesizer**

| # | Claim | Metric | Threshold |
|---|---|---|---|
| H1 | Bulk `polyop.getVerts` + Python stays inside the MCP timeout on 4.3 M-face meshes, where per-vertex MAXScript loops do not | wall time per plate readback | < 5 s per plate (observed 1.5–1.7 s; loop > 60 s and hang) |
| H2 | A face-count guard in front of `execute_maxscript` loops prevents DCC hangs | Max hangs or crashes per DCC job session | 0 in the next 5 Max jobs (this job: 1 hang + 1 crash) |
| H3 | Alpha-only holes are not visible in Max Default Shading; alpha + dark RGB is | first-show rejection «не вижу» on cutout textures | 0 rejections for this cause in the next 3 cutout jobs |
| H4 | Asking the intake questions before any DCC call shortens time-to-first-result | minutes from the task message to the first texture | ≤ 30 min (this job: 70 min to the first report at 12:51) |
| H5 | `uvverify` generalised (T3) reproduces this job's counts from the committed layout | per-face counts on a replay of `layout_AC_1004.json` + UV CSV | exactly 16×90, 32×25, 110×180, 220×72 |

## How it applies to this repository

- `jobs/skug26-k5-ac/STATE.md`: add a `Transcript:` line; script paths point to the scratch dir.
- `src/agr_mcp/max_side/max_bridge.py`, `src/agr_mcp/tools.py`: T1.
- `src/twinqa/` UV/texture checks and `src/dt_ai/ops/texel_density_readout.py`: T3.
- `docs/agents/CAPABILITIES.md` (3ds Max MCP route), `.agents/skills/*` Max skill: T2.
- `docs/domain/areas/textures.md`: T4.

## Open questions for the user

1. «Верни потом только материалы на ОКС» was never resolved: you said you would handle it yourself. Is the OKS
   material in v003 correct now, or is it a follow-up?
2. T2: should the Max pitfalls go into the repo skill (shared by all agents)? The alternative is to patch your
   user-level `3dsmax-mcp-dev` skill, which this card may not touch.
3. Is a 500 k-face guard threshold (T1) acceptable, or should the guard only warn?

## Sources

1. `origin/main:jobs/skug26-k5-ac/STATE.md` (read)
2. `origin/main:docs/agr/case_studies/SKUG26_K5_AC_SCREENS_VPM.md` (read)
3. `origin/main:docs/cases.md` row SKUG-26 K5 (read)
4. PR https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/1008: body, file list, 0 reviews, merged by artsafro (read via `gh`)
5. `origin/main:jobs/skug26-k5-ac/scripts/*` (headers read)
6. Transcript `C:/Users/artsafro/.claude/projects/C--Users-artsafro--AGR-DigitalTwin-pilot--claude-worktrees-vpm-conditioner-texture-4k-a8199d/bc045341-1087-412b-aaa6-9286e6f45ee2.jsonl`
   (1279 records; timeline extracted by `C:/x/job-retro-skug26-k5-ac-pr1008/extract.py`, not in git).
   Nothing matching `*skug26-k5-ac*` exists in either `logs/transcripts/` dir.
7. `C:/Users/artsafro/.claude/skills/3dsmax-mcp-dev/*.md` (grep)
8. `C:/Users/artsafro/.claude/projects/C--Users-artsafro--AGR-DigitalTwin-pilot/memory/max-mesh-edit-pitfalls.md` (lines 18–19)
9. `origin/main:src/dt_ai/ops/texel_density_readout.py` (docstring read)
10. `gh issue list --label roadmap` (#149, #298, #349, #352, #425, #426, #792)
