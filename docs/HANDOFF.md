# Handoff — 2026-11-15 16:00

Branch: `job/4bk-k3-vpm` · Commit: `6aa786d9` · Worktree: `C:\Users\artsafro\.AGR-DigitalTwin_pilot\.claude\worktrees\4bk-corpus-k3-modeling-6cfe72` · Job: `4bk-k3`
Transcript: `C:\Users\artsafro\.AGR-DigitalTwin_pilot\logs\transcripts\job-4bk-k3-vpm-pr1443-0a3a9c47-6962-4b43-a975-fa2a4cb6a4ab.jsonl`

<!-- Written by /handover (.claude/commands/handover.md), read by tools/hooks/session_context.py and /takeover.
Keep the `Branch:` line as is (the hook parses it). Facts only, no history: git log and the pull requests hold
that. The whole file stays under 7000 characters so the SessionStart hook passes it in full. Empty section: "-". -->

## Where we are

Job 4bk-k3: VPM of K3 tower floor 1 (A) and the stand-alone stylobate (B), built from Revit view `K3_stylobate_v001`.
- Both are at about 80 %. Artem accepted geometry (A v004, B v003), UV and UCX (A and B v001).
- Artem hand-finished both buildings. The etalon files are `…\63_4BK_vlad\bldA.max` and `bldB.max`.
- The combined scene is `…\63_4BK_vlad\scene_build_A_build_B_v002.max`, with layers Build_A, Build_B, UCX_A and UCX_B.
- Decisions are in `jobs/4bk-k3/TASK.md` and the status in `jobs/4bk-k3/STATE.md` (commit 6aa786d9, PR #1443).
- UCX gates pass on readback: `build\gf_parts\ucx_{A,B}\*_report.json`.

## In progress

- Artem is working on the big tower (typical floors) by hand. Nothing is running on our side.
- Local state outside git, all under `C:\Users\artsafro\Desktop\!3D viz\!А101\63_4BK_vlad\`:
  - `build\gf_parts\`: parts, UV, UCX, checks, `_review\max\` scenes, the analyses `artem_v007_analysis\` and `artem_final_analysis\`;
  - `bldA.max`, `bldB.max`, `scene_build_A_build_B*.max`.
- **Our textures were edited in place.** Artem painted the joints directly into our `_uv\textures_A_v003` Brick and AKP diffuse maps. Our originals exist only as a rebuild in the session scratchpad.
- **Max 2026 processes started by agents may still be open:** 916456, 816344, 924440, 948024, 316280 (combined scene). 936984 and 947044 were Artem's sessions. Close only the agent ones, and only after asking.
- **Stray files the user deletes by hand:**
  - `C:\png_v003`
  - `C:\dbg\top_op11_15.png`
  - `C:\gf_parts`
  - `C:\x\chk-4bk-k3-v005`

## User decisions not in the code

All decisions are in `jobs/4bk-k3/TASK.md`, dated 2026-11-15:
- After Artem accepts the geometry, it is frozen. Defects go to him as helpers, without QA loops.
- A UV/UCX use the accepted set: body v004, windows v003, roof v003.
- A long wall that overflows a UDIM tile is cut with full-height vertical loops (Connect), on the joints or about every 4 m.
- In a delivery, the main glass is always a separate object.
- RAL 020 30 20 = 104,64,58 is the truth.
- Стемалит, burgundy and the capsule are conventional colours; Artem chooses them.
- Known window defects go to a separate kanban card:
  - glass and grille without outline or embed;
  - frames too thin because the interiors were extruded from them.
- The UCX plan:
  - band envelopes, convex pieces;
  - bottom at −2.305;
  - roof slab and parapet ring are separate pieces;
  - the arcade stays free;
  - railing under 5 cm gets no UCX.
- The facade grid rule:
  - orthogonal edges where they serve joints;
  - one diagonal is better than a cut through the whole facade;
  - count thin strips.

  Mode: report-only, not blocking. Write it after acceptance.

## Waiting for the user

- **Address and naming, and the model rotation angle.** These block naming, GeoJSON, pivot and the full texture set.
- **Typical canopy model.** We will place it at the 10 Revit positions on A and B.
- **Box projection on diagonal facades.** Artem's brick UV is non-metric there (441 against 613 px/m). Is it a rule or an exception?
- **Merge PR #1443.** Waiting for Artem's command. The branch is 45 merges behind main.

## Next step

When Artem sends the canopy model or the address and rotation: place the canopies, then name A and B, set the pivot, write GeoJSON and package.

## Rules broken

- **QA loops on accepted geometry.** After Artem accepted A v004, five QA rounds (v005–v009) changed the accepted body and cost half a day. The memory line `accepted-geometry-freeze` was added.
- **First texture delivery of A was on v008e, not on the accepted v004.** Artem rejected it, and it was redone on v004.
- **The orthogonal-grid order made strips denser.** My instruction to cut body A to an orthogonal grid added dense thin strips. It was stopped and replaced by the frozen geometry.
- **The combined-scene agent read Artem's live Max sessions.** It made read-only queries there before Artem supplied the file paths.
- **A versioned file name was not used for the review scene.** Artem's A work was saved over our `_review\max\K3_A_tex_review_v003.max`, and his joints went into our maps in `textures_A_v003`. These were his own saves, not agent writes.
- **The B UCX re-check against Artem's geometry was skipped.** Artem checked it himself and accepted it.

## Open PRs and issues for this task

- #1443 job(4bk-k3): K3 floor 1 A + stylobate B VPM at 80 %. Open, waiting for the merge command.
- Retro `docs/retros/2026-11-15-4bk-k3-gf-stylobate.md`: issues #1445–#1451 (needs-triage, retro; all pass the
  ready gate). Already covered by #1365 and #1363. #1451 collects the decisions that need Artem's word, including the
  texel ≥ 520 px/m rule, which conflicts with [D160].

## Agent trace

- Sessions: `0a3a9c47-6962-4b43-a975-fa2a4cb6a4ab`
- Written by: -
- Subagents: general-purpose 13, independent-checker 5, source-inspector 1
- Skills: 3dsmax-mcp-dev 3, blender-mcp 1, revit-mcp 1, workflow-authoring 1
- Commands: none
- Hook denials: 4: mcp__revit-http-2025__revit_get_document_info - Load the `revit-mcp` skill first (Skill tool), follow it, then repeat this call ; mcp__revit-http-2025__revit_list_levels - Load the `revit-mcp` skill first (Skill tool), follow it, then repeat this call ; mcp__revit-http-2025__revit_list_categories - Load the `revit-mcp` skill first (Skill tool), follow it, then repeat this call ; mcp__revit-http-2025__revit_get_linked_files - Load the `revit-mcp` skill first (Skill tool), follow it, then repeat this call 
- Retries: none
- Context at handover: 32 % (325k of 1000k tokens)
- Duration: 26 h 44 min (2026-11-14T12:00:18Z - 2026-11-15T14:45:05Z, UTC)
- Commits: `bd842f97..6aa786d9` (7 commits)
