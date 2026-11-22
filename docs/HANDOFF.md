# Handoff — 2026-11-22 23:47 +0100

Branch: `main` · Commit: `a3cba07c` · Worktree: `-` · Job: `-`
Transcript: -

<!-- Shared pilot main snapshot for takeover; not ownership of a consuming feature branch. -->

## Where we are

Goal: use the shared AGR routes and verify the intended shape, not just mesh topology.
- Pilot main `a3cba07c2b03a350ff6dc6601691734c94ab7470` includes #1796, #1787 Ground surfaces/skirt, #1791 Ground research in OBSERVE, #1777 library fix, #1782 decision IDs, #1785 light names, #1778 planter rules, #1754 MAF conversion and #1774 review scene. Ground kernel delivery is not complex delivery acceptance.
- **KNOWN RED:** non-DCC full suite `20261121j` on this exact main: 29,377 passed, 1 failed, 194 skipped, 49 xfailed. `tests/test_skills_sync.py::test_claude_skills_match_agents_skills`: `model-flora/SKILL.md: differs or missing`. #1796 fixed the canonical description but did not sync its generated `.claude/skills` copy. Last full green receipt was on `13e8235b` (29,266 passed), not current main. No CI or DCC pass implied.
- Prior handoff was specific to 4bk-k3, whose job records remain under `jobs/4bk-k3/`. The earlier PR #1443 is merged; do not replay its old handoff or operate on user scenes.

## In progress

- Production pause remains; only bounded, explicitly authorized work took place afterward. Do not resume broadly or start #1608 without separate authorization.
- KPP1 NW: local-only `49326e15` on `fix/kpp1-nw-measured-reveal-pilot` changes the research prototype, not shared #1770. Evidence: `C:/x/kpp1-nw-a-t_aadee92c/v002/REPORT.md`. FBX readback on the crop: 90 degrees on three slices, no stray north gap or crop caps, two open apertures and four measured 110 mm front jambs. Six focused tests and 542 guards passed; back reveals and post seating unmeasured. Original scene unchanged. No production acceptance or remote publication.
- Audit plan: `agr-pilot` card `t_8e7524e7` comment 9671 and CLEAN review 9672. Observed AC09 ZIP-owner bypass, stale Flora pointer, D336 category-check gap and conflicting handoff template. Cross-session memory import not reproduced. Held-out Codex test on another equivalent ambiguity not started. No runtime policy changes.

## User decisions not in the code

- 2026-11-22: "А, прямой угол" on KPP1 NW only: 90 degrees, no chamfer. SHEET v003, `KPP1-NW-A-v001.json`, SHA-256 `d4c18c361b2d5953b8a264fc289706a023be47a74df0c202c52071d4e2c1074f`. No approval of post seating, unmeasured backs or other corners. Contour comparison observe-only, no automatic repair.
- KPP1 stage 3 remains rejected; `s_podz` is empty per D306/V011, no #1608 run. G22: customer provides GeoJSON; retain the exterior and trim neighboring faces up to 275 mm under D374 only where exterior is known. Sixteen pairs still need a reference.
- Sokolniki: rings by volume, up to three floor levels, 20 cm snap, openings cut with separate textured planes in NPM. Do not build before sheet v002 approval or edit Ground.

## Waiting for the user

- #1649: corrected `mesh001` or exterior reference for the remaining 16 pairs (Kanban comment 9630). No release with xView FAIL.
- #1784: visual approval of sheet v002 and decision on local +2.175 m cuts for the 16 doors outside snap tolerance; see PR #1786.
- Production resume and cold run #1608 require explicit authorization.

## Next step

Keep the merge/work holds; reconcile the generated skill copy and retest on an authorized repair, then run the held-out contour test before promoting the pilot behavior.

## Rules broken

- KPP1 sheet and audit plan reached the default reviewer despite Codex-only scope. The later local pilot completed on Codex without handoff.
- #1796 omitted the generated skill copy, causing the integrated failure above. No production repair during handover.

## Open PRs and issues for this task

- #1770 `c97cf3ec`: shared body core, open; last explicit CLEAN named `ca865516`, before main reconciliation. Revalidate current head before merge. #1771 `052c4c28` and #1773 `055b0c7d` also open; #1770/#1773 touch the same skeleton entry.
- #1797 `5ad78d86`: Blender xView, 67 affected tests, local review on `t_35f403b8`. #1798 `d453175c`: native Max xView preflight, 141 offline tests, independent review pending; native smoke not run.
- #1794 G22 draft, #1786 Sokolniki sheet, #1722 63B stage 2 visual acceptance, #1792 draft (blocks #1781), #1793 library and #1795 Ground research open. #1315 not delivered.

## Agent trace

- Sessions: not measured (no transcript)
- Written by: Hermes orchestrator (shared main checkpoint)
- Subagents: not measured (no usage log, no transcript)
- Skills: not measured (no usage log, no transcript)
- Commands: not measured (no usage log, no transcript)
- Hook denials: not measured (no transcript)
- Retries: not measured (no transcript)
- Context at handover: not measured (no transcript)
- Duration: not measured (no transcript)
- Commits: `a3cba07c..a3cba07c` (0 commits)
