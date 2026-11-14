# Handoff — 2026-11-14 12:00

Branch: `job/4bk-k3-vpm` · Commit: `fd538338` · Worktree: `C:\Users\artsafro\.AGR-DigitalTwin_pilot\.claude\worktrees\4bk-corpus-k3-modeling-6cfe72` · Job: `4bk-k3`
Transcript: `C:\Users\artsafro\.AGR-DigitalTwin_pilot\logs\transcripts\job-4bk-k3-vpm-prnone-d1636320-7403-4d5d-a4fb-b151aa37354d.jsonl`

<!-- Written by /handover (.claude/commands/handover.md), read by tools/hooks/session_context.py and /takeover.
Keep the `Branch:` line as is (the hook parses it). Facts only, no history: git log and the pull requests hold
that. The whole file stays under 7000 characters so the SessionStart hook passes it in full. Empty section: "-". -->

## Where we are

Job 4БК corpus K3 (A101/Astro1): VPM of the tower K3 and of the small stylobate (two separate VPM deliveries), NPM
later. Intake, passport, sources, Gate 1 (parts v001 confirmed) and all user decisions are committed in
`jobs/4bk-k3/` (TASK.md, SOURCE_ANALYSIS.md, STATE.md, job.yaml). The whole building is modelled (quads) and
UV-textured in headless Blender and assembled in Max: `…\63_4BK_vlad\build\3k_v004.max` (layer `K3_VPM_v001`).
Checks run per part in Blender (welds/embeds, coplanar overlaps, texel, joint positions); see STATE.md.

## In progress

- Artem is reviewing `3k_v004.max` in the viewport (joints on ID2/ID11/ID12, brick, stylobate windows, AC units).
- Local state outside git (must survive): build folder `C:\Users\artsafro\Desktop\!3D viz\!А101\63_4BK_vlad\build\`
  (3k_v001–v004.max, blender\K3_assembly_v001–v006.blend, fbx\, textures\); part blends, scripts and renders only in
  the session scratchpad `C:\Users\artsafro\AppData\Local\Temp\claude\1cc5c95fcc02bbdc\d1636320-7403-4d5d-a4fb-b151aa37354d\scratchpad\`
  (`4bk_parts\*`, `4bk_scripts\*`, `4bk_build\work\uv\uv_v002.py` = brick 38-course UV) — copy into `build\` before
  that temp folder is cleaned.
- Max 2026 (PID 563748) holds 3k_v004.max; a second Max (PID 570920) appeared mid-session — pin the PID and check
  `maxFileName` before writes. Nitrous texture size limit was raised to 4096 (global Max setting).
- Not done: xView in Max; split into two VPM packages; naming/address/GeoJSON; UDIM renumbering; NPM.

## User decisions not in the code

All recorded verbatim in `jobs/4bk-k3/TASK.md` (2026-11-12): brick 38 courses/floor; wedge bands = ID2 metal; niche
side walls brick, reveals unchanged; parts may join by embedding (smaller into larger, delete overlapped faces); АКП
joints 10 mm dark; stylobate = brick block right of the tower in «1 эт_2.jpg», all brick with joints by openings logic,
light plinth decision superseded («весь кирпичный»); two VPM deliveries; left-edge stacking joint method; tower АКП
3 tiles at 512 px/m.

## Waiting for the user

- Review of 3k_v004.max (joints visible? stylobate windows, AC units).
- K3_AC_17_10 raised to 52.90 vs Revit 52.20 — keep or as Revit?
- Open from earlier: 5 cm АКП strips at window edges (typ, Revit «кирпич_АКП») — keep?; superstructure wedges over
  windows in the brick zone ID2 vs brick (s1 shows brick); band joints at windows (±5 cm) and at 4 corners (0.3–0.5 m)
  vs drawing; terrace railing height 53.20 vs 1.1 m; stylobate roof at 5.048 vs Revit 5.20; stair 940 tris.
- Address, stem `SM_<Address>_NNN`, naming reference, GeoJSON (Artem: «дам позже»).

## Next step

After Artem's review of 3k_v004.max: apply his fixes, run xView in Max, then split into two VPM packages.

## Rules broken

- Gate 1 PartsList triangle budgets were exceeded silently by the assembly (~150.6 k vs 150 k target with stylobate);
  resolved by the two-VPM decision (tower ≈ 146 k), not re-measured per package.
- Window drafts (stylobate, 10 types) built outside `library/windows/drafts/` (K2 needs the preview sheet first) —
  noted in STATE.md, not added to the library.
- `/compact` was blocked by the PreCompact hook (stale handoff) — this handover fixes it.

## Open PRs and issues for this task

- No PR (mid-task, no push). Retro `docs/retros/2026-11-14-4bk-k3-modeling.md`: issues #1363, #1364, #1365, #1366,
  #1367 (needs-triage, retro); covered by #1326.

## Agent trace

- Sessions: `d1636320-7403-4d5d-a4fb-b151aa37354d`
- Written by: -
- Subagents: general-purpose 18, source-inspector 1
- Skills: 3dsmax-mcp-dev 1
- Commands: handover 1
- Hook denials: 1: mcp__3dsmax-mcp__list_max_instances - Load the `3dsmax-mcp-dev` skill first (Skill tool), follow it, then repeat this 
- Retries: none
- Context at handover: 62 % (624k of 1000k tokens)
- Duration: 47 h 59 min (2026-11-12T11:39:42Z - 2026-11-14T11:39:16Z, UTC)
- Commits: `5a9606d5..fd538338` (4 commits)
