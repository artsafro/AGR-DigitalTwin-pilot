# Handoff — 2026-11-21 10:00

Branch: `job/staropetrovskiy-maf-npm-claude` · Commit: `83aa656c` · Worktree: `C:\Users\artsafro\.AGR-DigitalTwin_pilot\.claude\worktrees\max-2026-migration-b57e10` · Job: `staropetrovskiy-maf-npm (outside git: C:/x/staropetrovskiy-maf-claude)`
Transcript: `C:\Users\artsafro\.AGR-DigitalTwin_pilot\logs\transcripts\job-staropetrovskiy-maf-npm-claude-prnone-f8d74c21-7ff7-43cc-9d2d-abafcb37c0b9.jsonl`

<!-- Written by /handover (.claude/commands/handover.md), read by tools/hooks/session_context.py and /takeover.
Keep the `Branch:` line as is (the hook parses it). Facts only, no history: git log and the pull requests hold
that. The whole file stays under 7000 characters so the SessionStart hook passes it in full. Empty section: "-". -->

## Where we are

NPM + VPM Ground packages for «Старопетровский проезд, ZU_7_A» (customer Ground/Flora + our MAF + planter shrubs)
built and **sent to the customer by Artem (2026-11-20)**. All work files are outside git in
`C:/x/staropetrovskiy-maf-claude/`; this branch has no task commits (job is outside git by design).

- Delivered: `final_2026-11-20/NPM/0205_ProezdStaropetrovskyi_ZU_7_A.zip` (= `site4/package_v015`, blend `site4/npm_v015.blend`)
  and `final_2026-11-20/VPM/SM_ProezdStaropetrovskyi_ZU_7_A_Ground.zip` (= `site5/..._v007.zip`, blend `site5/vpm_v007.blend`).
- Verified with SINTEZ AGR Checker 1.6.1 headless (`site4/sintez_check/run_sintez_lp.py`, results
  `site4/sintez_check/result_lp_v015.json`, `site5/sintez_vpm/result_v007.json`): NPM fails only 2.1.1 signature +
  2.1.2 FBX count (no OKS); VPM fails only 2.1.1 signature + 2.2.6 ZU_area=0 recommendation (kept by Artem).
- NPM: 156,372 tris (Ground 10,938 / GroundEl 141,098 / Flora 4,336), MAF one `SM_..._GroundEl`, Standard material
  `M_..._GroundEl_1`, 512 atlas d/o/m/r, smoothing hard edges by 51°.
- VPM: one `SM_..._Ground` 791,863 tris (customer 566,349 + MAF 181,694 with doubled segments on round parts +
  313 shrubs 43,820), MAF tiles 1032-1048 (4K atlas + 5 oversize 4K + 11 solid 256 placeholders), scaled shrubs on 1049.
- Job notes / chronology: memory `staropetrovskiy-maf-npm-job.md`; scripts `site4/work/`, `site5/work/`.

## In progress

- Nothing open on the delivery. Local state outside git: `C:/x/staropetrovskiy-maf-claude/` (site4, site5, final_2026-11-20,
  vpm_in, npm_in) must be kept; several 3ds Max windows with site v006-v010 may still be open (read-only views).

## User decisions not in the code

- Planting spots = MAF faces whose UVs sit on the atlas sand cell (ID26_soil UV 0.5-0.625 x 0.25-0.375); MAF materials never change (Artem 2026-11-20).
- Planter shrubs = customer flora species, native 1.23 m; shrink only until no intersection, min 0.55 m; no plant-plant overlap (Artem 2026-11-20).
- NPM: three separate atlases (MAF / Flora / Ground); budget 180k for the whole Ground package (Artem 2026-11-20).
- No quad work FBX on this job (Artem 2026-11-20) — overrides D198 here.
- VPM: normal + ERM solid placeholders everywhere; solid MAF colours as 256 placeholders; patterned cells 4K; shrubs taken from the customer VPM FBX with Diffuse alpha; customer flora kept as is (Artem 2026-11-20).
- Frosted glass / polycarbonate (ID 31/38/39) stay in MAF, not GroundGlass (Artem 2026-11-20).
- Sintez recommendations are fixed too; only signature and missing-OKS may remain; geojson ZU_area left as the customer sent it (Artem 2026-11-20/21).

## Waiting for the user

- Customer feedback on the delivered packages.
- Four decisions in #1734 (Sintez recommendations policy, D198 scope, VPM MAF textures, GeoJSON).
- `.sig` signatures are not ours (D163).

## Next step

New task from Artem (2026-11-21): add this job's MAF to our MAF library (`library/maf/`) as NPM and VPM versions for reuse — start with task intake (sources: `site4/npm_v015.blend` GroundEl per-MAF split from library v003 masters, `site5/maf_vpm_uv_v003.blend`, atlas `site4/maps_npm`, `site5/vpm_maps_v004`).

## Rules broken

- Job worked outside git with no job card / passport (`jobs/<ID>/passport.json` not created) — known since 2026-11-12, still open.
- Branch `job/staropetrovskiy-maf-npm-claude` is 163 merges behind origin/main; validator run from the main checkout.
- Shown builds before the independent check in places (v005-v009 site scenes opened for Artem before readback); the delivery packages were checked (independent-checker on NPM v012, SINTEZ on every final).
- Retro: `docs/retros/2026-11-21-staropetrovskiy-npm-vpm.md` - 13 incidents; issues #1729-#1734 (needs-triage, retro).

## Open PRs and issues for this task

- No PR (nothing of the job is in git).
- Retro issues #1729 #1730 #1731 #1732 #1733 #1734 - open, needs-triage; #1734 holds four decisions for Artem.

## Agent trace

- Sessions: `f8d74c21-7ff7-43cc-9d2d-abafcb37c0b9`
- Written by: -
- Subagents: general-purpose 46, Explore 2, fork 1, independent-checker 1
- Skills: anthropic-skills:built-in-browser 2, 3dsmax-mcp-dev 1, anthropic-skills:chrome-browser 1
- Commands: none
- Hook denials: 2: mcp__blender__get_objects_summary - Load the `blender-mcp` skill first (Skill tool), follow it, then repeat this cal; mcp__3dsmax-mcp__list_max_instances - Load the `3dsmax-mcp-dev` skill first (Skill tool), follow it, then repeat this 
- Retries: none
- Context at handover: 55 % (554k of 1000k tokens)
- Duration: 214 h 12 min (2026-11-12T01:37:34Z - 2026-11-20T23:50:00Z, UTC)
- Commits: `83aa656c..83aa656c` (0 commits)
